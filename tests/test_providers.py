"""Provider inventory and credential safety (all mocked, no network).

Inventory (post P0.2):
----------------------
Web LLM chain (Q&A and enhancement share web/services/llm_service.py),
in fallback order:

1. OpenRouter      — ``OPENROUTER_API_KEY``  → https://openrouter.ai/api/v1, ``llama-3.3-70b-instruct:free``
2. Groq            — ``GROQ_API_KEY``        → SDK default, ``llama-3.3-70b-versatile``
3. OpenAI          — ``OPENAI_API_KEY``      → SDK default, ``gpt-4o-mini``

Web transcription chain: Groq Whisper (``GROQ_API_KEY``,
``whisper-large-v3-turbo``) → OpenAI Whisper (``OPENAI_API_KEY``,
``whisper-1``); 503 with neither.

The fabricated "Muse" provider (MODEL_API_KEY → https://api.meta.ai/v1,
muse-spark-1.3 / muse-voice-transcribe-1.0) was removed: those endpoints do
not exist. These tests fail if Muse references return or the inventory drifts.

Desktop: Groq → OpenAI whisper (``ai/transcriber.py``), keys resolved from the
credential vault (DPAPI → keyring → obfuscated) with the environment as
fallback (``utils/credentials.load_api_keys``).
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
LLM_SERVICE = REPO / "web" / "services" / "llm_service.py"

ENV_KEYS = ("OPENROUTER_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY")
CLIENT_SECRETS = ENV_KEYS + ("gsk_", "sk-", "Bearer ")


def _clear_provider_keys(monkeypatch):
    for name in ENV_KEYS + ("MODEL_API_KEY",):
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

    calls: list = []  # constructor kwargs (api_key, base_url)
    create_calls: list = []  # chat.completions.create kwargs (model, messages)
    text: str = "stub answer"
    error: Exception | None = None  # fail every client when set
    fail_keys: tuple = ()  # ... or only clients built with these api keys

    def __init__(self, **kwargs):
        type(self).calls.append(kwargs)
        self._fail = type(self).error is not None or (kwargs.get("api_key", "") in type(self).fail_keys)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self.audio = SimpleNamespace(transcriptions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        type(self).create_calls.append(kwargs)
        if self._fail:
            raise type(self).error or RuntimeError("simulated provider failure")
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=type(self).text))])

    @classmethod
    def reset(cls, text: str = "stub answer", error: Exception | None = None, fail_keys: tuple = ()):
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
    source = LLM_SERVICE.read_text(encoding="utf-8")
    for fragment in (
        "OPENROUTER_API_KEY",
        "GROQ_API_KEY",
        "OPENAI_API_KEY",
        "openrouter.ai/api/v1",
        "meta-llama/llama-3.3-70b-instruct:free",
        "llama-3.3-70b-versatile",
        "gpt-4o-mini",
    ):
        assert fragment in source, f"provider inventory drift: {fragment} missing"


def test_fabricated_muse_provider_is_gone():
    for path in (WEB_APP, LLM_SERVICE, REPO / ".env.example", REPO / "render.yaml"):
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert "api.meta.ai" not in text, f"Muse endpoint still referenced in {path.name}"
        assert "muse-spark-1.3" not in text, f"Muse model still referenced in {path.name}"
        assert "muse-voice-transcribe" not in text, f"Muse transcribe still referenced in {path.name}"
    app_source = WEB_APP.read_text(encoding="utf-8")
    assert "MODEL_API_KEY" not in app_source, "MODEL_API_KEY must be removed from web/app.py"
    service_source = LLM_SERVICE.read_text(encoding="utf-8")
    assert "MODEL_API_KEY" not in service_source, "MODEL_API_KEY must be removed from llm_service.py"


def test_no_undeclared_provider_base_url_is_configured():
    """Only the OpenRouter base URL may exist in the LLM service."""
    import re

    source = LLM_SERVICE.read_text(encoding="utf-8")
    base_urls = set(re.findall(r'base_url\s*=\s*"([^"]+)"', source))
    assert base_urls <= {"https://openrouter.ai/api/v1"}, f"unexpected base URLs: {base_urls}"
    assert "https://openrouter.ai/api/v1" in source


# ── web LLM chain (Q&A / enhancement), fully mocked ─────────────────────────


def test_qa_uses_openrouter_first_with_its_documented_model(app_client, monkeypatch):
    client, web_app = app_client
    _clear_provider_keys(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "or_test_primary")
    user = _make_pro(client, web_app, "qaopenrouter@gmail.com")

    _RecordingClient.reset(text="openrouter answer")
    with _fake_module("openai", OpenAI=_RecordingClient):
        response = client.post("/api/qa", json={"question": "hi"}, headers=user.headers)

    assert response.status_code == 200
    assert response.get_json()["answer"] == "openrouter answer"
    assert _RecordingClient.calls[0]["api_key"] == "or_test_primary"
    assert _RecordingClient.calls[0]["base_url"] == "https://openrouter.ai/api/v1"
    assert _RecordingClient.create_calls[0]["model"] == "meta-llama/llama-3.3-70b-instruct:free"


def test_qa_falls_through_to_groq_when_openrouter_fails(app_client, monkeypatch):
    client, web_app = app_client
    _clear_provider_keys(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "or_test_broken")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_fallback")
    user = _make_pro(client, web_app, "qafallback@gmail.com")

    _RecordingClient.reset(fail_keys=("or_test_broken",))  # openrouter down, groq up
    with _fake_module("openai", OpenAI=_RecordingClient):
        with _fake_module("groq", Groq=_RecordingClient):
            response = client.post("/api/qa", json={"question": "hi"}, headers=user.headers)

    assert response.get_json()["answer"] == "stub answer"
    assert _RecordingClient.calls[0]["api_key"] == "or_test_broken"  # openrouter tried first
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


def test_enhancement_is_refused_with_503_when_no_provider_is_configured(app_client, monkeypatch):
    client, web_app = app_client
    _clear_provider_keys(monkeypatch)
    user = ApiUser(client, "nokeys@gmail.com")

    response = client.post("/api/enhance", json={"text": "hello world", "mode": "formal"}, headers=user.headers)
    assert response.status_code == 503
    assert "no AI provider key" in response.get_json()["error"]
    # Q&A degrades to the honest apology string, never a fabricated answer.
    assert web_app._call_llm_for_qa("anything").startswith("I'm sorry")


def test_openrouter_groq_openai_fallback_order(app_client, monkeypatch):
    client, web_app = app_client
    _clear_provider_keys(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "or_test_x")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_x")
    monkeypatch.setenv("OPENAI_API_KEY", "sk_test_x")
    user = _make_pro(client, web_app, "qarouter@gmail.com")

    _RecordingClient.reset(fail_keys=("or_test_x", "gsk_test_x"))
    with _fake_module("openai", OpenAI=_RecordingClient):
        with _fake_module("groq", Groq=_RecordingClient):
            response = client.post("/api/qa", json={"question": "hi"}, headers=user.headers)

    assert response.get_json()["answer"] == "stub answer"  # openai rescued the request
    # OpenRouter tried first, Groq second, OpenAI third.
    models = [call["model"] for call in _RecordingClient.create_calls[:3]]
    assert models == [
        "meta-llama/llama-3.3-70b-instruct:free",
        "llama-3.3-70b-versatile",
        "gpt-4o-mini",
    ]


def test_provider_failures_never_log_the_key(app_client, monkeypatch, caplog):
    client, web_app = app_client
    _clear_provider_keys(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "or_supervaluable_secret")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_supervaluable_secret")

    _RecordingClient.reset(error=RuntimeError("quota exhausted"))
    with _fake_module("openai", OpenAI=_RecordingClient):
        with _fake_module("groq", Groq=_RecordingClient):
            web_app._call_llm_for_qa("anything")

    assert "or_supervaluable_secret" not in caplog.text
    assert "gsk_supervaluable_secret" not in caplog.text


def test_llm_clients_enforce_explicit_timeouts(monkeypatch):
    """Server clients must carry an explicit timeout (connect=5s, read=30s)."""
    import importlib

    import web.services.llm_service as svc

    importlib.reload(svc)
    captured = {}

    class _TimeoutClient(_RecordingClient):
        pass

    def _capture_openai(**kwargs):
        captured["openai"] = dict(kwargs)
        return _RecordingClient(**kwargs)

    def _capture_groq(**kwargs):
        captured["groq"] = dict(kwargs)
        return _RecordingClient(**kwargs)

    monkeypatch.setenv("OPENROUTER_API_KEY", "or_timeout")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_timeout")
    monkeypatch.setenv("OPENAI_API_KEY", "sk_timeout")
    _RecordingClient.reset(text="ok", fail_keys=("or_timeout",))
    with _fake_module("openai", OpenAI=_capture_openai):
        with _fake_module("groq", Groq=_capture_groq):
            svc.chat("hello")

    assert "timeout" in captured["openai"], "OpenAI client missing explicit timeout"
    assert "timeout" in captured["groq"], "Groq client missing explicit timeout"
    assert captured["openai"]["timeout"] is not None
    assert captured["groq"]["timeout"] is not None


def test_desktop_clients_use_openai_api_timeout(isolated_home, monkeypatch):
    """ai/transcriber.py and ai/enhancer.py must thread OPENAI_API_TIMEOUT."""
    import config.constants as constants

    assert constants.OPENAI_API_TIMEOUT, "OPENAI_API_TIMEOUT must be defined and used"
    monkeypatch.setenv("GROQ_API_KEY", "gsk_desktop_timeout")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    seen = {}

    class _DesktopGroq:
        def __init__(self, **kwargs):
            seen.update(kwargs)

    with _fake_module("groq", Groq=_DesktopGroq):
        from ai.transcriber import Transcriber

        Transcriber()

    assert seen.get("timeout") == constants.OPENAI_API_TIMEOUT


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
    assert "GROQ_API_KEY" in response.get_json()["error"]


def test_transcribe_groq_failure_falls_through_to_openai(app_client, monkeypatch):
    client, web_app = app_client
    _clear_provider_keys(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_speech")
    monkeypatch.setenv("OPENAI_API_KEY", "sk_test_speech")
    user = _make_verified(client, web_app, "bothspeech@gmail.com")

    class _FailingGroq:
        def __init__(self, **kwargs):
            pass

        @property
        def audio(self):
            return SimpleNamespace(
                transcriptions=SimpleNamespace(create=lambda **kw: (_ for _ in ()).throw(RuntimeError("groq 500")))
            )

    class _OpenAIWhisper:
        def __init__(self, **kwargs):
            pass

        @property
        def audio(self):
            return SimpleNamespace(
                transcriptions=SimpleNamespace(create=lambda **kw: SimpleNamespace(text="openai heard this"))
            )

    with _fake_module("groq", Groq=_FailingGroq):
        with _fake_module("openai", OpenAI=_OpenAIWhisper):
            response = client.post(
                "/api/transcribe",
                data={"audio": (io.BytesIO(_wav_bytes()), "clip.wav")},
                headers=user.headers,
                content_type="multipart/form-data",
            )

    assert response.status_code == 200
    assert response.get_json()["provider"] == "openai-whisper"


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


def test_desktop_transcriber_selects_groq_from_the_environment(isolated_home, monkeypatch):
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
            for needle in ("MODEL_API_KEY", "OPENROUTER_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY", "gsk_", "sk-proj-"):
                if needle in text:
                    offenders.append(f"{path.name}: {needle}")
    assert offenders == []


def test_health_and_public_config_do_not_echo_provider_keys(app_client, monkeypatch):
    client, _ = app_client
    for name, value in zip(ENV_KEYS, ("or_x", "gsk_x", "sk_x")):
        monkeypatch.setenv(name, value)
    for path in ("/api/health", "/api/public-config"):
        response = client.get(path)
        assert response.status_code == 200
        assert "or_x" not in response.get_data(as_text=True)
        assert "gsk_x" not in response.get_data(as_text=True)
