#!/usr/bin/env python3
"""
Automated Graduation Testing Script

Tests the complete graduation flow without manual intervention:
1. Creates a test token
2. Buys it up to graduation threshold using oracle wallet
3. Verifies graduation triggers correctly
4. Monitors graduation completion

Usage:
    python3 scripts/test_graduation.py [--threshold USD_AMOUNT]
    
Example:
    python3 scripts/test_graduation.py --threshold 1.0
"""

import sys
import os
import time
import argparse
from decimal import Decimal

sys.path.insert(0, '/home/runner/workspace')

from app import app, db
from models import Token, PlatformSettings
from services.web3_service import get_web3_service
from services.graduation_state_manager import GraduationStateManager
from services.kas_oracle import oracle
from web3 import Web3

def create_test_token():
    """Create a test token for graduation testing"""
    print("📝 Creating test token...")
    
    web3_service = get_web3_service()
    oracle_wallet = web3_service.oracle_account
    
    # Create token metadata
    token_name = f"GRADTEST{int(time.time())}"
    token_symbol = token_name[:8]
    
    print(f"   Token: {token_name} ({token_symbol})")
    
    # Deploy token via factory
    factory = web3_service.contracts['TokenFactory']
    
    tx = factory.functions.createToken(
        token_name,                      # name
        token_symbol,                    # symbol
        1000000000,                      # totalSupply (1B tokens)
        "Automated graduation test",     # description
        "ipfs://QmTest",                 # imageUrl
        "",                               # twitterUrl
        "",                               # telegramUrl
        "",                               # websiteUrl
        False,                            # antiBotEnabled
        0,                                # reservedPercentage (BASIC token)
        0,                                # airdropsAllocation
        0,                                # marketingAllocation
        0                                 # teamAllocation
    ).build_transaction({
        'from': oracle_wallet.address,
        'nonce': web3_service.w3.eth.get_transaction_count(oracle_wallet.address),
        'gas': 3000000,
        'gasPrice': web3_service.w3.eth.gas_price
    })
    
    signed_tx = oracle_wallet.sign_transaction(tx)
    tx_hash = web3_service.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    
    print(f"   Deploying... TX: {tx_hash.hex()}")
    
    receipt = web3_service.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    
    if receipt['status'] != 1:
        raise Exception("Token deployment failed")
    
    # Extract token address from logs
    token_address = None
    for log in receipt['logs']:
        try:
            parsed = factory.events.TokenCreated().process_log(log)
            token_address = parsed['args']['token']
            break
        except:
            continue
    
    if not token_address:
        raise Exception("Could not extract token address from deployment")
    
    print(f"   ✅ Deployed: {token_address}")
    
    # Save to database
    with app.app_context():
        token = Token(
            name=token_name,
            symbol=token_symbol,
            contract_address=token_address,
            creator_address=oracle_wallet.address,
            image_url="ipfs://QmTest",
            description="Automated graduation test token",
            deployment_status='deployed',
            graduation_status='active',
            is_graduated=False,
            is_visible=True
        )
        db.session.add(token)
        db.session.commit()
        
        print(f"   💾 Saved to database (ID: {token.id})")
    
    return token_address, token_symbol

def buy_to_threshold(token_address, target_usd):
    """Buy token until market cap reaches target threshold"""
    print(f"\n💰 Buying token to ${target_usd} market cap...")
    
    web3_service = get_web3_service()
    oracle_wallet = web3_service.oracle_account
    pool = web3_service.get_bonding_pool_contract(token_address)
    
    # Calculate how much KAS needed
    target_kas = target_usd  # Assuming 1 KAS ≈ $1 on testnet
    
    print(f"   Target: ~{target_kas} KAS reserve")
    
    # Buy in increments to simulate real trading
    total_spent = Decimal(0)
    buy_amount = Decimal('0.5')  # 0.5 KAS per buy
    
    while True:
        # Check current market cap
        kas_reserve = pool.functions.virtualKasReserve().call()
        kas_reserve_decimal = Decimal(kas_reserve) / Decimal(10**18)
        market_cap_usd = oracle.get_market_cap_usd(kas_reserve)
        
        print(f"   Current: {kas_reserve_decimal:.4f} KAS (${market_cap_usd:.2f})")
        
        if market_cap_usd >= target_usd * 0.95:  # Within 5% is good enough
            print(f"   ✅ Target reached!")
            break
        
        # Execute buy
        kas_amount_wei = web3_service.w3.to_wei(buy_amount, 'ether')
        
        # Get quote first
        quote = pool.functions.getKasToBuy(kas_amount_wei).call()
        
        # Execute buy
        tx = pool.functions.buy(
            quote[0],  # minTokensOut
            oracle_wallet.address,  # recipient
            oracle_wallet.address   # referrer
        ).build_transaction({
            'from': oracle_wallet.address,
            'value': kas_amount_wei,
            'nonce': web3_service.w3.eth.get_transaction_count(oracle_wallet.address),
            'gas': 500000,
            'gasPrice': web3_service.w3.eth.gas_price
        })
        
        signed_tx = oracle_wallet.sign_transaction(tx)
        tx_hash = web3_service.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        receipt = web3_service.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
        
        if receipt['status'] != 1:
            print(f"   ⚠️ Buy failed")
            break
        
        total_spent += buy_amount
        print(f"   Bought {buy_amount} KAS (total: {total_spent} KAS)")
        
        time.sleep(1)  # Wait between buys
    
    return total_spent

def trigger_and_monitor_graduation(token_address, symbol):
    """Trigger graduation and monitor until completion"""
    print(f"\n🎓 Triggering graduation for {symbol}...")
    
    with app.app_context():
        token = Token.query.filter_by(contract_address=token_address).first()
        
        if not token:
            print("   ❌ Token not found in database")
            return False
        
        web3_service = get_web3_service()
        oracle_wallet = web3_service.oracle_account
        
        # Trigger graduation
        result = GraduationStateManager.initiate_graduation(token, oracle_wallet)
        
        if not result.get('success'):
            print(f"   ❌ Graduation failed: {result.get('error')}")
            return False
        
        print(f"   ✅ Initiated! TX: {result.get('tx_hash')}")
        print(f"   Status: {token.graduation_status}")
        
        # Monitor until completion
        print("\n📊 Monitoring graduation progress...")
        
        max_wait = 300  # 5 minutes max
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            db.session.refresh(token)
            
            print(f"   Status: {token.graduation_status} | Graduated: {token.is_graduated}")
            
            if token.is_graduated:
                print(f"\n   🎉 GRADUATION COMPLETE!")
                print(f"   DEX Pool: {token.dex_pool_address}")
                return True
            
            if token.graduation_status == 'active':
                print(f"   ⚠️ Graduation reverted to active (error occurred)")
                return False
            
            time.sleep(10)  # Check every 10 seconds
        
        print(f"   ⏱️ Timeout waiting for graduation")
        return False

def main():
    parser = argparse.ArgumentParser(description='Automated graduation testing')
    parser.add_argument('--threshold', type=float, default=1.0, help='Graduation threshold in USD (default: 1.0)')
    parser.add_argument('--skip-create', action='store_true', help='Skip token creation, use existing token')
    parser.add_argument('--token-address', type=str, help='Use existing token address')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("🧪 AUTOMATED GRADUATION TEST")
    print("=" * 70)
    
    # Set threshold
    with app.app_context():
        settings = PlatformSettings.get_settings()
        settings.graduation_threshold_usd = args.threshold
        db.session.commit()
        print(f"📊 Graduation threshold: ${args.threshold}")
    
    try:
        if args.skip_create and args.token_address:
            token_address = Web3.to_checksum_address(args.token_address)
            with app.app_context():
                token = Token.query.filter_by(contract_address=token_address).first()
                symbol = token.symbol if token else "UNKNOWN"
            print(f"🔄 Using existing token: {token_address}")
        else:
            # Create token
            token_address, symbol = create_test_token()
        
        # Buy to threshold
        kas_spent = buy_to_threshold(token_address, args.threshold)
        
        print(f"\n💸 Total KAS spent: {kas_spent}")
        
        # Trigger and monitor
        success = trigger_and_monitor_graduation(token_address, symbol)
        
        if success:
            print("\n" + "=" * 70)
            print("✅ GRADUATION TEST PASSED")
            print("=" * 70)
            return 0
        else:
            print("\n" + "=" * 70)
            print("❌ GRADUATION TEST FAILED")
            print("=" * 70)
            return 1
    
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
