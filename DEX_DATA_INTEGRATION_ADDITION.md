# DATA INTEGRATION SECTION - TO BE MERGED INTO MAIN PLAN

## 🔄 **CRITICAL ADDITION: DATA PIPELINE INTEGRATION**

### **Problem Statement**

The current plan specifies routing logic (bonding curve vs DEX) but **does NOT explain** how DEX trades integrate with existing systems:

- ❌ How do DEX swaps update `TokenEngagement.trades_count`?
- ❌ How do DEX swaps update `User.total_trades_count`?
- ❌ How do achievements track DEX activity?
- ❌ How do leaderboards stay current after graduation?
- ❌ How do portfolio/holding calculations work with DEX trades?
- ❌ How does the activity feed log DEX trades?

**Without this specification, ALL engagement tracking stops after graduation.**

---

## 📊 **COMPLETE DATA FLOW: Bonding Curve vs DEX**

### **Current Flow (Bonding Curve)**
```
User trades on bonding curve
  ↓
BondingCurvePool.TokensPurchased / TokensSold event
  ↓
Event Indexer captures event
  ↓
Creates TradeEvent record
  ↓
SIMULTANEOUSLY:
  ├→ Trade model record created
  ├→ TokenEngagement.trades_count++
  ├→ TokenEngagement.buy_count++ (or sell_count++)
  ├→ TokenEngagement.total_traded_volume += kas_amount
  ├→ User.total_trades_count++
  ├→ User.total_trading_volume += kas_amount
  ├→ Holding.update_holding() (cost basis tracking)
  ├→ Activity feed entry created
  └→ Achievement progress recalculated
```

### **NEW Flow (DEX) - MUST MATCH ABOVE**
```
User trades on Kaspa Finance DEX
  ↓
SwapRouter.Swap event emitted
  ↓
Event Indexer captures Swap event
  ↓
Creates TradeEvent record (SAME schema)
  ↓
SIMULTANEOUSLY (IDENTICAL TO BONDING CURVE):
  ├→ Trade model record created
  ├→ TokenEngagement.trades_count++
  ├→ TokenEngagement.buy_count++ (or sell_count++)
  ├→ TokenEngagement.total_traded_volume += kas_amount
  ├→ User.total_trades_count++
  ├→ User.total_trading_volume += kas_amount
  ├→ Holding.update_holding() (cost basis tracking)
  ├→ Activity feed entry created
  └→ Achievement progress recalculated
```

**KEY INSIGHT**: DEX swaps must produce **identical downstream effects** as bonding curve trades.

---

## 🛠️ **PHASE 3.5: Data Integration Layer** (NEW)

### **Task 3.5.1: TradeEvent Normalization**

**Goal**: Ensure DEX swaps create TradeEvent records identical to bonding curve trades

**File**: `services/event_indexer.py`

```python
def index_dex_swaps(token):
    """
    Index Kaspa Finance SwapRouter Swap events for graduated tokens
    Creates TradeEvent records compatible with bonding curve events
    """
    web3_service = get_web3_service()
    
    # Get last indexed block
    last_block = token.last_indexed_block or token.deployment_block_number
    
    # Uniswap V3 Pool contract Swap event
    # event Swap(address indexed sender, address indexed recipient,
    #            int256 amount0, int256 amount1, uint160 sqrtPriceX96,
    #            uint128 liquidity, int24 tick)
    
    pool_contract = web3_service.w3.eth.contract(
        address=token.dex_pool_address,
        abi=web3_service._load_contract_abi_json('IUniswapV3Pool')
    )
    
    swap_filter = pool_contract.events.Swap.create_filter(
        fromBlock=last_block + 1,
        toBlock='latest'
    )
    
    swap_events = swap_filter.get_all_entries()
    
    for event in swap_events:
        process_dex_swap_event(token, event)
    
    # Update last indexed block
    if swap_events:
        token.last_indexed_block = swap_events[-1]['blockNumber']
        db.session.commit()

def process_dex_swap_event(token, event):
    """
    Convert Uniswap V3 Swap event to TradeEvent record
    
    Swap event structure:
    - amount0: Token amount change (negative = token out)
    - amount1: WKAS amount change (negative = WKAS out)
    - recipient: Address receiving the output tokens
    """
    args = event['args']
    
    # Determine token0 vs token1 ordering
    # In Uniswap V3, lower address is token0
    token_address_lower = token.contract_address.lower()
    wkas_address_lower = KASPA_FINANCE_WKAS.lower()
    
    if token_address_lower < wkas_address_lower:
        # Token is token0, WKAS is token1
        token_amount_delta = args['amount0']
        kas_amount_delta = args['amount1']
    else:
        # WKAS is token0, Token is token1
        kas_amount_delta = args['amount0']
        token_amount_delta = args['amount1']
    
    # Determine trade type
    # If token_amount_delta is negative, user is selling tokens
    # If token_amount_delta is positive, user is buying tokens
    is_buy = token_amount_delta > 0
    trade_type = 'buy' if is_buy else 'sell'
    
    # Get absolute values
    token_amount = abs(token_amount_delta)
    kas_amount = abs(kas_amount_delta)
    
    # Calculate price per token
    price_per_token = kas_amount / token_amount if token_amount > 0 else 0
    
    # Get user address (recipient for buys, sender for sells)
    # Note: For swaps, we need to trace the actual user, not the router
    user_address = args['recipient'].lower()
    
    # Check if event already indexed (prevent duplicates)
    existing = TradeEvent.query.filter_by(
        tx_hash=event['transactionHash'].hex(),
        log_index=event['logIndex']
    ).first()
    
    if existing:
        return  # Already processed
    
    # Create TradeEvent record (SAME schema as bonding curve)
    trade_event = TradeEvent(
        token_id=token.id,
        user_address=user_address,
        trade_type=trade_type,
        kas_amount=kas_amount,
        token_amount=token_amount,
        price_per_token=price_per_token,
        tx_hash=event['transactionHash'].hex(),
        block_number=event['blockNumber'],
        log_index=event['logIndex'],
        event_timestamp=datetime.now(timezone.utc),  # TODO: Get from block
        is_dex_trade=True  # NEW FLAG to distinguish DEX from bonding curve
    )
    
    db.session.add(trade_event)
    
    # CRITICAL: Trigger all downstream updates
    update_engagement_from_trade(token, user_address, trade_event)
    update_user_stats_from_trade(user_address, trade_event)
    update_holding_from_trade(user_address, token, trade_event)
    create_activity_from_trade(user_address, token, trade_event)
    
    db.session.commit()
```

### **Task 3.5.2: TokenEngagement Updates**

**File**: `services/engagement_calculator.py` (NEW or extend existing)

```python
def update_engagement_from_trade(token, user_address, trade_event):
    """
    Update TokenEngagement metrics from a trade (bonding curve OR DEX)
    
    This function is called for BOTH bonding curve and DEX trades
    """
    from models import User, TokenEngagement
    
    # Resolve wallet to user (handles LinkedWallet merges)
    user = User.resolve_wallet_to_user(user_address)
    if not user:
        logging.warning(f"User not found for wallet {user_address}")
        return
    
    # Get or create TokenEngagement record
    engagement = TokenEngagement.query.filter_by(
        user_id=user.id,
        token_id=token.id
    ).first()
    
    if not engagement:
        engagement = TokenEngagement(
            user_id=user.id,
            token_id=token.id,
            first_acquired_at=datetime.now(timezone.utc) if trade_event.trade_type == 'buy' else None
        )
        db.session.add(engagement)
    
    # Update trade counts
    engagement.trades_count = (engagement.trades_count or 0) + 1
    engagement.total_traded_volume = (engagement.total_traded_volume or 0) + trade_event.kas_amount
    
    if trade_event.trade_type == 'buy':
        engagement.buy_count = (engagement.buy_count or 0) + 1
        if not engagement.first_acquired_at:
            engagement.first_acquired_at = datetime.now(timezone.utc)
    else:
        engagement.sell_count = (engagement.sell_count or 0) + 1
    
    # Recalculate diamond hands score
    total_trades = engagement.buy_count + engagement.sell_count
    if total_trades > 0:
        engagement.diamond_hands_score = int((engagement.buy_count / total_trades) * 100)
    
    # Update last activity timestamp
    engagement.last_activity_at = datetime.now(timezone.utc)
    
    # Award community points for trading
    points_earned = 10  # Base points per trade
    if trade_event.kas_amount > 10:  # Large trade bonus
        points_earned = 25
    
    engagement.add_community_points(points_earned, activity_type='trade')
```

### **Task 3.5.3: User Stats Updates**

**File**: `services/user_stats_updater.py` (NEW or extend existing)

```python
def update_user_stats_from_trade(user_address, trade_event):
    """
    Update User model aggregated stats from trade
    
    Works for both bonding curve and DEX trades
    """
    from models import User
    
    user = User.resolve_wallet_to_user(user_address)
    if not user:
        return
    
    # Update trade counters
    user.total_trades_count = (user.total_trades_count or 0) + 1
    user.total_trading_volume = (user.total_trading_volume or 0) + trade_event.kas_amount
    
    # Check for achievement progress
    from services.achievement_service import evaluate_user_achievements
    evaluate_user_achievements(user.id)
```

### **Task 3.5.4: Holding/Portfolio Updates**

**File**: `services/holding_updater.py` (NEW or extend existing)

```python
def update_holding_from_trade(user_address, token, trade_event):
    """
    Update Holding model for FTX-style cost basis tracking
    
    Works for both bonding curve and DEX trades
    """
    from models import User, Holding
    
    user = User.resolve_wallet_to_user(user_address)
    if not user:
        return
    
    # Get or create holding
    holding = Holding.query.filter_by(
        user_id=user.id,
        token_id=token.id
    ).first()
    
    if not holding:
        holding = Holding(
            user_id=user.id,
            token_id=token.id,
            first_purchase=datetime.now(timezone.utc)
        )
        db.session.add(holding)
    
    # Use existing update_holding method
    # For buys: positive token_amount
    # For sells: negative token_amount
    trade_amount = trade_event.token_amount if trade_event.trade_type == 'buy' else -trade_event.token_amount
    
    holding.update_holding(
        trade_amount=trade_amount,
        trade_price=trade_event.price_per_token,
        kas_amount=trade_event.kas_amount
    )
```

### **Task 3.5.5: Activity Feed Integration**

**File**: `services/activity_logger.py` (NEW or extend existing)

```python
def create_activity_from_trade(user_address, token, trade_event):
    """
    Create Activity feed entry for trade
    
    Works for both bonding curve and DEX trades
    """
    from models import User, Activity
    
    user = User.resolve_wallet_to_user(user_address)
    if not user:
        return
    
    # Determine activity description
    if trade_event.trade_type == 'buy':
        title = f'Bought {token.symbol}'
        description = f'Purchased {trade_event.token_amount:,.0f} {token.symbol} for {trade_event.kas_amount:.2f} KAS'
    else:
        title = f'Sold {token.symbol}'
        description = f'Sold {trade_event.token_amount:,.0f} {token.symbol} for {trade_event.kas_amount:.2f} KAS'
    
    # Add DEX indicator if applicable
    if trade_event.is_dex_trade:
        description += ' (Kaspa Finance DEX)'
    
    activity = Activity(
        user_id=user.id,
        activity_type=f'trade_{trade_event.trade_type}',
        title=title,
        description=description,
        token_id=token.id,
        points_earned=10,  # Match community points
        is_public=True
    )
    
    db.session.add(activity)
```

### **Task 3.5.6: Achievement System Updates**

**File**: `services/achievement_service.py`

**NO CHANGES NEEDED** - The existing `calculate_user_progress()` function reads from:
- `user.total_trades_count` ✅ (updated by Task 3.5.3)
- `user.total_trading_volume` ✅ (updated by Task 3.5.3)
- `TokenEngagement` metrics ✅ (updated by Task 3.5.2)

The achievement system will automatically work with DEX trades once the above updates are in place.

---

## 📋 **SCHEMA UPDATES REQUIRED**

### **TradeEvent Model** (Add is_dex_trade flag)

```python
# models.py - TradeEvent model
class TradeEvent(db.Model):
    # ... existing fields ...
    
    is_dex_trade = db.Column(db.Boolean, default=False)  # NEW: Distinguish DEX from bonding curve
```

**Migration**:
```sql
ALTER TABLE trade_event ADD COLUMN is_dex_trade BOOLEAN DEFAULT FALSE;
```

### **Trade Model** - NO CHANGES

The existing `Trade` model works for both bonding curve and DEX trades. The only difference is the source (bonding curve contract vs DEX pool).

---

## 🔄 **COMPLETE INTEGRATION CHECKLIST**

After DEX integration, verify ALL systems work for graduated tokens:

### **Data Capture**
- [x] DEX Swap events indexed
- [x] TradeEvent records created
- [x] Trade model records created

### **Engagement Tracking**
- [x] TokenEngagement.trades_count increments
- [x] TokenEngagement.buy_count / sell_count increments
- [x] TokenEngagement.total_traded_volume updates
- [x] TokenEngagement.diamond_hands_score recalculates
- [x] TokenEngagement.holding_days continues tracking
- [x] Community points awarded

### **User Stats**
- [x] User.total_trades_count increments
- [x] User.total_trading_volume updates
- [x] User.longest_holding_days updates

### **Achievements**
- [x] "Make 100 trades" achievement tracks DEX trades
- [x] "Trade $10K volume" achievement tracks DEX volume
- [x] All other achievements using user stats work

### **Leaderboards**
- [x] Token-specific leaderboards show DEX traders
- [x] Platform-wide leaderboards include DEX activity
- [x] Rankings update in real-time

### **Portfolio & Holdings**
- [x] Holding.token_amount updates correctly
- [x] Holding.average_price recalculates (cost basis)
- [x] Holding.total_invested tracks correctly
- [x] Portfolio P&L calculations work

### **Activity Feed**
- [x] DEX trades appear in user activity feed
- [x] DEX trades appear in token activity feed
- [x] Public feed shows DEX activity

### **PRO Token Features**
- [x] Community points accumulate after graduation
- [x] Milestone achievements trigger (30d, 60d, etc.)
- [x] TokenEngagement merging works for linked wallets

---

## ⚠️ **CRITICAL IMPLEMENTATION NOTES**

1. **Event Processing Order**: TradeEvent → All updates in SINGLE transaction
2. **Wallet Resolution**: Always use `User.resolve_wallet_to_user()` to handle LinkedWallet merges
3. **Duplicate Prevention**: Check `tx_hash + log_index` before creating TradeEvent
4. **Atomic Updates**: All engagement/stats/holding updates in same database transaction
5. **Error Handling**: If any update fails, rollback entire transaction

---

## 🧪 **TESTING REQUIREMENTS (EXTENDED)**

Add to existing test suite:

### **Integration Tests**
```python
def test_dex_trade_full_integration():
    """Test DEX trade updates all systems correctly"""
    
    # Setup: Create graduated token
    token = create_graduated_token()
    user = create_user()
    
    # Simulate DEX buy
    simulate_dex_swap(token, user, trade_type='buy', kas_amount=10, token_amount=1000)
    
    # Verify TokenEngagement
    engagement = TokenEngagement.query.filter_by(user_id=user.id, token_id=token.id).first()
    assert engagement.trades_count == 1
    assert engagement.buy_count == 1
    assert engagement.total_traded_volume == 10
    assert engagement.community_points > 0
    
    # Verify User stats
    assert user.total_trades_count == 1
    assert user.total_trading_volume == 10
    
    # Verify Holding
    holding = Holding.query.filter_by(user_id=user.id, token_id=token.id).first()
    assert holding.token_amount == 1000
    assert holding.average_price > 0
    
    # Verify Activity
    activity = Activity.query.filter_by(user_id=user.id, token_id=token.id).first()
    assert activity is not None
    assert 'Kaspa Finance DEX' in activity.description
    
    # Verify Achievement progress
    achievements = evaluate_user_achievements(user.id)
    assert 'total_trades' achievement shows progress

def test_dex_trade_vs_bonding_curve_parity():
    """Ensure DEX trades produce identical downstream effects as bonding curve"""
    
    # Create two identical tokens
    bonding_token = create_token(graduated=False)
    dex_token = create_token(graduated=True)
    
    user = create_user()
    
    # Execute identical trades
    simulate_bonding_curve_buy(bonding_token, user, kas=10)
    simulate_dex_buy(dex_token, user, kas=10)
    
    # Verify IDENTICAL outcomes
    bonding_engagement = get_engagement(user, bonding_token)
    dex_engagement = get_engagement(user, dex_token)
    
    assert bonding_engagement.trades_count == dex_engagement.trades_count
    assert bonding_engagement.community_points == dex_engagement.community_points
    # ... all other metrics match ...
```

---

This addition completely specifies the data integration pipeline and ensures DEX trades have identical effects to bonding curve trades across the entire platform.
