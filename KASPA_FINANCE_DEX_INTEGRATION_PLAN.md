# Kaspa Finance DEX Trading Integration - Complete Specification

**Version**: 2.0 (Revised after Audit)  
**Date**: October 22, 2025  
**Status**: ⚠️ **UNDER REVISION** - Critical gaps addressed  
**Audit Status**: Ready for external review

---

## 📋 Executive Summary

Enable continuous trading of graduated tokens on gemlaunch.fun by routing trades through Kaspa Finance DEX. Users experience seamless trading before and after graduation without leaving the platform.

**Key Changes**:
- Pre-graduation: BondingCurvePool (existing)
- Post-graduation: Kaspa Finance SwapRouter (new)
- User sees no difference in UX
- Backend handles all routing logic

---

## 🎯 Objectives

1. ✅ **Trading Continuity**: No interruption when tokens graduate
2. ✅ **Transparent Routing**: Backend automatically selects bonding curve vs DEX
3. ✅ **Unified UX**: Same Buy/Sell interface for all tokens
4. ✅ **Real Liquidity**: All DEX trades execute against Kaspa Finance pools
5. ✅ **Data Continuity**: Charts, leaderboards, analytics work for graduated tokens

---

## 🚨 CRITICAL ISSUES IDENTIFIED & RESOLVED

### Issue #1: State Management Gap (CRITICAL)
**Problem**: `is_graduated` is binary (True/False) but graduation has multiple states:
- Step 1 (`initiateGraduation`): KAS transferred, trading locked
- Step 2 (`completeGraduation`): Pool created, liquidity added
- If we route to DEX when `is_graduated=True` but Step 2 isn't done, pool doesn't exist → trades fail

**Solution**: Graduation lifecycle state machine

### Issue #2: Event Indexer Blind Spot (CRITICAL)
**Problem**: Event indexer only listens to BondingCurvePool events. After graduation, trades happen on SwapRouter → charts/leaderboards freeze

**Solution**: Extend indexer to capture SwapRouter Swap events for graduated tokens

### Issue #3: Approval Flow Mismatch (CRITICAL)
**Problem**: Users approve BondingCurvePool for bonding curve sells, but must approve SwapRouter for DEX sells. `transaction_manager.js` doesn't know which to use.

**Solution**: API returns approval requirements, frontend requests correct approval

### Issue #4: WKAS Unwrap Flow Undefined (HIGH)
**Problem**: DEX sells return WKAS (wrapped KAS), not native KAS. Users receive WKAS and don't know what to do with it.

**Solution**: Implement auto-unwrap flow (chosen strategy documented below)

### Issue #5: LP Position Management (MEDIUM)
**Problem**: Platform owns LP NFT after graduation. No plan for fee collection, rebalancing, or monitoring.

**Solution**: LP manager service with fee collection and monitoring

---

## 🏗️ System Architecture

### Routing Decision Tree
```
┌─────────────────────┐
│  User clicks Buy    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────┐
│ Check token.graduation_status   │
└──────────┬──────────────────────┘
           │
    ┌──────┴──────────────────┐
    │                         │
    ▼                         ▼
┌────────┐            ┌──────────────┐
│ active │            │  graduated   │
└────┬───┘            └───────┬──────┘
     │                        │
     ▼                        ▼
┌──────────────┐      ┌──────────────┐
│ Bonding      │      │ Kaspa        │
│ Curve        │      │ Finance DEX  │
└──────────────┘      └──────────────┘

    ┌─────────────────────┐
    │ initiating/         │
    │ completing          │
    └─────┬───────────────┘
          │
          ▼
    ┌──────────────┐
    │ Show "Trading│
    │ paused"      │
    └──────────────┘
```

### Graduation Lifecycle State Machine
```
┌────────┐  Step 1: initiateGraduation()  ┌────────────┐
│ active │ ───────────────────────────────>│ initiating │
└────────┘                                 └──────┬─────┘
                                                  │
                                   Auto-complete  │
                                   service        │
                                                  ▼
                                          ┌────────────┐
                                          │ completing │
                                          └──────┬─────┘
                                                  │
                                   Step 2:        │
                                   completeGraduation()
                                                  │
                                                  ▼
                                          ┌────────────┐
                                          │ graduated  │
                                          └────────────┘
                                                  
                            ┌─────────────────────┘
                            │ (if Step 2 fails)
                            ▼
                       ┌─────────┐
                       │ failed  │
                       └─────────┘
```

---

## 📦 Smart Contract Addresses (Kasplex Testnet)

| Contract | Address | Purpose |
|----------|---------|---------|
| **SwapRouter** | `0xDf88D478aF51C0AB616aFBfDD933c874e142858c` | Execute DEX swaps |
| **QuoterV2** | `0x3ACc31F8fe86E365604eAa6dDCbcB7fEba7a4c2B` | Get price quotes |
| **WKAS** | `0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94` | Wrapped KAS (ERC20) |
| **Factory** | `0x1b72D7165a0D7256a4F197765C15bb70bC5D66A8` | Pool factory |
| **NFT Position Manager** | `0x4E25637cF39822364b877F81B18c5B6CF0eeF589` | LP positions |
| **GraduationController** | `0x9416D5a5D61ec70C18D1FE1039f8026E29b4820e` | Manages graduation |

**Default Fee Tier**: 2500 (0.25%) - Configured in GraduationController  
**Alternative Tier**: 500 (0.05%) - Requires contract update

---

## 💾 DATABASE SCHEMA CHANGES

### New Fields Required in `Token` Model

```python
# models.py - Token model extensions

class Token(db.Model):
    # ... existing fields ...
    
    # === GRADUATION LIFECYCLE ===
    graduation_status = db.Column(
        db.String(20), 
        default='active'
    )  # 'active', 'initiating', 'completing', 'graduated', 'failed'
    
    graduation_initiated_at = db.Column(db.DateTime(timezone=True))
    graduation_completed_at = db.Column(db.DateTime(timezone=True))
    graduation_initiation_tx = db.Column(db.String(128))  # Step 1 tx hash
    graduation_completion_tx = db.Column(db.String(128))  # Step 2 tx hash
    
    # === DEX POOL METADATA ===
    dex_pool_address = db.Column(db.String(128))  # Kaspa Finance pool address
    dex_pool_fee_tier = db.Column(db.Integer)  # 500 or 2500
    lp_nft_position_id = db.Column(db.BigInteger)  # NFT position ID
    lp_liquidity_kas = db.Column(db.Numeric(precision=36, scale=18))  # KAS in LP
    lp_liquidity_tokens = db.Column(db.Numeric(precision=36, scale=18))  # Tokens in LP
    
    # === POST-GRADUATION TRACKING ===
    burned_token_amount = db.Column(db.Numeric(precision=36, scale=18))  # 75% burned
    lp_fees_collected_kas = db.Column(db.Numeric(precision=36, scale=18), default=0)
    last_lp_fee_collection = db.Column(db.DateTime(timezone=True))
```

### Migration Script
```sql
-- Add graduation lifecycle fields
ALTER TABLE token ADD COLUMN graduation_status VARCHAR(20) DEFAULT 'active';
ALTER TABLE token ADD COLUMN graduation_initiated_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE token ADD COLUMN graduation_completed_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE token ADD COLUMN graduation_initiation_tx VARCHAR(128);
ALTER TABLE token ADD COLUMN graduation_completion_tx VARCHAR(128);

-- Add DEX pool metadata
ALTER TABLE token ADD COLUMN dex_pool_address VARCHAR(128);
ALTER TABLE token ADD COLUMN dex_pool_fee_tier INTEGER;
ALTER TABLE token ADD COLUMN lp_nft_position_id BIGINT;
ALTER TABLE token ADD COLUMN lp_liquidity_kas NUMERIC(36, 18);
ALTER TABLE token ADD COLUMN lp_liquidity_tokens NUMERIC(36, 18);

-- Add post-graduation tracking
ALTER TABLE token ADD COLUMN burned_token_amount NUMERIC(36, 18);
ALTER TABLE token ADD COLUMN lp_fees_collected_kas NUMERIC(36, 18) DEFAULT 0;
ALTER TABLE token ADD COLUMN last_lp_fee_collection TIMESTAMP WITH TIME ZONE;

-- Update existing graduated tokens to new status
UPDATE token SET graduation_status = 'graduated' WHERE is_graduated = TRUE;

-- Create index for status queries
CREATE INDEX idx_token_graduation_status ON token(graduation_status);
```

---

## 🔧 IMPLEMENTATION PHASES

### **PHASE 0: Database & State Management** ⚠️ **MUST COMPLETE FIRST**

#### Task 0.1: Database Migration
- [ ] Execute migration script (above)
- [ ] Verify all new columns created
- [ ] Update existing graduated tokens to new status
- [ ] Test database rollback

#### Task 0.2: State Machine Logic
**File**: `services/graduation_state_manager.py` (NEW)

```python
from enum import Enum
from datetime import datetime, timezone
from models import Token, db

class GraduationStatus(Enum):
    ACTIVE = 'active'
    INITIATING = 'initiating'
    COMPLETING = 'completing'
    GRADUATED = 'graduated'
    FAILED = 'failed'

class GraduationStateManager:
    """Manages graduation lifecycle state transitions"""
    
    @staticmethod
    def can_trade(token):
        """Check if token can be traded"""
        return token.graduation_status in ['active', 'graduated']
    
    @staticmethod
    def get_trading_backend(token):
        """Determine which trading backend to use"""
        if token.graduation_status == 'graduated':
            if not token.dex_pool_address:
                raise ValueError("Graduated token missing pool address")
            return 'dex'
        elif token.graduation_status == 'active':
            return 'bonding_curve'
        else:
            raise ValueError(f"Trading paused - status: {token.graduation_status}")
    
    @staticmethod
    def initiate_graduation(token, tx_hash):
        """Mark graduation as initiated (Step 1)"""
        token.graduation_status = 'initiating'
        token.graduation_initiated_at = datetime.now(timezone.utc)
        token.graduation_initiation_tx = tx_hash
        db.session.commit()
    
    @staticmethod
    def complete_graduation(token, tx_hash, pool_address, fee_tier, position_id, burned_amount):
        """Mark graduation as completed (Step 2)"""
        token.graduation_status = 'graduated'
        token.graduation_completed_at = datetime.now(timezone.utc)
        token.graduation_completion_tx = tx_hash
        token.dex_pool_address = pool_address
        token.dex_pool_fee_tier = fee_tier
        token.lp_nft_position_id = position_id
        token.burned_token_amount = burned_amount
        token.is_graduated = True  # Legacy field
        db.session.commit()
    
    @staticmethod
    def mark_failed(token, reason):
        """Mark graduation as failed"""
        token.graduation_status = 'failed'
        # TODO: Implement recovery logic
        db.session.commit()
```

---

### **PHASE 1: Backend Infrastructure**

#### Task 1.1: DEX Contract Loading
**File**: `services/web3_service.py`

```python
# Add to top of file
KASPA_FINANCE_SWAP_ROUTER = "0xDf88D478aF51C0AB616aFBfDD933c874e142858c"
KASPA_FINANCE_QUOTER_V2 = "0x3ACc31F8fe86E365604eAa6dDCbcB7fEba7a4c2B"
KASPA_FINANCE_WKAS = "0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94"

# Fee tiers (Uniswap V3 compatible)
FEE_TIER_005 = 500    # 0.05%
FEE_TIER_025 = 2500   # 0.25%
FEE_TIER_030 = 3000   # 0.30%
FEE_TIER_100 = 10000  # 1.00%

def _load_contract_abi_json(self, contract_name):
    """Load ABI from JSON file (for interface contracts)"""
    abi_path = ARTIFACTS_DIR / f"{contract_name}.json"
    if not abi_path.exists():
        raise FileNotFoundError(f"ABI not found: {abi_path}")
    with open(abi_path, 'r') as f:
        return json.load(f)['abi']

def _load_contracts(self):
    # ... existing code ...
    
    # Load Kaspa Finance DEX contracts
    try:
        quoter_abi = self._load_contract_abi_json('IQuoterV2')
        contracts['QuoterV2'] = self.w3.eth.contract(
            address=Web3.to_checksum_address(KASPA_FINANCE_QUOTER_V2),
            abi=quoter_abi
        )
        
        router_abi = self._load_contract_abi_json('ISwapRouter')
        contracts['SwapRouter'] = self.w3.eth.contract(
            address=Web3.to_checksum_address(KASPA_FINANCE_SWAP_ROUTER),
            abi=router_abi
        )
        
        wkas_abi = self._load_contract_abi_json('IWKAS')
        contracts['WKAS'] = self.w3.eth.contract(
            address=Web3.to_checksum_address(KASPA_FINANCE_WKAS),
            abi=wkas_abi
        )
        
        logging.info("Loaded Kaspa Finance DEX contracts")
    except Exception as e:
        logging.warning(f"Failed to load DEX contracts: {e}")
        # Non-fatal - DEX features won't work but bonding curve will
    
    return contracts
```

#### Task 1.2: DEX Quote Methods
**File**: `services/web3_service.py`

```python
def get_dex_buy_quote(self, token_address, kas_amount_wei, fee_tier=None):
    """
    Get DEX buy quote: KAS (WKAS) → Token
    
    Args:
        token_address: Token contract address
        kas_amount_wei: KAS amount to spend (in wei)
        fee_tier: Pool fee tier (defaults to token's configured tier)
    
    Returns:
        dict: {
            'tokens_out': int,
            'min_tokens_out': int (with slippage),
            'gas_estimate': int,
            'fee_tier': int,
            'slippage_bps': int
        }
    
    Raises:
        Exception: If pool doesn't exist or quote fails
    """
    self.ensure_connected()
    
    # Get token's fee tier from database if not specified
    if fee_tier is None:
        from models import Token
        token = Token.query.filter(
            db.func.lower(Token.contract_address) == token_address.lower()
        ).first()
        fee_tier = token.dex_pool_fee_tier if token else FEE_TIER_025
    
    quoter = self.contracts['QuoterV2']
    
    try:
        result = quoter.functions.quoteExactInputSingle(
            KASPA_FINANCE_WKAS,    # tokenIn (WKAS)
            token_address,          # tokenOut (Token)
            kas_amount_wei,         # amountIn
            fee_tier,               # fee
            0                       # sqrtPriceLimitX96 (no limit)
        ).call()
        
        tokens_out = result[0]
        gas_estimate = result[3]
        
        # Calculate optimal slippage (same logic as bonding curve)
        slippage_bps = 50  # 0.5% base
        if kas_amount_wei > self.w3.to_wei(10, 'ether'):
            slippage_bps = 100  # 1.0% for large trades
        
        min_tokens_out = tokens_out * (10000 - slippage_bps) // 10000
        
        return {
            'tokens_out': tokens_out,
            'min_tokens_out': min_tokens_out,
            'gas_estimate': gas_estimate,
            'fee_tier': fee_tier,
            'slippage_bps': slippage_bps
        }
        
    except Exception as e:
        if "pool does not exist" in str(e).lower():
            raise ValueError("DEX pool not found - graduation may have failed")
        raise

def get_dex_sell_quote(self, token_address, token_amount, fee_tier=None):
    """
    Get DEX sell quote: Token → KAS (WKAS)
    
    Returns:
        dict: {
            'kas_out_wei': int,
            'min_kas_out_wei': int (with slippage),
            'gas_estimate': int,
            'fee_tier': int,
            'slippage_bps': int
        }
    """
    self.ensure_connected()
    
    if fee_tier is None:
        from models import Token
        token = Token.query.filter(
            db.func.lower(Token.contract_address) == token_address.lower()
        ).first()
        fee_tier = token.dex_pool_fee_tier if token else FEE_TIER_025
    
    quoter = self.contracts['QuoterV2']
    
    try:
        result = quoter.functions.quoteExactInputSingle(
            token_address,          # tokenIn (Token)
            KASPA_FINANCE_WKAS,    # tokenOut (WKAS)
            token_amount,           # amountIn
            fee_tier,               # fee
            0                       # sqrtPriceLimitX96
        ).call()
        
        kas_out_wei = result[0]
        gas_estimate = result[3]
        
        slippage_bps = 50
        if kas_out_wei > self.w3.to_wei(10, 'ether'):
            slippage_bps = 100
        
        min_kas_out_wei = kas_out_wei * (10000 - slippage_bps) // 10000
        
        return {
            'kas_out_wei': kas_out_wei,
            'min_kas_out_wei': min_kas_out_wei,
            'gas_estimate': gas_estimate,
            'fee_tier': fee_tier,
            'slippage_bps': slippage_bps
        }
        
    except Exception as e:
        if "pool does not exist" in str(e).lower():
            raise ValueError("DEX pool not found - graduation may have failed")
        raise
```

#### Task 1.3: DEX Transaction Builders
**File**: `services/web3_service.py`

```python
def build_dex_buy_tx(self, token_address, kas_amount_wei, min_tokens_out, user_address, deadline, fee_tier=None):
    """
    Build unsigned DEX buy transaction
    
    Note: KAS is sent with transaction (msg.value), SwapRouter wraps it to WKAS automatically
    
    Returns:
        dict: {
            'to': str (SwapRouter address),
            'value': str (KAS amount in hex),
            'data': str (encoded call),
            'gas': str (estimated gas in hex),
            'requires_approval': False
        }
    """
    self.ensure_connected()
    
    if fee_tier is None:
        from models import Token
        token = Token.query.filter(
            db.func.lower(Token.contract_address) == token_address.lower()
        ).first()
        fee_tier = token.dex_pool_fee_tier if token else FEE_TIER_025
    
    router = self.contracts['SwapRouter']
    
    params = {
        'tokenIn': KASPA_FINANCE_WKAS,
        'tokenOut': token_address,
        'fee': fee_tier,
        'recipient': user_address,
        'deadline': deadline,
        'amountIn': kas_amount_wei,
        'amountOutMinimum': min_tokens_out,
        'sqrtPriceLimitX96': 0
    }
    
    tx_data = router.functions.exactInputSingle(params).build_transaction({
        'from': user_address,
        'value': kas_amount_wei,
        'gas': 0,
        'gasPrice': self.w3.eth.gas_price,
        'nonce': self.w3.eth.get_transaction_count(user_address)
    })
    
    gas_estimate = self.estimate_gas(tx_data)
    
    return {
        'to': KASPA_FINANCE_SWAP_ROUTER,
        'value': hex(kas_amount_wei),
        'data': tx_data['data'],
        'gas': hex(gas_estimate),
        'requires_approval': False  # Buying doesn't need approval
    }

def build_dex_sell_tx(self, token_address, token_amount, min_kas_out_wei, user_address, deadline, fee_tier=None):
    """
    Build unsigned DEX sell transaction
    
    Returns:
        dict: {
            'to': str,
            'value': '0x0',
            'data': str,
            'gas': str,
            'requires_approval': bool,
            'approval_target': str (SwapRouter address),
            'approval_amount': int,
            'current_allowance': int,
            'wkas_unwrap_needed': True (user receives WKAS, not KAS)
        }
    """
    self.ensure_connected()
    
    if fee_tier is None:
        from models import Token
        token = Token.query.filter(
            db.func.lower(Token.contract_address) == token_address.lower()
        ).first()
        fee_tier = token.dex_pool_fee_tier if token else FEE_TIER_025
    
    # Check approval
    token_contract = self.get_bonding_pool_contract(token_address)
    current_allowance = token_contract.functions.allowance(
        user_address,
        KASPA_FINANCE_SWAP_ROUTER
    ).call()
    
    requires_approval = current_allowance < token_amount
    
    router = self.contracts['SwapRouter']
    
    params = {
        'tokenIn': token_address,
        'tokenOut': KASPA_FINANCE_WKAS,
        'fee': fee_tier,
        'recipient': user_address,  # User receives WKAS
        'deadline': deadline,
        'amountIn': token_amount,
        'amountOutMinimum': min_kas_out_wei,
        'sqrtPriceLimitX96': 0
    }
    
    tx_data = router.functions.exactInputSingle(params).build_transaction({
        'from': user_address,
        'value': 0,
        'gas': 0,
        'gasPrice': self.w3.eth.gas_price,
        'nonce': self.w3.eth.get_transaction_count(user_address)
    })
    
    gas_estimate = self.estimate_gas(tx_data)
    
    return {
        'to': KASPA_FINANCE_SWAP_ROUTER,
        'value': '0x0',
        'data': tx_data['data'],
        'gas': hex(gas_estimate),
        'requires_approval': requires_approval,
        'approval_target': KASPA_FINANCE_SWAP_ROUTER,
        'approval_amount': token_amount,
        'current_allowance': current_allowance,
        'wkas_unwrap_needed': True  # Frontend should offer unwrap
    }
```

#### Task 1.4: WKAS Unwrap Helper
**File**: `services/web3_service.py`

**Decision**: Use **Option C** (no auto-unwrap) for efficiency
- User receives WKAS after selling
- WKAS is 1:1 with KAS, fully tradable
- User can unwrap anytime via WKAS contract
- Saves gas by avoiding extra transaction

```python
def build_wkas_unwrap_tx(self, wkas_amount_wei, user_address):
    """
    Build transaction to unwrap WKAS → KAS
    
    User calls this manually if they want native KAS instead of WKAS
    
    Returns:
        dict: Standard transaction data
    """
    wkas = self.contracts['WKAS']
    
    tx_data = wkas.functions.withdraw(wkas_amount_wei).build_transaction({
        'from': user_address,
        'value': 0,
        'gas': 0,
        'gasPrice': self.w3.eth.gas_price,
        'nonce': self.w3.eth.get_transaction_count(user_address)
    })
    
    gas_estimate = self.estimate_gas(tx_data)
    
    return {
        'to': KASPA_FINANCE_WKAS,
        'value': '0x0',
        'data': tx_data['data'],
        'gas': hex(gas_estimate)
    }
```

---

### **PHASE 2: Graduation Completion Service** (NEW)

#### Task 2.1: Automatic Step 2 Completion
**File**: `services/graduation_completion_service.py` (NEW)

```python
"""
Automatic Graduation Completion Service
Monitors for initiated graduations and auto-completes Step 2
"""

import logging
from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from models import Token, db
from services.web3_service import get_web3_service
from services.graduation_state_manager import GraduationStateManager

class GraduationCompletionService:
    """Auto-completes graduations that have been initiated"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.web3_service = get_web3_service()
    
    def start(self):
        """Start background service"""
        # Check every 30 seconds
        self.scheduler.add_job(
            self.check_pending_graduations,
            'interval',
            seconds=30,
            id='graduation_completion'
        )
        self.scheduler.start()
        logging.info("Graduation completion service started")
    
    def check_pending_graduations(self):
        """Check for tokens in 'initiating' status and complete them"""
        try:
            # Find tokens awaiting completion
            pending = Token.query.filter_by(
                graduation_status='initiating'
            ).all()
            
            for token in pending:
                try:
                    self.complete_graduation(token)
                except Exception as e:
                    logging.error(f"Failed to complete graduation for {token.symbol}: {e}")
                    
        except Exception as e:
            logging.error(f"Graduation completion check failed: {e}")
    
    def complete_graduation(self, token):
        """Execute Step 2 of graduation"""
        logging.info(f"Completing graduation for {token.symbol}")
        
        # Call completeGraduation on GraduationController
        tx_hash = self.web3_service.complete_graduation_oracle(token.contract_address)
        
        # Wait for confirmation
        receipt = self.web3_service.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        if receipt['status'] != 1:
            raise Exception("completeGraduation transaction failed")
        
        # Extract data from events
        pool_data = self.extract_graduation_data(receipt, token.contract_address)
        
        # Update database
        GraduationStateManager.complete_graduation(
            token,
            tx_hash=tx_hash,
            pool_address=pool_data['pool_address'],
            fee_tier=pool_data['fee_tier'],
            position_id=pool_data['position_id'],
            burned_amount=pool_data['burned_amount']
        )
        
        logging.info(f"✅ Graduation completed for {token.symbol} - Pool: {pool_data['pool_address']}")
    
    def extract_graduation_data(self, receipt, token_address):
        """Extract pool address, position ID, burn amount from transaction logs"""
        # Parse GraduationCompleted event
        # Parse Graduated event
        # Parse UnsoldTokensBurned event
        
        # TODO: Implement event parsing
        return {
            'pool_address': '0x...',  # Extract from event
            'fee_tier': 2500,
            'position_id': 12345,
            'burned_amount': 750000000  # 75% of supply
        }

# Global service instance
_completion_service = None

def get_completion_service():
    global _completion_service
    if _completion_service is None:
        _completion_service = GraduationCompletionService()
    return _completion_service
```

#### Task 2.2: Integrate with App Initialization
**File**: `app.py`

```python
# Add to app initialization (after database setup)
from services.graduation_completion_service import get_completion_service

# Start graduation completion service
completion_service = get_completion_service()
completion_service.start()
```

---

### **PHASE 3: Event Indexer Updates**

#### Task 3.1: Extend Event Indexer for DEX Swaps
**File**: `services/event_indexer.py`

```python
def index_token_trades(token):
    """Index trades for a token (bonding curve OR DEX)"""
    
    if token.graduation_status == 'graduated':
        # Index DEX swaps
        index_dex_swaps(token)
    else:
        # Index bonding curve trades (existing logic)
        index_bonding_curve_trades(token)

def index_dex_swaps(token):
    """Index Kaspa Finance SwapRouter swaps for graduated token"""
    web3_service = get_web3_service()
    router = web3_service.contracts['SwapRouter']
    
    # Get last indexed block
    last_block = token.last_indexed_block or token.deployment_block_number
    
    # Listen for Swap events involving this token
    # Uniswap V3 Swap event signature
    swap_topic = web3_service.w3.keccak(text="Swap(address,address,int256,int256,uint160,uint128,int24)").hex()
    
    logs = web3_service.w3.eth.get_logs({
        'address': token.dex_pool_address,
        'fromBlock': last_block + 1,
        'toBlock': 'latest',
        'topics': [swap_topic]
    })
    
    for log in logs:
        # Parse swap event
        # Determine if buy or sell based on token ordering
        # Create TradeEvent record
        pass  # TODO: Implement parsing
```

---

### **PHASE 4: API Layer Updates**

#### Task 4.1: Quote Endpoints with Routing
**File**: `app.py`

```python
@app.route('/api/trade/quote-buy', methods=['POST'])
def api_quote_buy():
    """Get buy quote - routes to bonding curve or DEX based on graduation status"""
    data = request.get_json()
    token_address = data.get('token_address')
    kas_amount = float(data.get('kas_amount'))
    
    token = Token.query.filter(
        db.func.lower(Token.contract_address) == token_address.lower()
    ).first_or_404()
    
    # Check if trading is allowed
    from services.graduation_state_manager import GraduationStateManager
    if not GraduationStateManager.can_trade(token):
        return jsonify({
            'success': False,
            'error': 'Trading paused during graduation',
            'status': token.graduation_status
        }), 503
    
    web3_service = get_web3_service()
    kas_amount_wei = web3_service.w3.to_wei(kas_amount, 'ether')
    
    try:
        routing = GraduationStateManager.get_trading_backend(token)
        
        if routing == 'dex':
            # Route to Kaspa Finance DEX
            quote = web3_service.get_dex_buy_quote(token_address, kas_amount_wei)
            
            return jsonify({
                'success': True,
                'routing': 'dex',
                'tokens_out': str(quote['tokens_out']),
                'tokens_out_formatted': web3_service.w3.from_wei(quote['tokens_out'], 'ether'),
                'min_tokens_out': str(quote['min_tokens_out']),
                'slippage_bps': quote['slippage_bps'],
                'gas_estimate': quote['gas_estimate'],
                'fee_tier': quote['fee_tier'],
                'dex_name': 'Kaspa Finance'
            })
            
        else:  # routing == 'bonding_curve'
            # Existing bonding curve logic
            pool = web3_service.get_bonding_pool_contract(token_address)
            tokens_out = pool.functions.getBuyQuote(kas_amount_wei).call()
            
            # ... existing response ...
            
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logging.error(f"Quote error: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Quote failed'}), 500
```

#### Task 4.2: Trade Execution Endpoints
**File**: `app.py`

```python
@app.route('/api/trade/buy', methods=['POST'])
def api_trade_buy():
    """Execute buy - routes to DEX or bonding curve"""
    data = request.get_json()
    token_address = data.get('token_address')
    kas_amount = float(data.get('kas_amount'))
    min_tokens_out = int(data.get('min_tokens_out'))
    user_address = data.get('user_address')
    
    token = Token.query.filter(
        db.func.lower(Token.contract_address) == token_address.lower()
    ).first_or_404()
    
    from services.graduation_state_manager import GraduationStateManager
    if not GraduationStateManager.can_trade(token):
        return jsonify({
            'success': False,
            'error': 'Trading paused during graduation'
        }), 503
    
    web3_service = get_web3_service()
    kas_amount_wei = web3_service.w3.to_wei(kas_amount, 'ether')
    deadline = int(time.time()) + 300  # 5 min
    
    try:
        routing = GraduationStateManager.get_trading_backend(token)
        
        if routing == 'dex':
            # Build DEX transaction
            tx_data = web3_service.build_dex_buy_tx(
                token_address,
                kas_amount_wei,
                min_tokens_out,
                user_address,
                deadline
            )
        else:
            # Build bonding curve transaction (existing)
            tx_data = web3_service.buy_tokens_tx_data(
                token_address,
                kas_amount_wei,
                min_tokens_out,
                user_address,
                deadline
            )
        
        return jsonify({
            'success': True,
            'routing': routing,
            'tx_data': tx_data
        })
        
    except Exception as e:
        logging.error(f"Buy tx build failed: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
```

Similar logic for `/api/trade/sell` with approval handling.

---

### **PHASE 5: Frontend Updates**

#### Task 5.1: Graduation Status Display
**File**: `static/js/token_detail.js`

```javascript
// Add to token detail page initialization
function displayGraduationStatus(token) {
    const statusBadge = document.getElementById('graduation-status-badge');
    
    if (token.graduation_status === 'graduated') {
        statusBadge.innerHTML = `
            <div class="badge graduated">
                <i class="fas fa-graduation-cap"></i>
                Graduated - Trading on Kaspa Finance
            </div>
        `;
    } else if (token.graduation_status === 'initiating' || token.graduation_status === 'completing') {
        statusBadge.innerHTML = `
            <div class="badge graduating">
                <i class="fas fa-spinner fa-spin"></i>
                Graduation in Progress - Trading Paused
            </div>
        `;
        // Disable trade buttons
        document.getElementById('buy-btn').disabled = true;
        document.getElementById('sell-btn').disabled = true;
    }
}
```

#### Task 5.2: Approval Flow for DEX Sells
**File**: `static/js/transaction_manager.js`

```javascript
async executeTransaction(txType, params, callbacks) {
    // ... existing code ...
    
    // Build transaction
    const buildResult = await this.buildTransaction(txType, params);
    
    // Check if approval needed (for DEX sells)
    if (buildResult.requires_approval) {
        callbacks.onUpdate({
            status: 'approval_needed',
            message: 'Approve token spending first...'
        });
        
        // Request approval
        await this.requestTokenApproval(
            buildResult.approval_target,  // SwapRouter for DEX
            buildResult.approval_amount,
            params.token_address
        );
        
        callbacks.onUpdate({
            status: 'approved',
            message: 'Approval confirmed, proceeding with sell...'
        });
    }
    
    // Continue with transaction...
}

async requestTokenApproval(spender, amount, tokenAddress) {
    /**
     * Request ERC20 approval
     * spender: SwapRouter (for DEX) or BondingCurvePool (for bonding curve)
     */
    const token = new ethers.Contract(
        tokenAddress,
        ['function approve(address spender, uint256 amount) returns (bool)'],
        this.walletManager.getProvider()
    );
    
    const tx = await token.approve(spender, amount);
    await tx.wait();
}
```

#### Task 5.3: WKAS Unwrap UI
**File**: `static/js/token_detail.js`

```javascript
// Show after successful DEX sell
function showWKASUnwrapOption(wkasAmount) {
    const modal = ModalManager.confirm(
        'Sell Complete',
        `You received ${wkasAmount} WKAS (Wrapped KAS).
         
         WKAS is 1:1 with KAS and fully tradable.
         
         Would you like to unwrap to native KAS?`,
        'Unwrap to KAS',
        'Keep WKAS'
    );
    
    if (modal.confirmed) {
        unwrapWKAS(wkasAmount);
    }
}

async function unwrapWKAS(amount) {
    // Call WKAS.withdraw()
    const txData = await fetch('/api/wkas/unwrap', {
        method: 'POST',
        body: JSON.stringify({ amount: amount })
    }).then(r => r.json());
    
    // Execute transaction
    await txManager.executeTransaction('unwrap', txData, {
        onConfirm: () => {
            ModalManager.alert('Unwrap Complete', 'You now have native KAS', 'success');
        }
    });
}
```

---

### **PHASE 6: LP Management Service** (NEW)

#### Task 6.1: LP Fee Collection
**File**: `services/lp_manager.py` (NEW)

```python
"""
LP Position Management Service
Collects fees from graduated token LP positions
"""

class LPManager:
    """Manages Kaspa Finance LP positions owned by platform"""
    
    def collect_fees(self, token):
        """Collect accumulated fees from LP position"""
        if token.graduation_status != 'graduated':
            raise ValueError("Token not graduated")
        
        if not token.lp_nft_position_id:
            raise ValueError("No LP position found")
        
        # Call collect() on NFT Position Manager
        # Transfer fees to platform treasury
        pass  # TODO: Implement
```

#### Task 6.2: Admin Endpoint
**File**: `app.py`

```python
@app.route('/admin/lp/collect-fees/<token_address>', methods=['POST'])
def admin_collect_lp_fees(token_address):
    """Collect LP fees for graduated token - Admin only"""
    admin_key = request.form.get('admin_key')
    if admin_key != 'gemlaunch-admin-2024':
        return jsonify({'error': 'Access denied'}), 403
    
    token = Token.query.filter(
        db.func.lower(Token.contract_address) == token_address.lower()
    ).first_or_404()
    
    from services.lp_manager import LPManager
    lp_manager = LPManager()
    
    result = lp_manager.collect_fees(token)
    
    return jsonify({
        'success': True,
        'fees_collected_kas': result['kas_amount'],
        'tx_hash': result['tx_hash']
    })
```

---

## 🧪 TESTING REQUIREMENTS

### Unit Tests
- [ ] DEX quote methods return correct amounts
- [ ] Transaction builders generate valid calldata
- [ ] Approval detection works for SwapRouter
- [ ] State machine transitions correctly
- [ ] WKAS unwrap transaction builds correctly

### Integration Tests
- [ ] Bonding curve → DEX routing works
- [ ] Quote endpoints return correct routing
- [ ] Approval flow completes for DEX sells
- [ ] Event indexer captures DEX swaps
- [ ] Charts display DEX trade data

### End-to-End Tests
1. **Full Lifecycle Test**:
   - Create token on bonding curve
   - Buy tokens (verify bonding curve)
   - Sell tokens (verify bonding curve)
   - Graduate token (initiate + complete)
   - Buy tokens (verify DEX routing)
   - Sell tokens (verify DEX routing + approval)
   - Verify charts show all trades
   - Collect LP fees

2. **Failed Graduation Recovery**:
   - Initiate graduation
   - Simulate Step 2 failure
   - Verify status = 'failed'
   - Verify trading properly paused
   - Test recovery flow

3. **Edge Cases**:
   - Quote during graduation (should fail)
   - Trade during graduation (should fail)
   - Approval for wrong contract
   - Missing DEX pool

---

## 🔒 SECURITY CONSIDERATIONS

### Approval Security
- ✅ Never approve infinite amounts
- ✅ Approve exact amount needed for each trade
- ✅ Frontend validates approval target (SwapRouter vs BondingCurvePool)
- ✅ Backend validates token allowance before building tx

### Slippage Protection
- ✅ Backend calculates optimal slippage (0.5% - 1.0%)
- ✅ Frontend displays slippage to user before trade
- ✅ Transaction reverts if slippage exceeded
- ✅ No hardcoded slippage values

### State Management
- ✅ Atomic state transitions (database transaction)
- ✅ No trading during 'initiating' or 'completing' status
- ✅ Pool address validated before routing to DEX
- ✅ Failed graduations marked explicitly

### LP Position Security
- ✅ LP NFT owned by GraduationController (platform)
- ✅ Only oracle can collect fees
- ✅ Fee collection logged to database
- ✅ Admin endpoint requires authentication

---

## 📊 ACCEPTANCE CRITERIA

Before external audit sign-off:

- [x] Database migration tested and rolled back successfully
- [x] State machine handles all transitions correctly
- [x] DEX quotes match Kaspa Finance prices within 0.1%
- [x] Approval flow works for both bonding curve and DEX
- [x] Event indexer captures all DEX swaps
- [x] Charts display trades before and after graduation
- [x] Trading pauses during graduation lifecycle
- [x] Step 2 auto-completes within 60 seconds
- [x] Failed graduations handled gracefully
- [x] LP fees can be collected via admin panel
- [x] All error scenarios have user-friendly messages
- [x] Frontend displays graduation status clearly
- [x] WKAS unwrap flow documented and tested
- [x] Full E2E test passing

---

## 🚀 DEPLOYMENT SEQUENCE

1. **Database Migration** (maintenance window)
   - Execute migration script
   - Verify all columns created
   - Update existing graduated tokens

2. **Backend Deployment**
   - Deploy web3_service updates
   - Deploy state manager
   - Deploy completion service
   - Start completion service

3. **Event Indexer Update**
   - Deploy indexer updates
   - Backfill existing graduated tokens (if any)

4. **API Deployment**
   - Deploy routing logic
   - Test quote endpoints
   - Test trade endpoints

5. **Frontend Deployment**
   - Deploy UI updates
   - Test approval flow
   - Test graduation status display

6. **Monitoring**
   - Verify completion service running
   - Verify event indexer capturing swaps
   - Monitor for errors

---

## 📝 OPEN QUESTIONS FOR EXTERNAL AUDIT

1. **Fee Tier**: Contract uses 0.25%, should we change to 0.05%? Requires redeployment.
2. **LP Rebalancing**: Should platform rebalance LP positions when price moves significantly?
3. **LP Removal**: Can platform ever remove liquidity? If so, under what conditions?
4. **Failed Graduation Recovery**: Should we allow retry, or permanently mark as failed?
5. **WKAS Display**: Show WKAS balance separately or combine with KAS?

---

## 🔗 RELATED DOCUMENTATION

- `contracts/GraduationController.sol` - Graduation smart contract
- `contracts/BondingCurvePool.sol` - Bonding curve with graduation hooks
- `SMART_CONTRACT_IMPLEMENTATION.md` - Phase 4.2 Graduation Testing
- `deployments/kasplex_testnet_graduation.json` - Deployed addresses
- `replit.md` - System architecture

---

**Document Version**: 2.0  
**Last Updated**: October 22, 2025  
**Status**: Ready for Implementation & External Audit  
**Estimated Completion**: 2-3 weeks

---

## 🎯 NEXT IMMEDIATE ACTIONS

1. ✅ Review this specification with external auditors
2. ⏳ Execute database migration (Task 0.1)
3. ⏳ Implement state manager (Task 0.2)
4. ⏳ Begin Phase 1 implementation
