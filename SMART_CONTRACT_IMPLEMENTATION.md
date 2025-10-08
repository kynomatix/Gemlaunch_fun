# Gemlaunch.fun - Blockchain Smart Contract Implementation Plan

## Overview

This document outlines the implementation plan for integrating Kasplex zkEVM blockchain smart contracts into gemlaunch.fun to enable real token launches, bonding curve trading, and DEX graduation.

**Current Status**: Mock/database-driven implementation  
**Target**: Live blockchain integration on Kasplex zkEVM testnet → mainnet  
**DEX Partner**: Kaspa Finance (kaspafinance.io)  
**Security Priority**: CRITICAL - contracts will hold real money

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

**Bonding Curve Formula** (Based on Pump.sol analysis):
```solidity
// Midpoint pricing to prevent manipulation
function quoteBuy(uint256 ethAmount) public view returns (uint256 tokensPerETH) {
    uint256 currentPrice = getCurrentPrice();
    uint256 tokenAmount = ethAmount * currentPrice / 1e18;
    uint256 remainingTokens = balanceOf(address(this));
    
    // Price at midpoint of trade
    tokensPerETH = (remainingTokens - (tokenAmount / 2)) * 1e18 / 
                   (address(this).balance + (ethAmount / 2));
}

function quoteSell(uint256 tokenAmount) public view returns (uint256 tokensPerETH) {
    uint256 currentPrice = getCurrentPrice();
    uint256 ethAmount = tokenAmount * 1e18 / currentPrice;
    uint256 remainingTokens = balanceOf(address(this));
    
    // Price at midpoint of trade
    tokensPerETH = (remainingTokens + (tokenAmount / 2)) * 1e18 / 
                   (address(this).balance - (ethAmount / 2));
}

function getCurrentPrice() public view returns (uint256 tokensPerETH) {
    uint256 remainingTokens = balanceOf(address(this));
    uint256 contractETHBalance = address(this).balance;
    if (contractETHBalance < 0.01 ether) contractETHBalance = 0.01 ether;
    tokensPerETH = remainingTokens * 1e18 / contractETHBalance;
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
uint256 public constant PLATFORM_FEE_BPS = 100; // 1% fee
uint256 public constant GRADUATION_THRESHOLD = 75e18; // 75 KAS raised
address public treasury; // Gemlaunch treasury contract
mapping(address => uint256) public holdings;
mapping(address => uint256) public lastPurchaseTime;
uint256 public totalRaised;
bool public graduated;
```

**Fee Collection on Trades**:
```solidity
function buyTokens() external payable nonReentrant {
    require(!graduated, "Token graduated");
    require(msg.value > 0, "Must send KAS");
    
    // Calculate platform fee (1%)
    uint256 platformFee = msg.value * PLATFORM_FEE_BPS / 10000;
    uint256 tradeAmount = msg.value - platformFee;
    
    // Calculate tokens based on trade amount (after fee)
    uint256 tokens = quoteBuy(tradeAmount);
    
    // Enforce wallet cap
    require(
        holdings[msg.sender] + tokens <= (totalSupply() * MAX_WALLET_PCT) / 100,
        "Exceeds 10% wallet cap"
    );
    
    // Transfer tokens
    _transfer(address(this), msg.sender, tokens);
    holdings[msg.sender] += tokens;
    totalRaised += tradeAmount;
    
    // Send platform fee to treasury
    payable(treasury).transfer(platformFee);
    
    emit TokensPurchased(msg.sender, tokens, tradeAmount, platformFee);
    
    // Check graduation
    if (totalRaised >= GRADUATION_THRESHOLD) {
        _triggerGraduation();
    }
}

function sellTokens(uint256 tokenAmount) external nonReentrant {
    require(!graduated, "Token graduated");
    require(holdings[msg.sender] >= tokenAmount, "Insufficient balance");
    
    // Calculate KAS refund
    uint256 kasRefund = quoteSell(tokenAmount);
    
    // Calculate platform fee (1% of refund)
    uint256 platformFee = kasRefund * PLATFORM_FEE_BPS / 10000;
    uint256 userRefund = kasRefund - platformFee;
    
    // Update state
    _transfer(msg.sender, address(this), tokenAmount);
    holdings[msg.sender] -= tokenAmount;
    totalRaised -= kasRefund;
    
    // Send refund to user, fee to treasury
    payable(msg.sender).transfer(userRefund);
    payable(treasury).transfer(platformFee);
    
    emit TokensSold(msg.sender, tokenAmount, kasRefund, platformFee);
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
  - 30% GEM Buyback & Burn
  - 20% Network Support (validators, infrastructure)
  - 10% Community Rewards (airdrops, incentives)
- Multi-sig withdrawal controls
- Optional vesting schedules for team/contributors

**State Variables**:
```solidity
// Treasury wallet addresses
address public platformDevelopmentWallet;
address public buybackBurnWallet;
address public networkSupportWallet;
address public communityRewardsWallet;

// Fee tracking
uint256 public constant PLATFORM_FEE_BPS = 100; // 1% in basis points
uint256 public totalFeesCollected;

// Distribution percentages (in basis points)
uint256 public constant DEV_SHARE = 4000;      // 40%
uint256 public constant BUYBACK_SHARE = 3000;  // 30%
uint256 public constant NETWORK_SHARE = 2000;  // 20%
uint256 public constant COMMUNITY_SHARE = 1000; // 10%

mapping(address => VestingSchedule) public vesting;
```

**Fee Collection Flow**:
```solidity
function distributeFees() external nonReentrant {
    uint256 balance = address(this).balance;
    require(balance > 0, "No fees to distribute");
    
    uint256 devAmount = balance * DEV_SHARE / 10000;
    uint256 buybackAmount = balance * BUYBACK_SHARE / 10000;
    uint256 networkAmount = balance * NETWORK_SHARE / 10000;
    uint256 communityAmount = balance * COMMUNITY_SHARE / 10000;
    
    payable(platformDevelopmentWallet).transfer(devAmount);
    payable(buybackBurnWallet).transfer(buybackAmount);
    payable(networkSupportWallet).transfer(networkAmount);
    payable(communityRewardsWallet).transfer(communityAmount);
    
    emit FeesDistributed(devAmount, buybackAmount, networkAmount, communityAmount);
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

#### Step 2: Liquidity Preparation
```solidity
function graduate(address tokenAddress) external nonReentrant {
    require(checkGraduationEligibility(tokenAddress), "Not eligible");
    
    BondingCurvePool pool = BondingCurvePool(tokenAddress);
    uint256 kasRaised = pool.totalRaised();
    uint256 lpTokens = pool.mintLPSupply(); // 25% of total supply
    
    // Transfer assets to this contract
    pool.transferLiquidity(address(this), kasRaised, lpTokens);
    
    // Add to Kaspa Finance
    addLiquidityToKaspaFinance(tokenAddress, lpTokens, kasRaised);
    
    pool.lockCurve();
    emit TokenGraduated(tokenAddress, kasRaised, lpTokens);
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

## 8. Deployment Checklist

### Testnet Deployment

#### Pre-Deployment: Treasury Wallet Setup
- [ ] **Create Gemlaunch Treasury Wallets** (multi-sig recommended):
  - [ ] Platform Development Wallet (receives 40% of fees)
  - [ ] GEM Buyback & Burn Wallet (receives 30% of fees)
  - [ ] Network Support Wallet (receives 20% of fees)
  - [ ] Community Rewards Wallet (receives 10% of fees)
- [ ] Configure multi-sig with 2-of-3 or 3-of-5 threshold
- [ ] Document all wallet addresses and signers
- [ ] Test multi-sig transaction flow on testnet

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
- [ ] Test bonding curve trades (verify 1% fee goes to treasury)
- [ ] Test graduation to Kaspa Finance
- [ ] Monitor gas costs and optimize
- [ ] Verify fee splits match pitch deck model (40/30/20/10)

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
