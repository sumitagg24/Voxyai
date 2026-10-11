# Voxylis runbook (production, free tier)

Owner: _<your name>_ · Last verified: _<date>_ · Version: 3.0.0

## Where everything lives (all free, nothing on a laptop)

| Piece | Host | URL | Cost |
|---|---|---|---|
| Website + API | Flask same-origin | http://localhost:5000 | local |
| API (Flask) | Render free (Docker) | https://voxylis-api.onrender.com | free |
| Database | SQLite, replicated to B2 by Litestream | `/app/web/data/voxylis.db` + B2 replica | free |
| Backups | Litestream continuous replica + weekly download | B2 bucket, keep replica | free 10 GB |
| Keep-alive | UptimeRobot free, 5-min `GET /api/health` ("Voxylis API") | doubles as uptime alert | free |
| Backup ping | cron-job.org every 10 min (backup only; pause if Render hours run hot) | — | free |
| Auth | Auth0 free (google-oauth2 + github) | tenant `dev-g4w68c5tpeyhxh3d.us.auth0.com` | free |
| Email | Gmail SMTP (app password) | — | free ≤500/day |
| Errors | Sentry free | — | free ≤5k/mo |
| Uptime | UptimeRobot free, 5-min checks on `/api/health` | — | free |
| Releases | GitHub Actions + Releases | v3.0.0 live | free |

## Daily operations

- UptimeRobot alerts → open `https://voxylis-api.onrender.com/api/health`.
  `email.configured` and `monitoring.enabled` are reported there.
- Render Dashboard → Logs for tracebacks; Sentry for grouped errors.
- Contact-form spam → `contact_messages` table; decide retention below.

## Backup & restore (tested _<date>_)

- Continuous: Litestream replicates every SQLite write to the B2 bucket
  (see `docker-entrypoint.sh` + `LITESTREAM_*` env). A Render restart restores
  from the replica automatically on boot.
- Weekly: download `voxylis.db` from the B2 bucket (off-provider copy).
- Restore drill: `scripts/drill_restore.sh` (see below). The older manual form
  is `litestream restore -if-replica-exists -o /tmp/restore.db
  s3://<bucket>/voxylis.db` followed by `PRAGMA integrity_check`.
  (Local/tooling path `python -m web.backup` still works for manual snapshots.)
- Retention: B2 keeps the live replica; keep 4 weekly downloads.
  Restore owner: _<name>_.

## Quarterly restore drill

Cadence: once per quarter (first week of January, April, July, October).
Owner: _<name>_.

1. Run the drill from the repo root, with the deployment's Litestream
   environment available (the Render shell has it) or a local replica:

   ```sh
   scripts/drill_restore.sh                       # B2 replica (LITESTREAM_* env)
   scripts/drill_restore.sh --local-replica DIR   # replica directory on disk
   ```

2. The script restores into a scratch file and verifies it with
   `PRAGMA integrity_check`, the `web.backup` integrity helpers, and a check
   that `users`, `sessions` and `transcriptions` exist. It prints the sha256
   and size of what was restored.
3. Exit codes: `0` passed, `1` verification failed (treat as an incident),
   `2` usage error, `3` skipped because Litestream is not installed or not
   configured on that host — an honest skip, never a pass. If the host has no
   Litestream config, run the drill on the Render shell instead.
4. Record the outcome in the drill log below. A drill that has not been run on
   the current schema is not evidence that restores work.

| Date (UTC) | Operator | Mode | Result | sha256 (first 12) |
|---|---|---|---|---|
| _<date>_ | _<name>_ | B2 | _pass/skip/fail_ | _<hash>_ |

## Retention decisions

| Data | Keep | Notes |
|---|---|---|
| DB backups | 14 daily | see above |
| `contact_messages` | _decide, e.g. 90 days_ | personal data |
| `newsletter_subscribers` | _until unsubscribe_ | personal data |

## Incident basics

1. Site down? Check UptimeRobot → Render Dashboard → Logs.
2. Login broken? `GET /api/auth/auth0/config` must show `enabled:true`;
   check Auth0 Logs (Dashboard → Monitoring → Logs).
3. Mail not arriving? `/api/health` `email.configured`; Gmail app password
   expires if the Google password changes — regenerate it.
4. Bad deploy? Render → Manual Deploy → Rollback to a previous deploy.
