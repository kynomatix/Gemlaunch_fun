#!/usr/bin/env python3
"""
Test script to validate DEX trading with Oracle wallet
This bypasses MetaMask to isolate the issue
"""
import os
import sys
import time
from web3 import Web3
from services.web3_service import Web3Service

def test_dex_buy():
    """Test DEX buy transaction using Oracle wallet"""
    
    print("=" * 60)
    print("DEX BUY TEST - Using Oracle Wallet")
    print("=" * 60)
    
    # Initialize Web3Service
    w3_service = Web3Service()
    
    # Oracle wallet address
    oracle_address = w3_service.oracle_account.address
    print(f"\n📍 Oracle Wallet: {oracle_address}")
    
    # Get Oracle KAS balance
    balance_wei = w3_service.w3.eth.get_balance(oracle_address)
    balance_kas = w3_service.w3.from_wei(balance_wei, 'ether')
    print(f"💰 Oracle Balance: {balance_kas:.4f} KAS")
    
    if balance_kas < 1:
        print("❌ Insufficient KAS balance for test")
        return False
    
    # Test parameters - buy 1 KAS worth of MEGA
    token_address = "0xaE1CB77F32776Ce607175C603064aed639754Da6"  # MEGA
    pool_address = "0x1Bc9e2F8a3f1e89D741333CC85847e2C34F5E44D"  # MEGA DEX pool
    kas_amount = w3_service.w3.to_wei(1, 'ether')  # 1 KAS
    
    print(f"\n🎯 Target Token: {token_address}")
    print(f"🏊 Pool Address: {pool_address}")
    print(f"💵 KAS Amount: 1.0 KAS")
    
    try:
        # Step 1: Get quote
        print("\n" + "=" * 60)
        print("STEP 1: Getting DEX Buy Quote")
        print("=" * 60)
        
        quote = w3_service.get_dex_buy_quote(
            token_address,
            pool_address,
            kas_amount,
            fee_tier=2500  # 0.25%
        )
        
        print(f"✅ Quote received:")
        print(f"   - Tokens out: {w3_service.w3.from_wei(quote['tokens_out'], 'ether'):.4f}")
        print(f"   - Execution price: {quote['execution_price']:.8f} KAS/token")
        print(f"   - Price impact: {quote['price_impact_percent']:.2f}%")
        print(f"   - Gas estimate: {quote['gas_estimate']}")
        
        # Step 2: Build transaction
        print("\n" + "=" * 60)
        print("STEP 2: Building Transaction")
        print("=" * 60)
        
        deadline = int(time.time()) + 600  # 10 min deadline
        min_tokens_out = int(quote['tokens_out'] * 0.95)  # 5% slippage
        
        tx_unsigned = w3_service.build_dex_buy_tx(
            oracle_address,
            token_address,
            pool_address,
            kas_amount,
            min_tokens_out,
            deadline,
            fee_tier=2500
        )
        
        print(f"✅ Transaction built:")
        print(f"   - To: {tx_unsigned['to']}")
        print(f"   - Value: {int(tx_unsigned['value'], 16)} wei")
        print(f"   - Data: {tx_unsigned['data'][:66]}...")
        
        # Step 3: Sign and send
        print("\n" + "=" * 60)
        print("STEP 3: Signing & Broadcasting")
        print("=" * 60)
        
        # Add nonce and gas
        nonce = w3_service.w3.eth.get_transaction_count(oracle_address)
        gas_price = w3_service.w3.eth.gas_price
        
        tx_unsigned['nonce'] = nonce
        tx_unsigned['gas'] = 300000  # Estimate
        tx_unsigned['gasPrice'] = gas_price
        
        # Convert hex strings to int for signing
        tx_unsigned['value'] = int(tx_unsigned['value'], 16)
        
        print(f"📝 Signing with Oracle wallet...")
        signed_tx = w3_service.w3.eth.account.sign_transaction(
            tx_unsigned,
            w3_service.oracle_account.key
        )
        
        print(f"📡 Broadcasting transaction...")
        print(f"   - Raw TX: {signed_tx.raw_transaction.hex()[:100]}...")
        
        try:
            tx_hash = w3_service.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_hash_hex = tx_hash.hex()
            
            print(f"✅ RPC accepted broadcast!")
            print(f"   - Hash: {tx_hash_hex}")
            print(f"   - Explorer: https://explorer.kasplextest.xyz/tx/{tx_hash_hex}")
            
            # Check if transaction is in mempool
            print(f"\n🔍 Checking transaction status...")
            try:
                pending_tx = w3_service.w3.eth.get_transaction(tx_hash)
                print(f"✅ Transaction found in mempool/pending")
                print(f"   - From: {pending_tx['from']}")
                print(f"   - To: {pending_tx['to']}")
                print(f"   - Value: {pending_tx['value']}")
                print(f"   - Gas: {pending_tx['gas']}")
                print(f"   - GasPrice: {pending_tx['gasPrice']}")
            except Exception as e:
                print(f"❌ Transaction NOT in mempool: {e}")
                
        except Exception as broadcast_error:
            print(f"❌ RPC rejected broadcast: {broadcast_error}")
            raise
        
        # Step 4: Wait for confirmation
        print("\n" + "=" * 60)
        print("STEP 4: Waiting for Confirmation")
        print("=" * 60)
        
        print("⏳ Waiting for receipt (60s timeout)...")
        receipt = w3_service.w3.eth.wait_for_transaction_receipt(
            tx_hash,
            timeout=60
        )
        
        if receipt['status'] == 1:
            print(f"✅ SUCCESS! Transaction confirmed in block {receipt['blockNumber']}")
            print(f"   - Gas used: {receipt['gasUsed']}")
            return True
        else:
            print(f"❌ FAILED! Transaction reverted")
            print(f"   - Block: {receipt['blockNumber']}")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_dex_buy()
    sys.exit(0 if success else 1)
