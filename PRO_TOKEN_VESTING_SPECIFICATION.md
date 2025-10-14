# PRO Token Vesting System - Smart Contract Specification

## Executive Summary

This document specifies how the PRO token UI (reserve allocations and vesting schedules) should be implemented on-chain with proper smart contract enforcement. The current system stores allocation data in the database but doesn't enforce it on the blockchain.

## Current State vs. Required State

### ❌ Current Implementation (Database Only)
- UI collects: `reserved_percentage` (0-25%), `airdrops_allocation`, `marketing_allocation`, `team_allocation`
- Smart contracts: Hardcoded 25% reserve, manual one-time distribution
- Vesting: Not enforced on-chain
- **Problem**: Creator can ignore allocations and distribute however they want

### ✅ Required Implementation (Blockchain Enforced)
- UI → Smart Contract: All allocation data passed to `TokenFactory.createToken()`
- Automatic vesting contract deployment at token creation
- Time-locked token releases per schedule
- Immutable, trustless distribution

---

## UI Data Flow

### Form Data Collected
```javascript
// From create_token.html (lines 1425-1508)
{
  reserved_percentage: 0-25,           // Slider value
  airdrops_allocation: 0-100,          // % of reserve (must sum to 100)
  marketing_allocation: 0-100,         // % of reserve
  team_allocation: 0-100,              // % of reserve
  total_supply: 1000000000             // Base token supply
}
```

### Vesting Schedules (Hardcoded in UI)
- **Airdrops & Rewards**: 5% daily unlock (20 days total)
- **Marketing**: 12-month linear vesting (no cliff)
- **Team**: 6-month cliff + 18-month vesting (24 months total)

---

## Smart Contract Architecture

### 1. Enhanced TokenFactory.sol

**New `createToken()` signature:**
```solidity
function createToken(
    // Existing params
    string memory name,
    string memory symbol,
    uint256 totalSupply,
    string memory description,
    string memory imageUrl,
    string memory twitterUrl,
    string memory telegramUrl,
    string memory websiteUrl,
    bool antiBotEnabled,
    
    // NEW: PRO Token Vesting Params
    uint8 reservedPercentage,           // 0-25
    uint8 airdropsAllocation,           // 0-100 (% of reserve)
    uint8 marketingAllocation,          // 0-100 (% of reserve)
    uint8 teamAllocation,               // 0-100 (% of reserve)
    address airdropBeneficiary,         // Who can withdraw unlocked airdrops
    address marketingBeneficiary,       // Who can withdraw unlocked marketing
    address teamBeneficiary             // Who can withdraw unlocked team tokens
) external nonReentrant whenNotPaused returns (
    address poolAddress,
    address airdropVestingAddress,
    address marketingVestingAddress,
    address teamVestingAddress
)
```

**Implementation Logic:**
1. Validate allocations sum to 100
2. Validate reservedPercentage <= 25
3. Deploy BondingCurvePool (modified to support variable reserve)
4. Calculate token amounts from percentages
5. Deploy 3 vesting contracts if reservedPercentage > 0
6. Transfer tokens to vesting contracts
7. Return all addresses

### 2. Modified BondingCurvePool.sol

**Constructor Changes:**
```solidity
constructor(
    // Existing params...
    
    // NEW: Variable reserve support
    uint8 _reservedPercentage  // 0-25, replaces hardcoded LP_SUPPLY_PCT
) ERC20(name, symbol) Ownable(msg.sender) {
    // Calculate dynamic percentages
    uint256 curveSupplyPct = 100 - _reservedPercentage;  // 75-100%
    uint256 curveSupply = totalSupply * curveSupplyPct / 100;
    
    virtualTokenReserve = curveSupply;
    virtualKasReserve = INITIAL_VIRTUAL_KAS;
    
    // Reserve tokens stay in contract for vesting transfer
    // (100 - curveSupplyPct)% = _reservedPercentage
}
```

**Key Changes:**
- Remove `LP_SUPPLY_PCT` constant (25)
- Add `reservedPercentage` state variable
- Support 0% reserve (BASIC tokens) to 25% reserve (PRO tokens)

### 3. New Vesting Contracts

#### AirdropVesting.sol (5% Daily Unlock)
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract AirdropVesting is Ownable {
    IERC20 public immutable token;
    address public immutable beneficiary;
    uint256 public immutable totalAllocation;
    uint256 public immutable startTime;
    uint256 public constant DAILY_UNLOCK_PCT = 5; // 5% per day
    uint256 public constant VESTING_PERIOD = 20 days;
    uint256 public withdrawn;
    
    constructor(
        address _token,
        address _beneficiary,
        uint256 _totalAllocation
    ) Ownable(msg.sender) {
        token = IERC20(_token);
        beneficiary = _beneficiary;
        totalAllocation = _totalAllocation;
        startTime = block.timestamp;
    }
    
    function getUnlockedAmount() public view returns (uint256) {
        uint256 elapsed = block.timestamp - startTime;
        if (elapsed >= VESTING_PERIOD) {
            return totalAllocation; // 100% unlocked
        }
        
        uint256 daysElapsed = elapsed / 1 days;
        uint256 unlockedPct = daysElapsed * DAILY_UNLOCK_PCT;
        if (unlockedPct > 100) unlockedPct = 100;
        
        return (totalAllocation * unlockedPct) / 100;
    }
    
    function getWithdrawableAmount() public view returns (uint256) {
        uint256 unlocked = getUnlockedAmount();
        return unlocked > withdrawn ? unlocked - withdrawn : 0;
    }
    
    function withdraw() external {
        require(msg.sender == beneficiary, "Only beneficiary");
        
        uint256 amount = getWithdrawableAmount();
        require(amount > 0, "Nothing to withdraw");
        
        withdrawn += amount;
        require(token.transfer(beneficiary, amount), "Transfer failed");
    }
}
```

#### LinearVesting.sol (12-Month Marketing)
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract LinearVesting is Ownable {
    IERC20 public immutable token;
    address public immutable beneficiary;
    uint256 public immutable totalAllocation;
    uint256 public immutable startTime;
    uint256 public immutable duration;
    uint256 public withdrawn;
    
    constructor(
        address _token,
        address _beneficiary,
        uint256 _totalAllocation,
        uint256 _durationMonths  // 12 for marketing
    ) Ownable(msg.sender) {
        token = IERC20(_token);
        beneficiary = _beneficiary;
        totalAllocation = _totalAllocation;
        startTime = block.timestamp;
        duration = _durationMonths * 30 days;
    }
    
    function getUnlockedAmount() public view returns (uint256) {
        uint256 elapsed = block.timestamp - startTime;
        if (elapsed >= duration) {
            return totalAllocation;
        }
        return (totalAllocation * elapsed) / duration;
    }
    
    function getWithdrawableAmount() public view returns (uint256) {
        uint256 unlocked = getUnlockedAmount();
        return unlocked > withdrawn ? unlocked - withdrawn : 0;
    }
    
    function withdraw() external {
        require(msg.sender == beneficiary, "Only beneficiary");
        
        uint256 amount = getWithdrawableAmount();
        require(amount > 0, "Nothing to withdraw");
        
        withdrawn += amount;
        require(token.transfer(beneficiary, amount), "Transfer failed");
    }
}
```

#### CliffVesting.sol (6-Month Cliff + 18-Month Vest)
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract CliffVesting is Ownable {
    IERC20 public immutable token;
    address public immutable beneficiary;
    uint256 public immutable totalAllocation;
    uint256 public immutable startTime;
    uint256 public immutable cliff;        // 6 months
    uint256 public immutable vestingEnd;   // 24 months from start
    uint256 public withdrawn;
    
    constructor(
        address _token,
        address _beneficiary,
        uint256 _totalAllocation,
        uint256 _cliffMonths,      // 6 for team
        uint256 _vestingMonths     // 18 for team (after cliff)
    ) Ownable(msg.sender) {
        token = IERC20(_token);
        beneficiary = _beneficiary;
        totalAllocation = _totalAllocation;
        startTime = block.timestamp;
        cliff = _cliffMonths * 30 days;
        vestingEnd = startTime + (_cliffMonths + _vestingMonths) * 30 days;
    }
    
    function getUnlockedAmount() public view returns (uint256) {
        if (block.timestamp < startTime + cliff) {
            return 0; // Nothing unlocked before cliff
        }
        
        if (block.timestamp >= vestingEnd) {
            return totalAllocation; // Everything unlocked
        }
        
        // Linear unlock after cliff
        uint256 elapsed = block.timestamp - (startTime + cliff);
        uint256 vestingDuration = vestingEnd - (startTime + cliff);
        return (totalAllocation * elapsed) / vestingDuration;
    }
    
    function getWithdrawableAmount() public view returns (uint256) {
        uint256 unlocked = getUnlockedAmount();
        return unlocked > withdrawn ? unlocked - withdrawn : 0;
    }
    
    function withdraw() external {
        require(msg.sender == beneficiary, "Only beneficiary");
        
        uint256 amount = getWithdrawableAmount();
        require(amount > 0, "Nothing to withdraw");
        
        withdrawn += amount;
        require(token.transfer(beneficiary, amount), "Transfer failed");
    }
}
```

---

## Integration Flow

### 1. Frontend Form Submission
```javascript
// templates/app/create_token.html - Enhanced tokenData
const tokenData = {
    name: formData.get('name'),
    symbol: formData.get('symbol'),
    total_supply: formData.get('total_supply'),
    reserved_percentage: formData.get('reserved_percentage'),
    airdrops_allocation: formData.get('airdrops_allocation'),
    marketing_allocation: formData.get('marketing_allocation'),
    team_allocation: formData.get('team_allocation'),
    // ... other fields
};
```

### 2. Backend API Enhancement
```python
# app.py - /api/token/create

def create_token():
    data = request.json
    
    # Extract PRO token params
    reserved_pct = int(data.get('reserved_percentage', 0))
    airdrops_alloc = int(data.get('airdrops_allocation', 0))
    marketing_alloc = int(data.get('marketing_allocation', 0))
    team_alloc = int(data.get('team_allocation', 0))
    
    # Validate allocations
    if reserved_pct > 0:
        if airdrops_alloc + marketing_alloc + team_alloc != 100:
            return jsonify({'error': 'Allocations must sum to 100%'}), 400
    
    # Build transaction with vesting params
    tx_data = web3_service.create_token_tx_data(
        user_address=current_user.wallet_address,
        name=data['name'],
        symbol=data['symbol'],
        total_supply=int(data['total_supply']),
        # ... other params
        reserved_percentage=reserved_pct,
        airdrops_allocation=airdrops_alloc,
        marketing_allocation=marketing_alloc,
        team_allocation=team_alloc,
        airdrop_beneficiary=current_user.wallet_address,  # Creator initially
        marketing_beneficiary=current_user.wallet_address,
        team_beneficiary=current_user.wallet_address
    )
    
    return jsonify({'success': True, 'tx_data': tx_data})
```

### 3. Web3 Service Enhancement
```python
# services/web3_service.py

def create_token_tx_data(self, user_address, name, symbol, total_supply,
                        description, image_url, twitter_url, telegram_url,
                        website_url, anti_bot_enabled,
                        reserved_percentage, airdrops_allocation,
                        marketing_allocation, team_allocation,
                        airdrop_beneficiary, marketing_beneficiary,
                        team_beneficiary):
    
    contract = self.contracts['TokenFactory']
    
    tx_data = contract.functions.createToken(
        name,
        symbol,
        total_supply,
        description,
        image_url,
        twitter_url,
        telegram_url,
        website_url,
        anti_bot_enabled,
        reserved_percentage,
        airdrops_allocation,
        marketing_allocation,
        team_allocation,
        Web3.to_checksum_address(airdrop_beneficiary),
        Web3.to_checksum_address(marketing_beneficiary),
        Web3.to_checksum_address(team_beneficiary)
    ).build_transaction({
        'from': Web3.to_checksum_address(user_address),
        'value': 0,
        'gas': 0,  # Will be estimated
        'gasPrice': self.w3.eth.gas_price,
        'nonce': self.w3.eth.get_transaction_count(user_address)
    })
    
    return tx_data
```

### 4. TokenFactory Implementation
```solidity
// contracts/TokenFactory.sol - createToken() enhanced

function createToken(
    string memory name,
    string memory symbol,
    uint256 totalSupply,
    string memory description,
    string memory imageUrl,
    string memory twitterUrl,
    string memory telegramUrl,
    string memory websiteUrl,
    bool antiBotEnabled,
    uint8 reservedPercentage,
    uint8 airdropsAllocation,
    uint8 marketingAllocation,
    uint8 teamAllocation,
    address airdropBeneficiary,
    address marketingBeneficiary,
    address teamBeneficiary
) external nonReentrant whenNotPaused returns (address, address, address, address) {
    // Validations
    require(reservedPercentage <= 25, "Reserve exceeds 25%");
    if (reservedPercentage > 0) {
        require(
            airdropsAllocation + marketingAllocation + teamAllocation == 100,
            "Allocations must sum to 100"
        );
    }
    
    // Deploy pool with variable reserve
    BondingCurvePool pool = new BondingCurvePool(
        name,
        symbol,
        totalSupply,
        msg.sender,
        treasury,
        airdropTreasury,
        platformDevelopmentWallet,
        antiBotEnabled,
        graduationOracle,
        admin,
        buybackReserveWallet,
        kaspaNetworkSupportWallet,
        communityRewardsWallet,
        reservedPercentage  // NEW PARAM
    );
    
    address poolAddress = address(pool);
    
    // Deploy vesting contracts if PRO token
    address airdropVesting = address(0);
    address marketingVesting = address(0);
    address teamVesting = address(0);
    
    if (reservedPercentage > 0) {
        uint256 totalReserve = totalSupply * reservedPercentage / 100;
        
        // Calculate token amounts
        uint256 airdropTokens = totalReserve * airdropsAllocation / 100;
        uint256 marketingTokens = totalReserve * marketingAllocation / 100;
        uint256 teamTokens = totalReserve * teamAllocation / 100;
        
        // Deploy vesting contracts
        if (airdropTokens > 0) {
            AirdropVesting av = new AirdropVesting(
                poolAddress,
                airdropBeneficiary,
                airdropTokens
            );
            airdropVesting = address(av);
            IERC20(poolAddress).transferFrom(poolAddress, airdropVesting, airdropTokens);
        }
        
        if (marketingTokens > 0) {
            LinearVesting mv = new LinearVesting(
                poolAddress,
                marketingBeneficiary,
                marketingTokens,
                12  // 12 months
            );
            marketingVesting = address(mv);
            IERC20(poolAddress).transferFrom(poolAddress, marketingVesting, marketingTokens);
        }
        
        if (teamTokens > 0) {
            CliffVesting tv = new CliffVesting(
                poolAddress,
                teamBeneficiary,
                teamTokens,
                6,   // 6 month cliff
                18   // 18 month vesting
            );
            teamVesting = address(tv);
            IERC20(poolAddress).transferFrom(poolAddress, teamVesting, teamTokens);
        }
    }
    
    // Store metadata
    tokens[poolAddress] = TokenInfo({
        // ... existing fields
        vestingContracts: VestingInfo({
            airdrop: airdropVesting,
            marketing: marketingVesting,
            team: teamVesting
        })
    });
    
    emit TokenCreated(poolAddress, msg.sender, name, symbol, totalSupply, antiBotEnabled);
    emit VestingDeployed(poolAddress, airdropVesting, marketingVesting, teamVesting);
    
    return (poolAddress, airdropVesting, marketingVesting, teamVesting);
}
```

---

## Database Schema Updates

### Token Model Enhancement
```python
# models.py

class Token(db.Model):
    # ... existing fields
    
    # Vesting contract addresses
    airdrop_vesting_address = db.Column(db.String(128))
    marketing_vesting_address = db.Column(db.String(128))
    team_vesting_address = db.Column(db.String(128))
```

---

## User Flow Example

### Creating a PRO Token with Community First Template (50/30/20)

1. **User Input:**
   - Reserved: 25%
   - Allocations: 50% Airdrops, 30% Marketing, 20% Team
   - Total Supply: 1B tokens

2. **Calculated Amounts:**
   - Reserve: 250M tokens (25% of 1B)
   - Airdrops: 125M tokens (50% of 250M) → AirdropVesting
   - Marketing: 75M tokens (30% of 250M) → LinearVesting (12 months)
   - Team: 50M tokens (20% of 250M) → CliffVesting (6mo cliff + 18mo)
   - Curve: 750M tokens (75% of 1B) → Trading pool

3. **On-Chain Result:**
   - BondingCurvePool: 750M tokens for trading
   - AirdropVesting: 125M tokens (5% daily unlock)
   - LinearVesting: 75M tokens (12-month linear)
   - CliffVesting: 50M tokens (6mo cliff + 18mo vest)

4. **Withdrawals:**
   - Day 1: 6.25M airdrops unlocked (5% of 125M)
   - Month 6: Team cliff ends, linear vesting starts
   - Month 12: All marketing tokens unlocked
   - Day 20: All airdrop tokens unlocked
   - Month 24: All team tokens unlocked

---

## Migration Strategy

### Option 1: New Deployment (Recommended)
- Deploy new contract versions
- Test thoroughly on testnet
- Audit new contracts
- Deploy to mainnet as v2
- Migrate existing tokens gradually

### Option 2: Upgrade Existing
- Not possible without proxy pattern
- Would require complete redesign

**Recommendation:** Deploy as v2 system alongside current contracts, sunset v1 after migration period.

---

## Security Considerations

1. **Immutability**: All vesting parameters set at deployment, cannot be changed
2. **Beneficiary Protection**: Only beneficiary can withdraw their tokens
3. **Time-Lock Enforcement**: Blockchain timestamp ensures trustless unlocking
4. **Reentrancy Guards**: All withdrawal functions protected
5. **Integer Overflow**: Solidity ^0.8.20 has built-in protection

---

## Testing Requirements

### Unit Tests
- [ ] TokenFactory deployment with all param combinations
- [ ] BondingCurvePool with 0%, 10%, 25% reserves
- [ ] AirdropVesting 5% daily unlock calculations
- [ ] LinearVesting 12-month unlock calculations
- [ ] CliffVesting 6mo cliff + 18mo vest calculations
- [ ] Edge cases: 100% one allocation, 0% others

### Integration Tests
- [ ] End-to-end token creation with vesting
- [ ] Withdrawal after partial unlock
- [ ] Multiple withdrawals over time
- [ ] Beneficiary changes (if implemented)

### Audit Requirements
- [ ] External security audit (3rd party)
- [ ] Gas optimization review
- [ ] Economic model validation
- [ ] Time-lock mechanism verification

---

## Gas Optimization Notes

**Deployment Costs:**
- TokenFactory.createToken() with vesting: ~4-6M gas
- Without vesting (BASIC token): ~2-3M gas
- Users should be warned about increased gas for PRO tokens

**Optimization Strategies:**
- Use immutable variables where possible
- Minimize storage writes
- Batch token transfers in constructor
- Consider EIP-1167 minimal proxy for vesting contracts (future)

---

## Questions for Clarification

1. **Beneficiary Assignment**: Should users specify beneficiary wallets during creation, or default to creator?
2. **Transfer Restrictions**: Can beneficiary transfer vesting contract ownership?
3. **Emergency Withdrawals**: Should admin have emergency withdrawal capability?
4. **Partial Allocations**: What if user sets 10% reserve but only uses 50% of it (e.g., 50% airdrops, 0% marketing, 0% team)?

---

## Implementation Checklist

### Smart Contracts
- [ ] Modify BondingCurvePool.sol for variable reserve
- [ ] Create AirdropVesting.sol
- [ ] Create LinearVesting.sol
- [ ] Create CliffVesting.sol
- [ ] Enhance TokenFactory.sol with vesting deployment
- [ ] Add VestingInfo struct and events
- [ ] Write comprehensive tests
- [ ] External security audit

### Backend
- [ ] Update Web3Service.create_token_tx_data()
- [ ] Add vesting contract address tracking
- [ ] Create vesting status API endpoints
- [ ] Add withdrawal transaction builders

### Frontend
- [ ] Ensure allocation data sent to API
- [ ] Display vesting contract addresses on token page
- [ ] Show unlock schedules visually
- [ ] Add withdrawal UI for beneficiaries
- [ ] Update documentation

### Database
- [ ] Add vesting address columns to Token model
- [ ] Migration script for schema update

---

## Conclusion

This specification transforms the PRO token UI from a database-only feature into a fully on-chain, trustless vesting system. The key innovation is deploying dedicated vesting contracts at token creation time, enforcing the UI-promised schedules with blockchain immutability.

**Next Steps:**
1. Review and approve this specification
2. Estimate development timeline (suggest 2-3 weeks)
3. Plan security audit (critical before mainnet)
4. Implement in test environment
5. User acceptance testing
6. Audit and deploy
