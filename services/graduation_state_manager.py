"""
Graduation State Management Service
Manages token graduation lifecycle with atomic state transitions
"""

from enum import Enum
from datetime import datetime, timezone
from models import Token, db
import threading
import logging

class GraduationStatus(Enum):
    """Graduation lifecycle states"""
    ACTIVE = 'active'
    INITIATING = 'initiating'
    COMPLETING = 'completing'
    GRADUATED = 'graduated'
    FAILED = 'failed'

class GraduationStateManager:
    """Manages graduation lifecycle state transitions with atomic guarantees"""
    
    # Distributed lock for preventing concurrent graduations
    _graduation_locks = {}  # token_id -> threading.Lock
    _lock_manager = threading.Lock()
    
    @classmethod
    def _get_token_lock(cls, token_id):
        """Get or create lock for specific token"""
        with cls._lock_manager:
            if token_id not in cls._graduation_locks:
                cls._graduation_locks[token_id] = threading.Lock()
            return cls._graduation_locks[token_id]
    
    @staticmethod
    def can_trade(token):
        """Check if token can be traded"""
        return token.graduation_status in ['active', 'graduated']
    
    @staticmethod
    def get_trading_backend(token):
        """
        Determine which trading backend to use
        
        Returns:
            str: 'bonding_curve' or 'dex'
        
        Raises:
            ValueError: If trading is paused or pool address missing
        """
        if token.graduation_status == 'graduated':
            if not token.dex_pool_address:
                raise ValueError("Graduated token missing pool address")
            return 'dex'
        elif token.graduation_status == 'active':
            return 'bonding_curve'
        else:
            raise ValueError(f"Trading paused - status: {token.graduation_status}")
    
    @classmethod
    def initiate_graduation(cls, token, oracle_wallet):
        """
        Atomically initiate graduation with blockchain transaction
        
        CRITICAL: Uses two-phase commit to prevent state corruption
        
        Args:
            token: Token object to graduate
            oracle_wallet: Platform oracle wallet for transactions
        
        Returns:
            dict: {'success': bool, 'tx_hash': str, 'error': str}
        """
        lock = cls._get_token_lock(token.id)
        
        with lock:  # Prevent concurrent graduation attempts
            # Verify preconditions
            if token.graduation_status != 'active':
                return {
                    'success': False,
                    'error': f"Cannot graduate token in status: {token.graduation_status}"
                }
            
            # Begin nested transaction (savepoint)
            db.session.begin_nested()
            
            tx_hash = None  # Initialize to avoid unbound errors
            
            try:
                # 1. Update status OPTIMISTICALLY (not committed yet)
                token.graduation_status = 'initiating'
                token.graduation_initiated_at = datetime.now(timezone.utc)
                
                # 2. Send blockchain transaction BEFORE committing database
                from services.web3_service import get_web3_service
                web3_service = get_web3_service()
                
                tx_hash = web3_service.send_graduation_initiation_tx(
                    token=token,
                    oracle_wallet=oracle_wallet,
                    timeout=30  # 30 second timeout
                )
                
                # 3. Wait for blockchain confirmation
                receipt = web3_service.wait_for_confirmation(tx_hash, timeout=60)
                
                if not receipt or receipt['status'] != 1:
                    raise Exception(f"Initiation transaction failed: {tx_hash}")
                
                # 4. NOW commit database state (atomic with tx success)
                token.graduation_initiation_tx = tx_hash
                db.session.commit()
                
                logging.info(f"Graduation initiated for {token.symbol}: {tx_hash}")
                
                return {'success': True, 'tx_hash': tx_hash}
                
            except Exception as e:
                # Rollback ALL changes including status
                db.session.rollback()
                
                logging.error(f"Graduation initiation failed for {token.symbol}: {str(e)}")
                
                # Only mark as failed if transaction was actually sent
                if 'tx_hash' in locals() and tx_hash:
                    token.graduation_status = 'failed'
                    token.graduation_initiation_tx = tx_hash
                    db.session.commit()
                
                return {'success': False, 'error': str(e)}
    
    @classmethod
    def complete_graduation(cls, token, oracle_wallet, pool_address, fee_tier, position_id, burned_amount):
        """
        Atomically complete graduation with blockchain transaction
        
        CRITICAL: Uses two-phase commit pattern
        
        Args:
            token: Token object
            oracle_wallet: Platform oracle wallet
            pool_address: DEX pool contract address
            fee_tier: Pool fee tier (500, 2500, 3000, 10000)
            position_id: LP NFT position ID
            burned_amount: Amount of unsold tokens burned
        
        Returns:
            dict: {'success': bool, 'tx_hash': str, 'error': str}
        """
        lock = cls._get_token_lock(token.id)
        
        with lock:
            # Verify preconditions
            if token.graduation_status not in ['initiating', 'completing']:
                return {
                    'success': False,
                    'error': f"Cannot complete graduation from status: {token.graduation_status}"
                }
            
            db.session.begin_nested()
            
            tx_hash = None  # Initialize to avoid unbound errors
            
            try:
                # 1. Update status optimistically
                token.graduation_status = 'completing'
                
                # 2. Send completion transaction
                from services.web3_service import get_web3_service
                web3_service = get_web3_service()
                
                tx_hash = web3_service.send_graduation_completion_tx(
                    token=token,
                    oracle_wallet=oracle_wallet,
                    timeout=30
                )
                
                # 3. Wait for confirmation
                receipt = web3_service.wait_for_confirmation(tx_hash, timeout=120)  # 2 min
                
                if not receipt or receipt['status'] != 1:
                    raise Exception(f"Completion transaction failed: {tx_hash}")
                
                # 4. Commit all changes atomically
                token.graduation_status = 'graduated'
                token.graduation_completed_at = datetime.now(timezone.utc)
                token.graduation_completion_tx = tx_hash
                token.dex_pool_address = pool_address
                token.dex_pool_fee_tier = fee_tier
                token.lp_nft_position_id = position_id
                token.burned_token_amount = burned_amount
                token.is_graduated = True  # Legacy field
                db.session.commit()
                
                logging.info(f"Graduation completed for {token.symbol}: {tx_hash}")
                
                return {'success': True, 'tx_hash': tx_hash}
                
            except Exception as e:
                db.session.rollback()
                logging.error(f"Graduation completion failed for {token.symbol}: {str(e)}")
                
                # Mark as failed
                token.graduation_status = 'failed'
                if 'tx_hash' in locals() and tx_hash:
                    token.graduation_completion_tx = tx_hash
                db.session.commit()
                
                return {'success': False, 'error': str(e)}
    
    @staticmethod
    def mark_failed(token, reason):
        """Mark graduation as failed"""
        token.graduation_status = 'failed'
        logging.error(f"Token {token.symbol} graduation marked failed: {reason}")
        db.session.commit()
    
    @staticmethod
    def check_stuck_graduations():
        """
        Monitor for stuck graduations and alert
        
        Run this periodically (every 5 minutes) to detect issues
        
        Returns:
            list: List of stuck Token objects
        """
        from datetime import timedelta
        stuck_threshold = datetime.now(timezone.utc) - timedelta(minutes=10)
        
        stuck_tokens = Token.query.filter(
            Token.graduation_status.in_(['initiating', 'completing']),
            Token.graduation_initiated_at < stuck_threshold
        ).all()
        
        for token in stuck_tokens:
            logging.critical(
                f"STUCK GRADUATION DETECTED: {token.symbol} (ID: {token.id}) - "
                f"Status: {token.graduation_status}"
            )
            # TODO: Send alert to monitoring system
        
        return stuck_tokens
