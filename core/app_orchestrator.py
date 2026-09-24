"""
Main application orchestrator for Voxylis.

Pipeline (unchanged in shape, hardened in behaviour)::

    Hotkey -> Recorder -> Speech detection -> STT -> Language detection
           -> Voice commands -> Rich commands -> Enhancement -> Injection
           -> History / Stats

Hardening added here:
  * credentials come from the OS-backed vault, never plaintext settings.json;
  * transcription/enhancement failures are classified into user-facing errors;
  * every failure path clears state, so the UI never sticks on "Processing";
  * injection success is reported from the injector's real result;
  * recordings record their duration and target app for history/diagnostics.
"""

import os
import threading
import time
from pathlib import Path
from typing import Callable, Optional

# Add project root to path if not already there (for standalone web server)
project_root = Path(__file__).parent.parent
if str(project_root) not in os.sys.path:
    os.sys.path.insert(0, str(project_root))

from ai.enhancer import TextEnhancer
from ai.language_detector import language_detector
from ai.transcriber import Transcriber
from audio.audio_utils import has_speech
from audio.recorder import AudioRecorder
from config.constants import HOTKEY_DEFAULT, MODE_HOTKEY_DEFAULTS
from core.command_processor import CommandProcessor
from core.errors import VoxylisError, classify_exception, friendly_error
from core.event_manager import Events, event_manager
from core.history_manager import HistoryManager
from core.hotkey_listener import (
    HotkeyListener,
    find_conflicts,
    normalize_hotkey,
    validate_hotkey,
)
from core.per_app_profiles import PerAppProfiles, get_active_window_info
from core.sound_feedback import SoundFeedback
from core.stats_tracker import StatsTracker
from core.voice_commands import VoiceCommandProcessor
from system.injector import TextInjector
from utils import credentials, paths
from utils.helpers import ensure_directories, get_base_dir, load_json, save_json
from utils import observability
from utils.logger import log_debug, log_error, log_info, log_warning

try:
    from core.wake_word import WakeWordDetector
except ImportError:
    WakeWordDetector = None

# Language label -> ISO code for translation commands
_LANG_NAMES = {
    "english": "en",
    "hindi": "hi",
    "spanish": "es",
    "french": "fr",
    "german": "de",
    "italian": "it",
    "portuguese": "pt",
    "russian": "ru",
    "arabic": "ar",
    "urdu": "ur",
    "bengali": "bn",
    "punjabi": "pa",
    "gujarati": "gu",
    "tamil": "ta",
    "telugu": "te",
    "malayalam": "ml",
    "marathi": "mr",
    "japanese": "ja",
    "chinese": "zh",
    "korean": "ko",
    "turkish": "tr",
    "dutch": "nl",
    "polish": "pl",
    "vietnamese": "vi",
    "thai": "th",
    "indonesian": "id",
    "malay": "ms",
    "swedish": "sv",
    "norwegian": "no",
    "danish": "da",
    "finnish": "fi",
}

#: Provider retry policy (network/provider hiccups only, never bad keys).
MAX_ATTEMPTS = 3
RETRY_BASE_DELAY = 0.6


class AppOrchestrator:
    MIN_RECORDING_SECONDS = 1.0

    def __init__(self, config_path: Optional[str] = None):
        ensure_directories()
        self.config_path = config_path or str(paths.settings_path())
        self.config, self.migrated_secrets = self._load_config()
        # Crash reporting is opt-in (Settings → Privacy). Starting it here means
        # every failure below — recording, provider, injection, updater — can be
        # reported through one place instead of a second logging path.
        try:
            observability.init_observability(self.config)
        except Exception as exc:  # pragma: no cover - never block startup
            log_warning(f"Crash reporting unavailable: {type(exc).__name__}")

        self.recorder = AudioRecorder()
        self.transcriber: Optional[Transcriber] = None
        self.enhancer: Optional[TextEnhancer] = None
        self.injector = TextInjector()
        self.hotkey_listener: Optional[HotkeyListener] = None
        self.wake_word_detector = None
        self.api_keys: dict = {}

        self.voice_commands = VoiceCommandProcessor(self.config.get("voice_commands", {}))
        self.command_processor = CommandProcessor()
        self.history = HistoryManager(
            max_entries=int(self.config.get("max_history", 500)),
            enabled=bool(self.config.get("history_enabled", True)),
            retention_days=int(self.config.get("history_retention_days", 0)),
        )
        self.sound = SoundFeedback(
            enabled=self.config.get("sound_feedback", True),
            volume=self.config.get("sound_volume", 0.7),
        )
        self.stats = StatsTracker()
        self.profiles = PerAppProfiles(self.config.get("app_profiles", {}))

        # ── State ──────────────────────────────────────────────────────────
        self.current_language = "en"
        self.current_language_name = "English"
        self.current_script = "latin"
        self.is_running = False
        self._mode_override: Optional[str] = None
        self.last_transcript: Optional[str] = None
        self.last_error: Optional[VoxylisError] = None

        # Guards
        self._recording_active = False
        self._recording_session_lock = threading.Lock()
        self._processing_lock = threading.Lock()
        self._is_processing = False
        self._processing_stage = "idle"
        self._recording_started_at = 0.0
        self._recording_context = ""
        self._cancel_processing = threading.Event()
        self._last_beep_time = 0.0

        self._initialize_ai_components()
        self._setup_hotkey_listener()
        if WakeWordDetector:
            self._setup_wake_word()
        log_info("AppOrchestrator ready")

    # ── config ────────────────────────────────────────────────────────────

    def _load_config(self) -> tuple:
        """Load settings and move any plaintext credentials into the vault."""
        cfg = load_json(self.config_path)
        if not cfg:
            log_warning("Using default config")
            cfg = self._default_config()
        cleaned, migrated = credentials.migrate_config_secrets(cfg)
        if migrated:
            save_json(self.config_path, cleaned)
        return cleaned, migrated

    def _default_config(self) -> dict:
        return {
            "hotkey": HOTKEY_DEFAULT,
            "toggle_mode": False,
            "mode_hotkeys": dict(MODE_HOTKEY_DEFAULTS),
            "language": "auto",
            "secondary_language": "auto",
            "enhancement_mode": "formal",
            "enable_ai_enhancement": False,
            "audio_device": None,
            "sample_rate": 16000,
            "auto_inject": True,
            "show_floating_widget": True,
            "theme": "dark",
            "startup_on_boot": False,
            "log_level": "INFO",
            "max_history": 500,
            "history_enabled": True,
            "history_retention_days": 0,
            "sound_feedback": True,
            "sound_volume": 0.7,
            "voice_commands": {},
            "custom_modes": {},
            "app_profiles": {},
            # Off unless the user turns it on in Settings → Privacy. No install
            # ping, no analytics: a failure report is the only thing we ever send.
            "share_crash_reports": False,
        }

    # ── AI ────────────────────────────────────────────────────────────────

    def _initialize_ai_components(self) -> None:
        """Build provider clients from the credential vault (env as fallback)."""
        try:
            self.api_keys = credentials.load_api_keys(self.config)
            credentials.apply_to_environment(self.api_keys)
            groq_key = self.api_keys.get("groq_api_key")
            openai_key = self.api_keys.get("openai_api_key")

            if groq_key or openai_key:
                self.transcriber = Transcriber(openai_key)
                self.enhancer = TextEnhancer(openai_key)
                self.enhancer.set_custom_modes(self.config.get("custom_modes", {}))
                log_info(
                    "AI components ready (vault backend: %s; groq=%s openai=%s)"
                    % (
                        credentials.credential_store.backend_name,
                        bool(groq_key),
                        bool(openai_key),
                    )
                )
            else:
                self.transcriber = None
                self.enhancer = None
                log_warning("No API key configured — transcription disabled until one is added")
        except Exception as exc:
            log_error(f"AI init error: {exc}")
            self.transcriber = None
            self.enhancer = None

    def provider_status(self) -> dict:
        """Redacted provider summary for the settings UI and diagnostics."""
        keys = credentials.load_api_keys(self.config)
        return {
            "groq": {"configured": bool(keys.get("groq_api_key"))},
            "openai": {"configured": bool(keys.get("openai_api_key"))},
            "openrouter": {"configured": bool(keys.get("openrouter_api_key"))},
            "backend": credentials.credential_store.backend_name,
            "secure_storage": credentials.credential_store.is_secure,
            "transcriber_ready": self.transcriber is not None,
            "enhancer_ready": self.enhancer is not None,
        }

    # ── hotkey setup ──────────────────────────────────────────────────────

    def _setup_hotkey_listener(self) -> None:
        try:
            hotkey = self.config.get("hotkey", HOTKEY_DEFAULT)
            toggle_mode = self.config.get("toggle_mode", False)
            self.hotkey_listener = HotkeyListener(hotkey, toggle_mode=toggle_mode)
            self.hotkey_listener.on_hotkey_pressed = self._on_hotkey_pressed
            self.hotkey_listener.on_hotkey_released = self._on_hotkey_released
            self.hotkey_listener.on_mode_hotkey = self._on_mode_hotkey
            self.hotkey_listener.on_listener_lost = self._on_listener_lost

            mode_hotkeys = self.config.get("mode_hotkeys", {})
            if mode_hotkeys:
                self.hotkey_listener.set_mode_hotkeys(mode_hotkeys)
            self.hotkey_listener.set_enabled(not self.config.get("global_shortcuts_disabled", False))
            log_info(f"Hotkey: {hotkey}  toggle={toggle_mode}")
        except Exception as exc:
            log_error(f"Hotkey setup error: {exc}")
            self._emit_error(friendly_error("hotkey_listener_failed", detail=str(exc)))

    def _setup_wake_word(self) -> None:
        """Initialize the optional wake-word detector (no-op if unavailable)."""
        try:
            if WakeWordDetector is None:
                log_info("Wake-word detector unavailable — skipping")
                return
            if not self.config.get("wake_word_enabled", False):
                log_info("Wake-word disabled in config — skipping")
                return
            self.wake_word_detector = WakeWordDetector(self.config.get("wake_word", "voxy"))
            log_info("Wake-word detector ready")
        except Exception as exc:
            log_error(f"Wake-word setup error: {exc}")
            self.wake_word_detector = None

    # ── lifecycle ─────────────────────────────────────────────────────────

    def start(self) -> bool:
        try:
            if self.is_running:
                return False
            if not self.hotkey_listener:
                self._emit_error(friendly_error("hotkey_listener_failed", detail="listener not constructed"))
                return False
            started = self.hotkey_listener.start_listening()
            if not started and not self.config.get("global_shortcuts_disabled", False):
                self._emit_error(
                    friendly_error("hotkey_listener_failed", detail="start_listening() returned False")
                )
                # Not fatal: the tray menu and main window still work.
            self.recorder.on_audio_chunk = lambda level: event_manager.emit(Events.AUDIO_LEVEL_CHANGED, level)
            self.is_running = True
            log_info("Application started")
            return True
        except Exception as exc:
            log_error(f"Start error: {exc}", exc_info=True)
            return False

    def stop(self) -> bool:
        try:
            if self.recorder.is_recording:
                self.recorder.stop_recording()
            if self.hotkey_listener:
                self.hotkey_listener.stop_listening()
            self._is_processing = False
            self._processing_stage = "idle"
            self.is_running = False
            log_info("Application stopped")
            return True
        except Exception as exc:
            log_error(f"Stop error: {exc}", exc_info=True)
            return False

    # ── errors ────────────────────────────────────────────────────────────

    def _emit_error(self, error: VoxylisError, category: str = "pipeline") -> None:
        self.last_error = error
        log_error(f"[{error.code}] {error.summary} ({error.detail or 'no detail'})")
        # One funnel for user-facing failures: classified code, no transcript,
        # no key, no clipboard. A no-op unless the user opted in.
        observability.capture_error(error, category=category)
        event_manager.emit(Events.ERROR_OCCURRED, error)
        self._set_stage("idle")

    def _set_stage(self, stage: str) -> None:
        self._processing_stage = stage
        event_manager.emit(Events.PIPELINE_STAGE, stage)

    # ── hotkey callbacks ──────────────────────────────────────────────────

    def _beep_start(self) -> None:
        """Play the start beep once per press, even across multiple paths."""
        now = time.time()
        if now - self._last_beep_time > 0.3:
            self._last_beep_time = now
            self.sound.on_recording_start()

    def _begin_recording(self, mode_override: Optional[str] = None) -> bool:
        """Shared entry point for hotkey and tray-initiated recordings."""
        with self._recording_session_lock:
            if self._recording_active:
                log_warning("Recording already in progress — ignoring duplicate start")
                return False
            if not self.transcriber:
                self._emit_error(friendly_error("no_api_key"))
                return False
            self._recording_active = True
            self._mode_override = mode_override
            self._recording_context = ""
            try:
                self._recording_context = get_active_window_info().get("exe", "") or ""
            except Exception:
                self._recording_context = ""

        self._beep_start()
        self._recording_started_at = time.time()
        event_manager.emit(Events.RECORDING_STARTED)
        self._set_stage("recording")
        if not self.recorder.start_recording():
            self.sound.on_error()
            with self._recording_session_lock:
                self._recording_active = False
            self._emit_error(friendly_error("mic_unavailable"))
            event_manager.emit(Events.RECORDING_FAILED)
            return False
        return True

    def _end_recording(self, cancel: bool = False) -> None:
        with self._recording_session_lock:
            if not self._recording_active:
                return
            self._recording_active = False

        duration_ms = int((time.time() - self._recording_started_at) * 1000) if self._recording_started_at else 0
        audio_data = self.recorder.stop_recording()
        self.sound.on_recording_stop()

        if cancel:
            self._mode_override = None
            event_manager.emit(Events.RECORDING_CANCELLED)
            self._set_stage("idle")
            return

        if audio_data is None:
            event_manager.emit(Events.RECORDING_FAILED)
            self._emit_error(friendly_error("recording_failed"))
            return

        event_manager.emit(Events.RECORDING_STOPPED)
        self._spawn_process(audio_data, duration_ms)

    def _on_hotkey_pressed(self) -> None:
        profile_mode = self.profiles.get_mode_for_active_window()
        self._begin_recording(profile_mode)

    def _on_hotkey_released(self) -> None:
        self._end_recording()

    def _on_mode_hotkey(self, mode: str, action: str) -> None:
        if action == "press":
            self._begin_recording(mode)
        elif action == "release":
            self._end_recording()

    def _on_listener_lost(self) -> None:
        """Called by the listener when its hook dies; try one restart, then warn."""
        log_warning("Hotkey listener reported loss")
        if self.config.get("global_shortcuts_disabled", False):
            return
        if self.hotkey_listener and self.hotkey_listener.recover():
            log_info("Hotkey listener recovered")
            return
        self._emit_error(friendly_error("hotkey_listener_failed"))

    # ── public actions (tray / main window) ───────────────────────────────

    def start_recording(self, mode: Optional[str] = None) -> bool:
        return self._begin_recording(mode)

    def stop_recording(self) -> None:
        self._end_recording()

    def cancel_recording(self) -> None:
        """Abort any in-flight recording or processing and return to a known state."""
        self._cancel_processing.set()
        if self._recording_active:
            self._end_recording(cancel=True)
        self._is_processing = False
        self._set_stage("idle")
        log_info("Cancelled current voice operation")

    def toggle_recording(self) -> None:
        if self._recording_active:
            self._end_recording()
        else:
            self._begin_recording()

    # ── pipeline ──────────────────────────────────────────────────────────

    def _spawn_process(self, audio_data, duration_ms: int = 0) -> None:
        """Spawn the processing thread — only one utterance at a time."""
        with self._processing_lock:
            if self._is_processing:
                log_warning("Already processing — skipping duplicate")
                return
            self._is_processing = True
        self._cancel_processing.clear()
        threading.Thread(
            target=self._process_audio, args=(audio_data, duration_ms), daemon=True
        ).start()

    def _retry(self, fn: Callable, attempts: int = MAX_ATTEMPTS):
        """Retry a provider call with exponential backoff.

        Returns ``(value, error)`` where exactly one is set.
        """
        last = None
        for attempt in range(1, attempts + 1):
            if self._cancel_processing.is_set():
                return None, friendly_error("pipeline_error", cause="cancelled")
            try:
                return fn(), None
            except Exception as exc:  # noqa: BLE001 - classify below
                error = classify_exception(exc)
                last = error
                if not error.retryable or attempt == attempts:
                    return None, error
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                log_warning(f"[{error.code}] attempt {attempt}/{attempts} failed; retrying in {delay:.1f}s")
                time.sleep(delay)
        return None, last

    def _process_audio(self, audio_data, duration_ms: int = 0) -> None:
        try:
            from config.constants import SAMPLE_RATE

            # ── Gate 1: minimum duration ──────────────────────────────────
            min_samples = int(self.MIN_RECORDING_SECONDS * SAMPLE_RATE)
            if len(audio_data.flatten()) < min_samples:
                log_info("Audio too short — skipping")
                self._emit_error(friendly_error("no_speech"))
                return

            # ── Gate 2: silence check ─────────────────────────────────────
            if not has_speech(audio_data):
                log_info("No speech detected — skipping")
                self._emit_error(friendly_error("no_speech"))
                return

            self._set_stage("transcribing")
            event_manager.emit(Events.TRANSCRIPTION_STARTED)

            lang = self.config.get("language", "auto")
            provider = getattr(self.transcriber, "backend", "") or "the AI provider"

            def _transcribe():
                text = self.transcriber.transcribe(
                    audio_data, language=None if lang == "auto" else lang, settings=self.config
                )
                # The transcriber returns None for both "provider failed" and
                # "silence/hallucination". Only surface the former as an error so
                # we can retry it and tell the user what actually went wrong.
                provider_error = getattr(self.transcriber, "last_error", None)
                if text is None and provider_error is not None:
                    raise provider_error
                return text

            transcript, error = self._retry(_transcribe)
            if error is not None:
                self.sound.on_error()
                event_manager.emit(Events.TRANSCRIPTION_FAILED)
                self._emit_error(error)
                return
            if not transcript:
                self.sound.on_error()
                event_manager.emit(Events.TRANSCRIPTION_FAILED)
                self._emit_error(friendly_error("transcription_failed", provider=provider))
                return

            # ── Detect language ───────────────────────────────────────────
            lang_code, script, confidence = language_detector.detect_from_text(transcript)
            whisper_lang = getattr(self.transcriber, "_last_detected_lang", None)
            if whisper_lang and whisper_lang != "auto":
                lang_code = whisper_lang
                script = "whisper_detected"
                confidence = 1.0
            log_debug(f"Detected language: {lang_code} ({script}), confidence={confidence:.2f}")

            self.current_language = lang_code
            self.current_language_name = language_detector.get_language_name(lang_code)
            self.current_script = script
            event_manager.emit(Events.LANGUAGE_DETECTED, self.current_language_name, lang_code)

            # ── "translate it to <language>" ──────────────────────────────
            translate_target = self._detect_translate_command(transcript.lower().strip())
            if translate_target:
                self._handle_translation(translate_target, duration_ms)
                return

            self.last_transcript = transcript
            event_manager.emit(Events.TRANSCRIPTION_COMPLETED, transcript)
            event_manager.emit(Events.LIVE_TEXT_UPDATED, transcript)

            # ── Voice commands ────────────────────────────────────────────
            is_cmd, action = self.voice_commands.process(transcript)
            if is_cmd:
                self.sound.on_command()
                self.stats.record_command()
                event_manager.emit(Events.VOICE_COMMAND_EXECUTED, action)
                self._set_stage("idle")
                return

            # ── Rich commands ─────────────────────────────────────────────
            cmd_ok, cmd_msg = self.command_processor.process_command(transcript)
            if cmd_ok:
                self.sound.on_command()
                self.stats.record_command()
                event_manager.emit(Events.VOICE_COMMAND_EXECUTED, cmd_msg)
                self.last_transcript = None
                self._set_stage("idle")
                return

            # ── Enhancement ───────────────────────────────────────────────
            enhanced = transcript
            mode = self._mode_override or self.config.get("enhancement_mode", "formal")

            if self.config.get("enable_ai_enhancement") and self.enhancer:
                self._set_stage("enhancing")
                event_manager.emit(Events.ENHANCEMENT_STARTED)

                def _enhance():
                    return self.enhancer.enhance(transcript, mode, settings=self.config)

                result, enh_error = self._retry(_enhance, attempts=2)
                if enh_error is not None:
                    log_warning(f"Enhancement failed, using raw transcript: {enh_error.code}")
                    event_manager.emit(Events.ENHANCEMENT_FAILED)
                    event_manager.emit(Events.ERROR_OCCURRED, enh_error)
                elif result:
                    enhanced = result
                    event_manager.emit(Events.ENHANCEMENT_COMPLETED, enhanced)
            self._mode_override = None

            # ── Stats + history ───────────────────────────────────────────
            self.stats.record_transcription(enhanced, self.current_language_name)
            entry = self.history.add(
                transcript,
                enhanced,
                mode,
                self.current_language_name,
                app_context=self._recording_context,
                duration_ms=duration_ms,
            )
            event_manager.emit(Events.HISTORY_UPDATED)
            event_manager.emit(Events.STATS_UPDATED, self.stats.get_today())

            # ── Inject once (only after a real, reported delivery) ────────
            if self.config.get("auto_inject"):
                self._set_stage("injecting")
                event_manager.emit(Events.INJECTION_STARTED)
                outcome = self.injector.inject(enhanced)
                if outcome.success:
                    if entry:
                        self.history.store.mark_injected(entry["id"], True)
                    self.sound.on_success()
                    event_manager.emit(Events.INJECTION_COMPLETED, enhanced)
                else:
                    self.sound.on_error()
                    event_manager.emit(Events.INJECTION_FAILED)
                    self._emit_error(
                        friendly_error(
                            "injection_failed",
                            cause=outcome.user_message(),
                            detail=f"{outcome.error.value}: {outcome.detail}",
                        )
                    )
            self._set_stage("idle")

        except Exception as exc:
            log_error(f"Pipeline error: {exc}", exc_info=True)
            self.sound.on_error()
            classified = classify_exception(exc)
            observability.capture_exception(exc, category="pipeline", error_code=classified.code)
            self._emit_error(classified)
        finally:
            self._mode_override = None
            with self._processing_lock:
                self._is_processing = False
            if self._processing_stage != "idle":
                self._set_stage("idle")

    # ── translation helpers ───────────────────────────────────────────────

    def _detect_translate_command(self, text_lower: str) -> Optional[str]:
        """Return the ISO code for 'translate it to <language>', else None."""
        import re

        match = re.search(r"translate(?:\s+it)?\s+to\s+(\w+)", text_lower)
        if not match:
            return None
        return _LANG_NAMES.get(match.group(1).lower())

    def _handle_translation(self, target_lang: str, duration_ms: int = 0) -> None:
        """Translate the previous transcript and inject the result."""
        if not self.enhancer:
            self._emit_error(friendly_error("provider_unavailable"))
            return
        text_to_translate = self.last_transcript
        if not text_to_translate:
            log_warning("No previous transcript to translate")
            self._emit_error(friendly_error("transcription_failed", provider="translation"))
            return

        log_info(f"Translating to {target_lang} ({len(text_to_translate)} chars)")
        translated, error = self._retry(lambda: self.enhancer.translate(text_to_translate, target_lang), attempts=2)
        if error is not None or not translated:
            self.sound.on_error()
            self._emit_error(error or friendly_error("enhancement_failed"))
            return

        self.last_transcript = translated
        event_manager.emit(Events.TRANSCRIPTION_COMPLETED, translated)
        event_manager.emit(Events.LIVE_TEXT_UPDATED, translated)
        self.current_language = target_lang
        self.current_language_name = language_detector.get_language_name(target_lang)
        event_manager.emit(Events.LANGUAGE_DETECTED, self.current_language_name, target_lang)

        self.history.add(
            text_to_translate,
            translated,
            "translate:" + target_lang,
            self.current_language_name,
            app_context=self._recording_context,
            duration_ms=duration_ms,
        )

        if self.config.get("auto_inject"):
            outcome = self.injector.inject(translated)
            if outcome.success:
                self.sound.on_success()
                event_manager.emit(Events.INJECTION_COMPLETED, translated)
            else:
                self.sound.on_error()
                event_manager.emit(Events.INJECTION_FAILED)
                self._emit_error(friendly_error("injection_failed", cause=outcome.user_message()))
        self._set_stage("idle")

    # ── config updates ────────────────────────────────────────────────────

    def update_config(self, key: str, value) -> bool:
        try:
            if key in credentials.SECRET_CONFIG_KEYS:
                stored = credentials.credential_store.set(key, value if isinstance(value, str) and value else None)
                if not stored:
                    return False
                self._initialize_ai_components()
                event_manager.emit(Events.SETTINGS_CHANGED, key, "configured" if value else "")
                return True

            # A shortcut that Windows reserves (or that duplicates another
            # binding) must be refused *before* it is persisted. Writing it to
            # settings anyway would tell the user it worked and then silently
            # fail to register on the next start.
            if key == "hotkey":
                ok, canonical, error = validate_hotkey(value)
                if not ok:
                    log_warning(f"Rejected hotkey '{value}': {error}")
                    return False
                value = canonical
            if key == "mode_hotkeys":
                mapping = {
                    str(k).strip().lower(): str(v)
                    for k, v in (value or {}).items()
                    if str(k).strip()
                }
                # find_conflicts reports reserved combinations and duplicates
                # inside the mapping; the main shortcut is checked separately
                # because it is not part of this dict.
                problems = find_conflicts(mapping)
                main = normalize_hotkey(self.config.get("hotkey") or "")
                for shortcut in mapping:
                    if main and normalize_hotkey(shortcut) == main:
                        problems.append(f"{shortcut} is already the main shortcut")
                if problems:
                    log_warning("Rejected mode hotkeys: " + "; ".join(problems))
                    return False
                value = mapping

            self.config[key] = value
            if key == "hotkey" and self.hotkey_listener:
                self.hotkey_listener.set_hotkey(value)
            if key == "toggle_mode" and self.hotkey_listener:
                self.hotkey_listener.set_toggle_mode(value)
            if key == "mode_hotkeys" and self.hotkey_listener:
                self.hotkey_listener.set_mode_hotkeys(value)
            if key in ("openai_api_key", "groq_api_key"):
                self._initialize_ai_components()
            if key == "custom_modes" and self.enhancer:
                self.enhancer.set_custom_modes(value)
            if key == "voice_commands":
                self.voice_commands.update_custom(value)
            if key == "app_profiles":
                self.profiles.update(value)
            if key == "startup_on_boot":
                from core.startup_manager import startup_manager

                if value:
                    startup_manager.enable_auto_startup()
                else:
                    startup_manager.disable_auto_startup()
            if key in ("sound_feedback", "sound_volume"):
                self.sound.enabled = self.config.get("sound_feedback", True)
                self.sound.volume = self.config.get("sound_volume", 0.7)
            if key in ("history_enabled", "history_retention_days", "max_history"):
                self.history.configure(
                    max_entries=int(self.config.get("max_history", 500)),
                    retention_days=int(self.config.get("history_retention_days", 0)),
                    enabled=bool(self.config.get("history_enabled", True)),
                )
            if key == "global_shortcuts_disabled" and self.hotkey_listener:
                self.hotkey_listener.set_enabled(not value)

            save_json(self.config_path, self.config)
            event_manager.emit(Events.SETTINGS_CHANGED, key, value)
            log_info(f"Config: {key} = {value}")
            return True
        except Exception as exc:
            log_error(f"Config update error: {exc}", exc_info=True)
            return False

    def get_config(self, key=None, default=None):
        """Return one config value (falling back to ``default``) or all of it.

        The ``default`` argument is not optional sugar: the whole UI reads
        settings as ``get_config("theme", "dark")``. Without it every such call
        raised ``TypeError`` and the app died during startup, which the source
        test suite never caught because it stubs the orchestrator.
        """
        if key is None:
            return self.config
        return self.config.get(key, default)

    def get_status(self) -> dict:
        return {
            "is_running": self.is_running,
            "is_recording": self.recorder.is_recording,
            "is_processing": self._is_processing,
            "stage": self._processing_stage,
            "last_transcript": self.last_transcript,
            "transcriber_ready": self.transcriber is not None,
            "enhancer_ready": self.enhancer is not None,
            "history_count": len(self.history),
            "today_stats": self.stats.get_today(),
            "last_error": self.last_error.code if self.last_error else None,
        }


def get_base_dir_compat() -> str:
    """Kept for external callers that import this module for the data root."""
    return get_base_dir()
