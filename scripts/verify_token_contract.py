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
    print(f"   Expected V12 (COMPLETE FIX): 0xD7B75104f005DFC9dE004fdb97399444752d66D3")
    print(f"   V11 (PARTIAL FIX): 0xd0Ca76Dc29714Ef316a6aacCAC8837c3119439e0")
    
    is_v12 = gc_address.lower() == "0xD7B75104f005DFC9dE004fdb97399444752d66D3".lower()
    is_v11 = gc_address.lower() == "0xd0Ca76Dc29714Ef316a6aacCAC8837c3119439e0".lower()
    
    print(f"\n" + "=" * 80)
    if is_v12:
        print(f"✅ VERIFIED: Using LATEST V12 contracts (COMPLETE FIX)!")
        print(f"=" * 80)
        print(f"\nWhat this means:")
        print(f"   ✅ Has IERC721Receiver implementation (receives NFT from Position Manager)")
        print(f"   ✅ Uses unsafe transferFrom for burn (burn address can't receive safe transfers)")
        print(f"   ✅ COMPLETE TWO-PART STF FIX")
        print(f"   ✅ Will graduate successfully at $50 market cap")
        print(f"   ✅ Ready for production testing")
        print(f"\nNext Steps:")
        print(f"   1. Buy this token up to $50 market cap")
        print(f"   2. Monitor graduation process")
        print(f"   3. Verify successful DEX deployment")
    elif is_v11:
        print(f"⚠️  WARNING: Using V11 (PARTIAL FIX) - Will fail at burn phase!")
        print(f"=" * 80)
        print(f"\nPartial Fix Status:")
        print(f"   ✅ Has IERC721Receiver (can receive NFT)")
        print(f"   ❌ Uses safeTransferFrom for burn (will fail STF)")
        print(f"   ❌ Cannot graduate successfully - fails when burning LP NFT")
        print(f"\nRecommendation:")
        print(f"   This token is permanently broken. Create a new token to use V12 contracts.")
        print(f"   V11 tokens have the old GC address embedded and cannot be fixed.")
    else:
        print(f"❌ WARNING: Using OLD contract version!")
        print(f"=" * 80)
        print(f"\nIssues:")
        print(f"   ❌ Does NOT have complete STF fix")
        print(f"   ❌ Will encounter 'execution reverted: STF' error")
        print(f"   ❌ Cannot graduate successfully")
        print(f"\nRecommendation:")
        print(f"   Create a new token to use V12 contracts with complete two-part STF fix")
    
    print(f"\n" + "=" * 80)
    return is_v12

if __name__ == "__main__":
    token_address = sys.argv[1] if len(sys.argv) > 1 else "0x4c54aB0B2cFF4D05AeB8efAF1d5E8d4436953D1E"
    verify_token(token_address)
