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
- **web3.py**: Python library for Ethereum/EVM blockchain interaction (v7.13.0).
- **eth-account**: Ethereum account management for transaction signing.

# Phase 2 Integration Progress

## Blockchain Integration Foundation (COMPLETE ✅)
**Date Completed:** October 11, 2025

### Web3 Service Layer (Tasks 2.1.1-2.1.6)
- ✅ **RPC Connection**: Connected to Kasplex Testnet (https://rpc.kasplextest.xyz, Chain ID: 167012)
- ✅ **Oracle Wallet**: Derived secondary wallet from DEPLOYER_PRIVATE_KEY using keccak256("GEMLAUNCH_SECONDARY_WALLET" + deployer_key)
  - Oracle Address: 0x5f837F62744D4d80Fc79C3A5346B4A228956914E
- ✅ **Contract Loading**: ABIs loaded from Hardhat artifacts
  - TokenFactory: 0x348640F6e87a0226e8E4CdB5e068282B5D0b2F60
  - GraduationController: 0x9416D5a5D61ec70C18D1FE1039f8026E29b4820e
  - BondingCurvePool: Dynamic loading for each token
- ✅ **Transaction Utilities**: Gas estimation (20% buffer), signing, relay, status polling
- ✅ **POA Middleware**: ExtraDataToPOAMiddleware for Kasplex compatibility

### Contract Interaction Layer (Tasks 2.2.1-2.2.3)
- ✅ **TokenFactory Interactions**:
  - create_token_tx_data() - Build unsigned tx for user to sign
- ✅ **BondingCurvePool Interactions**:
  - get_buy_quote(), get_sell_quote() - Price quotes
  - get_auto_slippage() - Auto-calculated slippage protection
  - buy_tokens_tx_data(), sell_tokens_tx_data() - Build unsigned txs
  - get_creator_claimable(), withdraw_creator_fees_tx_data() - Fee management
- ✅ **GraduationController Interactions**:
  - initiate_graduation_oracle() - Oracle signs and relays
  - complete_graduation_oracle() - Oracle signs and relays

### Database Schema (Tasks 2.5.1-2.5.3)
- ✅ **Token Model Updates** (4 new fields):
  - creator_fees_accumulated (Numeric 20,8) - Track claimable creator fees
  - deployment_block_number (Integer) - Blockchain block number
  - nft_position_id (Integer) - Kaspa Finance NFT position after graduation
  - liquidity_pool_address (String 128) - Kaspa Finance pool address
- ✅ **TradeEvent Model** (13 fields):
  - Stores blockchain trade events from BondingCurvePool
  - Indexes: token_id, user_wallet_address, tx_hash (unique), block_number
- ✅ **AntiBotFeeTracker Model** (9 fields):
  - Tracks 70/30 anti-bot fee split (Airdrop Treasury / Platform Dev)
  - Relationships to Token and TradeEvent
- ✅ **Migration Complete**: All columns added, application running successfully

### Transaction Flow Architecture
**USER Transactions** (Frontend → User Wallet → Blockchain):
- Users sign transactions in their wallet
- Backend builds unsigned tx dicts with gas estimates
- Frontend sends signed tx to backend for relay

**ORACLE Transactions** (Backend → Blockchain):
- Backend signs with oracle_account (0x5f83...914E)
- Used for graduation triggers and automated operations
- No user interaction required

### Trading & Fee Management (Tasks 2.6-2.7) (COMPLETE ✅)
- ✅ **Quote Endpoints**: GET /api/trade/quote-buy, quote-sell with auto-slippage
- ✅ **Trade Endpoints**: POST /api/trade/buy, sell with unsigned tx building
- ✅ **Creator Fee Claiming**: POST /api/token/<address>/claim-creator-fees
- ✅ **Platform Fee Distribution**: POST /api/admin/distribute-platform-fees (4-way split: 40% dev/30% buyback/15% Kaspa/15% community)
- ✅ **Fee Statistics**: GET /api/token/<address>/fee-stats with hybrid DB/blockchain tracking

### Transaction Monitoring (Task 2.8) (COMPLETE ✅)
- ✅ **APScheduler Background Polling**: Checks pending txs every 10 seconds
- ✅ **SSE Streaming**: GET /api/tx/<hash>/stream with 2-second updates, 5-minute timeout
- ✅ **Relay Integration**: All relay endpoints enqueue txs for monitoring
- ✅ **Graceful Shutdown**: Handles worker reloads without orphaned jobs
- ✅ **Event Indexer Sanity Check**: Warns if >100 blocks behind on startup (simple gap detection)

### Post-Graduation Features (Task 2.9) (COMPLETE ✅)
- ✅ **DEX Pool Data Endpoint**: GET /api/token/<address>/dex-pool
  - Returns pool_address, nft_position_id, dex_url for graduated tokens
  - Returns is_graduated: false for non-graduated tokens
  - Placeholders for liquidity/volume_24h (future enhancement)
- ✅ **DEX Redirect Endpoint**: GET /token/<address>/trade
  - Redirects to https://kaspa.finance/pool/{pool_address} for graduated tokens
  - Redirects to token detail with flash message for non-graduated tokens
- ✅ **Flexible Address Validation**: Accepts EVM (0x...) and Kaspa-native formats
  - Normalization via lowercase + case-insensitive DB lookup
  - No hardcoded format restrictions (0x prefix, length checks)
  - Database-driven validation (404 for unknown addresses)

### Gas & Network Validation (Task 2.10) (COMPLETE ✅)
- ✅ **Gas Estimation Endpoint**: POST /api/gas/estimate
  - Returns gas_estimate, gas_with_buffer (+20%), gas_price, estimated_cost_kas
  - Placeholder for estimated_cost_usd (future KAS/USD integration)
- ✅ **Network Status Endpoint**: GET /api/network/status
  - Returns connected, chain_id, block_number, gas_price_gwei, network_name
- ✅ **Chain ID Validation**: validate_chain_id() middleware
  - Verifies Chain ID 167012 (Kasplex Testnet) on critical endpoints
  - Applied to buy, sell, claim-creator-fees endpoints
- ✅ **RPC Fallback Mechanism**: get_web3_with_fallback()
  - Web3Service now uses fallback-enabled initialization
  - Tries RPC endpoints in order with POA middleware
  - Logging for each RPC attempt, raises ConnectionError if all fail
  - Ready for multiple fallback RPCs when available

### Image Storage & Metadata (Task 2.11) (COMPLETE ✅)
**Date Completed:** October 11, 2025

- ✅ **PinataService**: IPFS upload service for images and JSON metadata
  - upload_file() - Uploads images to IPFS via Pinata
  - upload_json() - Uploads JSON metadata to IPFS
  - get_ipfs_url() - Generates public gateway URLs
- ✅ **Database Schema**: 4 new IPFS fields added to Token model
  - ipfs_image_hash (VARCHAR 128) - IPFS hash of token image
  - ipfs_metadata_hash (VARCHAR 128) - IPFS hash of token metadata
  - ipfs_image_url (VARCHAR 256) - Full IPFS URL for image
  - ipfs_metadata_url (VARCHAR 256) - Full IPFS URL for metadata
- ✅ **Upload Image Endpoint**: POST /api/token/<address>/upload-image
  - Validates file types (PNG, JPG, JPEG, WebP)
  - Uploads to IPFS, stores hash/URL in database
  - Automatic temp file cleanup
- ✅ **Generate Metadata Endpoint**: POST /api/token/<address>/generate-metadata
  - ERC-721/ERC-1155 standard metadata structure
  - Requires image to be uploaded first
  - Uploads JSON metadata to IPFS
  - Includes creator, supply, graduation status attributes
- ✅ **Get Metadata Endpoint**: GET /api/token/<address>/metadata
  - Returns IPFS URL if metadata exists
  - Generates on-the-fly metadata as fallback
- ✅ **Environment Variables**: PINATA_JWT (Bearer token authentication)

## Phase 2 Status: COMPLETE ✅
**Total Tasks:** 12/12 completed
**Completion Date:** October 11, 2025

All blockchain integration features are implemented, architect-approved, and production-ready:
- ✅ Web3 Service Layer & Contract Interactions
- ✅ Database Schema (8 blockchain fields + 3 new models: TradeEvent, AntiBotFeeTracker, ReserveDistribution)
- ✅ Trading & Fee Management APIs
- ✅ Transaction Monitoring (APScheduler + SSE streaming)
- ✅ Post-Graduation Features (DEX integration)
- ✅ Gas & Network Validation (RPC fallback active)
- ✅ Image Storage & Metadata (IPFS via Pinata)
- ✅ Reserve Token Distribution (PRO tokens - team/marketing/airdrop allocations)