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

            log_info("Audio recording started")
            return True

        except Exception as e:
            log_error(f"Error starting recording: {e}", exc_info=True)
            self.is_recording = False
            return False

    def stop_recording(self) -> Optional[np.ndarray]:
        """
        Stop recording and return audio data
        
        Returns:
            Audio data as numpy array or None if error
        """
        try:
            if not self.is_recording:
                log_warning("No recording in progress")
                return None

            self.is_recording = False

            # Wait for recording thread to finish
            if self.recording_thread:
                self.recording_thread.join(timeout=5)

            if len(self.audio_buffer) == 0:
                log_error("No audio data recorded")
                return None

            # Combine all chunks
            audio_data = np.concatenate(self.audio_buffer)

            # ── Active Noise Cancellation ─────────────────────────────────
            audio_data = self._noise_canceller.process(audio_data)
            log_info("ANC applied")

            # Apply processing
            audio_data = apply_noise_gate(audio_data)
            audio_data = normalize_audio(audio_data)

            duration = time.time() - self.start_time
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

                while self.is_recording:
                    # Check duration limit
                    if time.time() - self.start_time > MAX_RECORDING_DURATION:
                        log_warning("Max recording duration reached")
                        self.is_recording = False
                        break

                    # Read audio chunk
                    audio_chunk, _ = stream.read(self.chunk_size)
                    self.audio_buffer.append(audio_chunk)

                    # Calculate and report audio level
                    level = calculate_audio_level(audio_chunk)
                    if self.on_audio_chunk:
                        self.on_audio_chunk(level)

                    log_debug(f"Audio chunk recorded. Level: {level:.1f}%")

        except Exception as e:
            log_error(f"Error in recording thread: {e}", exc_info=True)
            self.is_recording = False

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
