# Release Process

Supported release targets:

| Platform | Artifact | Status |
|---|---|---|
| Windows | `Voxylis-Setup-<version>.exe` (Inno Setup) | supported consumer release |
| Windows | `Voxylis.exe` folder build (`dist/Voxylis/`) | for portable use and debugging |
| Linux | `dist/voxylis/` bundle | source/binary bundle, X11 hotkeys (Wayland needs a portal-aware listener) |

## 1. Bump the version once

```bash
python -m config.version --print        # current
# edit __version__ in config/version.py
python -m config.version --sync         # regenerates version_info.txt, version.json mirrors
```

Generated from `config/version.py`: EXE metadata (`packaging/version_info.txt`),
`web/static/version.json`, the installer (`/DAppVersion=`), `/api/health`, the
About dialog and the download page. If two of them disagree, the version-mirror
test fails, and a second `version.json` anywhere in the tree fails it too.

## 2. Verify before building

```bash
python -m flake8 .                                  # lint policy: setup.cfg
python -m pytest tests -q                           # unit + API + site tests
python -m pip-audit -r requirements.txt             # dependency scan
```

Match the formatter version to the pin in `requirements.txt` before trusting a
format check; a newer local black reports unrelated reformatting:

```bash
python -m pip install "black==24.4.2" && python -m black --check .   # line-length: pyproject.toml
```

Secret scan over the working tree (must return nothing):

```bash
grep -rniE "gsk_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}" \
  --exclude-dir=.git --exclude-dir=venv --exclude-dir=dist .
```

## 3. Build

```bash
build_windows.bat        # Windows: version sync → icons → PyInstaller → iscc → verify
build_linux.sh           # Linux bundle
```

`build_windows.bat` fails the build if a credential pattern (`gsk_`, `sk-`,
`SECRET_KEY`) is found inside `dist/Voxylis/`. The installer is optional in the
build script: without Inno Setup it skips and says so.

### Code signing

Set `CERT_PATH` (a `.pfx`) and `CERT_PASSWORD` before running the build, or add
`WINDOWS_CERT_BASE64` + `WINDOWS_CERT_PASSWORD` repository secrets for CI.
`signtool` signs both the EXE and the installer. **Unsigned builds are
development builds**: they trigger SmartScreen, and the download page says so
rather than implying otherwise. An EV/OV certificate from a public CA is
required; a self-signed certificate does not improve SmartScreen for other
users.

## 4. Publish

1. Tag `v<version>` and push the tag — `release.yml` builds, signs (when
   secrets exist), and uploads the artifacts.
2. Compute checksums and publish `update-manifest.json` for that release:

```json
{
  "version": "3.0.0",
  "notes_url": "https://github.com/sumitagg24/Voxyai/releases/tag/v3.0.0",
  "platforms": {
    "windows": {
      "url": "https://github.com/sumitagg24/Voxyai/releases/download/v3.0.0/Voxylis-Setup-3.0.0.exe",
      "sha256": "<64 hex chars>",
      "size": 12345678,
      "kind": "installer"
    }
  }
}
```

`core/updater.py` fetches
`https://github.com/sumitagg24/Voxyai/releases/latest/download/update-manifest.json`
(override with `VOXYLIS_UPDATE_FEED`). A download **without** a `sha256` in the
manifest is refused by the updater — never publish an unverifiable entry.

3. Update the website download metadata if the file name changed, then confirm
   `GET /api/health` reports the same version.

## 5. Release gate

- [ ] Lint and full test suite pass on the tagged commit
- [ ] `SENTRY_DSN` (and `SENTRY_DSN_BROWSER`) set if error monitoring is wanted;
      `EMAIL_PROVIDER` + `EMAIL_API_KEY` set so verification and reset mail is
      actually delivered; `python -m web.app` logs no email warning on startup
- [ ] `DOWNLOAD_URL_WINDOWS` set **only** once the matching release artifact
      exists, so the site does not link to a 404
- [ ] Version mirrors synced; no stale version string anywhere
- [ ] Fresh-clone build (no local `settings.json`, `.env`, database or cache in the tree)
- [ ] Artifact inspected: no keys, tokens, `.env`, personal paths, dev URLs or local DB
- [ ] Installer installs, launches, shows the right publisher/version, and
      uninstalls cleanly (leaving `%LOCALAPPDATA%\Voxylis` unless the user says otherwise)
- [ ] Upgrade over an older install replaces files and keeps user data
- [ ] Auto-start preference round-trips
- [ ] Update check finds the new release and verifies its checksum
- [ ] Website routes, pricing, download and legal pages match the shipped build
- [ ] `docs/` claims match the shipped build
- [ ] No `agent`/`agents` directories, duplicate trees or generated junk committed

## Known blockers for a fully signed release

* **Code-signing certificate** is not present in this repository. Until it is
  provided as a secret, releases are unsigned development builds.
* **Payment provider** is not integrated. Checkout reports "unavailable" and
  tiers can only change through a verified webhook, an audited admin action, or
  a development override that production refuses. Do not advertise a purchase
  flow that cannot complete.

Both are configuration gaps, not missing code; do not fake either one.

* **Transactional email** needs a provider key (`EMAIL_API_KEY` for Resend, or
  `SMTP_HOST`). Until one is set the app runs with the `console` provider: no
  verification or reset mail is delivered and startup logs an error. See
  [DEPLOYMENT.md](DEPLOYMENT.md) § E.
* **Error monitoring** needs `SENTRY_DSN` (server) and `SENTRY_DSN_BROWSER`
  (website). Both are optional; with neither set the app runs normally and
  reports nothing. The desktop app additionally requires the user to opt in.
* **No release has been published**, so the download page points at the
  releases page and marks the Windows card as not published yet. Publish the
  installer, then set `DOWNLOAD_URL_WINDOWS` to its URL.
