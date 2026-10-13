"""P6.9 site audit: boot the real Flask app with a seeded database and run
three checks against every public page in headless Chromium:

  1. an axe-core accessibility audit — fails on serious/critical violations;
  2. an internal link checker — every same-origin href must resolve;
  3. a console check — no JS errors and no uncaught exceptions on load.

Pages talk to the API through the local server: requests to any other host
(the pages hardcode the production API origin) are proxied to the local app,
so the audit is deterministic and never depends on external services.

Usage (from the repository root):

    python scripts/site_audit.py            # print a one-line summary per page
    python scripts/site_audit.py --verbose # also list every finding

Exit codes: 0 clean, 1 findings, 2 setup error. Runs in well under two
minutes; wired into CI as the `site-audit` job, which must be a required
status check (Settings → Branches → Required status checks).
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

AXE_PATH = REPO_ROOT / "scripts" / "vendor" / "axe.min.js"

#: Every site page (blog post slugs are appended at runtime from the DB).
ROUTES = [
    "/",
    "/pricing",
    "/about",
    "/contact",
    "/auth",
    "/download",
    "/privacy",
    "/terms",
    "/blog",
    "/docs/installation",
    "/docs/configuration",
    "/docs/voice-commands",
    "/docs/qa-feature",
    "/docs/troubleshooting",
    "/docs/tips-tricks",
]

BLOCKING_IMPACTS = {"serious", "critical"}


def _boot_app(port_holder: dict):
    """Import the app against a throwaway seeded database and serve it."""
    scratch = Path(tempfile.mkdtemp(prefix="voxylis-site-audit-"))
    os.environ["VOXYLIS_DB_PATH"] = str(scratch / "audit.db")
    os.environ.setdefault("SECRET_KEY", "site-audit-secret-key-0000000000000000")
    os.environ.pop("VOXYLIS_ENV", None)

    import logging

    logging.getLogger("werkzeug").setLevel(logging.ERROR)  # keep the report readable

    from web.app import app
    from web.db import _get_db

    # Seed: one account with history rows and a live session, so the
    # dashboard's authenticated API paths return real data when requested.
    from werkzeug.security import generate_password_hash

    conn = _get_db()
    cur = conn.execute(
        "INSERT INTO users (name, email_or_phone, password_hash, email_verified) "
        "VALUES ('Audit Seed', 'audit-seed@voxylis.com', ?, 1)",
        (generate_password_hash("site-audit-password-123"),),
    )
    audit_user_id = cur.lastrowid
    conn.executemany(
        "INSERT INTO transcriptions (user_id, text, enhanced, mode, language) VALUES (?, ?, 1, 'formal', 'en')",
        [(audit_user_id, f"seed transcription {i}") for i in range(3)],
    )
    conn.commit()
    conn.close()

    # Audit-only static route for axe: CSP is script-src 'self', so the
    # engine must be served same-origin rather than injected inline. This
    # route exists only inside this script's process, never in the app.
    axe_bytes = AXE_PATH.read_bytes()

    @app.route("/__audit/axe.min.js")
    def _audit_axe():  # noqa: ANN001
        return axe_bytes, 200, {"Content-Type": "application/javascript"}

    from werkzeug.serving import make_server

    server = make_server("127.0.0.1", 0, app)
    port_holder["port"] = server.server_address[1]

    # Discover blog slugs from the database (seeded by _init_db).
    with app.test_client() as probe:
        slugs = [p["slug"] for p in probe.get("/api/blog").get_json()["posts"]]
    if slugs:
        ROUTES.append(f"/blog/{slugs[0]}")

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return app


def _proxy_external(route, request, local_base: str):
    """Answer cross-origin requests from the local app (deterministic audit)."""
    import requests

    parts = urlsplit(request.url)
    local = f"{local_base}{parts.path}"
    if parts.query:
        local += f"?{parts.query}"
    try:
        upstream = requests.get(local, timeout=10)
        route.fulfill(
            status=upstream.status_code,
            body=upstream.content,
            content_type=upstream.headers.get("Content-Type", "application/json"),
        )
    except Exception:
        route.abort()


def _rewrite_config_js(route, local_base: str):
    """Serve config.js with the API base pointed at the local app.

    In production the site and the API share an origin, so the hardcoded
    Render base in config.js resolves same-origin; in this audit the site is
    local and the base would be cross-origin (and CSP-blocked). Rewriting it
    mirrors the production topology instead of loosening the policy.
    """
    route.fulfill(
        status=200,
        body=f"window.VOXYLIS_API_BASE = {local_base!r};\n",
        content_type="application/javascript",
    )


def _audit_page(page, url: str, local_base: str, verbose: bool) -> list:
    """Return the list of findings (strings) for one page."""
    findings: list = []
    console_errors: list = []
    page.on(
        "console",
        lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
    )
    page.on("pageerror", lambda exc: console_errors.append(f"uncaught exception: {exc}"))

    page.goto(url, wait_until="load", timeout=20_000)
    try:
        page.wait_for_load_state("networkidle", timeout=3_000)
    except Exception:
        pass  # long-polling or slow fetches must not fail the audit
    time.sleep(0.2)

    # 1) accessibility ------------------------------------------------------
    page.add_script_tag(url="/__audit/axe.min.js")
    axe_result = page.evaluate(
        "async () => {"
        "  const r = await axe.run(document, {resultTypes: ['violations']});"
        "  return r.violations.map(v => ({id: v.id, impact: v.impact, help: v.help, count: v.nodes.length,"
        "    nodes: v.nodes.slice(0, 3).map(n => (n.target || []).join(' '))}));"
        "}"
    )
    blocking = [v for v in axe_result if v.get("impact") in BLOCKING_IMPACTS]
    for violation in blocking:
        where = " | ".join(violation.get("nodes") or [])
        findings.append(
            f"a11y[{violation['impact']}] {violation['id']} ({violation['count']} nodes): {violation['help']} -> {where}"
        )

    # 2) console errors ------------------------------------------------------
    for message in console_errors:
        findings.append(f"console-error: {message[:300]}")

    # 3) internal links ------------------------------------------------------
    hrefs = page.evaluate("Array.from(document.querySelectorAll('a[href]')).map(a => a.href)")
    internal = set()
    for href in hrefs:
        parts = urlsplit(href)
        if parts.netloc and parts.netloc != urlsplit(local_base).netloc:
            continue  # external link: out of scope for this check
        if parts.netloc == "" and not href.startswith("/"):
            continue  # pure #fragment
        target = f"{local_base}{parts.path}" + (f"?{parts.query}" if parts.query else "")
        if parts.path:
            internal.add(target)
    import requests

    with requests.Session() as session:
        for target in sorted(internal):
            status = session.get(target, timeout=10, allow_redirects=True).status_code
            if status >= 400:
                findings.append(f"broken-link[{status}]: {target}")

    label = url.replace(local_base, "") or "/"
    if findings:
        print(f"FAIL {label} ({len(findings)} findings)")
        if verbose:
            for finding in findings:
                print(f"     - {finding}")
    else:
        print(f"ok   {label}")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--verbose", action="store_true", help="print every finding")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("setup error: playwright is not installed (pip install playwright; playwright install chromium)")
        return 2
    if not AXE_PATH.is_file():
        print(f"setup error: {AXE_PATH} is missing (axe-core vendored for the audit)")
        return 2

    port_holder: dict = {}
    try:
        _boot_app(port_holder)
    except Exception as exc:
        print(f"setup error: could not boot the Flask app: {exc}")
        return 2

    local_base = f"http://127.0.0.1:{port_holder['port']}"
    total: list = []
    started = time.time()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        context.route(
            "**/*",
            lambda route, request: (
                _rewrite_config_js(route, local_base)
                if request.url.endswith("/static/js/config.js")
                else (
                    route.continue_()
                    if request.url.startswith(local_base)
                    else _proxy_external(route, request, local_base)
                )
            ),
        )
        for route_path in ROUTES:
            page = context.new_page()
            try:
                total.extend(_audit_page(page, local_base + route_path, local_base, args.verbose))
            except Exception as exc:
                print(f"FAIL {route_path} (audit crashed: {exc})")
                total.append(f"audit-crash on {route_path}: {exc}")
            finally:
                page.close()
        browser.close()

    elapsed = time.time() - started
    print(f"\n{len(ROUTES)} pages audited in {elapsed:.1f}s — {len(total)} finding(s)")
    if total:
        print("SITE AUDIT FAILED")
        return 1
    print("SITE AUDIT PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
