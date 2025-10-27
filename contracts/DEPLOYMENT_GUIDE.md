# Contract Deployment Guide

## CRITICAL RULES

1. **ALWAYS update `deployed_addresses.json` FIRST before deploying**
2. **NEVER copy-paste addresses manually** - read from deployed_addresses.json
3. **VERIFY all dependencies** before marking deployment complete
4. **TEST with a new token** after any contract deployment

---

## Contract Dependency Map

### GraduationController
**References (set in constructor):**
- `kaspaFinanceFactory` - KaspaFinance.Factory
- `kaspaFinancePositionManager` - KaspaFinance.PositionManager  
- `kaspaFinanceWKAS` - KaspaFinance.WKAS
- `graduationOracle` - wallets.Oracle
- `tokenFactory` - TokenFactory.address
- `treasury` - wallets.Treasury

**Referenced by:**
- TokenFactory (constructor) - hardcoded into every pool it creates
- web3_service.py - GRADUATION_CONTROLLER_ADDRESS constant

**Constructor order:**
```solidity
constructor(
    address _kaspaFinanceFactory,      // 1
    address _kaspaFinancePositionManager, // 2
    address _kaspaFinanceWKAS,         // 3
    address _graduationOracle,         // 4
    address _tokenFactory,             // 5
    address _treasury                  // 6
)
```

---

### TokenFactory
**References (set in constructor):**
- `graduationController` - GraduationController.address
- `vestingDeployer` - VestingDeployer.address (auto-deploys if not provided)
- `graduationOracle` - wallets.Oracle

**Referenced by:**
- GraduationController (constructor) - validates pools came from this factory
- web3_service.py - TOKEN_FACTORY_ADDRESS constant
- Every BondingCurvePool created (immutable reference to factory)

---

### BondingCurvePool (created by TokenFactory)
**References (set at creation):**
- `graduationController` - from TokenFactory's graduationController (IMMUTABLE)
- `tokenFactory` - from TokenFactory that created it (IMMUTABLE)

**KEY ISSUE:** Pool's graduationController is **HARDCODED** at deployment. If TokenFactory references wrong GC, all pools are permanently broken.

---

### VestingDeployer
**References:**
- None (standalone helper)

**Referenced by:**
- TokenFactory (constructor) - used to deploy vesting contracts

---

## Deployment Checklist

### When Deploying GraduationController:
- [ ] Verify all 6 constructor params match deployed_addresses.json
- [ ] Note: `tokenFactory` should point to NEW TokenFactory (deploy TF after GC)
- [ ] Update deployed_addresses.json with new GC address
- [ ] **MUST deploy new TokenFactory next** (old TF still points to old GC)

### When Deploying TokenFactory:
- [ ] Verify graduationController param matches deployed_addresses.json
- [ ] Verify graduationOracle param matches deployed_addresses.json  
- [ ] Update deployed_addresses.json with new TF address
- [ ] Update web3_service.py TOKEN_FACTORY_ADDRESS constant
- [ ] **Go back and verify GC.tokenFactory matches this new TF address**
- [ ] Test: Create a new token and verify it can initiate graduation

### When Deploying VestingDeployer:
- [ ] Update deployed_addresses.json
- [ ] If deploying new TokenFactory, include this VD address in constructor

---

## Current State Assessment

### Active Contracts (WORKING):
- ✅ GraduationController V5: `0xbC90b2a362Af9fdF2067EDeE5F166CF88fbb39Ac`
  - Correct configuration
  - Ready to use

### Broken Contracts (DO NOT USE):
- ❌ TokenFactory V6: `0x222B82584B445Fab6AbBb1588855e3d9F93476b1`  
  - References GC V4 (broken)
  - All pools created by this are stuck

### Next Deployment Required:
- **TokenFactory V7** - Reference GC V5, deploy fresh VestingDeployer

---

## Post-Deployment Validation Script

After deploying TokenFactory, run:

```python
python3 << 'EOF'
import json
from web3 import Web3

w3 = Web3(Web3.HTTPProvider('https://rpc.kasplextest.xyz'))

# Load registry
with open('contracts/deployed_addresses.json') as f:
    registry = json.load(f)

# Load ABIs
with open('artifacts/contracts/TokenFactory.sol/TokenFactory.json') as f:
    tf_abi = json.load(f)['abi']
with open('artifacts/contracts/GraduationControllerV3.sol/GraduationControllerV3.json') as f:
    gc_abi = json.load(f)['abi']

# Verify TokenFactory
tf_addr = registry['contracts']['TokenFactory']['address']
tf = w3.eth.contract(address=Web3.to_checksum_address(tf_addr), abi=tf_abi)

gc_in_tf = tf.functions.graduationController().call()
expected_gc = registry['contracts']['GraduationController']['address']

print(f"TokenFactory.graduationController: {gc_in_tf}")
print(f"Expected (from registry):          {expected_gc}")
print(f"Match: {gc_in_tf.lower() == expected_gc.lower()}")

# Verify GraduationController
gc = w3.eth.contract(address=Web3.to_checksum_address(expected_gc), abi=gc_abi)

tf_in_gc = gc.functions.tokenFactory().call()

print(f"\nGraduationController.tokenFactory: {tf_in_gc}")
print(f"Expected (from registry):          {tf_addr}")
print(f"Match: {tf_in_gc.lower() == tf_addr.lower()}")

if (gc_in_tf.lower() == expected_gc.lower() and 
    tf_in_gc.lower() == tf_addr.lower()):
    print("\n✅ ALL ADDRESSES MATCH - Safe to deploy tokens")
else:
    print("\n❌ ADDRESS MISMATCH - DO NOT DEPLOY TOKENS")
EOF
```
