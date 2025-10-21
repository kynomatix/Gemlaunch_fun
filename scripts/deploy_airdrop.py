#!/usr/bin/env python3
"""
Deploy AirdropDistributor contract using Python web3
This uses the existing web3_service configuration with POA middleware
"""
import sys
import os
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.web3_service import get_web3, get_oracle_account
from web3 import Web3

def main():
    print("=" * 60)
    print("  Deploying AirdropDistributor Contract")
    print("=" * 60)
    print()
    
    # Get web3 instance (with POA middleware)
    w3 = get_web3()
    oracle_account = get_oracle_account()
    
    print(f"Network: Kasplex Testnet")
    print(f"Chain ID: {w3.eth.chain_id}")
    print(f"Deployer: {oracle_account.address}")
    balance = w3.eth.get_balance(oracle_account.address)
    print(f"Balance: {w3.from_wei(balance, 'ether')} KAS")
    print()
    
    if balance == 0:
        print("❌ Deployer has 0 balance!")
        return
    
    # Load compiled contract
    artifact_path = Path("artifacts/contracts/AirdropDistributor.sol/AirdropDistributor.json")
    if not artifact_path.exists():
        print(f"❌ Contract artifact not found: {artifact_path}")
        print("Run: npx hardhat compile")
        return
    
    with open(artifact_path) as f:
        artifact = json.load(f)
    
    print(f"Contract artifact loaded")
    print(f"Bytecode size: {len(artifact['bytecode'])} bytes")
    print()
    
    # Create contract
    AirdropDistributor = w3.eth.contract(
        abi=artifact['abi'],
        bytecode=artifact['bytecode']
    )
    
    print("Building deployment transaction...")
    
    # Get current gas price
    gas_price = w3.eth.gas_price
    print(f"Gas price: {w3.from_wei(gas_price, 'gwei')} gwei")
    
    # Build transaction
    constructor_txn = AirdropDistributor.constructor().build_transaction({
        'from': oracle_account.address,
        'nonce': w3.eth.get_transaction_count(oracle_account.address),
        'gas': 3000000,
        'gasPrice': gas_price
    })
    
    print(f"Estimated gas: {constructor_txn['gas']}")
    print()
    
    print("Signing transaction...")
    signed_txn = oracle_account.sign_transaction(constructor_txn)
    
    print("Sending transaction...")
    tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
    print(f"✅ Transaction sent: {tx_hash.hex()}")
    print(f"Explorer: https://explorer.testnet.kasplextest.xyz/tx/{tx_hash.hex()}")
    print()
    
    print("Waiting for confirmation (timeout: 60s)...")
    try:
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        
        print()
        print("=" * 60)
        print("  ✅ DEPLOYMENT SUCCESSFUL!")
        print("=" * 60)
        print()
        print(f"Contract Address: {receipt['contractAddress']}")
        print(f"Block Number: {receipt['blockNumber']}")
        print(f"Gas Used: {receipt['gasUsed']}")
        print(f"Status: {'Success' if receipt['status'] == 1 else 'Failed'}")
        print()
        print(f"Explorer: https://explorer.testnet.kasplextest.xyz/address/{receipt['contractAddress']}")
        print()
        
        # Save deployment info
        deployment_info = {
            "network": "kasplex_testnet",
            "chainId": w3.eth.chain_id,
            "contract": {
                "name": "AirdropDistributor",
                "address": receipt['contractAddress'],
                "transactionHash": tx_hash.hex(),
                "blockNumber": receipt['blockNumber'],
                "gasUsed": receipt['gasUsed']
            },
            "deployer": oracle_account.address
        }
        
        output_file = Path("deployments") / f"airdrop_distributor_{w3.eth.chain_id}.json"
        output_file.parent.mkdir(exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(deployment_info, f, indent=2)
        
        print(f"Deployment info saved: {output_file}")
        print()
        print("⚠️  Next steps:")
        print(f"  1. Update services/web3_service.py with:")
        print(f"     AIRDROP_DISTRIBUTOR_ADDRESS = '{receipt['contractAddress']}'")
        
    except Exception as e:
        print(f"\n❌ Transaction failed or timed out: {e}")
        print(f"Check status: https://explorer.testnet.kasplextest.xyz/tx/{tx_hash.hex()}")

if __name__ == "__main__":
    main()
