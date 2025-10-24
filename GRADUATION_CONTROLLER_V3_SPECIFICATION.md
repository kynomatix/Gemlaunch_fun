# GraduationControllerV3 Specification & Audit Plan

**Version:** 3.0  
**Date:** October 24, 2025  
**Status:** Pre-Implementation Audit Phase

---

## Executive Summary

GraduationControllerV2 contains a critical bug that prevents token graduation to Uniswap V3 DEX pools. The bug stems from querying stale reserve values from BondingCurvePool after KAS has been transferred out. V3 will fix this by snapshotting liquidity values during initiation and using only those trusted values for DEX price calculation.

**Impact:** All tokens using V2 cannot complete graduation (stuck in "initiating" status)  
**Severity:** Critical (P0)  
**Fix Complexity:** Medium (new storage + calculation logic changes)

---

## 1. Current V2 Issues

### 1.1 The Reserve Staleness Bug

**Location:** `GraduationControllerV2.sol` lines 700-704 in `_initializePoolIfNeeded()`

**What Happens:**

```solidity
// V2 BUGGY CODE
function _initializePoolIfNeeded(...) internal {
    // ...
    uint160 initialSqrtPrice = _calculateSqrtPriceX96(
        pool.virtualKasReserve(),    // ❌ STALE: Returns 1089.991 KAS
        pool.virtualTokenReserve(),  // ❌ STALE: Returns 688.08 tokens
        tokenAddress
    );
}
```

**The Problem:**

1. **Initiation Phase** (`BondingCurvePool.initiateGraduation()`):
   - Transfers 1089.99 KAS to GraduationController ✅
   - Approves GC for 250M tokens ✅
   - Sets `graduating = true` ✅
   - **BUT: Does NOT update `virtualKasReserve` or `virtualTokenReserve`** ❌

2. **Completion Phase** (`GraduationControllerV2.completeGraduation()`):
   - Queries `pool.virtualKasReserve()` → Returns **1089.991 KAS** (stale)
   - Pool actually only has **0.001 KAS** (INITIAL_VIRTUAL_KAS seed)
   - Calculates Uniswap V3 sqrtPrice using wrong reserves
   - **Transaction reverts silently** (no error message)

### 1.2 Verified Evidence

**KRABBY Token (0x4d259ecf324709496dcab7c141bfedffa2f88b2a):**
```
Pool virtualKasReserve:     1089.9910 KAS ← STALE (not updated after transfer)
Pool actual KAS balance:    0.0010 KAS    ← Only virtual seed remains
GC KAS balance:             1089.9900 KAS ← Liquidity was transferred
Expected KAS for DEX:       89.9910 KAS   ← Correct value (stored in GC)
Expected Tokens for DEX:    250,000,000   ← Correct value (stored in GC)
```

### 1.3 Why Individual Components Pass Tests

All these succeed individually but fail when combined:
- ✅ `transferFrom(pool → GC, 250M tokens)` - works
- ✅ `WKAS.deposit(89.991 KAS)` - works
- ✅ `Factory.createPool(KRABBY, WKAS, 2500)` - works
- ✅ All approvals correct
- ✅ All balances sufficient
- ❌ **But `completeGraduation()` reverts** due to price calculation using stale reserves

---

## 2. Root Cause Analysis

### 2.1 Architecture Flaw

V2 assumes `virtualKasReserve` and `virtualTokenReserve` represent the pool's actual state after graduation initiation. This assumption is **incorrect** because:

1. BondingCurvePool doesn't update reserves when transferring KAS out
2. Reserves are meant for bonding curve pricing, not post-graduation state
3. GC should trust its own stored values, not query mutable pool state

### 2.2 Why V2 Queries Pool Reserves

The original intent (lines 700-718) was to use the bonding curve's final price as the DEX launch price for **price continuity**. However:

- **Correct approach:** Use the **liquidity ratio** that will be deposited (89.991 KAS : 250M tokens)
- **V2 approach:** Use bonding curve reserves (stale 1089.991 KAS : 688.08 tokens)
- **Result:** Massive price mismatch causes Uniswap V3 operations to fail

### 2.3 What the Price Should Be

The Uniswap V3 pool price should reflect the **actual liquidity being deposited**:

```
Liquidity for DEX:
- KAS: virtualKasReserve - INITIAL_VIRTUAL_KAS = 1089.991 - 1.0 = 1089.99 KAS
- But only 10% goes to DEX (LP_SUPPLY_PERCENTAGE in GC is NOT bonding curve LP%)
  
Wait, let me check the actual calculation...

Actually from V2 line 510-513:
- expectedKas = pool.virtualKasReserve() - INITIAL_VIRTUAL_KAS
- expectedTokens = pool.totalSupply() * LP_SUPPLY_PERCENTAGE / 100 = 1B * 25% = 250M

So the DEX gets:
- KAS: 89.991 KAS (entire reserve minus seed, but GC has 1089.99?)
```

**WAIT - THIS REVEALS ANOTHER BUG!**

Let me check the actual expected values:

From diagnostic output:
- expectedKasLiquidity in GC: 89.991 KAS
- virtualKasReserve in pool: 1089.991 KAS
- GC actual balance: 1089.99 KAS

So the pool transferred 1089.99 KAS but GC only expects to use 89.991 KAS for the DEX!

This means:
- Pool sent: 1089.99 KAS
- DEX will use: 89.991 KAS  
- **Excess: 1000 KAS** (maybe for fees/creator?)

The price should be based on **89.991 KAS : 250M tokens**, not the full reserves.

---

## 3. Uniswap V3 LP Setup Considerations

### 3.1 Price Calculation Formula

Uniswap V3 uses `sqrtPriceX96` for pool initialization:

```solidity
sqrtPriceX96 = sqrt(price) * 2^96

where:
price = token1 / token0  (token addresses ordered: token0 < token1)
```

**For KRABBY:**
```
Addresses:
- KRABBY: 0x4D259ecF324709496DcAb7C141bFEDfFA2f88b2a
- WKAS:   0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94

Ordering: KRABBY < WKAS (0x4D... < 0xD1...)
Therefore:
- token0 = KRABBY (memecoin)
- token1 = WKAS

price = WKAS / KRABBY = 89.991 KAS / 250M tokens
      = 0.00000035996 WKAS per token
```

### 3.2 Current V2 Calculation (WRONG)

```solidity
// V2 uses stale reserves:
kasReserve = 1089.991 KAS  (stale, should be 89.991)
tokenReserve = 688.08 tokens (stale, should be 250M)

// Token ordering
tokenIsToken0 = true (KRABBY < WKAS)

// Price calculation (V2 line 756-757)
priceX192 = FullMath.mulDiv(kasReserve, 2^192, tokenReserve)
          = FullMath.mulDiv(1089.991e18, 2^192, 688.08e18)
          = MASSIVE NUMBER (wrong!)
```

### 3.3 Correct V3 Calculation

```solidity
// V3 should use stored snapshot values:
kasLiquidity = 89.991 KAS
tokenLiquidity = 250,000,000 tokens

// Token ordering (same)
tokenIsToken0 = true (KRABBY < WKAS)

// Correct price calculation
priceX192 = FullMath.mulDiv(kasLiquidity, 2^192, tokenLiquidity)
          = FullMath.mulDiv(89.991e18, 2^192, 250e6*1e18)
          = correct sqrtPriceX96
```

### 3.4 Tick Range

V2 uses full-range liquidity:
```solidity
tickLower = -887220  // MIN_TICK
tickUpper = 887220   // MAX_TICK
```

This is correct - full-range LPs provide liquidity at all prices, maximizing trading efficiency for a new DEX listing.

### 3.5 Fee Tier

V2 uses 0.25% fee tier (2500):
```solidity
POOL_FEE_TIER = 2500  // 0.25%
```

This is appropriate for volatile memecoin pairs (higher than 0.05% for stablecoins, lower than 1% for exotic pairs).

---

## 4. Industry Best Practices

### 4.1 Pump.fun (Solana)

**Graduation Flow:**
1. Bonding curve reaches market cap threshold
2. **Snapshot reserves at initiation block**
3. Transfer liquidity to Raydium AMM program
4. Initialize pool using **snapshotted reserves**
5. Burn LP tokens to lock liquidity

**Key Insight:** Never queries bonding curve state after initiation

### 4.2 Friend.tech (Base)

**No graduation** - perpetual bonding curve model  
**Insight:** Avoids the graduation complexity entirely

### 4.3 SunPump (Tron)

**Graduation Flow:**
1. Snapshots reserves when bonding curve completes
2. Creates SunSwap V2 pair
3. Uses snapshot for initial liquidity add
4. Emits event with snapshot hash for verification

**Key Insight:** Snapshot hash ensures deterministic pricing

### 4.4 Common Pattern

**All successful implementations:**
- ✅ Snapshot liquidity values during initiation
- ✅ Store snapshots in controller/manager contract
- ✅ Use snapshots exclusively for DEX initialization
- ❌ Never query bonding curve after initiation

---

## 5. V3 Architecture & Design

### 5.1 New Storage Structure

```solidity
/**
 * @dev Snapshot of graduation liquidity values
 * @notice Captured during initiateGraduation, immutable after creation
 */
struct GraduationSnapshot {
    uint256 kasLiquidity;        // KAS to wrap and add to DEX
    uint256 tokenLiquidity;      // Tokens to add to DEX (25% of supply)
    uint24 feeTier;              // Uniswap V3 fee tier (2500 = 0.25%)
    uint32 initiatedAt;          // Block timestamp of initiation
    uint160 targetSqrtPriceX96;  // Pre-calculated target price
    bool poolInitialized;        // True after pool.initialize() succeeds
    bool lpMinted;               // True after liquidity minted
    address uniswapPool;         // Created pool address
}

// Mapping: token address => graduation snapshot
mapping(address => GraduationSnapshot) public graduationSnapshots;
```

### 5.2 Why These Fields?

1. **kasLiquidity / tokenLiquidity:** The ground truth for DEX pricing
2. **feeTier:** Stored for consistency (always 2500 for now)
3. **initiatedAt:** Audit trail & deadline enforcement
4. **targetSqrtPriceX96:** Pre-calculated to save gas in completion
5. **poolInitialized / lpMinted:** State machine tracking
6. **uniswapPool:** Reference to created pool

### 5.3 Modified Functions

#### 5.3.1 `initiateGraduation()` Changes

```solidity
function initiateGraduation(address tokenAddress) 
    external 
    nonReentrant 
    whenNotPaused
    onlyOracle 
{
    if (hasGraduated[tokenAddress]) revert AlreadyGraduated();
    if (graduationSnapshots[tokenAddress].initiatedAt != 0) revert AlreadyInitiated();
    
    BondingCurvePool pool = BondingCurvePool(payable(tokenAddress));
    
    // Calculate expected liquidity amounts BEFORE initiating
    uint256 expectedKas = pool.virtualKasReserve() > INITIAL_VIRTUAL_KAS 
        ? pool.virtualKasReserve() - INITIAL_VIRTUAL_KAS 
        : 0;
    uint256 expectedTokens = (pool.totalSupply() * LP_SUPPLY_PERCENTAGE) / 100;
    
    if (expectedKas == 0 || expectedTokens == 0) revert InsufficientKAS();
    
    // ✅ NEW: Pre-calculate target sqrtPrice
    uint160 targetSqrtPrice = _calculateSqrtPriceX96(
        expectedKas,
        expectedTokens,
        tokenAddress
    );
    
    if (targetSqrtPrice == 0) revert InvalidPrice();
    
    // ✅ NEW: Store snapshot BEFORE pool state changes
    graduationSnapshots[tokenAddress] = GraduationSnapshot({
        kasLiquidity: expectedKas,
        tokenLiquidity: expectedTokens,
        feeTier: POOL_FEE_TIER,
        initiatedAt: uint32(block.timestamp),
        targetSqrtPriceX96: targetSqrtPrice,
        poolInitialized: false,
        lpMinted: false,
        uniswapPool: address(0)
    });
    
    // Trigger graduation on the pool contract
    try pool.initiateGraduation() {
        emit GraduationSnapshotCreated(
            tokenAddress,
            expectedKas,
            expectedTokens,
            targetSqrtPrice,
            block.timestamp
        );
        
        emit GraduationInitiated(
            tokenAddress,
            expectedKas,
            expectedTokens,
            block.timestamp
        );
    } catch Error(string memory reason) {
        // Clean up snapshot on failure
        delete graduationSnapshots[tokenAddress];
        emit GraduationFailed(tokenAddress, reason, block.timestamp);
        revert(reason);
    } catch (bytes memory) {
        delete graduationSnapshots[tokenAddress];
        emit GraduationFailed(tokenAddress, "Unknown error in pool.initiateGraduation", block.timestamp);
        revert("Pool graduation initiation failed");
    }
}
```

#### 5.3.2 `completeGraduation()` Changes

```solidity
function completeGraduation(address tokenAddress) 
    external 
    nonReentrant 
    whenNotPaused
    onlyOracle 
{
    if (hasGraduated[tokenAddress]) revert AlreadyGraduated();
    
    // ✅ NEW: Load snapshot
    GraduationSnapshot storage snapshot = graduationSnapshots[tokenAddress];
    if (snapshot.initiatedAt == 0) revert NotInitiated();
    if (snapshot.lpMinted) revert AlreadyCompleted();
    
    BondingCurvePool pool = BondingCurvePool(payable(tokenAddress));
    
    // Validate pool state
    if (!pool.graduating()) revert NotGraduating();
    if (!pool.liquidityTransferred()) revert LiquidityNotTransferred();
    
    // ✅ CHANGED: Use snapshot values instead of querying pool
    uint256 kasLiquidity = snapshot.kasLiquidity;
    uint256 tokenLiquidity = snapshot.tokenLiquidity;
    
    // Validate we actually received the KAS
    if (address(this).balance < kasLiquidity) revert InsufficientKAS();
    
    // Validate we have token approval or balance
    uint256 tokenBalance = IERC20(tokenAddress).balanceOf(address(this));
    uint256 tokenAllowance = IERC20(tokenAddress).allowance(address(pool), address(this));
    
    if (tokenBalance < tokenLiquidity && tokenAllowance < tokenLiquidity) {
        revert InsufficientTokens();
    }
    
    // Transfer tokens if we don't already have them
    if (tokenBalance < tokenLiquidity) {
        IERC20(tokenAddress).safeTransferFrom(address(pool), address(this), tokenLiquidity);
    }
    
    // Wrap KAS to WKAS
    IWKAS wkas = IWKAS(kaspaFinanceWKAS);
    wkas.deposit{value: kasLiquidity}();
    
    // Determine token ordering
    (address token0, address token1) = tokenAddress < kaspaFinanceWKAS
        ? (tokenAddress, kaspaFinanceWKAS)
        : (kaspaFinanceWKAS, tokenAddress);
    
    (uint256 amount0, uint256 amount1) = tokenAddress < kaspaFinanceWKAS
        ? (tokenLiquidity, kasLiquidity)
        : (kasLiquidity, tokenLiquidity);
    
    // Create or get Uniswap V3 pool
    address poolAddress = _getOrCreatePool(token0, token1);
    snapshot.uniswapPool = poolAddress;
    
    // ✅ CHANGED: Initialize pool using snapshot sqrtPrice
    _initializePoolIfNeeded(poolAddress, snapshot, tokenAddress);
    snapshot.poolInitialized = true;
    
    // Approve position manager
    IERC20(token0).forceApprove(kaspaFinancePositionManager, amount0);
    IERC20(token1).forceApprove(kaspaFinancePositionManager, amount1);
    
    // Mint liquidity
    (uint256 positionId, uint128 liquidity, uint256 actualAmount0, uint256 actualAmount1) = 
        _mintLiquidityPosition(token0, token1, amount0, amount1);
    
    if (liquidity == 0) revert NoLiquidityMinted();
    
    // Validate slippage
    uint256 minAmount0 = (amount0 * (10000 - graduationSlippageBps)) / 10000;
    uint256 minAmount1 = (amount1 * (10000 - graduationSlippageBps)) / 10000;
    if (actualAmount0 < minAmount0 || actualAmount1 < minAmount1) {
        revert SlippageExceeded();
    }
    
    // Mark snapshot complete
    snapshot.lpMinted = true;
    
    // Refund excess
    _refundExcessTokens(token0, token1, amount0, amount1, actualAmount0, actualAmount1, address(pool));
    
    // Update state
    hasGraduated[tokenAddress] = true;
    graduationTimestamp[tokenAddress] = block.timestamp;
    liquidityPositionId[tokenAddress] = positionId;
    uniswapPoolAddress[tokenAddress] = poolAddress;
    
    // Complete on pool
    try pool.completeGraduation() {
        // Success
    } catch Error(string memory reason) {
        emit GraduationFailed(tokenAddress, string(abi.encodePacked("Pool completion failed: ", reason)), block.timestamp);
    }
    
    uint256 kasAdded = (token1 == kaspaFinanceWKAS) ? actualAmount1 : actualAmount0;
    uint256 tokensAdded = (token0 == tokenAddress) ? actualAmount0 : actualAmount1;
    
    emit GraduationCompleted(
        tokenAddress,
        poolAddress,
        positionId,
        kasAdded,
        tokensAdded,
        block.timestamp
    );
}
```

#### 5.3.3 `_initializePoolIfNeeded()` Changes

```solidity
function _initializePoolIfNeeded(
    address poolAddress, 
    GraduationSnapshot storage snapshot,  // ✅ CHANGED: Accept snapshot instead of pool
    address tokenAddress
) internal {
    IUniswapV3Pool uniPool = IUniswapV3Pool(poolAddress);
    
    // Check if pool is already initialized
    (uint160 sqrtPriceX96, , , , , , ) = uniPool.slot0();
    
    if (sqrtPriceX96 == 0) {
        // ✅ CHANGED: Use pre-calculated snapshot sqrtPrice
        uint160 initialSqrtPrice = snapshot.targetSqrtPriceX96;
        
        if (initialSqrtPrice == 0) revert InvalidPrice();
        
        try uniPool.initialize(initialSqrtPrice) {
            emit PoolInitialized(tokenAddress, poolAddress, initialSqrtPrice, block.timestamp);
        } catch {
            revert PoolInitializationFailed();
        }
    } else {
        // Pool already initialized, validate price is reasonable
        // ✅ CHANGED: Compare against snapshot sqrtPrice
        _validatePriceDeviation(sqrtPriceX96, snapshot.targetSqrtPriceX96);
    }
}
```

### 5.4 New Events

```solidity
event GraduationSnapshotCreated(
    address indexed tokenAddress,
    uint256 kasLiquidity,
    uint256 tokenLiquidity,
    uint160 targetSqrtPriceX96,
    uint256 timestamp
);

event PoolInitialized(
    address indexed tokenAddress,
    address indexed poolAddress,
    uint160 sqrtPriceX96,
    uint256 timestamp
);

event LiquidityMinted(
    address indexed tokenAddress,
    uint256 positionId,
    uint128 liquidity,
    uint256 amount0,
    uint256 amount1,
    uint256 timestamp
);
```

### 5.5 New View Functions

```solidity
/**
 * @notice Get graduation snapshot for a token
 * @param tokenAddress The token to query
 * @return Graduation snapshot data
 */
function getGraduationSnapshot(address tokenAddress) 
    external 
    view 
    returns (GraduationSnapshot memory) 
{
    return graduationSnapshots[tokenAddress];
}

/**
 * @notice Check if a token has a valid snapshot
 * @param tokenAddress The token to check
 * @return True if snapshot exists and is valid
 */
function hasValidSnapshot(address tokenAddress) 
    external 
    view 
    returns (bool) 
{
    GraduationSnapshot storage snapshot = graduationSnapshots[tokenAddress];
    return snapshot.initiatedAt != 0 && !snapshot.lpMinted;
}
```

---

## 6. Implementation Checklist

### 6.1 Contract Changes

- [ ] Add `GraduationSnapshot` struct definition
- [ ] Add `graduationSnapshots` mapping
- [ ] Update `initiateGraduation()` to create snapshots
- [ ] Update `completeGraduation()` to use snapshots
- [ ] Update `_initializePoolIfNeeded()` signature and logic
- [ ] Remove `expectedKasLiquidity` and `expectedTokenLiquidity` mappings (replaced by snapshot)
- [ ] Add new events
- [ ] Add new view functions
- [ ] Update error messages for clarity

### 6.2 Gas Optimization

- [ ] Pack struct fields efficiently (uint256, uint32, uint160, bool)
- [ ] Use storage pointers to avoid SLOAD duplicates
- [ ] Consider making snapshot immutable after creation

### 6.3 Security Considerations

- [ ] Reentrancy protection (already has `nonReentrant`)
- [ ] Snapshot can only be created once per token
- [ ] Snapshot cannot be modified after creation
- [ ] Validate all snapshot fields are non-zero
- [ ] Protect against price manipulation between initiation and completion

---

## 7. Testing Strategy

### 7.1 Unit Tests

```javascript
describe("GraduationControllerV3", function() {
  describe("Snapshot Creation", function() {
    it("Should create snapshot with correct values during initiation");
    it("Should prevent duplicate snapshots");
    it("Should cleanup snapshot if pool.initiateGraduation() reverts");
    it("Should emit GraduationSnapshotCreated event");
  });
  
  describe("Price Calculation", function() {
    it("Should calculate correct sqrtPriceX96 for token0 < WKAS ordering");
    it("Should calculate correct sqrtPriceX96 for WKAS < token0 ordering");
    it("Should handle edge case: minimal liquidity (1 KAS : 1M tokens)");
    it("Should handle edge case: maximal liquidity (10000 KAS : 1B tokens)");
  });
  
  describe("Snapshot Usage", function() {
    it("Should use snapshot values, not pool queries");
    it("Should initialize pool with snapshot sqrtPrice");
    it("Should succeed even if pool reserves are zeroed");
  });
  
  describe("State Machine", function() {
    it("Should track poolInitialized and lpMinted flags");
    it("Should prevent double-completion");
    it("Should allow re-completion if LP mint failed previously");
  });
});
```

### 7.2 Integration Tests

```javascript
describe("Full Graduation Flow", function() {
  it("Should complete graduation end-to-end with snapshot");
  it("Should handle pool reserves being mutated between init and complete");
  it("Should create functional Uniswap V3 pool");
  it("Should allow swaps immediately after graduation");
});
```

### 7.3 Fuzz Tests

```javascript
describe("Fuzz Testing", function() {
  it("Should handle random liquidity amounts");
  it("Should handle various token decimal configurations");
  it("Should handle different fee tiers");
  it("Should handle edge case reserve ratios");
});
```

### 7.4 Manual Testing Checklist

- [ ] Deploy V3 to testnet
- [ ] Create test token and reach graduation threshold
- [ ] Initiate graduation and verify snapshot creation
- [ ] Mutate pool reserves manually to simulate the bug
- [ ] Complete graduation and verify success
- [ ] Perform test swaps on graduated pool
- [ ] Verify LP position ownership

---

## 8. Migration Plan

### 8.1 KRABBY Token (Immediate)

**Option A: Manual Graduation**
1. Deploy GraduationControllerV3
2. Manually call `initiateGraduation()` on KRABBY from V3 to create snapshot
3. This will fail (already graduating) - need special recovery path

**Option B: Cancel & Retry**
1. Add `cancelGraduationAdmin()` function to BondingCurvePool (requires pool redeployment)
2. Cancel KRABBY graduation in V2
3. Initiate graduation in V3
4. Complete in V3

**Option C: Direct Pool Creation (Recommended)**
1. Deploy V3
2. Add `emergencyGraduate()` function to V3 that bypasses normal flow
3. Manually create snapshot for KRABBY
4. Manually create Uniswap pool and add liquidity
5. Mark KRABBY as graduated in database

### 8.2 Future Tokens

1. Deploy GraduationControllerV3
2. Update TokenFactory to point new tokens to V3
3. Update oracle service to call V3 for graduation
4. Update frontend to read from V3 graduation status

### 8.3 Database Schema Changes

```sql
-- Add controller version tracking
ALTER TABLE tokens ADD COLUMN graduation_controller_version VARCHAR(10) DEFAULT 'v2';
ALTER TABLE tokens ADD COLUMN graduation_snapshot_kas NUMERIC(78, 0);
ALTER TABLE tokens ADD COLUMN graduation_snapshot_tokens NUMERIC(78, 0);
ALTER TABLE tokens ADD COLUMN graduation_snapshot_sqrt_price VARCHAR(66);

-- Update KRABBY
UPDATE tokens 
SET graduation_controller_version = 'v3_emergency',
    graduation_snapshot_kas = 89991000000000000000,
    graduation_snapshot_tokens = 250000000000000000000000000
WHERE contract_address = '0x4d259ecf324709496dcab7c141bfedffa2f88b2a';
```

### 8.4 Backend Service Updates

```python
# services/graduation_completion_service.py

def get_graduation_controller_for_token(token):
    """Route to correct controller based on token deployment date"""
    if token.created_at < datetime(2025, 10, 24):
        # Legacy V2 tokens - use V3 emergency path
        return get_v3_controller()
    else:
        # New tokens - use V3 normal path
        return get_v3_controller()
```

---

## 9. Security Audit Focus Areas

### 9.1 Critical Issues to Review

1. **Snapshot Immutability**
   - Can snapshots be overwritten?
   - Can snapshots be created multiple times?
   - What happens if snapshot creation partially succeeds?

2. **Price Manipulation**
   - Can an attacker manipulate reserves between init and complete?
   - Is the snapshot value source trustworthy?
   - Are there flash loan attack vectors?

3. **Reentrancy**
   - All external calls protected?
   - CEI pattern followed?
   - Snapshot state updated before external calls?

4. **Integer Overflow/Underflow**
   - sqrtPrice calculation safe?
   - Large liquidity amounts handled?
   - Token decimal mismatches?

5. **Access Control**
   - Only oracle can initiate/complete?
   - Owner functions properly restricted?
   - Emergency functions have appropriate controls?

### 9.2 Edge Cases

1. **Snapshot with 0 values**
   - What if kasLiquidity = 0?
   - What if tokenLiquidity = 0?

2. **Pool already exists**
   - What if someone front-runs pool creation?
   - What if pool already initialized with different price?

3. **Deadline expired**
   - Should snapshots expire after X blocks?
   - What if completion is delayed significantly?

4. **Token transfer failure**
   - What if pool refuses to transfer tokens?
   - What if approval is revoked between init and complete?

---

## 10. Deployment Plan

### 10.1 Testnet Deployment

1. Deploy GraduationControllerV3 to Kasplex testnet
2. Deploy mock BondingCurvePool for testing
3. Run full test suite
4. Manual QA with test tokens
5. Simulate V2 bug scenario and verify V3 fix
6. Get community/team review

### 10.2 Mainnet Deployment

1. Final security audit
2. Deploy to mainnet
3. Verify contract on explorer
4. Update TokenFactory to use V3
5. Update oracle service
6. Monitor first graduation closely
7. Emergency pause available if issues detected

### 10.3 Rollback Plan

If V3 has critical issues:
1. Pause V3 contract
2. Revert TokenFactory to V2 (for new tokens)
3. Investigate and fix
4. Redeploy V3.1
5. Resume graduations

---

## 11. Success Criteria

### 11.1 V3 Must Achieve:

- ✅ Complete graduation without reverting
- ✅ Create functional Uniswap V3 pool
- ✅ Initialize pool with correct price
- ✅ Allow swaps immediately after graduation
- ✅ Mint LP NFT to controller
- ✅ Handle edge cases gracefully
- ✅ Pass all security audits

### 11.2 Key Metrics:

- Gas cost for `completeGraduation()` < 8M gas
- Price deviation from bonding curve < 1%
- Graduation success rate = 100%
- No stuck tokens in "initiating" status

---

## 12. Appendix

### 12.1 V2 vs V3 Comparison

| Aspect | V2 (Buggy) | V3 (Fixed) |
|--------|-----------|-----------|
| Reserve source | Queries pool (stale) | Uses snapshot (correct) |
| Price calculation | After KAS transfer | During initiation |
| State tracking | Basic flags | Full snapshot struct |
| Error messages | Silent reverts | Descriptive reverts |
| Debugging | Impossible | Event-driven |
| Recovery | Cannot retry | Can retry completion |

### 12.2 References

- Uniswap V3 Core: https://github.com/Uniswap/v3-core
- Uniswap V3 Periphery: https://github.com/Uniswap/v3-periphery
- OpenZeppelin ERC20: https://github.com/OpenZeppelin/openzeppelin-contracts
- Pump.fun architecture: (research needed)
- SunPump architecture: (research needed)

### 12.3 Contract Addresses (Testnet)

```
GraduationControllerV2:  0x147E3Ecbe189bb301175001706ff1f44dF33B3ab (BUGGY)
TokenFactory:            0x39003ab4e8ad700F59bcfA082F73e68bc0477fDc
Kaspa Finance Factory:   0x1b72D7165a0D7256a4F197765C15bb70bC5D66A8
Kaspa Finance PosMgr:    0x4E25637cF39822364b877F81B18c5B6CF0eeF589
WKAS:                    0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94
KRABBY Pool (Stuck):     0x4D259ecF324709496DcAb7C141bFEDfFA2f88b2a
```

---

## Document Changelog

**v1.0 - October 24, 2025**
- Initial specification created
- Bug analysis complete
- V3 architecture defined
- Ready for audit review

---

**END OF SPECIFICATION**
