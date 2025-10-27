#!/usr/bin/env python3
"""Quick verification that $GNT is using the latest contracts"""

from web3 import Web3

RPC_URL = "https://rpc.kasplextest.xyz"
GNT = "0x1b2ae2a378ca7ecdc210363cd3381fd5c1825a9c"

# Expected addresses
EXPECTED_TF_V10 = "0xCD8e8F442E187B811130F8924B91a8F3445Ffb21"
EXPECTED_GC_V7 = "0xeb753f81F9beD4B6ea27381476a20d71ae496Cd1"

ABI = [
    {"inputs": [], "name": "tokenFactory", "outputs": [{"type": "address"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "graduationController", "outputs": [{"type": "address"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "name", "outputs": [{"type": "string"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "symbol", "outputs": [{"type": "string"}], "stateMutability": "view", "type": "function"},
]

w3 = Web3(Web3.HTTPProvider(RPC_URL))
pool = w3.eth.contract(address=Web3.to_checksum_address(GNT), abi=ABI)

print("\n" + "="*80)
print("🔍 VERIFYING $GNT CONTRACT CONFIGURATION")
print("="*80 + "\n")

name = pool.functions.name().call()
symbol = pool.functions.symbol().call()
factory = pool.functions.tokenFactory().call()
gc = pool.functions.graduationController().call()

print(f"Token: {name} (${symbol})")
print(f"Address: {GNT}\n")

# Check TokenFactory
tf_correct = factory.lower() == EXPECTED_TF_V10.lower()
print(f"TokenFactory: {factory}")
print(f"Expected:     {EXPECTED_TF_V10}")
print(f"{'✅ CORRECT - Using V10!' if tf_correct else '❌ WRONG - Not using V10!'}\n")

# Check GraduationController
gc_correct = gc.lower() == EXPECTED_GC_V7.lower()
print(f"GraduationController: {gc}")
print(f"Expected:             {EXPECTED_GC_V7}")
print(f"{'✅ CORRECT - Using V7!' if gc_correct else '❌ WRONG - Not using V7!'}\n")

# Final verdict
print("="*80)
if tf_correct and gc_correct:
    print("🎉 SUCCESS! $GNT is using the latest contracts (V10 + V7)")
    print("✅ Ready to fund and test graduation!")
else:
    print("❌ PROBLEM! $GNT is NOT using the latest contracts")
    print("⚠️  Do NOT fund - create a new token instead")
print("="*80 + "\n")
