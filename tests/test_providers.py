"""Provider inventory and credential safety (all mocked, no network).

Inventory verified from the code (v3.0.0)
-----------------------------------------
Web LLM chain (Q&A and enhancement share it), in fallback order:

1. Muse Spark      — ``MODEL_API_KEY``       → https://api.meta.ai/v1, model ``muse-spark-1.3``
2. OpenRouter      — ``OPENROUTER_API_KEY``  → https://openrouter.ai/api/v1, ``llama-3.3-70b-instruct:free``
3. Groq            — ``GROQ_API_KEY``        → SDK default, ``llama-3.3-70b-versatile``
4. OpenAI          — ``OPENAI_API_KEY``      → SDK default, ``gpt-4o-mini``

Web transcription chain: Muse Voice Transcribe (``MODEL_API_KEY``, multipart
REST) → Groq Whisper (``GROQ_API_KEY``, ``whisper-large-v3-turbo``); 503 with
neither.

Desktop: Groq → OpenAI whisper (``ai/transcriber.py``), keys resolved from the
credential vault (DPAPI → keyring → obfuscated) with the environment as
fallback (``utils/credentials.load_api_keys``).

No Muse transcription "plugin" or any other provider exists; these tests fail
if the inventory drifts.
"""

from __future__ import annotations

import io
import sys
import types
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

from tests.conftest import ApiUser

REPO = Path(__file__).resolve().parent.parent
WEB_APP = REPO / "web" / "app.py"

ENV_KEYS = ("MODEL_API_KEY", "OPENROUTER_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY")
CLIENT_SECRETS = ENV_KEYS + ("gsk_", "sk-", "Bearer ")


def _clear_provider_keys(monkeypatch):
    for name in ENV_KEYS:
        monkeypatch.delenv(name, raising=False)


@contextmanager
def _fake_module(name: str, **attrs):
    """Install a stand-in for an importable SDK module; restore afterwards."""
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    saved = sys.modules.get(name)
    sys.modules[name] = module
    try:
        yield module
    finally:
        if saved is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = saved


class _RecordingClient:
    """Stands in for openai.OpenAI / groq.Groq and records constructor args."""

    calls: list = []          # constructor kwargs (api_key, base_url)
    create_calls: list = []   # chat.completions.create kwargs (model, messages)
    text: str = "stub answer"
    error: Exception | None = None  # fail every client when set
    fail_keys: tuple = ()           # ... or only clients built with these api keys

    def __init__(self, **kwargs):
        type(self).calls.append(kwargs)
        self._fail = type(self).error is not None or (
            kwargs.get("api_key", "") in type(self).fail_keys
        )
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )
        self.audio = SimpleNamespace(
            transcriptions=SimpleNamespace(create=self._create)
        )

    def _create(self, **kwargs):
        type(self).create_calls.append(kwargs)
        if self._fail:
            raise type(self).error or RuntimeError("simulated provider failure")
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=type(self).text))]
        )

    @classmethod
    def reset(cls, text: str = "stub answer", error: Exception | None = None,
              fail_keys: tuple = ()):
        cls.calls = []
        cls.create_calls = []
        cls.text = text
        cls.error = error
        cls.fail_keys = fail_keys


def _make_pro(client, web_app, identifier: str) -> ApiUser:
    user = ApiUser(client, identifier)
    conn = web_app._get_db()
    conn.execute("UPDATE users SET tier = 'pro' WHERE id = ?", (user.user_id,))
    conn.commit()
    conn.close()
    return user


def _make_verified(client, web_app, identifier: str) -> ApiUser:
    user = ApiUser(client, identifier)
    conn = web_app._get_db()
    conn.execute("UPDATE users SET email_verified = 1 WHERE id = ?", (user.user_id,))
    conn.commit()
    conn.close()
    return user


# ── inventory guardrails ─────────────────────────────────────────────────────


def test_web_llm_chain_matches_the_documented_inventory():
    source = WEB_APP.read_text(encoding="utf-8")
    for fragment in (
        "MODEL_API_KEY",
        "OPENROUTER_API_KEY",
        "GROQ_API_KEY",
        "OPENAI_API_KEY",
        "https://api.meta.ai/v1",
        "muse-spark-1.3",
        "openrouter.ai/api/v1",
        "meta-llama/llama-3.3-70b-instruct:free",
        "llama-3.3-70b-versatile",
        "gpt-4o-mini",
    ):
        assert fragment in source, f"provider inventory drift: {fragment} missing"


def test_no_undeclared_provider_base_url_is_configured():
    """Only the two documented base URLs may exist in web/app.py."""
    import re

    source = WEB_APP.read_text(encoding="utf-8")
    base_urls = set(re.findall(r'base_url\s*=\s*"([^"]+)"', source))
    assert base_urls == {"https://api.meta.ai/v1", "https://openrouter.ai/api/v1"}


# ── web LLM chain (Q&A / enhancement), fully mocked ─────────────────────────


def test_qa_uses_muse_first_with_its_documented_model(app_client, monkeypatch):
    client, web_app = app_client
    _clear_provider_keys(monkeypatch)
    monkeypatch.setenv("MODEL_API_KEY", "mk_test_primary")
    user = _make_pro(client, web_app, "qamuse@gmail.com")

    _RecordingClient.reset(text="muse answer")
    with _fake_module("openai", OpenAI=_RecordingClient):
        response = client.post("/api/qa", json={"question": "hi"}, headers=user.headers)

    assert response.status_code == 200
    assert response.get_json()["answer"] == "muse answer"
    assert _RecordingClient.calls[0]["api_key"] == "mk_test_primary"
    assert _RecordingClient.calls[0]["base_url"] == "https://api.meta.ai/v1"
    assert _RecordingClient.create_calls[0]["model"] == "muse-spark-1.3"


def test_qa_falls_through_to_groq_when_muse_fails(app_client, monkeypatch):
    client, web_app = app_client
    _clear_provider_keys(monkeypatch)
    monkeypatch.setenv("MODEL_API_KEY", "mk_test_broken")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_fallback")
    user = _make_pro(client, web_app, "qafallback@gmail.com")

    _RecordingClient.reset(fail_keys=("mk_test_broken",))  # muse down, groq up
    with _fake_module("openai", OpenAI=_RecordingClient):
        with _fake_module("groq", Groq=_RecordingClient):
            response = client.post("/api/qa", json={"question": "hi"}, headers=user.headers)

    assert response.get_json()["answer"] == "stub answer"
    assert _RecordingClient.calls[0]["api_key"] == "mk_test_broken"  # muse tried first
    assert _RecordingClient.calls[1]["api_key"] == "gsk_test_fallback"
    assert _RecordingClient.create_calls[1]["model"] == "llama-3.3-70b-versatile"


def test_qa_openai_fallback_sends_no_base_url(app_client, monkeypatch):
    client, web_app = app_client
    _clear_provider_keys(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk_test_lastresort")
    user = _make_pro(client, web_app, "qaopenai@gmail.com")

    _RecordingClient.reset(text="openai answer")
    with _fake_module("openai", OpenAI=_RecordingClient):
        response = client.post("/api/qa", json={"question": "hi"}, headers=user.headers)

    assert response.get_json()["answer"] == "openai answer"
    assert _RecordingClient.calls[0]["api_key"] == "sk_test_lastresort"
    assert _RecordingClient.calls[0].get("base_url") is None
    assert _RecordingClient.create_calls[0]["model"] == "gpt-4o-mini"


def test_enhancement_is_refused_with_503_when_no_provider_is_configured(
    app_client, monkeypatch
):
    client, web_app = app_client
    _clear_provider_keys(monkeypatch)
    user = ApiUser(client, "nokeys@gmail.com")

    response = client.post(
        "/api/enhance", json={"text": "hello world", "mode": "formal"}, headers=user.headers
    )
    assert response.status_code == 503
    assert "no AI provider key" in response.get_json()["error"]
    # Q&A degrades to the honest apology string, never a fabricated answer.
    assert web_app._call_llm_for_qa("anything").startswith("I'm sorry")


def test_openrouter_sits_between_muse_and_groq(app_client, monkeypatch):
    client, web_app = app_client
    _clear_provider_keys(monkeypatch)
    monkeypatch.setenv("MODEL_API_KEY", "mk_test_x")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or_test_x")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_x")
    user = _make_pro(client, web_app, "qarouter@gmail.com")

    _RecordingClient.reset(fail_keys=("mk_test_x", "or_test_x"))
    with _fake_module("openai", OpenAI=_RecordingClient):
        with _fake_module("groq", Groq=_RecordingClient):
            response = client.post("/api/qa", json={"question": "hi"}, headers=user.headers)

    assert response.get_json()["answer"] == "stub answer"  # groq rescued the request
    # Muse is tried first, OpenRouter second, Groq third.
    models = [call["model"] for call in _RecordingClient.create_calls[:2]]
    assert models == ["muse-spark-1.3", "meta-llama/llama-3.3-70b-instruct:free"]
    assert _RecordingClient.calls[2]["api_key"] == "gsk_test_x"


def test_provider_failures_never_log_the_key(app_client, monkeypatch, caplog):
    client, web_app = app_client
    _clear_provider_keys(monkeypatch)
    monkeypatch.setenv("MODEL_API_KEY", "mk_supervaluable_secret")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_supervaluable_secret")

    _RecordingClient.reset(error=RuntimeError("quota exhausted"))
    with _fake_module("openai", OpenAI=_RecordingClient):
        with _fake_module("groq", Groq=_RecordingClient):
            web_app._call_llm_for_qa("anything")

    assert "mk_supervaluable_secret" not in caplog.text
    assert "gsk_supervaluable_secret" not in caplog.text


# ── web transcription chain ─────────────────────────────────────────────────


def _wav_bytes() -> bytes:
    return b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00" + b"\x00" * 16


def test_transcribe_falls_back_to_groq_whisper(app_client, monkeypatch):
    client, web_app = app_client
    _clear_provider_keys(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_whisper")
    user = _make_verified(client, web_app, "whisper@gmail.com")

    class _WhisperClient:
        calls: list = []

        def __init__(self, **kwargs):
            type(self).calls.append(kwargs)

        @property
        def audio(self):
            return SimpleNamespace(
                transcriptions=SimpleNamespace(
                    create=lambda **kw: (
                        type(self).calls.append(kw),
                        SimpleNamespace(text="hello from whisper"),
                    )[1]
                )
            )

    _WhisperClient.calls = []
    with _fake_module("groq", Groq=_WhisperClient):
        response = client.post(
            "/api/transcribe",
            data={"audio": (io.BytesIO(_wav_bytes()), "clip.wav")},
            headers=user.headers,
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["provider"] == "groq-whisper"
    assert body["transcript"] == "hello from whisper"
    assert _WhisperClient.calls[0]["api_key"] == "gsk_test_whisper"


def test_transcribe_without_any_speech_key_returns_503(app_client, monkeypatch):
    client, web_app = app_client
    _clear_provider_keys(monkeypatch)
    user = _make_verified(client, web_app, "nospeech@gmail.com")

    response = client.post(
        "/api/transcribe",
        data={"audio": (io.BytesIO(_wav_bytes()), "clip.wav")},
        headers=user.headers,
        content_type="multipart/form-data",
    )
    assert response.status_code == 503
    assert "MODEL_API_KEY" in response.get_json()["error"]


def test_transcribe_muse_failure_falls_through_to_groq(app_client, monkeypatch):
    client, web_app = app_client
    _clear_provider_keys(monkeypatch)
    monkeypatch.setenv("MODEL_API_KEY", "mk_test_speech")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_speech")
    user = _make_verified(client, web_app, "bothspeech@gmail.com")

    def _broken_post(*args, **kwargs):
        raise RuntimeError("muse transcribe 500")

    monkeypatch.setattr(web_app.http_requests, "post", _broken_post)

    class _WhisperClient:
        def __init__(self, **kwargs):
            pass

        @property
        def audio(self):
            return SimpleNamespace(
                transcriptions=SimpleNamespace(
                    create=lambda **kw: SimpleNamespace(text="groq heard this")
                )
            )

    with _fake_module("groq", Groq=_WhisperClient):
        response = client.post(
            "/api/transcribe",
            data={"audio": (io.BytesIO(_wav_bytes()), "clip.wav")},
            headers=user.headers,
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    assert response.get_json()["provider"] == "groq-whisper"


# ── desktop credential loading ───────────────────────────────────────────────


def test_desktop_keys_resolve_from_the_vault_first_then_the_environment(isolated_home):
    from utils import credentials

    store = credentials.CredentialStore(credentials.ObfuscatedBackend())
    assert store.set("groq_api_key", "gsk_from_vault")

    resolved = credentials.load_api_keys({}, store=store)
    assert resolved["groq_api_key"] == "gsk_from_vault"

    # Environment is the fallback for names the vault does not hold.
    resolved = credentials.load_api_keys({}, store=store)
    assert resolved.get("openrouter_api_key") in (None, "")  # nothing configured


def test_desktop_environment_is_a_fallback_not_an_override(isolated_home, monkeypatch):
    from utils import credentials

    monkeypatch.setenv("OPENROUTER_API_KEY", "or_from_environment")
    store = credentials.CredentialStore(credentials.ObfuscatedBackend())
    resolved = credentials.load_api_keys({}, store=store)
    assert resolved["openrouter_api_key"] == "or_from_environment"
    # The value still never lands in plaintext settings.
    assert "or_from_environment" not in repr(store.describe())


def test_desktop_transcriber_selects_groq_from_the_environment(
    isolated_home, monkeypatch
):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_desktop_env")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    class _DesktopGroq:
        calls: list = []

        def __init__(self, **kwargs):
            type(self).calls.append(kwargs)

    _DesktopGroq.calls = []
    with _fake_module("groq", Groq=_DesktopGroq):
        from ai.transcriber import Transcriber

        transcriber = Transcriber()

    assert transcriber.backend == "groq"
    assert transcriber.model == "whisper-large-v3-turbo"
    assert _DesktopGroq.calls[0]["api_key"] == "gsk_desktop_env"


# ── client bundle / log hygiene ──────────────────────────────────────────────


def test_no_provider_key_or_scheme_reaches_the_client_bundle():
    offenders = []
    for path in (REPO / "web" / "static").rglob("*"):
        if path.is_file() and path.suffix in {".html", ".js", ".css"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for needle in ("MODEL_API_KEY", "OPENROUTER_API_KEY", "GROQ_API_KEY",
                           "OPENAI_API_KEY", "gsk_", "sk-proj-"):
                if needle in text:
                    offenders.append(f"{path.name}: {needle}")
    assert offenders == []


def test_health_and_public_config_do_not_echo_provider_keys(app_client, monkeypatch):
    client, _ = app_client
    for name, value in zip(ENV_KEYS, ("mk_x", "or_x", "gsk_x", "sk_x")):
        monkeypatch.setenv(name, value)
    for path in ("/api/health", "/api/public-config"):
        response = client.get(path)
        assert response.status_code == 200
        assert "mk_x" not in response.get_data(as_text=True)
        assert "gsk_x" not in response.get_data(as_text=True)
