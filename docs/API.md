# Voxylis API Documentation

Base URL: `https://voxylis.com` (production) or `http://localhost:5000` (development)

All responses are JSON. Authentication uses `X-Session-Id` header or `session_id` in request body.

## Authentication

### POST /api/auth/signup
Create a new account.

**Request:**
```json
{
  "name": "John Doe",
  "email_or_phone": "john@example.com",
  "password": "securepassword123"
}
```

**Response (201):**
```json
{
  "success": true,
  "user_id": 1,
  "session_id": "abc123...",
  "name": "John Doe",
  "email_or_phone": "john@example.com",
  "onboarding": {
    "steps": [...],
    "completed": {}
  }
}
```

**Rate Limit:** 10 per hour

---

### POST /api/auth/login
Sign in to an existing account.

**Request:**
```json
{
  "email_or_phone": "john@example.com",
  "password": "securepassword123"
}
```

**Response (200):**
```json
{
  "success": true,
  "user_id": 1,
  "session_id": "abc123...",
  "name": "John Doe",
  "email_or_phone": "john@example.com"
}
```

**Rate Limit:** 10 per 15 minutes

---

### POST /api/auth/verify
Verify a session is still valid.

**Request:**
```json
{
  "session_id": "abc123..."
}
```

**Response (200):**
```json
{
  "valid": true,
  "user_id": 1,
  "name": "John Doe",
  "email_or_phone": "john@example.com",
  "onboarding": {
    "steps": [...],
    "completed": {"account": true, "download": false, ...}
  }
}
```

---

### POST /api/auth/logout
Delete a session.

**Request:**
```json
{
  "session_id": "abc123..."
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Logged out"
}
```

---

### POST /api/auth/forgot-password
Request a password reset token.

**Request:**
```json
{
  "email": "john@example.com"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "If an account exists, a reset link has been sent."
}
```

**Rate Limit:** 5 per hour

---

### POST /api/auth/reset-password
Reset password using a token.

**Request:**
```json
{
  "token": "reset_token_from_email",
  "password": "newsecurepassword123"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Password reset successful"
}
```

**Rate Limit:** 10 per hour

---

### POST /api/auth/verify-email
Send email verification (requires auth).

**Headers:** `X-Session-Id: <session_id>`

**Response (200):**
```json
{
  "success": true,
  "message": "Verification email sent"
}
```

**Rate Limit:** 5 per hour

---

### POST /api/auth/confirm-email
Confirm email with token.

**Request:**
```json
{
  "token": "verification_token"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Email verified successfully"
}
```

---

### POST /api/auth/update-profile
Update user profile (requires auth).

**Headers:** `X-Session-Id: <session_id>`

**Request:**
```json
{
  "name": "New Name",
  "current_password": "currentpass",
  "new_password": "newpass123"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Profile updated"
}
```

---

## User Data

### GET /api/me
Get current user profile (requires auth).

**Headers:** `X-Session-Id: <session_id>`

**Response (200):**
```json
{
  "success": true,
  "user": {
    "id": 1,
    "name": "John Doe",
    "email_or_phone": "john@example.com",
    "created_at": "2026-01-01 00:00:00",
    "onboarding": {...}
  }
}
```

---

### GET/POST /api/settings
Get or update user settings (requires auth).

**GET Response:**
```json
{
  "status": "success",
  "settings": {
    "theme": "light",
    "language": "en",
    "notifications": true,
    "sound": true,
    "autoStart": false,
    "hotkey": "Win+Shift",
    "wakeWord": "Voxy",
    "wakeWordSensitivity": 70
  }
}
```

**POST Request:** Send any subset of settings to update.

**Rate Limit:** 30 per minute

---

### GET/POST /api/hotkeys
Get or update user hotkeys (requires auth).

**GET Response:**
```json
{
  "status": "success",
  "hotkeys": {
    "record": "Win+Shift",
    "casual": "Win+Alt",
    "technical": "Win+Ctrl",
    "settings": "Win+;"
  }
}
```

**Rate Limit:** 30 per minute

---

### GET/POST /api/history
Get or add transcription history (requires auth for POST).

**POST Request:**
```json
{
  "text": "Hello world",
  "enhanced": true,
  "mode": "formal",
  "language": "en"
}
```

**GET Response:**
```json
{
  "status": "success",
  "history": [
    {
      "id": 1,
      "text": "Hello world",
      "enhanced": true,
      "mode": "formal",
      "language": "en",
      "timestamp": "2026-01-01 12:00:00"
    }
  ]
}
```

**Rate Limit:** 30 per minute

---

### GET/POST /api/onboarding
Get or update onboarding progress (requires auth).

**POST Request:**
```json
{
  "step": "download",
  "done": true
}
```

---

## Content

### GET /api/features
Returns feature list (cached 1 hour).

### GET /api/pricing
Returns pricing tiers (cached 1 hour).

### GET /api/stats
Returns usage statistics.

### GET /api/stats/public
Returns public user/transcription counts.

### GET /api/subscription
Returns current subscription status (requires auth).

```json
{
  "status": "success",
  "subscription": {
    "plan": "Free",
    "tier": "free",
    "price": 0,
    "renewalDate": null,
    "status": "active",
    "usage": { "transcriptions": 0, "limit": "100/month", "max": 100, "percentage": 0 },
    "can_self_upgrade": false,
    "checkout_available": false
  }
}
```

Logged-out visitors get Free-tier defaults plus `"authenticated": false`.
`can_self_upgrade` and `checkout_available` are false whenever no payment
provider is configured, so a client can hide a control that cannot complete.

### POST /api/subscription/upgrade
**This endpoint cannot grant a tier from a client request.** Sending a `tier`
in the body has no effect. Tier changes are owned by
`web/services/subscription_service.py` and come from exactly one of:

| Source | Allowed in production |
|---|---|
| `payment_webhook` — a verified webhook from the payment provider | yes (once configured) |
| `admin` — an admin acting on a user, audited | yes |
| `development` — the `ALLOW_DEV_TIER_CHANGE` override | **no** |

With no payment provider configured the endpoint answers `403` and reports why:

```json
{
  "success": false,
  "code": "self_service_tier_change_disabled",
  "error": "Plans cannot be changed from the app. Paid plans must be purchased through the payment provider.",
  "payments_configured": false
}
```

Other denial codes: `admin_required` (403), `owner_restricted` (403),
`invalid_tier` / `invalid_source` (400), `user_not_found` (404),
`payments_not_configured` (503), `webhook_unverified` (401). Every decision is
written to the `tier_audit` table with the old tier, new tier, source and actor.

Production flow, once payment is wired up:

```text
client → checkout → payment provider → verified webhook → backend
       → subscription state → client reads state from GET /api/subscription
```

The desktop client never grants itself Pro/Business access, and development
controls are separated from production controls rather than shipped.

---

## Q&A

### POST /api/qa
Ask Voxy a question.

**Request:**
```json
{
  "question": "What is Voxylis?"
}
```

**Response (200):**
```json
{
  "status": "success",
  "question": "What is Voxylis?",
  "answer": "Voxylis is a voice-to-text assistant...",
  "timestamp": "2026-01-01T12:00:00"
}
```

**Rate Limit:** 30 per minute

---

## Contact & Newsletter

### POST /api/contact
Submit a contact message.

**Request:**
```json
{
  "name": "John",
  "email": "john@example.com",
  "subject": "Question",
  "message": "How do I...?"
}
```

**Rate Limit:** 10 per hour

---

### POST /api/newsletter
Subscribe to newsletter.

**Request:**
```json
{
  "email": "john@example.com"
}
```

**Rate Limit:** 10 per hour

---

## Blog

### GET /api/blog
List all blog posts.

### GET /api/blog/:slug
Get a single blog post by slug.

---

## System

### GET /api/health
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-01T12:00:00",
  "version": "3.0.0",
  "subscription_policy": {
    "environment": "production",
    "payments_configured": false,
    "dev_tier_change_enabled": false,
    "self_service_upgrade_available": false
  }
}
```

`version` is read from `config/version.py`, so it cannot drift from the desktop
build, the installer or the website. `subscription_policy` never contains a
secret and is safe to expose.

---

### GET /api/download/urls
Returns download URLs for all platforms.

### GET /api/download/detect
Detects OS from User-Agent header.

### POST /api/download/track
Tracks a download click.

---

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| Global default | 240/hr, 60/min |
| Signup | 10/hr |
| Login | 10/15min |
| Forgot password | 5/hr |
| Reset password | 10/hr |
| Verify email | 5/hr |
| Confirm email | 10/hr |
| Update profile | 10/hr |
| Settings | 30/min |
| Hotkeys | 30/min |
| History | 30/min |
| Q&A | 30/min |
| Contact | 10/hr |
| Newsletter | 10/hr |
| Download track | 60/min |

Authenticated users are rate-limited by user ID. Unauthenticated requests are limited by IP address.
