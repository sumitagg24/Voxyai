@echo off
setlocal enabledelayedexpansion
echo ========================================
echo   Building Voxylis for Windows
echo ========================================

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.10+
    exit /b 1
)

REM ── Canonical version ────────────────────────────────────────────────────
REM Read once from config/version.py and pass it to every downstream tool so
REM the EXE metadata, the installer and /api/health can never disagree.
for /f "delims=" %%v in ('python -c "from config.version import __version__; print(__version__)"') do set APP_VERSION=%%v
if "%APP_VERSION%"=="" (
    echo ERROR: could not read the version from config/version.py
    exit /b 1
)
echo Version: %APP_VERSION%

echo Installing build dependencies...
pip install -r requirements.txt --quiet
pip install pyinstaller --quiet

echo Regenerating brand assets and version metadata...
python packaging\make_icons.py
python -m config.version --sync

echo Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo Building EXE...
pyinstaller voxylis.spec --clean --noconfirm
if errorlevel 1 (
    echo ERROR: PyInstaller build failed
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

REM ── Installer ───────────────────────────────────────────────────────────
where iscc >nul 2>&1
if errorlevel 1 (
    echo NOTE: Inno Setup ^(iscc^) not found - skipping installer.
    echo       Install it from https://jrsoftware.org/isdl.php to produce a Setup.exe.
) else (
    echo Building installer...
    iscc /DAppVersion=%APP_VERSION% installer\voxylis.iss
    if errorlevel 1 (
        echo ERROR: installer build failed
        exit /b 1
    )
    if defined CERT_PATH (
        signtool sign /f "%CERT_PATH%" /p "%CERT_PASSWORD%" /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 "installer\output\Voxylis-Setup-%APP_VERSION%.exe"
    )
)

REM ── Release artifact verification ───────────────────────────────────────
echo Verifying the build contains no secrets...
findstr /S /I /M /C:"gsk_" /C:"sk-" /C:"SECRET_KEY" dist\Voxylis\* >nul 2>&1
if not errorlevel 1 (
    echo ERROR: the build appears to contain a credential. Review dist\Voxylis before releasing.
    exit /b 1
)
echo   no credential patterns found

echo.
echo ========================================
echo   Build complete for %APP_VERSION%
echo   EXE:       dist\Voxylis\Voxylis.exe
echo   Installer: installer\output\Voxylis-Setup-%APP_VERSION%.exe
echo ========================================
