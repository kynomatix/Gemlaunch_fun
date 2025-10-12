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
Core contracts (`BondingCurvePool.sol`, `TokenFactory.sol`, `GraduationController.sol`) manage token creation, bonding curve mechanics, creator fee claims, anti-bot measures (wallet cap), and a two-step graduation process for transitioning tokens to the Kaspa Finance DEX. An off-chain backend service calculates auto-slippage. The BondingCurvePool acts as the ERC20 token itself.

## Database Schema
The `Token` model includes blockchain integration fields like `creator_fees_accumulated`, `deployment_block_number`, `nft_position_id`, and `liquidity_pool_address`. New models include `TradeEvent` and `AntiBotFeeTracker` for storing blockchain trade events and anti-bot fee distributions, with extensive indexing.

## Design Patterns
The project adheres to an MVC pattern, separating templates (views), Flask routes (controllers), and models.

## Performance Optimizations
Includes hardware-accelerated CSS animations, efficient asset caching, and JavaScript-enhanced smooth scrolling.

## Blockchain Integration Foundation
The system includes a Web3 Service Layer for RPC connection to Kasplex zkEVM L2 (Testnet), an Oracle Wallet for automated operations, and contract loading for `TokenFactory`, `GraduationController`, and `BondingCurvePool`. Transaction utilities handle gas estimation, signing, relay, and status polling, with POA middleware for Kasplex compatibility.

## Transaction Flow Architecture
Transactions follow a 5-phase lifecycle: Quote → Build → Sign → Relay → Monitor. For MetaMask, `eth_sendTransaction` combines Sign and Broadcast. For other wallets, the user signs, and the backend relays. Token creation is handled by a backend oracle wallet to maintain platform ownership and admin controls. Sell transactions require prior ERC20 approval for the BondingCurvePool.

## Transaction Manager Module
A dedicated `static/js/transaction_manager.js` module orchestrates all transaction types (token creation, buy, sell, claim fees) by integrating wallet management with backend APIs. It includes quote validation (freshness, mode), network validation (Kasplex Testnet), KAS balance checks, gas estimation display, IPFS upload error handling, and SSE connection management.

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

---

# Phase 3 Security Audits

## Third Security Audit & Final Fixes ✅
**Date:** October 12, 2025  
**Auditor:** Claude Opus (Final Security Review)

### Assessment
> "The plan is 95% there! Just fix the critical approval bug (CB-1) and implement the missing helper functions."

### Critical Bug Found & Fixed

#### CB-1: Sell Approval Logic Fundamentally Wrong (CRITICAL) ✅ FIXED
- **Issue:** Code tried to call `poolContract.token()` but BondingCurvePool doesn't have that function
- **Root Cause:** Misunderstood contract architecture - BondingCurvePool IS the ERC20 token (inherits from ERC20)
- **Fix:** Removed incorrect token() call, now correctly recognizes:
  1. BondingCurvePool inherits from ERC20 - it IS the token
  2. window.tokenContractAddress is the token address (not a separate contract)
  3. Approval: tokenContract.approve(window.tokenContractAddress, amount)
  4. This allows sellTokens() to call transferFrom(user, pool, amount)

### High Severity Fixes

#### H-5: AbortController Signal Not Propagated ✅ FIXED
- Added `signal` parameter to getQuote() method
- Properly passes signal to fetch options
- Enables request cancellation for in-flight quotes

#### H-6: Loading State Functions Missing ✅ FIXED
- Added all 6 missing helper functions:
  - showQuoteLoading() / hideQuoteLoading()
  - clearFeeBreakdown()
  - showQuoteError(errorMessage)
  - showTradeStatus(message) / hideTradeStatus()
- Added complete CSS for loading animations and spinner

### Medium Severity Fixes

#### M-5: Gas Estimation Method ✅ FIXED
- Added estimate_trade_gas() to web3_service.py
- Estimates gas for buy/sell transactions
- Returns gas units needed

#### M-6: Quote Methods Implementation ✅ FIXED
- Added get_buy_quote() to web3_service.py
- Added get_sell_quote() to web3_service.py
- Both return: tokens/kas_out, fee breakdown, auto_slippage, price_impact

#### M-7: Deployment Modal Functions ✅ FIXED
- Added showDeploymentModal()
- Added hideDeploymentModal()
- Added updateDeploymentStatus(message)

---

## Fourth Security Audit & Final Data Flow Fixes ✅
**Date:** October 12, 2025  
**Auditor:** Claude Opus (Final Data Flow Review)

### Assessment
> "Great progress! The critical bug (CB-1) is now properly fixed. However, I found 2 medium severity issues that will cause runtime problems."

### Medium Severity Fixes

#### M-8: Quote Data Structure Mismatch (CRITICAL DATA FLOW) ✅ FIXED
- **Issue:** Quote stored in nested structure but accessed directly
  - Stored: `window.lastQuote = { data: quote, timestamp, mode }`
  - Accessed: `window.lastQuote?.auto_slippage_bps` (undefined!)
- **Result:** Slippage always defaulted to 50 bps instead of using smart contract's calculated value
- **Fix:** Changed to flat structure using spread operator
  - Now: `window.lastQuote = { ...quote, timestamp, mode }`
  - Allows direct access: `window.lastQuote?.auto_slippage_bps` ✅

#### M-9: Sell Quote Uses Wrong Input Parameter ✅ FIXED
- **Issue:** Sell quotes need `token_amount` but code passed `kas_amount` for both modes
- **Result:** Sell quote requests would fail with "invalid parameter" error
- **Fix:** Implemented mode-based parameter selection
  - BUY mode: User enters KAS → passes `kas_amount` parameter ✅
  - SELL mode: User enters tokens → passes `token_amount` parameter ✅
  - Updates correct output field based on mode
  - USD value calculation works for both modes

### Architect Assessment
> "The M-8 and M-9 fixes satisfy audit requirements with no blocking defects. Quote persistence now flattens the response object, aligning structure with all access sites. updateTokenAmount() dynamically selects correct parameters, restores sell-quote backend compatibility. No regressions in surrounding logic."

**Verification:**
- ✅ No stale `lastQuote.data` references found
- ✅ Flat structure consistent with all slippage calculations
- ✅ Buy/sell parameter handling verified correct
- ✅ Output field updates work for both modes

**Status:** Phase 3 plan is **100% complete** after 4 security audits. All critical, high, and medium issues resolved. Planning document ready for implementation.