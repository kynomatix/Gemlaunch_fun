# Airdrop Batch Distribution - Deployment Checklist

## ✅ Completed Implementation

1. **Smart Contracts**
   - [x] Updated TokenFactory.sol (line 178): `airdropBeneficiary = msg.sender`
   - [x] Created AirdropDistributor.sol with pre-validation
   - [ ] Compiled contracts

2. **Database Schema**
   - [x] Added columns to Airdrop model:
     - `distribution_type` (claim/push)
     - `withdrawal_tx`, `approval_tx`, `distribution_tx`
   - ⚠️ **Auto-migration**: New columns will be added automatically on app restart (Flask-SQLAlchemy `db.create_all()`)

3. **Backend Implementation**
   - [x] Updated `/api/token/<address>/airdrop/create` to build transaction bundles
   - [x] Added web3_service.py methods:
     - `build_vesting_withdrawal_tx()`
     - `build_token_approval_tx()`
     - `build_batch_transfer_tx()`
   - [x] Added validation for zero-address distributor

4. **Frontend Implementation**
   - [x] Updated airdrop modal to sign 3 transactions sequentially
   - [x] Added error handling and retry messages

---

## 🚨 DEPLOYMENT STEPS (Required Before Testing)

### Step 1: Deploy AirdropDistributor Contract

```bash
# Compile contracts
npx hardhat compile

# Deploy AirdropDistributor to Kasplex Testnet
npx hardhat run scripts/deploy_airdrop_distributor.js --network kasplex_testnet
```

**Expected Output:**
```
AirdropDistributor deployed: 0x[NEW_ADDRESS]
```

### Step 2: Update Web3 Service

Edit `services/web3_service.py` line 33:

```python
# BEFORE:
AIRDROP_DISTRIBUTOR_ADDRESS = "0x0000000000000000000000000000000000000000"  # TODO

# AFTER:
AIRDROP_DISTRIBUTOR_ADDRESS = "0x[DEPLOYED_ADDRESS_FROM_STEP_1]"
```

### Step 3: Restart Application

```bash
# Database migration happens automatically via db.create_all()
# Just restart the Flask app
```

### Step 4: Deploy Updated TokenFactory (Optional but Recommended)

⚠️ **Current Tokens**: All existing tokens use old factory (platform custody)
✅ **New Tokens**: Will use new factory (creator custody)

```bash
# Only needed if you want new tokens to have creator custody
npx hardhat run scripts/deploy_factory.js --network kasplex_testnet

# Update TOKEN_FACTORY_ADDRESS in web3_service.py
```

---

## 🧪 Testing Checklist

### Prerequisites
- [ ] AirdropDistributor deployed and address updated
- [ ] App restarted (database columns created)
- [ ] Test PRO token created with airdrop allocation
- [ ] Tokens unlocked in vesting (wait or simulate time)

### Test Scenarios

#### Scenario 1: Basic Airdrop (Token Holders)
- [ ] Create PRO token with 10% airdrop allocation
- [ ] Buy tokens as 3 different users
- [ ] As creator, create airdrop for token holders (min balance: 100)
- [ ] Verify 3 transactions are built
- [ ] Sign all 3 transactions
- [ ] Verify recipients receive tokens

#### Scenario 2: Vesting Withdrawal
- [ ] Create PRO token with airdrop allocation
- [ ] Wait for vesting unlock (or simulate)
- [ ] Create airdrop that requires vesting withdrawal
- [ ] Verify withdrawal TX is included in bundle
- [ ] Verify tokens move from vesting to creator wallet

#### Scenario 3: Insufficient Balance
- [ ] Try to create airdrop with more tokens than available
- [ ] Verify proper error message
- [ ] Verify no partial transactions

#### Scenario 4: Transaction Failure & Retry
- [ ] Start airdrop creation
- [ ] Reject TX2 (approval) in wallet
- [ ] Verify error message mentions retry
- [ ] Verify TX1 (if completed) is tracked for retry

---

## ⚠️ Known Limitations

1. **Random Raffle**: Not implemented (removed from valid types)
2. **Claim-based airdrops**: Old system still in DB, coexists with push-based
3. **Nonce management**: Uses automatic wallet nonce (sequential signing required)
4. **Gas estimation**: Static estimates (100k base + 60k per recipient)

---

## 📝 Deployment Notes

### Database Migration
- Flask-SQLAlchemy auto-creates new columns on app start
- No manual migration needed
- Old airdrop records remain intact

### Smart Contract Addresses
Track deployed addresses here:

```
AirdropDistributor: 0x____ (TODO: Deploy)
TokenFactory (new): 0x2DDb083fCd62D27E9eE1F557B53140bD61F3009D (current)
TokenFactory (updated): 0x____ (TODO: If deploying new factory)
```

### Environment Variables
No new environment variables needed. Uses existing:
- `DEPLOYER_PRIVATE_KEY`
- `DATABASE_URL`

---

## 🐛 Troubleshooting

### "Airdrop system not yet deployed"
- AirdropDistributor address is still 0x000...
- Follow Step 1 & 2 above

### "Insufficient tokens"
- Check vesting unlock schedule (5% per day for airdrops)
- Verify creator's wallet balance + unlocked vesting

### Transaction fails mid-flow
- Check wallet has enough KAS for gas
- Ensure sequential signing (don't skip TXs)
- Check blockchain explorer for reverted TX reason

### No eligible recipients
- Verify TokenEngagement/Holding data exists
- Check filter parameters (min_messages, min_balance)
