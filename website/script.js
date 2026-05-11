// ============================================
// VOXYLIS WEBSITE - INTERACTIVE FEATURES
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

// FAQ Accordion
const faqItems = document.querySelectorAll('.faq-item');

faqItems.forEach(item => {
    const question = item.querySelector('.faq-question');
    
    question.addEventListener('click', () => {
        // Close other items
        faqItems.forEach(otherItem => {
            if (otherItem !== item) {
                otherItem.classList.remove('active');
            }
        });
        
        // Toggle current item
        item.classList.toggle('active');
    });
});

// Navbar scroll effect
let lastScrollTop = 0;
const navbar = document.querySelector('.navbar');

window.addEventListener('scroll', () => {
    let scrollTop = window.pageYOffset || document.documentElement.scrollTop;
    
    if (scrollTop > 100) {
        navbar.style.boxShadow = '0 2px 10px rgba(0, 0, 0, 0.1)';
    } else {
        navbar.style.boxShadow = 'none';
    }
    
    lastScrollTop = scrollTop <= 0 ? 0 : scrollTop;
});

// Button interactions
const buttons = document.querySelectorAll('.btn-primary, .btn-secondary');

buttons.forEach(button => {
    button.addEventListener('mouseenter', function() {
        this.style.transform = 'translateY(-2px)';
    });
    
    button.addEventListener('mouseleave', function() {
        this.style.transform = 'translateY(0)';
    });
    
    button.addEventListener('click', function(e) {
        // Ripple effect
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

// Observe feature cards, testimonials, etc.
document.querySelectorAll('.feature-card, .testimonial-card, .pricing-card, .mode-card').forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(20px)';
    el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
    observer.observe(el);
});

// Counter animation for performance metrics
const performanceSection = document.querySelector('.performance');
let hasAnimated = false;

const animateCounters = () => {
    if (hasAnimated) return;
    
    const perfNumbers = document.querySelectorAll('.perf-number');
    
    perfNumbers.forEach(number => {
        const text = number.textContent;
        const isTime = text.includes('ms') || text.includes('s');
        
        if (isTime) {
            // Animate time values
            const match = text.match(/(\d+)/);
            if (match) {
                const target = parseInt(match[1]);
                let current = 0;
                const increment = target / 30;
                
                const timer = setInterval(() => {
                    current += increment;
                    if (current >= target) {
                        current = target;
                        clearInterval(timer);
                    }
                    number.textContent = Math.round(current) + (text.includes('ms') ? 'ms' : 's');
                }, 30);
            }
        }
    });
    
    hasAnimated = true;
};

// Trigger counter animation when performance section is visible
const perfObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            animateCounters();
            perfObserver.unobserve(entry.target);
        }
    });
}, { threshold: 0.5 });

if (performanceSection) {
    perfObserver.observe(performanceSection);
}

// Parallax effect for hero section
const heroVisual = document.querySelector('.hero-visual');

if (heroVisual) {
    window.addEventListener('scroll', () => {
        const scrollPosition = window.pageYOffset;
        const heroSection = document.querySelector('.hero');
        const heroRect = heroSection.getBoundingClientRect();
        
        if (heroRect.top < window.innerHeight && heroRect.bottom > 0) {
            const offset = scrollPosition * 0.5;
            heroVisual.style.transform = `translateY(${offset}px)`;
        }
    });
}

// Mobile menu toggle (if needed)
const createMobileMenu = () => {
    const navbar = document.querySelector('.navbar');
    const navContainer = document.querySelector('.nav-container');
    
    // Check if mobile menu already exists
    if (document.querySelector('.mobile-menu-toggle')) return;
    
    if (window.innerWidth <= 768) {
        const toggle = document.createElement('button');
        toggle.className = 'mobile-menu-toggle';
        toggle.innerHTML = '☰';
        toggle.style.cssText = `
            display: none;
            background: none;
            border: none;
            font-size: 1.5rem;
            cursor: pointer;
            color: var(--text-primary);
        `;
        
        navContainer.appendChild(toggle);
    }
};

window.addEventListener('resize', createMobileMenu);
createMobileMenu();

// Smooth page load animation
window.addEventListener('load', () => {
    document.body.style.opacity = '1';
});

document.body.style.opacity = '0';
document.body.style.transition = 'opacity 0.5s ease';

// Add some initial opacity
setTimeout(() => {
    document.body.style.opacity = '1';
}, 100);

// Download button functionality
const downloadButtons = document.querySelectorAll('.btn-primary');

downloadButtons.forEach(button => {
    if (button.textContent.includes('Download')) {
        button.addEventListener('click', () => {
            // Show a modal or redirect to download page
            alert('Download page would open here. Redirecting to GitHub releases...');
            // window.open('https://github.com/yourusername/voxylis/releases', '_blank');
        });
    }
});

// Watch demo button
const demoButtons = document.querySelectorAll('.btn-secondary');

demoButtons.forEach(button => {
    if (button.textContent.includes('Demo') || button.textContent.includes('Watch')) {
        button.addEventListener('click', () => {
            // Show video modal
            showVideoModal();
        });
    }
});

// Video modal function
function showVideoModal() {
    const modal = document.createElement('div');
    modal.className = 'video-modal';
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.8);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 2000;
        animation: fadeIn 0.3s ease;
    `;
    
    const content = document.createElement('div');
    content.style.cssText = `
        background: white;
        border-radius: 1rem;
        padding: 2rem;
        max-width: 800px;
        width: 90%;
        position: relative;
    `;
    
    const closeBtn = document.createElement('button');
    closeBtn.innerHTML = '✕';
    closeBtn.style.cssText = `
        position: absolute;
        top: 1rem;
        right: 1rem;
        background: none;
        border: none;
        font-size: 1.5rem;
        cursor: pointer;
        color: #666;
    `;
    
    closeBtn.addEventListener('click', () => modal.remove());
    
    const videoContainer = document.createElement('div');
    videoContainer.style.cssText = `
        position: relative;
        padding-bottom: 56.25%;
        height: 0;
        overflow: hidden;
        border-radius: 0.5rem;
    `;
    
    const iframe = document.createElement('iframe');
    iframe.style.cssText = `
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        border: none;
        border-radius: 0.5rem;
    `;
    iframe.src = 'https://www.youtube.com/embed/dQw4w9WgXcQ';
    iframe.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture';
    iframe.allowFullscreen = true;
    
    videoContainer.appendChild(iframe);
    content.appendChild(closeBtn);
    content.appendChild(videoContainer);
    modal.appendChild(content);
    
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.remove();
        }
    });
    
    document.body.appendChild(modal);
}

// Add CSS animation
const style = document.createElement('style');
style.textContent = `
    @keyframes fadeIn {
        from {
            opacity: 0;
        }
        to {
            opacity: 1;
        }
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

// Newsletter signup (if needed)
const setupNewsletterForm = () => {
    // This would be added if there's a newsletter form
    const form = document.querySelector('.newsletter-form');
    if (form) {
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            const email = form.querySelector('input[type="email"]').value;
            console.log('Newsletter signup:', email);
            alert('Thanks for subscribing!');
            form.reset();
        });
    }
};

setupNewsletterForm();

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + K to focus search (if search exists)
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        // Focus search input if it exists
    }
    
    // Escape to close modals
    if (e.key === 'Escape') {
        const modals = document.querySelectorAll('.video-modal');
        modals.forEach(modal => modal.remove());
    }
});

// Performance monitoring
if (window.performance && window.performance.timing) {
    window.addEventListener('load', () => {
        const perfData = window.performance.timing;
        const pageLoadTime = perfData.loadEventEnd - perfData.navigationStart;
        console.log('Page load time:', pageLoadTime + 'ms');
    });
}

// Accessibility: Focus visible
document.addEventListener('keydown', (e) => {
    if (e.key === 'Tab') {
        document.body.classList.add('keyboard-nav');
    }
});

document.addEventListener('mousedown', () => {
    document.body.classList.remove('keyboard-nav');
});

// Add keyboard navigation styles
const keyboardStyle = document.createElement('style');
keyboardStyle.textContent = `
    .keyboard-nav button:focus,
    .keyboard-nav a:focus {
        outline: 2px solid var(--primary-color);
        outline-offset: 2px;
    }
`;
document.head.appendChild(keyboardStyle);

console.log('Voxylis website loaded successfully!');
