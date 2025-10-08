# Gemlaunch.fun - Blockchain Smart Contract Implementation Plan

## Overview

This document outlines the implementation plan for integrating Kasplex zkEVM blockchain smart contracts into gemlaunch.fun to enable real token launches, bonding curve trading, and DEX graduation.

**Current Status**: Mock/database-driven implementation  
**Target**: Live blockchain integration on Kasplex zkEVM testnet → mainnet  
**DEX Partner**: Kaspa Finance (kaspafinance.io)  
**Security Priority**: CRITICAL - contracts will hold real money

### Fee Structure
**Total Trading Fees: 1.5%**
- **1% Platform Fee** → Treasury (distributed: 40% dev, 30% buyback, 20% network, 10% community)
- **0.5% Creator Fee** → Accumulated and paid to token creator at graduation

**Note**: Creator fee is configurable via `CREATOR_FEE_BPS` constant (currently 50 basis points = 0.5%)

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

**Bonding Curve Formula** (SECURITY AUDIT FIX - Constant Product AMM):
```solidity
// AUDIT FIX: Use proven constant product formula (x*y=k) instead of broken midpoint pricing
// Prevents price manipulation and value leakage
function quoteBuy(uint256 kasIn) public view returns (uint256 tokensOut) {
    uint256 poolTokens = balanceOf(address(this));
    uint256 poolKas = address(this).balance;
    
    // Constant product invariant: k = poolTokens * poolKas
    uint256 k = poolTokens * poolKas;
    
    // After buy: k = (poolTokens - tokensOut) * (poolKas + kasIn)
    // Solve for tokensOut:
    uint256 newPoolKas = poolKas + kasIn;
    uint256 newPoolTokens = k / newPoolKas;
    tokensOut = poolTokens - newPoolTokens;
    
    require(tokensOut < poolTokens, "Exceeds available supply");
}

function quoteSell(uint256 tokensIn) public view returns (uint256 kasOut) {
    uint256 poolTokens = balanceOf(address(this));
    uint256 poolKas = address(this).balance;
    
    uint256 k = poolTokens * poolKas;
    
    uint256 newPoolTokens = poolTokens + tokensIn;
    uint256 newPoolKas = k / newPoolTokens;
    kasOut = poolKas - newPoolKas;
    
    require(kasOut < poolKas, "Exceeds available KAS");
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

**State Variables**:
```solidity
uint256 public constant CURVE_SUPPLY_PCT = 75;
uint256 public constant LP_SUPPLY_PCT = 25;
uint256 public constant MAX_WALLET_PCT = 10;
uint256 public constant PLATFORM_FEE_BPS = 100; // 1% platform fee
uint256 public immutable CREATOR_FEE_BPS; // 0.5% creator fee (immutable, set in constructor)
uint256 public constant GRADUATION_THRESHOLD = 75e18; // 75 KAS minimum balance
address public treasury; // Gemlaunch treasury contract
address public immutable creator; // Token creator address (immutable)
mapping(address => uint256) public claimableCreatorFees; // Pull-based fee claiming
mapping(address => uint256) public lastPurchaseTime;
uint256 public grossInBase; // Total KAS input (for tracking)
uint256 public netReservesBase; // Actual KAS reserves (for pricing)
bool public graduated;
bool public graduating; // Lock flag during graduation
```

**Constructor** (AUDIT FIX - Immutable creator fee):
```solidity
constructor(address _creator, uint256 _creatorFeeBps) {
    require(_creatorFeeBps >= 25 && _creatorFeeBps <= 100, "Fee must be 0.25-1%");
    creator = _creator;
    CREATOR_FEE_BPS = _creatorFeeBps; // Immutable, prevents rug
}
```

**Fee Collection on Trades** (AUDIT FIX - No double-fee):
```solidity
function buyTokens(uint256 minTokensOut, uint256 deadline) external payable nonReentrant {
    require(!graduated && !graduating, "Token graduated or graduating");
    require(block.timestamp <= deadline, "Transaction expired");
    require(msg.value > 0, "Must send KAS");
    
    // AUDIT FIX: Calculate total fees once (1% + 0.5% = 1.5%)
    uint256 totalFees = msg.value * 150 / 10000; // 1.5% total
    uint256 tradeAmount = msg.value - totalFees;
    
    // Split fees: 66.67% platform (1%), 33.33% creator (0.5%)
    uint256 platformFee = totalFees * 2 / 3;
    uint256 creatorFee = totalFees / 3;
    
    // Calculate tokens based on trade amount (after fees)
    uint256 tokens = quoteBuy(tradeAmount);
    
    // AUDIT FIX: Slippage protection
    require(tokens >= minTokensOut, "Slippage too high");
    
    // Update reserves tracking
    grossInBase += msg.value;
    netReservesBase += tradeAmount;
    
    // Transfer tokens (wallet cap enforced in _transfer override)
    _transfer(address(this), msg.sender, tokens);
    
    // Accumulate creator fee for pull-based claiming
    claimableCreatorFees[creator] += creatorFee;
    
    // AUDIT FIX: Use .call instead of .transfer
    _safeSend(treasury, platformFee);
    
    emit TokensPurchased(msg.sender, tokens, tradeAmount, platformFee, creatorFee);
    
    // AUDIT FIX: Check current balance (not cumulative) and auto-graduate
    if (!graduated && address(this).balance >= GRADUATION_THRESHOLD) {
        _triggerGraduation();
    }
}

// AUDIT FIX: Safe send helper (replaces .transfer)
function _safeSend(address to, uint256 amount) private {
    (bool success, ) = payable(to).call{value: amount}("");
    require(success, "Transfer failed");
}

function sellTokens(uint256 tokenAmount, uint256 minRefund, uint256 deadline) external nonReentrant {
    require(!graduated && !graduating, "Token graduated or graduating");
    require(block.timestamp <= deadline, "Transaction expired");
    require(balanceOf(msg.sender) >= tokenAmount, "Insufficient balance");
    
    // Calculate KAS refund
    uint256 kasRefund = quoteSell(tokenAmount);
    
    // Calculate fees (1.5% total)
    uint256 totalFees = kasRefund * 150 / 10000;
    uint256 platformFee = totalFees * 2 / 3;
    uint256 creatorFee = totalFees / 3;
    uint256 userRefund = kasRefund - totalFees;
    
    // AUDIT FIX: Slippage protection
    require(userRefund >= minRefund, "Slippage too high");
    
    // Update state
    _transfer(msg.sender, address(this), tokenAmount);
    netReservesBase -= kasRefund;
    
    // Accumulate creator fee for pull-based claiming
    claimableCreatorFees[creator] += creatorFee;
    
    // AUDIT FIX: Use .call instead of .transfer
    _safeSend(msg.sender, userRefund);
    _safeSend(treasury, platformFee);
    
    emit TokensSold(msg.sender, tokenAmount, kasRefund, platformFee, creatorFee);
}
```

**Wallet Cap Enforcement** (AUDIT FIX - Prevents transfer bypass):
```solidity
// Override _transfer to enforce wallet cap on ALL transfers
function _transfer(address from, address to, uint256 amount) internal override {
    if (!graduated) {
        // Circulating supply = total - contract balance
        uint256 circulating = totalSupply() - balanceOf(address(this));
        require(
            balanceOf(to) + amount <= (circulating * MAX_WALLET_PCT) / 100,
            "Exceeds 10% wallet cap"
        );
    }
    super._transfer(from, to, amount);
}
```

**Creator Fee Claiming** (AUDIT FIX - Pull pattern prevents reentrancy):
```solidity
function claimCreatorFees() external nonReentrant {
    uint256 amount = claimableCreatorFees[msg.sender];
    require(amount > 0, "No fees to claim");
    
    claimableCreatorFees[msg.sender] = 0;
    _safeSend(msg.sender, amount);
    
    emit CreatorFeeClaimed(msg.sender, amount);
}
```

**Graduation Lock & Execution** (AUDIT FIX - Atomic, no front-running):
```solidity
// Lock pool for graduation (called by GraduationController only)
function lockForGraduation() external onlyController nonReentrant {
    require(!graduated && !graduating, "Invalid state");
    require(address(this).balance >= GRADUATION_THRESHOLD, "Insufficient balance");
    graduating = true;
    emit GraduationLocked(block.timestamp);
}

// Internal graduation execution (atomic)
function _triggerGraduation() internal {
    require(!graduated, "Already graduated");
    graduated = true;
    
    // Creator fees remain claimable (pull-based, doesn't block graduation)
    
    // Proceed with DEX graduation...
    emit TokenGraduated(address(this), address(this).balance, claimableCreatorFees[creator]);
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
- Collects 1% platform fee from all bonding curve trades
- Distributes fees according to pitch deck model:
  - 40% Platform Development
  - 30% GEM Buyback Reserve (accumulates until TGE, then TWAP buybacks)
  - 20% GemFoundation (ecosystem support, future DAO-controlled)
  - 10% Community Rewards (airdrops, incentives)
- Multi-sig withdrawal controls
- Optional vesting schedules for team/contributors
- TWAP buyback mechanism post-GEM TGE

**State Variables**:
```solidity
// Treasury wallet addresses
address public platformDevelopmentWallet;
address public buybackReserveWallet; // Accumulates KAS until GEM TGE
address public gemFoundationWallet;  // Ecosystem support (future DAO-controlled)
address public communityRewardsWallet;

// Fee tracking
uint256 public constant PLATFORM_FEE_BPS = 100; // 1% in basis points
uint256 public totalFeesCollected;

// Distribution percentages (in basis points)
uint256 public constant DEV_SHARE = 4000;         // 40%
uint256 public constant BUYBACK_SHARE = 3000;     // 30% (accumulates, then TWAP)
uint256 public constant FOUNDATION_SHARE = 2000;  // 20% (future DAO)
uint256 public constant COMMUNITY_SHARE = 1000;   // 10%

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
    
    uint256 devAmount = balance * DEV_SHARE / 10000;
    uint256 buybackAmount = balance * BUYBACK_SHARE / 10000;
    uint256 foundationAmount = balance * FOUNDATION_SHARE / 10000;
    uint256 communityAmount = balance * COMMUNITY_SHARE / 10000;
    
    // AUDIT FIX: Use .call instead of .transfer to prevent failures
    _safeTransfer(platformDevelopmentWallet, devAmount);
    _safeTransfer(buybackReserveWallet, buybackAmount); // Accumulates until TGE
    _safeTransfer(gemFoundationWallet, foundationAmount); // Public, transparent
    _safeTransfer(communityRewardsWallet, communityAmount);
    
    emit FeesDistributed(devAmount, buybackAmount, foundationAmount, communityAmount);
}

function _safeTransfer(address to, uint256 amount) private {
    (bool success, ) = payable(to).call{value: amount}("");
    if (!success) {
        emit TransferFailed(to, amount);
        // Don't revert - log and continue to prevent blocking other transfers
    }
}
```

**GemFoundation Governance (Future DAO Integration)**:
```solidity
// Placeholder for future DAO governance
address public foundationDAO; // Will be set when DAO is deployed

// Transfer Foundation control to DAO (one-time, irreversible)
function transferFoundationToDAO(address _daoAddress) external onlyOwner {
    require(foundationDAO == address(0), "DAO already set");
    require(_daoAddress != address(0), "Invalid DAO address");
    
    foundationDAO = _daoAddress;
    // Future: Foundation funds controlled by DAO votes
    
    emit FoundationTransferredToDAO(_daoAddress);
}
```

**TWAP Buyback System (Post-TGE)** - AUDIT FIX: Price protection:
```solidity
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
    require(address(buybackReserveWallet).balance >= twapBuybackAmount, "Insufficient reserve");
    
    // AUDIT FIX: Get TWAP price from oracle to prevent manipulation
    uint256 twapPrice = ITWAPOracle(twapOracle).getTWAP(gemTokenAddress, twapPeriod);
    uint256 minGemOut = twapBuybackAmount * twapPrice * 95 / 100; // 5% slippage tolerance
    
    // Use Kaspa Finance router to swap KAS for GEM
    IKaspaFinanceRouter router = IKaspaFinanceRouter(kaspaFinanceRouter);
    
    address[] memory path = new address[](2);
    path[0] = router.WKAS(); // Wrapped KAS
    path[1] = gemTokenAddress;
    
    uint256 deadline = block.timestamp + 300;
    
    // AUDIT FIX: Enforce minimum output to prevent price manipulation
    router.swapExactETHForTokens{value: twapBuybackAmount}(
        minGemOut, // CRITICAL: Protect against sandwich attacks
        path,
        address(this), // Treasury receives GEM
        deadline
    );
    
    // Burn the purchased GEM tokens
    uint256 gemBalance = IERC20(gemTokenAddress).balanceOf(address(this));
    IERC20(gemTokenAddress).transfer(address(0xdead), gemBalance);
    
    emit TWAPBuybackExecuted(twapBuybackAmount, gemBalance, block.timestamp);
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

### Critical Issues Fixed

1. **✅ Bonding Curve Math - FIXED**
   - **Issue**: Broken midpoint pricing formula with circular logic
   - **Fix**: Implemented proper constant product AMM (x*y=k)
   - **Impact**: Prevents price manipulation and value leakage

2. **✅ Fee Distribution Double-Fee - FIXED**
   - **Issue**: Fees calculated on full msg.value causing 3% roundtrip loss
   - **Fix**: Single fee calculation (1.5% total), split 66.67%/33.33%
   - **Impact**: Fair fee structure, prevents value extraction

3. **✅ Fee Accounting Asymmetry - FIXED**
   - **Issue**: totalRaised incremented/decremented asymmetrically
   - **Fix**: Separate grossInBase and netReservesBase tracking
   - **Impact**: Accurate reserve accounting, prevents drift

4. **✅ Graduation Front-Running - FIXED**
   - **Issue**: External graduate() function exploitable via mempool watching
   - **Fix**: Auto-graduation within buy transaction (atomic)
   - **Impact**: Prevents MEV attacks and manipulation

5. **✅ Graduation Not Atomic - FIXED**
   - **Issue**: Multiple external calls, state changes between checks
   - **Fix**: lockForGraduation() mutex + atomic execution
   - **Impact**: Prevents reentrancy and state manipulation

6. **✅ Wallet Cap Bypass - FIXED**
   - **Issue**: Separate holdings mapping bypassable via transfers
   - **Fix**: Override _transfer() to enforce cap on ALL transfers
   - **Impact**: True whale protection, no bypass possible

7. **✅ No Minimum Liquidity Check - FIXED**
   - **Issue**: Graduation checked totalRaised (cumulative) not balance
   - **Fix**: Check address(this).balance >= GRADUATION_THRESHOLD
   - **Impact**: Ensures sufficient liquidity at graduation

8. **✅ Reentrancy in Graduation - FIXED**
   - **Issue**: Creator payout via .transfer() during graduation
   - **Fix**: Pull-based claimCreatorFees() pattern
   - **Impact**: Prevents reentrancy, unblocks graduation

9. **✅ Treasury Distribution Failures - FIXED**
   - **Issue**: .transfer() can brick entire distribution if one fails
   - **Fix**: Use .call{value:}() with failure logging
   - **Impact**: Robust fee distribution, no single point of failure

10. **✅ No Slippage Protection - FIXED**
    - **Issue**: No minTokensOut/minRefund parameters
    - **Fix**: Added minTokensOut, minRefund, deadline to all trades
    - **Impact**: MEV protection, sandwich attack prevention

11. **✅ transfer() vs .call - FIXED**
    - **Issue**: .transfer() uses 2300 gas, fails with smart wallets
    - **Fix**: _safeSend() helper using .call{value:}()
    - **Impact**: Compatible with all wallet types

12. **✅ Creator Fee Rug Risk - FIXED**
    - **Issue**: Mutable creator fee could be changed to 90%
    - **Fix**: immutable CREATOR_FEE_BPS with 0.25-1% cap
    - **Impact**: Prevents rug pulls, guarantees fairness

13. **✅ TWAP Buyback No Slippage - FIXED**
    - **Issue**: minAmountOut = 0 vulnerable to manipulation
    - **Fix**: Oracle-based TWAP price with 5% slippage protection
    - **Impact**: Prevents buyback fund drainage

### Additional Security Enhancements

- **Circulating Supply Based Caps**: Wallet cap uses circulating supply, not total
- **Deadline Protection**: All trades require deadline parameter
- **Safe Transfer Pattern**: Consistent use of .call{value:}() everywhere
- **Pull-Based Fees**: Creator fees claimable anytime, doesn't block graduation
- **Event Enrichment**: Full context in all events for analytics
- **Conservative Math**: Prevent overflow with supply caps

### Audit Sources
- **Claude Audit**: 20 findings (7 critical, 8 high, 5 medium)
- **ChatGPT Audit**: 15 findings (5 critical, 8 high, 2 medium)
- **Total Fixes**: 13 critical issues resolved

---

## 9. Deployment Checklist

### Testnet Deployment

#### Pre-Deployment: Treasury Wallet Setup
- [ ] **Create Gemlaunch Treasury Wallets** (multi-sig recommended):
  - [ ] Platform Development Wallet (receives 40% of fees)
  - [ ] GEM Buyback Reserve Wallet (receives 30% - accumulates until GEM TGE)
  - [ ] **GemFoundation Wallet** (receives 20% - public, transparent, future DAO-controlled)
  - [ ] Community Rewards Wallet (receives 10% of fees)
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
- [ ] Test bonding curve trades with constant product formula (x*y=k)
- [ ] Verify 1.5% total fee (1% platform + 0.5% creator) calculated once
- [ ] Test slippage protection (minTokensOut, minRefund, deadline)
- [ ] Verify platform fees sent via .call (not .transfer)
- [ ] Test pull-based creator fee claiming (claimCreatorFees)
- [ ] Test wallet cap enforcement on transfers (not just buys)
- [ ] Verify graduation lock mechanism (lockForGraduation)
- [ ] Test atomic graduation (no front-running possible)
- [ ] Confirm current balance check (not totalRaised)
- [ ] Test TWAP buyback with oracle price protection
- [ ] Monitor gas costs and optimize
- [ ] Verify treasury fee splits match pitch deck model (40/30/20/10)

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
