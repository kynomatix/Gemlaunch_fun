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
- **X/Twitter Verification System**: OAuth 2.0-based social verification system that authenticates user identities, prevents impersonation, and displays verified badges across the platform (profiles, chat messages, token pages, leaderboards). Enforces one-to-one mapping between X accounts and wallet addresses with CSRF/state validation.
- **KASPERS NFT Holder Recognition**: Social accolade system recognizes KASPERS NFT holders (KRC721) with special achievement badge and 500 bonus GEM points. Uses ERC721 balanceOf queries to verify ownership on-chain.
- **Graduation System**: Automated token lifecycle management transitioning tokens from bonding curve to DEX at $50 market cap threshold.
  - **Status Flow**: active → initiating → completing → graduated (4-state lifecycle per KASPA_FINANCE_DEX_INTEGRATION_PLAN.md)
  - **Critical Fix (Oct 22, 2025)**: Tokens now correctly initialize with `graduation_status = 'active'` on deployment (app.py line 6578)
  - **V3 Upgrade (Oct 26, 2025)**: TokenFactory updated to use GraduationController V3 with all 11 critical fixes + CORRECT Kaspa Finance addresses
    - GraduationController V3 (FINAL): 0x628EC1FF659e2935d531cec5aC489baCf06898aA (Block 9129036) ✅ ALL ADDRESSES CORRECT
    - Transaction: 7d4b267cb5f2ad0726c1e30ab964236be2bcbff2849809737aa6013ab27cb50b
    - Correct Kaspa Finance: Factory 0x1b72D7165..., PositionManager 0x4E25637cF..., WKAS 0xD18FCd278...
    - Correct TokenFactory: 0xf8F05F8c88Df82b3aA135b9D434553E064b56704 (V3)
    - All new tokens created after Oct 26, 2025 will graduate to real Kaspa Finance DEX
    - Legacy tokens + NPC (used wrong DEX/TF) marked as graduation_disabled
    - Previous V3: 0xBCF73222 (wrong TF), 0xD02b169B (wrong DEX), 0x2b68832 (bytecode)
  - **Monitor Service**: Background job checks eligible tokens every 60 seconds for graduation eligibility
  - **Oracle Integration**: Uses web3_service.oracle_account for automated graduation transactions

### PRO Token Vesting System
✅ **STATUS: Fully implemented - Atomic on-chain deployment (V2 - October 2025)**
- **Design:** Creator custody model - creators control all allocations
  - Airdrop vesting → Creator's wallet (5% daily unlock via AirdropVesting) ⭐ CHANGED
  - Marketing vesting → Creator's wallet (12-month linear via LinearVesting)
  - Team vesting → Creator's wallet (6mo cliff + 18mo vest via CliffVesting)
- **Smart Contracts (V2):**
  - TokenFactory V2 (0x39003ab4e8ad700F59bcfA082F73e68bc0477fDc) - graduation fix deployed Oct 2025
  - VestingDeployer V2 (0x319F9D08A9c1167770Fe037cb58e5097e287B9e7) - auto-deployed with TokenFactory
  - AirdropDistributor (0x86b83FE03cDa7456980364c929BB17CFA67E8495) - batch airdrop helper
  - Atomic deployment: user pays once, all contracts deployed in single transaction
  - Previous V1: 0x2DDb083fCd62D27E9eE1F557B53140bD61F3009D (deprecated - platform-managed airdrops)
- **Architecture:** Event-based vesting address extraction
  - TokenFactory emits VestingDeployed event with all three vesting contract addresses
  - Backend extracts addresses from event logs and saves to database
  - No async deployment, no timeout issues, no oracle wallet subsidy
- **Contract Size Optimization (EVM Constraint Workaround):**
  - VestingDeployer helper contract pattern (see VESTING_IMPLEMENTATION_NOTES.md)
  - Spec calls for direct deployment but exceeds 24KB limit
  - VestingDeployer functionally identical to spec, just delegated for size
  - TokenFactory: 19KB, VestingDeployer: 5KB
  - Zero allocations supported: returns address(0) for 0% allocations (e.g., 100/0/0 or 0/100/0)
  - User experience unchanged: atomic deployment, single transaction, user pays once
- **Frontend Portal:** Vesting status display on token detail pages with unlock schedules
- **Security:** All critical issues from spec audits resolved, matches PRO_TOKEN_VESTING_SPECIFICATION_V2.md exactly

## Smart Contract Architecture
Core contracts (`BondingCurvePool.sol`, `TokenFactory.sol`, `GraduationController.sol`) manage token creation, bonding curve mechanics, creator fee claims, anti-bot measures, and a two-step graduation process for transitioning tokens to the Kaspa Finance DEX. The BondingCurvePool acts as the ERC20 token itself.

### Active Contracts (Kasplex Testnet - October 2025)
- **TokenFactory V3**: 0xf8F05F8c88Df82b3aA135b9D434553E064b56704 (Oct 26, 2025 - Links to GC V3 FINAL)
- **GraduationController V3 (FINAL)**: 0x628EC1FF659e2935d531cec5aC489baCf06898aA (Oct 26, 2025 - ALL addresses correct)
- **VestingDeployer V2**: 0x319F9D08A9c1167770Fe037cb58e5097e287B9e7
- **AirdropDistributor**: 0x86b83FE03cDa7456980364c929BB17CFA67E8495
- **Deprecated**: 
  - GraduationController V3: 0xBCF73222 (wrong TokenFactory), 0xD02b169B (wrong DEX), 0x2b68832 (bytecode)
  - TokenFactory V2: 0x39003ab4e8ad700F59bcfA082F73e68bc0477fDc - OLD BondingCurvePool bytecode
  - GraduationController V2: 0x147e3ecbe189bb301175001706ff1f44df33b3ab - DO NOT USE

## Database Schema
The `Token` model includes blockchain integration fields. New models include `TradeEvent` and `AntiBotFeeTracker` for storing blockchain trade events and anti-bot fee distributions.

### Token Visibility System
- **is_visible** field: Boolean flag to hide test/spam tokens from marketplace
- Hidden tokens remain in database but are filtered from public views
- Use case: Remove test tokens like GRAD655 without deleting historical data

### Legacy Token Management (Oct 24, 2025)
- **graduation_disabled** field: Boolean flag to disable graduation attempts for legacy tokens
- **Purpose**: Tokens deployed before V3 GraduationController (Oct 24, 2025) use incompatible contracts
- **Behavior**: Legacy tokens remain visible in marketplace but graduation system skips them
- **Migration**: All 30 tokens created before Oct 24, 2025 marked as `graduation_disabled=True`
  - 29 V1 tokens (created before Oct 23, 2025)
  - KRABBY (created with V2, marked disabled to prevent system lockup)
- **Active V3 tokens**: All tokens created after Oct 24, 2025 will use V3 graduation with all fixes

### Data Architecture Strategy
**Current (Hybrid - Optimal Architecture):** 
- ✅ **Recent trading data**: Blockscout GraphQL API (real-time, last ~8 transfers, 10s cache)
- ✅ **Holder verification**: Web3 direct queries via balanceOf() (no database)
- ✅ **Chart historical data**: Live blockchain reserves + TradeEvent database replay
- ✅ **Quote endpoints**: Real-time blockchain virtualKasReserve/virtualTokenReserve queries
- ⚠️ **Portfolio aggregation**: Temporarily disabled (TODO: blockchain-backed implementation)
- 📦 **Database retained for**: User profiles, token metadata, trade history (charts), social features

**Real-Time Reserve Integration (Oct 2025):**
- **Chart endpoint**: Queries current on-chain reserves via `get_virtual_kas_reserve()` and `get_virtual_token_reserve()`, then works backwards through trades_in_window to calculate starting state
- **Buy/Sell quotes**: Query live blockchain reserves for accurate price impact calculations instead of stale database values
- **Market cap display**: Shows correct bonding curve TVL ($95.88 vs previous incorrect $297) based on real virtualKasReserve
- **Benefits**: Eliminates drift between database cache and actual on-chain state, ensures price quotes match blockchain reality

**Why Hybrid Architecture:** See `GRAPHQL_MIGRATION_STATUS.md` for full analysis:
- **GraphQL Limitation**: Blockscout API complexity limits prevent fetching complete trade history (max ~8 transfers per query, no effective pagination)
- **Chart Requirement**: TradingView charts require replaying ALL trades from deployment to calculate accurate bonding curve reserve changes
- **Event Indexer**: Still running to populate TradeEvent table for chart data (critical feature, cannot be removed)
- **API Endpoint**: `https://explorer.testnet.kasplextest.xyz/api/v1/graphql` (10s caching via Flask-Caching)
- **Benefits**: Real-time current state (blockchain + GraphQL) + complete historical data (database) = best of both worlds

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