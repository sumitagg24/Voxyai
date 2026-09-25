#!/bin/sh
# Voxylis Docker entrypoint: optional Litestream replication for SQLite.
#
# Render's free tier has an ephemeral filesystem: any restart/redeploy wipes
# the SQLite file. When LITESTREAM_BUCKET + LITESTREAM_ENDPOINT are set (with
# AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY holding a Backblaze B2 key), this
# script restores the DB from B2 on boot and replicates every write there, so
# the app survives restarts. Without those vars it just execs the CMD
# unchanged (local dev / hosts with persistent disks).

set -eu

if [ -n "${LITESTREAM_BUCKET:-}" ] && [ -n "${LITESTREAM_ENDPOINT:-}" ]; then
    : "${AWS_ACCESS_KEY_ID:?Set AWS_ACCESS_KEY_ID to the B2 key id}"
    : "${AWS_SECRET_ACCESS_KEY:?Set AWS_SECRET_ACCESS_KEY to the B2 application key}"
    DB_PATH="${VOXYLIS_DB_PATH:-/app/web/data/voxylis.db}"
    mkdir -p "$(dirname "$DB_PATH")"
    cat > /tmp/litestream.yml <<EOF
dbs:
  - path: $DB_PATH
    replicas:
      - url: s3://$LITESTREAM_BUCKET/voxylis.db
        endpoint: $LITESTREAM_ENDPOINT
EOF
    echo "[entrypoint] restoring SQLite from B2 replica if one exists..."
    litestream restore -if-replica-exists -config /tmp/litestream.yml "$DB_PATH" || true
    echo "[entrypoint] starting litestream replicate in background"
    litestream replicate -config /tmp/litestream.yml &
fi

exec "$@"
