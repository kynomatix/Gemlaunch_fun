// Particles.js Configuration
// Check if mobile device (screen width < 768px)
if (window.innerWidth >= 768) {
    particlesJS('particles-js', {
        "particles": {
            "number": {
                "value": 25,  // Reduced from 80 to 25 for 60% CPU reduction
                "density": {
                    "enable": true,
                    "value_area": 1200  // Increased area for better spacing with fewer particles
                }
            },
        "color": {
            "value": ["#20B2AA", "#00CED1", "#40E0D0"]
        },
        "shape": {
            "type": "circle",
            "stroke": {
                "width": 0,
                "color": "#000000"
            },
            "polygon": {
                "nb_sides": 6
            }
        },
        "opacity": {
            "value": 0.3,
            "random": true,
            "anim": {
                "enable": true,
                "speed": 1,
                "opacity_min": 0.1,
                "sync": false
            }
        },
        "size": {
            "value": 3,
            "random": true,
            "anim": {
                "enable": true,
                "speed": 2,
                "size_min": 0.1,
                "sync": false
            }
        },
        "line_linked": {
            "enable": true,
            "distance": 150,
            "color": "#20B2AA",
            "opacity": 0.2,
            "width": 1
        },
        "move": {
            "enable": true,
            "speed": 1,
            "direction": "none",
            "random": true,
            "straight": false,
            "out_mode": "out",
            "bounce": false,
            "attract": {
                "enable": false,
                "rotateX": 600,
                "rotateY": 1200
            }
        }
    },
    "interactivity": {
        "detect_on": "canvas",
        "events": {
            "onhover": {
                "enable": true,
                "mode": "repulse"
            },
            "onclick": {
                "enable": true,
                "mode": "push"
            },
            "resize": true
        },
        "modes": {
            "grab": {
                "distance": 400,
                "line_linked": {
                    "opacity": 1
                }
            },
            "bubble": {
                "distance": 400,
                "size": 40,
                "duration": 2,
                "opacity": 8,
                "speed": 3
            },
            "repulse": {
                "distance": 100,
                "duration": 0.4
            },
            "push": {
                "particles_nb": 4
            },
            "remove": {
                "particles_nb": 2
            }
        }
    },
        "retina_detect": true
    });
} else {
    // Disable particles entirely on mobile for better performance
    const particlesContainer = document.getElementById('particles-js');
    if (particlesContainer) {
        particlesContainer.style.display = 'none';
    }
}

// Floating elements animation
function createFloatingElements() {
    // Skip floating elements on mobile devices
    if (window.innerWidth < 768) {
        return;
    }
    const container = document.querySelector('.floating-elements');
    const elementCount = 8;  // Reduced from 15 to 8 for better performance
    
    for (let i = 0; i < elementCount; i++) {
        const element = document.createElement('div');
        element.className = 'floating-gem';
        element.style.left = Math.random() * 100 + '%';
        element.style.animationDelay = Math.random() * 20 + 's';
        element.style.animationDuration = (15 + Math.random() * 10) + 's';
        container.appendChild(element);
    }
}

// Initialize floating elements when DOM is loaded
document.addEventListener('DOMContentLoaded', createFloatingElements);
