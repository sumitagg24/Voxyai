# Voxylis

![Version](https://img.shields.io/badge/version-3.0.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![Platform](https://img.shields.io/badge/platform-Windows-0078D4)

Voxylis is a voice-first desktop assistant for Windows. Press a hotkey, speak
naturally, and AI-enhanced text lands at the cursor in whatever application has
focus — a browser, an editor, a chat window, a terminal. A companion website and
Flask API provide the account, dashboard, pricing and download surfaces.

The product name is **Voxylis**; the first-party engine is called **Voxy**.

## What it does

**Desktop app**

- Global hotkeys with hold *and* toggle modes, recorded and validated instead of
  typed — reserved Windows combinations and duplicates are rejected up front.
- Live recording overlay: state, microphone level, elapsed time, live transcript,
  current language and mode, cancel, and unmistakable success/error feedback.
- Speech-to-text and enhancement through Groq (preferred, free tier) or OpenAI
  (fallback), with optional AI enhancement modes: formal, casual, technical,
  concise, creative, or your own custom prompts.
- Text injected into the focused app with a real strategy chain: clipboard paste,
  then keyboard typing, then an honest "unsupported" result. Success is reported
  only when the strategy actually completed.
- Editable voice commands (`clear that`, `new line`, `undo`, `translate it to …`)
  and rich commands (web search, issue drafting, email drafting, snippets, Slack
  when configured).
- Per-application profiles so the same hotkey produces a casual tone in chat and
  a formal one in a document.
- Local history in SQLite with search, per-entry delete, retention, export and an
  off switch; counters and stats that never store your text.
- Real Windows installer, tray integration, optional run-at-login, single-instance
  behaviour, and a verified update flow.

**Website / backend**

- Account system with email verification, password reset, session rotation,
  Auth0 social login, and QR sign-in from the desktop app.
- Dashboard with history, usage stats and a Q&A panel.
- Pricing, downloads, blog, docs and legal pages, all reading one canonical
  version.

## Install

Download `Voxylis-Setup-3.0.0.exe` from the
[releases page](https://github.com/sumitagg24/Voxyai/releases) or the website's
[download page](web/static/download.html).

The installer is per-user by default (no administrator prompt), creates a Start
Menu entry, and offers optional desktop shortcut and run-at-login tasks. The
first-run wizard walks through microphone, shortcut, provider key, language and a
test recording.

> **Windows SmartScreen.** Public releases are signed when the signing
> certificate is available to CI. Unsigned development builds show
> *"Windows protected your PC"* on first run — that means Microsoft has no
> reputation for the file yet, not that it is malicious. See
> [docs/RELEASE.md](docs/RELEASE.md) for the signing setup.

### From source

```bash
git clone https://github.com/sumitagg24/Voxyai.git
cd voxyai
py -m venv venv
venv\Scripts\activate            # Windows (source venv/bin/activate on Unix)
py -m pip install -r requirements.txt
py main.py
```

Requirements: Windows 10/11, Python 3.10+ (64-bit), a microphone, and one
provider key (Groq is free at <https://console.groq.com/keys>).

## Where your data lives

Program files are never written to at runtime. Everything mutable is under one
user-data root:

```
%LOCALAPPDATA%\Voxylis\
├── config\     settings.json (non-secret preferences)
├── data\       history.sqlite3, stats.json
├── secrets\    credentials.vault   ← API keys, Windows DPAPI-encrypted
├── logs\       voxylis.log
├── temp\       temporary audio, deleted after every run
└── updates\    downloaded installers awaiting a verified install
```

API keys and session tokens are stored in the **operating system credential
store** (DPAPI at user scope, falling back to `keyring`), never in
`settings.json` and never in a log line. Legacy builds that kept keys in
`config/settings.json` are migrated automatically: the secret moves into the
vault and is removed from the file.

There is no analytics and no usage tracking. Crash reports are **off by default**
and only leave the machine if you enable them in Settings → Privacy; what a
report contains (and what it never contains) is listed in
[docs/PRIVACY.md](docs/PRIVACY.md).

Details: [docs/PRIVACY.md](docs/PRIVACY.md) · [docs/SECURITY.md](docs/SECURITY.md)

## Configuration

All preferences are in the app: **Settings** in the sidebar (or the tray menu).

| Section | What it covers |
|---|---|
| Home | Recording state and controls, setup readiness (provider, microphone, shortcut, insertion, history), today's counters, last error |
| History | Search, export, delete entries, retention, disable history |
| Microphone | Device picker, live level meter, record/playback test, toggle mode, language |
| AI Providers | Groq / OpenAI keys (stored in the credential vault), enhancement on/off, default mode, custom modes |
| Shortcuts | Record shortcuts (default + per-mode), hold/toggle mode, reserved-key and duplicate validation, disable global shortcuts, reset |
| Privacy | Retention, crash-report opt-in, diagnostics export, local data deletion |
| Account | Optional sign-in for the web dashboard |
| Diagnostics | Pipeline state, paths, recent errors, redacted support bundle |
| About | Version, licences, links |

`settings.json` keeps only non-secret fields (`hotkey`, `mode_hotkeys`,
`toggle_mode`, `language`, `secondary_language`, `enhancement_mode`,
`enable_ai_enhancement`, `auto_inject`, `audio_device`, `theme`,
`history_enabled`, `history_retention_days`, `max_history`, voice commands,
custom modes, app profiles). Which provider is used is derived from which key is
stored in the vault — Groq when present, otherwise OpenAI — so there is no
"provider" field to get out of sync. The shape is documented in
[config/settings.example.json](config/settings.example.json).

## Repository layout

```
voxyai/
├── main.py                    Desktop entry point (single instance, tray, shell)
├── config/
│   ├── version.py             Canonical version + generated mirrors
│   ├── constants.py           App constants and defaults
│   └── settings.example.json  Non-secret settings reference
├── core/
│   ├── app_orchestrator.py    Voice pipeline state machine
│   ├── hotkey_listener.py     Global hotkey capture and validation
│   ├── history_store.py       SQLite history persistence
│   ├── errors.py              Error catalogue + exception classification
│   ├── updater.py             Verified update download and handoff
│   └── voice_commands.py, command_processor.py, per_app_profiles.py, …
├── ai/                        transcriber, enhancer, language detector, prompts
├── audio/                     recorder, noise canceller, audio utils
├── ui/
│   ├── main_window.py         Persistent window + sidebar navigation
│   ├── pages.py               Home, History, Voice, AI, Shortcuts, Privacy, …
│   ├── overlay.py             Transient recording overlay
│   ├── shortcut_recorder.py   Record-a-shortcut widget
│   ├── error_dialog.py        User-facing error presentation
│   ├── diagnostics.py         Redacted support bundle
│   ├── theme.py               Shared styling and icons
│   └── onboarding_window.py   First-run wizard
├── system/                    injector (strategy chain), clipboard manager
├── utils/
│   ├── paths.py               User-data layout + legacy migration
│   ├── credentials.py         OS-backed credential vault
│   └── logger.py, helpers.py
├── web/
│   ├── app.py                 Flask app + API routes
│   ├── tier.py                Tier → features/quotas table
│   ├── verify_routes.py       Route inventory guard
│   ├── services/              subscription policy
│   └── static/                Website (pages, docs, blog, dashboard)
├── packaging/                 version_info (generated), icon generator, .ico
├── installer/voxylis.iss      Inno Setup definition
├── tests/                     Backend, desktop and site tests
└── docs/                      ARCHITECTURE, PRIVACY, SECURITY, RELEASE, API
```

## Web API

Base URL is the host running `web/app.py`. User-scoped endpoints take the session
id in the `X-Session-Id` header (or a `session_id` body field).

### Auth

| Method | Endpoint | Notes |
|---|---|---|
| POST | `/api/auth/signup` | rate limited |
| POST | `/api/auth/login` | rate limited |
| POST | `/api/auth/verify` | validate a session |
| POST | `/api/auth/logout` | destroy a session |
| POST | `/api/auth/forgot-password` | does not reveal whether an address exists |
| POST | `/api/auth/reset-password` | single-use expiring token |
| POST | `/api/auth/verify-email` | send confirmation |
| POST | `/api/auth/confirm-email` | confirm token |
| POST | `/api/auth/update-profile` | authenticated |
| GET | `/api/auth/auth0/config` | whether social login is configured |
| POST | `/api/auth/auth0` | social login exchange |
| POST | `/api/auth/qr/start` | QR sign-in from the desktop app |
| GET | `/api/auth/qr/status` | poll QR approval state |
| POST | `/api/auth/qr/approve` | approve from an authenticated browser |

### User and content

| Method | Endpoint | Notes |
|---|---|---|
| GET | `/api/me` | profile, tier, quotas |
| GET/POST | `/api/settings` | per-user settings |
| GET/POST | `/api/hotkeys` | per-user shortcuts |
| GET/POST | `/api/history` | list / add, DELETE `/api/history/<id>` |
| GET/POST | `/api/onboarding` | onboarding progress |
| GET | `/api/subscription` | status; says whether checkout exists |
| POST | `/api/subscription/upgrade` | **cannot grant a tier from the client** |
| GET | `/api/features`, `/api/pricing` | cached capability/pricing data |
| GET | `/api/stats`, `/api/stats/public` | usage statistics |
| POST | `/api/qa`, `/api/enhance`, `/api/transcribe` | provider-backed |
| POST | `/api/contact`, `/api/newsletter` | rate limited |
| GET | `/api/blog`, `/api/blog/<slug>` | blog posts |
| GET | `/api/download/urls`, `/api/download/detect` | release links |
| POST | `/api/download/track` | download counter |
| GET | `/api/admin/users` | admin only |
| GET | `/api/health` | version + subscription policy |

Full request/response detail: [docs/API.md](docs/API.md).

## Backend and deployment

```bash
# local
py -m web.app                       # http://localhost:5000

# containers
docker compose up -d

# gunicorn
gunicorn --bind 0.0.0.0:5000 --workers 4 web.app:app
```

Environment (see [.env.example](.env.example) for the full list and
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for how to obtain each value):

- `SECRET_KEY` — required in production; the app refuses to start with a missing
  or weak value.
- `GROQ_API_KEY` / `OPENAI_API_KEY` — server-side provider keys for the website
  only.
- `CORS_ORIGINS` — comma-separated allow-list; there is no wildcard.
- `VOXYLIS_DB_PATH` — SQLite location; defaults to `web/data/voxylis.db`.
- `ALLOW_DEV_TIER_CHANGE` — development-only tier override. It is ignored in
  production; never enable it on a deployed host.
- `EMAIL_PROVIDER` + `EMAIL_API_KEY` (or `SMTP_HOST`) + `FRONTEND_URL` — needed
  for verification and password-reset mail. Without them the app runs with the
  `console` provider: nothing is delivered and startup logs an error.
- `SENTRY_DSN` / `SENTRY_DSN_BROWSER` — optional error monitoring for the API
  and the website. Unset means monitoring is off and the app is unaffected.
- `DOWNLOAD_URL_WINDOWS` — set only once the matching release artifact exists;
  an empty value makes the download page point at the releases page and say the
  installer is not published yet.

`GET /api/health` reports `email` and `monitoring` status, so a deployment can
see whether those two are actually configured.

The backend is designed for a single instance with SQLite. Rate limits are
in-memory, so limiting stops being meaningful if you run several workers across
hosts — add a shared store first.

Deploying the static site (`vercel.json`) separately from the API: point the
frontend at the backend with `window.VOXYLIS_API_BASE` or
`/dashboard?api=https://your-backend.example.com`, and add that origin to
`CORS_ORIGINS`.

## Tests and lint

```bash
py -m pytest tests -q           # backend, desktop units, version/site checks
py -m flake8 .                  # policy in setup.cfg
```

CI runs lint, the suite, a version-mirror check and a packaging smoke build on
every push; tagged releases additionally build and (when certificate secrets
exist) sign the Windows artifacts.

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — process, pipeline, storage, ownership
- [docs/PRIVACY.md](docs/PRIVACY.md) — exact data flows and deletion
- [docs/SECURITY.md](docs/SECURITY.md) — trust boundaries, controls, limitations
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — every environment variable and the manual work it needs
- [docs/RELEASE.md](docs/RELEASE.md) — versioning, signing, release gate
- [docs/API.md](docs/API.md) — endpoint reference
- [CHANGELOG.md](CHANGELOG.md) — release history
- In-site docs: `web/static/docs/` (installation, configuration, voice commands,
  Q&A, tips, troubleshooting)

## Contributing

Fork, branch, and open a pull request. Run lint and the test suite before
pushing; see [CONTRIBUTING.md](CONTRIBUTING.md). Please do not commit user data,
API keys, build output or generated artifacts — the `.gitignore` covers them, and
CI checks for credential patterns in release builds.

## License

MIT — see [LICENSE](LICENSE).

## Support

- Issues: <https://github.com/sumitagg24/Voxyai/issues>
- Security reports: private advisory via the repository's Security tab
- Contact form on the website
