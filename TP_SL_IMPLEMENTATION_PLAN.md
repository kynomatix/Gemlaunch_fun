# Take Profit / Stop Loss Implementation Plan

**Status**: Future Feature - Not Yet Implemented  
**Priority**: Post-Graduation Fix  
**Estimated Effort**: 2-3 weeks  
**Dependencies**: Trade indexer, Cost basis calculation (✅ already working)

---

## Executive Summary

This document outlines the implementation plan for adding Take Profit (TP) and Stop Loss (SL) functionality to the gemlaunch.fun platform. The system will allow users to set conditional sell orders based on percentage gains/losses from their cost basis, with visual indicators on trading charts and automatic execution via backend oracle monitoring.

**Key Features:**
- Percentage-based TP/SL (e.g., "Sell at +50%" or "Stop loss at -20%")
- Visual chart lines showing TP/SL levels
- Cost basis integration (already working)
- User pays gas (oracle submits transaction on behalf)
- Real-time monitoring and execution
- Multiple orders per token per user
- Mobile-friendly UI

---

## Table of Contents

1. [User Experience](#user-experience)
2. [Architecture Overview](#architecture-overview)
3. [Cost Basis Integration](#cost-basis-integration)
4. [Database Schema](#database-schema)
5. [Backend Services](#backend-services)
6. [Frontend Components](#frontend-components)
7. [Chart Integration](#chart-integration)
8. [Security Model](#security-model)
9. [Implementation Phases](#implementation-phases)
10. [Testing Strategy](#testing-strategy)

---

## 1. User Experience

### 1.1 User Flow

```
Step 1: User views their token holdings (portfolio page)
   ↓
Step 2: User clicks "Set TP/SL" button on token card
   ↓
Step 3: Modal opens showing:
   - Current price: $0.051
   - Cost basis: $0.034 (calculated)
   - Current P&L: +50% 🟢
   ↓
Step 4: User sets conditions:
   ┌─────────────────────────────────────┐
   │ Take Profit: [+100%] = $0.068       │
   │ Amount: [50%] of holdings           │
   ├─────────────────────────────────────┤
   │ Stop Loss: [-30%] = $0.024          │
   │ Amount: [100%] of holdings          │
   └─────────────────────────────────────┘
   ↓
Step 5: User signs authorization (EIP-712)
   - No tokens escrowed
   - Grants approval for specific amounts
   ↓
Step 6: Orders appear on chart as colored lines
   - Green line at +100% (Take Profit)
   - Red line at -30% (Stop Loss)
   ↓
Step 7: Backend monitors price every 10s
   ↓
Step 8: When condition met → Oracle executes sell
   ↓
Step 9: User pays gas from their wallet
   ↓
Step 10: Notification: "✅ Take Profit executed at $0.070 (+106%)"
```

### 1.2 UI Mockup - TP/SL Modal

```
┌─────────────────────────────────────────────────────────┐
│  Set Take Profit / Stop Loss - $KTR                  ×  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Current Position                                       │
│  ┌───────────────────────────────────────────────────┐ │
│  │ Holdings:        1,234,567 KTR                    │ │
│  │ Cost Basis:      $0.034 per token                 │ │
│  │ Current Price:   $0.051 per token                 │ │
│  │ Total P&L:       +50.0% ($20,917)  🟢             │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  Take Profit Orders (Sell when price goes up)          │
│  ┌───────────────────────────────────────────────────┐ │
│  │ [+] Add Take Profit                               │ │
│  │                                                    │ │
│  │ TP #1                                          [×] │ │
│  │  ┌──────────────┬──────────────┬────────────────┐ │ │
│  │  │ Gain %       │ Target Price │ Amount to Sell │ │ │
│  │  ├──────────────┼──────────────┼────────────────┤ │ │
│  │  │ [+100  %]    │ $0.068       │ [50   %] 🔄    │ │ │
│  │  │              │              │ (617,283 KTR)  │ │ │
│  │  └──────────────┴──────────────┴────────────────┘ │ │
│  │                                                    │ │
│  │ TP #2                                          [×] │ │
│  │  ┌──────────────┬──────────────┬────────────────┐ │ │
│  │  │ [+200  %]    │ $0.102       │ [25   %] 🔄    │ │ │
│  │  │              │              │ (308,641 KTR)  │ │ │
│  │  └──────────────┴──────────────┴────────────────┘ │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  Stop Loss Orders (Sell when price goes down)          │
│  ┌───────────────────────────────────────────────────┐ │
│  │ [+] Add Stop Loss                                 │ │
│  │                                                    │ │
│  │ SL #1                                          [×] │ │
│  │  ┌──────────────┬──────────────┬────────────────┐ │ │
│  │  │ Loss %       │ Stop Price   │ Amount to Sell │ │ │
│  │  ├──────────────┼──────────────┼────────────────┤ │ │
│  │  │ [-30   %]    │ $0.024       │ [100  %] 🔄    │ │ │
│  │  │              │              │ (1,234,567 KTR)│ │ │
│  │  └──────────────┴──────────────┴────────────────┘ │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  Execution Settings                                    │
│  ┌───────────────────────────────────────────────────┐ │
│  │ ☑ Auto-execute when triggered                     │ │
│  │ ☑ Send notification on execution                  │ │
│  │ Gas Payment: From my wallet (estimated 0.02 KAS)  │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  [Cancel]                      [Sign & Create Orders]  │
└─────────────────────────────────────────────────────────┘
```

### 1.3 Chart Visualization

```
Price Chart with TP/SL Lines
┌─────────────────────────────────────────────────────────┐
│  $KTR / KAS                                    1H  1D  │
│                                                         │
│  $0.102 ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌ TP +200% (25%) 🟢     │
│         │                                               │
│  $0.068 ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌ TP +100% (50%) 🟢     │
│         │           ╱╲                                  │
│  $0.051 │      ╱───╯  ╲                                │
│         │   ╱─╯         ╲_  ← Current Price            │
│  $0.034 ━━━━━━━━━━━━━━━━━━━━━━━━━ Cost Basis 📍       │
│         │                                               │
│  $0.024 ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌ SL -30% (100%) 🔴     │
│         │                                               │
│         └───────────────────────────────────────────>  │
│         10:00    11:00    12:00    13:00    14:00      │
└─────────────────────────────────────────────────────────┘

Legend:
━━━━━  Cost Basis (blue solid line)
╌╌╌╌╌  Take Profit (green dashed line)
╌╌╌╌╌  Stop Loss (red dashed line)
```

### 1.4 Active Orders Display

On token detail page, show active orders in a collapsible panel:

```
┌─────────────────────────────────────────────────────────┐
│  Active TP/SL Orders (3)                             ▼  │
├─────────────────────────────────────────────────────────┤
│  🟢 Take Profit +100% → $0.068                          │
│     Sell 617,283 KTR (50% of holdings)                  │
│     Created: 2h ago  •  Status: Active  [Cancel]        │
├─────────────────────────────────────────────────────────┤
│  🟢 Take Profit +200% → $0.102                          │
│     Sell 308,641 KTR (25% of holdings)                  │
│     Created: 2h ago  •  Status: Active  [Cancel]        │
├─────────────────────────────────────────────────────────┤
│  🔴 Stop Loss -30% → $0.024                             │
│     Sell 1,234,567 KTR (100% of holdings)               │
│     Created: 2h ago  •  Status: Active  [Cancel]        │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Architecture Overview

### 2.1 System Components

```
┌─────────────┐
│   Browser   │  User creates TP/SL order
│   (User)    │  Signs EIP-712 authorization
└──────┬──────┘
       │ POST /api/orders/create
       ↓
┌─────────────────────┐
│   Flask Backend     │  
│ ─────────────────── │
│ • Verify signature  │  Stores order in database
│ • Store order       │  Returns order ID
│ • Approve tokens    │
└──────┬──────────────┘
       │
       ↓
┌─────────────────────┐
│   PostgreSQL DB     │  
│ ─────────────────── │
│ conditional_orders  │  Stores all TP/SL orders
│ user_positions      │  Stores cost basis
└──────┬──────────────┘
       │
       │ Every 10 seconds
       ↓
┌─────────────────────┐
│  TP/SL Monitor      │  
│  (Background Job)   │  Checks if conditions met
│ ─────────────────── │
│ • Fetch active      │  For each active order:
│   orders            │  1. Get current price
│ • Check conditions  │  2. Compare to trigger
│ • Execute if met    │  3. Execute sell if met
└──────┬──────────────┘
       │ Condition met!
       ↓
┌─────────────────────┐
│   Oracle Wallet     │  
│ ─────────────────── │  Submits transaction
│ • Build sell tx     │  User's wallet pays gas
│ • Sign with proof   │  Oracle relays tx
│ • Submit to chain   │
└──────┬──────────────┘
       │
       ↓
┌─────────────────────┐
│  Bonding Curve      │  
│  Smart Contract     │  Executes sell
└─────────────────────┘  Sends KAS to user
```

### 2.2 Gas Payment Model

**Key Principle:** User pays gas, oracle relays transaction.

**How it works:**
1. User pre-approves tokens to BondingCurvePool (standard approval)
2. User signs EIP-712 order authorization (off-chain)
3. When triggered, oracle builds transaction FROM user's address
4. Oracle submits transaction with user's signature
5. User's wallet pays gas automatically
6. No KAS needs to be held by oracle for gas

**Alternative (Simpler):** User pre-pays small KAS amount to oracle escrow
- User deposits 1 KAS to cover gas for 10-20 executions
- Oracle deducts gas from escrow balance
- User can withdraw unused balance anytime

---

## 3. Cost Basis Integration

### 3.1 Current Cost Basis System (Already Working)

The platform already calculates cost basis per token per user:

```python
# Example from existing codebase
def get_user_cost_basis(wallet_address, token_address):
    """
    Returns average cost per token based on all buys
    """
    buys = TradeEvent.query.filter_by(
        trader=wallet_address.lower(),
        token_address=token_address.lower(),
        is_buy=True
    ).all()
    
    total_tokens = sum(buy.token_amount for buy in buys)
    total_kas_spent = sum(buy.kas_amount for buy in buys)
    
    if total_tokens == 0:
        return 0
    
    return total_kas_spent / total_tokens  # KAS per token
```

### 3.2 TP/SL Calculation from Cost Basis

**Formula:**
```python
cost_basis = get_user_cost_basis(wallet, token)  # e.g., 0.034 KAS
tp_percentage = 100  # +100%
sl_percentage = -30  # -30%

tp_trigger_price = cost_basis * (1 + tp_percentage / 100)
# = 0.034 * (1 + 100/100) = 0.034 * 2 = 0.068 KAS

sl_trigger_price = cost_basis * (1 + sl_percentage / 100)
# = 0.034 * (1 - 30/100) = 0.034 * 0.70 = 0.0238 KAS
```

**Validation:**
```python
def validate_tp_sl_order(user, token, tp_pct=None, sl_pct=None):
    """Ensure TP/SL orders are valid"""
    
    # Get cost basis
    cost_basis = get_user_cost_basis(user.wallet_address, token.contract_address)
    
    if cost_basis == 0:
        raise ValueError("No position in this token")
    
    if tp_pct is not None:
        if tp_pct <= 0:
            raise ValueError("Take profit must be positive %")
        if tp_pct < 5:
            raise ValueError("Take profit must be at least +5%")
    
    if sl_pct is not None:
        if sl_pct >= 0:
            raise ValueError("Stop loss must be negative %")
        if sl_pct < -95:
            raise ValueError("Stop loss cannot be below -95%")
    
    return True
```

### 3.3 Real-Time P&L Display

**Current P&L Calculation:**
```python
cost_basis = get_user_cost_basis(wallet, token)
current_price = get_current_token_price(token)
pnl_percentage = ((current_price - cost_basis) / cost_basis) * 100

# Example:
# cost_basis = 0.034
# current_price = 0.051
# pnl = ((0.051 - 0.034) / 0.034) * 100 = +50%
```

**Display on UI:**
```html
<div class="position-summary">
    <span class="label">Cost Basis:</span>
    <span class="value">$0.034</span>
    
    <span class="label">Current Price:</span>
    <span class="value">$0.051</span>
    
    <span class="label">P&L:</span>
    <span class="value {{ 'profit' if pnl > 0 else 'loss' }}">
        {{ '+' if pnl > 0 else '' }}{{ pnl|round(1) }}%
    </span>
</div>
```

---

## 4. Database Schema

### 4.1 New Table: conditional_orders

```python
class ConditionalOrder(db.Model):
    __tablename__ = 'conditional_orders'
    
    # Primary key
    id = db.Column(db.Integer, primary_key=True)
    
    # Order identification
    order_type = db.Column(db.String(20), nullable=False)  # 'TAKE_PROFIT' or 'STOP_LOSS'
    
    # User & token
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    token_id = db.Column(db.Integer, db.ForeignKey('tokens.id'), nullable=False)
    wallet_address = db.Column(db.String(42), nullable=False, index=True)
    token_address = db.Column(db.String(42), nullable=False, index=True)
    
    # Trigger conditions (stored as percentage from cost basis)
    trigger_percentage = db.Column(db.Float, nullable=False)  # e.g., 100.0 for +100%, -30.0 for -30%
    trigger_price = db.Column(db.Numeric(20, 10), nullable=False)  # Calculated absolute price
    
    # Amount to sell
    amount_tokens = db.Column(db.Numeric(30, 0), nullable=False)  # Exact token amount
    amount_percentage = db.Column(db.Float)  # % of holdings (for display)
    
    # Cost basis snapshot (for reference)
    cost_basis_at_creation = db.Column(db.Numeric(20, 10), nullable=False)
    
    # Status tracking
    status = db.Column(db.String(20), default='active', index=True)
    # Statuses: 'active', 'triggered', 'executing', 'executed', 'cancelled', 'failed'
    
    # Execution tracking
    triggered_at = db.Column(db.DateTime)
    executed_at = db.Column(db.DateTime)
    execution_tx_hash = db.Column(db.String(66))
    execution_price = db.Column(db.Numeric(20, 10))  # Actual price when executed
    kas_received = db.Column(db.Numeric(20, 10))
    
    # Authorization signature (EIP-712)
    signature = db.Column(db.Text, nullable=False)
    signature_deadline = db.Column(db.DateTime, nullable=False)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Failure tracking
    failure_reason = db.Column(db.Text)
    retry_count = db.Column(db.Integer, default=0)
    
    # Relationships
    user = db.relationship('User', backref='conditional_orders')
    token = db.relationship('Token', backref='conditional_orders')
```

### 4.2 Indexes for Performance

```sql
CREATE INDEX idx_conditional_orders_active ON conditional_orders(status, token_address) 
    WHERE status = 'active';

CREATE INDEX idx_conditional_orders_user_token ON conditional_orders(wallet_address, token_address, status);

CREATE INDEX idx_conditional_orders_created ON conditional_orders(created_at DESC);
```

---

## 5. Backend Services

### 5.1 Order Creation Service

**File:** `services/conditional_order_service.py`

```python
class ConditionalOrderService:
    
    @staticmethod
    def create_order(
        user,
        token,
        order_type: str,  # 'TAKE_PROFIT' or 'STOP_LOSS'
        trigger_percentage: float,
        amount_percentage: float,
        signature: str,
        signature_deadline: int
    ):
        """Create a new TP/SL order"""
        
        # 1. Validate inputs
        if order_type not in ['TAKE_PROFIT', 'STOP_LOSS']:
            raise ValueError("Invalid order type")
        
        if order_type == 'TAKE_PROFIT' and trigger_percentage <= 0:
            raise ValueError("Take profit must be positive %")
        
        if order_type == 'STOP_LOSS' and trigger_percentage >= 0:
            raise ValueError("Stop loss must be negative %")
        
        if amount_percentage <= 0 or amount_percentage > 100:
            raise ValueError("Amount must be 1-100%")
        
        # 2. Get user's cost basis
        cost_basis = get_user_cost_basis(user.wallet_address, token.contract_address)
        if cost_basis == 0:
            raise ValueError("No position in this token")
        
        # 3. Calculate trigger price
        trigger_price = cost_basis * (1 + trigger_percentage / 100)
        
        # 4. Calculate exact token amount
        user_balance = get_user_token_balance(user.wallet_address, token.contract_address)
        amount_tokens = int(user_balance * amount_percentage / 100)
        
        if amount_tokens == 0:
            raise ValueError("Insufficient balance")
        
        # 5. Verify signature
        ConditionalOrderService._verify_signature(
            user.wallet_address,
            token.contract_address,
            order_type,
            trigger_price,
            amount_tokens,
            signature_deadline,
            signature
        )
        
        # 6. Create order
        order = ConditionalOrder(
            user_id=user.id,
            token_id=token.id,
            wallet_address=user.wallet_address.lower(),
            token_address=token.contract_address.lower(),
            order_type=order_type,
            trigger_percentage=trigger_percentage,
            trigger_price=trigger_price,
            amount_tokens=amount_tokens,
            amount_percentage=amount_percentage,
            cost_basis_at_creation=cost_basis,
            signature=signature,
            signature_deadline=datetime.fromtimestamp(signature_deadline),
            status='active'
        )
        
        db.session.add(order)
        db.session.commit()
        
        logger.info(f"Created {order_type} order #{order.id} for {user.wallet_address}")
        return order
    
    @staticmethod
    def _verify_signature(wallet, token, order_type, trigger_price, amount, deadline, signature):
        """Verify EIP-712 signature for order authorization"""
        
        # EIP-712 domain
        domain = {
            'name': 'GemLaunch TP/SL',
            'version': '1',
            'chainId': 167012,  # Kasplex testnet
            'verifyingContract': token
        }
        
        # Message types
        types = {
            'ConditionalOrder': [
                {'name': 'token', 'type': 'address'},
                {'name': 'orderType', 'type': 'string'},
                {'name': 'triggerPrice', 'type': 'uint256'},
                {'name': 'amount', 'type': 'uint256'},
                {'name': 'deadline', 'type': 'uint256'}
            ]
        }
        
        # Message data
        message = {
            'token': token,
            'orderType': order_type,
            'triggerPrice': int(trigger_price * 1e18),
            'amount': amount,
            'deadline': deadline
        }
        
        # Verify
        recovered_address = Account.recover_typed_data(domain, types, message, signature)
        
        if recovered_address.lower() != wallet.lower():
            raise ValueError("Invalid signature")
        
        return True
    
    @staticmethod
    def cancel_order(order_id, user):
        """Cancel an active order"""
        order = ConditionalOrder.query.get(order_id)
        
        if not order:
            raise ValueError("Order not found")
        
        if order.user_id != user.id:
            raise ValueError("Not authorized")
        
        if order.status != 'active':
            raise ValueError("Order not active")
        
        order.status = 'cancelled'
        order.updated_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Cancelled order #{order_id}")
        return order
```

### 5.2 TP/SL Monitor Service

**File:** `services/tpsl_monitor.py`

```python
from apscheduler.schedulers.background import BackgroundScheduler
import logging

class TPSLMonitor:
    def __init__(self, web3_service):
        self.web3_service = web3_service
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(
            func=self.check_all_orders,
            trigger="interval",
            seconds=10,  # Check every 10 seconds
            id='tpsl_monitor',
            name='TP/SL Order Monitor',
            replace_existing=True
        )
        logger.info("TP/SL Monitor initialized")
    
    def start(self):
        """Start the monitoring service"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("TP/SL Monitor started - checking every 10 seconds")
    
    def stop(self):
        """Stop the monitoring service"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("TP/SL Monitor stopped")
    
    def check_all_orders(self):
        """Check all active orders for trigger conditions"""
        try:
            # Get all active orders
            active_orders = ConditionalOrder.query.filter_by(status='active').all()
            
            logger.debug(f"Checking {len(active_orders)} active TP/SL orders")
            
            for order in active_orders:
                try:
                    self._check_order(order)
                except Exception as e:
                    logger.error(f"Error checking order #{order.id}: {e}")
        
        except Exception as e:
            logger.error(f"Error in TP/SL monitor: {e}")
    
    def _check_order(self, order):
        """Check if a single order should be executed"""
        
        # Get current price
        current_price = get_current_token_price_from_chain(order.token_address)
        
        # Check if condition is met
        triggered = False
        
        if order.order_type == 'TAKE_PROFIT':
            # Trigger if current price >= trigger price
            if current_price >= order.trigger_price:
                triggered = True
                logger.info(f"TP order #{order.id} triggered: ${current_price} >= ${order.trigger_price}")
        
        elif order.order_type == 'STOP_LOSS':
            # Trigger if current price <= trigger price
            if current_price <= order.trigger_price:
                triggered = True
                logger.info(f"SL order #{order.id} triggered: ${current_price} <= ${order.trigger_price}")
        
        if triggered:
            self._execute_order(order, current_price)
    
    def _execute_order(self, order, current_price):
        """Execute a triggered order"""
        
        # Update status
        order.status = 'executing'
        order.triggered_at = datetime.utcnow()
        db.session.commit()
        
        try:
            # Execute sell transaction
            tx_hash = self._submit_sell_transaction(order)
            
            # Wait for confirmation
            receipt = self.web3_service.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if receipt['status'] == 1:
                # Calculate KAS received from logs
                kas_received = self._extract_kas_from_receipt(receipt)
                
                # Update order
                order.status = 'executed'
                order.executed_at = datetime.utcnow()
                order.execution_tx_hash = tx_hash
                order.execution_price = current_price
                order.kas_received = kas_received
                db.session.commit()
                
                logger.info(f"✅ Order #{order.id} executed: {tx_hash}")
                
                # Send notification to user
                self._send_notification(order, kas_received)
            
            else:
                # Transaction failed
                order.status = 'failed'
                order.failure_reason = 'Transaction reverted'
                order.retry_count += 1
                db.session.commit()
                
                logger.error(f"❌ Order #{order.id} execution failed")
        
        except Exception as e:
            # Execution error
            order.status = 'failed'
            order.failure_reason = str(e)
            order.retry_count += 1
            db.session.commit()
            
            logger.error(f"Error executing order #{order.id}: {e}")
    
    def _submit_sell_transaction(self, order):
        """Submit sell transaction on behalf of user"""
        
        # Build transaction
        bonding_pool = self.web3_service.get_bonding_pool_contract(order.token_address)
        
        # Calculate minimum KAS out (5% slippage)
        estimated_kas = bonding_pool.functions.getSellQuote(order.amount_tokens).call()
        min_kas_out = int(estimated_kas * 0.95)
        
        # Build sell transaction FROM user's wallet
        tx_data = bonding_pool.functions.sell(
            order.amount_tokens,
            min_kas_out
        ).build_transaction({
            'from': order.wallet_address,
            'gas': 300000,
            'gasPrice': self.web3_service.w3.eth.gas_price,
            'nonce': self.web3_service.w3.eth.get_transaction_count(order.wallet_address)
        })
        
        # Oracle signs and submits (user pays gas)
        # Note: This requires user to have approved the bonding pool
        signed_tx = self.web3_service.oracle_account.sign_transaction(tx_data)
        tx_hash = self.web3_service.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        return tx_hash.hex()
    
    def _extract_kas_from_receipt(self, receipt):
        """Extract KAS received from transaction logs"""
        # Parse TokensSold event to get KAS amount
        # Implementation depends on event ABI
        return 0  # Placeholder
    
    def _send_notification(self, order, kas_received):
        """Send notification to user about execution"""
        # TODO: Implement notification system
        # - Email
        # - In-app notification
        # - Browser push notification
        pass
```

### 5.3 Price Fetching

```python
def get_current_token_price_from_chain(token_address):
    """Get current token price from bonding curve"""
    web3_service = get_web3_service()
    bonding_pool = web3_service.get_bonding_pool_contract(token_address)
    
    kas_reserve = bonding_pool.functions.virtualKasReserve().call()
    token_reserve = bonding_pool.functions.virtualTokenReserve().call()
    
    if token_reserve == 0:
        return 0
    
    # Price = KAS per token
    price = kas_reserve / token_reserve
    price_wei = web3_service.w3.from_wei(price, 'ether')
    
    return float(price_wei)
```

---

## 6. Frontend Components

### 6.1 TP/SL Modal Component

**File:** `static/js/tpsl_modal.js`

```javascript
class TPSLModal {
    constructor(tokenAddress, userWallet) {
        this.tokenAddress = tokenAddress;
        this.userWallet = userWallet;
        this.orders = {
            takeProfits: [],
            stopLosses: []
        };
    }
    
    async open() {
        // Fetch user position data
        const position = await this.fetchPosition();
        
        // Render modal
        this.render(position);
        
        // Setup event listeners
        this.setupListeners();
    }
    
    async fetchPosition() {
        const response = await fetch(`/api/user/position/${this.tokenAddress}`);
        return await response.json();
        // Returns: { holdings, costBasis, currentPrice, pnl }
    }
    
    render(position) {
        const html = `
            <div class="tpsl-modal">
                <div class="position-summary">
                    <h3>Current Position</h3>
                    <div class="stat">
                        <span>Holdings:</span>
                        <span>${position.holdings.toLocaleString()} tokens</span>
                    </div>
                    <div class="stat">
                        <span>Cost Basis:</span>
                        <span>$${position.costBasis.toFixed(6)}</span>
                    </div>
                    <div class="stat">
                        <span>Current Price:</span>
                        <span>$${position.currentPrice.toFixed(6)}</span>
                    </div>
                    <div class="stat ${position.pnl >= 0 ? 'profit' : 'loss'}">
                        <span>P&L:</span>
                        <span>${position.pnl >= 0 ? '+' : ''}${position.pnl.toFixed(1)}%</span>
                    </div>
                </div>
                
                <div class="orders-section">
                    <h3>Take Profit Orders</h3>
                    <button class="add-tp-btn">+ Add Take Profit</button>
                    <div id="tp-orders-container"></div>
                </div>
                
                <div class="orders-section">
                    <h3>Stop Loss Orders</h3>
                    <button class="add-sl-btn">+ Add Stop Loss</button>
                    <div id="sl-orders-container"></div>
                </div>
                
                <div class="modal-actions">
                    <button class="cancel-btn">Cancel</button>
                    <button class="submit-btn">Sign & Create Orders</button>
                </div>
            </div>
        `;
        
        // Append to DOM and show
        document.body.insertAdjacentHTML('beforeend', html);
    }
    
    addTakeProfitOrder() {
        const orderHtml = `
            <div class="order-row" data-order-type="TP">
                <input type="number" 
                       class="tp-percentage" 
                       placeholder="Gain %" 
                       min="5" 
                       step="5">
                <input type="number" 
                       class="tp-price" 
                       placeholder="Target $" 
                       readonly>
                <input type="number" 
                       class="tp-amount" 
                       placeholder="% to sell" 
                       min="1" 
                       max="100" 
                       step="1">
                <button class="remove-order">×</button>
            </div>
        `;
        
        document.getElementById('tp-orders-container')
            .insertAdjacentHTML('beforeend', orderHtml);
        
        this.setupOrderListeners();
    }
    
    calculateTargetPrice(costBasis, percentage) {
        return costBasis * (1 + percentage / 100);
    }
    
    async signOrders() {
        // Gather all orders
        const allOrders = [...this.orders.takeProfits, ...this.orders.stopLosses];
        
        if (allOrders.length === 0) {
            alert('Please add at least one order');
            return;
        }
        
        // Sign each order with EIP-712
        const signatures = [];
        
        for (const order of allOrders) {
            const signature = await this.signOrder(order);
            signatures.push({
                ...order,
                signature
            });
        }
        
        // Submit to backend
        await this.submitOrders(signatures);
    }
    
    async signOrder(order) {
        const domain = {
            name: 'GemLaunch TP/SL',
            version: '1',
            chainId: 167012,
            verifyingContract: this.tokenAddress
        };
        
        const types = {
            ConditionalOrder: [
                { name: 'token', type: 'address' },
                { name: 'orderType', type: 'string' },
                { name: 'triggerPrice', type: 'uint256' },
                { name: 'amount', type: 'uint256' },
                { name: 'deadline', type: 'uint256' }
            ]
        };
        
        const deadline = Math.floor(Date.now() / 1000) + 86400 * 30; // 30 days
        
        const message = {
            token: this.tokenAddress,
            orderType: order.type,
            triggerPrice: ethers.utils.parseEther(order.triggerPrice.toString()),
            amount: order.amount,
            deadline: deadline
        };
        
        const signature = await window.ethereum.request({
            method: 'eth_signTypedData_v4',
            params: [this.userWallet, JSON.stringify({ domain, types, message })]
        });
        
        return { signature, deadline };
    }
    
    async submitOrders(orders) {
        const response = await fetch('/api/orders/create-batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ orders })
        });
        
        if (response.ok) {
            alert('Orders created successfully!');
            this.close();
            window.location.reload();
        } else {
            const error = await response.json();
            alert(`Error: ${error.message}`);
        }
    }
}
```

### 6.2 Chart Integration

**File:** `static/js/chart_tpsl_overlay.js`

```javascript
class ChartTPSLOverlay {
    constructor(chart, tokenAddress, userWallet) {
        this.chart = chart;  // TradingView Lightweight Charts instance
        this.tokenAddress = tokenAddress;
        this.userWallet = userWallet;
        this.lines = [];
    }
    
    async loadOrders() {
        const response = await fetch(`/api/orders/active/${this.tokenAddress}/${this.userWallet}`);
        const orders = await response.json();
        
        this.renderOrderLines(orders);
    }
    
    renderOrderLines(orders) {
        // Clear existing lines
        this.clearLines();
        
        // Add cost basis line
        if (orders.costBasis) {
            this.addLine({
                price: orders.costBasis,
                color: '#3B82F6',  // Blue
                lineStyle: 0,  // Solid
                width: 2,
                title: 'Cost Basis',
                axisLabelVisible: true
            });
        }
        
        // Add take profit lines
        orders.takeProfits.forEach((tp, index) => {
            this.addLine({
                price: tp.triggerPrice,
                color: '#10B981',  // Green
                lineStyle: 2,  // Dashed
                width: 2,
                title: `TP +${tp.percentage}% (${tp.amountPct}%)`,
                axisLabelVisible: true
            });
        });
        
        // Add stop loss lines
        orders.stopLosses.forEach((sl, index) => {
            this.addLine({
                price: sl.triggerPrice,
                color: '#EF4444',  // Red
                lineStyle: 2,  // Dashed
                width: 2,
                title: `SL ${sl.percentage}% (${sl.amountPct}%)`,
                axisLabelVisible: true
            });
        });
    }
    
    addLine(options) {
        const priceLine = {
            price: options.price,
            color: options.color,
            lineWidth: options.width,
            lineStyle: options.lineStyle,
            axisLabelVisible: options.axisLabelVisible,
            title: options.title
        };
        
        const line = this.chart.createPriceLine(priceLine);
        this.lines.push(line);
    }
    
    clearLines() {
        this.lines.forEach(line => this.chart.removePriceLine(line));
        this.lines = [];
    }
}

// Usage:
const overlay = new ChartTPSLOverlay(chart, tokenAddress, userWallet);
overlay.loadOrders();

// Refresh when orders change
setInterval(() => overlay.loadOrders(), 30000);  // Every 30s
```

---

## 7. Chart Integration

### 7.1 TradingView Lightweight Charts

The platform already uses TradingView Lightweight Charts. TP/SL lines are added as price lines:

```javascript
// Add horizontal price line
const takeProfitLine = chart.createPriceLine({
    price: 0.068,
    color: '#10B981',
    lineWidth: 2,
    lineStyle: LightweightCharts.LineStyle.Dashed,
    axisLabelVisible: true,
    title: 'TP +100% (50%)'
});

// Interactive tooltip on hover
chart.subscribeCrosshairMove(param => {
    if (param.point) {
        // Show TP/SL info when hovering near line
    }
});
```

### 7.2 Visual Design

**Line Styles:**
- **Cost Basis**: Blue solid line (reference point)
- **Take Profit**: Green dashed line (upside target)
- **Stop Loss**: Red dashed line (downside protection)

**Labels:**
- Show percentage and amount on hover
- Display on right price axis
- Click to edit/cancel order

---

## 8. Security Model

### 8.1 EIP-712 Typed Signing

Users sign structured data (not raw transactions):

```typescript
{
  domain: {
    name: 'GemLaunch TP/SL',
    version: '1',
    chainId: 167012,
    verifyingContract: tokenAddress
  },
  types: {
    ConditionalOrder: [
      { name: 'token', type: 'address' },
      { name: 'orderType', type: 'string' },
      { name: 'triggerPrice', type: 'uint256' },
      { name: 'amount', type: 'uint256' },
      { name: 'deadline', type: 'uint256' }
    ]
  },
  message: {
    token: '0x81f3...',
    orderType: 'TAKE_PROFIT',
    triggerPrice: '68000000000000000',  // 0.068 in wei
    amount: '617283000000000000000000',  // 617,283 tokens
    deadline: 1745990400  // Unix timestamp
  }
}
```

**Security benefits:**
- User sees exactly what they're authorizing
- Signature expires after deadline
- Cannot be replayed on different tokens
- Oracle cannot modify parameters

### 8.2 Token Approval Management

**Required Approvals:**
1. User approves BondingCurvePool to spend tokens (standard ERC20 approval)
2. User signs TP/SL order (EIP-712 signature)

**No Token Escrow:**
- Tokens stay in user's wallet
- User can trade manually anytime
- Orders auto-cancel if balance too low

### 8.3 Gas Payment Security

**Option A: User Wallet Pays (Recommended)**
```python
# Oracle builds transaction FROM user address
tx = {
    'from': user_wallet,  # User pays gas
    'to': bonding_pool,
    'data': sell_function_data,
    'gas': 300000,
    'gasPrice': current_gas_price,
    'nonce': user_nonce
}

# Oracle signs with user's signature authorization
# Network deducts gas from user's KAS balance
```

**Option B: Gas Escrow**
```python
# User pre-deposits KAS for gas
GasEscrow.deposit(user_wallet, 1 KAS)

# Oracle pays gas from escrow
GasEscrow.deduct(user_wallet, actual_gas_cost)

# User withdraws unused balance
GasEscrow.withdraw(user_wallet)
```

### 8.4 Failure Handling

**Scenarios:**
1. **Insufficient balance** → Order auto-cancelled
2. **Price slippage** → Retry with wider slippage (up to 10%)
3. **Gas too high** → Skip execution, retry next cycle
4. **User revokes approval** → Order marked as failed
5. **Network error** → Retry up to 3 times

---

## 9. Implementation Phases

### Phase 1: Foundation (Week 1)

**Tasks:**
- [ ] Create `conditional_orders` database table
- [ ] Implement `ConditionalOrderService` (create, cancel)
- [ ] Add EIP-712 signature verification
- [ ] Create `/api/orders/create` endpoint
- [ ] Create `/api/orders/cancel/:id` endpoint
- [ ] Create `/api/orders/active/:token/:wallet` endpoint

**Deliverables:**
- Backend can store and retrieve orders ✅
- API endpoints functional ✅

### Phase 2: Monitoring (Week 2)

**Tasks:**
- [ ] Implement `TPSLMonitor` service
- [ ] Add price checking logic
- [ ] Add order execution logic
- [ ] Test with manual orders
- [ ] Add logging and error handling

**Deliverables:**
- Monitor checks orders every 10s ✅
- Can execute sells on trigger ✅

### Phase 3: Frontend UI (Week 2-3)

**Tasks:**
- [ ] Create TP/SL modal component
- [ ] Add "Set TP/SL" button to token pages
- [ ] Implement percentage input → price calculation
- [ ] Add EIP-712 signing flow
- [ ] Display active orders on token page
- [ ] Add cancel order functionality

**Deliverables:**
- Users can create TP/SL orders via UI ✅
- Users can view and cancel orders ✅

### Phase 4: Chart Integration (Week 3)

**Tasks:**
- [ ] Add price line overlay to charts
- [ ] Fetch user orders on chart load
- [ ] Render cost basis, TP, and SL lines
- [ ] Add interactive tooltips
- [ ] Real-time updates when orders executed

**Deliverables:**
- Chart shows visual TP/SL lines ✅
- Lines update in real-time ✅

### Phase 5: Testing & Refinement (Week 3-4)

**Tasks:**
- [ ] End-to-end testing with real tokens
- [ ] Load testing (1000+ orders)
- [ ] Gas optimization
- [ ] UI polish and mobile testing
- [ ] Documentation

**Deliverables:**
- Production-ready feature ✅
- User documentation ✅

---

## 10. Testing Strategy

### 10.1 Unit Tests

```python
def test_create_take_profit_order():
    # User has position with cost basis $0.034
    order = ConditionalOrderService.create_order(
        user=test_user,
        token=test_token,
        order_type='TAKE_PROFIT',
        trigger_percentage=100,  # +100%
        amount_percentage=50,
        signature='0x...',
        signature_deadline=int(time.time()) + 3600
    )
    
    assert order.trigger_price == 0.068
    assert order.status == 'active'

def test_stop_loss_triggers_correctly():
    # Create SL order at -30%
    order = create_sl_order(trigger_percentage=-30)
    
    # Price drops to trigger
    mock_price = 0.024
    
    # Monitor should detect and execute
    monitor._check_order(order)
    
    assert order.status == 'executed'
```

### 10.2 Integration Tests

```python
def test_full_tp_execution_flow():
    # 1. User creates TP order
    order = create_tp_via_api('+100%', '50%')
    
    # 2. Price increases to trigger
    set_token_price(trigger_price)
    
    # 3. Monitor detects
    monitor.check_all_orders()
    
    # 4. Order executed
    assert order.status == 'executed'
    assert order.execution_tx_hash is not None
    
    # 5. User received KAS
    user_balance_after = get_kas_balance(user.wallet)
    assert user_balance_after > user_balance_before
```

### 10.3 Load Testing

**Scenario:** 1000 active orders across 100 tokens
- Monitor cycle time: < 5 seconds
- Database query time: < 500ms
- Order execution time: < 10 seconds
- No missed triggers

---

## 11. Future Enhancements

### 11.1 Advanced Order Types

- **Trailing Stop Loss**: Stop loss follows price up
- **OCO Orders**: One-Cancels-Other (TP and SL linked)
- **Time-based**: Execute at specific date/time
- **Market Cap based**: Trigger on $X market cap instead of price

### 11.2 Notifications

- Email alerts when orders execute
- Browser push notifications
- Telegram bot integration
- SMS alerts (via Twilio)

### 11.3 Analytics

- Order success rate dashboard
- Average execution time
- Slippage analysis
- User profit from TP/SL

---

## Conclusion

This TP/SL system leverages the existing cost basis calculation and trade indexer infrastructure to provide automated conditional selling. Users retain full custody of tokens, pay their own gas, and can visualize their risk management strategy directly on price charts.

**Key Advantages:**
- ✅ No token escrow (funds stay in user wallet)
- ✅ User pays gas (oracle just relays)
- ✅ Uses existing cost basis system
- ✅ Visual chart integration
- ✅ EIP-712 security
- ✅ Simple percentage-based UI

**Implementation Timeline:** 3-4 weeks after graduation fix is complete.

---

**End of Document**
