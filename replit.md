# Overview

gemlaunch.fun is a web platform designed to enable the creation and launch of memecoins on the Kaspa blockchain. The project aims to democratize memecoin creation by providing a no-code solution for launching community-driven tokens with fair launch mechanisms. The platform leverages Kaspa's high-performance L1 blockchain capabilities to offer fast transaction processing for memecoin operations.

## Recent Changes
- **MAJOR ARCHITECTURAL CHANGE (Aug 26, 2025)**: Converted from Python Flask to Node.js Express
  - Backend migrated from Python/Flask to JavaScript/Express for easier maintenance
  - Template syntax converted from Jinja2 to EJS (configured to use .html files)
  - All routes preserved: /, /docs, /pitch-deck, /health
  - All functionality and front-end appearance remain identical
  - Static file serving maintained at /static/ paths
  - Conversion tested and verified - all endpoints return proper responses
- Updated pitch deck "Anti-Rug & Bot Protection" feature in Security & Social sub-slide
- Enhanced traction metrics: "1B Total Supply" → "1 Billion GEM Token Supply"
- Updated community metric to "Community Member Exposure" (reflecting Kaspa Finance partnership)
- Fixed documentation competitive positioning: "First-Mover" → "Early Pioneer Advantage"
- Removed exclusivity claims to reflect competitive landscape reality
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
- Removed API link from Resources section in footer
- Added complete investor pitch deck at /pitch-deck route with 12 interactive slides
- Created pitch deck link in footer Resources section for investor access
- Enhanced pitch deck with sequential entrance animations and connecting lines for "How It Works" section
- Added proper x*y=k bonding curve with token launch and DEX graduation points in brand colors
- Implemented innovative animated roadmap with progress line, traveling glow, and pulsing milestone dots
- Updated roadmap strategy: Q1 2026 focuses on community-driven features instead of mobile app (working with Kastle wallet)
- Q2 2026 Pro Analytics targets KRC20 bubble maps and market analytics rather than institutional features
- Added wallet integrations to Q4 2025 launch milestone

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Frontend Architecture
The application uses a traditional server-side rendered approach with Express templating. The frontend is built with:
- **HTML Templates**: EJS templating engine configured to use .html files for dynamic content rendering
- **CSS Framework**: Custom CSS with modern design patterns including CSS Grid, Flexbox, and CSS animations
- **JavaScript**: Vanilla JavaScript for interactive features and animations
- **Particle System**: Custom particle effects using particles.js for visual enhancement
- **Documentation System**: GitBook-style tabbed interface for comprehensive project documentation
- **Interactive Elements**: Tab-based navigation, smooth transitions, and hover effects
- **Responsive Design**: Mobile-first approach with viewport-based scaling

## Backend Architecture
The backend follows a minimal Node.js Express application structure:
- **Web Framework**: Express.js as the primary web framework
- **Routing**: Simple route-based architecture with dedicated endpoints for health checks and main pages
- **Template Engine**: EJS configured to render .html files
- **Static File Serving**: Express static middleware for CSS, JavaScript, and image assets
- **Configuration**: Environment-based configuration for port management

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
- **Express.js**: Node.js web framework for application structure and routing
- **EJS**: Template engine configured to render .html files for dynamic content

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
- **Node.js Runtime**: Express application requires Node.js environment
- **Static File Serving**: Express static middleware for CSS/JS asset delivery
- **Environment Variables**: PORT for server configuration (defaults to 5000)