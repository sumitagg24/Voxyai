FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Litestream: continuous SQLite replication to S3-compatible storage
# (Backblaze B2 free tier). Lets the app survive ephemeral disks
# (Render free tier) — see docker-entrypoint.sh.
ARG LITESTREAM_VERSION=0.3.13
RUN curl -fsSL -o /tmp/litestream.tar.gz \
        "https://github.com/benbjohnson/litestream/releases/download/v${LITESTREAM_VERSION}/litestream-v${LITESTREAM_VERSION}-linux-amd64.tar.gz" \
    && tar -xzf /tmp/litestream.tar.gz -C /usr/local/bin litestream \
    && rm /tmp/litestream.tar.gz \
    && litestream version

# Install Python dependencies — server-only: the full requirements.txt pulls
# desktop packages (PyQt5, pynput, sounddevice) the API never imports.
COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt gunicorn

# Copy application (gunicorn.conf.py lives at the repo root — the CMD needs it)
COPY web/ web/
COPY config/ config/
COPY gunicorn.conf.py .

# Create data directory
RUN mkdir -p web/data

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health')" || exit 1

# Entrypoint restores/replicates SQLite via Litestream when LITESTREAM_* is set,
# otherwise it execs the CMD unchanged.
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["docker-entrypoint.sh"]

# Run with gunicorn. The config binds $PORT (Render injects its own port;
# defaults to 5000 locally) — never hard-code the port here.
CMD ["gunicorn", "-c", "gunicorn.conf.py", "web.app:app"]
