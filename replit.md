# Overview

gemlaunch.fun is a web platform designed to enable the creation and launch of memecoins on the Kaspa blockchain. The project aims to democratize memecoin creation by providing a no-code solution for launching community-driven tokens with fair launch mechanisms. The platform leverages Kaspa's high-performance L1 blockchain capabilities to offer fast transaction processing for memecoin operations.

## Recent Changes
- Created separate documentation page with GitBook-style tabbed interface
- Moved comprehensive documentation to its own route (/docs)
- Integrated actual project documentation content (no placeholder data)
- Removed hallucinated statistics from hero section
- Implemented tab-based navigation for documentation categories

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