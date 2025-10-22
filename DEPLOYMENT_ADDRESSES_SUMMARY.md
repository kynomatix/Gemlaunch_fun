# Gemlaunch.fun Smart Contract Deployment Addresses

**Network**: Kasplex zkEVM L2 Testnet  
**Chain ID**: 167012  
**Last Updated**: October 22, 2025

---

## 🚨 IMPORTANT: TokenFactory V2 Migration (October 2025)

### What Happened:
- **Bug Found**: TokenFactory V1 had a critical bug preventing graduation (line 165 architecture mismatch)
- **Fix Applied**: Changed line 165 to pass `graduationController` address instead of `graduationOracle`
- **Redeployed**: TokenFactory V2 deployed with fix on October 22, 2025
- **Impact**: All tokens created AFTER V2 deployment work correctly. Legacy tokens need migration.

### Version History:
- **V1** (❌ DEPRECATED): `0x2DDb083fCd62D27E9eE1F557B53140bD61F3009D` - Had graduation bug
- **V2** (✅ CURRENT): `0x39003ab4e8ad700F59bcfA082F73e68bc0477fDc` - Graduation fix applied

**⚠️ USE V2 FOR ALL NEW TOKENS**

---

## 📍 Current Production Addresses (V2)

### Core Platform Contracts

| Contract Name | Address | Version | Deployment Date |
|---------------|---------|---------|-----------------|
| **TokenFactory** | `0x39003ab4e8ad700F59bcfA082F73e68bc0477fDc` | V2 | Oct 22, 2025 |
| **VestingDeployer** | `0x319F9D08A9c1167770Fe037cb58e5097e287B9e7` | V2 | Oct 22, 2025 |
| **GraduationController** | `0x9416D5a5D61ec70C18D1FE1039f8026E29b4820e` | V1 | Oct 11, 2025 |
| **AirdropDistributor** | `0x86b83FE03cDa7456980364c929BB17CFA67E8495` | V1 | Oct 21, 2025 |

### Kaspa Finance DEX Integration (External)

| Contract Name | Address | Notes |
|---------------|---------|-------|
| **SwapRouter** | `0xDf88D478aF51C0AB616aFBfDD933c874e142858c` | Uniswap V3 compatible |
| **QuoterV2** | `0x3ACc31F8fe86E365604eAa6dDCbcB7fEba7a4c2B` | Price quotes |
| **WKAS** | `0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94` | Wrapped KAS |
| **NFT Position Manager** | `0x4E25637cF39822364b877F81B18c5B6CF0eeF589` | Liquidity positions |
| **Uniswap V3 Factory** | `0x1b72D7165a0D7256a4F197765C15bb70bC5D66A8` | Pool factory |

---

## 🔐 Platform Wallets

### Primary Wallet (Deployer)
- **Address**: `0xe281e4776FB5De20817D0bbC72B0C4b955565619`
- **Roles**: 
  - Owner
  - Treasury
  - Platform Development Wallet
  - Buyback Reserve
  - Kaspa Support
  - Community Rewards
  - Graduation Controller (temporary)

### Secondary Wallet (Oracle)
- **Address**: `0x5f837F62744D4d80Fc79C3A5346B4A228956914E`
- **Roles**:
  - Admin
  - Graduation Oracle
  - Airdrop Treasury
- **Type**: Derived from deployer wallet (controlled)

---

## 📂 Where These Addresses Are Documented

### 1. Deployment Configuration Files
- **`deployments/kasplex_testnet_factory.json`** - TokenFactory V2 & VestingDeployer V2
- **`deployments/kasplex_testnet_graduation.json`** - GraduationController & Kaspa Finance integration

### 2. Backend Code
- **`services/web3_service.py`** (Lines 27-35)
  - `TOKEN_FACTORY_ADDRESS`
  - `VESTING_DEPLOYER_ADDRESS`
  - `GRADUATION_CONTROLLER_ADDRESS`
  - `AIRDROP_DISTRIBUTOR_ADDRESS`
  - `KASPA_FINANCE_*` addresses

### 3. Documentation
- **`replit.md`** (Lines 41-45) - Smart Contracts (V2) section
- **`KASPA_FINANCE_DEX_INTEGRATION_PLAN.md`** - Full graduation system documentation
- **This file** (`DEPLOYMENT_ADDRESSES_SUMMARY.md`) - Comprehensive address reference

---

## 🔄 Migration Status

### Tokens Created with V2 (✅ Working)
- **GRAD655** (ID: 61) - Test token, graduation verified working
- All tokens created after October 22, 2025

### Legacy Tokens Created with V1 (⚠️ Needs Migration)
The following tokens were created before the V2 fix and will fail graduation:
- JAK (ID: unknown)
- RX (ID: unknown)
- KTAR (ID: 41)
- ZZING (ID: 44)
- HYPR (ID: 50)
- PXLS (ID: 47)
- SEE (ID: 53)
- GRUMP (ID: 55)
- KASB (ID: 37)
- Any other tokens created before Oct 22, 2025

**Migration Options**:
1. Leave as bonding curve only (no graduation)
2. Manual contract update (admin function)
3. Create migration script (Task 5.5 - pending)

---

## 🔍 How to Verify Token Version

### Check if a token was created with V2:

```python
from services.web3_service import get_web3_service

web3_service = get_web3_service()
token_address = "0x..." # Your token address

# Get the pool contract
pool = web3_service.get_bonding_pool_contract(token_address)

# Check graduationOracle setting
oracle_address = pool.functions.graduationOracle().call()

print(f"Graduation Oracle: {oracle_address}")

if oracle_address.lower() == "0x9416D5a5D61ec70C18D1FE1039f8026E29b4820e".lower():
    print("✅ Token created with V2 - Graduation will work")
else:
    print("❌ Token created with V1 - Graduation will fail")
```

### Expected Results:
- **V2 Tokens**: `graduationOracle` = GraduationController (`0x9416D5a5...`)
- **V1 Tokens**: `graduationOracle` = Oracle Wallet (`0x5f837F62...`)

---

## 📝 Deployment Transaction History

### TokenFactory V2 Deployment
- **Transaction**: `0x360dc9eb52f81a096f21366c71dc2d09becd67f17fd55c434d6f348575613089`
- **Block**: 8,723,584
- **Timestamp**: 2025-10-22T06:21:51.376Z
- **Deployer**: `0xe281e4776FB5De20817D0bbC72B0C4b955565619`

### GraduationController Deployment (Unchanged)
- **Transaction**: `0xcf516197a019329ba6c6e8262f67efb652bff9410bf02fa3fecd8d34c2770ca0`
- **Block**: 7,768,289
- **Timestamp**: 2025-10-11T05:14:29.870Z
- **Deployer**: `0xe281e4776FB5De20817D0bbC72B0C4b955565619`

---

## 🛠️ Developer Quick Reference

### When Creating New Tokens:
```javascript
// Frontend - Automatically uses V2
const factoryAddress = "0x39003ab4e8ad700F59bcfA082F73e68bc0477fDc";
```

### When Checking Graduation:
```python
# Backend - web3_service.py
GRADUATION_CONTROLLER_ADDRESS = "0x9416D5a5D61ec70C18D1FE1039f8026E29b4820e"

# Token's pool.graduationOracle() MUST equal GRADUATION_CONTROLLER_ADDRESS
# for graduation to work
```

### When Building DEX Integrations:
```python
# Backend - Phase 5 DEX endpoints
KASPA_FINANCE_SWAP_ROUTER = "0xDf88D478aF51C0AB616aFBfDD933c874e142858c"
KASPA_FINANCE_QUOTER_V2 = "0x3ACc31F8fe86E365604eAa6dDCbcB7fEba7a4c2B"
KASPA_FINANCE_WKAS = "0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94"
```

---

## ⚠️ Important Notes

1. **Always use TokenFactory V2** for new token deployments
2. **Legacy tokens (V1) cannot graduate** without manual intervention
3. **GraduationController address** never changed - only TokenFactory was updated
4. **Kaspa Finance addresses** are external contracts - we don't control them
5. **All V2 addresses are documented** in 3 places (config files, code, docs)

---

## 🔗 Related Documentation

- **Full Graduation System Documentation**: `KASPA_FINANCE_DEX_INTEGRATION_PLAN.md`
- **Critical Issues & Resolutions**: See "GRADUATION SYSTEM CRITICAL ISSUES" section in integration plan
- **Project Overview**: `replit.md`
- **Vesting Implementation**: `PRO_TOKEN_VESTING_SPECIFICATION_V2.md`
- **Smart Contract Source**: `contracts/TokenFactory.sol` (line 165 fix)

---

**Last Verified**: October 22, 2025  
**Network Status**: ✅ All systems operational  
**Latest Version**: TokenFactory V2 + Phase 5 DEX Integration
