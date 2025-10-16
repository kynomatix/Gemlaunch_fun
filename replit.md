# Overview
gemlaunch.fun is a web platform for creating and launching memecoins on the Kaspa blockchain. It offers a no-code solution with an emphasis on fair launch mechanisms and community-driven tokens, leveraging Kaspa's high-performance L1 capabilities. The platform includes an AI Assistant (Gemmy), a social layer, a gamified leaderboard, and integrates with Kaspa Finance for DEX deployments. Its purpose is to democratize memecoin creation and foster a vibrant Kaspa ecosystem with business potential in the growing memecoin market.

# User Preferences
Preferred communication style: Simple, everyday language.

## Design Preferences
- **Button Style**: Sleek rectangular buttons with rounded corners (border-radius: 10px). NEVER use oval/pill-shaped buttons (border-radius: 25px+)
- **UI Consistency**: Token creation mode names match marketplace filters:
  - Basic Mode (cog icon) - Quick launch
  - Pro Mode (star icon) - Advanced features

# System Architecture

## Frontend Architecture
The frontend uses Flask and Jinja2 for server-side rendering, a custom CSS framework (Grid, Flexbox, animations), and vanilla JavaScript. It incorporates particles.js and a GitBook-style tabbed documentation system, with a responsive and mobile-first design.

## Backend Architecture
Built with Flask, the backend features a minimal, route-based architecture with environment-based configuration, Python logging, and XSS protection. It includes an achievement system and interactive AI suggestions from Gemmy that auto-fill forms.

### AI Features
- **Gemmy Zeroday Memification Engine**: An AI-powered trend discovery system using OpenRouter API for multi-source cultural trend detection and Kaspa Tech analysis.
- **AI Token Image Generation**: A two-stage AI pipeline uses OpenRouter Llama 3.1 70B for prompt enhancement and Replicate FLUX.1 Schnell for 1024x1024 WebP image generation.

### Core Features
- **Anti-Bot System (GEM System)**: An optional premium feature for PRO tokens using time-based KAS fee decay to prevent bot sniping.
- **Token-Specific Community Points System**: Allows PRO token creators to configure and track engagement points.
- **Multi-Wallet Linking System**: Securely links multiple wallets via challenge-response authentication.
- **Wallet Connection System**: A modal-based system supporting Kastle, KasWare, and MetaMask using challenge-response authentication.
- **Enhanced Marketplace Search**: Provides comprehensive search across token name, symbol, contract address, and creator information.
- **Deployment Confirmation System**: A 6-layer security verification system for confirming token deployments, ensuring server-side blockchain verification and multi-layer defense against fake deployments.

### PRO Token Vesting System
✅ **STATUS: Fully implemented - Atomic on-chain deployment**
- **Design:** Automatic beneficiary system with zero configuration complexity
  - Airdrop vesting → Platform's airdropTreasury wallet (5% daily unlock via AirdropVesting)
  - Marketing vesting → Creator's wallet (12-month linear via LinearVesting)
  - Team vesting → Creator's wallet (6mo cliff + 18mo vest via CliffVesting)
- **Smart Contracts:**
  - TokenFactory (0x2DDb083fCd62D27E9eE1F557B53140bD61F3009D) - deploys pool + vesting atomically
  - VestingDeployer (0x07edeC513453f193673639Fd60eC35Bc27f1A5E2) - helper contract for vesting deployment
  - Atomic deployment: user pays once, all contracts deployed in single transaction
- **Architecture:** Event-based vesting address extraction
  - TokenFactory emits VestingDeployed event with all three vesting contract addresses
  - Backend extracts addresses from event logs and saves to database
  - No async deployment, no timeout issues, no oracle wallet subsidy
- **Contract Size Optimization:**
  - VestingDeployer pattern used to avoid 24KB contract size limit
  - TokenFactory metadata storage removed (rely on events for data)
- **Frontend Portal:** Vesting status display on token detail pages with unlock schedules
- **Security:** All critical issues from spec audits resolved, matches PRO_TOKEN_VESTING_SPECIFICATION_V2.md exactly

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
Transactions follow a 5-phase lifecycle: Quote → Build → Sign → Relay → Monitor. Token creation is handled by a backend oracle wallet. Sell transactions require prior ERC20 approval for the BondingCurvePool. The `static/js/transaction_manager.js` module orchestrates all transaction types by integrating wallet management with backend APIs, including quote validation, network validation, KAS balance checks, gas estimation display, IPFS upload error handling, and SSE connection management.

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