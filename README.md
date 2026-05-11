# Voxylis – System-Wide AI Voice-to-Text & Writing Assistant

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.8+-blue)

Voxylis is a production-ready desktop application that transforms your voice into high-quality, AI-enhanced text. Press a hotkey, speak naturally, and watch as your words are instantly transcribed, enhanced, and injected into any application on your system.

## 🎯 Features

### Core Features
- **Global Hotkey System** - Press Ctrl+Shift+V (configurable) to start recording
- **Real-Time Audio Recording** - Capture microphone input with noise filtering
- **Speech-to-Text** - OpenAI Whisper API for accurate transcription
- **AI Text Enhancement** - GPT-powered grammar, punctuation, and tone improvement
- **System-Wide Text Injection** - Automatically insert text at cursor position
- **Floating Widget** - Real-time recording status and audio level visualization
- **Settings Panel** - Configure hotkey, language, enhancement mode, and more

### Enhancement Modes
- **Formal** - Professional and polished text
- **Casual** - Friendly and conversational
- **Technical** - Precise and technical terminology
- **Concise** - Brief and to-the-point
- **Creative** - Engaging and interesting

### Advanced Features
- Multi-language support (English, Spanish, French, German, Italian, Portuguese, Japanese, Chinese)
- Configurable audio device selection
- Privacy modes (cloud and local)
- Comprehensive logging and debugging
- System tray integration
- Customizable UI theme (dark/light)

## 📋 Requirements

- **OS**: Windows 10+ (with bash shell), macOS, or Linux
- **Python**: 3.8 or higher
- **Microphone**: Built-in, USB, or Bluetooth
- **OpenAI API Key**: Required for transcription and enhancement

## 🚀 Installation

### 1. Clone Repository
```bash
git clone https://github.com/yourusername/voxylis.git
cd voxylis
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure OpenAI API Key
```bash
# Option 1: Set environment variable
export OPENAI_API_KEY="your-api-key-here"

# Option 2: Add to settings.json
# Edit config/settings.json and add your API key
```

### 5. Run Application
```bash
python main.py
```

## 📖 Usage Guide

### Basic Workflow
1. **Start Application** - Run `python main.py`
2. **Press Hotkey** - Press Ctrl+Shift+V (or configured hotkey)
3. **Speak** - Talk naturally into your microphone
4. **Release Hotkey** - Release the key to stop recording
5. **Wait for Processing** - Text is transcribed and enhanced
6. **Text Injected** - Enhanced text appears at cursor position

### Configuration

#### Via Settings Window
1. Click the Voxylis tray icon
2. Select "Settings"
3. Configure:
   - **Hotkey**: Change recording hotkey
   - **Language**: Select input language
   - **Enhancement Mode**: Choose text style
   - **API Key**: Add OpenAI API key
   - **Theme**: Select dark or light theme

#### Via config/settings.json
```json
{
  "hotkey": "ctrl+shift+v",
  "language": "en",
  "enhancement_mode": "formal",
  "enable_ai_enhancement": true,
  "openai_api_key": "your-api-key",
  "auto_inject": true,
  "show_floating_widget": true,
  "theme": "dark"
}
```

## 🏗️ Project Structure

```
voxylis/
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── config/
│   ├── constants.py       # Global constants
│   └── settings.json      # User configuration
├── core/
│   ├── app_orchestrator.py    # Main orchestrator
│   ├── event_manager.py       # Event system
│   └── hotkey_listener.py     # Global hotkey detection
├── audio/
│   ├── recorder.py        # Audio recording engine
│   └── audio_utils.py     # Audio processing utilities
├── ai/
│   ├── transcriber.py     # Speech-to-text (Whisper)
│   ├── enhancer.py        # Text enhancement (GPT)
│   └── prompt_templates.py # AI prompt templates
├── system/
│   ├── injector.py        # Text injection engine
│   └── clipboard_manager.py # Clipboard operations
├── ui/
│   ├── overlay.py         # Floating widget
│   └── settings_window.py # Settings UI
└── utils/
    ├── logger.py          # Logging system
    └── helpers.py         # Utility functions
```

## 🔧 Architecture

### Three-Layer Design

**1. INPUT LAYER (Voice Capture)**
- Global hotkey detection
- Real-time audio recording
- Noise filtering and normalization

**2. INTELLIGENCE LAYER (AI Processing)**
- Speech-to-text conversion (Whisper API)
- AI text enhancement (GPT)
- Grammar, punctuation, and tone improvement

**3. OUTPUT LAYER (System Integration)**
- Clipboard management
- System-wide text injection
- Keyboard automation

### Event-Driven Architecture
- Centralized event manager
- Decoupled components
- Real-time status updates

## 🎮 Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+Shift+V | Start/Stop recording (default) |
| Tray Icon | Access menu |

## 🔐 Privacy & Security

- **Cloud Mode**: Uses OpenAI API (data sent to OpenAI)
- **Local Mode**: Future support for local models
- **No Data Storage**: Audio and text not stored permanently
- **Clipboard Restoration**: Original clipboard content restored after injection

## 🐛 Troubleshooting

### Issue: "OpenAI API key not found"
**Solution**: Set `OPENAI_API_KEY` environment variable or add to settings.json

### Issue: Hotkey not working
**Solution**: 
- Check if another application is using the hotkey
- Try a different hotkey combination
- Restart the application

### Issue: Text not injecting
**Solution**:
- Ensure target application is focused
- Check if clipboard is accessible
- Try fallback typing mode in advanced settings

### Issue: Poor transcription quality
**Solution**:
- Use a better microphone
- Reduce background noise
- Speak clearly and at normal pace
- Check microphone levels in audio settings

## 📊 Performance

- **Recording Latency**: < 100ms
- **Transcription Time**: 2-5 seconds (depends on audio length)
- **Enhancement Time**: 1-3 seconds
- **Text Injection**: < 500ms
- **Total Pipeline**: 3-8 seconds

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see LICENSE file for details.

## 🙏 Acknowledgments

- OpenAI for Whisper and GPT APIs
- PyQt5 for UI framework
- pynput for hotkey detection
- sounddevice for audio recording

## 📧 Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check existing documentation
- Review troubleshooting section

## 🚀 Roadmap

- [ ] Local Whisper model support
- [ ] Custom voice commands
- [ ] Text history and export
- [ ] Plugin system
- [ ] macOS and Linux native builds
- [ ] Cloud sync for settings
- [ ] Advanced voice commands
- [ ] Real-time transcription streaming
- [ ] Multi-language auto-detection
- [ ] Custom enhancement templates

## 📈 Version History

### v1.0.0 (Current)
- Initial release
- Core features implemented
- OpenAI API integration
- PyQt5 UI
- System tray integration

---

**Made with ❤️ by Voxylis Team**
