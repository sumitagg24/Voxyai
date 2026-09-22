# Voxylis - System-Wide AI Voice-to-Text & Writing Assistant

![Version](https://img.shields.io/badge/version-2.2.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.10+-blue)

Voxylis is a production-ready desktop application + web platform that transforms your voice into high-quality, AI-enhanced text. Press a hotkey, speak naturally, and watch as your words are instantly transcribed, enhanced, and injected into any application on your system.

## Features

### Desktop App
- **Global Hotkey System** - Win+Shift to record (configurable)
- **Real-Time Audio Recording** - Microphone capture with noise filtering
- **Speech-to-Text** - Groq Whisper (free) or OpenAI Whisper API
- **AI Text Enhancement** - Groq LLaMA (free) or OpenAI GPT-powered improvement
- **System-Wide Text Injection** - Clipboard-based injection at cursor position
- **Floating Widget** - Real-time recording status and audio visualization
- **Voice Commands** - "clear that", "new line", "undo" while recording
- **Per-App Profiles** - Auto-switch enhancement mode per application
- **First-Run Onboarding** - Guided setup wizard for new users

### Enhancement Modes
- **Formal** - Professional and polished text
- **Casual** - Friendly and conversational
- **Technical** - Precise and technical terminology
- **Concise** - Brief and to-the-point
- **Creative** - Engaging and interesting
- **Custom** - Create your own enhancement templates

### Web Platform
- **User Authentication** - Signup, login, session management
- **Dashboard** - Usage stats, transcription history, settings
- **Q&A Feature** - Ask Voxy questions (powered by Groq/OpenAI)
- **Blog** - Product updates, engineering posts, research
- **Download** - Platform-detected download links
- **Newsletter** - Email subscription
- **Contact** - Message submission

### Infrastructure
- **CI/CD** - GitHub Actions for lint, test, build, deploy
- **Docker** - Containerized Flask backend
- **Rate Limiting** - Per-IP and per-user rate limiting
- **Security Headers** - XSS, CSRF, clickjacking protection
- **Password Reset** - Token-based password recovery
- **Email Verification** - Account email confirmation

## Requirements

- **OS**: Windows 10+ (desktop app), any OS (web app)
- **Python**: 3.10 or higher
- **Microphone**: Built-in, USB, or Bluetooth (desktop)
- **API Key**: Groq (free) or OpenAI (paid)

## Quick Start

### Desktop App
```bash
git clone https://github.com/sumitagg24/Voxyai.git
cd voxyai
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

> **Windows SmartScreen warning?** The prebuilt `Voxylis.exe` is currently
> unsigned, so Windows shows *"Windows protected your PC"* on first run.
> This is expected for new/unsigned apps, not malware: click **More info →
> Run anyway**. To remove the file's internet-download mark instead, run
> `Unblock-File -Path Voxylis-Windows-*.zip` before extracting. Permanent
> fix (in progress): code-sign releases — see Deployment below.

### Web Backend
```bash
pip install -r requirements.txt
python -m web.app
# Server runs on http://localhost:5000
```

### Docker
```bash
docker compose up -d
# Server runs on http://localhost:5000
```

## Configuration

### Environment Variables
Copy `.env.example` to `.env` and fill in your values:
```bash
cp .env.example .env
```

Key variables:
- `GROQ_API_KEY` - Free transcription key from console.groq.com/keys
- `OPENAI_API_KEY` - Paid alternative from platform.openai.com
- `SECRET_KEY` - Session management secret
- `FLASK_ENV` - development or production

### Desktop Settings
Edit `config/settings.json` or use the Settings window from the tray icon.

## Project Structure

```
voxyai/
├── main.py                    # Desktop app entry point
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Container image
├── docker-compose.yml         # Multi-service setup
├── gunicorn.conf.py           # Production WSGI config
├── Procfile                   # Heroku/Railway deploy
├── vercel.json                # Vercel static hosting
│
├── web/                       # Web application (Flask)
│   ├── app.py                 # Flask server + API
│   ├── data/                  # SQLite database
│   └── static/                # Frontend HTML/CSS/JS
│       ├── index.html         # Landing page
│       ├── auth.html          # Sign in/up
│       ├── dashboard.html     # User dashboard
│       ├── pricing.html       # Pricing page
│       ├── blog.html          # Blog listing
│       └── docs/              # Documentation pages
│
├── ai/                        # AI/ML modules
│   ├── transcriber.py         # Groq/OpenAI Whisper STT
│   ├── enhancer.py            # LLM text enhancement
│   └── language_detector.py   # Multi-language detection
│
├── audio/                     # Audio processing
│   ├── recorder.py            # Microphone recording
│   └── noise_canceller.py     # FFT noise reduction
│
├── core/                      # Core logic
│   ├── app_orchestrator.py    # Pipeline orchestrator
│   ├── hotkey_listener.py     # Global hotkey detection
│   ├── voice_commands.py      # Voice command processor
│   └── command_processor.py   # Rich commands
│
├── config/                    # Configuration
│   ├── constants.py           # App constants
│   └── settings.json          # User settings (gitignored)
│
├── ui/                        # PyQt5 GUI
│   ├── overlay.py             # Floating widget
│   ├── settings_window.py     # Settings UI
│   ├── history_window.py      # Transcription history
│   ├── onboarding_window.py   # First-run wizard
│   └── custom_modes_window.py # Custom modes editor
│
├── system/                    # System integration
│   ├── injector.py            # Text injection
│   └── clipboard_manager.py   # Clipboard management
│
├── .github/workflows/         # CI/CD
│   ├── ci.yml                 # Lint, test, build
│   └── release.yml            # Tagged releases
│
└── utils/                     # Utilities
    ├── logger.py              # Logging system
    └── helpers.py             # Helper functions
```

## API Endpoints

### Authentication
| Method | Endpoint | Rate Limit | Description |
|--------|----------|------------|-------------|
| POST | `/api/auth/signup` | 10/hr | Create account |
| POST | `/api/auth/login` | 10/15min | Sign in |
| POST | `/api/auth/verify` | - | Verify session |
| POST | `/api/auth/logout` | - | Sign out |
| POST | `/api/auth/forgot-password` | 5/hr | Request reset |
| POST | `/api/auth/reset-password` | 10/hr | Reset password |
| POST | `/api/auth/verify-email` | 5/hr | Send verification |
| POST | `/api/auth/confirm-email` | 10/hr | Confirm email |
| POST | `/api/auth/update-profile` | 10/hr | Update profile |

### User Data
| Method | Endpoint | Rate Limit | Description |
|--------|----------|------------|-------------|
| GET | `/api/me` | - | Current user profile |
| GET/POST | `/api/settings` | 30/min | User settings |
| GET/POST | `/api/hotkeys` | 30/min | User hotkeys |
| GET/POST | `/api/history` | 30/min | Transcription history |
| GET/POST | `/api/onboarding` | - | Onboarding progress |
| GET | `/api/subscription` | - | Subscription status |

### Content
| Method | Endpoint | Rate Limit | Description |
|--------|----------|------------|-------------|
| GET | `/api/features` | Cached | Feature list |
| GET | `/api/pricing` | Cached | Pricing tiers |
| GET | `/api/stats` | - | Usage statistics |
| GET | `/api/stats/public` | - | Public stats |
| POST | `/api/qa` | 30/min | AI Q&A |
| POST | `/api/contact` | 10/hr | Contact form |
| POST | `/api/newsletter` | 10/hr | Newsletter subscribe |

### Blog
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/blog` | List posts |
| GET | `/api/blog/<slug>` | Single post |

### System
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/download/urls` | Download links |
| GET | `/api/download/detect` | OS detection |
| POST | `/api/download/track` | Track downloads |

## Deployment

### Vercel (Static Frontend)
Already configured via `vercel.json`. Push to deploy.

### Docker (Backend)
```bash
docker compose up -d
```

### Manual (Gunicorn)
```bash
gunicorn --bind 0.0.0.0:5000 --workers 4 web.app:app
```

### GitHub Actions
- **CI**: Runs on every push/PR (lint, test, build)
- **Release**: Triggered by `v*` tags (builds desktop exe, deploys web)

### Windows Code Signing (removes the SmartScreen warning)
1. Buy an OV/EV code-signing certificate (required — self-signed certs do
   not silence SmartScreen for other users).
2. Local build: `set CERT_PATH=C:\path\to\cert.pfx` and
   `set CERT_PASSWORD=...`, then run `build_windows.bat`.
3. CI build: add `WINDOWS_CERT_BASE64` + `WINDOWS_CERT_PASSWORD` repo
   secrets — `release.yml` signs automatically when present.
4. After the first signed release, submit the exe to
   <https://www.microsoft.com/en-us/wdsi/filesubmission> to build
   SmartScreen reputation faster.

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Win+Shift | Record (default mode) |
| Win+Alt | Record (casual mode) |
| Win+Ctrl | Record (technical mode) |
| Win+; | Open settings |

### Voice Commands (while recording)
| Command | Action |
|---------|--------|
| "clear that" | Undo last injection |
| "new line" | Insert line break |
| "undo" | Undo last action |

## Privacy & Security

- **Groq API** - Free, fast transcription (recommended)
- **OpenAI API** - Paid alternative
- **No Audio Storage** - Audio processed in real-time, not saved
- **Session Rotation** - Tokens refresh every 24 hours
- **Rate Limiting** - Per-IP and per-user limits
- **Security Headers** - XSS, CSRF, clickjacking protection
- **Password Hashing** - PBKDF2-SHA256 with salt

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

## Support

- **Documentation**: `/docs/installation`, `/docs/configuration`, etc.
- **Issues**: [GitHub Issues](https://github.com/sumitagg24/Voxyai/issues)
- **Email**: Via the contact form on the website

---

**Made with love by the Voxylis Team**
