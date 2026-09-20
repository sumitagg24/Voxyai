"""
Sound feedback for Voxylis — single soft beep on hotkey press/release.
"""

import threading
import time
import numpy as np
from utils.logger import log_error


def _play_soft_tone(freq: float, duration_ms: int, volume: float = 0.05):
    """Play a soft sine tone with smooth fade in/out to avoid harshness."""
    try:
        import sounddevice as sd

        sr = 22050
        samples = int(sr * duration_ms / 1000)
        t = np.linspace(0, duration_ms / 1000, samples, False)
        # Soft sine wave
        wave = np.sin(2 * np.pi * freq * t).astype(np.float32)
        # Smooth fade in and out (50% of duration each side)
        fade = samples // 2
        wave[:fade] *= np.linspace(0, 1, fade)
        wave[fade:] *= np.linspace(1, 0, samples - fade)
        wave *= volume
        sd.play(wave, sr, blocking=True)
    except Exception as e:
        log_error(f"Sound feedback error: {e}")


class SoundFeedback:
    """Plays a single soft audio cue for recording start/stop."""

    def __init__(self, enabled: bool = True, volume: float = 0.7):
        self.enabled = enabled
        self.volume = max(0.0, min(1.0, volume))
        self._lock = threading.Lock()
        self._last_event_time = 0.0
        self._cooldown = 0.5  # 500ms — guarantees only one beep per action

    def _play(self, freq: float, duration_ms: int):
        if not self.enabled:
            return
        now = time.time()
        with self._lock:
            if now - self._last_event_time < self._cooldown:
                return  # Swallow duplicate
            self._last_event_time = now

        threading.Thread(
            target=_play_soft_tone,
            args=(freq, duration_ms, 0.04),  # Very soft
            daemon=True,
        ).start()

    def on_recording_start(self):
        """Single soft high beep — recording started."""
        self._play(880, 80)  # A5, 80ms, soft

    def on_recording_stop(self):
        """Single soft low beep — recording stopped."""
        self._play(440, 80)  # A4, 80ms, soft

    def on_success(self):
        """Single soft chime — text injected."""
        self._play(660, 60)  # E5, 60ms, soft

    def on_error(self):
        """Single soft low tone — error."""
        self._play(220, 120)  # A3, 120ms, soft

    def on_command(self):
        """Single soft blip — voice command."""
        self._play(1100, 50)  # C#6, 50ms, soft
