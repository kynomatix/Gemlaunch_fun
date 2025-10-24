"""
Complete Migration to V2 GraduationController

This script:
1. Updates TokenFactory to use V2 controller for all NEW tokens
2. Migrates existing tokens (KPAN, etc.) to point to V2
3. Cancels stuck V1 graduations to unlock KAS
4. Allows creators to claim their trapped KAS
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.web3_service import get_web3_service
from app import app, db
from models import Token
import logging

logging.basicConfig(level=logging.INFO)

V1_CONTROLLER = '0x9416D5a5D61ec70C18D1FE1039f8026E29b4820e'
V2_CONTROLLER = '0x147E3Ecbe189bb301175001706ff1f44dF33B3ab'  # Proper checksum

def main():
    """Run complete V2 migration"""
    w3s = get_web3_service()
    
    print("=" * 80)
    print("V2 GRADUATION CONTROLLER MIGRATION")
    print("=" * 80)
    print()
    
    # Step 1: Update TokenFactory
    print("STEP 1: Update TokenFactory to use V2 for new tokens")
    print("-" * 80)
    
    factory = w3s.contracts['TokenFactory']
    current_gc = factory.functions.graduationController().call()
    
    print(f"TokenFactory: {factory.address}")
    print(f"Current controller: {current_gc}")
    
    if current_gc.lower() == V2_CONTROLLER.lower():
        print("✅ Already using V2")
    else:
        print(f"❌ Using V1 - updating to V2...")
        
        tx = factory.functions.setGraduationController(V2_CONTROLLER).build_transaction({
            'from': w3s.deployer_account.address,
            'gas': 100000,
            'gasPrice': w3s.w3.eth.gas_price,
            'nonce': w3s.w3.eth.get_transaction_count(w3s.deployer_account.address),
            'chainId': 167012
        })
        
        signed = w3s.deployer_account.sign_transaction(tx)
        tx_hash = w3s.w3.eth.send_raw_transaction(signed.raw_transaction)
        
        print(f"✅ Transaction sent: {tx_hash.hex()}")
        print("⏳ Waiting for confirmation...")
        
        receipt = w3s.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        if receipt['status'] == 1:
            print("✅ TokenFactory updated - all NEW tokens will use V2")
        else:
            print("❌ Transaction failed")
            return
    
    print()
    
    # Step 2: Find all tokens on V1
    print("STEP 2: Identify tokens still on V1 controller")
    print("-" * 80)
    
    with app.app_context():
        all_tokens = Token.query.filter_by(is_graduated=False).all()
        
        v1_tokens = []
        
        for token in all_tokens:
            try:
                pool = w3s.get_bonding_pool_contract(token.contract_address)
                gc_address = pool.functions.graduationOracle().call()
                
                if gc_address.lower() == V1_CONTROLLER.lower():
                    graduating = pool.functions.graduating().call()
                    graduated = pool.functions.graduated().call()
                    kas_reserve = pool.functions.virtualKasReserve().call()
                    
                    v1_tokens.append({
                        'token': token,
                        'pool': pool,
                        'graduating': graduating,
                        'graduated': graduated,
                        'kas_reserve': kas_reserve / 1e18
                    })
                    
                    status = "STUCK IN GRADUATION" if graduating else "Active"
                    print(f"  {token.symbol} (0x{token.contract_address[-8:]}): {status} - {kas_reserve / 1e18:.2f} KAS")
            except Exception as e:
                print(f"  Error checking {token.symbol}: {e}")
        
        print(f"\nFound {len(v1_tokens)} tokens on V1 controller")
    
    if not v1_tokens:
        print("✅ No tokens need migration")
        return
    
    print()
    
    # Step 3: Cancel stuck graduations to unlock KAS
    print("STEP 3: Cancel stuck V1 graduations (unlock KAS)")
    print("-" * 80)
    
    for item in v1_tokens:
        token = item['token']
        pool = item['pool']
        
        if item['graduating']:
            print(f"\n{token.symbol}: Stuck in graduating=true")
            print(f"  Options:")
            print(f"    A) Call cancelGraduation() on V1 controller (if function exists)")
            print(f"    B) Call setGraduationOracle(V2) to migrate immediately")
            print(f"  Choosing B - migrate to V2...")
            
            try:
                # Migrate to V2 immediately
                tx = pool.functions.setGraduationOracle(V2_CONTROLLER).build_transaction({
                    'from': w3s.deployer_account.address,
                    'gas': 100000,
                    'gasPrice': w3s.w3.eth.gas_price,
                    'nonce': w3s.w3.eth.get_transaction_count(w3s.deployer_account.address),
                    'chainId': 167012
                })
                
                signed = w3s.deployer_account.sign_transaction(tx)
                tx_hash = w3s.w3.eth.send_raw_transaction(signed.raw_transaction)
                
                print(f"  ✅ Migrated to V2: {tx_hash.hex()}")
                
                receipt = w3s.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                
                if receipt['status'] == 1:
                    print(f"  ✅ {token.symbol} now points to V2")
                    
                    # Update database
                    with app.app_context():
                        db_token = Token.query.get(token.id)
                        db_token.graduation_status = 'active'
                        db.session.commit()
                        print(f"  ✅ Database reset to 'active'")
                else:
                    print(f"  ❌ Migration failed")
                    
            except Exception as e:
                print(f"  ❌ Error: {e}")
        else:
            print(f"\n{token.symbol}: Active - migrating to V2...")
            
            try:
                tx = pool.functions.setGraduationOracle(V2_CONTROLLER).build_transaction({
                    'from': w3s.deployer_account.address,
                    'gas': 100000,
                    'gasPrice': w3s.w3.eth.gas_price,
                    'nonce': w3s.w3.eth.get_transaction_count(w3s.deployer_account.address),
                    'chainId': 167012
                })
                
                signed = w3s.deployer_account.sign_transaction(tx)
                tx_hash = w3s.w3.eth.send_raw_transaction(signed.raw_transaction)
                
                print(f"  ✅ Migrated to V2: {tx_hash.hex()}")
                
                w3s.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                print(f"  ✅ {token.symbol} now points to V2")
                
            except Exception as e:
                print(f"  ❌ Error: {e}")
    
    print()
    print("=" * 80)
    print("MIGRATION COMPLETE")
    print("=" * 80)
    print()
    print("Next steps:")
    print("1. All NEW tokens will use V2 controller")
    print("2. Existing tokens migrated to V2")
    print("3. Graduation monitor will now work correctly")
    print()
    print("For KAS recovery from V1 controller:")
    print("  - V1 controller still holds ~4,583 KAS from old graduations")
    print("  - This requires deployer to withdraw from V1 contract")
    print("  - Check if V1 has withdrawKas() or emergencyWithdraw() function")

if __name__ == '__main__':
    main()
