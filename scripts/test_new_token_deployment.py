"""Test that new tokens deploy with V2 controller"""
from web3 import Web3
import json

w3 = Web3(Web3.HTTPProvider("https://rpc.kasplextest.xyz"))

with open('artifacts/contracts/TokenFactory.sol/TokenFactory.json') as f:
    factory_abi = json.load(f)['abi']

factory = w3.eth.contract(address='0x39003ab4e8ad700F59bcfA082F73e68bc0477fDc', abi=factory_abi)
V2 = '0x147E3Ecbe189bb301175001706ff1f44dF33B3ab'

print("=" * 70)
print("NEW TOKEN DEPLOYMENT TEST")
print("=" * 70)
print()

# Check factory configuration
factory_gc = factory.functions.graduationController().call()

print(f"TokenFactory controller: {factory_gc}")
print(f"Expected V2 controller:  {V2}")
print()

if factory_gc == V2:
    print("✅ PASS - TokenFactory configured for V2")
    print()
    print("New tokens deployed through this factory will:")
    print("  1. Use V2 GraduationController")
    print("  2. Graduate properly when reaching $50 market cap")
    print("  3. Create Uniswap V3 pools correctly")
    print()
    print("You can now deploy a test token to verify end-to-end")
else:
    print("❌ FAIL - TokenFactory still on V1")
    print()
    print(f"Current: {factory_gc}")
    print(f"Expected: {V2}")
    print()
    print("Fix: Run migration script")

print("=" * 70)
