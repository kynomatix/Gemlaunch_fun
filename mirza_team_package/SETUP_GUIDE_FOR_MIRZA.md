# Local Setup Guide - Gemlaunch.fun

## Step 1: Install Dependencies

### Python Dependencies
```bash
pip install -r requirements.txt
```

### Node.js Dependencies
```bash
npm install
```

---

## Step 2: Database Setup

### Option A: PostgreSQL (Recommended - what production uses)

1. **Install PostgreSQL** (if not already installed)
   - macOS: `brew install postgresql`
   - Ubuntu: `sudo apt-get install postgresql postgresql-contrib`
   - Windows: Download from postgresql.org

2. **Create Database**
   ```bash
   psql -U postgres
   CREATE DATABASE gemlaunch_dev;
   \q
   ```

3. **Get Database URL**
   ```
   postgresql://postgres:password@localhost:5432/gemlaunch_dev
   ```

### Option B: Use Replit's Built-in Database
   - You can skip this and use Replit's provided DATABASE_URL if testing in Replit

---

## Step 3: Environment Variables

Create a `.env` file in the root directory:

```bash
# === REQUIRED FOR DEX SWAPS ===

# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/gemlaunch_dev

# Session Secret (generate random string)
SESSION_SECRET=your_random_secret_here_use_openssl_rand_base64_32

# Kasplex Testnet Configuration
TESTNET_RPC_URL=https://rpc.kasplextest.xyz
TESTNET_CHAIN_ID=167012
BLOCK_EXPLORER_URL=http://explorer.testnet.kasplextest.xyz

# Oracle Wallet (TESTNET ONLY)
DEPLOYER_ADDRESS=0xe281e4776FB5De20817D0bbC72B0C4b955565619
DEPLOYER_PRIVATE_KEY=your_private_key_here

# Treasury Addresses
PLATFORM_TREASURY=0xe281e4776FB5De20817D0bbC72B0C4b955565619
AIRDROP_TREASURY=0xe281e4776FB5De20817D0bbC72B0C4b955565619
GRADUATION_ORACLE=0xe281e4776FB5De20817D0bbC72B0C4b955565619

# Fee Distribution Wallets
PLATFORM_DEV_WALLET=0xe281e4776FB5De20817D0bbC72B0C4b955565619
BUYBACK_RESERVE_WALLET=0xe281e4776FB5De20817D0bbC72B0C4b955565619
KASPA_NETWORK_WALLET=0xe281e4776FB5De20817D0bbC72B0C4b955565619
COMMUNITY_REWARDS_WALLET=0xe281e4776FB5De20817D0bbC72B0C4b955565619

# === CRITICAL: Kaspa Finance DEX Addresses (Chain ID: 167012) ===
KASPA_FINANCE_FACTORY=0x1b72D7165a0D7256a4F197765C15bb70bC5D66A8
KASPA_FINANCE_NFT_POSITION_MANAGER=0x4E25637cF39822364b877F81B18c5B6CF0eeF589
KASPA_FINANCE_WKAS=0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94
KASPA_FINANCE_SWAP_ROUTER=0xDf88D478aF51C0AB616aFBfDD933c874e142858c
KASPA_FINANCE_QUOTER_V2=0x3ACc31F8fe86E365604eAa6dDCbcB7fEba7a4c2B

# === OPTIONAL (AI features, social integrations) ===
# OPENROUTER_API_KEY=your_key
# REPLICATE_API_TOKEN=your_token
# PINATA_JWT=your_jwt
# TWITTER_CLIENT_ID=your_client_id
# TWITTER_CLIENT_SECRET=your_secret
```

**IMPORTANT:** Replace `your_private_key_here` with a real testnet wallet private key that has KAS tokens.

---

## Step 4: Initialize Database

The database tables are created automatically when you first run the app:

```bash
python app.py
```

This will:
1. Connect to PostgreSQL using `DATABASE_URL`
2. Run `db.create_all()` (line 4129 in app.py)
3. Create all tables based on models in `models.py` and `models_extended.py`

**Tables Created:**
- Users, Tokens, Trades, Holdings, Positions
- TradeEvents (historical chart data)
- Achievements, UserAchievements
- ChatMessages, Polls, PollVotes
- Airdrops, AirdropRecipients
- And many more...

---

## Step 5: Run the Application

```bash
gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app
```

**Or just:**
```bash
python main.py
```

The app will run on: **http://localhost:5000**

---

## Step 6: Testing DEX Swaps (Post-Graduation)

### Prerequisites
1. **Graduated Token Required**: DEX swaps only work for tokens that have graduated (reached $50 market cap)
2. **MetaMask Wallet**: You need MetaMask connected to Kasplex Testnet
3. **Testnet KAS**: Get testnet KAS from faucet

### Network Setup in MetaMask

Add Kasplex Testnet to MetaMask:
- **Network Name:** Kasplex zkEVM Testnet
- **RPC URL:** https://rpc.kasplextest.xyz
- **Chain ID:** 167012
- **Currency Symbol:** KAS
- **Block Explorer:** https://explorer.kasplextest.xyz

### Testing DEX Buy

**API Endpoint:** `POST /api/dex/buy`

**Test with cURL:**
```bash
curl -X POST http://localhost:5000/api/dex/buy \
  -H "Content-Type: application/json" \
  -d '{
    "token_address": "0xYOUR_GRADUATED_TOKEN_ADDRESS",
    "kas_amount": "1.0",
    "min_tokens_out": "1000000",
    "deadline": 9999999999,
    "user_address": "0xYOUR_WALLET_ADDRESS"
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "tx_data": {
    "from": "0x...",
    "to": "0xDf88D478aF51C0AB616aFBfDD933c874e142858c",
    "value": "0x...",
    "data": "0x...",
    "gasPrice": "0x..."
  },
  "requires_approval": false
}
```

### Testing DEX Sell

**API Endpoint:** `POST /api/dex/sell`

**Test with cURL:**
```bash
curl -X POST http://localhost:5000/api/dex/sell \
  -H "Content-Type: application/json" \
  -d '{
    "token_address": "0xYOUR_GRADUATED_TOKEN_ADDRESS",
    "token_amount": "1000000",
    "min_kas_out": "0.5",
    "deadline": 9999999999,
    "user_address": "0xYOUR_WALLET_ADDRESS",
    "unwrap_wkas": true
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "tx_data": {
    "from": "0x...",
    "to": "0xDf88D478aF51C0AB616aFBfDD933c874e142858c",
    "value": "0x0",
    "data": "0x...",
    "gasPrice": "0x..."
  },
  "requires_approval": true,
  "approval_address": "0xYOUR_TOKEN_ADDRESS"
}
```

### Testing Price Quotes

**API Endpoint:** `POST /api/dex/quote`

```bash
curl -X POST http://localhost:5000/api/dex/quote \
  -H "Content-Type: application/json" \
  -d '{
    "token_address": "0xYOUR_GRADUATED_TOKEN_ADDRESS",
    "side": "buy",
    "amount_in": "1.0",
    "slippage_bps": 50,
    "fee_tier": 3000
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "amount_out": "1234.56",
  "execution_price": "0.00081",
  "price_impact_pct": 0.5,
  "gas_estimate": "150000",
  "fee_tier": 3000
}
```

---

## Step 7: Database Schema

### Key Tables for DEX Testing

**Token Table:**
- `contract_address` - The token's EVM address
- `has_graduated` - Boolean (must be True for DEX swaps)
- `graduation_status` - Must be "completed"
- `dex_pool_address` - Uniswap V3 pool address (set after graduation)

**TradeEvent Table:**
- Stores all trades (bonding curve + DEX)
- Used for historical chart data
- Auto-populated by blockchain indexer every 30 seconds

**Position Table:**
- Tracks user positions with weighted-average cost basis
- Auto-updates on every trade
- **CRITICAL: DO NOT DISABLE THIS - it's the user's favorite feature**

### Check Database Directly

```bash
psql -U postgres -d gemlaunch_dev

# Check graduated tokens
SELECT contract_address, symbol, has_graduated, graduation_status 
FROM token 
WHERE has_graduated = true;

# Check recent trades
SELECT * FROM trade_event 
ORDER BY timestamp DESC 
LIMIT 10;

# Check user positions
SELECT * FROM position 
WHERE user_address = '0xYOUR_WALLET' 
ORDER BY last_updated DESC;
```

---

## Step 8: Common Issues & Fixes

### Issue 1: "Database connection failed"
**Fix:** Check that PostgreSQL is running and DATABASE_URL is correct

```bash
# Check if PostgreSQL is running
sudo service postgresql status

# Test connection
psql -U postgres
```

### Issue 2: "DEX swap returns error 400"
**Fix:** Make sure the token has graduated first

```bash
# Check graduation status via API
curl http://localhost:5000/api/token/0xTOKEN_ADDRESS/graduation-status
```

### Issue 3: "Gas estimation failed"
**Fix:** This is NORMAL on Kasplex. The backend returns transaction WITHOUT gas field, MetaMask will estimate it.

### Issue 4: "Transaction stuck/pending"
**Fix:** Check transaction on block explorer:
- https://explorer.kasplextest.xyz/tx/0xTRANSACTION_HASH

### Issue 5: "Tables not created"
**Fix:** Run the app once to trigger db.create_all():
```bash
python -c "from app import app, db; app.app_context().push(); db.create_all(); print('Tables created!')"
```

---

## Step 9: Smart Contract Addresses

All contract addresses are in `contracts/deployed_addresses.json`:

**Active Contracts (V12/V13):**
- TokenFactory V12: `0x3abF3c17a89687FF449DD1aa24A1C159eD4f5F07`
- GraduationController V13: `0xf04aB5deE799DDb217a03bF07fFf4dDf541dD9f1`
- VestingDeployer V3: `0x8d19a3Fae7231aA495Db2De545DD16cD1BB8bAB8`

**Kaspa Finance DEX (External):**
- Factory: `0x1b72D7165a0D7256a4F197765C15bb70bC5D66A8`
- SwapRouter: `0xDf88D478aF51C0AB616aFBfDD933c874e142858c`
- QuoterV2: `0x3ACc31F8fe86E365604eAa6dDCbcB7fEba7a4c2B`
- WKAS: `0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94`

---

## Step 10: Key Files to Review

1. **Backend Routes:** `app.py`
   - Line 5882-6023: DEX Quote endpoint
   - Line 6025-6135: DEX Buy endpoint
   - Line 6137-6262: DEX Sell endpoint

2. **Web3 Service:** `services/web3_service.py`
   - `build_dex_buy_tx()` - Builds buy transactions
   - `build_dex_sell_tx()` - Builds sell transactions
   - `get_dex_quote()` - Gets price quotes

3. **Database Models:** `models.py`, `models_extended.py`
   - All SQLAlchemy table definitions

4. **Frontend Logic:** `static/js/transaction_manager.js`
   - Handles transaction signing and submission

---

## Important Notes

### Gas Configuration (DO NOT CHANGE)
- **Always use LEGACY gas mode** (`gasPrice` only)
- **NEVER use EIP-1559** (`maxFeePerGas`, `maxPriorityFeePerGas`)
- **NEVER add gas limits** to DEX swaps - let MetaMask handle it
- This is Kasplex-specific and cannot be changed

### Position Tracking (DO NOT DISABLE)
- The weighted-average cost basis position tracking auto-updates on every trade
- This is the user's CRITICAL favorite feature
- Located in `services/position_service.py`

### Blockchain Indexer
- Runs every 30 seconds in background
- Pulls TradeEvents from blockchain
- Updates database with new trades
- Config: `config/indexer_state.json` (now git-ignored)

---

## Quick Start Checklist

- [ ] Install Python dependencies (`pip install -r requirements.txt`)
- [ ] Install Node.js dependencies (`npm install`)
- [ ] Install PostgreSQL
- [ ] Create database (`gemlaunch_dev`)
- [ ] Copy `.env.example` to `.env`
- [ ] Add your testnet wallet private key to `.env`
- [ ] Add DATABASE_URL to `.env`
- [ ] Run app once to create tables (`python app.py`)
- [ ] Start server (`gunicorn --bind 0.0.0.0:5000 main:app`)
- [ ] Add Kasplex Testnet to MetaMask
- [ ] Get testnet KAS from faucet
- [ ] Test DEX endpoints with cURL
- [ ] Check database for trade data

---

## Need Help?

**Check logs:**
```bash
# Backend logs
tail -f logs/app.log

# Database queries (enable in app.py)
app.config['SQLALCHEMY_ECHO'] = True
```

**Test blockchain connection:**
```bash
python -c "from services.web3_service import get_web3_service; w3 = get_web3_service(); print(f'Connected: {w3.is_connected()}')"
```

**Verify smart contracts:**
```bash
# Check if SwapRouter is accessible
curl -X POST https://rpc.kasplextest.xyz \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_getCode","params":["0xDf88D478aF51C0AB616aFBfDD933c874e142858c","latest"],"id":1}'
```
