# Voxylis - Enhanced Features Implementation Guide

## Overview
This guide covers the implementation of new features for Voxylis v2.1:
1. Voice command improvements (no sound lag)
2. Custom wake word system
3. Mouse click activation
4. Web interface & dashboard
5. Q&A feature
6. Customizable hotkeys
7. Pricing/subscription system
8. Cross-platform builds (macOS & Windows)

---

## Phase 1: Voice Command Improvements

### 1.1 Remove Sound Lag
**File:** `core/voice_commands.py`

```python
# Implement async processing to eliminate lag
import asyncio
from concurrent.futures import ThreadPoolExecutor

class VoiceCommandProcessor:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.command_queue = asyncio.Queue()
    
    async def process_command_async(self, text):
        """Process voice commands without blocking"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._process_command,
            text
        )
    
    def _process_command(self, text):
        """Actual command processing"""
        # Fast command matching
        if self._match_command(text):
            return self._execute_command(text)
        return None
```

### 1.2 Removed Voice Commands
**Removed:**
- "remove text" - Too confusing
- "next line" - Ambiguous
- "next point" - Unclear

**Kept:**
- "undo" - Clear action
- "clear that" - Specific
- "new paragraph" - Explicit

---

## Phase 2: Custom Wake Word System

### 2.1 Wake Word Configuration
**File:** `core/wake_word_detector.py` (NEW)

```python
import speech_recognition as sr
from config.constants import DEFAULT_WAKE_WORD

class WakeWordDetector:
    def __init__(self, wake_word="Voxy", sensitivity=0.7):
        self.wake_word = wake_word.lower()
        self.sensitivity = sensitivity
        self.recognizer = sr.Recognizer()
        self.is_listening = False
    
    def listen_for_wake_word(self):
        """Listen for custom wake word"""
        with sr.Microphone() as source:
            try:
                audio = self.recognizer.listen(source, timeout=5)
                text = self.recognizer.recognize_google(audio).lower()
                
                # Fuzzy matching for wake word
                if self._fuzzy_match(text, self.wake_word):
                    return True
            except sr.UnknownValueError:
                pass
        return False
    
    def _fuzzy_match(self, text, wake_word):
        """Fuzzy matching with sensitivity threshold"""
        from difflib import SequenceMatcher
        ratio = SequenceMatcher(None, text, wake_word).ratio()
        return ratio >= self.sensitivity
    
    def set_wake_word(self, new_word):
        """Update wake word"""
        self.wake_word = new_word.lower()
        self._save_to_config()
    
    def _save_to_config(self):
        """Save wake word to config"""
        import json
        with open('config/settings.json', 'r') as f:
            config = json.load(f)
        config['wake_word'] = self.wake_word
        with open('config/settings.json', 'w') as f:
            json.dump(config, f, indent=2)
```

### 2.2 Integration with Main App
**File:** `core/app_orchestrator.py`

```python
# Add to AppOrchestrator.__init__
self.wake_word_detector = WakeWordDetector(
    wake_word=config.get('wake_word', 'Voxy'),
    sensitivity=config.get('wake_word_sensitivity', 0.7)
)

# Add method to start wake word listening
def start_wake_word_listening(self):
    """Start listening for wake word"""
    while self.running:
        if self.wake_word_detector.listen_for_wake_word():
            self.start_recording()
```

---

## Phase 3: Mouse Click Activation

### 3.1 Minion Widget Click Handler
**File:** `ui/overlay.py`

```python
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, pyqtSignal

class FloatingWidget(QWidget):
    recording_requested = pyqtSignal()
    
    def mousePressEvent(self, event):
        """Handle mouse click on widget"""
        if event.button() == Qt.LeftButton:
            self.recording_requested.emit()
            self.toggle_recording()
    
    def toggle_recording(self):
        """Toggle recording state"""
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()
    
    def start_recording(self):
        """Start recording animation"""
        self.is_recording = True
        self.animate_recording()
    
    def animate_recording(self):
        """Animate minion during recording"""
        # Pulse animation
        # Eye blinking
        # Mouth movement
        pass
```

---

## Phase 4: Web Interface

### 4.1 Website Structure
```
web/
├── index.html              # Landing page
├── dashboard.html          # User dashboard
├── docs/
│   ├── installation.html
│   ├── configuration.html
│   ├── voice-commands.html
│   ├── qa-feature.html
│   ├── troubleshooting.html
│   └── tips-tricks.html
├── css/
│   ├── style.css          # Main styles
│   ├── animations.css     # Animations
│   ├── dashboard.css      # Dashboard styles
│   └── docs.css           # Documentation styles
└── js/
    ├── main.js            # Main functionality
    └── dashboard.js       # Dashboard logic
```

### 4.2 Backend API (Flask)
**File:** `web/app.py` (NEW)

```python
from flask import Flask, jsonify, request
from flask_cors import CORS
import json

app = Flask(__name__)
CORS(app)

# API Routes
@app.route('/api/features', methods=['GET'])
def get_features():
    """Get all features"""
    return jsonify({
        'features': [
            'Voice-to-Text',
            'AI Enhancement',
            'Wake Word',
            'Q&A',
            'Custom Hotkeys'
        ]
    })

@app.route('/api/settings', methods=['GET', 'POST'])
def settings():
    """Get/update user settings"""
    if request.method == 'POST':
        data = request.json
        # Save settings
        return jsonify({'status': 'saved'})
    else:
        # Load settings
        return jsonify({})

@app.route('/api/qa', methods=['POST'])
def qa_endpoint():
    """Q&A feature endpoint"""
    question = request.json.get('question')
    answer = get_answer(question)
    return jsonify({'answer': answer})

def get_answer(question):
    """Get answer to question using AI"""
    # Implement Q&A logic
    pass

if __name__ == '__main__':
    app.run(debug=False, port=5000)
```

---

## Phase 5: Q&A Feature

### 5.1 Q&A System
**File:** `ai/qa_engine.py` (NEW)

```python
from openai import OpenAI

class QAEngine:
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)
    
    def get_answer(self, question, context=""):
        """Get answer to question"""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant. Provide concise, accurate answers."
                    },
                    {
                        "role": "user",
                        "content": question
                    }
                ],
                max_tokens=150,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error: {str(e)}"
    
    def display_answer(self, answer):
        """Display answer on screen"""
        # Show answer in overlay
        # Auto-hide after 5 seconds
        pass
```

### 5.2 Integration with UI
**File:** `ui/overlay.py`

```python
class FloatingWidget(QWidget):
    def show_qa_answer(self, answer):
        """Display Q&A answer"""
        self.answer_label = QLabel(answer)
        self.answer_label.setStyleSheet("""
            background: white;
            border: 2px solid #6366f1;
            border-radius: 8px;
            padding: 15px;
            font-size: 14px;
        """)
        self.answer_label.show()
        
        # Auto-hide after 5 seconds
        QTimer.singleShot(5000, self.answer_label.hide)
```

---

## Phase 6: Customizable Hotkeys

### 6.1 Hotkey Manager
**File:** `core/hotkey_manager.py` (NEW)

```python
from pynput import keyboard
import json

class HotkeyManager:
    def __init__(self):
        self.hotkeys = self._load_hotkeys()
        self.listener = None
    
    def _load_hotkeys(self):
        """Load hotkeys from config"""
        with open('config/settings.json', 'r') as f:
            config = json.load(f)
        return config.get('hotkeys', {
            'record': 'win+shift',
            'casual': 'win+alt',
            'technical': 'win+ctrl'
        })
    
    def register_hotkey(self, name, key_combo, callback):
        """Register a hotkey"""
        # Parse key combination
        # Register with pynput
        pass
    
    def update_hotkey(self, name, new_combo):
        """Update hotkey"""
        self.hotkeys[name] = new_combo
        self._save_hotkeys()
    
    def _save_hotkeys(self):
        """Save hotkeys to config"""
        with open('config/settings.json', 'r') as f:
            config = json.load(f)
        config['hotkeys'] = self.hotkeys
        with open('config/settings.json', 'w') as f:
            json.dump(config, f, indent=2)
```

---

## Phase 7: Pricing & Subscription

### 7.1 Subscription System
**File:** `web/subscription.py` (NEW)

```python
import stripe
from datetime import datetime, timedelta

class SubscriptionManager:
    def __init__(self, stripe_key):
        stripe.api_key = stripe_key
    
    def create_subscription(self, customer_id, plan_id):
        """Create subscription"""
        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{'price': plan_id}]
        )
        return subscription
    
    def get_subscription_status(self, subscription_id):
        """Get subscription status"""
        subscription = stripe.Subscription.retrieve(subscription_id)
        return {
            'status': subscription.status,
            'current_period_end': subscription.current_period_end,
            'plan': subscription.items.data[0].price.product
        }
    
    def cancel_subscription(self, subscription_id):
        """Cancel subscription"""
        stripe.Subscription.delete(subscription_id)
```

### 7.2 Pricing Tiers
```
Free:
- 100 transcriptions/month
- 5 languages
- Basic enhancement
- $0/month

Pro:
- Unlimited transcriptions
- 99+ languages
- All enhancement modes
- Live Q&A
- Custom wake word
- $9.99/month

Business:
- Everything in Pro
- Team collaboration
- API access
- Custom integrations
- Dedicated support
- $29.99/month
```

---

## Phase 8: Cross-Platform Builds

### 8.1 Windows Build
**File:** `build_windows.spec`

```python
# PyInstaller spec for Windows
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config/', 'config'),
        ('web/', 'web'),
    ],
    hiddenimports=[
        'PyQt5',
        'sounddevice',
        'openai',
        'pynput',
    ],
    ...
)
```

### 8.2 macOS Build
**File:** `build_macos.spec`

```python
# PyInstaller spec for macOS
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config/', 'config'),
        ('web/', 'web'),
    ],
    ...
)

# macOS-specific settings
app = BUNDLE(
    exe,
    name='Voxylis.app',
    icon='assets/icon.icns',
    bundle_identifier='com.voxylis.app',
    ...
)
```

### 8.3 Build Commands
```bash
# Windows
pyinstaller build_windows.spec

# macOS
pyinstaller build_macos.spec

# Create installers
# Windows: Use NSIS
# macOS: Use create-dmg
```

---

## Implementation Checklist

### Phase 1: Voice Commands
- [ ] Remove sound lag with async processing
- [ ] Remove confusing commands
- [ ] Test voice command accuracy
- [ ] Optimize performance

### Phase 2: Wake Word
- [ ] Implement wake word detector
- [ ] Add fuzzy matching
- [ ] Create settings UI
- [ ] Test with various accents

### Phase 3: Mouse Activation
- [ ] Add click handler to minion widget
- [ ] Implement recording animation
- [ ] Test on Windows and macOS
- [ ] Add visual feedback

### Phase 4: Web Interface
- [ ] Create landing page
- [ ] Build dashboard
- [ ] Implement documentation
- [ ] Add responsive design
- [ ] Test on mobile

### Phase 5: Q&A Feature
- [ ] Implement Q&A engine
- [ ] Add to UI overlay
- [ ] Create API endpoint
- [ ] Test accuracy

### Phase 6: Hotkeys
- [ ] Create hotkey manager
- [ ] Add customization UI
- [ ] Test all combinations
- [ ] Save to config

### Phase 7: Subscription
- [ ] Integrate Stripe
- [ ] Create pricing page
- [ ] Implement subscription logic
- [ ] Add license validation

### Phase 8: Cross-Platform
- [ ] Build Windows executable
- [ ] Build macOS app
- [ ] Create installers
- [ ] Test on both platforms

---

## Testing Strategy

### Unit Tests
```python
# Test voice commands
def test_voice_command_processing():
    processor = VoiceCommandProcessor()
    result = processor.process_command("undo")
    assert result == "undo_action"

# Test wake word
def test_wake_word_detection():
    detector = WakeWordDetector("Voxy")
    assert detector._fuzzy_match("voxy", "voxy") >= 0.7
```

### Integration Tests
- Test hotkey registration
- Test Q&A feature
- Test subscription validation
- Test cross-platform compatibility

### User Acceptance Tests
- Test on real microphones
- Test with various accents
- Test on different networks
- Test subscription flow

---

## Deployment

### Release Checklist
- [ ] All tests passing
- [ ] Documentation complete
- [ ] Builds tested on both platforms
- [ ] Pricing page live
- [ ] API endpoints tested
- [ ] Subscription system working
- [ ] Support documentation ready

### Version: 2.1.0
- Release Date: June 2026
- Features: All above
- Breaking Changes: None
- Migration Guide: Not needed

---

## Support & Maintenance

### Monitoring
- Track API usage
- Monitor error rates
- Check subscription status
- Monitor user feedback

### Updates
- Monthly feature updates
- Security patches as needed
- Performance optimizations
- User-requested features

---

## Timeline

| Phase | Duration | Status |
|-------|----------|--------|
| Phase 1 | 1 week | Planned |
| Phase 2 | 1 week | Planned |
| Phase 3 | 3 days | Planned |
| Phase 4 | 2 weeks | Planned |
| Phase 5 | 1 week | Planned |
| Phase 6 | 1 week | Planned |
| Phase 7 | 2 weeks | Planned |
| Phase 8 | 1 week | Planned |
| **Total** | **~8 weeks** | **Planned** |

---

## Resources

- [PyQt5 Documentation](https://www.riverbankcomputing.com/static/Docs/PyQt5/)
- [OpenAI API](https://platform.openai.com/docs)
- [Stripe API](https://stripe.com/docs/api)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [PyInstaller Guide](https://pyinstaller.org/)

---

## Contact & Support

For questions or issues:
- Email: dev@voxylis.com
- GitHub: github.com/voxylis/voxylis
- Discord: discord.gg/voxylis
