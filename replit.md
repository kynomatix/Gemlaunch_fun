# Overview
gemlaunch.fun is a web platform designed to facilitate the creation and launch of memecoins on the Kaspa blockchain. The project aims to democratize memecoin creation through a no-code solution, emphasizing fair launch mechanisms and community-driven tokens. It leverages Kaspa's high-performance L1 capabilities for rapid transaction processing. Key features include an AI Assistant (Gemmy), a social layer with $cashtags, and a gamified leaderboard. The platform supports Kaspa's ecosystem by integrating miner-friendly economics and Kaspa Finance for automatic DEX deployments. It also includes a comprehensive achievement system to reward user engagement.

# User Preferences
Preferred communication style: Simple, everyday language.

## Design Preferences
- **Button Style**: Sleek rectangular buttons with rounded corners (border-radius: 10px). NEVER use oval/pill-shaped buttons (border-radius: 25px+)

# System Architecture

## Frontend Architecture
The application uses a server-side rendered approach with Flask and Jinja2, featuring a custom CSS framework (CSS Grid, Flexbox, animations) and vanilla JavaScript for interactivity. It includes a particles.js integration and a GitBook-style tabbed documentation system. The design is responsive and mobile-first.

## Backend Architecture
Built with Flask, the backend follows a minimal, route-based architecture with environment-based configuration and Python logging. It includes a comprehensive achievement system tracking user activities, secure API endpoints, and XSS protection.

### Interactive Gemmy Chat
Gemmy's AI token suggestions are interactive; clicking an option auto-fills the token creation form with extracted name, symbol, and description, adapting to Simple or Advanced mode.

### Gemmy Zeroday Memification Engine
An AI-powered trend discovery system operates in three modes: Creative, Trending Memes (multi-source cultural trend detection from platforms like Know Your Meme, 4chan, Reddit CryptoMoonShots, scored by crypto-adoptability criteria), and Kaspa Tech (memification of Kaspa-native concepts). Technical implementation uses OpenRouter API with auto-failover, parallel processing for rapid analysis (6-8 seconds), source-aware fallback scoring, and a 12-hour rolling PostgreSQL cache.

### AI Token Image Generation
A two-stage AI pipeline generates token images. Stage 1 uses OpenRouter Llama 3.1 70B for prompt enhancement with Kaspa-specific styling. Stage 2 uses Replicate FLUX.1 Schnell to generate 1024x1024 WebP images. Users can generate, preview, and regenerate images within the token creation form via a Flask API endpoint.

### PRO Token Airdrop System
Features a comprehensive airdrop management system with a 5% per day vesting schedule (20-day full unlock). Supports various distribution types: Random Raffle, Top Contributors, Active Chatters, Token Holders, and Early Supporters. It includes a database schema for campaigns and recipients, with API endpoints for availability and creation, and a dynamic modal UI.

### Token-Specific Community Points System
Each PRO token has its own community points system to reward engagement. The `TokenEngagement` model tracks per-user, per-token metrics (points, messages, trades, polls, holdings). Points are distributed for chat, trading, poll, and spotlight activities, configurable by token creators. Integrates with token-specific leaderboards and will gate future features.

### Multi-Wallet Linking System
Users can link multiple wallets to their primary account using a secure challenge-response authentication with cryptographic signature verification. The system prevents whale wallet theft, replay attacks, and cross-profile hijacking, and provides a clear user experience for managing linked wallets.

### Transfer Request & Wallet Linking System
Allows users to link wallets that are already primary for another account through an approval flow. When a wallet is already in use, the owner receives a transfer request notification and can approve linking their wallet to the requester's account. The system merges data (achievements, GEM points, token engagements) into the requester's account while converting the owner's primary wallet to a LinkedWallet entry. **Crucially, both wallets remain usable** - the owner's wallet becomes linked to the requester's account, allowing login with either wallet to access the same merged account. Login resolution checks LinkedWallet table first for proper account routing. Features challenge-response verification, rate limiting (max 3 pending requests), 24-hour request expiration, and MetaMask account verification to prevent signature mismatches.

### Wallet Connection System
A modal-based system supports Kastle, KasWare, and MetaMask. It uses challenge-response authentication, `WalletManager` module for provider abstraction, and handles MetaMask account switching with auto-disconnect on change. API endpoints manage nonce generation, verification, session status, and disconnection. UI conditionally renders access based on wallet connection status.

### Enhanced Marketplace Search
The marketplace features a comprehensive search system that searches across multiple token fields: token name, symbol, contract address, and creator username/wallet address. Search operates in real-time with case-insensitive matching and works seamlessly with all filter categories (trending, social, new, gainers, near-grad, graduated, pro, basic). The implementation includes null-safe handling to prevent crashes when token data is incomplete. The search bar expands to 400-750px on desktop for comfortable multi-term searches.

## Design Patterns
Adheres to an MVC pattern, separating templates (views), Flask routes (controllers), and models. Utilizes efficient static asset organization and a component-based CSS approach.

## Performance Optimizations
Includes hardware-accelerated CSS animations, efficient asset caching, and JavaScript-enhanced smooth scrolling.

# External Dependencies

## Core Dependencies
- **Flask**: Python web framework.
- **Jinja2**: Template engine.

## Frontend Libraries
- **Font Awesome 6.0.0**: Icon library.
- **Google Fonts (Inter)**: Typography.
- **particles.js**: Particle animation library.

## Blockchain Integration
- **Kasplex zkEVM L2**: EVM-compatible Layer 2 on Kaspa for smart contract deployment (Chain ID: 202555 mainnet, 167012 testnet)
- **Kaspa Finance DEX**: Target DEX for token graduation and liquidity pools
- **Smart Contract Stack**: Solidity ^0.8.20, Hardhat, OpenZeppelin, bonding curve token launches

## External Services
- **Telegram**: Community engagement.
- **Twitter/X**: Social media.
- **Kaspa Finance**: Automatic DEX deployment.
- **presale.gemlaunch.fun**: External presale portal.
- **OpenRouter API**: For Gemmy AI, trend analysis, and image prompt enhancement (Meta Llama 3.1 70B, auto-failover).
- **Replicate API**: For AI-powered token image generation (FLUX.1 Schnell).
- **4chan /biz/**: Real-time meme trend scraping.
- **Reddit CryptoMoonShots**: Community-validated meme trends.

# Technical Debt & Known Issues

## Recent Codebase Audit (October 2025)
A comprehensive audit identified 15 issues across 4 severity levels. See `CODEBASE_AUDIT_REPORT.md` for full details.

### Critical Issues (Immediate Action Required)
- **Hardcoded admin key**: Admin routes use hardcoded 'gemlaunch-admin-2024' key in source code instead of wallet-based authentication with role verification

### High Priority Issues
- **Missing database indexes**: Activity.created_at, ChatMessage(token_id, created_at), TokenLeaderboard(token_id, points), Holding(token_id, token_amount) need indexes for performance at scale
- **No CSRF protection**: POST/DELETE routes vulnerable to cross-site request forgery
- **Monolithic app.py**: 2900-line file needs refactoring into Flask blueprints for maintainability
- **lazy='dynamic' relationships**: User.tokens_created and User.trades cause extra queries, should use explicit eager loading

### Medium Priority Issues
- **Rate limiting gaps**: Only wallet linking has rate limits; add to auth, token creation, chat, admin routes
- **Blockchain integration gap**: Platform currently uses mock/database-driven token launches; need smart contract integration on Kasplex zkEVM for real token deployment, bonding curves, and Kaspa Finance DEX graduation (see SMART_CONTRACT_IMPLEMENTATION.md for roadmap)

## Security Audit Integration (October 2025)
- **External Audits**: Received comprehensive security audits from Claude and ChatGPT covering smart contract architecture
- **Critical Fixes Implemented**: 13 critical security issues addressed in SMART_CONTRACT_IMPLEMENTATION.md:
  1. ✅ Fixed bonding curve math (proper constant product AMM instead of broken midpoint pricing)
  2. ✅ Fixed fee distribution (no double-fee on roundtrips)
  3. ✅ Fixed fee accounting asymmetry (separate grossInBase/netReservesBase tracking)
  4. ✅ Fixed graduation front-running (auto-graduation, atomic execution)
  5. ✅ Added graduation lock mechanism (lockForGraduation mutex)
  6. ✅ Fixed wallet cap bypass (enforced in _transfer override)
  7. ✅ Added minimum liquidity check (current balance, not totalRaised)
  8. ✅ Fixed reentrancy risk (pull-based creator fee claiming)
  9. ✅ Fixed treasury distribution (use .call instead of .transfer)
  10. ✅ Added slippage protection (minTokensOut, minRefund, deadline parameters)
  11. ✅ Replaced all .transfer() with .call{value:}() for smart wallet compatibility
  12. ✅ Made creator fee immutable (prevents rug pulls)
  13. ✅ Added TWAP buyback slippage protection (oracle-based price checks)

### Low Priority Issues
- **SQLAlchemy LSP warnings**: 88 type checker false positives due to backref relationships and constructor patterns

## Fixes Completed
- ✅ Fixed stored XSS vulnerability in profile modal (proper HTML escaping)
- ✅ Resolved leaderboard profile modal hanging issue (async/await with error handling)
- ✅ Fixed Turbo Drive navigation bugs (carousel initialization, number formatting)
- ✅ Patched datetime timezone mismatch in achievement service (holding_days calculation)
- ✅ **Implemented comprehensive CSRF protection** (October 2025): Flask-WTF CSRFProtect initialized, CSRF tokens added to all HTML forms and JavaScript fetch calls, X-CSRFToken headers on all POST/DELETE requests
- ✅ **Added performance database indexes** (October 2025): Activity.created_at, ChatMessage(token_id, created_at), TokenLeaderboard(token_id, points), Holding(token_id, token_amount)
- ✅ **Comprehensive MetaMask wallet integration fixes** (October 2025): Created centralized `getMetaMaskProvider()` helper for EIP-6963 multi-wallet support, fixed wallet detection/connection/signing/disconnection to handle multiple wallet extensions, updated all 10+ MetaMask touchpoints (wallet_manager.js + profile.html), added 2-second timeout to prevent disconnect hanging, ensured CSRF tokens on all wallet API endpoints
- ✅ **Code duplication cleanup** (October 2025): Eliminated 300+ lines of duplicated code by creating reusable utilities - static/js/utils/modal.js (centralized modal system for alert/confirm/prompt), static/js/utils/animations.js (IntersectionObserver scroll reveals with counter animations), utils/validators.py (wallet address validation). Updated docs.js, main.js, token_detail.js, and app.py to use shared utilities
- ✅ **Deprecated field cleanup** (October 2025): Removed unused UserProfile.profile_picture_url field from model, templates (profile.html, leaderboard.html), app.py fallback logic, and dropped database column
- ✅ **Kaspa wallet signature verification** (October 2025): Implemented cryptographic signature verification for Kastle and KasWare wallets. These wallets use EVM connectivity on Kaspa L2s, so they now use the same Ethereum personal_sign verification as MetaMask. Removed bypass logic and obsolete TODO, added nonce invalidation on verification failure
- ✅ **Dashboard performance optimization** (October 2025): Eliminated 5+ database queries that ran on every dashboard page load by implementing event-driven real-time stat updates. Stats now update instantly when events occur (token creation, chat messages, graduations). Consolidated graduation logic to single canonical path in Token.graduate_token() to prevent stat drift