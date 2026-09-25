# Voxylis — PythonAnywhere WSGI entry point (TEMPLATE, free tier)
#
# HOW TO USE (browser only, nothing on your laptop):
#   1. PythonAnywhere → Web → your app → WSGI configuration file
#      (path looks like /var/www/<PA_USER>_pythonanywhere_com_wsgi.py).
#   2. Replace that file's contents with this file, then replace EVERY
#      <PA_USER> below with your PythonAnywhere username and fill the
#      <PASTE-…> secrets (all values also documented in .env.example).
#   3. Web tab → Virtualenv: /home/<PA_USER>/.virtualenvs/voxylis
#      Source code: /home/<PA_USER>/voxyai   |   Working directory: same.
#   4. Press Reload. Open https://<PA_USER>.pythonanywhere.com/api/health
#      → {"version": "3.0.0", ...}.
#
# Secrets live ONLY in this file on the host (mode 600, never committed).

import os
import sys

# ---------------------------------------------------------------------------
# Secrets — paste real values, keep this file on the host only
# ---------------------------------------------------------------------------
os.environ.setdefault("SECRET_KEY", "<PASTE-64-hex-from-python-secrets-token_hex-32>")
os.environ.setdefault("VOXYLIS_ENV", "production")
os.environ.setdefault("VOXYLIS_DB_PATH", "/home/<PA_USER>/voxylis-data/voxylis.db")
os.environ.setdefault("CORS_ORIGINS", "https://voxylis-web.vercel.app")
os.environ.setdefault("FRONTEND_URL", "https://voxylis-web.vercel.app")
os.environ.setdefault("OWNER_EMAILS", "<PASTE-your-email>")

# Auth0 (SPA + Native device flow, already created)
os.environ.setdefault("AUTH0_DOMAIN", "dev-g4w68c5tpeyhxh3d.us.auth0.com")
os.environ.setdefault("AUTH0_CLIENT_ID", "yAAtiPLoCmlzGixp9HUSnUjfI4V83qfG")
os.environ.setdefault("AUTH0_DESKTOP_CLIENT_ID", "uhCL7jpmMZX3JRhTMVhZhYrbipbHDQdr")

# Server STT/QA chain (your provider keys, server-side only)
os.environ.setdefault("MODEL_API_KEY", "")
os.environ.setdefault("GROQ_API_KEY", "")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("OPENROUTER_API_KEY", "")

# Email via Gmail SMTP (free, no domain needed — app password, not your login)
os.environ.setdefault("EMAIL_PROVIDER", "smtp")
os.environ.setdefault("SMTP_HOST", "smtp.gmail.com")
os.environ.setdefault("SMTP_PORT", "587")
os.environ.setdefault("SMTP_USERNAME", "<PASTE-you@gmail.com>")
os.environ.setdefault("SMTP_PASSWORD", "<PASTE-16-char-app-password>")
os.environ.setdefault("SMTP_USE_TLS", "true")
os.environ.setdefault("EMAIL_FROM", "Voxylis <PASTE-you@gmail.com>")
os.environ.setdefault("SUPPORT_EMAIL", "<PASTE-you@gmail.com>")

# Sentry (optional, free tier)
os.environ.setdefault("SENTRY_DSN", "")
os.environ.setdefault("SENTRY_DSN_BROWSER", "")

# ---------------------------------------------------------------------------
# App (do not edit below)
# ---------------------------------------------------------------------------
sys.path.insert(0, "/home/<PA_USER>/voxyai")

from web.app import app as application  # noqa: E402
