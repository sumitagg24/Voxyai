// ============================================
// VOXYLIS - MAIN JAVASCRIPT
// ============================================

// Smooth scroll for navigation links
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

// Minion Widget Interactions
class MinionWidget {
    constructor() {
        this.widget = document.querySelector('.minion-widget');
        this.isRecording = false;
        this.init();
    }

    init() {
        if (this.widget) {
            this.widget.addEventListener('click', () => this.toggleRecording());
            this.widget.addEventListener('mouseenter', () => this.blink());
        }
    }

    toggleRecording() {
        this.isRecording = !this.isRecording;
        if (this.isRecording) {
            this.startRecording();
        } else {
            this.stopRecording();
        }
    }

    startRecording() {
        this.widget.classList.add('recording', 'talking');
        this.animateMouth();
    }

    stopRecording() {
        this.widget.classList.remove('recording', 'talking');
    }

    blink() {
        this.widget.classList.add('blinking');
        setTimeout(() => {
            this.widget.classList.remove('blinking');
        }, 300);
    }

    animateMouth() {
        if (this.isRecording) {
            setTimeout(() => this.animateMouth(), 400);
        }
    }
}

// Initialize minion widget
document.addEventListener('DOMContentLoaded', () => {
    new MinionWidget();
});

// Hotkey Display Animation
function animateHotkey() {
    const hotkeyDisplay = document.querySelector('.hotkey-display');
    if (hotkeyDisplay) {
        hotkeyDisplay.style.animation = 'none';
        setTimeout(() => {
            hotkeyDisplay.style.animation = 'hotkey-pulse 2s ease-in-out infinite';
        }, 10);
    }
}

// Intersection Observer for fade-in animations
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -100px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
        }
    });
}, observerOptions);

document.querySelectorAll('.feature-card, .doc-card, .pricing-card, .step').forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(20px)';
    el.style.transition = 'opacity 0.6s ease-out, transform 0.6s ease-out';
    observer.observe(el);
});

// Pricing Card Hover Effect
document.querySelectorAll('.pricing-card').forEach(card => {
    card.addEventListener('mouseenter', function() {
        this.style.transform = 'translateY(-10px)';
    });
    card.addEventListener('mouseleave', function() {
        if (this.classList.contains('featured')) {
            this.style.transform = 'scale(1.05)';
        } else {
            this.style.transform = 'translateY(0)';
        }
    });
});

// Feature Card Hover Effect
document.querySelectorAll('.feature-card').forEach(card => {
    card.addEventListener('mouseenter', function() {
        this.style.transform = 'translateY(-10px)';
    });
    card.addEventListener('mouseleave', function() {
        this.style.transform = 'translateY(0)';
    });
});

// Scroll Animation for Hotkey Display
window.addEventListener('scroll', () => {
    const heroSection = document.querySelector('.hero');
    if (heroSection) {
        const rect = heroSection.getBoundingClientRect();
        if (rect.top < window.innerHeight && rect.bottom > 0) {
            animateHotkey();
        }
    }
});

// Button Click Effects
document.querySelectorAll('.btn').forEach(btn => {
    btn.addEventListener('click', function(e) {
        const ripple = document.createElement('span');
        const rect = this.getBoundingClientRect();
        const size = Math.max(rect.width, rect.height);
        const x = e.clientX - rect.left - size / 2;
        const y = e.clientY - rect.top - size / 2;

        ripple.style.width = ripple.style.height = size + 'px';
        ripple.style.left = x + 'px';
        ripple.style.top = y + 'px';
        ripple.classList.add('ripple');

        this.appendChild(ripple);

        setTimeout(() => ripple.remove(), 600);
    });
});

// Add ripple effect CSS
const style = document.createElement('style');
style.textContent = `
    .btn {
        position: relative;
        overflow: hidden;
    }
    
    .ripple {
        position: absolute;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.6);
        transform: scale(0);
        animation: ripple-animation 0.6s ease-out;
        pointer-events: none;
    }
    
    @keyframes ripple-animation {
        to {
            transform: scale(4);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// Navbar Scroll Effect
let lastScrollTop = 0;
const navbar = document.querySelector('.navbar');

window.addEventListener('scroll', () => {
    let scrollTop = window.pageYOffset || document.documentElement.scrollTop;
    
    if (scrollTop > 100) {
        navbar.style.boxShadow = '0 4px 6px rgba(0, 0, 0, 0.1)';
    } else {
        navbar.style.boxShadow = '0 1px 2px rgba(0, 0, 0, 0.05)';
    }
    
    lastScrollTop = scrollTop <= 0 ? 0 : scrollTop;
});

// Counter Animation
function animateCounter(element, target, duration = 2000) {
    let current = 0;
    const increment = target / (duration / 16);
    
    const timer = setInterval(() => {
        current += increment;
        if (current >= target) {
            element.textContent = target;
            clearInterval(timer);
        } else {
            element.textContent = Math.floor(current);
        }
    }, 16);
}

// Observe counters
const counterObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting && !entry.target.dataset.animated) {
            const target = parseInt(entry.target.dataset.target);
            animateCounter(entry.target, target);
            entry.target.dataset.animated = 'true';
        }
    });
}, { threshold: 0.5 });

document.querySelectorAll('[data-target]').forEach(el => {
    counterObserver.observe(el);
});

// Modal Functionality
class Modal {
    constructor(modalId) {
        this.modal = document.getElementById(modalId);
        this.closeBtn = this.modal?.querySelector('.close');
        this.init();
    }

    init() {
        if (this.closeBtn) {
            this.closeBtn.addEventListener('click', () => this.close());
        }
        window.addEventListener('click', (e) => {
            if (e.target === this.modal) {
                this.close();
            }
        });
    }

    open() {
        if (this.modal) {
            this.modal.style.display = 'block';
            this.modal.classList.add('show');
        }
    }

    close() {
        if (this.modal) {
            this.modal.classList.remove('show');
            setTimeout(() => {
                this.modal.style.display = 'none';
            }, 300);
        }
    }
}

// Form Validation
function validateForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return false;

    const inputs = form.querySelectorAll('input, textarea');
    let isValid = true;

    inputs.forEach(input => {
        if (!input.value.trim()) {
            input.classList.add('error');
            isValid = false;
        } else {
            input.classList.remove('error');
        }
    });

    return isValid;
}

// Keyboard Shortcut Handler
document.addEventListener('keydown', (e) => {
    // Win + Shift to activate recording
    if (e.key === 'Shift' && e.ctrlKey) {
        const widget = document.querySelector('.minion-widget');
        if (widget) {
            widget.click();
        }
    }

    // Escape to close modals
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal.show').forEach(modal => {
            modal.classList.remove('show');
        });
    }
});

// Notification System
class Notification {
    static show(message, type = 'info', duration = 3000) {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3b82f6'};
            color: white;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            z-index: 10000;
            animation: slideInRight 0.3s ease-out;
        `;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.animation = 'slideInLeft 0.3s ease-out reverse';
            setTimeout(() => notification.remove(), 300);
        }, duration);
    }
}

// API Integration Example
async function fetchFeatures() {
    try {
        const response = await fetch('/api/features');
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Error fetching features:', error);
        Notification.show('Failed to load features', 'error');
    }
}

// Local Storage Management
const Storage = {
    set: (key, value) => {
        localStorage.setItem(key, JSON.stringify(value));
    },
    get: (key) => {
        const item = localStorage.getItem(key);
        return item ? JSON.parse(item) : null;
    },
    remove: (key) => {
        localStorage.removeItem(key);
    },
    clear: () => {
        localStorage.clear();
    }
};

// User Preferences
class UserPreferences {
    constructor() {
        this.preferences = Storage.get('voxylis_preferences') || this.getDefaults();
    }

    getDefaults() {
        return {
            theme: 'light',
            language: 'en',
            hotkey: 'Win+Shift',
            wakeWord: 'Voxy',
            notifications: true
        };
    }

    save() {
        Storage.set('voxylis_preferences', this.preferences);
    }

    update(key, value) {
        this.preferences[key] = value;
        this.save();
    }

    get(key) {
        return this.preferences[key];
    }
}

// Initialize user preferences
const userPrefs = new UserPreferences();

// Theme Toggle
function toggleTheme() {
    const currentTheme = userPrefs.get('theme');
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    userPrefs.update('theme', newTheme);
    applyTheme(newTheme);
}

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
}

// Initialize theme
applyTheme(userPrefs.get('theme'));

// Performance Monitoring
class PerformanceMonitor {
    static logMetric(name, value) {
        console.log(`[Performance] ${name}: ${value}ms`);
    }

    static measureFunction(fn, name) {
        const start = performance.now();
        const result = fn();
        const end = performance.now();
        this.logMetric(name, end - start);
        return result;
    }
}

// Export for use in other modules
window.Voxylis = {
    Modal,
    Notification,
    Storage,
    UserPreferences,
    PerformanceMonitor,
    validateForm
};

console.log('Voxylis initialized successfully');
