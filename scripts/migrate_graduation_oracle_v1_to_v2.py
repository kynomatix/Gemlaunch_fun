#!/usr/bin/env python3
"""
Migration Script: Update graduationOracle from V1 to V2
=======================================================

Problem: Tokens deployed before Oct 23, 2025 have V1 controller address.
When V2 tries to graduate them, pools reject with "Only oracle can initiate"

Solution: Call setGraduationOracle(V2_ADDRESS) on each pool as owner.

Affected Tokens:
- KAMI (0x6544e6b092d06601ba9ca2d10bc275883e848db9) - 990 KAS, user's token
- SPK  (0x8cf7c793978eadbdebec88e548c1377b6ecd120c) - 990 KAS
- JAK  (0xbb8b6012f9d2000a5d87a64972f913e53117f9db) - 3,958 KAS
- RAGR (0xae2312b6ba6c58123555cb172d4313ff39655ff0) - 1,218 KAS
"""

import sys
import os
from web3 import Web3
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.web3_service import Web3Service

# Controller addresses
V1_CONTROLLER = "0x9416D5a5D61ec70C18D1FE1039f8026E29b4820e"  # OLD/DEPRECATED
V2_CONTROLLER = "0x147e3ecbe189bb301175001706ff1f44df33b3ab"  # NEW (Oct 23, 2025)

# Tokens needing migration
TOKENS_TO_MIGRATE = [
    {
        "symbol": "KAMI",
        "address": "0x6544e6b092d06601ba9ca2d10bc275883e848db9",
        "market_cap_kas": 990,
        "notes": "User's token - stuck at graduation"
    },
    {
        "symbol": "SPK",
        "address": "0x8cf7c793978eadbdebec88e548c1377b6ecd120c",
        "market_cap_kas": 990,
        "notes": "Stuck at graduation"
    },
    {
        "symbol": "JAK",
        "address": "0xbb8b6012f9d2000a5d87a64972f913e53117f9db",
        "market_cap_kas": 3958,
        "notes": "Stuck at graduation"
    },
    {
        "symbol": "RAGR",
        "address": "0xae2312b6ba6c58123555cb172d4313ff39655ff0",
        "market_cap_kas": 1218,
        "notes": "Stuck at graduation"
    }
]


def check_current_oracle(w3_service, token_address):
    """Check what graduationOracle a token currently has"""
    try:
        pool_abi = w3_service.contracts['BondingCurvePoolABI']
        pool = w3_service.w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=pool_abi
        )
        current_oracle = pool.functions.graduationOracle().call()
        return current_oracle
    except Exception as e:
        print(f"❌ Error checking oracle for {token_address}: {e}")
        return None


def update_graduation_oracle(w3_service, token_address, new_oracle):
    """Update graduationOracle to V2 address (requires owner signature)"""
    try:
        pool_abi = w3_service.contracts['BondingCurvePoolABI']
        pool = w3_service.w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=pool_abi
        )
        
        # Check owner
        owner = pool.functions.owner().call()
        deployer_address = w3_service.deployer_account.address
        
        if owner.lower() != deployer_address.lower():
            return {
                'success': False,
                'error': f'Not owner! Owner: {owner}, Deployer: {deployer_address}'
            }
        
        # Build transaction
        tx_data = pool.functions.setGraduationOracle(
            Web3.to_checksum_address(new_oracle)
        ).build_transaction({
            'from': deployer_address,
            'value': 0,
            'gas': 0,
            'gasPrice': w3_service.w3.eth.gas_price,
            'nonce': w3_service.w3.eth.get_transaction_count(deployer_address)
        })
        
        # Estimate gas
        try:
            estimated_gas = w3_service.w3.eth.estimate_gas(tx_data)
            tx_data['gas'] = int(estimated_gas * 1.2)  # 20% buffer
        except Exception as e:
            return {'success': False, 'error': f'Gas estimation failed: {str(e)}'}
        
        # Sign with deployer account (owner)
        signed_txn = w3_service.deployer_account.sign_transaction(tx_data)
        
        # Send transaction
        tx_hash = w3_service.w3.eth.send_raw_transaction(signed_txn.raw_transaction)
        
        # Wait for confirmation
        print(f"⏳ Waiting for confirmation... Tx: {tx_hash.hex()}")
        receipt = w3_service.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        if receipt['status'] == 1:
            return {
                'success': True,
                'tx_hash': tx_hash.hex(),
                'gas_used': receipt['gasUsed']
            }
        else:
            return {
                'success': False,
                'error': f'Transaction reverted. Tx: {tx_hash.hex()}'
            }
            
    except Exception as e:
        return {'success': False, 'error': str(e)}


def main():
    print("=" * 80)
    print("Graduation Oracle Migration: V1 → V2")
    print("=" * 80)
    print()
    
    # Initialize Web3Service
    print("🔌 Connecting to blockchain...")
    w3_service = Web3Service()
    
    if not w3_service.is_connected:
        print("❌ Failed to connect to blockchain!")
        return 1
    
    print(f"✅ Connected to blockchain")
    print()
    
    # Migration summary
    total_tokens = len(TOKENS_TO_MIGRATE)
    migrated = 0
    skipped = 0
    failed = 0
    
    print(f"📋 Migrating {total_tokens} tokens from V1 to V2 controller")
    print(f"   V1 (OLD): {V1_CONTROLLER}")
    print(f"   V2 (NEW): {V2_CONTROLLER}")
    print()
    
    for token in TOKENS_TO_MIGRATE:
        symbol = token['symbol']
        address = token['address']
        notes = token.get('notes', '')
        
        print(f"🔍 Checking {symbol} ({address})...")
        
        # Check current oracle
        current_oracle = check_current_oracle(w3_service, address)
        
        if current_oracle is None:
            print(f"   ❌ Failed to read current oracle")
            failed += 1
            continue
        
        print(f"   Current oracle: {current_oracle}")
        
        # Check if already migrated
        if current_oracle.lower() == V2_CONTROLLER.lower():
            print(f"   ✅ Already using V2 - skipping")
            skipped += 1
            continue
        
        # Verify it's currently V1
        if current_oracle.lower() != V1_CONTROLLER.lower():
            print(f"   ⚠️  Unexpected oracle address: {current_oracle}")
            print(f"   ❓ Skipping (manual review needed)")
            skipped += 1
            continue
        
        # Perform migration
        print(f"   🔄 Updating to V2...")
        result = update_graduation_oracle(w3_service, address, V2_CONTROLLER)
        
        if result['success']:
            print(f"   ✅ Migration successful!")
            print(f"      Tx: {result['tx_hash']}")
            print(f"      Gas: {result['gas_used']:,}")
            migrated += 1
        else:
            print(f"   ❌ Migration failed: {result['error']}")
            failed += 1
        
        print()
    
    # Summary
    print("=" * 80)
    print("MIGRATION SUMMARY")
    print("=" * 80)
    print(f"Total tokens:     {total_tokens}")
    print(f"✅ Migrated:      {migrated}")
    print(f"⏭️  Skipped:       {skipped}")
    print(f"❌ Failed:        {failed}")
    print()
    
    if migrated > 0:
        print("🎉 Migration complete! Affected tokens can now graduate with V2 controller.")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
