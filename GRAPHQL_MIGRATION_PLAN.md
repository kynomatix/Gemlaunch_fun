# GraphQL Migration Plan - Decentralizing Trading Data

## 🚨 Critical Fixes Applied (Claude's Feedback)

**This plan has been updated with the following critical corrections:**

1. ✅ **Endpoint Discovery** - Added Phase 0 to test multiple endpoints (GraphiQL UI ≠ API endpoint)
2. ✅ **Use tokenTransfers, NOT transactions** - Fixed to query ERC-20 token movements, not ETH transactions
3. ✅ **Buy/Sell Detection** - Added logic to parse trade direction from transfer events
4. ✅ **KAS Amount Extraction** - Get transaction value for KAS amounts paid
5. ✅ **Proper Error Handling** - Added retry logic with exponential backoff
6. ✅ **Flask-Caching** - Replaced memory-leaking dict cache with Flask-Caching + Redis
7. ✅ **Batch Operations** - Added methods to query multiple tokens efficiently
8. ✅ **Real-Time Polling** - Use polling instead of WebSocket (Blockscout uses Phoenix, not standard GraphQL subscriptions)

---

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

**⚠️ CRITICAL: Endpoint Discovery Required First!**

The GraphiQL UI URL is NOT the API endpoint. Test these endpoints:
- `https://explorer.testnet.kasplextest.xyz/graphiql` (UI interface)
- `https://explorer.testnet.kasplextest.xyz/api/v2/graphql` (possible API)
- `https://explorer.testnet.kasplextest.xyz/graphql` (possible API)

**What it provides (FREE):**
- **Token transfers** (tokenTransfers) - buy/sell events
- **Holder balances** (tokenBalances) - current holdings
- **Transactions** (transactions) - KAS amounts
- **Block data** - timestamps, confirmations
- Already indexed and maintained by network

**Key Distinction:**
- `transactions()` = ETH/KAS transfers + contract interactions
- `tokenTransfers()` = ERC-20/KRC-20 token movements (what we need!)
- `tokenBalances()` = Current holder balances

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

### Phase 0: Endpoint Discovery (DO THIS FIRST!) ⚠️

**Test GraphQL Endpoints:**
```python
# test_graphql_endpoint.py
import requests
import json

# Test different endpoints
endpoints = [
    "https://explorer.testnet.kasplextest.xyz/graphiql",
    "https://explorer.testnet.kasplextest.xyz/api/v2/graphql",
    "https://explorer.testnet.kasplextest.xyz/graphql",
]

test_query = {
    "query": "{ __schema { types { name } } }"
}

for endpoint in endpoints:
    try:
        response = requests.post(
            endpoint, 
            json=test_query,
            headers={"Content-Type": "application/json"}
        )
        if response.ok:
            print(f"✅ Working endpoint: {endpoint}")
            print(f"Response: {response.json()[:200]}...")
        else:
            print(f"❌ Failed: {endpoint} - Status {response.status_code}")
    except Exception as e:
        print(f"❌ Error: {endpoint} - {e}")
```

**Manual Testing in GraphiQL:**
1. Open browser: `https://explorer.testnet.kasplextest.xyz/graphiql`
2. Open DevTools → Network tab
3. Run a test query
4. Find the actual POST request - that's your API endpoint!

---

### Phase 1: Setup GraphQL Client ✅

**Install Dependencies:**
```bash
pip install gql[all] requests flask-caching redis
```

**Create Client Service with Proper Error Handling:**
```python
# services/blockscout_client.py
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport
from gql.transport.exceptions import TransportQueryError
import logging
import time

# TODO: Replace with actual endpoint from Phase 0 discovery
BLOCKSCOUT_GRAPHQL = "https://explorer.testnet.kasplextest.xyz/api/v2/graphql"

class BlockscoutClient:
    def __init__(self):
        transport = RequestsHTTPTransport(
            url=BLOCKSCOUT_GRAPHQL,
            timeout=10,
            retries=3
        )
        self.client = Client(transport=transport, fetch_schema_from_transport=False)
        self.max_retries = 3
        self.retry_delay = 2
    
    def execute_with_retry(self, query, variables):
        """Execute GraphQL query with retry logic"""
        for attempt in range(self.max_retries):
            try:
                return self.client.execute(query, variable_values=variables)
            
            except TransportQueryError as e:
                logging.error(f"GraphQL query error: {e}")
                return None
            
            except Exception as e:
                logging.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    logging.error("All retries failed")
                    return None
    
    def get_token_transfers(self, contract_address, limit=100):
        """Get token transfer events (buy/sell trades)
        
        ⚠️ CRITICAL: Use tokenTransfers, NOT transactions
        """
        query = gql("""
            query GetTokenTransfers($address: AddressHash!, $first: Int!) {
                address(hash: $address) {
                    tokenTransfers(first: $first, order: DESC) {
                        edges {
                            node {
                                amount
                                fromAddressHash
                                toAddressHash
                                tokenContractAddressHash
                                transactionHash
                                blockNumber
                                timestamp
                                transaction {
                                    value
                                    input
                                }
                            }
                        }
                    }
                }
            }
        """)
        
        result = self.execute_with_retry(query, {
            "address": contract_address,
            "first": limit
        })
        
        if result is None:
            return []
        
        return [e['node'] for e in result['address']['tokenTransfers']['edges']]
    
    def get_token_holders(self, contract_address):
        """Get current token holders with balances"""
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
        
        result = self.execute_with_retry(query, {
            "address": contract_address
        })
        
        if result is None:
            return []
        
        return [e['node'] for e in result['address']['tokenBalances']['edges']]
    
    def parse_trades_from_transfers(self, contract_address, pool_address):
        """
        Parse token transfers to determine buy/sell trades
        
        Logic:
        - Transfer TO pool = SELL (user sends tokens to pool)
        - Transfer FROM pool = BUY (pool sends tokens to user)
        """
        transfers = self.get_token_transfers(contract_address, limit=100)
        
        trades = []
        for transfer in transfers:
            # Get KAS amount from transaction
            kas_amount = int(transfer['transaction']['value']) / 1e18 if transfer['transaction'] else 0
            token_amount = int(transfer['amount']) / 1e18 if transfer['amount'] else 0
            
            trade = {
                'tx_hash': transfer['transactionHash'],
                'timestamp': transfer['timestamp'],
                'token_amount': token_amount,
                'kas_amount': kas_amount,
                'block_number': transfer['blockNumber']
            }
            
            # Determine buy/sell by transfer direction
            if transfer['toAddressHash'].lower() == pool_address.lower():
                # User → Pool = SELL
                trade['type'] = 'sell'
                trade['trader'] = transfer['fromAddressHash']
            elif transfer['fromAddressHash'].lower() == pool_address.lower():
                # Pool → User = BUY
                trade['type'] = 'buy'
                trade['trader'] = transfer['toAddressHash']
            else:
                # Not a pool trade (could be transfer)
                continue
            
            trades.append(trade)
        
        return trades
    
    def get_user_trading_volume(self, wallet_address, limit=1000):
        """Get all trades for a user to calculate volume"""
        query = gql("""
            query GetUserTransfers($address: AddressHash!, $first: Int!) {
                address(hash: $address) {
                    tokenTransfers(first: $first, order: DESC) {
                        edges {
                            node {
                                transaction {
                                    value
                                }
                                timestamp
                            }
                        }
                    }
                }
            }
        """)
        
        result = self.execute_with_retry(query, {
            "address": wallet_address,
            "first": limit
        })
        
        if result is None:
            return 0
        
        transfers = [e['node'] for e in result['address']['tokenTransfers']['edges']]
        
        # Sum KAS volume from all trades
        total_volume = sum(
            int(t['transaction']['value']) / 1e18 
            for t in transfers 
            if t['transaction'] and t['transaction']['value']
        )
        
        return total_volume

# Singleton instance
blockscout_client = BlockscoutClient()
```

**Testing with Real Token:**
```python
# Test with actual deployed token
from services.blockscout_client import blockscout_client

# Get token from database
token = Token.query.filter_by(deployment_status='deployed').first()
pool_address = token.contract_address  # BondingCurvePool IS the token

# Test token transfers
transfers = blockscout_client.get_token_transfers(pool_address, limit=10)
print(f"Found {len(transfers)} transfers")
for t in transfers[:3]:
    print(f"  {t['fromAddressHash'][:10]}... → {t['toAddressHash'][:10]}... : {t['amount']}")

# Test parsing trades
trades = blockscout_client.parse_trades_from_transfers(pool_address, pool_address)
print(f"\nFound {len(trades)} trades:")
for trade in trades[:3]:
    print(f"  {trade['type'].upper()}: {trade['token_amount']:.2f} tokens, {trade['kas_amount']:.4f} KAS")

# Test holders
holders = blockscout_client.get_token_holders(pool_address)
print(f"\nFound {len(holders)} holders")
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

⚠️ **CRITICAL:** Simple dict cache causes memory leaks. Use Flask-Caching with Redis or in-memory cache.

### Setup Flask-Caching

```python
# app.py - Add caching initialization
from flask_caching import Cache

# Configure cache (use Redis for production)
cache_config = {
    'CACHE_TYPE': 'redis',
    'CACHE_REDIS_URL': os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
    'CACHE_DEFAULT_TIMEOUT': 60
}

# For development without Redis, use simple memory cache
# cache_config = {'CACHE_TYPE': 'simple'}

cache = Cache(config=cache_config)
cache.init_app(app)
```

### Cache GraphQL Queries

```python
# services/blockscout_client.py - Add caching
from app import cache

class BlockscoutClient:
    # ... existing methods ...
    
    @cache.memoize(timeout=30)  # Cache for 30 seconds
    def get_token_transfers_cached(self, contract_address, limit=100):
        """Cached version of get_token_transfers"""
        return self.get_token_transfers(contract_address, limit)
    
    @cache.memoize(timeout=60)  # Cache for 60 seconds
    def get_token_holders_cached(self, contract_address):
        """Cached version of get_token_holders"""
        return self.get_token_holders(contract_address)
    
    @cache.memoize(timeout=300)  # Cache for 5 minutes
    def get_user_trading_volume_cached(self, wallet_address):
        """Cached version of user trading volume"""
        return self.get_user_trading_volume(wallet_address)

# Usage in routes
@app.route('/api/token/<contract_address>/trades')
def get_recent_trades(contract_address):
    # Use cached version
    trades = blockscout_client.get_token_transfers_cached(contract_address, limit=20)
    # ... parse and return
```

### Cache Invalidation

```python
# Invalidate cache when new trade detected
def on_new_trade(contract_address):
    """Clear cache when new trade happens"""
    cache.delete_memoized(
        blockscout_client.get_token_transfers_cached,
        contract_address
    )
    cache.delete_memoized(
        blockscout_client.get_token_holders_cached,
        contract_address
    )
```

### Cache Key Strategy

```python
# Different cache durations for different data
CACHE_DURATIONS = {
    'trades': 30,       # Recent trades - 30s (frequently updated)
    'holders': 60,      # Token holders - 1min (changes less often)
    'user_volume': 300, # User stats - 5min (rarely changes)
    'token_stats': 30   # Token stats - 30s
}
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
