/**
 * Animation Utilities
 * Reusable scroll reveal and counter animations using IntersectionObserver
 * Consolidated from docs.js and main.js scroll reveal logic
 */

(function() {
    'use strict';
    
    // Track initialized elements to ensure idempotency (safe for Turbo navigation)
    const initializedElements = new WeakSet();
    
    // Store active observers for cleanup
    const activeObservers = new Map();
    
    /**
     * Animated counter for numeric elements
     * @param {HTMLElement} element - Element to animate
     * @param {number} target - Target number
     * @param {number} duration - Animation duration in ms
     */
    function animateCounter(element, target, duration = 2000) {
        const start = 0;
        const increment = target / (duration / 16);
        let current = start;
        
        const timer = setInterval(() => {
            current += increment;
            element.textContent = Math.floor(current).toLocaleString();
            
            if (current >= target) {
                element.textContent = target.toLocaleString();
                clearInterval(timer);
            }
        }, 16);
    }
    
    /**
     * Initialize scroll reveal animations
     * @param {string} selector - CSS selector for elements to animate
     * @param {Object} options - Configuration options
     * @param {number} [options.threshold=0.1] - Intersection threshold (0-1)
     * @param {string} [options.rootMargin='0px'] - Root margin for intersection
     * @param {number} [options.delay=0] - Initial delay before animation starts (ms)
     * @param {number} [options.staggerDelay=100] - Delay between each element (ms)
     * @param {number} [options.translateY=30] - Initial translateY value (px)
     * @param {string} [options.transition='opacity 0.8s ease, transform 0.8s ease'] - CSS transition property
     * @param {Function} onReveal - Optional callback when element is revealed (receives element and index)
     * @returns {IntersectionObserver|null} The created observer or null if no elements found
     */
    function initScrollReveal(selector, options = {}, onReveal = null) {
        // Default options
        const config = {
            threshold: 0.1,
            rootMargin: '0px',
            delay: 0,
            staggerDelay: 100,
            translateY: 30,
            transition: 'opacity 0.8s ease, transform 0.8s ease',
            ...options
        };
        
        // Get elements
        const elements = document.querySelectorAll(selector);
        if (elements.length === 0) return null;
        
        // Create unique key for this selector + config combination
        const observerKey = `${selector}-${JSON.stringify(config)}`;
        
        // Clean up existing observer if it exists (idempotent behavior)
        if (activeObservers.has(observerKey)) {
            const existingObserver = activeObservers.get(observerKey);
            existingObserver.disconnect();
            activeObservers.delete(observerKey);
        }
        
        // Create intersection observer
        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry, index) => {
                if (entry.isIntersecting && !initializedElements.has(entry.target)) {
                    // Mark as initialized to prevent re-animation
                    initializedElements.add(entry.target);
                    
                    // Calculate staggered delay
                    const totalDelay = config.delay + (index * config.staggerDelay);
                    
                    setTimeout(() => {
                        entry.target.style.opacity = '1';
                        entry.target.style.transform = 'translateY(0)';
                        
                        // Call custom reveal callback if provided
                        if (typeof onReveal === 'function') {
                            onReveal(entry.target, index);
                        }
                        
                        // Check for counter animation (hero stats)
                        if (entry.target.classList.contains('hero-stats')) {
                            const counters = entry.target.querySelectorAll('.stat-number');
                            counters.forEach(counter => {
                                const target = parseInt(counter.getAttribute('data-target'));
                                if (!isNaN(target)) {
                                    animateCounter(counter, target);
                                }
                            });
                        }
                    }, totalDelay);
                }
            });
        }, {
            threshold: config.threshold,
            rootMargin: config.rootMargin
        });
        
        // Initialize and observe elements
        elements.forEach(el => {
            // Only set initial styles if element hasn't been initialized
            if (!initializedElements.has(el)) {
                el.style.opacity = '0';
                el.style.transform = `translateY(${config.translateY}px)`;
                el.style.transition = config.transition;
            }
            observer.observe(el);
        });
        
        // Store observer for potential cleanup
        activeObservers.set(observerKey, observer);
        
        return observer;
    }
    
    /**
     * Initialize multiple scroll reveal groups at once
     * @param {Array} configs - Array of {selector, options, onReveal} objects
     * @returns {Array} Array of created observers
     */
    function initMultipleScrollReveals(configs) {
        return configs.map(config => {
            return initScrollReveal(config.selector, config.options, config.onReveal);
        }).filter(observer => observer !== null);
    }
    
    /**
     * Clean up all active observers
     */
    function cleanup() {
        activeObservers.forEach(observer => observer.disconnect());
        activeObservers.clear();
    }
    
    /**
     * Reset an element's animation state (useful for re-triggering animations)
     * @param {HTMLElement} element - Element to reset
     */
    function resetElement(element) {
        initializedElements.delete(element);
        element.style.opacity = '0';
        element.style.transform = '';
    }
    
    /**
     * Reset all elements matching a selector
     * @param {string} selector - CSS selector for elements to reset
     */
    function resetElements(selector) {
        const elements = document.querySelectorAll(selector);
        elements.forEach(el => resetElement(el));
    }
    
    // Export to window
    window.AnimationUtils = {
        initScrollReveal,
        initMultipleScrollReveals,
        animateCounter,
        cleanup,
        resetElement,
        resetElements
    };
    
    console.log('✨ Animation utilities loaded');
    
})();
