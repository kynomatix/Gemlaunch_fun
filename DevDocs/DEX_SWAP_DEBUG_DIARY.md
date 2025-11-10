# DEX Swap Debugging Diary

## Gemlaunch.fun Trading System Overview (For Kaspa Finance Devs)

### Pre-Graduation Trading (Bonding Curve Phase)

**How It Works:**
- Tokens launch with a **custom bonding curve pool** (our smart contract: `BondingCurvePool.sol`)
- Users trade KAS ↔ Tokens directly through our bonding curve
- All trades happen **on-chain via our contract**, not Kaspa Finance
- **Liquidity:** Virtual reserves (starts at ~1000 KAS virtual reserve)
- **Price discovery:** Determined by bonding curve formula (constant product)
- **Transaction signing:** Backend oracle wallet OR user's MetaMask
  - Buy: User sends KAS → receives tokens
  - Sell: User sends tokens → receives KAS

**Gas Handling (Pre-Graduation):**
```python
# Backend builds and signs transactions
{
    'gasPrice': self.w3.eth.gas_price,  # Legacy type-0 transactions
    'gas': estimated_gas_limit          # Explicitly calculated
}
```

**Market Cap Tracking:**
- Market cap calculated from bonding curve reserves
- Graduation threshold: **$50 USD market cap**
- When market cap hits $50, token is eligible for graduation

---

### Graduation Process (Transition to DEX)

**Automated 2-Step Process:**

**Step 1: Migrate Liquidity**
- Backend calls `GraduationController.initiateMigration(poolAddress)`
- Moves all KAS + tokens from bonding curve to DEX
- Creates **Kaspa Finance pool** (Uniswap V3 architecture)
- Pool configuration:
  - Fee tier: **0.25% (2500 basis points)**
  - Range: **Full range liquidity** (tick range: MIN_TICK to MAX_TICK)
  - Initial liquidity: All tokens + KAS from bonding curve (~10 KAS typical)

**Step 2: Complete Graduation**
- Backend calls `GraduationController.completeMigration(poolAddress)`
- Bonding curve permanently disabled
- Token lifecycle state changes: `active` → `graduated`
- All future trades route through **Kaspa Finance DEX**

---

### Post-Graduation Trading (DEX Phase)

**How It Works:**
- All trades go through **Kaspa Finance SwapRouter** (your contracts!)
- Users trade in **THE EXACT POOL WE CREATED** during graduation
  - Pool address stored in our DB: `token.dex_pool_address`
  - We query YOUR pool for quotes, prices, and liquidity
  - We route trades through YOUR SwapRouter to this specific pool
- **Liquidity:** Real concentrated liquidity (full range position we created)
- **Price discovery:** Kaspa Finance AMM pricing (your math)
- **Transaction signing:** User's MetaMask ONLY (no backend involvement)

**Critical Detail:**
We DON'T create our own trading mechanism post-graduation. When a token graduates, we:
1. Create a pool on YOUR DEX (via PoolManager/NonfungiblePositionManager)
2. Store the pool address: `0x1Bc9e2F8a3f1e89D741333CC85847e2C34F5E44D` (example)
3. ALL future trades route through YOUR SwapRouter → YOUR pool
4. We're essentially a **frontend for your DEX** after graduation

**Our Integration with Kaspa Finance:**

**BUY Flow (KAS → Token):**
```javascript
// 1. Get quote from your QuoterV2
const quote = await quoter.quoteExactInput(path, kasAmount);

// 2. Build multicall transaction
const tx = swapRouter.multicall(deadline, [
    exactInput({
        path: encode_path([WKAS, token], [2500]),
        recipient: userAddress,
        deadline: deadline,
        amountIn: kasAmount,
        amountOutMinimum: minTokensOut  // Slippage protection
    }),
    refundETH()  // Return excess KAS
]);

// 3. User signs via MetaMask
// 4. Transaction broadcasts to Kasplex L2
```

**SELL Flow (Token → KAS):**
```javascript
// 1. User approves SwapRouter to spend tokens
await token.approve(swapRouterAddress, tokenAmount);

// 2. Build exactInputSingle transaction
const tx = swapRouter.exactInputSingle({
    tokenIn: tokenAddress,
    tokenOut: WKAS,
    fee: 2500,  // 0.25% tier
    recipient: userAddress,
    deadline: deadline,
    amountIn: tokenAmount,
    amountOutMinimum: minKasOut,
    sqrtPriceLimitX96: 0  // No price limit
});

// 3. User signs via MetaMask
// 4. Transaction broadcasts to Kasplex L2
```

**Key Differences from Bonding Curve:**
1. **No backend signing** - User MetaMask signs everything
2. **EIP-1559 or Legacy gas** - MetaMask calculates fees (we don't set them)
3. **Slippage requirements** - Thin liquidity needs 2-8% slippage minimum
4. **Approval required** - Selling requires ERC20 approval first
5. **Gas estimation** - MetaMask auto-estimates (we DON'T hardcode gas limits)

---

### Critical Parameters

**Pool Configuration (Created During Graduation):**
- SwapRouter: `0xDf88D478aF51C0AB616aFBfDD933c874e142858c`
- WKAS: `0xd18fCD278F7156daA2a506dBc2A4a15337B91B94`
- Fee Tier: `2500` (0.25%)
- Tick Spacing: `50`
- Initial Liquidity: ~10 KAS + proportional tokens

**Transaction Requirements:**
- Chain ID: `167012` (Kasplex zkEVM Testnet)
- Gas Mode: Legacy (`gasPrice`) OR EIP-1559 (both work)
- Slippage: **Minimum 2%** for graduated tokens (thin liquidity)
- Deadline: 5 minutes from current timestamp

---

### Common Issues (For Debugging)

**Issue 1: "Execution Reverted"**
- **Cause:** Slippage too low for thin post-graduation liquidity
- **Solution:** Use 5-8% slippage minimum for graduated tokens

**Issue 2: "Insufficient Allowance"**
- **Cause:** User hasn't approved SwapRouter to spend tokens
- **Solution:** Call `token.approve(swapRouter, amount)` before sell

**Issue 3: "Transaction Pending Forever"**
- **Cause:** Hardcoded gas limit OR wrong gas pricing
- **Solution:** Let MetaMask auto-estimate gas, don't set `gas` field

**Issue 4: Pool Not Found**
- **Cause:** Token hasn't graduated yet OR wrong fee tier
- **Solution:** Check `token.graduation_status == 'graduated'` and use fee tier 2500

---

## Problem Statement
DEX swaps on Kaspa Finance are not reaching the blockchain. Transactions generate local hashes in MetaMask but never appear on chain.

## Key Facts
- **User's stuck nonce**: 325 (0x145) - 20 transactions pending
- **Kaspa Finance swaps work fine** when done directly on their site
- **Chain**: Kasplex zkEVM testnet (Chain ID: 167012)
- **Router**: 0xDf88D478aF51C0AB616aFBfDD933c874e142858c

## KASPA FINANCE SWAPROUTER ABI (attached_assets/SwapRouter_1762263429508.json)
**CRITICAL: Always reference this - stop misreading it!**

### Key Functions:
1. **multicall**: `multicall(bytes[] data)` - NO DEADLINE PARAMETER!
   - Input: Array of encoded function calls
   - Payable: YES
   - Returns: `bytes[] results`

2. **exactInputSingle**: For single-hop swaps
   - Input: ExactInputSingleParams struct (8 fields)
   - Payable: YES
   - Returns: `uint256 amountOut`

3. **refundETH**: Returns excess ETH/KAS to caller
   - No inputs
   - Payable: YES
   - No return value

### Correct Usage Pattern:
```javascript
// Build individual calls
exactInputSingle_call = encode_exactInputSingle(params)
refundETH_call = encode_refundETH()

// Use multicall(bytes[]) - NOT multicall(uint256, bytes[])
multicall_data = swaprouter.functions.multicall([
    exactInputSingle_call,
    refundETH_call
])._encode_transaction_data()
```

**DO NOT manually encode multicall with deadline - that signature doesn't exist!**

---

## ROOT CAUSE IDENTIFIED (Nov 5, 2025)

**Problem**: DEX swaps showed "0 KAS gas fee" in MetaMask and never reached blockchain.

**Root Cause**: We were letting MetaMask "auto-calculate" gas, which caused issues with our transaction structure.

**Why Bonding Curve Works**: Bonding curve explicitly sets:
```python
'gasPrice': self.w3.eth.gas_price  # Legacy type-0 transaction
```

**Note**: Kasplex supports BOTH legacy (gasPrice) and EIP-1559 (maxFeePerGas) transactions. We use legacy mode for consistency with bonding curve.

**Applied to**: `build_dex_buy_tx()` and `build_dex_sell_tx()` in services/web3_service.py

---

## What We Know Works (from Kaspa Finance)
```
Function: multicall(uint256 deadline, bytes[] data)
Param 1: deadline (timestamp like 1762302312)
Param 2: Array of encoded function calls
- Shows actual network fees (0.8615 KAS)
- Uses function selector 0xac9650d8
```

## Our Current Issues

### Issue 1: Wrong multicall signature in our ABI
- **Our ABI has**: `multicall(bytes[] data)` - NO deadline parameter
- **KF actually uses**: `multicall(uint256 deadline, bytes[] data)` - deadline FIRST
- **Status**: Manually encoding the correct signature

### Issue 2: Gas Parameters (OUTDATED)
- This was based on incorrect assumption that Kasplex requires EIP-1559
- **TRUTH**: Kasplex supports BOTH legacy (gasPrice) AND EIP-1559
- **Our choice**: Use legacy gasPrice for all transactions
- **Status**: Not an actual issue

### Issue 3: Gas Limits
- MetaMask estimates 10.5M gas (way too high)
- Should be 350k for DEX swaps
- **Status**: Fixed - hardcoded 350k

### Issue 4: Encoding Error 
- Error: "Value of type <class 'str'> cannot be encoded by ByteStringEncoder"
- Cause: Passing hex strings to eth_abi.encode instead of bytes
- **Status**: FIXED - converting hex to bytes with bytes.fromhex()

### Issue 5: Double 0x Prefix 
- Error: "Cannot convert string to Uint8Array. toBytes only supports 0x-prefixed hex strings"
- Cause: Adding 0x prefix when multicall_encoded already had one
- **Status**: FIXED - removed double prefix

### Issue 6: Transactions Not Reaching Chain (CURRENT BLOCKER)
- **Symptom**: MetaMask accepts tx, returns hash, but tx never appears on blockchain
- **Evidence**: 
  - Hash 0xe5c7b0f9... returned by MetaMask
  - Not found on explorer: https://explorer.testnet.kasplextest.xyz
  - User has 20+ stuck pending transactions at nonce 325
- **Likely Causes**:
  1. Gas price too low (showing 0 KAS fee)
  2. Nonce conflict - need to clear stuck transactions
  3. RPC silently rejecting transactions

## Transaction Structure Comparison

### Kaspa Finance (WORKING):
```
multicall(
    1762302312,  // deadline as first param
    [
        "0xb858183f...", // unknown function (not in our ABI)
        ...
    ]
)
```

### Our Attempt (NOT WORKING):
```
multicall(
    [  // No deadline, just data array
        "0x5d76b977...", // exactInputSingle
        "0x12210e8a..."  // refundETH
    ]
)
```

## CRITICAL DISCOVERY
The problem is NOT our code - it's the Kasplex RPC/MetaMask interaction:
1. Our multicall structure is CORRECT (MetaMask decodes it properly)
2. Gas prices are set correctly (4000 GWEI)
3. BUT MetaMask shows "0 KAS total gas fee" - this is the red flag
4. Transactions get a hash but NEVER reach the blockchain

## ROOT CAUSE
Kasplex testnet is silently rejecting transactions from MetaMask even though they appear to be submitted. The "0 KAS fee" display indicates MetaMask can't properly calculate fees for Kasplex.

## SOLUTION
Since manual Kaspa Finance trades work, the issue is specific to our integration. Possible fixes:
1. Use a different wallet (not MetaMask) that better supports Kasplex
2. Submit transactions directly via RPC (bypass MetaMask)
3. Match EXACTLY what Kaspa Finance does (need to capture their raw transaction)

## Key Learning
The SwapRouter ABI we have doesn't match what's actually deployed. Kaspa Finance's router has additional functions/signatures we don't have documented.

---

## Nov 5, 2025 - CRITICAL DISCOVERY: Gas Pricing Difference

### Test Results
**Bonding Curve (WORKS):**
- Uses `gasPrice` (legacy EIP-1 gas pricing)
- Tx confirms on-chain in seconds ✅
- Example: 0xbf6cd7af... confirmed at nonce 326

**DEX Swaps (FAILS):**
- Was using `maxFeePerGas` + `maxPriorityFeePerGas` (EIP-1559)
- MetaMask shows correct fee in popup (0.9 KAS)
- After confirm: shows 0 KAS, stuck pending forever ❌
- Never reaches blockchain

### Code Comparison
```python
# Bonding Curve (services/web3_service.py line 1654)
'gasPrice': self.w3.eth.gas_price,  # Legacy - WORKS

# DEX (was using)
'maxFeePerGas': hex(2001_gwei),
'maxPriorityFeePerGas': hex(2001_gwei),  # EIP-1559 - FAILS
```

### Root Cause Hypothesis (INCORRECT)
This hypothesis was wrong. Kasplex supports both legacy and EIP-1559 transactions fine. The real issue was with our transaction structure and gas parameter handling.

### Fix Attempt #1 (Nov 5, 14:58 UTC)
**Change:** Switched DEX transactions to use legacy `gasPrice` (same as bonding curve)
```python
tx_data = {
    'gasPrice': hex(final_gas_price),  # Legacy pricing
    'nonce': self.w3.eth.get_transaction_count(user_address)
}
```

**Status:** ❌ FAILED - Backend sent gasPrice, but frontend ignored it!

**User Evidence (Nov 5, ~15:05 UTC):**
- MetaMask still shows "Total gas fee: 0 KAS"
- Max fee per gas: 0.000002001 KAS (correct value)
- Transaction stuck pending at nonce 327
- Browser console shows NO gas pricing log (should have shown gasPrice or EIP-1559)

### ROOT CAUSE FOUND (Nov 5, 15:10 UTC) ⚡
**The bug was in the FRONTEND, not the backend!**

**Frontend code (transaction_manager.js line 314-322):**
```javascript
// Include EIP-1559 gas params if backend provides them
if (txData.maxFeePerGas && txData.maxPriorityFeePerGas) {
    txParams.maxFeePerGas = txData.maxFeePerGas;
    txParams.maxPriorityFeePerGas = txData.maxPriorityFeePerGas;
}
// ❌ NO HANDLING FOR gasPrice - it was IGNORED!
```

**What happened:**
1. Backend correctly sends `gasPrice: '0x...'`
2. Frontend only checks for EIP-1559 params (maxFeePerGas/maxPriorityFeePerGas)
3. Since neither exists, frontend sends txParams WITHOUT any gas pricing
4. MetaMask calculates its own EIP-1559 values (broken on Kasplex)
5. Result: 0 KAS total fee, transaction stuck

### Fix Attempt #2 (Nov 5, 15:10 UTC)
**Change:** Frontend now properly includes `gasPrice` from backend
```javascript
// Include gas pricing params from backend
if (txData.gasPrice) {
    // Legacy gas pricing (like bonding curve)
    txParams.gasPrice = txData.gasPrice;
    console.log('✅ DEX TX: Using backend legacy gas price:', txData.gasPrice);
} else if (txData.maxFeePerGas && txData.maxPriorityFeePerGas) {
    // EIP-1559 gas pricing
    txParams.maxFeePerGas = txData.maxFeePerGas;
    txParams.maxPriorityFeePerGas = txData.maxPriorityFeePerGas;
}
```

**Status:** ❌ FAILED - MetaMask still shows 0 KAS fee!

**User Evidence (Nov 5, ~15:15 UTC):**
- Browser console shows: `"✅ DEX TX: Using backend legacy gas price: 0x1d1e4e4ea00"` ✅
- Frontend IS passing gasPrice to MetaMask
- But MetaMask STILL shows: "Total gas fee: 0 KAS" ❌
- Transaction stuck pending at nonce 328

### THE ACTUAL ROOT CAUSE (Nov 5, 15:20 UTC) 🎯

**MetaMask REJECTS all gas pricing params on Kasplex!**

Discovery process:
1. **Bonding curve (WORKS):**
   - Backend sends `gasPrice`
   - OLD frontend ignored it (didn't check for gasPrice)
   - MetaMask got NO gas params
   - MetaMask AUTO-CALCULATED gas → SUCCESS ✅

2. **DEX with my "fix" (FAILS):**
   - Backend sends `gasPrice`
   - NEW frontend includes it
   - MetaMask gets `gasPrice` param
   - MetaMask converts to broken EIP-1559 → 0 KAS fee ❌

**Conclusion:** MetaMask's auto-calculation works perfectly, but providing ANY gas param (gasPrice OR EIP-1559) causes it to fail!

### Fix Attempt #3 (Nov 5, 15:20 UTC) - THE REAL FIX
**Change:** Remove ALL gas pricing params from backend - let MetaMask auto-calculate

**Backend (services/web3_service.py):**
```python
tx_data = {
    'from': user_address,
    'to': swap_router.address,
    'value': hex(kas_amount),
    'data': multicall_encoded,
    'gas': hex(450000)
    # NO gasPrice, NO maxFeePerGas - MetaMask will auto-calculate
}
```

**Frontend:** Will pass tx_data as-is (no gas params), letting MetaMask handle everything

**Expected Result:**
- MetaMask auto-calculates gas fees (like bonding curve)
- Shows proper fee in confirmation popup
- Transaction confirms on-chain ✅

**Status:** DEPLOYED - User needs to test

### Notes
- Pool detection via QuoterV2 was added but unrelated to core issue
- Both bonding curve and DEX use same submission method (MetaMask eth_sendTransaction)
- The ONLY difference that matters: gas pricing format
- **CRITICAL**: On Kasplex, MetaMask's auto-calculation works, but ANY explicit gas param fails!
- **LESSON LEARNED**: Always test what the working code is ACTUALLY doing, not what we think it should do!

---

## Nov 5, 2025 - ACTUAL ROOT CAUSE FOUND 🎯

### The Real Problem (After Testing Kaspa Finance Directly)

**User tested Kaspa Finance directly and discovered:**
1. ✅ **8% slippage = SUCCESS** (transaction confirmed!)
2. ❌ **1% slippage = FAILED** ("Execution reverted for an unknown reason")
3. ❌ **0.5% slippage = FAILED** (likely would fail)

**Kaspa Finance Transaction Details (SUCCESSFUL):**
```
Method: multicall(deadline, [exactInputSingle, refundETH])
Gas Limit: 200040 units
Gas Used: 149827 units
Base Fee: 2000 GWEI
Priority Fee: 1 GWEI
Total Gas: 0.299804 KAS
Transaction Type: EIP-1559 ✅
```

### Root Causes Identified

**1. SLIPPAGE TOO LOW** ⚡
- **Our ladder**: Started at 50 bps (0.5%) for all trades
- **DEX reality**: Thin liquidity post-graduation needs 2-8% minimum
- **Why**: Only 10 KAS liquidity after graduation → high price impact (0.97% shown in Kaspa Finance)
- **Fix**: Separate slippage ladders
  - Bonding curve: 0.5% → 1% → 2% → 5% → 7.5% → 10%
  - DEX: 2% → 5% → 8% → 10% → 15%

**2. GAS HANDLING** (NOT THE ROOT CAUSE)
- **Our approach**: Legacy transactions (`gasPrice`)
- **Kaspa Finance**: Can use either legacy or EIP-1559
- **Kasplex support**: BOTH types work equally well
- **Our choice**: Stick with legacy gasPrice for consistency
- **Note**: This was NOT the root cause of swap failures

### Updated Code (Nov 5, 15:35 UTC)

**Backend (services/web3_service.py):**
```python
# Use EIP-1559 (same as Kaspa Finance)
base_fee = self.w3.eth.gas_price

tx_data = {
    'from': user_address,
    'to': swap_router.address,
    'value': hex(kas_amount),
    'data': multicall_data,
    'gas': hex(450000),
    'maxFeePerGas': hex(base_fee),
    'maxPriorityFeePerGas': hex(1000000000)  # 1 gwei priority
}
```

**Frontend (transaction_manager.js):**
```javascript
// DEX tokens need higher slippage due to thin liquidity
const slippageLadder = isGraduated 
    ? [200, 500, 800, 1000, 1500]  // DEX: Start at 2%, max 15%
    : [50, 100, 200, 500, 750, 1000];  // Bonding curve: 0.5%
```

### Why This Fixes It

1. **First attempt starts at 2% slippage** - likely to succeed immediately
2. **Auto-retries at 5%, 8%** - matches what worked for user on Kaspa Finance
3. **EIP-1559 format** - matches Kaspa Finance's working implementation
4. **MetaMask will show proper fees** - base + priority fee calculation

**Status:** ❌ STILL FAILED - Transactions showing "0 KAS fee" despite optimal slippage

---

## Nov 5, 2025 - FINAL ROOT CAUSE: Hardcoded Gas Limits 🎯

### The Discovery

**User comparison of successful vs failed transactions:**

**Kaspa Finance (SUCCESS):**
```
Gas limit: 199,995 (MetaMask auto-estimated)
Gas used: 149,787
Total gas fee: 0.299724 KAS
Status: Confirmed ✅
```

**Our Platform (FAILED):**
```
Gas limit: 450,000 (hardcoded by us)
Total gas fee: 0 KAS
Status: Stuck pending ❌
```

### The Real Problem

We were hardcoding `gas: 450000` in our transaction data. When MetaMask receives a transaction with a **hardcoded gas limit**, it skips its own gas estimation and shows "0 KAS fee" if the call would revert.

**Why Kaspa Finance works:**
- They send transaction WITHOUT gas limit field
- MetaMask runs `eth_estimateGas` simulation
- Simulation succeeds (with proper slippage)
- MetaMask shows actual fee (~0.3 KAS)
- Transaction broadcasts successfully

**Why ours failed:**
- We forced `gas: 450000`
- MetaMask accepts the limit without simulation
- Transaction shows "0 KAS fee" 
- Gets stuck in pending forever

### The Complete Fix

**Backend (services/web3_service.py):**
```python
tx_data = {
    'from': user_address,
    'to': swap_router.address,
    'value': hex(kas_amount),
    'data': multicall_data,
    # NO gas limit - let MetaMask estimate ✅
    'maxFeePerGas': hex(base_fee),
    'maxPriorityFeePerGas': hex(1000000000)
}
```

**Frontend (transaction_manager.js):**
```javascript
// Dynamic slippage based on price impact
const priceImpactPct = quote.price_impact_pct || 0;
const calculatedSlippage = Math.max(priceImpactPct * 100 + 100, 500); // +1% buffer, min 5%
```

### Why BOTH Changes Were Needed

1. **Dynamic Slippage** - Ensures the swap won't revert during MetaMask's simulation
2. **No Gas Limit** - Allows MetaMask to run simulation and estimate gas properly

**Without both fixes:**
- Low slippage → MetaMask simulation reverts → can't estimate gas
- Hardcoded gas → MetaMask skips simulation → shows "0 KAS fee"

### Final Status

**Deployed:** Nov 5, 2025 16:42 UTC
**Testing:** User needs to test with hard refresh

**Expected behavior:**
- 1 KAS trade: ~5% slippage (0.19% impact + 1% buffer vs 5% minimum)
- Gas: ~200k auto-estimated by MetaMask
- Fee: ~0.3-0.4 KAS displayed properly
- Transaction: Confirms in seconds ✅