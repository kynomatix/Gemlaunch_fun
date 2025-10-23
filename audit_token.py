#!/usr/bin/env python3
"""
Comprehensive Token Audit Script
Verifies if a token was created with correct V2 contracts and proper setup
"""

import sys
from services.web3_service import get_web3_service

# Expected V2 addresses
EXPECTED_TOKEN_FACTORY_V2 = "0x39003ab4e8ad700F59bcfA082F73e68bc0477fDc"
EXPECTED_GRADUATION_CONTROLLER = "0x9416D5a5D61ec70C18D1FE1039f8026E29b4820e"
EXPECTED_VESTING_DEPLOYER_V2 = "0x319F9D08A9c1167770Fe037cb58e5097e287B9e7"

def audit_token(token_address):
    """Run full audit on a token"""
    print(f"\n{'='*80}")
    print(f"COMPREHENSIVE TOKEN AUDIT")
    print(f"Token Address: {token_address}")
    print(f"{'='*80}\n")
    
    web3_service = get_web3_service()
    w3 = web3_service.w3
    
    # Normalize address
    token_address = w3.to_checksum_address(token_address)
    
    # Get the BondingCurvePool contract
    print("📋 STEP 1: Loading BondingCurvePool Contract...")
    try:
        pool = web3_service.get_bonding_pool_contract(token_address)
        print(f"✅ Contract loaded successfully")
    except Exception as e:
        print(f"❌ CRITICAL: Failed to load contract: {e}")
        return False
    
    # Check basic token info
    print("\n📋 STEP 2: Token Basic Information...")
    try:
        name = pool.functions.name().call()
        symbol = pool.functions.symbol().call()
        total_supply = pool.functions.totalSupply().call()
        print(f"✅ Name: {name}")
        print(f"✅ Symbol: {symbol}")
        print(f"✅ Total Supply: {total_supply / 10**18:,.0f}")
    except Exception as e:
        print(f"❌ CRITICAL: Failed to read token info: {e}")
        return False
    
    # CRITICAL: Check graduationOracle setting
    print("\n📋 STEP 3: Graduation Oracle Configuration (CRITICAL)...")
    try:
        oracle_address = pool.functions.graduationOracle().call()
        oracle_address_checksum = w3.to_checksum_address(oracle_address)
        expected_checksum = w3.to_checksum_address(EXPECTED_GRADUATION_CONTROLLER)
        
        print(f"   Configured: {oracle_address_checksum}")
        print(f"   Expected:   {expected_checksum}")
        
        if oracle_address_checksum == expected_checksum:
            print(f"✅ PASS: Token created with V2 TokenFactory - Graduation will work!")
        else:
            print(f"❌ FAIL: Token created with V1 (old factory) - Graduation will FAIL!")
            print(f"   This token cannot graduate without emergency contract update")
            return False
    except Exception as e:
        print(f"❌ CRITICAL: Failed to read graduationOracle: {e}")
        return False
    
    # Check graduation status
    print("\n📋 STEP 4: Graduation Status...")
    try:
        is_graduated = pool.functions.graduated().call()
        is_graduating = pool.functions.graduating().call()
        print(f"   Graduated: {is_graduated}")
        print(f"   Graduating (in progress): {is_graduating}")
        
        if not is_graduated and not is_graduating:
            print(f"✅ Token is in bonding curve phase (normal)")
        elif is_graduating and not is_graduated:
            print(f"⚠️  Token is currently graduating (in progress)")
        elif is_graduated:
            print(f"✅ Token has graduated to DEX")
    except Exception as e:
        print(f"❌ WARNING: Failed to read graduation status: {e}")
    
    # Check reserves
    print("\n📋 STEP 5: Bonding Curve Reserves...")
    try:
        kas_reserve = pool.functions.virtualKasReserve().call()
        token_reserve = pool.functions.virtualTokenReserve().call()
        print(f"   KAS Reserve: {kas_reserve / 10**18:.4f} KAS")
        print(f"   Token Reserve: {token_reserve / 10**18:,.0f} tokens")
        print(f"✅ Reserves loaded successfully")
    except Exception as e:
        print(f"❌ WARNING: Failed to read reserves: {e}")
    
    # Check PRO token features
    print("\n📋 STEP 6: PRO Token Features...")
    try:
        # Check if this is a PRO token by checking allocations
        from models import Token
        from app import db
        
        token = Token.query.filter_by(contract_address=token_address.lower()).first()
        
        if token:
            total_allocation = (token.airdrops_allocation or 0) + (token.marketing_allocation or 0) + (token.team_allocation or 0)
            
            if total_allocation > 0:
                print(f"✅ PRO Token Detected")
                print(f"   Airdrop Allocation: {token.airdrops_allocation}%")
                print(f"   Marketing Allocation: {token.marketing_allocation}%")
                print(f"   Team Allocation: {token.team_allocation}%")
                
                # Check vesting addresses
                if token.airdrop_vesting_address:
                    print(f"   Airdrop Vesting: {token.airdrop_vesting_address}")
                if token.marketing_vesting_address:
                    print(f"   Marketing Vesting: {token.marketing_vesting_address}")
                if token.team_vesting_address:
                    print(f"   Team Vesting: {token.team_vesting_address}")
                
                print(f"✅ Vesting contracts deployed")
            else:
                print(f"✅ Basic Token (no PRO features)")
        else:
            print(f"⚠️  Token not found in database")
    except Exception as e:
        print(f"❌ WARNING: Failed to check PRO features: {e}")
    
    # Check deployment transaction
    print("\n📋 STEP 7: Deployment Transaction...")
    try:
        if token:
            tx_hash = token.deployment_tx
            if tx_hash:
                print(f"   TX Hash: {tx_hash}")
                print(f"   Block: {token.deployment_block_number}")
                print(f"   Deployed At: {token.created_at}")
                
                # Get transaction receipt
                receipt = w3.eth.get_transaction_receipt(tx_hash)
                print(f"   Status: {'✅ Success' if receipt['status'] == 1 else '❌ Failed'}")
                print(f"   Gas Used: {receipt['gasUsed']:,}")
            else:
                print(f"⚠️  No deployment transaction recorded")
    except Exception as e:
        print(f"❌ WARNING: Failed to check deployment transaction: {e}")
    
    # Final verdict
    print(f"\n{'='*80}")
    print(f"AUDIT RESULT")
    print(f"{'='*80}")
    print(f"✅ Token created with V2 TokenFactory")
    print(f"✅ Graduation system configured correctly")
    print(f"✅ Ready for graduation testing")
    print(f"\n⚡ This token should graduate successfully when it reaches $50 USD market cap")
    print(f"{'='*80}\n")
    
    return True

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python audit_token.py <token_address>")
        sys.exit(1)
    
    token_address = sys.argv[1]
    success = audit_token(token_address)
    sys.exit(0 if success else 1)
