"""
Web3 Service for Blockchain Integration
Handles RPC connections, contract interactions, and transaction relay
"""

import os
import json
import logging
from pathlib import Path
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account
from eth_account.messages import encode_defunct

# Kasplex Testnet Configuration
KASPLEX_TESTNET_RPC = "https://rpc.kasplextest.xyz"
KASPLEX_TESTNET_CHAIN_ID = 167012

# Deployed Contract Addresses (from Phase 1)
TOKEN_FACTORY_ADDRESS = "0x348640F6e87a0226e8E4CdB5e068282B5D0b2F60"
GRADUATION_CONTROLLER_ADDRESS = "0x9416D5a5D61ec70C18D1FE1039f8026E29b4820e"

# Contract ABI paths
ARTIFACTS_DIR = Path("artifacts/contracts")

class Web3Service:
    """Main service for Web3 blockchain interactions"""
    
    def __init__(self):
        """Initialize Web3 connection and load contracts"""
        self.w3 = self._init_web3()
        self.oracle_account = self._init_oracle_account()
        self.contracts = self._load_contracts()
        logging.info(f"Web3Service initialized - Chain ID: {self.w3.eth.chain_id}")
        
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
            
            # Check balance
            balance = self.w3.eth.get_balance(oracle_account.address)
            balance_kas = self.w3.from_wei(balance, 'ether')
            logging.info(f"Oracle wallet {oracle_account.address} - Balance: {balance_kas} KAS")
            
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
            
            # Load GraduationController
            graduation_abi = self._load_contract_abi('GraduationController')
            contracts['GraduationController'] = self.w3.eth.contract(
                address=Web3.to_checksum_address(GRADUATION_CONTROLLER_ADDRESS),
                abi=graduation_abi
            )
            logging.info(f"Loaded GraduationController at {GRADUATION_CONTROLLER_ADDRESS}")
            
            # Load BondingCurvePool ABI (for pool interactions later)
            contracts['BondingCurvePoolABI'] = self._load_contract_abi('BondingCurvePool')
            logging.info("Loaded BondingCurvePool ABI")
            
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
    
    def estimate_gas(self, transaction):
        """
        Estimate gas for a transaction with 20% buffer
        
        Args:
            transaction: Transaction dict with 'from', 'to', 'data', etc.
        
        Returns:
            int: Estimated gas with 20% buffer
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
            logging.error(f"Gas estimation failed: {str(e)}")
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
    
    # =========================
    # Task 2.2.1 - TokenFactory Interactions
    # =========================
    
    def create_token_tx_data(self, user_address, name, symbol, total_supply, description, 
                             image_url, twitter_url, telegram_url, website_url, anti_bot_enabled):
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
        
        Returns:
            dict: Unsigned transaction dict {from, to, data, value, gas}
        """
        try:
            logging.info(f"Building createToken tx for user {user_address} - Token: {name} ({symbol})")
            
            # Build contract call
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
                anti_bot_enabled
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
        Get buy quote from bonding curve pool
        
        Args:
            pool_address (str): Pool contract address
            kas_amount (int): KAS amount in wei
        
        Returns:
            int: Tokens out (in wei)
        """
        try:
            logging.debug(f"Getting buy quote for pool {pool_address} - KAS: {kas_amount}")
            
            pool = self.get_bonding_pool_contract(pool_address)
            tokens_out = pool.functions.quoteBuy(kas_amount).call()
            
            logging.debug(f"Buy quote: {kas_amount} wei KAS → {tokens_out} wei tokens")
            return tokens_out
            
        except Exception as e:
            logging.error(f"Failed to get buy quote for pool {pool_address}: {str(e)}")
            raise
    
    def get_sell_quote(self, pool_address, token_amount):
        """
        Get sell quote from bonding curve pool
        
        Args:
            pool_address (str): Pool contract address
            token_amount (int): Token amount in wei
        
        Returns:
            int: KAS out (in wei)
        """
        try:
            logging.debug(f"Getting sell quote for pool {pool_address} - Tokens: {token_amount}")
            
            pool = self.get_bonding_pool_contract(pool_address)
            kas_out = pool.functions.quoteSell(token_amount).call()
            
            logging.debug(f"Sell quote: {token_amount} wei tokens → {kas_out} wei KAS")
            return kas_out
            
        except Exception as e:
            logging.error(f"Failed to get sell quote for pool {pool_address}: {str(e)}")
            raise
    
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
    # Task 2.2.3 - GraduationController Interactions (Oracle Only)
    # =========================
    
    def initiate_graduation_oracle(self, token_address):
        """
        Oracle signs and relays GraduationController.initiateGraduation() - ORACLE TRANSACTION
        
        Args:
            token_address (str): Token/pool address to graduate
        
        Returns:
            str: Transaction hash
        """
        try:
            logging.info(f"Oracle initiating graduation for token {token_address}")
            
            # Build contract call
            contract = self.contracts['GraduationController']
            tx_data = contract.functions.initiateGraduation(
                Web3.to_checksum_address(token_address)
            ).build_transaction({
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
            
            logging.info(f"Graduation initiated by oracle - Token: {token_address}, TX: {tx_hash}")
            return tx_hash
            
        except Exception as e:
            logging.error(f"Failed to initiate graduation for {token_address}: {str(e)}")
            raise
    
    def complete_graduation_oracle(self, token_address):
        """
        Oracle signs and relays GraduationController.completeGraduation() - ORACLE TRANSACTION
        
        Args:
            token_address (str): Token/pool address to complete graduation
        
        Returns:
            str: Transaction hash
        """
        try:
            logging.info(f"Oracle completing graduation for token {token_address}")
            
            # Build contract call
            contract = self.contracts['GraduationController']
            tx_data = contract.functions.completeGraduation(
                Web3.to_checksum_address(token_address)
            ).build_transaction({
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
            
            logging.info(f"Graduation completed by oracle - Token: {token_address}, TX: {tx_hash}")
            return tx_hash
            
        except Exception as e:
            logging.error(f"Failed to complete graduation for {token_address}: {str(e)}")
            raise


# Global Web3 service instance
web3_service = None

def get_web3_service():
    """Get or create the global Web3 service instance"""
    global web3_service
    if web3_service is None:
        web3_service = Web3Service()
    return web3_service
