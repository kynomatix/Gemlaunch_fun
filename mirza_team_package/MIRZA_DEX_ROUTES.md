# DEX Swap Routes - Post-Graduation Trading

This document outlines the API routes and implementation for trading graduated tokens on Kaspa Finance DEX.

## API Endpoints

All routes are defined in `app.py`:

### 1. DEX Quote (Price Discovery)
**Route:** `POST /api/dex/quote`  
**Location:** `app.py` lines 5882-6023  
**Purpose:** Get price quotes for buying/selling graduated tokens

**Request:**
```json
{
  "token_address": "0x...",
  "side": "buy" | "sell",
  "amount_in": "10.5",
  "slippage_bps": 50,
  "fee_tier": 3000
}
```

**Response:**
```json
{
  "success": true,
  "amount_out": "1234.56",
  "execution_price": "0.045",
  "price_impact_pct": 0.5,
  "gas_estimate": "150000",
  "fee_tier": 3000
}
```

---

### 2. DEX Buy Transaction Builder
**Route:** `POST /api/dex/buy`  
**Location:** `app.py` lines 6025-6135  
**Purpose:** Build transaction data for buying graduated tokens with KAS

**Request:**
```json
{
  "token_address": "0x...",
  "kas_amount": "10.5",
  "min_tokens_out": "1000000",
  "deadline": 1234567890,
  "user_address": "0x..."
}
```

**Response:**
```json
{
  "success": true,
  "tx_data": {
    "from": "0x...",
    "to": "0x...",
    "value": "0x...",
    "data": "0x...",
    "gasPrice": "0x..."
  },
  "requires_approval": false
}
```

---

### 3. DEX Sell Transaction Builder
**Route:** `POST /api/dex/sell`  
**Location:** `app.py` lines 6137-6262  
**Purpose:** Build transaction data for selling graduated tokens for KAS

**Request:**
```json
{
  "token_address": "0x...",
  "token_amount": "1000000",
  "min_kas_out": "10.5",
  "deadline": 1234567890,
  "user_address": "0x...",
  "unwrap_wkas": true
}
```

**Response:**
```json
{
  "success": true,
  "tx_data": {
    "from": "0x...",
    "to": "0x...",
    "value": "0x0",
    "data": "0x...",
    "gasPrice": "0x..."
  },
  "requires_approval": true,
  "approval_address": "0x...",
  "unwrap_tx": {...}
}
```

---

## Backend Implementation

### Web3 Service Layer
**File:** `services/web3_service.py`

**Key Functions:**
- `build_dex_buy_tx()` - Builds buy transaction using Kaspa Finance SwapRouter
- `build_dex_sell_tx()` - Builds sell transaction using Kaspa Finance SwapRouter
- `get_dex_quote()` - Fetches price quotes from QuoterV2

### Contract Addresses
**File:** `contracts/deployed_addresses.json`

```json
{
  "externalContracts": {
    "KaspaFinance": {
      "Factory": "0x1b72D7165a0D7256a4F197765C15bb70bC5D66A8",
      "PositionManager": "0x4E25637cF39822364b877F81B18c5B6CF0eeF589",
      "WKAS": "0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94",
      "SwapRouter": "0xDf88D478aF51C0AB616aFBfDD933c874e142858c",
      "QuoterV2": "0x3ACc31F8fe86E365604eAa6dDCbcB7fEba7a4c2B"
    }
  }
}
```

---

## Critical Gas Configuration

**⚠️ IMPORTANT: Kasplex-Specific Gas Rules**

DEX swaps on Kasplex zkEVM use **LEGACY GAS MODE ONLY**:

```javascript
// Transaction structure returned
{
  from: "0x...",
  to: "0x...",
  value: "0x...",
  data: "0x...",
  gasPrice: w3.eth.gas_price  // LEGACY MODE
}
```

**DO NOT USE:**
- ❌ `maxFeePerGas`
- ❌ `maxPriorityFeePerGas`
- ❌ Gas estimation on DEX swaps (fails on Kasplex)
- ❌ Gas limits (let MetaMask handle it)

**Reference Implementation:**
- `services/web3_service.py` lines 1628-1673 (bonding curve pattern)

---

## Transaction Flow

### Buy Flow
1. User requests quote via `/api/dex/quote` (side: "buy")
2. Frontend displays quote to user
3. User confirms → call `/api/dex/buy` with quote params
4. Backend builds transaction using SwapRouter
5. Frontend signs & submits via MetaMask
6. Monitor transaction status via `/api/tx/<hash>/status`

### Sell Flow
1. User requests quote via `/api/dex/quote` (side: "sell")
2. Frontend displays quote to user
3. User confirms → call `/api/dex/sell` with quote params
4. Backend checks if token approval needed
5. If needed: Frontend requests approval first
6. Frontend signs & submits sell transaction via MetaMask
7. Monitor transaction status via `/api/tx/<hash>/status`

---

## Frontend Integration

**File:** `static/js/transaction_manager.js`

The Transaction Manager orchestrates all DEX swap transactions on the frontend, handling:
- Quote requests
- Transaction building
- Wallet signing
- Transaction monitoring
- Error handling

---

## Network Configuration

- **Network:** Kasplex zkEVM L2 Testnet
- **Chain ID:** 167012 (0x28c64)
- **RPC:** https://rpc.kasplextest.xyz
- **Block Explorer:** https://explorer.kasplextest.xyz

---

## For Mirza's Team

All code is available in the GitHub repository. Key files to inspect:

1. **Backend Routes:** `app.py` (lines 5882-6262)
2. **Web3 Implementation:** `services/web3_service.py`
3. **Contract Addresses:** `contracts/deployed_addresses.json`
4. **Frontend Logic:** `static/js/transaction_manager.js`

The DEX swap implementation follows the same pattern as bonding curve trades but uses Kaspa Finance's Uniswap V3 architecture (SwapRouter, QuoterV2).
