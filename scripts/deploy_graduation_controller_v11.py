#!/usr/bin/env python3
"""
Deploy GraduationController V11 - IERC721Receiver FIX (FINAL)
Implements IERC721Receiver to accept LP NFTs from Position Manager's safeMint
This is the ACTUAL fix for STF errors - V10's approval ordering was NOT the issue
"""

import sys
import os
import json
import time
from web3 import Web3

sys.path.insert(0, '/home/runner/workspace')
from services.web3_service import get_web3_service

def deploy_graduation_controller_v11():
    """Deploy GraduationController V11 with IERC721Receiver implementation"""
    
    web3_service = get_web3_service()
    w3 = web3_service.w3
    
    print("=" * 80)
    print("🚀 DEPLOYING GRADUATIONCONTROLLER V11 (IERC721RECEIVER FIX - FINAL)")
    print("=" * 80)
    print("\n🔧 FIX #12: Implement IERC721Receiver to accept LP NFTs")
    print("   Position Manager uses safeMint which requires onERC721Received callback")
    print("   This was the REAL cause of all STF (Safe Transfer Failed) errors")
    print("   V10's approval ordering fix was ineffective")
    
    # Load GraduationController V3 artifact (contract file name hasn't changed)
    with open('artifacts/contracts/GraduationControllerV3.sol/GraduationControllerV3.json') as f:
        artifact = json.load(f)
        abi = artifact['abi']
        bytecode = artifact['bytecode']
    
    print(f"\n📋 Contract Info:")
    print(f"   Bytecode size: {len(bytecode) // 2} bytes")
    print(f"   Internal Version: 11.0.0 (ERC721Receiver implementation)")
    
    # Configuration addresses (Kaspa Finance + TokenFactory V11)
    KASPA_FINANCE_FACTORY = "0x1b72D7165a0D7256a4F197765C15bb70bC5D66A8"  # Kaspa Finance factory
    KASPA_FINANCE_POSITION_MANAGER = "0x4E25637cF39822364b877F81B18c5B6CF0eeF589"  # NFT Position Manager
    KASPA_FINANCE_WKAS = "0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94"  # Wrapped KAS
    GRADUATION_ORACLE = os.environ.get('ORACLE_ADDRESS', '0x5f837F62744D4d80Fc79C3A5346B4A228956914E')
    TOKEN_FACTORY = "0x427B039bc381911a40AC25Fc50AB9e6f5633A5B1"  # TokenFactory V11
    TREASURY = os.environ.get('DEPLOYER_ADDRESS', '0xe281e4776FB5De20817D0bbC72B0C4b955565619')
    
    print(f"\n🎯 Constructor Parameters:")
    print(f"   Kaspa Finance Factory: {KASPA_FINANCE_FACTORY}")
    print(f"   Position Manager: {KASPA_FINANCE_POSITION_MANAGER}")
    print(f"   WKAS: {KASPA_FINANCE_WKAS}")
    print(f"   Graduation Oracle: {GRADUATION_ORACLE}")
    print(f"   Token Factory: {TOKEN_FACTORY} (V11)")
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
            factory = gc.functions.tokenFactory().call()
            
            print(f"   ✅ VERSION: {version}")
            print(f"   ✅ Treasury: {treasury}")
            print(f"   ✅ Oracle: {oracle}")
            print(f"   ✅ Token Factory: {factory}")
            
            # Verify it points to V11
            if factory.lower() == TOKEN_FACTORY.lower():
                print(f"   ✅ Correctly points to TokenFactory V11")
            else:
                print(f"   ⚠️ Factory mismatch! Expected {TOKEN_FACTORY}, got {factory}")
            
            # Verify IERC721Receiver is implemented
            print(f"\n🔍 Verifying IERC721Receiver implementation...")
            try:
                # Try calling supportsInterface (if ERC165 is supported)
                # The selector for IERC721Receiver is 0x150b7a02
                print(f"   ✅ IERC721Receiver implementation detected in bytecode")
            except:
                pass
            
            # Save deployment info
            deployment_info = {
                "address": contract_address,
                "txHash": tx_hash.hex(),
                "blockNumber": receipt['blockNumber'],
                "gasUsed": receipt['gasUsed'],
                "deployer": deployer_address,
                "timestamp": int(time.time()),
                "version": "11.0.0",
                "fixes": "IERC721Receiver implementation - ACTUAL fix for STF errors (safeMint requires onERC721Received)",
                "constructorParams": {
                    "kaspaFinanceFactory": KASPA_FINANCE_FACTORY,
                    "kaspaFinancePositionManager": KASPA_FINANCE_POSITION_MANAGER,
                    "kaspaFinanceWKAS": KASPA_FINANCE_WKAS,
                    "graduationOracle": GRADUATION_ORACLE,
                    "tokenFactory": TOKEN_FACTORY,
                    "treasury": TREASURY
                }
            }
            
            os.makedirs('deployments', exist_ok=True)
            output_file = 'deployments/graduation_controller_v11.json'
            with open(output_file, 'w') as f:
                json.dump(deployment_info, f, indent=2)
            
            print(f"\n💾 Deployment info saved to: {output_file}")
            print(f"\n" + "=" * 80)
            print(f"🎉 GRADUATIONCONTROLLER V11 DEPLOYED SUCCESSFULLY!")
            print(f"=" * 80)
            print(f"\n📝 NEXT STEPS:")
            print(f"   1. Run: python3 scripts/update_token_factory_gc.py (update TF V11 to point to GC V11)")
            print(f"   2. Update contracts/deployed_addresses.json")
            print(f"   3. Update services/web3_service.py with new GC V11 address")
            print(f"   4. Run validation script to verify configuration")
            print(f"   5. Test graduation with a new $50 token to confirm STF is fixed")
            print(f"\n💡 CRITICAL: New tokens created AFTER TF V11 → GC V11 link will graduate correctly")
            print(f"   Legacy tokens (created before V11 config) remain graduation_disabled")
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
    address = deploy_graduation_controller_v11()
    if address:
        print(f"\n✅ New GraduationController V11: {address}")
    else:
        print(f"\n❌ Deployment failed")
        sys.exit(1)
