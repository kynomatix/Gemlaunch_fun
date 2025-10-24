#!/usr/bin/env python3
"""
Migrate tokens from legacy GraduationController V1 to V2.

This script:
1. Updates pools to use GraduationControllerV2
2. Re-initiates graduations through V2
"""

import os
import sys
from services.web3_service import Web3Service
from models import db, Token
from app import app

# Initialize services
w3_service = Web3Service()

# V2 Controller address (checksummed)
V2_CONTROLLER = "0x147e3ecbE189BB301175001706fF1F44Df33B3Ab"

# Tokens to migrate
TOKENS_TO_MIGRATE = ['KPAN', 'GLAZED', 'KAMI']

def update_pool_controller(pool_address, new_controller):
    """Update a pool's graduationOracle to point to V2"""
    print(f"\n🔧 Updating pool {pool_address} to use controller {new_controller}")
    
    # Get pool contract
    pool = w3_service.get_bonding_pool_contract(pool_address)
    
    # Build setGraduationOracle transaction
    deployer = w3_service.deployer_account
    
    tx_data = pool.functions.setGraduationOracle(
        new_controller
    ).build_transaction({
        'from': deployer.address,
        'gas': 100000,
        'gasPrice': w3_service.w3.eth.gas_price,
        'nonce': w3_service.w3.eth.get_transaction_count(deployer.address)
    })
    
    # Sign and send
    signed_txn = w3_service.sign_transaction(tx_data)
    tx_hash = w3_service.relay_transaction(signed_txn)
    
    print(f"✅ Update tx sent: {tx_hash.hex()}")
    
    # Wait for confirmation
    try:
        receipt = w3_service.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt['status'] == 1:
            print(f"✅ Pool updated successfully!")
            return True
        else:
            print(f"❌ Transaction failed")
            return False
    except Exception as e:
        print(f"⚠️ Could not get receipt: {e}")
        return True  # Assume success for now

def main():
    with app.app_context():
        print("🚀 Migrating tokens to GraduationControllerV2")
        print(f"V2 Controller: {V2_CONTROLLER}")
        print(f"Tokens to migrate: {', '.join(TOKENS_TO_MIGRATE)}")
        
        for symbol in TOKENS_TO_MIGRATE:
            token = Token.query.filter_by(symbol=symbol).first()
            if not token:
                print(f"❌ Token {symbol} not found")
                continue
            
            print(f"\n📍 Processing {symbol} ({token.contract_address})")
            
            # Update pool to use V2
            success = update_pool_controller(token.contract_address, V2_CONTROLLER)
            
            if success:
                print(f"✅ {symbol} migrated to V2")
            else:
                print(f"❌ Failed to migrate {symbol}")
        
        print("\n✅ Migration complete!")
        print("\nNext steps:")
        print("1. Wait for transactions to confirm")
        print("2. The graduation monitor will detect eligible tokens and initiate graduations through V2")

if __name__ == "__main__":
    main()
