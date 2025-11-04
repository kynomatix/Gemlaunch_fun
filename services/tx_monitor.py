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
                    # Handle failed transaction callbacks (e.g., update token status)
                    self._handle_failed_transaction(tx, receipt)
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
            # Immediately index transaction so it appears in recent trades
            from services.event_indexer import index_transaction_immediately
            index_result = index_transaction_immediately(tx.tx_hash)
            if index_result.get('success'):
                logging.info(f"✅ Immediately indexed confirmed tx: {tx.tx_hash[:10]}...")
            else:
                logging.warning(f"Failed to immediately index tx {tx.tx_hash[:10]}...: {index_result.get('error')}")
        except Exception as e:
            logging.error(f"Error handling confirmed transaction {tx.tx_hash}: {str(e)}")
    
    def _handle_failed_transaction(self, tx, receipt):
        """Handle failed transaction callbacks to update token/user state"""
        try:
            # No transaction types to handle currently
            pass
        except Exception as e:
            logging.error(f"Error handling failed transaction {tx.tx_hash}: {str(e)}")
            
            # Clear the vesting tx hash so it can be retried
            # (Keep it for debugging: token.vesting_deployment_tx = None)
            
            logging.info(f"Token {token.id} vesting_deployment_status set to 'failed' - can be retried manually")
            
            db.session.commit()
            
        except Exception as e:
            logging.error(f"Error handling vesting deployment failure: {str(e)}")
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
