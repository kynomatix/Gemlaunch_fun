#!/usr/bin/env python3
"""
Check SPK's on-chain graduation status to determine if it's legitimately graduating
"""

import sys
sys.path.insert(0, '.')

from app import app
from services.web3_service import get_web3_service
from models import Token

def check_spk_status():
    """Check SPK's on-chain status"""
    with app.app_context():
        # Get SPK token
        spk = Token.query.filter_by(symbol='SPK').first()
        
        if not spk:
            print("❌ SPK token not found in database")
            return
        
        print(f"\n📊 SPK Token Status Check")
        print(f"=" * 60)
        print(f"Database ID: {spk.id}")
        print(f"Symbol: {spk.symbol}")
        print(f"Contract: {spk.contract_address}")
        print(f"DB Graduation Status: {spk.graduation_status}")
        print(f"DB is_graduated: {spk.is_graduated}")
        
        # Get web3 service
        w3_service = get_web3_service()
        
        # Check BondingCurvePool state
        pool = w3_service.get_bonding_pool_contract(spk.contract_address)
        
        graduating = pool.functions.graduating().call()
        liquid_transferred = pool.functions.liquidityTransferred().call()
        kas_reserve = pool.functions.virtualKasReserve().call()
        
        print(f"\n🔗 BondingCurvePool On-Chain State:")
        print(f"  graduating: {graduating}")
        print(f"  liquidityTransferred: {liquid_transferred}")
        print(f"  virtualKasReserve: {w3_service.w3.from_wei(kas_reserve, 'ether')} KAS")
        
        # Check GraduationController state
        grad_controller = w3_service.contracts['GraduationController']
        grad_info = grad_controller.functions.getGraduationInfo(spk.contract_address).call()
        
        has_initiated = grad_info[0]
        kas_amount = grad_info[1] if len(grad_info) > 1 else 0
        token_amount = grad_info[2] if len(grad_info) > 2 else 0
        
        print(f"\n🎓 GraduationController On-Chain State:")
        print(f"  hasInitiated: {has_initiated}")
        print(f"  kasAmount: {w3_service.w3.from_wei(kas_amount, 'ether')} KAS")
        print(f"  tokenAmount: {w3_service.w3.from_wei(token_amount, 'ether')} tokens")
        
        # Determine correct status
        print(f"\n🔍 Analysis:")
        print(f"=" * 60)
        
        if graduating and has_initiated:
            print(f"✅ LEGITIMATE GRADUATION IN PROGRESS")
            print(f"   - BondingCurvePool: graduating={graduating}")
            print(f"   - GraduationController: hasInitiated={has_initiated}")
            print(f"   - Status: Token correctly initiated and ready to complete")
            print(f"   - Action: Should be status='initiating' in DB, not 'failed'")
            print(f"\n💡 This token hit $50 USD when KAS price was higher.")
            print(f"   KAS price dropped, so market cap now appears below $50.")
            print(f"   But graduation should COMPLETE regardless of current price!")
        elif graduating and not has_initiated:
            print(f"❌ STUCK FROM V1→V2 MIGRATION")
            print(f"   - BondingCurvePool: graduating={graduating}")  
            print(f"   - GraduationController: hasInitiated={has_initiated}")
            print(f"   - Status: Token stuck between contract versions")
            print(f"   - Action: Correctly marked as 'failed'")
        elif not graduating:
            print(f"⚠️ NOT GRADUATING")
            print(f"   - BondingCurvePool: graduating={graduating}")
            print(f"   - Status: Token not in graduation state")
        else:
            print(f"🤔 UNEXPECTED STATE")

if __name__ == '__main__':
    check_spk_status()
