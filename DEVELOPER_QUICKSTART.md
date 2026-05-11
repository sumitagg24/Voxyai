# Voxylis v2.1 - Developer Quick Start

## 🚀 Quick Setup (5 minutes)

### 1. Clone Repository
```bash
git clone https://github.com/voxylis/voxylis.git
cd voxylis
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Set Environment Variables
```bash
# Windows PowerShell
$env:GROQ_API_KEY="your-api-key"
$env:OPENAI_API_KEY="your-api-key"

# macOS/Linux
export GROQ_API_KEY="your-api-key"
export OPENAI_API_KEY="your-api-key"
```

### 4. Run Application
```bash
python main.py
```

### 5. Access Web Interface
```
http://localhost:5000
```

---

## 📁 Project Structure

```
voxylis/
├── main.py                    # Application entry point
├── requirements.txt           # Python dependencies
├── config/
│   ├── constants.py          # Global constants
│   └── settings.json         # User configuration
├── core/
│   ├── app_orchestrator.py   # Main orchestrator
│   ├── wake_word_detector.py # NEW: Wake word system
│   ├── hotkey_manager.py     # NEW: Hotkey customization
│   ├── voice_commands.py     # Voice command processor
│   └── ...
├── ai/
│   ├── qa_engine.py          # NEW: Q&A system
│   ├── transcriber.py        # Speech-to-text
│   ├── enhancer.py           # Text enhancement
│   └── ...
├── ui/
│   ├── overlay.py            # Floating widget
│   ├── settings_window.py    # Settings UI
│   └── ...
├── web/                       # Web interface
│   ├── index.html            # Landing page
│   ├── dashboard.html        # User dashboard
│   ├── css/                  # Stylesheets
│   ├── js/                   # JavaScript
│   └── docs/                 # Documentation
└── IMPLEMENTATION_GUIDE.md   # Detailed guide
```

---

## 🔧 Key Files to Modify

### Adding New Features

#### 1. Voice Commands
**File**: `core/voice_commands.py`
```python
# Add new command
def handle_new_command(self, text):
    if "your command" in text.lower():
        return self.execute_action()
```

#### 2. Wake Word
**File**: `core/wake_word_detector.py`
```python
# Customize wake word
detector = WakeWordDetector(
    wake_word="YourWord",
    sensitivity=0.8
)
```

#### 3. Q&A Feature
**File**: `ai/qa_engine.py`
```python
# Add Q&A logic
def get_answer(self, question):
    # Implement your logic
    pass
```

#### 4. Hotkeys
**File**: `core/hotkey_manager.py`
```python
# Register new hotkey
manager.register_hotkey(
    'new_action',
    'ctrl+alt+n',
    callback_function
)
```

---

## 🌐 Web Development

### Frontend (HTML/CSS/JS)

#### Add New Page
1. Create `web/newpage.html`
2. Add navigation link in `web/index.html`
3. Style with `web/css/style.css`
4. Add interactivity in `web/js/main.js`

#### Add Dashboard Section
1. Add section in `web/dashboard.html`
2. Add navigation item in sidebar
3. Style in `web/css/dashboard.css`
4. Add logic in `web/js/dashboard.js`

### Backend (Flask)

#### Add API Endpoint
```python
# In web/app.py
@app.route('/api/newfeature', methods=['GET', 'POST'])
def new_feature():
    if request.method == 'POST':
        data = request.json
        # Process data
        return jsonify({'status': 'success'})
    else:
        # Return data
        return jsonify({})
```

---

## 🧪 Testing

### Run Tests
```bash
pytest tests/
```

### Test Voice Commands
```python
from core.voice_commands import VoiceCommandProcessor

processor = VoiceCommandProcessor()
result = processor.process_command("undo")
assert result == "undo_action"
```

### Test Wake Word
```python
from core.wake_word_detector import WakeWordDetector

detector = WakeWordDetector("Voxy")
assert detector._fuzzy_match("voxy", "voxy") >= 0.7
```

---

## 🐛 Debugging

### Enable Debug Mode
```python
# In main.py
if __name__ == "__main__":
    app = VoxylisApp()
    app.run(debug=True)
```

### Check Logs
```bash
# View application logs
tail -f logs/voxylis.log

# View web server logs
tail -f logs/web.log
```

### Common Issues

#### Issue: "API key not found"
```bash
# Set environment variable
export GROQ_API_KEY="your-key"
```

#### Issue: "Hotkey not working"
```python
# Check hotkey registration
from core.hotkey_manager import HotkeyManager
manager = HotkeyManager()
print(manager.hotkeys)
```

#### Issue: "Microphone not detected"
```python
# List available microphones
import sounddevice
print(sounddevice.query_devices())
```

---

## 📦 Building & Deployment

### Build Windows Executable
```bash
pyinstaller build_windows.spec
```

### Build macOS App
```bash
pyinstaller build_macos.spec
```

### Deploy Web Interface
```bash
# Using Flask
python web/app.py

# Using Gunicorn (production)
gunicorn -w 4 -b 0.0.0.0:5000 web.app:app
```

---

## 📚 Documentation

### Code Documentation
```python
def my_function(param1, param2):
    """
    Brief description.
    
    Args:
        param1: Description
        param2: Description
    
    Returns:
        Description of return value
    
    Raises:
        ExceptionType: When this happens
    """
    pass
```

### API Documentation
- See `web/docs/` for user documentation
- See `IMPLEMENTATION_GUIDE.md` for technical details
- See `API_REFERENCE.md` for API endpoints

---

## 🔄 Git Workflow

### Create Feature Branch
```bash
git checkout -b feature/new-feature
```

### Commit Changes
```bash
git add .
git commit -m "Add new feature"
```

### Push to Remote
```bash
git push origin feature/new-feature
```

### Create Pull Request
```bash
# On GitHub
1. Go to repository
2. Click "New Pull Request"
3. Select your branch
4. Add description
5. Submit PR
```

---

## 🚀 Performance Tips

### Optimize Voice Commands
```python
# Use async processing
async def process_command_async(self, text):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        self.executor,
        self._process_command,
        text
    )
```

### Cache Results
```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_language_code(language_name):
    # Expensive operation
    pass
```

### Profile Code
```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Your code here

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(10)
```

---

## 🔐 Security Best Practices

### Protect API Keys
```python
# Use environment variables
import os
api_key = os.getenv('GROQ_API_KEY')

# Never commit keys
# Add to .gitignore:
# .env
# config/secrets.json
```

### Validate User Input
```python
def validate_wake_word(word):
    if not isinstance(word, str):
        raise ValueError("Wake word must be string")
    if len(word) < 2:
        raise ValueError("Wake word too short")
    return word.lower()
```

### Use HTTPS
```python
# In production, always use HTTPS
# Use SSL certificates
# Redirect HTTP to HTTPS
```

---

## 📊 Monitoring

### Track Metrics
```python
import time

def track_performance(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        print(f"{func.__name__}: {duration:.2f}s")
        return result
    return wrapper
```

### Log Important Events
```python
from utils.logger import log_info, log_error

log_info("Feature activated")
log_error("Error occurred", exc_info=True)
```

---

## 🤝 Contributing

### Code Style
- Follow PEP 8
- Use type hints
- Write docstrings
- Keep functions small

### Testing
- Write unit tests
- Test edge cases
- Aim for 80%+ coverage
- Run tests before committing

### Documentation
- Update README
- Add docstrings
- Update CHANGELOG
- Add examples

---

## 📞 Support

### Get Help
- Check `IMPLEMENTATION_GUIDE.md`
- Read `API_REFERENCE.md`
- Search GitHub issues
- Ask in Discord

### Report Issues
1. Check if issue exists
2. Provide minimal reproduction
3. Include system info
4. Attach logs

### Request Features
1. Check if requested
2. Describe use case
3. Provide examples
4. Discuss implementation

---

## 🎯 Next Steps

1. **Explore Code**: Read through main modules
2. **Run Tests**: Ensure everything works
3. **Try Features**: Test all functionality
4. **Read Docs**: Understand architecture
5. **Make Changes**: Start developing
6. **Submit PR**: Share improvements

---

## 📚 Resources

- [Python Docs](https://docs.python.org/3/)
- [PyQt5 Docs](https://www.riverbankcomputing.com/static/Docs/PyQt5/)
- [Flask Docs](https://flask.palletsprojects.com/)
- [OpenAI API](https://platform.openai.com/docs)
- [Groq API](https://console.groq.com/docs)

---

## 🎉 Happy Coding!

Welcome to the Voxylis development team. We're excited to have you contribute!

**Questions?** Ask in Discord or open an issue on GitHub.

**Ready to code?** Start with `main.py` and explore!

---

**Voxylis Development Team**  
*Transform Your Voice Into Text*
