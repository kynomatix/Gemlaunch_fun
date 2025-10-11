# Overview
gemlaunch.fun is a web platform for creating and launching memecoins on the Kaspa blockchain. It offers a no-code solution, emphasizing fair launch mechanisms and community-driven tokens, leveraging Kaspa's high-performance L1 capabilities. The platform includes an AI Assistant (Gemmy), a social layer, a gamified leaderboard, and integrates with Kaspa Finance for DEX deployments. The project aims to democratize memecoin creation and foster a vibrant Kaspa ecosystem.

# Recent Changes

## October 10, 2025 - Phase 0 Complete: Smart Contract Development Ready ✅
- **Testnet Environment Setup**:
  - Deployer wallet: 0xe281e4776FB5De20817D0bbC72B0C4b955565619 (100 testnet KAS funded)
  - Kasplex Testnet configured (Chain ID: 167012, RPC: https://rpc.kasplextest.xyz)
  - All treasury addresses configured (using deployer for testnet simplicity)
  - Kaspa Finance DEX addresses confirmed (QuoterV2: 0x3ACc31F8fe86E365604eAa6dDCbcB7fEba7a4c2B)
  
- **Smart Contract Implementation**:
  - Created audit-approved v4 contracts (900 lines total):
    - contracts/BondingCurvePool.sol (452 lines) - Core trading with Anti-Bot GEM system
    - contracts/TokenFactory.sol (222 lines) - Token creation with anti-spam
    - contracts/GraduationController.sol (226 lines) - DEX graduation orchestration
  - Comprehensive test suite: **105/105 tests passing (100% pass rate)**
  - All security features verified: Anti-bot fees (70/30 split), wallet cap (10%), graduation flow, emergency controls
  - Development stack: Node.js 22.17.0, Hardhat 2.26, OpenZeppelin contracts
  
- **External Security Audits** (2 rounds):
  - **First Audit**: Fixed 7 vulnerabilities (3 Critical, 3 High, 1 Medium)
    - Constructor initialization, underflow protection, fund stranding prevention
  - **Second Audit**: Fixed 4 vulnerabilities (1 Critical, 2 Medium, 1 Low)
    - **C-4 CRITICAL**: Fixed distributeFees() draining trading reserves (would have been catastrophic)
    - Gas optimizations, configurable slippage, duplicate address validation
  - **Total**: 11 vulnerabilities fixed (4 Critical, 3 High, 3 Medium, 1 Low)
  - All fixes architect-reviewed and approved ✅
  - Final test suite: **91/91 tests passing (100%)**
  
- **Phase 0 Status**: ✅ COMPLETE - Ready for Phase 1 (Testnet Deployment)

## October 11, 2025 - Phase 1 Complete: Testnet Deployment Live ✅
- **Deployed Contracts (Kasplex Testnet - Chain ID: 167012)**:
  - **TokenFactory**: 0x348640F6e87a0226e8E4CdB5e068282B5D0b2F60
    - Transaction: 0x7528b202ce5c0484cb30d9db231a470078a6e6f10e945ae407068e5b60874943
    - Block: 7767989
    - Gas: ~4.9M (~24.39 KAS)
  - **GraduationController**: 0x9416D5a5D61ec70C18D1FE1039f8026E29b4820e
    - Transaction: 0xcf516197a019329ba6c6e8262f67efb652bff9410bf02fa3fecd8d34c2770ca0
    - Block: 7768289
    - Gas: ~1.3M (~2.59 KAS)
  - **Contracts Linked**: TokenFactory → GraduationController verified ✅
    - Linking Tx: 0x78d5bc4bc87eded7ba9a754253a58829ea1402d7a6c3485d55520bddc41cd3e7

- **Wallet Control Architecture**:
  - **Primary Wallet** (0xe281e4776FB5De20817D0bbC72B0C4b955565619):
    - Controls: Owner, Treasury, Platform Dev, Buyback, Kaspa Support, Community Rewards
    - Env: DEPLOYER_PRIVATE_KEY
  - **Secondary Wallet** (0x5f837F62744D4d80Fc79C3A5346B4A228956914E):
    - Controls: Admin, Graduation Oracle, Airdrop Treasury
    - Derived from deployer (m/44'/60'/0'/0/1) - fully controlled & recoverable
  - All validation constraints satisfied (treasury ≠ admin, treasury ≠ oracle, airdropTreasury ≠ platformDev) ✅

- **Deployment Infrastructure**:
  - Created resilient deployment scripts with controlled-address validation
  - Automated linking script with permission enforcement
  - Comprehensive deployment summary: `deployments/PHASE_1_DEPLOYMENT_SUMMARY.md`
  - All verification commands validated against constructor ABIs

- **Kaspa Finance Integration Configured**:
  - NFT Position Manager: 0x4E25637cF39822364b877F81B18c5B6CF0eeF589
  - WKAS: 0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94
  - QuoterV2: 0x3ACc31F8fe86E365604eAa6dDCbcB7fEba7a4c2B

- **Phase 1 Status**: ✅ COMPLETE - Ready for Phase 2 (Backend Web3 Integration)

## October 11, 2025 - Phase 2 Planning: COMPLETE ✅
- **Comprehensive Backend Integration Audit**:
  - Identified 13 major task sections for blockchain integration (2.0-2.12)
  - Platform currently uses mock data (tokens, trades, users) - ready for sunset
  - Critical fixes identified: temporary image URLs, missing fee claim routes, tx monitoring
  
- **Phase 2 Final Scope** (Tasks 2.0-2.12):
  - **2.0**: Transaction relay & authorization model (FOUNDATIONAL) 🔐
    - 3 distinct flows: User transactions, Privileged actions, Oracle actions
    - Security: No user key custody, signature validation, rate limiting, audit logs
  - **2.1-2.5**: Core Web3 infrastructure (RPC, ABIs, event indexer, database)
  - **2.6**: Trading APIs (quote-buy, quote-sell, buy, sell, auto-slippage) 🚨 CRITICAL
  - **2.7**: Fee management (creator claims, platform distribution, anti-bot tracking)
  - **2.8**: Transaction monitoring (status polling, retries, websockets, queue management)
  - **2.9**: Post-graduation DEX integration (pool data, redirects, NFT positions)
    - Dependency: Requires event indexer (2.4) capturing NFT position ID first
  - **2.10**: Gas estimation & network validation (Chain ID checks, RPC fallback)
  - **2.11**: Permanent image storage (IPFS/Pinata vs temporary Replicate URLs) 🚨 CRITICAL
  - **2.12**: Reserve token distribution for PRO tokens (team/marketing allocations)

- **Integration Strategy**:
  - Connect platform piece-by-piece to deployed contracts
  - Mock data will be sunset after integration (users/tokens/trades cleaned later)
  - Focus on blockchain connection first, database cleanup deferred
  - Testnet wallet: ~63 KAS remaining for integration testing
  
- **Phase 2 Planning Status**: ✅ COMPLETE - Ready for implementation
  - All transaction relay flows defined
  - Wallet authorization model clarified
  - Sequencing dependencies documented
  - Architect-reviewed and approved

# User Preferences
Preferred communication style: Simple, everyday language.

## Design Preferences
- **Button Style**: Sleek rectangular buttons with rounded corners (border-radius: 10px). NEVER use oval/pill-shaped buttons (border-radius: 25px+)

# System Architecture

## Frontend Architecture
The application uses Flask and Jinja2 for server-side rendering, a custom CSS framework (Grid, Flexbox, animations), and vanilla JavaScript. It includes particles.js and a GitBook-style tabbed documentation system, with a responsive and mobile-first design.

## Backend Architecture
Built with Flask, the backend features a minimal, route-based architecture with environment-based configuration, Python logging, and XSS protection. It includes a comprehensive achievement system.

### Interactive Gemmy Chat
Gemmy's AI suggestions are interactive; clicking an option auto-fills the token creation form.

### Gemmy Zeroday Memification Engine
An AI-powered trend discovery system operates in Creative, Trending Memes (multi-source cultural trend detection), and Kaspa Tech modes. It uses OpenRouter API with auto-failover, parallel processing, source-aware fallback scoring, and a 12-hour rolling PostgreSQL cache.

### AI Token Image Generation
A two-stage AI pipeline generates token images: OpenRouter Llama 3.1 70B for prompt enhancement and Replicate FLUX.1 Schnell for 1024x1024 WebP image generation.

### PRO Token Airdrop System
A comprehensive airdrop management system with a 5% per day vesting schedule (20-day full unlock). Supports various distribution types: Random Raffle, Top Contributors, Active Chatters, Token Holders, and Early Supporters.

### Anti-Bot System (GEM System)
An optional premium feature for PRO tokens that uses time-based KAS fee decay (95% → 1% over 60 seconds) to prevent bot sniping. All anti-bot fees are sent immediately to the Airdrop Treasury.

### Token-Specific Community Points System
Each PRO token has its own community points system to reward engagement, tracking points, messages, trades, polls, and holdings, configurable by token creators.

### Multi-Wallet Linking System
Users can link multiple wallets via secure challenge-response authentication with cryptographic signature verification. A transfer request system allows merging accounts if a wallet is already primary for another user.

### Wallet Connection System
A modal-based system supports Kastle, KasWare, and MetaMask, using challenge-response authentication and a `WalletManager` for provider abstraction.

### Enhanced Marketplace Search
The marketplace features a comprehensive search system across token name, symbol, contract address, and creator information, with real-time, case-insensitive matching across all filter categories.

## Smart Contract Architecture
The core contracts include `BondingCurvePool.sol`, `TokenFactory.sol`, and `GraduationController.sol`. These manage token creation, bonding curve mechanics, creator fee claims, anti-bot measures (wallet cap), and a two-step graduation process for transitioning tokens to the Kaspa Finance DEX. The system incorporates an off-chain backend service for auto-slippage calculation to optimize trades.

## Design Patterns
Adheres to an MVC pattern, separating templates (views), Flask routes (controllers), and models, with efficient static asset organization and component-based CSS.

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
- **Kasplex zkEVM L2**: EVM-compatible Layer 2 on Kaspa for smart contract deployment.
- **Kaspa Finance DEX**: Target DEX for token graduation and liquidity pools (Uniswap V3 architecture).
- **Smart Contract Stack**: Solidity ^0.8.20, Hardhat, OpenZeppelin.

## External Services
- **Telegram**: Community engagement.
- **Twitter/X**: Social media.
- **Kaspa Finance**: Automatic DEX deployment.
- **presale.gemlaunch.fun**: External presale portal.
- **OpenRouter API**: For Gemmy AI, trend analysis, and image prompt enhancement (Meta Llama 3.1 70B).
- **Replicate API**: For AI-powered token image generation (FLUX.1 Schnell).
- **4chan /biz/**: Real-time meme trend scraping.
- **Reddit CryptoMoonShots**: Community-validated meme trends.