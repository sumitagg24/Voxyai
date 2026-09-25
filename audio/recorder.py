"""
Audio recording engine for Voxylis
"""

import sounddevice as sd
import numpy as np
import threading
import time
from typing import Optional, Callable
from config.constants import (
    SAMPLE_RATE,
    CHUNK_SIZE,
    CHANNELS,
    AUDIO_FORMAT,
    MAX_RECORDING_DURATION,
)
from utils.logger import log_info, log_error, log_debug, log_warning
from audio.audio_utils import apply_noise_gate, normalize_audio, calculate_audio_level
from audio.noise_canceller import NoiseCanceller


class AudioRecorder:
    """Handles real-time audio recording from microphone"""

    def __init__(self, device_id: Optional[int] = None):
        """
        Initialize audio recorder

        Args:
            device_id: Audio device ID (None = default)
        """
        self.device_id = device_id
        self.sample_rate = SAMPLE_RATE
        self.chunk_size = CHUNK_SIZE
        self.channels = CHANNELS
        self.is_recording = False
        self.audio_buffer = []
        self.stream = None
        self.recording_thread = None
        self.start_time = None
        self.on_audio_chunk: Optional[Callable] = None
        # Called from a separate thread when silence auto-stop ends the recording
        self.on_auto_stop: Optional[Callable] = None
        # Silence auto-stop is opt-in (used by wake-word hands-free mode).
        # Hotkey recordings never auto-stop so the user stays in control.
        self.auto_stop_on_silence = False
        # Silence threshold in seconds before auto-stop triggers
        self.silence_timeout = 3.0
        # Serialises stop_recording so auto-stop and hotkey release can't race
        self._stop_lock = threading.Lock()
        self._noise_canceller = NoiseCanceller()

    def list_devices(self) -> list:
        """List available audio devices"""
        try:
            devices = sd.query_devices()
            return devices
        except Exception as e:
            log_error(f"Error listing audio devices: {e}")
            return []

    def start_recording(self) -> bool:
        """
        Start recording audio

        Returns:
            True if recording started successfully
        """
        try:
            # If already recording, stop it first
            if self.is_recording:
                log_info("Stopping previous recording before starting new one")
                self.stop_recording()

            self.audio_buffer = []
            self.is_recording = True
            self.start_time = time.time()

            # Reset noise canceller for fresh calibration
            self._noise_canceller.reset()

            # Start recording in separate thread
            self.recording_thread = threading.Thread(target=self._record_audio)
            self.recording_thread.daemon = True
            self.recording_thread.start()

            log_info(f"Audio recording started " f"(auto_stop_on_silence={self.auto_stop_on_silence})")
            return True

        except Exception as e:
            log_error(f"Error starting recording: {e}", exc_info=True)
            self.is_recording = False
            return False

    def stop_recording(self) -> Optional[np.ndarray]:
        """Thread-safe wrapper around stop logic (auto-stop vs hotkey race)."""
        with self._stop_lock:
            return self._stop_recording_impl()

    def _stop_recording_impl(self) -> Optional[np.ndarray]:
        """
        Stop recording and return audio data.
        Works both for a normal hotkey release and for a silence auto-stop,
        so audio recorded before the auto-stop is never discarded.
        """
        try:
            if not self.is_recording and len(self.audio_buffer) == 0:
                log_warning("No recording in progress")
                return None

            self.is_recording = False

            # Wait for recording thread to finish
            if self.recording_thread and self.recording_thread.is_alive():
                if threading.current_thread() is not self.recording_thread:
                    self.recording_thread.join(timeout=5)

            if len(self.audio_buffer) == 0:
                log_error("No audio data recorded")
                return None

            # Combine all chunks
            audio_data = np.concatenate(self.audio_buffer)
            self.audio_buffer = []

            # ── Active Noise Cancellation ─────────────────────────────────
            audio_data = self._noise_canceller.process(audio_data)
            log_info("ANC applied")

            # Apply processing
            audio_data = apply_noise_gate(audio_data)
            audio_data = normalize_audio(audio_data)

            duration = time.time() - self.start_time if self.start_time else 0.0
            log_info(f"Recording stopped. Duration: {duration:.2f}s, Samples: {len(audio_data)}")

            return audio_data

        except Exception as e:
            log_error(f"Error stopping recording: {e}", exc_info=True)
            return None

    def _record_audio(self):
        """Internal method to record audio in thread"""
        try:
            with sd.InputStream(
                device=self.device_id,
                samplerate=self.sample_rate,
                channels=self.channels,
                blocksize=self.chunk_size,
                dtype=AUDIO_FORMAT,
            ) as stream:
                self.stream = stream

                # Frames are chunk_size samples; convert seconds to frames
                frame_seconds = self.chunk_size / float(self.sample_rate)
                max_silent_frames = max(1, int(self.silence_timeout / frame_seconds))
                min_speech_frames = 3  # ~0.2 s of sound before silence counts again

                silent_frames = 0
                speech_frames = 0
                frame_count = 0

                while self.is_recording:
                    # Check duration limit
                    if time.time() - self.start_time > MAX_RECORDING_DURATION:
                        log_warning("Max recording duration reached")
                        self.is_recording = False
                        break

                    # Read audio chunk
                    audio_chunk, _ = stream.read(self.chunk_size)
                    frame_count += 1

                    # Calculate and report audio level
                    level = calculate_audio_level(audio_chunk)
                    if self.on_audio_chunk:
                        self.on_audio_chunk(level)

                    # Voice activity detection for silence auto-stop
                    audio_float = audio_chunk.flatten().astype(np.float32)
                    if audio_chunk.dtype == np.int16:
                        audio_float = audio_float / 32767.0
                    rms = float(np.sqrt(np.mean(audio_float**2)))

                    if rms < 0.008:
                        silent_frames += 1
                    else:
                        silent_frames = 0
                        speech_frames += 1

                    self.audio_buffer.append(audio_chunk)

                    elapsed = frame_count * frame_seconds
                    should_auto_stop = (
                        self.auto_stop_on_silence
                        and speech_frames >= min_speech_frames
                        and silent_frames > max_silent_frames
                    )
                    # Nothing spoken shortly after activation (e.g. wake word
                    # triggered but the user stayed quiet) — stop waiting.
                    no_speech_give_up = (
                        self.auto_stop_on_silence and speech_frames < min_speech_frames and elapsed > 5.0
                    )
                    if should_auto_stop or no_speech_give_up:
                        if no_speech_give_up:
                            log_info("Auto-stop: no speech detected after activation")
                        else:
                            log_info(f"Auto-stop: {silent_frames * frame_seconds:.1f}s of " f"silence after speech")
                        self.is_recording = False
                        break

                    log_debug(f"Chunk {frame_count}: level={level:.1f}% " f"rms={rms:.4f} silent={silent_frames}")

            # Notify listener (e.g. wake-word mode) that recording ended by itself.
            # Run in a fresh thread: the handler calls stop_recording(), which
            # must not join the current recording thread from inside itself.
            if self.auto_stop_on_silence and self.on_auto_stop and self.audio_buffer:
                threading.Thread(target=self.on_auto_stop, daemon=True).start()

        except Exception as e:
            log_error(f"Error in recording thread: {e}", exc_info=True)
            self.is_recording = False
            self.audio_buffer = []

    def get_recording_duration(self) -> float:
        """Get current recording duration in seconds"""
        if not self.is_recording or not self.start_time:
            return 0
        return time.time() - self.start_time

    def cancel_recording(self):
        """Cancel recording without saving"""
        self.is_recording = False
        self.audio_buffer = []
        log_info("Recording cancelled")
