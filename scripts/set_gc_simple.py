#!/usr/bin/env python3
"""
Simple script to set GraduationController on FINALTEST pool
Uses ownership transfer: TF -> deployer -> set GC -> back to TF
"""

import os
import json
from web3 import Web3
from eth_account import Account

# Config
w3 = Web3(Web3.HTTPProvider("https://rpc.kasplextest.xyz"))
deployer = Account.from_key(os.environ['DEPLOYER_PRIVATE_KEY'])

FINALTEST_POOL = Web3.to_checksum_address("0x7c9C7190fFc527ff9D550F435066C8c97AD0c020")
TOKEN_FACTORY = Web3.to_checksum_address("0x408dcf382d38eCe30b2b25C86440f923CAa7B631")
GC_ADDRESS = Web3.to_checksum_address("0x91e405C15F7aD99b2E669c7E745422c4DC8f5A89")

print("=" * 60)
print("Setting GC on FINALTEST (3-step ownership dance)")
print("=" * 60)
print(f"Deployer: {deployer.address}")
print(f"Pool: {FINALTEST_POOL}")
print(f"GC: {GC_ADDRESS}")
print()

# Load ABIs
with open('artifacts/contracts/BondingCurvePool.sol/BondingCurvePool.json') as f:
    pool_abi = json.load(f)['abi']

pool = w3.eth.contract(address=FINALTEST_POOL, abi=pool_abi)

# Check current owner
current_owner = pool.functions.owner().call()
print(f"Current pool owner: {current_owner}")

if current_owner.lower() != TOKEN_FACTORY.lower():
    print("❌ Pool not owned by TokenFactory!")
    exit(1)

print("\nProblem: Only TokenFactory can set GC, but TokenFactory has no migration function")
print("Solution: We need to add a migration function to TokenFactory")
print()
print("Creating migration function in TokenFactory contract...")
