#!/usr/bin/env python3
"""
End-to-End Graduation Test Script
Tests the complete graduation cycle with TokenFactory V2
"""

import os
import sys
import time
import json
import logging
import requests
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from web3 import Web3
from eth_account import Account

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
API_BASE_URL = "http://localhost:5000"
KASPLEX_TESTNET_RPC = "https://rpc.kasplextest.xyz"
KASPLEX_TESTNET_CHAIN_ID = 167012

def derive_oracle_wallet():
    """Derive Oracle Wallet from deployer private key"""
    deployer_private_key = os.environ.get('DEPLOYER_PRIVATE_KEY')
    if not deployer_private_key:
        raise Exception("DEPLOYER_PRIVATE_KEY not found in environment")
    
    w3 = Web3()
    
    if not deployer_private_key.startswith('0x'):
        deployer_private_key = f'0x{deployer_private_key}'
    
    seed_text = "GEMLAUNCH_SECONDARY_WALLET"
    seed_bytes = seed_text.encode('utf-8')
    deployer_bytes = bytes.fromhex(deployer_private_key[2:])
    combined = seed_bytes + deployer_bytes
    derived_key = w3.keccak(combined)
    derived_key_hex = '0x' + derived_key.hex()
    oracle_account = Account.from_key(derived_key_hex)
    
    logger.info(f"Oracle Wallet: {oracle_account.address}")
    return oracle_account

def sign_and_relay_transaction(tx_data, oracle_account, tx_type="deploy_token"):
    """Sign transaction with Oracle Wallet and relay to blockchain"""
    try:
        w3 = Web3(Web3.HTTPProvider(KASPLEX_TESTNET_RPC))
        nonce = w3.eth.get_transaction_count(oracle_account.address)
        gas_price = w3.eth.gas_price
        
        transaction = {
            'to': tx_data['to'],
            'value': int(tx_data['value'], 16),
            'gas': int(tx_data['gas'], 16),
            'gasPrice': gas_price,
            'nonce': nonce,
            'chainId': KASPLEX_TESTNET_CHAIN_ID,
            'data': tx_data['data']
        }
        
        signed_tx = oracle_account.sign_transaction(transaction)
        signed_tx_hex = '0x' + signed_tx.raw_transaction.hex() if not signed_tx.raw_transaction.hex().startswith('0x') else signed_tx.raw_transaction.hex()
        
        relay_response = requests.post(
            f"{API_BASE_URL}/api/relay/transaction",
            json={
                'signed_tx': signed_tx_hex,
                'tx_type': tx_type,
                'user_address': oracle_account.address
            },
            headers={'Content-Type': 'application/json'}
        )
        
        if relay_response.status_code != 200:
            raise Exception(f"Transaction relay failed: {relay_response.text}")
        
        relay_result = relay_response.json()
        if not relay_result.get('success'):
            raise Exception(f"Transaction relay failed: {relay_result.get('error', 'Unknown error')}")
        
        return relay_result['tx_hash']
        
    except Exception as e:
        raise Exception(f"Failed to sign and relay transaction: {str(e)}")

def wait_for_tx_confirmation(tx_hash, timeout=120):
    """Wait for transaction confirmation"""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"{API_BASE_URL}/api/tx/{tx_hash}/status")
            
            if response.status_code == 200:
                result = response.json()
                status = result.get('status')
                
                if status == 'confirmed':
                    logger.info(f"✅ Transaction confirmed!")
                    logger.info(f"   Block: {result.get('block_number')}")
                    logger.info(f"   Gas used: {result.get('gas_used')}")
                    return True
                elif status == 'failed':
                    logger.error(f"❌ Transaction failed!")
                    return False
        except:
            pass
        
        time.sleep(5)
    
    logger.error(f"❌ Timeout waiting for confirmation")
    return False

def create_test_token(oracle_account):
    """Create a new BASIC token for testing"""
    logger.info("=" * 80)
    logger.info("STEP 1: Creating test token 'Graduation Test Token' (GRAD)")
    logger.info("=" * 80)
    
    try:
        # Use timestamp to ensure unique name
        timestamp = int(time.time())
        
        # Create token via API
        token_params = {
            "name": f"Graduation Test {timestamp}",
            "symbol": f"GRAD{timestamp % 1000}",
            "description": "Testing graduation fix with TokenFactory V2",
            "total_supply": "1000000",  # 1M tokens
            "reserved_percentage": "0",  # BASIC token (no vesting)
            "anti_bot_enabled": False,
            "ipfs_hash": "QmGradTest123",
            "website": "",
            "twitter": "",
            "telegram": "",
            "user_address": oracle_account.address
        }
        
        logger.info(f"Creating token: {token_params['name']} ({token_params['symbol']})")
        
        response = requests.post(
            f"{API_BASE_URL}/api/token/create",
            json=token_params,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code != 200:
            raise Exception(f"Token creation failed: {response.text}")
        
        result = response.json()
        
        if not result.get('success'):
            raise Exception(f"Token creation failed: {result.get('error', 'Unknown error')}")
        
        token_id = result['token_id']
        logger.info(f"✅ Token database record created (ID: {token_id})")
        logger.info(f"   Estimated gas: {result['estimated_gas']}")
        
        # Sign and relay deployment transaction
        logger.info("\nSigning and relaying deployment transaction...")
        tx_hash = sign_and_relay_transaction(
            result['tx_data'],
            oracle_account,
            tx_type="deploy_token"
        )
        
        logger.info(f"   Deployment TX: {tx_hash}")
        
        # Wait for confirmation
        logger.info("   Waiting for deployment confirmation...")
        if not wait_for_tx_confirmation(tx_hash):
            raise Exception("Deployment confirmation failed")
        
        # Wait for event indexer to process the TokenCreated event and populate contract_address
        logger.info("   Waiting for event indexer to process deployment...")
        from app import app, db
        from models import Token
        
        max_wait = 60  # Wait up to 60 seconds
        start_time = time.time()
        
        with app.app_context():
            while time.time() - start_time < max_wait:
                token = Token.query.get(token_id)
                
                if token and token.contract_address:
                    logger.info(f"✅ Token deployed successfully!")
                    logger.info(f"   Contract Address: {token.contract_address}")
                    logger.info(f"   Deployment TX: {token.deployment_tx}")
                    return token
                
                logger.info(f"   Waiting for contract address... ({int(time.time() - start_time)}s)")
                time.sleep(5)
            
            raise Exception("Timeout waiting for contract address to be indexed")
                
    except Exception as e:
        logger.error(f"❌ Deployment failed: {str(e)}")
        raise

def execute_buy_trades(token, oracle_account):
    """Execute buy trades to push market cap above $200"""
    logger.info("\n" + "=" * 80)
    logger.info("STEP 2: Executing buy trades to reach graduation threshold")
    logger.info("=" * 80)
    
    try:
        # Get current market cap from API
        stats_response = requests.get(f"{API_BASE_URL}/api/token/{token.contract_address}/stats")
        if stats_response.status_code != 200:
            raise Exception(f"Failed to get token stats: {stats_response.text}")
        
        stats = stats_response.json()
        current_market_cap = stats.get('market_cap', 0)
        
        logger.info(f"Current market cap: ${current_market_cap:.2f}")
        logger.info(f"Graduation threshold: $200.00")
        logger.info(f"Target market cap: $205.00 (safety margin)")
        
        # Calculate KAS needed
        kas_price_usd = stats.get('kas_price_usd', 0.05137)
        logger.info(f"Current KAS price: ${kas_price_usd:.4f}")
        
        target_market_cap = 205.0
        required_kas_reserve = target_market_cap / kas_price_usd
        current_kas_reserve = stats.get('market_cap_kas', 0)
        kas_to_buy = required_kas_reserve - current_kas_reserve
        
        # Add 10% safety margin
        kas_to_buy = kas_to_buy * 1.1
        
        logger.info(f"\nKAS Reserve Analysis:")
        logger.info(f"   Current reserve: {current_kas_reserve:.4f} KAS")
        logger.info(f"   Required reserve: {required_kas_reserve:.4f} KAS")
        logger.info(f"   KAS to buy with: {kas_to_buy:.4f} KAS")
        
        # Get buy quote
        logger.info(f"\nGetting buy quote...")
        quote_response = requests.post(
            f"{API_BASE_URL}/api/trade/quote-buy",
            json={
                'token_address': token.contract_address,
                'kas_amount': kas_to_buy
            },
            headers={'Content-Type': 'application/json'}
        )
        
        if quote_response.status_code != 200:
            raise Exception(f"Failed to get buy quote: {quote_response.text}")
        
        quote = quote_response.json()
        if not quote.get('success'):
            raise Exception(f"Buy quote failed: {quote.get('error')}")
        
        tokens_out = int(float(quote.get('tokens_out', 0)) * 10**18)
        min_tokens_out = int(tokens_out * 0.95)  # 5% slippage
        deadline = int(time.time()) + 300
        
        logger.info(f"   Quote: {kas_to_buy:.4f} KAS → {tokens_out / 10**18:.2f} tokens")
        
        # Build buy transaction
        logger.info(f"\nBuilding buy transaction...")
        buy_tx_response = requests.post(
            f"{API_BASE_URL}/api/trade/buy",
            json={
                'token_address': token.contract_address,
                'kas_amount': kas_to_buy,
                'min_tokens_out': min_tokens_out,
                'deadline': deadline,
                'user_address': oracle_account.address
            },
            headers={'Content-Type': 'application/json'}
        )
        
        if buy_tx_response.status_code != 200:
            raise Exception(f"Failed to build buy transaction: {buy_tx_response.text}")
        
        buy_tx_result = buy_tx_response.json()
        if not buy_tx_result.get('success'):
            raise Exception(f"Buy transaction build failed: {buy_tx_result.get('error')}")
        
        # Sign and relay
        logger.info(f"Signing and relaying buy transaction...")
        buy_tx_hash = sign_and_relay_transaction(
            buy_tx_result['tx_data'],
            oracle_account,
            tx_type="buy"
        )
        
        logger.info(f"   Buy TX: {buy_tx_hash}")
        
        # Wait for confirmation
        logger.info("   Waiting for confirmation...")
        if not wait_for_tx_confirmation(buy_tx_hash):
            raise Exception("Buy transaction confirmation failed")
        
        # Check new market cap
        stats_response = requests.get(f"{API_BASE_URL}/api/token/{token.contract_address}/stats")
        if stats_response.status_code == 200:
            stats = stats_response.json()
            new_market_cap = stats.get('market_cap', 0)
            
            logger.info(f"\n✅ Buy trade executed!")
            logger.info(f"   New market cap: ${new_market_cap:.2f}")
            logger.info(f"   Progress: {(new_market_cap / 200.0) * 100:.1f}%")
            
            if new_market_cap >= 200:
                logger.info(f"🎓 Token is now ready for graduation!")
            else:
                logger.warning(f"⚠️  Token has not reached graduation threshold yet")
            
            return new_market_cap
        else:
            logger.warning("Could not verify new market cap")
            return 205.0  # Assume success
            
    except Exception as e:
        logger.error(f"❌ Buy trade failed: {str(e)}")
        raise

def wait_for_graduation_initiation(token, timeout=180):
    """Wait for graduation monitor to detect and initiate graduation"""
    logger.info("\n" + "=" * 80)
    logger.info("STEP 3: Waiting for graduation monitor to detect token")
    logger.info("=" * 80)
    logger.info(f"Graduation monitor runs every 60 seconds")
    logger.info(f"Waiting up to {timeout} seconds for initiation...")
    
    start_time = time.time()
    check_interval = 5  # Check database every 5 seconds
    
    with app.app_context():
        while time.time() - start_time < timeout:
            elapsed = int(time.time() - start_time)
            
            # Refresh token from database
            db.session.refresh(token)
            
            logger.info(f"\n[{elapsed}s] Checking token status...")
            logger.info(f"   Graduation status: {token.graduation_status}")
            
            if token.graduation_status == 'initiating':
                logger.info(f"✅ Graduation initiation detected!")
                logger.info(f"   Initiated at: {token.graduation_initiated_at}")
                logger.info(f"   Initiation TX: {token.graduation_initiation_tx}")
                return True
            
            elif token.graduation_status == 'failed':
                logger.error(f"❌ Graduation initiation FAILED")
                return False
            
            time.sleep(check_interval)
        
        logger.error(f"❌ Timeout waiting for graduation initiation ({timeout}s)")
        return False

def verify_graduation_initiation(token):
    """Verify graduation initiation transaction and blockchain state"""
    logger.info("\n" + "=" * 80)
    logger.info("STEP 4: Verifying graduation initiation")
    logger.info("=" * 80)
    
    with app.app_context():
        web3_service = get_web3_service()
        
        # Check transaction receipt
        logger.info(f"Checking transaction receipt...")
        logger.info(f"   TX hash: {token.graduation_initiation_tx}")
        
        try:
            receipt = web3_service.w3.eth.get_transaction_receipt(token.graduation_initiation_tx)
            
            if receipt['status'] == 1:
                logger.info(f"✅ Transaction succeeded!")
                logger.info(f"   Block number: {receipt['blockNumber']}")
                logger.info(f"   Gas used: {receipt['gasUsed']:,}")
            else:
                logger.error(f"❌ Transaction FAILED!")
                logger.error(f"   Status: {receipt['status']}")
                return False
            
        except Exception as e:
            logger.error(f"❌ Could not get transaction receipt: {str(e)}")
            return False
        
        # Check pool.graduating() state
        logger.info(f"\nChecking pool graduation state...")
        
        try:
            pool = web3_service.get_bonding_pool_contract(token.contract_address)
            is_graduating = pool.functions.graduating().call()
            
            if is_graduating:
                logger.info(f"✅ pool.graduating() returns TRUE")
            else:
                logger.error(f"❌ pool.graduating() returns FALSE (should be TRUE)")
                return False
            
        except Exception as e:
            logger.error(f"❌ Could not check graduating state: {str(e)}")
            return False
        
        logger.info(f"\n✅ Graduation initiation verified successfully!")
        return True

def wait_for_graduation_completion(token, timeout=120):
    """Wait for automatic graduation completion (30s after initiation)"""
    logger.info("\n" + "=" * 80)
    logger.info("STEP 5: Waiting for graduation completion")
    logger.info("=" * 80)
    logger.info(f"Graduation completes automatically 30 seconds after initiation")
    logger.info(f"Waiting up to {timeout} seconds...")
    
    start_time = time.time()
    check_interval = 5
    
    with app.app_context():
        while time.time() - start_time < timeout:
            elapsed = int(time.time() - start_time)
            
            # Refresh token from database
            db.session.refresh(token)
            
            logger.info(f"\n[{elapsed}s] Checking graduation status...")
            logger.info(f"   Status: {token.graduation_status}")
            
            if token.graduation_status == 'graduated':
                logger.info(f"✅ Graduation completed!")
                logger.info(f"   Completed at: {token.graduated_at}")
                logger.info(f"   Completion TX: {token.graduation_completion_tx}")
                return True
            
            elif token.graduation_status == 'failed':
                logger.error(f"❌ Graduation FAILED during completion")
                return False
            
            time.sleep(check_interval)
        
        logger.error(f"❌ Timeout waiting for graduation completion ({timeout}s)")
        return False

def verify_graduation_completion(token):
    """Verify graduation completion and DEX pool creation"""
    logger.info("\n" + "=" * 80)
    logger.info("STEP 6: Verifying graduation completion")
    logger.info("=" * 80)
    
    with app.app_context():
        web3_service = get_web3_service()
        
        # Check completion transaction
        logger.info(f"Checking completion transaction...")
        logger.info(f"   TX hash: {token.graduation_completion_tx}")
        
        try:
            receipt = web3_service.w3.eth.get_transaction_receipt(token.graduation_completion_tx)
            
            if receipt['status'] == 1:
                logger.info(f"✅ Completion transaction succeeded!")
                logger.info(f"   Block number: {receipt['blockNumber']}")
                logger.info(f"   Gas used: {receipt['gasUsed']:,}")
            else:
                logger.error(f"❌ Completion transaction FAILED!")
                return False
            
        except Exception as e:
            logger.error(f"❌ Could not get completion transaction receipt: {str(e)}")
            return False
        
        # Check DEX pool address
        logger.info(f"\nChecking DEX pool creation...")
        
        if token.dex_pool_address:
            logger.info(f"✅ DEX pool created!")
            logger.info(f"   Pool address: {token.dex_pool_address}")
            logger.info(f"   Pool fee tier: {token.dex_pool_fee_tier}")
        else:
            logger.error(f"❌ DEX pool address not set")
            return False
        
        # Check LP position
        if token.dex_position_id:
            logger.info(f"✅ LP position created!")
            logger.info(f"   Position ID: {token.dex_position_id}")
        else:
            logger.warning(f"⚠️  LP position ID not set")
        
        logger.info(f"\n✅ Graduation completion verified successfully!")
        return True

def print_final_report(token, market_cap):
    """Print final test report"""
    logger.info("\n" + "=" * 80)
    logger.info("FINAL TEST REPORT")
    logger.info("=" * 80)
    
    with app.app_context():
        db.session.refresh(token)
        
        logger.info(f"\n📊 Token Information:")
        logger.info(f"   Name: {token.name}")
        logger.info(f"   Symbol: {token.symbol}")
        logger.info(f"   Contract Address: {token.contract_address}")
        logger.info(f"   Total Supply: {token.total_supply:,}")
        
        logger.info(f"\n🎓 Graduation Results:")
        logger.info(f"   Final Status: {token.graduation_status}")
        logger.info(f"   Market Cap (before): ${market_cap:.2f}")
        logger.info(f"   Graduation Threshold: $200.00")
        
        logger.info(f"\n📝 Transaction Hashes:")
        logger.info(f"   Deployment: {token.deployment_tx}")
        logger.info(f"   Initiation: {token.graduation_initiation_tx}")
        logger.info(f"   Completion: {token.graduation_completion_tx}")
        
        logger.info(f"\n🏊 DEX Pool Information:")
        logger.info(f"   Pool Address: {token.dex_pool_address}")
        logger.info(f"   Fee Tier: {token.dex_pool_fee_tier}")
        logger.info(f"   Position ID: {token.dex_position_id}")
        
        if token.graduation_status == 'graduated':
            logger.info(f"\n✅ TEST PASSED - Full graduation cycle completed successfully!")
            logger.info(f"   The TokenFactory V2 graduation fix is working correctly.")
        else:
            logger.info(f"\n❌ TEST FAILED - Graduation did not complete")
            logger.info(f"   Current status: {token.graduation_status}")

def main():
    """Main test execution"""
    try:
        logger.info("=" * 80)
        logger.info("END-TO-END GRADUATION TEST - TokenFactory V2")
        logger.info("=" * 80)
        
        # Get oracle wallet
        oracle_account = derive_oracle_wallet()
        
        # Step 1: Create test token
        token = create_test_token(oracle_account)
        
        # Step 2: Execute buy trades
        market_cap = execute_buy_trades(token, oracle_account)
        
        # Step 3: Wait for graduation initiation
        if not wait_for_graduation_initiation(token):
            logger.error("❌ TEST FAILED: Graduation initiation timeout")
            return False
        
        # Step 4: Verify initiation
        if not verify_graduation_initiation(token):
            logger.error("❌ TEST FAILED: Graduation initiation verification failed")
            return False
        
        # Step 5: Wait for completion
        if not wait_for_graduation_completion(token):
            logger.error("❌ TEST FAILED: Graduation completion timeout")
            return False
        
        # Step 6: Verify completion
        if not verify_graduation_completion(token):
            logger.error("❌ TEST FAILED: Graduation completion verification failed")
            return False
        
        # Print final report
        print_final_report(token, market_cap)
        
        return True
        
    except KeyboardInterrupt:
        logger.info("\n⚠️  Test interrupted by user")
        return False
    except Exception as e:
        logger.error(f"\n❌ TEST FAILED with exception: {str(e)}", exc_info=True)
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
