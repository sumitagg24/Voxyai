"""
Main application orchestrator for Voxylis
"""

import os
import threading
import time
import sys
from pathlib import Path
from typing import Optional

# Add project root to path if not already there (for standalone web server)
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from audio.recorder import AudioRecorder
from audio.audio_utils import has_speech
from ai.transcriber import Transcriber
from ai.enhancer import TextEnhancer
from ai.language_detector import language_detector
from system.injector import TextInjector
from core.hotkey_listener import HotkeyListener
from core.event_manager import event_manager, Events
from core.voice_commands import VoiceCommandProcessor
from core.command_processor import CommandProcessor
from core.history_manager import HistoryManager
from core.sound_feedback import SoundFeedback
from core.stats_tracker import StatsTracker
from core.per_app_profiles import PerAppProfiles
from core.startup_manager import startup_manager
from utils.logger import log_info, log_error, log_warning, log_debug
from utils.helpers import load_json, save_json, ensure_directories

try:
    from core.wake_word import WakeWordDetector
except ImportError:
    WakeWordDetector = None

# Language label → ISO code for translation commands
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


class AppOrchestrator:
    def __init__(self, config_path: str = None):
        ensure_directories()
        if config_path is None:
            try:
                from utils.helpers import get_base_dir
                config_path = os.path.join(get_base_dir(), "config", "settings.json")
            except Exception:
                config_path = "config/settings.json"
        self.config_path = config_path
        self.config = self._load_config()

        self.recorder = AudioRecorder()
        self.transcriber = None
        self.enhancer = None
        self.injector = TextInjector()
        self.hotkey_listener = None
        self.wake_word_detector = None

        self.voice_commands = VoiceCommandProcessor(
            self.config.get("voice_commands", {})
        )
        self.command_processor = CommandProcessor()
        self.history = HistoryManager(self.config.get("max_history", 100))
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

        # Guard for active recording session across threads
        self._recording_active = False
        self._recording_session_lock = threading.Lock()

        # Last injected transcript — used for translation
        self.last_transcript: Optional[str] = None

        # Guard: prevent _process_audio running twice for one hotkey press
        self._processing_lock = threading.Lock()
        self._is_processing = False

        # Last beep time to prevent rapid beeps
        self._last_beep_time = 0.0

        self._initialize_ai_components()
        self._setup_hotkey_listener()
        if WakeWordDetector:
            self._setup_wake_word()
        log_info("AppOrchestrator ready")

    # ── config ────────────────────────────────────────────────────────────

    def _load_config(self) -> dict:
        cfg = load_json(self.config_path)
        if not cfg:
            log_warning("Using default config")
            cfg = self._default_config()
        return cfg

    def _default_config(self) -> dict:
        return {
            "hotkey": "win+shift",
            "toggle_mode": False,
            "mode_hotkeys": {"win+alt": "casual", "win+ctrl": "technical"},
            "language": "auto",
            "secondary_language": "auto",
            "enhancement_mode": "formal",
            "enable_ai_enhancement": False,
            "groq_api_key": "",
            "openai_api_key": "",
            "audio_device": None,
            "sample_rate": 16000,
            "auto_inject": True,
            "show_floating_widget": True,
            "theme": "dark",
            "startup_on_boot": False,
            "log_level": "INFO",
            "max_history": 100,
            "sound_feedback": True,
            "sound_volume": 0.7,
            "voice_commands": {},
            "custom_modes": {},
            "app_profiles": {},
        }

    # ── AI ────────────────────────────────────────────────────────────────

    def _initialize_ai_components(self):
        try:
            api_key = self.config.get("openai_api_key") or os.getenv("OPENAI_API_KEY")
            groq_key = self.config.get("groq_api_key") or os.getenv("GROQ_API_KEY")
            if groq_key:
                os.environ["GROQ_API_KEY"] = groq_key
            if api_key:
                os.environ["OPENAI_API_KEY"] = api_key

            if groq_key or api_key:
                self.transcriber = Transcriber(api_key)
                self.enhancer = TextEnhancer(api_key)
                self.enhancer.set_custom_modes(self.config.get("custom_modes", {}))
                log_info("AI components ready")
            else:
                log_warning("No API key — AI disabled")
        except Exception as e:
            log_error(f"AI init error: {e}")

    # ── hotkey setup ──────────────────────────────────────────────────────

    def _setup_hotkey_listener(self):
        try:
            hotkey = self.config.get("hotkey", "win+shift")
            toggle_mode = self.config.get("toggle_mode", False)
            self.hotkey_listener = HotkeyListener(hotkey, toggle_mode=toggle_mode)
            self.hotkey_listener.on_hotkey_pressed = self._on_hotkey_pressed
            self.hotkey_listener.on_hotkey_released = self._on_hotkey_released
            self.hotkey_listener.on_mode_hotkey = self._on_mode_hotkey

            mode_hotkeys = self.config.get("mode_hotkeys", {})
            if mode_hotkeys:
                self.hotkey_listener.set_mode_hotkeys(mode_hotkeys)
            log_info(f"Hotkey: {hotkey}  toggle={toggle_mode}")
        except Exception as e:
            log_error(f"Hotkey setup error: {e}")

    def _setup_wake_word(self):
        """Initialize optional wake-word detector (no-op if unavailable)."""
        try:
            if WakeWordDetector is None:
                log_info("Wake-word detector unavailable — skipping")
                return
            if not self.config.get("wake_word_enabled", False):
                log_info("Wake-word disabled in config — skipping")
                return
            self.wake_word_detector = WakeWordDetector(
                self.config.get("wake_word", "voxy")
            )
            log_info("Wake-word detector ready")
        except Exception as e:
            log_error(f"Wake-word setup error: {e}")
            self.wake_word_detector = None

    # ── lifecycle ─────────────────────────────────────────────────────────

    def start(self) -> bool:
        try:
            if self.is_running:
                return False
            if not self.hotkey_listener:
                log_error("No hotkey listener")
                return False
            if not self.hotkey_listener.start_listening():
                log_error("Failed to start hotkey listener")
                return False
            self.recorder.on_audio_chunk = lambda level: event_manager.emit(
                Events.AUDIO_LEVEL_CHANGED, level
            )
            self.is_running = True
            log_info("Application started")
            return True
        except Exception as e:
            log_error(f"Start error: {e}", exc_info=True)
            return False

    def stop(self) -> bool:
        try:
            if not self.is_running:
                return False
            if self.recorder.is_recording:
                self.recorder.stop_recording()
            if self.hotkey_listener:
                self.hotkey_listener.stop_listening()
            self.is_running = False
            log_info("Application stopped")
            return True
        except Exception as e:
            log_error(f"Stop error: {e}", exc_info=True)
            return False

    # ── hotkey callbacks ──────────────────────────────────────────────────

    def _beep_start(self):
        """Play start beep only once per press, even if called from multiple paths."""
        now = time.time()
        if now - self._last_beep_time > 0.3:  # 300 ms guard
            self._last_beep_time = now
            self.sound.on_recording_start()

    def _on_hotkey_pressed(self):
        if not self.transcriber:
            event_manager.emit(Events.ERROR_OCCURRED, "no_api_key")
            return
        profile_mode = self.profiles.get_mode_for_active_window()
        if profile_mode:
            self._mode_override = profile_mode
        self._beep_start()
        event_manager.emit(Events.RECORDING_STARTED)
        self.recorder.start_recording()

    def _on_hotkey_released(self):
        audio_data = self.recorder.stop_recording()
        self.sound.on_recording_stop()
        if audio_data is None:
            event_manager.emit(Events.RECORDING_FAILED)
            return
        event_manager.emit(Events.RECORDING_STOPPED)
        self._spawn_process(audio_data)

    def _on_mode_hotkey(self, mode: str, action: str):
        if action == "press":
            self._mode_override = mode
            if not self.transcriber:
                event_manager.emit(Events.ERROR_OCCURRED, "no_api_key")
                return
            self._beep_start()
            event_manager.emit(Events.RECORDING_STARTED)
            self.recorder.start_recording()
        elif action == "release":
            audio_data = self.recorder.stop_recording()
            self.sound.on_recording_stop()
            if audio_data is None:
                event_manager.emit(Events.RECORDING_FAILED)
                self._mode_override = None
                return
            event_manager.emit(Events.RECORDING_STOPPED)
            self._spawn_process(audio_data)

    # ── pipeline ──────────────────────────────────────────────────────────

    def _spawn_process(self, audio_data):
        """Spawn processing thread — only one at a time."""
        with self._processing_lock:
            if self._is_processing:
                log_warning("Already processing — skipping duplicate")
                return
            self._is_processing = True
        threading.Thread(
            target=self._process_audio, args=(audio_data,), daemon=True
        ).start()

    MIN_RECORDING_SECONDS = 1.0

    def _process_audio(self, audio_data):
        try:
            from config.constants import SAMPLE_RATE

            # ── Gate 1: minimum duration ──────────────────────────────────
            min_samples = int(self.MIN_RECORDING_SECONDS * SAMPLE_RATE)
            if len(audio_data.flatten()) < min_samples:
                log_info("Audio too short — skipping")
                self._mode_override = None
                return

            # ── Gate 2: silence check ─────────────────────────────────────
            if not has_speech(audio_data):
                log_info("No speech detected — skipping")
                self._mode_override = None
                return

            event_manager.emit(Events.TRANSCRIPTION_STARTED)

            lang = self.config.get("language", "auto")
            transcript = self.transcriber.transcribe(
                audio_data, language=None if lang == "auto" else lang
            )

            if not transcript:
                event_manager.emit(Events.TRANSCRIPTION_FAILED)
                self.sound.on_error()
                self._mode_override = None
                return

            # ── Detect language ───────────────────────────────────────────
            lang_code, script, confidence = language_detector.detect_from_text(
                transcript
            )
            whisper_lang = getattr(self.transcriber, "_last_detected_lang", None)
            if whisper_lang and whisper_lang != "auto":
                lang_code = whisper_lang
                script = "whisper_detected"
                confidence = 1.0
            log_debug(
                f"Detected language: {lang_code} ({script}), "
                f"confidence={confidence:.2f}"
            )

            self.current_language = lang_code
            self.current_language_name = language_detector.get_language_name(lang_code)
            self.current_script = script
            event_manager.emit(
                Events.LANGUAGE_DETECTED, self.current_language_name, lang_code
            )

            # ── Check for "translate it to <language>" command ────────────
            t_lower = transcript.lower().strip()
            translate_target = self._detect_translate_command(t_lower)
            if translate_target:
                self._handle_translation(translate_target)
                self._mode_override = None
                return

            # ── Store transcript for future translation ───────────────────
            self.last_transcript = transcript
            event_manager.emit(Events.TRANSCRIPTION_COMPLETED, transcript)
            event_manager.emit(Events.LIVE_TEXT_UPDATED, transcript)

            # ── Voice commands ────────────────────────────────────────────
            is_cmd, action = self.voice_commands.process(transcript)
            if is_cmd:
                self.sound.on_command()
                self.stats.record_command()
                event_manager.emit(Events.VOICE_COMMAND_EXECUTED, action)
                self._mode_override = None
                return

            # ── Rich commands (search, GitHub, email, Slack) ──────────────
            cmd_ok, cmd_msg = self.command_processor.process_command(transcript)
            if cmd_ok:
                self.sound.on_command()
                self.stats.record_command()
                event_manager.emit(Events.VOICE_COMMAND_EXECUTED, cmd_msg)
                self.last_transcript = None
                self._mode_override = None
                return

            # ── Enhancement ───────────────────────────────────────────────
            enhanced = transcript
            mode = self._mode_override or self.config.get("enhancement_mode", "formal")
            self._mode_override = None

            if self.config.get("enable_ai_enhancement") and self.enhancer:
                event_manager.emit(Events.ENHANCEMENT_STARTED)
                result = self.enhancer.enhance(transcript, mode)
                if result:
                    enhanced = result
                    event_manager.emit(Events.ENHANCEMENT_COMPLETED, enhanced)

            # ── Stats + history ───────────────────────────────────────────
            self.stats.record_transcription(enhanced, self.current_language_name)
            self.history.add(transcript, enhanced, mode, self.current_language_name)
            event_manager.emit(Events.HISTORY_UPDATED)
            event_manager.emit(Events.STATS_UPDATED, self.stats.get_today())

            # ── Inject once ───────────────────────────────────────────────
            if self.config.get("auto_inject"):
                event_manager.emit(Events.INJECTION_STARTED)
                if self.injector.inject_text(enhanced):
                    self.sound.on_success()
                    event_manager.emit(Events.INJECTION_COMPLETED, enhanced)
                else:
                    self.sound.on_error()
                    event_manager.emit(Events.INJECTION_FAILED)

        except Exception as e:
            log_error(f"Pipeline error: {e}", exc_info=True)
            self.sound.on_error()
            event_manager.emit(Events.ERROR_OCCURRED, str(e))
            self._mode_override = None
        finally:
            with self._processing_lock:
                self._is_processing = False

    # ── translation helpers ───────────────────────────────────────────────

    def _detect_translate_command(self, text_lower: str) -> Optional[str]:
        """
        If transcript is 'translate it to <language>' or
        'translate to <language>', return the ISO code, else None.
        """
        import re

        m = re.search(r"translate(?:\s+it)?\s+to\s+(\w+)", text_lower)
        if not m:
            return None
        lang_word = m.group(1).lower()
        return _LANG_NAMES.get(lang_word)

    def _handle_translation(self, target_lang: str):
        """Translate last_transcript to target_lang and inject."""
        if not self.enhancer:
            log_warning("No enhancer — cannot translate")
            return
        text_to_translate = self.last_transcript
        if not text_to_translate:
            log_warning("No previous transcript to translate")
            return

        log_info(f"Translating to {target_lang}: {repr(text_to_translate[:60])}")
        translated = self.enhancer.translate(text_to_translate, target_lang)
        if not translated:
            self.sound.on_error()
            return

        self.last_transcript = translated
        event_manager.emit(Events.TRANSCRIPTION_COMPLETED, translated)
        event_manager.emit(Events.LIVE_TEXT_UPDATED, translated)
        self.current_language = target_lang
        self.current_language_name = language_detector.get_language_name(target_lang)
        event_manager.emit(
            Events.LANGUAGE_DETECTED, self.current_language_name, target_lang
        )

        if self.config.get("auto_inject"):
            event_manager.emit(Events.INJECTION_STARTED)
            if self.injector.inject_text(translated):
                self.sound.on_success()
                event_manager.emit(Events.INJECTION_COMPLETED, translated)
            else:
                self.sound.on_error()
                event_manager.emit(Events.INJECTION_FAILED)

    # ── config updates ────────────────────────────────────────────────────

    def update_config(self, key: str, value) -> bool:
        try:
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
                if value:
                    startup_manager.enable_auto_startup()
                else:
                    startup_manager.disable_auto_startup()
            if key in ("sound_feedback", "sound_volume"):
                self.sound.enabled = self.config.get("sound_feedback", True)
                self.sound.volume = self.config.get("sound_volume", 0.7)
            save_json(self.config_path, self.config)
            event_manager.emit(Events.SETTINGS_CHANGED, key, value)
            log_info(f"Config: {key} = {value}")
            return True
        except Exception as e:
            log_error(f"Config update error: {e}", exc_info=True)
            return False

    def get_config(self, key=None):
        return self.config.get(key) if key else self.config

    def get_status(self) -> dict:
        return {
            "is_running": self.is_running,
            "is_recording": self.recorder.is_recording,
            "last_transcript": self.last_transcript,
            "transcriber_ready": self.transcriber is not None,
            "enhancer_ready": self.enhancer is not None,
            "history_count": len(self.history),
            "today_stats": self.stats.get_today(),
        }
