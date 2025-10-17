# GraphQL Migration Plan - Decentralizing Trading Data

## Executive Summary

**Goal:** Migrate trading data from PostgreSQL to Blockscout GraphQL API to prevent database bloat and enable scalability.

**Current Problem:**
- Database stores granular trade events (TradeEvent table)
- Duplicate on-chain data stored off-chain
- Event indexer creates sync delays and complexity
- Database will bloat with high trading volume
- Won't scale to many users

**Solution:**
- Use Blockscout GraphQL API for all trading data queries
- Keep database for user profiles, points, and token creator data
- Store only aggregated metrics for points system
- Remove custom event indexer

---

## Current Architecture Issues

### ❌ Database Overload

**What we're storing unnecessarily:**
```python
# models.py - Trading data (REMOVE)
class TradeEvent(db.Model):
    # Stores every buy/sell - duplicates blockchain
    id = db.Column(db.Integer, primary_key=True)
    token_id = db.Column(db.Integer, db.ForeignKey('token.id'))
    trader_address = db.Column(db.String(42))
    trade_type = db.Column(db.String(4))  # 'buy' or 'sell'
    kas_amount = db.Column(db.Numeric(36, 18))
    token_amount = db.Column(db.Numeric(36, 18))
    timestamp = db.Column(db.DateTime)
    # ... bloats with every trade

class Holding(db.Model):
    # Duplicate of on-chain balances
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    token_id = db.Column(db.Integer, db.ForeignKey('token.id'))
    amount = db.Column(db.Numeric(36, 18))
    # ... can be queried from blockchain
```

**Event Indexer Overhead:**
- `services/event_indexer.py` - Custom indexer polling blockchain
- Scheduled jobs running every 20 seconds
- Sync delays, potential data loss during downtime
- Maintenance overhead

---

## New Architecture

### ✅ Blockscout GraphQL API

**Endpoint:** `https://explorer.testnet.kasplextest.xyz/api/graphql`

**What it provides (FREE):**
- All token transactions in real-time
- Token transfer events
- Holder balances
- Transaction history
- Block data
- Already indexed and maintained by network

### Data Separation Strategy

#### 🗄️ KEEP in Database (Off-Chain State)

**1. User Identity & Social Features**
```python
class User(db.Model):
    # Profile data
    wallet_address = db.Column(db.String(42), unique=True)
    username = db.Column(db.String(64))
    bio = db.Column(db.Text)
    avatar_url = db.Column(db.String(512))
    
    # Aggregated metrics (computed from GraphQL)
    gem_points = db.Column(db.Integer, default=0)
    total_volume_traded = db.Column(db.Numeric(36, 18), default=0)
    tokens_created = db.Column(db.Integer, default=0)
    
    # Social
    achievements = db.relationship('Achievement')
    activity_feeds = db.relationship('ActivityFeed')

class LinkedWallet(db.Model):
    # Multi-wallet system
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    wallet_address = db.Column(db.String(42), unique=True)
    wallet_label = db.Column(db.String(100))
```

**2. Token Creator Data (Recovery System)**
```python
class Token(db.Model):
    # Static metadata
    name = db.Column(db.String(100))
    symbol = db.Column(db.String(20))
    description = db.Column(db.Text)
    image_url = db.Column(db.String(512))
    
    # Deployment state (for recovery)
    deployment_status = db.Column(db.String(20))  # pending/deployed/failed
    deployment_tx_hash = db.Column(db.String(66))
    contract_address = db.Column(db.String(42))
    
    # Vesting (PRO tokens)
    marketing_vesting_address = db.Column(db.String(42))
    team_vesting_address = db.Column(db.String(42))
    airdrop_vesting_address = db.Column(db.String(42))
    
    # REMOVE these (query from GraphQL instead):
    # kas_reserve - blockchain query
    # token_reserve - blockchain query
    # current_price - calculate from reserves
    # current_market_cap - calculate from reserves
    # trade_count - count from GraphQL
    # holder_count - query from GraphQL
```

**3. Points System (Aggregated Only)**
```python
class UserTradingStats(db.Model):
    """Aggregated metrics computed from GraphQL"""
    user_address = db.Column(db.String(42), primary_key=True)
    total_volume_kas = db.Column(db.Numeric(36, 18))
    total_trades = db.Column(db.Integer)
    tokens_held_count = db.Column(db.Integer)
    last_updated = db.Column(db.DateTime)
    # Updated by scheduled job that queries GraphQL
```

#### 🔗 QUERY from GraphQL (On-Chain Data)

**Real-Time Trading Data:**
- Recent trades for a token
- Trade history for a user
- Current holder balances
- Token transfer events
- Trading volume (calculate from trades)
- Holder count (count from balances)

**Market Data:**
- Token reserves (query pool contract)
- Current price (calculate from reserves)
- Market cap (calculate from reserves × price)
- Bonding curve state

---

## Implementation Phases

### Phase 1: Setup GraphQL Client ✅

**Install Dependencies:**
```bash
pip install gql[all] requests
```

**Create Client Service:**
```python
# services/blockscout_client.py
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport
import logging

BLOCKSCOUT_GRAPHQL = "https://explorer.testnet.kasplextest.xyz/api/graphql"

class BlockscoutClient:
    def __init__(self):
        transport = RequestsHTTPTransport(
            url=BLOCKSCOUT_GRAPHQL,
            timeout=10
        )
        self.client = Client(transport=transport, fetch_schema_from_transport=True)
    
    def get_token_transactions(self, contract_address, limit=20):
        """Get recent transactions for a token"""
        query = gql("""
            query GetTokenTransactions($address: AddressHash!, $first: Int!) {
                address(hash: $address) {
                    transactions(first: $first, order: DESC) {
                        edges {
                            node {
                                hash
                                blockNumber
                                fromAddressHash
                                toAddressHash
                                value
                                gasUsed
                                timestamp
                                status
                                input
                            }
                        }
                    }
                }
            }
        """)
        
        result = self.client.execute(query, variable_values={
            "address": contract_address,
            "first": limit
        })
        
        return [edge['node'] for edge in result['address']['transactions']['edges']]
    
    def get_token_holders(self, contract_address):
        """Get current token holders"""
        query = gql("""
            query GetTokenHolders($address: AddressHash!) {
                address(hash: $address) {
                    tokenBalances {
                        edges {
                            node {
                                addressHash
                                value
                            }
                        }
                    }
                }
            }
        """)
        
        result = self.client.execute(query, variable_values={
            "address": contract_address
        })
        
        return [edge['node'] for edge in result['address']['tokenBalances']['edges']]
    
    def get_user_trades(self, wallet_address, limit=100):
        """Get all trades for a user"""
        query = gql("""
            query GetUserTransactions($address: AddressHash!, $first: Int!) {
                address(hash: $address) {
                    transactions(first: $first, order: DESC) {
                        edges {
                            node {
                                hash
                                toAddressHash
                                value
                                timestamp
                            }
                        }
                    }
                }
            }
        """)
        
        result = self.client.execute(query, variable_values={
            "address": wallet_address,
            "first": limit
        })
        
        return [edge['node'] for edge in result['address']['transactions']['edges']]

# Singleton instance
blockscout_client = BlockscoutClient()
```

**Testing:**
```python
# Test GraphQL client
from services.blockscout_client import blockscout_client

# Test getting token transactions
trades = blockscout_client.get_token_transactions("0x123...")
print(f"Found {len(trades)} trades")

# Test getting holders
holders = blockscout_client.get_token_holders("0x123...")
print(f"Found {len(holders)} holders")
```

---

### Phase 2: Migrate Recent Trades Display ✅

**Before (Database Query):**
```python
# app.py - OLD approach
@app.route('/api/token/<contract_address>/trades')
def get_recent_trades(contract_address):
    token = Token.query.filter_by(contract_address=contract_address).first()
    
    # Query from database
    trades = TradeEvent.query.filter_by(
        token_id=token.id
    ).order_by(TradeEvent.timestamp.desc()).limit(20).all()
    
    return jsonify([{
        'trader': t.trader_address,
        'type': t.trade_type,
        'kas_amount': float(t.kas_amount),
        'timestamp': t.timestamp.isoformat()
    } for t in trades])
```

**After (GraphQL Query):**
```python
# app.py - NEW approach
from services.blockscout_client import blockscout_client

@app.route('/api/token/<contract_address>/trades')
def get_recent_trades(contract_address):
    try:
        # Query from Blockscout GraphQL
        transactions = blockscout_client.get_token_transactions(contract_address, limit=20)
        
        # Parse and format
        trades = []
        for tx in transactions:
            # Decode transaction to determine buy/sell
            # This requires parsing the tx.input data
            trades.append({
                'tx_hash': tx['hash'],
                'trader': tx['fromAddressHash'],
                'value': float(tx['value']) / 1e18,  # Convert from wei
                'timestamp': tx['timestamp'],
                'status': tx['status']
            })
        
        return jsonify({'success': True, 'trades': trades})
    except Exception as e:
        logging.error(f"Error fetching trades from GraphQL: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
```

---

### Phase 3: Points System (Hybrid) ✅

**Aggregation Service:**
```python
# services/points_aggregator.py
from services.blockscout_client import blockscout_client
from models import User, db
import logging

def update_user_points(wallet_address):
    """
    Query trading data from GraphQL, calculate points, store aggregates
    """
    try:
        # Get user's trading activity from blockchain
        user_trades = blockscout_client.get_user_trades(wallet_address)
        
        # Calculate aggregates
        total_volume = sum(float(tx['value']) / 1e18 for tx in user_trades)
        total_trades = len(user_trades)
        
        # Get tokens held (from GraphQL or blockchain query)
        # tokens_held = get_user_token_holdings(wallet_address)
        
        # Calculate points
        trading_points = int(total_volume * 10)  # 10 points per KAS traded
        holder_points = 0  # tokens_held * 50
        
        # Update database with aggregates only
        user = User.query.filter_by(wallet_address=wallet_address).first()
        if user:
            user.total_volume_traded = total_volume
            user.gem_points = trading_points + holder_points
            db.session.commit()
            
            logging.info(f"Updated points for {wallet_address}: {user.gem_points}")
            return True
    except Exception as e:
        logging.error(f"Error updating user points: {str(e)}")
        db.session.rollback()
        return False

def update_all_user_points():
    """Scheduled job: Update points for all users"""
    users = User.query.all()
    for user in users:
        update_user_points(user.wallet_address)
```

**Scheduled Job:**
```python
# Add to scheduled tasks (run every hour)
from apscheduler.schedulers.background import BackgroundScheduler
from services.points_aggregator import update_all_user_points

scheduler = BackgroundScheduler()
scheduler.add_job(
    func=update_all_user_points,
    trigger="interval",
    hours=1,
    id='update_points'
)
scheduler.start()
```

---

### Phase 4: Clean Up Database Schema ✅

**Models to Remove:**
```python
# models.py - DELETE THESE

class TradeEvent(db.Model):
    # DELETE - query from GraphQL instead
    pass

class Holding(db.Model):
    # DELETE - calculate from GraphQL
    pass

class AntiBotFeeTracker(db.Model):
    # DELETE - query from blockchain events
    pass
```

**Token Model - Clean Up:**
```python
# models.py - UPDATE Token model

class Token(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    # KEEP - Token metadata
    name = db.Column(db.String(100), nullable=False)
    symbol = db.Column(db.String(20), nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(512))
    total_supply = db.Column(db.Numeric(36, 18))
    
    # KEEP - Deployment state (for recovery)
    deployment_status = db.Column(db.String(20))
    deployment_tx_hash = db.Column(db.String(66))
    contract_address = db.Column(db.String(42))
    
    # KEEP - Vesting addresses
    marketing_vesting_address = db.Column(db.String(42))
    team_vesting_address = db.Column(db.String(42))
    airdrop_vesting_address = db.Column(db.String(42))
    
    # REMOVE - Query from blockchain instead
    # kas_reserve = db.Column(db.Numeric(36, 18))  # DELETE
    # token_reserve = db.Column(db.Numeric(36, 18))  # DELETE
    # current_price = db.Column(db.Numeric(36, 18))  # DELETE
    # current_market_cap = db.Column(db.Numeric(36, 18))  # DELETE
    # trade_count = db.Column(db.Integer)  # DELETE
    # holder_count = db.Column(db.Integer)  # DELETE
    
    # REMOVE - Relationships to deleted models
    # trades = db.relationship('TradeEvent', backref='token')  # DELETE
    # holdings = db.relationship('Holding', backref='token')  # DELETE
```

**Migration Commands:**
```bash
# After updating models.py, sync database
# (Drizzle-style, but we're using SQLAlchemy)

# Option 1: Let SQLAlchemy auto-update (development only)
# Just restart the app - db.create_all() will update schema

# Option 2: Manual migration (production)
# Create migration script to drop tables
```

---

### Phase 5: Remove Event Indexer ✅

**Delete These Files:**
```bash
# Remove custom event indexer
rm services/event_indexer.py

# Remove scheduled indexing jobs
# Update app.py to remove scheduler jobs
```

**Update app.py:**
```python
# app.py - REMOVE indexer initialization

# DELETE THIS SECTION:
# from apscheduler.schedulers.background import BackgroundScheduler
# from services.event_indexer import index_all_events
# 
# scheduler = BackgroundScheduler()
# scheduler.add_job(
#     func=index_all_events,
#     trigger="interval",
#     seconds=20,
#     id='index_events'
# )
# scheduler.start()
```

---

## API Endpoints Update

### Current Endpoints (Database)

```python
# app.py - OLD (using database)

@app.route('/api/token/<contract_address>/stats')
def token_stats(contract_address):
    token = Token.query.filter_by(contract_address=contract_address).first()
    return jsonify({
        'trade_count': token.trade_count,
        'holder_count': token.holder_count,
        'kas_reserve': float(token.kas_reserve),
        'current_price': float(token.current_price)
    })
```

### New Endpoints (GraphQL + Blockchain)

```python
# app.py - NEW (using GraphQL + blockchain)

@app.route('/api/token/<contract_address>/stats')
def token_stats(contract_address):
    try:
        # Get trades from GraphQL
        trades = blockscout_client.get_token_transactions(contract_address, limit=1000)
        trade_count = len(trades)
        
        # Get holders from GraphQL
        holders = blockscout_client.get_token_holders(contract_address)
        holder_count = len(holders)
        
        # Get reserves from blockchain
        web3_service = get_web3_service()
        reserves = web3_service.get_pool_reserves(contract_address)
        
        # Calculate price from reserves
        price = reserves['kas_reserve'] / reserves['token_reserve'] if reserves['token_reserve'] > 0 else 0
        
        return jsonify({
            'trade_count': trade_count,
            'holder_count': holder_count,
            'kas_reserve': reserves['kas_reserve'],
            'current_price': price
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

---

## Caching Strategy

To avoid hammering GraphQL API, implement caching:

```python
# services/cache_manager.py
from functools import wraps
import time

cache = {}

def cached(ttl_seconds=60):
    """Cache decorator with TTL"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{args}:{kwargs}"
            
            if cache_key in cache:
                result, timestamp = cache[cache_key]
                if time.time() - timestamp < ttl_seconds:
                    return result
            
            result = func(*args, **kwargs)
            cache[cache_key] = (result, time.time())
            return result
        return wrapper
    return decorator

# Usage
@cached(ttl_seconds=30)
def get_token_trades_cached(contract_address):
    return blockscout_client.get_token_transactions(contract_address)
```

---

## Risk Assessment

### Risks & Mitigations

**1. GraphQL API Downtime**
- **Risk:** Blockscout API unavailable
- **Mitigation:** 
  - Cache responses with TTL
  - Fallback to last known values
  - Show "data temporarily unavailable" message

**2. Rate Limiting**
- **Risk:** Too many GraphQL requests
- **Mitigation:**
  - Implement request caching (30-60s TTL)
  - Batch queries where possible
  - Use pagination

**3. Data Format Changes**
- **Risk:** Blockscout changes GraphQL schema
- **Mitigation:**
  - Version API calls
  - Monitor schema changes
  - Add error handling for missing fields

**4. Points System Accuracy**
- **Risk:** Aggregated points may be inaccurate
- **Mitigation:**
  - Run reconciliation jobs
  - Log discrepancies
  - Allow manual point adjustments

---

## Testing Plan

### Unit Tests

```python
# tests/test_blockscout_client.py
import pytest
from services.blockscout_client import blockscout_client

def test_get_token_transactions():
    """Test fetching token transactions"""
    contract_address = "0x123..."  # Test token
    trades = blockscout_client.get_token_transactions(contract_address, limit=10)
    
    assert len(trades) <= 10
    assert all('hash' in trade for trade in trades)
    assert all('timestamp' in trade for trade in trades)

def test_get_token_holders():
    """Test fetching token holders"""
    contract_address = "0x123..."
    holders = blockscout_client.get_token_holders(contract_address)
    
    assert isinstance(holders, list)
    assert all('addressHash' in holder for holder in holders)
```

### Integration Tests

```python
# tests/test_points_system.py
def test_user_points_calculation():
    """Test points are calculated correctly from GraphQL"""
    wallet_address = "0xabc..."
    
    # Update points
    update_user_points(wallet_address)
    
    # Verify in database
    user = User.query.filter_by(wallet_address=wallet_address).first()
    assert user.gem_points > 0
    assert user.total_volume_traded > 0
```

---

## Rollout Strategy

### Week 1: Setup & Testing
- [x] Install GraphQL client library
- [ ] Create `services/blockscout_client.py`
- [ ] Write unit tests for GraphQL queries
- [ ] Test on testnet tokens

### Week 2: Migrate Read Operations
- [ ] Update Recent Trades to use GraphQL
- [ ] Update Token Stats to use GraphQL
- [ ] Add caching layer
- [ ] Monitor performance

### Week 3: Points System
- [ ] Create aggregation service
- [ ] Schedule periodic updates
- [ ] Test points calculation accuracy
- [ ] Deploy to production

### Week 4: Clean Up
- [ ] Remove TradeEvent, Holding models
- [ ] Delete event_indexer.py
- [ ] Remove scheduled indexing jobs
- [ ] Archive old trade data
- [ ] Documentation update

---

## Success Metrics

**Performance:**
- [ ] API response time < 500ms (cached)
- [ ] GraphQL queries < 2s (uncached)
- [ ] Database size growth < 10% per month

**Reliability:**
- [ ] 99.9% uptime for trading data display
- [ ] Graceful degradation if GraphQL unavailable
- [ ] Points accuracy within 1% of blockchain truth

**Scalability:**
- [ ] Support 10,000+ users
- [ ] Handle 1000+ trades per minute
- [ ] Database storage < 1GB for user data

---

## Monitoring & Alerts

**Dashboard Metrics:**
- GraphQL API response time
- Cache hit rate
- Points calculation lag
- Database query performance

**Alerts:**
- GraphQL API errors > 5% 
- Cache miss rate > 50%
- Points sync lag > 1 hour
- Database storage > 80%

---

## Appendix: Useful GraphQL Queries

### Get All Token Transactions
```graphql
query GetTokenTransactions($address: AddressHash!, $first: Int!) {
  address(hash: $address) {
    transactions(first: $first, order: DESC) {
      edges {
        node {
          hash
          blockNumber
          fromAddressHash
          toAddressHash
          value
          gasUsed
          timestamp
          status
          input
        }
      }
    }
  }
}
```

### Get Token Holders
```graphql
query GetTokenHolders($address: AddressHash!) {
  address(hash: $address) {
    tokenBalances {
      edges {
        node {
          addressHash
          value
        }
      }
    }
  }
}
```

### Get User Transaction History
```graphql
query GetUserTransactions($address: AddressHash!, $first: Int!) {
  address(hash: $address) {
    transactions(first: $first, order: DESC) {
      edges {
        node {
          hash
          toAddressHash
          value
          timestamp
        }
      }
    }
  }
}
```

---

## References

- Blockscout GraphQL Explorer: https://explorer.testnet.kasplextest.xyz/graphiql
- GQL Python Library: https://gql.readthedocs.io/
- Blockscout API Docs: https://docs.blockscout.com/
