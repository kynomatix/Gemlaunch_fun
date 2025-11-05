# Kaspa Finance DEX Integration Issue

## Problem
Multicall transactions to SwapRouter fail with "0 KAS gas fee" in MetaMask on Kasplex Testnet, while simple contract calls work fine.

## Environment
- **Chain:** Kasplex zkEVM Testnet (Chain ID: 167012)
- **SwapRouter:** 0xDf88D478aF51C0AB616aFBfDD933c874e142858c
- **WKAS:** 0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94
- **Pool:** 0x1Bc9e2F8a3f1e89D741333CC85847e2C34F5E44D (MEGA/WKAS 0.25%)
- **Token:** 0xe9c2F32816054c87Ab04b7eb57Cce657EA1aDe76 (MEGA)

## What Works
- Bonding curve trades (simple contract calls) work perfectly
- User's wallet has funds (3365 KAS balance)
- Direct Kaspa Finance UI works fine

## What Fails
- Our multicall transactions to SwapRouter
- MetaMask shows "Total gas fee: 0 KAS"
- Transaction gets stuck pending and never confirms

## Transaction Data We're Sending

**Function:** `multicall(uint256 deadline, bytes[] data)`

**Multicall Parameters:**
- Param 1 (deadline): Current timestamp + 300 seconds
- Param 2 (data array):
  - Item 1: `exactInputSingle` encoded call
  - Item 2: `refundETH` encoded call

**ExactInputSingle params:**
```
tokenIn: WKAS (0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94)
tokenOut: MEGA (0xe9c2F32816054c87Ab04b7eb57Cce657EA1aDe76)
fee: 2500 (0.25%)
recipient: user_address
deadline: timestamp
amountIn: 10 KAS (10000000000000000000 wei)
amountOutMinimum: calculated with 0.5% slippage
sqrtPriceLimitX96: 0
```

**Gas params sent to MetaMask:**
```javascript
{
    from: user_address,
    to: SwapRouter,
    value: '0x8ac7230489e80000',  // 10 KAS
    data: multicall_encoded,
    gas: '0x6ddd0'  // 450,000
    // NO gasPrice, NO maxFeePerGas - let MetaMask auto-calculate
}
```

## Example Transaction That Failed
- **Nonce:** 328
- **MetaMask shows:** "Max fee per gas: 0.000002001 KAS, Total gas fee: 0 KAS"
- **Status:** Stuck pending forever

## Code Files

### Backend: Building the multicall transaction
**File:** `services/web3_service.py` - function `build_dex_buy_tx()`

**Key code:**
```python
# Encode exactInputSingle
exact_input_params = (
    wkas_address,           # tokenIn (WKAS)
    token_address,          # tokenOut (Token)
    fee_tier,               # fee (2500 = 0.25%)
    user_address,           # recipient
    deadline,               # deadline
    kas_amount,             # amountIn
    min_tokens_out,         # amountOutMinimum
    0                       # sqrtPriceLimitX96
)
exact_input_encoded = swap_router.functions.exactInputSingle(exact_input_params)._encode_transaction_data()

# Encode refundETH
refund_eth_encoded = swap_router.functions.refundETH()._encode_transaction_data()

# Manually encode multicall(uint256 deadline, bytes[] data)
from eth_abi import encode
multicall_selector = Web3.keccak(text="multicall(uint256,bytes[])")[:4]
exact_input_bytes = bytes.fromhex(exact_input_encoded[2:])
refund_eth_bytes = bytes.fromhex(refund_eth_encoded[2:])

encoded_params = encode(
    ['uint256', 'bytes[]'],
    [deadline, [exact_input_bytes, refund_eth_bytes]]
)

multicall_encoded = '0x' + multicall_selector.hex() + encoded_params.hex()

# Build transaction (NO gas pricing - let MetaMask handle it)
tx_data = {
    'from': user_address,
    'to': swap_router.address,
    'value': hex(kas_amount),
    'data': multicall_encoded,
    'gas': hex(450000)
}
```

### Frontend: Submitting to MetaMask
**File:** `static/js/transaction_manager.js` - function `_signWithMetaMask()`

```javascript
const txParams = {
    from: accounts[0],
    to: txData.to,
    value: txData.value || '0x0',
    data: txData.data
};

if (txData.gas) {
    txParams.gas = txData.gas;
}

// eth_sendTransaction signs AND submits to blockchain
const txHash = await provider.request({
    method: 'eth_sendTransaction',
    params: [txParams]
});
```

## Questions for Kaspa Finance Team

1. ~~Is our multicall encoding correct?~~ ✅ RESOLVED - Encoding was correct
2. ~~Do we need to include any special parameters for Kasplex?~~ ✅ RESOLVED - Standard EIP-1559
3. ~~How does your frontend submit multicall transactions to MetaMask?~~ ✅ RESOLVED - Without gas limit
4. ~~Are there any known issues with MetaMask on Kasplex for complex transactions?~~ ✅ RESOLVED - Works when gas auto-estimated
5. ~~What gas params do you send to MetaMask for DEX swaps?~~ ✅ RESOLVED - maxFeePerGas + maxPriorityFeePerGas only

---

## ✅ SOLUTION FOUND (Nov 5, 2025)

### Root Cause
We were hardcoding `gas: 450000` which prevented MetaMask from running gas estimation simulation. Combined with low slippage, this caused "0 KAS fee" display and stuck transactions.

### The Fix

**Backend (services/web3_service.py):**
```python
tx_data = {
    'from': user_address,
    'to': swap_router.address,
    'value': hex(kas_amount),
    'data': multicall_data,
    # NO gas field - let MetaMask auto-estimate (~200k)
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

### Why Both Changes Were Critical

1. **Dynamic Slippage** - Prevents revert during MetaMask's `eth_estimateGas` simulation
2. **No Gas Limit** - Allows MetaMask to run simulation and estimate gas properly

**Result:**
- Gas: ~200k (auto-estimated, vs our 450k hardcoded)
- Fee: ~0.3-0.4 KAS (displayed properly)
- Status: **Transactions confirming successfully** ✅

## Contact
Platform: gemlaunch.fun - memecoin launchpad on Kasplex L2
Goal: Integrate Kaspa Finance DEX for post-graduation trading
**Status:** Integration complete and working!
