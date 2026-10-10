"""Shared Flask extensions (created without app, init via init_app)."""

from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

cache = Cache()
limiter = Limiter(key_func=get_remote_address, default_limits=["240 per hour", "60 per minute"])
