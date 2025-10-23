#!/usr/bin/env python3
"""
Manual graduation completion script for SPK token
SPK is stuck with graduating=True on-chain but active in database
"""

import sys
import logging
from app import app, db
from models import Token
from services.web3_service import get_web3_service
from services.graduation_completion_service import GraduationCompletionService
from services.graduation_state_manager import GraduationStateManager

logging.basicConfig(level=logging.INFO)

def main():
    """Complete SPK graduation manually"""
    with app.app_context():
        # Find SPK token
        pool_address = "0x8cf7c793978eadbdebec88e548c1377b6ecd120c"
        token = Token.query.filter(db.func.lower(Token.contract_address) == pool_address.lower()).first()
        
        if not token:
            print(f"❌ Token not found: {pool_address}")
            return 1
        
        print(f"\n📊 SPK Token Status:")
        print(f"  ID: {token.id}")
        print(f"  Name: {token.name} ({token.symbol})")
        print(f"  Database graduation_status: {token.graduation_status}")
        
        # Check on-chain status
        w3_service = get_web3_service()
        pool = w3_service.get_bonding_pool_contract(pool_address)
        
        graduated = pool.functions.graduated().call()
        graduating = pool.functions.graduating().call()
        liquid_transferred = pool.functions.liquidityTransferred().call()
        
        print(f"\n⛓️  On-Chain BondingCurvePool Status:")
        print(f"  graduated: {graduated}")
        print(f"  graduating: {graduating}")
        print(f"  liquidityTransferred: {liquid_transferred}")
        
        # Check GraduationController
        try:
            graduation_controller = w3_service.contracts['GraduationController']
            checksum_address = w3_service.w3.to_checksum_address(pool_address)
            grad_info = graduation_controller.functions.getGraduationInfo(checksum_address).call()
            has_initiated = grad_info[0]
            kas_deposited = grad_info[1]
            
            print(f"\n⛓️  On-Chain GraduationController Status:")
            print(f"  hasInitiated: {has_initiated}")
            print(f"  kasDeposited: {kas_deposited}")
        except Exception as e:
            print(f"\n❌ Error checking GraduationController: {e}")
            has_initiated = False
        
        # Diagnose the issue
        print(f"\n🔍 Diagnosis:")
        if graduating and not graduated:
            print(f"  ❌ Token stuck in graduating state on BondingCurvePool")
            print(f"  ❌ All trading is blocked")
            
            if has_initiated:
                print(f"  ✅ GraduationController has initiation record")
                print(f"  💡 Solution: Complete the graduation")
            else:
                print(f"  ❌ GraduationController has NO initiation record")
                print(f"  💡 This is the V2 contract redeployment issue")
                print(f"  ⚠️  Cannot complete graduation - need to re-initiate")
                return 1
        
        # Ask for confirmation
        print(f"\n⚠️  This will complete SPK's graduation and create a DEX pool on Kaspa Finance")
        response = input("Continue? (yes/no): ").strip().lower()
        
        if response != 'yes':
            print("❌ Aborted by user")
            return 1
        
        # Update database status to 'initiating' so completion service can pick it up
        print(f"\n🔄 Updating database status to 'initiating'...")
        token.graduation_status = 'initiating'
        db.session.commit()
        
        # Manually trigger completion
        print(f"\n🚀 Triggering graduation completion...")
        completion_service = GraduationCompletionService(app)
        
        try:
            completion_service._complete_single_graduation(token)
            
            # Refresh token from database
            db.session.refresh(token)
            
            print(f"\n✅ Graduation completion attempted!")
            print(f"  New database status: {token.graduation_status}")
            print(f"  DEX pool address: {token.dex_pool_address if hasattr(token, 'dex_pool_address') else 'N/A'}")
            
            # Verify on-chain
            graduated_now = pool.functions.graduated().call()
            graduating_now = pool.functions.graduating().call()
            
            print(f"\n⛓️  Updated On-Chain Status:")
            print(f"  graduated: {graduated_now}")
            print(f"  graduating: {graduating_now}")
            
            if graduated_now and not graduating_now:
                print(f"\n🎉 SUCCESS! SPK has graduated and trading is now available on Kaspa Finance DEX")
                return 0
            else:
                print(f"\n⚠️  Completion may have failed - check logs")
                return 1
                
        except Exception as e:
            print(f"\n❌ Error during completion: {e}")
            import traceback
            traceback.print_exc()
            return 1

if __name__ == '__main__':
    sys.exit(main())
