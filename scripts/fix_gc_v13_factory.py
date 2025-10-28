#!/usr/bin/env python3
"""
Fix GraduationController V13 to use TokenFactory V12

ISSUE: GC V13 is configured with TokenFactory V11 (0x427B..5B1) but Mega token
       was deployed by TokenFactory V12 (0x3abF..F07), causing graduation to fail
       
SOLUTION: Call setTokenFactory() on GC V13 to update to TF V12
"""

import sys
import os
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account
import json

# Configuration
RPC_URL = 'https://rpc.kasplextest.xyz'
GC_V13_ADDRESS = '0xf04aB5deE799DDb217a03bF07fFf4dDf541dD9f1'
TF_V12_ADDRESS = '0x3abF3c17a89687FF449DD1aa24A1C159eD4f5F07'
TREASURY_KEY = os.environ.get('ORACLE_PRIVATE_KEY')

# Initialize Web3
w3 = Web3(Web3.HTTPProvider(RPC_URL))
w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

# Treasury account (owns GraduationController)
treasury_account = Account.from_key(TREASURY_KEY)
print(f"Treasury wallet: {treasury_account.address}")

# GraduationController ABI
gc_abi = [
    {
        "inputs": [],
        "name": "tokenFactory",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"name": "newFactory", "type": "address"}],
        "name": "setTokenFactory",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

gc_contract = w3.eth.contract(
    address=Web3.to_checksum_address(GC_V13_ADDRESS),
    abi=gc_abi
)

# Step 1: Check current factory
print("\n=== BEFORE ===")
current_factory = gc_contract.functions.tokenFactory().call()
print(f"Current factory in GC V13: {current_factory}")
print(f"Should be: {TF_V12_ADDRESS}")

if current_factory.lower() == TF_V12_ADDRESS.lower():
    print("✅ Already configured correctly!")
    sys.exit(0)

# Step 2: Update factory
print("\n=== UPDATING FACTORY ===")
nonce = w3.eth.get_transaction_count(treasury_account.address)
gas_price = w3.eth.gas_price

tx = gc_contract.functions.setTokenFactory(
    Web3.to_checksum_address(TF_V12_ADDRESS)
).build_transaction({
    'from': treasury_account.address,
    'nonce': nonce,
    'gas': 100000,
    'gasPrice': gas_price,
    'chainId': 167012
})

print(f"Signing transaction...")
signed_tx = treasury_account.sign_transaction(tx)

print(f"Sending transaction...")
tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
print(f"Transaction hash: {tx_hash.hex()}")

print(f"Waiting for confirmation...")
receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

if receipt['status'] == 1:
    print(f"✅ Transaction confirmed in block {receipt['blockNumber']}")
else:
    print(f"❌ Transaction failed!")
    sys.exit(1)

# Step 3: Verify update
print("\n=== AFTER ===")
new_factory = gc_contract.functions.tokenFactory().call()
print(f"New factory in GC V13: {new_factory}")

if new_factory.lower() == TF_V12_ADDRESS.lower():
    print("✅ Successfully updated GraduationController V13 to use TokenFactory V12!")
    print("\n🎓 Mega token can now graduate!")
else:
    print(f"❌ Update failed! Still pointing to: {new_factory}")
    sys.exit(1)
