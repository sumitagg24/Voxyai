# Voxylis runbook (production, free tier)

Owner: _<your name>_ · Last verified: _<date>_ · Version: 3.0.0

## Where everything lives (all free, nothing on a laptop)

| Piece | Host | URL | Cost |
|---|---|---|---|
| Website (static) | Vercel | https://voxylis-web.vercel.app | free |
| API (Flask) | PythonAnywhere | https://<PA_USER>.pythonanywhere.com | free |
| Database | SQLite file on the API host | `/home/<PA_USER>/voxylis-data/voxylis.db` | free |
| Backups | PA scheduled task + weekly download | `~/voxylis-backups`, keep 14 | free |
| Auth | Auth0 free (google-oauth2 + github) | tenant `dev-g4w68c5tpeyhxh3d.us.auth0.com` | free |
| Email | Gmail SMTP (app password) | — | free ≤500/day |
| Errors | Sentry free | — | free ≤5k/mo |
| Uptime | UptimeRobot free, 5-min checks on `/api/health` | — | free |
| Releases | GitHub Actions + Releases | v3.0.0 live | free |

## Daily operations

- UptimeRobot alerts → open `https://<PA_USER>.pythonanywhere.com/api/health`.
  `email.configured` and `monitoring.enabled` are reported there.
- PA Web tab → Log files → `error log` for tracebacks; Sentry for grouped errors.
- Contact-form spam → `contact_messages` table; decide retention below.

## Backup & restore (tested _<date>_)

- Daily 03:00 UTC scheduled task:
  `cd ~/voxyai && ~/.virtualenvs/voxylis/bin/python -m web.backup --backup-dir ~/voxylis-backups --keep 14`
- Weekly: download newest backup via Files tab (off-machine copy).
- Restore drill: stop web app → `--restore <file> --force` on a scratch copy →
  confirm `PRAGMA integrity_check` ok → Reload.
- Retention: 14 daily. Restore owner: _<name>_.

## Retention decisions

| Data | Keep | Notes |
|---|---|---|
| DB backups | 14 daily | see above |
| `contact_messages` | _decide, e.g. 90 days_ | personal data |
| `newsletter_subscribers` | _until unsubscribe_ | personal data |

## Incident basics

1. Site down? Check UptimeRobot → PA Web tab → Reload → error log.
2. Login broken? `GET /api/auth/auth0/config` must show `enabled:true`;
   check Auth0 Logs (Dashboard → Monitoring → Logs).
3. Mail not arriving? `/api/health` `email.configured`; Gmail app password
   expires if the Google password changes — regenerate it.
4. Bad deploy? PA Web → Reload previous code via `git pull` + Reload;
   Vercel → Deployments → promote previous Ready build.
