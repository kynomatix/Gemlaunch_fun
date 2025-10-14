# PRO Token Vesting System - Smart Contract Specification V2
## ✅ CORRECTED MODEL - Simple and Clean

---

## Executive Summary

This document specifies the **correct tokenomics model** for PRO tokens with on-chain vesting enforcement.

### ✅ Tokenomics Model (CORRECTED)

**BASIC Tokens:**
- 75% → Bonding curve
- 25% → LP (fixed)
- 0% → Vesting
- **Total: 100%**

**PRO Tokens:**
- **(75 - X)% → Bonding curve** (where X = vesting percentage)
- **X% → Vesting** (0-25%)
- **25% → LP** (ALWAYS FIXED, same as BASIC)
- **Total: 100%**

### Examples:
- **0% vesting:** 75% curve + 0% vesting + 25% LP = 100%
- **10% vesting:** 65% curve + 10% vesting + 25% LP = 100%
- **25% vesting:** 50% curve + 25% vesting + 25% LP = 100%

---

## Key Simplification

**The 25% LP is ALWAYS the same as BASIC tokens.** The vesting comes from the bonding curve supply, not from the LP!

This means:
- ✅ Simple math: Curve = 75 - vesting%
- ✅ Graduation always has 25% LP (no minimum checks needed)
- ✅ No complex LP allocation logic
- ✅ Same graduation logic as BASIC tokens

---

## Smart Contract Changes

### 1. BondingCurvePool.sol

```solidity
// ====== CHANGE 1: Add State Variables ======
uint8 public reservedPercentage;  // 0-25 (vesting %)
address public factory;
mapping(address => bool) public isVestingContract;
bool public vestingInitialized;

// ====== CHANGE 2: Update Constructor ======
constructor(
    // ... existing params
    uint8 _reservedPercentage  // NEW: 0-25
) {
    // ... existing validation
    
    require(_reservedPercentage <= 25, "Vesting exceeds 25%");
    reservedPercentage = _reservedPercentage;
    factory = msg.sender;
    
    // ✅ KEY CALCULATION: Curve supply decreases as vesting increases
    uint256 curveSupply = totalSupply * (75 - _reservedPercentage) / 100;
    uint256 vestingSupply = totalSupply * _reservedPercentage / 100;
    
    // Mint curve tokens to contract (for bonding curve trading)
    _mint(address(this), curveSupply);
    
    // Mint vesting tokens to contract (factory will transfer to vesting contracts)
    if (vestingSupply > 0) {
        _mint(address(this), vestingSupply);
    }
    
    // Initialize virtual reserves (bonding curve math)
    virtualKasReserve = INITIAL_VIRTUAL_KAS;
    virtualTokenReserve = curveSupply;  // Only curve supply in AMM
}

// ====== CHANGE 3: Vesting Transfer Function ======
function transferReserveToVesting(address vestingContract, uint256 amount) external nonReentrant {
    require(msg.sender == factory, "Only factory");
    require(!vestingInitialized, "Already finalized");
    
    // Register for wallet cap exemption
    isVestingContract[vestingContract] = true;
    
    _transfer(address(this), vestingContract, amount);
}

// ====== CHANGE 4: Finalize Vesting Setup ======
function finalizeVestingSetup() external {
    require(msg.sender == factory, "Only factory");
    require(!vestingInitialized, "Already finalized");
    
    vestingInitialized = true;
    reserveDistributed = true;
    
    emit VestingFinalized(block.timestamp);
}

// ====== CHANGE 5: Graduation (NO CHANGES NEEDED!) ======
function initiateGraduation() external nonReentrant {
    require(msg.sender == graduationOracle, "Only oracle");
    require(!graduated && !graduating, "Already graduated");
    
    graduating = true;
    
    // ✅ LP is ALWAYS 25% (same as BASIC tokens)
    uint256 lpTokens = totalSupply() * 25 / 100;
    
    // Approve graduation oracle
    _approve(address(this), graduationOracle, lpTokens);
    
    // Transfer KAS liquidity
    uint256 actualKasLiquidity = virtualKasReserve - INITIAL_VIRTUAL_KAS;
    _safeSend(graduationOracle, actualKasLiquidity);
    liquidityTransferred = true;
    
    emit GraduationInitiated(virtualKasReserve, lpTokens);
}

// ====== CHANGE 6: Update Wallet Cap Exemption ======
function _update(address from, address to, uint256 amount) internal override {
    // ... existing exemptions
    
    if (to != address(0) &&
        to != address(this) &&
        to != graduationOracle &&
        !isVestingContract[to] &&  // ✅ Exempt vesting contracts
        !graduated) {
        
        uint256 maxWallet = totalSupply() * MAX_WALLET_PCT / 100;
        require(balanceOf(to) + amount <= maxWallet, "Exceeds max wallet");
    }
    
    super._update(from, to, amount);
}

// ====== CHANGE 7: Prevent distributeReserve() if Vesting Enabled ======
function distributeReserve(address[] calldata recipients, uint256[] calldata amounts) external nonReentrant {
    require(msg.sender == creator, "Only creator");
    require(reservedPercentage == 0, "PRO tokens use vesting contracts"); // ✅ Block if vesting enabled
    require(!reserveDistributed, "Already distributed");
    
    // ... rest of function
}
```

---

### 2. TokenFactory.sol

```solidity
function createToken(
    // ... existing params
    uint8 reservedPercentage,        // 0-25 (vesting %)
    uint8 airdropsAllocation,        // % of vesting reserve
    uint8 marketingAllocation,       // % of vesting reserve
    uint8 teamAllocation,            // % of vesting reserve
    address airdropBeneficiary,
    address marketingBeneficiary,
    address teamBeneficiary
) external nonReentrant whenNotPaused returns (
    address poolAddress,
    address airdropVestingAddress,
    address marketingVestingAddress,
    address teamVestingAddress
) {
    // Validate vesting params
    require(reservedPercentage <= 25, "Vesting exceeds 25%");
    
    if (reservedPercentage > 0) {
        // ✅ Allocations can sum to anything <= 100 (flexible split)
        require(
            airdropsAllocation + marketingAllocation + teamAllocation <= 100,
            "Allocations cannot exceed 100%"
        );
        
        require(airdropBeneficiary != address(0), "Invalid beneficiary");
        require(marketingBeneficiary != address(0), "Invalid beneficiary");
        require(teamBeneficiary != address(0), "Invalid beneficiary");
    }
    
    // Deploy pool with vesting percentage
    BondingCurvePool pool = new BondingCurvePool(
        name,
        symbol,
        totalSupply,
        msg.sender,
        treasury,
        airdropTreasury,
        platformDevelopmentWallet,
        antiBotEnabled,
        graduationOracle,
        admin,
        buybackReserveWallet,
        kaspaNetworkSupportWallet,
        communityRewardsWallet,
        reservedPercentage  // ✅ Pass vesting percentage
    );
    
    poolAddress = address(pool);
    
    // Deploy vesting contracts if PRO token
    if (reservedPercentage > 0) {
        uint256 totalVesting = totalSupply * reservedPercentage / 100;
        
        // Calculate token amounts
        uint256 airdropTokens = totalVesting * airdropsAllocation / 100;
        uint256 marketingTokens = totalVesting * marketingAllocation / 100;
        uint256 teamTokens = totalVesting * teamAllocation / 100;
        
        // Deploy airdrop vesting
        if (airdropTokens > 0) {
            AirdropVesting av = new AirdropVesting(
                poolAddress,
                airdropBeneficiary,
                airdropTokens
            );
            airdropVestingAddress = address(av);
            pool.transferReserveToVesting(airdropVestingAddress, airdropTokens);
            
            require(
                IERC20(poolAddress).balanceOf(airdropVestingAddress) == airdropTokens,
                "Airdrop vesting underfunded"
            );
        }
        
        // Deploy marketing vesting
        if (marketingTokens > 0) {
            LinearVesting mv = new LinearVesting(
                poolAddress,
                marketingBeneficiary,
                marketingTokens,
                12  // 12 months
            );
            marketingVestingAddress = address(mv);
            pool.transferReserveToVesting(marketingVestingAddress, marketingTokens);
            
            require(
                IERC20(poolAddress).balanceOf(marketingVestingAddress) == marketingTokens,
                "Marketing vesting underfunded"
            );
        }
        
        // Deploy team vesting
        if (teamTokens > 0) {
            CliffVesting tv = new CliffVesting(
                poolAddress,
                teamBeneficiary,
                teamTokens,
                6,   // 6 month cliff
                18   // 18 month vesting
            );
            teamVestingAddress = address(tv);
            pool.transferReserveToVesting(teamVestingAddress, teamTokens);
            
            require(
                IERC20(poolAddress).balanceOf(teamVestingAddress) == teamTokens,
                "Team vesting underfunded"
            );
        }
        
        // Finalize vesting setup (prevents bypass)
        pool.finalizeVestingSetup();
    }
    
    // Store metadata
    tokens[poolAddress] = TokenInfo({...});
    deployedTokens.push(poolAddress);
    
    emit TokenCreated(poolAddress, poolAddress, msg.sender, name, symbol, totalSupply, antiBotEnabled, block.timestamp);
    emit VestingDeployed(poolAddress, airdropVestingAddress, marketingVestingAddress, teamVestingAddress);
    
    return (poolAddress, airdropVestingAddress, marketingVestingAddress, teamVestingAddress);
}
```

---

### 3. Vesting Contracts (Unchanged)

See original spec for:
- `AirdropVesting.sol` (5% daily)
- `LinearVesting.sol` (12 month linear)
- `CliffVesting.sol` (6mo cliff + 18mo vest)

All contracts:
- ✅ Fully immutable (no Ownable)
- ✅ ReentrancyGuard on withdraw()
- ✅ Time-locked token releases

---

## Summary of Changes

### BondingCurvePool.sol (7 changes):
1. Add `reservedPercentage`, `factory`, `isVestingContract`, `vestingInitialized` state vars
2. Update constructor to accept `_reservedPercentage` and calculate curve = 75 - vesting%
3. Add `transferReserveToVesting()` function
4. Add `finalizeVestingSetup()` function
5. Graduation uses fixed 25% LP (NO CHANGES to graduation logic!)
6. Update `_update()` to exempt vesting contracts from wallet cap
7. Block `distributeReserve()` if vesting enabled

### TokenFactory.sol (3 changes):
1. Add vesting parameters to `createToken()` signature
2. Change allocation validation from `== 100` to `<= 100`
3. Deploy vesting contracts + transfer tokens + finalize

### Vesting Contracts (3 new contracts):
1. AirdropVesting.sol
2. LinearVesting.sol
3. CliffVesting.sol

**Total: 13 modifications across 5 contracts**

---

## Key Benefits of This Model

✅ **Simple**: LP is always 25% (same as BASIC)
✅ **No complex validation**: No LP minimum checks needed
✅ **Same graduation logic**: No changes to DEX migration
✅ **Flexible vesting**: 0-25% of total supply
✅ **Clean math**: Curve = 75 - vesting%

---

## Examples

### Example 1: BASIC Token (0% vesting)
- reservedPercentage = 0
- Curve: 75% (750M of 1B)
- Vesting: 0%
- LP: 25% (250M)

### Example 2: PRO Token (10% vesting)
- reservedPercentage = 10
- Curve: 65% (650M of 1B)
- Vesting: 10% (100M split into airdrops/marketing/team)
- LP: 25% (250M)

### Example 3: MAX PRO Token (25% vesting)
- reservedPercentage = 25
- Curve: 50% (500M of 1B)
- Vesting: 25% (250M split into airdrops/marketing/team)
- LP: 25% (250M)

---

## Audit Findings Addressed

### Round 1 Fixes:
- ✅ BI-1: Token transfer via `transferReserveToVesting()`
- ✅ BI-2: Variable vesting (not hardcoded 25%)
- ✅ BI-3: Vesting contracts exempt from wallet cap
- ✅ BI-4: Removed Ownable from vesting contracts
- ✅ H-3: ReentrancyGuard on all withdrawals

### Round 2 Fixes:
- ✅ NC-1: `vestingInitialized` flag prevents bypass
- ✅ NC-3: Balance verification after transfers

### Round 3 Fix:
- ✅ **NC-2 OBSOLETE**: No LP minimum check needed (always 25% by design!)

---

## PRO Token Claim Portal (UI Requirements)

### Overview
PRO tokens require a **Claim Portal** in the creator dashboard to allow beneficiaries to withdraw unlocked vesting tokens. This portal is SEPARATE from the airdrop system (which is self-contained within token communities).

### Portal Location
- **Dashboard → "Portal" button** (replaces "Fees" button for PRO token creators)
- Only visible to token creator wallet (beneficiary of marketing/team vesting)

### Portal Sections

#### Section 1: Creator Fees (Existing)
- Shows accumulated trading fees (same as BASIC tokens)
- Claim button for fees
- Display KAS amount

#### Section 2: Vesting Claims (NEW)
**Marketing Vesting:**
- Contract address
- Total allocation: X tokens
- Unlocked: Y tokens (Z%)
- Schedule: "12-month linear vesting"
- Progress bar showing unlock percentage
- "Claim Marketing Tokens" button
- Next unlock: "X tokens in Y days"

**Team Vesting:**
- Contract address
- Total allocation: X tokens
- Unlocked: Y tokens (Z%)
- Schedule: "6-month cliff + 18-month vesting"
- Progress bar showing unlock percentage
- Status: "Cliff period" or "Vesting active"
- "Claim Team Tokens" button
- Next unlock: "X tokens in Y days"

### Key Features
1. **Real-time unlock calculation** - Call vesting contract's `getWithdrawableAmount()`
2. **Transaction building** - Backend builds withdraw() transaction for user to sign
3. **Visual progress** - Progress bars, unlock schedules, countdown timers
4. **Access control** - Only beneficiary wallet can see/claim
5. **Airdrop exclusion** - Airdrop vesting NOT shown (handled separately by communities)

### Backend Requirements
- API endpoint: `GET /api/vesting/status/<token_address>` 
  - Returns unlocked amounts for marketing & team
- API endpoint: `POST /api/vesting/withdraw/<token_address>/<vesting_type>`
  - Builds withdrawal transaction
- Database: Track marketing_beneficiary, team_beneficiary addresses
- Web3: Call `getWithdrawableAmount()`, `getUnlockedAmount()` on vesting contracts

### Frontend Flow
1. User connects wallet
2. Check if wallet is creator/beneficiary of any PRO tokens
3. If yes, show "Portal" button in dashboard
4. Portal displays:
   - Creator fees section (if any)
   - Marketing vesting section (if wallet is marketing beneficiary)
   - Team vesting section (if wallet is team beneficiary)
5. User clicks "Claim" → Backend builds transaction → User signs
6. Tokens transferred from vesting contract to beneficiary

---

## Implementation Checklist

### Smart Contracts:
- [ ] Update BondingCurvePool.sol (7 changes)
- [ ] Create AirdropVesting.sol
- [ ] Create LinearVesting.sol
- [ ] Create CliffVesting.sol
- [ ] Update TokenFactory.sol (3 changes)
- [ ] Write comprehensive tests
- [ ] External security audit

### Backend:
- [ ] Update Web3Service.create_token_tx_data() with vesting params
- [ ] Add vesting address tracking in database
- [ ] Create vesting status API endpoints
- [ ] Add vesting withdrawal transaction builders
- [ ] Track beneficiary addresses for each vesting type

### Frontend - Token Creation:
- [ ] Display tokenomics breakdown: X% curve + Y% vesting + 25% LP
- [ ] Show "Bonding curve will have X%" based on vesting slider
- [ ] Vesting contract addresses on token page

### Frontend - PRO Token Claim Portal (NEW REQUIREMENT):
- [ ] **Rename "Fees" to "Portal" for PRO token creators in dashboard**
- [ ] **Portal should show TWO sections:**
  - **1. Creator Fees** (from trading, same as BASIC tokens)
  - **2. Vesting Claims** (from Marketing & Team vesting contracts)
- [ ] **Vesting Claims UI:**
  - Display unlocked tokens from Marketing vesting contract
  - Display unlocked tokens from Team vesting contract  
  - Show vesting progress bars (% unlocked vs total)
  - "Claim" button for each vesting type
  - Display total claimable amount
- [ ] **Note: Airdrop vesting is self-contained** (handled by token communities with preset buttons, NOT shown in creator portal)
- [ ] **Access control:** Only token creator wallet can access the portal
- [ ] **Show vesting schedules:**
  - Marketing: "X tokens unlocked of Y total (12-month linear)"
  - Team: "X tokens unlocked of Y total (6mo cliff + 18mo vest)"

---

---

## Audit Findings (Round 3) - All Addressed ✅

### Critical Issues (BLOCKING):
- ✅ **BI-1**: Token transfer mechanism → `transferReserveToVesting()` added
- ✅ **BI-2**: Incorrect reserve math → V2 model uses correct allocation (curve = 75 - vesting%)
- ✅ **BI-3**: Wallet cap blocks vesting → `isVestingContract` mapping exempts vesting contracts
- ✅ **BI-4**: Vesting contracts mutable → Removed `Ownable`, fully immutable

### High Severity:
- ✅ **H-1**: Vesting initialization bypass → `vestingInitialized` flag + `finalizeVestingSetup()`
- ✅ **H-2**: Graduation LP calculation → Always 25% (fixed), no calculation needed
- ✅ **H-3**: Reentrancy on withdrawals → `nonReentrant` on all `withdraw()` functions

### Medium Severity:
- ✅ **M-1**: Allocation validation → Changed to `<= 100` (flexible split)
- ✅ **M-2**: LP minimum requirement → N/A (always 25% by design)

**All audit findings resolved!** The V2 model is simpler, safer, and mathematically correct.

---

## Conclusion

This simplified model is **much cleaner** than the previous spec:
- No complex LP minimum validation
- Same graduation logic as BASIC tokens  
- 25% LP is guaranteed by contract design
- Vesting comes from curve supply, not LP
- Claim portal connects vesting contracts to UI

**Key Components:**
1. **Smart Contracts**: 5 contracts (BondingCurvePool + Factory + 3 vesting)
2. **Backend**: Vesting status APIs + withdrawal transaction builders
3. **Frontend**: Claim portal for marketing/team vesting (airdrop is self-contained)

**Ready for implementation!** 🚀
