#!/bin/bash

# ============================================
# VOXYLIS - MACOS/LINUX STARTUP SCRIPT
# ============================================

echo ""
echo "╔════════════════════════════════════════╗"
echo "║     VOXYLIS - AI Voice Assistant       ║"
echo "║         Starting Application...        ║"
echo "╚════════════════════════════════════════╝"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ ERROR: Python 3 is not installed"
    echo ""
    echo "Please install Python 3 from: https://www.python.org/downloads/"
    echo ""
    echo "Or use Homebrew (macOS):"
    echo "  brew install python3"
    echo ""
    echo "Or use apt (Linux):"
    echo "  sudo apt-get install python3 python3-pip"
    echo ""
    exit 1
fi

echo "✓ Python found: $(python3 --version)"
echo ""

# Linux only: pynput (global hotkeys) pulls in `evdev`, which compiles a C
# extension and therefore needs the Python dev headers + a C compiler. Without
# them `pip install -r requirements.txt` dies mid-install.
if [ "$(uname -s)" = "Linux" ] && [ ! -d "/usr/include/python$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')" ]; then
    echo "⚠ Python development headers not found (needed by pynput/evdev)."
    echo ""
    echo "  Debian/Ubuntu:  sudo apt-get install python3-dev build-essential"
    echo "  Fedora:         sudo dnf install python3-devel gcc"
    echo "  Arch:           sudo pacman -S python gcc"
    echo ""
    echo "Install the headers for your distribution and run run.sh again."
    exit 1
fi

# Check if required packages are installed
echo "Checking dependencies..."
python3 -c "import flask" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠ Installing required packages..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "❌ ERROR: Failed to install dependencies"
        exit 1
    fi
fi

echo "✓ Dependencies ready"
echo ""

# Create necessary directories
mkdir -p config
mkdir -p logs

echo "✓ Directories ready"
echo ""

# Start the application
echo "Starting Voxylis..."
echo ""
echo "🚀 Voxylis is starting up..."
echo ""
echo "📱 Web Interface: http://localhost:5000"
echo "🖥️  Desktop Application: Starting..."
echo ""
echo "Press Ctrl+C to stop the application"
echo ""

python3 main.py

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ ERROR: Application failed to start"
    echo ""
    exit 1
fi
