"""One-shot route verification. Run from repo root: py web/verify_routes.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from web.app import app, _create_session, _get_db  # noqa: E402  (path bootstrap must run first)

c = app.test_client()
checks = [
    ("GET", "/", None, 200),
    ("GET", "/pricing", None, 200),
    ("GET", "/blog", None, 200),
    ("GET", "/blog/introducing-voxy-2-0", None, 200),  # follow_redirects=True
    ("GET", "/about", None, 200),
    ("GET", "/contact", None, 200),
    ("GET", "/auth", None, 200),
    ("GET", "/download", None, 200),
    ("GET", "/privacy", None, 200),
    ("GET", "/terms", None, 200),
    ("GET", "/dashboard", None, 200),
    ("GET", "/static/css/dashboard.css", None, 200),
    ("GET", "/static/js/dashboard.js", None, 200),
    ("GET", "/static/js/api.js", None, 200),
    ("GET", "/static/js/cookie-consent.js", None, 200),
    ("GET", "/docs/installation", None, 200),
    ("GET", "/docs/troubleshooting", None, 200),
    ("GET", "/docs/nope", None, 404),
    ("GET", "/api/health", None, 200),
    ("GET", "/api/stats", None, 200),
    ("GET", "/api/stats/public", None, 200),
    # Auth-required endpoints must refuse anonymous callers
    ("GET", "/api/history", None, 401),
    ("GET", "/api/settings", None, 401),
    ("GET", "/api/hotkeys", None, 401),
    ("GET", "/api/subscription", None, 200),
    ("GET", "/api/blog", None, 200),
    ("GET", "/api/blog/introducing-voxy-2-0", None, 200),
    ("GET", "/api/download/urls", None, 200),
    ("GET", "/api/download/detect", None, 200),
    ("GET", "/api/features", None, 200),
    ("GET", "/api/pricing", None, 200),
]
fails = 0
for method, path, _body, want in checks:
    r = c.get(path, follow_redirects=True)
    ok = r.status_code == want
    fails += not ok
    print(("PASS" if ok else "FAIL"), method, path, "->", r.status_code)

# Create a test Pro user for authenticated endpoint testing
conn = _get_db()
cur = conn.cursor()
cur.execute("SELECT id FROM users WHERE email_or_phone = 'verify_routes@voxylis.com'")
row = cur.fetchone()
if not row:
    cur.execute(
        "INSERT INTO users (name, email_or_phone, password_hash, tier) VALUES ('Route Tester', 'verify_routes@voxylis.com', 'test', 'pro')"
    )
    user_id = cur.lastrowid
else:
    user_id = row[0]
    cur.execute("UPDATE users SET tier = 'pro' WHERE id = ?", (user_id,))
conn.commit()
conn.close()

session_id = _create_session(user_id)
authed_headers = {"X-Session-Id": session_id}

posts = [
    ("/api/settings", {}, 200),
    ("/api/qa", {"question": "hi"}, 200),
    ("/api/qa", {}, 400),
]
for path, body, want in posts:
    r = c.post(path, json=body, headers=authed_headers)
    ok = r.status_code == want
    fails += not ok
    print(("PASS" if ok else "FAIL"), "POST", path, "->", r.status_code)

for path in ("/api/settings", "/api/qa"):
    r = c.post(path, data="not-json", content_type="application/json", headers=authed_headers)
    ok = r.status_code == 400
    fails += not ok
    print(("PASS" if ok else "FAIL"), "POST", path, "garbage ->", r.status_code)

print("FAILURES:", fails)
sys.exit(1 if fails else 0)
