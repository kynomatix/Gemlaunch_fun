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
        # Find tokens in 'initiating' status (excluding disabled tokens)
        pending_tokens = Token.query.filter_by(
            graduation_status='initiating',
            graduation_disabled=False
        ).all()
        
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
        Complete graduation for a single token using V4 GraduationController architecture
        
        V4 CORRECT FLOW: Oracle calls GraduationController.completeGraduation()
        
        THIS IS THE CORRECT ORDER:
        1. Oracle calls GC.completeGraduation(tokenAddress)
        2. GC creates LP on Kaspa Finance DEX (CRITICAL: LP creation FIRST)
        3. GC calls Pool.completeGraduation() as callback  
        4. Pool marks itself graduated (only after LP exists)
        5. Database synced from on-chain state
        
        SUCCESS METRIC: LP exists on Kaspa Finance before database marks graduated
        """
        logging.info(f"Completing graduation for {token.symbol} (ID: {token.id})")
        
        # 1. Verify on-chain graduation status before attempting completion
        try:
            checksum_address = self.w3_service.w3.to_checksum_address(token.contract_address)
            
            # Check BondingCurvePool.graduating() and graduated() to confirm token state
            pool = self.w3_service.get_bonding_pool_contract(checksum_address)
            graduating = pool.functions.graduating().call()
            graduated = pool.functions.graduated().call()
            
            # Case 1: Already graduated on-chain - verify LP exists before syncing database
            if graduated:
                logging.info(f"✅ Token {token.symbol} is already graduated on-chain!")
                
                # V4 FIX: Verify LP actually exists on Kaspa Finance before marking graduated
                gc = self.w3_service.contracts['GraduationController']
                try:
                    lp_address = gc.functions.uniswapPoolAddress(checksum_address).call()
                    
                    if lp_address == '0x0000000000000000000000000000000000000000':
                        logging.error(f"❌ Token {token.symbol} marked graduated but NO LP exists!")
                        logging.error(f"   This is a corrupted state - pool.graduated=true but LP not created")
                        logging.error(f"   Keeping DB status as 'initiating' to prevent false completion")
                        return
                    
                    logging.info(f"✅ LP verified on Kaspa Finance: {lp_address}")
                    
                except Exception as lp_check_error:
                    logging.error(f"Failed to verify LP exists: {str(lp_check_error)}")
                    logging.error(f"Cannot confirm LP creation - keeping DB as 'initiating'")
                    return
                
                # LP exists - safe to sync database
                logging.info(f"   Syncing database to match on-chain state...")
                from datetime import datetime, timezone
                token.graduation_status = 'graduated'
                token.is_graduated = True
                token.lp_pool_address = lp_address
                if not token.graduation_completed_at:
                    token.graduation_completed_at = datetime.now(timezone.utc)
                db.session.commit()
                
                logging.info(f"✅ {token.symbol} database status synced to graduated with LP {lp_address}")
                return
            
            # Case 2: Graduation not initiated on-chain - reset to active
            if not graduating:
                logging.warning(f"⚠️ Token {token.symbol} has DB status 'initiating' but on-chain graduating=False")
                logging.warning(f"   Resetting status to 'active' to trigger re-initiation.")
                GraduationStateManager.reset_to_active(token)
                return
            
            # Case 3: Graduation in progress - ready to complete
            logging.info(f"✅ On-chain check passed: {token.symbol} graduating={graduating}, ready to complete")
            
        except Exception as e:
            logging.error(f"On-chain verification failed: {str(e)}")
            return
        
        # 2. Call GraduationController.completeGraduation() via oracle (V4 CORRECT FLOW)
        try:
            logging.info(f"🚀 V4 FLOW: Calling GraduationController.completeGraduation() for {token.symbol}")
            
            # V4 CORRECT FLOW: Call GC which creates LP FIRST, then calls pool callback
            # SUCCESS METRIC: LP on Kaspa Finance before pool marks graduated
            tx_hash = self.w3_service.complete_graduation_via_controller(checksum_address)
            
            # Wait for confirmation
            receipt = self.w3_service.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if not receipt or receipt['status'] != 1:
                raise Exception(f"Completion transaction failed: {tx_hash}")
            
            logging.info(f"✅ Completion tx confirmed: {tx_hash}")
            logging.info(f"   Block: {receipt['blockNumber']}")
            
        except Exception as e:
            logging.error(f"Exception calling completeGraduation: {str(e)}")
            logging.info(f"Will retry on next cycle")
            return
        
        # 4. Extract pool data from GraduationCompleted event
        pool_data = self._extract_pool_data_from_completion(receipt, token)
        
        if not pool_data:
            logging.error(f"Could not extract pool data from completion event")
            logging.info(f"Will retry on next cycle")
            return
        
        # 5. Update database with completion data
        try:
            token.graduation_status = 'graduated'
            token.graduation_completed_at = datetime.now(timezone.utc)
            token.graduation_completion_tx = tx_hash.hex()
            token.dex_pool_address = pool_data.get('pool_address')
            token.lp_nft_position_id = pool_data.get('position_id')  # FIXED: Use correct column name
            token.dex_pool_fee_tier = pool_data.get('fee_tier')
            token.is_graduated = True  # Set legacy field for backward compatibility
            
            db.session.commit()
            
            logging.info(f"✅ {token.symbol} graduated successfully!")
            logging.info(f"   Pool: {pool_data.get('pool_address')}")
            logging.info(f"   Position ID: {pool_data.get('position_id')}")
            logging.info(f"   Fee Tier: {pool_data.get('fee_tier')}")
            
        except Exception as e:
            logging.error(f"Failed to update database: {str(e)}")
            db.session.rollback()
    
    def _extract_pool_data_from_completion(self, receipt, token):
        """
        Extract pool data from GraduationCompleted event
        
        Event GraduationCompleted(
            address indexed tokenAddress,
            uint256 liquidityPositionId,
            uint256 kasAdded,
            uint256 tokensAdded,
            uint256 timestamp
        )
        
        Returns:
            dict: {
                'pool_address': str (derived from CREATE2),
                'fee_tier': int (constant 2500),
                'position_id': int,
                'kas_added': int,
                'tokens_added': int
            } or None if not found
        """
        try:
            graduation_controller = self.w3_service.contracts['GraduationController']
            
            # Get GraduationCompleted event
            event = graduation_controller.events.GraduationCompleted()
            
            # Process logs to find GraduationCompleted event
            for log in receipt['logs']:
                try:
                    # Try to decode log as GraduationCompleted
                    decoded = event.process_log(log)
                    
                    # Verify it's for this token
                    if decoded['args']['tokenAddress'].lower() == token.contract_address.lower():
                        position_id = decoded['args']['liquidityPositionId']
                        kas_added = decoded['args']['kasAdded']
                        tokens_added = decoded['args']['tokensAdded']
                        
                        # Fee tier is constant from GraduationController
                        fee_tier = 2500
                        
                        # Derive pool address using CREATE2
                        pool_address = self._compute_pool_address(
                            token.contract_address,
                            fee_tier
                        )
                        
                        pool_data = {
                            'pool_address': pool_address,
                            'fee_tier': fee_tier,
                            'position_id': position_id,
                            'kas_added': kas_added,
                            'tokens_added': tokens_added
                        }
                        
                        logging.info(f"Extracted pool data: pool={pool_address}, fee={fee_tier}, position={position_id}")
                        return pool_data
                        
                except Exception:
                    # Not a GraduationCompleted event, skip
                    continue
            
            logging.error(f"GraduationCompleted event not found in tx {receipt['transactionHash'].hex()}")
            return None
            
        except Exception as e:
            logging.error(f"Error extracting pool data: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def _compute_pool_address(self, token_address, fee_tier):
        """
        Compute Kaspa Finance (Uniswap V3) pool address using CREATE2
        
        Pool address = CREATE2(
            factory_address,
            keccak256(abi.encode(token0, token1, fee)),
            POOL_INIT_CODE_HASH
        )
        """
        from web3 import Web3
        
        # Kaspa Finance addresses (from web3_service)
        wkas_address = self.w3_service.contracts['WKAS'].address
        
        # Determine token0 and token1 (sorted by address)
        if int(token_address, 16) < int(wkas_address, 16):
            token0 = token_address
            token1 = wkas_address
        else:
            token0 = wkas_address
            token1 = token_address
        
        # For now, return a placeholder since we need the factory address and init code hash
        # TODO: Get these constants from deployment or contract
        logging.warning(f"Pool address derivation not fully implemented - returning placeholder")
        
        # For now, we can query the pool address from the blockchain
        # The GraduationController should have a getter function
        try:
            grad_controller = self.w3_service.contracts['GraduationController']
            # Try to get graduation info
            info = grad_controller.functions.getGraduationInfo(token_address).call()
            # info should contain the pool address
            # The exact structure depends on the contract
            logging.info(f"Graduation info: {info}")
            
            # Return placeholder for now
            return "0x0000000000000000000000000000000000000000"
        except Exception as e:
            logging.error(f"Could not query pool address: {str(e)}")
            return "0x0000000000000000000000000000000000000000"

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
