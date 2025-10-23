#!/usr/bin/env python3
"""
Simple script to check SPK's on-chain graduation status
"""

import os
from web3 import Web3
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Database connection
DATABASE_URL = os.environ.get('DATABASE_URL')
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

# Web3 setup
RPC_URL = "https://rpc.kasplextest.xyz"
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Contract ABIs (minimal)
BONDING_POOL_ABI = [
    {"inputs": [], "name": "graduating", "outputs": [{"type": "bool"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "liquidityTransferred", "outputs": [{"type": "bool"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "virtualKasReserve", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"}
]

GRAD_CONTROLLER_ABI = [
    {
        "inputs": [{"type": "address", "name": "tokenAddress"}],
        "name": "getGraduationInfo",
        "outputs": [
            {"type": "bool", "name": "hasInitiated"},
            {"type": "uint256", "name": "kasAmount"},
            {"type": "uint256", "name": "tokenAmount"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]

GRAD_CONTROLLER_ADDRESS = "0x9416D5a5D61ec70C18D1FE1039f8026E29b4820e"

def main():
    # Get SPK from database
    result = session.execute("SELECT id, symbol, contract_address, graduation_status, is_graduated FROM token WHERE symbol = 'SPK'")
    spk = result.fetchone()
    
    if not spk:
        print("❌ SPK not found")
        return
    
    token_id, symbol, contract_address, grad_status, is_graduated = spk
    
    print(f"\n📊 SPK Token Status Check")
    print(f"=" * 60)
    print(f"Database ID: {token_id}")
    print(f"Contract: {contract_address}")
    print(f"DB Graduation Status: {grad_status}")
    print(f"DB is_graduated: {is_graduated}")
    
    # Check BondingCurvePool
    pool_contract = w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=BONDING_POOL_ABI)
    
    graduating = pool_contract.functions.graduating().call()
    liquid_transferred = pool_contract.functions.liquidityTransferred().call()
    kas_reserve = pool_contract.functions.virtualKasReserve().call()
    
    print(f"\n🔗 BondingCurvePool On-Chain State:")
    print(f"  graduating: {graduating}")
    print(f"  liquidityTransferred: {liquid_transferred}")
    print(f"  virtualKasReserve: {w3.from_wei(kas_reserve, 'ether')} KAS")
    
    # Check GraduationController
    grad_controller = w3.eth.contract(address=GRAD_CONTROLLER_ADDRESS, abi=GRAD_CONTROLLER_ABI)
    grad_info = grad_controller.functions.getGraduationInfo(Web3.to_checksum_address(contract_address)).call()
    
    has_initiated, kas_amount, token_amount = grad_info
    
    print(f"\n🎓 GraduationController On-Chain State:")
    print(f"  hasInitiated: {has_initiated}")
    print(f"  kasAmount: {w3.from_wei(kas_amount, 'ether')} KAS")
    print(f"  tokenAmount: {w3.from_wei(token_amount, 'ether')} tokens")
    
    # Analysis
    print(f"\n🔍 Analysis:")
    print(f"=" * 60)
    
    if graduating and has_initiated:
        print(f"✅ LEGITIMATE GRADUATION IN PROGRESS")
        print(f"   Status: Token correctly initiated and ready to complete")
        print(f"   Action: Should be status='initiating' in DB, not 'failed'")
        print(f"\n💡 This token hit $50 USD when KAS price was higher.")
        print(f"   Market cap threshold is only checked at INITIATION, not COMPLETION!")
        print(f"\n🔧 FIX NEEDED: UPDATE token SET graduation_status='initiating' WHERE id={token_id};")
    elif graduating and not has_initiated:
        print(f"❌ STUCK FROM V1→V2 MIGRATION")
        print(f"   Status: Token stuck between contract versions")
        print(f"   Action: Correctly marked as 'failed'")
    else:
        print(f"⚠️ Unexpected state")

if __name__ == '__main__':
    main()
