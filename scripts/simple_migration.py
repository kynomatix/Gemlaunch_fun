"""Simple V2 Migration - No Flask dependency"""
from web3 import Web3
from eth_account import Account
import json
import os

# Config
RPC_URL = "https://rpc.kasplextest.xyz"
V1_CONTROLLER = '0x9416D5a5D61ec70C18D1FE1039f8026E29b4820e'
V2_CONTROLLER = '0x147E3Ecbe189bb301175001706ff1f44dF33B3ab'

# Get deployer key
DEPLOYER_KEY = os.environ.get('DEPLOYER_PRIVATE_KEY')
if not DEPLOYER_KEY:
    print("❌ DEPLOYER_PRIVATE_KEY not found")
    exit(1)

# Connect
w3 = Web3(Web3.HTTPProvider(RPC_URL))
deployer = Account.from_key(DEPLOYER_KEY)

print("=" * 80)
print("SIMPLE V2 MIGRATION")
print("=" * 80)
print()

# Load TokenFactory ABI
with open('artifacts/contracts/TokenFactory.sol/TokenFactory.json') as f:
    factory_artifact = json.load(f)
    
FACTORY_ADDRESS = '0x39003ab4e8ad700F59bcfA082F73e68bc0477fDc'
factory = w3.eth.contract(address=FACTORY_ADDRESS, abi=factory_artifact['abi'])

# Check current controller
current_gc = factory.functions.graduationController().call()
print(f"TokenFactory: {FACTORY_ADDRESS}")
print(f"Current controller: {current_gc}")

if current_gc == V2_CONTROLLER:
    print("✅ Already using V2")
else:
    print(f"❌ Using V1 - Updating to V2...")
    
    # Build transaction
    tx = factory.functions.setGraduationController(V2_CONTROLLER).build_transaction({
        'from': deployer.address,
        'gas': 100000,
        'gasPrice': w3.eth.gas_price,
        'nonce': w3.eth.get_transaction_count(deployer.address),
        'chainId': 167012
    })
    
    # Sign and send
    signed = deployer.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    
    print(f"✅ TX sent: {tx_hash.hex()}")
    print("⏳ Waiting for confirmation...")
    
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    
    if receipt['status'] == 1:
        print("✅ TokenFactory updated to V2!")
        print()
        print("All NEW tokens will now use V2 controller")
    else:
        print("❌ Transaction failed")
        exit(1)

print()
print("=" * 80)
print("MIGRATION COMPLETE")
print("=" * 80)
