# Airdrop Batch Transfer Implementation Plan

**Status:** ✅ Ready for Implementation - Architecture Approved  
**Updated:** January 2025 (after Claude audit review + user decision)

---

## 📋 Final Architecture Decision

### ✅ Creator Custody Model (APPROVED)

**Change TokenFactory.sol line 178 from:**
```solidity
address airdropBeneficiary = airdropTreasury;   // Platform wallet
```

**To:**
```solidity
address airdropBeneficiary = msg.sender;        // Creator wallet
```

**Why This Approach:**
- ✅ Creator owns and controls their airdrop tokens
- ✅ Creator pays gas for distributions (sustainable for platform)
- ✅ No trust issues - tokens are never in platform custody
- ✅ Platform provides convenient "Create Airdrop" UI as the easy distribution path
- ✅ Kasplex limited tooling means creators will naturally use our UI

**Reality Check:**
- Creator can technically withdraw tokens manually via Kasplex block explorer
- BUT Kasplex tooling is limited compared to Etherscan - not user-friendly
- Our "Create Airdrop" button is path of least resistance
- Manual distribution (20 individual transfers) is expensive/annoying
- Platform UI = easy batch distribution tool

---

## 🚨 Problems Being Solved

### Problem #1: Airdrop Distribution Not Implemented

**Critical Design Gap:** Airdrops are ALWAYS batch transfers (20-500 recipients), but current smart contracts only support single `transfer()` calls. This results in:
- ❌ Non-atomic distributions (20 separate transactions)
- ❌ High gas costs (20x transaction overhead)
- ❌ Poor UX (each transfer could fail independently)

**SOLUTION:** Deploy AirdropDistributor.sol helper contract

---

### Problem #2: Multi-Wallet Recipient Logic

**PROBLEM:** Users can link multiple wallets to their profile. Which wallet receives the airdrop?

**SOLUTION:** Send to user's primary/default wallet (User.wallet_address)

**Rationale:**
- Simplest approach - no complex tracking needed
- Primary wallet is what user signed up with
- If they want airdrops on different wallet, they can set it as primary
- Keeps implementation clean and maintainable

**Implementation:**
```python
def get_airdrop_recipient_address(user):
    """Get wallet address for airdrop distribution"""
    return user.wallet_address  # Always use primary wallet
```

## Current State Analysis

### Existing Contracts:
```
contracts/
├── AirdropVesting.sol       ✅ Vesting logic (5% daily unlock)
├── VestingDeployer.sol      ✅ Helper for deploying vesting (24KB workaround)
├── BondingCurvePool.sol     ✅ ERC20 token (standard transfer only)
└── [NO BATCH DISTRIBUTOR]   ❌ Missing batch transfer capability
```

### Current Airdrop Flow (BROKEN):
1. Platform wallet withdraws from AirdropVesting.sol
2. Must call `transfer()` 20 times individually
3. 20 separate transactions, high gas, not atomic

## Solution: AirdropDistributor Helper Contract

### Complete System Architecture

**Note:** Airdrop allocation is DYNAMIC (creator chooses % when deploying PRO token).

```
┌─────────────────────────────────────────────────────┐
│  AirdropVesting.sol (holds X% of reserved tokens)   │
│  Beneficiary: Creator's Wallet ✅                    │
│  Unlock: 5% daily over 20 days                      │
└──────────────────┬──────────────────────────────────┘
                   │
                   │ 1. Creator clicks "Create Airdrop" button
                   │    on token detail page
                   ▼
┌─────────────────────────────────────────────────────┐
│  Create Airdrop Modal (Token Detail Page)           │
│  ┌───────────────────────────────────────────────┐  │
│  │ Select Recipients:                            │  │
│  │ [Dropdown]                                    │  │
│  │  • Token Holders (min balance filter)        │  │
│  │  • Chat Participants (min message count)     │  │
│  │  • Top Traders (by volume)                   │  │
│  │  • Custom List (manual entry)                │  │
│  │                                               │  │
│  │ Amount Per Recipient: [____] tokens          │  │
│  │ Total Recipients: 20                          │  │
│  │ Total Tokens: 20,000                          │  │
│  │                                               │  │
│  │ Gas Estimate: 0.0005 KAS (~$0.000027)        │  │
│  │                                               │  │
│  │ [Cancel]  [Create Airdrop]                   │  │
│  └───────────────────────────────────────────────┘  │
└──────────────────┬──────────────────────────────────┘
                   │
                   │ 2. Backend builds 3 unsigned transactions
                   ▼
┌─────────────────────────────────────────────────────┐
│  Transaction Bundle (Creator Signs All)              │
│  ─────────────────────────────────────────────────  │
│  TX 1: AirdropVesting.withdraw()                     │
│        → Withdraws unlocked tokens to creator        │
│                                                      │
│  TX 2: Token.approve(AirdropDistributor, amount)     │
│        → Approves helper to spend tokens             │
│                                                      │
│  TX 3: AirdropDistributor.batchTransfer(...)         │
│        → Distributes to all recipients atomically    │
└──────────────────┬──────────────────────────────────┘
                   │
                   │ 3. Creator's wallet signs transactions
                   │    (via WalletManager - MetaMask/Kastle/KasWare)
                   ▼
┌─────────────────────────────────────────────────────┐
│  AirdropDistributor.sol (NEW HELPER CONTRACT)       │
│  ────────────────────────────────────────────────── │
│  function batchTransfer(                             │
│    address token,                                    │
│    address[] recipients,    // Primary wallets       │
│    uint256[] amounts        // Token amounts         │
│  )                                                   │
│  ────────────────────────────────────────────────── │
│  • ReentrancyGuard protection                        │
│  • Validates array lengths match                     │
│  • Max 500 recipients per batch                      │
│  • Atomic execution (all or nothing)                 │
│  • Lower gas than individual transfers               │
└──────────────────┬──────────────────────────────────┘
                   │
                   │ 4. transferFrom() × 20 (internal loop)
                   ▼
         ┌──────────────────────┐
         │ Recipients' Wallets   │
         │ (Primary wallet addr) │
         │ Tokens appear! ✨     │
         └──────────────────────┘
```

### Community Reward Presets

The "Create Airdrop" modal will offer preset filters to reward token communities:

**1. Token Holders**
- Filter: Users with balance > minimum threshold
- Configurable: Minimum holding amount
- Use case: Reward loyal holders

**2. Chat Participants**
- Filter: Users who sent messages in token's chat
- Configurable: Minimum message count
- Use case: Reward active community members

**3. Top Traders**
- Filter: Users ranked by trading volume
- Configurable: Top N traders
- Use case: Reward market makers / high-volume traders

**4. Custom List**
- Manual entry of wallet addresses
- CSV upload support (future)
- Use case: Custom recipient selection

## Implementation Steps

### Phase 1: Smart Contract (New Deployment Required)

**File: `contracts/AirdropDistributor.sol`**
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/**
 * @title AirdropDistributor
 * @notice Helper contract for batch token transfers (airdrops)
 * @dev Separated from main contracts to avoid 24KB EVM size limit
 */
contract AirdropDistributor is ReentrancyGuard {
    event AirdropDistributed(
        address indexed token,
        address indexed distributor,
        uint256 recipientCount,
        uint256 totalAmount
    );
    
    /**
     * @notice Distribute tokens to multiple recipients in one transaction
     * @param token ERC20 token to distribute
     * @param recipients Array of recipient addresses
     * @param amounts Array of token amounts (must match recipients length)
     */
    function batchTransfer(
        address token,
        address[] calldata recipients,
        uint256[] calldata amounts
    ) external nonReentrant {
        require(recipients.length == amounts.length, "Length mismatch");
        require(recipients.length > 0, "Empty recipients");
        require(recipients.length <= 500, "Max 500 recipients"); // Gas safety
        
        IERC20 tokenContract = IERC20(token);
        uint256 totalAmount = 0;
        
        // Transfer to each recipient
        for (uint256 i = 0; i < recipients.length; i++) {
            require(recipients[i] != address(0), "Invalid recipient");
            require(amounts[i] > 0, "Invalid amount");
            
            require(
                tokenContract.transferFrom(msg.sender, recipients[i], amounts[i]),
                "Transfer failed"
            );
            
            totalAmount += amounts[i];
        }
        
        emit AirdropDistributed(token, msg.sender, recipients.length, totalAmount);
    }
}
```

**Deployment:**
- Deploy to Kasplex zkEVM Testnet
- Verify on block explorer
- Add address to `services/web3_service.py`

---

### Phase 2: Backend Integration

**File: `services/airdrop_service.py` (NEW)**
```python
from web3 import Web3
from services.web3_service import get_web3_service
import json

class AirdropService:
    def __init__(self):
        self.web3 = get_web3_service()
        # Load AirdropDistributor contract
        with open('artifacts/contracts/AirdropDistributor.sol/AirdropDistributor.json') as f:
            self.distributor_abi = json.load(f)['abi']
        
        self.distributor_address = '0x...'  # Set after deployment
    
    def build_batch_airdrop_tx(self, token_address, recipients, amounts):
        """
        Build unsigned batch airdrop transaction
        
        Args:
            token_address: BondingCurvePool contract address
            recipients: List of wallet addresses
            amounts: List of token amounts (in wei)
        
        Returns:
            dict: Unsigned transaction data for frontend signing
        """
        distributor = self.web3.w3.eth.contract(
            address=self.distributor_address,
            abi=self.distributor_abi
        )
        
        # Build transaction
        tx_data = distributor.functions.batchTransfer(
            token_address,
            recipients,
            amounts
        ).build_transaction({
            'from': '0x...',  # Caller address (from frontend)
            'gas': 0,  # Estimate separately
            'gasPrice': self.web3.w3.eth.gas_price,
            'nonce': 0  # Fetch separately
        })
        
        return tx_data
    
    def estimate_airdrop_gas(self, token_address, recipient_count):
        """Estimate gas cost for batch airdrop"""
        # Base cost + per-recipient cost
        base_gas = 50000
        per_recipient_gas = 25000
        estimated_gas = base_gas + (recipient_count * per_recipient_gas)
        
        gas_price = self.web3.w3.eth.gas_price
        cost_wei = estimated_gas * gas_price
        cost_kas = Web3.from_wei(cost_wei, 'ether')
        
        return {
            'estimated_gas': estimated_gas,
            'gas_price_gwei': Web3.from_wei(gas_price, 'gwei'),
            'cost_kas': float(cost_kas),
            'cost_usd': float(cost_kas) * self.web3.get_kas_price()
        }
```

**File: `app.py` (NEW ENDPOINT)**
```python
@app.route('/api/token/<contract_address>/airdrop/create', methods=['POST'])
@csrf.exempt
def create_airdrop(contract_address):
    """
    Create batch airdrop transaction
    
    Request:
    {
        "recipient_type": "holders" | "chat_participants" | "custom",
        "recipients": ["0x...", "0x..."],  // If custom
        "amount_per_recipient": "1000",    // Tokens per person
        "total_amount": "20000"            // Total distribution
    }
    
    Response:
    {
        "success": true,
        "tx_data": {...},           // Unsigned transaction
        "gas_estimate": {...},       // Cost breakdown
        "recipients": 20,
        "total_tokens": "20000"
    }
    """
    # Implementation here
    pass
```

---

### Phase 3: Frontend Integration

**File: `static/js/airdrop_manager.js` (NEW)**
- UI for selecting recipients (dropdown: holders, chat participants, custom)
- Gas estimate display
- Batch transaction signing via WalletManager
- Success confirmation

**File: `templates/app/token_detail.html` (MODIFY)**
- Add "Create Airdrop" button in vesting section
- Modal for airdrop configuration
- Transaction status tracking

---

## Complete Transaction Flow

### User Experience Flow:

**Step 1: Creator Navigates to Token Page**
- Creator visits their PRO token's detail page
- Sees "Vesting" section with airdrop allocation info
- Clicks "Create Airdrop" button (visible only to creator)

**Step 2: Configure Airdrop in Modal**
```
Modal opens with options:
├── Recipient Type Dropdown:
│   ├── Token Holders (min balance: ___ tokens)
│   ├── Chat Participants (min messages: ___)
│   ├── Top Traders (top ___ by volume)
│   └── Custom List (enter addresses)
│
├── Amount Per Recipient: [____] tokens
├── Preview: 20 recipients × 1000 tokens = 20,000 total
├── Unlocked Available: 5,000 tokens (5% vested today)
├── Gas Estimate: 0.0005 KAS (~$0.000027)
└── [Create Airdrop] button
```

**Step 3: Backend Fetches Recipients**
```
API: GET /api/token/<address>/airdrop/recipients?type=chat_participants&min_messages=5

Returns:
{
  "recipients": [
    {"wallet": "0xAAA...", "display_name": "User1", "messages": 15},
    {"wallet": "0xBBB...", "display_name": "User2", "messages": 12},
    ...
  ],
  "total_count": 20
}
```

**Step 4: Backend Builds Transaction Bundle**
```
API: POST /api/token/<address>/airdrop/create
Body: {
  "recipient_type": "chat_participants",
  "amount_per_recipient": "1000000000000000000000",  // 1000 tokens in wei
  "min_messages": 5
}

Backend builds 3 unsigned transactions:
├── TX 1: AirdropVesting.withdraw()
│         Gets unlocked tokens from vesting
├── TX 2: Token.approve(AirdropDistributor, 20000...)
│         Approves batch distributor
└── TX 3: AirdropDistributor.batchTransfer([recipients], [amounts])
          Distributes to all recipients

Returns: {
  "transactions": [tx1, tx2, tx3],
  "gas_estimate": {...},
  "recipients_count": 20
}
```

**Step 5: Creator Signs Transactions**
```
Frontend (WalletManager):
1. Prompts creator's wallet (MetaMask/Kastle/KasWare)
2. Shows: "Sign 3 transactions to distribute airdrop"
3. Creator signs TX 1 → TX 2 → TX 3 sequentially
4. Frontend submits signed transactions to blockchain
```

**Step 6: Execution & Confirmation**
```
Blockchain executes:
├── TX 1: Tokens → Creator's wallet ✅
├── TX 2: Approval granted ✅
└── TX 3: Batch transfer to 20 recipients ✅

All atomic - if TX 3 fails, all revert
```

**Step 7: Database Update & UI Feedback**
```
Backend saves airdrop record:
├── token_id
├── creator_id
├── recipient_type
├── recipients_count: 20
├── total_amount: 20000
├── tx_hash: 0x...
├── status: 'distributed'
└── created_at

Frontend shows:
"✅ Airdrop distributed successfully!
20 recipients received 1,000 tokens each
TX: 0x... [View on Explorer]"
```

---

## Gas Cost Analysis

### Per-Transaction Costs:
| Scenario | Recipients | Gas Used | Cost (KAS) | Cost (USD) |
|----------|-----------|----------|------------|------------|
| Small    | 20        | 550K     | 0.00055    | $0.00003   |
| Medium   | 100       | 2.55M    | 0.00255    | $0.00014   |
| Large    | 500       | 12.5M    | 0.0125     | $0.00069   |

**Current KAS Price:** $0.0548  
**Max Gas Limit:** 15M (block limit), so 500 recipients is safe

---

## Security Considerations

### Smart Contract Security:
- ✅ ReentrancyGuard on batchTransfer
- ✅ Array length validation
- ✅ Max recipient limit (500) to prevent block gas limit issues
- ✅ Zero address checks
- ✅ Uses transferFrom (requires prior approval)

### Platform Security:
- Platform wallet holds tokens temporarily
- Approval scoped to exact amount needed
- Revoke approval after distribution
- Log all distributions to database

---

## Migration Path

### For Existing PRO Tokens:
1. Platform wallet calls `AirdropVesting.withdraw()` to claim unlocked tokens
2. Platform wallet approves `AirdropDistributor` for distribution amount
3. Creator configures airdrop via UI
4. Platform wallet executes `batchTransfer()` (creator pays gas via meta-transaction OR platform subsidizes)
5. Tokens distributed atomically

### Database Updates:
- Mark airdrop records as 'distributed' after successful transaction
- Store tx_hash for verification
- Track total distributed amount

---

## Implementation Checklist

### Phase 1: Smart Contract Changes

**1.1 Update TokenFactory.sol**
- [ ] Change line 178: `address airdropBeneficiary = airdropTreasury;` → `msg.sender;`
- [ ] Compile contracts: `npx hardhat compile`
- [ ] Deploy new TokenFactory: `npx hardhat run scripts/deploy_factory.js --network kasplex_testnet`
- [ ] Save new TokenFactory address
- [ ] Update `services/web3_service.py` with new factory address

**1.2 Create AirdropDistributor.sol**
- [ ] Write `contracts/AirdropDistributor.sol` with enhanced security (from Claude's audit)
  - Pre-validate total allowance
  - Individual recipient events for audit trail
  - Optional `batchTransferEqual()` for gas optimization
- [ ] Compile: `npx hardhat compile`
- [ ] Create deployment script: `scripts/deploy_airdrop_distributor.js`
- [ ] Deploy to testnet
- [ ] Verify on Kasplex block explorer
- [ ] Test with 5 recipients (smoke test)

---

### Phase 2: Backend Implementation

**2.1 Recipient Fetching Service**
- [ ] Create `/api/token/<address>/airdrop/recipients` endpoint
  - Query param: `type` (holders|chat_participants|top_traders|custom)
  - Query param: `min_balance` (for holders)
  - Query param: `min_messages` (for chat participants)
  - Query param: `limit` (top N traders)
  - Returns: List of primary wallet addresses (User.wallet_address)
  
**2.2 Airdrop Service**
- [ ] Create `services/airdrop_service.py`
  - Load AirdropDistributor contract ABI
  - Build 3-transaction bundle (withdraw, approve, batchTransfer)
  - Gas estimation logic
  - Recipient resolution (always use primary wallet)

**2.3 Airdrop Creation Endpoint**
- [ ] Create `/api/token/<address>/airdrop/create` endpoint
  - Validate creator owns token
  - Fetch recipients based on type
  - Build unsigned transaction bundle
  - Calculate gas estimate
  - Save airdrop record to database (status='pending')
  - Return transactions + metadata

**2.4 Airdrop Confirmation Endpoint**
- [ ] Create `/api/token/<address>/airdrop/confirm` endpoint
  - Receives tx_hash after successful distribution
  - Updates database record (status='distributed')
  - Logs transaction details

**2.5 Database Model**
- [ ] Create `Airdrop` model:
  ```python
  class Airdrop(db.Model):
      id = db.Column(db.Integer, primary_key=True)
      token_id = db.Column(db.Integer, db.ForeignKey('token.id'))
      creator_id = db.Column(db.Integer, db.ForeignKey('user.id'))
      recipient_type = db.Column(db.String(32))  # holders, chat, traders, custom
      recipients_count = db.Column(db.Integer)
      total_amount = db.Column(db.Numeric(30, 0))  # Tokens distributed
      tx_hash = db.Column(db.String(128), index=True)
      status = db.Column(db.String(16))  # pending, distributed, failed
      created_at = db.Column(db.DateTime)
      distributed_at = db.Column(db.DateTime, nullable=True)
  ```

---

### Phase 3: Frontend Implementation

**3.1 Create Airdrop Button**
- [ ] Add to `templates/app/token_detail.html` in vesting section
  - Show only if current user is token creator
  - Show unlocked airdrop balance
  - Button: "Create Airdrop"

**3.2 Airdrop Modal UI**
- [ ] Create modal HTML structure:
  - Recipient type dropdown (Holders, Chat, Traders, Custom)
  - Dynamic filter inputs (min balance, min messages, etc.)
  - Amount per recipient input
  - Real-time preview (recipients count, total tokens)
  - Available unlocked balance display
  - Gas estimate display
  - Create/Cancel buttons

**3.3 Airdrop Manager JavaScript**
- [ ] Create `static/js/airdrop_manager.js`:
  - Handle modal open/close
  - Fetch recipients preview on filter change
  - Calculate totals in real-time
  - Build transaction bundle via API
  - Integrate with WalletManager for signing
  - Submit transactions sequentially (TX1 → TX2 → TX3)
  - Handle success/error states
  - Update UI with confirmation

**3.4 Transaction Monitoring**
- [ ] Poll `/api/tx/<tx_hash>/status` for TX3 (batch transfer)
- [ ] Show pending state while confirming
- [ ] Display success message with explorer link
- [ ] Update vesting balance display

---

### Phase 4: Testing

**4.1 Smart Contract Testing**
- [ ] Deploy test PRO token with new TokenFactory
- [ ] Verify creator is airdrop beneficiary
- [ ] Test AirdropDistributor with 5, 20, 100 recipients
- [ ] Measure actual gas costs
- [ ] Test failure scenarios (insufficient balance, no approval)

**4.2 Backend Testing**
- [ ] Test recipient fetching for all presets
- [ ] Verify primary wallet resolution for multi-wallet users
- [ ] Test transaction building
- [ ] Test gas estimation accuracy

**4.3 Frontend Testing**
- [ ] Test modal UI with all recipient types
- [ ] Test real-time calculations
- [ ] Test wallet signing flow (MetaMask, Kastle, KasWare)
- [ ] Test error handling (rejected signature, insufficient balance)

**4.4 End-to-End Testing**
- [ ] Create PRO token
- [ ] Wait for vesting unlock (or use time manipulation for testing)
- [ ] Create airdrop with chat participants preset
- [ ] Sign transactions
- [ ] Verify recipients received tokens
- [ ] Verify database records correct
- [ ] Test with 100+ recipients

---

## Timeline Estimate

**Total:** ~4-6 hours
- Smart Contract: 1 hour
- Deployment + Testing: 1 hour
- Backend Integration: 1.5 hours
- Frontend UI: 1.5 hours
- End-to-End Testing: 1 hour

---

## Alternative Considered (Rejected)

**Why not modify BondingCurvePool.sol?**
- ❌ Already audited - changes invalidate audit
- ❌ Already deployed - can't modify existing tokens
- ❌ 24KB size limit - adding batch logic might exceed limit
- ✅ Helper contract approach is safer and non-invasive

---

## Summary

### Changes Required

**1. TokenFactory.sol (1 line change)**
```solidity
// Line 178:
address airdropBeneficiary = msg.sender;  // Creator controls (not platform)
```

**2. New Smart Contract**
- `AirdropDistributor.sol` - Batch transfer helper (~150 lines)
- Enables atomic distribution to multiple recipients
- Follows Claude's audit recommendations

**3. Backend Implementation**
- `services/airdrop_service.py` - Transaction building
- `/api/token/<>/airdrop/recipients` - Fetch eligible users
- `/api/token/<>/airdrop/create` - Build transaction bundle
- `/api/token/<>/airdrop/confirm` - Confirm distribution
- `Airdrop` database model - Track distributions

**4. Frontend Implementation**
- "Create Airdrop" button on token detail page
- Modal with preset filters (Holders, Chat, Traders, Custom)
- Real-time recipient preview
- Gas estimation display
- Multi-step transaction signing

### Key Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Who controls tokens?** | Creator (msg.sender) | Sustainable model, no trust issues |
| **Who pays gas?** | Creator | Platform doesn't subsidize creator promotions |
| **Multi-wallet recipients?** | Primary wallet only | Simplest, most maintainable |
| **Max recipients?** | 500 per batch | Gas safety limit |
| **Recipient presets?** | Holders, Chat, Traders, Custom | Covers main use cases |

### Timeline Estimate

**Total:** ~6-8 hours
- Smart Contract: 1.5 hours (TokenFactory + AirdropDistributor)
- Deployment + Testing: 1 hour
- Backend Implementation: 2 hours
- Frontend UI: 2 hours
- End-to-End Testing: 1.5 hours

### Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| TokenFactory redeployment | Medium | Test tokens are throwaway, acceptable |
| Gas limit exceeded (500+) | Low | Hard cap at 500 recipients |
| Creator insufficient balance | Medium | Pre-validate in UI before signing |
| Wrong recipient wallet | Low | Use primary wallet (simple, predictable) |

---

**Status:** ✅ Plan Complete - Ready for User Approval  
**Risk Level:** Low (isolated changes, helper contract doesn't touch audited code)  
**Complexity:** Medium (full-stack integration with smart contract changes)  

**Next Step:** User review and approval to begin implementation
