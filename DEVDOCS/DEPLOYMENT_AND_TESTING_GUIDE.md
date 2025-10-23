# GraduationController V2 - Deployment & Testing Guide

**Version**: 2.0.0  
**Date**: October 23, 2025  
**Status**: Ready for Testnet Deployment

---

## TABLE OF CONTENTS

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Contract Deployment Guide](#contract-deployment-guide)
3. [Testing Strategy](#testing-strategy)
4. [Integration with Backend](#integration-with-backend)
5. [Verification Procedures](#verification-procedures)
6. [Rollback Plan](#rollback-plan)
7. [Production Deployment](#production-deployment)

---

## 1. PRE-DEPLOYMENT CHECKLIST

### Dependencies Check
- [ ] OpenZeppelin Contracts v5.0.0+ installed
- [ ] Hardhat or Foundry configured for Kaspa testnet
- [ ] All interfaces compiled without errors
- [ ] Gas reporter plugin configured

### Environment Configuration
```bash
# .env file required variables
KASPA_TESTNET_RPC=<testnet_rpc_url>
DEPLOYER_PRIVATE_KEY=<deployer_wallet_private_key>
ETHERSCAN_API_KEY=<kaspa_explorer_api_key>

# Contract addresses (Kaspa Finance Testnet)
UNISWAP_V3_FACTORY=0x1b72D7165a0D7256a4F197765C15bb70bC5D66A8
UNISWAP_V3_POSITION_MANAGER=0x4E25637cF39822364b877F81B18c5B6CF0eeF589
WKAS_ADDRESS=0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94
TOKEN_FACTORY=<your_token_factory_address>
GRADUATION_ORACLE=<your_backend_oracle_address>
```

### Code Audit Checks
- [x] All critical issues from audit resolved
- [x] All high severity issues resolved
- [x] Medium severity issues addressed
- [x] Low severity issues documented
- [ ] External security audit completed (recommended)
- [ ] Code review by 2+ developers

### Contract Compilation
```bash
# Compile contracts
npx hardhat compile

# Or with Foundry
forge build

# Verify no compilation warnings
# Check contract size (should be < 24KB)
```

---

## 2. CONTRACT DEPLOYMENT GUIDE

### Step 1: Deploy to Testnet

**Hardhat Deployment Script** (`scripts/deployGraduationV2.js`):

```javascript
const hre = require("hardhat");

async function main() {
    console.log("Deploying GraduationController V2...");
    
    // Get constructor parameters
    const factory = process.env.UNISWAP_V3_FACTORY;
    const positionManager = process.env.UNISWAP_V3_POSITION_MANAGER;
    const wkas = process.env.WKAS_ADDRESS;
    const oracle = process.env.GRADUATION_ORACLE;
    const tokenFactory = process.env.TOKEN_FACTORY;
    
    // Validate addresses
    if (!factory || !positionManager || !wkas || !oracle || !tokenFactory) {
        throw new Error("Missing required environment variables");
    }
    
    console.log("Constructor parameters:");
    console.log("- Factory:", factory);
    console.log("- Position Manager:", positionManager);
    console.log("- WKAS:", wkas);
    console.log("- Oracle:", oracle);
    console.log("- Token Factory:", tokenFactory);
    
    // Deploy
    const GraduationController = await hre.ethers.getContractFactory("GraduationController");
    const controller = await GraduationController.deploy(
        factory,
        positionManager,
        wkas,
        oracle,
        tokenFactory
    );
    
    await controller.waitForDeployment();
    
    const address = await controller.getAddress();
    console.log("\n✅ GraduationController V2 deployed to:", address);
    
    // Verify immutable variables
    console.log("\nVerifying deployment...");
    const factoryCheck = await controller.kaspaFinanceFactory();
    const pmCheck = await controller.kaspaFinancePositionManager();
    const wkasCheck = await controller.kaspaFinanceWKAS();
    const oracleCheck = await controller.graduationOracle();
    const version = await controller.VERSION();
    
    console.log("- Factory:", factoryCheck, factoryCheck === factory ? "✅" : "❌");
    console.log("- Position Manager:", pmCheck, pmCheck === positionManager ? "✅" : "❌");
    console.log("- WKAS:", wkasCheck, wkasCheck === wkas ? "✅" : "❌");
    console.log("- Oracle:", oracleCheck, oracleCheck === oracle ? "✅" : "❌");
    console.log("- Version:", version);
    
    // Save deployment info
    const deploymentInfo = {
        network: hre.network.name,
        address: address,
        deployer: (await hre.ethers.getSigners())[0].address,
        timestamp: new Date().toISOString(),
        version: version,
        constructorArgs: [factory, positionManager, wkas, oracle, tokenFactory]
    };
    
    const fs = require("fs");
    fs.writeFileSync(
        `deployments/GraduationControllerV2_${hre.network.name}.json`,
        JSON.stringify(deploymentInfo, null, 2)
    );
    
    console.log("\n💾 Deployment info saved to deployments/");
    
    return address;
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
```

**Run Deployment**:
```bash
npx hardhat run scripts/deployGraduationV2.js --network kaspaTestnet
```

### Step 2: Verify Contract on Explorer

```bash
npx hardhat verify --network kaspaTestnet \
    <DEPLOYED_ADDRESS> \
    "0x1b72D7165a0D7256a4F197765C15bb70bC5D66A8" \
    "0x4E25637cF39822364b877F81B18c5B6CF0eeF589" \
    "0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94" \
    "<ORACLE_ADDRESS>" \
    "<TOKEN_FACTORY_ADDRESS>"
```

### Step 3: Initial Configuration

After deployment, configure the contract:

```javascript
// Set graduation parameters (if different from defaults)
await controller.setGraduationParams(
    500,    // 5% slippage
    300,    // 5 minute deadline
    100     // 1% max price deviation
);

// Verify settings
const slippage = await controller.graduationSlippageBps();
const deadline = await controller.graduationDeadlineSeconds();
const maxDeviation = await controller.maxPriceDeviationBps();

console.log("Configuration:");
console.log("- Slippage:", slippage.toString(), "bps");
console.log("- Deadline:", deadline.toString(), "seconds");
console.log("- Max Price Deviation:", maxDeviation.toString(), "bps");
```

---

## 3. TESTING STRATEGY

### Unit Tests

**Test File** (`test/GraduationControllerV2.test.js`):

```javascript
const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("GraduationController V2", function() {
    let controller;
    let factory;
    let positionManager;
    let wkas;
    let tokenFactory;
    let owner;
    let oracle;
    let user;
    
    beforeEach(async function() {
        [owner, oracle, user] = await ethers.getSigners();
        
        // Deploy mock contracts
        const MockFactory = await ethers.getContractFactory("MockUniswapV3Factory");
        factory = await MockFactory.deploy();
        
        const MockPM = await ethers.getContractFactory("MockNonfungiblePositionManager");
        positionManager = await MockPM.deploy();
        
        const MockWKAS = await ethers.getContractFactory("MockWKAS");
        wkas = await MockWKAS.deploy();
        
        const MockTokenFactory = await ethers.getContractFactory("MockTokenFactory");
        tokenFactory = await MockTokenFactory.deploy();
        
        // Deploy GraduationController
        const GraduationController = await ethers.getContractFactory("GraduationController");
        controller = await GraduationController.deploy(
            await factory.getAddress(),
            await positionManager.getAddress(),
            await wkas.getAddress(),
            oracle.address,
            await tokenFactory.getAddress()
        );
    });
    
    describe("Deployment", function() {
        it("Should set correct immutable addresses", async function() {
            expect(await controller.kaspaFinanceFactory()).to.equal(await factory.getAddress());
            expect(await controller.kaspaFinancePositionManager()).to.equal(await positionManager.getAddress());
            expect(await controller.kaspaFinanceWKAS()).to.equal(await wkas.getAddress());
        });
        
        it("Should set correct oracle", async function() {
            expect(await controller.graduationOracle()).to.equal(oracle.address);
        });
        
        it("Should have correct version", async function() {
            expect(await controller.VERSION()).to.equal("2.0.0");
        });
        
        it("Should set default parameters", async function() {
            expect(await controller.graduationSlippageBps()).to.equal(500);
            expect(await controller.graduationDeadlineSeconds()).to.equal(300);
            expect(await controller.maxPriceDeviationBps()).to.equal(100);
        });
    });
    
    describe("Pool Creation", function() {
        it("Should create pool when it doesn't exist", async function() {
            // Test implementation
        });
        
        it("Should use existing pool when it exists", async function() {
            // Test implementation
        });
        
        it("Should emit PoolCreated event", async function() {
            // Test implementation
        });
    });
    
    describe("Price Calculation", function() {
        it("Should calculate correct sqrtPriceX96 for token < WKAS", async function() {
            // Test with KTR example:
            // kasReserve = 1131177000000000000000 (1131.177 KAS)
            // tokenReserve = 574620000000000000000 (574.62 tokens)
            // Expected price = 1.9686 KAS per token
            // Expected sqrtPriceX96 ≈ 111161266831013092294972669952
        });
        
        it("Should calculate correct sqrtPriceX96 for WKAS < token", async function() {
            // Test with reversed token ordering
        });
        
        it("Should revert with zero reserves", async function() {
            // Test error handling
        });
    });
    
    describe("Pool Initialization", function() {
        it("Should initialize pool with correct price", async function() {
            // Test implementation
        });
        
        it("Should skip initialization if pool already initialized", async function() {
            // Test implementation
        });
        
        it("Should validate price deviation on pre-initialized pool", async function() {
            // Test implementation
        });
        
        it("Should revert if price deviation too high", async function() {
            // Test implementation
        });
    });
    
    describe("Liquidity Minting", function() {
        it("Should mint full-range liquidity position", async function() {
            // Test implementation
        });
        
        it("Should respect slippage parameters", async function() {
            // Test implementation
        });
        
        it("Should revert if slippage exceeded", async function() {
            // Test implementation
        });
        
        it("Should revert if no liquidity minted", async function() {
            // Test implementation
        });
    });
    
    describe("Refund Mechanism", function() {
        it("Should refund excess tokens to pool", async function() {
            // Test implementation
        });
        
        it("Should unwrap and refund excess WKAS as KAS", async function() {
            // Test implementation
        });
    });
    
    describe("Access Control", function() {
        it("Should only allow oracle to initiate graduation", async function() {
            await expect(
                controller.connect(user).initiateGraduation(user.address)
            ).to.be.revertedWithCustomError(controller, "OnlyOracle");
        });
        
        it("Should only allow oracle to complete graduation", async function() {
            await expect(
                controller.connect(user).completeGraduation(user.address)
            ).to.be.revertedWithCustomError(controller, "OnlyOracle");
        });
        
        it("Should only allow owner to collect fees", async function() {
            await expect(
                controller.connect(user).collectFees(user.address)
            ).to.be.revertedWithCustomError(controller, "OwnableUnauthorizedAccount");
        });
    });
    
    describe("Emergency Functions", function() {
        it("Should allow owner to cancel graduation", async function() {
            // Test implementation
        });
        
        it("Should allow owner to emergency withdraw", async function() {
            // Test implementation
        });
        
        it("Should prevent withdrawing graduated tokens", async function() {
            // Test implementation
        });
    });
    
    describe("Configuration", function() {
        it("Should update graduation parameters", async function() {
            await controller.setGraduationParams(1000, 600, 200);
            expect(await controller.graduationSlippageBps()).to.equal(1000);
            expect(await controller.graduationDeadlineSeconds()).to.equal(600);
            expect(await controller.maxPriceDeviationBps()).to.equal(200);
        });
        
        it("Should revert with invalid parameters", async function() {
            await expect(
                controller.setGraduationParams(0, 300, 100) // Too low slippage
            ).to.be.revertedWithCustomError(controller, "InvalidParameters");
        });
    });
    
    describe("View Functions", function() {
        it("Should return correct graduation info", async function() {
            // Test implementation
        });
        
        it("Should return correct batch graduation info", async function() {
            // Test implementation
        });
    });
    
    describe("Events", function() {
        it("Should emit all graduation events", async function() {
            // Test all events are emitted correctly
        });
    });
    
    describe("Gas Usage", function() {
        it("Should use reasonable gas for initiation", async function() {
            // Target: < 200k gas
        });
        
        it("Should use reasonable gas for completion", async function() {
            // Target: < 950k gas total
        });
    });
});
```

**Run Tests**:
```bash
npx hardhat test
npx hardhat test --network hardhat --gas-reporter
```

### Integration Tests

**Create Test Token and Graduate**:

```javascript
// scripts/testGraduation.js
async function testFullGraduation() {
    const [deployer] = await ethers.getSigners();
    
    // 1. Create a test token via TokenFactory
    console.log("1. Creating test token...");
    const tokenFactory = await ethers.getContractAt("TokenFactory", TOKEN_FACTORY_ADDRESS);
    const tx = await tokenFactory.createToken(
        "Test Token",
        "TEST",
        "ipfs://metadata",
        0, // No reserved supply
        { value: ethers.parseEther("0.1") } // Creation fee
    );
    const receipt = await tx.wait();
    const tokenAddress = /* parse from event */;
    console.log("✅ Token created:", tokenAddress);
    
    // 2. Buy tokens to reach $50 market cap
    console.log("2. Buying tokens to reach graduation threshold...");
    const token = await ethers.getContractAt("BondingCurvePool", tokenAddress);
    
    // Buy multiple times to reach ~$50
    for (let i = 0; i < 10; i++) {
        await token.buy(0, { value: ethers.parseEther("20") });
        console.log(`  Buy ${i+1}/10 completed`);
    }
    
    const virtualKas = await token.virtualKasReserve();
    console.log("✅ Virtual KAS Reserve:", ethers.formatEther(virtualKas), "KAS");
    
    // 3. Trigger graduation (as oracle)
    console.log("3. Initiating graduation...");
    const controller = await ethers.getContractAt("GraduationController", CONTROLLER_V2_ADDRESS);
    const oracleSigner = /* get oracle signer */;
    
    const initTx = await controller.connect(oracleSigner).initiateGraduation(tokenAddress);
    await initTx.wait();
    console.log("✅ Graduation initiated");
    
    // 4. Complete graduation
    console.log("4. Completing graduation...");
    const completeTx = await controller.connect(oracleSigner).completeGraduation(tokenAddress);
    const completeReceipt = await completeTx.wait();
    console.log("✅ Graduation completed");
    console.log("  Gas used:", completeReceipt.gasUsed.toString());
    
    // 5. Verify results
    console.log("5. Verifying graduation...");
    const info = await controller.getGraduationInfo(tokenAddress);
    console.log("  Graduated:", info.graduated);
    console.log("  Timestamp:", new Date(Number(info.timestamp) * 1000).toISOString());
    console.log("  Position ID:", info.positionId.toString());
    console.log("  Pool Address:", info.poolAddress);
    
    // 6. Verify Uniswap pool
    console.log("6. Verifying Uniswap V3 pool...");
    const uniPool = await ethers.getContractAt("IUniswapV3Pool", info.poolAddress);
    const slot0 = await uniPool.slot0();
    console.log("  Pool Price (sqrtPriceX96):", slot0.sqrtPriceX96.toString());
    console.log("  Pool Unlocked:", slot0.unlocked);
    
    // 7. Try trading on Uniswap
    console.log("7. Testing trade on Uniswap...");
    const swapRouter = await ethers.getContractAt("ISwapRouter", SWAP_ROUTER_ADDRESS);
    // Perform a small test swap
    // ...
    
    console.log("\n✅ Full graduation test completed successfully!");
}
```

---

## 4. INTEGRATION WITH BACKEND

### Backend Oracle Update

**Required Changes in Backend Service**:

```typescript
// services/graduationOracle.ts

import { ethers } from 'ethers';

// Update contract ABI to V2
const GRADUATION_CONTROLLER_ABI = [ /* V2 ABI */ ];

// Update contract address
const GRADUATION_CONTROLLER_ADDRESS = process.env.GRADUATION_CONTROLLER_V2_ADDRESS;

class GraduationOracle {
    private provider: ethers.Provider;
    private controller: ethers.Contract;
    private oracleSigner: ethers.Wallet;
    
    constructor() {
        this.provider = new ethers.JsonRpcProvider(process.env.RPC_URL);
        this.oracleSigner = new ethers.Wallet(process.env.ORACLE_PRIVATE_KEY, this.provider);
        this.controller = new ethers.Contract(
            GRADUATION_CONTROLLER_ADDRESS,
            GRADUATION_CONTROLLER_ABI,
            this.oracleSigner
        );
    }
    
    async checkAndGraduateTokens() {
        const tokens = await this.getTokensNearGraduation();
        
        for (const token of tokens) {
            try {
                // Check if already graduated or in process
                const isGraduated = await this.controller.isGraduated(token.address);
                if (isGraduated) continue;
                
                const pool = new ethers.Contract(token.address, POOL_ABI, this.provider);
                const isGraduating = await pool.graduating();
                
                if (isGraduating) {
                    // Complete graduation
                    await this.completeGraduation(token.address);
                } else {
                    // Check if threshold reached
                    const shouldGraduate = await this.checkGraduationThreshold(token);
                    if (shouldGraduate) {
                        await this.initiateGraduation(token.address);
                    }
                }
            } catch (error) {
                console.error(`Error processing token ${token.address}:`, error);
                // Log to monitoring system
            }
        }
    }
    
    async initiateGraduation(tokenAddress: string) {
        console.log(`Initiating graduation for ${tokenAddress}`);
        
        try {
            const tx = await this.controller.initiateGraduation(tokenAddress);
            console.log(`Initiation TX: ${tx.hash}`);
            
            const receipt = await tx.wait();
            console.log(`Initiation confirmed in block ${receipt.blockNumber}`);
            
            // Update database
            await db.updateGraduationStatus(tokenAddress, 'initiating', tx.hash);
            
            return receipt;
        } catch (error) {
            console.error(`Initiation failed:`, error);
            await db.updateGraduationStatus(tokenAddress, 'failed', null, error.message);
            throw error;
        }
    }
    
    async completeGraduation(tokenAddress: string) {
        console.log(`Completing graduation for ${tokenAddress}`);
        
        try {
            // Validate pool state before attempting
            const pool = new ethers.Contract(tokenAddress, POOL_ABI, this.provider);
            const graduating = await pool.graduating();
            const liquidityTransferred = await pool.liquidityTransferred();
            
            if (!graduating) {
                throw new Error('Pool not in graduating state');
            }
            if (!liquidityTransferred) {
                throw new Error('Liquidity not transferred yet');
            }
            
            const tx = await this.controller.completeGraduation(tokenAddress);
            console.log(`Completion TX: ${tx.hash}`);
            
            const receipt = await tx.wait();
            console.log(`Completion confirmed in block ${receipt.blockNumber}`);
            
            // Parse events
            const event = receipt.logs.find(log => 
                log.topics[0] === this.controller.interface.getEvent('GraduationCompleted').topicHash
            );
            
            if (event) {
                const decoded = this.controller.interface.decodeEventLog(
                    'GraduationCompleted',
                    event.data,
                    event.topics
                );
                
                console.log(`Graduation successful!`);
                console.log(`  Pool: ${decoded.poolAddress}`);
                console.log(`  Position ID: ${decoded.liquidityPositionId}`);
                console.log(`  KAS Added: ${ethers.formatEther(decoded.kasAdded)}`);
                console.log(`  Tokens Added: ${ethers.formatEther(decoded.tokensAdded)}`);
                
                // Update database with completion details
                await db.updateGraduationStatus(
                    tokenAddress,
                    'graduated',
                    tx.hash,
                    null,
                    {
                        poolAddress: decoded.poolAddress,
                        positionId: decoded.liquidityPositionId.toString(),
                        kasAdded: decoded.kasAdded.toString(),
                        tokensAdded: decoded.tokensAdded.toString()
                    }
                );
            }
            
            return receipt;
        } catch (error) {
            console.error(`Completion failed:`, error);
            await db.updateGraduationStatus(tokenAddress, 'failed', null, error.message);
            
            // Consider cancelling graduation if fails repeatedly
            const failureCount = await db.getGraduationFailureCount(tokenAddress);
            if (failureCount >= 3) {
                console.log(`Graduation failed ${failureCount} times, considering cancellation`);
                // Alert admin
            }
            
            throw error;
        }
    }
    
    async monitorGraduations() {
        // Listen for graduation events
        this.controller.on('GraduationCompleted', async (tokenAddress, poolAddress, positionId, kasAdded, tokensAdded) => {
            console.log(`📢 Graduation completed: ${tokenAddress}`);
            // Update UI, send notifications, etc.
        });
        
        this.controller.on('GraduationFailed', async (tokenAddress, reason) => {
            console.error(`❌ Graduation failed: ${tokenAddress} - ${reason}`);
            // Alert admins
        });
    }
}

export default GraduationOracle;
```

### Database Schema Updates

```sql
-- Add new columns for V2
ALTER TABLE tokens ADD COLUMN graduation_pool_address VARCHAR(42);
ALTER TABLE tokens ADD COLUMN graduation_position_id BIGINT;
ALTER TABLE tokens ADD COLUMN graduation_kas_added NUMERIC(78, 0);
ALTER TABLE tokens ADD COLUMN graduation_tokens_added NUMERIC(78, 0);
ALTER TABLE tokens ADD COLUMN graduation_failure_count INT DEFAULT 0;
ALTER TABLE tokens ADD COLUMN graduation_failure_reason TEXT;

-- Index for querying graduation candidates
CREATE INDEX idx_tokens_graduation_status ON tokens(graduation_status);
CREATE INDEX idx_tokens_market_cap ON tokens(market_cap_usd) WHERE graduation_status IS NULL;
```

---

## 5. VERIFICATION PROCEDURES

### Post-Deployment Verification

Run these checks after deploying to testnet:

```bash
# 1. Verify contract addresses
npx hardhat verify --network kaspaTestnet <ADDRESS> <CONSTRUCTOR_ARGS...>

# 2. Check immutable variables
cast call <CONTROLLER_ADDRESS> "kaspaFinanceFactory()(address)" --rpc-url <RPC>
cast call <CONTROLLER_ADDRESS> "kaspaFinancePositionManager()(address)" --rpc-url <RPC>
cast call <CONTROLLER_ADDRESS> "kaspaFinanceWKAS()(address)" --rpc-url <RPC>

# 3. Check configuration
cast call <CONTROLLER_ADDRESS> "graduationSlippageBps()(uint256)" --rpc-url <RPC>
cast call <CONTROLLER_ADDRESS> "graduationDeadlineSeconds()(uint256)" --rpc-url <RPC>
cast call <CONTROLLER_ADDRESS> "maxPriceDeviationBps()(uint256)" --rpc-url <RPC>

# 4. Check ownership
cast call <CONTROLLER_ADDRESS> "owner()(address)" --rpc-url <RPC>
cast call <CONTROLLER_ADDRESS> "graduationOracle()(address)" --rpc-url <RPC>
```

### Manual Graduation Test Checklist

- [ ] Create test token via TokenFactory
- [ ] Buy tokens to reach $50 market cap
- [ ] Monitor backend picks up graduation candidate
- [ ] Backend calls `initiateGraduation()`
- [ ] Verify `GraduationInitiated` event emitted
- [ ] Verify pool state: `graduating = true`, `liquidityTransferred = true`
- [ ] Verify KAS transferred to controller
- [ ] Backend calls `completeGraduation()`
- [ ] Verify Uniswap pool created (check factory)
- [ ] Verify pool initialized (check slot0.sqrtPriceX96 != 0)
- [ ] Verify liquidity position minted (check NFT ID)
- [ ] Verify `GraduationCompleted` event emitted
- [ ] Verify pool state: `graduated = true`
- [ ] Try swapping on Uniswap V3
- [ ] Verify no funds stuck in controller

---

## 6. ROLLBACK PLAN

### If Deployment Fails

**Scenario**: Contract deployment succeeds but functionality is broken

**Steps**:
1. DO NOT update backend to use V2 address
2. Keep using V1 address (even though broken)
3. Mark all tokens as "Graduation temporarily unavailable"
4. Fix bugs in V2
5. Redeploy V2 with fixes
6. Resume testing

### If Graduation Fails on Testnet

**Scenario**: First graduation test fails

**Steps**:
1. Pause contract: `await controller.pause()`
2. Investigate failure reason from events/logs
3. If bug in contract:
   - Fix and redeploy V2.1
   - Update backend with new address
4. If bug in backend:
   - Fix backend code
   - Test again with same V2 contract
5. If stuck funds:
   - Use `emergencyWithdraw()` or `cancelGraduation()`
   - Return funds to users

### If Critical Bug Found in Production

**Scenario**: Bug discovered after production deployment

**Steps**:
1. **IMMEDIATE**: Pause contract
2. Alert all users graduation is temporarily paused
3. Deploy fixed V2.1 contract
4. Update backend
5. Resume graduations on V2.1
6. Offer to manually complete any stuck V2 graduations

---

## 7. PRODUCTION DEPLOYMENT

### Pre-Production Checklist

- [ ] All testnet tests passed (10/10 graduations successful)
- [ ] Gas usage within budget (< 1M gas per graduation)
- [ ] No funds stuck in controller after tests
- [ ] Backend integration working smoothly
- [ ] Monitoring and alerts configured
- [ ] External security audit completed (if possible)
- [ ] Emergency procedures documented and tested
- [ ] Team trained on emergency response

### Production Deployment Steps

1. **Deploy to Mainnet**
```bash
npx hardhat run scripts/deployGraduationV2.js --network kaspaMainnet
```

2. **Verify on Explorer**
```bash
npx hardhat verify --network kaspaMainnet <ADDRESS> <ARGS...>
```

3. **Configure Contract**
```javascript
// Set production parameters
await controller.setGraduationParams(500, 300, 100);
```

4. **Update Backend**
```typescript
// Update environment variables
GRADUATION_CONTROLLER_ADDRESS=<V2_MAINNET_ADDRESS>
```

5. **Staged Rollout**
   - Week 1: Monitor but don't graduate (dry run)
   - Week 2: Graduate 1 token and monitor closely
   - Week 3: Graduate 3-5 tokens
   - Week 4: Full rollout

6. **Monitor First Graduations**
   - Watch every transaction
   - Verify pool creation
   - Verify price initialization
   - Verify liquidity minting
   - Check for any anomalies

7. **Post-Deployment**
   - Update documentation
   - Announce V2 launch to users
   - Mark V1 tokens as legacy
   - Monitor error rates and gas costs

### Success Metrics

Track these metrics to ensure V2 is working:

- **Graduation Success Rate**: Target 100%
- **Average Gas Cost**: Target < 1M gas
- **Average Time to Complete**: Target < 5 minutes
- **Stuck Funds**: Target 0 KAS stuck
- **User Satisfaction**: Monitor feedback

---

## 8. EMERGENCY CONTACTS

**In case of critical issues**:

- Smart Contract Lead: [Contact Info]
- Backend Lead: [Contact Info]
- DevOps Lead: [Contact Info]
- Security Team: [Contact Info]

**Emergency Actions**:
- Pause Contract: `controller.pause()`
- Cancel Graduation: `controller.cancelGraduation(tokenAddress)`
- Emergency Withdraw: `controller.emergencyWithdraw(token, amount)`

---

## CONCLUSION

This guide provides a comprehensive path from development to production deployment. Follow each step carefully and don't skip testing phases.

**Remember**: 
- Test extensively on testnet first
- Monitor closely during production rollout
- Have emergency procedures ready
- Document everything

Good luck with the V2 deployment! 🚀
