#!/usr/bin/env python3
"""
Verify which GraduationController version a token is using
"""

import sys
from web3 import Web3

sys.path.insert(0, '/home/runner/workspace')
from services.web3_service import get_web3_service

def verify_token(token_address):
    """Verify token contract version"""
    
    w3_service = get_web3_service()
    
    print("=" * 80)
    print(f"TOKEN CONTRACT VERIFICATION")
    print("=" * 80)
    
    # Get token contract
    pool = w3_service.get_bonding_pool_contract(token_address)
    
    # Get basic info
    name = pool.functions.name().call()
    symbol = pool.functions.symbol().call()
    gc_address = pool.functions.graduationController().call()
    
    print(f"\nToken Details:")
    print(f"   Name: {name}")
    print(f"   Symbol: ${symbol}")
    print(f"   Address: {token_address}")
    
    print(f"\nContract Version Check:")
    print(f"   GraduationController: {gc_address}")
    print(f"   Expected V10: 0x7384F95729Ff5c2B2BFe4Cc101139a13A85a66e9")
    
    is_v10 = gc_address.lower() == "0x7384F95729Ff5c2B2BFe4Cc101139a13A85a66e9".lower()
    
    print(f"\n" + "=" * 80)
    if is_v10:
        print(f"✅ VERIFIED: Using LATEST V10 contracts!")
        print(f"=" * 80)
        print(f"\nWhat this means:")
        print(f"   ✅ Has STF fix applied (approvals before pool creation)")
        print(f"   ✅ Will graduate successfully at $50 market cap")
        print(f"   ✅ Ready for production testing")
        print(f"\nNext Steps:")
        print(f"   1. Buy this token up to $50 market cap")
        print(f"   2. Monitor graduation process")
        print(f"   3. Verify successful DEX deployment")
    else:
        print(f"❌ WARNING: Using OLD contract version!")
        print(f"=" * 80)
        print(f"\nIssues:")
        print(f"   ❌ Does NOT have STF fix")
        print(f"   ❌ Will encounter 'execution reverted: STF' error")
        print(f"   ❌ Cannot graduate successfully")
        print(f"\nRecommendation:")
        print(f"   Create a new token to use V10 contracts")
    
    print(f"\n" + "=" * 80)
    return is_v10

if __name__ == "__main__":
    token_address = sys.argv[1] if len(sys.argv) > 1 else "0x4c54aB0B2cFF4D05AeB8efAF1d5E8d4436953D1E"
    verify_token(token_address)
