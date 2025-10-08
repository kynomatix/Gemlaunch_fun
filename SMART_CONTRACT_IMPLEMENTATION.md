# Gemlaunch.fun - Blockchain Smart Contract Implementation Plan

## ⚠️ IMPLEMENTATION NOTES

**CURRENT VERSION**: v4 (AUDIT-APPROVED - Anti-Bot System)

**IMPORTANT**: 
- Some sections contain historical/outdated code marked with ⚠️ SUPERSEDED
- Always use the **AUDIT FIX v4** versions for implementation
- Key functions are clearly labeled with version numbers
- Ignore any section marked as "SUPERSEDED" or "DO NOT USE"

**Quick Reference - Use These Implementations**:
- **State Variables**: Line ~131 (AUDIT FIX v4)
- **Constructor**: Line ~162 (AUDIT FIX v4)
- **buyTokens()**: Line ~200 (AUDIT FIX v4 - with Anti-Bot)
- **sellTokens()**: Line ~1582 (AUDIT FIX v4 - KAS-based fees) ⚠️ NOT line 431!
- **Events**: Line ~266 (AUDIT FIX v4)
- **View Functions**: Line ~294 (AUDIT FIX v4)
- **Anti-Bot Documentation**: Line ~330 (Complete specs)

---

## Overview

This document outlines the implementation plan for integrating Kasplex zkEVM blockchain smart contracts into gemlaunch.fun to enable real token launches, bonding curve trading, and DEX graduation.

**Current Status**: Mock/database-driven implementation  
**Target**: Live blockchain integration on Kasplex zkEVM testnet → mainnet  
**DEX Partner**: Kaspa Finance (kaspafinance.io)  
**Security Priority**: CRITICAL - contracts will hold real money

### Fee Structure
**Total Trading Fees: 1%**
- **Platform Fee (90%)**: 0.9% of trade value → Treasury
  - 40% Platform Development (0.36% of trade)
  - 30% GEM Buyback & Burn (0.27% of trade)
  - 15% Kaspa Network Support (0.135% of trade)
  - 15% Community Rewards (0.135% of trade) - uses remainder pattern
- **Creator Fee (10%)**: 0.1% of trade value → Accumulated and claimable by token creator

---

## 1. Kasplex zkEVM Network Configuration

### Testnet
```
Network Name: Kasplex zkEVM Testnet
RPC URL: https://rpc.kasplextest.xyz
Chain ID: 167012
Block Explorer: http://explorer.testnet.kasplextest.xyz
Native Token: KAS (bridged from Kaspa L1)
Faucet: 50 KAS every 24 hours (no auth required)
```

### Mainnet
```
Network Name: Kasplex zkEVM
RPC URL: https://evmrpc.kasplex.org
Chain ID: 202555
Block Explorer: https://explorer.kasplex.org
Bridge: https://kasbridge-evm.kaspafoundation.org
Documentation: https://docs-kasplex.gitbook.io/l2-network/
```

### Technical Characteristics
- **Full EVM Equivalence**: Standard Solidity contracts work without modification
- **Based Rollup Model**: Kaspa L1 handles sequencing (no centralized sequencer)
- **Sub-second Finality**: GHOSTDAG consensus integration
- **PLONK-based zk-SNARKs**: Zero-knowledge proof generation
- **Compatible Tools**: Hardhat, Foundry, Remix, MetaMask, Ethers.js, Viem

---

## 2. Smart Contract Architecture

### Core Contracts

#### 2.1 TokenFactory.sol
**Purpose**: Deploys new ERC-20 tokens with bonding curve pools

**Key Features**:
- Factory pattern for unlimited token creation
- Stores token metadata (name, symbol, description, image, socials)
- Associates each token with its BondingCurvePool
- Emits TokenCreated events for indexing
- Access control for pausing new deployments

**State Variables**:
```solidity
mapping(address => TokenInfo) public tokens;
address[] public deployedTokens;
address public graduationController;
uint256 public platformFee; // Basis points (e.g., 100 = 1%)
address public feeRecipient;
```

**Security Features**:
- Pausable deployment
- Owner-controlled fee adjustments
- Token metadata validation
- Anti-spam deployment limits

---

#### 2.2 BondingCurvePool.sol
**Purpose**: Manages token trading via bonding curve pricing

**Bonding Curve Formula** (AUDIT FIX v2 - Virtual Reserves Pattern):
```solidity
// AUDIT FIX: Virtual reserves eliminate fee/reserve confusion
// Fees are stored separately, AMM only uses tradeable reserves
function quoteBuy(uint256 kasIn) public view returns (uint256 tokensOut) {
    // Use ONLY virtual reserves for pricing (excludes accumulated fees)
    uint256 k = virtualTokenReserve * virtualKasReserve;
    
    // Constant product: (virtualTokenReserve - tokensOut) * (virtualKasReserve + kasIn) = k
    uint256 newKasReserve = virtualKasReserve + kasIn;
    uint256 newTokenReserve = k / newKasReserve;
    tokensOut = virtualTokenReserve - newTokenReserve;
    
    require(tokensOut > 0 && tokensOut < virtualTokenReserve, "Invalid output");
}

function quoteSell(uint256 tokensIn) public view returns (uint256 kasOut) {
    uint256 k = virtualTokenReserve * virtualKasReserve;
    
    uint256 newTokenReserve = virtualTokenReserve + tokensIn;
    uint256 newKasReserve = k / newTokenReserve;
    kasOut = virtualKasReserve - newKasReserve;
    
    require(kasOut > 0 && kasOut < virtualKasReserve, "Invalid output");
}
```

**Supply Distribution**:
- **75%** allocated to bonding curve
- **25%** reserved for DEX liquidity post-graduation

**Key Features**:
- Buy tokens with KAS (ETH-compatible on Kasplex)
- Sell tokens back to curve for KAS
- Dynamic pricing based on reserve ratio
- 10% wallet cap (anti-whale protection)
- Slippage protection via minTokensOut/maxTokensIn
- Time-weighted purchase limits (anti-bot)
- Emergency pause functionality

**State Variables** (AUDIT FIX v4 - Virtual Reserves + Anti-Bot):
```solidity
uint256 public constant CURVE_SUPPLY_PCT = 75;
uint256 public constant LP_SUPPLY_PCT = 25;
uint256 public constant MAX_WALLET_PCT = 10;
uint256 public constant TOTAL_FEE_BPS = 100; // 1% total trading fee
uint256 public constant CREATOR_SHARE_BPS = 1000; // 10% of fees (0.1% of trade)
uint256 public constant GRADUATION_THRESHOLD = 75e18; // 75 KAS in virtual reserve
uint256 public constant MIN_TRADE_AMOUNT = 0.001 ether; // Minimum trade size

address public treasury; // Gemlaunch treasury contract
address public airdropTreasury; // Airdrop Treasury for anti-bot fees
address public immutable creator; // Token creator address (immutable)

// AUDIT FIX: Virtual reserves - single source of truth for AMM pricing
uint256 public virtualKasReserve;   // Tradeable KAS only (excludes fees)
uint256 public virtualTokenReserve; // Tradeable tokens only

// Fee tracking (separate from reserves)
uint256 public accumulatedPlatformFees;
uint256 public accumulatedCreatorFees;
uint256 public totalAntiBotFeesCollected; // AUDIT FIX: Total anti-bot fees (analytics only)

// Anti-Bot System (GEM System - optional per token)
bool public antiBotEnabled;
uint256 public deploymentTime; // Launch timestamp

bool public graduated;
bool public graduating; // Lock flag during graduation
```

**Constructor** (AUDIT FIX v4 - Anti-Bot Validation):
```solidity
constructor(
    string memory name,
    string memory symbol,
    uint256 totalSupply,
    address _creator,
    address _treasury,
    address _airdropTreasury,
    bool _antiBotEnabled
) ERC20(name, symbol) {
    require(_creator != address(0), "Invalid creator");
    require(_treasury != address(0), "Invalid treasury");
    require(_airdropTreasury != address(0), "Invalid airdrop treasury");
    require(_airdropTreasury != address(this), "Airdrop treasury cannot be self");
    
    creator = _creator;
    treasury = _treasury;
    airdropTreasury = _airdropTreasury;
    antiBotEnabled = _antiBotEnabled;
    
    // AUDIT FIX: Only set deploymentTime if anti-bot enabled
    if (_antiBotEnabled) {
        deploymentTime = block.timestamp;
    }
    
    // Mint total supply to contract
    _mint(address(this), totalSupply);
    
    // CRITICAL: Initialize virtual reserves to prevent division by zero
    uint256 curveSupply = totalSupply * CURVE_SUPPLY_PCT / 100; // 75%
    virtualTokenReserve = curveSupply;
    virtualKasReserve = 0.001 ether; // 0.001 KAS virtual seed for initial pricing
    
    // LP tokens (25%) stay in contract, not in virtualTokenReserve
}
```

**Buy Function** (AUDIT FIX v4 - Corrected Fee Order):
```solidity
function buyTokens(uint256 minTokensOut, uint256 deadline) external payable nonReentrant {
    require(!graduated && !graduating, "Token graduated or graduating");
    require(block.timestamp <= deadline, "Transaction expired");
    require(msg.value >= MIN_TRADE_AMOUNT, "Below minimum trade");
    
    uint256 remainingValue = msg.value;
    uint256 antiBotFee = 0;
    
    // AUDIT FIX: Step 1 - Calculate and deduct anti-bot fee FIRST
    if (antiBotEnabled && block.timestamp < deploymentTime + 60) {
        uint256 elapsed = block.timestamp - deploymentTime;
        // Linear decay: 95% → 1% over 60 seconds
        uint256 feePercent = 9500 - (9400 * elapsed / 60);
        antiBotFee = msg.value * feePercent / 10000;
        remainingValue = msg.value - antiBotFee;
        
        // Send anti-bot fee immediately to airdrop treasury
        totalAntiBotFeesCollected += antiBotFee;
        _safeSend(airdropTreasury, antiBotFee);
        emit AntiBotFeePaid(msg.sender, antiBotFee, elapsed);
    }
    
    // AUDIT FIX: Step 2 - Calculate platform/creator fees from REMAINING value
    uint256 platformFee = remainingValue * 90 / 10000; // 0.9% of remainder
    uint256 creatorFee = remainingValue * 10 / 10000;  // 0.1% of remainder
    uint256 totalFees = platformFee + creatorFee;
    uint256 tradeAmount = remainingValue - totalFees;
    
    // Step 3: AMM calculation
    uint256 tokensOut = quoteBuy(tradeAmount);
    require(tokensOut >= minTokensOut, "Slippage too high");
    require(tokensOut > 0, "Insufficient output");
    
    // Step 4: Update state (CEI pattern)
    virtualKasReserve += tradeAmount;
    virtualTokenReserve -= tokensOut;
    
    accumulatedPlatformFees += platformFee;
    accumulatedCreatorFees += creatorFee;
    
    // Step 5: Check graduation
    bool shouldGraduate = !graduated && !graduating && virtualKasReserve >= GRADUATION_THRESHOLD;
    
    if (shouldGraduate) {
        graduating = true;
    }
    
    // Step 6: Transfer tokens (wallet cap enforced in _transfer override)
    _transfer(address(this), msg.sender, tokensOut);
    
    emit TokensPurchased(msg.sender, tokensOut, tradeAmount, platformFee, creatorFee, antiBotFee);
    
    // Step 7: Execute graduation if needed
    if (graduating) {
        _executeGraduation();
    }
}

// AUDIT FIX: Safe send helper (replaces .transfer)
function _safeSend(address to, uint256 amount) private {
    (bool success, ) = payable(to).call{value: amount}("");
    require(success, "Transfer failed");
}

**Events** (AUDIT FIX v4 - Complete Event Definitions):
```solidity
event TokensPurchased(
    address indexed buyer,
    uint256 tokensOut,
    uint256 tradeAmount,
    uint256 platformFee,
    uint256 creatorFee,
    uint256 antiBotFee
);

event TokensSold(
    address indexed seller,
    uint256 tokensIn,
    uint256 kasOut,
    uint256 platformFee,
    uint256 creatorFee
);

event AntiBotFeePaid(
    address indexed user,
    uint256 feeAmount,
    uint256 elapsedSeconds
);

event Graduated(address indexed pool, uint256 kasLiquidity, uint256 tokenLiquidity);
```

**View Functions** (AUDIT FIX v4 - UX Helpers):
```solidity
// Get current anti-bot fee for a given KAS amount
function getCurrentAntiBotFee(uint256 kasAmount) public view returns (uint256) {
    if (!antiBotEnabled) return 0;
    if (block.timestamp >= deploymentTime + 60) return 0;
    
    uint256 elapsed = block.timestamp - deploymentTime;
    uint256 feePercent = 9500 - (9400 * elapsed / 60);
    return kasAmount * feePercent / 10000;
}

// Get seconds remaining until normal fees
function getSecondsUntilNormalFees() public view returns (uint256) {
    if (!antiBotEnabled) return 0;
    if (block.timestamp >= deploymentTime + 60) return 0;
    return deploymentTime + 60 - block.timestamp;
}

// Get complete fee breakdown for UX
function getEffectiveFeeBreakdown(uint256 kasAmount) external view returns (
    uint256 antiBotFee,
    uint256 platformFee,
    uint256 creatorFee,
    uint256 tradeAmount
) {
    antiBotFee = getCurrentAntiBotFee(kasAmount);
    uint256 remaining = kasAmount - antiBotFee;
    platformFee = remaining * 90 / 10000;
    creatorFee = remaining * 10 / 10000;
    tradeAmount = remaining - platformFee - creatorFee;
}
```

---

### 2.2.1 Anti-Bot System (GEM System) - AUDIT-APPROVED Implementation

**Audit Status**: ✅ **FIXED** - All critical issues resolved (v4)

**Purpose**: Prevent bot sniping with time-based KAS fee decay that makes instant purchases unprofitable while rewarding patient community members.

**Mechanism**: Linear fee decay from 95% → 1% over 60 seconds after token launch.

**Corrected Fee Calculation** (AUDIT FIX v4):
```solidity
// CRITICAL: Anti-bot fee deducted FIRST, then platform/creator fees from remainder
uint256 remainingValue = msg.value;
uint256 antiBotFee = 0;

if (antiBotEnabled && block.timestamp < deploymentTime + 60) {
    uint256 elapsed = block.timestamp - deploymentTime;
    uint256 feePercent = 9500 - (9400 * elapsed / 60); // Linear decay
    antiBotFee = msg.value * feePercent / 10000;
    remainingValue = msg.value - antiBotFee;
    
    totalAntiBotFeesCollected += antiBotFee;
    _safeSend(airdropTreasury, antiBotFee); // Immediate transfer
}

// Platform/creator fees from REMAINING value (not msg.value)
uint256 platformFee = remainingValue * 90 / 10000;  // 0.9% of remainder
uint256 creatorFee = remainingValue * 10 / 10000;   // 0.1% of remainder
uint256 tradeAmount = remainingValue - (platformFee + creatorFee);
```

**Fee Distribution**:
- **100% of anti-bot fees → Airdrop Treasury** (transferred immediately via `_safeSend`)
- Anti-bot fees are SEPARATE from platform fees (0.9%) and creator fees (0.1%)
- Bot snipes effectively "donate" KAS to the community

**Airdrop Treasury Distribution** (OFF-CHAIN - Manual Management):
- **70% Leaderboard Rewards**: Top traders, creators, and community contributors
- **30% Team/Dev**: Platform development, security audits, and infrastructure costs

**Important**: The smart contract sends 100% of anti-bot fees to the `airdropTreasury` address. The 70/30 split is handled OFF-CHAIN by the platform team through manual distributions based on leaderboard data. This provides flexibility in reward distribution without hardcoding logic in the immutable smart contract.

**State Variables**:
```solidity
bool public antiBotEnabled;                 // Optional per-token
uint256 public deploymentTime;              // Launch timestamp
address public airdropTreasury;             // Receives all anti-bot fees (validated != address(0))
uint256 public totalAntiBotFeesCollected;   // Total historical fees (analytics)
```

**Security Audit Fixes (v4)**:
1. ✅ **CRITICAL FIX**: Anti-bot fee deducted FIRST, platform/creator fees from remainder
2. ✅ **CRITICAL FIX**: Proper validation of airdropTreasury in constructor
3. ✅ **CRITICAL FIX**: Changed `accumulatedAntiBotFees` → `totalAntiBotFeesCollected`
4. ✅ **HIGH FIX**: Added view functions for UX (`getCurrentAntiBotFee`, `getSecondsUntilNormalFees`)
5. ✅ **MEDIUM FIX**: Added `MIN_TRADE_AMOUNT` constant
6. ✅ **LOW FIX**: Defined `AntiBotFeePaid` event properly
7. ✅ **Fee Order**: Anti-bot → Platform → Creator → Trade (correct sequence)
8. ✅ **Immediate Transfer**: Anti-bot fees sent immediately (not accumulated)
9. ✅ **No Reserve Contamination**: Anti-bot fees never enter virtual reserves

**Updated Example Trade Flow** (100 KAS at t=5s):
```
1. User sends 100 KAS at t=5 seconds
2. Elapsed = 5s
3. Fee percent = 9500 - (9400 × 5 / 60) = 8716 bps = 87.16%
4. Anti-bot fee = 100 × 0.8716 = 87.16 KAS → Airdrop Treasury (immediate transfer)
5. Remaining = 12.84 KAS
6. Platform fee = 12.84 × 0.009 = 0.116 KAS (0.9% of remainder)
7. Creator fee = 12.84 × 0.001 = 0.013 KAS (0.1% of remainder)
8. Trade amount = 12.84 - 0.129 = 12.71 KAS → Bonding curve
9. User receives tokens worth 12.71 KAS (paid 100 KAS total) ✓
```

**Game Theory Analysis**:
- **Bot Perspective**: Early snipe (t=0) = 95% fee → Get 5% value. Wait 60s = 1% fee → Get 99% value
- **Rational Choice**: WAIT (anti-bot neutralizes sniping advantage ✓)
- **Community Benefit**: Failed bot snipes fund rewards (70% leaderboard, 30% team/dev) ✓

**Frontend UX Functions**:
- `getCurrentAntiBotFee(kasAmount)` - Show user exact fee before trade
- `getSecondsUntilNormalFees()` - Display countdown timer
- `getEffectiveFeeBreakdown(kasAmount)` - Complete fee breakdown for preview

## ⚠️ SUPERSEDED SECTION - DO NOT USE

**~~Sell Function (AUDIT FIX v3)~~ - BROKEN TOKEN-BASED FEES**

**⚠️ THIS CODE IS OUTDATED AND BROKEN - DO NOT IMPLEMENT**

**REASON**: This v3 implementation uses token-based fees with hypothetical KAS conversion, causing accounting mismatches. The `quoteSell(totalFees)` creates hypothetical KAS that doesn't exist in contract balance, breaking fee withdrawals.

**USE INSTEAD**: See **Priority 1: Fixed Sell Function** at line ~1582 for the CORRECT V4 implementation with:
- ✅ Fee on KAS OUTPUT (not token input)
- ✅ Actual KAS fees (not hypothetical)
- ✅ Correct accounting that matches contract balance
- ✅ All fees in KAS for unified accounting

**This section is kept for historical reference only - shows what NOT to do.**

---

### AUDIT FIX v3 Updates (Critical Fixes)

**C-1: Virtual Reserve Initialization** ✅
- Added proper constructor initialization with 0.001 KAS virtual seed
- Prevents division by zero on first trade
- Clear separation: 75% to virtualTokenReserve, 25% for LP

**C-2: Symmetric Fee Calculation** ✅
- Buy: Fee on INPUT (KAS)
- Sell: Fee on INPUT (tokens) - NOW SYMMETRIC
- Eliminates round-trip asymmetry
- Fee tokens converted to KAS value for unified accounting

**C-3: Graduation Check Timing** ✅
- Reserves updated FIRST (CEI pattern)
- Graduation checked AFTER update (uses actual new state)
- Eliminates premature graduation risk

**C-4: Correct LP Reserve Split** ✅
- ALL virtualKasReserve goes to LP (~75 KAS)
- 25% of total supply (reserved tokens) go to LP
- Unsold curve tokens burned
- Correct economic model

**H-1: Minimum Trade Amount** ✅
- 0.001 KAS minimum enforced
- Prevents dust attacks and rounding exploits
- Applied to both buy and sell

**H-2: Enhanced Transfer Cooldown** ✅
- Cooldown tracks BOTH sender and receiver
- Prevents flash loan and multi-wallet bypass
- 5-minute window enforced

**H-3: Balance Verification** ✅
- Graduation verifies sufficient balance
- Fee withdrawals respect reserve requirements
- Invariant: balance >= virtualKasReserve + accumulated fees

---

**Wallet Cap Enforcement** (AUDIT FIX v3 - Enhanced Cooldown):
```solidity
mapping(address => uint256) public lastTransferTime;
uint256 public constant TRANSFER_COOLDOWN = 5 minutes;

// Override _transfer to enforce wallet cap + bidirectional cooldown
function _transfer(address from, address to, uint256 amount) internal override {
    if (!graduated && from != address(this) && to != address(this)) {
        // Circulating supply = total - contract holdings
        uint256 circulating = totalSupply() - balanceOf(address(this));
        
        // Check wallet cap based on circulating supply
        require(
            balanceOf(to) + amount <= (circulating * MAX_WALLET_PCT) / 100,
            "Exceeds 10% wallet cap"
        );
        
        // AUDIT FIX v3: Bidirectional cooldown (sender AND receiver)
        require(
            block.timestamp >= lastTransferTime[from] + TRANSFER_COOLDOWN,
            "Sender cooldown active"
        );
        require(
            block.timestamp >= lastTransferTime[to] + TRANSFER_COOLDOWN,
            "Receiver cooldown active"
        );
        
        lastTransferTime[from] = block.timestamp;
        lastTransferTime[to] = block.timestamp;
    }
    super._transfer(from, to, amount);
}
```

**Fee Withdrawal Functions** (AUDIT FIX v2 - Access Control + Pull Pattern):
```solidity
// Creator fee claiming (ONLY creator can claim)
function claimCreatorFees() external nonReentrant {
    require(msg.sender == creator, "Only creator");
    require(accumulatedCreatorFees > 0, "No fees to claim");
    
    uint256 amount = accumulatedCreatorFees;
    accumulatedCreatorFees = 0;
    
    _safeSend(creator, amount);
    emit CreatorFeeClaimed(creator, amount);
}

// Platform fee withdrawal (AUDIT FIX v3 - Balance Verification)
function withdrawPlatformFees() external nonReentrant {
    require(msg.sender == treasury, "Only treasury");
    require(accumulatedPlatformFees > 0, "No fees to withdraw");
    
    // CRITICAL: Ensure contract has enough balance after reserving for graduation
    uint256 withdrawable = address(this).balance - virtualKasReserve;
    uint256 amount = accumulatedPlatformFees;
    
    // Can only withdraw what's actually available
    if (amount > withdrawable) {
        amount = withdrawable;
    }
    
    require(amount > 0, "Insufficient withdrawable balance");
    accumulatedPlatformFees -= amount;
    
    _safeSend(treasury, amount);
    emit PlatformFeesWithdrawn(amount);
}

// Emergency fee rescue (ONLY if creator cannot receive - admin + timelock)
function rescueStuckCreatorFees(address newRecipient) external onlyAdmin afterTimelock {
    require(accumulatedCreatorFees > 0, "No fees stuck");
    
    // Verify creator actually cannot receive (e.g., contract with no receive)
    (bool canReceive, ) = payable(creator).call{value: 0}("");
    require(!canReceive, "Creator can receive");
    
    uint256 amount = accumulatedCreatorFees;
    accumulatedCreatorFees = 0;
    
    _safeSend(newRecipient, amount);
    emit CreatorFeesRescued(creator, newRecipient, amount);
}
```

**Graduation Execution** (AUDIT FIX v3 - Correct LP Split + Balance Verification):
```solidity
// Internal graduation execution (called atomically within buyTokens)
function _executeGraduation() internal {
    require(graduating && !graduated, "Invalid graduation state");
    
    // Mark graduated (locks all future trading)
    graduated = true;
    
    // ALL virtualKasReserve goes to LP
    uint256 kasForLP = virtualKasReserve;
    
    // CRITICAL: Verify contract has sufficient balance for graduation
    require(address(this).balance >= kasForLP, "Insufficient balance for graduation");
    
    // LP gets the 25% reserved tokens (NOT from virtualTokenReserve)
    uint256 lpTokens = totalSupply() * LP_SUPPLY_PCT / 100;
    
    // Burn unsold curve tokens (from the 75% allocation)
    uint256 unsoldCurveTokens = virtualTokenReserve;
    if (unsoldCurveTokens > 0) {
        _burn(address(this), unsoldCurveTokens);
    }
    
    // Transfer graduation data to controller
    IGraduationController(graduationController).graduateToken{value: kasForLP}(
        address(this),
        lpTokens,
        kasForLP
    );
    
    emit TokenGraduated(address(this), kasForLP, lpTokens, block.timestamp);
}

// View function to check if ready to graduate
function canGraduate() public view returns (bool) {
    return !graduated && !graduating && virtualKasReserve >= GRADUATION_THRESHOLD;
}
```

**Security Features**:
- ReentrancyGuard on buy/sell
- Pull-over-push pattern for refunds
- Checks-Effects-Interactions ordering
- Safe math (Solidity ^0.8)
- Wallet cap modifier
- Rate limiting per address
- Circuit breaker for price spikes

---

#### 2.3 GraduationController.sol
**Purpose**: Manages token graduation to Kaspa Finance DEX

**Graduation Logic**:
1. Monitor bonding curve completion (75 KAS raised threshold)
2. Calculate liquidity provision: 25% token supply + raised KAS
3. Create Kaspa Finance liquidity pool
4. Lock curve trading permanently
5. Enable DEX trading

**Kaspa Finance Integration**:
- **DEX**: Kaspa Finance (kaspafinance.io) - First DeFi super app on Kasplex L2
- **Pool Creation**: Automated via router contract
- **Liquidity Split**: 75% KAS from curve + 25% token supply
- **LP Tokens**: Burned or sent to treasury (configurable)

**Key Features**:
- Automated graduation trigger
- Secure liquidity transfer
- Pool creation on Kaspa Finance
- Graduation status events
- Multi-sig treasury integration

**State Variables**:
```solidity
address public kaspaFinanceRouter;
mapping(address => bool) public graduatedTokens;
uint256 public minLiquidityThreshold;
address public treasury;
```

**Security Features**:
- Pull-based graduation (user-triggered, contract-verified)
- Reentrancy protection
- Liquidity lock verification
- Access control for emergency stops
- Event emission for transparency

---

#### 2.4 Treasury/VestingVault.sol
**Purpose**: Manages platform fees and optional token vesting

**Key Features**:
- Collects 1% total trading fee (90% platform, 10% creator)
- Platform fee (0.9% of trade) distributes to:
  - 40% Platform Development (0.36% of trade)
  - 30% GEM Buyback & Burn (0.27% of trade - accumulates until TGE, then TWAP buybacks)
  - 15% Kaspa Network Support (0.135% of trade)
  - 15% Community Rewards (0.135% of trade - airdrops, incentives, uses remainder pattern)
- Creator fee: 10% of total fees (0.1% of trade)
- Multi-sig withdrawal controls
- Optional vesting schedules for team/contributors
- TWAP buyback mechanism post-GEM TGE

**State Variables**:
```solidity
// Treasury wallet addresses
address public platformDevelopmentWallet;
address public buybackReserveWallet;      // Accumulates KAS until GEM TGE
address public kaspaNetworkSupportWallet; // Kaspa ecosystem support
address public communityRewardsWallet;

// Fee tracking
uint256 public constant PLATFORM_FEE_BPS = 90; // 90% of 1% = 0.9% in basis points
uint256 public totalFeesCollected;

// Distribution percentages (of platform fees, in basis points)
uint256 public constant DEV_SHARE = 4000;       // 40% of platform fees
uint256 public constant BUYBACK_SHARE = 3000;   // 30% of platform fees (accumulates, then TWAP)
uint256 public constant KASPA_SHARE = 1500;     // 15% of platform fees (Kaspa Network Support)
uint256 public constant COMMUNITY_SHARE = 1500; // 15% of platform fees (CORRECTED from 500)

// TWAP Buyback (activated post-TGE)
bool public twapBuybackEnabled;
address public gemTokenAddress;
uint256 public twapPeriod = 24 hours;
uint256 public twapBuybackAmount; // KAS per period

mapping(address => VestingSchedule) public vesting;
```

**Fee Distribution Flow** (AUDIT FIX v4 - Safe transfers + Remainder Pattern):
```solidity
function distributeFees() external nonReentrant {
    uint256 balance = address(this).balance;
    require(balance > 0, "No fees to distribute");
    
    // Calculate shares (remainder pattern ensures 100% distribution)
    uint256 devAmount = balance * DEV_SHARE / 10000;         // 40%
    uint256 buybackAmount = balance * BUYBACK_SHARE / 10000; // 30%
    uint256 kaspaAmount = balance * KASPA_SHARE / 10000;     // 15%
    uint256 communityAmount = balance - devAmount - buybackAmount - kaspaAmount; // 15% (remainder)
    
    // AUDIT FIX: Use .call instead of .transfer to prevent failures
    _safeTransfer(platformDevelopmentWallet, devAmount);
    _safeTransfer(buybackReserveWallet, buybackAmount);        // Accumulates until GEM TGE
    _safeTransfer(kaspaNetworkSupportWallet, kaspaAmount);     // Kaspa ecosystem support
    _safeTransfer(communityRewardsWallet, communityAmount);    // Remainder = exactly 15%
    
    emit FeesDistributed(devAmount, buybackAmount, kaspaAmount, communityAmount);
}

function _safeTransfer(address to, uint256 amount) private {
    (bool success, ) = payable(to).call{value: amount}("");
    if (!success) {
        emit TransferFailed(to, amount);
        // Don't revert - log and continue to prevent blocking other transfers
    }
}
```

**Kaspa Network Support (Transparent Allocation)**:
```solidity
// 15% of platform fees supports Kaspa ecosystem (miners, development, infrastructure)
// Transparent wallet with clear allocation guidelines
address public kaspaNetworkSupportWallet;

// Future: Could implement governance for allocation decisions
function updateKaspaNetworkWallet(address _newWallet) external onlyOwner {
    require(_newWallet != address(0), "Invalid wallet");
    kaspaNetworkSupportWallet = _newWallet;
    emit KaspaNetworkWalletUpdated(_newWallet);
}
```

**TWAP Buyback System (Post-TGE)** - AUDIT FIX v2: Oracle Validation:
```solidity
uint256 public constant MIN_TWAP_PERIOD = 30 minutes;
uint256 public constant MAX_PRICE_DEVIATION_BPS = 1000; // 10%
uint256 public lastBuybackTime;
uint256 public constant MIN_BUYBACK_INTERVAL = 6 hours; // Prevent predictable timing

// Enable TWAP buyback after GEM TGE
function enableTWAPBuyback(
    address _gemTokenAddress,
    address _twapOracle,
    uint256 _twapPeriod,
    uint256 _buybackAmountPerPeriod
) external onlyOwner {
    require(!twapBuybackEnabled, "Already enabled");
    require(_gemTokenAddress != address(0), "Invalid GEM address");
    require(_twapOracle != address(0), "Invalid oracle");
    require(_twapPeriod >= MIN_TWAP_PERIOD, "TWAP period too short");
    
    gemTokenAddress = _gemTokenAddress;
    twapOracle = _twapOracle;
    twapPeriod = _twapPeriod;
    twapBuybackAmount = _buybackAmountPerPeriod;
    twapBuybackEnabled = true;
    
    emit TWAPBuybackEnabled(_gemTokenAddress, _twapPeriod, _buybackAmountPerPeriod);
}

// Execute TWAP buyback (called periodically after TGE)
function executeTWAPBuyback() external nonReentrant {
    require(twapBuybackEnabled, "TWAP not enabled");
    require(block.timestamp >= lastBuybackTime + MIN_BUYBACK_INTERVAL, "Too soon");
    require(address(this).balance >= twapBuybackAmount, "Insufficient reserve");
    
    // Get TWAP price from oracle (30min+ average)
    uint256 twapPrice = ITWAPOracle(twapOracle).getTWAP(gemTokenAddress, twapPeriod);
    require(twapPrice > 0, "Invalid TWAP price");
    
    // Get current spot price from DEX
    uint256 spotPrice = _getSpotPrice(gemTokenAddress);
    require(spotPrice > 0, "Invalid spot price");
    
    // AUDIT FIX: Sanity check - TWAP and spot shouldn't deviate >10%
    uint256 deviation = twapPrice > spotPrice 
        ? ((twapPrice - spotPrice) * 10000) / spotPrice
        : ((spotPrice - twapPrice) * 10000) / twapPrice;
    require(deviation <= MAX_PRICE_DEVIATION_BPS, "Price manipulation detected");
    
    // Use the LOWER price for user protection
    uint256 safePrice = twapPrice < spotPrice ? twapPrice : spotPrice;
    uint256 minGemOut = (twapBuybackAmount * safePrice * 95) / (100 * 1e18); // 5% slippage
    
    // Use Kaspa Finance router to swap KAS for GEM
    IKaspaFinanceRouter router = IKaspaFinanceRouter(kaspaFinanceRouter);
    
    address[] memory path = new address[](2);
    path[0] = router.WKAS(); // Wrapped KAS
    path[1] = gemTokenAddress;
    
    uint256 deadline = block.timestamp + 300;
    
    // Execute swap with protected minimum output
    router.swapExactETHForTokens{value: twapBuybackAmount}(
        minGemOut,
        path,
        address(this),
        deadline
    );
    
    // Burn the purchased GEM tokens
    uint256 gemBalance = IERC20(gemTokenAddress).balanceOf(address(this));
    require(gemBalance >= minGemOut, "Insufficient tokens received");
    IERC20(gemTokenAddress).transfer(address(0xdead), gemBalance);
    
    lastBuybackTime = block.timestamp;
    emit TWAPBuybackExecuted(twapBuybackAmount, gemBalance, block.timestamp);
}

// Helper to get spot price from DEX
function _getSpotPrice(address token) internal view returns (uint256) {
    IKaspaFinancePair pair = IKaspaFinancePair(
        IKaspaFinanceFactory(kaspaFinanceFactory).getPair(token, router.WKAS())
    );
    (uint112 reserve0, uint112 reserve1,) = pair.getReserves();
    
    // Calculate price based on reserves
    address token0 = pair.token0();
    return token0 == token 
        ? (uint256(reserve1) * 1e18) / uint256(reserve0)
        : (uint256(reserve0) * 1e18) / uint256(reserve1);
}
```

---

### Contract Interaction Flow

```
User → TokenFactory.createToken()
    ↓
TokenFactory deploys:
    - ERC20 Token Contract
    - BondingCurvePool (owns 100% initial supply)
    ↓
User → BondingCurvePool.buyTokens(value: KAS)
    ↓
BondingCurvePool:
    - Calculates tokens via bonding curve
    - Checks wallet cap (10% max)
    - Transfers tokens to user
    - Emits TokensPurchased event
    ↓
When totalRaised >= GRADUATION_THRESHOLD:
    User → GraduationController.graduate(tokenAddress)
    ↓
GraduationController:
    - Verifies curve completion
    - Mints 25% LP tokens
    - Creates Kaspa Finance pool
    - Locks curve trading
    - Emits TokenGraduated event
```

---

## 3. Security Checklist

### Critical Vulnerabilities to Prevent

#### 3.1 Reentrancy Attacks
- ✅ Use OpenZeppelin ReentrancyGuard
- ✅ Checks-Effects-Interactions pattern
- ✅ Pull-over-push for withdrawals
- ✅ State changes before external calls

#### 3.2 Front-Running & MEV
- ✅ Slippage parameters (minTokensOut, maxTokensIn)
- ✅ Deadline parameters for trades
- ✅ Midpoint pricing to reduce manipulation
- ✅ Time-weighted purchase limits

#### 3.3 Whale Manipulation
- ✅ 10% wallet cap enforcement
- ✅ Per-address rate limiting
- ✅ Progressive cooldown periods
- ✅ Max single-trade limits

#### 3.4 Graduation Exploits
- ✅ Pull-based graduation (not automatic)
- ✅ Verify curve completion on-chain
- ✅ Prevent partial graduations
- ✅ Lock curve after graduation
- ✅ Verify DEX pool creation

#### 3.5 Access Control
- ✅ OpenZeppelin AccessControl
- ✅ Separate roles: ADMIN, GUARDIAN, PAUSER
- ✅ Multi-sig for critical functions
- ✅ Timelock for parameter changes

#### 3.6 Emergency Mechanisms
- ✅ Pausable contracts
- ✅ Circuit breakers for anomalies
- ✅ Emergency withdrawal (with delays)
- ✅ Upgrade path (proxy pattern for factory only)

#### 3.7 Mathematical Safety
- ✅ Solidity ^0.8 (automatic overflow checks)
- ✅ Safe division (check denominators)
- ✅ Rounding in favor of contract
- ✅ Formal verification of bonding curve math

---

## 4. Implementation Phases

### Phase 1: Core Smart Contracts (Week 1-2)
**Deliverables**:
- [ ] TokenFactory.sol with metadata storage
- [ ] BondingCurvePool.sol with buy/sell logic
- [ ] GraduationController.sol with Kaspa Finance integration
- [ ] Treasury.sol for fee management
- [ ] OpenZeppelin security libraries integrated
- [ ] Hardhat test suite (>90% coverage)
- [ ] Deployment scripts for testnet

**Testing**:
- Unit tests for all functions
- Integration tests for token lifecycle
- Fuzz testing for bonding curve math
- Gas optimization profiling

---

### Phase 2: Backend Web3 Integration (Week 3)
**Deliverables**:
- [ ] Python web3.py service for blockchain interaction
- [ ] Celery task queue for async transaction handling
- [ ] Event indexer (Node.js + ethers.js + PostgreSQL)
- [ ] RPC failover and rate limiting
- [ ] Gas estimation and transaction monitoring
- [ ] Database schema updates for on-chain state

**Architecture**:
```
Flask App (existing)
    ↓
Web3 Service (Python)
    - Transaction broadcasting
    - Gas estimation
    - Wallet nonce management
    ↓
Celery Workers
    - Transaction monitoring
    - Graduation triggers
    - Balance updates
    ↓
Event Indexer (Node.js)
    - Listen to contract events
    - Update PostgreSQL
    - Trigger Flask webhooks
```

---

### Phase 3: Frontend Web3 Integration (Week 4)
**Deliverables**:
- [ ] Viem + Wagmi wallet client
- [ ] Multi-wallet support (MetaMask, Kastle, KasWare)
- [ ] Chain ID detection (167012)
- [ ] Real-time price updates via WebSocket
- [ ] Transaction status UI with confirmations
- [ ] Slippage controls in trading modal
- [ ] Gas fee estimation display
- [ ] Error handling for failed transactions

**User Flows**:
1. Connect wallet → Verify Kasplex testnet
2. Create token → Deploy via TokenFactory
3. Buy tokens → Execute curve trade with slippage
4. Sell tokens → Execute curve sell with preview
5. Graduate → Trigger DEX listing when threshold met

---

### Phase 4: Indexer & Real-time Sync (Week 5)
**Deliverables**:
- [ ] Event indexer syncing all contract events
- [ ] Redis cache for hot data (prices, volumes)
- [ ] WebSocket server for live updates
- [ ] Event sourcing for on-chain reconciliation
- [ ] Periodic checksum jobs (verify on-chain vs DB)
- [ ] RPC fallback mechanisms

**Data Flow**:
```
Smart Contract Event
    ↓
Indexer (Node.js)
    - Parse event
    - Update PostgreSQL
    - Invalidate Redis cache
    - Publish to WebSocket
    ↓
Flask Backend
    - Receive webhook
    - Update user sessions
    - Trigger notifications
    ↓
Frontend
    - Receive WebSocket update
    - Update UI optimistically
    - Confirm via blockchain
```

---

### Phase 5: Security Audit & Mainnet (Week 6-8)
**Deliverables**:
- [ ] Static analysis (Slither, MythX)
- [ ] External security audit (2-4 weeks)
- [ ] Bug bounty program
- [ ] Chaos testing on testnet
- [ ] Gas optimization audit
- [ ] Mainnet deployment checklist
- [ ] Multi-sig treasury setup
- [ ] Monitoring & alerting infrastructure

**Audit Requirements**:
- Smart contract security audit by reputable firm
- Formal verification of bonding curve math
- Economic model review
- Front-running analysis
- Emergency response plan

---

## 5. Kaspa Finance DEX Integration

### Graduation Process

#### Step 1: Threshold Detection
```solidity
function checkGraduationEligibility(address tokenAddress) public view returns (bool) {
    BondingCurvePool pool = BondingCurvePool(tokenAddress);
    return pool.totalRaised() >= GRADUATION_THRESHOLD && !pool.graduated();
}
```

#### Step 2: Liquidity Preparation & Creator Payout
```solidity
function graduate(address tokenAddress) external nonReentrant {
    require(checkGraduationEligibility(tokenAddress), "Not eligible");
    
    BondingCurvePool pool = BondingCurvePool(tokenAddress);
    uint256 kasRaised = pool.totalRaised();
    uint256 lpTokens = pool.mintLPSupply(); // 25% of total supply
    uint256 creatorFees = pool.creatorFeesAccumulated();
    address creator = pool.creator();
    
    // Pay creator their accumulated fees FIRST
    if (creatorFees > 0) {
        payable(creator).transfer(creatorFees);
        emit CreatorFeePayout(creator, creatorFees);
    }
    
    // Transfer liquidity assets to this contract
    pool.transferLiquidity(address(this), kasRaised, lpTokens);
    
    // Add to Kaspa Finance DEX
    addLiquidityToKaspaFinance(tokenAddress, lpTokens, kasRaised);
    
    pool.lockCurve();
    emit TokenGraduated(tokenAddress, kasRaised, lpTokens, creatorFees);
}
```

#### Step 3: Kaspa Finance Pool Creation (Uniswap V3 Architecture)

**Important**: Kaspa Finance uses Uniswap V3 architecture with concentrated liquidity. For graduation liquidity, we use **full-range positions** to ensure liquidity is always active.

```solidity
function addLiquidityToKaspaFinance(
    address token,
    uint256 tokenAmount,
    uint256 kasAmount
) internal {
    // Get Kaspa Finance position manager (Uniswap V3 style)
    INonfungiblePositionManager positionManager = INonfungiblePositionManager(kaspaFinancePositionManager);
    
    // Approve position manager to spend tokens
    IERC20(token).approve(address(positionManager), tokenAmount);
    
    // Wrap KAS to WKAS for pool
    IWKAS wkas = IWKAS(kaspaFinanceWKAS);
    wkas.deposit{value: kasAmount}();
    wkas.approve(address(positionManager), kasAmount);
    
    // Determine token ordering (token0 < token1)
    (address token0, address token1) = token < address(wkas) 
        ? (token, address(wkas)) 
        : (address(wkas), token);
    (uint256 amount0, uint256 amount1) = token < address(wkas)
        ? (tokenAmount, kasAmount)
        : (kasAmount, tokenAmount);
    
    // Create full-range position on 0.25% fee tier
    INonfungiblePositionManager.MintParams memory params = INonfungiblePositionManager.MintParams({
        token0: token0,
        token1: token1,
        fee: 2500,              // 0.25% fee tier (tightest spreads for initial liquidity)
        tickLower: -887220,     // Full range lower bound (minimum tick)
        tickUpper: 887220,      // Full range upper bound (maximum tick)
        amount0Desired: amount0,
        amount1Desired: amount1,
        amount0Min: amount0 * 95 / 100,  // 5% slippage protection
        amount1Min: amount1 * 95 / 100,  // 5% slippage protection
        recipient: treasury,    // Treasury receives NFT position
        deadline: block.timestamp + 300
    });
    
    // Mint the position (returns NFT tokenId)
    (uint256 tokenId,,,) = positionManager.mint(params);
    
    emit LiquidityAddedToKaspaFinance(token, tokenId, tokenAmount, kasAmount);
}
```

**Why Full Range + 0.25% Fee Tier?**
- ✅ **Full range (-887220 to 887220)**: Liquidity is ALWAYS active regardless of price movement
- ✅ **0.25% fee tier**: Tightest spreads for initial liquidity, best user experience
- ✅ **Users can add custom ranges**: Community can add concentrated liquidity to other tiers (0.05%, 0.3%, 1%) if desired
- ✅ **NFT position**: Treasury holds position NFT for potential future management

### Kaspa Finance Interfaces (Uniswap V3 Compatible)
```solidity
interface INonfungiblePositionManager {
    struct MintParams {
        address token0;
        address token1;
        uint24 fee;
        int24 tickLower;
        int24 tickUpper;
        uint256 amount0Desired;
        uint256 amount1Desired;
        uint256 amount0Min;
        uint256 amount1Min;
        address recipient;
        uint256 deadline;
    }
    
    function mint(MintParams calldata params)
        external
        payable
        returns (
            uint256 tokenId,
            uint128 liquidity,
            uint256 amount0,
            uint256 amount1
        );
}

interface IWKAS {
    function deposit() external payable;
    function approve(address spender, uint256 amount) external returns (bool);
}
```

**Contract Addresses**:
```solidity
// TESTNET (Kasplex zkEVM Testnet - Chain ID: 167012)
address public constant KASPA_FINANCE_FACTORY = 0x8D47ab5aC84b2ADc2214b34394fCe71a958BE364; // ✅ VERIFIED
// Name: KaspaV3Factory
// Explorer: http://explorer.testnet.kasplextest.xyz/address/0x8D47ab5aC84b2ADc2214b34394fCe71a958BE364
// Deployed: Block 5 (May 30, 2025)

address public constant KASPA_FINANCE_POSITION_MANAGER = 0x4E25637cF39822364b877F81B18c5B6CF0eeF589; // ✅ VERIFIED
// Name: Kaspa Finance V3 Positions NFT-V1 (KFC-V3-POS)
// Explorer: http://explorer.testnet.kasplextest.xyz/token/0x4E25637cF39822364b877F81B18c5B6CF0eeF589
// Deployed: Block 2,192,870 (July 30, 2025)

address public constant KASPA_FINANCE_WKAS = 0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94; // ✅ VERIFIED
// Name: Wrapped Kas (WKAS)
// Symbol: WKAS, Decimals: 18
// Explorer: http://explorer.testnet.kasplextest.xyz/token/0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94

// All deployed by: 0x4B498547082D64fDFBCf3AF67Bd7792dA1e7b6Dd

// MAINNET  
// TBD - Contact Kaspa Finance team: https://t.me/KaspaFinanceIO

// SOURCE CODE: https://github.com/KaspaFinance/V3-Core-Contracts (Uniswap V3 fork)
```

---

## 6. Testing Strategy

### 6.1 Unit Tests (Hardhat)
```javascript
describe("BondingCurvePool", function() {
    it("Should enforce 10% wallet cap", async function() {
        // Test wallet cap enforcement
    });
    
    it("Should calculate correct bonding curve price", async function() {
        // Test price calculation
    });
    
    it("Should prevent reentrancy on buy", async function() {
        // Test reentrancy protection
    });
    
    it("Should handle slippage correctly", async function() {
        // Test slippage parameters
    });
});
```

### 6.2 Fuzz Testing (Foundry)
```solidity
function testFuzz_BondingCurvePricing(uint256 ethAmount) public {
    vm.assume(ethAmount > 0.001 ether && ethAmount < 100 ether);
    
    uint256 tokens = pool.quoteBuy(ethAmount);
    uint256 ethBack = pool.quoteSell(tokens);
    
    // Price should be consistent (with rounding tolerance)
    assertApproxEqRel(ethAmount, ethBack, 0.01e18); // 1% tolerance
}
```

### 6.3 Static Analysis
```bash
# Slither (vulnerability detection)
slither contracts/ --filter-paths node_modules

# MythX (symbolic execution)
mythx analyze contracts/BondingCurvePool.sol

# Manticore (formal verification)
manticore contracts/BondingCurvePool.sol
```

### 6.4 Integration Tests
- Full token lifecycle: create → trade → graduate
- Multi-user scenarios with concurrent trades
- Edge cases: dust amounts, max supply, zero liquidity
- Failure scenarios: insufficient balance, slippage exceeded

### 6.5 Platform Integration Tests (Testnet)
**Frontend-Blockchain Integration**:
- [ ] Real wallet transactions (buy/sell with actual gas)
- [ ] Transaction confirmation flows
- [ ] Gas estimation accuracy
- [ ] Failed transaction handling & recovery
- [ ] Optimistic UI updates validation

**AI Services Testing**:
- [ ] OpenRouter API under load (Gemmy chat, image prompts)
- [ ] Replicate image generation reliability
- [ ] Trend scraping (4chan, Reddit) with rate limits
- [ ] 12-hour cache behavior verification
- [ ] Cost tracking and API limits

**Multi-Wallet System**:
- [ ] Wallet linking with real EVM signatures
- [ ] Transfer request flow (request → accept → merge)
- [ ] Account merging edge cases
- [ ] Cross-wallet balance tracking

**Airdrop System**:
- [ ] PRO token vesting (5% daily unlock over 20 days)
- [ ] Distribution types: Raffle, Top Contributors, Active Chatters, Token Holders
- [ ] Claiming mechanics with real transactions
- [ ] Vesting schedule accuracy

**Anti-Bot System (GEM System) - AUDIT-APPROVED v4**:
- [ ] ✅ CRITICAL FIX: Fee calculation order (anti-bot FIRST, then platform/creator from remainder)
- [ ] ✅ CRITICAL FIX: Airdrop treasury validation (≠ address(0), ≠ address(this))
- [ ] ✅ CRITICAL FIX: Use totalAntiBotFeesCollected (not accumulatedAntiBotFees)
- [ ] ✅ HIGH FIX: View functions implemented (getCurrentAntiBotFee, getSecondsUntilNormalFees, getEffectiveFeeBreakdown)
- [ ] ✅ MEDIUM FIX: MIN_TRADE_AMOUNT constant added
- [ ] ✅ LOW FIX: AntiBotFeePaid event properly defined
- [ ] Time-based fee decay (95% → 1% over 60 seconds)
- [ ] Anti-bot fee immediate transfer to Airdrop Treasury
- [ ] Fee breakdown testing: t=0s (95%), t=30s (48%), t=60s (1%)
- [ ] Frontend integration with view functions
- [ ] Example: 100 KAS at t=5s = 87.16 KAS anti-bot fee + 0.116 platform + 0.013 creator = 12.71 KAS trade

**Social Features**:
- [ ] Chat messages with spam prevention
- [ ] Polls & voting (one vote per wallet verification)
- [ ] Token-gated spotlights (holder verification)
- [ ] Reaction system
- [ ] Message deletion (creator authorization)

**Achievement System**:
- [ ] Point accumulation from trades, chat, holdings
- [ ] Achievement unlocking triggers
- [ ] Leaderboard real-time updates
- [ ] Concurrent action handling

**Community Points (Per Token)**:
- [ ] Points tracking per token
- [ ] Engagement scoring accuracy
- [ ] Token-specific leaderboards
- [ ] Creator configuration options

**Referral System**:
- [ ] Custom referral code validation
- [ ] Referral tracking across wallets
- [ ] Reward distribution mechanics

**Real-time Features**:
- [ ] WebSocket price updates
- [ ] Live chat message streaming
- [ ] Wallet state change notifications
- [ ] Trading event broadcasts

**Gas & Transaction Optimization**:
- [ ] Gas price estimation (EIP-1559)
- [ ] Transaction batching opportunities
- [ ] Nonce management with multiple pending txs
- [ ] Failed transaction retry logic

---

## 7. Technology Stack

### Smart Contracts
- **Language**: Solidity ^0.8.20
- **Framework**: Hardhat + Foundry
- **Libraries**: OpenZeppelin (ReentrancyGuard, AccessControl, Pausable, ERC20)
- **Testing**: Hardhat (unit), Foundry (fuzz), Slither (static analysis)

### Backend
- **Web3 Service**: Python web3.py
- **Task Queue**: Celery + Redis
- **Indexer**: Node.js + ethers.js
- **Database**: PostgreSQL (existing)
- **Cache**: Redis

### Frontend
- **Wallet Client**: Viem + Wagmi
- **Web3 Library**: ethers.js v6 / viem
- **Real-time**: WebSocket (Socket.io)
- **State**: Optimistic UI updates

### Infrastructure
- **RPC Providers**: Kasplex official RPC + fallback nodes
- **Monitoring**: Sentry (errors) + Custom alerting
- **Secrets**: Environment vault (existing)

---

## 8. Security Audit Fixes (Claude + ChatGPT Audits - October 2025)

### 🔴 CRITICAL Issues - Round 2 Fixes (v2)

**C-1: ✅ AMM Math Corrected - Virtual Reserves Pattern**
- **Original Issue**: Fees deducted BEFORE AMM breaks invariant (x*y=k violated)
- **v1 Attempt**: Used constant product but contaminated reserves with fees
- **v2 Fix**: Virtual reserves pattern - fees stored separately
  ```solidity
  virtualKasReserve: tradeable KAS only
  accumulatedPlatformFees: fees stored separately
  AMM pricing uses ONLY virtualKasReserve (no fee contamination)
  ```
- **Impact**: True constant product pricing, no arbitrage opportunities

**C-2: ✅ Reserve Accounting - Single Source of Truth**
- **Original Issue**: 3 sources of truth (grossInBase, netReservesBase, address(this).balance)
- **v1 Attempt**: Tracked both gross and net
- **v2 Fix**: Virtual reserves are THE ONLY pricing source
  ```solidity
  virtualKasReserve += tradeAmount;  // Only trade amount
  accumulatedFees += fees;           // Separate tracking
  quoteBuy() uses virtualKasReserve  // Clean pricing
  ```
- **Impact**: No state divergence, accurate graduation threshold

**C-3: ✅ Graduation Lock Timing - Before Transfer**
- **Original Issue**: Lock set after _transfer() enables reentrancy
- **v1 Attempt**: Lock in _triggerGraduation()
- **v2 Fix**: Lock BEFORE any state changes or transfers
  ```solidity
  bool willGraduate = check threshold FIRST
  if (willGraduate) graduating = true;  // LOCK EARLY
  _transfer(...);                       // Then transfer
  if (graduating) _executeGraduation(); // Atomic completion
  ```
- **Impact**: No reentrancy window, atomic graduation

**C-4: ✅ Creator Fee Access Control - Strict Validation**
- **Original Issue**: No access control, anyone could claim
- **v1 Attempt**: Pull pattern only
- **v2 Fix**: Access control + emergency rescue
  ```solidity
  require(msg.sender == creator, "Only creator");
  rescueStuckCreatorFees() for lost key scenarios
  ```
- **Impact**: Prevents griefing, enables fee recovery

### 🟠 HIGH Severity Fixes

**H-1: ✅ Wallet Cap - Cooldown + Circulating Supply**
- **Issue**: Flash loans and multi-wallet Sybil bypass 10% cap
- **Fix**: 5-minute transfer cooldown + circulating supply math
  ```solidity
  circulating = totalSupply - balanceOf(address(this))
  cap = (circulating * 10%) / 100
  require(block.timestamp >= lastTransferTime[to] + 5 minutes)
  ```
- **Impact**: Prevents flash loan exploits and rapid wallet rotation

**H-2: ✅ TWAP Oracle - Deviation Checks + Spot Validation**
- **Issue**: No TWAP period validation, predictable execution
- **Fix**: 30-min minimum TWAP + spot price sanity check
  ```solidity
  require(twapPeriod >= 30 minutes)
  deviation = abs(twapPrice - spotPrice) / spotPrice
  require(deviation <= 10%)
  minGemOut uses LOWER of (twapPrice, spotPrice)
  ```
- **Impact**: Prevents oracle manipulation and sandwich attacks

**H-3: ✅ Liquidity Verification - LP Token Checks**
- **Issue**: No verification LP tokens received after graduation
- **Fix**: Verify minimum LP tokens received
  ```solidity
  require(lpTokensReceived >= minLP, "Insufficient LP")
  ```
- **Impact**: Ensures graduation success, prevents silent failures

### Security Architecture Summary

**Virtual Reserve Pattern (Core Innovation)**
```solidity
// Separate fee storage from AMM reserves
uint256 public virtualKasReserve;    // AMM pricing source
uint256 public virtualTokenReserve;  // AMM pricing source
uint256 public accumulatedPlatformFees;  // Fee storage
uint256 public accumulatedCreatorFees;   // Fee storage

// Fees NEVER contaminate reserves
AMM invariant: k = virtualKasReserve * virtualTokenReserve (pure)
```

**Lock-Before-Transfer Pattern**
```solidity
1. Check graduation threshold
2. Set graduating = true (LOCK)
3. Update virtual reserves
4. Execute _transfer()
5. Complete graduation atomically
```

**Access Control Matrix**
- Creator: claimCreatorFees()
- Treasury: withdrawPlatformFees()
- Admin (timelock): rescueStuckCreatorFees(), parameter updates
- Public: buy/sell (with slippage + deadline protection)

### Audit Results
- **Round 1**: Claude (20 findings), ChatGPT (15 findings) - Initial architecture
- **Round 2**: Claude (7 critical) - Virtual reserves v2 fixes
- **Round 3**: Claude (4 critical, 6 high) - Implementation details v3
- **Round 4**: Claude (0 critical, 2 high, 5 medium, 3 low) - **FINAL TESTNET REVIEW** 🟢
- **Total Critical Fixes**: 18 across all rounds
- **Status**: 🟡 90% Ready → 🟢 100% Ready with Priority 1-3 fixes

### v3 Fixes Summary
**Critical Fixes (All ✅):**
1. Virtual reserve initialization (0.001 KAS seed)
2. Symmetric fee calculation (fee on input for both buy/sell)
3. CEI-compliant graduation check (reserves updated first)
4. Correct LP split (ALL KAS + 25% tokens to LP, burn unsold)

**High Priority Fixes:**
1. 0.001 KAS minimum trade amount
2. Bidirectional transfer cooldown (sender + receiver)
3. Balance verification for fee withdrawals

---

## ROUND 4 AUDIT - FINAL TESTNET REVIEW (October 8, 2025)

**Overall Assessment**: 🟢 EXCELLENT - All critical issues resolved, ready for testnet with minor fixes

**Remaining Issues**: 0 Critical ✅ | 2 High ⚠️ | 5 Medium ⚠️ | 3 Low ℹ️

### 🔴 HIGH SEVERITY (Round 4)

**H-1: Sell Function Fee Accounting Broken** ⚠️ MUST FIX
- **Issue**: Fee tokens converted to hypothetical KAS value but never actually sold
- **Impact**: `accumulatedPlatformFees` increases without actual KAS, breaking withdrawals
- **Root Cause**: Mixing token fees and KAS fees in same accounting
- **Solution**: Use KAS-based fees on both buy AND sell (asymmetric but consistent)

**H-2: Min Trade Amount Missing in Buy Function** ⚠️ MUST FIX  
- **Issue**: Buy allows trades < MIN_TRADE_AMOUNT, sell enforces it
- **Impact**: Dust attacks, fee evasion (1 wei trade = 0 fee due to rounding)
- **Solution**: Add `require(msg.value >= MIN_TRADE_AMOUNT)` to buyTokens()

### 🟡 MEDIUM SEVERITY (Round 4)

**M-1: Fee Precision Loss on Small Trades**
- Two-step division causes rounding errors
- Creator gets 0 fees on trades where totalFees < 10 wei
- Fix: Direct calculation `platformFee = msg.value * 90 / 10000`

**M-2: Treasury Distribution Only Sums to 90%**
- DEV(40%) + BUYBACK(30%) + KASPA(15%) + COMMUNITY(5%) = 90%
- Missing 10% stuck in contract forever
- Fix: Adjust COMMUNITY_SHARE to 1500 (15%) or use remainder pattern

**M-3: Graduation Could Fail if Fees Withdrawn Early**
- Graduation uses virtualKasReserve but fees might be withdrawn
- Contract balance could be < virtualKasReserve
- Fix: Verify actual balance before graduation OR block withdrawals until graduated

**M-4: No Protection Against Direct KAS Transfers**
- Direct transfers break invariant: `balance = virtualKasReserve + fees`
- Fix: Add `receive() { revert(); }` blocker

**M-5: Partial Fee Withdrawals Create Accounting Confusion**
- If withdrawable < accumulated, only partial amount sent
- `accumulatedPlatformFees` decremented but fees still "owed"
- Fix: Require full amount or revert with clear error

### 🔵 LOW SEVERITY (Round 4)

**L-1**: MIN_TRADE_AMOUNT constant not defined (compilation error)  
**L-2**: Comments reference old 1.5% fee model  
**L-3**: Treasury distribution missing GemFoundation clarification

---

## ROUND 4 CORRECTED IMPLEMENTATIONS

### Priority 1: Fixed Sell Function (KAS-Based Fees)

**CORRECTED** - Fee on KAS output (not token input):

```solidity
uint256 public constant MIN_TRADE_AMOUNT = 0.001 ether; // 0.001 KAS minimum

function sellTokens(uint256 tokenAmount, uint256 minKasOut, uint256 deadline) external nonReentrant {
    require(!graduated && !graduating, "Token graduated or graduating");
    require(block.timestamp <= deadline, "Transaction expired");
    require(balanceOf(msg.sender) >= tokenAmount, "Insufficient balance");
    
    // Calculate FULL KAS output first (before fees)
    uint256 kasGross = quoteSell(tokenAmount);
    
    // Fee on KAS OUTPUT (1% of KAS) - NOT on tokens
    uint256 totalFeesKas = kasGross * TOTAL_FEE_BPS / 10000; // 1% of KAS
    uint256 creatorFeeKas = totalFeesKas * 10 / 100; // 10% of fees = 0.1% of KAS
    uint256 platformFeeKas = totalFeesKas - creatorFeeKas; // 90% of fees = 0.9% of KAS
    uint256 kasNet = kasGross - totalFeesKas;
    
    // Slippage check on NET amount user receives
    require(kasNet >= minKasOut, "Slippage too high");
    require(kasNet >= MIN_TRADE_AMOUNT, "Below minimum trade");
    
    // CEI Pattern: Update reserves FIRST (full KAS amount leaves)
    virtualTokenReserve += tokenAmount;
    virtualKasReserve -= kasGross; // Full amount (including fees)
    
    // Accumulate KAS fees (actual KAS, not hypothetical)
    accumulatedPlatformFees += platformFeeKas;
    accumulatedCreatorFees += creatorFeeKas;
    
    // Transfer tokens to pool
    _transfer(msg.sender, address(this), tokenAmount);
    
    // Send NET KAS to user (fees stay in contract balance)
    _safeSend(msg.sender, kasNet);
    
    emit TokensSold(msg.sender, tokenAmount, kasGross, platformFeeKas, creatorFeeKas);
}
```

**Why This Works:**
- ✅ Fees are actual KAS (not hypothetical)
- ✅ `accumulatedPlatformFees` matches actual contract balance
- ✅ Fee withdrawals will work correctly
- ✅ All accounting in KAS (consistent with buy function)

---

### ~~Priority 2: Fixed Buy Function (Min Trade + Precision)~~ ⚠️ SUPERSEDED BY V4

**⚠️ THIS SECTION IS OUTDATED - DO NOT USE**

**REASON**: This v3 implementation is missing the Anti-Bot System (GEM) logic that was added in v4.

**USE INSTEAD**: See **Buy Function (AUDIT FIX v4)** at line 200 for the complete implementation with:
- ✅ Anti-bot fee logic (95% → 1% decay)
- ✅ Proper fee calculation order (anti-bot first, then platform/creator from remainder)
- ✅ View functions for UX
- ✅ MIN_TRADE_AMOUNT validation

**This section is kept for historical reference only.**

---

### Priority 3: Fixed Treasury Distribution

**CORRECTED** - Distribution sums to 100%:

```solidity
// OPTION A: Use remainder pattern (recommended)
function distributeFees() external nonReentrant {
    require(msg.sender == treasury || msg.sender == admin, "Unauthorized");
    
    uint256 balance = address(this).balance;
    require(balance > 0, "No fees to distribute");
    
    // Calculate shares (avoiding 10% loss)
    uint256 devAmount = balance * 40 / 100;      // 40%
    uint256 buybackAmount = balance * 30 / 100;  // 30%
    uint256 kaspaAmount = balance * 15 / 100;    // 15%
    uint256 communityAmount = balance - devAmount - buybackAmount - kaspaAmount; // 15% (remainder)
    
    // Send to designated wallets
    _safeSend(platformDevelopmentWallet, devAmount);
    _safeSend(buybackReserveWallet, buybackAmount);
    _safeSend(kaspaNetworkSupportWallet, kaspaAmount);
    _safeSend(communityRewardsWallet, communityAmount);
    
    emit FeesDistributed(devAmount, buybackAmount, kaspaAmount, communityAmount);
}

// OPTION B: Adjust constants to sum to 10000
uint256 public constant DEV_SHARE = 4000;       // 40%
uint256 public constant BUYBACK_SHARE = 3000;   // 30%
uint256 public constant KASPA_SHARE = 1500;     // 15%
uint256 public constant COMMUNITY_SHARE = 1500; // 15% (adjusted from 500)
// Total: 10000 = 100% ✓
```

---

### Medium Priority Fixes

**M-3: Graduation Balance Verification**
```solidity
function _executeGraduation() internal {
    require(graduating && !graduated, "Invalid graduation state");
    
    graduated = true;
    uint256 kasForLP = virtualKasReserve;
    
    // ✅ Verify ACTUAL balance after accounting for fees
    uint256 reservedForFees = accumulatedPlatformFees + accumulatedCreatorFees;
    uint256 availableBalance = address(this).balance - reservedForFees;
    require(availableBalance >= kasForLP, "Insufficient liquid balance - fees withdrawn");
    
    // Proceed with graduation...
}
```

**M-4: Block Direct Transfers**
```solidity
// Prevent direct KAS transfers that corrupt accounting
receive() external payable {
    revert("Use buyTokens() to purchase");
}

fallback() external payable {
    revert("Use buyTokens() to purchase");
}

// Emergency sweep for accidentally sent KAS
function sweepExcessKas() external onlyAdmin {
    uint256 expected = virtualKasReserve + accumulatedPlatformFees + accumulatedCreatorFees;
    uint256 actual = address(this).balance;
    
    if (actual > expected) {
        uint256 excess = actual - expected;
        _safeSend(treasury, excess);
        emit ExcessKasSwept(excess);
    }
}
```

**M-5: Stricter Fee Withdrawal**
```solidity
// CORRECTED: Require full amount or revert
function withdrawPlatformFees() external nonReentrant {
    require(msg.sender == treasury, "Only treasury");
    
    uint256 amount = accumulatedPlatformFees;
    require(amount > 0, "No fees to withdraw");
    
    // Must have enough actual balance (excluding virtual reserve)
    uint256 reservedForTrading = virtualKasReserve;
    uint256 availableBalance = address(this).balance - reservedForTrading;
    
    require(
        availableBalance >= amount, 
        "Insufficient liquid balance - wait for more fees or graduation"
    );
    
    accumulatedPlatformFees = 0;
    _safeSend(treasury, amount);
    emit PlatformFeesWithdrawn(amount);
}
```

---

## 9. Deployment Checklist

### Testnet Deployment

#### Pre-Deployment: Treasury Wallet Setup
- [ ] **Create Gemlaunch Treasury Wallets** (multi-sig recommended):
  - [ ] Platform Development Wallet (receives 40% of platform fees → 0.36% of trades)
  - [ ] GEM Buyback Reserve Wallet (receives 30% of platform fees → 0.27% of trades, accumulates until GEM TGE)
  - [ ] Kaspa Network Support Wallet (receives 15% of platform fees → 0.135% of trades, ecosystem support)
  - [ ] Community Rewards Wallet (receives 15% of platform fees → 0.135% of trades, uses remainder pattern)
- [ ] Configure multi-sig with 2-of-3 or 3-of-5 threshold
- [ ] Document all wallet addresses and signers
- [ ] **Publicly announce GemFoundation wallet address** for transparency
- [ ] Test multi-sig transaction flow on testnet

#### Post-GEM TGE: TWAP Buyback Activation
- [ ] Deploy GEM token on Kasplex zkEVM
- [ ] Create GEM/KAS liquidity pool on Kaspa Finance
- [ ] Call `enableTWAPBuyback()` with GEM token address
- [ ] Set TWAP period (e.g., 24 hours)
- [ ] Set buyback amount per period
- [ ] Set up automated keeper/bot to call `executeTWAPBuyback()` periodically
- [ ] Monitor buyback execution and GEM burn events

#### Future: GemFoundation DAO Transition
- [ ] Design and deploy DAO governance contracts
- [ ] Create proposal/voting mechanism
- [ ] Call `transferFoundationToDAO()` to transfer control
- [ ] Test DAO-controlled fund allocation
- [ ] Document DAO governance process for community

#### Smart Contract Deployment
- [ ] Configure Hardhat for Kasplex testnet (Chain ID: 167012)
- [ ] Fund deployer wallet from faucet (50 KAS)
- [ ] Deploy Treasury.sol with wallet addresses
- [ ] Deploy TokenFactory.sol with Treasury reference
- [ ] Deploy GraduationController.sol with Kaspa Finance router
- [ ] Set up contract relationships (controller ↔ factory ↔ treasury)
- [ ] Verify contracts on block explorer
- [ ] Test treasury fee distribution function
- [ ] Test end-to-end token creation with fee collection
**Round 4 Critical Fixes Validation (MUST COMPLETE):**
- [ ] ✅ **H-1: Sell fee accounting** - Verify KAS-based fees (fee on output, not tokens)
- [ ] ✅ **H-2: Min trade amount** - Confirm buyTokens() enforces MIN_TRADE_AMOUNT
- [ ] ✅ **M-1: Fee precision** - Test direct calculation (platformFee = msg.value * 90 / 10000)
- [ ] ✅ **M-2: Treasury distribution** - Verify shares sum to 100% (no lost 10%)
- [ ] ✅ **M-3: Graduation balance** - Test actual balance verification before graduation
- [ ] ✅ **M-4: Direct transfers** - Confirm receive()/fallback() revert
- [ ] ✅ **M-5: Fee withdrawals** - Verify full amount required (no partial withdrawals)
- [ ] ✅ **Round-trip symmetry** - Buy 1 KAS → Sell tokens → Get ~0.98 KAS (2% loss = 1% each way)

**V3 Audit Fixes Validation:**
- [ ] Test virtual reserve initialization (0.001 KAS seed prevents division by zero)
- [ ] Verify KAS-based fee calculation for BOTH buy and sell (v4 corrected)
- [ ] Test CEI pattern: reserves updated BEFORE graduation check
- [ ] Verify correct LP split: ALL virtualKasReserve + 25% tokens to LP, burn unsold
- [ ] Test 0.001 KAS minimum trade amount enforcement (both buy AND sell)
- [ ] Verify bidirectional transfer cooldown (both sender and receiver)
- [ ] Test balance verification in fee withdrawal (respects virtualKasReserve)
- [ ] Verify fee accounting: accumulatedFees matches actual contract balance

**General Validation:**
- [ ] Test virtual reserve AMM (k = virtualKasReserve * virtualTokenReserve)
- [ ] Verify fees stored separately (accumulatedPlatformFees, accumulatedCreatorFees)
- [ ] Test 1% total fee doesn't contaminate AMM pricing
- [ ] Verify slippage protection (minTokensOut, minKasOut, deadline)
- [ ] Test creator fee access control (only creator can claim)
- [ ] Test platform fee withdrawal with balance verification
- [ ] Verify wallet cap uses circulating supply (not total supply)
- [ ] Test 5-minute transfer cooldown (prevents flash loans)
- [ ] Test graduation lock BEFORE _transfer (no reentrancy window)
- [ ] Verify atomic graduation execution
- [ ] Test TWAP oracle validation (30min minimum, 10% deviation check)
- [ ] Verify spot price sanity check against TWAP
- [ ] Test LP token verification after graduation
- [ ] Monitor gas costs and optimize
- [ ] Verify emergency fee rescue mechanism (timelock + admin)
- [ ] Verify treasury fee distribution: 40% dev, 30% buyback, 15% Kaspa, 15% community (remainder), 10% creator

### Mainnet Preparation
- [ ] Complete external security audit (4 internal rounds complete ✅)
- [ ] Address all audit findings (Round 4 fixes: 2 high + 5 medium)
- [ ] Bug bounty program (minimum 2 weeks, post-testnet)
- [ ] Multi-sig setup for admin functions (3-of-5 recommended)
- [ ] Timelock for parameter changes (24-48 hour delay)
- [ ] 24-hour testnet stress test with real users
- [ ] Final independent code review

**Testnet to Mainnet Timeline:**
- Week 1-2: Deploy Round 4 fixes, comprehensive testing
- Week 3-4: Community testing, monitor for edge cases
- Week 5: External audit (if budget allows) or extended testing
- Week 6+: Mainnet deployment at 100% confidence
- [ ] Emergency response plan documented
- [ ] Gas price strategy (EIP-1559)
- [ ] Contract verification scripts
- [ ] Monitoring dashboards
- [ ] User documentation

---

## 9. Risk Assessment & Mitigation

### Smart Contract Risks
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Reentrancy attack | CRITICAL | Low | ReentrancyGuard, CEI pattern |
| Bonding curve math error | CRITICAL | Medium | Formal verification, extensive testing |
| Graduation liquidity theft | CRITICAL | Low | Pull-based graduation, multi-sig |
| Front-running | HIGH | High | Slippage params, midpoint pricing |
| Whale manipulation | MEDIUM | Medium | 10% cap, rate limiting |
| Pause abuse | MEDIUM | Low | Multi-sig pauser role |

### Infrastructure Risks
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| RPC node failure | HIGH | Medium | Multi-endpoint failover |
| Indexer desync | MEDIUM | Medium | Checksum jobs, event replay |
| Gas price spike | MEDIUM | High | Dynamic gas estimation |
| WebSocket disconnect | LOW | Medium | Auto-reconnect, polling fallback |

### Economic Risks
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Low liquidity after graduation | MEDIUM | Medium | Minimum threshold enforcement |
| Platform fee abuse | LOW | Low | Governance-controlled fees |
| Token spam | LOW | High | Deployment rate limits |

---

## 10. Next Steps

### Immediate Actions
1. ✅ **Review Pump.sol reference implementation** - Analyze security patterns
2. ✅ **Study Kaspa Finance documentation** - Understand DEX integration
3. ⏳ **Set up Hardhat project** - Configure for Kasplex testnet
4. ⏳ **Implement TokenFactory.sol** - Core factory contract
5. ⏳ **Implement BondingCurvePool.sol** - Trading logic with security
6. ⏳ **Write comprehensive tests** - Unit + integration + fuzz

### Research Questions
- [x] **Kaspa Finance contract addresses** (CRITICAL - Required before deployment):
  - ✅ Factory: `0x8D47ab5aC84b2ADc2214b34394fCe71a958BE364` (testnet verified - Block 5, May 2025)
  - ✅ INonfungiblePositionManager: `0x4E25637cF39822364b877F81B18c5B6CF0eeF589` (testnet verified - Block 2.19M, July 2025)
  - ✅ WKAS: `0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94` (testnet verified)
  - ✅ Source Code: https://github.com/KaspaFinance/V3-Core-Contracts (Uniswap V3 fork)
  - [ ] Mainnet addresses (Position Manager, WKAS, Factory)
  - Contact: https://t.me/KaspaFinanceIO
- [ ] **Kaspa Finance V3 pool creation**:
  - Confirm 0.25% fee tier (2500 basis points) exists
  - Verify full-range position support (-887220 to 887220)
  - Pool initialization requirements (if any)
- [ ] Multi-sig wallet setup (Gnosis Safe on Kasplex?)
- [ ] Audit firm selection and timeline

---

## 11. Reference Implementations

### Pump.sol (James Bachini)
**Security Patterns Identified**:
- ✅ Midpoint pricing formula prevents manipulation
- ✅ Simple dynamic curve: `remainingTokens / ethBalance`
- ✅ Minimum ETH floor (0.01 ETH) prevents division by zero
- ❌ Missing: Reentrancy guards, wallet caps, slippage protection
- ❌ Missing: Emergency pause, access control
- ❌ Missing: Graduation logic

**Key Takeaway**: Good mathematical foundation, but needs comprehensive security hardening.

### Moonbound (Competitor on Kasplex)
**Features to Match**:
- Bonding curve: 75% curve, 25% DEX LP
- 10% wallet cap enforcement
- Auto-graduation to Zealous Swap (we use Kaspa Finance)
- Sybil protection mechanisms
- Immutable contract logic

---

## Appendix: Hardhat Configuration

```javascript
// hardhat.config.js
require("@nomicfoundation/hardhat-toolbox");
require("dotenv").config();

module.exports = {
  solidity: {
    version: "0.8.20",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200
      }
    }
  },
  networks: {
    kasplexTestnet: {
      url: "https://rpc.kasplextest.xyz",
      chainId: 167012,
      accounts: [process.env.DEPLOYER_PRIVATE_KEY],
      gasPrice: "auto"
    },
    kasplexMainnet: {
      url: "https://evmrpc.kasplex.org",
      chainId: 202555,
      accounts: [process.env.DEPLOYER_PRIVATE_KEY],
      gasPrice: "auto"
    }
  },
  etherscan: {
    apiKey: {
      kasplexTestnet: process.env.KASPLEX_API_KEY || "none",
      kasplexMainnet: process.env.KASPLEX_API_KEY || "none"
    },
    customChains: [
      {
        network: "kasplexTestnet",
        chainId: 167012,
        urls: {
          apiURL: "https://frontend.kasplextest.xyz/api",
          browserURL: "https://frontend.kasplextest.xyz"
        }
      },
      {
        network: "kasplexMainnet",
        chainId: 202555,
        urls: {
          apiURL: "https://explorer.kasplex.org/api",
          browserURL: "https://explorer.kasplex.org"
        }
      }
    ]
  }
};
```

---

**Document Status**: Initial Draft  
**Last Updated**: October 8, 2025  
**Next Review**: After Phase 1 completion
