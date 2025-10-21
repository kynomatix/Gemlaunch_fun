// Documentation page JavaScript functionality

document.addEventListener('DOMContentLoaded', function() {
    
    // Documentation tab functionality
    const docsTabs = document.querySelectorAll('.docs-tab');
    const docsPanels = document.querySelectorAll('.tab-panel');
    
    const switchTab = (tab) => {
        const targetTab = tab.getAttribute('data-tab');
        
        // Remove active class from all tabs and panels
        docsTabs.forEach(t => t.classList.remove('active'));
        docsPanels.forEach(p => p.classList.remove('active'));
        
        // Add active class to clicked tab and corresponding panel
        tab.classList.add('active');
        const targetPanel = document.getElementById(targetTab);
        if (targetPanel) {
            targetPanel.classList.add('active');
        }
    };
    
    docsTabs.forEach(tab => {
        // Support both click and touch events for mobile devices
        tab.addEventListener('click', () => switchTab(tab));
        tab.addEventListener('touchend', (e) => {
            e.preventDefault();
            switchTab(tab);
        });
    });

    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Header scroll effect
    const header = document.querySelector('header');
    let lastScroll = 0;

    window.addEventListener('scroll', () => {
        const currentScroll = window.pageYOffset;
        
        if (currentScroll > 100) {
            header.classList.add('scrolled');
        } else {
            header.classList.remove('scrolled');
        }
        
        lastScroll = currentScroll;
    });

    // Enhanced scroll reveal animations for docs content using AnimationUtils
    AnimationUtils.initScrollReveal('.docs-panel h3, .docs-panel h4, .highlight-box, .option-card, .process-step, .fee-item, .contract-item, .phase, .competitive-item, .metric-category, .message-category', {
        threshold: 0.1,
        staggerDelay: 50,
        translateY: 20,
        transition: 'opacity 0.6s ease, transform 0.6s ease'
    });

    // Mobile menu functionality (reused from main.js)
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

    console.log('📚 Documentation page loaded successfully!');
});