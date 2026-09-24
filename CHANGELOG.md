# Changelog

All notable changes to Voxylis. The canonical version lives in
`config/version.py`; see `docs/RELEASE.md` for the release procedure.

## Unreleased — email, monitoring and repository hygiene

### Email (new)

* **Transactional email actually sends.** Verification and password-reset
  endpoints previously minted tokens, stored them, and delivered nothing while
  reporting success. A provider abstraction now sits behind every message:
  Resend over HTTP, SMTP (stdlib), or a `console` provider for development that
  records instead of sending and warns loudly at startup in production.
* **Ten templates** (welcome, verify, reset, password-changed, security alert,
  plan change, usage warning, usage limit, account deleted, product update) with
  text and HTML bodies, all built from `FRONTEND_URL` so a hosted deployment
  cannot mail a `localhost` link.
* **Account security mail**: a password change signs out every other session and
  notifies the account; requesting a new verification or reset link retires the
  previous one; reset links are single use and expire in an hour.
* **Marketing consent is separate.** Product news requires an explicit opt-in and
  carries a signed unsubscribe link; absence of a preference row means "no".
* **Account deletion** (`POST /api/account/delete`) requires the password and a
  typed confirmation, refuses the owner account, and cascades every related row.

### Monitoring (new)

* **Sentry for the API, the website and the desktop app**, all optional: with no
  DSN the app runs exactly as before. Request bodies are never attached, frame
  locals are dropped, and headers, cookies, query strings, session ids and
  user-content fields are scrubbed before an event leaves the process.
* **Desktop reporting is opt-in** (Settings → Privacy) and off by default; a
  local crash report is still written either way.
* `/api/public-config` exposes only the public browser DSN; `SENTRY_DSN` never
  reaches the frontend.

### Security and correctness

* **Startup crash fixed.** `AppOrchestrator.get_config()` accepted only a key,
  but the whole UI calls it with a default (`get_config("theme", "dark")`).
  Every such call raised `TypeError`, so the packaged app died immediately after
  startup; the test double already had the two-argument form, which is why the
  unit suite never noticed. Found by launching the frozen build.
* `load_dotenv()` ran *after* `SECRET_KEY` and `CORS_ORIGINS` were resolved, so a
  `.env` file was ignored for the two values that matter most.
* `POST /api/transcribe` now requires a confirmed email address (owner and admin
  exempt), so an unverified throwaway address cannot consume the monthly quota.
* Cross-origin credentials are no longer advertised by default (`X-Session-Id`
  header auth, no cookies); `CORS_SUPPORTS_CREDENTIALS` opts back in.
* Password changes through `update-profile` sign out other devices and send a
  notice.
* Application logs now have a real handler, so email and monitoring messages are
  not silently discarded by the host. Recipients are masked; bodies and tokens
  are never logged.

### Website and releases

* The download page no longer advertises an installer that was never published:
  `/api/download/urls` reports per-platform `available` flags and links to the
  releases page when no artifact is configured.
* Removed a stale duplicate download page (`web/downloads/`) that linked to
  `.exe`, `.dmg`, `.deb`, `.rpm` and AppImage builds that do not exist, and the
  second `version.json` mirror that only drifted.
* `pyproject.toml` pins black to the project's 120-column style so the CI format
  check can actually pass.

### Repository hygiene

* `config/users.json` and `config/sessions.json` are no longer tracked; both were
  already gitignored, and their presence made the CI secret scan fail.
* `.gitignore` covers `.env` (with `!.env.example`), private keys, vaults,
  SQLite files and runtime directories; `.env.example` documents only variables
  the code actually reads, with no values.

## 3.0.0 — production release (hardening)

> Release note: the `v3.0.0` tag currently points at the commit *before* this
> hardening work. Move the tag onto the hardened commit, or bump
> `config/version.py` to `3.0.1`, before publishing — do not ship an artifact
> whose version string disagrees with the tag.

### Desktop

* **Application shell.** The recording overlay is no longer the whole UI. A
  persistent, branded main window with sidebar navigation adds Home, History,
  Microphone, AI Providers, Shortcuts, Privacy, Account, Diagnostics and About,
  and the tray exposes Open Voxylis, History, Settings, current mode, status and
  Quit without rebuilding its menus on every change.
* **Single instance.** A second launch signals the running instance and brings
  the existing window forward instead of starting a duplicate process.
* **Shortcut recorder.** Shortcuts are recorded, not typed: reserved Windows
  combinations, modifier-only combos, duplicates and invalid keys are rejected
  before registration, with reset-to-default.
* **Overlay.** Recording state, microphone level, elapsed time, live transcript,
  language and mode, explicit success/error states, cancel, DPI-correct and
  multi-monitor-safe placement, theme support.
* **Error UX.** Failures render as *what happened → why → what you can do* with
  one-click jumps into the relevant settings page; raw detail is behind
  "Show diagnostics".
* **Diagnostics.** A redacted support bundle (version, OS, runtime, provider,
  microphone, connectivity, last error, recent pipeline stages). It cannot
  contain keys, tokens or transcripts.
* **Onboarding.** Rewritten first-run flow: welcome, microphone permission and
  test, shortcut, provider and key, language, enhancement mode, optional sign-in,
  test recording.
* **Updates.** Version check → download → size and SHA-256 verification → hand
  off to the installer. A running binary is never replaced in place and a
  manifest without a checksum is refused.

### Storage and privacy

* **User data moved out of the install directory** to
  `%LOCALAPPDATA%\Voxylis` (config, data, secrets, logs, cache, models, temp,
  updates, crashes), with a non-destructive migration of legacy in-tree files.
* **History is now SQLite** (`data/history.sqlite3`) instead of a plaintext JSON
  file, with per-entry delete, delete-all, retention window, entry cap, JSON/CSV
  export, and a setting that disables history storage entirely.
* **API keys moved to the OS credential store** — Windows DPAPI via `crypt32`,
  falling back to `keyring`, then to a documented obfuscated store. Plaintext
  keys in a legacy `settings.json` are migrated into the vault and removed from
  the file. Nothing logs a credential; `${value}` redaction is applied before
  display.

### Voice pipeline and injection

* Explicit state machine with cancellation, timeouts, bounded retry with
  backoff, provider fallback, duplicate-start and duplicate-injection
  prevention, max recording duration, microphone/network/quota/invalid-key
  handling, and guaranteed return to `idle` after any failure.
* Injection is now a strategy chain (clipboard paste → keyboard typing →
  unsupported) that reports success only when the chosen strategy completed,
  with clipboard restoration, Unicode handling and retry.
* Hotkey listener validates configuration, recovers from listener loss,
  supports hold and toggle modes, and can be disabled without crashing the app.

### Backend and security

* **Client-forgeable tier upgrade removed.** `POST /api/subscription/upgrade`
  can no longer set a tier from a client request. Tier changes are owned by
  `web/services/subscription_service.py`: verified payment webhook, audited
  admin action, or a development override that is *refused in production*.
  `GET /api/subscription` reports whether self-service upgrade or checkout
  exists so the UI can hide what is not implemented.
* **`SECRET_KEY` guard.** The backend refuses to start in production when the
  key is missing, a known placeholder, or shorter than 32 characters.
* **Session rotation fixed.** Rotated session ids are actually returned to
  clients (`X-Rotated-Session-Id` and a JSON field) instead of being discarded.
* Security headers, explicit CORS allow-list, 1 MB request cap, per-user rate
  limit keys, generic error responses and parameterised SQL throughout.
* `web/tier.py` and `web/services/` extracted from the single large Flask file
  without changing the public API.

### Packaging, brand and docs

* **Real Windows installer** (Inno Setup 6): branded name, publisher, version,
  Start Menu entry, optional desktop shortcut, optional run-at-login, per-user
  install by default, upgrade path, clean uninstall that asks before touching
  user data, and no file associations it does not need.
* **Icon/brand system** generated by `packaging/make_icons.py` (`.ico` with
  multiple sizes, favicon, apple-touch icon, Open Graph image, installer and
  shortcut icons) — no generic microphone stock art as the product mark.
* **One canonical version** feeding EXE metadata, installer, `/api/health`,
  website download metadata and the About dialog, with a sync command and a test
  that fails when they disagree.
* **Marketing claims audited.** Fabricated traction, unverifiable speed claims
  and invented ratings were removed or labelled as illustrative; feature and
  language claims now match the implementation.
* **Docs:** `docs/ARCHITECTURE.md`, `docs/PRIVACY.md`, `docs/SECURITY.md`,
  `docs/RELEASE.md`, updated `docs/API.md` and the in-site docs pages, plus a
  README that describes the product that actually exists.
* **Tests:** backend (auth, sessions, rotation, rate limits, tier enforcement,
  subscription policy, security headers), desktop units (credentials, history
  store, paths, errors, shortcut validation), and version/site consistency.

### Repository hygiene

* Removed `config/users.json` and `config/sessions.json` (plaintext user and
  session data) from tracking; they are user data, not source.
* Removed the abandoned generated `docs/superpowers/` plan tree and the
  duplicate settings/history windows superseded by the main window pages.
* `.gitignore` now covers user data, vault files, databases, installer output,
  screenshots, `.freebuff/`, `.playwright-mcp/` and verification artefacts.

## 2.2.0

* Real download flow and frontend → backend connection (`window.VOXYLIS_API_BASE`,
  `?api=` override, CORS allow-list).

## 2.1.1

* Vercel rewrite for `/static/:dir/:file` so dashboard assets resolve on the
  static host.

## 2.1.0

* Repository cleanup checkpoint: single desktop implementation, single website,
  single backend.
