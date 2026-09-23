// ============================================
// DASHBOARD JAVASCRIPT
// ============================================

// ============================================
// TIER MANAGEMENT
// ============================================

class TierManager {
    constructor() {
        this.tier = 'free';
        this.enhancementModes = {
            free: ['formal'],
            pro: ['formal', 'casual', 'technical', 'concise', 'creative'],
            business: ['formal', 'casual', 'technical', 'concise', 'creative'],
            owner: ['formal', 'casual', 'technical', 'concise', 'creative']
        };
        this.fetchTier();
    }

    async fetchTier() {
        try {
            const resp = await voxyFetch('/api/me');
            if (resp && resp.ok) {
                const r = await resp.json();
                if (r && r.success && r.user && r.user.tier) {
                    this.tier = r.user.tier;
                }
            }
        } catch (e) {
            // default to free
        }
        this.applyTierUI();
    }

    isFree() { return this.tier === 'free'; }

    hasFeature(feature) {
        const features = {
            free: ['transcription', 'enhancement_basic', 'history', 'settings', 'hotkeys'],
            pro: ['transcription', 'enhancement_basic', 'enhancement_all', 'qa', 'advanced_stt', 'wake_word', 'history', 'settings', 'hotkeys'],
            business: ['transcription', 'enhancement_basic', 'enhancement_all', 'qa', 'advanced_stt', 'wake_word', 'api_access', 'team_features', 'custom_integrations', 'history', 'settings', 'hotkeys'],
            owner: ['transcription', 'enhancement_basic', 'enhancement_all', 'qa', 'advanced_stt', 'wake_word', 'api_access', 'team_features', 'custom_integrations', 'history', 'settings', 'hotkeys', 'unlimited']
        };
        return feature in (features[this.tier] || features.free);
    }

    canUseMode(mode) {
        return this.enhancementModes[this.tier] && this.enhancementModes[this.tier].includes(mode);
    }

    applyTierUI() {
        // Gate enhancement mode chips
        const chips = document.querySelectorAll('#modeChips .chip');
        chips.forEach(chip => {
            const mode = chip.dataset.mode;
            if (this.canUseMode(mode)) {
                chip.style.opacity = '1';
                chip.style.pointerEvents = 'auto';
                chip.removeAttribute('title');
            } else {
                chip.style.opacity = '0.4';
                chip.style.pointerEvents = 'none';
                chip.title = 'Upgrade to Pro to use this mode';
            }
        });

        // Gate Q&A nav link and section
        const qaNav = document.querySelector('[data-section="qa"]');
        if (qaNav && this.isFree()) {
            qaNav.style.opacity = '0.4';
            qaNav.title = 'Upgrade to Pro to use Q&A';
        } else if (qaNav) {
            qaNav.style.opacity = '1';
            qaNav.removeAttribute('title');
        }

        // Gate Q&A section content
        const qaSection = document.getElementById('qa');
        if (qaSection && this.isFree()) {
            const form = qaSection.querySelector('.settings-form');
            if (form) {
                form.innerHTML = `
                    <div class="tier-locked" style="text-align:center;padding:3rem 1rem;">
                        <div style="font-size:2.5rem;margin-bottom:1rem;">🔒</div>
                        <h3 style="margin-bottom:0.5rem;">Q&A requires a Pro plan</h3>
                        <p style="color:var(--muted);margin-bottom:1.5rem;">Upgrade to ask questions about your transcriptions.</p>
                        <a href="/pricing" class="btn btn-primary">View Plans</a>
                    </div>
                `;
            }
        }

        // Update tier badge in subscription section
        const tierBadge = document.getElementById('subscriptionTierBadge');
        if (tierBadge) {
            tierBadge.textContent = this.tier.charAt(0).toUpperCase() + this.tier.slice(1);
            tierBadge.className = 'tier-badge tier-' + this.tier;
        }
    }
}

const tierManager = new TierManager();

// Load subscription data into the plan section
async function loadSubscriptionData() {
    try {
        const resp = await voxyFetch('/api/subscription');
        if (resp && resp.ok) {
            const r = await resp.json();
            if (r && r.subscription) {
                const s = r.subscription;
                const planEl = document.getElementById('planName');
                const renewalEl = document.getElementById('planRenewal');
                const countEl = document.getElementById('usageCount');
                const barEl = document.getElementById('usageBar');
                const badgeEl = document.getElementById('subscriptionTierBadge');
                if (planEl) planEl.textContent = s.plan || (s.tier === 'owner' ? 'Owner (Unlimited)' : 'Free');
                if (renewalEl) renewalEl.textContent = s.renewalDate ? 'Renews ' + s.renewalDate : (s.tier === 'owner' ? 'Lifetime Access' : '');
                if (countEl) countEl.textContent = s.usage ? s.usage.transcriptions + ' / ' + s.usage.limit : '–';
                if (barEl) barEl.style.width = s.usage ? s.usage.percentage + '%' : '0%';
                if (badgeEl) {
                    badgeEl.textContent = s.tier ? s.tier.charAt(0).toUpperCase() + s.tier.slice(1) : 'Free';
                    badgeEl.className = 'tier-badge tier-' + (s.tier || 'free');
                }
                // Update manage button
                const btn = document.getElementById('managePlanBtn');
                if (btn && s.tier === 'owner') {
                    btn.textContent = 'Owner Access';
                    btn.removeAttribute('href');
                    btn.style.pointerEvents = 'none';
                    btn.style.opacity = '0.7';
                } else if (btn && s.tier !== 'free') {
                    btn.textContent = 'Manage Plan';
                }
            }
        }
    } catch (e) {}
}
document.addEventListener('DOMContentLoaded', loadSubscriptionData);

// Section Navigation
class DashboardNav {
    constructor() {
        this.navItems = document.querySelectorAll('.nav-item');
        this.sections = document.querySelectorAll('.section');
        this.init();
    }

    init() {
        this.navItems.forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const sectionId = item.dataset.section;
                this.showSection(sectionId);
                this.updateActiveNav(item);
            });
        });
    }

    showSection(sectionId) {
        this.sections.forEach(section => {
            section.classList.remove('active');
        });
        const section = document.getElementById(sectionId);
        if (section) {
            section.classList.add('active');
        }
    }

    updateActiveNav(activeItem) {
        this.navItems.forEach(item => {
            item.classList.remove('active');
        });
        activeItem.classList.add('active');
    }
}

// Initialize dashboard navigation
document.addEventListener('DOMContentLoaded', () => {
    new DashboardNav();
    initializeCharts();
    initializeSettings();
    initializeHotkeys();
    initializeWakeWord();
    initializeHistory();
});

// ============================================
// CHARTS
// ============================================

function initializeCharts() {
    // The live wiring block in dashboard.html renders real charts from
    // /api/stats + /api/history when the backend is reachable. The sample
    // charts below are only a fallback for offline/demo mode.
    if (window.__chartsReal) return;
    const usageCtx = document.getElementById('usageChart');
    if (usageCtx) {
        new Chart(usageCtx, {
            type: 'line',
            data: {
                labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                datasets: [{
                    label: 'Transcriptions',
                    data: [12, 19, 3, 5, 2, 3, 15],
                    borderColor: '#6366f1',
                    backgroundColor: 'rgba(99, 102, 241, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }

    // Languages Chart
    const languagesCtx = document.getElementById('languagesChart');
    if (languagesCtx) {
        new Chart(languagesCtx, {
            type: 'doughnut',
            data: {
                labels: ['English', 'Spanish', 'French', 'German', 'Others'],
                datasets: [{
                    data: [45, 20, 15, 12, 8],
                    backgroundColor: [
                        '#6366f1',
                        '#ec4899',
                        '#f59e0b',
                        '#10b981',
                        '#8b5cf6'
                    ]
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }
}

// ============================================
// SETTINGS
// ============================================

function initializeSettings() {
    const themeSelect = document.getElementById('themeSelect');
    const languageSelect = document.getElementById('languageSelect');
    const notificationsToggle = document.getElementById('notificationsToggle');
    const soundToggle = document.getElementById('soundToggle');
    const autoStartToggle = document.getElementById('autoStartToggle');

    // Load saved settings
    const savedTheme = localStorage.getItem('voxylis_theme') || 'light';
    const savedLanguage = localStorage.getItem('voxylis_language') || 'en';
    const savedNotifications = localStorage.getItem('voxylis_notifications') !== 'false';
    const savedSound = localStorage.getItem('voxylis_sound') !== 'false';
    const savedAutoStart = localStorage.getItem('voxylis_autostart') === 'true';

    if (themeSelect) {
        themeSelect.value = savedTheme;
        applyTheme(savedTheme);
        themeSelect.addEventListener('change', (e) => {
            localStorage.setItem('voxylis_theme', e.target.value);
            applyTheme(e.target.value);
        });
    }

    if (languageSelect) {
        languageSelect.value = savedLanguage;
        languageSelect.addEventListener('change', (e) => {
            localStorage.setItem('voxylis_language', e.target.value);
        });
    }

    if (notificationsToggle) {
        notificationsToggle.checked = savedNotifications;
        notificationsToggle.addEventListener('change', (e) => {
            localStorage.setItem('voxylis_notifications', e.target.checked);
        });
    }

    if (soundToggle) {
        soundToggle.checked = savedSound;
        soundToggle.addEventListener('change', (e) => {
            localStorage.setItem('voxylis_sound', e.target.checked);
        });
    }

    if (autoStartToggle) {
        autoStartToggle.checked = savedAutoStart;
        autoStartToggle.addEventListener('change', (e) => {
            localStorage.setItem('voxylis_autostart', e.target.checked);
        });
    }

    // Save settings button
    const saveBtn = document.querySelector('.settings-form .btn-primary');
    if (saveBtn) {
        saveBtn.addEventListener('click', () => {
            Voxylis.Notification.show('Settings saved successfully!', 'success');
        });
    }
}

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
}

// ============================================
// HOTKEYS
// ============================================

function initializeHotkeys() {
    const changeButtons = document.querySelectorAll('.hotkey-item .btn-secondary');
    
    changeButtons.forEach((btn, index) => {
        btn.addEventListener('click', () => {
            showHotkeyRecorder(index);
        });
    });
}

function showHotkeyRecorder(index) {
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content">
            <h3>Press your new hotkey combination</h3>
            <p id="hotkeyDisplay">Waiting for input...</p>
            <button class="btn btn-secondary" onclick="this.parentElement.parentElement.remove()">Cancel</button>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    let keys = [];
    
    document.addEventListener('keydown', (e) => {
        e.preventDefault();
        keys = [];
        if (e.ctrlKey) keys.push('Ctrl');
        if (e.altKey) keys.push('Alt');
        if (e.shiftKey) keys.push('Shift');
        if (e.metaKey) keys.push('Win');
        
        if (e.key !== 'Control' && e.key !== 'Alt' && e.key !== 'Shift' && e.key !== 'Meta') {
            keys.push(e.key.toUpperCase());
        }
        
        document.getElementById('hotkeyDisplay').textContent = keys.join(' + ');
    });
}

// ============================================
// WAKE WORD
// ============================================

function initializeWakeWord() {
    const wakeWordInput = document.getElementById('wakeWordInput');
    const listenBtn = document.querySelector('.wake-word-preview .btn-primary');
    const statusText = document.getElementById('wakeWordStatus');

    if (wakeWordInput) {
        const savedWakeWord = localStorage.getItem('voxylis_wakeword') || 'Voxy';
        wakeWordInput.value = savedWakeWord;
    }

    if (listenBtn) {
        listenBtn.addEventListener('click', () => {
            startWakeWordListening();
        });
    }

    // Save wake word button
    const saveWakeWordBtn = document.querySelector('.wake-word-config .btn-primary');
    if (saveWakeWordBtn) {
        saveWakeWordBtn.addEventListener('click', () => {
            const wakeWord = wakeWordInput.value;
            localStorage.setItem('voxylis_wakeword', wakeWord);
            Voxylis.Notification.show(`Wake word set to "${wakeWord}"`, 'success');
        });
    }
}

function startWakeWordListening() {
    const statusText = document.getElementById('wakeWordStatus');
    const listenBtn = document.querySelector('.wake-word-preview .btn-primary');
    
    statusText.textContent = '🎤 Listening...';
    listenBtn.disabled = true;
    
    // Simulate listening
    setTimeout(() => {
        statusText.textContent = '✓ Wake word detected!';
        listenBtn.disabled = false;
        
        setTimeout(() => {
            statusText.textContent = 'Ready to listen...';
        }, 2000);
    }, 3000);
}

// ============================================
// HISTORY
// ============================================

function initializeHistory() {
    const searchInput = document.querySelector('.search-input');
    const filterSelect = document.querySelector('.filter-select');
    const historyItems = document.querySelectorAll('.history-item');

    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            filterHistory(e.target.value, filterSelect?.value);
        });
    }

    if (filterSelect) {
        filterSelect.addEventListener('change', (e) => {
            filterHistory(searchInput?.value, e.target.value);
        });
    }

    // Copy button
    document.querySelectorAll('.history-item .btn-icon').forEach((btn, index) => {
        if (index % 2 === 0) { // Copy buttons
            btn.addEventListener('click', () => {
                const text = btn.parentElement.parentElement.querySelector('.history-text').textContent;
                navigator.clipboard.writeText(text);
                Voxylis.Notification.show('Copied to clipboard!', 'success');
            });
        } else { // Delete buttons
            btn.addEventListener('click', () => {
                btn.parentElement.parentElement.remove();
                Voxylis.Notification.show('Item deleted', 'success');
            });
        }
    });
}

function filterHistory(searchTerm, language) {
    const historyItems = document.querySelectorAll('.history-item');
    const term = (searchTerm || '').trim().toLowerCase();
    const lang = (language || '').trim().toLowerCase();
    
    historyItems.forEach(item => {
        const text = (item.querySelector('.history-text')?.textContent || '').toLowerCase();
        const meta = (item.querySelector('.history-meta')?.textContent || '').toLowerCase();
        
        const matchesSearch = !term || text.includes(term);
        const matchesLanguage = !lang || meta.includes(lang);
        
        item.style.display = (matchesSearch && matchesLanguage) ? 'flex' : 'none';
    });
}

// ============================================
// SUBSCRIPTION
// ============================================

function initializeSubscription() {
    const upgradeBtn = document.querySelector('.current-plan .btn-secondary');
    
    if (upgradeBtn) {
        upgradeBtn.addEventListener('click', () => {
            window.location.href = '/pricing';
        });
    }
}

// ============================================
// UTILITIES
// ============================================

// Auto-save functionality
function autoSaveSettings() {
    const settings = {
        theme: document.getElementById('themeSelect')?.value,
        language: document.getElementById('languageSelect')?.value,
        notifications: document.getElementById('notificationsToggle')?.checked,
        sound: document.getElementById('soundToggle')?.checked,
        autoStart: document.getElementById('autoStartToggle')?.checked
    };
    
    localStorage.setItem('voxylis_settings', JSON.stringify(settings));
}

// Periodic auto-save
setInterval(autoSaveSettings, 30000);

// Export data
function exportData() {
    const data = {
        settings: JSON.parse(localStorage.getItem('voxylis_settings') || '{}'),
        history: JSON.parse(localStorage.getItem('voxylis_history') || '[]'),
        timestamp: new Date().toISOString()
    };
    
    const dataStr = JSON.stringify(data, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `voxylis-data-${Date.now()}.json`;
    link.click();
}

// Import data
function importData(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
        try {
            const data = JSON.parse(e.target.result);
            localStorage.setItem('voxylis_settings', JSON.stringify(data.settings));
            localStorage.setItem('voxylis_history', JSON.stringify(data.history));
            Voxylis.Notification.show('Data imported successfully!', 'success');
            location.reload();
        } catch (error) {
            Voxylis.Notification.show('Error importing data', 'error');
        }
    };
    reader.readAsText(file);
}
