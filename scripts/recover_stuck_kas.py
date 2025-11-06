"""
Emergency KAS Recovery from GraduationController V6
Recovers KAS from failed graduations ($MLEAF, $CHIM)
"""

from services.web3_service import Web3Service
from web3 import Web3
import json
import os

# Initialize Web3
w3s = Web3Service()

GC_V6 = "0xBbfdF7341aaF104D259876972844EBF9795b9C4C"

# Pools with stuck KAS
POOLS_TO_RECOVER = [
    ("MLEAF", "0x7E22EEECEF429cAc88C4aa01381Ff2F865386587", 891.0),
    ("CHIM", "0x8c4102Cce3B6D9461eF5aA7A845172DD2F479ecA", 920.7),
]

print("\n" + "="*80)
print("🚨 EMERGENCY KAS RECOVERY FROM GC V6")
print("="*80 + "\n")

# Load GC contract
with open('artifacts/contracts/GraduationControllerV3.sol/GraduationControllerV3.json') as f:
    gc_data = json.load(f)
    gc_abi = gc_data['abi']

gc = w3s.w3.eth.contract(address=Web3.to_checksum_address(GC_V6), abi=gc_abi)

# Get owner
owner = gc.functions.owner().call()
print(f"📋 Contract Info:")
print(f"   GC V6: {GC_V6}")
print(f"   Owner: {owner}")
print()

# Check if we're using the right account
deployer_address = w3s.deployer_account.address
print(f"🔑 Deployer (Treasury): {deployer_address}")

if deployer_address.lower() != owner.lower():
    print(f"❌ ERROR: Deployer is not the owner!")
    print(f"   You need to use the Treasury wallet to recover funds.")
    exit(1)

print("✅ Deployer IS the owner - can execute recovery!")
print()

# Show what will be recovered
total_kas = sum(kas for _, _, kas in POOLS_TO_RECOVER)
print(f"💰 RECOVERY PLAN:")
print(f"   Total KAS to recover: {total_kas:.4f} KAS (~${total_kas * 0.05762:.2f} USD)")
print()

for symbol, pool_addr, kas_amount in POOLS_TO_RECOVER:
    print(f"   ${symbol}: {kas_amount:.4f} KAS")

print()
choice = input("🚀 Proceed with recovery? (yes/no): ")

if choice.lower() != 'yes':
    print("❌ Recovery cancelled.")
    exit(0)

print()
print("="*80)
print("EXECUTING RECOVERY")
print("="*80)

# Recovery method: emergencyReturnGraduationFunds(poolAddress)
# This returns KAS to the pool, then pool owner can withdraw

for symbol, pool_addr, kas_amount in POOLS_TO_RECOVER:
    print(f"\n🔄 Recovering ${symbol}...")
    
    try:
        pool_checksum = Web3.to_checksum_address(pool_addr)
        
        # Build transaction
        tx = gc.functions.emergencyReturnGraduationFunds(pool_checksum).build_transaction({
            'from': deployer_address,
            'gas': 500_000,
            'gasPrice': w3s.w3.eth.gas_price,
            'nonce': w3s.w3.eth.get_transaction_count(deployer_address),
        })
        
        # Sign with deployer (Treasury)
        signed = w3s.w3.eth.account.sign_transaction(tx, os.environ.get('DEPLOYER_PRIVATE_KEY'))
        
        # Send
        tx_hash = w3s.w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"   📡 TX: {tx_hash.hex()}")
        
        # Wait for confirmation
        receipt = w3s.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        if receipt['status'] == 1:
            print(f"   ✅ SUCCESS! {kas_amount:.4f} KAS returned to pool")
        else:
            print(f"   ❌ FAILED! Status: {receipt['status']}")
            
    except Exception as e:
        print(f"   ❌ ERROR: {e}")

print()
print("="*80)
print("✅ RECOVERY COMPLETE!")
print("="*80)
print()
print("💡 Next steps:")
print("   1. KAS has been returned to each pool")
print("   2. Pool creators can now withdraw via creatorWithdraw()")
print("   3. Or you can withdraw from pools using the deployer wallet")
