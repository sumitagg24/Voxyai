#!/bin/bash
set -e

echo "========================================"
echo "  Building Voxylis for Linux"
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
echo "Building binary..."
pyinstaller main.py \
    --name voxylis \
    --onedir \
    --add-data "config:config" \
    --add-data "assets:assets" \
    --hidden-import pynput.keyboard._xorg \
    --hidden-import pynput.mouse._xorg \
    --hidden-import sounddevice._portaudio \
    --noconfirm

# Create AppImage if appimagetool is available
if command -v appimagetool &> /dev/null; then
    echo "Creating AppImage..."
    VERSION=$(python3 -c "from config.constants import APP_VERSION; print(APP_VERSION)" 2>/dev/null || echo "2.2.0")
    
    mkdir -p AppDir/usr/bin AppDir/usr/share/applications AppDir/usr/share/icons
    cp -r dist/voxylis/* AppDir/usr/bin/
    
    cat > AppDir/voxylis.desktop << EOF
[Desktop Entry]
Name=Voxylis
Exec=voxylis
Icon=voxylis
Type=Application
Categories=Utility;Audio;
EOF
    
    if [ -f assets/icon.png ]; then
        cp assets/icon.png AppDir/usr/share/icons/voxylis.png
    fi
    
    appimagetool AppDir "dist/voxylis-${VERSION}.AppImage" 2>/dev/null || echo "AppImage creation failed, binary available at dist/voxylis"
else
    echo "appimagetool not found. Binary at: dist/voxylis"
fi

echo ""
echo "========================================"
echo "  Build complete!"
echo "========================================"
