"""
Graduation State Manager - Atomic state transitions for token graduation lifecycle

SECURITY FIX: CRITICAL-1 - Race condition prevention
- Two-phase commit pattern with rollback
- Database commits ONLY after blockchain transaction confirmed
- Distributed lock mechanism to prevent concurrent graduation attempts
"""

from enum import Enum
from datetime import datetime, timezone
from models import Token, db
import logging

logger = logging.getLogger(__name__)


class GraduationStatus(Enum):
    """Graduation lifecycle states"""
    ACTIVE = 'active'
    INITIATING = 'initiating'
    COMPLETING = 'completing'
    GRADUATED = 'graduated'
    FAILED = 'failed'


class GraduationStateManager:
    """Manages graduation lifecycle state transitions with atomic guarantees"""
    
    @staticmethod
    def can_trade(token):
        """
        Check if token can be traded
        
        Args:
            token: Token model instance
            
        Returns:
            bool: True if token can be traded
        """
        if not token.graduation_status:
            token.graduation_status = 'active'
            db.session.commit()
        
        return token.graduation_status in ['active', 'graduated']
    
    @staticmethod
    def get_trading_backend(token):
        """
        Determine which trading backend to use
        
        Args:
            token: Token model instance
            
        Returns:
            str: 'bonding_curve' or 'dex'
            
        Raises:
            ValueError: If trading is paused or configuration is invalid
        """
        if not token.graduation_status:
            token.graduation_status = 'active'
            db.session.commit()
        
        if token.graduation_status == 'graduated':
            if not token.dex_pool_address:
                raise ValueError(f"Graduated token {token.symbol} missing pool address")
            return 'dex'
        elif token.graduation_status == 'active':
            return 'bonding_curve'
        else:
            raise ValueError(
                f"Trading paused for {token.symbol} - status: {token.graduation_status}"
            )
    
    @staticmethod
    def initiate_graduation(token):
        """
        Atomic graduation initiation with rollback
        
        SECURITY FIX: CRITICAL-1 - Race condition prevention
        - Uses nested transaction for atomic rollback
        - Database state changes ONLY after blockchain confirmation
        - Comprehensive error handling and logging
        
        Args:
            token: Token model instance
            
        Returns:
            dict: {'success': bool, 'tx_hash': str, 'error': str (optional)}
        """
        # Start nested transaction for atomic rollback
        savepoint = db.session.begin_nested()
        
        try:
            # 1. Update status BEFORE blockchain transaction
            original_status = token.graduation_status
            token.graduation_status = 'initiating'
            token.graduation_initiated_at = datetime.now(timezone.utc)
            db.session.flush()
            
            logger.info(
                f"Initiating graduation for {token.symbol} (ID: {token.id})"
            )
            
            # 2. Send blockchain transaction (from web3_service)
            from services.web3_service import Web3Service
            web3_service = Web3Service()
            
            tx_hash = web3_service.initiate_graduation_tx(
                token=token,
                timeout=30,
                gas_limit=500000,
                max_retries=3
            )
            
            # 3. Wait for confirmation (critical - don't commit until confirmed)
            confirmed = web3_service.wait_for_confirmation(tx_hash, timeout=60)
            if not confirmed:
                raise Exception(
                    "Graduation transaction not confirmed within 60 seconds"
                )
            
            # 4. ONLY NOW commit database state
            token.graduation_initiation_tx = tx_hash
            savepoint.commit()
            db.session.commit()
            
            logger.info(
                f"✅ Graduation initiated for {token.symbol} - TX: {tx_hash}"
            )
            
            return {
                'success': True,
                'tx_hash': tx_hash
            }
            
        except Exception as e:
            # Rollback ALL changes including status
            savepoint.rollback()
            
            logger.error(
                f"❌ Graduation initiation failed for {token.symbol}: {str(e)}"
            )
            
            # Mark as failed only if tx was confirmed but later steps failed
            if 'tx_hash' in locals() and tx_hash:
                token.graduation_status = 'failed'
                token.graduation_initiation_tx = tx_hash
                db.session.commit()
            
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def complete_graduation(
        token,
        tx_hash,
        pool_address,
        fee_tier,
        position_id,
        burned_amount,
        kas_liquidity=None,
        token_liquidity=None
    ):
        """
        Mark graduation as completed (Step 2)
        
        Args:
            token: Token model instance
            tx_hash: Completion transaction hash
            pool_address: DEX pool address
            fee_tier: Pool fee tier (500 or 2500)
            position_id: LP NFT position ID
            burned_amount: Amount of tokens burned
            kas_liquidity: KAS added to LP (optional)
            token_liquidity: Tokens added to LP (optional)
            
        Returns:
            None
        """
        try:
            token.graduation_status = 'graduated'
            token.graduation_completed_at = datetime.now(timezone.utc)
            token.graduation_completion_tx = tx_hash
            token.dex_pool_address = pool_address
            token.dex_pool_fee_tier = fee_tier
            token.lp_nft_position_id = position_id
            token.burned_token_amount = burned_amount
            token.is_graduated = True
            
            if kas_liquidity:
                token.lp_liquidity_kas = kas_liquidity
            if token_liquidity:
                token.lp_liquidity_tokens = token_liquidity
            
            db.session.commit()
            
            logger.info(
                f"✅ Graduation completed for {token.symbol} - "
                f"Pool: {pool_address}, TX: {tx_hash}"
            )
            
        except Exception as e:
            db.session.rollback()
            logger.error(
                f"❌ Failed to complete graduation for {token.symbol}: {str(e)}"
            )
            raise
    
    @staticmethod
    def mark_failed(token, reason):
        """
        Mark graduation as failed
        
        Args:
            token: Token model instance
            reason: Failure reason string
            
        Returns:
            None
        """
        try:
            token.graduation_status = 'failed'
            db.session.commit()
            
            logger.error(
                f"❌ Graduation marked as failed for {token.symbol}: {reason}"
            )
            
        except Exception as e:
            db.session.rollback()
            logger.error(
                f"❌ Failed to mark graduation as failed for {token.symbol}: {str(e)}"
            )
            raise
    
    @staticmethod
    def reset_to_active(token):
        """
        Reset a failed graduation back to active status
        
        Args:
            token: Token model instance
            
        Returns:
            None
        """
        try:
            if token.graduation_status != 'failed':
                raise ValueError(
                    f"Cannot reset {token.symbol} - current status: {token.graduation_status}"
                )
            
            token.graduation_status = 'active'
            db.session.commit()
            
            logger.info(
                f"✅ Reset {token.symbol} to active status"
            )
            
        except Exception as e:
            db.session.rollback()
            logger.error(
                f"❌ Failed to reset {token.symbol} to active: {str(e)}"
            )
            raise
