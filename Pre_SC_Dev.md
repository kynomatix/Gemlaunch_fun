# Pre-Smart Contract Development Checklist

**Purpose:** Track implementation of all missing platform features required before smart contract deployment.

**Last Updated:** October 9, 2025

---

## 📊 Implementation Status Overview

**Total Features:** 10 categories  
**Completed:** 0/10  
**In Progress:** 0/10  
**Not Started:** 10/10

---

## Phase 1: Critical Trading UX

### 1. ✅ Slippage & Deadline Controls
**Smart Contract Parameters:** `minTokensOut`, `minKasOut`, `deadline`

- [ ] Add slippage tolerance selector to trade panel
  - [ ] Preset options: 0.5%, 1%, 2%, 5%
  - [ ] Custom slippage input field
  - [ ] Save user preference to localStorage
- [ ] Add deadline picker
  - [ ] Preset options: 5min, 10min, 30min
  - [ ] Custom deadline input
  - [ ] Calculate Unix timestamp for contract call
- [ ] Add price impact warning
  - [ ] Calculate price impact percentage
  - [ ] Show warning for >5% impact
  - [ ] Block trades >20% impact with confirmation modal
- [ ] Display slippage breakdown
  - [ ] Expected output amount
  - [ ] Minimum guaranteed amount (after slippage)
  - [ ] "Transaction may revert" warning for high slippage

**Files to Update:**
- `templates/app/partials/token_trading.html`
- `static/js/token_detail.js`
- `static/css/token_detail.css`

---

### 2. ✅ Real-Time Price Quotes
**Smart Contract Functions:** `quoteBuy(uint256 kasIn)`, `quoteSell(uint256 tokensIn)`

- [ ] Integrate quoteBuy() for buy trades
  - [ ] Call contract function as user types KAS amount
  - [ ] Display exact token amount to receive
  - [ ] Update in real-time (debounce 300ms)
- [ ] Integrate quoteSell() for sell trades
  - [ ] Call contract function as user types token amount
  - [ ] Display exact KAS amount to receive
  - [ ] Update in real-time (debounce 300ms)
- [ ] Display price per token
  - [ ] Calculate from quote (KAS amount / token amount)
  - [ ] Show in "1 TOKEN = X KAS" format
  - [ ] Display USD equivalent
- [ ] Show price impact percentage
  - [ ] Compare quote price vs current market price
  - [ ] Highlight if >3% impact
  - [ ] Red warning if >10% impact
- [ ] Add loading state during quote fetch
  - [ ] Spinner/skeleton while calculating
  - [ ] Error handling for failed quotes

**Files to Update:**
- `static/js/token_detail.js` (add quote functions)
- `templates/app/partials/token_trading.html` (add price display)

---

### 3. ✅ Minimum Trade Validation
**Smart Contract Constant:** `MIN_TRADE_AMOUNT = 0.001 ether` (0.001 KAS)

- [ ] Add client-side validation
  - [ ] Check KAS input >= 0.001 KAS
  - [ ] Show error message if below minimum
  - [ ] Disable trade button for invalid amounts
- [ ] Display minimum trade requirement
  - [ ] "Minimum: 0.001 KAS" text below input
  - [ ] Highlight in red when violated
- [ ] Add helper text
  - [ ] "Enter at least 0.001 KAS to trade"
  - [ ] Auto-set to 0.001 on focus if empty

**Files to Update:**
- `templates/app/partials/token_trading.html`
- `static/js/token_detail.js`

---

### 4. ✅ Fee Breakdown Display
**Smart Contract Function:** `getEffectiveFeeBreakdown(uint256 kasAmount)`

- [ ] Add fee breakdown section to trade panel
  - [ ] Platform fee (0.9% of trade amount)
  - [ ] Creator fee (0.1% of trade amount)
  - [ ] Anti-bot fee (if active - see Phase 2)
  - [ ] Total fees
  - [ ] Net amount to trade
- [ ] Display fee breakdown on hover
  - [ ] Tooltip with detailed breakdown
  - [ ] "Where do fees go?" info icon
- [ ] Add transparency section
  - [ ] Link to fee distribution explanation
  - [ ] Show % breakdown visually (pie chart optional)

**Files to Update:**
- `templates/app/partials/token_trading.html`
- `static/js/token_detail.js`
- `static/css/token_detail.css`

---

## Phase 2: Anti-Bot System (GEM System)

### 5. ✅ Anti-Bot Fee Display
**Smart Contract Function:** `getCurrentAntiBotFee(uint256 kasAmount)`

- [ ] Check if anti-bot enabled for token
  - [ ] Query `antiBotEnabled` state variable
  - [ ] Show/hide anti-bot UI based on flag
- [ ] Display current anti-bot fee percentage
  - [ ] Calculate using: `9500 - (9400 * elapsed / 60)` basis points
  - [ ] Show as percentage: "Current Anti-Bot Fee: 87%"
  - [ ] Update every second
- [ ] Add anti-bot badge to token header
  - [ ] "🛡️ Anti-Bot Protected" badge
  - [ ] Tooltip explaining protection
- [ ] Show fee in trade preview
  - [ ] "Anti-Bot Fee: 15.3 KAS (72%)" in breakdown
  - [ ] Highlight that fee goes to community (70%) + platform (30%)

**Files to Update:**
- `templates/app/partials/token_trading.html`
- `templates/app/partials/token_header.html`
- `static/js/token_detail.js`

---

### 6. ✅ Countdown Timer
**Smart Contract Function:** `getSecondsUntilNormalFees()`

- [ ] Add countdown timer to trade panel
  - [ ] Display "Normal fees in: MM:SS"
  - [ ] Update every second
  - [ ] Hide when anti-bot window expires (60 seconds after launch)
- [ ] Visual countdown indicator
  - [ ] Progress bar showing time remaining
  - [ ] Color transition: red → yellow → green
  - [ ] Pulse animation when <10 seconds remain
- [ ] Add launch time display
  - [ ] "Token launched: 2 minutes ago"
  - [ ] Calculate from `deploymentTime` state variable
- [ ] Show "Anti-bot protection ended" message
  - [ ] Green checkmark when timer reaches 0
  - [ ] "Normal fees now active (1% total)"

**Files to Update:**
- `templates/app/partials/token_trading.html`
- `static/js/token_detail.js`
- `static/css/token_detail.css`

---

### 7. ✅ Fee Split Visualization
**Smart Contract Split:** 70% Airdrop Treasury, 30% Platform Development

- [ ] Add fee distribution chart
  - [ ] Show anti-bot fee split: 70/30
  - [ ] Visual breakdown (bar chart or pie chart)
  - [ ] Tooltip: "70% funds airdrops, 30% platform development"
- [ ] Display total anti-bot fees collected
  - [ ] Query `totalAntiBotFeesCollected` state variable
  - [ ] Show historical total for transparency
  - [ ] Display as badge: "Total Anti-Bot Fees: 450 KAS"
- [ ] Add transparency modal
  - [ ] "Where do anti-bot fees go?" button
  - [ ] Detailed explanation of 70/30 split
  - [ ] Link to airdrop leaderboard

**Files to Update:**
- `templates/app/partials/token_header.html`
- `static/js/token_detail.js`
- `static/css/token_detail.css`

---

## Phase 3: Creator Features

### 8. ✅ Creator Fee Claim Portal
**Smart Contract Functions:** `getCreatorClaimableAmount()`, `withdrawCreatorFees()`

**STATUS: ✅ UI COMPLETE** (Smart contract integration pending)

- [x] Add "Creator Dashboard" section to dashboard
  - [x] Show only for token creators (in "Your Created Tokens" section)
  - [x] Display all tokens created by user
- [x] Display accumulated fees per token
  - [x] Show accumulated fees in KAS (placeholder calculation)
  - [x] Show claimable amount in KAS
  - [x] Display USD equivalent
- [x] Add "Claim Fees" button
  - [x] Modal with detailed fee breakdown
  - [x] Graduation status check (enabled only after $70K)
  - [x] Placeholder for `withdrawCreatorFees()` call
  - [x] Transaction confirmation ready for SC integration
- [x] Show fee statistics
  - [x] Total fees accumulated per token
  - [x] Platform vs Creator fee breakdown (0.9% vs 0.1%)
  - [x] Total trades count
  - [x] Fee rate display (0.1% per trade)
- [x] Creator Fee Modal UI
  - [x] Token info header with image
  - [x] Fee stats grid (accumulated, lifetime, trades, rate)
  - [x] Fee breakdown section (platform/creator split)
  - [x] Claim status badge (pre/post graduation)
  - [x] Claim button (disabled until graduated)

**Files Updated:**
- ✅ `templates/app/dashboard.html` (added fee stats to token cards)
- ✅ `templates/app/partials/creator_fee_modal.html` (new modal template)
- ✅ JavaScript functions (openCreatorFeeModal, closeCreatorFeeModal, claimCreatorFees)

**Next Steps for SC Integration:**
- Replace placeholder fee calculations with `getCreatorClaimableAmount()` contract call
- Wire claim button to `withdrawCreatorFees()` contract function
- Add transaction confirmation and success feedback
- Fetch real KAS/USD price from oracle

---

### 9. ✅ Deployment Cooldown UI
**Smart Contract Functions:** `canDeploy(address user)`, `getSecondsUntilNextDeployment(address user)`

- [ ] Check deployment eligibility on page load
  - [ ] Query `canDeploy(userAddress)`
  - [ ] Show/hide create button based on result
- [ ] Display cooldown timer
  - [ ] Query `getSecondsUntilNextDeployment(userAddress)`
  - [ ] Show "You can create again in: MM:SS"
  - [ ] Update every second
- [ ] Disable create button during cooldown
  - [ ] Gray out button
  - [ ] Show tooltip: "Cooldown: 45 seconds remaining"
  - [ ] Enable when cooldown expires
- [ ] Show last deployment info
  - [ ] "Last token created: 15 seconds ago"
  - [ ] Link to last created token
- [ ] Add cooldown settings display
  - [ ] "Deployment cooldown: 60 seconds"
  - [ ] Note: Admin configurable (0-3600s)

**Files to Update:**
- `templates/app/create_token.html`
- `static/js/create_token.js`

---

## Phase 4: Safety Features

### 10. ✅ Wallet Cap Warning
**Smart Contract Constant:** `MAX_WALLET_PCT = 10` (10% of supply)

- [ ] Calculate current holdings vs cap
  - [ ] Query user token balance
  - [ ] Calculate % of total supply
  - [ ] Show "You hold: 3.2% of supply"
- [ ] Display wallet cap limit
  - [ ] "Wallet cap: 10% of supply"
  - [ ] Show exact token amount: "Max: 75,000,000 PEPE"
- [ ] Add purchase cap warning
  - [ ] Check if purchase would exceed 10% cap
  - [ ] Show warning: "This purchase would exceed wallet cap"
  - [ ] Suggest maximum allowed purchase amount
- [ ] Add progress bar to cap
  - [ ] Visual bar: "█████░░░░░ 50% of wallet cap"
  - [ ] Color coding: green < 7%, yellow 7-9%, red > 9%
  - [ ] Highlight when near cap
- [ ] Show PRO token exemption (if applicable)
  - [ ] Badge: "PRO Token: 25% Vesting Allowed"
  - [ ] Note: "Airdrop treasury exempt from cap"
  - [ ] Display vesting allocation separately

**Files to Update:**
- `templates/app/partials/token_trading.html`
- `templates/app/token_detail.html`
- `static/js/token_detail.js`

---

### 11. ✅ Graduation Progress Tracker
**Target:** $70,000 USD market cap

- [ ] Add graduation progress section
  - [ ] Current market cap (USD)
  - [ ] Target: $70,000 USD
  - [ ] Percentage progress
- [ ] Display progress bar to graduation
  - [ ] Visual bar: "████████░░ 67% to Kaspa Finance"
  - [ ] Color gradient as approaches 100%
  - [ ] Pulse animation when >90%
- [ ] Show graduation metrics
  - [ ] Current KAS reserve
  - [ ] KAS needed for $70K (based on KAS/USD price)
  - [ ] Estimated time to graduation (if trending up)
- [ ] Add "Graduation Imminent" warning
  - [ ] Show when >95% to graduation
  - [ ] Banner: "🚀 Graduating Soon to Kaspa Finance DEX!"
  - [ ] Countdown if volume is high
- [ ] Display post-graduation info
  - [ ] "Liquidity: virtualKasReserve + 25% tokens"
  - [ ] "DEX: Kaspa Finance (0.25% fee tier)"

**Files to Update:**
- `templates/app/partials/token_header.html`
- `templates/app/token_detail.html`
- `static/js/token_detail.js`

---

### 12. ✅ Post-Graduation Trading UI
**Status:** Routes to Kaspa Finance DEX after graduation

- [ ] Check graduation status
  - [ ] Query `graduated` state variable
  - [ ] Show different UI if graduated
- [ ] Add "Graduated" banner
  - [ ] "🎓 This token has graduated to Kaspa Finance DEX"
  - [ ] Display graduation timestamp
  - [ ] Show liquidity pool NFT position ID
- [ ] Update trade routing
  - [ ] Backend routes trades to Kaspa Finance
  - [ ] Display "Trading on Kaspa Finance" indicator
  - [ ] Same UI, different backend routing
- [ ] Add DEX integration info
  - [ ] Link to Kaspa Finance pool
  - [ ] Display pool address
  - [ ] Show liquidity pool stats (TVL, 24h volume)
- [ ] Maintain chat/community features
  - [ ] Keep chat active post-graduation
  - [ ] Continue airdrops for holders
  - [ ] Leaderboard still functional
- [ ] Add liquidity info modal
  - [ ] "View on Kaspa Finance" button
  - [ ] Pool composition (KAS + TOKEN)
  - [ ] Current pool price

**Files to Update:**
- `templates/app/token_detail.html`
- `templates/app/partials/token_trading.html`
- `static/js/token_detail.js`
- `routes.py` (add DEX routing logic)

---

### 13. ✅ Token Registry Pagination
**Smart Contract Function:** `getDeployedTokens(uint256 offset, uint256 limit)`

- [ ] Implement paginated token loading
  - [ ] Call `getDeployedTokens(offset, limit)` instead of loading all
  - [ ] Default: 20 tokens per page
  - [ ] Load more on scroll or pagination buttons
- [ ] Add pagination controls
  - [ ] Previous/Next buttons
  - [ ] Page numbers (1, 2, 3... 10)
  - [ ] Jump to page input
- [ ] Display total token count
  - [ ] Query `getDeployedTokenCount()`
  - [ ] Show "Page 3 of 47 (940 tokens total)"
- [ ] Optimize gas usage
  - [ ] Fetch only visible tokens
  - [ ] Cache results in localStorage
  - [ ] Prefetch next page on hover

**Files to Update:**
- `templates/app/marketplace.html`
- `static/js/marketplace.js`
- `routes.py` (update marketplace route)

---

## 📋 Smart Contract Integration Checklist

### Required Contract Addresses (Testnet)
- [ ] Deploy TokenFactory.sol
- [ ] Deploy BondingCurvePool.sol (via factory)
- [ ] Deploy GraduationController.sol
- [ ] Deploy Treasury/VestingVault.sol
- [ ] Configure Kaspa Finance addresses:
  - [x] Factory: `0x1b72D7165a0D7256a4F197765C15bb70bC5D66A8`
  - [x] NonfungiblePositionManager: `0x4E25637cF39822364b877F81B18c5B6CF0eeF589`
  - [x] WKAS: `0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94`
  - [x] SwapRouter: `0xDf88D478aF51C0AB616aFBfDD933c874e142858c`
  - [x] QuoterV2: `0x3ACc31F8fe86E365604eAa6dDCbcB7fEba7a4c2B`

### Required Backend Services
- [x] KAS/USD Price Oracle (`services/kas_oracle.py`)
- [ ] Graduation monitoring service (checks $70K threshold)
- [ ] DEX routing service (post-graduation trades)
- [ ] Contract event listeners (TokensPurchased, Graduated, etc.)

---

## 🎯 Implementation Priority

**Week 1:** Phase 1 (Critical Trading UX)
- Slippage controls
- Real-time quotes
- Minimum trade validation
- Fee breakdown

**Week 2:** Phase 2 (Anti-Bot System)
- Anti-bot fee display
- Countdown timer
- Fee split visualization

**Week 3:** Phase 3 (Creator Features)
- Creator fee claim portal
- Deployment cooldown UI

**Week 4:** Phase 4 (Safety Features)
- Wallet cap warnings
- Graduation progress tracker
- Post-graduation trading UI
- Registry pagination

---

## ✅ Definition of Done

Each feature is considered complete when:
1. [ ] UI components implemented and styled
2. [ ] Smart contract integration tested on testnet
3. [ ] Error handling implemented
4. [ ] Loading states added
5. [ ] Mobile responsive
6. [ ] Accessibility checked (ARIA labels, keyboard navigation)
7. [ ] Cross-browser tested (Chrome, Firefox, Safari)
8. [ ] Documentation updated in replit.md

---

**Next Steps After Completion:**
1. Full platform testing with testnet contracts
2. Security audit of smart contracts
3. Mainnet deployment preparation
4. User acceptance testing (UAT)
5. Launch! 🚀
