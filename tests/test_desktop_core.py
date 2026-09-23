"""Desktop-side unit tests for storage, credentials, injection and hotkeys."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.history_store import HistoryStore
from core.errors import catalog, classify_exception, friendly_error
from utils import credentials, paths


# ── paths ────────────────────────────────────────────────────────────────────


def test_user_data_root_follows_the_override(isolated_home):
    assert paths.user_data_root() == isolated_home
    assert str(isolated_home) in str(paths.settings_path())
    assert paths.history_db_path().parent == paths.data_dir()


def test_ensure_directories_creates_the_whole_tree(isolated_home):
    created = paths.ensure_directories()
    for name in ("config", "data", "secrets", "logs", "cache", "models", "temp", "updates"):
        assert Path(created[name]).is_dir(), name


def test_program_files_are_never_used_for_user_data(isolated_home):
    """The install directory must never be a data location."""
    program = paths.program_dir().resolve()
    for directory in (paths.config_dir(), paths.data_dir(), paths.logs_dir(), paths.secrets_dir()):
        assert program not in directory.resolve().parents
        assert directory.resolve() != program


def test_legacy_migration_copies_and_keeps_the_source(tmp_path, monkeypatch):
    legacy = tmp_path / "legacy-install"
    (legacy / "config").mkdir(parents=True)
    (legacy / "config" / "settings.json").write_text('{"hotkey": "win+shift"}', encoding="utf-8")

    monkeypatch.setattr(paths, "program_dir", lambda: legacy)
    monkeypatch.setattr(paths, "legacy_roots", lambda: [legacy])

    copied = paths.migrate_legacy_data()
    assert copied, "expected the legacy settings file to be migrated"
    assert paths.settings_path().is_file()
    # Non-destructive: the original file is left in place.
    assert (legacy / "config" / "settings.json").is_file()


# ── credentials ──────────────────────────────────────────────────────────────


def test_vault_round_trip(isolated_home):
    store = credentials.CredentialStore(credentials.ObfuscatedBackend())
    assert store.set("groq_api_key", "gsk_test_value_1234567890")
    assert store.get("groq_api_key") == "gsk_test_value_1234567890"
    assert store.has("groq_api_key")
    assert store.delete("groq_api_key")
    assert store.get("groq_api_key") is None


def test_redaction_never_reveals_the_secret():
    secret = "gsk_abcdefghijklmnopqrstuvwxyz"
    shown = credentials.redact(secret)
    assert secret not in shown
    assert shown.endswith("*")
    assert credentials.redact("") == "<empty>"
    assert set(credentials.redact("abcd")) == {"*"}


def test_plaintext_secrets_are_migrated_out_of_settings(isolated_home):
    store = credentials.CredentialStore(credentials.ObfuscatedBackend())
    config = {
        "hotkey": "shift+win",
        "groq_api_key": "gsk_plaintext_to_be_removed",
        "openai_api_key": "sk-plaintext-to-be-removed",
    }
    cleaned, migrated = credentials.migrate_config_secrets(config, store=store)

    assert set(migrated) == {"groq_api_key", "openai_api_key"}
    assert "groq_api_key" not in cleaned
    assert "openai_api_key" not in cleaned
    assert cleaned["hotkey"] == "shift+win"
    assert store.get("groq_api_key") == "gsk_plaintext_to_be_removed"
    # Non-secret metadata is retained so the UI can say "configured".
    assert cleaned["providers"]["groq"]["configured"] is True
    # Nothing resembling a key survives a round trip through the settings file.
    assert "gsk_" not in json.dumps(cleaned)


def test_env_is_used_when_the_vault_is_empty(isolated_home, monkeypatch):
    store = credentials.CredentialStore(credentials.ObfuscatedBackend())
    monkeypatch.setenv("GROQ_API_KEY", "gsk_from_environment")
    keys = credentials.load_api_keys({}, store=store)
    assert keys["groq_api_key"] == "gsk_from_environment"


def test_diagnostics_describe_never_returns_values(isolated_home):
    store = credentials.CredentialStore(credentials.ObfuscatedBackend())
    store.set("openai_api_key", "sk-super-secret-value")
    described = json.dumps(store.describe())
    assert "sk-super-secret-value" not in described
    assert "openai_api_key" in described


# ── history ──────────────────────────────────────────────────────────────────


def test_history_add_read_delete_clear(tmp_path):
    store = HistoryStore(db_path=tmp_path / "h.db")
    entry = store.add("hello world", "Hello, world.", "formal", "English", app_context="code.exe")
    assert entry and entry["word_count"] == 2
    assert entry["app_context"] == "code.exe"
    assert store.count() == 1

    assert store.get_all()[0]["raw"] == "hello world"
    assert store.get_recent(1)[0]["id"] == entry["id"]

    assert store.mark_injected(entry["id"]) is True
    assert store.get_all()[0]["injected"] is True

    assert store.delete(entry["id"]) is True
    assert store.count() == 0


def test_history_respects_max_entries(tmp_path):
    store = HistoryStore(db_path=tmp_path / "h.db", max_entries=3)
    for index in range(6):
        store.add(f"entry {index}")
    assert store.count() == 3
    assert store.get_all()[0]["raw"] == "entry 5"


def test_history_retention_prunes_old_entries(tmp_path):
    store = HistoryStore(db_path=tmp_path / "h.db")
    store.add("recent")
    conn = store._connect()
    conn.execute(
        "INSERT INTO history (created_at, raw, enhanced, word_count) VALUES (?, ?, ?, ?)",
        ("2001-01-01 00:00:00", "ancient", "ancient", 1),
    )
    conn.commit()
    conn.close()

    removed = store.purge_older_than(30)
    assert removed == 1
    assert [row["raw"] for row in store.get_all()] == ["recent"]


def test_history_can_be_disabled_entirely(tmp_path):
    store = HistoryStore(db_path=tmp_path / "h.db", enabled=False)
    assert store.add("this must not be stored") is None
    assert store.count() == 0


def test_history_export_json_and_csv(tmp_path):
    store = HistoryStore(db_path=tmp_path / "h.db")
    store.add("export me", "Export me.", "casual", "English")

    as_json = store.export(tmp_path / "out.json")
    payload = json.loads(as_json.read_text(encoding="utf-8"))
    assert payload["entries"][0]["raw"] == "export me"

    as_csv = store.export(tmp_path / "out.csv", fmt="csv")
    text = as_csv.read_text(encoding="utf-8")
    assert "export me" in text and text.splitlines()[0].startswith("id,")


def test_legacy_json_history_is_imported(tmp_path):
    legacy = tmp_path / "transcription_history.json"
    legacy.write_text(
        json.dumps(
            [
                {"id": 2, "timestamp": "2026-01-02 10:00:00", "raw": "newer", "enhanced": "Newer", "mode": "formal", "language": "English"},
                {"id": 1, "timestamp": "2026-01-01 10:00:00", "raw": "older", "enhanced": "Older", "mode": "casual", "language": "English"},
            ]
        ),
        encoding="utf-8",
    )
    store = HistoryStore(db_path=tmp_path / "h.db")
    assert store.import_legacy(legacy) == 2
    # Legacy stored newest-first; after import the newest must still be first.
    assert [row["raw"] for row in store.get_all()] == ["newer", "older"]


# ── error model ──────────────────────────────────────────────────────────────


def test_every_catalog_entry_tells_the_user_what_to_do():
    for code, error in catalog().items():
        assert error.action, f"{code} has no action"
        assert error.summary, f"{code} has no summary"


def test_friendly_error_interpolates_context():
    error = friendly_error("invalid_api_key", provider="Groq")
    assert "Groq" in error.title
    assert "Groq" in error.summary
    assert "{" not in error.action


def test_classify_exception_maps_provider_failures():
    class HttpError(Exception):
        def __init__(self, status):
            super().__init__(f"HTTP {status}")
            self.status_code = status

    assert classify_exception(HttpError(401), "Groq").code == "invalid_api_key"
    assert classify_exception(HttpError(429), "Groq").code == "rate_limited"
    assert classify_exception(TimeoutError("timed out")).code == "network_error"
    assert classify_exception(ConnectionError("connection reset")).code == "network_error"
    assert classify_exception(ValueError("something odd")).code == "pipeline_error"


def test_retryable_errors_are_flagged():
    assert friendly_error("network_error").retryable is True
    assert friendly_error("invalid_api_key").retryable is True
    assert friendly_error("no_api_key").retryable is False


# ── injection ────────────────────────────────────────────────────────────────


@pytest.fixture
def injector():
    pytest.importorskip("pyperclip")
    from system.injector import InjectionError, InjectionStrategy, TextInjector

    return TextInjector, InjectionStrategy, InjectionError


def test_injection_of_empty_text_is_a_failure(injector):
    TextInjector, _, InjectionError = injector
    result = TextInjector().inject("   ")
    assert result.success is False
    assert result.error is InjectionError.EMPTY_TEXT
    assert bool(result) is False


def test_unsupported_strategy_reports_failure_not_success(injector):
    """The old injector returned True as soon as Ctrl+V was sent."""
    TextInjector, InjectionStrategy, _ = injector
    text_injector = TextInjector(strategy_order=[InjectionStrategy.UNSUPPORTED])
    result = text_injector.inject("never delivered")
    assert result.success is False
    assert result.verified is False
    assert result.strategy is InjectionStrategy.UNSUPPORTED
    assert result.user_message()


def test_duplicate_injection_is_suppressed(injector):
    TextInjector, InjectionStrategy, _ = injector
    text_injector = TextInjector(strategy_order=[InjectionStrategy.UNSUPPORTED])
    assert text_injector.inject("once").success is False
    # A strategy that cannot deliver must never be recorded as a success either.
    assert text_injector.inject_text("once") is False


def test_injector_diagnostics_are_safe(injector):
    TextInjector, _, _ = injector
    payload = TextInjector().diagnostics()
    assert "strategies" in payload
    assert "timeout_s" in payload


# ── hotkey validation ────────────────────────────────────────────────────────


def test_hotkey_validation_rules():
    pytest.importorskip("pynput")
    from core.hotkey_listener import (
        HotkeyListener,
        find_conflicts,
        normalize_hotkey,
        validate_hotkey,
    )

    ok, canonical, error = validate_hotkey("win+shift")
    assert ok and canonical == "shift+win" and error is None

    ok, _, error = validate_hotkey("ctrl+shift+v")
    assert not ok and "reserved" in error.lower()

    ok, _, error = validate_hotkey("alt+tab")
    assert not ok

    ok, _, error = validate_hotkey("")
    assert not ok and error

    ok, _, error = validate_hotkey("ctrl+ctrl+r")
    assert not ok and "twice" in error.lower()

    ok, _, error = validate_hotkey("ctrl+alt+shift+r")
    assert not ok and "three keys" in error.lower()

    assert normalize_hotkey("Win+Shift") == "shift+win"

    conflicts = find_conflicts({"win+alt": "casual", "alt+win": "technical"})
    assert conflicts and "assigned to both" in conflicts[0]

    # Malformed configuration must not take the listener down.
    listener = HotkeyListener("definitely+not+a+valid+hotkey")
    assert listener.hotkey == "shift+win"
    assert listener.describe()["enabled"] is True


def test_listener_rejects_reserved_hotkey_changes():
    pytest.importorskip("pynput")
    from core.hotkey_listener import HotkeyListener

    listener = HotkeyListener("win+shift")
    assert listener.set_hotkey("alt+f4") is False
    assert listener.hotkey == "shift+win"
    assert listener.set_hotkey("ctrl+alt+r") is True
    assert listener.hotkey == "alt+ctrl+r"


def _config_only_orchestrator(tmp_path):
    """An orchestrator with just enough state to exercise config writes.

    Constructing the real object starts threads, a recorder and a global
    listener; the persistence guard does not need any of that.
    """
    from types import SimpleNamespace

    from core.app_orchestrator import AppOrchestrator

    app = object.__new__(AppOrchestrator)
    app.config = {"hotkey": "win+shift", "mode_hotkeys": {}}
    app.config_path = tmp_path / "settings.json"
    app.hotkey_listener = None
    app.enhancer = None
    app.history = SimpleNamespace(configure=lambda **kwargs: None)
    app.voice_commands = SimpleNamespace(update_custom=lambda value: None)
    app.profiles = SimpleNamespace(update=lambda value: None)
    app.sound = SimpleNamespace(enabled=True, volume=0.7)
    return app


def test_reserved_hotkey_is_never_persisted(tmp_path):
    """Accepting a combo the listener refuses would lie to the user."""
    app = _config_only_orchestrator(tmp_path)

    assert app.update_config("hotkey", "alt+f4") is False
    assert app.config["hotkey"] == "win+shift"
    assert not app.config_path.exists()

    assert app.update_config("hotkey", "ctrl+alt+d") is True
    assert app.config["hotkey"] == "alt+ctrl+d"


def test_mode_hotkeys_must_not_collide_or_be_reserved(tmp_path):
    app = _config_only_orchestrator(tmp_path)

    assert app.update_config("mode_hotkeys", {"win+shift": "casual"}) is False
    assert app.update_config("mode_hotkeys", {"alt+f4": "casual"}) is False
    assert app.config["mode_hotkeys"] == {}

    assert app.update_config("mode_hotkeys", {"win+alt": "casual"}) is True
    assert app.config["mode_hotkeys"] == {"win+alt": "casual"}
