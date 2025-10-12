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
- **Gemmy Zeroday Memification Engine**: An AI-powered trend discovery system using OpenRouter API for multi-source cultural trend detection and Kaspa Tech analysis.
- **AI Token Image Generation**: A two-stage AI pipeline uses OpenRouter Llama 3.1 70B for prompt enhancement and Replicate FLUX.1 Schnell for 1024x1024 WebP image generation.

### Core Features
- **PRO Token Airdrop System**: Manages airdrops with a 5% per day vesting schedule.
- **Anti-Bot System (GEM System)**: An optional premium feature for PRO tokens using time-based KAS fee decay to prevent bot sniping.
- **Token-Specific Community Points System**: Allows PRO token creators to configure and track engagement points.
- **Multi-Wallet Linking System**: Securely links multiple wallets via challenge-response authentication.
- **Wallet Connection System**: A modal-based system supporting Kastle, KasWare, and MetaMask using challenge-response authentication.
- **Enhanced Marketplace Search**: Provides comprehensive search across token name, symbol, contract address, and creator information.

## Smart Contract Architecture
Core contracts (`BondingCurvePool.sol`, `TokenFactory.sol`, `GraduationController.sol`) manage token creation, bonding curve mechanics, creator fee claims, anti-bot measures, and a two-step graduation process for transitioning tokens to the Kaspa Finance DEX. The BondingCurvePool acts as the ERC20 token itself.

## Database Schema
The `Token` model includes blockchain integration fields. New models include `TradeEvent` and `AntiBotFeeTracker` for storing blockchain trade events and anti-bot fee distributions.

## Design Patterns
The project adheres to an MVC pattern.

## Performance Optimizations
Includes hardware-accelerated CSS animations, efficient asset caching, and JavaScript-enhanced smooth scrolling.

## Blockchain Integration Foundation
The system includes a Web3 Service Layer for RPC connection to Kasplex zkEVM L2 (Testnet), an Oracle Wallet for automated operations, and contract loading. Transaction utilities handle gas estimation, signing, relay, and status polling, with POA middleware for Kasplex compatibility.

## Transaction Flow Architecture
Transactions follow a 5-phase lifecycle: Quote → Build → Sign → Relay → Monitor. Token creation is handled by a backend oracle wallet. Sell transactions require prior ERC20 approval for the BondingCurvePool.

## Transaction Manager Module
A dedicated `static/js/transaction_manager.js` module orchestrates all transaction types (token creation, buy, sell, claim fees) by integrating wallet management with backend APIs. It includes quote validation, network validation, KAS balance checks, gas estimation display, IPFS upload error handling, and SSE connection management.

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

# Phase 3 Implementation Progress & Audit

## PHASE 3 AUDIT REPORT ✅
**Date:** October 12, 2025  
**Auditor:** Claude Opus

### Status: 70% Complete (7/10 tasks done)

#### ✅ COMPLETE - Frontend (Phases 3.1-3.7)
- ✅ **3.1:** TransactionManager class with 5-phase transaction flow
- ✅ **3.2:** Web3Service methods (estimate_gas, get_buy_quote, get_sell_quote)
- ✅ **3.3:** Real-time quote updates (M-8, M-9, CD-1 fixes applied)
- ✅ **3.4:** Fee breakdown display (Anti-Bot, 0.9% Platform, 0.1% Creator, Price Impact)
- ✅ **3.5:** executeTrade() with approval flow, network validation, gas estimation
- ✅ **3.6:** Loading helpers with UX fixes (spinner on input field)
- ✅ **3.7:** Input event listeners with M-10 fix (mode-aware quote updates)

#### ❌ MISSING - Backend APIs (Phase 3.8)
**Required endpoints NOT implemented:**
- ❌ POST /api/trade/quote-buy
- ❌ POST /api/trade/quote-sell  
- ❌ POST /api/trade/buy
- ❌ POST /api/trade/sell
- ❌ POST /api/trade/{action}/estimate-gas
- ❌ POST /api/relay/transaction
- ❌ GET /api/tx/{hash}/stream (SSE)

**Impact:** Frontend complete but cannot execute trades without backend

#### ⏸️ BLOCKED - Testing (Phases 3.9-3.10)
- ⏸️ **3.9:** Buy transaction testing (blocked by missing backend)
- ⏸️ **3.10:** Sell transaction testing (blocked by missing backend)

### Key Fixes Applied
- **CB-1:** ERC20 approval - BondingCurvePool IS the token (correct architecture)
- **M-8:** Quote storage with flat structure (spread operator)
- **M-9:** Mode-based parameters (kas_amount for buy, token_amount for sell)
- **M-10:** Mode-aware input listeners (buy/sell gating)
- **CD-1:** Quote storage in main updateTokenAmount() function
- **H-2:** Network validation (Chain ID 167012)
- **H-3:** KAS balance check before buy
- **H-4:** Gas estimation display
- **H-5:** AbortController signal propagation
- **H-6:** Loading state functions with CSS animations
- **NC-2:** SSE connection cleanup
- **NC-3:** Quote freshness validation (30-second expiry)

### SMART_CONTRACT_IMPLEMENTATION.md Updates
✅ Marked complete in official planning doc:
- [x] Step 1: Real-time quote updates (Phase 3.3)
- [x] Step 2: Fee breakdown display (Phase 3.4)
- [x] Step 3: Trade execution (Frontend complete, backend pending)
- [x] Step 4: Loading & Status Helpers (Phase 3.6)
- [x] Step 5: CSS for Loading States (Phase 3.6)
- [x] Step 6: Input Event Listeners (Phase 3.7)

### Next Steps
**PRIORITY:** Implement Phase 3.8 backend API routes to unblock testing
