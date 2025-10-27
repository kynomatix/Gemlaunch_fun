#!/usr/bin/env python3
"""
Deployment script for Fixed Graduation System (October 27, 2025)
- GraduationController V3 with pool-initiated handshake
- TokenFactory V4 with isDeployedPool mapping
- Complete security fixes for preventing snapshot corruption
"""

import os
import sys
import json
import time
from web3 import Web3
from eth_account import Account

# Configuration
RPC_URL = "https://rpc.kasplextest.xyz"
CHAIN_ID = 167012

# Deployment tracking
deployment_log = {
    "deployment_date": time.strftime("%Y-%m-%d %H:%M:%S"),
    "network": "kasplex_testnet",
    "chain_id": CHAIN_ID,
    "fixes": [
        "Pool-initiated handshake (pool calls GC directly)",
        "TokenFactory.isDeployedPool mapping prevents fake pools",
        "Snapshot captures correct pool address (no more 0x0 corruption)",
        "Emergency recovery function for corrupted graduations"
    ],
    "contracts": {}
}

def load_contract_artifact(contract_name):
    """Load compiled contract ABI and bytecode"""
    artifact_path = f'artifacts/contracts/{contract_name}.sol/{contract_name}.json'
    print(f"📂 Loading artifact: {artifact_path}")
    with open(artifact_path) as f:
        artifact = json.load(f)
    return artifact['abi'], artifact['bytecode']

def deploy_contract(w3, deployer, contract_name, constructor_args=None):
    """Deploy a contract and return the deployed address"""
    print(f"\n🚀 Deploying {contract_name}...")
    
    abi, bytecode = load_contract_artifact(contract_name)
    
    # Create contract instance
    Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    
    # Build transaction
    if constructor_args:
        print(f"   Constructor args: {constructor_args}")
        constructor_tx = Contract.constructor(*constructor_args)
    else:
        constructor_tx = Contract.constructor()
    
    # Estimate gas
    gas_estimate = constructor_tx.estimate_gas({'from': deployer.address})
    print(f"   ⛽ Gas estimate: {gas_estimate:,}")
    
    # Build and sign transaction
    tx = constructor_tx.build_transaction({
        'from': deployer.address,
        'nonce': w3.eth.get_transaction_count(deployer.address),
        'gas': int(gas_estimate * 1.2),  # 20% buffer
        'gasPrice': w3.eth.gas_price,
        'chainId': CHAIN_ID
    })
    
    signed_tx = deployer.sign_transaction(tx)
    
    # Send transaction
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print(f"   📤 Transaction sent: {tx_hash.hex()}")
    
    # Wait for confirmation
    print(f"   ⏳ Waiting for confirmation...")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
    
    if receipt['status'] == 1:
        contract_address = receipt['contractAddress']
        print(f"   ✅ {contract_name} deployed at: {contract_address}")
        print(f"   📊 Gas used: {receipt['gasUsed']:,}")
        print(f"   🧱 Block: {receipt['blockNumber']}")
        return contract_address, tx_hash.hex(), receipt
    else:
        print(f"   ❌ Deployment failed!")
        sys.exit(1)

def main():
    print("=" * 80)
    print("FIXED GRADUATION SYSTEM DEPLOYMENT")
    print("October 27, 2025 - Pool-Initiated Handshake + Security Fixes")
    print("=" * 80)
    
    # Connect to network
    print(f"\n🌐 Connecting to {RPC_URL}...")
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    
    if not w3.is_connected():
        print("❌ Failed to connect to RPC")
        sys.exit(1)
    
    print(f"✅ Connected! Chain ID: {w3.eth.chain_id}")
    
    # Load deployer account
    private_key = os.environ.get('DEPLOYER_PRIVATE_KEY') or os.environ.get('ORACLE_PRIVATE_KEY')
    if not private_key:
        print("❌ DEPLOYER_PRIVATE_KEY or ORACLE_PRIVATE_KEY not found in environment")
        sys.exit(1)
    
    deployer = Account.from_key(private_key)
    print(f"👤 Deployer address: {deployer.address}")
    
    balance = w3.eth.get_balance(deployer.address)
    print(f"💰 Balance: {w3.from_wei(balance, 'ether')} KAS")
    
    if balance == 0:
        print("❌ Insufficient balance")
        sys.exit(1)
    
    # Deployment wallet addresses
    DEPLOYER_ADDRESS = deployer.address
    # Oracle address is derived from deployer wallet (index 1)
    ORACLE_ADDRESS = "0x5f837F62744D4d80Fc79C3A5346B4A228956914E"
    
    # Kaspa Finance addresses (CORRECT - from replit.md)
    KASPA_FINANCE_FACTORY = "0x1b72D7165a0D7256a4F197765C15bb70bC5D66A8"
    KASPA_FINANCE_POSITION_MANAGER = "0x4E25637cF39822364b877F81B18c5B6CF0eeF589"
    KASPA_FINANCE_WKAS = "0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94"
    
    print(f"\n📋 Configuration:")
    print(f"   Deployer: {DEPLOYER_ADDRESS}")
    print(f"   Oracle: {ORACLE_ADDRESS}")
    print(f"   Kaspa Finance Factory: {KASPA_FINANCE_FACTORY}")
    print(f"   Kaspa Finance Position Manager: {KASPA_FINANCE_POSITION_MANAGER}")
    print(f"   Kaspa Finance WKAS: {KASPA_FINANCE_WKAS}")
    
    # STEP 1: Deploy GraduationController V3
    print("\n" + "=" * 80)
    print("STEP 1: Deploy GraduationController V3")
    print("=" * 80)
    
    # Note: We'll deploy with temp TokenFactory address, then update later
    temp_token_factory = "0x0000000000000000000000000000000000000001"  # Placeholder
    
    gc_args = [
        KASPA_FINANCE_FACTORY,
        KASPA_FINANCE_POSITION_MANAGER,
        KASPA_FINANCE_WKAS,
        ORACLE_ADDRESS,  # oracle
        temp_token_factory,  # will be updated after TokenFactory deployment
        DEPLOYER_ADDRESS  # treasury
    ]
    
    gc_address, gc_tx, gc_receipt = deploy_contract(
        w3, deployer, "GraduationControllerV3", gc_args
    )
    
    deployment_log["contracts"]["GraduationControllerV3"] = {
        "address": gc_address,
        "tx_hash": gc_tx,
        "block": gc_receipt['blockNumber'],
        "gas_used": gc_receipt['gasUsed']
    }
    
    # STEP 2: Deploy TokenFactory V4
    print("\n" + "=" * 80)
    print("STEP 2: Deploy TokenFactory V4 (with isDeployedPool mapping)")
    print("=" * 80)
    
    tf_args = [
        gc_address,  # graduationController
        DEPLOYER_ADDRESS,  # treasury
        ORACLE_ADDRESS,  # airdropTreasury
        DEPLOYER_ADDRESS,  # platformDevelopmentWallet
        ORACLE_ADDRESS,  # graduationOracle
        ORACLE_ADDRESS,  # admin
        DEPLOYER_ADDRESS,  # buybackReserveWallet
        DEPLOYER_ADDRESS,  # kaspaNetworkSupportWallet
        DEPLOYER_ADDRESS  # communityRewardsWallet
    ]
    
    tf_address, tf_tx, tf_receipt = deploy_contract(
        w3, deployer, "TokenFactory", tf_args
    )
    
    deployment_log["contracts"]["TokenFactory"] = {
        "address": tf_address,
        "tx_hash": tf_tx,
        "block": tf_receipt['blockNumber'],
        "gas_used": tf_receipt['gasUsed'],
        "version": "V4",
        "features": ["isDeployedPool mapping for security validation"]
    }
    
    # STEP 3: Update GraduationController with correct TokenFactory address
    print("\n" + "=" * 80)
    print("STEP 3: Configure GraduationController with TokenFactory address")
    print("=" * 80)
    
    gc_abi, _ = load_contract_artifact("GraduationControllerV3")
    gc_contract = w3.eth.contract(address=gc_address, abi=gc_abi)
    
    print(f"   Updating tokenFactory to: {tf_address}")
    
    update_tx = gc_contract.functions.updateTokenFactory(tf_address).build_transaction({
        'from': deployer.address,
        'nonce': w3.eth.get_transaction_count(deployer.address),
        'gas': 100000,
        'gasPrice': w3.eth.gas_price,
        'chainId': CHAIN_ID
    })
    
    signed_update = deployer.sign_transaction(update_tx)
    update_tx_hash = w3.eth.send_raw_transaction(signed_update.raw_transaction)
    print(f"   📤 Update transaction sent: {update_tx_hash.hex()}")
    
    update_receipt = w3.eth.wait_for_transaction_receipt(update_tx_hash, timeout=120)
    
    if update_receipt['status'] == 1:
        print(f"   ✅ TokenFactory address updated successfully!")
    else:
        print(f"   ❌ Failed to update TokenFactory address")
        sys.exit(1)
    
    deployment_log["configuration"] = {
        "graduation_controller_token_factory_update": {
            "tx_hash": update_tx_hash.hex(),
            "block": update_receipt['blockNumber']
        }
    }
    
    # STEP 4: Verify deployment
    print("\n" + "=" * 80)
    print("STEP 4: Verify Deployment")
    print("=" * 80)
    
    # Verify GC configuration
    stored_tf = gc_contract.functions.tokenFactory().call()
    print(f"   GraduationController.tokenFactory: {stored_tf}")
    print(f"   Expected: {tf_address}")
    
    if stored_tf.lower() == tf_address.lower():
        print(f"   ✅ Configuration verified!")
    else:
        print(f"   ❌ Configuration mismatch!")
        sys.exit(1)
    
    # STEP 5: Save deployment records
    print("\n" + "=" * 80)
    print("STEP 5: Save Deployment Records")
    print("=" * 80)
    
    filename = f"deployments/fixed_graduation_system_{int(time.time())}.json"
    with open(filename, 'w') as f:
        json.dump(deployment_log, f, indent=2)
    
    print(f"   📄 Deployment log saved: {filename}")
    
    # Print summary
    print("\n" + "=" * 80)
    print("DEPLOYMENT COMPLETE!")
    print("=" * 80)
    print(f"\n✅ GraduationController V3: {gc_address}")
    print(f"✅ TokenFactory V4: {tf_address}")
    print(f"\n🔗 Explorer links:")
    print(f"   GC: https://explorer.testnet.kasplextest.xyz/address/{gc_address}")
    print(f"   TF: https://explorer.testnet.kasplextest.xyz/address/{tf_address}")
    print(f"\n📝 Next steps:")
    print(f"   1. Update services/web3_service.py with new addresses")
    print(f"   2. Create test token to verify basic deployment")
    print(f"   3. Test graduation initiation phase")
    print(f"   4. Test graduation completion phase (30-min wait)")
    print(f"   5. Update backend to remove direct GC calls")
    print("=" * 80)

if __name__ == "__main__":
    main()
