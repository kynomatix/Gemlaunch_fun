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
  
- **External Security Audit**:
  - Conducted comprehensive security audit via Claude
  - Fixed all 7 vulnerabilities (3 Critical, 3 High, 1 Medium)
  - Critical fixes: Constructor initialization, underflow protection, fund stranding prevention
  - All fixes architect-reviewed and approved ✅
  
- **Phase 0 Status**: ✅ COMPLETE - Ready for Phase 1 (Testnet Deployment)

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