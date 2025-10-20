# Airdrop Implementation Proposal

**Status:** Proposal - Awaiting User Approval  
**Date:** January 2025

---

## Executive Summary

**Current State:** Airdrop vesting contracts exist, but there's no way for creators to distribute tokens to their communities.

**Proposed Solution:** 
1. Change who controls airdrop tokens (platform → creator)
2. Add batch transfer helper contract for gas-efficient distributions
3. Build UI for creators to manage airdrops

**Critical Decision Needed:** Should creators control their own airdrop tokens, or should platform hold them in custody?

---

## Current Architecture (As-Is)

### How PRO Token Vesting Works Now:

```
Creator deploys PRO token with:
├── reservedPercentage: 0-25% (user configurable)
└── Vesting allocation breakdown (user configurable):
    ├── Airdrop: X% of reserved (e.g., 33%, 50%, 100%)
    ├── Marketing: Y% of reserved (e.g., 33%, 25%, 0%)
    └── Team: Z% of reserved (e.g., 34%, 25%, 0%)
    
Example: 15% reserved, 40% airdrop = 6% of total supply
```

**Deployed Vesting Contracts:**
- `AirdropVesting.sol` → Beneficiary = **Platform Wallet** (0x5f837...)
- `MarketingVesting.sol` → Beneficiary = **Creator Wallet**
- `TeamVesting.sol` → Beneficiary = **Creator Wallet**

**Problem:** Creator controls marketing/team vesting, but platform controls airdrop vesting.

### Why This Is An Issue:

**Trust Problem:**
- Users see: "33% locked in vesting" (or whatever % they chose)
- Reality: Platform wallet can withdraw those tokens
- Trust concern: What if platform rugs?

**Control Problem:**
- Creator can't manage their own community rewards
- Creator must ask platform to distribute tokens
- Platform pays gas (or complex meta-transaction system needed)

**Claude's Audit Finding:**
> "This is backwards! The creator should control their own airdrops."

---

## Proposed Architecture (To-Be)

### Option A: Creator Custody (Recommended by Claude)

**Change TokenFactory.sol line 178:**
```solidity
// FROM:
address airdropBeneficiary = airdropTreasury;   // Platform wallet

// TO:
address airdropBeneficiary = msg.sender;        // Creator wallet
```

**Flow:**
```
AirdropVesting.sol
  ↓ beneficiary = Creator's Wallet
  ↓
Creator withdraws unlocked tokens
  ↓
Creator uses platform's "Create Airdrop" UI
  ↓
Creator's wallet approves AirdropDistributor helper
  ↓
Creator's wallet signs batchTransfer()
  ↓
Tokens distributed to recipients atomically
  ↓
Creator pays gas (~0.0005 KAS for 20 people)
```

**Pros:**
- ✅ Creator controls their own tokens
- ✅ No trust issues
- ✅ Platform is just a tool, not custodian
- ✅ Matches industry standard (Sablier, etc.)

**Cons:**
- ❌ Requires redeploying TokenFactory
- ❌ Existing test tokens stuck with old architecture
- ❌ Creator pays gas for airdrops

---

### Option B: Platform Custody (Current)

**Keep everything as-is**, just add distribution tools.

**Flow:**
```
AirdropVesting.sol
  ↓ beneficiary = Platform Wallet
  ↓
Platform withdraws unlocked tokens
  ↓
Creator configures airdrop via UI
  ↓
Platform's wallet approves AirdropDistributor
  ↓
Platform's wallet signs batchTransfer()
  ↓
Tokens distributed to recipients
  ↓
Platform pays gas (or creator via meta-tx)
```

**Pros:**
- ✅ No smart contract changes needed
- ✅ Works with existing deployed contracts
- ✅ Ship faster

**Cons:**
- ❌ Platform holds tokens in custody (trust issue)
- ❌ Platform pays gas (or complex meta-tx system)
- ❌ Not industry standard

---

## Required Components (Both Options)

### 1. AirdropDistributor.sol (NEW Helper Contract)

**Purpose:** Enable atomic batch transfers in one transaction

**Why needed:** 
- Standard ERC20 `transfer()` = one recipient per transaction
- 20 recipients = 20 separate transactions = high gas + not atomic
- Batch transfer = one transaction = lower gas + atomic

**Contract:**
```solidity
contract AirdropDistributor {
    function batchTransfer(
        address token,
        address[] recipients,
        uint256[] amounts
    ) external {
        // Validates arrays match
        // Calls transferFrom() in loop
        // All succeed or all revert (atomic)
    }
}
```

**Gas Savings:**
- Without: 20 txs × 50K gas = 1M gas total
- With: 1 tx × 550K gas = 550K gas (45% savings)

---

### 2. Multi-Wallet Recipient Logic

**Problem Claude Identified:**
```
User has 3 wallets linked to profile:
├── Wallet A (primary): 0xAAA...
├── Wallet B: 0xBBB...
└── Wallet C: 0xCCC...

User participates in token chat using Wallet B
Airdrop goes to "default wallet" (Wallet A)
User checks Wallet B → sees nothing → complains
```

**Solution:**
Track which wallet user engaged with, send airdrop there.

**Implementation:**
```python
def get_airdrop_recipient_address(user, token):
    """
    Priority:
    1. Wallet that holds the token (if any)
    2. Wallet used in token's chat (if chat exists)
    3. User's primary wallet
    """
    # Check which wallet holds this token
    for wallet in user.linked_wallets:
        if has_balance(wallet.address, token):
            return wallet.address
    
    # Check which wallet user chatted with
    last_message = get_last_chat_message(user, token)
    if last_message:
        return last_message.wallet_address
    
    # Fallback to primary
    return user.wallet_address
```

---

### 3. Backend API

**Endpoint:** `/api/token/<address>/airdrop/create`

**Request:**
```json
{
  "recipient_type": "holders" | "chat_participants" | "top_traders" | "custom",
  "recipients": ["0x...", "0x..."],  // if custom
  "amount_per_recipient": "1000",    // tokens
  "min_holding": "100"               // if holders type
}
```

**Response:**
```json
{
  "success": true,
  "tx_data": {
    "to": "0x...",           // AirdropDistributor address
    "data": "0x...",         // Encoded batchTransfer call
    "value": "0",
    "gas": 550000
  },
  "recipients": 20,
  "total_tokens": "20000",
  "gas_estimate": {
    "kas": "0.0005",
    "usd": "$0.000027"
  }
}
```

---

### 4. Frontend UI

**Location:** Token detail page (vesting section)

**Components:**
- "Create Airdrop" button (visible to creator only)
- Modal with:
  - Recipient selection dropdown
  - Amount input
  - Gas estimate display
  - Confirmation button
- Transaction signing via WalletManager
- Status tracking (pending → confirmed)

---

## Decision Matrix

| Factor | Option A (Creator Custody) | Option B (Platform Custody) |
|--------|---------------------------|----------------------------|
| **Trust Model** | ✅ Trustless (creator controls) | ❌ Trusted (platform controls) |
| **Gas Payment** | Creator pays | Platform pays (or complex meta-tx) |
| **Industry Standard** | ✅ Yes (Sablier, etc.) | ❌ No |
| **Time to Ship** | ~6 hours (redeploy needed) | ~4 hours (use existing) |
| **Test Token Impact** | Old tokens stuck | Works with existing |
| **Smart Contract Changes** | 1 line + helper contract | Helper contract only |
| **Complexity** | Medium | Low |

---

## Implementation Checklist

### Phase 1: Smart Contract
- [ ] **Decision:** Creator custody (Option A) or Platform custody (Option B)?
- [ ] Write AirdropDistributor.sol helper contract
- [ ] If Option A: Change TokenFactory.sol beneficiary line
- [ ] Compile contracts
- [ ] Deploy to testnet
- [ ] Verify on block explorer

### Phase 2: Backend
- [ ] Implement multi-wallet recipient logic
- [ ] Create `airdrop_service.py` with batch transfer building
- [ ] Add `/api/token/<>/airdrop/create` endpoint
- [ ] Add `/api/token/<>/airdrop/recipients` endpoint (fetch eligible users)
- [ ] Test gas estimation

### Phase 3: Frontend
- [ ] Add "Create Airdrop" button to token detail page
- [ ] Build airdrop configuration modal
- [ ] Integrate WalletManager for transaction signing
- [ ] Add transaction status tracking
- [ ] Display success/error states

### Phase 4: Testing
- [ ] Deploy new PRO token (or use existing for Option B)
- [ ] Create airdrop with 5 recipients
- [ ] Verify atomic distribution
- [ ] Test gas costs
- [ ] Verify multi-wallet recipient logic
- [ ] Test failure scenarios

---

## Open Questions for User

1. **Custody Model:** Option A (creator controls) or Option B (platform controls)?

2. **Test Tokens:** Your existing test tokens - are they throwaway or do they need to keep working?

3. **Gas Payment:** Who should pay for airdrop distributions?
   - Option A: Creator pays (simple)
   - Option B: Platform subsidizes (requires funding oracle wallet)
   - Option C: Meta-transaction (complex)

4. **Recipient Selection:** What filters should creators have?
   - Token holders (min balance threshold)
   - Chat participants (min message count)
   - Top traders (by volume)
   - Custom list (CSV upload)
   - All of the above?

5. **Max Recipients:** Should there be a limit per airdrop?
   - Suggested: 500 (gas safety)
   - Allow batching for larger distributions?

6. **Deployment Timeline:** How urgent is this feature?
   - Critical (ship this week)
   - Important (ship this month)
   - Nice-to-have (backlog)

---

## Security Considerations

### Smart Contract Security:
- ✅ ReentrancyGuard on batch transfer
- ✅ Array length validation
- ✅ Gas limit protection (500 max recipients)
- ✅ Zero address checks
- ✅ Allowance validation before loop
- ⚠️ Duplicate recipient detection (optional)

### Platform Security:
- Token approval scoped to exact amount
- Revoke approval after distribution
- Log all distributions to database
- Rate limiting on airdrop creation

---

## Cost Analysis

**Contract Deployment:**
- AirdropDistributor: ~0.005 KAS (one-time)
- TokenFactory (if Option A): ~0.015 KAS (one-time)

**Per-Airdrop Costs:**
| Recipients | Gas | Cost (KAS) | Cost (USD) |
|-----------|-----|------------|------------|
| 20 | 550K | 0.0005 | $0.000027 |
| 100 | 2.5M | 0.0025 | $0.00014 |
| 500 | 12.5M | 0.0125 | $0.00069 |

*(Based on KAS = $0.0548)*

---

## Next Steps

**Awaiting User Decision:**
1. Choose custody model (Option A vs B)
2. Answer open questions above
3. Review and approve this plan

**After Approval:**
1. Implement chosen architecture
2. Test thoroughly
3. Deploy to production
4. Update documentation

---

**Status:** 🟡 Proposal - No implementation started  
**Blocker:** Need user decision on custody model and open questions
