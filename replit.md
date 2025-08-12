# Overview

gemlaunch.fun is a web platform designed to enable the creation and launch of memecoins on the Kaspa blockchain. The project aims to democratize memecoin creation by providing a no-code solution for launching community-driven tokens with fair launch mechanisms. The platform leverages Kaspa's high-performance L1 blockchain capabilities to offer fast transaction processing for memecoin operations.

## Recent Changes
- Created separate documentation page with GitBook-style tabbed interface
- Moved comprehensive documentation to its own route (/docs)
- Integrated actual project documentation content (no placeholder data)
- Removed hallucinated statistics from hero section
- Implemented tab-based navigation for documentation categories
- Corrected misinformation: Kaspa is 10 BPS (blocks per second), not 100+ BPS
- Removed fake "launch fee" step from How It Works - no launch fees exist, only 1% swap fee
- Updated steps to match authentic project information from original content
- Added Gemmy mascot to both homepage hero section and documentation overview
- Implemented floating mascot card with hover animations and AI assistant branding
- Fixed Lightning Fast feature card: corrected "1-second block times" to accurate "~100ms block times"
- Added innovative platform features: AI Assistant (Gemmy), Built-in Social Layer with $cashtags, Gamified Leaderboard
- Enhanced Why Kaspa section with authentic messaging about other blockchains being "stale/bloated/oversaturated"
- Added Kaspa Finance partnership highlight showing automatic DEX deployment for graduated tokens
- Updated Kaspa features to match original content: Lightning Speed, Ultra-Low Fees, EVM Compatible, First-Mover Edge, K-for-Kaspa Culture
- Fixed glitch text capitalization: added inline CSS to ensure "Gemlaunch.fun" displays with proper uppercase G
- Integrated GDF logo into footer section replacing gem icon with proper image element and hover effects
- Updated social media links to new URLs (t.me/gemlaunchio and x.com/gemlaunchio)
- Added proper spacing to documentation page between tab navigation and content frames
- Corrected Gamified Leaderboard messaging: seasonal airdrops, leaderboard points, acolades terminology
- Replaced robot emoji with Gemmy head image in "Meet Gemmy - AI Assistant" feature card
- Updated hero text: changed "fastest L1 blockchain" to accurate "fastest proof-of-work blockchain"
- Added miner-friendly economics section explaining how memecoin trading fees support mining profitability
- Added 4 additional Kaspa feature cards: Trilemma Solved, Bitcoin Security, Passionate Community, Fair Launch DNA
- Fixed duplicate fire emoji between Ultra-Low Fees and Passionate Community (changed latter to blue heart)
- Updated Community-First Economics hover effect from wild swivel to subtle lift with glow
- Updated milestone text to specify "Kaspa Finance DEX" instead of generic "major DEXs"
- Removed go-to-market strategy section from documentation (hidden from public view)
- Sanitized documentation by replacing competitor references (pump.fun, LetsBonk.fun) with generic terms
- Fixed social media links in documentation navigation to use correct URLs (t.me/gemlaunchio, x.com/gemlaunchio)
- Applied comprehensive mobile scroll trap fixes to eliminate horizontal scrolling issues
- Added prominent "Join GEM Presale" button in hero section with golden styling and glow animation
- Button links to external presale portal (https://presale.gemlaunch.fun) instead of on-page section
- Updated documentation to include KAS/GEM pairing options with premium GEM benefits
- Added comprehensive GEM pairing incentives: lower fees, graduation bonuses, airdrop boosts, dual rewards, DAO perks
- Updated launch process to include pair token selection step
- Enhanced tokenomics section with differential fee structure (1% GEM vs 2% KAS)
- Added leaderboard carousel feature for GEM-paired graduated tokens

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Frontend Architecture
The application uses a traditional server-side rendered approach with Flask templating. The frontend is built with:
- **HTML Templates**: Jinja2 templating engine for dynamic content rendering
- **CSS Framework**: Custom CSS with modern design patterns including CSS Grid, Flexbox, and CSS animations
- **JavaScript**: Vanilla JavaScript for interactive features and animations
- **Particle System**: Custom particle effects using particles.js for visual enhancement
- **Documentation System**: GitBook-style tabbed interface for comprehensive project documentation
- **Interactive Elements**: Tab-based navigation, smooth transitions, and hover effects
- **Responsive Design**: Mobile-first approach with viewport-based scaling

## Backend Architecture
The backend follows a minimal Flask application structure:
- **Web Framework**: Flask as the primary web framework
- **Routing**: Simple route-based architecture with dedicated endpoints for health checks and main pages
- **Configuration**: Environment-based configuration for session management
- **Logging**: Built-in Python logging for debugging and monitoring

## Design Patterns
- **MVC Pattern**: Separation of concerns with templates (views), Flask routes (controllers), and potential future models
- **Static Asset Organization**: Structured separation of CSS, JavaScript, and other static resources
- **Component-Based CSS**: Modular CSS architecture with reusable components and utility classes

## Performance Optimizations
- **CSS Animations**: Hardware-accelerated CSS transforms and transitions
- **Asset Organization**: Logical separation of stylesheets and JavaScript files for efficient caching
- **Smooth Scrolling**: JavaScript-enhanced user experience with smooth navigation

# External Dependencies

## Core Dependencies
- **Flask**: Python web framework for application structure and routing
- **Jinja2**: Template engine (included with Flask) for dynamic HTML rendering

## Frontend Libraries
- **Font Awesome 6.0.0**: Icon library via CDN for UI elements and social media icons
- **Google Fonts (Inter)**: Typography via CDN for consistent font rendering
- **particles.js**: Particle animation library for background effects

## Blockchain Integration
- **Kaspa Blockchain**: Target blockchain for memecoin deployment (integration layer not yet implemented)

## External Services
- **Telegram**: Community engagement platform (linked via t.me/gemlaunchfun)
- **Twitter/X**: Social media presence (linked via x.com/gemlaunchfun)
- **Documentation Platform**: Separate docs site (docs.gemlaunch.fun)

## Development Environment
- **Python Runtime**: Flask application requires Python environment
- **Static File Serving**: Flask development server for CSS/JS asset delivery
- **Environment Variables**: SESSION_SECRET for Flask session management