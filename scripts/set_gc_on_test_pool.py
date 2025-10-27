#!/usr/bin/env python3
"""
Helper script to set GraduationController address on test pools
Used for testing graduation flow when pools are created without GC set
"""

import os
import json
from web3 import Web3
from eth_account import Account

# Configuration
RPC_URL = "https://rpc.kasplextest.xyz"
CHAIN_ID = 167012

# Addresses
TOKEN_FACTORY = "0x408dcf382d38eCe30b2b25C86440f923CAa7B631"
GRADUATION_CONTROLLER = "0x91e405C15F7aD99b2E669c7E745422c4DC8f5A89"
FINALTEST_POOL = "0x7c9C7190fFc527ff9D550F435066C8c97AD0c020"

def main():
    # Initialize web3
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    deployer = Account.from_key(os.environ['DEPLOYER_PRIVATE_KEY'])
    
    print("=" * 60)
    print("Setting GraduationController on FINALTEST Pool")
    print("=" * 60)
    print(f"Deployer: {deployer.address}")
    print(f"TokenFactory: {TOKEN_FACTORY}")
    print(f"GraduationController: {GRADUATION_CONTROLLER}")
    print(f"FINALTEST Pool: {FINALTEST_POOL}")
    print()
    
    # Load TokenFactory ABI
    with open('artifacts/contracts/TokenFactory.sol/TokenFactory.json') as f:
        tf_abi = json.load(f)['abi']
    
    tf = w3.eth.contract(address=TOKEN_FACTORY, abi=tf_abi)
    
    # Verify deployer is owner
    tf_owner = tf.functions.owner().call()
    if tf_owner.lower() != deployer.address.lower():
        print(f"❌ ERROR: Deployer is not TokenFactory owner!")
        print(f"   Expected: {deployer.address}")
        print(f"   Actual: {tf_owner}")
        return
    
    print("✅ Verified: Deployer owns TokenFactory")
    
    # Load Pool ABI
    with open('artifacts/contracts/BondingCurvePool.sol/BondingCurvePool.json') as f:
        pool_abi = json.load(f)['abi']
    
    pool = w3.eth.contract(address=FINALTEST_POOL, abi=pool_abi)
    
    # Check current state
    current_gc = pool.functions.graduationController().call()
    pool_owner = pool.functions.owner().call()
    
    print(f"\nCurrent Pool State:")
    print(f"  Owner: {pool_owner}")
    print(f"  GraduationController: {current_gc}")
    
    if pool_owner.lower() != TOKEN_FACTORY.lower():
        print(f"❌ ERROR: Pool not owned by TokenFactory!")
        return
    
    print("✅ Verified: TokenFactory owns pool")
    
    if current_gc.lower() == GRADUATION_CONTROLLER.lower():
        print("\n✅ GraduationController already set correctly!")
        return
    
    # Build transaction to transfer ownership temporarily
    print("\n📝 Strategy:")
    print("  1. TokenFactory transfers pool ownership to deployer")
    print("  2. Deployer sets GraduationController")
    print("  3. Deployer transfers pool ownership back to TokenFactory")
    print()
    
    # Step 1: Transfer ownership from TF to deployer
    print("Step 1: Transferring pool ownership to deployer...")
    
    # We need to call this from TokenFactory
    # TokenFactory doesn't have a function to transfer pool ownership
    # So we need to use Ownable's transferOwnership on the pool
    
    # Actually, we can't do this without a migration function on TokenFactory
    # Let me create a simple Hardhat script instead
    
    print("\n⚠️ TokenFactory doesn't have a migration function.")
    print("Creating Hardhat script instead...")

if __name__ == "__main__":
    main()
