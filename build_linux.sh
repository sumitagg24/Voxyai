#!/bin/bash
# Build the Linux bundle from the shared PyInstaller spec.
#
# Linux is a source/binary bundle, not a packaged installer: the supported
# consumer release is Windows. The version comes from config/version.py.
set -e

echo "========================================"
echo "  Building Voxylis for Linux"
echo "========================================"

if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found. Install Python 3.10+"
    exit 1
fi

VERSION=$(python3 -m config.version --print)
echo "Version: ${VERSION}"

python3 -m pip install -r requirements.txt --quiet
python3 -m pip install pyinstaller --quiet
python3 -m config.version --sync

rm -rf build dist

pyinstaller voxylis.spec \
    --clean \
    --noconfirm \
    --name voxylis

echo ""
echo "Binary: dist/voxylis/voxylis"
echo "Note: global hotkeys on Wayland require a portal-aware listener; X11 works."
