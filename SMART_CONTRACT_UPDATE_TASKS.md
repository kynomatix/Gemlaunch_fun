# Smart Contract Update Tasks

**Last Updated:** October 21, 2025

## Overview
This document tracks the deployment of updated smart contracts to Kasplex testnet. Two contracts need deployment:

1. **TokenFactory** - Updated to give creators control of airdrop distributions (msg.sender beneficiary)
2. **AirdropDistributor** - New helper contract for batch token distributions

---

## Background

### Why This Change?

**Reference:** See `AIRDROP_BATCH_TRANSFER_PLAN.md` for complete rationale

**Creator Custody Model Benefits:**
- ✅ **Creator owns and controls their airdrop tokens** - No trust needed in platform
- ✅ **Creator pays gas for distributions** - Sustainable model for platform (no subsidy needed)
- ✅ **No custody risk** - Tokens never in platform's possession
- ✅ **Platform provides convenient UI** - "Create Airdrop" button is path of least resistance
- ✅ **Kasplex limited tooling** - Manual distribution via block explorer is expensive/annoying

**Reality Check:**
While creators technically CAN withdraw tokens manually via Kasplex block explorer and distribute themselves, the platform UI provides:
- Batch distribution (vs 20+ individual transfers)
- Lower gas costs (atomic batch vs multiple transactions)  
- Preset recipient filters (holders, chat participants, top traders)
- User-friendly interface (vs raw contract calls)

This makes the platform's "Create Airdrop" feature the natural choice for distributions.

---

### Current On-Chain State
- **TokenFactory Address:** `0x2DDb083fCd62D27E9eE1F557B53140bD61F3009D`
- **Deployed:** October 16, 2025
- **Airdrop Beneficiary Logic:** Platform's `airdropTreasury` wallet (`0x5f837F62744D4d80Fc79C3A5346B4A228956914E`)
- **Existing PRO Tokens:** 3 tokens (JAK, RX, DUMP) using platform-managed airdrops

### Desired Changes
The source code was updated on October 20, 2025 to change airdrop beneficiary from platform-managed to creator-managed:

**OLD (Currently Deployed):**
```solidity
address airdropBeneficiary = airdropTreasury;   // Platform wallet
address marketingBeneficiary = msg.sender;       // Creator wallet
address teamBeneficiary = msg.sender;            // Creator wallet
```

**NEW (Source Code - Not Deployed):**
```solidity
address airdropBeneficiary = msg.sender;         // Creator wallet
address marketingBeneficiary = msg.sender;       // Creator wallet  
address teamBeneficiary = msg.sender;            // Creator wallet
```

---

## Task List

### Task 1: Deploy AirdropDistributor Contract ⏳

**Status:** Transaction submitted, pending confirmation

**Contract:** `contracts/AirdropDistributor.sol`

**Purpose:** Helper contract for batch token distributions (airdrops to multiple recipients in single transaction)

**Details:**
- Transaction Hash: `0x5e574c3a104c01b11baff71239beb1d74d809a01ba5c21340a8d734203f6ac76`
- Explorer: https://explorer.testnet.kasplextest.xyz/tx/0x5e574c3a104c01b11baff71239beb1d74d809a01ba5c21340a8d734203f6ac76
- Status: Pending (Kasplex testnet slow block times)
- Deployment Method: Python web3.py (Hardhat/ethers.js incompatible with Kasplex RPC)

**Next Steps:**
1. Monitor transaction until confirmation
2. Extract contract address from receipt
3. Update `services/web3_service.py` with contract address:
   ```python
   AIRDROP_DISTRIBUTOR_ADDRESS = "0x<deployed_address>"
   ```
4. Test batch transfer functionality

**RPC Issue Documented:**
Kasplex testnet RPC rejects `"pending"` parameter in `eth_getTransactionCount` and other calls, causing Hardhat/ethers.js to hang. Python web3.py deployment works.

---

### Task 2: Deploy New TokenFactory Contract ⏳

**Status:** Not started

**Contract:** `contracts/TokenFactory.sol` (current source code version)

**Purpose:** Updated factory with creator-controlled airdrop distributions

**Key Changes:**
- Line 178: `address airdropBeneficiary = msg.sender;` (was `airdropTreasury`)
- Creators now control all three vesting allocations (airdrop, marketing, team)

**Deployment Steps:**

#### 2.1 Pre-Deployment Verification
- [ ] Verify current source code has `msg.sender` airdrop beneficiary logic
- [ ] Compile contracts: `npx hardhat compile --force`
- [ ] Review deployment parameters in `deployments/kasplex_testnet_factory.json`
- [ ] Ensure deployer wallet has sufficient KAS balance

#### 2.2 Deploy TokenFactory
**Method:** Python web3.py (avoids Kasplex RPC issues)

```python
# Create deployment script: scripts/deploy_token_factory_v2.py

import json
import os
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account

# Connect
w3 = Web3(Web3.HTTPProvider('https://rpc.kasplextest.xyz'))
w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

account = Account.from_key(os.environ['DEPLOYER_PRIVATE_KEY'])

# Load artifact
with open('./artifacts/contracts/TokenFactory.sol/TokenFactory.json') as f:
    artifact = json.load(f)

# Constructor parameters (from kasplex_testnet_factory.json)
constructor_params = [
    "0xe281e4776FB5De20817D0bbC72B0C4b955565619",  # graduationController
    "0xe281e4776FB5De20817D0bbC72B0C4b955565619",  # treasury
    "0x5f837F62744D4d80Fc79C3A5346B4A228956914E",  # airdropTreasury (still used for constructor, but not for beneficiary)
    "0xe281e4776FB5De20817D0bbC72B0C4b955565619",  # platformDevelopmentWallet
    "0x5f837F62744D4d80Fc79C3A5346B4A228956914E",  # graduationOracle
    "0x5f837F62744D4d80Fc79C3A5346B4A228956914E",  # admin
    "0xe281e4776FB5De20817D0bbC72B0C4b955565619",  # buybackReserve
    "0xe281e4776FB5De20817D0bbC72B0C4b955565619",  # kaspaSupport
    "0xe281e4776FB5De20817D0bbC72B0C4b955565619"   # communityRewards
]

# Encode constructor
TokenFactory = w3.eth.contract(abi=artifact['abi'], bytecode=artifact['bytecode'])
tx_data = TokenFactory.constructor(*constructor_params).build_transaction({
    'from': account.address,
    'nonce': w3.eth.get_transaction_count(account.address),
    'gas': 5000000,
    'gasPrice': w3.eth.gas_price,
    'chainId': 167012
})

# Sign and send
signed = account.sign_transaction(tx_data)
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
print(f"TX: {tx_hash.hex()}")

# Wait for receipt
receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
print(f"Deployed: {receipt['contractAddress']}")
```

**Execution:**
```bash
python3 scripts/deploy_token_factory_v2.py
```

#### 2.3 Post-Deployment Tasks
- [ ] Save deployment info to `deployments/token_factory_v2_kasplex_testnet.json`
- [ ] Update `services/web3_service.py` with new address:
  ```python
  TOKEN_FACTORY_ADDRESS = "0x<new_deployed_address>"
  ```
- [ ] Update VestingDeployer address if factory deploys new one
- [ ] Verify contract on Blockscout (optional)

#### 2.4 Verification & Testing
- [ ] Deploy test PRO token using new factory
- [ ] Verify airdrop vesting beneficiary = creator wallet (not platform)
- [ ] Verify marketing vesting beneficiary = creator wallet
- [ ] Verify team vesting beneficiary = creator wallet
- [ ] Test withdrawal from all three vesting contracts
- [ ] Confirm UI displays vesting status correctly

#### 2.5 Database & Frontend Updates
- [ ] No database migrations required (schema unchanged)
- [ ] Frontend token creation flow unchanged (users won't notice)
- [ ] Airdrop distribution UI will work with creator-controlled vesting

---

## Migration Strategy

### Option A: Clean Cutover (Recommended)
1. Deploy new TokenFactory
2. Update `TOKEN_FACTORY_ADDRESS` in code
3. All future PRO tokens use new factory (creator-controlled airdrops)
4. Existing 3 PRO tokens remain on old factory (platform-managed airdrops)

**Pros:**
- Simple, no data migration
- Existing tokens unaffected
- Clear distinction between old/new tokens

**Cons:**
- Two TokenFactory contracts active
- Inconsistent behavior for users (old vs new tokens)

### Option B: Full Migration
1. Deploy new TokenFactory
2. Mark old factory as deprecated in database
3. Create migration script to flag old PRO tokens
4. Update UI to show different airdrop controls based on factory version

**Pros:**
- Clear user communication
- Can support both token types

**Cons:**
- More complex implementation
- Requires UI changes

---

## Known Issues & Workarounds

### Issue Report: Kasplex RPC Compatibility Problems

**Discovered:** October 21, 2025 during AirdropDistributor deployment

#### Problem 1: RPC Rejects "pending" Parameter

**Symptom:** Hardhat and ethers.js deployments hang indefinitely with no error

**Root Cause:** Kasplex testnet RPC returns error for `"pending"` parameter:
```json
{
  "code": -32600,
  "message": "invalid request"
}
```

**Affected RPC Calls:**
- `eth_getTransactionCount(address, "pending")` - Used by ethers.js to get nonce
- `eth_getBlockByNumber("latest", false)` - Also causes issues
- Any call with `"pending"` block parameter

**Affected Tools:**
- ❌ Hardhat deployment scripts (`npx hardhat run scripts/deploy_*.js`)
- ❌ ethers.js v6 provider initialization (tries to auto-detect network)
- ❌ Any deployment workflow using standard Ethereum tooling

**Example Error:**
```
Error: could not coalesce error 
(error={ "code": -32600, "message": "invalid request" }, 
payload={ "id": 2, "jsonrpc": "2.0", "method": "eth_getTransactionCount", 
"params": [ "0xe281e4776fb5de20817d0bbc72b0c4b955565619", "pending" ] }, 
code=UNKNOWN_ERROR, version=6.15.0)
```

**Workaround - Use Python web3.py:**
```python
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

w3 = Web3(Web3.HTTPProvider('https://rpc.kasplextest.xyz'))
w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

# Use 'latest' instead of 'pending'
nonce = w3.eth.get_transaction_count(account.address, 'latest')  # ✅ Works
```

**Why Python Works:**
- web3.py doesn't default to `"pending"` parameter
- Can explicitly specify `"latest"` for block parameter
- POA middleware handles Kasplex's consensus quirks

---

#### Problem 2: Extremely Slow Block Times

**Symptom:** Transactions remain pending for 2+ minutes

**Impact on Deployment:**
- Standard 60s timeouts fail
- Cannot verify deployment success quickly
- Difficult to debug issues (transaction vs network problem?)

**Example:**
```
AirdropDistributor Deployment:
- TX Sent: October 21, 2025
- TX Hash: 0x5e574c3a104c01b11baff71239beb1d74d809a01ba5c21340a8d734203f6ac76
- Status: Still pending after 2+ minutes
- Explorer: Shows "pending" status
```

**Workaround:**
```python
# Use very long timeout (5+ minutes)
receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

# Or poll manually with status checks
for i in range(30):  # 5 minutes = 30 × 10s
    sleep(10)
    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        if receipt:
            print(f"Confirmed in block {receipt['blockNumber']}")
            break
    except:
        print(f"Still pending... ({i+1}/30)")
```

---

#### Problem 3: TestMinimal Deploys, AirdropDistributor Hangs

**Observation:** Small contracts deploy fine, larger contracts hang

**Test Results:**
- ✅ `TestMinimal.sol` (few functions) - Deploys successfully in ~30s
- ❌ `AirdropDistributor.sol` (ReentrancyGuard + loops) - Hangs indefinitely

**Hypothesis:**
- Larger bytecode may require more gas
- Default gas estimation hitting issues
- RPC may be throttling complex deployments

**Attempted Solutions:**
1. ❌ Hardhat with increased gas limit - Still hangs
2. ❌ ethers.js with manual gas - RPC compatibility error
3. ⏳ Python web3.py with high gas limit - Transaction sent but pending

**Current Status:**
Transaction successfully submitted via Python, waiting for testnet to mine block.

---

### Deployment Strategy Going Forward

**For All Future Contract Deployments:**

1. **Use Python web3.py exclusively** - No Hardhat/ethers.js for Kasplex
2. **Set long timeouts** - Minimum 300s (5 minutes)
3. **Manual monitoring** - Check explorer for confirmation
4. **Test small contracts first** - Verify network health before large deployments

**Template for Kasplex Deployments:**
```python
import json, os, time
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account

def deploy_contract(artifact_path, constructor_args=[]):
    # Connect
    w3 = Web3(Web3.HTTPProvider('https://rpc.kasplextest.xyz'))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    
    account = Account.from_key(os.environ['DEPLOYER_PRIVATE_KEY'])
    
    # Load artifact
    with open(artifact_path) as f:
        artifact = json.load(f)
    
    # Build transaction
    Contract = w3.eth.contract(abi=artifact['abi'], bytecode=artifact['bytecode'])
    tx_data = Contract.constructor(*constructor_args).build_transaction({
        'from': account.address,
        'nonce': w3.eth.get_transaction_count(account.address, 'latest'),
        'gas': 5000000,  # High gas limit
        'gasPrice': w3.eth.gas_price,
        'chainId': 167012
    })
    
    # Sign and send
    signed = account.sign_transaction(tx_data)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"TX: {tx_hash.hex()}")
    print(f"Explorer: https://explorer.testnet.kasplextest.xyz/tx/{tx_hash.hex()}")
    
    # Wait with long timeout
    print("Waiting for confirmation (5 min timeout)...")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
    
    print(f"✅ Deployed: {receipt['contractAddress']}")
    return receipt['contractAddress']
```

---

## Rollback Plan

If new TokenFactory has issues:

1. **Immediate Rollback:**
   ```python
   TOKEN_FACTORY_ADDRESS = "0x2DDb083fCd62D27E9eE1F557B53140bD61F3009D"  # Revert to old
   ```

2. **No Database Changes Required** - Schema unchanged

3. **Monitor Existing Tokens** - Old tokens continue working

4. **Debugging New Contract:**
   - Check constructor parameters
   - Verify vesting deployer integration
   - Test on fresh wallet with minimal PRO token

---

## Success Criteria

### AirdropDistributor Deployment
- ✅ Contract deployed successfully
- ✅ Address saved to `services/web3_service.py`
- ✅ Batch transfer tested (2-3 recipients)
- ✅ Gas costs documented
- ✅ UI integration tested

### TokenFactory V2 Deployment
- ✅ Contract deployed successfully  
- ✅ VestingDeployer integration verified
- ✅ Test PRO token created with new factory
- ✅ Airdrop beneficiary = creator wallet confirmed on-chain
- ✅ All three vesting types withdraw successfully
- ✅ No regressions in BASIC token creation
- ✅ UI displays vesting info correctly

---

## Timeline

**AirdropDistributor:**
- Submitted: October 21, 2025
- Expected: Waiting for testnet confirmation
- ETA: When testnet speeds up (check periodically)

**TokenFactory V2:**
- Planning: October 21, 2025
- Deployment: TBD (waiting for user confirmation)
- Testing: 1-2 hours after deployment
- Production: Immediate (update address in code)

---

## Resources

**Deployment Files:**
- `contracts/TokenFactory.sol` - Updated factory contract
- `contracts/AirdropDistributor.sol` - Batch distribution helper
- `deployments/kasplex_testnet_factory.json` - Current deployment info
- `services/web3_service.py` - Contract addresses

**Documentation:**
- `PRO_TOKEN_VESTING_SPECIFICATION_V2.md` - Vesting system spec
- `VESTING_IMPLEMENTATION_NOTES.md` - Implementation details
- `SMART_CONTRACT_IMPLEMENTATION.md` - Contract architecture

**Network:**
- RPC: `https://rpc.kasplextest.xyz`
- Explorer: `https://explorer.testnet.kasplextest.xyz`
- Chain ID: `167012`
