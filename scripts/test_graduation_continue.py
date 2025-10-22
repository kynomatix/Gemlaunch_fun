#!/usr/bin/env python3
"""
Continue Graduation Test with Existing Token
Uses the recently created GRAD655 token
"""

import os
import sys
import time
import logging
import requests
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
    
    return oracle_account

def get_token_by_id(token_id):
    """Get token details from database"""
    from app import app, db
    from models import Token
    
    with app.app_context():
        token = Token.query.get(token_id)
        if not token:
            raise Exception(f"Token {token_id} not found")
        if not token.contract_address:
            raise Exception(f"Token {token_id} has no contract address")
        return token

def sign_and_relay_transaction(tx_data, oracle_account, tx_type="buy"):
    """Sign transaction with Oracle Wallet and relay to blockchain"""
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
                    return True
                elif status == 'failed':
                    return False
        except:
            pass
        
        time.sleep(5)
    
    return False

def execute_buy_to_graduation(token, oracle_account):
    """Execute buy trades to push market cap above $200"""
    logger.info("=" * 80)
    logger.info("Executing buy trades to reach graduation threshold")
    logger.info("=" * 80)
    
    # Get current stats
    stats_response = requests.get(f"{API_BASE_URL}/api/token/{token.contract_address}/stats")
    if stats_response.status_code != 200:
        raise Exception(f"Failed to get token stats")
    
    stats = stats_response.json()
    current_market_cap = stats.get('market_cap', 0)
    
    logger.info(f"Current market cap: ${current_market_cap:.2f}")
    logger.info(f"Target: $205.00")
    
    # Calculate KAS needed (with 20% safety margin for bonding curve dynamics)
    kas_price_usd = stats.get('kas_price_usd', 0.05137)
    target_market_cap = 205.0
    required_kas_reserve = target_market_cap / kas_price_usd
    current_kas_reserve = stats.get('market_cap_kas', 0)
    kas_to_buy = (required_kas_reserve - current_kas_reserve) * 1.2
    
    logger.info(f"KAS to buy: {kas_to_buy:.4f} KAS")
    
    # Get buy quote
    quote_response = requests.post(
        f"{API_BASE_URL}/api/trade/quote-buy",
        json={'token_address': token.contract_address, 'kas_amount': kas_to_buy},
        headers={'Content-Type': 'application/json'}
    )
    
    if quote_response.status_code != 200:
        raise Exception(f"Failed to get buy quote")
    
    quote = quote_response.json()
    if not quote.get('success'):
        raise Exception(f"Buy quote failed: {quote.get('error')}")
    
    tokens_out = int(float(quote.get('tokens_out', 0)) * 10**18)
    min_tokens_out = int(tokens_out * 0.95)
    deadline = int(time.time()) + 300
    
    # Build buy transaction
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
        raise Exception(f"Failed to build buy transaction")
    
    buy_tx_result = buy_tx_response.json()
    if not buy_tx_result.get('success'):
        raise Exception(f"Buy transaction build failed: {buy_tx_result.get('error')}")
    
    # Sign and relay
    logger.info("Signing and relaying buy transaction...")
    buy_tx_hash = sign_and_relay_transaction(buy_tx_result['tx_data'], oracle_account, tx_type="buy")
    
    logger.info(f"Buy TX: {buy_tx_hash}")
    logger.info("Waiting for confirmation...")
    
    if not wait_for_tx_confirmation(buy_tx_hash):
        raise Exception("Buy transaction confirmation failed")
    
    # Check new market cap
    stats_response = requests.get(f"{API_BASE_URL}/api/token/{token.contract_address}/stats")
    if stats_response.status_code == 200:
        stats = stats_response.json()
        new_market_cap = stats.get('market_cap', 0)
        logger.info(f"✅ New market cap: ${new_market_cap:.2f}")
        return new_market_cap
    
    return 205.0

def wait_for_graduation(token):
    """Wait for graduation to complete"""
    logger.info("\n" + "=" * 80)
    logger.info("Waiting for graduation (monitor runs every 60s, completion after 30s)")
    logger.info("=" * 80)
    
    from app import app, db
    from models import Token
    
    timeout = 180  # 3 minutes total
    start_time = time.time()
    
    with app.app_context():
        while time.time() - start_time < timeout:
            elapsed = int(time.time() - start_time)
            db.session.refresh(token)
            
            logger.info(f"[{elapsed}s] Status: {token.graduation_status}")
            
            if token.graduation_status == 'graduated':
                logger.info("✅ GRADUATION COMPLETED!")
                return True
            elif token.graduation_status == 'failed':
                logger.error("❌ GRADUATION FAILED")
                return False
            
            time.sleep(10)
        
        logger.error("❌ Timeout waiting for graduation")
        return False

def print_final_report(token):
    """Print final test report"""
    from app import app, db
    from models import Token
    
    logger.info("\n" + "=" * 80)
    logger.info("GRADUATION TEST REPORT")
    logger.info("=" * 80)
    
    with app.app_context():
        db.session.refresh(token)
        
        logger.info(f"\nToken: {token.name} ({token.symbol})")
        logger.info(f"Contract: {token.contract_address}")
        logger.info(f"Status: {token.graduation_status}")
        logger.info(f"\nInitiation TX: {token.graduation_initiation_tx}")
        logger.info(f"Completion TX: {token.graduation_completion_tx}")
        logger.info(f"\nDEX Pool: {token.dex_pool_address}")
        logger.info(f"DEX Position ID: {token.dex_position_id}")
        
        if token.graduation_status == 'graduated':
            logger.info("\n✅ TEST PASSED - Full graduation cycle completed!")
        else:
            logger.info(f"\n❌ TEST FAILED - Status: {token.graduation_status}")

def main():
    """Main test execution"""
    try:
        logger.info("=" * 80)
        logger.info("GRADUATION TEST - Using Existing Token")
        logger.info("=" * 80)
        
        oracle_account = derive_oracle_wallet()
        logger.info(f"Oracle Wallet: {oracle_account.address}")
        
        # Use existing token ID 61 (GRAD655)
        TOKEN_ID = 61
        logger.info(f"\nUsing existing token ID: {TOKEN_ID}")
        
        token = get_token_by_id(TOKEN_ID)
        logger.info(f"Token: {token.name} ({token.symbol})")
        logger.info(f"Contract: {token.contract_address}")
        
        # Execute buy trades
        market_cap = execute_buy_to_graduation(token, oracle_account)
        
        # Wait for graduation
        if not wait_for_graduation(token):
            return False
        
        # Print report
        print_final_report(token)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ TEST FAILED: {str(e)}", exc_info=True)
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
