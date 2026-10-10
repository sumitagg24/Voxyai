"""
Centralized LLM provider service for Voxylis web backend.

Fallback order: OpenRouter -> Groq -> OpenAI.
(Fabricated Muse provider removed: that endpoint does not exist.)

System prompts are defined once here. All clients use explicit timeouts:
server connect=5s / read=30s. Desktop uses config.constants.OPENAI_API_TIMEOUT.

Clients are constructed lazily on every call (reading os.environ fresh) so
tests can monkeypatch env vars and stub the openai/groq SDK modules.
"""

from __future__ import annotations

import io
import os
from typing import Any, Dict, List, Optional

from utils.logger import log_warning

# System prompts defined once.
SYSTEM_PROMPT_QA = (
    "You are Voxy, a helpful AI assistant built into the Voxylis voice-to-text app. "
    "Answer questions concisely and accurately. If the question is about Voxylis, "
    "reference its features (voice-to-text, AI enhancement, multi-language support)."
)

ENHANCEMENT_MODE_PROMPTS = {
    "formal": "Rewrite the following text in a formal, professional tone. Fix grammar, punctuation, and clarity. Preserve the original meaning. Output ONLY the enhanced text, nothing else.",
    "casual": "Rewrite the following text in a relaxed, friendly, conversational tone. Fix obvious errors. Preserve the original meaning. Output ONLY the enhanced text, nothing else.",
    "technical": "Rewrite the following text in a precise, technical tone suitable for documentation or engineering audiences. Fix grammar and clarity. Preserve the original meaning. Output ONLY the enhanced text, nothing else.",
    "concise": "Rewrite the following text as concisely as possible while preserving all key information. Remove filler words and redundancy. Output ONLY the enhanced text, nothing else.",
    "creative": "Rewrite the following text with creative flair — vivid language, varied sentence structure, engaging tone. Preserve the original meaning. Output ONLY the enhanced text, nothing else.",
}

# Server timeout: connect=5s, read=30s. openai/groq clients accept an
# httpx.Timeout or a float (total). Prefer httpx.Timeout when available.
def _server_timeout():
    try:
        import httpx

        return httpx.Timeout(30.0, connect=5.0)
    except Exception:
        return 30.0


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
GROQ_CHAT_MODEL = "llama-3.3-70b-versatile"
OPENAI_CHAT_MODEL = "gpt-4o-mini"


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def is_configured() -> bool:
    """True when at least one chat provider key is present in the environment."""
    return any(_env(n) for n in ("OPENROUTER_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY"))


def is_transcribe_configured() -> bool:
    """True when at least one STT provider key is present."""
    return any(_env(n) for n in ("GROQ_API_KEY", "OPENAI_API_KEY"))


def _make_openai_client(api_key: str, base_url: Optional[str] = None):
    from openai import OpenAI

    kwargs: Dict[str, Any] = {
        "api_key": api_key,
        "timeout": _server_timeout(),
        "max_retries": 0,
    }
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def _make_groq_client(api_key: str):
    from groq import Groq

    return Groq(api_key=api_key, timeout=_server_timeout())


def _try_chat(client, model: str, messages: List[Dict[str, str]], max_tokens: int, temperature: float) -> Optional[str]:
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        content = resp.choices[0].message.content
        return (content or "").strip() or None
    except Exception as e:
        # Never log keys: clients only log the failure.
        log_warning(f"LLM chat failed (model={model}): {e}")
        return None


def chat(
    prompt: str,
    system_prompt: str = SYSTEM_PROMPT_QA,
    max_tokens: int = 512,
    temperature: float = 0.7,
) -> str:
    """Chat completion with fallback chain OpenRouter -> Groq -> OpenAI.

    Raises RuntimeError when no provider is configured or all fail.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    openrouter_key = _env("OPENROUTER_API_KEY")
    if openrouter_key:
        try:
            client = _make_openai_client(openrouter_key, base_url=OPENROUTER_BASE_URL)
        except Exception as e:
            log_warning(f"OpenRouter client init failed: {e}")
            client = None
        if client is not None:
            result = _try_chat(client, OPENROUTER_MODEL, messages, max_tokens, temperature)
            if result:
                return result

    groq_key = _env("GROQ_API_KEY")
    if groq_key:
        try:
            client = _make_groq_client(groq_key)
        except Exception as e:
            log_warning(f"Groq client init failed: {e}")
            client = None
        if client is not None:
            result = _try_chat(client, GROQ_CHAT_MODEL, messages, max_tokens, temperature)
            if result:
                return result

    openai_key = _env("OPENAI_API_KEY")
    if openai_key:
        try:
            client = _make_openai_client(openai_key)
        except Exception as e:
            log_warning(f"OpenAI client init failed: {e}")
            client = None
        if client is not None:
            result = _try_chat(client, OPENAI_CHAT_MODEL, messages, max_tokens, temperature)
            if result:
                return result

    raise RuntimeError("All LLM providers failed or not configured")


def transcribe(audio_bytes: bytes, filename: str = "audio.wav", mode: str = "PUSH_TO_TALK") -> Dict[str, Any]:
    """Transcribe audio via Groq Whisper (primary) then OpenAI Whisper.

    Returns dict with transcript/provider/mode. Raises RuntimeError when
    unconfigured or all providers fail.
    """
    groq_key = _env("GROQ_API_KEY")
    if groq_key:
        try:
            client = _make_groq_client(groq_key)
        except Exception as e:
            log_warning(f"Groq client init failed: {e}")
            client = None
        if client is not None:
            try:
                kwargs: Dict[str, Any] = {
                    "file": (filename, audio_bytes, "audio/wav"),
                    "model": "whisper-large-v3-turbo",
                    "response_format": "verbose_json",
                }
                if mode == "DIARIZATION":
                    kwargs["timestamp_granularities"] = ["segment"]
                resp = client.audio.transcriptions.create(**kwargs)
                transcript = getattr(resp, "text", None) or str(resp)
                if transcript.strip():
                    return {"transcript": transcript.strip(), "provider": "groq-whisper", "mode": mode}
            except Exception as e:
                log_warning(f"Groq Whisper failed: {e}")

    openai_key = _env("OPENAI_API_KEY")
    if openai_key:
        try:
            client = _make_openai_client(openai_key)
        except Exception as e:
            log_warning(f"OpenAI client init failed: {e}")
            client = None
        if client is not None:
            try:
                audio_file = io.BytesIO(audio_bytes)
                audio_file.name = filename
                resp = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json",
                )
                transcript = getattr(resp, "text", None) or str(resp)
                if transcript.strip():
                    return {"transcript": transcript.strip(), "provider": "openai-whisper", "mode": mode}
            except Exception as e:
                log_warning(f"OpenAI Whisper failed: {e}")

    raise RuntimeError("Transcription unavailable: no GROQ_API_KEY or OPENAI_API_KEY configured")


# Backwards-compatible class wrapper (some code imports LLMService).
class LLMService:
    """Thin wrapper preserving the old class API; all state is env-driven."""

    SYSTEM_PROMPT_QA = SYSTEM_PROMPT_QA
    ENHANCEMENT_MODE_PROMPTS = ENHANCEMENT_MODE_PROMPTS

    def chat(self, prompt: str, system_prompt: str = SYSTEM_PROMPT_QA, max_tokens: int = 512, temperature: float = 0.7) -> str:
        return chat(prompt, system_prompt=system_prompt, max_tokens=max_tokens, temperature=temperature)

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.wav", mode: str = "PUSH_TO_TALK") -> Dict[str, Any]:
        return transcribe(audio_bytes, filename=filename, mode=mode)

    def is_configured(self) -> bool:
        return is_configured()

    def is_transcribe_configured(self) -> bool:
        return is_transcribe_configured()


def get_llm_service() -> LLMService:
    return LLMService()
