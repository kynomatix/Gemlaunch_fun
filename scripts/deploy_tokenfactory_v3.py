#!/usr/bin/env python3
"""
Deploy TokenFactory V3 with updated BondingCurvePool bytecode
This fixes the "Price slippage check" error by deploying with current contract code
"""

import sys
import os
import json
import time
from web3 import Web3

sys.path.insert(0, '/home/runner/workspace')
from services.web3_service import get_web3_service

def deploy_tokenfactory_v3():
    """Deploy TokenFactory V3 with current BondingCurvePool code"""
    
    web3_service = get_web3_service()
    w3 = web3_service.w3
    
    print("=" * 80)
    print("🚀 DEPLOYING TOKENFACTORY V3")
    print("=" * 80)
    
    # Load TokenFactory artifact
    with open('artifacts/contracts/TokenFactory.sol/TokenFactory.json') as f:
        artifact = json.load(f)
        abi = artifact['abi']
        bytecode = artifact['bytecode']
    
    print(f"\n📋 Contract Info:")
    print(f"   Bytecode size: {len(bytecode) // 2} bytes")
    
    # Configuration addresses (same as V2)
    GC_V3 = "0x2b68832db449f82bf70907a033bf279c73209b59"
    TREASURY = os.environ.get('DEPLOYER_ADDRESS', '0xe281e4776FB5De20817D0bbC72B0C4b955565619')
    AIRDROP_TREASURY = os.environ.get('ORACLE_ADDRESS', '0x5f837F62744D4d80Fc79C3A5346B4A228956914E')
    PLATFORM_DEV = TREASURY
    ORACLE = os.environ.get('ORACLE_ADDRESS', '0x5f837F62744D4d80Fc79C3A5346B4A228956914E')
    ADMIN = ORACLE
    BUYBACK = TREASURY
    KASPA_SUPPORT = TREASURY
    COMMUNITY = TREASURY
    
    print(f"\n🎯 Constructor Parameters:")
    print(f"   GraduationController V3: {GC_V3}")
    print(f"   Treasury: {TREASURY}")
    print(f"   Airdrop Treasury: {AIRDROP_TREASURY}")
    print(f"   Oracle: {ORACLE}")
    
    # Create contract instance
    TokenFactory = w3.eth.contract(abi=abi, bytecode=bytecode)
    
    # Build constructor transaction
    constructor_args = [
        Web3.to_checksum_address(GC_V3),
        Web3.to_checksum_address(TREASURY),
        Web3.to_checksum_address(AIRDROP_TREASURY),
        Web3.to_checksum_address(PLATFORM_DEV),
        Web3.to_checksum_address(ORACLE),
        Web3.to_checksum_address(ADMIN),
        Web3.to_checksum_address(BUYBACK),
        Web3.to_checksum_address(KASPA_SUPPORT),
        Web3.to_checksum_address(COMMUNITY)
    ]
    
    print(f"\n⛽ Estimating gas...")
    try:
        gas_estimate = TokenFactory.constructor(*constructor_args).estimate_gas({
            'from': Web3.to_checksum_address(TREASURY)
        })
        print(f"   Gas estimate: {gas_estimate:,}")
    except Exception as e:
        print(f"   ⚠️ Gas estimation failed: {str(e)[:200]}")
        gas_estimate = 5000000  # Fallback
    
    # Build transaction
    deployer_address = Web3.to_checksum_address(TREASURY)
    nonce = w3.eth.get_transaction_count(deployer_address)
    
    # Get deployer private key
    deployer_key = os.environ.get('DEPLOYER_PRIVATE_KEY')
    if not deployer_key:
        print("❌ DEPLOYER_PRIVATE_KEY not found in environment!")
        return None
    
    tx = TokenFactory.constructor(*constructor_args).build_transaction({
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
            deployed_factory = w3.eth.contract(
                address=Web3.to_checksum_address(contract_address),
                abi=abi
            )
            
            gc_address = deployed_factory.functions.graduationController().call()
            print(f"   graduationController(): {gc_address}")
            
            if gc_address.lower() == GC_V3.lower():
                print(f"   ✅ Correctly linked to GraduationController V3")
            else:
                print(f"   ❌ MISMATCH! Expected {GC_V3}")
            
            # Save deployment info
            deployment_info = {
                'address': contract_address,
                'txHash': tx_hash.hex(),
                'blockNumber': receipt['blockNumber'],
                'gasUsed': receipt['gasUsed'],
                'deployer': deployer_address,
                'timestamp': int(time.time()),
                'graduationController': gc_address
            }
            
            with open('deployments/tokenfactory_v3.json', 'w') as f:
                json.dump(deployment_info, f, indent=2)
            
            print(f"\n💾 Deployment info saved to deployments/tokenfactory_v3.json")
            
            return contract_address
        else:
            print(f"\n❌ DEPLOYMENT FAILED!")
            print(f"   Transaction reverted")
            return None
            
    except Exception as e:
        print(f"\n❌ Error waiting for receipt: {e}")
        return None

if __name__ == '__main__':
    address = deploy_tokenfactory_v3()
    
    if address:
        print("\n" + "=" * 80)
        print("🎉 NEXT STEPS")
        print("=" * 80)
        print(f"\n1. Update services/web3_service.py:")
        print(f"   TOKEN_FACTORY_ADDRESS = \"{address}\"")
        print(f"\n2. Restart the application")
        print(f"\n3. Create a test token to verify it uses current BondingCurvePool")
        print("=" * 80)
    else:
        print("\n❌ Deployment failed. Check errors above.")
        sys.exit(1)
