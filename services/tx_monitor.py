"""
Transaction Monitor Service
Monitors pending blockchain transactions and provides status updates
"""

import logging
from datetime import datetime, timedelta, timezone
from models import db, PendingTransaction
from services.web3_service import get_web3_service

class TransactionMonitor:
    """Service for monitoring pending blockchain transactions"""
    
    def __init__(self):
        """Initialize transaction monitor with web3 service"""
        self.web3_service = get_web3_service()
        logging.info("TransactionMonitor initialized")
    
    def check_pending_transactions(self):
        """Check status of all pending transactions from last 24 hours"""
        try:
            # Get pending txs from last 24 hours
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            pending_txs = PendingTransaction.query.filter(
                PendingTransaction.status == 'pending',
                PendingTransaction.created_at >= cutoff
            ).all()
            
            logging.info(f"Checking {len(pending_txs)} pending transactions")
            
            for tx in pending_txs:
                self.check_transaction_status(tx)
                
            return len(pending_txs)
            
        except Exception as e:
            logging.error(f"Error checking pending transactions: {str(e)}")
            return 0
    
    def check_transaction_status(self, tx):
        """Check single transaction status and update database"""
        try:
            # Get transaction receipt from blockchain
            receipt = self.web3_service.w3.eth.get_transaction_receipt(tx.tx_hash)
            
            if receipt:
                # Transaction confirmed or failed
                tx.status = 'confirmed' if receipt['status'] == 1 else 'failed'
                tx.confirmed_at = datetime.now(timezone.utc)
                tx.block_number = receipt['blockNumber']
                tx.gas_used = receipt['gasUsed']
                
                if receipt['status'] != 1:
                    tx.error_message = 'Transaction reverted'
                else:
                    # Handle successful transaction callbacks
                    self._handle_confirmed_transaction(tx, receipt)
                
                db.session.commit()
                logging.info(f"Transaction {tx.tx_hash[:10]}... {tx.status} at block {tx.block_number}")
                return True
            
            return False
            
        except Exception as e:
            # Transaction still pending or RPC error
            logging.debug(f"Transaction {tx.tx_hash[:10]}... still pending: {str(e)}")
            return False
    
    def _handle_confirmed_transaction(self, tx, receipt):
        """Handle post-confirmation actions for different transaction types"""
        try:
            if tx.tx_type == 'deploy_vesting':
                self._handle_vesting_deployment_confirmed(tx, receipt)
        except Exception as e:
            logging.error(f"Error handling confirmed transaction {tx.tx_hash}: {str(e)}")
    
    def _handle_vesting_deployment_confirmed(self, tx, receipt):
        """Handle confirmed vesting deployment transaction"""
        try:
            from models import Token
            
            if not tx.token_id:
                logging.error(f"Vesting deployment tx {tx.tx_hash} has no token_id")
                return
            
            token = Token.query.get(tx.token_id)
            if not token:
                logging.error(f"Token {tx.token_id} not found for vesting deployment {tx.tx_hash}")
                return
            
            logging.info(f"🎉 Vesting deployment confirmed for token {token.id} ({token.symbol})")
            
            # Extract vesting addresses from receipt
            vesting_addresses = self.web3_service.extract_vesting_addresses_from_receipt(tx.tx_hash)
            
            # Update token with vesting addresses
            token.marketing_vesting_address = vesting_addresses.get('marketing_vesting_address')
            token.team_vesting_address = vesting_addresses.get('team_vesting_address')
            token.airdrop_vesting_address = vesting_addresses.get('airdrop_vesting_address')
            token.vesting_deployment_status = 'deployed'
            
            logging.info(f"✅ Vesting addresses saved:")
            logging.info(f"  Marketing: {token.marketing_vesting_address}")
            logging.info(f"  Team: {token.team_vesting_address}")
            logging.info(f"  Airdrop: {token.airdrop_vesting_address}")
            
            # Now submit reserve transfer transaction (non-blocking)
            try:
                transfer_tx_hash = self.web3_service.transfer_reserves_to_vesting_async(
                    pool_address=token.contract_address,
                    marketing_vesting=token.marketing_vesting_address,
                    team_vesting=token.team_vesting_address,
                    airdrop_vesting=token.airdrop_vesting_address
                )
                
                if transfer_tx_hash:
                    logging.info(f"🚀 Reserve transfer tx submitted: {transfer_tx_hash}")
                    
                    # Add transfer tx to monitor
                    transfer_pending_tx = PendingTransaction(
                        tx_hash=transfer_tx_hash,
                        tx_type='transfer_reserves',
                        user_address=tx.user_address,
                        token_id=token.id,
                        status='pending',
                        created_at=datetime.now(timezone.utc)
                    )
                    db.session.add(transfer_pending_tx)
                    
            except Exception as e:
                logging.error(f"Failed to submit reserve transfer: {str(e)}")
            
            db.session.commit()
            
        except Exception as e:
            logging.error(f"Error handling vesting deployment confirmation: {str(e)}")
            db.session.rollback()
    
    def add_pending_transaction(self, tx_hash, tx_type, user_address, token_id=None):
        """Add new pending transaction to monitor
        
        Args:
            tx_hash: Transaction hash
            tx_type: Type of transaction (buy, sell, claim_fees, distribute_fees, deploy_token)
            user_address: User's wallet address
            token_id: Optional token ID
            
        Returns:
            PendingTransaction object or None if failed
        """
        try:
            # Check if transaction already exists
            existing_tx = PendingTransaction.query.filter_by(tx_hash=tx_hash).first()
            if existing_tx:
                logging.warning(f"Transaction {tx_hash[:10]}... already being monitored")
                return existing_tx
            
            # Create new pending transaction
            pending_tx = PendingTransaction(
                tx_hash=tx_hash,
                tx_type=tx_type,
                user_address=user_address.lower() if user_address else None,
                token_id=token_id,
                status='pending'
            )
            
            db.session.add(pending_tx)
            db.session.commit()
            
            logging.info(f"Added pending transaction {tx_hash[:10]}... (type: {tx_type})")
            return pending_tx
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Failed to add pending transaction: {str(e)}")
            return None
    
    def get_transaction_status(self, tx_hash):
        """Get transaction status from database or blockchain
        
        Args:
            tx_hash: Transaction hash
            
        Returns:
            dict with status information
        """
        try:
            # First check database
            tx = PendingTransaction.query.filter_by(tx_hash=tx_hash).first()
            
            if tx:
                # Transaction found in database
                return {
                    'success': True,
                    'status': tx.status,
                    'tx_type': tx.tx_type,
                    'tx_hash': tx.tx_hash,
                    'user_address': tx.user_address,
                    'token_id': tx.token_id,
                    'created_at': tx.created_at.isoformat() if tx.created_at else None,
                    'confirmed_at': tx.confirmed_at.isoformat() if tx.confirmed_at else None,
                    'block_number': tx.block_number,
                    'gas_used': tx.gas_used,
                    'error_message': tx.error_message
                }
            
            # Transaction not in database, check blockchain directly
            try:
                receipt = self.web3_service.w3.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    return {
                        'success': True,
                        'status': 'confirmed' if receipt['status'] == 1 else 'failed',
                        'tx_hash': tx_hash,
                        'block_number': receipt['blockNumber'],
                        'gas_used': receipt['gasUsed']
                    }
            except Exception as e:
                logging.debug(f"Transaction {tx_hash[:10]}... not found on blockchain: {str(e)}")
            
            # Transaction not found anywhere, assume pending
            return {
                'success': True,
                'status': 'pending',
                'tx_hash': tx_hash
            }
            
        except Exception as e:
            logging.error(f"Error getting transaction status: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


# Global transaction monitor instance
_tx_monitor = None

def get_tx_monitor():
    """Get or create the global transaction monitor instance"""
    global _tx_monitor
    if _tx_monitor is None:
        _tx_monitor = TransactionMonitor()
    return _tx_monitor
