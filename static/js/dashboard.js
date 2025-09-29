// Dashboard functionality - loaded once globally
(function() {
    // Tab switching functionality - define globally
    window.switchTab = function(tabName) {
        console.log('[Dashboard] Switching to tab:', tabName);
        
        if (!tabName) {
            console.error('[Dashboard] No tab name provided');
            return;
        }
        
        // Remove active class from all tabs and buttons
        const allButtons = document.querySelectorAll('.tab-btn');
        const allPanes = document.querySelectorAll('.tab-pane');
        
        allButtons.forEach(btn => {
            btn.classList.remove('active');
        });
        
        allPanes.forEach(pane => {
            pane.classList.remove('active');
            pane.style.display = 'none';
        });
        
        // Find and activate the correct button
        allButtons.forEach(btn => {
            if (btn.dataset.tab === tabName) {
                btn.classList.add('active');
            }
        });
        
        // Show the correct tab pane
        const targetTab = document.getElementById(`${tabName}-tab`);
        if (targetTab) {
            targetTab.classList.add('active');
            targetTab.style.display = 'block';
            console.log('[Dashboard] Tab activated:', targetTab.id);
        } else {
            console.error('[Dashboard] Tab not found:', tabName + '-tab');
        }
    };

    // Initialize dashboard functionality
    window.initializeDashboard = function() {
        console.log('[Dashboard] Initializing...');
        
        // Setup tab click handlers using event delegation
        const tabNav = document.querySelector('.tab-navigation');
        if (tabNav) {
            // Remove any existing listeners first
            tabNav.replaceWith(tabNav.cloneNode(true));
            const newTabNav = document.querySelector('.tab-navigation');
            
            newTabNav.addEventListener('click', function(e) {
                const button = e.target.closest('.tab-btn');
                if (button && button.dataset.tab) {
                    e.preventDefault();
                    e.stopPropagation();
                    window.switchTab(button.dataset.tab);
                }
            });
        }
        
        // Ensure initial tab state is correct
        const activeBtn = document.querySelector('.tab-btn.active');
        if (activeBtn && activeBtn.dataset.tab) {
            // Force show the active tab
            const tabName = activeBtn.dataset.tab;
            const targetTab = document.getElementById(`${tabName}-tab`);
            if (targetTab) {
                targetTab.style.display = 'block';
                targetTab.classList.add('active');
            }
        }
        
        // Initialize animations for elements
        const accoladeCards = document.querySelectorAll('.accolade-card');
        accoladeCards.forEach((card, index) => {
            card.style.opacity = '0';
            card.style.transform = 'translateY(20px)';
            
            setTimeout(() => {
                card.style.transition = 'all 0.5s ease';
                card.style.opacity = '1';
                card.style.transform = 'translateY(0)';
            }, index * 50);
        });
        
        const activityItems = document.querySelectorAll('.activity-item');
        activityItems.forEach((item, index) => {
            item.style.opacity = '0';
            item.style.transform = 'translateY(20px)';
            
            setTimeout(() => {
                item.style.transition = 'all 0.5s ease';
                item.style.opacity = '1';
                item.style.transform = 'translateY(0)';
            }, 300 + (index * 80));
        });
        
        console.log('[Dashboard] Initialization complete');
    };

    // Setup HTMX event listeners
    if (window.htmx) {
        document.body.addEventListener('htmx:afterSwap', function(evt) {
            // Check if we're on the dashboard
            if (evt.detail.target.id === 'content-area') {
                const dashboardContent = document.querySelector('.dashboard-header');
                if (dashboardContent) {
                    console.log('[Dashboard] HTMX swap detected, reinitializing...');
                    // Small delay to ensure DOM is ready
                    setTimeout(window.initializeDashboard, 100);
                }
            }
        });
        
        document.body.addEventListener('htmx:afterSettle', function(evt) {
            // Additional safety check after settle
            if (evt.detail.target.id === 'content-area') {
                const dashboardContent = document.querySelector('.dashboard-header');
                if (dashboardContent) {
                    const activeTab = document.querySelector('.tab-pane.active');
                    if (activeTab && activeTab.style.display !== 'block') {
                        activeTab.style.display = 'block';
                    }
                }
            }
        });
    }

    // Initialize on regular page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            const dashboardContent = document.querySelector('.dashboard-header');
            if (dashboardContent) {
                window.initializeDashboard();
            }
        });
    } else {
        // DOM already loaded
        const dashboardContent = document.querySelector('.dashboard-header');
        if (dashboardContent) {
            window.initializeDashboard();
        }
    }
})();