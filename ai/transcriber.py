"""
Speech-to-text transcription using Groq Whisper (free)
Fallback to OpenAI Whisper if Groq key not set.

Language accuracy:
  - When language="auto", Whisper first detects the language,
    then transcribes using that detected code — this prevents
    Bengali being written as Hindi, Punjabi as Urdu, etc.
  - verbose_json used for OpenAI to get no_speech_prob per segment.
  - Hallucination blocklist + minimum word count enforced.
"""

import os
import re
import tempfile
import wave
import numpy as np
from typing import Optional, Tuple
from utils.logger import log_info, log_error, log_debug, log_warning
from config.constants import SAMPLE_RATE

# ── Whisper language code → BCP-47 map (subset) ───────────────────────────
# Whisper returns short codes; we map them to full ISO 639-1 codes
_WHISPER_LANG_MAP = {
    "af": "af",
    "ar": "ar",
    "hy": "hy",
    "az": "az",
    "be": "be",
    "bs": "bs",
    "bg": "bg",
    "ca": "ca",
    "zh": "zh",
    "hr": "hr",
    "cs": "cs",
    "da": "da",
    "nl": "nl",
    "en": "en",
    "et": "et",
    "fi": "fi",
    "fr": "fr",
    "gl": "gl",
    "de": "de",
    "el": "el",
    "he": "he",
    "hi": "hi",
    "hu": "hu",
    "is": "is",
    "id": "id",
    "it": "it",
    "ja": "ja",
    "kn": "kn",
    "kk": "kk",
    "ko": "ko",
    "lv": "lv",
    "lt": "lt",
    "mk": "mk",
    "ms": "ms",
    "mr": "mr",
    "mi": "mi",
    "ne": "ne",
    "no": "no",
    "fa": "fa",
    "pl": "pl",
    "pt": "pt",
    "ro": "ro",
    "ru": "ru",
    "sr": "sr",
    "sk": "sk",
    "sl": "sl",
    "es": "es",
    "sw": "sw",
    "sv": "sv",
    "tl": "tl",
    "ta": "ta",
    "th": "th",
    "tr": "tr",
    "uk": "uk",
    "ur": "ur",
    "vi": "vi",
    "cy": "cy",
    # Indian languages Whisper supports
    "bn": "bn",  # Bengali  ← key fix
    "gu": "gu",  # Gujarati
    "pa": "pa",  # Punjabi
    "te": "te",  # Telugu
    "ml": "ml",  # Malayalam
    "si": "si",  # Sinhala
}

# ── Hallucination blocklist ────────────────────────────────────────────────
_HALLUCINATION_PATTERNS = [
    r"視聴ありがとう",
    r"ご視聴ありがとう",
    r"おやすみなさい",
    r"ありがとうございました",
    r"チャンネル登録",
    r"高評価",
    r"^thanks for watching",
    r"^thank you for watching",
    r"^please subscribe",
    r"^like and subscribe",
    r"^subscribe to",
    r"^\[music\]$",
    r"^\[applause\]$",
    r"^\[silence\]$",
    r"^\[blank_audio\]$",
    r"^\.\.\.$",
    r"^\.+$",
    r"^\s*$",
    r"^[^a-zA-Z\u0900-\uFFFF]{0,5}$",
]
_HALLUCINATION_RE = [re.compile(p, re.IGNORECASE) for p in _HALLUCINATION_PATTERNS]
_MIN_WORDS = 2


def _is_hallucination(text: str) -> bool:
    t = text.strip()
    if not t:
        return True
    if len(t.split()) < _MIN_WORDS:
        log_warning(f"Transcript too short: {repr(t)}")
        return True
    for pat in _HALLUCINATION_RE:
        if pat.search(t):
            log_warning(f"Hallucination blocked: {repr(t)}")
            return True
    return False


class Transcriber:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.openai_api_key = api_key
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.client = None
        self.backend = None
        self.model = model or None
        self._last_detected_lang = None
        self._init_client()

    def _init_client(self):
        if self.groq_api_key:
            try:
                from groq import Groq

                self.client = Groq(api_key=self.groq_api_key)
                self.backend = "groq"
                if not self.model:
                    self.model = "whisper-large-v3-turbo"
                log_info(f"Transcriber: Groq ({self.model})")
                return
            except Exception as e:
                log_error(f"Groq init failed: {e}")

        if self.openai_api_key:
            try:
                from openai import OpenAI

                self.client = OpenAI(api_key=self.openai_api_key)
                self.backend = "openai"
                if not self.model:
                    self.model = "whisper-1"
                log_info(f"Transcriber: OpenAI ({self.model})")
                return
            except Exception as e:
                log_error(f"OpenAI init failed: {e}")

        log_error("No transcription backend. Set GROQ_API_KEY or openai_api_key.")

    # ── public ────────────────────────────────────────────────────────────

    def transcribe(
        self, audio_data: np.ndarray, language: Optional[str] = None, settings: dict = None
    ) -> Optional[str]:
        """
        Transcribe audio.

        Auto mode performs a SINGLE verbose_json call that returns both the
        transcript and the detected language (previously this cost two API
        calls). Hindi results get one extra English pass to catch Hinglish.

        An explicit language code (e.g. "bn") uses one direct call.
        """
        if self.client is None:
            log_error("No transcription client")
            return None

        self._last_detected_lang = None  # reset for each call

        tmp_path = None
        try:
            tmp_path = self._save_wav(audio_data)

            if language and language != "auto":
                text = self._do_transcribe(tmp_path, language)
                if text:
                    self._last_detected_lang = language
            else:
                text, detected = self._transcribe_auto(tmp_path)
                self._last_detected_lang = detected
                if detected == "hi" and text:
                    hinglish = self._try_hinglish(tmp_path, text)
                    if hinglish:
                        text = hinglish

            if not text:
                return None

            if _is_hallucination(text):
                return None

            log_info(
                f"Transcription OK [{self._last_detected_lang or 'auto'}]: "
                f"{repr(text[:80])}"
            )
            return text

        except Exception as e:
            log_error(f"Transcription error: {e}", exc_info=True)
            return None
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    # ── language detection ────────────────────────────────────────────────

    _LANG_NAME_MAP = {
        "english": "en",
        "spanish": "es",
        "french": "fr",
        "german": "de",
        "italian": "it",
        "portuguese": "pt",
        "russian": "ru",
        "chinese": "zh",
        "japanese": "ja",
        "korean": "ko",
        "hindi": "hi",
        "bengali": "bn",
        "punjabi": "pa",
        "gujarati": "gu",
        "tamil": "ta",
        "telugu": "te",
        "malayalam": "ml",
        "marathi": "mr",
        "urdu": "ur",
        "arabic": "ar",
        "turkish": "tr",
        "dutch": "nl",
        "polish": "pl",
        "swedish": "sv",
        "norwegian": "no",
        "danish": "da",
        "finnish": "fi",
        "czech": "cs",
        "hungarian": "hu",
        "romanian": "ro",
        "ukrainian": "uk",
        "greek": "el",
        "hebrew": "he",
        "thai": "th",
        "vietnamese": "vi",
        "indonesian": "id",
        "malay": "ms",
        "tagalog": "tl",
    }

    def _normalize_lang(self, lang: Optional[str]) -> Optional[str]:
        if not lang:
            return None
        lang = lang.lower().strip()
        return _WHISPER_LANG_MAP.get(lang, self._LANG_NAME_MAP.get(lang, lang))

    def _transcribe_auto(self, wav_path: str) -> Tuple[Optional[str], Optional[str]]:
        """
        One verbose_json call returning (text, iso_language).
        Falls back to plain transcription if verbose_json is unavailable.
        """
        try:
            with open(wav_path, "rb") as f:
                result = self.client.audio.transcriptions.create(
                    model=self.model,
                    file=f,
                    response_format="verbose_json",
                )
            text = (getattr(result, "text", "") or "").strip()
            detected = self._normalize_lang(getattr(result, "language", None))

            # Discard if Whisper says it is not speech (OpenAI only)
            segments = getattr(result, "segments", []) or []
            if segments:
                avg_no_speech = sum(s.get("no_speech_prob", 0) for s in segments) / len(
                    segments
                )
                if avg_no_speech > 0.6:
                    log_warning(f"no_speech_prob={avg_no_speech:.2f} — discarding")
                    return None, detected

            return text, detected
        except Exception as e:
            log_warning(f"verbose_json failed ({e}); retrying plain json")
            text = self._do_transcribe(wav_path, None)
            return text, None

    def _try_hinglish(self, wav_path: str, hindi_text: str) -> Optional[str]:
        """
        Hindi audio may actually be Hinglish (Hindi spoken with English
        words). Re-transcribe once as English; keep it when the detector
        confirms a Hinglish mix, otherwise keep the Hindi transcript.
        """
        try:
            english_text = self._do_transcribe(wav_path, "en")
            if not english_text or len(english_text.split()) <= 2:
                return None
            from ai.language_detector import language_detector

            is_hinglish, confidence = language_detector.detect_hinglish(english_text)
            if is_hinglish and confidence >= 0.3:
                log_info(f"Hinglish kept (confidence {confidence:.2f})")
                return english_text
        except Exception as e:
            log_debug(f"Hinglish detection failed: {e}")
        return None

    def _detect_language(self, wav_path: str) -> Optional[str]:
        """Detect language only (kept for API compatibility / diagnostics)."""
        _, detected = self._transcribe_auto(wav_path)
        return detected

    # ── transcription ─────────────────────────────────────────────────────

    def _do_transcribe(self, wav_path: str, language: Optional[str]) -> Optional[str]:
        """Run the actual transcription with an explicit language code."""
        try:
            with open(wav_path, "rb") as f:
                if self.backend == "openai":
                    kwargs = dict(
                        model=self.model or "whisper-1",
                        file=f,
                        response_format="verbose_json",
                    )
                    if language:
                        kwargs["language"] = language
                    result = self.client.audio.transcriptions.create(**kwargs)

                    # Discard if Whisper itself says it's not speech
                    segments = getattr(result, "segments", []) or []
                    if segments:
                        avg_no_speech = sum(
                            s.get("no_speech_prob", 0) for s in segments
                        ) / len(segments)
                        if avg_no_speech > 0.6:
                            log_warning(
                                f"no_speech_prob={avg_no_speech:.2f} — discarding"
                            )
                            return None

                    return (result.text or "").strip()

                else:
                    # Groq
                    kwargs = dict(
                        model=self.model or "whisper-large-v3-turbo",
                        file=f,
                    )
                    if language:
                        kwargs["language"] = language
                    result = self.client.audio.transcriptions.create(**kwargs)
                    return (result.text or "").strip()

        except Exception as e:
            log_error(f"_do_transcribe error: {e}", exc_info=True)
            return None

    # ── wav helper ────────────────────────────────────────────────────────

    def _save_wav(self, audio_data: np.ndarray) -> str:
        audio_data = audio_data.flatten()
        if audio_data.dtype != np.int16:
            audio_data = np.clip(audio_data * 32767, -32767, 32767).astype(np.int16)
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        with wave.open(tmp.name, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_data.tobytes())
        return tmp.name
