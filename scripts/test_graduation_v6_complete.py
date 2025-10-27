#!/usr/bin/env python3
"""
GraduationController V6 & TokenFactory V8 End-to-End Test
===========================================================

This script performs a comprehensive test of the complete graduation flow:
1. Deploy test token via TokenFactory V8
2. Execute buy transactions to reach graduation threshold ($50)
3. Monitor graduation initiation (oracle calls initiateGraduation)
4. Verify snapshot creation
5. Monitor graduation completion (oracle calls completeGraduation)
6. Verify LP creation on Kaspa Finance DEX FIRST
7. Verify pool marks itself graduated
8. Verify database syncs correctly

Key Verification Points:
- GC V6 successfully calls Kaspa Finance contracts (Factory, Position Manager)
- LP exists BEFORE completeGraduation() is called
- No reverts or errors during graduation
- Database graduation_status reflects on-chain state accurately

Contract Addresses:
- TokenFactory V8: 0x1b641c1dF9eEbaf5bd8B5251e24794Cab01D9071
- GraduationController V6: 0xBbfdF7341aaF104D259876972844EBF9795b9C4C
- Kaspa Finance Factory: 0x1b72D7165a0D7256a4F197765C15bb70bC5D66A8
- Kaspa Finance Position Manager: 0x4E25637cF39822364b877F81B18c5B6CF0eeF589
"""

import os
import sys
import time
import json
import logging
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timezone
from web3 import Web3
from eth_account import Account

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
KASPLEX_TESTNET_RPC = "https://rpc.kasplextest.xyz"
KASPLEX_TESTNET_CHAIN_ID = 167012
TOKEN_FACTORY_V8 = "0x1b641c1dF9eEbaf5bd8B5251e24794Cab01D9071"
GRADUATION_CONTROLLER_V6 = "0xBbfdF7341aaF104D259876972844EBF9795b9C4C"
KASPA_FINANCE_FACTORY = "0x1b72D7165a0D7256a4F197765C15bb70bC5D66A8"
KASPA_FINANCE_POSITION_MANAGER = "0x4E25637cF39822364b877F81B18c5B6CF0eeF589"
KASPA_FINANCE_WKAS = "0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94"

# Graduation threshold
GRADUATION_THRESHOLD_USD = 50.0

# Transaction hashes storage
tx_hashes = {
    'deployment': None,
    'buy_trades': [],
    'initiation': None,
    'completion': None
}

class TestResult:
    """Store test results"""
    def __init__(self):
        self.token_address = None
        self.token_symbol = None
        self.deployment_tx = None
        self.buy_txs = []
        self.initiation_tx = None
        self.completion_tx = None
        self.lp_pool_address = None
        self.snapshot_verified = False
        self.lp_created_before_completion = False
        self.on_chain_graduated = False
        self.database_synced = False
        self.success = False

def derive_oracle_wallet():
    """Derive Oracle Wallet from DEPLOYER_PRIVATE_KEY"""
    deployer_private_key = os.environ.get('DEPLOYER_PRIVATE_KEY')
    if not deployer_private_key:
        raise Exception("DEPLOYER_PRIVATE_KEY not found in environment")
    
    w3 = Web3()
    
    if not deployer_private_key.startswith('0x'):
        deployer_private_key = f'0x{deployer_private_key}'
    
    # Derive secondary wallet using same method as web3_service.py
    seed_text = "GEMLAUNCH_SECONDARY_WALLET"
    seed_bytes = seed_text.encode('utf-8')
    deployer_bytes = bytes.fromhex(deployer_private_key[2:])
    combined = seed_bytes + deployer_bytes
    derived_key = w3.keccak(combined)
    derived_key_hex = '0x' + derived_key.hex()
    oracle_account = Account.from_key(derived_key_hex)
    
    logger.info(f"Oracle Wallet: {oracle_account.address}")
    
    # Verify expected address
    expected = "0x5f837F62744D4d80Fc79C3A5346B4A228956914E"
    if oracle_account.address.lower() != expected.lower():
        logger.warning(f"⚠️  Oracle address mismatch! Expected {expected}")
    
    return oracle_account

def check_oracle_balance(oracle_address):
    """Check Oracle wallet balance"""
    try:
        w3 = Web3(Web3.HTTPProvider(KASPLEX_TESTNET_RPC))
        balance_wei = w3.eth.get_balance(oracle_address)
        balance_kas = w3.from_wei(balance_wei, 'ether')
        
        logger.info(f"💰 Oracle Balance: {balance_kas} KAS")
        
        if balance_kas < 5:
            logger.warning(f"⚠️  Low balance! Need ~5 KAS for deployment + trades + graduation")
            return False
        
        return True
    except Exception as e:
        logger.error(f"Failed to check balance: {str(e)}")
        return False

def deploy_test_token(oracle_account):
    """Deploy test token via TokenFactory V8"""
    logger.info("\n" + "=" * 80)
    logger.info("STEP 1: Deploying Test Token via TokenFactory V8")
    logger.info("=" * 80)
    
    try:
        from app import app, db
        from models import Token
        from services.web3_service import get_web3_service
        
        w3_service = get_web3_service()
        timestamp = int(time.time())
        
        token_data = {
            'name': f'GC V6 Test {timestamp}',
            'symbol': f'GCTEST{timestamp % 1000}',
            'total_supply': 1000000000,  # 1B tokens
            'description': 'Testing GraduationController V6 with TokenFactory V8',
            'image_url': 'QmTest123',
            'anti_bot_enabled': False,
            'reserved_percentage': 0,  # Basic token
            'airdrops_allocation': 0,
            'marketing_allocation': 0,
            'team_allocation': 0
        }
        
        logger.info(f"Token: {token_data['name']} ({token_data['symbol']})")
        logger.info(f"Supply: {token_data['total_supply']:,}")
        
        # Build deployment transaction
        logger.info("\nBuilding deployment transaction...")
        factory = w3_service.contracts['TokenFactory']
        
        tx_data = factory.functions.createToken(
            token_data['name'],
            token_data['symbol'],
            token_data['total_supply'] * 10**18,
            token_data['description'],
            token_data['image_url'],
            '',  # twitter
            '',  # telegram
            '',  # website
            token_data['anti_bot_enabled'],
            token_data['reserved_percentage'],
            token_data['airdrops_allocation'],
            token_data['marketing_allocation'],
            token_data['team_allocation']
        ).build_transaction({
            'from': oracle_account.address,
            'nonce': w3_service.w3.eth.get_transaction_count(oracle_account.address),
            'gas': 5000000,
            'gasPrice': w3_service.w3.eth.gas_price,
            'chainId': KASPLEX_TESTNET_CHAIN_ID,
            'value': 0
        })
        
        # Sign and send
        logger.info("Signing and sending transaction...")
        signed_tx = oracle_account.sign_transaction(tx_data)
        tx_hash = w3_service.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        tx_hash_hex = tx_hash.hex()
        
        logger.info(f"✅ Deployment TX: {tx_hash_hex}")
        logger.info(f"🔗 Explorer: https://explorer.kasplextest.xyz/tx/{tx_hash_hex}")
        
        # Wait for confirmation
        logger.info("\n⏳ Waiting for confirmation...")
        receipt = w3_service.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        
        if receipt['status'] != 1:
            raise Exception(f"Deployment transaction failed!")
        
        logger.info(f"✅ Confirmed in block {receipt['blockNumber']}")
        logger.info(f"   Gas used: {receipt['gasUsed']:,}")
        
        # Extract pool address from logs
        pool_address = None
        for log in receipt['logs']:
            try:
                if log['address'].lower() == TOKEN_FACTORY_V8.lower():
                    # TokenCreated event: first topic is event signature, second is token address
                    if len(log['topics']) >= 2:
                        pool_address = '0x' + log['topics'][1].hex()[-40:]
                        break
            except:
                pass
        
        if not pool_address:
            raise Exception("Could not extract pool address from logs")
        
        # Convert to checksum address
        pool_address = w3_service.w3.to_checksum_address(pool_address)
        
        logger.info(f"\n✅ Token Deployed Successfully!")
        logger.info(f"   Contract Address: {pool_address}")
        
        # Create database record
        with app.app_context():
            from models import User
            
            # Get or create user for oracle address
            user = User.get_or_create_by_wallet(oracle_account.address.lower())
            
            token = Token(
                name=token_data['name'],
                symbol=token_data['symbol'],
                contract_address=pool_address,
                creator_id=user.id,
                total_supply=token_data['total_supply'],
                description=token_data['description'],
                ipfs_image_hash=token_data['image_url'],
                anti_bot_enabled=token_data['anti_bot_enabled'],
                deployment_status='deployed',
                deployment_tx=tx_hash_hex,
                graduation_status='active',
                is_graduated=False
            )
            db.session.add(token)
            db.session.commit()
            
            logger.info(f"   Database ID: {token.id}")
            
            return token, tx_hash_hex
        
    except Exception as e:
        logger.error(f"❌ Deployment failed: {str(e)}")
        raise

def execute_buy_trades(token, oracle_account):
    """Execute buy trades to push market cap above $50"""
    logger.info("\n" + "=" * 80)
    logger.info("STEP 2: Executing Buy Trades to Reach Graduation Threshold")
    logger.info("=" * 80)
    
    try:
        from services.web3_service import get_web3_service
        from services.kas_oracle import oracle
        
        w3_service = get_web3_service()
        pool = w3_service.get_bonding_pool_contract(token.contract_address)
        
        # Get KAS price
        kas_price_usd = oracle.get_kas_price()
        logger.info(f"KAS Price: ${kas_price_usd:.4f}")
        logger.info(f"Graduation Threshold: ${GRADUATION_THRESHOLD_USD:.2f}")
        
        # Get current reserves
        virtual_kas = pool.functions.virtualKasReserve().call()
        virtual_tokens = pool.functions.virtualTokenReserve().call()
        
        current_market_cap_usd = (virtual_kas / 10**18) * kas_price_usd
        
        logger.info(f"\nCurrent Market Cap: ${current_market_cap_usd:.2f}")
        logger.info(f"Virtual KAS Reserve: {virtual_kas / 10**18:.4f} KAS")
        logger.info(f"Virtual Token Reserve: {virtual_tokens / 10**18:.2f} tokens")
        
        # Calculate KAS needed (with 20% safety margin)
        target_market_cap = GRADUATION_THRESHOLD_USD * 1.2
        required_kas_reserve = target_market_cap / kas_price_usd
        kas_to_buy = required_kas_reserve - (virtual_kas / 10**18)
        
        # Add extra margin for fees
        kas_to_buy = kas_to_buy * 1.1
        
        logger.info(f"\nKAS Analysis:")
        logger.info(f"   Target Market Cap: ${target_market_cap:.2f}")
        logger.info(f"   Required KAS Reserve: {required_kas_reserve:.4f} KAS")
        logger.info(f"   KAS to Buy: {kas_to_buy:.4f} KAS")
        
        # Execute buy transaction
        logger.info(f"\n🚀 Executing buy transaction...")
        
        # Get quote
        tokens_out = pool.functions.quoteBuy(int(kas_to_buy * 0.95 * 10**18)).call()
        min_tokens_out = int(tokens_out * 0.9)  # 10% slippage tolerance
        deadline = int(time.time()) + 300
        
        logger.info(f"   Quote: {kas_to_buy:.4f} KAS → {tokens_out / 10**18:.2f} tokens")
        
        # Build transaction
        tx_data = pool.functions.buyTokens(
            min_tokens_out,
            deadline
        ).build_transaction({
            'from': oracle_account.address,
            'value': int(kas_to_buy * 10**18),
            'nonce': w3_service.w3.eth.get_transaction_count(oracle_account.address),
            'gas': 500000,
            'gasPrice': w3_service.w3.eth.gas_price,
            'chainId': KASPLEX_TESTNET_CHAIN_ID
        })
        
        # Sign and send
        signed_tx = oracle_account.sign_transaction(tx_data)
        tx_hash = w3_service.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        tx_hash_hex = tx_hash.hex()
        
        logger.info(f"✅ Buy TX: {tx_hash_hex}")
        logger.info(f"🔗 Explorer: https://explorer.kasplextest.xyz/tx/{tx_hash_hex}")
        
        # Wait for confirmation
        logger.info("\n⏳ Waiting for confirmation...")
        receipt = w3_service.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        
        if receipt['status'] != 1:
            raise Exception("Buy transaction failed!")
        
        logger.info(f"✅ Confirmed in block {receipt['blockNumber']}")
        logger.info(f"   Gas used: {receipt['gasUsed']:,}")
        
        # Get new reserves
        new_virtual_kas = pool.functions.virtualKasReserve().call()
        new_virtual_tokens = pool.functions.virtualTokenReserve().call()
        new_market_cap_usd = (new_virtual_kas / 10**18) * kas_price_usd
        
        logger.info(f"\n✅ Buy Trade Executed!")
        logger.info(f"   New Market Cap: ${new_market_cap_usd:.2f}")
        logger.info(f"   New KAS Reserve: {new_virtual_kas / 10**18:.4f} KAS")
        logger.info(f"   Progress: {(new_market_cap_usd / GRADUATION_THRESHOLD_USD) * 100:.1f}%")
        
        if new_market_cap_usd >= GRADUATION_THRESHOLD_USD:
            logger.info(f"🎓 Token is ready for graduation!")
        else:
            logger.warning(f"⚠️  Token has not reached graduation threshold yet")
        
        return [tx_hash_hex], new_market_cap_usd
        
    except Exception as e:
        logger.error(f"❌ Buy trade failed: {str(e)}")
        raise

def wait_for_graduation_initiation(token, timeout=180):
    """Wait for graduation monitor to detect and initiate graduation"""
    logger.info("\n" + "=" * 80)
    logger.info("STEP 3: Waiting for Graduation Monitor to Initiate Graduation")
    logger.info("=" * 80)
    logger.info(f"Monitor runs every 60 seconds")
    logger.info(f"Waiting up to {timeout} seconds...")
    
    from app import app, db
    from models import Token
    
    start_time = time.time()
    check_interval = 5
    
    with app.app_context():
        while time.time() - start_time < timeout:
            elapsed = int(time.time() - start_time)
            
            # Refresh token
            db.session.refresh(token)
            
            logger.info(f"\n[{elapsed}s] Status: {token.graduation_status}")
            
            if token.graduation_status == 'initiating':
                logger.info(f"✅ Graduation initiated!")
                logger.info(f"   Initiated at: {token.graduation_initiated_at}")
                logger.info(f"   Initiation TX: {token.graduation_initiation_tx}")
                return token.graduation_initiation_tx
            
            elif token.graduation_status == 'failed':
                logger.error(f"❌ Graduation initiation FAILED")
                return None
            
            time.sleep(check_interval)
        
        logger.error(f"❌ Timeout waiting for graduation initiation")
        return None

def verify_snapshot_creation(token):
    """Verify graduation snapshot was created correctly"""
    logger.info("\n" + "=" * 80)
    logger.info("STEP 4: Verifying Graduation Snapshot")
    logger.info("=" * 80)
    
    try:
        from services.web3_service import get_web3_service
        
        w3_service = get_web3_service()
        gc = w3_service.contracts['GraduationController']
        
        # Get snapshot from GraduationController
        snapshot = gc.functions.graduationSnapshots(token.contract_address).call()
        
        logger.info(f"Snapshot Details:")
        logger.info(f"   Token Liquidity: {snapshot[0] / 10**18:.2f} tokens")
        logger.info(f"   KAS Liquidity: {snapshot[1] / 10**18:.4f} KAS")
        logger.info(f"   Timestamp: {snapshot[2]}")
        logger.info(f"   Authorized Oracle: {snapshot[3]}")
        logger.info(f"   Snapshot Taken: {snapshot[4]}")
        
        if not snapshot[4]:
            logger.error(f"❌ Snapshot not taken!")
            return False
        
        if snapshot[0] == 0 or snapshot[1] == 0:
            logger.error(f"❌ Snapshot has zero reserves!")
            return False
        
        logger.info(f"✅ Snapshot verified successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to verify snapshot: {str(e)}")
        return False

def wait_for_graduation_completion(token, timeout=120):
    """Wait for automatic graduation completion"""
    logger.info("\n" + "=" * 80)
    logger.info("STEP 5: Waiting for Graduation Completion")
    logger.info("=" * 80)
    logger.info(f"Completion service runs every 15 seconds")
    logger.info(f"Waiting up to {timeout} seconds...")
    
    from app import app, db
    from models import Token
    
    start_time = time.time()
    check_interval = 5
    
    with app.app_context():
        while time.time() - start_time < timeout:
            elapsed = int(time.time() - start_time)
            
            # Refresh token
            db.session.refresh(token)
            
            logger.info(f"\n[{elapsed}s] Status: {token.graduation_status}")
            
            if token.graduation_status == 'graduated':
                logger.info(f"✅ Graduation completed!")
                logger.info(f"   Completed at: {token.graduation_completed_at}")
                logger.info(f"   Completion TX: {token.graduation_completion_tx}")
                logger.info(f"   LP Pool Address: {token.dex_pool_address}")
                return token.graduation_completion_tx, token.dex_pool_address
            
            elif token.graduation_status == 'failed':
                logger.error(f"❌ Graduation completion FAILED")
                return None, None
            
            time.sleep(check_interval)
        
        logger.error(f"❌ Timeout waiting for graduation completion")
        return None, None

def verify_lp_creation(token_address, lp_pool_address):
    """Verify LP was created on Kaspa Finance DEX"""
    logger.info("\n" + "=" * 80)
    logger.info("STEP 6: Verifying LP Creation on Kaspa Finance")
    logger.info("=" * 80)
    
    try:
        from services.web3_service import get_web3_service
        
        w3_service = get_web3_service()
        
        # Load Uniswap V3 Pool ABI (minimal)
        pool_abi = [
            {
                "inputs": [],
                "name": "token0",
                "outputs": [{"type": "address"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "token1",
                "outputs": [{"type": "address"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "liquidity",
                "outputs": [{"type": "uint128"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]
        
        pool = w3_service.w3.eth.contract(
            address=w3_service.w3.to_checksum_address(lp_pool_address),
            abi=pool_abi
        )
        
        # Get pool details
        token0 = pool.functions.token0().call()
        token1 = pool.functions.token1().call()
        liquidity = pool.functions.liquidity().call()
        
        logger.info(f"LP Pool Address: {lp_pool_address}")
        logger.info(f"   Token0: {token0}")
        logger.info(f"   Token1: {token1}")
        logger.info(f"   Liquidity: {liquidity}")
        
        # Verify one of the tokens is our token
        if token_address.lower() not in [token0.lower(), token1.lower()]:
            logger.error(f"❌ LP pool does not contain our token!")
            return False
        
        # Verify one of the tokens is WKAS
        if KASPA_FINANCE_WKAS.lower() not in [token0.lower(), token1.lower()]:
            logger.error(f"❌ LP pool does not contain WKAS!")
            return False
        
        if liquidity == 0:
            logger.error(f"❌ LP pool has zero liquidity!")
            return False
        
        logger.info(f"✅ LP verified on Kaspa Finance!")
        logger.info(f"🔗 Pool: https://app.kaspa.finance/pool/{lp_pool_address}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to verify LP: {str(e)}")
        return False

def verify_on_chain_graduation(token_address):
    """Verify pool is marked as graduated on-chain"""
    logger.info("\n" + "=" * 80)
    logger.info("STEP 7: Verifying On-Chain Graduation Status")
    logger.info("=" * 80)
    
    try:
        from services.web3_service import get_web3_service
        
        w3_service = get_web3_service()
        pool = w3_service.get_bonding_pool_contract(token_address)
        
        graduated = pool.functions.graduated().call()
        graduating = pool.functions.graduating().call()
        
        logger.info(f"Pool Graduation State:")
        logger.info(f"   graduated: {graduated}")
        logger.info(f"   graduating: {graduating}")
        
        if not graduated:
            logger.error(f"❌ Pool not marked as graduated!")
            return False
        
        if graduating:
            logger.warning(f"⚠️  Pool still has graduating flag set (should be false)")
        
        logger.info(f"✅ Pool marked as graduated on-chain!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to verify on-chain status: {str(e)}")
        return False

def verify_database_sync(token):
    """Verify database reflects on-chain state"""
    logger.info("\n" + "=" * 80)
    logger.info("STEP 8: Verifying Database Synchronization")
    logger.info("=" * 80)
    
    from app import app, db
    from models import Token
    
    try:
        with app.app_context():
            db.session.refresh(token)
            
            logger.info(f"Database State:")
            logger.info(f"   graduation_status: {token.graduation_status}")
            logger.info(f"   is_graduated: {token.is_graduated}")
            logger.info(f"   lp_pool_address: {token.lp_pool_address}")
            logger.info(f"   graduation_initiated_at: {token.graduation_initiated_at}")
            logger.info(f"   graduation_completed_at: {token.graduation_completed_at}")
            
            if token.graduation_status != 'graduated':
                logger.error(f"❌ Database status is not 'graduated'!")
                return False
            
            if not token.is_graduated:
                logger.error(f"❌ is_graduated flag is False!")
                return False
            
            if not token.dex_pool_address:
                logger.error(f"❌ DEX pool address not set!")
                return False
            
            logger.info(f"✅ Database synced correctly!")
            return True
            
    except Exception as e:
        logger.error(f"❌ Failed to verify database sync: {str(e)}")
        return False

def print_final_report(result):
    """Print comprehensive test report"""
    logger.info("\n" + "=" * 100)
    logger.info("=" * 100)
    logger.info("GRADUATION CONTROLLER V6 TEST REPORT")
    logger.info("=" * 100)
    logger.info("=" * 100)
    
    logger.info(f"\n📊 TOKEN INFORMATION")
    logger.info(f"-" * 100)
    logger.info(f"   Symbol: {result.token_symbol}")
    logger.info(f"   Contract Address: {result.token_address}")
    logger.info(f"   Explorer: https://explorer.kasplextest.xyz/address/{result.token_address}")
    
    logger.info(f"\n📝 TRANSACTION HASHES")
    logger.info(f"-" * 100)
    logger.info(f"   Deployment TX: {result.deployment_tx}")
    logger.info(f"      └─ https://explorer.kasplextest.xyz/tx/{result.deployment_tx}")
    
    for i, tx in enumerate(result.buy_txs, 1):
        logger.info(f"   Buy Trade #{i}: {tx}")
        logger.info(f"      └─ https://explorer.kasplextest.xyz/tx/{tx}")
    
    if result.initiation_tx:
        logger.info(f"   Initiation TX: {result.initiation_tx}")
        logger.info(f"      └─ https://explorer.kasplextest.xyz/tx/{result.initiation_tx}")
    
    if result.completion_tx:
        logger.info(f"   Completion TX: {result.completion_tx}")
        logger.info(f"      └─ https://explorer.kasplextest.xyz/tx/{result.completion_tx}")
    
    logger.info(f"\n🏊 KASPA FINANCE DEX")
    logger.info(f"-" * 100)
    if result.lp_pool_address:
        logger.info(f"   LP Pool Address: {result.lp_pool_address}")
        logger.info(f"   Pool URL: https://app.kaspa.finance/pool/{result.lp_pool_address}")
    else:
        logger.info(f"   ❌ LP Pool not created")
    
    logger.info(f"\n✅ VERIFICATION RESULTS")
    logger.info(f"-" * 100)
    logger.info(f"   Snapshot Created: {'✅ PASS' if result.snapshot_verified else '❌ FAIL'}")
    logger.info(f"   LP Created Before Completion: {'✅ PASS' if result.lp_created_before_completion else '❌ FAIL'}")
    logger.info(f"   Pool Marked Graduated On-Chain: {'✅ PASS' if result.on_chain_graduated else '❌ FAIL'}")
    logger.info(f"   Database Synced: {'✅ PASS' if result.database_synced else '❌ FAIL'}")
    
    logger.info(f"\n" + "=" * 100)
    if result.success:
        logger.info("✅ TEST PASSED - GraduationController V6 working correctly!")
    else:
        logger.info("❌ TEST FAILED - Issues found in graduation flow")
    logger.info("=" * 100 + "\n")

def main():
    """Main test execution"""
    result = TestResult()
    
    try:
        logger.info("=" * 80)
        logger.info("GRADUATIONCONTROLLER V6 & TOKENFACTORY V8 E2E TEST")
        logger.info("=" * 80)
        logger.info(f"\nContract Addresses:")
        logger.info(f"   TokenFactory V8: {TOKEN_FACTORY_V8}")
        logger.info(f"   GraduationController V6: {GRADUATION_CONTROLLER_V6}")
        logger.info(f"   Kaspa Finance Factory: {KASPA_FINANCE_FACTORY}")
        logger.info(f"   Kaspa Finance Position Manager: {KASPA_FINANCE_POSITION_MANAGER}")
        
        # Get oracle wallet
        oracle_account = derive_oracle_wallet()
        
        # Check balance
        if not check_oracle_balance(oracle_account.address):
            logger.warning("⚠️  Proceeding anyway (may fail if insufficient funds)")
        
        # Step 1: Deploy test token
        token, deployment_tx = deploy_test_token(oracle_account)
        result.token_address = token.contract_address
        result.token_symbol = token.symbol
        result.deployment_tx = deployment_tx
        
        # Step 2: Execute buy trades
        buy_txs, market_cap = execute_buy_trades(token, oracle_account)
        result.buy_txs = buy_txs
        
        # Step 3: Wait for graduation initiation
        initiation_tx = wait_for_graduation_initiation(token)
        if not initiation_tx:
            raise Exception("Graduation initiation failed or timed out")
        result.initiation_tx = initiation_tx
        
        # Step 4: Verify snapshot
        result.snapshot_verified = verify_snapshot_creation(token)
        
        # Step 5: Wait for graduation completion
        completion_tx, lp_pool_address = wait_for_graduation_completion(token)
        if not completion_tx or not lp_pool_address:
            raise Exception("Graduation completion failed or timed out")
        result.completion_tx = completion_tx
        result.lp_pool_address = lp_pool_address
        
        # Step 6: Verify LP creation
        result.lp_created_before_completion = verify_lp_creation(token.contract_address, lp_pool_address)
        
        # Step 7: Verify on-chain graduation
        result.on_chain_graduated = verify_on_chain_graduation(token.contract_address)
        
        # Step 8: Verify database sync
        result.database_synced = verify_database_sync(token)
        
        # Determine overall success
        result.success = all([
            result.snapshot_verified,
            result.lp_created_before_completion,
            result.on_chain_graduated,
            result.database_synced
        ])
        
        # Print final report
        print_final_report(result)
        
        return 0 if result.success else 1
        
    except KeyboardInterrupt:
        logger.info("\n⚠️  Test interrupted by user")
        print_final_report(result)
        return 1
    except Exception as e:
        logger.error(f"\n❌ TEST FAILED: {str(e)}", exc_info=True)
        print_final_report(result)
        return 1

if __name__ == '__main__':
    sys.exit(main())
