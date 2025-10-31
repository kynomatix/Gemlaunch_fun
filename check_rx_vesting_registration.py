#!/usr/bin/env python3
"""
Check if RoninX (RX) vesting contracts are registered in BondingCurvePool
"""

import logging
from services.web3_service import Web3Service

logging.basicConfig(level=logging.INFO)

def check_vesting_registration():
    """Check if vesting contracts are registered in BondingCurvePool"""
    
    # Initialize Web3 service
    web3_service = Web3Service()
    
    # RX Token addresses (from database query)
    pool_address = "0xbf16c193784146cb57541f2f7eec0e82d127568b"
    marketing_vesting = "0xbddf802836f0572cc463c9306241f17a9f4a806a"
    team_vesting = "0x3dc1a3c44ee6bf720eee6181bbb07ac77eb9c2fc"
    airdrop_vesting = "0xc4b2e6b7d64f6af2685ee7204cc5b76ffd0a0a5a"
    
    print("\n" + "="*80)
    print("RoninX (RX) Vesting Contract Registration Check")
    print("="*80)
    print(f"\nBondingCurvePool: {pool_address}")
    print(f"Marketing Vesting: {marketing_vesting}")
    print(f"Team Vesting: {team_vesting}")
    print(f"Airdrop Vesting: {airdrop_vesting}")
    print("\n" + "-"*80)
    
    # Get BondingCurvePool contract instance
    pool_contract = web3_service.get_bonding_pool_contract(pool_address)
    
    # Check marketing vesting contract
    print("\nChecking Marketing Vesting Contract...")
    try:
        is_marketing_registered = pool_contract.functions.isVestingContract(
            web3_service.w3.to_checksum_address(marketing_vesting)
        ).call()
        print(f"  ✓ isVestingContract(marketing): {is_marketing_registered}")
    except Exception as e:
        print(f"  ✗ Error checking marketing vesting: {e}")
        is_marketing_registered = None
    
    # Check team vesting contract
    print("\nChecking Team Vesting Contract...")
    try:
        is_team_registered = pool_contract.functions.isVestingContract(
            web3_service.w3.to_checksum_address(team_vesting)
        ).call()
        print(f"  ✓ isVestingContract(team): {is_team_registered}")
    except Exception as e:
        print(f"  ✗ Error checking team vesting: {e}")
        is_team_registered = None
    
    # Check airdrop vesting contract (optional - might not exist yet)
    print("\nChecking Airdrop Vesting Contract...")
    try:
        is_airdrop_registered = pool_contract.functions.isVestingContract(
            web3_service.w3.to_checksum_address(airdrop_vesting)
        ).call()
        print(f"  ✓ isVestingContract(airdrop): {is_airdrop_registered}")
    except Exception as e:
        print(f"  ✗ Error checking airdrop vesting: {e}")
        is_airdrop_registered = None
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    if is_marketing_registered and is_team_registered:
        print("\n✅ PASS: All vesting contracts are properly registered")
        print("   The 10% wallet cap exemption should work correctly.")
    else:
        print("\n❌ FAIL: Vesting contracts are NOT registered")
        print("   This is the bug causing the 10% wallet cap issue!")
        print("\n   Expected: Both should return True")
        print(f"   Actual: Marketing={is_marketing_registered}, Team={is_team_registered}")
        print("\n   Impact: Vesting contracts will be blocked by the 10% wallet cap")
        print("          when they try to receive reserved tokens during deployment.")
    
    if is_airdrop_registered is not None:
        if is_airdrop_registered:
            print(f"\n   Airdrop vesting is also registered: {is_airdrop_registered}")
        else:
            print(f"\n   Note: Airdrop vesting is not registered: {is_airdrop_registered}")
    
    print("\n" + "="*80)
    
    return {
        'marketing': is_marketing_registered,
        'team': is_team_registered,
        'airdrop': is_airdrop_registered
    }

if __name__ == "__main__":
    check_vesting_registration()
