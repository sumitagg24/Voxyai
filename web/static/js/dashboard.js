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
            let stored = null;
            try { stored = localStorage.getItem('session_id'); } catch (e) {}
            if (!stored) return; // guests stay on the free tier: avoids a 401
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
            pro: ['transcription', 'enhancement_basic', 'enhancement_all', 'qa', 'advanced_stt', 'history', 'settings', 'hotkeys'],
            business: ['transcription', 'enhancement_basic', 'enhancement_all', 'qa', 'advanced_stt', 'api_access', 'team_features', 'custom_integrations', 'history', 'settings', 'hotkeys'],
            owner: ['transcription', 'enhancement_basic', 'enhancement_all', 'qa', 'advanced_stt', 'api_access', 'team_features', 'custom_integrations', 'history', 'settings', 'hotkeys', 'unlimited']
        };
        return feature in (features[this.tier] || features.free);
    }

    canUseMode(mode) {
        return this.enhancementModes[this.tier] && this.enhancementModes[this.tier].includes(mode);
    }

    applyTierUI() {
        // Gate enhancement mode chips. Locked chips keep full contrast and
        // announce the upgrade path (opacity dimming fails color-contrast).
        const chips = document.querySelectorAll('#modeChips .chip');
        chips.forEach(chip => {
            const mode = chip.dataset.mode;
            if (this.canUseMode(mode)) {
                chip.classList.remove('locked');
                chip.removeAttribute('title');
                chip.removeAttribute('aria-disabled');
            } else {
                chip.classList.add('locked');
                chip.title = 'Upgrade to Pro to use this mode';
                chip.setAttribute('aria-disabled', 'true');
            }
        });

        // Gate Q&A nav link (locked style, still navigable to the explainer)
        const qaNav = document.querySelector('[data-section="qa"]');
        if (qaNav && this.isFree()) {
            qaNav.classList.add('locked');
            qaNav.title = 'Upgrade to Pro to use Q&A';
            qaNav.setAttribute('aria-disabled', 'true');
        } else if (qaNav) {
            qaNav.classList.remove('locked');
            qaNav.removeAttribute('title');
            qaNav.removeAttribute('aria-disabled');
        }

        // Gate Q&A section content (built with DOM + classes, no inline styles,
        // so the strict CSP stays clean)
        const qaSection = document.getElementById('qa');
        if (qaSection && this.isFree()) {
            const form = qaSection.querySelector('.settings-form');
            if (form) {
                form.textContent = '';
                const wrap = document.createElement('div');
                wrap.className = 'tier-locked';
                const lock = document.createElement('div');
                lock.className = 'tier-locked-icon';
                lock.textContent = '🔒';
                const heading = document.createElement('h3');
                heading.textContent = 'Q&A requires a Pro plan';
                const sub = document.createElement('p');
                sub.textContent = 'Upgrade to ask questions about your transcriptions.';
                const link = document.createElement('a');
                link.href = '/pricing';
                link.className = 'btn btn-primary';
                link.textContent = 'View Plans';
                wrap.appendChild(lock);
                wrap.appendChild(heading);
                wrap.appendChild(sub);
                wrap.appendChild(link);
                form.appendChild(wrap);
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
                if (barEl) barEl.style.setProperty('--usage-pct', (s.usage ? s.usage.percentage : 0) + '%');
                if (badgeEl) {
                    badgeEl.textContent = s.tier ? s.tier.charAt(0).toUpperCase() + s.tier.slice(1) : 'Free';
                    badgeEl.className = 'tier-badge tier-' + (s.tier || 'free');
                }
                // Update manage button: hosted Dodo checkout when the backend
                // offers it, honest disabled copy when paid plans are
                // unavailable on this deployment.
                const btn = document.getElementById('managePlanBtn');
                const note = document.getElementById('planNote');
                const urls = s.checkout_urls || {};
                if (btn && s.tier === 'owner') {
                    btn.textContent = 'Owner Access';
                    btn.removeAttribute('href');
                    btn.classList.add('is-disabled');
                } else if (btn && s.checkout_available && (urls.pro || urls.business)) {
                    const target = s.tier === 'pro' ? (urls.business || urls.pro) : (urls.pro || urls.business);
                    let link = target;
                    // Best-effort email prefill for the hosted form; the
                    // parameter is ignored when the provider does not support it.
                    // Signed-in only: /api/me 401s for guests (console noise).
                    try {
                        var email = null;
                        if (hasStoredSession()) {
                            const meResp = await voxyFetch('/api/me');
                            const me = meResp && meResp.ok ? await meResp.json() : null;
                            email = me && me.user && me.user.email_or_phone;
                        }
                        if (email && email.indexOf('@') !== -1) link += (link.indexOf('?') === -1 ? '?' : '&') + 'email=' + encodeURIComponent(email);
                    } catch (e) { /* prefill is best-effort */ }
                    btn.textContent = s.tier === 'pro' ? 'Upgrade to Business' : 'Upgrade to Pro';
                    btn.href = link;
                    btn.classList.remove('is-disabled');
                    btn.removeAttribute('title');
                    if (note) note.textContent = '';
                } else if (btn && !s.checkout_available) {
                    btn.textContent = 'Paid plans unavailable';
                    btn.removeAttribute('href');
                    btn.classList.add('is-disabled');
                    btn.title = 'Paid plans are not purchasable yet on this deployment';
                    if (note) note.textContent = 'Paid plans are not purchasable yet on this deployment — no payment provider is connected, and no card details are collected.';
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
    // Button wiring lives in loadHotkeys() (backend-backed save flow).
    // showHotkeyRecorder() below stays available for callers that need a
    // bare capture modal.
}

function showHotkeyRecorder(index) {
    const modal = document.createElement('div');
    modal.className = 'modal';
    // Built with textContent/DOM (no inline onclick) so CSP needs no 'unsafe-inline'.
    const content = document.createElement('div');
    content.className = 'modal-content';
    const heading = document.createElement('h3');
    heading.textContent = 'Press your new hotkey combination';
    const display = document.createElement('p');
    display.id = 'hotkeyDisplay';
    display.textContent = 'Waiting for input...';
    const cancel = document.createElement('button');
    cancel.className = 'btn btn-secondary';
    cancel.textContent = 'Cancel';
    cancel.addEventListener('click', () => modal.remove());
    content.appendChild(heading);
    content.appendChild(display);
    content.appendChild(cancel);
    modal.appendChild(content);

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
// HISTORY PAGINATION (P6.3)
// ============================================

// Page size mirrors the server default (max 100). The render half lives in
// dashboard.html's live wiring block, which exposes window.appendHistoryItems;
// this controller owns the paging state and fetches the next page.
const HISTORY_PAGE_SIZE = 50;
const historyPager = { page: 0, hasMore: false, loading: false };

function updateLoadOlderButton() {
    const btn = document.getElementById('loadOlderHistory');
    if (!btn) return;
    btn.hidden = !historyPager.hasMore;
    btn.disabled = historyPager.loading;
    btn.textContent = historyPager.loading ? 'Loading…' : 'Load older';
}

window.HISTORY_PAGE_SIZE = HISTORY_PAGE_SIZE;
window.historyPager = historyPager;
window.updateLoadOlderButton = updateLoadOlderButton;

window.loadOlderHistory = async function () {
    if (historyPager.loading || !historyPager.hasMore) return;
    historyPager.loading = true;
    updateLoadOlderButton();
    const nextPage = historyPager.page + 1;
    try {
        const resp = await voxyFetch('/api/history?page=' + nextPage + '&page_size=' + HISTORY_PAGE_SIZE);
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) throw new Error(data.error || ('HTTP ' + resp.status));
        if (window.appendHistoryItems) window.appendHistoryItems(data.history || []);
        historyPager.page = nextPage;
        historyPager.hasMore = !!(data.pagination && data.pagination.has_more);
    } catch (e) {
        Voxylis.Notification.show('Could not load older history', 'error');
    } finally {
        historyPager.loading = false;
        updateLoadOlderButton();
    }
};

document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('loadOlderHistory');
    if (btn) btn.addEventListener('click', window.loadOlderHistory);
});

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
        
        item.classList.toggle('is-hidden', !(matchesSearch && matchesLanguage));
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

// ============================================
// DASHBOARD INITIALIZATION (live wiring)
// ============================================

// Hotkey recording
async function captureHotkey() {
    return new Promise((resolve) => {
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.innerHTML = `<div class="modal-content">
            <h3>Press your new hotkey combination</h3>
            <p id="hotkeyDisplay">Waiting for input… (Esc cancels)</p>
            <button class="btn btn-secondary" type="button">Cancel</button>
        </div>`;
        document.body.appendChild(modal);
        const done = (value) => {
            modal.remove();
            document.removeEventListener('keydown', onKey, true);
            resolve(value);
        };
        modal.querySelector('button').addEventListener('click', () => done(null));
        const onKey = (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            if (ev.key === 'Escape' || ev.key === 'Enter') { done(null); return; }
            if (['Control', 'Alt', 'Shift', 'Meta'].includes(ev.key)) return;
            const keys = [];
            if (ev.ctrlKey) keys.push('Ctrl');
            if (ev.altKey) keys.push('Alt');
            if (ev.shiftKey) keys.push('Shift');
            if (ev.metaKey) keys.push('Win');
            keys.push(ev.key.length === 1 ? ev.key.toUpperCase() : ev.key);
            const combo = keys.join('+');
            document.getElementById('hotkeyDisplay').textContent = combo;
            setTimeout(() => done(combo), 300);
        };
        document.addEventListener('keydown', onKey, true);
    });
}

async function initializeDashboard() {
    const notify = (window.Voxylis && window.Voxylis.Notification) || { show: function () {} };
    const form = document.getElementById("settingsForm");
    if (form) form.addEventListener("submit", function (e) { e.preventDefault(); });
    // Settings are per-account: only fetch when signed in (avoids 401 noise).
    if (hasStoredSession()) {
    try {
        const { settings } = await getJSON("/api/settings");
        if (document.getElementById("themeSelect")) document.getElementById("themeSelect").value = settings.theme;
        if (document.getElementById("languageSelect")) document.getElementById("languageSelect").value = settings.language;
        if (document.getElementById("notificationsToggle")) document.getElementById("notificationsToggle").checked = settings.notifications !== false;
        if (document.getElementById("soundToggle")) document.getElementById("soundToggle").checked = settings.sound !== false;
        if (document.getElementById("autoStartToggle")) document.getElementById("autoStartToggle").checked = settings.autoStart === true;
    } catch (e) { console.warn("settings load failed:", e); }
    }

    try {
        const { subscription } = await getJSON("/api/subscription");
        document.getElementById("planName").textContent = subscription.price
            ? `${subscription.plan} — $${subscription.price}/mo`
            : subscription.plan;
        document.getElementById("planRenewal").textContent = subscription.renewalDate
            ? `Renews ${new Date(subscription.renewalDate).toLocaleDateString()}`
            : (subscription.tier && subscription.tier !== 'free' ? '' : 'Free plan');
        document.getElementById("usageCount").textContent = `${subscription.usage.transcriptions} / ${subscription.usage.limit}`;
        document.getElementById("usageBar").style.setProperty('--usage-pct', `${subscription.usage.percentage}%`);
    } catch (e) { console.warn("subscription failed:", e); }

    document.getElementById("settingsSaveBtn").addEventListener("click", async (e) => {
        e.stopImmediatePropagation();
        const payload = {
            theme: document.getElementById("themeSelect").value,
            language: document.getElementById("languageSelect").value,
            notifications: document.getElementById("notificationsToggle").checked,
            sound: document.getElementById("soundToggle").checked,
            autoStart: document.getElementById("autoStartToggle").checked,
        };
        try {
            const res = await voxyFetch("/api/settings", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            try { localStorage.setItem('voxylis_theme', payload.theme); } catch (err) {}
            if (window.applyTheme) window.applyTheme(payload.theme);
            notify.show("Settings saved successfully!", "success");
        } catch (err) { notify.show("Failed to save settings", "error"); }
    });

    // Q&A
    const qaAskBtn = document.getElementById("qaAskBtn");
    if (qaAskBtn) qaAskBtn.addEventListener("click", async (e) => {
        e.stopImmediatePropagation();
        const q = document.getElementById("qaInput").value.trim();
        if (!q) { notify.show("Type a question first", "error"); return; }
        document.getElementById("qaAnswer").textContent = "Thinking…";
        try {
            const res = await voxyFetch("/api/qa", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ question: q }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
            document.getElementById("qaAnswer").textContent = data.answer;
        } catch (err) { document.getElementById("qaAnswer").textContent = `Error: ${err.message}`; }
    });

    // Initial loads
    await window.refreshStats();
    await window.refreshHistory();
    await loadHotkeys();

    // Logout
    const logoutBtn = document.getElementById("logoutBtn");
    if (logoutBtn) {
        logoutBtn.addEventListener("click", async (e) => {
            e.preventDefault();
            try {
                const sid = localStorage.getItem("session_id");
                if (sid) {
                    await voxyFetch("/api/auth/logout", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ session_id: sid }),
                    });
                }
            } catch (err) { /* logging out is best-effort client-side */ }
            localStorage.removeItem("session_id");
            window.location.href = "/auth";
        });
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', initializeDashboard);


// ============================================
// INLINE SCRIPTS MOVED FROM dashboard.html
// ============================================

// --- Inline script 1 ---
// Minimal notification shim (same API as main.js Notification)
    window.Voxylis = window.Voxylis || {};
    window.Voxylis.Notification = {
        show(message, type = "info", duration = 3000) {
            const el = document.createElement("div");
            el.className = "voxy-toast voxy-toast-" + (type === "success" || type === "error" ? type : "info");
            el.textContent = message;
            el.setAttribute("role", "status");
            document.body.appendChild(el);
            setTimeout(() => el.remove(), duration);
        },
    };

// --- Inline script 2 ---
// Voice-agent stage: mic orb + live waveform + speech-to-text + Q&A.
    (function () {
        const orb = document.getElementById("micOrb");
        const wrap = document.getElementById("orbWrap");
        const pill = document.getElementById("agentStatus");
        const pillText = document.getElementById("agentStatusText");
        const canvas = document.getElementById("waveCanvas");
        const ctx = canvas.getContext("2d");
        const stream = document.getElementById("transcriptStream");
        const askBtn = document.getElementById("askTranscriptBtn");
        const copyBtn = document.getElementById("copyTranscriptBtn");
        const notify = window.Voxylis.Notification;
        let listening = false;
        let audioCtx = null, analyser = null, micStream = null, rafId = null;
        let recognizer = null, liveBubble = null, lastFinal = "";
        let mediaRecorder = null, audioChunks = [], pendingAudio = null;

        function hasSession() {
            try { return !!localStorage.getItem('session_id'); } catch (e) { return false; }
        }

        function currentMode() {
            const c = document.querySelector('#modeChips .chip.active');
            return c ? c.dataset.mode : 'formal';
        }

        // --- Real cloud transcription path: MediaRecorder -> 16kHz mono WAV -> /api/transcribe ---
        function startRecorder(stream) {
            audioChunks = [];
            let rec = null;
            try {
                const mime = (window.MediaRecorder && MediaRecorder.isTypeSupported('audio/webm')) ? 'audio/webm' : '';
                rec = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
            } catch (e) { notify.show("Recording not supported in this browser", "error"); return false; }
            mediaRecorder = rec;
            mediaRecorder.ondataavailable = (e) => { if (e.data && e.data.size) audioChunks.push(e.data); };
            pendingAudio = new Promise((resolve) => {
                mediaRecorder.onstop = () => resolve(new Blob(audioChunks, { type: mediaRecorder.mimeType || 'audio/webm' }));
            });
            try { mediaRecorder.start(250); } catch (e) { return false; }
            return true;
        }

        function stopRecorder() {
            if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                try { mediaRecorder.stop(); } catch (e) {}
            }
            mediaRecorder = null;
        }

        function floatTo16BitPCM(view, offset, input) {
            for (let i = 0; i < input.length; i++, offset += 2) {
                const s = Math.max(-1, Math.min(1, input[i]));
                view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
            }
        }

        function encodeWAV(samples, sampleRate) {
            const buffer = new ArrayBuffer(44 + samples.length * 2);
            const view = new DataView(buffer);
            const writeStr = (o, s) => { for (let i = 0; i < s.length; i++) view.setUint8(o + i, s.charCodeAt(i)); };
            writeStr(0, 'RIFF'); view.setUint32(4, 36 + samples.length * 2, true); writeStr(8, 'WAVE');
            writeStr(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
            view.setUint16(22, 1, true); view.setUint32(24, sampleRate, true);
            view.setUint32(28, sampleRate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
            writeStr(36, 'data'); view.setUint32(40, samples.length * 2, true);
            floatTo16BitPCM(view, 44, samples);
            return new Blob([view], { type: 'audio/wav' });
        }

        async function blobToMono16k(blob) {
            const AC = window.AudioContext || window.webkitAudioContext;
            const tmpCtx = new AC();
            try {
                const buf = await blob.arrayBuffer();
                const audioBuf = await tmpCtx.decodeAudioData(buf);
                const targetRate = 16000;
                const ratio = audioBuf.sampleRate / targetRate;
                const len = Math.max(1, Math.floor(audioBuf.length / ratio));
                const out = new Float32Array(len);
                const ch0 = audioBuf.getChannelData(0);
                const ch1 = audioBuf.numberOfChannels > 1 ? audioBuf.getChannelData(1) : null;
                for (let i = 0; i < len; i++) {
                    const idx = Math.min(ch0.length - 1, Math.floor(i * ratio));
                    out[i] = ch1 ? (ch0[idx] + ch1[idx]) / 2 : ch0[idx];
                }
                return encodeWAV(out, targetRate);
            } finally { try { tmpCtx.close(); } catch (e) {} }
        }

        async function transcribeWithBackend(wavBlob) {
            const fd = new FormData();
            fd.append('audio', wavBlob, 'recording.wav');
            fd.append('mode', 'PUSH_TO_TALK');
            const res = await voxyFetch('/api/transcribe', { method: 'POST', body: fd });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const err = new Error(data.error || ('HTTP ' + res.status));
                err.status = res.status;
                throw err;
            }
            return data;
        }

        async function finishBackendTranscription() {
            setStatus("processing", "Transcribing…");
            try {
                const blob = await pendingAudio;
                if (!blob || !blob.size) throw new Error("No audio captured — mic may be blocked.");
                const wav = await blobToMono16k(blob);
                const data = await transcribeWithBackend(wav);
                lastFinal = data.transcript;
                addBubble(data.transcript + (data.provider ? `  [${data.provider}]` : ""), "user");
                askBtn.disabled = false;
                copyBtn.disabled = false;
                try {
                    await voxyFetch('/api/history', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ text: data.transcript, mode: currentMode(), language: 'en' }),
                    });
                } catch (e) { /* history save is best-effort */ }
                if (window.refreshHistory) { try { await window.refreshHistory(); } catch (e) {} }
                if (window.refreshStats) { try { await window.refreshStats(); } catch (e) {} }
                setStatus("", "Ready — tap the orb to talk");
                notify.show("Transcription saved to history", "success");
            } catch (e) {
                if (e && e.status === 401) {
                    addBubble("Please sign in to use cloud transcription.", "agent");
                    if (window.showLoginBanner) window.showLoginBanner();
                } else if (e && e.status === 403) {
                    addBubble("Transcription blocked: " + e.message, "agent");
                } else if (e && e.status === 503) {
                    addBubble("Speech service is offline (no API key on server). " + (lastFinal ? "Browser transcript kept below." : "Sign in and try the desktop app instead."), "agent");
                } else {
                    addBubble("Transcription failed: " + (e && e.message ? e.message : e), "agent");
                }
                setStatus("", "Ready — tap the orb to talk");
            } finally {
                pendingAudio = null;
            }
        }

        function setStatus(mode, text) {
            pill.classList.remove("listening", "processing");
            if (mode) pill.classList.add(mode);
            pillText.textContent = text;
        }

        function addBubble(text, who, live) {
            const div = document.createElement("div");
            div.className = "bubble " + who + (live ? " live" : "");
            div.textContent = text;
            stream.appendChild(div);
            stream.scrollTop = stream.scrollHeight;
            return div;
        }

        function drawWave(data) {
            const W = canvas.width, H = canvas.height, mid = H / 2;
            ctx.clearRect(0, 0, W, H);
            ctx.fillStyle = "#7c6cff";
            const n = 64, bw = W / n;
            for (let i = 0; i < n; i++) {
                const v = data ? data[i] / 255 : 0.06 + 0.05 * Math.abs(Math.sin(Date.now() / 350 + i * 0.55));
                const h = Math.max(3, v * H * 0.92);
                const x = i * bw + bw * 0.2;
                ctx.globalAlpha = 0.35 + 0.65 * (v || 0.1);
                ctx.fillRect(x, mid - h / 2, bw * 0.6, h);
            }
            ctx.globalAlpha = 1;
        }

        function loop() {
            if (!listening) return;
            if (analyser) {
                const arr = new Uint8Array(analyser.frequencyBinCount);
                analyser.getByteFrequencyData(arr);
                drawWave(arr.slice(0, 64));
            } else {
                drawWave(null); // simulated idle motion
            }
            rafId = requestAnimationFrame(loop);
        }

        async function startAudio() {
            try {
                micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                const src = audioCtx.createMediaStreamSource(micStream);
                analyser = audioCtx.createAnalyser();
                analyser.fftSize = 256;
                src.connect(analyser);
                return true;
            } catch (e) {
                analyser = null; // fall back to simulated waveform
                return false;
            }
        }

        function startSpeech() {
            const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SR) {
                addBubble("Live transcription needs Chrome or Edge. The waveform still visualizes your mic — use Win+Shift on desktop for full dictation.", "agent");
                return;
            }
            recognizer = new SR();
            recognizer.continuous = true;
            recognizer.interimResults = true;
            recognizer.onresult = (ev) => {
                let interim = "";
                for (let i = ev.resultIndex; i < ev.results.length; i++) {
                    const t = ev.results[i][0].transcript;
                    if (ev.results[i].isFinal) {
                        if (liveBubble) { liveBubble.remove(); liveBubble = null; }
                        lastFinal = (lastFinal + " " + t).trim();
                        addBubble(t.trim(), "user");
                        askBtn.disabled = false;
                        copyBtn.disabled = false;
                    } else {
                        interim += t;
                    }
                }
                if (interim) {
                    if (!liveBubble) liveBubble = addBubble("", "user", true);
                    liveBubble.textContent = interim;
                }
            };
            recognizer.onerror = () => {};
            try { recognizer.start(); } catch (e) {}
        }

        function stopAll() {
            listening = false;
            cancelAnimationFrame(rafId);
            stopRecorder(); // resolves pendingAudio with the captured clip
            if (recognizer) { try { recognizer.stop(); } catch (e) {} recognizer = null; }
            if (micStream) { micStream.getTracks().forEach((t) => t.stop()); micStream = null; }
            if (audioCtx) { audioCtx.close().catch(() => {}); audioCtx = null; analyser = null; }
            if (liveBubble && !liveBubble.textContent) { liveBubble.remove(); }
            liveBubble = null;
            wrap.classList.remove("live");
            drawWave(null);
        }

        orb.addEventListener("click", async () => {
            if (listening) {
                const wasBackend = hasSession();
                const recBubble = liveBubble;
                stopAll();
                if (wasBackend) {
                    // Remove the "Recording…" placeholder; the real transcript bubble follows.
                    if (recBubble && recBubble.parentNode) recBubble.remove();
                    liveBubble = null;
                    await finishBackendTranscription();
                } else {
                    setStatus("", "Ready — tap the orb to talk");
                }
                return;
            }
            listening = true;
            lastFinal = "";
            wrap.classList.add("live");
            setStatus("listening", "Listening… speak now (tap orb to stop)");
            const micOk = await startAudio();
            if (!micOk) notify.show("Mic blocked — showing simulated waveform", "error");
            if (hasSession()) {
                // Logged in: capture audio for real cloud transcription on stop.
                if (micOk && micStream && startRecorder(micStream)) {
                    liveBubble = addBubble("Recording… tap the orb to stop", "user", true);
                } else {
                    addBubble("Mic recording unavailable — falling back to browser transcription.", "agent");
                    startSpeech();
                }
            } else {
                // Logged out: free browser transcription demo (Chrome/Edge).
                startSpeech();
            }
            loop();
        });

        copyBtn.addEventListener("click", () => {
            if (!lastFinal) return;
            navigator.clipboard.writeText(lastFinal);
            notify.show("Transcript copied!", "success");
        });

        askBtn.addEventListener("click", async () => {
            if (!lastFinal) return;
            setStatus("processing", "Voxylis is thinking…");
            try {
                const res = await voxyFetch("/api/qa", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ question: lastFinal }),
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || "HTTP " + res.status);
                addBubble(data.answer, "agent");
            } catch (e) {
                addBubble("Sorry — I could not answer that: " + e.message, "agent");
            }
            setStatus(listening ? "listening" : "", listening ? "Listening… speak now (tap orb to stop)" : "Ready — tap the orb to talk");
        });

        document.getElementById("modeChips").addEventListener("click", async (e) => {
            const chip = e.target.closest(".chip");
            if (!chip) return;
            if (chip.classList.contains("locked")) {
                notify.show("Upgrade to Pro to use this mode", "error");
                return;
            }
            document.querySelectorAll("#modeChips .chip").forEach((c) => c.classList.remove("active"));
            chip.classList.add("active");
            try {
                await voxyFetch("/api/settings", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ enhancement_mode: chip.dataset.mode }),
                });
                notify.show(`Enhancement mode: ${chip.dataset.mode}`, "success");
            } catch (err) {
                notify.show("Could not save mode", "error");
            }
        });

        drawWave(null);
    })();

// ============================================
// LIVE API WIRING (backend-backed sections)
// ============================================
// Session-aware helpers. Authed endpoints (settings/history/hotkeys) are
// only fetched when a session exists, so logged-out visitors never trigger
// failing requests. Public endpoints (stats/subscription) always load.

function hasStoredSession() {
    try { return !!localStorage.getItem('session_id'); } catch (e) { return false; }
}

async function getJSON(url) {
    var sid = '';
    try { sid = localStorage.getItem('session_id') || ''; } catch (e) {}
    var res = await fetch((window.VOXYLIS_API_BASE || '') + url, {
        headers: sid ? { 'X-Session-Id': sid } : {},
    });
    if (!res.ok) throw new Error(url + ': HTTP ' + res.status);
    return res.json();
}

window.showLoginBanner = function () {
    if (document.getElementById('loginBanner')) return;
    var main = document.querySelector('.dashboard-content');
    if (!main) return;
    var div = document.createElement('div');
    div.id = 'loginBanner';
    div.className = 'login-banner';
    var text = document.createElement('span');
    text.textContent = 'Browsing as a guest \u2014 stats, history, Q&A and cloud transcription need an account. ';
    var link = document.createElement('a');
    link.href = '/auth';
    link.className = 'login-banner-link';
    link.textContent = 'Sign in';
    div.appendChild(text);
    div.appendChild(link);
    main.prepend(div);
};

function renderCharts(stats, history) {
    if (typeof Chart === 'undefined') return;
    var weekly = (stats && stats.weekly) || { labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], counts: [0, 0, 0, 0, 0, 0, 0] };
    var usageEl = document.getElementById('usageChart');
    if (usageEl) {
        var prev = Chart.getChart(usageEl);
        if (prev) prev.destroy();
        new Chart(usageEl, {
            type: 'line',
            data: {
                labels: weekly.labels,
                datasets: [{
                    label: 'Transcriptions',
                    data: weekly.counts,
                    borderColor: '#6366f1',
                    backgroundColor: 'rgba(99, 102, 241, 0.1)',
                    tension: 0.4,
                    fill: true,
                }],
            },
            options: {
                responsive: true,
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
            },
        });
    }
    var langEl = document.getElementById('languagesChart');
    if (langEl) {
        var counts = {};
        (history || []).forEach(function (h) {
            var k = h.language || 'Unknown';
            counts[k] = (counts[k] || 0) + 1;
        });
        var entries = Object.entries(counts).sort(function (a, b) { return b[1] - a[1]; });
        var top = entries.slice(0, 4);
        var rest = entries.slice(4).reduce(function (s, en) { return s + en[1]; }, 0);
        if (rest) top.push(['Others', rest]);
        var prev2 = Chart.getChart(langEl);
        if (prev2) prev2.destroy();
        new Chart(langEl, {
            type: 'doughnut',
            data: {
                labels: top.length ? top.map(function (t) { return t[0]; }) : ['No data yet'],
                datasets: [{
                    data: top.length ? top.map(function (t) { return t[1]; }) : [1],
                    backgroundColor: ['#6366f1', '#ec4899', '#f59e0b', '#10b981', '#8b5cf6'],
                }],
            },
            options: { responsive: true, plugins: { legend: { position: 'bottom' } } },
        });
    }
    window.__chartsReal = true;
}

window.refreshStats = async function () {
    try {
        var payload = await getJSON('/api/stats');
        var stats = payload.stats || payload;
        document.getElementById('statTranscriptions').textContent = stats.transcriptions;
        document.getElementById('statTime').textContent = stats.totalTime;
        document.getElementById('statLanguages').textContent = stats.languages;
        document.getElementById('statEnhancements').textContent = stats.enhancements;
        var hist = { history: [] };
        if (hasStoredSession()) {
            try { hist = await getJSON('/api/history'); } catch (e) { /* logged out */ }
        }
        renderCharts(stats, hist.history || []);
    } catch (e) { console.warn('stats failed:', e); }
};

// Append one page of history entries. Rendered with textContent only (stored
// strings are raw, escaped at render time).
window.appendHistoryItems = function (history) {
    var notify = (window.Voxylis && window.Voxylis.Notification) || { show: function () {} };
    var list = document.getElementById('historyList');
    if (!list) return;
    (history || []).forEach(function (h) {
        var item = document.createElement('div');
        item.className = 'history-item';
        item.dataset.id = String(h.id);
        var left = document.createElement('div');
        var text = document.createElement('p');
        text.className = 'history-text';
        text.textContent = h.text || '';
        var meta = document.createElement('p');
        meta.className = 'history-meta';
        var when = h.timestamp ? new Date(h.timestamp).toLocaleString() : '';
        meta.textContent = (h.language || '') + ' \u00b7 ' + (h.mode || '') + ' \u00b7 ' + when + (h.enhanced ? ' \u00b7 \u2728' : '');
        left.appendChild(text);
        left.appendChild(meta);
        var actions = document.createElement('div');
        var copyBtn = document.createElement('button');
        copyBtn.className = 'btn btn-icon';
        copyBtn.type = 'button';
        copyBtn.textContent = '\u29c9';
        copyBtn.setAttribute('aria-label', 'Copy entry');
        copyBtn.addEventListener('click', function () {
            navigator.clipboard.writeText(text.textContent);
            notify.show('Copied to clipboard!', 'success');
        });
        var delBtn = document.createElement('button');
        delBtn.className = 'btn btn-icon';
        delBtn.type = 'button';
        delBtn.textContent = '\ud83d\uddd1';
        delBtn.setAttribute('aria-label', 'Delete entry');
        delBtn.addEventListener('click', async function () {
            try {
                var res = await voxyFetch('/api/history/' + item.dataset.id, { method: 'DELETE' });
                var data = await res.json().catch(function () { return {}; });
                if (!res.ok) throw new Error(data.error || ('HTTP ' + res.status));
                item.remove();
                notify.show('Item deleted', 'success');
                if (window.refreshStats) { try { await window.refreshStats(); } catch (e) {} }
            } catch (e) {
                notify.show('Delete failed: ' + e.message, 'error');
            }
        });
        actions.appendChild(copyBtn);
        actions.appendChild(delBtn);
        item.appendChild(left);
        item.appendChild(actions);
        list.appendChild(item);
    });
};

window.refreshHistory = async function () {
    var list = document.getElementById('historyList');
    if (!list) return;
    if (!hasStoredSession()) {
        list.textContent = '';
        var msg = document.createElement('p');
        msg.className = 'help-text';
        msg.textContent = 'Sign in to see your transcription history.';
        list.appendChild(msg);
        if (window.historyPager) {
            window.historyPager.page = 0;
            window.historyPager.hasMore = false;
        }
        if (window.updateLoadOlderButton) window.updateLoadOlderButton();
        return;
    }
    var pageSize = window.HISTORY_PAGE_SIZE || 50;
    try {
        var data = await getJSON('/api/history?page=1&page_size=' + pageSize);
        list.textContent = '';
        window.appendHistoryItems(data.history || []);
        if (window.historyPager) {
            window.historyPager.page = 1;
            window.historyPager.hasMore = !!(data.pagination && data.pagination.has_more);
        }
        if (window.updateLoadOlderButton) window.updateLoadOlderButton();
    } catch (e) { console.warn('history failed:', e); }
};

async function loadHotkeys() {
    var notify = (window.Voxylis && window.Voxylis.Notification) || { show: function () {} };
    var list = document.getElementById('hotkeysList');
    if (!list) return;
    var hotkeys = null;
    if (hasStoredSession()) {
        try {
            var res = await voxyFetch('/api/hotkeys');
            if (res.ok) {
                var data = await res.json();
                hotkeys = data.hotkeys || data;
            }
        } catch (e) { /* offline: fall through to defaults */ }
    }
    var labels = { record: 'Record', casual: 'Casual mode', technical: 'Technical mode', settings: 'Settings' };
    var names = (hotkeys && Object.keys(hotkeys).length ? Object.keys(hotkeys) : Object.keys(labels));
    list.textContent = '';
    if (!hasStoredSession()) {
        var note = document.createElement('p');
        note.className = 'help-text';
        note.textContent = 'Sign in to sync shortcuts across devices. Defaults shown below.';
        list.appendChild(note);
    }
    var defaults = { record: 'Win+Shift', casual: 'Win+Alt', technical: 'Win+Ctrl', settings: 'Win+;' };
    names.forEach(function (name) {
        var combo = (hotkeys && hotkeys[name]) || defaults[name] || '';
        var item = document.createElement('div');
        item.className = 'hotkey-item';
        var info = document.createElement('div');
        info.className = 'hotkey-info';
        var title = document.createElement('h3');
        title.textContent = labels[name] || name;
        var sub = document.createElement('p');
        sub.textContent = combo;
        info.appendChild(title);
        info.appendChild(sub);
        var btn = document.createElement('button');
        btn.className = 'btn btn-secondary';
        btn.type = 'button';
        btn.textContent = 'Change';
        btn.setAttribute('aria-label', 'Change ' + (labels[name] || name) + ' shortcut');
        btn.addEventListener('click', async function () {
            var next = await captureHotkey();
            if (!next) return;
            sub.textContent = next;
            if (!hasStoredSession()) return;
            try {
                var payload = {};
                payload[name] = next;
                var save = await voxyFetch('/api/hotkeys', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });
                var saved = await save.json().catch(function () { return {}; });
                if (!save.ok) throw new Error(saved.error || saved.message || ('HTTP ' + save.status));
                notify.show('Hotkey saved: ' + next, 'success');
            } catch (err) { notify.show('Could not save hotkey: ' + err.message, 'error'); }
        });
        item.appendChild(info);
        item.appendChild(btn);
        list.appendChild(item);
    });
}