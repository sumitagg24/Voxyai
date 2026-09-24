"""
OS-backed secret storage for Voxylis.

Threat model
------------
``config/settings.json`` is world-readable, gets pasted into bug reports, and
ends up inside support zips.  API keys and session tokens must therefore
**never** be stored there in plaintext.

Backends, in order of preference:

1. ``DpapiBackend``  - Windows DPAPI (``crypt32``) at user scope.  The vault is
                       encrypted with the logged-in user's master key, so a
                       copied file is useless on another machine or account.
2. ``KeyringBackend``- any OS credential store exposed through ``keyring``
                       (Windows Credential Manager, macOS Keychain, Secret
                       Service).  One entry per secret.
3. ``ObfuscatedBackend`` - last resort.  Base64 + machine-bound XOR.  This is
                       **not** secure and logs a loud warning; it exists only so
                       a broken environment degrades instead of crashing.

The vault file is written atomically with restrictive permissions and is never
logged.  Values are redacted in every diagnostic surface.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import sys
import tempfile
import threading
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from utils.logger import log_error, log_info, log_warning
from utils import paths

#: Config keys that are secrets and must be moved out of settings.json.
SECRET_CONFIG_KEYS = (
    "groq_api_key",
    "openai_api_key",
    "openrouter_api_key",
    "model_api_key",
    "anthropic_api_key",
    "web_token",
    "session_id",
    "auth_session_id",
    "refresh_token",
    "access_token",
)

_ENTROPY = b"voxylis.credentials.v1"
_DPAPI_PREFIX = b"DPAPI1:"
_OBF_PREFIX = b"OBF1:"


def redact(value: Optional[str], visible: int = 4) -> str:
    """Return a log-safe representation of a secret."""
    if not value:
        return "<empty>"
    text = str(value)
    if len(text) <= visible:
        return "*" * len(text)
    return f"{text[:visible]}{'*' * max(4, min(20, len(text) - visible))}"


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------


class Backend:
    name = "none"
    secure = False

    def load(self) -> Optional[bytes]:  # pragma: no cover - interface
        raise NotImplementedError

    def store(self, payload: bytes) -> bool:  # pragma: no cover - interface
        raise NotImplementedError

    def clear(self) -> bool:  # pragma: no cover - interface
        return True


class DpapiBackend(Backend):
    """Windows DPAPI, user scope. No third-party dependency."""

    name = "dpapi"
    secure = True

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else paths.vault_path()

    @staticmethod
    def available() -> bool:
        return sys.platform.startswith("win")

    # -- crypto helpers ----------------------------------------------------
    def _crypt(self, data: bytes, unprotect: bool) -> bytes:
        import ctypes
        from ctypes import wintypes  # type: ignore[attr-defined]

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [
                ("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_char)),
            ]

        crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

        blob_in = DATA_BLOB(len(data), ctypes.cast(ctypes.c_char_p(data), ctypes.POINTER(ctypes.c_char)))
        entropy = DATA_BLOB(len(_ENTROPY), ctypes.cast(ctypes.c_char_p(_ENTROPY), ctypes.POINTER(ctypes.c_char)))
        blob_out = DATA_BLOB()

        if unprotect:
            ok = crypt32.CryptUnprotectData(
                ctypes.byref(blob_in), None, ctypes.byref(entropy), None, None, 0, ctypes.byref(blob_out)
            )
        else:
            ok = crypt32.CryptProtectData(
                ctypes.byref(blob_in), None, ctypes.byref(entropy), None, None, 0, ctypes.byref(blob_out)
            )
        if not ok:
            raise OSError("DPAPI operation failed")
        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            kernel32.LocalFree(blob_out.pbData)

    # -- Backend -----------------------------------------------------------
    def load(self) -> Optional[bytes]:
        if not self.path.is_file():
            return None
        raw = self.path.read_bytes()
        if not raw.startswith(_DPAPI_PREFIX):
            return None
        return self._crypt(raw[len(_DPAPI_PREFIX) :], unprotect=True)

    def store(self, payload: bytes) -> bool:
        blob = _DPAPI_PREFIX + self._crypt(payload, unprotect=False)
        _atomic_write(self.path, blob)
        return True

    def clear(self) -> bool:
        try:
            self.path.unlink(missing_ok=True)
        except OSError as exc:  # pragma: no cover
            log_error(f"Could not delete credential vault: {exc}")
            return False
        return True


class KeyringBackend(Backend):
    """One ``keyring`` entry per secret."""

    name = "keyring"
    secure = True
    SERVICE = "Voxylis"

    def __init__(self) -> None:
        self._keyring = None
        try:
            import keyring  # type: ignore

            self._keyring = keyring
        except Exception:
            self._keyring = None

    @classmethod
    def available(cls) -> bool:
        try:
            import keyring  # type: ignore  # noqa: F401

            return True
        except Exception:
            return False

    def load(self) -> Optional[bytes]:
        if not self._keyring:
            return None
        try:
            blob = self._keyring.get_password(self.SERVICE, "__vault__")
        except Exception as exc:
            log_warning(f"Keyring unavailable: {exc}")
            return None
        if not blob:
            return None
        return base64.b64decode(blob.encode("ascii"))

    def store(self, payload: bytes) -> bool:
        if not self._keyring:
            return False
        try:
            self._keyring.set_password(self.SERVICE, "__vault__", base64.b64encode(payload).decode("ascii"))
            return True
        except Exception as exc:
            log_warning(f"Keyring write failed: {exc}")
            return False

    def clear(self) -> bool:
        if not self._keyring:
            return False
        try:
            self._keyring.delete_password(self.SERVICE, "__vault__")
        except Exception:
            pass
        return True


class ObfuscatedBackend(Backend):
    """Machine-bound XOR + base64. Insecure by construction - warning logged."""

    name = "obfuscated"
    secure = False

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else paths.vault_path()

    def _key(self) -> bytes:
        seed = "|".join(
            [
                platform.node(),
                os.environ.get("USERNAME") or os.environ.get("USER") or "voxylis",
                platform.system(),
            ]
        )
        return hashlib.sha256(seed.encode("utf-8")).digest()

    def _xor(self, data: bytes) -> bytes:
        key = self._key()
        return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))

    def load(self) -> Optional[bytes]:
        if not self.path.is_file():
            return None
        raw = self.path.read_bytes()
        if not raw.startswith(_OBF_PREFIX):
            return None
        return self._xor(base64.b64decode(raw[len(_OBF_PREFIX) :]))

    def store(self, payload: bytes) -> bool:
        log_warning(
            "No OS credential store available - secrets are only obfuscated, "
            "not encrypted. Install 'keyring' or run on Windows for DPAPI."
        )
        blob = _OBF_PREFIX + base64.b64encode(self._xor(payload))
        _atomic_write(self.path, blob)
        return True

    def clear(self) -> bool:
        try:
            self.path.unlink(missing_ok=True)
        except OSError:  # pragma: no cover
            return False
        return True


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".vault-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _select_backend(explicit: Optional[Backend] = None) -> Backend:
    if explicit is not None:
        return explicit
    if DpapiBackend.available():
        return DpapiBackend()
    if KeyringBackend.available():
        return KeyringBackend()
    return ObfuscatedBackend()


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class CredentialStore:
    """Key/value secret store backed by whichever OS store is available."""

    def __init__(self, backend: Optional[Backend] = None):
        self.backend = _select_backend(backend)
        self._lock = threading.RLock()
        self._cache: Optional[Dict[str, str]] = None

    # -- low level ---------------------------------------------------------
    @property
    def backend_name(self) -> str:
        return self.backend.name

    @property
    def is_secure(self) -> bool:
        return self.backend.secure

    def _read(self) -> Dict[str, str]:
        with self._lock:
            if self._cache is not None:
                return dict(self._cache)
            data: Dict[str, str] = {}
            try:
                payload = self.backend.load()
                if payload:
                    decoded = json.loads(payload.decode("utf-8"))
                    if isinstance(decoded, dict):
                        data = {str(k): str(v) for k, v in decoded.items() if v is not None}
            except Exception as exc:
                log_error(f"Credential vault unreadable ({self.backend.name}): {exc}")
                data = {}
            self._cache = data
            return dict(data)

    def _write(self, data: Dict[str, str]) -> bool:
        with self._lock:
            payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
            try:
                ok = self.backend.store(payload)
            except Exception as exc:
                log_error(f"Credential vault write failed ({self.backend.name}): {exc}")
                return False
            if ok:
                self._cache = dict(data)
            return bool(ok)

    # -- public API --------------------------------------------------------
    def get(self, name: str, default: Optional[str] = None) -> Optional[str]:
        value = self._read().get(name)
        return value if value else default

    def set(self, name: str, value: Optional[str]) -> bool:
        if value is None or value == "":
            return self.delete(name)
        data = self._read()
        data[name] = str(value)
        ok = self._write(data)
        if ok:
            log_info(f"Credential stored: {name} = {redact(value)}")
        return ok

    def delete(self, name: str) -> bool:
        data = self._read()
        if name not in data:
            return True
        data.pop(name, None)
        log_info(f"Credential removed: {name}")
        return self._write(data)

    def has(self, name: str) -> bool:
        return bool(self.get(name))

    def names(self) -> List[str]:
        return sorted(self._read().keys())

    def describe(self) -> Dict[str, object]:
        """Redacted summary for diagnostics."""
        data = self._read()
        return {
            "backend": self.backend_name,
            "secure": self.is_secure,
            "stored": sorted(data.keys()),
            "hints": {k: redact(v) for k, v in data.items()},
        }

    def clear_all(self) -> bool:
        self._cache = {}
        return self._write({}) and self.backend.clear()


#: Process-wide store. Import this instead of constructing your own.
credential_store = CredentialStore()


# ---------------------------------------------------------------------------
# settings.json migration
# ---------------------------------------------------------------------------


def migrate_config_secrets(config: dict, store: Optional[CredentialStore] = None) -> Tuple[dict, List[str]]:
    """Move plaintext secrets out of a settings dict into the vault.

    Returns ``(cleaned_config, migrated_names)``.  The returned dict is a copy
    with the secret fields removed, so callers can write it back to
    ``settings.json`` without ever touching the plaintext keys again.
    """
    store = store or credential_store
    cleaned = dict(config or {})
    migrated: List[str] = []

    for key in SECRET_CONFIG_KEYS:
        value = cleaned.get(key)
        if isinstance(value, str) and value.strip():
            store.set(key, value.strip())
            migrated.append(key)
        cleaned.pop(key, None)

    # Non-secret metadata so the UI can show "configured" without the secret.
    providers = cleaned.setdefault("providers", {})
    if isinstance(providers, dict):
        for key in ("groq_api_key", "openai_api_key", "openrouter_api_key", "model_api_key"):
            if store.has(key):
                providers[key.replace("_api_key", "")] = {"configured": True}
        for key in ("groq", "openai", "openrouter", "model"):
            providers.setdefault(key, {"configured": store.has(f"{key}_api_key")})

    if migrated:
        log_info(f"Migrated {len(migrated)} plaintext credential(s) into the secure store: {', '.join(migrated)}")
    return cleaned, migrated


def load_api_keys(config: dict, store: Optional[CredentialStore] = None) -> Dict[str, Optional[str]]:
    """Resolve provider credentials from the vault first, env second."""
    store = store or credential_store
    resolved: Dict[str, Optional[str]] = {}
    for key in SECRET_CONFIG_KEYS:
        value = store.get(key)
        if not value:
            value = (config or {}).get(key)
            if isinstance(value, str) and value.strip():
                value = value.strip()
                store.set(key, value)
                log_warning(f"Recovered plaintext credential '{key}' from settings into the secure store")
        if not value:
            env_name = key.upper()
            env_value = os.environ.get(env_name)
            if env_value:
                value = env_value.strip()
        resolved[key] = value or None
    return resolved


def apply_to_environment(keys: Dict[str, Optional[str]]) -> None:
    """Expose provider keys as env vars for the vendor SDKs (process-local)."""
    mapping = {"GROQ_API_KEY": keys.get("groq_api_key"), "OPENAI_API_KEY": keys.get("openai_api_key")}
    for env_name, value in mapping.items():
        if value:
            os.environ[env_name] = value
        else:
            os.environ.pop(env_name, None)


def iter_secret_names() -> Iterable[str]:
    return tuple(SECRET_CONFIG_KEYS)
