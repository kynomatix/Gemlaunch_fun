"""
Graduation Completion Service
Monitors for GraduationInitiated events and automatically completes graduation
"""

import logging
import time
import threading
from datetime import datetime, timezone
from models import Token, db
from services.web3_service import get_web3_service
from services.graduation_state_manager import GraduationStateManager

class GraduationCompletionService:
    """
    Automated graduation completion service
    Monitors blockchain for GraduationInitiated events and completes graduation
    """
    
    def __init__(self, app=None):
        """
        Initialize graduation completion service
        
        Args:
            app: Flask application instance (required for database access)
        """
        self.app = app
        self.w3_service = get_web3_service()
        self.running = False
        self.monitor_thread = None
        self.check_interval = 15  # Check every 15 seconds
        
        logging.info("GraduationCompletionService initialized")
    
    def start(self):
        """Start monitoring for graduations to complete"""
        if self.running:
            logging.warning("GraduationCompletionService already running")
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        logging.info("GraduationCompletionService started - monitoring for graduations")
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        logging.info("GraduationCompletionService stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop - runs in background thread"""
        while self.running:
            try:
                # Run database operations in app context
                if self.app:
                    with self.app.app_context():
                        self._check_and_complete_graduations()
                else:
                    logging.error("No Flask app provided - cannot run graduation completion")
                    break
            except Exception as e:
                logging.error(f"Error in graduation completion loop: {str(e)}")
            
            # Wait before next check
            time.sleep(self.check_interval)
    
    def _check_and_complete_graduations(self):
        """Check for pending graduations and complete them"""
        # Find tokens in 'initiating' status
        pending_tokens = Token.query.filter_by(graduation_status='initiating').all()
        
        if not pending_tokens:
            return
        
        logging.info(f"Found {len(pending_tokens)} tokens pending graduation completion")
        
        for token in pending_tokens:
            try:
                self._complete_single_graduation(token)
            except Exception as e:
                logging.error(f"Failed to complete graduation for {token.symbol}: {str(e)}")
    
    def _complete_single_graduation(self, token):
        """
        Complete graduation for a single token
        
        Steps:
        1. Verify initiation transaction succeeded
        2. Extract pool address and position ID from events
        3. Call GraduationController.completeGraduation
        4. Update token status to 'graduated'
        """
        logging.info(f"Completing graduation for {token.symbol} (ID: {token.id})")
        
        # 1. Verify initiation transaction
        if not token.graduation_initiation_tx:
            logging.error(f"Token {token.symbol} has no initiation tx - cannot complete")
            return
        
        # Get initiation transaction receipt
        try:
            receipt = self.w3_service.w3.eth.get_transaction_receipt(token.graduation_initiation_tx)
            
            if not receipt or receipt['status'] != 1:
                logging.error(f"Initiation tx {token.graduation_initiation_tx} failed - marking graduation as failed")
                GraduationStateManager.mark_failed(token, "Initiation transaction failed")
                return
        except Exception as e:
            logging.error(f"Could not get initiation tx receipt: {str(e)}")
            return
        
        # 2. Extract pool address and position ID from GraduationInitiated event
        pool_data = self._extract_pool_data_from_receipt(receipt, token)
        
        if not pool_data:
            logging.error(f"Could not extract pool data from initiation tx")
            GraduationStateManager.mark_failed(token, "Pool data extraction failed")
            return
        
        # 3. Call completeGraduation via oracle wallet
        try:
            result = GraduationStateManager.complete_graduation(
                token=token,
                oracle_wallet=self.w3_service.oracle_account,
                pool_address=pool_data['pool_address'],
                fee_tier=pool_data['fee_tier'],
                position_id=pool_data['position_id'],
                burned_amount=pool_data['burned_amount']
            )
            
            if result['success']:
                logging.info(f"✅ Graduation completed for {token.symbol} - TX: {result['tx_hash']}")
            else:
                logging.error(f"❌ Graduation completion failed for {token.symbol}: {result.get('error')}")
                
        except Exception as e:
            logging.error(f"Exception during graduation completion: {str(e)}")
            GraduationStateManager.mark_failed(token, str(e))
    
    def _extract_pool_data_from_receipt(self, receipt, token):
        """
        Extract pool address, fee tier, position ID, and burned amount from GraduationInitiated event
        
        Event GraduationInitiated(
            address indexed tokenAddress,
            address poolAddress,
            uint24 feeTier,
            uint256 positionId,
            uint256 burnedTokens
        )
        
        Returns:
            dict: {
                'pool_address': str,
                'fee_tier': int,
                'position_id': int,
                'burned_amount': int
            } or None if not found
        """
        try:
            graduation_controller = self.w3_service.contracts['GraduationController']
            
            # Get GraduationInitiated event signature
            event = graduation_controller.events.GraduationInitiated()
            
            # Process logs to find GraduationInitiated event
            for log in receipt['logs']:
                try:
                    # Try to decode log as GraduationInitiated
                    decoded = event.process_log(log)
                    
                    # Verify it's for this token
                    if decoded['args']['tokenAddress'].lower() == token.token_address.lower():
                        pool_data = {
                            'pool_address': decoded['args']['poolAddress'],
                            'fee_tier': decoded['args']['feeTier'],
                            'position_id': decoded['args']['positionId'],
                            'burned_amount': decoded['args']['burnedTokens']
                        }
                        
                        logging.info(f"Extracted pool data: pool={pool_data['pool_address']}, fee={pool_data['fee_tier']}, position={pool_data['position_id']}")
                        return pool_data
                        
                except Exception:
                    # Not a GraduationInitiated event, skip
                    continue
            
            logging.error(f"GraduationInitiated event not found in tx {receipt['transactionHash'].hex()}")
            return None
            
        except Exception as e:
            logging.error(f"Error extracting pool data: {str(e)}")
            return None

# Singleton instance
_graduation_completion_service = None

def get_graduation_completion_service(app=None):
    """
    Get or create graduation completion service singleton
    
    Args:
        app: Flask application instance (required for first call)
    """
    global _graduation_completion_service
    if _graduation_completion_service is None:
        if app is None:
            raise ValueError("Flask app must be provided when creating GraduationCompletionService")
        _graduation_completion_service = GraduationCompletionService(app=app)
    return _graduation_completion_service

def start_graduation_completion_service(app):
    """
    Start the graduation completion service
    
    Args:
        app: Flask application instance
    """
    service = get_graduation_completion_service(app=app)
    service.start()
    return service

def stop_graduation_completion_service():
    """Stop the graduation completion service"""
    service = get_graduation_completion_service()
    service.stop()
