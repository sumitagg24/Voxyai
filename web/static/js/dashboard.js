// ============================================
// DASHBOARD JAVASCRIPT
// ============================================

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
    // Usage Chart
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
    
    historyItems.forEach(item => {
        const text = item.querySelector('.history-text').textContent.toLowerCase();
        const meta = item.querySelector('.history-meta').textContent.toLowerCase();
        
        const matchesSearch = text.includes(searchTerm.toLowerCase());
        const matchesLanguage = !language || meta.includes(language);
        
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
            window.location.href = 'index.html#pricing';
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

console.log('Dashboard initialized successfully');
