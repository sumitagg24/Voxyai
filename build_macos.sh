#!/bin/bash
set -e

echo "========================================"
echo "  Building Voxylis for macOS"
echo "========================================"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 not found. Install Python 3.10+"
    exit 1
fi

# Install build dependencies
echo "Installing build dependencies..."
pip3 install pyinstaller --quiet

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build dist

# Build with PyInstaller
echo "Building app bundle..."
pyinstaller main.py \
    --name Voxylis \
    --windowed \
    --onedir \
    --add-data "config:config" \
    --add-data "assets:assets" \
    --hidden-import pynput.keyboard._darwin \
    --hidden-import pynput.mouse._darwin \
    --hidden-import sounddevice._portaudio \
    --noconfirm

# Create DMG if hdiutil is available
if command -v hdiutil &> /dev/null; then
    echo "Creating DMG..."
    VERSION=$(python3 -c "from config.constants import APP_VERSION; print(APP_VERSION)" 2>/dev/null || echo "2.2.0")
    hdiutil create -volname "Voxylis" \
        -srcfolder dist/Voxylis.app \
        -ov -format UDZO \
        "dist/Voxylis-${VERSION}.dmg"
    echo "DMG created: dist/Voxylis-${VERSION}.dmg"
else
    echo "hdiutil not found. App bundle at: dist/Voxylis.app"
fi

echo ""
echo "========================================"
echo "  Build complete!"
echo "========================================"
