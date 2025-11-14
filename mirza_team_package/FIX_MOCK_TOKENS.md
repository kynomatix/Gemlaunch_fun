# FIX: Removing Mock Tokens (FLOKI, DOGE, PEPE, etc.)

## Problem

You're seeing fake tokens like:
- FlokiKas (FLOKI)
- Doge Kaspa (DOGKAS)
- PepeCoin (PEPE)
- Moon Rocket (MOON)
- Laser Eyes (LASER)

These are **mock tokens** created by the app when it starts with an empty database.

---

## Quick Fix (Delete Mock Tokens & Import Real Data)

### Step 1: Stop the App

Press `Ctrl+C` in the terminal running the app.

---

### Step 2: Clear Mock Tokens from Database

```bash
psql -U postgres -d gemlaunch_dev -c "DELETE FROM token;"
psql -U postgres -d gemlaunch_dev -c "DELETE FROM user WHERE wallet_address IN ('0xa51d8f597570353ae50a25df90ade162d2305ffa', '0x2a3b4c5d6e7f8901234567890abcdef123456789', '0x9f8e7d6c5b4a39281726354647382910abcdef12', '0x5d4c3b2a1908765432101234567890abcdef1234');"
```

---

### Step 3: Import Real Token Data

```bash
psql -U postgres -d gemlaunch_dev -f database_data.sql
```

This imports the **real** tokens from the production database (including graduated tokens you need for DEX testing).

---

### Step 4: Verify Real Tokens Imported

```bash
psql -U postgres -d gemlaunch_dev -c "SELECT symbol, name, contract_address FROM token LIMIT 10;"
```

**You should see:** Real token addresses like `0x0e041bf893c585173bbf0b1beffc46d4491afc91` (not the mock ones)

---

### Step 5: Restart the App

```bash
python main.py
```

**Now you'll see real tokens!**

---

## Alternative Fix (Disable Mock Token Creation)

If you want to prevent mock tokens from being created in the future:

### Edit `app.py` (around line 4276)

**Find this:**
```python
# Create sample tokens with contract addresses if none exist
if not Token.query.first():
    print("Creating sample tokens...")
```

**Change to:**
```python
# Create sample tokens with contract addresses if none exist
# DISABLED FOR LOCAL TESTING - using real data from SQL dump instead
if False:  # Changed from: if not Token.query.first():
    print("Creating sample tokens...")
```

**Save the file and restart the app.**

Now it will NEVER create mock tokens, even if the database is empty.

---

## Why This Happened

1. ✅ You imported `database_schema.sql` (created empty tables)
2. ❌ You either:
   - Didn't import `database_data.sql`, OR
   - Imported it but it had errors
3. App started, saw empty database
4. Auto-created mock tokens for demo purposes

---

## Verify Real vs Mock Tokens

**Mock Token Addresses (FAKE):**
```
0x80707fad25e8727117d5ff2ad0960dae2b7aa463  ← DOGKAS (mock)
0x91818fbe36d8827228e6cc7c5af1cd52e4315g74  ← MOON (mock)
0xc3d4e5f6789012345678901234567890abcdef12  ← LASER (mock)
0xa1b2c3d4e5f6789012345678901234567890abcd  ← PEPE (mock)
0xd4e5f6789012345678901234567890abcdef1234  ← FLOKI (mock)
```

**Real Token Addresses (from production):**
```
0x0e041bf893c585173bbf0b1beffc46d4491afc91  ← Real token
0x3e5270a10e6ba500122ee5000c1e84f013d8d0fc  ← Real token
... (and more)
```

Check your token addresses - if they match the mock list, you're seeing fake data!

---

## Complete Clean Setup (Start Fresh)

If you want to completely reset:

```bash
# 1. Drop database
dropdb gemlaunch_dev

# 2. Recreate
createdb gemlaunch_dev

# 3. Import schema
psql -U postgres -d gemlaunch_dev -f database_schema.sql

# 4. Import real data
psql -U postgres -d gemlaunch_dev -f database_data.sql

# 5. Verify
psql -U postgres -d gemlaunch_dev -c "SELECT COUNT(*) FROM token;"

# Should show a number > 5 (if only showing 5, you still have mock tokens)
```

---

## Testing DEX Swaps with Real Tokens

After importing real data, find a graduated token:

```bash
psql -U postgres -d gemlaunch_dev -c "
SELECT contract_address, symbol, name, has_graduated, dex_pool_address 
FROM token 
WHERE has_graduated = true 
LIMIT 1;
"
```

Use that contract address for DEX swap testing!

---

## Summary

**The fix:**
1. Delete mock tokens from database
2. Import `database_data.sql` (real data)
3. Restart app
4. Optionally: Edit `app.py` line 4276 to disable mock token creation

**You'll now see:**
- Real token addresses
- Real trade history
- Graduated tokens for DEX testing
- Actual production data snapshot
