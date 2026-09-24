"""
Canonical version metadata for Voxylis.

Every surface (desktop app, About dialog, installer, EXE metadata, backend
/health, website download metadata, packaging scripts) must read the version
from here.  Do not hard-code a version string anywhere else.

Release procedure
-----------------
1. Bump __version__ below.
2. `python -m config.version --sync` rewrites the generated mirrors that cannot
   import Python at runtime (packaging/version_info.txt, web/static/version.json).
3. Tag the commit `v<__version__>`.
"""

from __future__ import annotations

import json
from pathlib import Path

__version__ = "3.0.0"

#: Marketing / product name shown in the UI and installers.
APP_NAME = "Voxylis"
APP_DISPLAY_NAME = "Voxylis - AI Voice Assistant"
PUBLISHER = "Voxylis"
COPYRIGHT = "Copyright (c) 2026 Voxylis"
#: Product name for the first-party engine (used in copy, not in binaries).
ENGINE_NAME = "Voxy"

VERSION_TUPLE = tuple(int(p) for p in __version__.split("."))
VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH = VERSION_TUPLE

#: Update channel metadata.  The updater compares `latest` against __version__.
UPDATE_CHANNEL = "stable"

REPO_URL = "https://github.com/sumitagg24/Voxyai"
RELEASES_URL = f"{REPO_URL}/releases"


def version_string() -> str:
    return __version__


def version_tag() -> str:
    return f"v{__version__}"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def version_info_text() -> str:
    """Render the PyInstaller version resource with the canonical version."""
    quad = f"({VERSION_MAJOR}, {VERSION_MINOR}, {VERSION_PATCH}, 0)"
    return f"""# UTF-8
#
# GENERATED FILE - do not edit by hand.
# Regenerate with: python -m config.version --sync
#
# PyInstaller version resource for Voxylis.exe, referenced from voxylis.spec.
# An EXE without version metadata looks anonymous to Windows SmartScreen and
# always triggers the "unrecognized app" warning.
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={quad},
    prodvers={quad},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'040904B0',
          [StringStruct(u'CompanyName', u'{PUBLISHER}'),
          StringStruct(u'FileDescription', u'{APP_DISPLAY_NAME}'),
          StringStruct(u'FileVersion', u'{__version__}'),
          StringStruct(u'InternalName', u'{APP_NAME}'),
          StringStruct(u'LegalCopyright', u'{COPYRIGHT}'),
          StringStruct(u'OriginalFilename', u'{APP_NAME}.exe'),
          StringStruct(u'ProductName', u'{APP_NAME}'),
          StringStruct(u'ProductVersion', u'{__version__}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""


def sync() -> list:
    """Rewrite the generated version mirrors. Returns the paths written."""
    root = _repo_root()
    written = []

    version_info = root / "packaging" / "version_info.txt"
    version_info.parent.mkdir(parents=True, exist_ok=True)
    if not version_info.exists() or version_info.read_text(encoding="utf-8") != version_info_text():
        version_info.write_text(version_info_text(), encoding="utf-8")
    written.append(str(version_info))

    payload = {
        "version": __version__,
        "name": APP_NAME,
        "engine": ENGINE_NAME,
        "released": UPDATE_CHANNEL,
        "releases_url": RELEASES_URL,
    }
    # One served mirror is enough: web/static/version.json is what the deployed
    # site (Vercel outputDirectory web/static) and the Flask /version.json route
    # both use. A second copy under web/downloads only drifted.
    target = root / "web" / "static" / "version.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    written.append(str(target))

    return written


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Voxylis version tooling")
    parser.add_argument("--sync", action="store_true", help="regenerate version mirrors")
    parser.add_argument("--print", dest="print_version", action="store_true")
    args = parser.parse_args(argv)

    if args.print_version or not args.sync:
        print(__version__)
    if args.sync:
        for path in sync():
            print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
