#!/usr/bin/env sh
# Voxylis disaster-recovery drill: restore the SQLite database from the
# Litestream replica into a scratch file and verify what came back.
#
# Usage (run from the repository root):
#   scripts/drill_restore.sh                       # B2 replica (LITESTREAM_* env)
#   scripts/drill_restore.sh --local-replica DIR   # drill against a local replica
#   scripts/drill_restore.sh --keep                # keep the scratch restore for inspection
#
# Exit codes: 0 = drill passed, 1 = verification failed, 2 = usage error,
#             3 = skipped (Litestream is not configured / binary missing).
#
# Run quarterly — see docs/RUNBOOK.md § "Quarterly restore drill".

set -eu

KEEP=0
LOCAL_REPLICA="${LITESTREAM_LOCAL_REPLICA:-}"
DB_SOURCE="${VOXYLIS_DB_PATH:-/app/web/data/voxylis.db}"

while [ $# -gt 0 ]; do
    case "$1" in
        --local-replica)
            shift
            LOCAL_REPLICA="${1:?--local-replica needs a directory}"
            ;;
        --db)
            shift
            DB_SOURCE="${1:?--db needs a path}"
            ;;
        --keep)
            KEEP=1
            ;;
        -h | --help)
            sed -n '2,14p' "$0"
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 2
            ;;
    esac
    shift
done

say() { printf '%s\n' "$*"; }
fail() {
    say "FAIL: $*" >&2
    exit 1
}

if [ ! -f web/backup.py ]; then
    say "Run this drill from the repository root (web/backup.py not found)." >&2
    exit 2
fi

if ! command -v litestream >/dev/null 2>&1; then
    say "SKIPPED: litestream is not installed on this host."
    say "  Install it (https://litestream.io/install/) or run this drill on the"
    say "  Render container. Nothing was restored or verified; this is an honest"
    say "  skip, not a pass."
    exit 3
fi

WORKDIR="$(mktemp -d)"
cleanup() {
    if [ "$KEEP" -ne 1 ]; then
        rm -rf "$WORKDIR"
    fi
}
trap cleanup EXIT

CONFIG="$WORKDIR/litestream.yml"
SCRATCH="$WORKDIR/restore.db"

if [ -n "$LOCAL_REPLICA" ]; then
    say "Mode: local replica at $LOCAL_REPLICA"
    cat >"$CONFIG" <<EOF
dbs:
  - path: $DB_SOURCE
    replicas:
      - url: file://$LOCAL_REPLICA
EOF
elif [ -n "${LITESTREAM_BUCKET:-}" ] && [ -n "${LITESTREAM_ENDPOINT:-}" ]; then
    : "${AWS_ACCESS_KEY_ID:?Set AWS_ACCESS_KEY_ID to the B2 key id}"
    : "${AWS_SECRET_ACCESS_KEY:?Set AWS_SECRET_ACCESS_KEY to the B2 application key}"
    say "Mode: Backblaze B2 replica s3://$LITESTREAM_BUCKET/voxylis.db"
    cat >"$CONFIG" <<EOF
dbs:
  - path: $DB_SOURCE
    replicas:
      - url: s3://$LITESTREAM_BUCKET/voxylis.db
        endpoint: $LITESTREAM_ENDPOINT
EOF
else
    say "SKIPPED: Litestream is not configured on this host."
    say "  Set LITESTREAM_BUCKET + LITESTREAM_ENDPOINT (+ AWS_ACCESS_KEY_ID /"
    say "  AWS_SECRET_ACCESS_KEY) for the B2 drill, or pass --local-replica DIR"
    say "  to drill against a replica on disk. Nothing was restored or verified;"
    say "  this is an honest skip, not a pass."
    exit 3
fi

say "Restoring into scratch database: $SCRATCH"
if ! litestream restore -if-replica-exists -config "$CONFIG" "$SCRATCH"; then
    fail "litestream restore reported an error (see output above)."
fi
if [ ! -s "$SCRATCH" ]; then
    say "FAIL: no replica data was restored." >&2
    say "  If the replica is missing this is a real finding: the only off-host" >&2
    say "  copy of the database does not exist." >&2
    exit 1
fi

PYTHON_BIN="${PYTHON:-}"
if [ -z "$PYTHON_BIN" ]; then
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN=python3
    else
        PYTHON_BIN=python
    fi
fi

say "Running PRAGMA integrity_check and the web.backup integrity helpers..."
if ! "$PYTHON_BIN" - "$SCRATCH" <<'PY'
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from web.backup import _integrity_ok, _sha256

path = Path(sys.argv[1])
ok = True

try:
    con = sqlite3.connect(str(path))
    row = con.execute("PRAGMA integrity_check").fetchone()
    con.close()
    pragma = str(row[0]) if row else ""
except sqlite3.Error as exc:
    pragma = f"error: {exc}"
print(f"PRAGMA integrity_check: {pragma or 'FAILED'}")
ok = ok and pragma == "ok"

backup_ok = _integrity_ok(path)
print(f"web.backup._integrity_ok: {'ok' if backup_ok else 'FAILED'}")
ok = ok and backup_ok

print(f"sha256: {_sha256(path)}")
print(f"size: {path.stat().st_size} bytes")

# A restored production database must contain the core tables, not just a
# structurally valid file.
table_names = {
    row[0]
    for row in sqlite3.connect(str(path)).execute("SELECT name FROM sqlite_master WHERE type='table'")
}
missing = {"users", "sessions", "transcriptions"} - table_names
if missing:
    print(f"core tables missing: {', '.join(sorted(missing))}")
    ok = False
else:
    print("core tables present: users, sessions, transcriptions")

sys.exit(0 if ok else 1)
PY
then
    fail "the restored database failed verification."
fi

say ""
say "DRILL PASSED $(date -u '+%Y-%m-%d %H:%M UTC')"
say "  The replica restored cleanly and passed both integrity checks."
say "  Record the date, replica age and sha256 in docs/RUNBOOK.md (drill log)."
if [ "$KEEP" -eq 1 ]; then
    say "  Scratch file kept at $SCRATCH"
fi
exit 0
