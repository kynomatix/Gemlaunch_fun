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

### Gemmy Zeroday Memification Engine
The platform features an advanced AI-powered trend discovery system with three operational modes:
- **Creative Mode**: Traditional AI brainstorming for custom token ideas
- **Trending Memes Mode**: Real-time scraping of 4chan /biz/ and Reddit CryptoMoonShots with AI-scored trend analysis using 7 crypto-adoptability criteria (viral potential, cultural timing, community signal, crypto-native elements, mascot strength, moggability, cringe factor)
- **Kaspa Tech Mode**: Memification of Kaspa-native technical concepts (GHOSTDAG, DAGKnight, BlockDAG, 10 BPS, phantom blocks)

Technical implementation uses Meta Llama 3.1 70B via OpenRouter API with auto-failover across multiple providers (Groq, Together.ai, Cerebras) for maximum reliability. A 12-hour rolling cache window stored in PostgreSQL optimizes costs (~$0.20/day maximum). On-demand scraping triggers when cache expires, with automatic cleanup of old entries after 24 hours. The system follows the proven meme path: 4chan → Reddit → Twitter → Crypto, providing early-mover advantage.

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
- **OpenRouter API**: Meta Llama 3.1 70B inference with auto-failover for Gemmy AI and trend analysis.
- **4chan /biz/**: Real-time meme trend scraping for Zeroday Memification Engine.
- **Reddit CryptoMoonShots**: Community-validated meme trends and ticker mentions.

## Development Environment
- **Python Runtime**
- **Pillow**: Image processing for profile picture compression.