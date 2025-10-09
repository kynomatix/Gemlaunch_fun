# Overview
gemlaunch.fun is a web platform designed for creating and launching memecoins on the Kaspa blockchain. It offers a no-code solution for memecoin creation, emphasizing fair launch mechanisms and community-driven tokens, leveraging Kaspa's high-performance L1 capabilities. The platform includes an AI Assistant (Gemmy), a social layer, a gamified leaderboard, and integrates with Kaspa Finance for DEX deployments. The project aims to democratize memecoin creation and foster a vibrant Kaspa ecosystem.

# Recent Changes

## October 8, 2025
- **Fixed Dashboard Turbo Navigation Bug**: Resolved grid layout rendering issue when navigating from other pages. Added `data-turbo="false"` to Dashboard link and implemented View Transitions API for smooth page transitions without white flash.
- **View Transitions API**: Added cross-fade animations for full page reloads, eliminating white screen between page loads while maintaining proper grid layout calculations.
- **UI Refinements**: Adjusted hamburger menu and logo spacing in top bar for optimal visual balance.
- **Smart Contract Progress Tracker**: Added comprehensive implementation checklist to SMART_CONTRACT_IMPLEMENTATION.md with 7 phases, starting with Testnet setup as Phase 1. Tracks all implementation milestones with checkboxes.
- **SMART_CONTRACT_IMPLEMENTATION.md Restructuring** (AUDIT-SAFE): 
  - Added "v4 CANONICAL IMPLEMENTATION" section consolidating all audit-approved code
  - Finalized implementation decisions (treasury remainder pattern, anti-bot 70/30 split)
  - Added Round 4 audit fix status cross-reference table
  - Created visual barrier separating historical/superseded code from current implementation
  - Updated Quick Reference with canonical line numbers
  - All changes were copy-only (no code modifications) to preserve audit integrity
- **BondingCurvePool.sol COMPLETE Specification** (Lines 220-748):
  - Added graduation functions (initiateGraduation, completeGraduation) with oracle authorization
  - Implemented creator fee claim portal (withdrawCreatorFees, getCreatorClaimableAmount)
  - Added access control & security (receive blocker, pause/unpause, oracle management)
  - Implemented 10% wallet cap enforcement via _transfer override
  - Added complete contract structure with OpenZeppelin imports (ERC20, ReentrancyGuard, Pausable, Ownable)
  - Comprehensive implementation checklist with line number references
  - STATUS: ✅ AUDIT READY
- **TokenFactory.sol COMPLETE Specification** (Lines 752-975):
  - Full createToken() implementation with metadata storage (name, symbol, description, image, socials)
  - Anti-spam controls: 60-second deployment cooldown per user (configurable 0-3600s)
  - Input validation: name/symbol length, supply limits (1M-1B tokens), 280-char descriptions
  - On-chain token registry with pagination (getDeployedTokens with offset/limit)
  - Admin functions: pause/unpause, cooldown updates, graduation controller management
  - View functions: canDeploy(), getSecondsUntilNextDeployment(), getTokenInfo()
  - STATUS: ✅ AUDIT READY
- **GraduationController.sol COMPLETE Specification** (Lines 979-1218):
  - Two-step graduation flow: initiateGraduation() → completeGraduation()
  - Kaspa Finance DEX integration (Uniswap V3 architecture, full-range positions, 0.25% fee tier)
  - Backend oracle integration for USD market cap verification ($70K threshold)
  - Liquidity transfer: virtualKasReserve + 25% token supply to DEX
  - Emergency controls: graduation reversal, token recovery, oracle updates
  - Position tracking: NFT position IDs, graduation timestamps
  - STATUS: ✅ AUDIT READY
- **v4 Canonical Implementation Complete**: All 3 core contracts (BondingCurvePool, TokenFactory, GraduationController) now have complete audit-ready specifications addressing all critical audit findings from Claude 4.5 review
- **CRITICAL FIX: PRO Token Wallet Cap Conflict Resolved**:
  - Issue: 10% wallet cap would block PRO token airdrop allocations (up to 25% of supply)
  - Solution: Updated _transfer override with airdropTreasury exemptions
  - Airdrop treasury can now hold 25% vested allocations
  - Transfers FROM airdropTreasury exempt from 10% cap (allows >10% distributions to team/founders/vesting contracts)
  - Line 621-641: Complete implementation with 4 exemption categories

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

### Anti-Bot System (GEM System) - AUDIT-APPROVED v4
Optional premium feature for PRO tokens. Time-based KAS fee decay (95% → 1% over 60 seconds) prevents bot sniping while rewarding patient community members. **Audit Status: ✅ ALL CRITICAL ISSUES FIXED** - Corrected fee calculation order (anti-bot first, then platform/creator from remainder), proper treasury validation, view functions for UX. All anti-bot fees sent immediately to Airdrop Treasury, funding community rewards.

### Token-Specific Community Points System
Each PRO token has its own community points system to reward engagement, tracking points, messages, trades, polls, and holdings, configurable by token creators.

### Multi-Wallet Linking System
Users can link multiple wallets via secure challenge-response authentication with cryptographic signature verification, preventing various forms of attack. A transfer request system allows merging accounts if a wallet is already primary for another user.

### Wallet Connection System
A modal-based system supports Kastle, KasWare, and MetaMask, using challenge-response authentication and a `WalletManager` for provider abstraction.

### Enhanced Marketplace Search
The marketplace features a comprehensive search system across token name, symbol, contract address, and creator information, with real-time, case-insensitive matching across all filter categories.

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
- **Kaspa Finance DEX**: Target DEX for token graduation and liquidity pools.
- **Smart Contract Stack**: Solidity ^0.8.20, Hardhat, OpenZeppelin, bonding curve token launches.

## External Services
- **Telegram**: Community engagement.
- **Twitter/X**: Social media.
- **Kaspa Finance**: Automatic DEX deployment.
- **presale.gemlaunch.fun**: External presale portal.
- **OpenRouter API**: For Gemmy AI, trend analysis, and image prompt enhancement (Meta Llama 3.1 70B).
- **Replicate API**: For AI-powered token image generation (FLUX.1 Schnell).
- **4chan /biz/**: Real-time meme trend scraping.
- **Reddit CryptoMoonShots**: Community-validated meme trends.