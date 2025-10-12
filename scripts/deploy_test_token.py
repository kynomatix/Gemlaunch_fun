#!/usr/bin/env python3
"""
Deploy Test Token on Kasplex Testnet

This script deploys a real BondingCurvePool token through TokenFactory
for end-to-end API testing.

Usage:
    python scripts/deploy_test_token.py
"""

import os
import sys
import time
import json
import requests
from pathlib import Path
from web3 import Web3
from eth_account import Account

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Constants
API_BASE_URL = "http://localhost:5000"
KASPLEX_TESTNET_RPC = "https://rpc.kasplextest.xyz"
KASPLEX_TESTNET_CHAIN_ID = 167012
EXPECTED_ORACLE_ADDRESS = "0x5f837F62744D4d80Fc79C3A5346B4A228956914E"

def derive_oracle_wallet(deployer_private_key):
    """
    Derive Oracle Wallet from deployer private key
    Uses same method as web3_service.py:
    keccak256("GEMLAUNCH_SECONDARY_WALLET" + deployer_private_key)
    """
    try:
        # Initialize Web3 for keccak256
        w3 = Web3()
        
        # Normalize private key (ensure 0x prefix)
        if not deployer_private_key.startswith('0x'):
            deployer_private_key = f'0x{deployer_private_key}'
        
        # Derive secondary key: keccak256("GEMLAUNCH_SECONDARY_WALLET" + deployer_key)
        seed_text = "GEMLAUNCH_SECONDARY_WALLET"
        seed_bytes = seed_text.encode('utf-8')
        deployer_bytes = bytes.fromhex(deployer_private_key[2:])  # Remove 0x prefix
        
        # Concatenate and hash
        combined = seed_bytes + deployer_bytes
        derived_key = w3.keccak(combined)
        
        # Create account from derived key
        derived_key_hex = '0x' + derived_key.hex()
        oracle_account = Account.from_key(derived_key_hex)
        
        print(f"✅ Derived Oracle Wallet: {oracle_account.address}")
        
        # Verify it matches expected address
        if oracle_account.address.lower() != EXPECTED_ORACLE_ADDRESS.lower():
            print(f"⚠️  WARNING: Oracle address mismatch!")
            print(f"   Expected: {EXPECTED_ORACLE_ADDRESS}")
            print(f"   Got:      {oracle_account.address}")
        
        return oracle_account
        
    except Exception as e:
        print(f"❌ Failed to derive Oracle Wallet: {str(e)}")
        raise

def check_oracle_balance(oracle_address):
    """Check Oracle Wallet KAS balance"""
    try:
        w3 = Web3(Web3.HTTPProvider(KASPLEX_TESTNET_RPC))
        balance_wei = w3.eth.get_balance(oracle_address)
        balance_kas = w3.from_wei(balance_wei, 'ether')
        
        print(f"💰 Oracle Wallet Balance: {balance_kas} KAS")
        
        if balance_kas < 1:
            print(f"⚠️  WARNING: Low balance! Need at least 1 KAS for deployment + gas")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to check balance: {str(e)}")
        return False

def create_test_token(oracle_address):
    """Create test token via /api/token/create endpoint"""
    try:
        # Use timestamp to ensure unique token name
        import time
        timestamp = int(time.time())
        
        token_params = {
            "name": f"Phase3 Test Token {timestamp}",
            "symbol": f"P3T{timestamp % 10000}",  # Keep symbol short
            "description": "Test token for Phase 3 API validation",
            "total_supply": "1000000000",  # 1 billion tokens
            "reserved_percentage": "0",  # No reserved tokens
            "anti_bot_enabled": True,  # Enable anti-bot for testing
            "ipfs_hash": "QmTest123456789",  # Placeholder IPFS hash
            "website": "",
            "twitter": "",
            "telegram": "",
            "user_address": oracle_address  # Use Oracle as creator
        }
        
        print(f"\n📝 Creating token: {token_params['name']} ({token_params['symbol']})")
        
        response = requests.post(
            f"{API_BASE_URL}/api/token/create",
            json=token_params,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code != 200:
            print(f"❌ Token creation failed: {response.text}")
            return None
        
        result = response.json()
        
        if not result.get('success'):
            print(f"❌ Token creation failed: {result.get('error', 'Unknown error')}")
            return None
        
        print(f"✅ Token database record created (ID: {result['token_id']})")
        print(f"   Estimated gas: {result['estimated_gas']}")
        
        return result
        
    except Exception as e:
        print(f"❌ Failed to create token: {str(e)}")
        return None

def sign_and_relay_transaction(tx_data, oracle_account, tx_type="deploy_token"):
    """Sign transaction with Oracle Wallet and relay to blockchain"""
    try:
        w3 = Web3(Web3.HTTPProvider(KASPLEX_TESTNET_RPC))
        
        # Get current nonce
        nonce = w3.eth.get_transaction_count(oracle_account.address)
        
        # Get current gas price
        gas_price = w3.eth.gas_price
        
        # Build complete transaction
        transaction = {
            'to': tx_data['to'],
            'value': int(tx_data['value'], 16),
            'gas': int(tx_data['gas'], 16),
            'gasPrice': gas_price,
            'nonce': nonce,
            'chainId': KASPLEX_TESTNET_CHAIN_ID,
            'data': tx_data['data']
        }
        
        print(f"\n🔐 Signing transaction with Oracle Wallet...")
        print(f"   Nonce: {nonce}")
        print(f"   Gas: {transaction['gas']}")
        print(f"   Gas Price: {w3.from_wei(gas_price, 'gwei')} Gwei")
        
        # Sign transaction
        signed_tx = oracle_account.sign_transaction(transaction)
        
        print(f"✅ Transaction signed")
        
        # Relay to blockchain via API
        print(f"📡 Relaying transaction to blockchain...")
        
        # Format signed transaction with 0x prefix
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
            print(f"❌ Transaction relay failed: {relay_response.text}")
            return None
        
        relay_result = relay_response.json()
        
        if not relay_result.get('success'):
            print(f"❌ Transaction relay failed: {relay_result.get('error', 'Unknown error')}")
            return None
        
        tx_hash = relay_result['tx_hash']
        print(f"✅ Transaction relayed: {tx_hash}")
        print(f"🔗 Explorer: https://explorer.kasplextest.xyz/tx/{tx_hash}")
        
        return tx_hash
        
    except Exception as e:
        print(f"❌ Failed to sign and relay transaction: {str(e)}")
        return None

def wait_for_confirmation(tx_hash, timeout=120):
    """Wait for transaction confirmation using SSE or polling"""
    try:
        print(f"\n⏳ Waiting for transaction confirmation...")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Poll transaction status
            response = requests.get(f"{API_BASE_URL}/api/tx/{tx_hash}/status")
            
            if response.status_code == 200:
                result = response.json()
                status = result.get('status')
                
                if status == 'confirmed':
                    print(f"✅ Transaction confirmed!")
                    print(f"   Block: {result.get('block_number')}")
                    print(f"   Gas used: {result.get('gas_used')}")
                    return True
                
                elif status == 'failed':
                    print(f"❌ Transaction failed!")
                    print(f"   Error: {result.get('error_message', 'Unknown error')}")
                    return False
                
                else:
                    print(f"   Status: {status}... (checking again in 5s)")
            
            time.sleep(5)
        
        print(f"⏱️  Timeout waiting for confirmation")
        return False
        
    except Exception as e:
        print(f"❌ Error waiting for confirmation: {str(e)}")
        return False

def get_deployed_token(token_id):
    """Get deployed token details from database"""
    try:
        # Query token by ID via API or database
        # For now, we'll use a simple approach
        import sys
        sys.path.insert(0, str(project_root))
        
        from app import app, db
        from models import Token
        
        with app.app_context():
            token = Token.query.get(token_id)
            
            if not token:
                print(f"❌ Token not found in database")
                return None
            
            print(f"\n📊 Token Deployment Details:")
            print(f"   Name: {token.name}")
            print(f"   Symbol: {token.symbol}")
            print(f"   Contract Address: {token.contract_address}")
            print(f"   Deployment Status: {token.deployment_status}")
            print(f"   Total Supply: {token.total_supply}")
            print(f"   Anti-bot Enabled: {token.anti_bot_enabled}")
            
            return token
        
    except Exception as e:
        print(f"❌ Failed to get token details: {str(e)}")
        return None

def verify_contract_on_chain(contract_address):
    """Verify contract exists on blockchain"""
    try:
        w3 = Web3(Web3.HTTPProvider(KASPLEX_TESTNET_RPC))
        
        code = w3.eth.get_code(contract_address)
        
        if code == b'' or code == b'\x00':
            print(f"❌ No contract code at address {contract_address}")
            return False
        
        print(f"✅ Contract verified on-chain")
        print(f"   Address: {contract_address}")
        print(f"   Code size: {len(code)} bytes")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to verify contract: {str(e)}")
        return False

def test_quote_apis(token_address):
    """Test buy/sell quote APIs"""
    try:
        print(f"\n🧪 Testing Quote APIs...")
        
        # Test buy quote
        print(f"   Testing /api/trade/quote-buy...")
        buy_quote_response = requests.post(
            f"{API_BASE_URL}/api/trade/quote-buy",
            json={
                'token_address': token_address,
                'kas_amount': 1.0
            },
            headers={'Content-Type': 'application/json'}
        )
        
        if buy_quote_response.status_code == 200:
            buy_quote = buy_quote_response.json()
            if buy_quote.get('success'):
                print(f"   ✅ Buy quote API works!")
                print(f"      1 KAS → {buy_quote.get('tokens_out', 0)} tokens")
            else:
                print(f"   ❌ Buy quote failed: {buy_quote.get('error')}")
        else:
            print(f"   ❌ Buy quote API returned {buy_quote_response.status_code}")
        
        # Test sell quote (need some tokens first, so this might fail initially)
        print(f"   Testing /api/trade/quote-sell...")
        sell_quote_response = requests.post(
            f"{API_BASE_URL}/api/trade/quote-sell",
            json={
                'token_address': token_address,
                'token_amount': str(1000000 * 10**18)  # 1M tokens
            },
            headers={'Content-Type': 'application/json'}
        )
        
        if sell_quote_response.status_code == 200:
            sell_quote = sell_quote_response.json()
            if sell_quote.get('success'):
                print(f"   ✅ Sell quote API works!")
                print(f"      1M tokens → {sell_quote.get('kas_out', 0)} KAS")
            else:
                print(f"   ⚠️  Sell quote: {sell_quote.get('error')} (expected before first buy)")
        else:
            print(f"   ⚠️  Sell quote API returned {sell_quote_response.status_code} (expected)")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to test quote APIs: {str(e)}")
        return False

def seed_initial_liquidity(token_address, oracle_account):
    """Seed initial liquidity with a small buy (1 KAS)"""
    try:
        print(f"\n💧 Seeding initial liquidity (1 KAS buy)...")
        
        # Get buy quote first
        quote_response = requests.post(
            f"{API_BASE_URL}/api/trade/quote-buy",
            json={
                'token_address': token_address,
                'kas_amount': 1.0
            },
            headers={'Content-Type': 'application/json'}
        )
        
        if quote_response.status_code != 200:
            print(f"❌ Failed to get buy quote: {quote_response.text}")
            return False
        
        quote = quote_response.json()
        
        if not quote.get('success'):
            print(f"❌ Buy quote failed: {quote.get('error')}")
            return False
        
        tokens_out = int(float(quote.get('tokens_out', 0)) * 10**18)  # Convert to wei
        min_tokens_out = int(tokens_out * 0.95)  # 5% slippage tolerance
        deadline = int(time.time()) + 300  # 5 minutes
        
        print(f"   Quote: 1 KAS → {tokens_out / 10**18} tokens")
        
        # Build buy transaction
        buy_tx_response = requests.post(
            f"{API_BASE_URL}/api/trade/buy",
            json={
                'token_address': token_address,
                'kas_amount': 1.0,
                'min_tokens_out': min_tokens_out,
                'deadline': deadline,
                'user_address': oracle_account.address
            },
            headers={'Content-Type': 'application/json'}
        )
        
        if buy_tx_response.status_code != 200:
            print(f"❌ Failed to build buy transaction: {buy_tx_response.text}")
            return False
        
        buy_tx_result = buy_tx_response.json()
        
        if not buy_tx_result.get('success'):
            print(f"❌ Buy transaction build failed: {buy_tx_result.get('error')}")
            return False
        
        # Sign and relay buy transaction
        buy_tx_hash = sign_and_relay_transaction(
            buy_tx_result['tx_data'],
            oracle_account,
            tx_type="buy"
        )
        
        if not buy_tx_hash:
            return False
        
        # Wait for buy confirmation
        if wait_for_confirmation(buy_tx_hash):
            print(f"✅ Initial liquidity seeded successfully!")
            return True
        
        return False
        
    except Exception as e:
        print(f"❌ Failed to seed liquidity: {str(e)}")
        return False

def main():
    """Main deployment flow"""
    print("=" * 80)
    print("🚀 PHASE 3 TEST TOKEN DEPLOYMENT")
    print("=" * 80)
    
    # Step 1: Get deployer private key from environment
    deployer_private_key = os.environ.get('DEPLOYER_PRIVATE_KEY')
    
    if not deployer_private_key:
        print("❌ DEPLOYER_PRIVATE_KEY not found in environment")
        print("   Please ensure DEPLOYER_PRIVATE_KEY is set in Replit Secrets")
        return 1
    
    # Step 2: Derive Oracle Wallet
    print("\n[1/8] Deriving Oracle Wallet from DEPLOYER_PRIVATE_KEY...")
    oracle_account = derive_oracle_wallet(deployer_private_key)
    
    # Step 3: Check Oracle balance
    print("\n[2/8] Checking Oracle Wallet balance...")
    if not check_oracle_balance(oracle_account.address):
        print("⚠️  Continuing anyway (may fail if gas needed)...")
    
    # Step 4: Create test token
    print("\n[3/8] Creating test token...")
    token_result = create_test_token(oracle_account.address)
    
    if not token_result:
        return 1
    
    token_id = token_result['token_id']
    
    # Step 5: Sign and relay deployment transaction
    print("\n[4/8] Signing and relaying deployment transaction...")
    tx_hash = sign_and_relay_transaction(
        token_result['tx_data'],
        oracle_account,
        tx_type="deploy_token"
    )
    
    if not tx_hash:
        return 1
    
    # Step 6: Wait for confirmation
    print("\n[5/8] Waiting for deployment confirmation...")
    if not wait_for_confirmation(tx_hash):
        print("❌ Deployment failed or timed out")
        return 1
    
    # Step 7: Get deployed token details
    print("\n[6/8] Fetching deployed token details...")
    token = get_deployed_token(token_id)
    
    if not token or not token.contract_address:
        print("❌ Token not deployed (contract_address missing)")
        return 1
    
    # Step 8: Verify contract on-chain
    print("\n[7/8] Verifying contract on blockchain...")
    if not verify_contract_on_chain(token.contract_address):
        return 1
    
    # Step 9: Test quote APIs
    print("\n[8/8] Testing Quote APIs...")
    test_quote_apis(token.contract_address)
    
    # Optional: Seed initial liquidity
    seed_liquidity = input("\n💧 Seed initial liquidity with 1 KAS buy? (y/N): ").strip().lower()
    
    if seed_liquidity == 'y':
        seed_initial_liquidity(token.contract_address, oracle_account)
    
    # Final summary
    print("\n" + "=" * 80)
    print("✅ DEPLOYMENT COMPLETE!")
    print("=" * 80)
    print(f"\n📊 Token Details:")
    print(f"   Name: {token.name}")
    print(f"   Symbol: {token.symbol}")
    print(f"   Contract Address: {token.contract_address}")
    print(f"   Deployment TX: {tx_hash}")
    print(f"   Explorer: https://explorer.kasplextest.xyz/tx/{tx_hash}")
    print(f"   Token Page: {API_BASE_URL}/token/{token.contract_address}")
    
    print(f"\n🧪 Test APIs:")
    print(f"   Buy Quote: curl -X POST {API_BASE_URL}/api/trade/quote-buy -H 'Content-Type: application/json' -d '{{\"token_address\": \"{token.contract_address}\", \"kas_amount\": 1.0}}'")
    print(f"   Sell Quote: curl -X POST {API_BASE_URL}/api/trade/quote-sell -H 'Content-Type: application/json' -d '{{\"token_address\": \"{token.contract_address}\", \"token_amount\": \"1000000000000000000\"}}'")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
