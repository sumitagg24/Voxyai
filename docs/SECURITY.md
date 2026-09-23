# Voxylis Security

## Reporting a vulnerability

Open a private security advisory on
<https://github.com/sumitagg24/Voxyai/security/advisories/new> rather than a
public issue. Include the version from `config/version.py` (or `/api/health`),
reproduction steps and impact. Please do not include real API keys or real
transcripts in the report — redacted samples are enough.

## Trust boundaries

```
untrusted ───────────────────────────────────────────────────────────► trusted
browser JS   desktop client   network        backend
   │              │              │              │
   │              │              │              └─ authoritative for tier,
   │              │              │                 role, quotas, account state
   │              │              └─ TLS; provider responses are untrusted input
   │              └─ no authority: it reads state, never grants it
   └─ no authority: Origin/Referer are never used for authorization
```

**The desktop client and the website can never grant themselves anything.**
Tier, role and feature flags are read-only projections of server state.

## Secrets

| Secret | Storage | Never |
|---|---|---|
| Provider API keys (Groq, OpenAI; newer keys listed in `SECRET_CONFIG_KEYS`) | OS credential store via `utils/credentials.py` (DPAPI → keyring → obfuscated fallback) | written to `settings.json`, logged, included in diagnostics |
| Server `SECRET_KEY` | Environment variable | committed; the app refuses to start in production if it is missing, a known placeholder, or < 32 characters |
| Session tokens | OS credential store (desktop), `Authorization`-free `X-Session-Id` header (web) | put in URLs or logs |
| Passwords | PBKDF2-SHA256 with per-user salt via `werkzeug.security` | logged or returned by any endpoint |

Credential values are redacted by `utils.credentials.redact()` before any
display, log or diagnostics output. Plaintext keys found in a legacy settings
file are migrated into the vault and stripped from the JSON.

## Authentication and sessions

* Sessions are server-side rows in SQLite with an explicit `expires_at`.
* Sessions **rotate**: past a configurable age the server issues a new id,
  invalidates the old one, and returns the new id to the client
  (`X-Rotated-Session-Id` + the `rotated_session_id` field in JSON responses) so
  the client can persist it.
* Expired sessions are rejected, not silently renewed.
* Password reset and email confirmation use single-use, expiring tokens; the
  reset endpoint does not reveal whether an address exists.
* Session lookups are rate-limit keys too, so limits are per user, not only
  per IP.

## Authorization

* Every user-scoped endpoint resolves the caller from the session, never from a
  request body field such as `user_id`.
* Admin endpoints require an admin session and are audited.
* Subscription/tier changes are owned by `web/services/subscription_service.py`.
  Only a verified payment webhook, an audited admin action, or a development
  override that is refused in production can change a tier.
  `POST /api/subscription/upgrade` can no longer set a tier from a client
  request; `GET /api/subscription` reports whether self-service upgrade or
  checkout exists so the UI can hide what is not implemented.

## Transport and browser controls

* CORS uses an explicit allow-list (`CORS_ORIGINS`). There is no wildcard, and
  credentials are only allowed for listed origins.
* Security headers on every response: `Content-Security-Policy`,
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`,
  `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`,
  `Cross-Origin-Resource-Policy`.
* `MAX_CONTENT_LENGTH` caps request bodies at 1 MB.
* Rate limits are applied per route (auth endpoints are the tightest) with a
  per-user key when a session is present.

## Input handling

* All SQL uses parameter binding. There is no string-built SQL anywhere in
  `web/app.py`.
* The API returns JSON; user-supplied text is never echoed into HTML without
  escaping. The static pages are plain HTML with no dynamic interpolation of
  user content.
* File serving is restricted to the static folder; download routes build paths
  from a fixed table rather than from request input.
* Error handlers return generic messages. Internal exception text and stack
  traces are not returned to clients; they are logged server-side without
  secrets.
* The desktop app validates hotkeys against a reserved-combination list before
  registering them, and never executes anything from a downloaded artifact
  without a SHA-256 match against the release manifest.

## Dependency and release hygiene

CI runs lint, the test suite, a version-consistency check and a packaging smoke
build. `pip-audit` and secret scanning are run against releases (see
`docs/RELEASE.md`). Do not merge a change that suppresses a scanner finding to
make CI green — fix it or document why it is not exploitable.

## Known limitations

* **Unsigned development builds.** Public Windows releases are code-signed only
  when the signing certificate secrets are available in CI; unsigned builds
  trigger SmartScreen. This is stated on the download page instead of being
  hidden.
* **Rate limiting is per process.** The backend is designed for a single
  instance with SQLite; limits are in-memory. Adding instances requires a
  shared store before the limits mean anything.
* **Payment integration is not configured.** Checkout reports "unavailable"
  rather than pretending a subscription can be purchased, and no tier can be
  self-granted in production.
* **Elevated windows.** Windows rejects synthetic input into some elevated
  contexts (UAC prompts, Task Manager). Injection reports failure rather than
  claiming success.
