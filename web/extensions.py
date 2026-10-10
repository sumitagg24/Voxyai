"""Shared Flask extensions (created without app, init via init_app)."""

import logging
import os

from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

logger = logging.getLogger(__name__)

cache = Cache()
limiter = Limiter(key_func=get_remote_address, default_limits=["240 per hour", "60 per minute"])


def _truthy(value: str) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


def trust_proxy() -> bool:
    """True when the app runs behind a proxy that sets ``X-Forwarded-For``."""
    return _truthy(os.environ.get("TRUST_PROXY") or "")


def limiter_storage_uri() -> str:
    """Rate-limit store: ``REDIS_URL`` when set, otherwise in-process memory.

    Read lazily (at ``create_app`` time, not import time) so tests and
    containers can point at a scratch backend per process. Memory storage is
    per-worker: with N gunicorn workers each one counts separately, so the
    effective default limits are roughly N times the configured values. Set
    ``REDIS_URL`` (and install the ``redis`` package) for exact shared
    counting. A ``REDIS_URL`` without the ``redis`` package falls back to
    memory with a warning instead of refusing to start.
    """
    url = (os.environ.get("REDIS_URL") or "").strip()
    if not url:
        return "memory://"
    try:
        import redis  # noqa: F401
    except ImportError:
        logger.warning("REDIS_URL is set but the 'redis' package is not installed; using memory rate limits")
        return "memory://"
    return url


def cache_config() -> dict:
    """Flask-Caching config: ``CACHE_TYPE`` from the environment.

    Defaults to ``SimpleCache`` (per-worker memory, same caveat as the rate
    limiter). ``RedisCache`` honours ``CACHE_REDIS_URL`` (falling back to
    ``REDIS_URL``); without any Redis URL it degrades to ``SimpleCache`` with
    a warning instead of failing on first cache use.
    """
    cache_type = (os.environ.get("CACHE_TYPE") or "SimpleCache").strip() or "SimpleCache"
    config: dict = {"CACHE_TYPE": cache_type, "CACHE_DEFAULT_TIMEOUT": 300}
    if cache_type.lower() == "rediscache":
        redis_url = (os.environ.get("CACHE_REDIS_URL") or os.environ.get("REDIS_URL") or "").strip()
        if redis_url:
            config["CACHE_REDIS_URL"] = redis_url
        else:
            logger.warning("CACHE_TYPE=RedisCache without CACHE_REDIS_URL/REDIS_URL; using SimpleCache")
            config["CACHE_TYPE"] = "SimpleCache"
    return config
