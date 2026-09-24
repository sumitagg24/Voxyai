# Voxylis deployment and manual configuration

Everything in this file is work that **cannot be done from the repository**: it
needs an account with a third party, a secret value, or a machine you control.
Nothing here is faked in code — where a service is unconfigured, the application
says so and refuses to pretend.

Legend: **Required** = the product is broken or dishonest without it.
**Recommended** = the product works, but you are flying blind.
**Optional** = a feature most deployments do not need.

Never paste a real secret into a file in this repository. `.env` is local-only
and gitignored; production values belong in the hosting provider's secret store.

---

## A. Local development

| Item | Where | Variable | Type | Required | Verify |
|---|---|---|---|---|---|
| Signing key | `.env` | `SECRET_KEY` | 64-char hex | Recommended | App logs a warning when missing; in production it refuses to start |
| App environment | `.env` | `VOXYLIS_ENV` | `development` \| `production` | No | `curl /api/health` → `subscription_policy.environment` |
| Database | `.env` | `VOXYLIS_DB_PATH` | path | No | Defaults to `web/data/voxylis.db` |

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"   # paste into SECRET_KEY
python -m web.app                                          # http://localhost:5000
python -m pytest tests -q && python -m flake8 .
```

Local dev intentionally runs the `console` email provider (nothing is delivered,
the message is logged) and leaves Sentry off. Neither is a production setting.

---

## B. Vercel (static website)

The site is a static export: `vercel.json` sets `outputDirectory: web/static`.

| Item | Where | Variable | Type | Required | Verify |
|---|---|---|---|---|---|
| API origin | `web/static/js/api.js` load order, or per-page `?api=` | `window.VOXYLIS_API_BASE` | https URL | Required if the API is on another host | Open the dashboard; the network tab shows requests to your API |
| Allowed origin | API host | `CORS_ORIGINS` | comma-separated origins | Required | `curl -H "Origin: https://your-site" -i /api/health` returns that origin, never `*` |

Security notes: keep the site on HTTPS. The CSP already allows
`https://*.ingest.sentry.io` for monitoring; if you move the API to a new host,
add it to `CORS_ORIGINS` rather than relaxing CORS to a wildcard.

---

## C. Backend server (Docker / gunicorn / Render / Railway)

| Item | Variable | Type | Required | Notes |
|---|---|---|---|---|
| Signing key | `SECRET_KEY` | 32+ random chars | **Required** | Startup fails without it in production |
| Database path | `VOXYLIS_DB_PATH` | path on a persistent volume | Required | Docker compose mounts `web-data` at `/app/web/data` |
| CORS | `CORS_ORIGINS` | comma-separated | Required | No wildcard is accepted |
| Cookies | `SESSION_COOKIE_*` | n/a | Not used | Sessions travel in the `X-Session-Id` header, not a cookie. `CORS_SUPPORTS_CREDENTIALS` defaults to false |
| Workers | `GUNICORN_WORKERS` | int | No | Defaults to `cpu_count * 2 + 1` |
| Proxy | forward `X-Forwarded-For` | – | Required behind a proxy | Rate limits key on the client IP |

Single-instance only: rate limits are in-process and the database is SQLite.
Do not scale horizontally without first moving both to a shared store.

---

## D. Database

SQLite, single writer, on a persistent volume. That is deliberate for a
single-instance deployment — see `docs/ARCHITECTURE.md`.

**MANUAL PRODUCTION CONFIGURATION REQUIRED — backups.** The application does
not create backups on a schedule; the tooling below has to be driven by cron,
Task Scheduler or the host's scheduler. Before you take traffic:

1. Schedule `python -m web.backup --backup-dir /backups/voxylis --keep 14`
   daily (a sensible floor) on the API host. Every run uses SQLite's online
   backup API — safe against a live, concurrently written database — then
   verifies the copy with `PRAGMA integrity_check` and a SHA-256 checksum
   before reporting success, and prunes backups beyond `--keep`.
2. Keep the backup directory on a **different volume** than the database, and
   make sure that volume is itself snapshotted or replicated by the host.
3. Test a restore into a scratch environment at least once, then whenever the
   version changes:
   `python -m web.backup --restore /backups/voxylis/voxylis-YYYYMMDD-HHMMSS.db --force`
   (stop the app first; `--force` is required before a non-empty live database
   is overwritten). Restore verifies the backup's integrity, replaces the file
   atomically and removes stale WAL sidecars.
4. Decide who owns restore, and write it down somewhere outside this repo.

The retention window is whatever `--keep` you schedule: 14 daily backups is
the default starting point. Document the chosen window and the restore owner
with your runbook, not in this repository.

Copying the live file with `cp`/`scp` while it is being written can produce a
corrupt backup — use the tooling above, a filesystem snapshot, or
`sqlite3 voxylis.db ".backup /backups/$(date +%F).db"` instead.

If you outgrow one instance, migrate to PostgreSQL as a documented project —
the code is written against `sqlite3` and does not silently switch engines.
A migration plan would need, at minimum: schema translation (the 15 tables
including `tier_audit`), a dual-write or freeze-and-cutover window, and a
rewritten `web/backup.py` against `pg_dump`/`pg_restore`. Do not start it as
a side effect of a deploy.

---

## E. Email provider — **MANUAL CONFIGURATION REQUIRED**

Without this, **email verification and password reset do not work**. The app
generates the token and then has no way to deliver it. Startup logs an error in
production when no provider is configured.

| Item | Variable | Type | Required |
|---|---|---|---|
| Adapter | `EMAIL_PROVIDER` | `resend` \| `smtp` \| `console` \| `auto` | Required (or leave `auto`) |
| API key | `EMAIL_API_KEY` | provider secret | Required for `resend` |
| Sender | `EMAIL_FROM` | `Name <address@domain>` | Required — must be a verified sender |
| Reply-to | `EMAIL_REPLY_TO` | address | Recommended |
| Support inbox | `SUPPORT_EMAIL` | address | Required — receives contact-form notifications |
| SMTP host | `SMTP_HOST` / `SMTP_PORT` / `SMTP_USERNAME` / `SMTP_PASSWORD` / `SMTP_USE_TLS` | strings | Required for `smtp` |
| Public origin | `FRONTEND_URL` | https URL | **Required** — every link is built from it |
| Link overrides | `EMAIL_VERIFICATION_URL`, `PASSWORD_RESET_URL` | URL with `{token}` | Optional |

Verify: `curl https://your-api/api/health` → `email.configured` is `true`.
Then sign up with a real inbox and confirm the message arrives and the link
lands on `/auth?verify_token=…`.

Security notes: use a dedicated sending subdomain with SPF, DKIM and DMARC
configured, or your mail lands in spam. Never let `FRONTEND_URL` stay
`localhost` in production — a reset link to `localhost` is useless and would be
mailed to a real user. Verification links expire in 24 hours, reset links in
1 hour, both are single use, and requesting a new one retires the old one.

---

## F. Sentry — **MANUAL CONFIGURATION REQUIRED**

| Item | Variable | Type | Required | Where |
|---|---|---|---|---|
| Server DSN | `SENTRY_DSN` | DSN URL | Optional | API host secret store |
| Browser DSN | `SENTRY_DSN_BROWSER` | DSN URL (public) | Optional | API host — served via `/api/public-config` |
| Environment | `SENTRY_ENVIRONMENT` | string | No | Defaults to the resolved environment |
| Release | `SENTRY_RELEASE` | string | No | Defaults to the canonical version `voxylis@3.0.0` |
| Trace rate | `SENTRY_TRACES_SAMPLE_RATE` | 0.0–1.0 | No | Defaults 0.05 production / 1.0 development |
| Release upload token | `SENTRY_AUTH_TOKEN` | token | Only for source-map upload | CI secret store — **never** in frontend code |

Behaviour: with no DSN, monitoring is off and the app runs normally. With a DSN
set but `sentry-sdk` missing, the app logs an error and keeps running.

What is sent: exception type, stack trace, route, method, status code, app
version, environment, subscription tier, and an internal user id. Frame locals
are dropped, request bodies are never attached (`max_request_body_size="never"`),
and headers, cookies and query strings are removed before an event leaves the
process. Session ids are reduced to a hash. Transcripts, prompts, clipboard
contents and API keys are scrubbed by key and by length.

Verify: `curl /api/health` → `monitoring.enabled`; trigger a 500 on a staging
host and confirm the event arrives **without** a request body or an email
address attached.

**Desktop app:** reporting is additionally gated on user consent (Settings →
Privacy → crash reports). It is off by default and a machine with no DSN
sends nothing even when ticked.

**Desktop DSN mechanism — runtime only, never baked into the build.** The
PyInstaller bundle contains no Sentry configuration and must never gain any:
both `utils/observability.dsn()` and the spec guardrail test enforce this. A
frozen build resolves its DSN at startup from, in priority order:

1. `SENTRY_DSN` in the process environment (CI, test runs, manual launches);
2. a file whose absolute path is in `SENTRY_DSN_FILE`, whose entire contents
   are the DSN URL — for installed machines, set once per machine with
   `setx SENTRY_DSN_FILE "C:\ProgramData\Voxylis\sentry-dsn.txt"` (the file
   itself is protected by normal filesystem ACLs). The file is only read when
   the build is frozen, so a developer workstation cannot pick one up by
   accident.

Consent always comes from the user (Settings → Privacy → Send crash reports,
stored as `share_crash_reports`). `SENTRY_DESKTOP_CRASH_REPORTS=true` is an
operator/CI verification switch, not a substitute for consent. With consent on
but no DSN resolvable, the app runs normally and reports nothing; that is the
supported state for un-configured deployments. To verify a deployment: set the
dsn, `setx SENTRY_DESKTOP_CRASH_REPORTS true`, launch the frozen app, confirm
the event appears in the project with no transcript, key or user path — then
remove the env var so real users decide for themselves.

---

## G. OAuth / social login (Auth0) — optional

| Item | Variable | Type | Required | Verify |
|---|---|---|---|---|
| Tenant | `AUTH0_DOMAIN` | `tenant.us.auth0.com` (no scheme) | Required for social login | `/api/auth/auth0/config` returns `enabled: true` |
| SPA client | `AUTH0_CLIENT_ID` | client id (public) | Required | Google/GitHub buttons complete a login |
| Desktop client | `AUTH0_DESKTOP_CLIENT_ID` | client id (public) | Optional | Device flow on a desktop build |

Register these callback URLs in Auth0: `https://your-site/dashboard`,
`https://your-site/auth`, and a native app entry for the desktop device flow.
Password signup is separate and is restricted by `PASSWORD_LOGIN_DOMAINS`; it
does not use Auth0 at all.

---

## H. Payment provider — **NOT IMPLEMENTED**

There is no checkout. The pricing page says paid plans are not purchasable yet,
and `POST /api/subscription/upgrade` refuses self-service changes: a tier can
only change through a verified webhook, an audited admin action, or a
development override that production ignores.

If you add a provider, `STRIPE_WEBHOOK_SECRET` is the single value the backend
already reads (`payments_configured()`). Until it is set, every webhook-sourced
change is refused with `payments_not_configured` (HTTP 503). Do not flip the
pricing page to "buy" until a real, signature-verified webhook path exists.

---

## I. GitHub releases

| Item | Where | Required | Notes |
|---|---|---|---|
| Publish the installer | GitHub Releases, tag matching `config/version.py` | To offer downloads | `Voxylis-Setup-<version>.exe` |
| `DOWNLOAD_URL_WINDOWS` | API host env | Only after the release exists | Empty means the site sends visitors to the releases page and labels the Windows card "not published yet" |
| `GITHUB_TOKEN` | CI secret | For release automation | Never in client code |

Verify: open the URL from `/api/download/urls` and confirm it downloads the file
whose name matches the current version.

---

## J. Windows code signing — **MANUAL CONFIGURATION REQUIRED**

Unsigned installers trigger SmartScreen warnings, so this is required for a real
release. You need an Authenticode certificate (OV or EV) from a CA.

| Item | Where | Type |
|---|---|---|
| Certificate file | CI secret / secure store | `.pfx` (never committed) |
| Certificate password | CI secret | string |
| Timestamp server | release workflow | URL |

The release workflow already looks for certificate secrets and skips signing when
they are absent, producing an unsigned build instead of failing. Install the
certificate, add the secrets, and verify with:

```powershell
Get-AuthenticodeSignature .\dist\Voxylis\Voxylis.exe | Format-List Status, SignerCertificate
```

`Status` must read `Valid`. Removing the SmartScreen warning takes time even with
a valid signature — that is a reputation process, not a code change.

---

## K. DNS, HTTPS, headers

- Point the site and API at HTTPS; never serve auth over plain HTTP.
- HSTS is not set by the app (it is a host-level decision). Enable it at the
  CDN once you are sure every subdomain is HTTPS.
- The API sets CSP, `nosniff`, `SAMEORIGIN`, a referrer policy and a
  permissions policy on every response. If you add a third-party script, add it
  to the CSP explicitly — do not add `*`.

---

## L. Desktop application

| Item | Where | Notes |
|---|---|---|
| API base URL | build-time config | The desktop talks to the API you point it at |
| User data root | `VOXYLIS_HOME` | Defaults to `%LOCALAPPDATA%\Voxylis` |
| Update feed | `VOXYLIS_UPDATE_FEED` | Signed release manifest; verified checksum before apply |
| Provider keys | Settings → AI Providers | Stored in the OS credential store (DPAPI / Keychain / Secret Service), never in a settings file |

Never ship a build with a provider key embedded: the desktop is BYOK by design.

---

## M. Monitoring and backups

- Uptime check on `GET /api/health` (`email.configured` and
  `monitoring.enabled` are reported there, so one endpoint tells you whether the
  two most commonly forgotten settings are live).
- Watch for repeated `tier_audit` rows with `source = admin`: that is somebody
  changing plans manually.
- Database backups per section D. Also decide how long you keep
  `contact_messages` and `newsletter_subscribers`, both of which are personal
  data, and write that retention down.

---

## Summary of what is genuinely blocked today

| Blocker | Effect | Section |
|---|---|---|
| No email provider key | Verification and reset mail is not delivered | E |
| No Sentry DSN | No error visibility (app is unaffected) | F |
| No payment provider | Pro/Business cannot be purchased; site says so | H |
| No code-signing certificate | Installers are unsigned; SmartScreen warns | J |
| No published release artifact | Download page points at the releases page | I |
| No backup schedule | No point-in-time recovery | D |
