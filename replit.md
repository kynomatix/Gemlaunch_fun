# Overview
gemlaunch.fun is a web platform for creating and launching memecoins on the Kaspa blockchain. It offers a no-code solution with an emphasis on fair launch mechanisms and community-driven tokens, leveraging Kaspa's high-performance L1 capabilities. The platform includes an AI Assistant (Gemmy), a social layer, a gamified leaderboard, and integrates with Kaspa Finance for DEX deployments. Its purpose is to democratize memecoin creation and foster a vibrant Kaspa ecosystem with business potential in the growing memecoin market.

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
- **AI Multi-Category Token Classification**: Automatic token categorization using Llama 3.1 8B via OpenRouter. Each token can have up to 3 categories from: Animals, Holidays, Tech, Finance, PopCulture, Food, Sports, Nature, Abstract, Community. Categories are stored as JSON arrays. Finance category is highly restrictive (only actual financial products like vaults/DeFi).

### Core Features
- **Anti-Bot System (GEM System)**: An optional premium feature for PRO tokens using time-based KAS fee decay to prevent bot sniping.
- **Token-Specific Community Points System**: Allows PRO token creators to configure and track engagement points. **CRITICAL**: Token creators are excluded from earning points in their own token's leaderboard (enforced in both `event_indexer.py` and `engagement_calculator.py`).
- **Multi-Wallet Linking System**: Securely links multiple wallets via challenge-response authentication.
- **Wallet Connection System**: A modal-based system supporting Kastle, KasWare, and MetaMask using challenge-response authentication.
- **Enhanced Marketplace Search**: Provides comprehensive search across token name, symbol, contract address, and creator information.
- **Deployment Confirmation System**: A 6-layer security verification system for confirming token deployments.
- **X/Twitter Verification System**: OAuth 2.0-based social verification system that authenticates user identities and prevents impersonation.
- **KASPERS NFT Holder Recognition**: Social accolade system recognizes KASPERS NFT holders (KRC721) with a special achievement badge and bonus GEM points.
- **Graduation System**: Automated token lifecycle management transitioning tokens from bonding curve to DEX at a $50 market cap threshold, with a 4-state lifecycle (active → initiating → completing → graduated). It includes critical fixes for `graduationController` initialization and ensures correct `msg.sender` for snapshot integrity. A monitor service checks eligibility every 60 seconds.
- **PRO Token Vesting System**: Fully implemented with atomic on-chain deployment. It uses a creator custody model for airdrop, marketing, and team vesting, managed by `TokenFactory V2` and `VestingDeployer V2` smart contracts. Event-based vesting address extraction is used, and contract size optimization is achieved via a `VestingDeployer` helper contract. **CRITICAL**: All vesting contracts (AirdropVesting, LinearVesting, CliffVesting) use `getWithdrawableAmount()` to check available balance, not `releasable()`.
- **Airdrop Distribution System**: PRO token creators can distribute airdrops to various recipient categories (top_by_points, active_chatters, token_holders, early_supporters, diamond_holders). The system automatically checks creator's wallet balance plus unlocked vesting tokens, bundles multi-step transactions (vesting withdrawal if needed, approval, batch transfer), and protects all endpoints with CSRF tokens.
- **Poll Voting System with Token Burning**: Token creators can create polls with customizable vote costs requiring users to burn tokens. The system uses a secure transaction flow where users submit a MetaMask transaction to burn tokens to the burn address (0x000000000000000000000000000000000000dEaD), then the backend verifies: (1) Transfer event is from the correct token contract, (2) Burned amount exactly matches the vote_cost, (3) burn_tx_hash is unique and not previously used. The PollVote model stores burn_tx_hash with a unique constraint to prevent transaction replay attacks.

## Smart Contract Architecture
Core contracts (`BondingCurvePool.sol`, `TokenFactory.sol`, `GraduationController.sol`) manage token creation, bonding curve mechanics, creator fee claims, anti-bot measures, and a two-step graduation process for transitioning tokens to the Kaspa Finance DEX. The `BondingCurvePool` acts as the ERC20 token itself.

### Active Contracts (Kasplex Testnet)
**CRITICAL: All contract addresses are managed in `contracts/deployed_addresses.json`**
**ALWAYS follow `contracts/DEPLOYMENT_GUIDE.md` when deploying new contracts**

Current working contracts (Oct 28, 2025 - V12 COMPLETE FIX):
- **TokenFactory V11**: `0x427B039bc381911a40AC25Fc50AB9e6f5633A5B1` (Points to GraduationController V12)
- **GraduationController V12**: `0xD7B75104f005DFC9dE004fdb97399444752d66D3` (COMPLETE STF FIX: IERC721Receiver + unsafe burn transfer)
- **AirdropDistributor**: `0x86b83FE03cDa7456980364c929BB17CFA67E8495`

Deprecated contracts (DO NOT USE):
- **GraduationController V11**: `0xd0Ca76Dc29714Ef316a6aacCAC8837c3119439e0` (PARTIAL FIX: Has IERC721Receiver but uses safeTransferFrom for burn)
- **GraduationController V10**: `0x7384F95729Ff5c2B2BFe4Cc101139a13A85a66e9` (Wrong fix - approval ordering)
- **GraduationController V9**: `0xaC022Ab0860D3D7D5A8738cd6BF58090117CC7f6` (Pre-fix version)
- **GraduationController V8**: `0x22F3cC689401462B6ceb85EF544E86FE27ad178f` (Points to TF V10, wrong factory)
- **TokenFactory V10**: `0xCD8e8F442E187B811130F8924B91a8F3445Ffb21` (Points to GC V7 with wrong oracle)
- **GraduationController V7**: `0xeb753f81F9beD4B6ea27381476a20d71ae496Cd1` (WRONG ORACLE: Used treasury address)
- **TokenFactory V9**: `0xB4D21bD000275F58A7180502Af5215fc4adE9984` (STF error persisted)
- **TokenFactory V8**: `0x1b641c1dF9eEbaf5bd8B5251e24794Cab01D9071` (References GC V6 with STF error)
- **GraduationController V6**: `0xBbfdF7341aaF104D259876972844EBF9795b9C4C` (STF error on safeTransferFrom)
- **GraduationController V5**: `0xbC90b2a362Af9fdF2067EDeE5F166CF88fbb39Ac` (Wrong DEX addresses)

Legacy tokens (50 tokens with graduation_disabled - ALL tokens created before V12 deployment):
- **Locked KAS**: ~1,812 KAS stuck in failed graduation contracts (recoverable via Treasury wallet)
  - $MLEAF: 891 KAS locked in GC V6
  - $CHIM: 920.7 KAS locked in GC V6
- **$KYR**: Created with TF V11 pointing to GC V11 (partial fix - graduation_disabled)
- **$CYBR**: Created by TF V11 but has GC V8 embedded (graduation_disabled)
- **IMPORTANT**: Only NEW tokens created after V12 deployment can graduate successfully

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

**Chart Timezone & Display**: Trading charts display times in the user's local timezone for improved UX. Backend stores all timestamps in UTC and sends them with explicit `+00:00` timezone suffix (via `timestamp.replace(tzinfo=timezone.utc)` in Python). Frontend uses JavaScript's automatic timezone conversion to display local times while maintaining alignment accuracy - trade markers use Unix timestamps (timezone-agnostic) which align correctly with candle buckets regardless of display timezone. This architecture ensures perfect marker alignment across all timezones while providing an intuitive local time display.

## Design Patterns
The project adheres to an MVC pattern.

## Performance Optimizations
Includes hardware-accelerated CSS animations, efficient asset caching, and JavaScript-enhanced smooth scrolling.

## Blockchain Integration Foundation
The system includes a Web3 Service Layer for RPC connection to **Kasplex zkEVM L2 (Testnet)**, an Oracle Wallet for automated operations, and contract loading. Transaction utilities handle gas estimation, signing, relay, and status polling, with POA middleware for Kasplex compatibility.

**⚠️ IMPORTANT: Kasplex L2 vs Kaspa L1**
- **This platform uses Kasplex zkEVM L2** (EVM-compatible Layer 2 on Kaspa)
- **NOT native Kaspa L1** (DAG-based blockchain using wRPC protocol)
- Uses standard Ethereum JSON-RPC, not Kaspa's native wRPC

**CRITICAL: Kasplex Testnet Chain ID is 167012 (0x28c64)** - All MetaMask transactions must use this chainId or they will fail to broadcast.

**CRITICAL: MetaMask Gas Price Bug on Kasplex** - MetaMask's gas estimation is broken on Kasplex Testnet. It interprets the RPC's gasPrice response of 2001 Gwei as 2001 wei (1 billion times too low), causing transactions to sign but never broadcast. All MetaMask transactions must explicitly include `gasPrice: hex(w3.eth.gas_price)` to override MetaMask's broken estimation.

**RPC Endpoint:** `https://rpc.kasplextest.xyz` (HTTP/HTTPS) - WebSocket availability unverified, see `WEBSOCKET_IMPLEMENTATION_PLAN.md` Phase 0.

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