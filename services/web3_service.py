"""
Web3 Service for Blockchain Integration
Handles RPC connections, contract interactions, and transaction relay
"""

import os
import json
import logging
import time
from pathlib import Path
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account
from eth_account.messages import encode_defunct

from services import v3_quoter

# Kasplex Testnet Configuration
KASPLEX_TESTNET_RPC = "https://rpc.kasplextest.xyz"
KASPLEX_TESTNET_CHAIN_ID = 167012

# RPC Fallback Endpoints (add more when available)
RPC_ENDPOINTS = [
    'https://rpc.kasplextest.xyz',
    # Add fallback RPCs here when available
]

# Deployed Contract Addresses (Kasplex Testnet - October 2025)
# SOURCE OF TRUTH: contracts/deployed_addresses.json
TOKEN_FACTORY_ADDRESS = "0x3abF3c17a89687FF449DD1aa24A1C159eD4f5F07"  # V12 - Oct 28, 2025 - MAX_WALLET_PCT FIX (GC V13)
VESTING_DEPLOYER_ADDRESS = "0x69AC4E0235757B6E81072A13E79c67aD964A9c21"  # Auto-deployed with TokenFactory V7
GRADUATION_CONTROLLER_ADDRESS = "0xf04aB5deE799DDb217a03bF07fFf4dDf541dD9f1"  # V13 - Oct 28, 2025 - FINAL FIX: IERC721Receiver (no pure) + unsafe transferFrom
AIRDROP_DISTRIBUTOR_ADDRESS = "0x86b83FE03cDa7456980364c929BB17CFA67E8495"  # Batch airdrop helper

# Kaspa Finance DEX Addresses (Kasplex Testnet)
KASPA_FINANCE_FACTORY = "0x1b72D7165a0D7256a4F197765C15bb70bC5D66A8"
KASPA_FINANCE_NFT_POSITION_MANAGER = "0x4E25637cF39822364b877F81B18c5B6CF0eeF589"
KASPA_FINANCE_WKAS = "0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94"
KASPA_FINANCE_SWAP_ROUTER = "0xDf88D478aF51C0AB616aFBfDD933c874e142858c"
KASPA_FINANCE_QUOTER_V2 = "0xE0EE9e756CB67f49326DCEf98e24e1231F26Ce70"  # Deployed Oct 28 (Mirza's has no bytecode)

# Fee tiers for Kaspa Finance (Uniswap V3 compatible)
FEE_TIER_005 = 500    # 0.05%
FEE_TIER_025 = 2500   # 0.25%
FEE_TIER_030 = 3000   # 0.30%
FEE_TIER_100 = 10000  # 1.00%

# Contract ABI paths
ARTIFACTS_DIR = Path("artifacts/contracts")

class Web3Service:
    """Main service for Web3 blockchain interactions"""
    
    def __init__(self):
        """Initialize Web3Service with RPC fallback support"""
        # Use fallback mechanism instead of single RPC
        self.w3 = get_web3_with_fallback()
        
        # Store contract addresses for security verification
        self.token_factory_address = TOKEN_FACTORY_ADDRESS
        
        # Check if we're in offline mode
        self.is_connected = self.w3.is_connected()
        
        # Rest of initialization
        self.deployer_account = self._init_deployer_account()
        self.oracle_account = self._init_oracle_account()
        self.contracts = self._load_contracts()
        
        if self.is_connected:
            logging.info(f"Web3Service initialized - Chain ID: {self.w3.eth.chain_id}")
        else:
            logging.warning("⚠️ Web3Service initialized in OFFLINE mode - blockchain features disabled")
    
    def ensure_connected(self):
        """Check if blockchain is available, raise error if not"""
        if not self.is_connected:
            raise ConnectionError("Blockchain RPC is currently unavailable. Please try again later.")
        
    def _init_web3(self):
        """Initialize Web3 provider connection"""
        try:
            w3 = Web3(Web3.HTTPProvider(KASPLEX_TESTNET_RPC))
            
            # Add PoA middleware for Kasplex (if needed)
            w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            
            # Verify connection
            if not w3.is_connected():
                raise Exception(f"Failed to connect to RPC: {KASPLEX_TESTNET_RPC}")
            
            # Verify chain ID
            chain_id = w3.eth.chain_id
            if chain_id != KASPLEX_TESTNET_CHAIN_ID:
                logging.warning(f"Chain ID mismatch: expected {KASPLEX_TESTNET_CHAIN_ID}, got {chain_id}")
            
            logging.info(f"Connected to Kasplex Testnet RPC - Chain ID: {chain_id}")
            return w3
            
        except Exception as e:
            logging.error(f"Failed to initialize Web3: {str(e)}")
            raise
    
    def _derive_secondary_wallet(self, deployer_private_key):
        """
        Derive secondary wallet from deployer private key
        Uses same method as deployment scripts:
        keccak256("GEMLAUNCH_SECONDARY_WALLET" + deployer_private_key)
        """
        try:
            # Normalize private key (ensure 0x prefix)
            if not deployer_private_key.startswith('0x'):
                deployer_private_key = f'0x{deployer_private_key}'
            
            # Derive secondary key: keccak256("GEMLAUNCH_SECONDARY_WALLET" + deployer_key)
            seed_text = "GEMLAUNCH_SECONDARY_WALLET"
            seed_bytes = seed_text.encode('utf-8')
            deployer_bytes = bytes.fromhex(deployer_private_key[2:])  # Remove 0x prefix
            
            # Concatenate and hash
            combined = seed_bytes + deployer_bytes
            derived_key = self.w3.keccak(combined)
            
            # Create account from derived key
            derived_key_hex = '0x' + derived_key.hex()
            secondary_account = Account.from_key(derived_key_hex)
            
            logging.info(f"Derived secondary wallet: {secondary_account.address}")
            return secondary_account
            
        except Exception as e:
            logging.error(f"Failed to derive secondary wallet: {str(e)}")
            raise
    
    def _init_deployer_account(self):
        """Initialize deployer account (main wallet with funds)"""
        try:
            deployer_private_key = os.environ.get('DEPLOYER_PRIVATE_KEY')
            if not deployer_private_key:
                raise Exception("DEPLOYER_PRIVATE_KEY not found in environment")
            
            # Normalize private key (ensure 0x prefix)
            if not deployer_private_key.startswith('0x'):
                deployer_private_key = f'0x{deployer_private_key}'
            
            deployer_account = Account.from_key(deployer_private_key)
            
            # Check balance only if connected
            if self.is_connected:
                balance = self.w3.eth.get_balance(deployer_account.address)
                balance_kas = self.w3.from_wei(balance, 'ether')
                logging.info(f"Deployer wallet {deployer_account.address} - Balance: {balance_kas} KAS")
            else:
                logging.warning(f"Deployer wallet {deployer_account.address} - Balance check skipped (offline mode)")
            
            return deployer_account
            
        except Exception as e:
            logging.error(f"Failed to initialize deployer account: {str(e)}")
            raise
    
    def _init_oracle_account(self):
        """Initialize oracle account (secondary wallet) for automated transactions"""
        try:
            deployer_private_key = os.environ.get('DEPLOYER_PRIVATE_KEY')
            if not deployer_private_key:
                raise Exception("DEPLOYER_PRIVATE_KEY not found in environment")
            
            # Derive secondary wallet (oracle)
            oracle_account = self._derive_secondary_wallet(deployer_private_key)
            
            # Verify oracle address matches expected
            expected_oracle = "0x5f837F62744D4d80Fc79C3A5346B4A228956914E"
            if oracle_account.address.lower() != expected_oracle.lower():
                logging.warning(f"Oracle address mismatch: expected {expected_oracle}, got {oracle_account.address}")
            
            # Check balance only if connected
            if self.is_connected:
                balance = self.w3.eth.get_balance(oracle_account.address)
                balance_kas = self.w3.from_wei(balance, 'ether')
                logging.info(f"Oracle wallet {oracle_account.address} - Balance: {balance_kas} KAS")
            else:
                logging.warning(f"Oracle wallet {oracle_account.address} - Balance check skipped (offline mode)")
            
            return oracle_account
            
        except Exception as e:
            logging.error(f"Failed to initialize oracle account: {str(e)}")
            raise
    
    def _load_contract_abi(self, contract_name):
        """Load contract ABI from Hardhat artifacts"""
        try:
            # Find the contract JSON file
            abi_path = ARTIFACTS_DIR / f"{contract_name}.sol" / f"{contract_name}.json"
            
            if not abi_path.exists():
                raise FileNotFoundError(f"ABI file not found: {abi_path}")
            
            with open(abi_path, 'r') as f:
                contract_json = json.load(f)
            
            return contract_json['abi']
            
        except Exception as e:
            logging.error(f"Failed to load ABI for {contract_name}: {str(e)}")
            raise
    
    def _load_interface_abi(self, interface_name):
        """Load interface ABI (stored in artifacts/contracts/interfaces/)"""
        try:
            # Interface ABIs are stored in interfaces subfolder
            abi_path = ARTIFACTS_DIR / "interfaces" / f"{interface_name}.sol" / f"{interface_name}.json"
            
            if not abi_path.exists():
                raise FileNotFoundError(f"Interface ABI not found: {abi_path}")
            
            with open(abi_path, 'r') as f:
                abi_json = json.load(f)
            
            return abi_json['abi'] if 'abi' in abi_json else abi_json
            
        except Exception as e:
            logging.error(f"Failed to load interface ABI for {interface_name}: {str(e)}")
            raise
    
    def _compute_pool_address(self, token_a, token_b, fee):
        """
        Compute Uniswap V3 pool address using Factory.getPool()
        
        Args:
            token_a (str): First token address
            token_b (str): Second token address
            fee (int): Fee tier (e.g., 3000 for 0.3%)
        
        Returns:
            str: Pool address (checksum)
        """
        try:
            factory = self.contracts.get('KaspaFinanceFactory')
            if not factory:
                raise Exception("Kaspa Finance Factory contract not loaded")
            
            # Normalize addresses
            token_a = Web3.to_checksum_address(token_a)
            token_b = Web3.to_checksum_address(token_b)
            
            # Call factory.getPool(tokenA, tokenB, fee)
            pool_address = factory.functions.getPool(token_a, token_b, fee).call()
            
            # Check if pool exists
            if pool_address == '0x0000000000000000000000000000000000000000':
                raise Exception(f"Pool does not exist for {token_a}/{token_b} with fee {fee}")
            
            return Web3.to_checksum_address(pool_address)
            
        except Exception as e:
            logging.error(f"Failed to compute pool address: {str(e)}")
            raise
    
    def _load_contracts(self):
        """Load all deployed contracts"""
        try:
            contracts = {}
            
            # Load TokenFactory
            token_factory_abi = self._load_contract_abi('TokenFactory')
            contracts['TokenFactory'] = self.w3.eth.contract(
                address=Web3.to_checksum_address(TOKEN_FACTORY_ADDRESS),
                abi=token_factory_abi
            )
            logging.info(f"Loaded TokenFactory at {TOKEN_FACTORY_ADDRESS}")
            
            # Load GraduationController V3
            # NOTE: V3 fixes all 11 critical issues from V2
            # Uses GraduationControllerV3.sol with snapshot architecture
            graduation_abi_path = ARTIFACTS_DIR / "GraduationControllerV3.sol" / "GraduationControllerV3.json"
            with open(graduation_abi_path, 'r') as f:
                graduation_abi = json.load(f)['abi']
            
            contracts['GraduationController'] = self.w3.eth.contract(
                address=Web3.to_checksum_address(GRADUATION_CONTROLLER_ADDRESS),
                abi=graduation_abi
            )
            logging.info(f"Loaded GraduationController V4 at {GRADUATION_CONTROLLER_ADDRESS}")
            
            # Load BondingCurvePool ABI (for pool interactions later)
            contracts['BondingCurvePoolABI'] = self._load_contract_abi('BondingCurvePool')
            logging.info("Loaded BondingCurvePool ABI")
            
            # Load PRO Token Vesting Contract ABIs
            contracts['AirdropVestingABI'] = self._load_contract_abi('AirdropVesting')
            contracts['LinearVestingABI'] = self._load_contract_abi('LinearVesting')
            contracts['CliffVestingABI'] = self._load_contract_abi('CliffVesting')
            logging.info("Loaded PRO Token Vesting ABIs")
            
            # Load AirdropDistributor (batch transfer helper)
            airdrop_distributor_abi = self._load_contract_abi('AirdropDistributor')
            contracts['AirdropDistributor'] = self.w3.eth.contract(
                address=Web3.to_checksum_address(AIRDROP_DISTRIBUTOR_ADDRESS),
                abi=airdrop_distributor_abi
            )
            contracts['AirdropDistributorABI'] = airdrop_distributor_abi
            logging.info(f"Loaded AirdropDistributor at {AIRDROP_DISTRIBUTOR_ADDRESS}")
            
            # Load Kaspa Finance DEX Contracts (for post-graduation trading)
            # Load Factory (required for pool address computation)
            try:
                factory_abi = self._load_interface_abi('IUniswapV3Factory')
                contracts['KaspaFinanceFactory'] = self.w3.eth.contract(
                    address=Web3.to_checksum_address(KASPA_FINANCE_FACTORY),
                    abi=factory_abi
                )
                logging.info(f"Loaded Kaspa Finance Factory at {KASPA_FINANCE_FACTORY}")
            except FileNotFoundError:
                logging.warning("IUniswapV3Factory interface not found - pool address computation disabled")
                contracts['KaspaFinanceFactory'] = None
            
            # NOTE: QuoterV2 and SwapRouter interfaces optional - not critical for core functionality
            try:
                quoter_v2_abi = self._load_interface_abi('IQuoterV2')
                contracts['QuoterV2'] = self.w3.eth.contract(
                    address=Web3.to_checksum_address(KASPA_FINANCE_QUOTER_V2),
                    abi=quoter_v2_abi
                )
                logging.info(f"Loaded QuoterV2 at {KASPA_FINANCE_QUOTER_V2}")
            except FileNotFoundError:
                logging.warning("IQuoterV2 interface not found - post-graduation quote features disabled")
                contracts['QuoterV2'] = None
            
            try:
                # Load FULL SwapRouter ABI from Kaspa Finance Hardhat artifact
                # This contains the complete interface including multicall(bytes[]), refundETH(), etc.
                swap_router_abi_path = Path(__file__).parent.parent / "attached_assets" / "SwapRouter_1762263429508.json"
                with open(swap_router_abi_path, 'r') as f:
                    swap_router_artifact = json.load(f)
                swap_router_abi = swap_router_artifact['abi']
                
                contracts['SwapRouter'] = self.w3.eth.contract(
                    address=Web3.to_checksum_address(KASPA_FINANCE_SWAP_ROUTER),
                    abi=swap_router_abi
                )
                logging.info(f"Loaded SwapRouter (FULL ABI) at {KASPA_FINANCE_SWAP_ROUTER}")
            except FileNotFoundError:
                logging.warning("SwapRouter ABI not found - post-graduation swap features disabled")
                contracts['SwapRouter'] = None
            
            # Load IWKAS from interfaces directory
            try:
                # IWKAS is defined in contracts/interfaces/IWKAS.sol
                wkas_abi = self._load_interface_abi('IWKAS')
            except Exception as e:
                logging.error(f"Failed to load IWKAS: {e}")
                raise
            contracts['WKAS'] = self.w3.eth.contract(
                address=Web3.to_checksum_address(KASPA_FINANCE_WKAS),
                abi=wkas_abi
            )
            contracts['WKASABI'] = wkas_abi  # Store ABI for ERC20 interactions
            logging.info(f"Loaded WKAS at {KASPA_FINANCE_WKAS}")
            
            return contracts
            
        except Exception as e:
            logging.error(f"Failed to load contracts: {str(e)}")
            raise
    
    def get_bonding_pool_contract(self, pool_address):
        """Get BondingCurvePool contract instance for a specific pool"""
        try:
            return self.w3.eth.contract(
                address=Web3.to_checksum_address(pool_address),
                abi=self.contracts['BondingCurvePoolABI']
            )
        except Exception as e:
            logging.error(f"Failed to get pool contract at {pool_address}: {str(e)}")
            raise
    
    def get_airdrop_vesting_contract(self, vesting_address):
        """Get AirdropVesting contract instance"""
        try:
            return self.w3.eth.contract(
                address=Web3.to_checksum_address(vesting_address),
                abi=self.contracts['AirdropVestingABI']
            )
        except Exception as e:
            logging.error(f"Failed to get airdrop vesting contract at {vesting_address}: {str(e)}")
            raise
    
    def get_linear_vesting_contract(self, vesting_address):
        """Get LinearVesting contract instance (for marketing tokens)"""
        try:
            return self.w3.eth.contract(
                address=Web3.to_checksum_address(vesting_address),
                abi=self.contracts['LinearVestingABI']
            )
        except Exception as e:
            logging.error(f"Failed to get linear vesting contract at {vesting_address}: {str(e)}")
            raise
    
    def get_cliff_vesting_contract(self, vesting_address):
        """Get CliffVesting contract instance (for team tokens)"""
        try:
            return self.w3.eth.contract(
                address=Web3.to_checksum_address(vesting_address),
                abi=self.contracts['CliffVestingABI']
            )
        except Exception as e:
            logging.error(f"Failed to get cliff vesting contract at {vesting_address}: {str(e)}")
            raise
    
    def get_uniswap_v3_pool_contract(self, pool_address):
        """
        Get Uniswap V3 Pool contract instance for a specific DEX pool
        
        Args:
            pool_address: Address of the Uniswap V3 pool
        
        Returns:
            Contract: Web3 contract instance for the pool
        """
        try:
            # Load Uniswap V3 Pool ABI (standard interface)
            pool_abi = self._load_interface_abi('IUniswapV3Pool')
            
            return self.w3.eth.contract(
                address=Web3.to_checksum_address(pool_address),
                abi=pool_abi
            )
        except Exception as e:
            logging.error(f"Failed to get Uniswap V3 pool contract at {pool_address}: {str(e)}")
            raise
    
    # =========================
    # PRO Token Vesting Status Methods
    # =========================
    
    def get_airdrop_vesting_status(self, vesting_address):
        """
        Get airdrop vesting status (unlocked amount, total amount, unlock schedule)
        
        Returns:
            dict: {
                'total_amount': int (wei),
                'unlocked_amount': int (wei),
                'claimed_amount': int (wei),
                'available_to_claim': int (wei),
                'daily_unlock_rate': int (5% = 500 bps),
                'start_time': int (timestamp),
                'beneficiary': str (address)
            }
        """
        try:
            contract = self.get_airdrop_vesting_contract(vesting_address)
            
            total_amount = contract.functions.totalAllocation().call()
            unlocked_amount = contract.functions.getUnlockedAmount().call()
            claimed_amount = contract.functions.withdrawn().call()
            start_time = contract.functions.startTime().call()
            beneficiary = contract.functions.beneficiary().call()
            
            return {
                'total_amount': total_amount,
                'unlocked_amount': unlocked_amount,
                'claimed_amount': claimed_amount,
                'available_to_claim': max(0, unlocked_amount - claimed_amount),
                'daily_unlock_rate': 500,  # 5% daily = 500 bps
                'start_time': start_time,
                'beneficiary': beneficiary
            }
        except Exception as e:
            logging.error(f"Failed to get airdrop vesting status: {str(e)}")
            raise
    
    def get_marketing_vesting_status(self, vesting_address):
        """
        Get marketing vesting status (12-month linear vesting)
        
        Returns:
            dict: {
                'total_amount': int (wei),
                'unlocked_amount': int (wei),
                'claimed_amount': int (wei),
                'available_to_claim': int (wei),
                'duration': int (seconds, 12 months),
                'start_time': int (timestamp),
                'beneficiary': str (address)
            }
        """
        try:
            contract = self.get_linear_vesting_contract(vesting_address)
            
            total_amount = contract.functions.totalAllocation().call()
            unlocked_amount = contract.functions.getUnlockedAmount().call()
            claimed_amount = contract.functions.withdrawn().call()
            start_time = contract.functions.startTime().call()
            duration = contract.functions.duration().call()
            beneficiary = contract.functions.beneficiary().call()
            
            return {
                'total_amount': total_amount,
                'unlocked_amount': unlocked_amount,
                'claimed_amount': claimed_amount,
                'available_to_claim': max(0, unlocked_amount - claimed_amount),
                'duration': duration,
                'start_time': start_time,
                'beneficiary': beneficiary
            }
        except Exception as e:
            logging.error(f"Failed to get marketing vesting status: {str(e)}")
            raise
    
    def get_team_vesting_status(self, vesting_address):
        """
        Get team vesting status (6mo cliff + 18mo linear vesting)
        
        Returns:
            dict: {
                'total_amount': int (wei),
                'unlocked_amount': int (wei),
                'claimed_amount': int (wei),
                'available_to_claim': int (wei),
                'cliff_duration': int (seconds, 6 months),
                'vesting_duration': int (seconds, 18 months),
                'start_time': int (timestamp),
                'cliff_end': int (timestamp),
                'beneficiary': str (address)
            }
        """
        try:
            contract = self.get_cliff_vesting_contract(vesting_address)
            
            total_amount = contract.functions.totalAllocation().call()
            unlocked_amount = contract.functions.getUnlockedAmount().call()
            claimed_amount = contract.functions.withdrawn().call()
            start_time = contract.functions.startTime().call()
            cliff_duration = contract.functions.cliff().call()
            vesting_end = contract.functions.vestingEnd().call()
            beneficiary = contract.functions.beneficiary().call()
            
            return {
                'total_amount': total_amount,
                'unlocked_amount': unlocked_amount,
                'claimed_amount': claimed_amount,
                'available_to_claim': max(0, unlocked_amount - claimed_amount),
                'cliff_duration': cliff_duration,
                'vesting_duration': vesting_end - (start_time + cliff_duration),
                'start_time': start_time,
                'cliff_end': start_time + cliff_duration,
                'beneficiary': beneficiary
            }
        except Exception as e:
            logging.error(f"Failed to get team vesting status: {str(e)}")
            raise
    
    # =========================
    # PRO Token Vesting Withdrawal Transaction Builders
    # =========================
    
    def build_airdrop_vesting_claim_tx(self, vesting_address, claimer_address):
        """
        Build transaction to claim unlocked airdrop tokens
        
        Args:
            vesting_address (str): AirdropVesting contract address
            claimer_address (str): Address claiming tokens (must be platform airdropTreasury)
        
        Returns:
            dict: Unsigned transaction {from, to, data, gas, value}
        """
        try:
            contract = self.get_airdrop_vesting_contract(vesting_address)
            
            # Build claim transaction
            tx_data = contract.functions.claim().build_transaction({
                'from': Web3.to_checksum_address(claimer_address),
                'value': 0,
                'gas': 0,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(Web3.to_checksum_address(claimer_address))
            })
            
            # Estimate gas
            gas_estimate = self.estimate_gas({
                'from': tx_data['from'],
                'to': tx_data['to'],
                'data': tx_data['data'],
                'value': tx_data['value']
            })
            
            tx_data['gas'] = gas_estimate['gas']
            
            logging.info(f"Built airdrop vesting claim tx - Gas: {gas_estimate['gas']}")
            return tx_data
            
        except Exception as e:
            logging.error(f"Failed to build airdrop vesting claim tx: {str(e)}")
            raise
    
    def build_marketing_vesting_withdraw_tx(self, vesting_address, creator_address):
        """
        Build transaction to withdraw unlocked marketing tokens
        
        Args:
            vesting_address (str): LinearVesting contract address
            creator_address (str): Token creator address (beneficiary)
        
        Returns:
            dict: Unsigned transaction {from, to, data, gas, value}
        """
        try:
            contract = self.get_linear_vesting_contract(vesting_address)
            
            # Build withdraw transaction
            tx_data = contract.functions.withdraw().build_transaction({
                'from': Web3.to_checksum_address(creator_address),
                'value': 0,
                'gas': 0,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(Web3.to_checksum_address(creator_address))
            })
            
            # Estimate gas
            gas_estimate = self.estimate_gas({
                'from': tx_data['from'],
                'to': tx_data['to'],
                'data': tx_data['data'],
                'value': tx_data['value']
            })
            
            tx_data['gas'] = gas_estimate['gas']
            
            logging.info(f"Built marketing vesting withdraw tx - Gas: {gas_estimate['gas']}")
            return tx_data
            
        except Exception as e:
            logging.error(f"Failed to build marketing vesting withdraw tx: {str(e)}")
            raise
    
    def build_team_vesting_withdraw_tx(self, vesting_address, creator_address):
        """
        Build transaction to withdraw unlocked team tokens
        
        Args:
            vesting_address (str): CliffVesting contract address
            creator_address (str): Token creator address (beneficiary)
        
        Returns:
            dict: Unsigned transaction {from, to, data, gas, value}
        """
        try:
            contract = self.get_cliff_vesting_contract(vesting_address)
            
            # Build withdraw transaction
            tx_data = contract.functions.withdraw().build_transaction({
                'from': Web3.to_checksum_address(creator_address),
                'value': 0,
                'gas': 0,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(Web3.to_checksum_address(creator_address))
            })
            
            # Estimate gas
            gas_estimate = self.estimate_gas({
                'from': tx_data['from'],
                'to': tx_data['to'],
                'data': tx_data['data'],
                'value': tx_data['value']
            })
            
            tx_data['gas'] = gas_estimate['gas']
            
            logging.info(f"Built team vesting withdraw tx - Gas: {gas_estimate['gas']}")
            return tx_data
            
        except Exception as e:
            logging.error(f"Failed to build team vesting withdraw tx: {str(e)}")
            raise
    
    def _decode_revert_reason(self, exception):
        """
        Decode contract revert reason from exception
        
        Handles custom error selectors like 0x8bbc6532 (InsufficientKAS)
        
        Args:
            exception: Exception from gas estimation or transaction
        
        Returns:
            str: Human-readable error message
        """
        error_str = str(exception)
        
        # Known custom error selectors
        CUSTOM_ERRORS = {
            '0x8bbc6532': 'InsufficientKAS() - Oracle wallet does not have enough KAS to pay for gas. Please fund the oracle wallet.',
            '0x118cdaa7': 'AddressMismatch() - Token address does not match expected address',
            '0x48f5c3ed': 'InvalidCaller() - Only authorized caller can execute this function',
            '0x3204506f': 'InvalidState() - Contract is in invalid state for this operation',
        }
        
        # Check for custom error selector (4-byte function signature)
        if '0x8bbc6532' in error_str:
            return CUSTOM_ERRORS['0x8bbc6532']
        elif '0x118cdaa7' in error_str:
            return CUSTOM_ERRORS['0x118cdaa7']
        elif '0x48f5c3ed' in error_str:
            return CUSTOM_ERRORS['0x48f5c3ed']
        elif '0x3204506f' in error_str:
            return CUSTOM_ERRORS['0x3204506f']
        
        # Check for standard revert string (execution reverted: ...)
        if 'execution reverted:' in error_str:
            # Extract revert reason after "execution reverted: "
            parts = error_str.split('execution reverted:', 1)
            if len(parts) > 1:
                reason = parts[1].strip().strip("'\"")
                return f"Transaction would revert: {reason}"
        
        # Return raw error if we can't decode it
        return error_str
    
    def estimate_gas(self, transaction):
        """
        Estimate gas for a transaction with 20% buffer
        
        Args:
            transaction: Transaction dict with 'from', 'to', 'data', etc.
        
        Returns:
            int: Estimated gas with 20% buffer
        
        Raises:
            ValueError: With decoded revert reason if gas estimation fails
        """
        try:
            # Estimate gas
            gas_estimate = self.w3.eth.estimate_gas(transaction)
            
            # Add 20% buffer for safety
            gas_with_buffer = int(gas_estimate * 1.2)
            
            # Get gas price
            gas_price = self.w3.eth.gas_price
            
            # Calculate cost in KAS
            cost_wei = gas_with_buffer * gas_price
            cost_kas = self.w3.from_wei(cost_wei, 'ether')
            
            logging.debug(f"Gas estimate: {gas_estimate} (with buffer: {gas_with_buffer}), Cost: {cost_kas} KAS")
            
            return {
                'gas': gas_with_buffer,
                'gas_price': gas_price,
                'cost_wei': cost_wei,
                'cost_kas': float(cost_kas)
            }
            
        except Exception as e:
            # Decode contract revert reason
            error_message = self._decode_revert_reason(e)
            logging.error(f"Gas estimation failed: {error_message}")
            raise ValueError(error_message)
    
    def estimate_trade_gas(self, action, params):
        """
        Estimate gas for buy/sell transaction with safety buffer
        
        Args:
            action (str): 'buy' or 'sell'
            params (dict): {
                'pool_address': str,
                'kas_amount': int (for buy) or 'token_amount': int (for sell),
                'from_address': str (optional, defaults to deployer for buy, oracle for sell),
                'min_tokens_out': int (optional, for buy),
                'min_kas_out': int (optional, for sell),
                'deadline': int (optional, unix timestamp)
            }
        
        Returns:
            dict: {'gas': int, 'gas_price': int, 'cost_wei': int, 'cost_kas': float}
        """
        try:
            pool_address = params['pool_address']
            # Use deployer (has KAS) for buy, oracle (has tokens) for sell estimation
            # If from_address not provided, choose based on action
            if 'from_address' not in params or not params['from_address']:
                from_address = self.deployer_account.address if action == 'buy' else self.oracle_account.address
            else:
                from_address = params['from_address']
            
            pool = self.get_bonding_pool_contract(pool_address)
            
            deadline = params.get('deadline', int(time.time()) + 300)
            
            if action == 'buy':
                kas_amount = params['kas_amount']
                min_tokens_out = params.get('min_tokens_out', 0)
                tx_data = pool.functions.buyTokens(min_tokens_out, deadline).build_transaction({
                    'from': Web3.to_checksum_address(from_address),
                    'value': kas_amount
                })
                tx = {
                    'from': tx_data['from'],
                    'to': tx_data['to'],
                    'value': tx_data['value'],
                    'data': tx_data['data']
                }
                
            elif action == 'sell':
                token_amount = params['token_amount']
                min_kas_out = params.get('min_kas_out', 0)
                
                # VALIDATION CHECK 1: Validate minimum trade
                try:
                    min_trade = pool.functions.MINIMUM_TRADE().call()
                    if token_amount < min_trade:
                        raise ValueError(f"Amount {token_amount} below minimum trade {min_trade}")
                except AttributeError:
                    # Contract doesn't have MINIMUM_TRADE constant, skip this check
                    pass
                except Exception as e:
                    # Only raise if it's our ValueError, otherwise log and continue
                    if "below minimum trade" in str(e):
                        raise
                    logging.debug(f"Could not check MINIMUM_TRADE: {str(e)}")
                
                # VALIDATION CHECK 2: Validate wallet balance
                try:
                    balance = pool.functions.balanceOf(from_address).call()
                    if token_amount > balance:
                        raise ValueError(f"Insufficient balance. Need {token_amount}, have {balance}")
                except Exception as e:
                    # Only raise if it's our ValueError, otherwise log and continue
                    if "Insufficient balance" in str(e):
                        raise
                    logging.debug(f"Could not check balance: {str(e)}")
                
                tx_data = pool.functions.sellTokens(token_amount, min_kas_out, deadline).build_transaction({
                    'from': Web3.to_checksum_address(from_address),
                    'value': 0
                })
                tx = {
                    'from': tx_data['from'],
                    'to': tx_data['to'],
                    'value': tx_data['value'],
                    'data': tx_data['data']
                }
                
            else:
                raise ValueError(f"Invalid action: {action}. Must be 'buy' or 'sell'")
            
            return self.estimate_gas(tx)
            
        except ValueError as e:
            # Re-raise ValueError for proper 400 error handling in endpoint
            raise
        except Exception as e:
            # Check if this is a contract revert with known validation errors
            error_message = str(e)
            if "Below minimum trade" in error_message:
                raise ValueError("Amount below minimum trade requirement")
            elif "Insufficient balance" in error_message or "ERC20: burn amount exceeds balance" in error_message:
                raise ValueError("Insufficient token balance for this transaction")
            else:
                logging.error(f"Failed to estimate trade gas for {action}: {str(e)}")
                raise
    
    def sign_transaction(self, transaction, private_key=None):
        """
        Sign a transaction
        
        Args:
            transaction: Transaction dict
            private_key: Optional private key (defaults to oracle account)
        
        Returns:
            Signed transaction
        """
        try:
            # Use oracle account if no private key provided
            if private_key is None:
                account = self.oracle_account
            else:
                account = Account.from_key(private_key)
            
            # Add nonce if not present
            if 'nonce' not in transaction:
                transaction['nonce'] = self.w3.eth.get_transaction_count(account.address)
            
            # Add gas price if not present
            if 'gasPrice' not in transaction:
                transaction['gasPrice'] = self.w3.eth.gas_price
            
            # Add chain ID
            transaction['chainId'] = KASPLEX_TESTNET_CHAIN_ID
            
            # Sign transaction
            signed_txn = self.w3.eth.account.sign_transaction(transaction, account.key)
            
            return signed_txn
            
        except Exception as e:
            logging.error(f"Transaction signing failed: {str(e)}")
            raise
    
    def relay_transaction(self, signed_txn):
        """
        Relay a signed transaction to the blockchain
        
        Args:
            signed_txn: Signed transaction object
        
        Returns:
            str: Transaction hash
        """
        try:
            # Send signed transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.raw_transaction)
            tx_hash_hex = tx_hash.hex()
            
            logging.info(f"Transaction relayed: {tx_hash_hex}")
            return tx_hash_hex
            
        except Exception as e:
            logging.error(f"Transaction relay failed: {str(e)}")
            raise
    
    def relay_signed_transaction(self, signed_tx):
        """
        Relay a user-signed transaction to the blockchain
        
        Args:
            signed_tx (str): Signed transaction hex string (e.g., "0x...")
        
        Returns:
            str: Transaction hash (hex string)
        
        Raises:
            Exception: If transaction relay fails
        """
        try:
            # Validate hex format
            if not isinstance(signed_tx, str) or not signed_tx.startswith('0x'):
                raise ValueError("signed_tx must be a hex string starting with '0x'")
            
            # Send raw transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx)
            tx_hash_hex = tx_hash.hex()
            
            logging.info(f"User transaction relayed: {tx_hash_hex}")
            return tx_hash_hex
            
        except ValueError as e:
            logging.error(f"Invalid transaction format: {str(e)}")
            raise
        except Exception as e:
            logging.error(f"Failed to relay user transaction: {str(e)}")
            raise
    
    def validate_and_relay_signed_tx(self, raw_signed_tx):
        """
        Validate and relay a user-signed transaction (legacy method)
        
        Args:
            raw_signed_tx: Raw signed transaction bytes (from frontend)
        
        Returns:
            str: Transaction hash
        """
        try:
            # Decode signed transaction
            tx = self.w3.eth.account.recover_transaction(raw_signed_tx)
            
            # Validate chain ID
            # Note: recover_transaction doesn't give us the full tx, so we'll relay it
            # and let the network validate
            
            # Send raw transaction
            tx_hash = self.w3.eth.send_raw_transaction(raw_signed_tx)
            tx_hash_hex = tx_hash.hex()
            
            logging.info(f"User transaction relayed: {tx_hash_hex}")
            return tx_hash_hex
            
        except Exception as e:
            logging.error(f"Failed to relay user transaction: {str(e)}")
            raise
    
    def wait_for_transaction_receipt(self, tx_hash, timeout=120):
        """
        Wait for transaction to be mined
        
        Args:
            tx_hash: Transaction hash
            timeout: Timeout in seconds (default 120)
        
        Returns:
            Transaction receipt
        """
        try:
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
            
            if receipt['status'] == 1:
                logging.info(f"Transaction {tx_hash} successful - Block: {receipt['blockNumber']}")
            else:
                logging.error(f"Transaction {tx_hash} failed")
            
            return receipt
            
        except Exception as e:
            logging.error(f"Error waiting for transaction {tx_hash}: {str(e)}")
            raise
    
    def get_transaction_status(self, tx_hash):
        """
        Get status of a transaction
        
        Args:
            tx_hash: Transaction hash
        
        Returns:
            dict: Transaction status info
        """
        try:
            # Try to get receipt
            try:
                receipt = self.w3.eth.get_transaction_receipt(tx_hash)
                return {
                    'status': 'confirmed' if receipt['status'] == 1 else 'failed',
                    'block_number': receipt['blockNumber'],
                    'gas_used': receipt['gasUsed']
                }
            except Exception:
                # Receipt not found, check if pending
                try:
                    tx = self.w3.eth.get_transaction(tx_hash)
                    return {
                        'status': 'pending',
                        'block_number': None,
                        'gas_used': None
                    }
                except Exception:
                    return {
                        'status': 'not_found',
                        'block_number': None,
                        'gas_used': None
                    }
                    
        except Exception as e:
            logging.error(f"Error getting transaction status for {tx_hash}: {str(e)}")
            raise
    
    def send_transaction_with_retry(self, transaction, account=None, max_retries=11, initial_gas=None):
        """
        Send transaction with Kasplex-specific retry logic
        
        Kasplex testnet can drop transactions due to RPC issues. This method implements:
        - Progressive gas increases (+15% per retry)
        - Transaction resubmission on drop
        - Extended monitoring periods
        
        Based on Kasplex developer best practices:
        "Developers report occasional RPC rejections during deployment requiring 
        progressive gas adjustments (up to 11 retries)"
        
        Args:
            transaction (dict): Transaction parameters (to, data, value, etc.)
            account: Account to sign with (defaults to oracle_account)
            max_retries (int): Maximum retry attempts (default 11 per Kasplex docs)
            initial_gas (int): Starting gas limit (if None, uses estimation)
        
        Returns:
            dict: {
                'tx_hash': str,
                'receipt': dict,
                'attempts': int,
                'final_gas': int
            }
        
        Raises:
            Exception: If all retries fail
        """
        if account is None:
            account = self.oracle_account
        
        # Determine initial gas
        if initial_gas is None:
            try:
                gas_estimate = self.w3.eth.estimate_gas(transaction)
                current_gas = int(gas_estimate * 1.3)  # Start with 30% buffer
            except Exception as e:
                logging.warning(f"Gas estimation failed: {e}, using fallback 3M gas")
                current_gas = 3000000
        else:
            current_gas = initial_gas
        
        logging.info(f"Starting transaction with retry - Initial gas: {current_gas:,}")
        
        for attempt in range(1, max_retries + 1):
            try:
                # Get fresh nonce for each attempt
                nonce = self.w3.eth.get_transaction_count(account.address)
                
                # Build transaction with current gas
                tx = transaction.copy()
                tx.update({
                    'from': account.address,
                    'nonce': nonce,
                    'gas': current_gas,
                    'gasPrice': self.w3.eth.gas_price,
                    'chainId': KASPLEX_TESTNET_CHAIN_ID
                })
                
                # Sign and send
                signed = account.sign_transaction(tx)
                tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
                tx_hash_hex = tx_hash.hex()
                
                logging.info(f"[Attempt {attempt}/{max_retries}] TX sent: {tx_hash_hex} (gas: {current_gas:,})")
                
                # Wait for confirmation with extended timeout
                receipt = None
                wait_time = 30 if attempt == 1 else 60  # Longer wait on retries
                
                for check in range(wait_time // 5):
                    time.sleep(5)
                    try:
                        receipt = self.w3.eth.get_transaction_receipt(tx_hash_hex)
                        if receipt:
                            if receipt['status'] == 1:
                                logging.info(f"✅ TX confirmed in block {receipt['blockNumber']} (attempt {attempt}, gas: {current_gas:,})")
                                return {
                                    'tx_hash': tx_hash_hex,
                                    'receipt': receipt,
                                    'attempts': attempt,
                                    'final_gas': current_gas
                                }
                            else:
                                logging.error(f"❌ TX failed in block {receipt['blockNumber']}")
                                raise Exception(f"Transaction reverted on-chain")
                    except Exception as e:
                        if "reverted" in str(e).lower():
                            raise
                        continue
                
                # Transaction dropped or pending too long
                logging.warning(f"⏱️ [Attempt {attempt}] TX {tx_hash_hex} not confirmed after {wait_time}s")
                
                if attempt < max_retries:
                    # Increase gas by 15% for next attempt
                    current_gas = int(current_gas * 1.15)
                    logging.info(f"   Retrying with increased gas: {current_gas:,}")
                    time.sleep(2)  # Brief pause before retry
                
            except Exception as e:
                error_msg = str(e)
                
                # Don't retry on fatal errors
                if any(fatal in error_msg.lower() for fatal in ['insufficient funds', 'nonce too low', 'reverted']):
                    logging.error(f"❌ Fatal error, cannot retry: {error_msg}")
                    raise
                
                logging.warning(f"[Attempt {attempt}] Send failed: {error_msg}")
                
                if attempt < max_retries:
                    current_gas = int(current_gas * 1.15)
                    logging.info(f"   Retrying with gas: {current_gas:,}")
                    time.sleep(2)
        
        raise Exception(f"Transaction failed after {max_retries} attempts with final gas {current_gas:,}")
    
    # =========================
    # Task 2.2.1 - TokenFactory Interactions
    # =========================
    
    def create_token_tx_data(self, user_address, name, symbol, total_supply, description, 
                             image_url, twitter_url, telegram_url, website_url, anti_bot_enabled,
                             reserved_percentage=0, airdrops_allocation=0, 
                             marketing_allocation=0, team_allocation=0):
        """
        Build transaction data for TokenFactory.createToken() - USER TRANSACTION
        
        Args:
            user_address (str): User's wallet address
            name (str): Token name
            symbol (str): Token symbol
            total_supply (int): Total supply in wei
            description (str): Token description
            image_url (str): Token image URL
            twitter_url (str): Twitter URL
            telegram_url (str): Telegram URL
            website_url (str): Website URL
            anti_bot_enabled (bool): Enable anti-bot protection
            reserved_percentage (int): PRO token vesting % (0=BASIC, 1-25=PRO)
            airdrops_allocation (int): % of reserved tokens for airdrops (0-100)
            marketing_allocation (int): % of reserved tokens for marketing (0-100)
            team_allocation (int): % of reserved tokens for team (0-100)
        
        Returns:
            dict: Unsigned transaction dict {from, to, data, value, gas}
        """
        try:
            token_type = "PRO" if reserved_percentage > 0 else "BASIC"
            logging.info(f"Building createToken tx for user {user_address} - {token_type} Token: {name} ({symbol})")
            
            # Build contract call with vesting parameters
            contract = self.contracts['TokenFactory']
            tx_data = contract.functions.createToken(
                name,
                symbol,
                total_supply,
                description,
                image_url,
                twitter_url,
                telegram_url,
                website_url,
                anti_bot_enabled,
                reserved_percentage,
                airdrops_allocation,
                marketing_allocation,
                team_allocation
            ).build_transaction({
                'from': Web3.to_checksum_address(user_address),
                'value': 0,
                'gas': 0,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(Web3.to_checksum_address(user_address))
            })
            
            # Estimate gas
            gas_estimate = self.estimate_gas({
                'from': tx_data['from'],
                'to': tx_data['to'],
                'data': tx_data['data'],
                'value': tx_data['value']
            })
            
            tx_data['gas'] = gas_estimate['gas']
            
            logging.info(f"createToken tx built - Gas: {gas_estimate['gas']}, Cost: {gas_estimate['cost_kas']} KAS")
            return tx_data
            
        except Exception as e:
            logging.error(f"Failed to build createToken tx: {str(e)}")
            raise
    
    # =========================
    # Task 2.2.2 - BondingCurvePool Interactions
    # =========================
    
    def get_buy_quote(self, pool_address, kas_amount):
        """
        Get comprehensive buy quote from bonding curve pool
        
        Args:
            pool_address (str): Pool contract address
            kas_amount (int): KAS amount in wei
        
        Returns:
            dict: {
                'tokens_out': int (in wei),
                'fees': {
                    'anti_bot': int (in wei),
                    'platform': int (in wei),
                    'creator': int (in wei)
                },
                'auto_slippage_bps': int,
                'price_impact_percent': float
            }
        """
        try:
            logging.debug(f"Getting buy quote for pool {pool_address} - KAS: {kas_amount}")
            
            pool = self.get_bonding_pool_contract(pool_address)
            
            tokens_out = pool.functions.quoteBuy(kas_amount).call()
            
            fee_breakdown = pool.functions.getEffectiveFeeBreakdown(kas_amount).call()
            anti_bot_fee_wei = fee_breakdown[0]
            platform_fee_wei = fee_breakdown[1]
            creator_fee_wei = fee_breakdown[2]
            
            auto_slippage_bps = pool.functions.calculateOptimalSlippage(kas_amount).call()
            
            virtual_kas_reserve = pool.functions.virtualKasReserve().call()
            price_impact_percent = 0.0
            if virtual_kas_reserve > 0:
                kas_amount_kas = kas_amount / 10**18
                virtual_kas_reserve_kas = virtual_kas_reserve / 10**18
                price_impact_percent = (kas_amount_kas / virtual_kas_reserve_kas) * 100
                price_impact_percent = round(price_impact_percent, 2)
            
            result = {
                'tokens_out': tokens_out,
                'fees': {
                    'anti_bot': anti_bot_fee_wei,
                    'platform': platform_fee_wei,
                    'creator': creator_fee_wei
                },
                'auto_slippage_bps': auto_slippage_bps,
                'price_impact_percent': price_impact_percent
            }
            
            logging.debug(f"Buy quote: {kas_amount} wei KAS → {tokens_out} wei tokens, fees (wei): anti_bot={anti_bot_fee_wei}, platform={platform_fee_wei}, creator={creator_fee_wei}, slippage: {auto_slippage_bps} bps, impact: {price_impact_percent}%")
            return result
            
        except Exception as e:
            logging.error(f"Failed to get buy quote for pool {pool_address}: {str(e)}")
            raise
    
    def get_sell_quote(self, pool_address, token_amount):
        """
        Get comprehensive sell quote from bonding curve pool
        
        Args:
            pool_address (str): Pool contract address
            token_amount (int): Token amount in wei
        
        Returns:
            dict: {
                'kas_out': int (in wei, NET amount user receives),
                'fees': {
                    'anti_bot': int (in wei, always 0 for sell),
                    'platform': int (in wei),
                    'creator': int (in wei)
                },
                'auto_slippage_bps': int,
                'price_impact_percent': float
            }
        """
        try:
            logging.debug(f"Getting sell quote for pool {pool_address} - Tokens: {token_amount}")
            
            pool = self.get_bonding_pool_contract(pool_address)
            
            # quoteSell() returns GROSS KAS (AMM output BEFORE fees)
            # See BondingCurvePool.sol line 220: uint256 kasGross = quoteSell(tokenAmount);
            kas_gross = pool.functions.quoteSell(token_amount).call()
            
            # Sells have NO anti-bot fees, only 1% total (0.9% platform + 0.1% creator)
            # See BondingCurvePool.sol lines 223-225
            TOTAL_FEE_BPS = 100  # 1%
            PLATFORM_FEE_BPS = 90  # 0.9%
            CREATOR_FEE_BPS = 10  # 0.1%
            
            # Calculate fees from GROSS amount
            total_fees = kas_gross * TOTAL_FEE_BPS // 10000
            platform_fee_wei = kas_gross * PLATFORM_FEE_BPS // 10000
            creator_fee_wei = kas_gross * CREATOR_FEE_BPS // 10000
            anti_bot_fee_wei = 0  # No anti-bot fees on sells
            
            # NET is what user actually receives (GROSS - fees)
            kas_net = kas_gross - total_fees
            
            # Calculate auto slippage on NET amount
            auto_slippage_bps = pool.functions.calculateOptimalSlippage(kas_net).call()
            
            virtual_token_reserve = pool.functions.virtualTokenReserve().call()
            price_impact_percent = 0.0
            if virtual_token_reserve > 0:
                token_amount_tokens = token_amount / 10**18
                virtual_token_reserve_tokens = virtual_token_reserve / 10**18
                price_impact_percent = (token_amount_tokens / virtual_token_reserve_tokens) * 100
                price_impact_percent = round(price_impact_percent, 2)
            
            result = {
                'kas_out': kas_net,  # NET amount user receives
                'fees': {
                    'anti_bot': anti_bot_fee_wei,  # Always 0 for sells
                    'platform': platform_fee_wei,
                    'creator': creator_fee_wei
                },
                'auto_slippage_bps': auto_slippage_bps,
                'price_impact_percent': price_impact_percent
            }
            
            logging.debug(f"Sell quote: {token_amount} wei tokens → {kas_net} wei KAS (net), fees (wei): platform={platform_fee_wei}, creator={creator_fee_wei}, slippage: {auto_slippage_bps} bps, impact: {price_impact_percent}%")
            return result
            
        except Exception as e:
            logging.error(f"Failed to get sell quote for pool {pool_address}: {str(e)}")
            raise
    
    def get_bonding_curve_quote(self, pool_address, direction, kas_amount=None, token_amount=None):
        """
        Unified bidirectional quote function for bonding curve trading
        
        Args:
            pool_address (str): Pool contract address
            direction (str): 'buy' or 'sell'
            kas_amount (int, optional): KAS amount in wei (input for buy, output for sell)
            token_amount (int, optional): Token amount in wei (output for buy, input for sell)
        
        Returns:
            dict: {
                'kas_amount': int (in wei),
                'token_amount': int (in wei),
                'fees': {
                    'anti_bot': int (in wei),
                    'platform': int (in wei),
                    'creator': int (in wei)
                },
                'price_impact_percent': float,
                'auto_slippage_bps': int
            }
        
        Raises:
            ValueError: If both or neither amounts are provided, or invalid direction
        """
        # Validate inputs
        if direction not in ['buy', 'sell']:
            raise ValueError("direction must be 'buy' or 'sell'")
        
        if kas_amount is not None and token_amount is not None:
            raise ValueError("Exactly one of kas_amount or token_amount must be provided, not both")
        
        if kas_amount is None and token_amount is None:
            raise ValueError("Either kas_amount or token_amount must be provided")
        
        # Convert string inputs to integers (API may pass strings)
        if kas_amount is not None:
            kas_amount = int(kas_amount) if isinstance(kas_amount, str) else kas_amount
        if token_amount is not None:
            token_amount = int(token_amount) if isinstance(token_amount, str) else token_amount
        
        try:
            if direction == 'buy':
                if kas_amount is not None:
                    # Forward buy: kas_amount → token_amount
                    result = self.get_buy_quote(pool_address, kas_amount)
                    return {
                        'kas_amount': kas_amount,
                        'token_amount': result['tokens_out'],
                        'fees': result['fees'],
                        'price_impact_percent': result['price_impact_percent'],
                        'auto_slippage_bps': result['auto_slippage_bps']
                    }
                else:
                    # Inverse buy: token_amount → kas_amount (solve for kas_amount)
                    solved_kas_amount = self._solve_buy_for_kas_amount(pool_address, token_amount)
                    result = self.get_buy_quote(pool_address, solved_kas_amount)
                    return {
                        'kas_amount': solved_kas_amount,
                        'token_amount': result['tokens_out'],
                        'fees': result['fees'],
                        'price_impact_percent': result['price_impact_percent'],
                        'auto_slippage_bps': result['auto_slippage_bps']
                    }
            
            else:  # direction == 'sell'
                if token_amount is not None:
                    # Forward sell: token_amount → kas_amount
                    result = self.get_sell_quote(pool_address, token_amount)
                    return {
                        'kas_amount': result['kas_out'],
                        'token_amount': token_amount,
                        'fees': result['fees'],
                        'price_impact_percent': result['price_impact_percent'],
                        'auto_slippage_bps': result['auto_slippage_bps']
                    }
                else:
                    # Inverse sell: kas_amount → token_amount (solve for token_amount)
                    solved_token_amount = self._solve_sell_for_token_amount(pool_address, kas_amount)
                    result = self.get_sell_quote(pool_address, solved_token_amount)
                    return {
                        'kas_amount': result['kas_out'],
                        'token_amount': solved_token_amount,
                        'fees': result['fees'],
                        'price_impact_percent': result['price_impact_percent'],
                        'auto_slippage_bps': result['auto_slippage_bps']
                    }
                    
        except Exception as e:
            logging.error(f"Failed to get bonding curve quote: {str(e)}")
            raise
    
    def _solve_buy_for_kas_amount(self, pool_address, target_token_amount):
        """
        Solve for kas_amount that produces target_token_amount in a buy
        Uses warm-start binary search with price estimate for faster convergence
        
        Args:
            pool_address (str): Pool contract address
            target_token_amount (int): Desired token amount in wei
        
        Returns:
            int: KAS amount in wei that produces target_token_amount
        """
        # WARM START: Get price estimate from a small forward quote
        try:
            # Use 1 KAS as sample to get current price
            sample_kas = 10**18  # 1 KAS in wei
            sample_result = self.get_buy_quote(pool_address, sample_kas)
            tokens_per_kas = sample_result['tokens_out'] / sample_kas
            
            # Estimate KAS needed (with 20% buffer for price impact)
            estimated_kas = int((target_token_amount / tokens_per_kas) * 1.2)
            
            # Set tighter bounds around estimate
            low = max(0, int(estimated_kas * 0.5))
            high = int(estimated_kas * 2.0)
            
            logging.info(f"✅ Warm start buy: sample {sample_kas} KAS → {sample_result['tokens_out']} tokens, estimated {estimated_kas} KAS for target {target_token_amount} tokens")
        except Exception as e:
            # Fallback to wide bounds if warm start fails
            logging.warning(f"⚠️ Warm start buy failed: {str(e)}, using wide bounds")
            low = 0
            high = 10**22
        
        # Optimized binary search parameters
        tolerance = 10**17  # 0.1 token tolerance - imperceptible to users
        max_iterations = 12  # Reduced from 30 for sub-2s response
        
        for iteration in range(max_iterations):
            mid = (low + high) // 2
            
            try:
                result = self.get_buy_quote(pool_address, mid)
                tokens_out = result['tokens_out']
                
                # Early exit if within tolerance
                if abs(tokens_out - target_token_amount) <= tolerance:
                    logging.debug(f"Solved buy: {mid} wei KAS → {tokens_out} wei tokens (target: {target_token_amount}, iterations: {iteration + 1})")
                    return mid
                
                if tokens_out < target_token_amount:
                    low = mid + 1
                else:
                    high = mid - 1
                    
            except Exception as e:
                # If quote fails at this amount, try lower
                high = mid - 1
        
        # Return best approximation (might not have hit exact tolerance)
        final_result = self.get_buy_quote(pool_address, mid)
        logging.info(f"🎯 Buy solver: {mid} wei KAS → {final_result['tokens_out']} tokens (target: {target_token_amount}, error: {abs(final_result['tokens_out'] - target_token_amount)})")
        return mid
    
    def _solve_sell_for_token_amount(self, pool_address, target_kas_amount):
        """
        Solve for token_amount that produces target_kas_amount in a sell
        Uses warm-start binary search with price estimate for faster convergence
        
        Args:
            pool_address (str): Pool contract address
            target_kas_amount (int): Desired KAS amount in wei (NET amount user receives)
        
        Returns:
            int: Token amount in wei that produces target_kas_amount
        """
        # WARM START: Get price estimate from a small forward quote
        try:
            # Use 1000 tokens as sample to get current price
            sample_tokens = 10**21  # 1000 tokens in wei
            sample_result = self.get_sell_quote(pool_address, sample_tokens)
            kas_per_token = sample_result['kas_out'] / sample_tokens
            
            # Estimate tokens needed (with 20% buffer for price impact)
            estimated_tokens = int((target_kas_amount / kas_per_token) * 1.2)
            
            # Set tighter bounds around estimate
            low = max(0, int(estimated_tokens * 0.5))
            high = int(estimated_tokens * 2.0)
            
            logging.info(f"✅ Warm start sell: sample {sample_tokens} tokens → {sample_result['kas_out']} KAS, estimated {estimated_tokens} tokens for target {target_kas_amount} KAS")
        except Exception as e:
            # Fallback to wide bounds if warm start fails
            logging.warning(f"⚠️ Warm start sell failed: {str(e)}, using wide bounds")
            low = 0
            high = 10**25
        
        # Optimized binary search parameters
        tolerance = 10**17  # 0.1 KAS tolerance - imperceptible to users
        max_iterations = 12  # Reduced from 30 for sub-2s response
        
        for iteration in range(max_iterations):
            mid = (low + high) // 2
            
            try:
                result = self.get_sell_quote(pool_address, mid)
                kas_out = result['kas_out']  # NET amount
                
                # Early exit if within tolerance
                if abs(kas_out - target_kas_amount) <= tolerance:
                    logging.debug(f"Solved sell: {mid} wei tokens → {kas_out} wei KAS (target: {target_kas_amount}, iterations: {iteration + 1})")
                    return mid
                
                if kas_out < target_kas_amount:
                    low = mid + 1
                else:
                    high = mid - 1
                    
            except Exception as e:
                # If quote fails at this amount, try lower
                high = mid - 1
        
        # Return best approximation (might not have hit exact tolerance)
        final_result = self.get_sell_quote(pool_address, mid)
        logging.info(f"🎯 Sell solver: {mid} wei tokens → {final_result['kas_out']} KAS (target: {target_kas_amount}, error: {abs(final_result['kas_out'] - target_kas_amount)})")
        return mid
    
    def get_auto_slippage(self, pool_address, kas_amount):
        """
        Get minimum tokens out with auto-calculated slippage
        
        Args:
            pool_address (str): Pool contract address
            kas_amount (int): KAS amount in wei
        
        Returns:
            int: Minimum tokens out with auto slippage (in wei)
        """
        try:
            logging.debug(f"Getting auto slippage for pool {pool_address} - KAS: {kas_amount}")
            
            pool = self.get_bonding_pool_contract(pool_address)
            min_tokens_out = pool.functions.getMinTokensOutWithAutoSlippage(kas_amount).call()
            
            logging.debug(f"Auto slippage: {kas_amount} wei KAS → min {min_tokens_out} wei tokens")
            return min_tokens_out
            
        except Exception as e:
            logging.error(f"Failed to get auto slippage for pool {pool_address}: {str(e)}")
            raise
    
    def buy_tokens_tx_data(self, user_address, pool_address, kas_amount, min_tokens_out, deadline):
        """
        Build transaction data for pool.buyTokens() - USER TRANSACTION (PAYABLE)
        
        Args:
            user_address (str): User's wallet address
            pool_address (str): Pool contract address
            kas_amount (int): KAS amount to send (in wei)
            min_tokens_out (int): Minimum tokens to receive (in wei)
            deadline (int): Transaction deadline (unix timestamp)
        
        Returns:
            dict: Unsigned transaction dict {from, to, data, value, gas}
        """
        try:
            logging.info(f"Building buyTokens tx for user {user_address} - Pool: {pool_address}, KAS: {kas_amount}")
            
            # Build contract call
            pool = self.get_bonding_pool_contract(pool_address)
            tx_data = pool.functions.buyTokens(
                min_tokens_out,
                deadline
            ).build_transaction({
                'from': Web3.to_checksum_address(user_address),
                'value': kas_amount,
                'gas': 0,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(Web3.to_checksum_address(user_address))
            })
            
            # Estimate gas
            gas_estimate = self.estimate_gas({
                'from': tx_data['from'],
                'to': tx_data['to'],
                'data': tx_data['data'],
                'value': tx_data['value']
            })
            
            tx_data['gas'] = gas_estimate['gas']
            
            logging.info(f"buyTokens tx built - Gas: {gas_estimate['gas']}, Total cost: {self.w3.from_wei(kas_amount + gas_estimate['cost_wei'], 'ether')} KAS")
            return tx_data
            
        except Exception as e:
            logging.error(f"Failed to build buyTokens tx: {str(e)}")
            raise
    
    def sell_tokens_tx_data(self, user_address, pool_address, token_amount, min_kas_out, deadline):
        """
        Build transaction data for pool.sellTokens() - USER TRANSACTION
        
        Args:
            user_address (str): User's wallet address
            pool_address (str): Pool contract address
            token_amount (int): Token amount to sell (in wei)
            min_kas_out (int): Minimum KAS to receive (in wei)
            deadline (int): Transaction deadline (unix timestamp)
        
        Returns:
            dict: Unsigned transaction dict {from, to, data, value, gas}
        """
        try:
            logging.info(f"Building sellTokens tx for user {user_address} - Pool: {pool_address}, Tokens: {token_amount}")
            
            # Build contract call
            pool = self.get_bonding_pool_contract(pool_address)
            tx_data = pool.functions.sellTokens(
                token_amount,
                min_kas_out,
                deadline
            ).build_transaction({
                'from': Web3.to_checksum_address(user_address),
                'value': 0,
                'gas': 0,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(Web3.to_checksum_address(user_address))
            })
            
            # Estimate gas
            gas_estimate = self.estimate_gas({
                'from': tx_data['from'],
                'to': tx_data['to'],
                'data': tx_data['data'],
                'value': tx_data['value']
            })
            
            tx_data['gas'] = gas_estimate['gas']
            
            logging.info(f"sellTokens tx built - Gas: {gas_estimate['gas']}, Cost: {gas_estimate['cost_kas']} KAS")
            return tx_data
            
        except Exception as e:
            logging.error(f"Failed to build sellTokens tx: {str(e)}")
            raise
    
    # =========================
    # DEX Trading Methods (Post-Graduation)
    # =========================
    
    def get_dex_buy_quote(self, token_address, pool_address, kas_amount, fee_tier=FEE_TIER_025):
        """
        Get quote for buying tokens via Kaspa Finance DEX using pool state + V3 math
        
        Bypasses QuoterV2 due to ABI compatibility issues with Kaspa Finance.
        Reads pool reserves and calculates quotes using Uniswap V3 formulas.
        
        Args:
            token_address (str): Token contract address
            pool_address (str): DEX pool contract address
            kas_amount (int): KAS amount to spend (in wei)
            fee_tier (int): Pool fee tier (2500 for 0.25%)
        
        Returns:
            dict: {
                'tokens_out': int (wei),
                'price_impact_percent': float,
                'execution_price': float (KAS per token),
                'gas_estimate': int
            }
        """
        try:
            logging.info(f"Getting DEX buy quote via pool state: {kas_amount} wei KAS for fee tier {fee_tier}")
            
            # Normalize addresses
            token_address = Web3.to_checksum_address(token_address)
            wkas_address = Web3.to_checksum_address(KASPA_FINANCE_WKAS)
            
            # Use V3 quoter to calculate quote from pool reserves
            result = v3_quoter.calculate_exact_input_quote(
                self.w3,
                pool_address,
                wkas_address,
                token_address,
                kas_amount,
                fee_tier
            )
            
            tokens_out = result['amount_out']
            gas_estimate = result['gas_estimate']
            price_impact_percent = result['price_impact_percent']
            
            # Calculate execution price
            execution_price = kas_amount / tokens_out if tokens_out > 0 else 0
            
            logging.info(f"DEX buy quote: {kas_amount} KAS → {tokens_out} tokens (impact: {price_impact_percent:.2f}%, gas: {gas_estimate})")
            
            return {
                'tokens_out': tokens_out,
                'price_impact_percent': price_impact_percent,
                'execution_price': execution_price,
                'gas_estimate': gas_estimate
            }
            
        except Exception as e:
            logging.error(f"Failed to get DEX buy quote: {str(e)}")
            raise
    
    def get_dex_sell_quote(self, token_address, pool_address, token_amount, fee_tier=FEE_TIER_025):
        """
        Get quote for selling tokens via Kaspa Finance DEX using pool state + V3 math
        
        Bypasses QuoterV2 due to ABI compatibility issues with Kaspa Finance.
        Reads pool reserves and calculates quotes using Uniswap V3 formulas.
        
        Args:
            token_address (str): Token contract address
            pool_address (str): DEX pool contract address
            token_amount (int): Token amount to sell (in wei)
            fee_tier (int): Pool fee tier (2500 for 0.25%)
        
        Returns:
            dict: {
                'kas_out': int (wei),
                'price_impact_percent': float,
                'execution_price': float (KAS per token),
                'gas_estimate': int
            }
        """
        try:
            logging.info(f"Getting DEX sell quote via pool state: {token_amount} wei tokens for fee tier {fee_tier}")
            
            # Normalize addresses
            token_address = Web3.to_checksum_address(token_address)
            wkas_address = Web3.to_checksum_address(KASPA_FINANCE_WKAS)
            
            # Use V3 quoter to calculate quote from pool reserves
            result = v3_quoter.calculate_exact_input_quote(
                self.w3,
                pool_address,
                token_address,
                wkas_address,
                token_amount,
                fee_tier
            )
            
            kas_out = result['amount_out']
            gas_estimate = result['gas_estimate']
            price_impact_percent = result['price_impact_percent']
            
            # Calculate execution price
            execution_price = kas_out / token_amount if token_amount > 0 else 0
            
            logging.info(f"DEX sell quote: {token_amount} tokens → {kas_out} WKAS (impact: {price_impact_percent:.2f}%, gas: {gas_estimate})")
            
            return {
                'kas_out': kas_out,
                'price_impact_percent': price_impact_percent,
                'execution_price': execution_price,
                'gas_estimate': int(gas_estimate)
            }
            
        except Exception as e:
            logging.error(f"Failed to get DEX sell quote: {str(e)}")
            raise
    
    def build_dex_buy_tx(self, user_address, token_address, kas_amount, min_tokens_out, deadline, fee_tier=FEE_TIER_025):
        """
        Build transaction for buying tokens via Kaspa Finance DEX using native KAS
        
        Uses Uniswap V3 pattern: exactInputSingle wrapped in multicall with refundETH
        to return any unused KAS to the user.
        
        Args:
            user_address (str): User's wallet address
            token_address (str): Token contract address
            kas_amount (int): KAS amount to spend (in wei)
            min_tokens_out (int): Minimum tokens to receive (slippage protection)
            deadline (int): Transaction deadline (unix timestamp)
            fee_tier (int): Pool fee tier (2500 for 0.25%)
        
        Returns:
            dict: Unsigned transaction dict {from, to, data, value}
        """
        try:
            logging.info(f"Building DEX buy tx - Token: {token_address}, KAS: {kas_amount}, Fee tier: {fee_tier}")
            
            swap_router = self.contracts['SwapRouter']
            user_address = Web3.to_checksum_address(user_address)
            token_address = Web3.to_checksum_address(token_address)
            wkas_address = Web3.to_checksum_address(KASPA_FINANCE_WKAS)
            
            # Build ExactInputSingleParams struct for swapping WKAS → Token
            # struct ExactInputSingleParams {
            #     address tokenIn;
            #     address tokenOut;
            #     uint24 fee;
            #     address recipient;
            #     uint256 deadline;
            #     uint256 amountIn;
            #     uint256 amountOutMinimum;
            #     uint160 sqrtPriceLimitX96;
            # }
            exact_input_params = (
                wkas_address,           # tokenIn (WKAS)
                token_address,          # tokenOut (Token)
                fee_tier,               # fee (e.g., 2500 = 0.25%)
                user_address,           # recipient
                deadline,               # deadline
                kas_amount,             # amountIn
                min_tokens_out,         # amountOutMinimum
                0                       # sqrtPriceLimitX96 (0 = no limit)
            )
            
            # Encode exactInputSingle and refundETH calls
            exact_input_encoded = swap_router.functions.exactInputSingle(exact_input_params)._encode_transaction_data()
            refund_eth_encoded = swap_router.functions.refundETH()._encode_transaction_data()
            
            # CRITICAL: Kaspa Finance's SwapRouter uses multicall(uint256 deadline, bytes[] data)
            # but our ABI only has multicall(bytes[] data). We need to manually encode the correct version.
            
            # Manually encode multicall(uint256 deadline, bytes[] data)
            # Function selector for multicall(uint256,bytes[])
            from eth_abi import encode
            
            # Calculate correct function selector
            multicall_with_deadline_sig = "multicall(uint256,bytes[])"
            multicall_selector = Web3.keccak(text=multicall_with_deadline_sig)[:4]
            
            # Encode the parameters: deadline (uint256) and data array (bytes[])
            encoded_params = encode(
                ['uint256', 'bytes[]'],
                [deadline, [exact_input_encoded[10:], refund_eth_encoded[10:]]]  # Remove '0x' + 8-char selector from each
            )
            
            # Combine selector and encoded params
            multicall_encoded = multicall_selector.hex() + encoded_params.hex()
            
            # Get current base fee for EIP-1559
            latest_block = self.w3.eth.get_block('latest')
            base_fee = latest_block['baseFeePerGas']
            
            # Set EIP-1559 parameters
            max_fee_per_gas = hex(base_fee * 2)
            max_priority_fee = hex(0)  # Kasplex doesn't support priority fees
            
            tx_data = {
                'from': user_address,
                'to': swap_router.address,
                'value': hex(kas_amount),
                'data': '0x' + multicall_encoded,
                'gas': hex(350000),  # 350k gas for DEX swap
                'maxFeePerGas': max_fee_per_gas,
                'maxPriorityFeePerGas': max_priority_fee
            }
            
            logging.info(f"✅ DEX buy tx built - multicall(deadline, [exactInputSingle, refundETH]) - Gas: 350000")
            return tx_data
            
        except Exception as e:
            logging.error(f"Failed to build DEX buy tx: {str(e)}")
            raise
    
    def build_dex_sell_tx(self, user_address, token_address, token_amount, min_kas_out, deadline, fee_tier=FEE_TIER_025):
        """
        Build transaction for selling tokens via Kaspa Finance DEX
        
        NOTE: User must approve token spending before calling this (approve SwapRouter)
        
        Uses exactInputSingle to swap Token → WKAS, then user can unwrap WKAS → KAS separately.
        
        Args:
            user_address (str): User's wallet address
            token_address (str): Token contract address
            token_amount (int): Token amount to sell (in wei)
            min_kas_out (int): Minimum WKAS to receive (slippage protection)
            deadline (int): Transaction deadline (unix timestamp)
            fee_tier (int): Pool fee tier (2500 for 0.25%)
        
        Returns:
            dict: Unsigned transaction dict {from, to, data, value}
        """
        try:
            logging.info(f"Building DEX sell tx - Token: {token_address}, Amount: {token_amount}, Fee tier: {fee_tier}")
            
            swap_router = self.contracts['SwapRouter']
            user_address = Web3.to_checksum_address(user_address)
            token_address = Web3.to_checksum_address(token_address)
            wkas_address = Web3.to_checksum_address(KASPA_FINANCE_WKAS)
            
            # Build ExactInputSingleParams struct for swapping Token → WKAS
            # struct ExactInputSingleParams {
            #     address tokenIn;
            #     address tokenOut;
            #     uint24 fee;
            #     address recipient;
            #     uint256 deadline;
            #     uint256 amountIn;
            #     uint256 amountOutMinimum;
            #     uint160 sqrtPriceLimitX96;
            # }
            exact_input_params = (
                token_address,          # tokenIn (Token)
                wkas_address,           # tokenOut (WKAS)
                fee_tier,               # fee (e.g., 2500 = 0.25%)
                user_address,           # recipient
                deadline,               # deadline
                token_amount,           # amountIn
                min_kas_out,            # amountOutMinimum
                0                       # sqrtPriceLimitX96 (0 = no limit)
            )
            
            # Encode function call
            encoded_data = swap_router.functions.exactInputSingle(exact_input_params)._encode_transaction_data()
            
            # Get current base fee for EIP-1559
            latest_block = self.w3.eth.get_block('latest')
            base_fee = latest_block['baseFeePerGas']
            
            # Set EIP-1559 parameters (Kasplex doesn't support priority fees)
            max_fee_per_gas = hex(base_fee * 2)
            max_priority_fee = hex(0)
            
            tx_data = {
                'from': user_address,
                'to': swap_router.address,
                'value': '0x0',
                'data': encoded_data,
                'gas': hex(350000),  # 350k gas for DEX swap
                'maxFeePerGas': max_fee_per_gas,
                'maxPriorityFeePerGas': max_priority_fee
            }
            
            logging.info(f"✅ DEX sell tx built - Gas: 350000, MaxFee: {int(max_fee_per_gas, 16)} wei ({int(max_fee_per_gas, 16)/1e9:.1f} gwei)")
            return tx_data
            
        except Exception as e:
            logging.error(f"Failed to build DEX sell tx: {str(e)}")
            raise
    
    def build_wkas_unwrap_tx(self, user_address, wkas_amount):
        """
        Build transaction for unwrapping WKAS → KAS
        
        Args:
            user_address (str): User's wallet address
            wkas_amount (int): WKAS amount to unwrap (in wei)
        
        Returns:
            dict: Unsigned transaction dict {from, to, data, value, gas}
        """
        try:
            logging.info(f"Building WKAS unwrap tx for user {user_address} - Amount: {wkas_amount}")
            
            wkas_contract = self.contracts['WKAS']
            
            # Encode function call
            encoded_data = wkas_contract.functions.withdraw(wkas_amount)._encode_transaction_data()
            
            # Get current base fee for EIP-1559
            latest_block = self.w3.eth.get_block('latest')
            base_fee = latest_block['baseFeePerGas']
            
            # Set EIP-1559 parameters (Kasplex doesn't support priority fees)
            max_fee_per_gas = hex(base_fee * 2)
            max_priority_fee = hex(0)
            
            tx_data = {
                'from': Web3.to_checksum_address(user_address),
                'to': wkas_contract.address,
                'value': '0x0',
                'data': encoded_data,
                'gas': hex(50000),  # 50k gas for WKAS unwrap
                'maxFeePerGas': max_fee_per_gas,
                'maxPriorityFeePerGas': max_priority_fee
            }
            
            logging.info(f"WKAS unwrap tx built - Gas: 50000")
            return tx_data
            
        except Exception as e:
            logging.error(f"Failed to build WKAS unwrap tx: {str(e)}")
            raise
    
    def get_dex_buy_quote_reverse(self, token_address, pool_address, tokens_out, fee_tier=FEE_TIER_025):
        """
        REVERSE calculation: Calculate KAS needed to buy a specific amount of tokens using QuoterV2
        
        Uses Uniswap V3 concentrated liquidity quoting for accurate price discovery.
        
        Args:
            token_address (str): Token contract address
            pool_address (str): DEX pool contract address (not used, QuoterV2 finds pool by tokens+fee)
            tokens_out (int): Desired token amount to receive (in wei)
            fee_tier (int): Pool fee tier (default 0.30% = 3000)
        
        Returns:
            dict: {
                'kas_in': int (wei),
                'price_impact_percent': float,
                'execution_price': float (KAS per token),
                'gas_estimate': int
            }
        """
        try:
            logging.info(f"Getting DEX reverse buy quote via V3 math: Want {tokens_out} wei tokens")
            
            # Normalize addresses
            token_address = Web3.to_checksum_address(token_address)
            wkas_address = Web3.to_checksum_address(KASPA_FINANCE_WKAS)
            
            # Use V3 quoter to calculate exact output quote
            result = v3_quoter.calculate_exact_output_quote(
                self.w3,
                pool_address,
                wkas_address,
                token_address,
                tokens_out,
                fee_tier
            )
            
            kas_in = result['amount_in']
            gas_estimate = result['gas_estimate']
            price_impact_percent = result['price_impact_percent']
            
            # Calculate execution price
            execution_price = kas_in / tokens_out if tokens_out > 0 else 0
            
            logging.info(f"DEX reverse buy quote (V3 math): {kas_in} KAS needed → {tokens_out} tokens (gas: {gas_estimate}, impact: {price_impact_percent:.2f}%)")
            
            return {
                'kas_in': kas_in,
                'price_impact_percent': price_impact_percent,
                'execution_price': execution_price,
                'gas_estimate': gas_estimate
            }
            
        except Exception as e:
            logging.error(f"Failed to get DEX reverse buy quote: {str(e)}")
            raise
    
    def get_dex_sell_quote_reverse(self, token_address, pool_address, kas_out, fee_tier=FEE_TIER_025):
        """
        REVERSE calculation: Calculate tokens needed to sell to get a specific amount of KAS using V3 math
        
        Uses deterministic Uniswap V3 math for accurate price discovery.
        Reads pool state directly and calculates quotes without QuoterV2.
        
        Args:
            token_address (str): Token contract address
            pool_address (str): DEX pool contract address
            kas_out (int): Desired KAS amount to receive (in wei)
            fee_tier (int): Pool fee tier (default 0.30% = 3000)
        
        Returns:
            dict: {
                'tokens_in': int (wei),
                'price_impact_percent': float,
                'execution_price': float (KAS per token),
                'gas_estimate': int
            }
        """
        try:
            logging.info(f"Getting DEX reverse sell quote via V3 math: Want {kas_out} wei KAS")
            
            # Normalize addresses
            token_address = Web3.to_checksum_address(token_address)
            wkas_address = Web3.to_checksum_address(KASPA_FINANCE_WKAS)
            
            # Use V3 quoter to calculate exact output quote
            result = v3_quoter.calculate_exact_output_quote(
                self.w3,
                pool_address,
                token_address,
                wkas_address,
                kas_out,
                fee_tier
            )
            
            tokens_in = result['amount_in']
            gas_estimate = result['gas_estimate']
            price_impact_percent = result['price_impact_percent']
            
            # Calculate execution price
            execution_price = kas_out / tokens_in if tokens_in > 0 else 0
            
            logging.info(f"DEX reverse sell quote (V3 math): {tokens_in} tokens needed → {kas_out} KAS (gas: {gas_estimate}, impact: {price_impact_percent:.2f}%)")
            
            return {
                'tokens_in': tokens_in,
                'price_impact_percent': price_impact_percent,
                'execution_price': execution_price,
                'gas_estimate': gas_estimate
            }
            
        except Exception as e:
            logging.error(f"Failed to get DEX reverse sell quote: {str(e)}")
            raise
    
    def get_dex_quote(self, side, token_address, pool_address, amount_in=None, amount_out=None, fee_tier=FEE_TIER_025):
        """
        Unified DEX quote method (wraps buy/sell quotes with forward and reverse calculations)
        
        Args:
            side (str): 'buy' or 'sell'
            token_address (str): Token contract address
            pool_address (str): DEX pool contract address
            amount_in (int): Amount in wei (KAS for buy, tokens for sell) - for forward calculation
            amount_out (int): Amount out wei (tokens for buy, KAS for sell) - for reverse calculation
            fee_tier (int): Pool fee tier (default 0.30% = 3000)
        
        Returns:
            dict: {
                'amount_out': int (wei) OR 'amount_in': int (wei),
                'execution_price': float (KAS per token),
                'price_impact_pct': float,
                'gas_estimate': int,
                'fee_tier': int
            }
        """
        try:
            if amount_in is not None and amount_out is not None:
                raise ValueError("Specify either amount_in OR amount_out, not both")
            if amount_in is None and amount_out is None:
                raise ValueError("Must specify either amount_in or amount_out")
            
            # Forward calculation (amount_in → amount_out)
            if amount_in is not None:
                logging.info(f"Getting DEX {side} quote (forward): {amount_in} wei from pool {pool_address}")
                
                if side == 'buy':
                    quote = self.get_dex_buy_quote(token_address, pool_address, amount_in, fee_tier)
                    return {
                        'amount_out': quote['tokens_out'],
                        'execution_price': quote['execution_price'],
                        'price_impact_pct': quote['price_impact_percent'],
                        'gas_estimate': quote['gas_estimate'],
                        'fee_tier': fee_tier
                    }
                elif side == 'sell':
                    quote = self.get_dex_sell_quote(token_address, pool_address, amount_in, fee_tier)
                    return {
                        'amount_out': quote['kas_out'],
                        'execution_price': quote['execution_price'],
                        'price_impact_pct': quote['price_impact_percent'],
                        'gas_estimate': quote['gas_estimate'],
                        'fee_tier': fee_tier
                    }
            
            # Reverse calculation (amount_out → amount_in)
            else:  # amount_out is not None
                logging.info(f"Getting DEX {side} quote (reverse): want {amount_out} wei from pool {pool_address}")
                
                if side == 'buy':
                    # Reverse buy: Given tokens_out, find kas_in
                    quote = self.get_dex_buy_quote_reverse(token_address, pool_address, amount_out, fee_tier)
                    return {
                        'amount_in': quote['kas_in'],
                        'execution_price': quote['execution_price'],
                        'price_impact_pct': quote['price_impact_percent'],
                        'gas_estimate': quote['gas_estimate'],
                        'fee_tier': fee_tier
                    }
                elif side == 'sell':
                    # Reverse sell: Given kas_out, find tokens_in
                    quote = self.get_dex_sell_quote_reverse(token_address, pool_address, amount_out, fee_tier)
                    return {
                        'amount_in': quote['tokens_in'],
                        'execution_price': quote['execution_price'],
                        'price_impact_pct': quote['price_impact_percent'],
                        'gas_estimate': quote['gas_estimate'],
                        'fee_tier': fee_tier
                    }
                
            raise ValueError(f"Invalid side: {side}. Must be 'buy' or 'sell'")
                
        except Exception as e:
            logging.error(f"Failed to get DEX quote: {str(e)}")
            raise
    
    def get_wkas_balance(self, address):
        """
        Get WKAS balance for an address
        
        Args:
            address (str): Wallet address
        
        Returns:
            int: WKAS balance in wei
        """
        try:
            logging.debug(f"Getting WKAS balance for {address}")
            
            wkas_contract = self.contracts['WKAS']
            balance = wkas_contract.functions.balanceOf(
                Web3.to_checksum_address(address)
            ).call()
            
            logging.debug(f"WKAS balance: {balance} wei ({self.w3.from_wei(balance, 'ether')} WKAS)")
            return balance
            
        except Exception as e:
            logging.error(f"Failed to get WKAS balance for {address}: {str(e)}")
            raise
    
    def get_dex_pool_reserves(self, pool_address):
        """
        Get DEX pool reserves (token0 and token1 reserves)
        
        Note: This requires the Uniswap V3 Pool contract interface
        Returns slot0 data for price calculation
        
        Args:
            pool_address (str): Uniswap V3 pool address
        
        Returns:
            dict: {
                'reserve_token': int (token reserve in wei),
                'reserve_wkas': int (WKAS reserve in wei),
                'price': float (current price from slot0)
            }
        """
        try:
            logging.info(f"Getting DEX pool reserves for {pool_address}")
            
            # Load Uniswap V3 Pool interface
            pool_contract = self.get_uniswap_v3_pool_contract(pool_address)
            
            # Get slot0 for current price
            slot0 = pool_contract.functions.slot0().call()
            sqrtPriceX96 = slot0[0]
            
            # Calculate price from sqrtPriceX96
            # price = (sqrtPriceX96 / 2^96)^2
            price = (sqrtPriceX96 / (2**96)) ** 2
            
            # Get liquidity
            liquidity = pool_contract.functions.liquidity().call()
            
            # Note: Uniswap V3 doesn't have simple reserve0/reserve1 like V2
            # Reserves are distributed across ticks based on positions
            # For now, return price and liquidity
            
            logging.info(f"Pool price: {price}, liquidity: {liquidity}")
            
            return {
                'reserve_token': 0,  # V3 doesn't have simple reserves
                'reserve_wkas': 0,
                'price': price,
                'liquidity': liquidity,
                'sqrtPriceX96': sqrtPriceX96
            }
            
        except Exception as e:
            logging.error(f"Failed to get DEX pool reserves for {pool_address}: {str(e)}")
            raise
    
    def get_graduated_token_market_cap(self, token_address, pool_address, kas_price_usd):
        """
        Calculate market cap for a graduated token using DEX pool data
        
        Args:
            token_address (str): Token contract address
            pool_address (str): Uniswap V3 pool address
            kas_price_usd (float): Current KAS/USD price
        
        Returns:
            dict: {
                'market_cap_usd': float,
                'price_kas': float,
                'price_usd': float,
                'total_supply': int,
                'kas_reserve': float,
                'token_reserve': float
            }
        """
        try:
            logging.info(f"Calculating market cap for graduated token {token_address}")
            
            # Get token contract to read total supply and balances
            token_contract = self.get_bonding_pool_contract(token_address)
            
            # Get total supply
            total_supply_wei = token_contract.functions.totalSupply().call()
            total_supply = total_supply_wei / 10**18
            
            # Get actual token balances in the pool (not virtual reserves)
            # This works for both Uniswap V2 and V3 pools
            token_balance_in_pool = token_contract.functions.balanceOf(
                Web3.to_checksum_address(pool_address)
            ).call()
            
            # Get WKAS balance in pool
            wkas_contract = self.contracts['WKAS']
            kas_balance_in_pool = wkas_contract.functions.balanceOf(
                Web3.to_checksum_address(pool_address)
            ).call()
            
            # Convert to human-readable
            token_reserve = token_balance_in_pool / 10**18
            kas_reserve = kas_balance_in_pool / 10**18
            
            # Calculate price: KAS per token
            if token_reserve > 0:
                price_kas = kas_reserve / token_reserve
            else:
                # Fallback to pool slot0 price if no reserves
                pool_data = self.get_dex_pool_reserves(pool_address)
                price_kas = pool_data['price']
            
            # Calculate market cap
            price_usd = price_kas * kas_price_usd
            market_cap_usd = total_supply * price_usd
            
            logging.info(
                f"✅ Graduated token market cap: ${market_cap_usd:.2f} "
                f"(Supply: {total_supply:,.0f}, Price: {price_kas:.8f} KAS = ${price_usd:.6f})"
            )
            
            return {
                'market_cap_usd': market_cap_usd,
                'price_kas': price_kas,
                'price_usd': price_usd,
                'total_supply': total_supply,
                'kas_reserve': kas_reserve,
                'token_reserve': token_reserve
            }
            
        except Exception as e:
            logging.error(f"Failed to calculate graduated token market cap: {str(e)}")
            raise
    
    # =========================
    # Creator Fee Methods (Bonding Curve)
    # =========================
    
    def get_creator_claimable(self, pool_address):
        """
        Get claimable creator fees from pool
        
        Args:
            pool_address (str): Pool contract address
        
        Returns:
            int: Claimable amount (in wei)
        """
        try:
            logging.debug(f"Getting creator claimable for pool {pool_address}")
            
            pool = self.get_bonding_pool_contract(pool_address)
            claimable = pool.functions.getCreatorClaimableAmount().call()
            
            logging.debug(f"Creator claimable: {claimable} wei ({self.w3.from_wei(claimable, 'ether')} KAS)")
            return claimable
            
        except Exception as e:
            logging.error(f"Failed to get creator claimable for pool {pool_address}: {str(e)}")
            raise
    
    def withdraw_creator_fees_tx_data(self, user_address, pool_address):
        """
        Build transaction data for pool.withdrawCreatorFees() - USER TRANSACTION
        
        Args:
            user_address (str): User's wallet address (must be creator)
            pool_address (str): Pool contract address
        
        Returns:
            dict: Unsigned transaction dict {from, to, data, value, gas}
        """
        try:
            logging.info(f"Building withdrawCreatorFees tx for user {user_address} - Pool: {pool_address}")
            
            # Build contract call
            pool = self.get_bonding_pool_contract(pool_address)
            tx_data = pool.functions.withdrawCreatorFees().build_transaction({
                'from': Web3.to_checksum_address(user_address),
                'value': 0,
                'gas': 0,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(Web3.to_checksum_address(user_address))
            })
            
            # Estimate gas
            gas_estimate = self.estimate_gas({
                'from': tx_data['from'],
                'to': tx_data['to'],
                'data': tx_data['data'],
                'value': tx_data['value']
            })
            
            tx_data['gas'] = gas_estimate['gas']
            
            logging.info(f"withdrawCreatorFees tx built - Gas: {gas_estimate['gas']}, Cost: {gas_estimate['cost_kas']} KAS")
            return tx_data
            
        except Exception as e:
            logging.error(f"Failed to build withdrawCreatorFees tx: {str(e)}")
            raise
    
    # =========================
    # Task 2.7.2 - Platform Fee Distribution (Admin Only)
    # =========================
    
    def get_platform_claimable(self, pool_address):
        """
        Get claimable platform fees from pool
        
        Args:
            pool_address (str): Pool contract address
        
        Returns:
            int: Claimable platform fees (in wei)
        """
        try:
            logging.debug(f"Getting platform claimable for pool {pool_address}")
            
            pool = self.get_bonding_pool_contract(pool_address)
            claimable = pool.functions.accumulatedPlatformFees().call()
            
            logging.debug(f"Platform claimable: {claimable} wei ({self.w3.from_wei(claimable, 'ether')} KAS)")
            return claimable
            
        except Exception as e:
            logging.error(f"Failed to get platform claimable for pool {pool_address}: {str(e)}")
            raise
    
    def get_creator_total_accumulated(self, pool_address):
        """
        Get total accumulated creator fees from pool
        Note: accumulatedCreatorFees resets on withdrawal, so this represents current available
        
        Args:
            pool_address (str): Pool contract address
        
        Returns:
            int: Accumulated creator fees (in wei)
        """
        try:
            logging.debug(f"Getting creator accumulated fees for pool {pool_address}")
            
            pool = self.get_bonding_pool_contract(pool_address)
            accumulated = pool.functions.accumulatedCreatorFees().call()
            
            logging.debug(f"Creator accumulated: {accumulated} wei ({self.w3.from_wei(accumulated, 'ether')} KAS)")
            return accumulated
            
        except Exception as e:
            logging.error(f"Failed to get creator accumulated for pool {pool_address}: {str(e)}")
            raise
    
    def get_platform_total_accumulated(self, pool_address):
        """
        Get total accumulated platform fees from pool
        Note: accumulatedPlatformFees resets on distribution, so this represents current available
        
        Args:
            pool_address (str): Pool contract address
        
        Returns:
            int: Accumulated platform fees (in wei)
        """
        try:
            logging.debug(f"Getting platform accumulated fees for pool {pool_address}")
            
            pool = self.get_bonding_pool_contract(pool_address)
            accumulated = pool.functions.accumulatedPlatformFees().call()
            
            logging.debug(f"Platform accumulated: {accumulated} wei ({self.w3.from_wei(accumulated, 'ether')} KAS)")
            return accumulated
            
        except Exception as e:
            logging.error(f"Failed to get platform accumulated for pool {pool_address}: {str(e)}")
            raise
    
    def distribute_platform_fees_tx_data(self, admin_address, pool_address):
        """
        Build transaction data for pool.distributeFees() - ADMIN TRANSACTION
        
        This distributes accumulated platform fees to treasury wallets:
        - 40% → Platform Development Wallet
        - 30% → Buyback Reserve Wallet
        - 15% → Kaspa Network Support Wallet
        - 15% → Community Rewards Wallet
        
        Args:
            admin_address (str): Admin's wallet address (must be treasury or admin)
            pool_address (str): Pool contract address
        
        Returns:
            dict: Unsigned transaction dict {from, to, data, value, gas}
        """
        try:
            logging.info(f"Building distributeFees tx for admin {admin_address} - Pool: {pool_address}")
            
            # Build contract call
            pool = self.get_bonding_pool_contract(pool_address)
            tx_data = pool.functions.distributeFees().build_transaction({
                'from': Web3.to_checksum_address(admin_address),
                'value': 0,
                'gas': 0,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(Web3.to_checksum_address(admin_address))
            })
            
            # Estimate gas
            gas_estimate = self.estimate_gas({
                'from': tx_data['from'],
                'to': tx_data['to'],
                'data': tx_data['data'],
                'value': tx_data['value']
            })
            
            tx_data['gas'] = gas_estimate['gas']
            
            logging.info(f"distributeFees tx built - Gas: {gas_estimate['gas']}, Cost: {gas_estimate['cost_kas']} KAS")
            return tx_data
            
        except Exception as e:
            logging.error(f"Failed to build distributeFees tx: {str(e)}")
            raise
    
    # =========================
    # Task 2.12 - Reserve Token Distribution (PRO Tokens)
    # =========================
    
    def distribute_reserve_tx_data(self, user_address, pool_address, recipients, amounts):
        """
        Build transaction data for pool.distributeReserve() - CREATOR TRANSACTION
        
        Distributes reserve tokens to specified recipients (team, marketing, airdrops).
        This is a one-time operation per pool enforced by smart contract.
        
        Args:
            user_address (str): Creator's wallet address (must be pool creator)
            pool_address (str): Pool contract address
            recipients (list): List of recipient wallet addresses
            amounts (list): List of token amounts (in wei) corresponding to recipients
        
        Returns:
            dict: Unsigned transaction dict {from, to, data, value, gas}
        """
        try:
            logging.info(f"Building distributeReserve tx for user {user_address} - Pool: {pool_address}")
            logging.info(f"Recipients: {recipients}, Amounts: {amounts}")
            
            # Convert recipients to checksum addresses
            recipients_checksum = [Web3.to_checksum_address(addr) for addr in recipients]
            
            # Build contract call
            pool = self.get_bonding_pool_contract(pool_address)
            tx_data = pool.functions.distributeReserve(
                recipients_checksum,
                amounts
            ).build_transaction({
                'from': Web3.to_checksum_address(user_address),
                'value': 0,
                'gas': 0,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(Web3.to_checksum_address(user_address))
            })
            
            # Estimate gas
            gas_estimate = self.estimate_gas({
                'from': tx_data['from'],
                'to': tx_data['to'],
                'data': tx_data['data'],
                'value': tx_data['value']
            })
            
            tx_data['gas'] = gas_estimate['gas']
            
            logging.info(f"distributeReserve tx built - Gas: {gas_estimate['gas']}, Cost: {gas_estimate['cost_kas']} KAS")
            return tx_data
            
        except Exception as e:
            logging.error(f"Failed to build distributeReserve tx: {str(e)}")
            raise
    
    def get_reserve_status(self, pool_address):
        """
        Get reserve distribution status from pool
        
        Args:
            pool_address (str): Pool contract address
        
        Returns:
            dict: {
                'distributed': bool,
                'available_reserve': int (in wei),
                'total_reserve': int (in wei)
            }
        """
        try:
            logging.debug(f"Getting reserve status for pool {pool_address}")
            
            pool = self.get_bonding_pool_contract(pool_address)
            result = pool.functions.getReserveStatus().call()
            
            # Result is tuple: (bool distributed, uint256 availableReserve, uint256 totalReserve)
            status = {
                'distributed': result[0],
                'available_reserve': result[1],
                'total_reserve': result[2]
            }
            
            logging.debug(f"Reserve status: distributed={status['distributed']}, "
                         f"available={self.w3.from_wei(status['available_reserve'], 'ether')} tokens, "
                         f"total={self.w3.from_wei(status['total_reserve'], 'ether')} tokens")
            
            return status
            
        except Exception as e:
            logging.error(f"Failed to get reserve status for pool {pool_address}: {str(e)}")
            raise
    
    def get_virtual_kas_reserve(self, pool_address):
        """
        Get real-time virtual KAS reserve from bonding pool contract
        
        Args:
            pool_address (str): Pool contract address
        
        Returns:
            int: Virtual KAS reserve in wei (18 decimals)
        """
        try:
            logging.debug(f"Getting virtual KAS reserve for pool {pool_address}")
            
            pool = self.get_bonding_pool_contract(pool_address)
            kas_reserve_wei = pool.functions.virtualKasReserve().call()
            
            kas_reserve_kas = self.w3.from_wei(kas_reserve_wei, 'ether')
            logging.debug(f"Virtual KAS reserve: {kas_reserve_kas} KAS ({kas_reserve_wei} wei)")
            
            return kas_reserve_wei
            
        except Exception as e:
            logging.error(f"Failed to get virtual KAS reserve for pool {pool_address}: {str(e)}")
            raise
    
    def get_virtual_token_reserve(self, pool_address):
        """
        Get real-time virtual token reserve from bonding pool contract
        
        Args:
            pool_address (str): Pool contract address
        
        Returns:
            int: Virtual token reserve in wei (18 decimals)
        """
        try:
            logging.debug(f"Getting virtual token reserve for pool {pool_address}")
            
            pool = self.get_bonding_pool_contract(pool_address)
            token_reserve_wei = pool.functions.virtualTokenReserve().call()
            
            token_reserve_tokens = self.w3.from_wei(token_reserve_wei, 'ether')
            logging.debug(f"Virtual token reserve: {token_reserve_tokens} tokens ({token_reserve_wei} wei)")
            
            return token_reserve_wei
            
        except Exception as e:
            logging.error(f"Failed to get virtual token reserve for pool {pool_address}: {str(e)}")
            raise
    
    # =========================
    # Task 2.2.3 - GraduationController Interactions (Oracle Only)
    # =========================
    
    def get_pool_graduation_controller(self, pool_address):
        """
        Query which GraduationController a specific pool expects
        
        Args:
            pool_address (str): Pool contract address
        
        Returns:
            str: GraduationController address the pool trusts
        """
        try:
            pool = self.get_bonding_pool_contract(pool_address)
            controller_address = pool.functions.graduationController().call()
            logging.debug(f"Pool {pool_address} expects GraduationController: {controller_address}")
            return controller_address
        except Exception as e:
            logging.warning(f"Could not query graduationController for pool {pool_address}, using default: {str(e)}")
            # Fall back to default controller
            return self.contracts['GraduationController'].address
    
    def initiate_graduation_oracle(self, token_address):
        """
        Oracle signs and relays Pool.initiateGraduation() - ORACLE TRANSACTION
        
        POOL-INITIATED GRADUATION: Oracle calls the pool, which then forwards to its 
        configured GraduationController. This is the only way to initiate graduation
        in GraduationControllerV3 architecture.
        
        Args:
            token_address (str): Token/pool address to graduate
        
        Returns:
            str: Transaction hash
        """
        try:
            logging.info(f"Oracle initiating graduation for token {token_address}")
            
            # Get the pool contract
            pool = self.get_bonding_pool_contract(token_address)
            
            # Build contract call - call POOL.initiateGraduation()
            # The pool will internally call its graduationController.initiateGraduation(msg.sender)
            tx_data = pool.functions.initiateGraduation().build_transaction({
                'from': self.oracle_account.address,
                'value': 0,
                'gas': 0,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.oracle_account.address)
            })
            
            # Estimate gas
            gas_estimate = self.estimate_gas({
                'from': tx_data['from'],
                'to': tx_data['to'],
                'data': tx_data['data'],
                'value': tx_data['value']
            })
            
            tx_data['gas'] = gas_estimate['gas']
            
            # Sign transaction with oracle account
            signed_txn = self.sign_transaction(tx_data)
            
            # Relay transaction
            tx_hash = self.relay_transaction(signed_txn)
            
            logging.info(f"Graduation initiated by oracle - Pool: {token_address}, TX: {tx_hash}")
            return tx_hash
            
        except Exception as e:
            logging.error(f"Failed to initiate graduation for {token_address}: {str(e)}")
            raise
    
    def complete_graduation_via_controller(self, token_address):
        """
        V4 CORRECT FLOW: Oracle calls GraduationController.completeGraduation()
        
        THIS IS THE CORRECT FLOW FOR V4 ARCHITECTURE:
        1. Oracle calls GraduationController.completeGraduation(tokenAddress)
        2. GC creates LP on Kaspa Finance DEX (CRITICAL: LP creation FIRST)
        3. GC calls Pool.completeGraduation() as callback
        4. Pool marks itself graduated (only after LP exists)
        
        SUCCESS METRIC: LP exists on Kaspa Finance before pool marks graduated
        
        Args:
            token_address (str): Token/pool address to complete graduation
        
        Returns:
            str: Transaction hash
        """
        try:
            logging.info(f"🚀 V4 FLOW: Oracle calling GraduationController.completeGraduation({token_address})")
            
            # Get GraduationController contract
            gc = self.contracts['GraduationController']
            
            # Build contract call - call GC.completeGraduation(tokenAddress)
            # This creates LP FIRST, then calls pool as callback
            tx_data = gc.functions.completeGraduation(
                Web3.to_checksum_address(token_address)
            ).build_transaction({
                'from': self.oracle_account.address,
                'value': 0,
                'gas': 0,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.oracle_account.address)
            })
            
            # Estimate gas (high limit for DEX operations)
            gas_estimate = self.estimate_gas({
                'from': tx_data['from'],
                'to': tx_data['to'],
                'data': tx_data['data'],
                'value': tx_data['value']
            })
            
            # Use higher gas limit for DEX operations
            tx_data['gas'] = min(gas_estimate['gas'] * 2, 8000000)
            
            # Sign transaction with oracle account
            signed_txn = self.sign_transaction(tx_data)
            
            # Relay transaction
            tx_hash = self.relay_transaction(signed_txn)
            
            logging.info(f"✅ GC.completeGraduation() called - Token: {token_address}, TX: {tx_hash}")
            logging.info(f"   This will: (1) Create LP on Kaspa Finance, (2) Call pool callback, (3) Mark graduated")
            return tx_hash
            
        except Exception as e:
            logging.error(f"Failed to complete graduation via GC for {token_address}: {str(e)}")
            raise
    
    def complete_graduation_oracle(self, token_address):
        """
        DEPRECATED V3 FLOW - DO NOT USE
        
        This function calls Pool.completeGraduation() directly, which is WRONG!
        It allows the pool to mark itself graduated WITHOUT verifying LP creation.
        
        USE complete_graduation_via_controller() INSTEAD
        
        Args:
            token_address (str): Token/pool address to complete graduation
        
        Returns:
            str: Transaction hash
        """
        logging.warning("⚠️ DEPRECATED: complete_graduation_oracle() calls Pool directly - USE complete_graduation_via_controller() instead!")
        
        try:
            logging.info(f"Oracle completing graduation for token {token_address}")
            
            # Get the pool contract
            pool = self.get_bonding_pool_contract(token_address)
            
            # Build contract call - call POOL.completeGraduation()
            # The pool will internally finalize graduation and emit events
            tx_data = pool.functions.completeGraduation().build_transaction({
                'from': self.oracle_account.address,
                'value': 0,
                'gas': 0,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.oracle_account.address)
            })
            
            # Estimate gas
            gas_estimate = self.estimate_gas({
                'from': tx_data['from'],
                'to': tx_data['to'],
                'data': tx_data['data'],
                'value': tx_data['value']
            })
            
            tx_data['gas'] = gas_estimate['gas']
            
            # Sign transaction with oracle account
            signed_txn = self.sign_transaction(tx_data)
            
            # Relay transaction
            tx_hash = self.relay_transaction(signed_txn)
            
            logging.info(f"Graduation completed by oracle - Pool: {token_address}, TX: {tx_hash}")
            return tx_hash
            
        except Exception as e:
            logging.error(f"Failed to complete graduation for {token_address}: {str(e)}")
            raise
    
    def _get_token_created_signature(self) -> str:
        """
        Get TokenCreated event signature hash for log filtering.
        
        Event: TokenCreated(address,address,address,string,string,uint256,bool,uint256)
        Hash: 0x5b03baff921747c518abf8237d62983e3d41970c86b6f35fbd3c1f70c016b5ec
        """
        return '0x5b03baff921747c518abf8237d62983e3d41970c86b6f35fbd3c1f70c016b5ec'
    
    def _get_vesting_deployed_signature(self) -> str:
        """
        Get VestingDeployed event signature hash for log filtering.
        
        Event: VestingDeployed(address,address,uint8,address,uint8,address,uint8)
        Hash: 0x8c43b4ef9935131ccd06baec8deb63e48eae5f310986bb054bcd6c4fd4d1d78c
        """
        return '0x8c43b4ef9935131ccd06baec8deb63e48eae5f310986bb054bcd6c4fd4d1d78c'
    
    def extract_token_address_from_receipt(self, tx_hash: str, expected_creator: str = None) -> str:
        """
        Extract deployed token contract address from transaction receipt.
        
        SECURITY:
        - Verifies transaction was sent to TokenFactory
        - Verifies TokenCreated event was emitted by TokenFactory
        - Optionally verifies creator in event matches expected creator
        
        Args:
            tx_hash: Transaction hash of token deployment
            expected_creator: Optional - verify event creator matches this address
            
        Returns:
            Token contract address (checksummed)
            
        Raises:
            ValueError: If verification fails or TokenCreated event not found
        """
        try:
            # Get transaction and receipt
            tx = self.w3.eth.get_transaction(tx_hash)
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            
            if not receipt or not receipt.get('logs'):
                raise ValueError('No logs found in transaction receipt')
            
            # SECURITY: Verify transaction was sent to TokenFactory
            if tx['to'].lower() != self.token_factory_address.lower():
                raise ValueError(f'Transaction not sent to TokenFactory. Expected {self.token_factory_address}, got {tx["to"]}')
            
            event_signature = self._get_token_created_signature().lower()
            
            logging.debug(f"Searching for TokenCreated event in {len(receipt['logs'])} logs. Expected signature: {event_signature}")
            
            # Find TokenCreated event in logs
            for i, log in enumerate(receipt['logs']):
                if log.get('topics') and len(log['topics']) > 0:
                    # Check event signature (topics can be HexBytes or str)
                    topic0_raw = log['topics'][0]
                    topic0 = topic0_raw.hex() if hasattr(topic0_raw, 'hex') else str(topic0_raw)
                    # Normalize: ensure 0x prefix and lowercase
                    topic0_normalized = topic0.lower().strip()
                    if not topic0_normalized.startswith('0x'):
                        topic0_normalized = '0x' + topic0_normalized
                    
                    logging.debug(f"Log {i}: address={log['address']}, topic0={topic0_normalized}")
                    
                    if topic0_normalized == event_signature:
                        logging.debug(f"Found matching TokenCreated event at log index {i}")
                        
                        # SECURITY: Verify log was emitted by TokenFactory
                        if log['address'].lower() != self.token_factory_address.lower():
                            raise ValueError(f'TokenCreated event not from TokenFactory. Expected {self.token_factory_address}, got {log["address"]}')
                        
                        # Verify we have required topics
                        if len(log['topics']) < 4:
                            raise ValueError('TokenCreated event missing required indexed parameters')
                        
                        # Extract tokenAddress from topics[1] (can be HexBytes or str)
                        topic1_raw = log['topics'][1]
                        topic1 = topic1_raw.hex() if hasattr(topic1_raw, 'hex') else str(topic1_raw)
                        token_address = '0x' + topic1[-40:]
                        
                        # SECURITY: Verify creator if provided
                        if expected_creator:
                            topic3_raw = log['topics'][3]
                            topic3 = topic3_raw.hex() if hasattr(topic3_raw, 'hex') else str(topic3_raw)
                            event_creator = '0x' + topic3[-40:]
                            if event_creator.lower() != expected_creator.lower():
                                raise ValueError(f'Event creator {event_creator} does not match expected creator {expected_creator}')
                        
                        # Validate and checksum token address
                        if not Web3.is_address(token_address):
                            raise ValueError(f'Invalid token address format: {token_address}')
                        
                        logging.info(f"Successfully extracted token address: {token_address} from tx {tx_hash}")
                        return Web3.to_checksum_address(token_address)
            
            raise ValueError('TokenCreated event not found in transaction receipt')
            
        except Exception as e:
            logging.error(f"Failed to extract token address from receipt {tx_hash}: {str(e)}")
            raise
    
    def extract_vesting_addresses_from_receipt(self, tx_hash: str) -> dict:
        """
        Extract vesting contract addresses from VestingDeployed event in transaction receipt.
        
        Returns dict with vesting addresses (None if allocation is 0):
        {
            'airdrop_vesting_address': '0x...' or None,
            'marketing_vesting_address': '0x...' or None,
            'team_vesting_address': '0x...' or None
        }
        
        Args:
            tx_hash: Transaction hash of token deployment
            
        Returns:
            dict: Vesting addresses (None for each if allocation is 0)
            
        Raises:
            ValueError: If VestingDeployed event parsing fails
        """
        try:
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            
            if not receipt or not receipt.get('logs'):
                logging.debug(f"No logs found in receipt {tx_hash} - likely BASIC token (no vesting)")
                return {
                    'airdrop_vesting_address': None,
                    'marketing_vesting_address': None,
                    'team_vesting_address': None
                }
            
            event_signature = self._get_vesting_deployed_signature().lower()
            
            logging.debug(f"Searching for VestingDeployed event in {len(receipt['logs'])} logs")
            
            for i, log in enumerate(receipt['logs']):
                if log.get('topics') and len(log['topics']) > 0:
                    topic0_raw = log['topics'][0]
                    topic0 = topic0_raw.hex() if hasattr(topic0_raw, 'hex') else str(topic0_raw)
                    topic0_normalized = topic0.lower().strip()
                    if not topic0_normalized.startswith('0x'):
                        topic0_normalized = '0x' + topic0_normalized
                    
                    if topic0_normalized == event_signature:
                        logging.debug(f"Found VestingDeployed event at log index {i}")
                        
                        if log['address'].lower() != self.token_factory_address.lower():
                            raise ValueError(f'VestingDeployed event not from TokenFactory')
                        
                        data_raw = log.get('data', '0x')
                        data_hex = data_raw.hex() if hasattr(data_raw, 'hex') else str(data_raw)
                        if not data_hex.startswith('0x'):
                            data_hex = '0x' + data_hex
                        
                        data_bytes = bytes.fromhex(data_hex[2:])
                        
                        airdrop_vesting_bytes = data_bytes[0:32]
                        airdrop_allocation = int.from_bytes(data_bytes[32:64], 'big')
                        marketing_vesting_bytes = data_bytes[64:96]
                        marketing_allocation = int.from_bytes(data_bytes[96:128], 'big')
                        team_vesting_bytes = data_bytes[128:160]
                        team_allocation = int.from_bytes(data_bytes[160:192], 'big')
                        
                        airdrop_vesting_address = '0x' + airdrop_vesting_bytes[-20:].hex()
                        marketing_vesting_address = '0x' + marketing_vesting_bytes[-20:].hex()
                        team_vesting_address = '0x' + team_vesting_bytes[-20:].hex()
                        
                        zero_address = '0x0000000000000000000000000000000000000000'
                        
                        result = {
                            'airdrop_vesting_address': Web3.to_checksum_address(airdrop_vesting_address) if airdrop_allocation > 0 and airdrop_vesting_address.lower() != zero_address else None,
                            'marketing_vesting_address': Web3.to_checksum_address(marketing_vesting_address) if marketing_allocation > 0 and marketing_vesting_address.lower() != zero_address else None,
                            'team_vesting_address': Web3.to_checksum_address(team_vesting_address) if team_allocation > 0 and team_vesting_address.lower() != zero_address else None
                        }
                        
                        logging.info(f"Extracted vesting addresses from tx {tx_hash}: airdrop={result['airdrop_vesting_address']}, marketing={result['marketing_vesting_address']}, team={result['team_vesting_address']}")
                        return result
            
            logging.debug(f"VestingDeployed event not found - likely BASIC token (no vesting)")
            return {
                'airdrop_vesting_address': None,
                'marketing_vesting_address': None,
                'team_vesting_address': None
            }
            
        except Exception as e:
            logging.error(f"Failed to extract vesting addresses from receipt {tx_hash}: {str(e)}")
            return {
                'airdrop_vesting_address': None,
                'marketing_vesting_address': None,
                'team_vesting_address': None
            }
    
    # =========================
    # Airdrop Batch Transfer Methods
    # =========================
    
    def build_vesting_withdrawal_tx(self, user_address, vesting_contract_address, vesting_type='airdrop'):
        """
        Build transaction for withdrawing unlocked tokens from vesting contract
        
        Args:
            user_address (str): Creator's wallet address (vesting beneficiary)
            vesting_contract_address (str): Address of vesting contract
            vesting_type (str): 'airdrop', 'marketing', or 'team'
        
        Returns:
            dict: Transaction data for release() call
        """
        try:
            logging.info(f"Building vesting withdrawal TX for {user_address} from {vesting_contract_address}")
            
            # Get appropriate vesting contract
            if vesting_type == 'airdrop':
                vesting_contract = self.get_airdrop_vesting_contract(vesting_contract_address)
            elif vesting_type == 'marketing':
                vesting_contract = self.get_linear_vesting_contract(vesting_contract_address)
            elif vesting_type == 'team':
                vesting_contract = self.get_cliff_vesting_contract(vesting_contract_address)
            else:
                raise ValueError(f"Invalid vesting type: {vesting_type}")
            
            # Build release() call
            tx_data = vesting_contract.functions.release().build_transaction({
                'from': Web3.to_checksum_address(user_address),
                'nonce': self.w3.eth.get_transaction_count(Web3.to_checksum_address(user_address)),
                'gas': 100000,  # Estimate for release()
                'gasPrice': self.w3.eth.gas_price
            })
            
            return {
                'to': vesting_contract_address,
                'value': hex(0),
                'data': tx_data['data'],
                'gas': hex(tx_data['gas'])
            }
            
        except Exception as e:
            logging.error(f"Failed to build vesting withdrawal TX: {str(e)}")
            raise
    
    def build_token_approval_tx(self, user_address, token_address, spender_address, amount):
        """
        Build transaction for ERC20 approve()
        
        Args:
            user_address (str): User's wallet address
            token_address (str): ERC20 token contract address
            spender_address (str): Address to approve (AirdropDistributor)
            amount (int): Amount to approve (in wei/base units)
        
        Returns:
            dict: Transaction data for approve() call
        """
        try:
            logging.info(f"Building approval TX: {amount} tokens from {token_address} to {spender_address}")
            
            # Get token contract (use BondingCurvePool ABI since it's also the token)
            token_contract = self.get_bonding_pool_contract(token_address)
            
            # Build approve() call
            tx_data = token_contract.functions.approve(
                Web3.to_checksum_address(spender_address),
                amount
            ).build_transaction({
                'from': Web3.to_checksum_address(user_address),
                'nonce': self.w3.eth.get_transaction_count(Web3.to_checksum_address(user_address)),
                'gas': 60000,  # Standard ERC20 approve gas
                'gasPrice': self.w3.eth.gas_price
            })
            
            return {
                'to': token_address,
                'value': hex(0),
                'data': tx_data['data'],
                'gas': hex(tx_data['gas'])
            }
            
        except Exception as e:
            logging.error(f"Failed to build approval TX: {str(e)}")
            raise
    
    def build_batch_transfer_tx(self, user_address, token_address, recipients, amounts):
        """
        Build transaction for AirdropDistributor.batchTransfer()
        
        Args:
            user_address (str): Creator's wallet address (msg.sender)
            token_address (str): ERC20 token contract address
            recipients (list): List of recipient addresses
            amounts (list): List of amounts (in wei/base units)
        
        Returns:
            dict: Transaction data for batchTransfer() call
        """
        try:
            logging.info(f"Building batch transfer TX: {len(recipients)} recipients, total {sum(amounts)} tokens")
            
            # Validate inputs
            if len(recipients) != len(amounts):
                raise ValueError("Recipients and amounts arrays must have same length")
            
            if len(recipients) == 0:
                raise ValueError("Cannot batch transfer to 0 recipients")
            
            # Get AirdropDistributor contract
            distributor = self.contracts['AirdropDistributor']
            
            # Convert addresses to checksum format
            recipients_checksum = [Web3.to_checksum_address(addr) for addr in recipients]
            token_checksum = Web3.to_checksum_address(token_address)
            
            # Build batchTransfer() call
            tx_data = distributor.functions.batchTransfer(
                token_checksum,
                recipients_checksum,
                amounts
            ).build_transaction({
                'from': Web3.to_checksum_address(user_address),
                'nonce': self.w3.eth.get_transaction_count(Web3.to_checksum_address(user_address)),
                'gas': 100000 + (len(recipients) * 60000),  # Base + per-recipient gas estimate
                'gasPrice': self.w3.eth.gas_price
            })
            
            return {
                'to': AIRDROP_DISTRIBUTOR_ADDRESS,
                'value': hex(0),
                'data': tx_data['data'],
                'gas': hex(tx_data['gas'])
            }
            
        except Exception as e:
            logging.error(f"Failed to build batch transfer TX: {str(e)}")
            raise
    
    def check_vesting_unlocked_balance(self, vesting_contract_address, vesting_type='airdrop'):
        """
        Check how many tokens are unlocked and ready to withdraw from vesting
        
        Args:
            vesting_contract_address (str): Address of vesting contract
            vesting_type (str): 'airdrop', 'marketing', or 'team'
        
        Returns:
            int: Unlocked token amount (in wei/base units)
        """
        try:
            # Get appropriate vesting contract
            if vesting_type == 'airdrop':
                vesting_contract = self.get_airdrop_vesting_contract(vesting_contract_address)
            elif vesting_type == 'marketing':
                vesting_contract = self.get_linear_vesting_contract(vesting_contract_address)
            elif vesting_type == 'team':
                vesting_contract = self.get_cliff_vesting_contract(vesting_contract_address)
            else:
                raise ValueError(f"Invalid vesting type: {vesting_type}")
            
            # Call getWithdrawableAmount() to get unlocked amount available for withdrawal
            unlocked_amount = vesting_contract.functions.getWithdrawableAmount().call()
            
            logging.info(f"Vesting contract {vesting_contract_address} has {unlocked_amount} tokens unlocked")
            return unlocked_amount
            
        except Exception as e:
            logging.error(f"Failed to check vesting unlocked balance: {str(e)}")
            raise


def get_web3_with_fallback():
    """Try RPC endpoints in order until one works"""
    for rpc_url in RPC_ENDPOINTS:
        try:
            w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 5}))
            
            # Add POA middleware immediately after connection
            w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            
            # Test connection
            if w3.is_connected():
                chain_id = w3.eth.chain_id
                logging.info(f"Connected to RPC: {rpc_url} - Chain ID: {chain_id}")
                return w3
        except Exception as e:
            logging.warning(f"RPC {rpc_url} failed: {str(e)}")
            continue
    
    # Return disconnected Web3 instance instead of crashing
    logging.error("⚠️ All RPC endpoints failed - App running in offline mode")
    w3 = Web3(Web3.HTTPProvider(RPC_ENDPOINTS[0], request_kwargs={'timeout': 5}))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3

# Global Web3 service instance
web3_service = None

def get_web3_service():
    """Get or create the global Web3 service instance"""
    global web3_service
    if web3_service is None:
        web3_service = Web3Service()
    return web3_service
