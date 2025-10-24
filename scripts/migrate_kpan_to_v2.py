"""Migrate KPAN (and other V1 tokens) to V2 Controller"""
from web3 import Web3
from eth_account import Account
import json
import os

# Config
RPC_URL = "https://rpc.kasplextest.xyz"
V1_CONTROLLER = '0x9416D5a5D61ec70C18D1FE1039f8026E29b4820e'
V2_CONTROLLER = '0x147E3Ecbe189bb301175001706ff1f44dF33B3ab'

# Tokens to migrate
TOKENS_TO_MIGRATE = [
    ('KPAN', '0xc33b27a9d68cb3e8b83dcba031da1a7cb4e29a98'),
    ('RAGR', '0xa75c9441ba642165df45fbcdb03b5627521ecb7a'),
]

# Get deployer key
DEPLOYER_KEY = os.environ.get('DEPLOYER_PRIVATE_KEY')
if not DEPLOYER_KEY:
    print("❌ DEPLOYER_PRIVATE_KEY not found")
    exit(1)

# Connect
w3 = Web3(Web3.HTTPProvider(RPC_URL))
deployer = Account.from_key(DEPLOYER_KEY)

# Load BondingCurvePool ABI
with open('artifacts/contracts/BondingCurvePool.sol/BondingCurvePool.json') as f:
    pool_artifact = json.load(f)

print("=" * 80)
print("MIGRATE TOKENS TO V2 CONTROLLER")
print("=" * 80)
print()

for symbol, address in TOKENS_TO_MIGRATE:
    print(f"\n{symbol} ({address})")
    print("-" * 80)
    
    pool = w3.eth.contract(address=Web3.to_checksum_address(address), abi=pool_artifact['abi'])
    
    # Check current controller
    current_gc = pool.functions.graduationOracle().call()
    graduating = pool.functions.graduating().call()
    graduated = pool.functions.graduated().call()
    
    print(f"  Current controller: {current_gc}")
    print(f"  graduating: {graduating}")
    print(f"  graduated: {graduated}")
    
    if current_gc == V2_CONTROLLER:
        print(f"  ✅ Already on V2")
        continue
    
    if graduated:
        print(f"  ⏭️ Already graduated - skip migration")
        continue
    
    print(f"  ❌ On V1 - Migrating to V2...")
    
    # Update to V2
    tx = pool.functions.setGraduationOracle(V2_CONTROLLER).build_transaction({
        'from': deployer.address,
        'gas': 100000,
        'gasPrice': w3.eth.gas_price,
        'nonce': w3.eth.get_transaction_count(deployer.address),
        'chainId': 167012
    })
    
    signed = deployer.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    
    print(f"  ✅ TX sent: {tx_hash.hex()}")
    print("  ⏳ Waiting for confirmation...")
    
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    
    if receipt['status'] == 1:
        print(f"  ✅ {symbol} migrated to V2!")
        
        # If was graduating, reset that flag
        if graduating:
            print(f"  📌 Was stuck in 'graduating' - now reset, ready to graduate via V2")
    else:
        print(f"  ❌ Migration failed")

print()
print("=" * 80)
print("MIGRATION COMPLETE")
print("=" * 80)
print()
print("All tokens now point to V2 controller.")
print("Graduation monitor will now work correctly.")
