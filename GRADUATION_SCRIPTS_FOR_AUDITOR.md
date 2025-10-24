# Graduation Automation Scripts - Complete List

**Date:** October 24, 2025  
**Purpose:** Comprehensive list of all Python scripts that orchestrate token graduation  
**For:** Third-party smart contract auditor

---

## 📋 Overview

The graduation system is split across 6 main Python files that work together to:
1. Monitor tokens for graduation readiness
2. Initiate graduation transactions
3. Complete the two-phase graduation process
4. Index graduation events from blockchain
5. Manage state transitions

**Total Lines of Code:** ~4,500 lines across all graduation scripts

---

## 🎯 CORE GRADUATION SCRIPTS (Priority 1)

### 1. `services/graduation_monitor.py` (181 lines)

**Purpose:** Background service that monitors ALL tokens to detect when they reach graduation threshold

**Key Functions:**
```python
class GraduationMonitor:
    def start()
        # Starts background thread, runs every 60 seconds
    
    def _monitor_loop()
        # Main loop: checks all active tokens
    
    def check_token_graduation(token)
        # For each token:
        # 1. Query virtualKasReserve from blockchain
        # 2. Calculate market cap in USD (KAS * $0.0513)
        # 3. If >= $50, trigger initiation
    
    def initiate_graduation(token)
        # Calls BondingCurvePool.initiateGraduation()
        # Uses oracle wallet to sign transaction
```

**How It Works:**
1. **Every 60 seconds:** Wakes up and queries database for all tokens with `graduation_status = 'active'`
2. **For each token:** Makes RPC call to `pool.virtualKasReserve()` to get current bonding curve reserves
3. **Calculate market cap:** `kas_reserve * kasPrice (hardcoded $0.0513) = market_cap_usd`
4. **Threshold check:** If `market_cap_usd >= $50.00`, triggers graduation
5. **Initiate transaction:** Calls `pool.initiateGraduation()` using oracle wallet
6. **State update:** Sets `token.graduation_status = 'initiating'` in database

**Critical Code Path:**
```python
# Line ~60-95
kas_reserve_wei = pool.functions.virtualKasReserve().call()
kas_reserve = kas_reserve_wei / 1e18  # Convert from wei
market_cap_usd = kas_reserve * 0.0513  # Hardcoded KAS price

if market_cap_usd >= 50.0:  # Graduation threshold
    logging.info(f"🎓 Token {token.symbol} ready for graduation!")
    initiate_graduation(token)
```

**Known Issues:**
- ⚠️ **Line 133-139:** Uses `pool.graduationOracle()` address dynamically, which might return V1 (deprecated) controller for old tokens
- 🐛 **Infinite Loop Bug:** Tokens on V1 controller keep triggering graduation attempts that fail with "Already graduated or graduating"

---

### 2. `services/graduation_completion_service.py` (427 lines)

**Purpose:** Background service that monitors for tokens in 'initiating' status and completes the graduation

**Key Functions:**
```python
class GraduationCompletionService:
    def start()
        # Starts background thread, runs every 15 seconds
    
    def _check_and_complete_graduations()
        # Finds tokens with graduation_status='initiating'
    
    def _complete_single_graduation(token)
        # Phase 1: Verify initiation succeeded
        # Phase 2: Transfer KAS from oracle to GraduationController
        # Phase 3: Call completeGraduation()
        # Phase 4: Extract pool data from event
        # Phase 5: Update database
    
    def _extract_pool_data_from_completion(receipt, token)
        # Parse GraduationCompleted event for pool address, position ID
```

**Complete Graduation Flow:**
```python
# Phase 1: Verification (Lines 104-126)
pool = get_bonding_pool_contract(token.contract_address)
graduating = pool.functions.graduating().call()

if not graduating:
    # Reset to active - re-initiate on next cycle
    GraduationStateManager.reset_to_active(token)
    return

# Phase 2: Transfer KAS to GraduationController (Lines 128-194)
gc_address = pool.functions.graduationOracle().call()
expected_kas = gc.functions.expectedKasLiquidity(token.contract_address).call()

# Check if GC already has KAS
gc_balance = w3.eth.get_balance(gc_address)
if gc_balance < expected_kas:
    # Transfer KAS from oracle wallet to GraduationController
    transfer_tx = {
        'from': oracle_account.address,
        'to': gc_address,
        'value': expected_kas,
        'gas': 21000
    }
    signed_transfer = oracle_account.sign_transaction(transfer_tx)
    w3.eth.send_raw_transaction(signed_transfer.raw_transaction)
    
    # CRITICAL: Wait for transfer to mine before proceeding
    logging.info("⏳ Waiting for KAS transfer to be mined")
    return  # Exit and try again next cycle

# Phase 3: Call completeGraduation() (Lines 196-249)
tx_data = gc.functions.completeGraduation(token.contract_address).build_transaction({
    'from': oracle_account.address,
    'value': 0,  # No KAS in this call - already transferred
    'gas': estimated_gas,
    'gasPrice': w3.eth.gas_price,
    'nonce': current_nonce
})

signed_txn = sign_transaction(tx_data)
tx_hash = relay_transaction(signed_txn)

# Try to get receipt (may fail on Kasplex due to receipt purging)
try:
    receipt = w3.eth.get_transaction_receipt(tx_hash)
except:
    logging.warning("Could not fetch receipt yet (RPC limitation)")
    return  # Wait for next cycle

# Phase 4: Extract Pool Data (Lines 251-327)
pool_data = _extract_pool_data_from_completion(receipt, token)
# Returns: {
#     'pool_address': '0x...',
#     'position_id': 12345,
#     'fee_tier': 2500,
#     'kas_added': 1217700000000000000000,
#     'tokens_added': 250000000000000000000000
# }

# Phase 5: Update Database (Lines 259-278)
token.graduation_status = 'graduated'
token.graduation_completed_at = datetime.now(timezone.utc)
token.graduation_completion_tx = tx_hash.hex()
token.dex_pool_address = pool_data['pool_address']
token.lp_nft_position_id = pool_data['position_id']
token.dex_pool_fee_tier = pool_data['fee_tier']
token.is_graduated = True
db.session.commit()
```

**Critical Details:**
- ✅ **Lines 188-189:** DOES wait for KAS transfer to mine before calling `completeGraduation()`
- ✅ **Lines 212-220:** Gas estimation is done properly
- ⚠️ **Lines 133-139:** Uses pool's `graduationOracle()` address, which may point to V1 (deprecated)
- ⚠️ **Lines 230-238:** Handles Kasplex RPC receipt purging gracefully (waits for next cycle if receipt not available)

---

### 3. `services/graduation_state_manager.py` (85 lines)

**Purpose:** Centralized state management for graduation lifecycle

**Key Functions:**
```python
class GraduationStateManager:
    @staticmethod
    def initiate(token, tx_hash)
        # Sets graduation_status = 'initiating'
        # Records graduation_initiated_at timestamp
        # Stores initiation transaction hash
    
    @staticmethod
    def complete(token, pool_data, tx_hash)
        # Sets graduation_status = 'graduated'
        # Records completion timestamp
        # Stores pool address, position ID, etc.
    
    @staticmethod
    def cancel(token, reason)
        # Sets graduation_status = 'cancelled'
        # Records cancellation reason
    
    @staticmethod
    def reset_to_active(token)
        # Resets to 'active' if initiation failed
        # Allows re-triggering graduation
```

**State Transitions:**
```
active → initiating → graduated ✅
active → initiating → cancelled ❌
active → initiating → active (reset if failure) 🔄
```

---

## 🔗 SUPPORTING INFRASTRUCTURE (Priority 2)

### 4. `services/web3_service.py` (2,832 lines)

**Purpose:** Core blockchain interaction layer - handles ALL RPC calls, transaction signing, and contract loading

**Key Sections for Graduation:**

**A. Configuration (Lines 1-50)**
```python
# Kasplex Testnet RPC
KASPLEX_TESTNET_RPC = "https://rpc.kasplextest.xyz"
KASPLEX_TESTNET_CHAIN_ID = 167012

# Deployed Contract Addresses
GRADUATION_CONTROLLER_V2 = "0x147e3ecbe189bb301175001706ff1f44df33b3ab"
GRADUATION_CONTROLLER_V1 = "0x9416D5a5D61ec70C18D1FE1039f8026E29b4820e"  # DEPRECATED

# Kaspa Finance (Uniswap V3 Fork)
KASPA_FINANCE_FACTORY = "0x1b72D7165a0D7256a4F197765C15bb70bC5D66A8"
KASPA_FINANCE_POSITION_MANAGER = "0x4E25637cF39822364b877F81B18c5B6CF0eeF589"
KASPA_FINANCE_WKAS = "0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94"
```

**B. Oracle Wallet Derivation (Lines 101-130)**
```python
def _derive_secondary_wallet(self, deployer_private_key):
    """
    Derives oracle wallet deterministically from deployer key:
    oracle_key = keccak256("GEMLAUNCH_SECONDARY_WALLET" + deployer_key)
    
    Result: 0x5f837F62744D4d80Fc79C3A5346B4A228956914E
    """
    seed_text = "GEMLAUNCH_SECONDARY_WALLET"
    seed_bytes = seed_text.encode('utf-8')
    deployer_bytes = bytes.fromhex(deployer_private_key[2:])
    
    combined = seed_bytes + deployer_bytes
    derived_key = w3.keccak(combined)
    
    oracle_account = Account.from_key('0x' + derived_key.hex())
    return oracle_account
```

**C. Transaction Utilities (Lines 600-850)**
```python
def estimate_gas(tx_params):
    """
    Simulates transaction to get accurate gas estimate
    Returns: {'gas': 450000, 'gasPrice': 2000000000000}
    """
    gas_estimate = w3.eth.estimate_gas(tx_params)
    gas_price = w3.eth.gas_price
    return {'gas': int(gas_estimate * 1.2), 'gasPrice': gas_price}

def sign_transaction(tx_data):
    """
    Signs transaction with oracle account
    Automatically adds chainId (167012) if missing
    """
    if 'chainId' not in tx_data:
        tx_data['chainId'] = KASPLEX_TESTNET_CHAIN_ID
    
    signed = oracle_account.sign_transaction(tx_data)
    return signed

def relay_transaction(signed_txn):
    """
    Broadcasts signed transaction to Kasplex RPC
    Returns: transaction hash
    """
    tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
    return tx_hash

def wait_for_transaction_receipt(tx_hash, timeout=120):
    """
    Polls for transaction receipt (with Kasplex RPC workarounds)
    May raise TransactionNotFound on Kasplex testnet (receipts purged)
    """
    try:
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
        return receipt
    except Exception as e:
        logging.warning(f"Receipt not available: {e}")
        return None
```

**D. Contract Loading (Lines 224-350)**
```python
def _load_contracts(self):
    """
    Loads ABIs from Hardhat artifacts and creates contract instances
    """
    contracts = {
        'TokenFactory': self._load_contract('TokenFactory', TOKEN_FACTORY_ADDRESS),
        'GraduationController': self._load_contract('GraduationControllerV2', GRADUATION_CONTROLLER_V2),
        'BondingCurvePool': self._load_contract_abi('BondingCurvePool'),  # ABI only
        # ... more contracts
    }
    return contracts

def get_bonding_pool_contract(self, pool_address):
    """
    Creates BondingCurvePool contract instance at given address
    Used by graduation scripts to interact with pools
    """
    abi = self.contracts['BondingCurvePool'].abi
    return w3.eth.contract(address=pool_address, abi=abi)
```

**E. Kasplex RPC Workarounds (Lines 450-550)**
```python
# Kasplex Testnet Issues:
# 1. Receipts get purged after ~10 minutes
# 2. eth_estimateGas sometimes returns errors that don't match reality
# 3. Nonce management requires careful tracking

def get_safe_nonce(account_address):
    """
    Gets nonce with retry logic for Kasplex RPC instability
    """
    max_retries = 3
    for i in range(max_retries):
        try:
            nonce = w3.eth.get_transaction_count(account_address)
            return nonce
        except Exception as e:
            if i == max_retries - 1:
                raise
            time.sleep(1)
```

---

### 5. `services/event_indexer.py` (~500 lines estimated)

**Purpose:** Indexes blockchain events into database for historical tracking

**Key Functions:**
```python
class EventIndexer:
    def index_graduation_events()
        # Listens for:
        # - GraduationInitiated events
        # - GraduationCompleted events
        # - GraduationCancelled events
        # Stores in database for analytics
    
    def backfill_events(from_block, to_block)
        # Re-indexes events from blockchain
        # Used for recovering missing data
```

**Graduation Events Tracked:**
```solidity
// From GraduationControllerV2.sol
event GraduationInitiated(
    address indexed tokenAddress,
    uint256 kasLiquidity,
    uint256 tokenLiquidity,
    uint256 timestamp
);

event GraduationCompleted(
    address indexed tokenAddress,
    uint256 liquidityPositionId,
    uint256 kasAdded,
    uint256 tokensAdded,
    uint256 timestamp
);

event GraduationCancelled(
    address indexed tokenAddress,
    string reason
);
```

---

### 6. `app.py` - Graduation Endpoints (Lines 7500-7800 estimated)

**Purpose:** Flask HTTP endpoints for graduation status checks and manual triggers

**Key Endpoints:**
```python
@app.route('/api/token/<address>/graduation-status')
def get_graduation_status(address):
    """
    Returns current graduation status for a token
    Response: {
        'status': 'active' | 'initiating' | 'graduated' | 'cancelled',
        'market_cap_usd': 62.49,
        'threshold_usd': 50.00,
        'progress_pct': 124.98,
        'initiated_at': '2025-10-24T03:00:00Z',
        'completed_at': null,
        'dex_pool_address': null
    }
    """
    token = Token.query.filter_by(contract_address=address.lower()).first()
    
    # Get current market cap from blockchain
    pool = web3_service.get_bonding_pool_contract(token.contract_address)
    kas_reserve = pool.functions.virtualKasReserve().call() / 1e18
    market_cap_usd = kas_reserve * 0.0513  # KAS price
    
    return jsonify({
        'status': token.graduation_status,
        'market_cap_usd': market_cap_usd,
        'threshold_usd': 50.0,
        'progress_pct': (market_cap_usd / 50.0) * 100,
        # ... more fields
    })

@app.route('/api/admin/graduation/initiate/<address>', methods=['POST'])
@admin_required
def manual_initiate_graduation(address):
    """
    Manual graduation trigger (admin only)
    Used for testing or recovering from failures
    """
    token = Token.query.filter_by(contract_address=address.lower()).first()
    
    # Trigger graduation via monitor service
    graduation_monitor.initiate_graduation(token)
    
    return jsonify({'success': True, 'message': 'Graduation initiated'})

@app.route('/api/admin/graduation/cancel/<address>', methods=['POST'])
@admin_required
def manual_cancel_graduation(address):
    """
    Cancel stuck graduation (admin only)
    """
    token = Token.query.filter_by(contract_address=address.lower()).first()
    
    GraduationStateManager.cancel(token, reason='Manual cancellation')
    
    return jsonify({'success': True, 'message': 'Graduation cancelled'})
```

---

## 🔄 COMPLETE GRADUATION FLOW (Script-by-Script)

### Step-by-Step Execution:

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. MONITORING (graduation_monitor.py - Every 60 seconds)       │
├─────────────────────────────────────────────────────────────────┤
│ • Query database: Token.query.filter_by(graduation_status='active') │
│ • For each token:                                               │
│   - RPC call: pool.virtualKasReserve() via web3_service        │
│   - Calculate: market_cap_usd = kas_reserve * 0.0513           │
│   - Check: if market_cap_usd >= $50.00                         │
│ • If ready:                                                     │
│   - Call initiate_graduation(token)                            │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. INITIATION (graduation_monitor.py)                          │
├─────────────────────────────────────────────────────────────────┤
│ • web3_service.get_bonding_pool_contract(token.address)        │
│ • Build transaction: pool.initiateGraduation()                 │
│ • Sign with oracle wallet via web3_service.sign_transaction()  │
│ • Broadcast via web3_service.relay_transaction()               │
│ • Update database via graduation_state_manager.initiate()      │
│   - graduation_status = 'initiating'                           │
│   - graduation_initiated_at = now()                            │
│   - graduation_initiation_tx = tx_hash                         │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. COMPLETION MONITORING (graduation_completion_service.py - Every 15s) │
├─────────────────────────────────────────────────────────────────┤
│ • Query database: Token.query.filter_by(graduation_status='initiating') │
│ • For each token:                                               │
│   - Verify on-chain: pool.graduating() == true                 │
│   - Get controller: pool.graduationOracle()                    │
│   - Get expected KAS: controller.expectedKasLiquidity(token)   │
│   - Check controller balance: web3.eth.get_balance(controller) │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. KAS TRANSFER (graduation_completion_service.py)             │
├─────────────────────────────────────────────────────────────────┤
│ • If controller.balance < expected_kas:                         │
│   - Build transfer tx: oracle → controller (value: expected_kas) │
│   - Sign with oracle wallet                                    │
│   - Broadcast via web3_service                                 │
│   - WAIT for confirmation (exit and retry next cycle)          │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. COMPLETION CALL (graduation_completion_service.py)          │
├─────────────────────────────────────────────────────────────────┤
│ • Build transaction: controller.completeGraduation(token)      │
│ • Estimate gas via web3_service.estimate_gas()                 │
│ • Sign with oracle wallet                                      │
│ • Broadcast transaction                                        │
│ • Wait for receipt (with RPC error handling)                   │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 6. EVENT PARSING (graduation_completion_service.py)            │
├─────────────────────────────────────────────────────────────────┤
│ • Parse receipt logs for GraduationCompleted event             │
│ • Extract:                                                      │
│   - liquidityPositionId (NFT ID)                               │
│   - kasAdded (amount of KAS in pool)                          │
│   - tokensAdded (amount of tokens in pool)                    │
│ • Derive Uniswap V3 pool address via CREATE2                   │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 7. DATABASE UPDATE (graduation_state_manager.py)               │
├─────────────────────────────────────────────────────────────────┤
│ • graduation_status = 'graduated'                              │
│ • graduation_completed_at = now()                              │
│ • graduation_completion_tx = tx_hash                           │
│ • dex_pool_address = derived_pool_address                      │
│ • lp_nft_position_id = position_id                            │
│ • dex_pool_fee_tier = 2500 (0.25%)                            │
│ • is_graduated = True (legacy field)                           │
│ • db.session.commit()                                          │
└─────────────────────────────────────────────────────────────────┘
                            ↓
                         SUCCESS ✅
```

---

## 🐛 KNOWN BUGS & ISSUES

### BUG #1: Infinite Loop on V1 Tokens (CRITICAL)

**Location:** `services/graduation_monitor.py` Lines 133-139

**Symptom:** RAGR token (and others on V1 controller) trigger graduation every 60 seconds, fail with "Already graduated or graduating", then retry infinitely.

**Root Cause:**
```python
# graduation_monitor.py - Line 135
gc_address = pool.functions.graduationOracle().call()  # Returns V1 address for old tokens
graduation_controller = w3.eth.contract(address=gc_address, abi=gc_abi)

# Then tries to call V1 controller which rejects with:
# "Already graduated or graduating" (stuck in graduating=true from previous attempt)
```

**Affected Tokens:**
- RAGR: 0xa75c9441ba642165df45fbcdb03b5627521ecb7a (1,217.7 KAS)
- KPAN: 0xc33b27a9d68cb3e8b83dcba031da1a7cb4e29a98 (1,039.5 KAS)
- GLAZED: 0x9eb22b725f113f4e37654f3e87e830c7bbe1a0c3 (1,336.5 KAS)
- KAMI: 0x81f3cab02aefdb75d4cf9e720044a61c0fd15cc8 (990 KAS)

**Fix:**
```python
# Add to graduation_monitor.py Line 60
V1_DEPRECATED = '0x9416D5a5D61ec70C18D1FE1039f8026E29b4820e'

def check_token_graduation(token):
    # ... existing code ...
    
    # CRITICAL FIX: Skip V1 tokens
    pool = w3_service.get_bonding_pool_contract(token.contract_address)
    gc_address = pool.functions.graduationOracle().call()
    
    if gc_address.lower() == V1_DEPRECATED.lower():
        logging.warning(f"⏭️ Skipping {token.symbol} - on V1 controller (needs migration)")
        return
    
    # ... rest of code ...
```

### BUG #2: Hardcoded KAS Price

**Location:** Multiple files

**Issue:** KAS price is hardcoded at $0.0513 instead of being fetched from an oracle

**Locations:**
- `services/graduation_monitor.py` Line 75: `kas_price = 0.0513`
- `app.py` (multiple endpoints): `kas_price = 0.0513`

**Impact:** If KAS price changes significantly, graduation thresholds are wrong

**Fix:** Integrate with `services/kas_oracle.py` to fetch live KAS price

### BUG #3: Receipt Purging Handling

**Location:** `services/graduation_completion_service.py` Lines 230-238

**Issue:** Kasplex RPC purges receipts after ~10 minutes, causing graduation completion to retry indefinitely

**Current Workaround:** Service waits for next cycle if receipt not available

**Better Fix:** Use event logs from subsequent blocks to verify completion, or use balance-based verification

---

## 📊 SCRIPT DEPENDENCIES

```
graduation_monitor.py
├── web3_service.py (RPC calls, transaction signing)
├── graduation_state_manager.py (database updates)
└── models.py (Token model)

graduation_completion_service.py
├── web3_service.py (RPC calls, transaction signing)
├── graduation_state_manager.py (database updates)
└── models.py (Token model)

graduation_state_manager.py
├── models.py (Token model)
└── database (SQLAlchemy)

web3_service.py
├── web3.py library
├── eth_account library
└── Hardhat artifacts (ABIs)

event_indexer.py
├── web3_service.py
└── models.py (TradeEvent, etc.)
```

---

## 🔧 CONFIGURATION FILES

**Environment Variables Required:**
```bash
# .env file
DEPLOYER_PRIVATE_KEY=0x...  # Used to derive oracle wallet
DATABASE_URL=postgresql://...
KASPLEX_RPC_URL=https://rpc.kasplextest.xyz  # Optional override
```

**Hardhat Artifacts:**
```
artifacts/contracts/
├── GraduationControllerV2.sol/
│   └── GraduationControllerV2.json  # ABI + bytecode
├── BondingCurvePool.sol/
│   └── BondingCurvePool.json
└── TokenFactory.sol/
    └── TokenFactory.json
```

---

## 📝 TESTING COMMANDS

**To test graduation monitoring:**
```bash
# In Python shell
from services.graduation_monitor import GraduationMonitor
from app import app

monitor = GraduationMonitor(app)
monitor.check_token_graduation(token)  # Test single token
```

**To test graduation completion:**
```bash
from services.graduation_completion_service import GraduationCompletionService

service = GraduationCompletionService(app)
service._complete_single_graduation(token)  # Test single completion
```

**To verify on-chain state:**
```bash
from services.web3_service import get_web3_service

w3 = get_web3_service()
pool = w3.get_bonding_pool_contract('0xa75c9441ba642165df45fbcdb03b5627521ecb7a')

print(pool.functions.graduating().call())  # Should be False after completion
print(pool.functions.graduated().call())   # Should be True after completion
```

---

## 📋 SUMMARY FOR AUDITOR

**Core Files to Review:**
1. ✅ `services/graduation_monitor.py` (181 lines) - Initiation trigger
2. ✅ `services/graduation_completion_service.py` (427 lines) - Completion logic
3. ✅ `services/graduation_state_manager.py` (85 lines) - State management
4. ✅ `services/web3_service.py` (2,832 lines) - Blockchain interface
5. ⚠️ `services/event_indexer.py` (~500 lines) - Event tracking
6. ⚠️ `app.py` (graduation endpoints ~300 lines) - HTTP API

**Total Lines to Review:** ~4,325 lines of Python code

**Key Questions for Code Review:**
1. ✅ Does `graduation_completion_service.py` wait for KAS transfer before calling `completeGraduation()`? **YES (Line 188-189)**
2. ✅ Is gas estimation done correctly? **YES (Lines 212-220)**
3. ⚠️ Are expected amounts validated between script and contract? **PARTIALLY (needs improvement)**
4. ❌ Is there retry logic causing infinite loops? **YES - V1 tokens loop forever (needs fix)**

**Critical Fix Needed:**
Filter out V1 tokens in `graduation_monitor.py` to stop the infinite loop.

---

**Prepared by:** gemlaunch.fun engineering team  
**Date:** October 24, 2025  
**For:** Third-party smart contract audit
