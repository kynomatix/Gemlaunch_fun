# Troubleshooting: "Static Tokens" Issue

## Need More Information

When you say "static tokens", what exactly do you see? Please provide:

1. **Screenshot** - What's on your screen?
2. **URL** - What page are you looking at? (e.g., /marketplace, /token/0x123...)
3. **Browser Console** - Any errors in F12 developer console?
4. **Server Logs** - What does the terminal show when you start the app?

---

## Common Causes & Fixes

### Issue 1: Database Data Not Imported

**Symptom:** Empty marketplace or no tokens showing

**Check:**
```bash
psql -U postgres -d gemlaunch_dev -c "SELECT COUNT(*) FROM token;"
```

**Expected:** Should show a number > 0

**If it shows 0:**
```bash
# You only imported the schema, not the data!
# Import the data:
psql -U postgres -d gemlaunch_dev -f database_data.sql
```

---

### Issue 2: DATABASE_URL Not Set

**Symptom:** App starts but shows empty data

**Check your `.env` file:**
```bash
cat .env | grep DATABASE_URL
```

**Should show:**
```
DATABASE_URL=postgresql://postgres:password@localhost:5432/gemlaunch_dev
```

**If missing or wrong:**
```bash
echo "DATABASE_URL=postgresql://postgres:password@localhost:5432/gemlaunch_dev" >> .env
```

Then restart the app.

---

### Issue 3: Wrong Database Name

**Symptom:** App works but shows no tokens

**Check:**
```bash
# List all databases
psql -U postgres -c "\l"

# Check which database has data
psql -U postgres -d gemlaunch_dev -c "SELECT COUNT(*) FROM token;"
```

**Make sure** your `.env` DATABASE_URL points to the correct database name.

---

### Issue 4: Frontend Cached Data

**Symptom:** Old/example data showing

**Fix:**
1. Clear browser cache (Ctrl+Shift+Delete)
2. Hard refresh (Ctrl+F5)
3. Open in incognito/private window

---

### Issue 5: Wrong Port/URL

**Symptom:** Seeing old deployed version

**Check:** Are you accessing the correct URL?
- ✅ Local: http://localhost:5000
- ❌ Production: https://gemlaunch.fun (not your local version!)

---

## Verification Steps

### Step 1: Verify Database Has Data

```bash
psql -U postgres -d gemlaunch_dev
```

**Run these queries:**

```sql
-- Check tokens
SELECT contract_address, symbol, name FROM token LIMIT 5;

-- If no results, data wasn't imported!
```

**If no tokens found:**
```bash
# Exit psql
\q

# Import data
psql -U postgres -d gemlaunch_dev -f database_data.sql
```

---

### Step 2: Verify App Connects to Database

**Start the app and look for this in terminal:**
```
✅ Database tables created
```

**If you see errors like:**
```
FATAL: database "gemlaunch_dev" does not exist
```

**Then create the database:**
```bash
createdb gemlaunch_dev
psql -U postgres -d gemlaunch_dev -f database_schema.sql
psql -U postgres -d gemlaunch_dev -f database_data.sql
```

---

### Step 3: Verify Tokens Load on Homepage

**Start the app:**
```bash
python main.py
```

**Open browser:**
```
http://localhost:5000
```

**You should see:**
- Token marketplace with tokens
- Token cards showing real data
- Not placeholder/example data

**If you still see "static tokens":**
- What does the page show exactly?
- Screenshot please!

---

### Step 4: Check API Endpoint Directly

**Test the API:**
```bash
curl http://localhost:5000/api/tokens
```

**Expected response:**
```json
{
  "tokens": [
    {
      "contract_address": "0x...",
      "symbol": "...",
      "name": "...",
      ...
    }
  ]
}
```

**If returns empty array `[]`:**
- Database has no data
- Re-import database_data.sql

**If returns error:**
- DATABASE_URL not set
- Database not running
- Wrong database name

---

## Debug Mode: Enable SQL Logging

**Edit `app.py` around line 156:**

```python
# Add this line to see all SQL queries
app.config['SQLALCHEMY_ECHO'] = True
```

**Restart app** - you'll now see every database query in the terminal.

**Look for queries like:**
```sql
SELECT token.id, token.name, token.symbol ...
FROM token
```

**If you see these but still no data:** 
- Queries are running but returning 0 results
- Database has no data - reimport database_data.sql

**If you DON'T see these:**
- Database isn't being queried
- Check DATABASE_URL in .env

---

## Quick Diagnostic Script

**Create this file `test_db.py`:**

```python
import os
from app import app, db
from models import Token

with app.app_context():
    # Test database connection
    print(f"DATABASE_URL: {os.environ.get('DATABASE_URL')}")
    
    # Count tokens
    token_count = Token.query.count()
    print(f"Total tokens in database: {token_count}")
    
    # Show first 5 tokens
    if token_count > 0:
        print("\nFirst 5 tokens:")
        tokens = Token.query.limit(5).all()
        for token in tokens:
            print(f"  - {token.symbol}: {token.name} ({token.contract_address})")
    else:
        print("\n❌ NO TOKENS FOUND!")
        print("Import database_data.sql:")
        print("  psql -U postgres -d gemlaunch_dev -f database_data.sql")
```

**Run it:**
```bash
python test_db.py
```

**Expected output:**
```
DATABASE_URL: postgresql://postgres:password@localhost:5432/gemlaunch_dev
Total tokens in database: 54

First 5 tokens:
  - JAK: Jak Token (0x0e041bf893c585173bbf0b1beffc46d4491afc91)
  - PHNT: Phantom Token (0x3e5270a10e6ba500122ee5000c1e84f013d8d0fc)
  ...
```

---

## What "Static Tokens" Might Mean

Please clarify which of these you're seeing:

### Scenario A: Placeholder Text
**You see:** "Example Token", "Test Token", dummy data

**This means:** Frontend is showing hardcoded examples, database not connected

**Fix:** Set DATABASE_URL correctly, restart app

---

### Scenario B: Empty Marketplace
**You see:** No tokens at all, just empty page

**This means:** Database has no data

**Fix:** Import database_data.sql

---

### Scenario C: Old Cached Data
**You see:** Tokens but they don't match what's in database

**This means:** Browser cache

**Fix:** Hard refresh (Ctrl+F5)

---

### Scenario D: Tokens Not Updating
**You see:** Token prices/stats not changing

**This means:** Normal! Updates happen every 30 seconds via indexer

**Not a bug:** Wait 30 seconds or check indexer is running

---

## Still Stuck?

**Please provide:**

1. **Output of:** `python test_db.py`
2. **Screenshot** of what you see in browser
3. **Your .env file** (hide passwords):
   ```bash
   cat .env | grep -v "PRIVATE_KEY\|PASSWORD"
   ```
4. **Terminal output** when starting the app
5. **Browser console** (F12 → Console tab → screenshot)

With this info, we can diagnose the exact issue!

---

## Most Likely Issue

**90% chance it's one of these:**

1. ❌ **Didn't import data** - Only imported schema, not database_data.sql
2. ❌ **Wrong DATABASE_URL** - Typo in .env file
3. ❌ **Wrong database name** - DATABASE_URL points to wrong database

**Quick fix:**
```bash
# Verify database exists and has data
psql -U postgres -d gemlaunch_dev -c "SELECT COUNT(*) FROM token;"

# If shows 0, import data:
psql -U postgres -d gemlaunch_dev -f database_data.sql

# Restart app
python main.py
```
