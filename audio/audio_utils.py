"""
Audio utility functions for Voxylis
"""

import numpy as np


def apply_noise_gate(audio_data: np.ndarray, threshold: float = 0.02) -> np.ndarray:
    """
    Apply noise gate to reduce background noise

    Args:
        audio_data: Audio samples as numpy array
        threshold: Noise threshold (0-1)

    Returns:
        Processed audio data (float32, 1D)
    """
    # Flatten to 1D
    audio_data = audio_data.flatten()

    # Convert int16 to float32
    if audio_data.dtype == np.int16:
        audio_float = audio_data.astype(np.float32) / 32767.0
    else:
        audio_float = audio_data.astype(np.float32)

    max_val = np.max(np.abs(audio_float))
    if max_val == 0:
        return audio_float

    normalized = audio_float / max_val
    gate = np.abs(normalized) > threshold
    return (normalized * gate * max_val).astype(np.float32)


def normalize_audio(audio_data: np.ndarray) -> np.ndarray:
    """
    Normalize audio to prevent clipping

    Args:
        audio_data: Audio samples as numpy array

    Returns:
        Normalized audio data (int16)
    """
    # Flatten to 1D first
    audio_data = audio_data.flatten()

    # If already int16, convert to float for processing
    if audio_data.dtype == np.int16:
        audio_float = audio_data.astype(np.float32) / 32767.0
    else:
        audio_float = audio_data.astype(np.float32)

    max_val = np.max(np.abs(audio_float))
    if max_val == 0:
        return np.zeros(len(audio_float), dtype=np.int16)

    # Normalize to 90% of max to avoid clipping
    normalized = audio_float / max_val * 0.9
    return (normalized * 32767).astype(np.int16)


def calculate_audio_level(audio_data: np.ndarray) -> float:
    """
    Calculate audio level (0-100)

    Args:
        audio_data: Audio samples as numpy array

    Returns:
        Audio level percentage
    """
    if len(audio_data) == 0:
        return 0.0

    flat = audio_data.flatten().astype(np.float32)
    if audio_data.dtype == np.int16:
        flat = flat / 32767.0

    rms = float(np.sqrt(np.mean(flat**2)))
    return min(100.0, rms * 100.0 * 10)  # scale to 0-100


def detect_silence(audio_data: np.ndarray, threshold: float = 0.01) -> bool:
    """
    Detect if audio is silent using RMS energy.
    Returns True if the audio is too quiet to contain real speech.
    """
    if len(audio_data) == 0:
        return True

    flat = audio_data.flatten().astype(np.float32)
    if audio_data.dtype == np.int16:
        flat = flat / 32767.0

    rms = float(np.sqrt(np.mean(flat**2)))
    return rms < threshold


def has_speech(
    audio_data: np.ndarray,
    rms_threshold: float = 0.02,
    peak_threshold: float = 0.08,
    min_speech_ratio: float = 0.10,
) -> bool:
    """
    Returns True only if the audio likely contains real speech.

    Three-layer gate (thresholds tuned to reject background noise):
      1. RMS energy must exceed rms_threshold  (0.02 = fairly loud)
      2. Peak amplitude must exceed peak_threshold (0.08)
      3. At least min_speech_ratio of 512-sample frames must be active

    Background noise / fan hum / keyboard clicks typically sit at
    RMS < 0.005, so 0.02 gives a comfortable margin.
    """
    if len(audio_data) == 0:
        return False

    flat = audio_data.flatten().astype(np.float32)
    if audio_data.dtype == np.int16:
        flat = flat / 32767.0

    # 1. Overall RMS
    rms = float(np.sqrt(np.mean(flat**2)))
    if rms < rms_threshold:
        return False

    # 2. Peak amplitude
    peak = float(np.max(np.abs(flat)))
    if peak < peak_threshold:
        return False

    # 3. Fraction of frames with energy above threshold
    frame_size = 512
    n_frames = len(flat) // frame_size
    if n_frames == 0:
        return rms >= rms_threshold

    active = sum(
        1
        for i in range(n_frames)
        if float(np.sqrt(np.mean(flat[i * frame_size : (i + 1) * frame_size] ** 2))) >= rms_threshold
    )

    return (active / n_frames) >= min_speech_ratio


def resample_audio(audio_data: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """
    Resample audio to target sample rate

    Args:
        audio_data: Audio samples as numpy array
        orig_sr: Original sample rate
        target_sr: Target sample rate

    Returns:
        Resampled audio data
    """
    if orig_sr == target_sr:
        return audio_data

    # Simple linear interpolation resampling
    num_samples = int(len(audio_data) * target_sr / orig_sr)
    indices = np.linspace(0, len(audio_data) - 1, num_samples)
    resampled = np.interp(indices, np.arange(len(audio_data)), audio_data)

    return resampled.astype(audio_data.dtype)
