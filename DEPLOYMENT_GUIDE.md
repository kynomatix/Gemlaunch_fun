# TokenFactory Deployment Guide

## Overview

This guide explains how to deploy the TokenFactory contract with **controlled addresses only**. The deployment script ensures that all constructor parameters use addresses we have private keys for, making the contract fully operable.

## 🔐 Wallet Control Structure

### Testnet Deployment Uses 2 Controlled Wallets:

#### **Primary Wallet (Deployer)**
- **Environment Variable**: `DEPLOYER_PRIVATE_KEY`
- **Controls**:
  - `treasury` - Platform fee collector
  - `platformDevelopmentWallet` - Platform development fund
  - `buybackReserveWallet` - Token buyback reserves
  - `kaspaNetworkSupportWallet` - Kaspa network support fund
  - `communityRewardsWallet` - Community rewards fund
  - `graduationController` - Temporary (update after GraduationController deployed)
  - Contract `owner` - Admin control of TokenFactory

#### **Secondary Wallet (Admin/Oracle)**
- **Environment Variable**: `SECONDARY_PRIVATE_KEY` (optional)
- **Derivation**: If not provided, derived deterministically from deployer key
- **Controls**:
  - `admin` - Administrative functions
  - `graduationOracle` - Oracle role for graduation decisions
  - `airdropTreasury` - Airdrop distribution fund

## 📋 Contract Validation Constraints

The TokenFactory constructor enforces these constraints:

```solidity
require(_treasury != _admin, "Treasury cannot be admin");
require(_treasury != _graduationOracle, "Treasury cannot be oracle");
require(_airdropTreasury != _platformDevelopmentWallet, "Duplicate wallets");
```

**Our 2-wallet strategy satisfies all constraints:**
- ✅ treasury (primary) ≠ admin (secondary)
- ✅ treasury (primary) ≠ graduationOracle (secondary)
- ✅ airdropTreasury (secondary) ≠ platformDevelopmentWallet (primary)

## 🚀 Deployment Instructions

### Prerequisites

1. **Fund the deployer wallet** with testnet KAS:
   ```bash
   # Check wallet status
   npx hardhat run scripts/check_wallet.js --network kasplex_testnet
   ```

2. **Set environment variables** in `.env`:
   ```bash
   DEPLOYER_PRIVATE_KEY=0x...  # Required
   SECONDARY_PRIVATE_KEY=0x... # Optional - will derive if not provided
   ```

### Deployment Steps

1. **Deploy TokenFactory**:
   ```bash
   npx hardhat run scripts/deploy_factory.js --network kasplex_testnet
   ```

2. **Review deployment output** for wallet addresses and roles

3. **Deploy GraduationController** (separate script)

4. **Update graduationController address**:
   ```javascript
   const factory = await ethers.getContractAt("TokenFactory", factoryAddress);
   await factory.setGraduationController(graduationControllerAddress);
   ```

## 🔑 Secondary Wallet Management

### Option 1: Use Environment Variable (Recommended for Production)
```bash
# .env
SECONDARY_PRIVATE_KEY=0x1234567890abcdef...
```

### Option 2: Use Derived Wallet (Default for Testnet)
If `SECONDARY_PRIVATE_KEY` is not set, the script automatically derives a secondary wallet:

```javascript
// Derivation method (deterministic)
const derivedKey = keccak256(
  concat([
    toUtf8Bytes("GEMLAUNCH_SECONDARY_WALLET"),
    getBytes(DEPLOYER_PRIVATE_KEY)
  ])
);
```

**To recover the derived secondary wallet:**
```javascript
import { ethers } from "hardhat";

const deployerKey = process.env.DEPLOYER_PRIVATE_KEY;
const derivedKey = ethers.keccak256(
  ethers.concat([
    ethers.toUtf8Bytes("GEMLAUNCH_SECONDARY_WALLET"),
    ethers.getBytes(deployerKey)
  ])
);

const secondaryWallet = new ethers.Wallet(derivedKey);
console.log("Secondary Address:", secondaryWallet.address);
console.log("Secondary Private Key:", derivedKey);
```

## 📊 Deployment Output

The deployment script provides:

1. **Wallet Information**
   - Primary wallet address and balance
   - Secondary wallet address and derivation method
   - Role assignments for each wallet

2. **Constructor Parameters Table**
   - All 9 constructor parameters
   - Which wallet controls each parameter
   - Validation status

3. **Deployment Summary**
   - Contract address
   - Transaction hash
   - Block number
   - Gas used

4. **Wallet Control Summary**
   - Private key locations
   - Recovery instructions

5. **Next Steps**
   - Contract verification command
   - GraduationController deployment
   - Configuration updates

## 📁 Configuration Files

### `config/wallet_config.json`
Stores the wallet strategy and role assignments:

```json
{
  "testnet": {
    "wallets": {
      "primary": {
        "address": "0x...",
        "envVar": "DEPLOYER_PRIVATE_KEY",
        "roles": ["treasury", "platformDevelopmentWallet", ...]
      },
      "secondary": {
        "address": "USE_ENV_VAR_OR_DERIVE",
        "envVar": "SECONDARY_PRIVATE_KEY",
        "roles": ["admin", "graduationOracle", "airdropTreasury"]
      }
    }
  }
}
```

### `deployments/{network}_factory.json`
Stores deployment results:

```json
{
  "network": "kasplex_testnet",
  "tokenFactory": "0x...",
  "wallets": {
    "primary": { "address": "0x...", "roles": [...] },
    "secondary": { 
      "address": "0x...", 
      "controlled": true,
      "derivedFromDeployer": true 
    }
  },
  "constructorParams": {...},
  "deploymentTx": "0x...",
  "timestamp": "2025-10-11T..."
}
```

## 🔒 Security Considerations

### ✅ SECURE - What We Do:
- ✅ All addresses are **controlled** (we have private keys)
- ✅ Secondary wallet is **deterministically derived** or from env var
- ✅ **No random address generation** (previous security issue fixed)
- ✅ Pre-deployment validation of all constraints
- ✅ Configuration stored in version control (addresses only, no keys)
- ✅ Private keys stored in `.env` (gitignored)

### ⚠️ Important Notes:
1. **Derived Secondary Wallet**: If you lose the deployer private key, you also lose access to the derived secondary wallet. Always backup `DEPLOYER_PRIVATE_KEY`.

2. **Separate Keys for Production**: For mainnet, use separate hardware wallets for primary and secondary roles. Set both `DEPLOYER_PRIVATE_KEY` and `SECONDARY_PRIVATE_KEY` explicitly.

3. **graduationController Update**: The initial deployment uses deployer address as a placeholder. Update it after deploying GraduationController:
   ```javascript
   await tokenFactory.setGraduationController(graduationControllerAddress);
   ```

## 🧪 Testing Deployment

After deployment, verify the configuration:

```javascript
const factory = await ethers.getContractAt("TokenFactory", factoryAddress);

console.log("Owner:", await factory.owner());
console.log("Treasury:", await factory.treasury());
console.log("Admin:", await factory.admin());
console.log("Graduation Oracle:", await factory.graduationOracle());
console.log("Airdrop Treasury:", await factory.airdropTreasury());
console.log("Platform Dev Wallet:", await factory.platformDevelopmentWallet());
```

**Expected Result:**
- Owner = Primary wallet ✓
- Treasury = Primary wallet ✓
- Admin = Secondary wallet ✓
- Graduation Oracle = Secondary wallet ✓
- Airdrop Treasury = Secondary wallet ✓
- Platform Dev Wallet = Primary wallet ✓

## 🚨 Troubleshooting

### Error: "Treasury cannot be admin"
- **Cause**: Same address used for treasury and admin
- **Fix**: Ensure secondary wallet is different from primary wallet

### Error: "DEPLOYER_PRIVATE_KEY not found"
- **Cause**: Environment variable not set
- **Fix**: Add to `.env` file: `DEPLOYER_PRIVATE_KEY=0x...`

### Error: "Deployer wallet has no KAS"
- **Cause**: No funds in deployer wallet
- **Fix**: Get testnet KAS from faucet

### Warning: Secondary wallet has 0 balance
- **Info**: This is normal. The secondary wallet only needs balance if it will perform transactions. For receiving funds (airdropTreasury), no balance is needed.

## 📚 Related Documentation

- `contracts/TokenFactory.sol` - Smart contract source
- `config/wallet_config.json` - Wallet configuration
- `SMART_CONTRACT_IMPLEMENTATION.md` - Contract architecture
- `DEPLOYMENT_SUMMARY.md` - High-level deployment overview

## ✅ Deployment Checklist

Before deploying:
- [ ] `DEPLOYER_PRIVATE_KEY` set in `.env`
- [ ] Deployer wallet funded with testnet KAS
- [ ] Reviewed `config/wallet_config.json` configuration
- [ ] Understood which wallet controls which role

After deploying:
- [ ] Saved deployment output (contract address)
- [ ] Verified all roles assigned correctly
- [ ] Backed up `deployments/{network}_factory.json`
- [ ] Noted secondary wallet address and derivation method
- [ ] Ready to deploy GraduationController
- [ ] Planned to update graduationController address

---

**Last Updated**: October 11, 2025
**Status**: ✅ Fixed - All addresses now controlled, no random generation
