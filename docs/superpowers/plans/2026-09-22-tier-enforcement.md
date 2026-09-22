# Tier Enforcement & Usage Limits Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add real subscription tier enforcement to Voxylis — web backend, desktop app, and platform builds — so free users cannot access paid features, and usage quotas are enforced.

**Architecture:** Add `tier` column to the SQLite `users` table, create a tier-checking decorator for Flask endpoints, add usage quota enforcement for free tier, gate desktop AI features behind tier checks, and create platform-specific build scripts for Windows EXE, macOS DMG, and Linux AppImage.

**Tech Stack:** Python 3.12, Flask, SQLite, PyQt5, PyInstaller, Python setuptools

**Spec:** This plan enforces the pricing tiers defined in `web/static/pricing.html`:
- **Free**: 100 transcriptions/month, 5 languages, basic enhancement only (formal mode), no Q&A, no advanced STT modes
- **Pro** ($9.99/mo): Unlimited transcriptions, 99+ languages, all 5 enhancement modes, Q&A, all STT modes, wake word
- **Business** ($29.99/mo): Everything in Pro + API access, team features, custom integrations

---

## Global Constraints

- Python 3.10+ compatibility (CI tests on 3.10, 3.11, 3.12)
- SQLite database at `web/data/voxylis.db`
- Desktop config at `config/settings.json` (JSON-file-based, no server required)
- Desktop app must work offline (tier info cached locally, synced when online)
- No new pip dependencies (use existing `openai`, `groq`, `requests`, `flask-limiter`)
- PyInstaller builds for Windows EXE, macOS DMG, Linux AppImage
- All changes must be backward-compatible with existing user databases (migration)

---

## Task 1: Add `tier` column to users table + tier constants

**Files:**
- Modify: `web/app.py:143-245` (database init)
- Create: `web/tier.py` (tier constants and helpers)

**Interfaces:**
- Consumes: existing `_init_db()` function, `sqlite3` connection
- Produces: `web/tier.py` with `TIER_FREE`, `TIER_PRO`, `TIER_BUSINESS`, `TIER_FEATURES`, `get_user_tier()`, `check_tier_access()`

- [ ] **Step 1: Create `web/tier.py`**

```python
"""
Tier constants and enforcement helpers for Voxylis.
"""
import sqlite3
from functools import wraps
from flask import jsonify, g
from web.app import _get_db, _extract_session, _verify_session

TIER_FREE = "free"
TIER_PRO = "pro"
TIER_BUSINESS = "business"

# Feature access map: tier -> set of allowed features
TIER_FEATURES = {
    TIER_FREE: {
        "transcription",       # basic (PUSH_TO_TALK only)
        "enhancement_basic",   # formal mode only
        "history",
        "settings",
        "hotkeys",
    },
    TIER_PRO: {
        "transcription",       # all modes (PUSH_TO_TALK, ENDPOINTING, DIARIZATION)
        "enhancement_basic",
        "enhancement_all",     # all 5 modes
        "qa",                  # Q&A feature
        "advanced_stt",        # ENDPOINTING, DIARIZATION modes
        "wake_word",
        "history",
        "settings",
        "hotkeys",
    },
    TIER_BUSINESS: {
        "transcription",
        "enhancement_basic",
        "enhancement_all",
        "qa",
        "advanced_stt",
        "wake_word",
        "api_access",
        "team_features",
        "custom_integrations",
        "history",
        "settings",
        "hotkeys",
    },
}

# Free tier limits
FREE_MONTHLY_TRANSCRIPTIONS = 100

# Allowed enhancement modes per tier
TIER_ENHANCEMENT_MODES = {
    TIER_FREE: {"formal"},
    TIER_PRO: {"formal", "casual", "technical", "concise", "creative"},
    TIER_BUSINESS: {"formal", "casual", "technical", "concise", "creative"},
}

# Allowed STT modes per tier
TIER_STT_MODES = {
    TIER_FREE: {"PUSH_TO_TALK"},
    TIER_PRO: {"PUSH_TO_TALK", "ENDPOINTING", "DIARIZATION"},
    TIER_BUSINESS: {"PUSH_TO_TALK", "ENDPOINTING", "DIARIZATION"},
}


def get_user_tier(user_id: int) -> str:
    """Get the subscription tier for a user. Defaults to free."""
    conn = _get_db()
    try:
        row = conn.execute("SELECT tier FROM users WHERE id = ?", (user_id,)).fetchone()
        if row and row["tier"]:
            return row["tier"]
    except Exception:
        pass
    finally:
        conn.close()
    return TIER_FREE


def has_feature(user_id: int, feature: str) -> bool:
    """Check if a user's tier includes a specific feature."""
    tier = get_user_tier(user_id)
    return feature in TIER_FEATURES.get(tier, TIER_FEATURES[TIER_FREE])


def get_monthly_transcription_count(user_id: int) -> int:
    """Count transcriptions for the current month."""
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM transcriptions "
            "WHERE user_id = ? AND created_at >= date('now', 'start of month')",
            (user_id,),
        ).fetchone()
        return row["cnt"] if row else 0
    except Exception:
        return 0
    finally:
        conn.close()


def check_transcription_quota(user_id: int) -> tuple[bool, int, int]:
    """Check if user has transcription quota remaining.
    Returns (allowed, used, limit). limit=0 means unlimited.
    """
    tier = get_user_tier(user_id)
    if tier in (TIER_PRO, TIER_BUSINESS):
        return True, 0, 0  # unlimited
    used = get_monthly_transcription_count(user_id)
    return used < FREE_MONTHLY_TRANSCRIPTIONS, used, FREE_MONTHLY_TRANSCRIPTIONS


def require_tier(*allowed_tiers):
    """Decorator: requires the user to have one of the specified tiers."""
    def decorator(f):
        @wraps(f)
        def wrapper(user_id=None, *args, **kwargs):
            if user_id is None:
                return jsonify({"error": "Authentication required"}), 401
            tier = get_user_tier(user_id)
            if tier not in allowed_tiers:
                return jsonify({
                    "error": "This feature requires a paid plan",
                    "current_tier": tier,
                    "required_tiers": list(allowed_tiers),
                    "upgrade_url": "/pricing",
                }), 403
            return f(user_id=user_id, *args, **kwargs)
        return wrapper
    return decorator


def require_feature(feature: str):
    """Decorator: requires the user's tier to include a specific feature."""
    def decorator(f):
        @wraps(f)
        def wrapper(user_id=None, *args, **kwargs):
            if user_id is None:
                return jsonify({"error": "Authentication required"}), 401
            if not has_feature(user_id, feature):
                tier = get_user_tier(user_id)
                return jsonify({
                    "error": f"This feature requires a paid plan",
                    "current_tier": tier,
                    "missing_feature": feature,
                    "upgrade_url": "/pricing",
                }), 403
            return f(user_id=user_id, *args, **kwargs)
        return wrapper
    return decorator
```

- [ ] **Step 2: Add migration to `_init_db()` in `web/app.py`**

Add after the existing column migration block (after line ~223):

```python
    if "tier" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN tier TEXT NOT NULL DEFAULT 'free'")
        conn.commit()
```

- [ ] **Step 3: Update `/api/me` to return tier**

In the `me()` endpoint, add `"tier"` to the user response dict.

- [ ] **Step 4: Verify syntax**

Run: `python -m py_compile web/app.py && python -m py_compile web/tier.py`

---

## Task 2: Enforce tiers on web backend endpoints

**Files:**
- Modify: `web/app.py` (qa_endpoint, enhance_endpoint, transcribe_endpoint, subscription)

**Interfaces:**
- Consumes: `web/tier.py` functions (`get_user_tier`, `has_feature`, `check_transcription_quota`, `require_feature`, `TIER_ENHANCEMENT_MODES`, `TIER_STT_MODES`)
- Produces: tier-enforced API endpoints that return 403 for unauthorized access

- [ ] **Step 1: Import tier module in `web/app.py`**

Add near top of file:
```python
from web.tier import (
    get_user_tier, has_feature, check_transcription_quota,
    require_feature, TIER_ENHANCEMENT_MODES, TIER_STT_MODES,
    TIER_FREE, FREE_MONTHLY_TRANSCRIPTIONS,
)
```

- [ ] **Step 2: Enforce Q&A endpoint**

Modify `qa_endpoint()` to require authentication and the `qa` feature:
```python
@app.route("/api/qa", methods=["POST"])
@limiter.limit("30 per minute", key_func=get_remote_address)
def qa_endpoint():
    # Require auth
    session_id = _extract_session()
    user_id = _verify_session(session_id)
    if user_id is None:
        return jsonify({"error": "Login required for Q&A"}), 401
    
    # Require paid tier
    if not has_feature(user_id, "qa"):
        tier = get_user_tier(user_id)
        return jsonify({
            "error": "Q&A requires a Pro or Business plan",
            "current_tier": tier,
            "upgrade_url": "/pricing",
        }), 403
    
    data = request.get_json(silent=True)
    # ... rest of existing logic
```

- [ ] **Step 3: Enforce enhancement endpoint**

Modify `enhance_endpoint()` to check mode permissions and require auth:
```python
@app.route("/api/enhance", methods=["POST"])
@limiter.limit("30 per minute", key_func=get_remote_address)
def enhance_endpoint():
    # Require auth
    session_id = _extract_session()
    user_id = _verify_session(session_id)
    if user_id is None:
        return jsonify({"error": "Login required for enhancement"}), 401
    
    data = request.get_json(silent=True)
    mode = data.get("mode", "formal").strip().lower()
    
    # Check mode permission
    tier = get_user_tier(user_id)
    allowed_modes = TIER_ENHANCEMENT_MODES.get(tier, TIER_ENHANCEMENT_MODES[TIER_FREE])
    if mode not in allowed_modes:
        return jsonify({
            "error": f"Mode '{mode}' requires a paid plan. Free tier: formal only.",
            "current_tier": tier,
            "allowed_modes": list(allowed_modes),
            "upgrade_url": "/pricing",
        }), 403
    
    # ... rest of existing logic
```

- [ ] **Step 4: Enforce transcription endpoint + quota**

Modify `transcribe_endpoint()` to check auth, quota, and STT mode permissions:
```python
@app.route("/api/transcribe", methods=["POST"])
@limiter.limit("20 per minute", key_func=get_remote_address)
def transcribe_endpoint():
    # Require auth
    session_id = _extract_session()
    user_id = _verify_session(session_id)
    if user_id is None:
        return jsonify({"error": "Login required for transcription"}), 401
    
    # Check transcription quota
    allowed, used, limit = check_transcription_quota(user_id)
    if not allowed:
        return jsonify({
            "error": f"Monthly transcription limit reached ({limit})",
            "used": used,
            "limit": limit,
            "upgrade_url": "/pricing",
        }), 403
    
    # Check STT mode permission
    mode = request.form.get("mode", "PUSH_TO_TALK").upper()
    tier = get_user_tier(user_id)
    allowed_modes = TIER_STT_MODES.get(tier, TIER_STT_MODES[TIER_FREE])
    if mode not in allowed_modes:
        return jsonify({
            "error": f"STT mode '{mode}' requires a paid plan",
            "current_tier": tier,
            "allowed_modes": list(allowed_modes),
            "upgrade_url": "/pricing",
        }), 403
    
    # ... rest of existing logic (audio file handling, Muse/Groq calls)
    # After successful transcription, the count is already tracked in the transcriptions table
```

- [ ] **Step 5: Update `/api/subscription` to return real tier**

Replace the hardcoded "Free" response:
```python
@app.route("/api/subscription", methods=["GET"])
@require_auth
def subscription(user_id):
    tier = get_user_tier(user_id)
    trans_count = get_monthly_transcription_count(user_id)
    
    tier_info = {
        TIER_FREE: {"price": 0, "limit": "100/month", "name": "Free"},
        TIER_PRO: {"price": 9.99, "limit": "Unlimited", "name": "Pro"},
        TIER_BUSINESS: {"price": 29.99, "limit": "Unlimited", "name": "Business"},
    }
    info = tier_info.get(tier, tier_info[TIER_FREE])
    
    return jsonify({
        "status": "success",
        "subscription": {
            "plan": info["name"],
            "tier": tier,
            "price": info["price"],
            "status": "active",
            "usage": {
                "transcriptions": trans_count,
                "limit": info["limit"],
                "percentage": min(trans_count, 100) if tier == TIER_FREE else 0,
            },
        },
    })
```

- [ ] **Step 6: Add tier upgrade endpoint (for testing/admin)**

```python
@app.route("/api/subscription/upgrade", methods=["POST"])
@require_auth
def upgrade_tier(user_id):
    """Set user tier. In production, this would be triggered by Stripe webhook."""
    data = request.json or {}
    new_tier = data.get("tier", "").strip().lower()
    if new_tier not in (TIER_FREE, TIER_PRO, TIER_BUSINESS):
        return jsonify({"error": "Invalid tier"}), 400
    
    conn = _get_db()
    conn.execute("UPDATE users SET tier = ? WHERE id = ?", (new_tier, user_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "tier": new_tier})
```

- [ ] **Step 7: Verify all endpoints with syntax check**

Run: `python -m py_compile web/app.py`

---

## Task 3: Desktop app tier enforcement

**Files:**
- Modify: `ai/transcriber.py` (add tier checks)
- Modify: `ai/enhancer.py` (add tier checks)
- Modify: `core/user_manager.py` (add tier field)
- Modify: `config/constants.py` (add tier constants)
- Modify: `ui/settings_window.py` (show tier info)
- Modify: `core/app_orchestrator.py` (pass tier to AI modules)

**Interfaces:**
- Consumes: user tier from `config/settings.json` or `core/user_manager.py`
- Produces: tier-gated AI features in desktop app

- [ ] **Step 1: Add tier constants to `config/constants.py`**

Add at the end of the file:
```python
# Subscription tiers
TIER_FREE = "free"
TIER_PRO = "pro"
TIER_BUSINESS = "business"

TIER_FEATURES = {
    TIER_FREE: {"transcription", "enhancement_basic", "history", "settings"},
    TIER_PRO: {"transcription", "enhancement_basic", "enhancement_all", "qa", "advanced_stt", "wake_word", "history", "settings"},
    TIER_BUSINESS: {"transcription", "enhancement_basic", "enhancement_all", "qa", "advanced_stt", "wake_word", "api_access", "team_features", "history", "settings"},
}

FREE_MONTHLY_TRANSCRIPTIONS = 100
TIER_ENHANCEMENT_MODES = {
    TIER_FREE: {"formal"},
    TIER_PRO: {"formal", "casual", "technical", "concise", "creative"},
    TIER_BUSINESS: {"formal", "casual", "technical", "concise", "creative"},
}
TIER_STT_MODES = {
    TIER_FREE: {"PUSH_TO_TALK"},
    TIER_PRO: {"PUSH_TO_TALK", "ENDPOINTING", "DIARIZATION"},
    TIER_BUSINESS: {"PUSH_TO_TALK", "ENDPOINTING", "DIARIZATION"},
}
```

- [ ] **Step 2: Add tier to user manager**

In `core/user_manager.py`, add `tier` field to user data dict in `create_user()` and `login()`. Default to `"free"`.

- [ ] **Step 3: Add tier helper function**

Create a helper in `config/constants.py` or `utils/helpers.py`:
```python
def get_user_tier(settings: dict) -> str:
    """Get tier from user settings. Defaults to free."""
    return settings.get("tier", "free")

def has_tier_feature(settings: dict, feature: str) -> bool:
    """Check if user's tier has a feature."""
    tier = get_user_tier(settings)
    return feature in TIER_FEATURES.get(tier, TIER_FEATURES[TIER_FREE])
```

- [ ] **Step 4: Gate enhancer modes in `ai/enhancer.py`**

In the `enhance()` method, add tier check:
```python
from config.constants import get_user_tier, has_tier_feature, TIER_ENHANCEMENT_MODES

def enhance(self, text: str, mode: str = "formal", settings: dict = None) -> str:
    # Check tier permission
    if settings:
        tier = get_user_tier(settings)
        allowed = TIER_ENHANCEMENT_MODES.get(tier, TIER_ENHANCEMENT_MODES["free"])
        if mode not in allowed:
            # Fall back to formal for free tier
            mode = "formal"
    
    # ... existing enhancement logic
```

- [ ] **Step 5: Gate transcription modes in `ai/transcriber.py`**

In the `transcribe()` method, add tier check for STT modes:
```python
from config.constants import get_user_tier, TIER_STT_MODES

def transcribe(self, audio_path: str, mode: str = "push_to_talk", settings: dict = None) -> str:
    # Check tier permission for advanced modes
    if settings:
        tier = get_user_tier(settings)
        allowed_modes = TIER_STT_MODES.get(tier, TIER_STT_MODES["free"])
        if mode.upper() not in allowed_modes:
            mode = "push_to_talk"  # fallback to free tier mode
    
    # ... existing transcription logic
```

- [ ] **Step 6: Pass settings through orchestrator**

In `core/app_orchestrator.py`, ensure `self.settings` is passed to `enhancer.enhance()` and `transcriber.transcribe()` calls.

- [ ] **Step 7: Show tier in settings window**

In `ui/settings_window.py`, add a "Plan" section showing current tier and upgrade button.

- [ ] **Step 8: Verify syntax for all desktop files**

Run:
```bash
python -m py_compile config/constants.py
python -m py_compile core/user_manager.py
python -m py_compile ai/enhancer.py
python -m py_compile ai/transcriber.py
python -m py_compile core/app_orchestrator.py
```

---

## Task 4: Platform-specific build scripts

**Files:**
- Modify: `voxylis.spec` (PyInstaller spec - Windows EXE)
- Create: `build_macos.sh` (macOS DMG build script)
- Create: `build_linux.sh` (Linux AppImage build script)
- Create: `build_windows.bat` (Windows EXE build script)
- Create: `pyproject.toml` (package metadata)

**Interfaces:**
- Consumes: `main.py` as entry point, all source directories
- Produces: platform-specific distributable binaries

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "voxylis"
version = "2.2.0"
description = "AI-powered voice-to-text desktop assistant"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.10"
dependencies = [
    "PyQt5>=5.15",
    "flask>=3.0",
    "flask-cors>=4.0",
    "flask-caching>=2.0",
    "flask-limiter>=3.0",
    "gunicorn>=21.0",
    "openai>=1.0",
    "groq>=0.4",
    "requests>=2.31",
    "sounddevice>=0.4",
    "pyperclip>=1.8",
    "pynput>=1.7",
    "pyttsx3>=2.9",
    "numpy>=1.24",
    "scipy>=1.10",
    "python-dotenv>=1.0",
    "werkzeug>=3.0",
    "markupsafe>=2.1",
]

[project.optional-dependencies]
dev = ["black", "flake8", "pytest", "pyinstaller"]

[project.scripts]
voxylis = "main:main"

[tool.black]
line-length = 100
target-version = ["py310"]

[tool.flake8]
max-line-length = 100
exclude = ["venv", "build", "dist", "__pycache__"]
```

- [ ] **Step 2: Update `voxylis.spec` for Windows EXE**

Ensure the spec file includes all necessary data files (config, icons, etc.) and has proper platform detection.

- [ ] **Step 3: Create `build_windows.bat`**

```batch
@echo off
echo Building Voxylis for Windows...
pip install pyinstaller
pyinstaller voxylis.spec --clean
echo Build complete: dist\Voxylis.exe
pause
```

- [ ] **Step 4: Create `build_macos.sh`**

```bash
#!/bin/bash
set -e
echo "Building Voxylis for macOS..."

# Build app bundle
pyinstaller main.py \
    --name Voxylis \
    --windowed \
    --onedir \
    --icon assets/icon.icns \
    --add-data "config:config" \
    --add-data "assets:assets" \
    --hidden-import pynput.keyboard._darwin \
    --hidden-import pynput.mouse._darwin \
    --noconfirm

# Create DMG
if command -v hdiutil &> /dev/null; then
    echo "Creating DMG..."
    hdiutil create -volname "Voxylis" \
        -srcfolder dist/Voxylis.app \
        -ov -format UDZO \
        dist/Voxylis-$(cat config/constants.py | grep VERSION | cut -d'"' -f2).dmg
    echo "DMG created: dist/Voxylis-*.dmg"
else
    echo "hdiutil not found. App bundle at: dist/Voxylis.app"
fi
```

- [ ] **Step 5: Create `build_linux.sh`**

```bash
#!/bin/bash
set -e
echo "Building Voxylis for Linux..."

# Build with PyInstaller
pyinstaller main.py \
    --name voxylis \
    --onedir \
    --icon assets/icon.png \
    --add-data "config:config" \
    --add-data "assets:assets" \
    --hidden-import pynput.keyboard._xorg \
    --hidden-import pynput.mouse._xorg \
    --noconfirm

# Create AppImage (if appimagetool is available)
if command -v appimagetool &> /dev/null; then
    echo "Creating AppImage..."
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
    cp assets/icon.png AppDir/usr/share/icons/voxylis.png
    
    appimagetool AppDir dist/voxylis-$(grep VERSION config/constants.py | cut -d'"' -f2).AppImage
    echo "AppImage created"
else
    echo "appimagetool not found. Binary at: dist/voxylis"
fi
```

- [ ] **Step 6: Make shell scripts executable**

Run: `chmod +x build_macos.sh build_linux.sh`

---

## Task 5: Dashboard frontend tier enforcement

**Files:**
- Modify: `web/static/js/dashboard.js`
- Modify: `web/static/dashboard.html`

**Interfaces:**
- Consumes: `/api/subscription` response with real tier data
- Produces: UI that gates features based on tier

- [ ] **Step 1: Add tier check helper to dashboard.js**

```javascript
function getUserTier() {
    const sub = window._subscriptionData;
    return sub ? sub.tier : 'free';
}

function hasFeature(feature) {
    const tier = getUserTier();
    const features = {
        free: ['transcription', 'enhancement_basic', 'history', 'settings'],
        pro: ['transcription', 'enhancement_basic', 'enhancement_all', 'qa', 'advanced_stt', 'wake_word', 'history', 'settings'],
        business: ['transcription', 'enhancement_basic', 'enhancement_all', 'qa', 'advanced_stt', 'wake_word', 'api_access', 'team_features', 'history', 'settings'],
    };
    return features[tier]?.includes(feature) || false;
}

function showUpgradeModal(feature) {
    // Show a modal suggesting upgrade
    const modal = document.getElementById('upgradeModal');
    if (modal) {
        modal.querySelector('.upgrade-feature').textContent = feature;
        modal.classList.add('show');
    }
}
```

- [ ] **Step 2: Gate Q&A section**

In dashboard.html, wrap the Q&A section with a tier check. If free tier, show upgrade prompt instead of the Q&A form.

- [ ] **Step 3: Gate enhancement modes**

In the mode chip click handler, check tier before allowing non-basic modes. If free user clicks "casual", show upgrade modal.

- [ ] **Step 4: Update subscription section display**

Use real tier data from `/api/subscription` to show correct plan name, usage, and limits.

- [ ] **Step 5: Add upgrade modal HTML**

Add a modal element to dashboard.html that prompts users to upgrade when they try to access a paid feature.

---

## Task 6: Smoke test all endpoints

**Files:**
- Test: manual curl commands against running Flask server

**Interfaces:**
- Consumes: running Flask dev server on port 5000
- Produces: verified endpoint responses

- [ ] **Step 1: Start Flask dev server**

```bash
cd web && python app.py
```

- [ ] **Step 2: Test health**

```bash
curl http://localhost:5000/api/health
```

- [ ] **Step 3: Test signup + login**

```bash
curl -X POST http://localhost:5000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"name":"Test","email_or_phone":"test@test.com","password":"password123"}'
```

- [ ] **Step 4: Test tier enforcement (Q&A without auth)**

```bash
curl -X POST http://localhost:5000/api/qa \
  -H "Content-Type: application/json" \
  -d '{"question":"hello"}'
# Expected: 401 Unauthorized
```

- [ ] **Step 5: Test tier enforcement (Q&A as free user)**

```bash
# Use session_id from signup
curl -X POST http://localhost:5000/api/qa \
  -H "Content-Type: application/json" \
  -H "X-Session-Id: <session_id>" \
  -d '{"question":"hello"}'
# Expected: 403 - Q&A requires Pro plan
```

- [ ] **Step 6: Test upgrade to Pro**

```bash
curl -X POST http://localhost:5000/api/subscription/upgrade \
  -H "Content-Type: application/json" \
  -H "X-Session-Id: <session_id>" \
  -d '{"tier":"pro"}'
# Expected: 200 success
```

- [ ] **Step 7: Test Q&A as Pro user**

```bash
curl -X POST http://localhost:5000/api/qa \
  -H "Content-Type: application/json" \
  -H "X-Session-Id: <session_id>" \
  -d '{"question":"What is Voxylis?"}'
# Expected: 200 with AI answer
```

- [ ] **Step 8: Test enhancement mode restriction**

```bash
# As free user, try casual mode
curl -X POST http://localhost:5000/api/enhance \
  -H "Content-Type: application/json" \
  -H "X-Session-Id: <free_session>" \
  -d '{"text":"hello world","mode":"casual"}'
# Expected: 403 - casual mode requires paid plan
```

- [ ] **Step 9: Test transcription quota**

```bash
curl http://localhost:5000/api/subscription \
  -H "X-Session-Id: <session_id>"
# Expected: shows correct tier and usage
```

---

## Task 7: Final verification and cleanup

- [ ] **Step 1: Run syntax checks on all modified files**

```bash
python -m py_compile web/app.py
python -m py_compile web/tier.py
python -m py_compile config/constants.py
python -m py_compile core/user_manager.py
python -m py_compile ai/enhancer.py
python -m py_compile ai/transcriber.py
python -m py_compile core/app_orchestrator.py
```

- [ ] **Step 2: Verify no regressions in existing endpoints**

Start server, test all endpoints from previous smoke test.

- [ ] **Step 3: Verify desktop app still launches**

```bash
python main.py
```

- [ ] **Step 4: Update README.md with tier enforcement documentation**

Add a section explaining the tier system and how to test it.

---

## Migration Safety

The `tier` column migration uses `ALTER TABLE ... ADD COLUMN` with a `DEFAULT 'free'` value, which:
- Is backward-compatible with existing databases
- All existing users start as Free tier
- No data loss
- Works on SQLite 3.25+ (Python 3.10+ ships with 3.31+)
