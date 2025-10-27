"""
Complete ORING graduation properly by calling GraduationController.completeGraduation()

This will:
1. Create the Uniswap V3 pool on Kaspa Finance
2. Mint the LP NFT with full-range liquidity
3. Burn the LP NFT to lock liquidity permanently
4. Complete the pool's graduation state
"""

import os
import sys
import json
from web3 import Web3
from eth_account import Account
import time

# Connect to Kasplex testnet
w3 = Web3(Web3.HTTPProvider('https://rpc.kasplextest.xyz'))
print(f"Connected to RPC - Chain ID: {w3.eth.chain_id}")

# Get deployer account and derive oracle account (secondary wallet)
DEPLOYER_PRIVATE_KEY = os.environ.get('DEPLOYER_PRIVATE_KEY')
if not DEPLOYER_PRIVATE_KEY:
    print("ERROR: DEPLOYER_PRIVATE_KEY not found in environment")
    sys.exit(1)

# Derive oracle account from deployer (same as web3_service.py)
deployer_account = Account.from_key(DEPLOYER_PRIVATE_KEY)

# Normalize private key
if not DEPLOYER_PRIVATE_KEY.startswith('0x'):
    DEPLOYER_PRIVATE_KEY = f'0x{DEPLOYER_PRIVATE_KEY}'

# Derive secondary wallet (oracle) using the CORRECT method from web3_service
seed_text = "GEMLAUNCH_SECONDARY_WALLET"
seed_bytes = seed_text.encode('utf-8')
deployer_bytes = bytes.fromhex(DEPLOYER_PRIVATE_KEY[2:])  # Remove 0x prefix
combined = seed_bytes + deployer_bytes
derived_key = w3.keccak(combined)
derived_key_hex = '0x' + derived_key.hex()
oracle_account = Account.from_key(derived_key_hex)
print(f"Oracle wallet: {oracle_account.address}")
print(f"Oracle balance: {w3.eth.get_balance(oracle_account.address) / 1e18:.4f} KAS")

# Contract addresses
ORING_ADDRESS = '0x462F79A487d26a3F61Ac13389a1b0070171dF1Bc'
GC_V3_ADDRESS = '0x91e405C15F7aD99b2E669c7E745422c4DC8f5A89'

# Load GraduationController ABI
with open('artifacts/contracts/GraduationControllerV3.sol/GraduationControllerV3.json', 'r') as f:
    gc_artifact = json.load(f)

gc_contract = w3.eth.contract(
    address=Web3.to_checksum_address(GC_V3_ADDRESS),
    abi=gc_artifact['abi']
)

# Check current state
print("\n=== Pre-Completion State ===")
print(f"GC Balance: {w3.eth.get_balance(GC_V3_ADDRESS) / 1e18:.4f} KAS")

try:
    snapshot = gc_contract.functions.graduationSnapshots(ORING_ADDRESS).call()
    print(f"Snapshot exists: {snapshot[0] > 0}")  # initiatedAt
    print(f"LP Minted: {snapshot[7]}")  # lpMinted
except Exception as e:
    print(f"Snapshot check failed: {e}")

# Build transaction to call completeGraduation
print("\n=== Calling GraduationController.completeGraduation() ===")

try:
    # Build the transaction
    tx = gc_contract.functions.completeGraduation(
        Web3.to_checksum_address(ORING_ADDRESS)
    ).build_transaction({
        'from': oracle_account.address,
        'nonce': w3.eth.get_transaction_count(oracle_account.address),
        'gasPrice': w3.eth.gas_price,
        'gas': 5000000,  # High gas limit for complex DEX operations
        'chainId': w3.eth.chain_id
    })
    
    # Sign the transaction
    signed_tx = oracle_account.sign_transaction(tx)
    
    # Send the transaction
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print(f"Transaction sent: {tx_hash.hex()}")
    
    # Wait for confirmation
    print("Waiting for confirmation...")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
    
    print(f"\n=== Transaction Result ===")
    print(f"Block: {receipt['blockNumber']}")
    print(f"Gas used: {receipt['gasUsed']:,}")
    print(f"Status: {'SUCCESS' if receipt['status'] == 1 else 'FAILED'}")
    
    if receipt['status'] == 1:
        print("\n=== Post-Completion State ===")
        print(f"GC Balance: {w3.eth.get_balance(GC_V3_ADDRESS) / 1e18:.4f} KAS")
        
        # Check for events
        print(f"\nEvents emitted: {len(receipt['logs'])}")
        
        # Try to get pool address
        try:
            pool_address = gc_contract.functions.uniswapPoolAddress(ORING_ADDRESS).call()
            print(f"✅ Kaspa Finance Pool created: {pool_address}")
        except Exception as e:
            print(f"Could not fetch pool address: {e}")
        
        print(f"\n✅ ORING graduation completed successfully!")
        print(f"Transaction: {tx_hash.hex()}")
        
    else:
        print("\n❌ Transaction failed - check logs for details")
        print(f"Logs: {receipt['logs']}")

except Exception as e:
    print(f"\n❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
