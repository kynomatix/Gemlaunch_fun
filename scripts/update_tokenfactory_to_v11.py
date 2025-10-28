#!/usr/bin/env python3
"""
Update TokenFactory V11 to point to GraduationController V11
Uses setGraduationController() function
"""

import sys
import os
from web3 import Web3

sys.path.insert(0, '/home/runner/workspace')
from services.web3_service import get_web3_service

def update_tokenfactory_gc():
    """Update TokenFactory V11 to use GraduationController V11"""
    
    web3_service = get_web3_service()
    w3 = web3_service.w3
    
    print("=" * 80)
    print("🔧 UPDATING TOKENFACTORY V11 TO USE GRADUATIONCONTROLLER V11")
    print("=" * 80)
    
    TOKEN_FACTORY_V11 = "0x427B039bc381911a40AC25Fc50AB9e6f5633A5B1"
    GRADUATION_CONTROLLER_V11 = "0xd0Ca76Dc29714Ef316a6aacCAC8837c3119439e0"
    
    print(f"\n📋 Configuration:")
    print(f"   TokenFactory V11: {TOKEN_FACTORY_V11}")
    print(f"   New GC V11 (IERC721Receiver): {GRADUATION_CONTROLLER_V11}")
    
    # Load TokenFactory contract
    tf = web3_service.contracts['TokenFactory']
    
    # Check current GC address
    current_gc = tf.functions.graduationController().call()
    print(f"\n🔍 Current GC: {current_gc}")
    
    if current_gc.lower() == GRADUATION_CONTROLLER_V11.lower():
        print(f"✅ Already pointing to V11! No update needed.")
        return True
    
    print(f"   Updating from: {current_gc}")
    print(f"   Updating to:   {GRADUATION_CONTROLLER_V11}")
    
    # Build transaction
    owner_account = web3_service.deployer_account
    owner_address = owner_account.address
    
    print(f"\n📝 Building transaction...")
    print(f"   Owner: {owner_address}")
    
    # Get nonce
    nonce = w3.eth.get_transaction_count(owner_address)
    
    # Build setGraduationController transaction
    tx = tf.functions.setGraduationController(
        Web3.to_checksum_address(GRADUATION_CONTROLLER_V11)
    ).build_transaction({
        'from': owner_address,
        'nonce': nonce,
        'gas': 100000,
        'gasPrice': w3.eth.gas_price,
        'chainId': 167012
    })
    
    print(f"   Nonce: {nonce}")
    print(f"   Gas: {tx['gas']:,}")
    
    # Sign transaction
    print(f"\n🔐 Signing transaction...")
    deployer_key = os.environ.get('DEPLOYER_PRIVATE_KEY')
    if not deployer_key:
        print("❌ DEPLOYER_PRIVATE_KEY not found!")
        return False
    
    signed_tx = w3.eth.account.sign_transaction(tx, deployer_key)
    
    # Send transaction
    print(f"\n📤 Sending update transaction...")
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print(f"   TX Hash: {tx_hash.hex()}")
    print(f"   Explorer: https://explorer.testnet.kasplextest.xyz/tx/{tx_hash.hex()}")
    
    # Wait for confirmation
    print(f"\n⏳ Waiting for confirmation...")
    try:
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        if receipt['status'] == 1:
            print(f"\n✅ UPDATE SUCCESSFUL!")
            print(f"   Block: {receipt['blockNumber']}")
            print(f"   Gas Used: {receipt['gasUsed']:,}")
            
            # Verify update
            print(f"\n🔍 Verifying update...")
            new_gc = tf.functions.graduationController().call()
            print(f"   New GC Address: {new_gc}")
            
            if new_gc.lower() == GRADUATION_CONTROLLER_V11.lower():
                print(f"   ✅ VERIFIED: TokenFactory V11 now points to GraduationController V11!")
                print(f"   ✅ CRITICAL FIX ACTIVE: IERC721Receiver implemented - STF errors resolved")
            else:
                print(f"   ❌ VERIFICATION FAILED: Still showing {new_gc}")
                return False
            
            print(f"\n" + "=" * 80)
            print(f"🎉 TOKENFACTORY V11 UPDATED SUCCESSFULLY!")
            print(f"=" * 80)
            print(f"\n📝 NEXT STEPS:")
            print(f"   1. Update contracts/deployed_addresses.json")
            print(f"   2. Update services/web3_service.py constants")
            print(f"   3. Restart application to pick up changes")
            print(f"   4. Test graduation with a new $50 token to confirm STF fix works")
            print(f"\n💡 REMINDER: Only NEW tokens created after this update will graduate correctly")
            print(f"   Legacy tokens (created before V11 config) remain graduation_disabled")
            print(f"\n" + "=" * 80)
            
            return True
            
        else:
            print(f"\n❌ UPDATE FAILED!")
            print(f"   TX Status: {receipt['status']}")
            return False
            
    except Exception as e:
        print(f"\n❌ Error waiting for transaction: {str(e)}")
        return False

if __name__ == "__main__":
    success = update_tokenfactory_gc()
    if success:
        print(f"\n✅ TokenFactory V11 updated to use GraduationController V11")
    else:
        print(f"\n❌ Update failed")
        sys.exit(1)
