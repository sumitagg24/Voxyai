@echo off
echo ========================================
echo   Building Voxylis for Windows
echo ========================================

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.10+
    pause
    exit /b 1
)

REM Install build dependencies
echo Installing build dependencies...
pip install pyinstaller --quiet

REM Clean previous builds
echo Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Build with PyInstaller
echo Building EXE...
pyinstaller voxylis.spec --clean --noconfirm

if errorlevel 1 (
    echo ERROR: Build failed
    pause
    exit /b 1
)

REM ── Optional code signing (removes the SmartScreen warning) ─────────────
REM Set CERT_PATH to a .pfx code-signing certificate and CERT_PASSWORD to its
REM password. Requires signtool.exe from the Windows SDK. Unsigned builds
REM still work but show "Windows protected your PC" on first run.
if defined CERT_PATH (
    echo Signing executable...
    where signtool >nul 2>&1
    if errorlevel 1 (
        echo WARNING: signtool not found, skipping signing
    ) else (
        signtool sign /f "%CERT_PATH%" /p "%CERT_PASSWORD%" /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 "dist\Voxylis\Voxylis.exe"
        if errorlevel 1 (
            echo WARNING: signing failed
        ) else (
            echo Executable signed.
        )
    )
) else (
    echo NOTE: CERT_PATH not set, skipping code signing (SmartScreen will warn).
)

echo.
echo ========================================
echo   Build complete!
echo   Output: dist\Voxylis\Voxylis.exe
echo ========================================
pause
