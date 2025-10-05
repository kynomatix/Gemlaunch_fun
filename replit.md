# Overview
gemlaunch.fun is a web platform designed to facilitate the creation and launch of memecoins on the Kaspa blockchain. The project aims to democratize memecoin creation through a no-code solution, emphasizing fair launch mechanisms and community-driven tokens. It leverages Kaspa's high-performance L1 capabilities for rapid transaction processing. Key features include an AI Assistant (Gemmy), a social layer with $cashtags, and a gamified leaderboard. The platform supports Kaspa's ecosystem by integrating miner-friendly economics and Kaspa Finance for automatic DEX deployments. It also includes a comprehensive achievement system to reward user engagement.

# User Preferences
Preferred communication style: Simple, everyday language.

## Design Preferences
- **Button Style**: Sleek rectangular buttons with rounded corners (border-radius: 10px). NEVER use oval/pill-shaped buttons (border-radius: 25px+)

# System Architecture

## Frontend Architecture
The application uses a server-side rendered approach with Flask and Jinja2, featuring a custom CSS framework (CSS Grid, Flexbox, animations) and vanilla JavaScript for interactivity. It includes a particles.js integration and a GitBook-style tabbed documentation system. The design is responsive and mobile-first.

## Backend Architecture
Built with Flask, the backend follows a minimal, route-based architecture with environment-based configuration and Python logging. It includes a comprehensive achievement system tracking user activities, secure API endpoints, and XSS protection.

### Interactive Gemmy Chat
Gemmy's AI token suggestions are interactive; clicking an option auto-fills the token creation form with extracted name, symbol, and description, adapting to Simple or Advanced mode.

### Gemmy Zeroday Memification Engine
An AI-powered trend discovery system operates in three modes: Creative, Trending Memes (multi-source cultural trend detection from platforms like Know Your Meme, 4chan, Reddit CryptoMoonShots, scored by crypto-adoptability criteria), and Kaspa Tech (memification of Kaspa-native concepts). Technical implementation uses OpenRouter API with auto-failover, parallel processing for rapid analysis (6-8 seconds), source-aware fallback scoring, and a 12-hour rolling PostgreSQL cache.

### AI Token Image Generation
A two-stage AI pipeline generates token images. Stage 1 uses OpenRouter Llama 3.1 70B for prompt enhancement with Kaspa-specific styling. Stage 2 uses Replicate FLUX.1 Schnell to generate 1024x1024 WebP images. Users can generate, preview, and regenerate images within the token creation form via a Flask API endpoint.

### PRO Token Airdrop System
Features a comprehensive airdrop management system with a 5% per day vesting schedule (20-day full unlock). Supports various distribution types: Random Raffle, Top Contributors, Active Chatters, Token Holders, and Early Supporters. It includes a database schema for campaigns and recipients, with API endpoints for availability and creation, and a dynamic modal UI.

### Token-Specific Community Points System
Each PRO token has its own community points system to reward engagement. The `TokenEngagement` model tracks per-user, per-token metrics (points, messages, trades, polls, holdings). Points are distributed for chat, trading, poll, and spotlight activities, configurable by token creators. Integrates with token-specific leaderboards and will gate future features.

### Multi-Wallet Linking System
Users can link multiple wallets to their primary account using a secure challenge-response authentication with cryptographic signature verification. The system prevents whale wallet theft, replay attacks, and cross-profile hijacking, and provides a clear user experience for managing linked wallets.

### Claim Ownership System
Allows users to prove ownership and merge accounts if they attempt to link a wallet already primary for another account. A merge strategy consolidates data into the claimant's account, archiving the legacy account. This process involves a challenge-response verification, an account merge service handling data transfer (achievements, engagements, linked wallets, activity records), and robust security features like rate limiting and audit logging.

### Wallet Connection System
A modal-based system supports Kastle, KasWare, and MetaMask. It uses challenge-response authentication, `WalletManager` module for provider abstraction, and handles MetaMask account switching with auto-disconnect on change. API endpoints manage nonce generation, verification, session status, and disconnection. UI conditionally renders access based on wallet connection status.

## Design Patterns
Adheres to an MVC pattern, separating templates (views), Flask routes (controllers), and models. Utilizes efficient static asset organization and a component-based CSS approach.

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
- **Kaspa Blockchain**: Target L1 for memecoin deployment.

## External Services
- **Telegram**: Community engagement.
- **Twitter/X**: Social media.
- **Kaspa Finance**: Automatic DEX deployment.
- **presale.gemlaunch.fun**: External presale portal.
- **OpenRouter API**: For Gemmy AI, trend analysis, and image prompt enhancement (Meta Llama 3.1 70B, auto-failover).
- **Replicate API**: For AI-powered token image generation (FLUX.1 Schnell).
- **4chan /biz/**: Real-time meme trend scraping.
- **Reddit CryptoMoonShots**: Community-validated meme trends.