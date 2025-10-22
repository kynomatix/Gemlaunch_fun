# Kaspa Finance DEX Trading Integration Plan

**Date**: October 2025  
**Status**: Planning Phase  
**Goal**: Enable continuous trading of graduated tokens on gemlaunch.fun via Kaspa Finance DEX

---

## 📋 Executive Summary

Currently, when tokens graduate from the bonding curve to Kaspa Finance DEX, trading stops on gemlaunch.fun. Users must leave the platform to trade on Kaspa Finance directly. This integration will allow graduated tokens to continue trading seamlessly on gemlaunch.fun by routing trades through Kaspa Finance DEX in the backend.

**User Experience**: No change - users click Buy/Sell as usual  
**Backend Routing**: Pre-graduation → BondingCurvePool | Post-graduation → Kaspa Finance SwapRouter

---

## 🎯 Objectives

1. **Continuous Trading**: Graduated tokens remain tradable on gemlaunch.fun
2. **Transparent Routing**: Backend detects graduation status and routes appropriately
3. **Unified UX**: Same frontend interface for both bonding curve and DEX trades
4. **Real Liquidity**: All trades execute against real Kaspa Finance DEX pools

---

## 🏗️ Architecture Overview

### Current Flow (Pre-Graduation)
```
User → Frontend → API → BondingCurvePool.buyTokens() → Blockchain
```

### New Flow (Post-Graduation)
```
User → Frontend → API → QuoterV2 (quote) → SwapRouter.exactInputSingle() → Kaspa Finance Pool → Blockchain
```

### Routing Logic
```python
if token.is_graduated:
    # Route to Kaspa Finance DEX
    quote = quoter_v2.quoteExactInputSingle(...)
    tx = swap_router.exactInputSingle(...)
else:
    # Route to bonding curve
    quote = bonding_pool.getBuyQuote(...)
    tx = bonding_pool.buyTokens(...)
```

---

## 📦 Smart Contract Addresses (Kasplex Testnet)

| Contract | Address | Purpose |
|----------|---------|---------|
| **SwapRouter** | `0xDf88D478aF51C0AB616aFBfDD933c874e142858c` | Execute DEX trades |
| **QuoterV2** | `0x3ACc31F8fe86E365604eAa6dDCbcB7fEba7a4c2B` | Get price quotes |
| **WKAS** | `0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94` | Wrapped KAS token |
| **Factory** | `0x1b72D7165a0D7256a4F197765C15bb70bC5D66A8` | Pool factory |
| **NFT Position Manager** | `0x4E25637cF39822364b877F81B18c5B6CF0eeF589` | Liquidity positions |

**Fee Tier**: 0.05% (500 basis points) or 0.25% (2500 basis points) - TBD based on graduation contract configuration

---

## 🔧 Implementation Phases

### **Phase 1: Backend Infrastructure** ✅ IN PROGRESS

#### Task 1.1: Add DEX Contract ABIs
- [x] Create `artifacts/contracts/ISwapRouter.json` with Uniswap V3 SwapRouter ABI
- [x] Create `artifacts/contracts/IQuoterV2.json` with QuoterV2 ABI  
- [x] Create `artifacts/contracts/IWKAS.json` with WKAS (Wrapped KAS) ABI
- [x] Add Kaspa Finance addresses to `services/web3_service.py`

**Status**: Complete ✅

#### Task 1.2: Extend Web3Service Contract Loading
**File**: `services/web3_service.py`

Add to `_load_contracts()` method:
```python
# Load Kaspa Finance DEX contracts
quoter_v2_abi = self._load_contract_abi_json('IQuoterV2')
contracts['QuoterV2'] = self.w3.eth.contract(
    address=Web3.to_checksum_address(KASPA_FINANCE_QUOTER_V2),
    abi=quoter_v2_abi
)

swap_router_abi = self._load_contract_abi_json('ISwapRouter')
contracts['SwapRouter'] = self.w3.eth.contract(
    address=Web3.to_checksum_address(KASPA_FINANCE_SWAP_ROUTER),
    abi=swap_router_abi
)

wkas_abi = self._load_contract_abi_json('IWKAS')
contracts['WKAS'] = self.w3.eth.contract(
    address=Web3.to_checksum_address(KASPA_FINANCE_WKAS),
    abi=wkas_abi
)
```

**New Helper Method**:
```python
def _load_contract_abi_json(self, contract_name):
    """Load ABI from JSON file (for Kaspa Finance contracts)"""
    abi_path = ARTIFACTS_DIR / f"{contract_name}.json"
    with open(abi_path, 'r') as f:
        return json.load(f)['abi']
```

#### Task 1.3: Implement DEX Quote Methods
**File**: `services/web3_service.py`

```python
def get_dex_buy_quote(self, token_address, kas_amount_wei, fee_tier=FEE_TIER_005):
    """
    Get DEX buy quote using QuoterV2
    Buying tokens with KAS means: KAS (WKAS) → Token
    
    Returns:
        dict: {
            'tokens_out': int,
            'price_impact': float,
            'gas_estimate': int,
            'fee_tier': int
        }
    """
    quoter = self.contracts['QuoterV2']
    
    # For buying tokens: tokenIn = WKAS, tokenOut = Token
    result = quoter.functions.quoteExactInputSingle(
        KASPA_FINANCE_WKAS,           # tokenIn (WKAS)
        token_address,                 # tokenOut (Token)
        kas_amount_wei,                # amountIn (KAS to spend)
        fee_tier,                      # fee (500 = 0.05%)
        0                              # sqrtPriceLimitX96 (0 = no limit)
    ).call()
    
    tokens_out = result[0]
    gas_estimate = result[3]
    
    return {
        'tokens_out': tokens_out,
        'price_impact': 0,  # TODO: Calculate from sqrtPriceX96
        'gas_estimate': gas_estimate,
        'fee_tier': fee_tier
    }

def get_dex_sell_quote(self, token_address, token_amount, fee_tier=FEE_TIER_005):
    """
    Get DEX sell quote using QuoterV2
    Selling tokens for KAS means: Token → KAS (WKAS)
    
    Returns:
        dict: {
            'kas_out_wei': int,
            'price_impact': float,
            'gas_estimate': int,
            'fee_tier': int
        }
    """
    quoter = self.contracts['QuoterV2']
    
    # For selling tokens: tokenIn = Token, tokenOut = WKAS
    result = quoter.functions.quoteExactInputSingle(
        token_address,                 # tokenIn (Token)
        KASPA_FINANCE_WKAS,           # tokenOut (WKAS)
        token_amount,                  # amountIn (tokens to sell)
        fee_tier,                      # fee (500 = 0.05%)
        0                              # sqrtPriceLimitX96 (0 = no limit)
    ).call()
    
    kas_out_wei = result[0]
    gas_estimate = result[3]
    
    return {
        'kas_out_wei': kas_out_wei,
        'price_impact': 0,  # TODO: Calculate from sqrtPriceX96
        'gas_estimate': gas_estimate,
        'fee_tier': fee_tier
    }
```

#### Task 1.4: Implement DEX Transaction Builders
**File**: `services/web3_service.py`

```python
def build_dex_buy_tx(self, token_address, kas_amount_wei, min_tokens_out, user_address, deadline, fee_tier=FEE_TIER_005):
    """
    Build unsigned DEX buy transaction
    User must:
    1. Have KAS balance >= kas_amount_wei
    2. Transaction will wrap KAS → WKAS automatically via msg.value
    
    Returns:
        dict: {
            'to': str (SwapRouter address),
            'value': int (KAS amount in wei),
            'data': str (encoded function call),
            'gas': int (estimated gas)
        }
    """
    swap_router = self.contracts['SwapRouter']
    
    # Build swap params (KAS → Token via WKAS)
    params = {
        'tokenIn': KASPA_FINANCE_WKAS,
        'tokenOut': token_address,
        'fee': fee_tier,
        'recipient': user_address,
        'deadline': deadline,
        'amountIn': kas_amount_wei,
        'amountOutMinimum': min_tokens_out,
        'sqrtPriceLimitX96': 0  # No price limit
    }
    
    # Build transaction
    tx_data = swap_router.functions.exactInputSingle(params).build_transaction({
        'from': user_address,
        'value': kas_amount_wei,  # Send KAS with transaction
        'gas': 0,  # Will be estimated
        'gasPrice': self.w3.eth.gas_price,
        'nonce': self.w3.eth.get_transaction_count(user_address)
    })
    
    # Estimate gas
    gas_estimate = self.estimate_gas(tx_data)
    tx_data['gas'] = gas_estimate
    
    return {
        'to': KASPA_FINANCE_SWAP_ROUTER,
        'value': hex(kas_amount_wei),
        'data': tx_data['data'],
        'gas': hex(gas_estimate)
    }

def build_dex_sell_tx(self, token_address, token_amount, min_kas_out_wei, user_address, deadline, fee_tier=FEE_TIER_005):
    """
    Build unsigned DEX sell transaction
    User must:
    1. Approve SwapRouter to spend tokens first
    2. Have token balance >= token_amount
    
    Returns:
        dict: {
            'to': str (SwapRouter address),
            'value': 0,
            'data': str (encoded function call),
            'gas': int (estimated gas),
            'requires_approval': bool,
            'approval_target': str (token address),
            'approval_amount': int
        }
    """
    swap_router = self.contracts['SwapRouter']
    
    # Check current approval
    token_contract = self.get_bonding_pool_contract(token_address)
    current_allowance = token_contract.functions.allowance(
        user_address,
        KASPA_FINANCE_SWAP_ROUTER
    ).call()
    
    requires_approval = current_allowance < token_amount
    
    # Build swap params (Token → WKAS → KAS)
    params = {
        'tokenIn': token_address,
        'tokenOut': KASPA_FINANCE_WKAS,
        'fee': fee_tier,
        'recipient': user_address,  # Receives WKAS, need to unwrap separately
        'deadline': deadline,
        'amountIn': token_amount,
        'amountOutMinimum': min_kas_out_wei,
        'sqrtPriceLimitX96': 0
    }
    
    tx_data = swap_router.functions.exactInputSingle(params).build_transaction({
        'from': user_address,
        'value': 0,
        'gas': 0,
        'gasPrice': self.w3.eth.gas_price,
        'nonce': self.w3.eth.get_transaction_count(user_address)
    })
    
    gas_estimate = self.estimate_gas(tx_data)
    tx_data['gas'] = gas_estimate
    
    return {
        'to': KASPA_FINANCE_SWAP_ROUTER,
        'value': '0x0',
        'data': tx_data['data'],
        'gas': hex(gas_estimate),
        'requires_approval': requires_approval,
        'approval_target': token_address,
        'approval_amount': token_amount
    }
```

---

### **Phase 2: API Layer Updates**

#### Task 2.1: Update Quote Endpoints
**File**: `app.py`

Modify `/api/trade/quote-buy` and `/api/trade/quote-sell`:

```python
@app.route('/api/trade/quote-buy', methods=['POST'])
def api_quote_buy():
    data = request.get_json()
    token_address = data.get('token_address')
    kas_amount = float(data.get('kas_amount'))
    
    # Get token from database
    token = Token.query.filter(
        db.func.lower(Token.contract_address) == token_address.lower()
    ).first_or_404()
    
    web3_service = get_web3_service()
    kas_amount_wei = web3_service.w3.to_wei(kas_amount, 'ether')
    
    if token.is_graduated:
        # Route to Kaspa Finance DEX
        quote = web3_service.get_dex_buy_quote(token_address, kas_amount_wei)
        
        return jsonify({
            'success': True,
            'routing': 'dex',
            'tokens_out': quote['tokens_out'],
            'tokens_out_formatted': web3_service.w3.from_wei(quote['tokens_out'], 'ether'),
            'price_impact': quote['price_impact'],
            'gas_estimate': quote['gas_estimate'],
            'fee_tier': quote['fee_tier'],
            'dex': 'Kaspa Finance'
        })
    else:
        # Route to bonding curve (existing logic)
        pool = web3_service.get_bonding_pool_contract(token_address)
        tokens_out = pool.functions.getBuyQuote(kas_amount_wei).call()
        
        return jsonify({
            'success': True,
            'routing': 'bonding_curve',
            'tokens_out': tokens_out,
            # ... existing response
        })
```

#### Task 2.2: Update Trade Execution Endpoints
Similar branching logic for `/api/trade/buy` and `/api/trade/sell`

---

### **Phase 3: Frontend Updates**

#### Task 3.1: Add Graduation Status Display
**File**: `static/js/token_detail.js`

```javascript
// Add to chart header or trading panel
if (tokenData.is_graduated) {
    tradingPanel.innerHTML += `
        <div class="graduated-badge">
            <i class="fas fa-graduation-cap"></i> 
            Graduated - Trading on Kaspa Finance
        </div>
    `;
}
```

#### Task 3.2: Handle Approval Flow for DEX Sells
```javascript
async function executeSell() {
    const quote = await getQuote('sell', ...);
    
    if (quote.routing === 'dex' && quote.requires_approval) {
        // Show approval step
        await approveToken(quote.approval_target, quote.approval_amount);
    }
    
    // Proceed with sell
    await submitSellTransaction();
}
```

---

## 🧪 Testing Plan

### Unit Tests
- [ ] DEX quote methods return correct amounts
- [ ] Transaction builders generate valid calldata
- [ ] Approval detection works correctly
- [ ] Routing logic switches based on graduation status

### Integration Tests
- [ ] Buy graduated token via DEX
- [ ] Sell graduated token via DEX
- [ ] Approval → Sell flow completes successfully
- [ ] Non-graduated tokens still use bonding curve

### End-to-End Test Scenario
1. Create token on bonding curve
2. Buy tokens (verify bonding curve routing)
3. Graduate token to DEX
4. Buy more tokens (verify DEX routing)
5. Sell tokens (verify approval + DEX routing)
6. Verify all transactions on blockchain explorer

---

## 🔒 Security Considerations

1. **Slippage Protection**: Both bonding curve and DEX trades include `minTokensOut`/`minKasOut`
2. **Deadline Enforcement**: DEX trades have 5-minute deadline
3. **Approval Amounts**: Only approve exact amount needed for trade (not infinite)
4. **Contract Verification**: All Kaspa Finance contracts verified on block explorer
5. **Fee Tier Validation**: Ensure graduation uses correct fee tier (0.05% or 0.25%)

---

## 📊 Success Metrics

- [ ] 100% of graduated tokens remain tradable on platform
- [ ] Quote accuracy within 0.1% of actual execution price
- [ ] Average trade execution time < 30 seconds
- [ ] Zero failed trades due to routing errors
- [ ] User retention increases post-graduation

---

## 🚀 Deployment Checklist

- [ ] All ABIs added to `artifacts/contracts/`
- [ ] Web3Service loads Kaspa Finance contracts
- [ ] Quote methods tested with mainnet pool
- [ ] API endpoints handle both routing paths
- [ ] Frontend displays graduation status
- [ ] Error handling covers DEX-specific failures
- [ ] Documentation updated in `replit.md`
- [ ] Graduation fee tier verified (0.05% vs 0.25%)

---

## 📝 Open Questions

1. **Fee Tier**: Should we use 0.05% or 0.25%? Current GraduationController is hardcoded to 0.25%
2. **WKAS Unwrapping**: Should backend auto-unwrap WKAS → KAS after sell, or leave as WKAS?
3. **Automatic Completion**: Should Step 2 of graduation (completeGraduation) be automatic?
4. **Fallback**: If DEX pool doesn't exist (graduation failed), how should we handle it?

---

## 🔗 Related Documents

- `SMART_CONTRACT_IMPLEMENTATION.md` - Phase 4.2 (Graduation Testing)
- `contracts/GraduationController.sol` - Graduation logic
- `deployments/kasplex_testnet_graduation.json` - Deployed addresses
- `replit.md` - Architecture overview

---

**Last Updated**: October 22, 2025  
**Next Review**: After Phase 1 completion
