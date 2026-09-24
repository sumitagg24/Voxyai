"""
Email preferences and marketing consent.

Two separate ideas, deliberately not merged:

* **Transactional mail** (verification, reset, security notices, plan changes,
  usage notices) is part of the account.  It is sent to every user and there is
  no opt-out, which is why the templates are written to be worth reading.
* **Product news** is opt-in.  :func:`marketing_opt_in` returns ``False`` for
  anyone who has not explicitly asked for it, and "no row" is not consent.

The unsubscribe link is a signed, stateless token so a user can opt out from an
email without signing in.  It is signed with ``SECRET_KEY`` and carries only a
user id and the address it was issued for; the signature is compared in
constant time and the address must still match the account, so a leaked or
edited link cannot unsubscribe somebody else.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import sqlite3
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_PURPOSE = "unsubscribe"


def _signing_key() -> str:
    """Secret used to sign opt-out links.

    Refuses to sign with an unset or placeholder key: an unsigned unsubscribe
    link would let anyone opt any address out of product news.
    """
    try:  # Prefer the running app's resolved key.
        from flask import current_app

        key = (current_app.config.get("SECRET_KEY") or "").strip()
        if key:
            return key
    except Exception:  # pragma: no cover - no app context (CLI/tests)
        pass
    return (os.environ.get("SECRET_KEY") or "").strip()


def _sign(payload: str) -> str:
    key = _signing_key()
    if not key:
        raise RuntimeError("Cannot sign an unsubscribe link without SECRET_KEY")
    return hmac.new(key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def unsubscribe_token(user_id: int, email: str) -> str:
    """Mint ``{purpose}.{user_id}.{base64(email)}.{signature}``."""
    address = (email or "").strip().lower()
    payload = f"{_PURPOSE}.{int(user_id)}.{base64.urlsafe_b64encode(address.encode()).decode().rstrip('=')}"
    return f"{payload}.{_sign(payload)}"


def read_unsubscribe_token(token: str) -> Optional[Tuple[int, str]]:
    """Return ``(user_id, email)`` when the signature is valid, else ``None``."""
    parts = (token or "").split(".")
    if len(parts) != 4:
        return None
    purpose, raw_id, encoded, signature = parts
    if purpose != _PURPOSE:
        return None
    payload = f"{purpose}.{raw_id}.{encoded}"
    try:
        expected = _sign(payload)
    except RuntimeError:
        return None
    if not hmac.compare_digest(expected, signature):
        return None
    try:
        user_id = int(raw_id)
        padding = "=" * (-len(encoded) % 4)
        email = base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    return user_id, email


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS email_preferences (
            user_id           INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            marketing_opt_in  INTEGER NOT NULL DEFAULT 0,
            source            TEXT    NOT NULL DEFAULT '',
            updated_at        TEXT    NOT NULL DEFAULT (datetime('now'))
        )
        """
    )


def set_marketing_opt_in(
    conn: sqlite3.Connection,
    user_id: int,
    opt_in: bool,
    source: str = "signup",
) -> None:
    """Record an explicit choice. Called for both opt-in and opt-out."""
    ensure_schema(conn)
    conn.execute(
        "INSERT INTO email_preferences (user_id, marketing_opt_in, source, updated_at) "
        "VALUES (?, ?, ?, datetime('now')) "
        "ON CONFLICT(user_id) DO UPDATE SET "
        "marketing_opt_in = excluded.marketing_opt_in, "
        "source = excluded.source, "
        "updated_at = datetime('now')",
        (user_id, 1 if opt_in else 0, source or ""),
    )


def marketing_opt_in(conn: sqlite3.Connection, user_id: int) -> bool:
    """True only when the user explicitly opted in. Absence of a row is "no"."""
    try:
        ensure_schema(conn)
        row = conn.execute(
            "SELECT marketing_opt_in FROM email_preferences WHERE user_id = ?", (user_id,)
        ).fetchone()
    except sqlite3.Error:  # pragma: no cover - defensive
        return False
    if row is None:
        return False
    try:
        return bool(row["marketing_opt_in"])
    except (TypeError, IndexError):
        return bool(row[0])


def opt_out_by_token(conn: sqlite3.Connection, token: str) -> Optional[str]:
    """Apply an unsubscribe link. Returns the masked address on success.

    The address in the token must still match the account, so a stale link from
    an old address cannot change current preferences.
    """
    parsed = read_unsubscribe_token(token)
    if parsed is None:
        return None
    user_id, email = parsed
    row = conn.execute(
        "SELECT email_or_phone FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if row is None:
        return None
    current = (row["email_or_phone"] if not hasattr(row, "keys") else row["email_or_phone"]) or ""
    if current.strip().lower() != email.strip().lower():
        return None
    set_marketing_opt_in(conn, user_id, False, source="unsubscribe-link")
    masked = email[:1] + "***" + email[email.find("@"):] if "@" in email else "***"
    logger.info("email: marketing opt-out applied for %s", masked)
    return masked
