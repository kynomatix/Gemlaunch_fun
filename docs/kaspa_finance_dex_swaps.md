# Kaspa Finance DEX Swap Implementation

## Contract Addresses (Kasplex Testnet)

| Contract | Address |
|----------|---------|
| Factory | `0x1b72D7165a0D7256a4F197765C15bb70bC5D66A8` |
| SwapRouter | `0xDf88D478aF51C0AB616aFBfDD933c874e142858c` |
| QuoterV2 | `0xE0EE9e756CB67f49326DCEf98e24e1231F26Ce70` |
| WKAS | `0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94` |
| NFTPositionManager | `0x4E25637cF39822364b877F81B18c5B6CF0eeF589` |

## The Pattern (SwapRouter02 Style)

Kaspa Finance uses a **hybrid SwapRouter** that differs from standard Uniswap V3:

1. **Outer wrapper**: `multicall(uint256 deadline, bytes[] data)` - selector `0x5ae401dc`
2. **Inner function**: `exactInput` with a struct that does NOT include deadline (deadline is in outer multicall)

## Function Selectors

| Function | Selector |
|----------|----------|
| `multicall(uint256,bytes[])` | `0x5ae401dc` |
| `exactInput((bytes,address,uint256,uint256))` | `0xb858183f` |
| `unwrapWETH9(uint256,address)` | `0x49404b7c` |
| `refundETH()` | `0x12210e8a` |

## Fee Tiers

| Fee | Value |
|-----|-------|
| 0.05% | `500` |
| 0.25% | `2500` |
| 0.30% | `3000` |
| 1.00% | `10000` |

---

## Buy Transaction (Native KAS → Token)

```python
from eth_abi.abi import encode

# 1. Build path: WKAS(20 bytes) + fee(3 bytes) + Token(20 bytes)
path = bytes.fromhex(wkas_address[2:]) + fee_tier.to_bytes(3, 'big') + bytes.fromhex(token_address[2:])

# 2. Encode exactInput - struct has NO deadline field
# Selector: 0xb858183f
# Struct: (bytes path, address recipient, uint256 amountIn, uint256 amountOutMinimum)
exact_input_selector = bytes.fromhex('b858183f')
exact_input_encoded = encode(
    ['(bytes,address,uint256,uint256)'],
    [(path, user_address, kas_amount, min_tokens_out)]
)
inner_calldata = exact_input_selector + exact_input_encoded

# 3. Wrap in multicall(uint256 deadline, bytes[] data) - selector 0x5ae401dc
multicall_selector = bytes.fromhex('5ae401dc')
multicall_encoded = encode(
    ['uint256', 'bytes[]'],
    [deadline, [inner_calldata]]
)
final_calldata = '0x' + (multicall_selector + multicall_encoded).hex()

# 4. Build transaction - MUST send native KAS as value
tx = {
    'from': user_address,
    'to': '0xDf88D478aF51C0AB616aFBfDD933c874e142858c',  # SwapRouter
    'value': hex(kas_amount),  # Router wraps this to WKAS
    'data': final_calldata,
    'gasPrice': hex(gas_price)  # LEGACY gas mode only
}
```

---

## Sell Transaction (Token → Native KAS)

Uses multicall with TWO inner calls: `exactInput` + `unwrapWETH9`

```python
from eth_abi.abi import encode

# 1. Build path: Token → WKAS (reversed)
path = bytes.fromhex(token_address[2:]) + fee_tier.to_bytes(3, 'big') + bytes.fromhex(wkas_address[2:])

# 2. exactInput - recipient is SwapRouter (not user) so we can unwrap after
exact_input_encoded = encode(
    ['(bytes,address,uint256,uint256)'],
    [(path, swap_router_address, token_amount, min_kas_out)]  # Note: recipient = router
)
inner_calldata_1 = bytes.fromhex('b858183f') + exact_input_encoded

# 3. unwrapWETH9(uint256 amountMinimum, address recipient)
# Uses web3.py contract encoder (swap_router is the loaded contract)
unwrap_hex = swap_router.functions.unwrapWETH9(min_kas_out, user_address)._encode_transaction_data()
inner_calldata_2 = bytes.fromhex(unwrap_hex[2:])

# 4. Wrap BOTH in multicall
multicall_encoded = encode(
    ['uint256', 'bytes[]'],
    [deadline, [inner_calldata_1, inner_calldata_2]]
)
final_calldata = '0x' + (bytes.fromhex('5ae401dc') + multicall_encoded).hex()

# 5. Build transaction - NO value for sells (user sends tokens, not KAS)
tx = {
    'from': user_address,
    'to': '0xDf88D478aF51C0AB616aFBfDD933c874e142858c',
    'value': '0x0',
    'data': final_calldata,
    'gasPrice': hex(gas_price)
}
```

---

## Critical Implementation Notes

1. **LEGACY gas mode only** - Never use EIP-1559 (`maxFeePerGas`/`maxPriorityFeePerGas`) on Kasplex
2. **No gas estimation for DEX swaps** - Just send `{from, to, value, data, gasPrice}` - let MetaMask estimate
3. **Sells require prior approval** - User must approve SwapRouter to spend their tokens first
4. **Deadline in outer multicall** - The `exactInput` struct does NOT include deadline (unlike standard Uniswap V3 ISwapRouter)

## Path Encoding

The path is packed bytes: `tokenIn(20) + fee(3) + tokenOut(20)`

For multi-hop: `tokenA(20) + feeAB(3) + tokenB(20) + feeBC(3) + tokenC(20)`

## Swap Event (PancakeSwap V3 Style)

Kaspa Finance emits PancakeSwap V3 style Swap events, NOT standard Uniswap V3:

```
Swap(address sender, address recipient, int256 amount0, int256 amount1, uint160 sqrtPriceX96, uint128 liquidity, int24 tick, uint128 protocolFeesToken0, uint128 protocolFeesToken1)
```

Event signature hash: `0x19b47279256b2a23a1665c810c8d55a1758940ee09377d4f8d26497a3577dc83`
