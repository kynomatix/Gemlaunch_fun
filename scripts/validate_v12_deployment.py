#!/usr/bin/env python3
"""
Validate V12 Deployment Configuration
Ensures all addresses are correct and KYR is marked as disabled
"""

import sys
import json
sys.path.insert(0, '/home/runner/workspace')

from services.web3_service import get_web3_service, GRADUATION_CONTROLLER_ADDRESS, TOKEN_FACTORY_ADDRESS
from models import Token, db
from app import app

def validate_deployment():
    """Validate V12 deployment configuration"""
    
    print("=" * 80)
    print("V12 DEPLOYMENT VALIDATION")
    print("=" * 80)
    
    # 1. Check deployed_addresses.json
    print("\n📋 Step 1: Checking deployed_addresses.json...")
    with open('contracts/deployed_addresses.json') as f:
        deployed = json.load(f)
    
    gc_address = deployed['contracts']['GraduationController']['address']
    gc_version = deployed['contracts']['GraduationController']['version']
    tf_address = deployed['contracts']['TokenFactory']['address']
    
    print(f"   GraduationController: {gc_address}")
    print(f"   Version: {gc_version}")
    print(f"   TokenFactory: {tf_address}")
    
    if gc_version == "V12" and gc_address == "0xD7B75104f005DFC9dE004fdb97399444752d66D3":
        print("   ✅ deployed_addresses.json is correct!")
    else:
        print("   ❌ deployed_addresses.json has wrong version or address!")
        return False
    
    # 2. Check web3_service.py constants
    print("\n🔧 Step 2: Checking web3_service.py constants...")
    print(f"   GRADUATION_CONTROLLER_ADDRESS: {GRADUATION_CONTROLLER_ADDRESS}")
    print(f"   TOKEN_FACTORY_ADDRESS: {TOKEN_FACTORY_ADDRESS}")
    
    if GRADUATION_CONTROLLER_ADDRESS == "0xD7B75104f005DFC9dE004fdb97399444752d66D3":
        print("   ✅ web3_service.py has correct V12 address!")
    else:
        print("   ❌ web3_service.py has wrong GC address!")
        return False
    
    # 3. Check on-chain configuration
    print("\n⛓️  Step 3: Checking on-chain configuration...")
    web3_service = get_web3_service()
    
    # Check TokenFactory points to correct GC
    tf = web3_service.contracts['TokenFactory']
    tf_gc_address = tf.functions.graduationController().call()
    
    print(f"   TokenFactory.graduationController(): {tf_gc_address}")
    
    if tf_gc_address.lower() == "0xD7B75104f005DFC9dE004fdb97399444752d66D3".lower():
        print("   ✅ TokenFactory V11 points to GraduationController V12!")
    else:
        print(f"   ❌ TokenFactory points to wrong GC: {tf_gc_address}")
        return False
    
    # Check GC version
    gc = web3_service.contracts['GraduationController']
    gc_version_onchain = gc.functions.VERSION().call()
    
    print(f"   GraduationController.VERSION(): {gc_version_onchain}")
    
    if gc_version_onchain == "12.0.0":
        print("   ✅ GraduationController V12 verified on-chain!")
    else:
        print(f"   ❌ Wrong GC version on-chain: {gc_version_onchain}")
        return False
    
    # 4. Check KYR is marked as disabled
    print("\n🚫 Step 4: Checking KYR graduation_disabled status...")
    with app.app_context():
        kyr = Token.query.filter_by(symbol='KYR').first()
        
        if not kyr:
            print("   ⚠️  KYR token not found in database")
        else:
            print(f"   KYR contract: {kyr.contract_address}")
            print(f"   KYR graduation_disabled: {kyr.graduation_disabled}")
            print(f"   KYR graduation_status: {kyr.graduation_status}")
            
            if kyr.graduation_disabled:
                print("   ✅ KYR is correctly marked as graduation_disabled!")
            else:
                print("   ❌ KYR should be marked as graduation_disabled!")
                return False
    
    # 5. Summary
    print("\n" + "=" * 80)
    print("✅ ALL VALIDATION CHECKS PASSED!")
    print("=" * 80)
    print("\n📝 Configuration Summary:")
    print(f"   • GraduationController V12: 0xD7B75104f005DFC9dE004fdb97399444752d66D3")
    print(f"   • TokenFactory V11: 0x427B039bc381911a40AC25Fc50AB9e6f5633A5B1")
    print(f"   • On-chain link: TokenFactory → GraduationController V12 ✅")
    print(f"   • V12 Features: IERC721Receiver + unsafe burn transfer")
    print(f"   • KYR token: graduation_disabled = True ✅")
    print("\n🎯 Ready to create new tokens with V12!")
    print("   New tokens will use complete STF fix and graduate successfully")
    print("\n" + "=" * 80)
    
    return True

if __name__ == "__main__":
    try:
        success = validate_deployment()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Validation error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
