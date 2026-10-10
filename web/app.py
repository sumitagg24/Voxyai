"""Voxylis Web Server - app factory with blueprints (behavior preserved)."""

import logging
import os
import secrets
from pathlib import Path

import requests as http_requests  # noqa: F401  (re-exported for backwards compat)

from flask import Flask, g, jsonify, request
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

from web import observability
from web.auth_helpers import _verify_session, get_user_tier
from web.db import _init_db, get_db_path
from web.extensions import cache, cache_config, limiter, limiter_storage_uri, trust_proxy
from web.services import email_service, subscription_service

logger = logging.getLogger(__name__)

# Give the application logger a real output handler. Without this, INFO records
# from the app (email delivery, quota notices, pipeline fallbacks) are dropped by
# Python's logging-of-last-resort, which only prints warnings and above — so the
# container log would show nothing at all about a failed verification email.
# ``basicConfig`` is a no-op when a runner (gunicorn) already configured root.
logging.basicConfig(
    level=getattr(logging, (os.environ.get("LOG_LEVEL") or "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

# Load .env *before* anything reads the environment.
# This used to run after SECRET_KEY and CORS_ORIGINS were resolved, so a .env
# file was silently ignored for exactly the values that matter most: the
# signing key and the allowed origins.
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

#: Overridable so tests and containers can point at a scratch database.
#: Recomputed on every import/reload so VOXYLIS_DB_PATH changes take effect.
DB_PATH = get_db_path()
try:
    import web.db as _db_module

    _db_module.DB_PATH = DB_PATH
except Exception:
    pass

#: Secrets that must never be used as a real signing key.
_PLACEHOLDER_SECRETS = {
    "change-me-in-production",
    "your_secret_key_here_change_in_production",
    "secret",
    "dev",
}


class InsecureConfiguration(RuntimeError):
    """Raised at import time when production security settings are missing."""


def _resolve_secret_key() -> str:
    """Resolve and validate SECRET_KEY.

    A per-process random key silently breaks sessions across workers and hides
    a misconfigured deployment. In production we therefore refuse to start
    rather than run with an insecure or ephemeral key.
    """

    provided = (os.environ.get("SECRET_KEY") or "").strip()
    insecure = not provided or provided.lower() in _PLACEHOLDER_SECRETS or len(provided) < 32
    if not insecure:
        return provided

    if subscription_service.is_production():
        raise InsecureConfiguration(
            "SECRET_KEY must be set to a random value of at least 32 characters in production. "
            'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
        )

    logger.warning(
        "SECRET_KEY is unset or too weak — using an ephemeral development key. " "Set SECRET_KEY before deploying."
    )
    return secrets.token_hex(32)


def create_app() -> Flask:
    """Build and configure the Flask application (all behavior preserved)."""

    app = Flask(__name__, static_folder="static")
    # Behind a proxy (Render, Fly, nginx) TLS is terminated upstream and the
    # client IP arrives in X-Forwarded-For. Honour exactly one proxy hop — and
    # only when TRUST_PROXY says one is there — so rate limits key on the real
    # client instead of the proxy. Never enable with direct client connections:
    # the header would be client-controlled and limits trivially bypassable.
    if trust_proxy():
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)
    # CORS origins are env-configurable so a separately-hosted frontend
    # (e.g. https://<your-name>.onrender.com) can reach the API. Same-origin
    # localhost:5000 is the default; Flask serves web/static itself.
    # Set CORS_ORIGINS as a comma-separated list to override the defaults.
    _cors_origins = [
        o.strip()
        for o in os.environ.get(
            "CORS_ORIGINS",
            "http://localhost:5000,http://127.0.0.1:5000",
        ).split(",")
        if o.strip()
    ]
    # The API authenticates with an explicit `X-Session-Id` header, not with
    # cookies, so the browser never needs to attach credentials to a cross-origin
    # request. Leaving `Access-Control-Allow-Credentials` off removes a whole class
    # of ambient-authority mistakes; set CORS_SUPPORTS_CREDENTIALS=true only if a
    # cookie-based client is introduced deliberately.
    _cors_credentials = (os.environ.get("CORS_SUPPORTS_CREDENTIALS") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    CORS(app, origins=_cors_origins, supports_credentials=_cors_credentials, expose_headers=["X-Session-Rotated"])

    cache.init_app(app, config=cache_config())

    # Rate limiting. The store is REDIS_URL when set (shared, exact counts),
    # otherwise in-process memory — which is per-worker, so the effective
    # default limits scale with GUNICORN_WORKERS (documented in DEPLOYMENT §C).
    app.config["RATELIMIT_STORAGE_URI"] = limiter_storage_uri()
    limiter.init_app(app)

    app.config["JSON_SORT_KEYS"] = False
    app.config["JSONIFY_PRETTYPRINT_REGULAR"] = False
    app.config["MAX_CONTENT_LENGTH"] = 33554432  # 32 MB request cap (audio uploads)
    app.config["SECRET_KEY"] = _resolve_secret_key()

    # Error monitoring. No DSN (or no SDK) simply means monitoring is off: the API
    # must never depend on a third-party service being reachable.
    observability.init_sentry(app)
    # Say plainly, once, when mail cannot be delivered. A silently misconfigured
    # email provider means every verification and password reset is lost.
    email_service.warn_if_unconfigured()

    #: Paths the monitoring hook never touches the database for: static
    #: assets, the version stamp and the health check carry no session, so a
    #: lookup would be pure overhead (and a DB failure there must never be
    #: able to break a health check).
    _MONITORING_SKIP_PATHS = frozenset({"/version.json", "/api/health", "/favicon.ico"})

    def _monitoring_tier(user_id: int) -> str:
        """Tier for the monitoring hook, cached per request on ``flask.g``.

        The hook and the endpoint each resolve the tier independently; without
        the cache a single authenticated request pays for the lookup twice.
        ``g`` is request-scoped, so nothing leaks across requests.
        """
        try:
            cached = getattr(g, "_tier_cache", None)
        except RuntimeError:  # outside a request context: just look it up
            return get_user_tier(user_id)
        if isinstance(cached, dict) and user_id in cached:
            return cached[user_id]
        tier = get_user_tier(user_id)
        try:
            if not isinstance(getattr(g, "_tier_cache", None), dict):
                g._tier_cache = {}
            g._tier_cache[user_id] = tier
        except RuntimeError:
            pass
        return tier

    @app.before_request
    def attach_monitoring_context():
        """Tag the Sentry scope with the internal user id (never the email).

        Strictly read-only: rotation lives in the endpoint's own
        ``_verify_session`` call so it happens at most once per request.
        Static assets, /version.json, /api/health and the favicon skip the
        database entirely. Database errors are swallowed silently — a
        monitoring hook must never fail, slow, or log-noise a request.
        """

        if not observability.is_enabled():
            return None
        path = request.path
        if path in _MONITORING_SKIP_PATHS or path.startswith("/static"):
            return None
        try:
            session_id = request.headers.get("X-Session-Id", "")
            if session_id:
                user_id = _verify_session(session_id, rotate=False)
                if user_id is not None:
                    observability.set_user(user_id, _monitoring_tier(user_id))
        except Exception:
            pass
        return None

    @app.after_request
    def security_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "SAMEORIGIN"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        resp.headers["Permissions-Policy"] = "microphone=(self), clipboard-read=(self), clipboard-write=(self)"
        resp.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        # Sentry ingest endpoints are allowed for browser error reporting; without
        # them the browser SDK could not report anything under this policy.
        # P2.4: the VOXYLIS_API_BASE bootstrap lives in /static/js/config.js so
        # script-src needs no 'unsafe-inline'. Chart.js (dashboard) is the only
        # remaining CDN (jsdelivr); unpkg.com was dropped (unused).
        # NOTE (P3.3): remaining inline page scripts + onclick handlers still
        # need vendoring into /static/js; they are tracked for P3.3.
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self' https://*.ingest.sentry.io https://*.ingest.us.sentry.io "
            "https://*.ingest.de.sentry.io; "
            "frame-ancestors 'self'"
        )
        # A session older than 24h is transparently rotated inside _verify_session().
        # Tell the client its new id, otherwise it would keep using a dead session.
        rotated = getattr(g, "rotated_session_id", None)
        if rotated:
            resp.headers["X-Session-Rotated"] = rotated
        return resp

    # Blueprints (every @app.route lives in one of these; same URLs preserved).
    from web.routes.account import account_bp
    from web.routes.auth import auth_bp
    from web.routes.content import content_bp
    from web.routes.pages import pages_bp
    from web.routes.usage import usage_bp
    from web.routes.webhooks import webhooks_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(usage_bp)
    app.register_blueprint(content_bp)
    app.register_blueprint(webhooks_bp)

    # Health, version and static assets are exempt from the default rate
    # limits: uptime monitors and browsers hit these constantly, and none of
    # them does expensive work. Route-specific limits (none on these views)
    # are unaffected; only the extension-wide defaults are skipped.
    for _exempt_endpoint in ("content.version_json", "content.health", "static"):
        try:
            _exempt_view = app.view_functions.get(_exempt_endpoint)
            if _exempt_view is not None:
                limiter.exempt(_exempt_view)
        except Exception:
            pass

    @app.errorhandler(404)
    def not_found(error):
        """HTML 404 page for site navigations, JSON for API paths.

        API clients (and tests) keep getting structured JSON; a visitor who follows
        a dead link gets a real page instead of a bare JSON string.
        """

        if request.path.startswith("/api/"):
            return jsonify({"error": "Not found"}), 404
        return app.send_static_file("404.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        """Return a plain message and keep the traceback out of the response.

        The detail is already captured by the logs and by Sentry; leaking it to the
        caller would hand an attacker the file layout and dependency versions.
        """

        try:
            observability.capture_exception(getattr(error, "original_exception", None) or error, category="http_500")
        except Exception:
            pass
        return jsonify({"error": "Server error"}), 500

    @app.errorhandler(413)
    def request_too_large(error):
        """JSON 413 for oversized bodies/uploads (never Flask HTML on /api/*)."""
        return jsonify({"success": False, "error": "Request too large (max 32 MB)"}), 413

    @app.errorhandler(429)
    def rate_limited(error):
        """JSON 429 for rate-limited routes (never Flask HTML on /api/*)."""
        retry_after = None
        try:
            retry_after = getattr(error, "retry_after", None)
        except Exception:
            retry_after = None
        payload = {"success": False, "error": "Rate limit exceeded, try again later."}
        resp = jsonify(payload)
        resp.status_code = 429
        if retry_after:
            try:
                resp.headers["Retry-After"] = str(int(retry_after))
            except Exception:
                pass
        return resp

    @app.errorhandler(400)
    def bad_request(error):
        """JSON 400 for malformed requests (never Flask HTML on /api/*)."""
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "error": "Bad request"}), 400
        return jsonify({"success": False, "error": "Bad request"}), 400

    # Fresh state on every create_app()/reload (tests reload web.app per case).
    try:
        limiter.reset()
    except Exception:
        pass
    try:
        with app.app_context():
            cache.clear()
    except Exception:
        try:
            cache.clear()
        except Exception:
            pass
    try:
        from web.routes.auth import _jwks_cache

        _jwks_cache.update(keys=[], fetched_at=None)
    except Exception:
        pass
    try:
        from web.routes.content import _DOWNLOAD_CACHE

        _DOWNLOAD_CACHE.update(at=0.0, payload=None)
    except Exception:
        pass

    # Initialise DB at app creation (was at import time before).
    _init_db()
    # Keep DB_PATH in sync for `web_app.DB_PATH` readers.
    try:
        global DB_PATH  # noqa: PLW0603  (module-level re-export, re-read on reload)
        DB_PATH = get_db_path()
        _db_module.DB_PATH = DB_PATH
    except Exception:
        pass
    return app


app = create_app()

# ---------------------------------------------------------------------------
# Legacy re-exports (tests do `import web.app as web_app` and use these).
# ---------------------------------------------------------------------------
from config.version import (  # noqa: F401,E402
    APP_NAME,
    ENGINE_NAME,
    RELEASES_URL,
    REPO_URL as REPOSITORY_URL,
)
from config.version import __version__ as APP_VERSION  # noqa: F401,E402
from web.auth_helpers import (  # noqa: F401,E402
    _check_password,
    _create_session,
    _delete_session_ids,
    _ensure_admin,
    _ensure_owner,
    _extract_session,
    _hash_password,
    _hash_session_id,
    _is_hex,
    _is_legacy_sha256,
    _issue_email_token,
    _notify_usage_threshold,
    _sanitize,
    _text,
    _valid_identifier,
    _valid_name,
    _valid_password,
    check_transcription_quota,
    get_monthly_transcription_count,
    get_user_entitlements,
    has_feature,
    is_admin,
    is_email_verified,
    is_owner,
    normalize_email,
    record_usage,
    require_admin,
    require_auth,
    require_verified_email,
)
from web.content.blog_posts import BLOG_POSTS, LEGACY_BLOG_SLUGS  # noqa: F401,E402
from web.db import BASE_DIR, DB_DIR, _get_db, get_db_path as get_db_path, utcnow  # noqa: F401,E402
from web.routes.auth import _auth0_jwks, _verify_auth0_token  # noqa: F401,E402
from web.routes.usage import (  # noqa: F401,E402
    _any_llm_key_configured,
    _call_llm_for_enhancement,
    _call_llm_for_qa,
)
from web.services import email_preferences, llm_service  # noqa: F401,E402
from web.tier import (  # noqa: F401,E402
    FREE_MONTHLY_TRANSCRIPTIONS,
    OWNER_MONTHLY_TRANSCRIPTIONS,
    TIER_BUSINESS,
    TIER_ENHANCEMENT_MODES,
    TIER_FEATURES,
    TIER_FREE,
    TIER_OWNER,
    TIER_QUOTAS,
    TIER_STT_MODES,
)

if __name__ == "__main__":
    os.makedirs(app.static_folder, exist_ok=True)
    os.makedirs(os.path.join(app.static_folder, "docs"), exist_ok=True)
    DB_DIR.mkdir(parents=True, exist_ok=True)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
