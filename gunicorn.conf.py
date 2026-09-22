"""Gunicorn configuration for Voxylis production deployment."""

import os
import multiprocessing

# Server socket
bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"

# Worker processes
workers = int(os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "gthread"
threads = 2
timeout = 120
keepalive = 5

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")

# Process naming
proc_name = "voxylis"

# Security
limit_request_line = 8190
limit_request_fields = 100
limit_request_field_size = 8190

# Server mechanics
preload_app = True
daemon = False
