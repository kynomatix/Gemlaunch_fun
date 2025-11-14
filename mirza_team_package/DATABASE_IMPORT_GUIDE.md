# Database Import Guide for Mirza's Team

## Files Included

1. **`database_schema.sql`** (2,946 lines) - Complete database structure (all 36 tables)
2. **`database_data.sql`** (328 lines) - Essential data for testing:
   - Tokens (including graduated tokens)
   - Trade events (historical trades)
   - Positions (user holdings with cost basis)
   - Users
   - Platform settings

---

## Quick Start (PostgreSQL)

### 1. Install PostgreSQL

**macOS:**
```bash
brew install postgresql
brew services start postgresql
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib
sudo service postgresql start
```

**Windows:**
Download from https://www.postgresql.org/download/windows/

---

### 2. Create Database

```bash
# Connect to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE gemlaunch_dev;

# Exit
\q
```

---

### 3. Import Schema

```bash
psql -U postgres -d gemlaunch_dev -f database_schema.sql
```

**Expected output:**
```
CREATE TABLE
CREATE TABLE
...
CREATE INDEX
(2946 lines processed)
```

---

### 4. Import Data

```bash
psql -U postgres -d gemlaunch_dev -f database_data.sql
```

**Expected output:**
```
COPY 10  # tokens
COPY 150 # trade_events
COPY 45  # positions
...
```

---

### 5. Verify Import

```bash
psql -U postgres -d gemlaunch_dev
```

**Run these checks:**

```sql
-- Check tables exist
\dt

-- Check token data
SELECT contract_address, symbol, name, has_graduated 
FROM token 
LIMIT 5;

-- Check graduated tokens (needed for DEX testing)
SELECT contract_address, symbol, graduation_status, dex_pool_address 
FROM token 
WHERE has_graduated = true;

-- Check trade events
SELECT COUNT(*) FROM trade_event;

-- Check positions
SELECT COUNT(*) FROM position;

-- Exit
\q
```

---

## Set Up Environment

Create `.env` file:

```bash
# Database Connection
DATABASE_URL=postgresql://postgres:password@localhost:5432/gemlaunch_dev

# Session Secret (generate random)
SESSION_SECRET=your_random_secret_here

# Copy the rest from .env.example
# (RPC URLs, wallet addresses, DEX contracts, etc.)
```

---

## Test DEX Swaps

### Prerequisites

1. **Find a graduated token:**

```sql
psql -U postgres -d gemlaunch_dev -c "
SELECT contract_address, symbol, name, dex_pool_address 
FROM token 
WHERE has_graduated = true 
LIMIT 1;
"
```

Copy the `contract_address` - you'll need it for testing.

2. **Start the app:**

```bash
python main.py
# or
gunicorn --bind 0.0.0.0:5000 main:app
```

3. **Test DEX quote:**

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

4. **Test DEX buy:**

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

---

## Database Notes

### What's Included

**Complete Schema:**
- All 36 tables
- Indexes
- Foreign key constraints
- Check constraints

**Essential Data:**
- **Tokens:** Including graduated tokens needed for DEX testing
- **Trade Events:** Historical trade data for charts
- **Positions:** User holdings with weighted-average cost basis
- **Users:** Basic user accounts
- **Platform Settings:** Global configuration

**Not Included (Not Needed for DEX Testing):**
- Chat messages
- Polls/votes
- Achievement data
- Social features
- Admin data

---

### Important Tables for DEX Testing

**1. `token` table:**
- `contract_address` - Token contract address (PRIMARY KEY)
- `has_graduated` - Boolean (must be TRUE for DEX swaps)
- `graduation_status` - Must be "completed"
- `dex_pool_address` - Uniswap V3 pool address
- `current_price_usd` - Current token price
- `market_cap_usd` - Market capitalization

**2. `trade_event` table:**
- All historical trades
- Used for price charts
- Indexed by token_address

**3. `position` table:**
- User holdings with weighted-average cost basis
- **CRITICAL:** This is the user's favorite feature - NEVER DISABLE
- Auto-updates on every trade

---

## Troubleshooting

### Issue: "psql: command not found"
**Fix:** PostgreSQL not installed or not in PATH
```bash
# macOS
brew install postgresql

# Ubuntu
sudo apt-get install postgresql-client
```

### Issue: "database does not exist"
**Fix:** Create the database first
```bash
createdb gemlaunch_dev
```

### Issue: "permission denied"
**Fix:** Use correct PostgreSQL user
```bash
# Check your PostgreSQL username
whoami

# Use that username
psql -U your_username -d gemlaunch_dev
```

### Issue: "ERROR: duplicate key value"
**Fix:** Database already has data, drop and recreate
```bash
dropdb gemlaunch_dev
createdb gemlaunch_dev
psql -U postgres -d gemlaunch_dev -f database_schema.sql
psql -U postgres -d gemlaunch_dev -f database_data.sql
```

### Issue: "No graduated tokens found"
**Fix:** The data dump may not have graduated tokens. You can either:

**Option A:** Graduate a token manually in the database:
```sql
UPDATE token 
SET has_graduated = true, 
    graduation_status = 'completed',
    dex_pool_address = '0xYOUR_POOL_ADDRESS'
WHERE contract_address = '0xYOUR_TOKEN_ADDRESS';
```

**Option B:** Create a token and trade it to $50 market cap to trigger graduation

---

## Production Database Access (Not Recommended)

If you need access to the LIVE production database for testing:

**WARNING:** This is risky! You could accidentally delete production data.

**Safer Alternative:** Use the dumps provided (schema + data)

**If you really need production access:**
1. Contact the project owner for credentials
2. Use a read-only connection
3. NEVER run DELETE/UPDATE/DROP on production

---

## Connection String Format

```
postgresql://username:password@host:port/database

Examples:
- Local: postgresql://postgres:password@localhost:5432/gemlaunch_dev
- Remote: postgresql://user:pass@host.com:5432/gemlaunch_prod
```

---

## Next Steps After Import

1. ✅ Verify tables imported correctly
2. ✅ Check graduated tokens exist
3. ✅ Update `.env` with DATABASE_URL
4. ✅ Start the app
5. ✅ Test DEX endpoints with cURL
6. ✅ Connect MetaMask to Kasplex Testnet
7. ✅ Test full trading flow

---

## Need More Data?

If you need the complete dataset (all tables including social features):

```bash
# Full database dump (may be large!)
pg_dump $DATABASE_URL --no-owner --no-privileges > full_database_dump.sql

# Import
psql -U postgres -d gemlaunch_dev -f full_database_dump.sql
```

---

## Summary

**What You Got:**
- 36 table schema (structure)
- Essential data for DEX testing
- Tokens, trades, positions, users

**What You Need to Do:**
1. Install PostgreSQL
2. Create database
3. Import schema.sql
4. Import data.sql
5. Update .env
6. Start testing!

**Time Required:** ~15 minutes
