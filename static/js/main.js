// Main JavaScript for enhanced interactions and animations

document.addEventListener('DOMContentLoaded', function() {
    
    // Header scroll effect
    const header = document.querySelector('header');
    let lastScroll = 0;

    if (header) {
        window.addEventListener('scroll', () => {
            const currentScroll = window.pageYOffset;
            
            if (currentScroll > 100) {
                header.classList.add('scrolled');
            } else {
                header.classList.remove('scrolled');
            }
            
            lastScroll = currentScroll;
        });
    }

    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            // Only handle valid anchor links with IDs, not just "#"
            if (href && href.length > 1) {
                e.preventDefault();
                const target = document.querySelector(href);
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            }
        });
    });

    // XP Bar animations
    function initXPBars() {
        const xpBars = document.querySelectorAll('.xp-fill');
        xpBars.forEach((bar, index) => {
            const targetWidth = bar.getAttribute('data-xp');
            bar.style.setProperty('--target-width', targetWidth + '%');
            
            // Start animation with progressive delays
            setTimeout(() => {
                bar.style.width = targetWidth + '%';
                // Show XP text after bar fills
                const xpText = bar.parentElement.querySelector('.xp-text');
                if (xpText) {
                    setTimeout(() => {
                        xpText.style.opacity = '1';
                    }, 2000);
                }
            }, 1000 + (index * 500));
        });
    }

    // Initialize XP bars
    initXPBars();

    // Initialize scroll reveal animations using AnimationUtils
    // Add 'reveal' class to elements for CSS compatibility
    document.querySelectorAll('.step, .feature, .kaspa-feature, .benefit, .hero-stats').forEach(el => {
        el.classList.add('reveal');
    });
    
    // Setup scroll reveal with AnimationUtils (handles counter animations automatically for .hero-stats)
    AnimationUtils.initScrollReveal('.step, .feature, .kaspa-feature, .benefit, .hero-stats', {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    }, function(element, index) {
        // Add 'active' class for CSS compatibility
        element.classList.add('active');
    });

    // Enhanced button hover effects
    document.querySelectorAll('.btn').forEach(btn => {
        btn.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-3px) scale(1.05)';
        });
        
        btn.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0) scale(1)';
        });
    });

    // Glass card tilt effect
    document.querySelectorAll('.glass-card').forEach(card => {
        card.addEventListener('mousemove', function(e) {
            const rect = this.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            const centerX = rect.width / 2;
            const centerY = rect.height / 2;
            const rotateX = (y - centerY) / 10;
            const rotateY = (centerX - x) / 10;
            
            this.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateZ(10px)`;
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'perspective(1000px) rotateX(0) rotateY(0) translateZ(0)';
        });
    });

    // Parallax effect for hero section
    window.addEventListener('scroll', () => {
        const scrolled = window.pageYOffset;
        const hero = document.querySelector('.hero');
        const rate = scrolled * -0.5;
        
        if (hero) {
            hero.style.transform = `translateY(${rate}px)`;
        }
    });

    // Dynamic text animation for tagline
    const tagline = document.querySelector('.tagline');
    if (tagline) {
        const text = tagline.textContent;
        tagline.innerHTML = '';
        
        [...text].forEach((char, i) => {
            const span = document.createElement('span');
            span.textContent = char === ' ' ? '\u00A0' : char;
            span.style.animationDelay = `${i * 0.1}s`;
            span.classList.add('char-animate');
            tagline.appendChild(span);
        });
        
        // Add CSS for character animation
        const style = document.createElement('style');
        style.textContent = `
            .char-animate {
                display: inline-block;
                animation: charFadeIn 0.8s ease-in-out forwards;
                opacity: 0;
                transform: translateY(20px);
            }
            @keyframes charFadeIn {
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
        `;
        document.head.appendChild(style);
    }

    // Mobile menu toggle (if needed)
    const createMobileMenu = () => {
        if (window.innerWidth <= 768) {
            const nav = document.querySelector('header nav > div:last-child');
            if (nav && !nav.classList.contains('mobile-menu-created')) {
                nav.classList.add('mobile-menu-created');
                
                const menuToggle = document.createElement('button');
                menuToggle.innerHTML = '<i class="fas fa-bars"></i>';
                menuToggle.classList.add('mobile-menu-toggle');
                menuToggle.style.cssText = `
                    background: none;
                    border: none;
                    color: #20B2AA;
                    font-size: 1.5rem;
                    cursor: pointer;
                    display: none;
                `;
                
                if (window.innerWidth <= 768) {
                    menuToggle.style.display = 'block';
                    nav.style.display = 'none';
                }
                
                nav.parentNode.insertBefore(menuToggle, nav);
                
                menuToggle.addEventListener('click', () => {
                    nav.style.display = nav.style.display === 'none' ? 'flex' : 'none';
                });
            }
        }
    };

    // Initialize mobile menu
    createMobileMenu();
    window.addEventListener('resize', createMobileMenu);

    // Add loading animation
    window.addEventListener('load', () => {
        document.body.classList.add('loaded');
        
        // Add CSS for loaded state
        const style = document.createElement('style');
        style.textContent = `
            body:not(.loaded) .hero-content {
                opacity: 0;
                transform: translateY(50px);
            }
            body.loaded .hero-content {
                animation: heroFadeIn 1s ease-out forwards;
            }
            @keyframes heroFadeIn {
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
        `;
        document.head.appendChild(style);
    });

    // Particle interaction enhancement
    let mouseX = 0;
    let mouseY = 0;

    document.addEventListener('mousemove', (e) => {
        mouseX = e.clientX;
        mouseY = e.clientY;
        
        // Create trailing effect
        if (Math.random() > 0.95) {
            createTrailParticle(mouseX, mouseY);
        }
    });

    function createTrailParticle(x, y) {
        const particle = document.createElement('div');
        particle.style.cssText = `
            position: fixed;
            left: ${x}px;
            top: ${y}px;
            width: 4px;
            height: 4px;
            background: linear-gradient(45deg, #20B2AA, #00CED1);
            border-radius: 50%;
            pointer-events: none;
            z-index: 1000;
            animation: trailFade 1s ease-out forwards;
        `;
        
        document.body.appendChild(particle);
        
        // Add trail animation CSS if not exists
        if (!document.querySelector('#trail-style')) {
            const trailStyle = document.createElement('style');
            trailStyle.id = 'trail-style';
            trailStyle.textContent = `
                @keyframes trailFade {
                    0% {
                        opacity: 0.8;
                        transform: scale(1);
                    }
                    100% {
                        opacity: 0;
                        transform: scale(0.3) translateY(-20px);
                    }
                }
            `;
            document.head.appendChild(trailStyle);
        }
        
        setTimeout(() => {
            particle.remove();
        }, 1000);
    }

    // Enhanced scroll reveal animations
    const revealElements = document.querySelectorAll('.section-title, .step, .feature, .kaspa-feature');
    
    const revealObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry, index) => {
            if (entry.isIntersecting) {
                setTimeout(() => {
                    entry.target.style.opacity = '1';
                    entry.target.style.transform = 'translateY(0)';
                }, index * 100);
            }
        });
    }, { threshold: 0.1 });

    revealElements.forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(30px)';
        el.style.transition = 'opacity 0.8s ease, transform 0.8s ease';
        revealObserver.observe(el);
    });

    console.log('🚀 Gemlaunch.fun enhanced interface loaded successfully!');
});
