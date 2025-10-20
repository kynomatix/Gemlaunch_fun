# Airdrop Batch Transfer Implementation Plan

## Problem Identified
**Critical Design Gap:** Airdrops are ALWAYS batch transfers (20-500 recipients), but current smart contracts only support single `transfer()` calls. This results in:
- ❌ Non-atomic distributions (20 separate transactions)
- ❌ High gas costs (20x transaction overhead)
- ❌ Poor UX (each transfer could fail independently)

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

### Architecture
```
┌─────────────────────────────────────────────────────┐
│  AirdropVesting.sol (holds 33% tokens)              │
│  Beneficiary: Platform Wallet                        │
└──────────────────┬──────────────────────────────────┘
                   │ withdraw() → Platform Wallet
                   ▼
┌─────────────────────────────────────────────────────┐
│  Platform Wallet                                     │
│  - Receives unlocked tokens from AirdropVesting     │
│  - Approves tokens to AirdropDistributor            │
└──────────────────┬──────────────────────────────────┘
                   │ approve() + batchTransfer()
                   ▼
┌─────────────────────────────────────────────────────┐
│  AirdropDistributor.sol (NEW HELPER)                │
│  - batchTransfer(token, recipients[], amounts[])    │
│  - ONE atomic transaction                           │
│  - Lower gas (no per-tx overhead)                   │
└──────────────────┬──────────────────────────────────┘
                   │ transferFrom() × 20 (in loop)
                   ▼
         ┌──────────────────────┐
         │ Recipients' Wallets   │
         │ Tokens appear! ✨     │
         └──────────────────────┘
```

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

## Transaction Flow

### Step-by-Step Execution:

**1. Platform Wallet Preparation (Backend)**
```
AirdropVesting.withdraw()
  ↓ Platform wallet receives unlocked tokens
Token.approve(AirdropDistributor, totalAmount)
  ↓ Platform wallet approves distributor to spend
```

**2. Creator Initiates Airdrop (Frontend)**
```
Creator selects: "Active Chat Participants" (20 people)
  ↓
Backend calculates amounts: 1000 tokens each
  ↓
Gas estimate: 0.5M gas × 1 gwei = 0.0005 KAS (~$0.00003)
  ↓
Creator confirms
```

**3. Batch Transfer (Atomic)**
```
AirdropDistributor.batchTransfer(
  tokenAddress,
  [0xAAA, 0xBBB, ...],  // 20 addresses
  [1000, 1000, ...]     // 1000 tokens each
)
  ↓ ONE transaction
  ↓ 20 transferFrom() calls internally
  ↓ All succeed or all revert (atomic)
```

**4. Completion**
```
Database: Mark airdrop as 'distributed'
Frontend: Show success message
Recipients: Tokens appear in wallets ✨
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

## Deployment Checklist

**Smart Contract:**
- [ ] Write `AirdropDistributor.sol`
- [ ] Compile with Hardhat
- [ ] Deploy to Kasplex testnet
- [ ] Verify contract on block explorer
- [ ] Test with small batch (5 recipients)

**Backend:**
- [ ] Add AirdropDistributor address to config
- [ ] Implement `airdrop_service.py`
- [ ] Create `/api/token/<>/airdrop/create` endpoint
- [ ] Test approval + batch transfer flow

**Frontend:**
- [ ] Add "Create Airdrop" button to token detail page
- [ ] Build airdrop configuration modal
- [ ] Integrate with WalletManager for signing
- [ ] Display gas estimates

**Testing:**
- [ ] Test with 5, 20, 100 recipients
- [ ] Verify gas costs
- [ ] Test failure scenarios (insufficient balance, approval)
- [ ] End-to-end airdrop flow

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

## Questions to Resolve

1. **Who pays gas?** Creator's wallet (recommended) OR Platform subsidizes?
2. **Max recipients per batch?** 500 (safe) or allow higher with warning?
3. **Approval flow?** Manual approve + batchTransfer OR meta-transaction?
4. **Recipient selection UI?** Dropdown (holders, chat) OR manual CSV upload?

---

**Status:** Ready for implementation pending approval
**Risk Level:** Low (isolated helper contract, doesn't touch audited code)
**Complexity:** Medium (new contract + full-stack integration)
