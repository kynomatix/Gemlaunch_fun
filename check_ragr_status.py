"""
Check RAGR Token Graduation Readiness
Verify market cap and graduation state
"""

from app import app, db
from models import Token
from services.web3_service import get_web3_service
from decimal import Decimal

def main():
    w3_service = get_web3_service()
    ragr_address = "0xa75c9441ba642165df45fbcdb03b5627521ecb7a"
    
    print("=" * 80)
    print("RAGR TOKEN GRADUATION READINESS CHECK")
    print("=" * 80)
    print()
    
    with app.app_context():
        # Get token from database
        token = Token.query.filter_by(contract_address=ragr_address.lower()).first()
        
        if not token:
            print(f"❌ Token not found in database")
            return
        
        print(f"Token: {token.symbol} ({token.name})")
        print(f"Contract: {token.contract_address}")
        print(f"DB Status: {token.graduation_status}")
        print()
        
        # Check on-chain market cap
        try:
            pool_contract = w3_service.get_bonding_pool_contract(ragr_address)
            
            # Get virtual KAS reserve
            virtual_kas_reserve = pool_contract.functions.virtualKasReserve().call()
            virtual_kas_reserve_kas = Decimal(virtual_kas_reserve) / Decimal(10**18)
            
            print(f"Virtual KAS Reserve: {virtual_kas_reserve_kas} KAS")
            
            # Get KAS price in USD (assume 0.05198 per current data)
            kas_price_usd = Decimal("0.05198")
            market_cap_usd = virtual_kas_reserve_kas * kas_price_usd
            
            print(f"Market Cap: ${market_cap_usd:.2f} USD")
            print(f"Graduation Threshold: $50.00 USD")
            print()
            
            if market_cap_usd >= 50:
                print(f"✅ READY FOR GRADUATION (${market_cap_usd:.2f} >= $50.00)")
            else:
                print(f"❌ NOT READY (${market_cap_usd:.2f} < $50.00)")
                progress = (market_cap_usd / 50) * 100
                print(f"   Progress: {progress:.1f}%")
            
            print()
            
        except Exception as e:
            print(f"❌ Error checking on-chain data: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # Check if already graduated
        try:
            grad_controller = w3_service.contracts['GraduationController']
            has_graduated = grad_controller.functions.hasGraduated(
                w3_service.w3.to_checksum_address(ragr_address)
            ).call()
            
            print(f"On-chain hasGraduated: {has_graduated}")
            
            if has_graduated:
                print("⚠️ Token has already graduated on-chain!")
        except Exception as e:
            print(f"Error checking graduation status: {str(e)}")
        
        print()
        
        # Check BondingCurvePool graduating() status
        try:
            pool_contract = w3_service.get_bonding_pool_contract(ragr_address)
            graduating = pool_contract.functions.graduating().call()
            
            print(f"BondingCurvePool.graduating(): {graduating}")
            
            if graduating:
                print("✅ Token is in 'graduating' state - ready for completion!")
            else:
                print("⚠️ Token is NOT in 'graduating' state - needs initiation first")
        except Exception as e:
            print(f"Error checking graduating status: {str(e)}")

if __name__ == "__main__":
    main()
