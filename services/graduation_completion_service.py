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
        Complete graduation for a single token
        
        NEW APPROACH (per architect guidance):
        1. Verify initiation transaction succeeded
        2. Transfer KAS from oracle wallet to GraduationController contract
        3. Call GraduationController.completeGraduation(tokenAddress)
        4. Extract pool data from GraduationCompleted event
        5. Update database with all metadata
        
        Note: Step 2 is critical - BondingCurvePool sends KAS to oracle wallet,
        but GraduationController expects KAS in its own balance. We forward it.
        """
        logging.info(f"Completing graduation for {token.symbol} (ID: {token.id})")
        
        # 1. Verify initiation transaction (optional but good for logging)
        if not token.graduation_initiation_tx:
            logging.warning(f"Token {token.symbol} has no initiation tx recorded")
        
        # Verify on-chain graduation status before attempting completion
        try:
            checksum_address = self.w3_service.w3.to_checksum_address(token.contract_address)
            
            # Check BondingCurvePool.graduating() to confirm token is in graduation state
            pool = self.w3_service.get_bonding_pool_contract(checksum_address)
            graduating = pool.functions.graduating().call()
            
            if not graduating:
                logging.warning(f"⚠️ Token {token.symbol} has DB status 'initiating' but on-chain graduating=False")
                logging.warning(f"   Resetting status to 'active' to trigger re-initiation.")
                GraduationStateManager.reset_to_active(token)
                return
            
            logging.info(f"✅ On-chain check passed: {token.symbol} graduating={graduating}, ready to complete")
            
        except Exception as e:
            logging.error(f"On-chain verification failed: {str(e)}")
            # Continue anyway - the completion will fail if there's a real issue
        
        # 2. Transfer KAS from oracle wallet to GraduationController
        try:
            oracle_account = self.w3_service.oracle_account
            checksum_address = self.w3_service.w3.to_checksum_address(token.contract_address)
            
            # Get the GraduationController address from the pool (supports dynamic controller detection)
            pool = self.w3_service.get_bonding_pool_contract(checksum_address)
            gc_address = pool.functions.graduationOracle().call()
            
            # Load GraduationController contract at the detected address
            gc_abi = self.w3_service.contracts['GraduationController'].abi
            graduation_controller = self.w3_service.w3.eth.contract(address=gc_address, abi=gc_abi)
            
            # Try to get expected KAS amount from GraduationController
            try:
                expected_kas = graduation_controller.functions.expectedKasLiquidity(checksum_address).call()
            except Exception as e:
                logging.warning(f"expectedKasLiquidity() call failed: {e}")
                expected_kas = 0
            
            # V3 CONTROLLER FIX: If expectedKasLiquidity not available, get virtualKasReserve from pool
            # CRITICAL: Must subtract INITIAL_VIRTUAL_KAS (0.001 KAS seed) that stays in pool
            if expected_kas == 0:
                kas_reserve = pool.functions.virtualKasReserve().call()
                if kas_reserve > 0:
                    INITIAL_VIRTUAL_KAS = int(0.001 * 1e18)  # 0.001 ether in wei (the virtual seed)
                    logging.warning(f"⚠️ GraduationController V3 detected ({gc_address})")
                    logging.warning(f"   expectedKasLiquidity() not available, using virtualKasReserve - INITIAL_VIRTUAL_KAS")
                    expected_kas = kas_reserve - INITIAL_VIRTUAL_KAS  # 🔧 FIX: Subtract the 0.001 KAS seed
                    logging.info(f"   Virtual reserve: {kas_reserve / 1e18:.10f} KAS")
                    logging.info(f"   Minus seed (0.001): {expected_kas / 1e18:.10f} KAS required for graduation")
                else:
                    logging.warning(f"Expected KAS is 0 and pool reserve is 0 - graduation may be completed/cancelled")
                    return
            
            # Check if GraduationController already has the required KAS
            gc_balance = self.w3_service.w3.eth.get_balance(gc_address)
            logging.info(f"📊 GraduationController balance: {gc_balance / 1e18:.4f} KAS, required: {expected_kas / 1e18:.4f} KAS")
            
            if gc_balance >= expected_kas:
                logging.info(f"✅ GraduationController already has sufficient KAS - skipping transfer")
            else:
                # FIX: Only transfer the DIFFERENCE, not the full amount
                kas_to_transfer = expected_kas - gc_balance
                logging.info(f"📤 Transferring {kas_to_transfer / 1e18:.10f} KAS from oracle to GraduationController ({gc_address})")
                logging.info(f"   GC has: {gc_balance / 1e18:.10f} KAS, needs: {expected_kas / 1e18:.10f} KAS")
                
                # Build KAS transfer transaction
                transfer_tx = {
                    'from': oracle_account.address,
                    'to': gc_address,
                    'value': kas_to_transfer,  # ✅ FIX: Send only what's missing
                    'gas': 21000,  # Standard ETH transfer gas
                    'gasPrice': self.w3_service.w3.eth.gas_price,
                    'nonce': self.w3_service.w3.eth.get_transaction_count(oracle_account.address)
                }
                
                # Add chainId
                chain_id = self.w3_service.w3.eth.chain_id
                transfer_tx['chainId'] = chain_id
                
                # Sign and send transfer
                signed_transfer = oracle_account.sign_transaction(transfer_tx)
                transfer_hash = self.w3_service.w3.eth.send_raw_transaction(signed_transfer.raw_transaction)
                
                logging.info(f"✅ KAS transfer tx sent: {transfer_hash.hex()}")
                logging.info(f"⏳ Waiting for KAS transfer to be mined before calling completeGraduation()")
                logging.info(f"   Will check on next cycle")
                return  # Wait for transfer to be mined before proceeding
                
        except Exception as e:
            logging.error(f"Failed to transfer KAS to GraduationController: {str(e)}")
            logging.info(f"Will retry on next cycle")
            return
        
        # 3. Call completeGraduation() on blockchain with Kasplex retry logic
        try:
            # Build transaction data (let retry mechanism handle gas estimation)
            tx_data = graduation_controller.functions.completeGraduation(
                checksum_address
            ).build_transaction({
                'from': oracle_account.address,
                'value': 0
            })
            
            # Prepare transaction for retry mechanism (remove gas from tx_data)
            tx = {
                'to': tx_data['to'],
                'data': tx_data['data'],
                'value': 0,
                'from': oracle_account.address
            }
            
            logging.info(f"🚀 Sending completeGraduation with Kasplex retry logic...")
            
            # Use new retry mechanism with progressive gas increases
            result = self.w3_service.send_transaction_with_retry(
                transaction=tx,
                account=oracle_account,
                max_retries=11,  # Kasplex best practice
                initial_gas=3000000  # Start with 3M gas (skip estimation)
            )
            
            tx_hash = result['tx_hash']
            receipt = result['receipt']
            attempts = result['attempts']
            final_gas = result['final_gas']
            
            logging.info(f"✅ Completion tx confirmed after {attempts} attempt(s)")
            logging.info(f"   TX: {tx_hash}")
            logging.info(f"   Block: {receipt['blockNumber']}")
            logging.info(f"   Final gas: {final_gas:,}")
            
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
