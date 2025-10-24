"""Verify V2 migration status - run this to check if KPAN fix succeeded"""
from web3 import Web3
import json

w3 = Web3(Web3.HTTPProvider("https://rpc.kasplextest.xyz"))

with open('artifacts/contracts/TokenFactory.sol/TokenFactory.json') as f:
    factory_abi = json.load(f)['abi']
with open('artifacts/contracts/BondingCurvePool.sol/BondingCurvePool.json') as f:
    pool_abi = json.load(f)['abi']

V2 = '0x147E3Ecbe189bb301175001706ff1f44dF33B3ab'

factory = w3.eth.contract(address='0x39003ab4e8ad700F59bcfA082F73e68bc0477fDc', abi=factory_abi)
kpan = w3.eth.contract(address=Web3.to_checksum_address('0xc33b27a9d68cb3e8b83dcba031da1a7cb4e29a98'), abi=pool_abi)

print("=" * 70)
print("V2 MIGRATION STATUS")
print("=" * 70)
print()

# Check factory
factory_gc = factory.functions.graduationController().call()
factory_ok = factory_gc == V2

print("TokenFactory:")
print(f"  Controller: {factory_gc}")
print(f"  Status: {'✅ V2' if factory_ok else '❌ V1'}")
print()

# Check KPAN
kpan_gc = kpan.functions.graduationOracle().call()
kpan_graduating = kpan.functions.graduating().call()
kpan_ok = kpan_gc == V2

print("KPAN Token:")
print(f"  Controller: {kpan_gc}")
print(f"  Status: {'✅ V2' if kpan_ok else '❌ V1'}")
print(f"  Graduating: {kpan_graduating}")
print()

print("=" * 70)
if factory_ok and kpan_ok:
    print("✅ MIGRATION COMPLETE - READY TO TEST")
    print()
    print("New tokens will use V2 controller")
    print("KPAN can now graduate properly")
elif factory_ok:
    print("⚠️ PARTIAL MIGRATION")
    print()
    print("✅ New tokens work (Factory → V2)")
    print("❌ KPAN stuck (needs manual fix)")
    print()
    print("Run: python3 scripts/fix_kpan_retry.py")
else:
    print("❌ MIGRATION FAILED")
    print()
    print("Contact support - factory not on V2")
print("=" * 70)
