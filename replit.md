# Overview
gemlaunch.fun is a web platform designed for creating and launching memecoins on the Kaspa blockchain. It offers a no-code solution, emphasizing fair launch mechanisms and community-driven tokens, leveraging Kaspa's high-performance L1 capabilities. The platform includes an AI Assistant (Gemmy), a social layer, a gamified leaderboard, and integrates with Kaspa Finance for DEX deployments. The project aims to democratize memecoin creation and foster a vibrant Kaspa ecosystem.

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
- **Gemmy Zeroday Memification Engine**: An AI-powered trend discovery system operating in Creative, Trending Memes (multi-source cultural trend detection), and Kaspa Tech modes. It uses OpenRouter API with auto-failover, parallel processing, source-aware fallback scoring, and a 12-hour rolling PostgreSQL cache.
- **AI Token Image Generation**: A two-stage AI pipeline uses OpenRouter Llama 3.1 70B for prompt enhancement and Replicate FLUX.1 Schnell for 1024x1024 WebP image generation.

### Core Features
- **PRO Token Airdrop System**: Manages airdrops with a 5% per day vesting schedule, supporting various distribution types (Raffle, Top Contributors, Active Chatters, Token Holders, Early Supporters).
- **Anti-Bot System (GEM System)**: An optional premium feature for PRO tokens using time-based KAS fee decay to prevent bot sniping. Fees are sent to the Airdrop Treasury.
- **Token-Specific Community Points System**: Allows PRO token creators to configure and track points for engagement.
- **Multi-Wallet Linking System**: Securely links multiple wallets via challenge-response authentication.
- **Wallet Connection System**: A modal-based system supporting Kastle, KasWare, and MetaMask using challenge-response authentication.
- **Enhanced Marketplace Search**: Provides comprehensive search across token name, symbol, contract address, and creator information with real-time, case-insensitive matching.

## Smart Contract Architecture
The core contracts (`BondingCurvePool.sol`, `TokenFactory.sol`, `GraduationController.sol`) manage token creation, bonding curve mechanics, creator fee claims, anti-bot measures (wallet cap), and a two-step graduation process for transitioning tokens to the Kaspa Finance DEX. An off-chain backend service calculates auto-slippage for optimized trades.

## Database Schema
The Token model includes blockchain integration fields such as `creator_fees_accumulated`, `deployment_block_number`, `nft_position_id`, and `liquidity_pool_address`. New models like `TradeEvent` and `AntiBotFeeTracker` are introduced to store blockchain trade events and anti-bot fee distributions, with extensive indexing for efficient querying.

## Design Patterns
The project adheres to an MVC pattern, separating templates (views), Flask routes (controllers), and models.

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
- **Kasplex zkEVM L2**: EVM-compatible Layer 2 on Kaspa.
- **Kaspa Finance DEX**: Target DEX for token graduation and liquidity pools (Uniswap V3 architecture).
- **Smart Contract Stack**: Solidity ^0.8.20, Hardhat, OpenZeppelin.

## External Services
- **Telegram**: Community engagement.
- **Twitter/X**: Social media.
- **Kaspa Finance**: Automatic DEX deployment.
- **OpenRouter API**: For Gemmy AI, trend analysis, and image prompt enhancement (Meta Llama 3.1 70B).
- **Replicate API**: For AI-powered token image generation (FLUX.1 Schnell).
- **4chan /biz/**: Real-time meme trend scraping.
- **Reddit CryptoMoonShots**: Community-validated meme trends.
- **Pinata**: IPFS pinning service for permanent image storage.