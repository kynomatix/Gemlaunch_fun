# DEX Swap Debugging Diary

## Problem Statement
DEX swaps on Kaspa Finance are not reaching the blockchain. Transactions generate local hashes in MetaMask but never appear on chain.

## Key Facts
- **User's stuck nonce**: 325 (0x145) - 20 transactions pending
- **Kaspa Finance swaps work fine** when done directly on their site
- **Chain**: Kasplex zkEVM testnet (Chain ID: 167012)
- **Router**: 0xDf88D478aF51C0AB616aFBfDD933c874e142858c

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

### Issue 2: EIP-1559 Parameters
- Kasplex requires EIP-1559 (no legacy transactions)
- maxPriorityFeePerGas should be 0 (Kasplex doesn't support priority fees)
- **Status**: Fixed - setting priority fee to 0

### Issue 3: Gas Limits
- MetaMask estimates 10.5M gas (way too high)
- Should be 350k for DEX swaps
- **Status**: Fixed - hardcoded 350k

### Issue 4: Encoding Error (CURRENT)
- Error: "Value of type <class 'str'> cannot be encoded by ByteStringEncoder"
- Cause: Passing hex strings to eth_abi.encode instead of bytes
- **Status**: Just fixed - converting hex to bytes with bytes.fromhex()

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

## Next Steps
1. Test the latest fix (hex to bytes conversion)
2. If still fails, consider:
   - Finding the correct SwapRouter ABI from Kaspa Finance
   - Using a different function (not multicall)
   - Checking if we need the mysterious 0xb858183f function

## Key Learning
The SwapRouter ABI we have doesn't match what's actually deployed. Kaspa Finance's router has additional functions/signatures we don't have documented.