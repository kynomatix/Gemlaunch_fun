"""Fix KPAN - Migrate from V1 to V2 controller"""
from web3 import Web3
from eth_account import Account
import json
import os
import time

RPC_URL = "https://rpc.kasplextest.xyz"
V2_CONTROLLER = '0x147E3Ecbe189bb301175001706ff1f44dF33B3ab'
KPAN_ADDRESS = '0xc33b27a9d68cb3e8b83dcba031da1a7cb4e29a98'

DEPLOYER_KEY = os.environ.get('DEPLOYER_PRIVATE_KEY')
if not DEPLOYER_KEY:
    print("❌ DEPLOYER_PRIVATE_KEY not set")
    exit(1)

w3 = Web3(Web3.HTTPProvider(RPC_URL))
deployer = Account.from_key(DEPLOYER_KEY)

# Load BondingCurvePool ABI
with open('artifacts/contracts/BondingCurvePool.sol/BondingCurvePool.json') as f:
    abi = json.load(f)['abi']

kpan = w3.eth.contract(address=Web3.to_checksum_address(KPAN_ADDRESS), abi=abi)

print("=" * 80)
print("FIXING KPAN")
print("=" * 80)
print()

# Check current state
gc = kpan.functions.graduationOracle().call()
graduating = kpan.functions.graduating().call()
kas_reserve = kpan.functions.virtualKasReserve().call() / 1e18

print(f"KPAN: {KPAN_ADDRESS}")
print(f"  Current controller: {gc}")
print(f"  graduating: {graduating}")
print(f"  KAS locked: {kas_reserve:.2f} KAS")
print()

if gc == V2_CONTROLLER:
    print("✅ Already on V2")
    exit(0)

print("🔧 Migrating to V2...")
print()

# Build transaction
tx = kpan.functions.setGraduationOracle(V2_CONTROLLER).build_transaction({
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
print()

# Poll for receipt (Kasplex RPC is slow)
print("⏳ Waiting for confirmation (may take 2+ minutes)...")
for i in range(60):  # Poll for up to 60 seconds
    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        if receipt:
            if receipt['status'] == 1:
                print(f"✅ SUCCESS!")
                print()
                
                # Verify new state
                new_gc = kpan.functions.graduationOracle().call()
                new_graduating = kpan.functions.graduating().call()
                
                print(f"New controller: {new_gc}")
                print(f"New graduating flag: {new_graduating}")
                print()
                
                if new_gc == V2_CONTROLLER:
                    print("=" * 80)
                    print("✅ KPAN SUCCESSFULLY MIGRATED TO V2")
                    print("=" * 80)
                    print()
                    print(f"🎯 {kas_reserve:.2f} KAS can now graduate properly")
                else:
                    print("❌ Migration failed - controller didn't update")
                    exit(1)
            else:
                print("❌ Transaction reverted")
                exit(1)
            break
    except Exception:
        pass
    
    time.sleep(2)
    if (i + 1) % 10 == 0:
        print(f"  Still waiting... ({i+1}s)")
else:
    print("⚠️ Polling timeout - but transaction may still succeed")
    print(f"   Check manually: https://explorer.testnet.kasplextest.xyz/tx/{tx_hash.hex()}")
