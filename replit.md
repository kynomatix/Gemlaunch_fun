# Overview
gemlaunch.fun is a web platform for creating and launching memecoins on the Kaspa blockchain. It offers a no-code solution with an emphasis on fair launch mechanisms and community-driven tokens, leveraging Kaspa's high-performance L1 capabilities. The platform includes an AI Assistant (Gemmy), a social layer, a gamified leaderboard, and integrates with Kaspa Finance for DEX deployments. Its purpose is to democratize memecoin creation and foster a vibrant Kaspa ecosystem.

# User Preferences
Preferred communication style: Simple, everyday language.

## Design Preferences
- **Button Style**: Sleek rectangular buttons with rounded corners (border-radius: 10px). NEVER use oval/pill-shaped buttons (border-radius: 25px+)

# System Architecture

## Frontend Architecture
The frontend uses Flask and Jinja2 for server-side rendering, a custom CSS framework (Grid, Flexbox, animations), and vanilla JavaScript. It incorporates particles.js and a GitBook-style tabbed documentation system, with a responsive and mobile-first design.

## Backend Architecture
Built with Flask, the backend features a minimal, route-based architecture with environment-based configuration, Python logging, and XSS protection. It includes an achievement system and interactive AI suggestions from Gemmy that auto-fill forms.

### AI Features
- **Gemmy Zeroday Memification Engine**: An AI-powered trend discovery system using OpenRouter API for multi-source cultural trend detection and Kaspa Tech analysis, with auto-failover, parallel processing, and a PostgreSQL cache.
- **AI Token Image Generation**: A two-stage AI pipeline uses OpenRouter Llama 3.1 70B for prompt enhancement and Replicate FLUX.1 Schnell for 1024x1024 WebP image generation.

### Core Features
- **PRO Token Airdrop System**: Manages airdrops with a 5% per day vesting schedule and various distribution types.
- **Anti-Bot System (GEM System)**: An optional premium feature for PRO tokens using time-based KAS fee decay to prevent bot sniping.
- **Token-Specific Community Points System**: Allows PRO token creators to configure and track engagement points.
- **Multi-Wallet Linking System**: Securely links multiple wallets via challenge-response authentication.
- **Wallet Connection System**: A modal-based system supporting Kastle, KasWare, and MetaMask using challenge-response authentication.
- **Enhanced Marketplace Search**: Provides comprehensive search across token name, symbol, contract address, and creator information with real-time, case-insensitive matching.

## Smart Contract Architecture
Core contracts (`BondingCurvePool.sol`, `TokenFactory.sol`, `GraduationController.sol`) manage token creation, bonding curve mechanics, creator fee claims, anti-bot measures (wallet cap), and a two-step graduation process for transitioning tokens to the Kaspa Finance DEX. An off-chain backend service calculates auto-slippage.

## Database Schema
The `Token` model includes blockchain integration fields like `creator_fees_accumulated`, `deployment_block_number`, `nft_position_id`, and `liquidity_pool_address`. New models include `TradeEvent` and `AntiBotFeeTracker` for storing blockchain trade events and anti-bot fee distributions, with extensive indexing.

## Design Patterns
The project adheres to an MVC pattern, separating templates (views), Flask routes (controllers), and models.

## Performance Optimizations
Includes hardware-accelerated CSS animations, efficient asset caching, and JavaScript-enhanced smooth scrolling.

## Blockchain Integration Foundation
The system includes a Web3 Service Layer for RPC connection to Kasplex zkEVM L2 (Testnet), an Oracle Wallet for automated operations, and contract loading for `TokenFactory`, `GraduationController`, and `BondingCurvePool`. Transaction utilities handle gas estimation, signing, relay, and status polling, with POA middleware for Kasplex compatibility.

## Transaction Flow Architecture
Transactions follow a 5-phase lifecycle: Quote → Build → Sign → Relay → Monitor. User signs transactions in their wallet, and the backend relays them to the blockchain. Oracle transactions are signed and relayed by the backend for automated operations.

## Transaction Manager Module
A dedicated `static/js/transaction_manager.js` module orchestrates all transaction types (token creation, buy, sell, claim fees) by integrating wallet management with backend APIs.

# External Dependencies

## Core Dependencies
- **Flask**: Python web framework.
- **Jinja2**: Template engine.

## Frontend Libraries
- **Font Awesome 6.0.0**: Icon library.
- **Google Fonts (Inter)**: Typography.
- **particles.js**: Particle animation library.

## Blockchain Integration
- **Kasplex zkEVM L2**: EVM-compatible Layer 2 on Kaspa.
- **Kaspa Finance DEX**: Target DEX for token graduation and liquidity pools (Uniswap V3 architecture).
- **Smart Contract Stack**: Solidity ^0.8.20, Hardhat, OpenZeppelin.
- **web3.py**: Python library for Ethereum/EVM blockchain interaction.
- **eth-account**: Ethereum account management for transaction signing.

## External Services
- **Telegram**: Community engagement.
- **Twitter/X**: Social media.
- **Kaspa Finance**: Automatic DEX deployment.
- **OpenRouter API**: For Gemmy AI, trend analysis, and image prompt enhancement (Meta Llama 3.1 70B).
- **Replicate API**: For AI-powered token image generation (FLUX.1 Schnell).
- **4chan /biz/**: Real-time meme trend scraping.
- **Reddit CryptoMoonShots**: Community-validated meme trends.
- **Pinata**: IPFS pinning service for permanent image storage.

# Phase 3: Frontend & Wallet Integration

## External Security Audit & Critical Corrections ✅
**Date:** October 12, 2025  
**Auditor:** Claude (External Security Review)

### Critical Architectural Flaws Found & Fixed

#### C-1: MetaMask Relay Architecture (CRITICAL) ✅ FIXED
- **Flaw:** Original plan showed MetaMask transactions needing backend relay
- **Reality:** MetaMask's `eth_sendTransaction` signs AND broadcasts in one step
- **Fix:** Sections 3.0 & 3.1 rewritten with wallet-specific branching
  - MetaMask: Sign (auto-broadcasts) → Monitor
  - Other wallets: Sign → Relay (backend) → Monitor

#### C-2: Token Ownership Model (CRITICAL) ✅ FIXED
- **Flaw:** Users deploying tokens become contract owners, platform loses admin control
- **Reality:** If user calls TokenFactory.createToken(), they become owner (can pause/unpause)
- **Fix:** Section 3.2 completely rewritten
  - **Backend oracle wallet deploys tokens** (user is creator, not owner)
  - Platform retains ownership and admin controls
  - Added IPFS upload integration

#### C-3: Sell Transaction Parameters (CRITICAL) ✅ FIXED
- **Flaw:** Sell transactions used wrong parameter name (`kas_amount`)
- **Reality:** Buy and sell have different parameter structures
- **Fix:** Section 3.3 corrected
  - Buy: `{kas_amount, min_tokens_out, deadline}`
  - Sell: `{token_amount, min_kas_out, deadline}`

#### High Severity Issues Fixed
- **H-1:** Added slippage protection to all trades (min_out + deadline)
- **H-2:** Added IPFS upload integration to token creation
- **H-3:** Documented ABI loading in web3_service
- **H-4:** Fixed contract method: `graduated()` (not `isGraduated()`)

### Architect Review: PASSED ✅
> **"Pass – Phase 3 plan corrections align with audit requirements and are ready for implementation."**

### Corrected Architecture

**Transaction Flow:**
```
MetaMask: Quote → Build → Sign (eth_sendTransaction) → Monitor
Others:   Quote → Build → Sign → Relay (backend) → Monitor
```

**Token Creation:**
```
OLD (Wrong): User deploys → User is owner ❌
NEW (Correct): Backend deploys → User is creator ✅
```

**Trade Parameters:**
```
Buy:  {kas_amount, min_tokens_out, deadline} ✅
Sell: {token_amount, min_kas_out, deadline} ✅
```

**Status:** Phase 3 plan is security-audited, architect-approved, and ready for implementation.

---

## Second Security Audit & Additional Fixes ✅
**Date:** October 12, 2025  
**Auditor:** Claude (Second Security Review)

### Assessment
> "Architecture is now solid. Remaining issues are mostly implementation details and edge cases."

### New Critical Issues Found & Fixed

#### NC-1: ERC20 Token Approval Missing (CRITICAL) ✅ FIXED
- **Issue:** Sell transactions would fail without token approval
- **Root Cause:** ERC20 tokens require approval before contracts can spend them
- **Fix:** Added approval flow that:
  1. Gets token address from `poolContract.token()`
  2. Checks current allowance
  3. Requests user approval if insufficient
  4. Approves BondingCurvePool as spender (MaxUint256)
- **Regression Fixed:** Initially approved wrong contract (token itself), corrected to approve BondingCurvePool

#### NC-2: SSE Memory Leaks (CRITICAL) ✅ FIXED  
- **Issue:** `closeAllConnections()` existed but never called
- **Fix:** Added event handlers in TransactionManager constructor:
  - `beforeunload` - Cleanup on page close
  - `popstate` - Cleanup on navigation

#### NC-3: Quote Staleness Race Condition (HIGH) ✅ FIXED
- **Issue:** Users could execute trades with outdated quotes
- **Fix:** Added quote validation:
  - Store quotes with timestamp and mode
  - Check freshness (30s max age)
  - Verify correct mode (buy vs sell)
  - Auto-refresh if stale

### High Severity Fixes

#### H-1: TokenFactory Contract Initialization ✅ FIXED
- Added Web3Service.__init__() with proper contract loading
- Loads ABIs from contracts/abis directory
- Initializes TokenFactory and GraduationController contracts
- Sets up oracle account from ORACLE_PRIVATE_KEY

#### H-2: Network Validation ✅ FIXED
- Added `validateNetwork()` method to TransactionManager
- Checks for Kasplex Testnet (Chain ID: 167012)
- Auto-switches with `wallet_switchEthereumChain`
- Auto-adds network if not present

#### H-3: Balance Validation ✅ FIXED
- Added KAS balance check before buy transactions
- Includes 1% gas buffer in calculation
- Shows clear error: required vs available balance

#### H-4: Gas Estimation Display ✅ FIXED
- Added `estimateTradeGas()` helper function
- Fetches estimates from `/api/trade/${action}/estimate-gas`
- Displays gas cost in KAS and USD in confirmation modals

### Medium Severity Fixes

#### M-1: IPFS Upload Failure Handling ✅ FIXED
- Aborts deployment on IPFS upload failure
- Closes modal and shows error instead of continuing

#### M-2: Quote Request Cancellation ✅ FIXED
- Added AbortController to cancel in-flight requests
- Prevents wasted API calls during rapid input

#### M-3: Backend API Endpoints ✅ FIXED
- Documented implementations for:
  - `/api/trade/quote-buy` - Buy quotes with fees/slippage
  - `/api/trade/quote-sell` - Sell quotes with fees/slippage
  - `/api/trade/${action}/estimate-gas` - Gas estimates

#### M-4: Wallet Disconnection Handlers ✅ FIXED
- Added `accountsChanged` event handler
- Closes SSE connections on disconnect
- Added `chainChanged` handler with page reload

### Architect Final Assessment ✅
> **"Pass: NC-1 approval flow now correctly approves the BondingCurvePool as spender, restoring sell functionality. All second audit findings properly resolved."**

**Recommended Testing:**
1. Smoke-test sell transactions on Kasplex testnet (approval flow end-to-end)
2. Regression-test other wallet types (Kastle/KasWare)
3. Verify all audit fixes work together without conflicts

**Status:** All critical, high, and medium severity issues from second audit are fixed and architect-approved. Phase 3 plan is production-ready.