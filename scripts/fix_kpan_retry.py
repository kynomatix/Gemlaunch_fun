"""Fix KPAN - Retry with fresh nonce"""
from web3 import Web3
from eth_account import Account
import json
import os
import time

RPC_URL = "https://rpc.kasplextest.xyz"
V2_CONTROLLER = '0x147E3Ecbe189bb301175001706ff1f44dF33B3ab'
KPAN_ADDRESS = '0xc33b27a9d68cb3e8b83dcba031da1a7cb4e29a98'

DEPLOYER_KEY = os.environ.get('DEPLOYER_PRIVATE_KEY')
w3 = Web3(Web3.HTTPProvider(RPC_URL))
deployer = Account.from_key(DEPLOYER_KEY)

with open('artifacts/contracts/BondingCurvePool.sol/BondingCurvePool.json') as f:
    abi = json.load(f)['abi']

kpan = w3.eth.contract(address=Web3.to_checksum_address(KPAN_ADDRESS), abi=abi)

# Check current state
gc = kpan.functions.graduationOracle().call()
print(f"Current controller: {gc}")

if gc == V2_CONTROLLER:
    print("✅ Already on V2!")
    exit(0)

print(f"Deployer: {deployer.address}")

# Get fresh nonce
nonce = w3.eth.get_transaction_count(deployer.address)
print(f"Nonce: {nonce}")

# Build with higher gas
tx = kpan.functions.setGraduationOracle(V2_CONTROLLER).build_transaction({
    'from': deployer.address,
    'gas': 200000,  # Higher gas
    'gasPrice': int(w3.eth.gas_price * 1.5),  # 50% higher gas price
    'nonce': nonce,
    'chainId': 167012
})

print(f"Gas: {tx['gas']}, GasPrice: {tx['gasPrice'] / 1e9:.2f} gwei")

# Sign and send
signed = deployer.sign_transaction(tx)
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

print(f"\n✅ TX: {tx_hash.hex()}")
print(f"Explorer: https://explorer.testnet.kasplextest.xyz/tx/{tx_hash.hex()}")

# Wait 30s then check
time.sleep(30)

try:
    receipt = w3.eth.get_transaction_receipt(tx_hash)
    if receipt['status'] == 1:
        print("\n✅ SUCCESS - KPAN migrated to V2!")
    else:
        print("\n❌ Transaction failed")
except:
    print("\n⏳ Still pending - check explorer")
