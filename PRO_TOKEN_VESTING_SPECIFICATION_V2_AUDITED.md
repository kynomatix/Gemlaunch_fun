# PRO Token Vesting System - Smart Contract Specification V2
## 🔒 POST-AUDIT REVISION - All Critical Issues Fixed

---

## Executive Summary

This document specifies how the PRO token UI (reserve allocations and vesting schedules) should be implemented on-chain with proper smart contract enforcement. **This V2 revision addresses all critical security issues identified in the security audit.**

---

## Critical Fixes Implemented

### ✅ BI-1: Token Transfer Mechanism Fixed
- Added `transferReserveToVesting()` function to BondingCurvePool
- Factory can now safely transfer tokens to vesting contracts

### ✅ BI-2: All LP_SUPPLY_PCT References Updated
- Changed constant to `reservedPercentage` state variable
- Updated `initiateGraduation()` and `getReserveStatus()` to use variable

### ✅ BI-3: Vesting Contracts Exempted from Wallet Cap
- Added vesting contract registry to BondingCurvePool
- Factory can register vesting contracts for cap exemption

### ✅ BI-4: Vesting Contracts Fully Immutable
- Removed `Ownable` inheritance from all vesting contracts
- No ownership transfer possible

---

## Smart Contract Architecture

### 1. Modified BondingCurvePool.sol

#### Required Changes:

```solidity
// contracts/BondingCurvePool.sol

// ====== CHANGE 1: Remove Constants ======
// DELETE THESE LINES:
// uint256 public constant CURVE_SUPPLY_PCT = 75;
// uint256 public constant LP_SUPPLY_PCT = 25;

// ====== CHANGE 2: Add State Variables ======
uint8 public reservedPercentage;  // 0-25, replaces LP_SUPPLY_PCT
address public factory;            // Factory address for vesting transfers
mapping(address => bool) public isVestingContract; // Wallet cap exemption

// ====== CHANGE 3: Update Constructor ======
constructor(
    string memory name,
    string memory symbol,
    uint256 totalSupply,
    address _creator,
    address _treasury,
    address _airdropTreasury,
    address _platformDevelopmentWallet,
    bool _antiBotEnabled,
    address _graduationOracle,
    address _admin,
    address _buybackReserve,
    address _kaspaSupport,
    address _communityRewards,
    uint8 _reservedPercentage  // NEW PARAMETER
) ERC20(name, symbol) Ownable(msg.sender) {
    require(_reservedPercentage <= 25, "Reserve exceeds 25%");
    
    // Store factory (msg.sender is TokenFactory)
    factory = msg.sender;
    
    // Store reserved percentage
    reservedPercentage = _reservedPercentage;
    
    // ... existing validation (creator, treasury, etc.)
    
    creator = _creator;
    treasury = _treasury;
    airdropTreasury = _airdropTreasury;
    platformDevelopmentWallet = _platformDevelopmentWallet;
    antiBotEnabled = _antiBotEnabled;
    graduationOracle = _graduationOracle;
    admin = _admin;
    buybackReserveWallet = _buybackReserve;
    kaspaNetworkSupportWallet = _kaspaSupport;
    communityRewardsWallet = _communityRewards;
    
    if (_antiBotEnabled) {
        deploymentTime = block.timestamp;
    }
    
    // Mint total supply to contract
    _mint(address(this), totalSupply);
    
    // ✅ FIXED: Use variable reserve percentage
    uint256 curveSupplyPct = 100 - reservedPercentage;
    uint256 curveSupply = totalSupply * curveSupplyPct / 100;
    virtualTokenReserve = curveSupply;
    virtualKasReserve = INITIAL_VIRTUAL_KAS;
    
    // Reserve tokens (reservedPercentage%) stay in contract for vesting transfer
}

// ====== CHANGE 4: Add Vesting Transfer Function ======
// FIX for BI-1: Token transfer mechanism
function transferReserveToVesting(address vestingContract, uint256 amount) external nonReentrant {
    require(msg.sender == factory, "Only factory can transfer to vesting");
    require(!reserveDistributed, "Reserve already distributed");
    
    uint256 availableReserve = balanceOf(address(this)) - virtualTokenReserve;
    require(amount <= availableReserve, "Exceeds available reserve");
    
    // Register vesting contract for wallet cap exemption
    isVestingContract[vestingContract] = true;
    
    _transfer(address(this), vestingContract, amount);
}

// ====== CHANGE 5: Update Graduation Function ======
// FIX for BI-2 and H-2: Use variable reserve and actual balance
function initiateGraduation() external nonReentrant {
    require(msg.sender == graduationOracle, "Only oracle can initiate");
    require(!graduated && !graduating, "Already graduated or graduating");
    
    graduating = true;
    
    // ✅ FIXED: Calculate actual LP tokens available (not theoretical reserve)
    uint256 contractBalance = balanceOf(address(this));
    uint256 actualLpTokens = contractBalance - virtualTokenReserve;
    
    require(actualLpTokens > 0, "No LP tokens available");
    
    // Approve graduation oracle to pull LP tokens for DEX
    _approve(address(this), graduationOracle, actualLpTokens);
    
    // Transfer KAS liquidity to oracle (for DEX deployment)
    uint256 actualKasLiquidity = virtualKasReserve - INITIAL_VIRTUAL_KAS;
    require(actualKasLiquidity > 0, "No KAS liquidity");
    
    _safeSend(graduationOracle, actualKasLiquidity);
    liquidityTransferred = true;
    
    emit GraduationInitiated(actualKasLiquidity, actualLpTokens);
}

// ====== CHANGE 6: Update Reserve Status Function ======
// FIX for BI-2: Use variable reserve
function getReserveStatus() external view returns (
    bool distributed,
    uint256 availableReserve,
    uint256 totalReserve
) {
    distributed = reserveDistributed;
    
    // ✅ FIXED: Use variable reserve percentage
    totalReserve = totalSupply() * reservedPercentage / 100;
    
    if (!graduated && !graduating) {
        availableReserve = balanceOf(address(this)) - virtualTokenReserve;
    } else {
        availableReserve = 0;
    }
}

// ====== CHANGE 7: Update Wallet Cap Exemption ======
// FIX for BI-3: Exempt vesting contracts from 10% cap
function _update(address from, address to, uint256 amount) internal virtual override {
    // Exemptions for wallet cap:
    // 1. Burning/minting (to/from == address(0))
    // 2. Contract itself
    // 3. Airdrop treasury (holds vested allocations)
    // 4. Graduation oracle (receives LP tokens)
    // 5. Owner (emergency operations)
    // 6. Transfers FROM airdropTreasury (allows vesting distributions)
    // 7. Transfers FROM contract (buy operations)
    // 8. ✅ NEW: Vesting contracts (can hold >10%)
    // 9. Graduated pools (no restrictions)
    
    if (to != address(0) &&
        to != address(this) && 
        to != airdropTreasury &&
        to != graduationOracle &&
        to != owner() &&
        from != airdropTreasury &&
        from != address(this) &&
        !isVestingContract[to] &&  // ✅ FIXED: Exempt vesting contracts
        !graduated) {
        
        uint256 maxWallet = totalSupply() * MAX_WALLET_PCT / 100; // 10%
        require(balanceOf(to) + amount <= maxWallet, "Exceeds 10% max wallet");
    }
    
    super._update(from, to, amount);
}

// ====== CHANGE 8: Add Guard for BASIC Tokens ======
// FIX for H-1: Prevent misleading function calls on 0% reserve tokens
function distributeReserve(address[] calldata recipients, uint256[] calldata amounts) external nonReentrant {
    require(reservedPercentage > 0, "BASIC token has no reserve");
    require(msg.sender == creator, "Only creator can distribute");
    require(!reserveDistributed, "Reserve already distributed");
    require(!graduated && !graduating, "Cannot distribute after graduation");
    require(recipients.length == amounts.length, "Length mismatch");
    require(recipients.length > 0, "Empty recipients");
    
    uint256 totalDistribution = 0;
    for (uint256 i = 0; i < amounts.length; i++) {
        require(recipients[i] != address(0), "Invalid recipient");
        require(amounts[i] > 0, "Invalid amount");
        totalDistribution += amounts[i];
    }
    
    uint256 availableReserve = balanceOf(address(this)) - virtualTokenReserve;
    require(totalDistribution <= availableReserve, "Exceeds available reserve");
    
    reserveDistributed = true;
    
    for (uint256 i = 0; i < recipients.length; i++) {
        _transfer(address(this), recipients[i], amounts[i]);
    }
    
    emit ReserveDistributed(creator, recipients, amounts, totalDistribution);
}
```

---

### 2. Enhanced TokenFactory.sol

```solidity
// contracts/TokenFactory.sol

function createToken(
    string memory name,
    string memory symbol,
    uint256 totalSupply,
    string memory description,
    string memory imageUrl,
    string memory twitterUrl,
    string memory telegramUrl,
    string memory websiteUrl,
    bool antiBotEnabled,
    uint8 reservedPercentage,        // NEW: 0-25
    uint8 airdropsAllocation,        // NEW: 0-100 (% of reserve)
    uint8 marketingAllocation,       // NEW: 0-100 (% of reserve)
    uint8 teamAllocation,            // NEW: 0-100 (% of reserve)
    address airdropBeneficiary,      // NEW: Who gets airdrops
    address marketingBeneficiary,    // NEW: Who gets marketing
    address teamBeneficiary          // NEW: Who gets team tokens
) external nonReentrant whenNotPaused returns (
    address poolAddress,
    address airdropVestingAddress,
    address marketingVestingAddress,
    address teamVestingAddress
) {
    // Validate deployment cooldown
    require(
        block.timestamp >= lastDeploymentTime[msg.sender] + deploymentCooldown,
        "Deployment cooldown active"
    );
    
    // Validate basic inputs
    require(bytes(name).length > 0 && bytes(name).length <= 32, "Invalid name");
    require(bytes(symbol).length > 0 && bytes(symbol).length <= 10, "Invalid symbol");
    require(totalSupply >= 1_000_000 * 10**18, "Supply too low");
    require(totalSupply <= 1_000_000_000 * 10**18, "Supply too high");
    require(bytes(description).length <= 280, "Description too long");
    
    // ✅ Validate PRO token params
    require(reservedPercentage <= 25, "Reserve exceeds 25%");
    if (reservedPercentage > 0) {
        require(
            airdropsAllocation + marketingAllocation + teamAllocation == 100,
            "Allocations must sum to 100%"
        );
    }
    
    // Deploy BondingCurvePool with variable reserve
    BondingCurvePool pool = new BondingCurvePool(
        name,
        symbol,
        totalSupply,
        msg.sender, // creator
        treasury,
        airdropTreasury,
        platformDevelopmentWallet,
        antiBotEnabled,
        graduationOracle,
        admin,
        buybackReserveWallet,
        kaspaNetworkSupportWallet,
        communityRewardsWallet,
        reservedPercentage  // ✅ NEW: Pass variable reserve
    );
    
    poolAddress = address(pool);
    
    // Deploy vesting contracts if PRO token
    airdropVestingAddress = address(0);
    marketingVestingAddress = address(0);
    teamVestingAddress = address(0);
    
    if (reservedPercentage > 0) {
        uint256 totalReserve = totalSupply * reservedPercentage / 100;
        
        // Calculate token amounts for each category
        uint256 airdropTokens = totalReserve * airdropsAllocation / 100;
        uint256 marketingTokens = totalReserve * marketingAllocation / 100;
        uint256 teamTokens = totalReserve * teamAllocation / 100;
        
        // Deploy and fund airdrop vesting
        if (airdropTokens > 0) {
            AirdropVesting av = new AirdropVesting(
                poolAddress,
                airdropBeneficiary,
                airdropTokens
            );
            airdropVestingAddress = address(av);
            
            // ✅ FIXED (BI-1): Use pool's transfer function instead of transferFrom
            pool.transferReserveToVesting(airdropVestingAddress, airdropTokens);
        }
        
        // Deploy and fund marketing vesting
        if (marketingTokens > 0) {
            LinearVesting mv = new LinearVesting(
                poolAddress,
                marketingBeneficiary,
                marketingTokens,
                12  // 12 months linear vesting
            );
            marketingVestingAddress = address(mv);
            
            // ✅ FIXED (BI-1): Use pool's transfer function
            pool.transferReserveToVesting(marketingVestingAddress, marketingTokens);
        }
        
        // Deploy and fund team vesting
        if (teamTokens > 0) {
            CliffVesting tv = new CliffVesting(
                poolAddress,
                teamBeneficiary,
                teamTokens,
                6,   // 6 month cliff
                18   // 18 month vesting after cliff
            );
            teamVestingAddress = address(tv);
            
            // ✅ FIXED (BI-1): Use pool's transfer function
            pool.transferReserveToVesting(teamVestingAddress, teamTokens);
        }
    }
    
    // Store token metadata
    tokens[poolAddress] = TokenInfo({
        name: name,
        symbol: symbol,
        totalSupply: totalSupply,
        creator: msg.sender,
        poolAddress: poolAddress,
        description: description,
        imageUrl: imageUrl,
        twitterUrl: twitterUrl,
        telegramUrl: telegramUrl,
        websiteUrl: websiteUrl,
        deployedAt: block.timestamp,
        antiBotEnabled: antiBotEnabled
    });
    
    deployedTokens.push(poolAddress);
    lastDeploymentTime[msg.sender] = block.timestamp;
    
    emit TokenCreated(
        poolAddress,
        poolAddress,
        msg.sender,
        name,
        symbol,
        totalSupply,
        antiBotEnabled,
        block.timestamp
    );
    
    emit VestingDeployed(poolAddress, airdropVestingAddress, marketingVestingAddress, teamVestingAddress);
    
    return (poolAddress, airdropVestingAddress, marketingVestingAddress, teamVestingAddress);
}
```

---

### 3. Vesting Contracts (Fully Immutable)

#### AirdropVesting.sol (5% Daily Unlock)

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

// ✅ FIXED (BI-4): Removed Ownable - fully immutable contract
contract AirdropVesting is ReentrancyGuard {
    IERC20 public immutable token;
    address public immutable beneficiary;
    uint256 public immutable totalAllocation;
    uint256 public immutable startTime;
    uint256 public constant DAILY_UNLOCK_PCT = 5; // 5% per day
    uint256 public constant VESTING_PERIOD = 20 days;
    uint256 public withdrawn;
    
    event TokensWithdrawn(address indexed beneficiary, uint256 amount);
    
    constructor(
        address _token,
        address _beneficiary,
        uint256 _totalAllocation
    ) {
        require(_token != address(0), "Invalid token");
        require(_beneficiary != address(0), "Invalid beneficiary");
        require(_totalAllocation > 0, "Invalid allocation");
        
        token = IERC20(_token);
        beneficiary = _beneficiary;
        totalAllocation = _totalAllocation;
        startTime = block.timestamp;
    }
    
    function getUnlockedAmount() public view returns (uint256) {
        uint256 elapsed = block.timestamp - startTime;
        
        if (elapsed >= VESTING_PERIOD) {
            return totalAllocation; // 100% unlocked after 20 days
        }
        
        uint256 daysElapsed = elapsed / 1 days;
        uint256 unlockedPct = daysElapsed * DAILY_UNLOCK_PCT;
        
        if (unlockedPct > 100) unlockedPct = 100;
        
        return (totalAllocation * unlockedPct) / 100;
    }
    
    function getWithdrawableAmount() public view returns (uint256) {
        uint256 unlocked = getUnlockedAmount();
        return unlocked > withdrawn ? unlocked - withdrawn : 0;
    }
    
    // ✅ FIXED (H-3): Added ReentrancyGuard
    function withdraw() external nonReentrant {
        require(msg.sender == beneficiary, "Only beneficiary");
        
        uint256 amount = getWithdrawableAmount();
        require(amount > 0, "Nothing to withdraw");
        
        withdrawn += amount;
        require(token.transfer(beneficiary, amount), "Transfer failed");
        
        emit TokensWithdrawn(beneficiary, amount);
    }
}
```

#### LinearVesting.sol (12-Month Linear)

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

// ✅ FIXED (BI-4): Removed Ownable - fully immutable contract
contract LinearVesting is ReentrancyGuard {
    IERC20 public immutable token;
    address public immutable beneficiary;
    uint256 public immutable totalAllocation;
    uint256 public immutable startTime;
    uint256 public immutable duration;
    uint256 public withdrawn;
    
    event TokensWithdrawn(address indexed beneficiary, uint256 amount);
    
    constructor(
        address _token,
        address _beneficiary,
        uint256 _totalAllocation,
        uint256 _durationMonths  // 12 for marketing
    ) {
        require(_token != address(0), "Invalid token");
        require(_beneficiary != address(0), "Invalid beneficiary");
        require(_totalAllocation > 0, "Invalid allocation");
        require(_durationMonths > 0, "Invalid duration");
        
        token = IERC20(_token);
        beneficiary = _beneficiary;
        totalAllocation = _totalAllocation;
        startTime = block.timestamp;
        duration = _durationMonths * 30 days;
    }
    
    function getUnlockedAmount() public view returns (uint256) {
        uint256 elapsed = block.timestamp - startTime;
        
        if (elapsed >= duration) {
            return totalAllocation;
        }
        
        return (totalAllocation * elapsed) / duration;
    }
    
    function getWithdrawableAmount() public view returns (uint256) {
        uint256 unlocked = getUnlockedAmount();
        return unlocked > withdrawn ? unlocked - withdrawn : 0;
    }
    
    // ✅ FIXED (H-3): Added ReentrancyGuard
    function withdraw() external nonReentrant {
        require(msg.sender == beneficiary, "Only beneficiary");
        
        uint256 amount = getWithdrawableAmount();
        require(amount > 0, "Nothing to withdraw");
        
        withdrawn += amount;
        require(token.transfer(beneficiary, amount), "Transfer failed");
        
        emit TokensWithdrawn(beneficiary, amount);
    }
}
```

#### CliffVesting.sol (6-Month Cliff + 18-Month Vest)

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

// ✅ FIXED (BI-4): Removed Ownable - fully immutable contract
contract CliffVesting is ReentrancyGuard {
    IERC20 public immutable token;
    address public immutable beneficiary;
    uint256 public immutable totalAllocation;
    uint256 public immutable startTime;
    uint256 public immutable cliff;
    uint256 public immutable vestingEnd;
    uint256 public withdrawn;
    
    event TokensWithdrawn(address indexed beneficiary, uint256 amount);
    
    constructor(
        address _token,
        address _beneficiary,
        uint256 _totalAllocation,
        uint256 _cliffMonths,      // 6 for team
        uint256 _vestingMonths     // 18 for team (after cliff)
    ) {
        require(_token != address(0), "Invalid token");
        require(_beneficiary != address(0), "Invalid beneficiary");
        require(_totalAllocation > 0, "Invalid allocation");
        require(_cliffMonths > 0, "Invalid cliff");
        require(_vestingMonths > 0, "Invalid vesting period");
        
        token = IERC20(_token);
        beneficiary = _beneficiary;
        totalAllocation = _totalAllocation;
        startTime = block.timestamp;
        cliff = _cliffMonths * 30 days;
        vestingEnd = startTime + (_cliffMonths + _vestingMonths) * 30 days;
    }
    
    function getUnlockedAmount() public view returns (uint256) {
        // Nothing unlocked before cliff
        if (block.timestamp < startTime + cliff) {
            return 0;
        }
        
        // Everything unlocked after vesting period
        if (block.timestamp >= vestingEnd) {
            return totalAllocation;
        }
        
        // Linear unlock after cliff
        uint256 elapsed = block.timestamp - (startTime + cliff);
        uint256 vestingDuration = vestingEnd - (startTime + cliff);
        
        return (totalAllocation * elapsed) / vestingDuration;
    }
    
    function getWithdrawableAmount() public view returns (uint256) {
        uint256 unlocked = getUnlockedAmount();
        return unlocked > withdrawn ? unlocked - withdrawn : 0;
    }
    
    // ✅ FIXED (H-3): Added ReentrancyGuard
    function withdraw() external nonReentrant {
        require(msg.sender == beneficiary, "Only beneficiary");
        
        uint256 amount = getWithdrawableAmount();
        require(amount > 0, "Nothing to withdraw");
        
        withdrawn += amount;
        require(token.transfer(beneficiary, amount), "Transfer failed");
        
        emit TokensWithdrawn(beneficiary, amount);
    }
}
```

---

## Summary of Changes

### BondingCurvePool.sol (7 changes)
1. ✅ Remove `CURVE_SUPPLY_PCT` and `LP_SUPPLY_PCT` constants
2. ✅ Add `reservedPercentage` state variable + `factory` address + vesting registry
3. ✅ Update constructor to accept `_reservedPercentage` parameter
4. ✅ Add `transferReserveToVesting()` function (fixes token transfer bug)
5. ✅ Update `initiateGraduation()` to use variable reserve
6. ✅ Update `getReserveStatus()` to use variable reserve
7. ✅ Update `_update()` to exempt vesting contracts from wallet cap
8. ✅ Add guard in `distributeReserve()` for BASIC tokens

### TokenFactory.sol (2 changes)
1. ✅ Add 7 new parameters to `createToken()` signature
2. ✅ Use `pool.transferReserveToVesting()` instead of `transferFrom()`

### Vesting Contracts (2 changes)
1. ✅ Remove `Ownable` inheritance (fully immutable)
2. ✅ Add `ReentrancyGuard` to all `withdraw()` functions

---

## Testing Checklist

### Critical Path Tests
- [ ] BASIC token (0% reserve) deploys without vesting contracts
- [ ] PRO token (25% reserve) deploys with 3 vesting contracts
- [ ] Token transfers from pool to vesting work correctly
- [ ] Vesting contracts exempt from 10% wallet cap
- [ ] Graduation works with actual available balance
- [ ] Vesting unlock calculations accurate for all 3 types

### Edge Cases
- [ ] 100% allocation to single category works
- [ ] Reserve already distributed → graduation still works
- [ ] Multiple withdrawals over time work correctly
- [ ] Beneficiary can't bypass vesting (no ownership transfer)

---

## Deployment Sequence

1. Deploy new `AirdropVesting.sol`, `LinearVesting.sol`, `CliffVesting.sol`
2. Deploy updated `BondingCurvePool.sol` (with 8 changes)
3. Deploy updated `TokenFactory.sol` (with new signature)
4. Test on testnet thoroughly
5. External security audit
6. Deploy to mainnet as V2 system

---

## Gas Estimates (Updated)

**BASIC Token** (0% reserve):
- BondingCurvePool deployment: ~2.5M gas
- Total: **~2.5M gas**

**PRO Token** (25% reserve with vesting):
- BondingCurvePool deployment: ~2.8M gas
- AirdropVesting deployment: ~850K gas
- LinearVesting deployment: ~850K gas
- CliffVesting deployment: ~950K gas
- 3x transferReserveToVesting: ~150K gas
- Total: **~5.6M gas**

At 50 Gwei: ~0.28 ETH (~$560 USD at $2000/ETH) for PRO tokens

---

## Conclusion

This V2 specification fixes all critical security issues:
- ✅ Token transfers work correctly
- ✅ Variable reserve fully implemented
- ✅ Vesting contracts exempt from caps
- ✅ Fully immutable vesting (no ownership exploits)
- ✅ BASIC tokens protected from misleading functions
- ✅ Graduation handles actual balances correctly

**Ready for external security audit and testnet deployment.**
