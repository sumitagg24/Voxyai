# Voxylis Architecture

Canonical version lives in `config/version.py` (`__version__ = "3.0.0"`). Every
other surface (EXE metadata, installer, `/api/health`, `web/static/version.json`,
About dialog) is generated from or reads that value.

## 1. Surfaces

```
Voxylis
├── Desktop app      PyQt5, Windows-first (main.py)
├── Website          static HTML/CSS/JS in web/static/ (Vercel or Flask)
└── Backend API      Flask in web/app.py (+ web/services/, web/tier.py)
```

There is exactly one desktop implementation, one website and one backend. No
duplicate trees, no generated second frontend/backend.

## 2. Desktop process

```
main.py
└── VoxylisApp
    ├── SingleInstance            named mutex + local socket, brings the
    │                             existing window forward instead of starting twice
    ├── QApplication
    ├── MainWindow      (ui/main_window.py)   primary surface, hidden on close
    │   └── pages       (ui/pages.py)         Home, History, Microphone,
    │                                         AI Providers, Shortcuts, Privacy,
    │                                         Account, Diagnostics, About
    ├── Overlay         (ui/overlay.py)       transient recording HUD
    ├── QSystemTrayIcon                       start/cancel, mode, status, quit
    ├── AppOrchestrator (core/app_orchestrator.py)
    ├── HotkeyListener  (core/hotkey_listener.py)
    └── Updater         (core/updater.py)     background version check
```

Lifecycle rules:

* The main window is created once and only hidden on close; the app exits from
  the tray **Quit** action or `exit_app()`.
* The overlay is a secondary surface — it is never the application UI.
* Single-instance is enforced before any window is created.
* Every thread that can outlive the pipeline (`QThread`s for microphone test,
  update check) is joined or abandoned explicitly on shutdown.

### Voice pipeline (unchanged in shape, hardened in behaviour)

```
hotkey press/release
  → HotkeyListener            validates combos, toggle or hold mode
  → AudioRecorder             mic capture, level → overlay, max duration
  → speech/silence gate       skips silent audio
  → Transcriber               Groq / OpenAI / OpenRouter, retry + timeout
  → LanguageDetector          reports BCP-47 code to the UI
  → VoiceCommands             "clear that", "new line", "undo", …
  → CommandProcessor          rich commands (search, issue, email, snippet, Slack)
  → Enhancer                  provider + mode prompt, fallback on failure
  → Injector                  clipboard-paste → keyboard-type → unsupported
  → HistoryStore (optional)   SQLite insert, retention enforced
  → StatsTracker              counts only, no text
```

State machine stages are published through `core/event_manager.py`
(`idle → listening → transcribing → enhancing → injecting → success/error`). The
UI only renders events; it never drives the pipeline. A failure always returns
the machine to `idle` — there is no permanent "Processing…" state.

## 3. Filesystem layout

Program files are immutable; all mutable state lives under one root
(`utils/paths.py`):

```
%LOCALAPPDATA%\Voxylis\          (Windows; LOCALAPPDATA not APPDATA, see below)
├── config/     settings.json, onboarding.json   (non-secret only)
├── data/       history.sqlite3, stats.json
├── secrets/    credentials.vault                (DPAPI-encrypted, user scope)
├── logs/       voxylis.log (rotated)
├── cache/      transient caches
├── models/     optional local models
├── temp/       temporary audio, deleted after each run
├── updates/    downloaded installers awaiting apply
└── crashes/    opt-in redacted crash reports
```

macOS uses `~/Library/Application Support/Voxylis`; Linux uses
`$XDG_DATA_HOME/voxylis` or `~/.local/share/voxylis`. `VOXYLIS_HOME` overrides
the root (used by tests and portable installs).

**Why LOCALAPPDATA:** the payload is cache-shaped (SQLite database, logs, temp
audio, update packages). Roaming profiles are synced by domain policy, so
`APPDATA` would push transcripts and a WAL-mode database over the network on
every logon.

Legacy builds wrote `config/settings.json`, `config/users.json`,
`config/sessions.json` and `logs/transcription_history.json` next to the
executable. `utils.paths.migrate_legacy_data()` copies (never moves, never
deletes) those into the user-data root on first start; an existing destination
always wins.

## 4. Secrets

`utils/credentials.py` implements a vault with pluggable backends, chosen in
order: **Windows DPAPI** (user scope, via `crypt32`) → **keyring** (any OS
credential store) → **obfuscated file** (documented last resort, machine-bound
XOR — it is obfuscation, not encryption, and is labelled as such in the code).

`settings.json` stores only non-secret metadata (`"provider": "groq"`,
`"configured": true`). Plaintext keys found in a legacy settings file are
migrated into the vault and removed from the JSON on first load.

## 5. Local persistence

* `core/history_store.py` — SQLite (`data/history.sqlite3`), WAL, indexed by
  timestamp; supports add, get, delete, clear, retention purge, entry cap,
  JSON/CSV export and legacy JSON import. Retries on `SQLITE_BUSY`.
* `core/history_manager.py` — the orchestrator-facing façade: honours
  `history_enabled`, applies retention/limit after each insert, and keeps the
  in-memory list the UI reads.
* `core/stats_tracker.py` — counters only (`data/stats.json`). No transcript
  text is ever written here.

## 6. Error model

`core/errors.py` holds a catalogue of `VoxylisError` records (code, title,
summary, cause, action, retryable, settings section, docs slug) plus
`classify_exception()` which maps provider/SDK/OS exceptions onto them. The UI
(`ui/error_dialog.py`) renders *what happened → why → what you can do* with the
technical detail behind "Show diagnostics" and one-click jumps into the relevant
settings page. Nothing in the dialog is a raw stack trace.

## 7. Diagnostics

`ui/diagnostics.py` builds a redacted support bundle: version, OS, runtime,
provider/model, microphone, permission state, connectivity, last error, recent
pipeline stages, path map (`utils.paths.describe_paths()`). It deliberately
cannot include API keys, tokens, passwords, email addresses or transcript text —
redaction happens at construction, not at copy time.

## 8. Web/backend

`web/app.py` remains the single Flask application and SQLite database (one
instance deployment; SQLite is sufficient and no Redis or external DB was
added). The pieces that must not be reimplemented per-endpoint were extracted:

```
web/
├── app.py                     app factory state, routes, security headers
├── tier.py                    tier → features/modes/quotas table
├── verify_routes.py           route inventory guard used by tests
└── services/
    └── subscription_service.py   the ONLY place a tier can change
```

Tier policy (`web/services/subscription_service.py`):

* A tier changes only via a verified payment webhook, an audited admin action,
  or an explicit development override that is refused in production.
* `POST /api/subscription/upgrade` can no longer set a tier from the client.
* `GET /api/subscription` reports whether self-service upgrade or checkout is
  available so the UI can hide a control that does not exist.

`SECRET_KEY` resolution refuses to start in production when the value is
missing, a known placeholder, or shorter than 32 characters.

## 9. Packaging and updates

```
voxylis.spec         PyInstaller one-folder build → dist/Voxylis/
packaging/
├── version_info.txt GENERATED from config/version.py (EXE metadata)
├── voxylis.ico      multi-size icon used by EXE, installer and shortcuts
└── make_icons.py    regenerates the icon set from the brand mark
installer/voxylis.iss   Inno Setup 6 → Voxylis-Setup-<version>.exe
build_windows.bat        sync version → PyInstaller → iscc → optional signing
build_linux.sh           source tarball build
```

Update flow (`core/updater.py`): fetch `update-manifest.json` from the release
feed → compare versions → download into `updates/` → verify size **and**
SHA-256 → hand off to the installer, which is the only component allowed to
move files. A running binary is never replaced in place; a missing checksum is
a hard failure rather than a silent install.

## 10. CI/CD

`.github/workflows/ci.yml` — lint (flake8, `setup.cfg` policy), the pytest
suite, version-mirror consistency check, and a packaging smoke build.
`.github/workflows/release.yml` — on a `v*` tag: build the EXE and installer,
sign when the certificate secrets are present, publish the artifacts, and update
`update-manifest.json` with the checksums the updater requires.
