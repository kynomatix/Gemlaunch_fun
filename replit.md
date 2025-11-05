# Overview
gemlaunch.fun is a web platform for creating and launching memecoins on the Kaspa blockchain. It offers a no-code solution with an emphasis on fair launch mechanisms and community-driven tokens, leveraging Kaspa's high-performance L1 capabilities. The platform includes an AI Assistant (Gemmy), a social layer, a gamified leaderboard, and integrates with Kaspa Finance for DEX deployments. Its purpose is to democratize memecoin creation and foster a vibrant Kaspa ecosystem with business potential in the growing memecoin market.

# Recent Changes (Nov 3, 2025)
- **Achievement Auto-Evaluation**: Achievements now automatically evaluate and award after token deployment, in addition to lazy-loading when users click the Accolades tab
- **Stat Tracking Fixes**: `total_tokens_created` now automatically increments when tokens are deployed (was previously broken)
- **Trading Volume Display**: Dashboard now correctly converts KAS trading volume to USD for display
- **User Stats System**: Trading volume tracked automatically via event indexer processing TradeEvents every 30 seconds

# User Preferences
Preferred communication style: Simple, everyday language.

## Design Preferences
- **Button Style**: Sleek rectangular buttons with rounded corners (border-radius: 10px). NEVER use oval/pill-shaped buttons (border-radius: 25px+)
- **UI Consistency**: Token type icons are semantically meaningful:
  - BASIC tokens: ⚡ (fa-bolt) - Quick/simple launch
  - PRO tokens: 💎 (fa-gem) - Premium/advanced features

# System Architecture

## Frontend Architecture
The frontend uses Flask and Jinja2 for server-side rendering, a custom CSS framework (Grid, Flexbox, animations), and vanilla JavaScript. It incorporates particles.js and a GitBook-style tabbed documentation system, with a responsive and mobile-first design.

## Backend Architecture
Built with Flask, the backend features a minimal, route-based architecture with environment-based configuration, Python logging, and XSS protection. It includes an achievement system and interactive AI suggestions from Gemmy that auto-fill forms.

### AI Features
- **Gemmy Zeroday Memification Engine**: An AI-powered trend discovery system using OpenRouter API for multi-source cultural trend detection and Kaspa Tech analysis.
- **AI Token Image Generation**: A two-stage AI pipeline uses OpenRouter Llama 3.1 70B for prompt enhancement and Replicate FLUX.1 Schnell for 1024x1024 WebP image generation.
- **AI Multi-Category Token Classification**: Automatic token categorization using Llama 3.1 8B via OpenRouter. Categories are stored as JSON arrays.

### Core Features
- **Anti-Bot System (GEM System)**: An optional premium feature for PRO tokens using time-based KAS fee decay to prevent bot sniping.
- **Token-Specific Community Points System**: Allows PRO token creators to configure and track engagement points. Token creators are excluded from earning points in their own token's leaderboard.
- **Multi-Wallet Linking System**: Securely links multiple wallets via challenge-response authentication.
- **Wallet Connection System**: A modal-based system supporting Kastle, KasWare, and MetaMask using challenge-response authentication.
- **Enhanced Marketplace Search**: Provides comprehensive search across token name, symbol, contract address, and creator information.
- **Deployment Confirmation System**: A 6-layer security verification system for confirming token deployments.
- **X/Twitter Verification System**: OAuth 2.0-based social verification system that authenticates user identities and prevents impersonation.
- **KASPERS NFT Holder Recognition**: Social accolade system recognizes KASPERS NFT holders (KRC721) with a special achievement badge and bonus GEM points.
- **Graduation System**: Automated token lifecycle management transitioning tokens from bonding curve to DEX at a $50 market cap threshold, with a 4-state lifecycle. A monitor service checks eligibility every 60 seconds.
- **PRO Token Vesting System**: Fully implemented with atomic on-chain deployment. It uses a creator custody model for airdrop, marketing, and team vesting, managed by `TokenFactory V2` and `VestingDeployer V2` smart contracts. All vesting contracts (AirdropVesting, LinearVesting, CliffVesting) use `getWithdrawableAmount()` to check available balance, not `releasable()`.
- **Airdrop Distribution System**: PRO token creators can distribute airdrops to various recipient categories. The system automatically checks creator's wallet balance plus unlocked vesting tokens, bundles multi-step transactions, and protects all endpoints with CSRF tokens.
- **Poll Voting System with Token Burning**: Token creators can create polls with customizable vote costs requiring users to burn tokens to a specified burn address. The backend verifies burn transaction details to prevent replay attacks.

## Smart Contract Architecture
Core contracts (`BondingCurvePool.sol`, `TokenFactory.sol`, `GraduationController.sol`) manage token creation, bonding curve mechanics, creator fee claims, anti-bot measures, and a two-step graduation process for transitioning tokens to the Kaspa Finance DEX. The `BondingCurvePool` acts as the ERC20 token itself.
**CRITICAL: All contract addresses are managed in `contracts/deployed_addresses.json`**
**ALWAYS follow `contracts/DEPLOYMENT_GUIDE.md` when deploying new contracts**

## Database Schema
The `Token` model includes blockchain integration fields, `TradeEvent` for trade history, and `AntiBotFeeTracker` for fee distributions. `is_visible` and `graduation_disabled` flags manage token visibility and graduation eligibility.

### Data Architecture Strategy
A hybrid approach uses Blockscout GraphQL API and Web3 direct queries for real-time data, and `TradeEvent` database replay for historical chart data. The database retains user profiles, token metadata, trade history (charts), and social features. Timestamps are stored in UTC and displayed in the user's local timezone.

## Design Patterns
The project adheres to an MVC pattern.

## Performance Optimizations
Includes hardware-accelerated CSS animations, efficient asset caching, and JavaScript-enhanced smooth scrolling.

## Blockchain Integration Foundation
The system includes a Web3 Service Layer for RPC connection to **Kasplex zkEVM L2 (Testnet)**, an Oracle Wallet for automated operations, and contract loading. Transaction utilities handle gas estimation, signing, relay, and status polling, with POA middleware for Kasplex compatibility.
**⚠️ IMPORTANT: This platform uses Kasplex zkEVM L2, not native Kaspa L1.**
**CRITICAL: Kasplex Testnet Chain ID is 167012 (0x28c64).**

### CRITICAL GAS RULES - DO NOT MODIFY UNLESS EXPLICITLY ASKED
**🚨 LEGACY GAS MODE ONLY - NEVER CHANGE THIS 🚨**
- **ALL transactions MUST use LEGACY gas mode**: `gasPrice: self.w3.eth.gas_price`
- **NEVER use EIP-1559**: No `maxFeePerGas` or `maxPriorityFeePerGas`
- **NEVER add gas estimation to DEX swaps**: Gas estimation fails on Kasplex for DEX transactions
- **NEVER add gas limits to DEX swaps**: Let MetaMask handle gas estimation
- **Bonding curve pattern is the reference**: `services/web3_service.py` lines 1628-1673 show the correct pattern
- **DEX swap transactions return**: `{from, to, value, data, gasPrice}` ONLY - nothing else

This configuration works and has been tested. DO NOT modify gas-related code in `build_dex_buy_tx()` or `build_dex_sell_tx()` unless the user explicitly requests changes.

## Transaction Flow Architecture
Transactions follow a 5-phase lifecycle: Quote → Build → Sign → Relay → Monitor. Token creation is handled by a backend oracle wallet. Sell transactions require prior ERC20 approval for the BondingCurvePool. The `static/js/transaction_manager.js` module orchestrates all transaction types.

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