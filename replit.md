# Overview

gemlaunch.fun is a web platform designed to facilitate the creation and launch of memecoins on the Kaspa blockchain. The project aims to democratize memecoin creation through a no-code solution, emphasizing fair launch mechanisms and community-driven tokens. It leverages Kaspa's high-performance L1 capabilities for rapid transaction processing. The platform incorporates innovative features like an AI Assistant (Gemmy), a built-in social layer with $cashtags, and a gamified leaderboard. A key ambition is to support Kaspa's ecosystem by offering miner-friendly economics, where memecoin trading fees contribute to mining profitability, and integrating with Kaspa Finance for automatic DEX deployments. The project also includes a comprehensive achievement system to reward user engagement and activity.

# User Preferences

Preferred communication style: Simple, everyday language.

## Design Preferences
- **Button Style**: Sleek rectangular buttons with rounded corners (border-radius: 10px). NEVER use oval/pill-shaped buttons (border-radius: 25px+)

# System Architecture

## Frontend Architecture
The application utilizes a server-side rendered approach with Flask and Jinja2 templating. It features a custom CSS framework using modern design patterns (CSS Grid, Flexbox, animations), vanilla JavaScript for interactivity, and a particles.js integration for visual enhancements. The documentation system is a GitBook-style tabbed interface. The design emphasizes responsiveness and mobile-first principles.

## Backend Architecture
The backend is built with Flask, following a minimal application structure. It uses a simple route-based architecture, environment-based configuration for session management, and Python's built-in logging. A comprehensive achievement system is implemented with real database tracking, evaluating user activities (e.g., chat messages, poll participation, token creation, trades, holdings) and automatically awarding achievements and GEM points. Secure API endpoints are implemented for features like message deletion with proper ownership validation and XSS protection is applied across the chat system and UI.

### Interactive Gemmy Chat
Gemmy's AI responses are fully interactive - when Gemmy provides token suggestions, each individual option becomes clickable with a visual indicator (left border that highlights on hover). Clicking a suggestion automatically fills the token creation form with the extracted name, symbol, and description. The system intelligently parses each option to extract these details and populates the appropriate fields based on whether Simple or Advanced mode is active. Visual feedback confirms successful form filling.

### Gemmy Zeroday Memification Engine
The platform features an advanced AI-powered trend discovery system with three operational modes:
- **Creative Mode**: Traditional AI brainstorming for custom token ideas
- **Trending Memes Mode**: Multi-source cultural trend detection that finds NEW memes BEFORE they become coins:
  - **Know Your Meme**: Trending/new memes (pre-coin cultural moments)
  - **4chan culture boards** (/pol/, /tv/, /b/): Emerging mascots, catchphrases, and viral moments
  - **4chan /biz/** (legacy): Late-stage coin discussions
  - **Reddit CryptoMoonShots** (legacy): Community validation
  - AI-scored using 7 crypto-adoptability criteria: viral potential, cultural timing, community signal, crypto-native elements, mascot strength, moggability, cringe factor
- **Kaspa Tech Mode**: Memification of Kaspa-native technical concepts (GHOSTDAG, DAGKnight, BlockDAG, 10 BPS, phantom blocks)

Technical implementation uses advanced AI via OpenRouter API with auto-failover across multiple providers (Groq, Together.ai, Cerebras) for maximum reliability. **Parallel processing** scores up to 20 trends simultaneously using ThreadPoolExecutor, reducing analysis time from 60-80 seconds to 6-8 seconds. Source-aware fallback scoring ensures KnowYourMeme and culture board entries rank properly even without AI. A 12-hour rolling cache window stored in PostgreSQL optimizes costs (~$0.20/day maximum). On-demand scraping triggers when cache expires, with automatic cleanup of old entries after 24 hours. The system captures memes at their source (culture boards) before they become mainstream coins, providing true zero-day advantage.

### AI Token Image Generation
The platform features AI-powered token image generation with a two-stage pipeline:
- **Stage 1: Prompt Enhancement** - Uses OpenRouter Llama 3.1 70B to transform basic token information (name, symbol, description) into detailed image prompts with Kaspa-specific styling guidelines (teal/turquoise themes, simple illustrative art, minimalist design, thumbnail-optimized)
- **Stage 2: Image Generation** - Uses Replicate FLUX.1 Schnell to generate 1024x1024 WebP images in ~1 second at $0.003 per image
- **User Flow**: Users click "Generate with AI" button in token creation form, view generated image preview, and can regenerate or use the image for their token
- **Technical Implementation**: Flask API endpoint at `/api/generate-token-image`, Python service module `services/image_generator.py`, JSON validation and comprehensive error handling, loading state with estimated 10-30 second generation time

## Design Patterns
The architecture adheres to an MVC pattern, separating templates (views), Flask routes (controllers), and future models. Static assets are organized for efficiency, and a component-based CSS approach ensures modularity and reusability.

## Performance Optimizations
Hardware-accelerated CSS animations, efficient asset organization for caching, and JavaScript-enhanced smooth scrolling contribute to performance.

# External Dependencies

## Core Dependencies
- **Flask**: Python web framework.
- **Jinja2**: Template engine.

## Frontend Libraries
- **Font Awesome 6.0.0**: Icon library (via CDN).
- **Google Fonts (Inter)**: Typography (via CDN).
- **particles.js**: Particle animation library.

## Blockchain Integration
- **Kaspa Blockchain**: Target L1 blockchain for memecoin deployment.

## External Services
- **Telegram**: Community engagement.
- **Twitter/X**: Social media.
- **Kaspa Finance**: Partnership for automatic DEX deployment.
- **presale.gemlaunch.fun**: External presale portal.
- **OpenRouter API**: Meta Llama 3.1 70B inference with auto-failover for Gemmy AI, trend analysis, and image prompt enhancement.
- **Replicate API**: FLUX.1 Schnell model for AI-powered token image generation (1024x1024 WebP, $0.003/image).
- **4chan /biz/**: Real-time meme trend scraping for Zeroday Memification Engine.
- **Reddit CryptoMoonShots**: Community-validated meme trends and ticker mentions.

## Development Environment
- **Python Runtime**
- **Pillow**: Image processing for profile picture compression.