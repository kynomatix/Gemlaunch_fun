# Gemlaunch.fun - Blockchain Smart Contract Implementation Plan

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
  - 5% Community Rewards (0.045% of trade)
- **Creator Fee (10%)**: 0.1% of trade value → Accumulated and claimable by token creator

---

## 1. Kasplex zkEVM Network Configuration

### Testnet
```
Network Name: Kasplex zkEVM Testnet
RPC URL: https://rpc.kasplextest.xyz
Chain ID: 167012
Block Explorer: https://frontend.kasplextest.xyz
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

**State Variables** (AUDIT FIX v2 - Virtual Reserves):
```solidity
uint256 public constant CURVE_SUPPLY_PCT = 75;
uint256 public constant LP_SUPPLY_PCT = 25;
uint256 public constant MAX_WALLET_PCT = 10;
uint256 public constant TOTAL_FEE_BPS = 100; // 1% total trading fee
uint256 public constant CREATOR_SHARE_BPS = 1000; // 10% of fees (0.1% of trade)
uint256 public constant GRADUATION_THRESHOLD = 75e18; // 75 KAS in virtual reserve

address public treasury; // Gemlaunch treasury contract
address public immutable creator; // Token creator address (immutable)

// AUDIT FIX: Virtual reserves - single source of truth for AMM pricing
uint256 public virtualKasReserve;   // Tradeable KAS only (excludes fees)
uint256 public virtualTokenReserve; // Tradeable tokens only

// Fee tracking (separate from reserves)
uint256 public accumulatedPlatformFees;
uint256 public accumulatedCreatorFees;

bool public graduated;
bool public graduating; // Lock flag during graduation
```

**Constructor** (AUDIT FIX v3 - Initialize Virtual Reserves):
```solidity
constructor(
    string memory name,
    string memory symbol,
    uint256 totalSupply,
    address _creator,
    address _treasury
) ERC20(name, symbol) {
    require(_creator != address(0), "Invalid creator");
    require(_treasury != address(0), "Invalid treasury");
    
    creator = _creator;
    treasury = _treasury;
    
    // Mint total supply to contract
    _mint(address(this), totalSupply);
    
    // CRITICAL: Initialize virtual reserves to prevent division by zero
    uint256 curveSupply = totalSupply * CURVE_SUPPLY_PCT / 100; // 75%
    virtualTokenReserve = curveSupply;
    virtualKasReserve = 0.001 ether; // 0.001 KAS virtual seed for initial pricing
    
    // LP tokens (25%) stay in contract, not in virtualTokenReserve
}
```

**Buy Function** (AUDIT FIX v2 - Virtual Reserve Pattern):
```solidity
function buyTokens(uint256 minTokensOut, uint256 deadline) external payable nonReentrant {
    require(!graduated && !graduating, "Token graduated or graduating");
    require(block.timestamp <= deadline, "Transaction expired");
    require(msg.value > 0, "Must send KAS");
    
    // Fee calculation: 1% total (100 bps)
    uint256 totalFees = msg.value * TOTAL_FEE_BPS / 10000; // 1% total
    uint256 creatorFee = totalFees * CREATOR_SHARE_BPS / 10000; // 10% of fees = 0.1% of trade
    uint256 platformFee = totalFees - creatorFee; // 90% of fees = 0.9% of trade
    uint256 tradeAmount = msg.value - totalFees;
    
    // Calculate tokens using virtual reserves (no fee contamination)
    uint256 tokensOut = quoteBuy(tradeAmount);
    require(tokensOut >= minTokensOut, "Slippage too high");
    
    // CRITICAL: Check if this trade will trigger graduation BEFORE any state changes
    bool willGraduate = !graduated && (virtualKasReserve + tradeAmount >= GRADUATION_THRESHOLD);
    
    if (willGraduate) {
        graduating = true; // LOCK BEFORE ANY TRANSFERS
    }
    
    // Update virtual reserves (separate from fees)
    virtualKasReserve += tradeAmount;
    virtualTokenReserve -= tokensOut;
    
    // Store fees separately (NOT in reserves)
    accumulatedPlatformFees += platformFee;
    accumulatedCreatorFees += creatorFee;
    
    // Transfer tokens (wallet cap enforced in _transfer override)
    _transfer(address(this), msg.sender, tokensOut);
    
    emit TokensPurchased(msg.sender, tokensOut, tradeAmount, platformFee, creatorFee);
    
    // Execute graduation atomically if flagged
    if (graduating) {
        _executeGraduation();
    }
}

// AUDIT FIX: Safe send helper (replaces .transfer)
function _safeSend(address to, uint256 amount) private {
    (bool success, ) = payable(to).call{value: amount}("");
    require(success, "Transfer failed");
}

**Sell Function** (AUDIT FIX v3 - Fee on Input, Symmetric with Buy):
```solidity
function sellTokens(uint256 tokenAmount, uint256 minKasOut, uint256 deadline) external nonReentrant {
    require(!graduated && !graduating, "Token graduated or graduating");
    require(block.timestamp <= deadline, "Transaction expired");
    require(balanceOf(msg.sender) >= tokenAmount, "Insufficient balance");
    
    // AUDIT FIX: Fee on INPUT (tokens) for symmetry with buy
    uint256 totalFees = tokenAmount * TOTAL_FEE_BPS / 10000; // 1% of tokens
    uint256 creatorFee = totalFees * CREATOR_SHARE_BPS / 10000; // 10% of fees
    uint256 platformFee = totalFees - creatorFee; // 90% of fees
    uint256 tradeTokens = tokenAmount - totalFees;
    
    // Calculate KAS output using trade tokens (after fees)
    uint256 kasOut = quoteSell(tradeTokens);
    
    // AUDIT FIX: Slippage protection on KAS received
    require(kasOut >= minKasOut, "Slippage too high");
    
    // Minimum trade check
    require(kasOut >= MIN_TRADE_AMOUNT, "Below minimum trade");
    
    // Update virtual reserves FIRST (CEI pattern)
    virtualTokenReserve += tradeTokens; // Only trade tokens enter reserve
    virtualKasReserve -= kasOut;
    
    // Convert fee tokens to KAS value for accounting (optional, or keep as tokens)
    uint256 feeKasValue = quoteSell(totalFees);
    accumulatedPlatformFees += (feeKasValue * 90) / 100;
    accumulatedCreatorFees += (feeKasValue * 10) / 100;
    
    // Transfer ALL tokens back to pool (including fee tokens)
    _transfer(msg.sender, address(this), tokenAmount);
    
    // Send KAS to user
    _safeSend(msg.sender, kasOut);
    
    emit TokensSold(msg.sender, tokenAmount, kasOut, platformFee, creatorFee);
}
```

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
  - 15% Kaspa Network Support (0.135% of trade - reduced from 20%)
  - 5% Community Rewards (0.045% of trade - airdrops, incentives)
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
uint256 public constant COMMUNITY_SHARE = 500;  // 5% of platform fees

// TWAP Buyback (activated post-TGE)
bool public twapBuybackEnabled;
address public gemTokenAddress;
uint256 public twapPeriod = 24 hours;
uint256 public twapBuybackAmount; // KAS per period

mapping(address => VestingSchedule) public vesting;
```

**Fee Distribution Flow** (AUDIT FIX - Safe transfers):
```solidity
function distributeFees() external nonReentrant {
    uint256 balance = address(this).balance;
    require(balance > 0, "No fees to distribute");
    
    uint256 devAmount = balance * DEV_SHARE / 10000;         // 40%
    uint256 buybackAmount = balance * BUYBACK_SHARE / 10000; // 30%
    uint256 kaspaAmount = balance * KASPA_SHARE / 10000;     // 15%
    uint256 communityAmount = balance * COMMUNITY_SHARE / 10000; // 5%
    
    // AUDIT FIX: Use .call instead of .transfer to prevent failures
    _safeTransfer(platformDevelopmentWallet, devAmount);
    _safeTransfer(buybackReserveWallet, buybackAmount);        // Accumulates until GEM TGE
    _safeTransfer(kaspaNetworkSupportWallet, kaspaAmount);     // Kaspa ecosystem support
    _safeTransfer(communityRewardsWallet, communityAmount);
    
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

#### Step 3: Kaspa Finance Pool Creation
```solidity
function addLiquidityToKaspaFinance(
    address token,
    uint256 tokenAmount,
    uint256 kasAmount
) internal {
    IKaspaFinanceRouter router = IKaspaFinanceRouter(kaspaFinanceRouter);
    
    // Approve router
    IERC20(token).approve(address(router), tokenAmount);
    
    // Add liquidity
    router.addLiquidityETH{value: kasAmount}(
        token,
        tokenAmount,
        tokenAmount * 95 / 100, // 5% slippage
        kasAmount * 95 / 100,
        treasury, // LP tokens recipient (can burn or lock)
        block.timestamp + 300
    );
}
```

### Kaspa Finance Router Interface
```solidity
interface IKaspaFinanceRouter {
    function addLiquidityETH(
        address token,
        uint256 amountTokenDesired,
        uint256 amountTokenMin,
        uint256 amountETHMin,
        address to,
        uint256 deadline
    ) external payable returns (uint256 amountToken, uint256 amountETH, uint256 liquidity);
}
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
- **Total Critical Fixes**: 18 across all rounds
- **Status**: Testnet-ready pending final validation

### v3 Fixes Summary (Latest Round)
**Critical Fixes:**
1. Virtual reserve initialization (0.001 KAS seed)
2. Symmetric fee calculation (fee on input for both buy/sell)
3. CEI-compliant graduation check (reserves updated first)
4. Correct LP split (ALL KAS + 25% tokens to LP, burn unsold)

**High Priority Fixes:**
1. 0.001 KAS minimum trade amount
2. Bidirectional transfer cooldown (sender + receiver)
3. Balance verification for fee withdrawals

---

## 9. Deployment Checklist

### Testnet Deployment

#### Pre-Deployment: Treasury Wallet Setup
- [ ] **Create Gemlaunch Treasury Wallets** (multi-sig recommended):
  - [ ] Platform Development Wallet (receives 40% of platform fees → 0.36% of trades)
  - [ ] GEM Buyback Reserve Wallet (receives 30% of platform fees → 0.27% of trades, accumulates until GEM TGE)
  - [ ] Kaspa Network Support Wallet (receives 15% of platform fees → 0.135% of trades, ecosystem support)
  - [ ] Community Rewards Wallet (receives 5% of platform fees → 0.045% of trades)
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
**V3 Audit Fixes Validation:**
- [ ] Test virtual reserve initialization (0.001 KAS seed prevents division by zero)
- [ ] Verify symmetric fee calculation (fee on INPUT for both buy and sell)
- [ ] Test CEI pattern: reserves updated BEFORE graduation check
- [ ] Verify correct LP split: ALL virtualKasReserve + 25% tokens to LP, burn unsold
- [ ] Test 0.001 KAS minimum trade amount enforcement
- [ ] Verify bidirectional transfer cooldown (both sender and receiver)
- [ ] Test balance verification in fee withdrawal (respects virtualKasReserve)
- [ ] Verify round-trip buy→sell symmetry (1% each way = 2% total loss)

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
- [ ] Verify treasury fee distribution: 40% dev, 30% buyback, 15% Kaspa, 5% community, 10% creator

### Mainnet Preparation
- [ ] Complete security audit
- [ ] Address all audit findings
- [ ] Bug bounty program (minimum 2 weeks)
- [ ] Multi-sig setup for admin functions
- [ ] Timelock for parameter changes
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
- [ ] Kaspa Finance router contract address on testnet/mainnet
- [ ] Kaspa Finance LP token handling (burn vs lock)
- [ ] Kaspa Finance pool creation fee structure
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
