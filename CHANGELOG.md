# Changelog

All notable changes to Voxylis. The canonical version lives in
`config/version.py`; see `docs/RELEASE.md` for the release procedure.

## 3.1.0 — 2026-10-11

### Foundation & Cleanup (P0)

* **Dependencies fixed**: `pywin32` (Windows), `psutil`, `groq`, `openai`, `PyJWT`, `cryptography` added; `scipy` removed; CI audits both `requirements.txt` and `requirements-server.txt`.
* **Fabricated "Muse" provider removed**: non-existent `api.meta.ai` endpoints deleted; LLM chain centralized in `web/services/llm_service.py` with explicit timeouts (server: connect 5s/read 30s; desktop: `OPENAI_API_TIMEOUT`); fallback order OpenRouter → Groq → OpenAI.
* **Wake word deleted everywhere**: no module existed but was advertised in features, tiers, dashboard, settings, docs — all removed.
* **Legacy desktop user manager deleted**: unsalted SHA-256 + plaintext JSON sessions removed; desktop now stores only Auth0 session id in OS credential vault.
* **Deployment consolidated to local-first + optional Render**: removed `Procfile`, `docker-compose.yml`, `vercel.json`, PythonAnywhere template, Vercel CI jobs; email `from_address` requires `EMAIL_FROM` (no `voxylis.com` default); download URLs resolved via GitHub API (cached 1h) with `DOWNLOAD_URL_*` overrides.
* **Dead code swept**: unused `UNSAFE_COMBOS`, `is_safe_combo`, `_canonical_targets`, `_detect_language`, `_count_transcriptions`, `catalog()`, `inject_with_fallback`, `inject_text_with_delay`, `MIN_RECORDING_DURATION`, `WHISPER_MODEL`, `GPT_MODEL`, `translate_pending` voice command removed.
* **Single tier policy**: `web/tier.py` is now the sole source of truth; desktop reads entitlements from `/api/me`; `/api/pricing` generated from tier data; wake word removed from all tiers; Q&A labelled Pro+.
* **web/app.py split into blueprints**: pages, auth, account, usage, content routes + `auth_helpers`, `extensions`, `db`, `llm_service`; zero behavior change.

### Backend Correctness (P1)

* **Session rotation fixed**: `attach_monitoring_context` read-only; rotation once/request with `X-Session-Rotated` header + JSON body; CORS exposes header; client `voxyFetch` persists new id; race-safe conditional UPDATE.
* **Email normalization**: lowercase at every boundary (signup, login, forgot-password, Auth0, QR, admin, newsletter); one-time migration dedupes case-variant duplicates; unique index on `LOWER(email_or_phone)`.
* **Microphone selection works**: `audio_device` config applied to `AudioRecorder`; validated via `sounddevice.query_devices()`; invalid indices rejected with warning.
* **Upload cap + JSON errors**: `MAX_CONTENT_LENGTH=32MB`; explicit 32MB check; JSON handlers for 413/429/400.
* **History/quota hole closed**: `/api/history` validates mode/language; STT quota enforced via `usage_records` (feature="transcription"), not `transcriptions` table; free-tier history rate capped.
* **Auth0 lifecycle**: `delete_account` allows auth0 users with typed DELETE + fresh session; `update_profile` allows auth0 users to set initial password.
* **Backup prune tie-break**: numeric suffix parsed (None=0) so same-second backups sort correctly.
* **Dodo Payments integration**: `DODO_WEBHOOK_SECRET` + `DODO_CHECKOUT_URL_PRO/BUSINESS`; Standard-Webhooks HMAC-SHA256 verification; idempotent via `processed_events`; 503 when unconfigured; honest UI when disabled.
* **Proxy-aware limiting**: `ProxyFix(x_for=1)` behind `TRUST_PROXY`; `RATELIMIT_STORAGE_URI`/`CACHE_TYPE` from `REDIS_URL`; `/version.json`, `/api/health`, `/static` exempt.
* **Monitoring hook cheap**: skips static/health/version; caches tier on `flask.g`.

### Behavior & Hardening (P2)

* **Enhancement failures surface**: `TextEnhancer.enhance()` raises on provider exhaustion; orchestrator emits `ENHANCEMENT_FAILED` + classified error; raw transcript injected as fallback.
* **Rich commands anchored**: triggers now `re.match` at start (`search for`, `google search for`, `draft email to`, `create github issue`, `send slack message`); opt-in via `rich_commands_enabled` (default true); `GITHUB_REPO` required; empty extraction returns False.
* **Injection/ANC/sound**: clipboard restore delay 60ms→150ms; `verified=False` for paste; ANC calibrates on quietest frames only, skips frame-0 speech, soft expander replaces gate; sound volume threaded (`0.02 + 0.13 * volume`).
* **Crypto & session hygiene**: `hmac.compare_digest` for legacy SHA-256; login transparently rehashes to PBKDF2; sessions stored hashed (sha256 server-side); `X-XSS-Protection` removed; CSP tightened (no `unsafe-inline`, CDN allowlist narrowed, fonts/Chart.js self-hosted).
* **Input validation**: settings/hotkeys allowlists with per-type checks; raw strings stored, escaped at render; language validated against ISO codes; `download_track` platform capped; `/api/stats` uses single `GROUP BY` query.
* **Desktop fixes**: Qt enum DPI attributes; `import sys` not `os.sys.path`; `unsubscribe` doesn't swallow `ValueError`; hotkey KeyCode matched by normalized char/vk; stats prune >90d; custom templates use `.replace("{text}", ...)` only; `_api_base()` empty sentinel disables cloud sign-in with clear copy.

### Website Redesign (P3)

* **Unified light design system** (`docs/DESIGN.md`): one light editorial palette across marketing pages and dashboard (paper `#fafafa`, ink `#1e1e1e`, hairline `#e5e5e5`, muted `#5f636e`); red ONLY for REC/destructive (AA `#d64545` on light), green ONLY success/online; one grotesk + one mono (self-hosted); hairline borders, subtle card shadows; record lamp motif; 150–250ms state transitions; no gradients, no glassmorphism, no badge clutter. The earlier dark "Control Room" pass was fully reverted and every dark-theme token, selector and JS hook was purged.
* **Vendored assets**: Space Grotesk + JetBrains Mono (woff2) in `web/static/fonts/`; Chart.js in `web/static/vendor/`; no CDN at runtime.
* **Consolidated CSS**: `base.css` + per-page files; one grid, one button, one card, one input; inline styles removed.
* **Honest copy**: features/pricing from `web/tier.py`; download from `/api/download/urls`; pricing CTAs respect `checkout_available`; Q&A shows real 403 upgrade.
* **Session**: `voxyFetch` handles `X-Session-Rotated`; no localStorage session id elsewhere.
* **A11y**: landmarks, focus-visible, 4.5:1 contrast, `prefers-reduced-motion`, keyboard-reachable, alt text.
* **Responsive**: 1440/768/390; mobile nav no library.
* **Perf**: `font-display: swap`, preload woff2, lazy images, JS <60KB (excl Chart.js).
* **CSP**: `default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data:; connect-src 'self' https://*.ingest.sentry.io...` — no CDN.
* **Same-origin downloads**: the download buttons hit `/download/<platform>`, which 302s to the resolved release asset — visitors download the app from the website and are never bounced to a GitHub page. `DOWNLOAD_URL_*` env overrides still win.
* **Serverless-ready startup**: the default data directory is only created when the database actually lives in the app tree; with `VOXYLIS_DB_PATH` pointed elsewhere (Vercel/immutable filesystems) the app imports cleanly on a read-only tree.
* **CI correctness**: updater e2e tests pin the host platform (the stub feed publishes a Windows installer), so the suite is green on Linux CI, not only on Windows.

### Desktop Frontend (P4)

* **Light theme only**: `ui/theme.py` ships the light palette (mirrors the website); the dark palette was removed; helper factories (`h1`, `body`, `primary_button`, `field_row`, `section_frame`, `lamp`, `meter`); same object names so `pages.py` works unchanged.
* **Desktop degrades gracefully offline**: reads entitlements from `/api/me`; local mode with clear copy when server unreachable.

---

## 3.0.0 — production release (hardening)

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
