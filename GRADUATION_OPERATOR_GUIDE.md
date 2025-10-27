# Graduation Operator Guide

This guide provides step-by-step instructions for platform operators to handle token graduation issues and perform recovery operations.

## Table of Contents

1. [Understanding Graduation](#understanding-graduation)
2. [Normal Graduation Flow](#normal-graduation-flow)
3. [Common Issues](#common-issues)
4. [Recovery Procedures](#recovery-procedures)
5. [Monitoring & Alerts](#monitoring--alerts)
6. [Emergency Procedures](#emergency-procedures)

---

## Understanding Graduation

Token graduation is a two-phase process that migrates tokens from the bonding curve to Kaspa Finance DEX:

### Phase 1: Initiation
- Backend oracle detects token reached $70K market cap
- Oracle calls `GraduationController.initiateGraduation()`
- Pool transfers KAS and tokens to GraduationController
- Snapshot created with current reserves and target price
- Token status: `initiating`

### Phase 2: Completion
- Backend oracle calls `GraduationController.completeGraduation()`
- Uniswap V3 pool created atomically with initial price
- Full-range liquidity position minted
- LP NFT burned to 0x...dEaD (permanent liquidity lock)
- Pool.completeGraduation() callback executed
- Token status: `graduated`

**Success Metric:** LP exists on Kaspa Finance with liquidity > 0

---

## Normal Graduation Flow

### Expected Timeline
1. Market cap reaches $70K: 0 seconds
2. Oracle detects and initiates: 15-30 seconds
3. Initiation tx confirmed: 5-15 seconds
4. Oracle calls completion: 15-30 seconds
5. Completion tx confirmed: 5-15 seconds
6. Database synced: 5-10 seconds

**Total expected time:** ~1-2 minutes

### Monitoring Points
- Token status in database
- On-chain `graduating` and `graduated` flags
- LP pool existence on Kaspa Finance
- LP pool sqrtPriceX96 value (must be > 0)
- Backend service logs

---

## Common Issues

### Issue 1: Stuck in 'initiating' Status

**Symptoms:**
- Token shows `graduation_status = 'initiating'` in database
- On-chain `graduating = true` but `graduated = false`
- More than 10 minutes since initiation

**Causes:**
- Backend oracle crashed before calling completion
- RPC node down or unresponsive
- Transaction gas price too low (stuck in mempool)
- GraduationController contract issue

**Diagnosis:**
```python
# Check on-chain state
pool = web3.eth.contract(address=token_address, abi=pool_abi)
graduating = pool.functions.graduating().call()
graduated = pool.functions.graduated().call()

# Check GC snapshot
gc = web3.eth.contract(address=GRADUATION_CONTROLLER_ADDRESS, abi=gc_abi)
snapshot = gc.functions.graduationSnapshots(token_address).call()
print(f"Snapshot initiated at: {snapshot[4]}")
print(f"LP minted: {snapshot[6]}")
```

**Recovery:**
See [Recovery Procedure 1](#recovery-1-complete-stuck-graduation)

---

### Issue 2: False Graduation (No LP)

**Symptoms:**
- Database shows `is_graduated = True`
- On-chain `graduated = true`
- LP pool address is 0x0000...0000 or pool not initialized
- Users cannot trade token

**Causes:**
- Database synced before LP verification
- Pool.completeGraduation() called without LP creation
- GraduationController failure during LP mint

**Diagnosis:**
```python
# Check LP exists
gc = web3.eth.contract(address=GRADUATION_CONTROLLER_ADDRESS, abi=gc_abi)
lp_address = gc.functions.uniswapPoolAddress(token_address).call()
print(f"LP address: {lp_address}")

if lp_address != '0x0000000000000000000000000000000000000000':
    # Check LP initialized
    pool = web3.eth.contract(address=lp_address, abi=pool_abi)
    slot0 = pool.functions.slot0().call()
    sqrt_price = slot0[0]
    print(f"sqrtPriceX96: {sqrt_price}")
```

**Recovery:**
See [Recovery Procedure 2](#recovery-2-fix-false-graduation)

---

### Issue 3: Graduation Timeout

**Symptoms:**
- Token stuck in `initiating` for > 1 hour
- Funds locked in GraduationController
- Cannot retry graduation

**Causes:**
- Oracle permanently offline
- Smart contract bug preventing completion
- Network congestion

**Recovery:**
See [Recovery Procedure 3](#recovery-3-cancel-stuck-graduation)

---

## Recovery Procedures

### Recovery 1: Complete Stuck Graduation

**When to use:**
- Token in `initiating` status
- On-chain `graduating = true`
- Snapshot exists in GraduationController
- Less than 1 hour since initiation

**Steps:**

1. **Verify state:**
```python
from services.web3_service import get_web3_service
w3_service = get_web3_service()

pool = w3_service.get_bonding_pool_contract(token_address)
graduating = pool.functions.graduating().call()
graduated = pool.functions.graduated().call()

print(f"graduating: {graduating}, graduated: {graduated}")
```

2. **Manually trigger completion:**
```python
# Using Python service
tx_hash = w3_service.complete_graduation_via_controller(token_address)
print(f"Completion tx: {tx_hash}")

# Wait for confirmation
receipt = w3_service.wait_for_transaction_receipt(tx_hash, timeout=120)
print(f"Status: {receipt['status']}")
```

3. **Verify LP created:**
```python
gc = w3_service.contracts['GraduationController']
lp_address = gc.functions.uniswapPoolAddress(token_address).call()
print(f"LP created at: {lp_address}")
```

4. **Sync database:**
```python
from models import Token, db

token = Token.query.filter_by(contract_address=token_address).first()
token.graduation_status = 'graduated'
token.is_graduated = True
token.lp_pool_address = lp_address
token.graduation_completed_at = datetime.now(timezone.utc)
db.session.commit()
```

---

### Recovery 2: Fix False Graduation

**When to use:**
- Database shows `graduated` but LP doesn't exist
- On-chain `graduated = true` but LP not created

**Prerequisites:**
- Must be using GraduationControllerV4 with `forceCompleteCorruptedGraduation()`
- Owner account must be available

**Steps:**

1. **Reset pool state (if possible):**
```python
# Only works if pool has forceResetGraduation()
pool = w3_service.get_bonding_pool_contract(token_address)
tx_hash = pool.functions.forceResetGraduation().transact({
    'from': owner_address
})
```

2. **Force complete via V4 controller:**
```python
# Using owner account
gc = w3_service.contracts['GraduationController']

tx = gc.functions.forceCompleteCorruptedGraduation(token_address).build_transaction({
    'from': owner_address,
    'gas': 5000000,
    'gasPrice': w3_service.w3.eth.gas_price,
    'nonce': w3_service.w3.eth.get_transaction_count(owner_address)
})

signed = w3_service.w3.eth.account.sign_transaction(tx, private_key)
tx_hash = w3_service.w3.eth.send_raw_transaction(signed.rawTransaction)
print(f"Recovery tx: {tx_hash.hex()}")
```

3. **Verify LP created:**
```python
lp_address = gc.functions.uniswapPoolAddress(token_address).call()
print(f"LP verified: {lp_address}")
```

4. **Sync database:**
```python
token.lp_pool_address = lp_address
token.dex_pool_address = lp_address
db.session.commit()
```

---

### Recovery 3: Cancel Stuck Graduation

**When to use:**
- Token stuck > 1 hour
- Cannot complete graduation
- Need to return funds and retry

**Steps:**

1. **Check timeout:**
```python
gc = w3_service.contracts['GraduationController']
can_cancel = gc.functions.canCancelStuckGraduation(token_address).call()
print(f"Can cancel: {can_cancel}")
```

2. **Cancel via owner:**
```python
tx = gc.functions.cancelStuckGraduation(token_address).build_transaction({
    'from': owner_address,
    'gas': 500000,
    'gasPrice': w3_service.w3.eth.gas_price,
    'nonce': w3_service.w3.eth.get_transaction_count(owner_address)
})

signed = w3_service.w3.eth.account.sign_transaction(tx, private_key)
tx_hash = w3_service.w3.eth.send_raw_transaction(signed.rawTransaction)
```

3. **Reset database:**
```python
token.graduation_status = 'active'
token.graduation_initiated_at = None
token.graduation_initiation_tx = None
db.session.commit()
```

4. **Retry graduation:**
Wait for token to reach threshold again, or manually trigger if still above $70K.

---

## Monitoring & Alerts

### Metrics to Monitor

1. **Graduation Success Rate**
   - Target: > 95%
   - Alert if < 90% over 24 hours

2. **Average Graduation Duration**
   - Target: < 2 minutes
   - Alert if > 5 minutes

3. **Stuck Graduations**
   - Alert if any token stuck > 10 minutes
   - Critical if > 30 minutes

4. **LP Verification Failures**
   - Alert on any false graduation
   - Critical priority

### Log Monitoring

**Key log patterns to watch:**

```
# Success pattern
✅ Graduation initiated for {symbol}: {tx_hash}
✅ GC.completeGraduation() called - Token: {address}
✅ LP verified on Kaspa Finance: {lp_address}
✅ {symbol} graduated successfully!

# Warning pattern
⚠️ Token {symbol} has DB status 'initiating' but on-chain graduating=False

# Error pattern
❌ Token {symbol} marked graduated but NO LP exists!
❌ LP exists but not initialized: {lp_address}
Failed to complete graduation via GC for {address}: {error}
```

### Alerting Configuration

```python
# Example alert rules (pseudo-code)
if token.graduation_status == 'initiating' and \
   (now - token.graduation_initiated_at) > timedelta(minutes=10):
    send_alert(
        severity='high',
        message=f'Stuck graduation: {token.symbol}',
        token_id=token.id
    )

if token.is_graduated and not verify_lp_exists(token.contract_address):
    send_alert(
        severity='critical',
        message=f'False graduation: {token.symbol}',
        token_id=token.id
    )
```

---

## Emergency Procedures

### Emergency 1: Oracle Down

**Symptoms:**
- Multiple tokens stuck in `initiating`
- Backend oracle service crashed
- No graduation completions happening

**Action Plan:**

1. **Restart oracle service:**
```bash
systemctl restart gemlaunch-oracle
```

2. **Check service logs:**
```bash
tail -f /var/log/gemlaunch/oracle.log
```

3. **Manually complete stuck graduations:**
See [Recovery 1](#recovery-1-complete-stuck-graduation)

4. **Monitor for new issues:**
Watch for repeat failures indicating systemic issue

---

### Emergency 2: RPC Node Down

**Symptoms:**
- All blockchain operations failing
- "Connection refused" or timeout errors
- Cannot query contract state

**Action Plan:**

1. **Switch to backup RPC:**
```python
# Edit web3_service.py RPC_ENDPOINTS
# Move working endpoint to top of list
```

2. **Wait for primary RPC recovery**

3. **Resume normal operations**

---

### Emergency 3: Smart Contract Issue

**Symptoms:**
- All graduation attempts reverting
- Consistent failure pattern
- Contract may have been upgraded incorrectly

**Action Plan:**

1. **Pause graduations:**
```python
gc.functions.pause().transact({'from': owner_address})
```

2. **Investigate issue:**
   - Check recent contract deployments
   - Review transaction revert reasons
   - Test on testnet

3. **Deploy fix if needed**

4. **Resume graduations:**
```python
gc.functions.unpause().transact({'from': owner_address})
```

---

## Contract Version Check

Always verify you're using the correct contract version:

```python
def verify_contract_version():
    """Verify GraduationController version matches expectation"""
    gc = w3_service.contracts['GraduationController']
    version = gc.functions.VERSION().call()
    expected = "3.0.0"  # Or "4.0.0" if using V4
    
    if version != expected:
        raise ValueError(f"Version mismatch: expected {expected}, got {version}")
    
    print(f"✅ GraduationController version verified: {version}")
```

---

## Contact Information

**For urgent issues:**
- Platform Owner: [Contact details]
- On-call Engineer: [Contact details]
- Smart Contract Auditor: [Contact details]

**Documentation:**
- Security Audit: `SECURITY_AUDIT_REPORT.md`
- Deployment Guide: `contracts/DEPLOYMENT_GUIDE.md`
- API Documentation: [Link]

---

## Appendix: Useful Commands

### Check Token Status
```python
from models import Token
token = Token.query.filter_by(symbol='MEME').first()
print(f"Status: {token.graduation_status}")
print(f"Graduated: {token.is_graduated}")
print(f"LP Address: {token.lp_pool_address}")
```

### Check On-Chain State
```python
pool = w3.eth.contract(address=token_address, abi=pool_abi)
print(f"graduating: {pool.functions.graduating().call()}")
print(f"graduated: {pool.functions.graduated().call()}")
print(f"liquidityTransferred: {pool.functions.liquidityTransferred().call()}")
```

### Check GC Snapshot
```python
gc = w3.eth.contract(address=gc_address, abi=gc_abi)
snapshot = gc.functions.graduationSnapshots(token_address).call()
print(f"kasLiquidity: {snapshot[0]}")
print(f"tokenLiquidity: {snapshot[1]}")
print(f"initiatedAt: {snapshot[4]}")
print(f"lpMinted: {snapshot[6]}")
```

### Verify LP Pool
```python
lp_address = gc.functions.uniswapPoolAddress(token_address).call()
if lp_address != '0x0000000000000000000000000000000000000000':
    pool = w3.eth.contract(address=lp_address, abi=v3_pool_abi)
    slot0 = pool.functions.slot0().call()
    print(f"LP initialized: {slot0[0] > 0}")
    print(f"sqrtPriceX96: {slot0[0]}")
```

---

**Last Updated:** October 27, 2025  
**Document Version:** 1.0
