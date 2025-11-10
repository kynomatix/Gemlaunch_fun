# PRO Token Vesting Integration Test Playbook

## Overview
Final integration testing checklist for PRO token vesting system before production release.

## Test Environment
- **Network**: Kasplex Testnet (Chain ID: 167012)
- **Deployed Contracts**:
  - VestingManager: `0x8b137230C7E3F8C1E451A8ffA45e28dA1cf3dd7d`
  - TokenFactory: `0x14689311eE96F715A5eae2F8Ca6670b1dC701164`
- **Backend**: Web3Service configured with new addresses
- **Database**: PostgreSQL with vesting columns added

## 1. End-to-End Happy Path

### 1.1 PRO Token Creation via UI
**Steps**:
1. Connect wallet to application (Kastle/KasWare/MetaMask)
2. Navigate to "Create Token" page
3. Enable PRO mode (toggle switch)
4. Fill in token details:
   - Name: "Integration Test Token"
   - Symbol: "ITEST"
   - Description: "Testing PRO vesting integration"
   - Image: Upload or use AI generation
5. Configure vesting:
   - Reserved Percentage: 20% (slider)
   - Airdrops: 50% (50M tokens)
   - Marketing: 30% (30M tokens)
   - Team: 20% (20M tokens)
6. Enable anti-bot protection
7. Submit and sign transaction

**Expected Results**:
- ✅ Transaction succeeds on Kasplex testnet
- ✅ VestingDeployed event emitted with 3 contract addresses
- ✅ Database `tokens` table updated with:
  - `marketing_vesting_address`: populated
  - `team_vesting_address`: populated
  - `airdrop_vesting_address`: populated
- ✅ Token appears in marketplace
- ✅ Creator redirected to token detail page

### 1.2 Verify Database Storage
**Query**:
```sql
SELECT 
  id, name, symbol, contract_address,
  reserved_percentage, airdrops_allocation, marketing_allocation, team_allocation,
  marketing_vesting_address, team_vesting_address, airdrop_vesting_address
FROM tokens 
WHERE symbol = 'ITEST';
```

**Expected**:
- All vesting addresses are non-null
- Allocations sum to 100%
- Reserved percentage = 20

### 1.3 Creator Portal Verification
**Steps**:
1. Navigate to Creator Portal
2. Find "Integration Test Token" in creator's tokens
3. View vesting section

**Expected Results**:
- ✅ Marketing vesting shows: 30M tokens total, unlocked amount, available to claim
- ✅ Team vesting shows: 20M tokens total, unlocked amount, available to claim
- ✅ Vesting contracts display correctly with addresses
- ✅ Withdraw buttons enabled when tokens unlocked
- ✅ Progress bars show unlock percentage

### 1.4 Token Detail Page Verification
**Steps**:
1. Navigate to token detail page
2. Click "View Vesting Info" button in PRO badge

**Expected Results**:
- ✅ Vesting modal opens
- ✅ Shows 20% total reserved (50M tokens)
- ✅ Breakdown: 50% airdrops, 30% marketing, 20% team
- ✅ Contract addresses displayed
- ✅ Progress bars show current unlock status
- ✅ "Manage Vesting" button links to creator portal

## 2. API Verification

### 2.1 Vesting Status Endpoints
**Test**: GET `/api/token/<token_id>/vesting/status`

**Expected Response**:
```json
{
  "airdrop": {
    "contract_address": "0x...",
    "total_allocated": "100000000000000000000000000",
    "total_unlocked": "5000000000000000000000000",
    "total_claimed": "0",
    "available_to_claim": "5000000000000000000000000"
  },
  "marketing": {
    "contract_address": "0x...",
    "total_allocated": "60000000000000000000000000",
    "total_unlocked": "5000000000000000000000000",
    "total_claimed": "0",
    "available_to_claim": "5000000000000000000000000"
  },
  "team": {
    "contract_address": "0x...",
    "total_allocated": "40000000000000000000000000",
    "total_unlocked": "0",
    "total_claimed": "0",
    "available_to_claim": "0"
  }
}
```

**Validation**:
- ✅ Status code: 200
- ✅ All fields present
- ✅ available_to_claim = max(0, unlocked - claimed)
- ✅ Team shows 0 if within cliff period

### 2.2 Withdrawal Transaction Builders
**Test**: POST `/api/token/<token_id>/vesting/withdraw-marketing`

**Expected Response**:
```json
{
  "success": true,
  "tx_data": {
    "from": "0x...",
    "to": "0x...",
    "data": "0x3ccfd60b",
    "value": 0,
    "gas": 150000
  }
}
```

**Validation**:
- ✅ Status code: 200
- ✅ tx_data contains valid transaction parameters
- ✅ `to` address matches marketing vesting contract
- ✅ `from` matches creator wallet

### 2.3 Error Handling
**Test**: GET `/api/token/99999/vesting/status` (non-existent token)

**Expected**:
- ✅ Status code: 404
- ✅ Error message: "Token not found"

**Test**: POST `/api/token/<token_id>/vesting/withdraw-marketing` (wrong user)

**Expected**:
- ✅ Status code: 403
- ✅ Error message: "Only creator can withdraw vesting tokens"

## 3. Frontend Validation

### 3.1 Reserved Percentage Bounds
**Test Cases**:
1. Set reserved % to -1: ❌ Error toast "Reserved % must be 0-25"
2. Set reserved % to 0: ✅ BASIC token (no vesting)
3. Set reserved % to 25: ✅ PRO token with max vesting
4. Set reserved % to 26: ❌ Error toast "Reserved % must be 0-25"

### 3.2 Allocation Validation
**Test Cases**:
1. Airdrops 60% + Marketing 30% + Team 20% = 110%: ❌ Error "Allocations must sum to 100%"
2. Airdrops 50% + Marketing 30% + Team 20% = 100%: ✅ Valid
3. Negative allocation: ❌ Error "Allocations must be positive"
4. Decimal allocation: ❌ Error "Allocations must be whole numbers"

### 3.3 Wallet Connection
**Test Cases**:
1. Submit form without wallet: ❌ Error "Please connect wallet"
2. Submit with wallet connected: ✅ Transaction builds

### 3.4 Creator Portal Edge Cases
**Test**: View BASIC token (no vesting)
- ✅ Vesting section hidden or shows "Not a PRO token"
- ✅ No withdrawal buttons displayed

**Test**: Loading state
- ✅ Skeleton loaders display while fetching vesting data
- ✅ Error message if API fails

## 4. Edge Cases & Error Scenarios

### 4.1 Invalid Vesting Parameters
**Test**: Attempt PRO creation with reserved % = 0 but allocations set
**Expected**: Frontend validation prevents submission OR backend rejects

### 4.2 Database Constraints
**Test**: Create token with duplicate symbol
**Expected**:
- ✅ Database constraint violation caught
- ✅ User sees error message "Symbol already exists"
- ✅ Transaction reverted

### 4.3 Missing Vesting Addresses (Legacy Tokens)
**Test**: Query token created before vesting implementation
**Expected**:
- ✅ API returns null for vesting addresses
- ✅ Frontend gracefully handles null (shows "No vesting" or hides section)
- ✅ No JavaScript errors

### 4.4 Withdrawal Before Unlock
**Test**: Attempt withdrawal when 0 tokens unlocked
**Expected**:
- ✅ Smart contract reverts with "No tokens to withdraw"
- ✅ Frontend shows "No tokens available to claim"
- ✅ Withdraw button disabled

### 4.5 Repeated Withdrawals
**Test**: Withdraw twice in succession
**Expected**:
- ✅ First withdrawal succeeds
- ✅ Second withdrawal shows updated available amount
- ✅ UI updates withdrawn total
- ✅ API reflects new claimed amount

## 5. Regression Gates

### 5.1 Test Suites
**Pre-Release Checklist**:
- ✅ Run `npx hardhat test` (105 tests passing)
- ✅ Run `npx hardhat test test/VestingSchedules.fork.test.js` (18/18 passing)
- ✅ All tests green before deployment

### 5.2 Artifact Address Verification
**Check**:
```python
# In services/web3_service.py
TOKEN_FACTORY_ADDRESS == "0x14689311eE96F715A5eae2F8Ca6670b1dC701164"  # ✅

# In deployments/kasplex_testnet_factory.json
"tokenFactory": "0x14689311eE96F715A5eae2F8Ca6670b1dC701164"  # ✅
"vestingManager": "0x8b137230C7E3F8C1E451A8ffA45e28dA1cf3dd7d"  # ✅
```

### 5.3 Environment Variables
**Staging Pipeline Check**:
- ✅ `DEPLOYER_PRIVATE_KEY` set
- ✅ `SESSION_SECRET` set
- ✅ `DATABASE_URL` configured
- ✅ `WEB3_PROVIDER_URI` = https://rpc.kasplextest.xyz

### 5.4 Known Issues
**Chat DB Error**: `null value in column "token_id" of relation "chat_message"`
- **Status**: Known issue, outside vesting scope
- **Impact**: None on vesting functionality
- **Action**: Track separately, not blocking vesting release

## 6. Success Criteria

### Task 16 Completion Checklist:
- ✅ End-to-end PRO token creation works via UI
- ✅ Vesting contracts deploy automatically
- ✅ Database stores all vesting addresses
- ✅ Creator portal displays vesting status correctly
- ✅ Token detail page shows vesting info modal
- ✅ API endpoints return correct data
- ✅ Withdrawal transactions build correctly
- ✅ All validation and error handling works
- ✅ Edge cases handled gracefully
- ✅ All test suites passing
- ✅ Deployment artifacts verified
- ✅ Documentation complete

## 7. Evidence Artifacts

### Required for Release:
1. **Screenshots**:
   - PRO token creation form with vesting config
   - Creator portal vesting section
   - Token detail vesting modal
   - Successful withdrawal transaction

2. **RPC Logs**:
   - VestingDeployed event emission
   - Successful withdrawal transaction receipt

3. **Database Entries**:
   - SQL query results showing populated vesting addresses
   - Multiple PRO tokens with different allocations

4. **API Responses**:
   - Successful vesting status responses
   - Withdrawal transaction payloads
   - Error responses (404, 403)

## 8. Production Readiness

### Before Mainnet Deployment:
1. ✅ All integration tests passing
2. ✅ Security audit completed (7 rounds done, all issues addressed in spec)
3. ✅ Frontend UX reviewed
4. ✅ API rate limiting configured
5. ✅ Error monitoring setup (Sentry/similar)
6. ✅ Backup deployer keys secured
7. ✅ Mainnet RPC configured
8. ✅ Gas price strategy confirmed
9. ✅ Deployment script tested on testnet
10. ✅ Rollback plan documented

## 9. Optional CI Integration

### Recommended CI Job:
```yaml
name: Vesting Integration Tests
on: [pull_request, workflow_dispatch]

jobs:
  fork-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - run: npm ci
      - run: npx hardhat test test/VestingSchedules.fork.test.js
      
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - run: npm ci
      - run: npx hardhat test
```

---

**Last Updated**: October 15, 2025  
**Status**: Ready for Final Integration Testing  
**Next**: Execute playbook and collect evidence artifacts
