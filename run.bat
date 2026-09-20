@echo off
REM ============================================
REM VOXYLIS - WINDOWS STARTUP SCRIPT
REM ============================================

echo.
echo ╔════════════════════════════════════════╗
echo ║     VOXYLIS - AI Voice Assistant       ║
echo ║         Starting Application...        ║
echo ╚════════════════════════════════════════╝
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ ERROR: Python is not installed or not in PATH
    echo.
    echo Please install Python from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation
    echo.
    pause
    exit /b 1
)

echo ✓ Python found
echo.

REM Check if required packages are installed
echo Checking dependencies...
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo ⚠ Installing required packages...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ❌ ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
)

echo ✓ Dependencies ready
echo.

REM Create necessary directories
if not exist "config" mkdir config
if not exist "logs" mkdir logs

echo ✓ Directories ready
echo.

REM Start the application
echo Starting Voxylis...
echo.
echo 🚀 Voxylis is starting up...
echo.
echo 📱 Web Interface: http://localhost:5000
echo 🖥️  Desktop Application: Starting...
echo.
echo Press Ctrl+C to stop the application
echo.

python main.py

if errorlevel 1 (
    echo.
    echo ❌ ERROR: Application failed to start
    echo.
    pause
    exit /b 1
)

pause
