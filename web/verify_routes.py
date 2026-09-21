"""One-shot route verification. Run from repo root: py web/verify_routes.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from web.app import app

c = app.test_client()
checks = [
    ("GET", "/", None, 200),
    ("GET", "/pricing", None, 200),
    ("GET", "/blog", None, 200),
    ("GET", "/blog/introducing-voxy-2-0", None, 200),
    ("GET", "/about", None, 200),
    ("GET", "/contact", None, 200),
    ("GET", "/auth", None, 200),
    ("GET", "/download", None, 200),
    ("GET", "/dashboard", None, 200),
    ("GET", "/static/css/dashboard.css", None, 200),
    ("GET", "/static/js/dashboard.js", None, 200),
    ("GET", "/static/js/api.js", None, 200),
    ("GET", "/docs/installation", None, 200),
    ("GET", "/docs/troubleshooting", None, 200),
    ("GET", "/docs/nope", None, 404),
    ("GET", "/api/health", None, 200),
    ("GET", "/api/stats", None, 200),
    ("GET", "/api/stats/public", None, 200),
    ("GET", "/api/history", None, 200),
    ("GET", "/api/settings", None, 200),
    ("GET", "/api/hotkeys", None, 200),
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
    r = c.get(path)
    ok = r.status_code == want
    fails += not ok
    print(("PASS" if ok else "FAIL"), method, path, "->", r.status_code)

posts = [
    ("/api/settings", {}, 200),
    ("/api/qa", {"question": "hi"}, 200),
    ("/api/qa", {}, 400),
]
for path, body, want in posts:
    r = c.post(path, json=body)
    ok = r.status_code == want
    fails += not ok
    print(("PASS" if ok else "FAIL"), "POST", path, "->", r.status_code)

for path in ("/api/settings", "/api/qa"):
    r = c.post(path, data="not-json", content_type="application/json")
    ok = r.status_code == 400
    fails += not ok
    print(("PASS" if ok else "FAIL"), "POST", path, "garbage ->", r.status_code)

print("FAILURES:", fails)
sys.exit(1 if fails else 0)
