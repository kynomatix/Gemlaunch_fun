#!/usr/bin/env python3
"""
Deploy GraduationController V3 - FIXED VERSION
Clean deployment from audited source code (no stray bytecode)
"""

import sys
import os
import json
import time
from web3 import Web3

sys.path.insert(0, '/home/runner/workspace')
from services.web3_service import get_web3_service

def deploy_graduation_controller_v3():
    """Deploy clean GraduationController V3"""
    
    web3_service = get_web3_service()
    w3 = web3_service.w3
    
    print("=" * 80)
    print("🚀 DEPLOYING GRADUATIONCONTROLLER V3 (FIXED)")
    print("=" * 80)
    
    # Load GraduationController V3 artifact
    with open('artifacts/contracts/GraduationControllerV3.sol/GraduationControllerV3.json') as f:
        artifact = json.load(f)
        abi = artifact['abi']
        bytecode = artifact['bytecode']
    
    print(f"\n📋 Contract Info:")
    print(f"   Bytecode size: {len(bytecode) // 2} bytes")
    print(f"   Version: 3.0.0")
    
    # Configuration addresses (CORRECT Kaspa Finance addresses)
    KASPA_FINANCE_FACTORY = "0x1b72D7165a0D7256a4F197765C15bb70bC5D66A8"  # Kaspa Finance factory (FIXED)
    KASPA_FINANCE_POSITION_MANAGER = "0x4E25637cF39822364b877F81B18c5B6CF0eeF589"  # NFT Position Manager (FIXED)
    KASPA_FINANCE_WKAS = "0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94"  # Wrapped KAS
    GRADUATION_ORACLE = os.environ.get('ORACLE_ADDRESS', '0x5f837F62744D4d80Fc79C3A5346B4A228956914E')
    TOKEN_FACTORY = "0xf8F05F8c88Df82b3aA135b9D434553E064b56704"  # CORRECT TokenFactory V3 (FIXED)
    TREASURY = os.environ.get('DEPLOYER_ADDRESS', '0xe281e4776FB5De20817D0bbC72B0C4b955565619')
    
    print(f"\n🎯 Constructor Parameters:")
    print(f"   Kaspa Finance Factory: {KASPA_FINANCE_FACTORY}")
    print(f"   Position Manager: {KASPA_FINANCE_POSITION_MANAGER}")
    print(f"   WKAS: {KASPA_FINANCE_WKAS}")
    print(f"   Graduation Oracle: {GRADUATION_ORACLE}")
    print(f"   Token Factory: {TOKEN_FACTORY}")
    print(f"   Treasury: {TREASURY}")
    
    # Create contract instance
    GraduationController = w3.eth.contract(abi=abi, bytecode=bytecode)
    
    # Build constructor transaction
    constructor_args = [
        Web3.to_checksum_address(KASPA_FINANCE_FACTORY),
        Web3.to_checksum_address(KASPA_FINANCE_POSITION_MANAGER),
        Web3.to_checksum_address(KASPA_FINANCE_WKAS),
        Web3.to_checksum_address(GRADUATION_ORACLE),
        Web3.to_checksum_address(TOKEN_FACTORY),
        Web3.to_checksum_address(TREASURY)
    ]
    
    print(f"\n⛽ Estimating gas...")
    try:
        gas_estimate = GraduationController.constructor(*constructor_args).estimate_gas({
            'from': Web3.to_checksum_address(TREASURY)
        })
        print(f"   Gas estimate: {gas_estimate:,}")
    except Exception as e:
        print(f"   ⚠️ Gas estimation failed: {str(e)[:200]}")
        gas_estimate = 3000000  # Fallback
    
    # Build transaction
    deployer_address = Web3.to_checksum_address(TREASURY)
    nonce = w3.eth.get_transaction_count(deployer_address)
    
    # Get deployer private key
    deployer_key = os.environ.get('DEPLOYER_PRIVATE_KEY')
    if not deployer_key:
        print("❌ DEPLOYER_PRIVATE_KEY not found in environment!")
        return None
    
    tx = GraduationController.constructor(*constructor_args).build_transaction({
        'from': deployer_address,
        'nonce': nonce,
        'gas': gas_estimate + 100000,  # Add buffer
        'gasPrice': w3.eth.gas_price,
        'chainId': 167012
    })
    
    print(f"\n📝 Transaction Details:")
    print(f"   From: {deployer_address}")
    print(f"   Nonce: {nonce}")
    print(f"   Gas: {tx['gas']:,}")
    print(f"   Gas Price: {Web3.from_wei(tx['gasPrice'], 'gwei')} gwei")
    
    # Sign transaction
    print(f"\n🔐 Signing transaction...")
    signed_tx = w3.eth.account.sign_transaction(tx, deployer_key)
    
    # Send transaction
    print(f"\n📤 Sending deployment transaction...")
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print(f"   TX Hash: {tx_hash.hex()}")
    print(f"   Explorer: https://explorer.testnet.kasplextest.xyz/tx/{tx_hash.hex()}")
    
    # Wait for confirmation
    print(f"\n⏳ Waiting for confirmation...")
    try:
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        
        if receipt['status'] == 1:
            contract_address = receipt['contractAddress']
            print(f"\n✅ DEPLOYMENT SUCCESSFUL!")
            print(f"   Contract Address: {contract_address}")
            print(f"   Block: {receipt['blockNumber']}")
            print(f"   Gas Used: {receipt['gasUsed']:,}")
            
            # Verify configuration
            print(f"\n🔍 Verifying configuration...")
            gc = w3.eth.contract(address=contract_address, abi=abi)
            
            version = gc.functions.VERSION().call()
            treasury = gc.functions.treasury().call()
            oracle = gc.functions.graduationOracle().call()
            
            print(f"   ✅ VERSION: {version}")
            print(f"   ✅ Treasury: {treasury}")
            print(f"   ✅ Oracle: {oracle}")
            
            # Save deployment info
            deployment_info = {
                "address": contract_address,
                "txHash": tx_hash.hex(),
                "blockNumber": receipt['blockNumber'],
                "gasUsed": receipt['gasUsed'],
                "deployer": deployer_address,
                "timestamp": int(time.time()),
                "version": "3.0.0-fixed",
                "constructorParams": {
                    "kaspaFinanceFactory": KASPA_FINANCE_FACTORY,
                    "kaspaFinancePositionManager": KASPA_FINANCE_POSITION_MANAGER,
                    "kaspaFinanceWKAS": KASPA_FINANCE_WKAS,
                    "graduationOracle": GRADUATION_ORACLE,
                    "tokenFactory": TOKEN_FACTORY,
                    "treasury": TREASURY
                }
            }
            
            output_file = 'deployments/graduation_controller_v3_fixed.json'
            with open(output_file, 'w') as f:
                json.dump(deployment_info, f, indent=2)
            
            print(f"\n💾 Deployment info saved to: {output_file}")
            print(f"\n" + "=" * 80)
            print(f"🎉 GRADUATIONCONTROLLER V3 DEPLOYED SUCCESSFULLY!")
            print(f"=" * 80)
            print(f"\n📝 NEXT STEPS:")
            print(f"   1. Update web3_service.py with new address: {contract_address}")
            print(f"   2. Restart application")
            print(f"   3. Test with new token creation")
            print(f"\n" + "=" * 80)
            
            return contract_address
            
        else:
            print(f"\n❌ DEPLOYMENT FAILED!")
            print(f"   TX Status: {receipt['status']}")
            return None
            
    except Exception as e:
        print(f"\n❌ Error waiting for transaction: {str(e)}")
        return None

if __name__ == "__main__":
    address = deploy_graduation_controller_v3()
    if address:
        print(f"\n✅ New GraduationController V3: {address}")
    else:
        print(f"\n❌ Deployment failed")
        sys.exit(1)
