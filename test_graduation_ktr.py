"""
Test script to check KTR bonding pool state and diagnose graduation issue
"""

import logging
from services.web3_service import get_web3_service
from models import Token, db
from app import app

logging.basicConfig(level=logging.INFO)

def check_ktr_state():
    """Check KTR token's bonding pool state"""
    
    with app.app_context():
        # Get KTR token
        ktr = Token.query.filter_by(symbol='KTR').first()
        
        if not ktr:
            print("❌ KTR token not found in database")
            return
        
        print(f"\n=== KTR Token Database State ===")
        print(f"ID: {ktr.id}")
        print(f"Contract Address: {ktr.contract_address}")
        print(f"Graduation Status: {ktr.graduation_status}")
        print(f"Market Cap: ${ktr.current_market_cap}")
        print(f"KAS Reserve: {ktr.kas_reserve} KAS")
        print(f"Token Reserve: {ktr.token_reserve}")
        print(f"Is Graduated (legacy): {ktr.is_graduated}")
        print(f"Graduated At (legacy): {ktr.graduated_at}")
        print(f"Initiation TX: {ktr.graduation_initiation_tx}")
        print(f"Completion TX: {ktr.graduation_completion_tx}")
        print(f"DEX Pool Address: {ktr.dex_pool_address}")
        
        # Get web3 service
        w3_service = get_web3_service()
        
        # Get bonding pool contract
        pool_address = w3_service.w3.to_checksum_address(ktr.contract_address)
        pool = w3_service.get_bonding_pool_contract(pool_address)
        
        print(f"\n=== KTR Bonding Pool On-Chain State ===")
        
        # Check if pool is in graduating state
        try:
            graduating = pool.functions.graduating().call()
            print(f"Graduating: {graduating}")
        except Exception as e:
            print(f"❌ Error reading graduating state: {e}")
        
        # Check virtual reserves
        try:
            virtual_kas = pool.functions.virtualKasReserve().call()
            virtual_kas_ether = w3_service.w3.from_wei(virtual_kas, 'ether')
            print(f"Virtual KAS Reserve: {virtual_kas_ether} KAS ({virtual_kas} wei)")
        except Exception as e:
            print(f"❌ Error reading virtual KAS reserve: {e}")
        
        try:
            virtual_token = pool.functions.virtualTokenReserve().call()
            virtual_token_ether = w3_service.w3.from_wei(virtual_token, 'ether')
            print(f"Virtual Token Reserve: {virtual_token_ether} tokens ({virtual_token} wei)")
        except Exception as e:
            print(f"❌ Error reading virtual token reserve: {e}")
        
        # Check treasury KAS (real reserve)
        try:
            treasury_kas = w3_service.w3.eth.get_balance(pool_address)
            treasury_kas_ether = w3_service.w3.from_wei(treasury_kas, 'ether')
            print(f"Treasury KAS Balance: {treasury_kas_ether} KAS ({treasury_kas} wei)")
        except Exception as e:
            print(f"❌ Error reading treasury balance: {e}")
        
        # Check if initiation transaction succeeded
        if ktr.graduation_initiation_tx:
            print(f"\n=== Checking Initiation Transaction ===")
            try:
                tx_hash = ktr.graduation_initiation_tx
                if not tx_hash.startswith('0x'):
                    tx_hash = '0x' + tx_hash
                
                receipt = w3_service.w3.eth.get_transaction_receipt(tx_hash)
                print(f"Initiation TX Status: {'✅ SUCCESS' if receipt['status'] == 1 else '❌ FAILED'}")
                print(f"Block Number: {receipt['blockNumber']}")
                print(f"Gas Used: {receipt['gasUsed']}")
                
                # Decode logs
                if receipt['status'] == 1:
                    print("\nLooking for GraduationInitiated event...")
                    for log in receipt['logs']:
                        if log['address'].lower() == pool_address.lower():
                            print(f"  Log from bonding pool: {log['topics']}")
            
            except Exception as e:
                print(f"❌ Error checking initiation tx: {e}")

if __name__ == '__main__':
    check_ktr_state()
