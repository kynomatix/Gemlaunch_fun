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
- **Deployment Confirmation System**: A 6-layer security verification system for confirming token deployments.
- **X/Twitter Verification System**: OAuth 2.0-based social verification system that authenticates user identities and prevents impersonation.
- **KASPERS NFT Holder Recognition**: Social accolade system recognizes KASPERS NFT holders (KRC721) with a special achievement badge and bonus GEM points.
- **Graduation System**: Automated token lifecycle management transitioning tokens from bonding curve to DEX at a $50 market cap threshold, with a 4-state lifecycle (active → initiating → completing → graduated). It includes critical fixes for `graduationController` initialization and ensures correct `msg.sender` for snapshot integrity. A monitor service checks eligibility every 60 seconds.
- **PRO Token Vesting System**: Fully implemented with atomic on-chain deployment. It uses a creator custody model for airdrop, marketing, and team vesting, managed by `TokenFactory V2` and `VestingDeployer V2` smart contracts. Event-based vesting address extraction is used, and contract size optimization is achieved via a `VestingDeployer` helper contract.

## Smart Contract Architecture
Core contracts (`BondingCurvePool.sol`, `TokenFactory.sol`, `GraduationController.sol`) manage token creation, bonding curve mechanics, creator fee claims, anti-bot measures, and a two-step graduation process for transitioning tokens to the Kaspa Finance DEX. The `BondingCurvePool` acts as the ERC20 token itself.

### Active Contracts (Kasplex Testnet)
**CRITICAL: All contract addresses are managed in `contracts/deployed_addresses.json`**
**ALWAYS follow `contracts/DEPLOYMENT_GUIDE.md` when deploying new contracts**

Current working contracts (Oct 27, 2025 - FINAL CONFIGURATION):
- **TokenFactory V11**: `0x427B039bc381911a40AC25Fc50AB9e6f5633A5B1` (Points to GraduationController V9)
- **GraduationController V9**: `0xaC022Ab0860D3D7D5A8738cd6BF58090117CC7f6` (Configured with TokenFactory V11)
- **AirdropDistributor**: `0x86b83FE03cDa7456980364c929BB17CFA67E8495`

Deprecated contracts (DO NOT USE):
- **GraduationController V8**: `0x22F3cC689401462B6ceb85EF544E86FE27ad178f` (Points to TF V10, wrong factory)
- **TokenFactory V10**: `0xCD8e8F442E187B811130F8924B91a8F3445Ffb21` (Points to GC V7 with wrong oracle)
- **GraduationController V7**: `0xeb753f81F9beD4B6ea27381476a20d71ae496Cd1` (WRONG ORACLE: Used treasury address)
- **TokenFactory V9**: `0xB4D21bD000275F58A7180502Af5215fc4adE9984` (STF error persisted)
- **TokenFactory V8**: `0x1b641c1dF9eEbaf5bd8B5251e24794Cab01D9071` (References GC V6 with STF error)
- **GraduationController V6**: `0xBbfdF7341aaF104D259876972844EBF9795b9C4C` (STF error on safeTransferFrom)
- **GraduationController V5**: `0xbC90b2a362Af9fdF2067EDeE5F166CF88fbb39Ac` (Wrong DEX addresses)

Legacy tokens (49 tokens with graduation_disabled - ALL tokens created before final V11/V9 config):
- **Locked KAS**: ~1,812 KAS stuck in failed graduation contracts (recoverable via Treasury wallet)
  - $MLEAF: 891 KAS locked in GC V6
  - $CHIM: 920.7 KAS locked in GC V6
- **$CYBR**: Created by TF V11 but has GC V8 embedded (graduation_disabled)
- **IMPORTANT**: Only NEW tokens created after V11/V9 config can graduate successfully

### Contract Deployment Protocol
1. **NEVER deploy contracts without checking the deployment guide first**
2. **ALWAYS update `contracts/deployed_addresses.json` after deployment**
3. **ALWAYS run validation script after deploying TokenFactory**
4. **ALWAYS update `services/web3_service.py` constants to match registry**
5. **Test with a new token** before considering deployment successful

## Database Schema
The `Token` model includes blockchain integration fields, `TradeEvent` for trade history, and `AntiBotFeeTracker` for fee distributions. `is_visible` and `graduation_disabled` flags manage token visibility and graduation eligibility for legacy tokens.

### Data Architecture Strategy
A hybrid approach is used:
- **Real-time data**: Blockscout GraphQL API for recent trading data and Web3 direct queries for holder verification.
- **Historical data**: `TradeEvent` database replay for chart data and blockchain reserves for accurate quotes.
- **Database retained for**: User profiles, token metadata, trade history (charts), and social features.
This approach ensures real-time accuracy while providing comprehensive historical data for charting.

## Design Patterns
The project adheres to an MVC pattern.

## Performance Optimizations
Includes hardware-accelerated CSS animations, efficient asset caching, and JavaScript-enhanced smooth scrolling.

## Blockchain Integration Foundation
The system includes a Web3 Service Layer for RPC connection to Kasplex zkEVM L2 (Testnet), an Oracle Wallet for automated operations, and contract loading. Transaction utilities handle gas estimation, signing, relay, and status polling, with POA middleware for Kasplex compatibility.

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