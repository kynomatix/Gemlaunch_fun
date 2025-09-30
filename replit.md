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
- Removed API link from Resources section in footer
- Added complete investor pitch deck at /pitch-deck route with 12 interactive slides
- Created pitch deck link in footer Resources section for investor access
- Enhanced pitch deck with sequential entrance animations and connecting lines for "How It Works" section
- Added proper x*y=k bonding curve with token launch and DEX graduation points in brand colors
- Implemented innovative animated roadmap with progress line, traveling glow, and pulsing milestone dots
- Updated roadmap strategy: Q1 2026 focuses on community-driven features instead of mobile app (working with Kastle wallet)
- Q2 2026 Pro Analytics targets KRC20 bubble maps and market analytics rather than institutional features
- Added wallet integrations to Q4 2025 launch milestone
- Fixed token card layout issue on marketplace page where market cap boxes were extending outside card frames
- Implemented comprehensive profile image upload system with Pillow compression (150x150 WebP at 80% quality)
- Added proper file storage in static/uploads/profile/ directory instead of base64 database storage
- Updated UserProfile model with avatar_path and avatar_updated_at fields for efficient image management
- Replaced URL input with proper file upload form with drag-and-drop styling and validation
- Added automatic cleanup of old avatar files when new ones are uploaded
- Implemented cache busting with timestamp query parameters for image updates
- Fixed Kasplex testnet network configuration: corrected Chain ID from 0x28CC4 (167108) to 0x28C64 (167012)
- Updated network name from "Kasplex Network Testnet" to "Kasplex Testnet" to match official specifications
- Fixed pro token settings modal to display treasury management and airdrop distribution features instead of basic chat requirements
- Corrected JavaScript type detection for pro tokens in getCurrentTokenData() function
- Added crown icon for pro token holders-only toggle to distinguish from basic tokens
- Updated settings modal to properly detect pro tokens using server-side is_pro_token flag
- Simplified Token Rewards section to only show measurable activities (chat, polls, engagement, holding)
- Made Token Rewards and achievement sections collapsible to save space
- Removed unmeasurable rewards like liquidity providing, user onboarding, and DAO governance
- Implemented message deletion capability for token owners to moderate chat (delete spam/offensive content)
- Added delete button (trash icon) visible only to token owner with confirmation modal
- Created secure DELETE API endpoint that validates token ownership before deletion
- Message deletion includes smooth UI animation and proper state cleanup
- Fixed message reactions (hearts) persistence - reactions now properly stored in database and persist across page refreshes
- Backend API returns love_count and is_loved_by_user for each message from MessageReaction table
- Frontend loads reaction data from database instead of localStorage, ensuring accurate counts after refresh
- Heart icons properly show as active (red) when user has already loved a message
- Merged Token Rewards and How to Earn Rewards sections into single collapsible section
- Fixed Treasury percentage to display actual reserved_percentage from token (not arbitrary calculation)
- Enabled anonymous access to marketplace and leaderboard pages (no wallet connection required for browsing)
- Created @wallet_optional decorator for routes that allow anonymous users while maintaining wallet-gated features
- Added wallet-connect banners on marketplace and leaderboard for anonymous users to encourage connection
- Updated templates to safely handle user=None and provide clear messaging about wallet benefits
- Fixed Enter key sending duplicate messages by adding preventDefault() to keypress event handler
- Restored spotlight messages to dedicated pinned panel above chat (no longer mixed in regular chat)
- Spotlight panel now stays visible at top of chat, messages don't scroll away
- Removed duplicate spotlight display in regular chat flow - spotlight messages only appear in dedicated panel
- Implemented comprehensive XSS security fixes across entire chat system and UI
- Added escapeHtml() utility function to sanitize all user-controlled HTML content
- Fixed XSS vulnerabilities in poll rendering (creator, question, option text)
- Fixed XSS vulnerabilities in chat messages (displayName, message, reply references)
- Fixed XSS vulnerabilities in spotlight messages (user, message)
- Fixed XSS vulnerabilities in modal helpers (alert, confirm, prompt - all title/message/input fields)
- All user-controlled strings now properly escaped before innerHTML insertion or HTML attribute assignment

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