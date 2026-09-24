"""
Active Noise Cancellation for Voxylis
==========================================
Implements a real-time, adaptive noise cancellation pipeline:

  1. Ambient calibration — learns the noise floor from the first
     N_CALIB_FRAMES frames of every recording (before you speak).
  2. Spectral subtraction — subtracts the learned noise spectrum
     from each frame in the frequency domain.
  3. Wiener filter        — applies a smooth gain mask to suppress
     residual noise without creating "musical noise" artefacts.
  4. Post-gate            — zeroes out frames that are still below
     the noise floor after processing.

No external libraries required — pure numpy FFT.
"""

import numpy as np
from utils.logger import log_debug

# ── tuneable constants ─────────────────────────────────────────────────────
FRAME_SIZE = 512  # FFT frame size (samples)
HOP_SIZE = 256  # overlap-add hop (50 % overlap)
N_CALIB_FRAMES = 20  # frames used to estimate noise floor (~0.3 s)
OVER_SUBTRACT = 1.8  # how aggressively to subtract noise
SPECTRAL_FLOOR = 0.005  # minimum gain after subtraction (balanced to avoid silence/artifacts)
WIENER_ALPHA = 0.96  # smoothing factor for noise estimate update
POST_GATE_RMS = 0.004  # frames below this RMS after processing → zero (balanced sensitivity)


class NoiseCanceller:
    """
    Stateful noise canceller.  One instance per recording session.

    Usage:
        nc = NoiseCanceller()
        clean = nc.process(raw_audio_int16_or_float32)
    """

    def __init__(self):
        self._noise_psd = None  # estimated noise power spectrum (np.ndarray or None)
        self._calibrated = False
        self._frame_count = 0

    # ── public ────────────────────────────────────────────────────────────

    def process(self, audio: np.ndarray) -> np.ndarray:
        """
        Run the full ANC pipeline on a complete recording.

        Args:
            audio: 1-D int16 or float32 numpy array

        Returns:
            Cleaned audio as int16 numpy array
        """
        float_audio = self._to_float(audio)

        # Step 1 — calibrate noise floor from the first N_CALIB_FRAMES
        self._calibrate(float_audio)

        if self._noise_psd is None:
            # No calibration data — return original
            return self._to_int16(float_audio)

        # Step 2 — frame-by-frame spectral subtraction + Wiener filter
        clean = self._process_frames(float_audio)

        log_debug(f"ANC: input_rms={self._rms(float_audio):.4f} " f"output_rms={self._rms(clean):.4f}")
        return self._to_int16(clean)

    def reset(self):
        """Call before each new recording to reset calibration state."""
        self._noise_psd = None
        self._calibrated = False
        self._frame_count = 0

    # ── calibration ───────────────────────────────────────────────────────

    def _calibrate(self, audio: np.ndarray):
        """Estimate noise PSD from the first N_CALIB_FRAMES frames."""
        psds = []
        for i in range(N_CALIB_FRAMES):
            start = i * HOP_SIZE
            end = start + FRAME_SIZE
            if end > len(audio):
                break
            frame = audio[start:end] * np.hanning(FRAME_SIZE)
            spectrum = np.fft.rfft(frame)
            psds.append(np.abs(spectrum) ** 2)

        if psds:
            self._noise_psd = np.mean(psds, axis=0)
            self._calibrated = True
            log_debug(f"ANC calibrated from {len(psds)} frames, " f"noise_rms≈{np.sqrt(np.mean(self._noise_psd)):.5f}")

    # ── frame processing ──────────────────────────────────────────────────

    def _process_frames(self, audio: np.ndarray) -> np.ndarray:
        """Overlap-add spectral subtraction + Wiener filter."""
        n = len(audio)
        output = np.zeros(n, dtype=np.float32)
        window = np.hanning(FRAME_SIZE).astype(np.float32)
        noise_psd = self._noise_psd.copy()

        pos = 0
        while pos + FRAME_SIZE <= n:
            frame = audio[pos : pos + FRAME_SIZE] * window
            spectrum = np.fft.rfft(frame)
            mag = np.abs(spectrum)
            phase = np.angle(spectrum)
            psd = mag**2

            # ── spectral subtraction ──────────────────────────────────────
            clean_psd = np.maximum(psd - OVER_SUBTRACT * noise_psd, SPECTRAL_FLOOR * psd)
            clean_mag = np.sqrt(clean_psd)

            # ── Wiener gain ───────────────────────────────────────────────
            # G(k) = clean_psd / (clean_psd + noise_psd)
            wiener_gain = clean_psd / (clean_psd + noise_psd + 1e-10)
            clean_mag = clean_mag * wiener_gain

            # ── reconstruct ───────────────────────────────────────────────
            clean_spectrum = clean_mag * np.exp(1j * phase)
            clean_frame = np.fft.irfft(clean_spectrum).astype(np.float32)
            clean_frame *= window

            # ── post-gate: silence frames that are still mostly noise ─────
            if self._rms(clean_frame) < POST_GATE_RMS:
                clean_frame[:] = 0.0

            # ── overlap-add ───────────────────────────────────────────────
            output[pos : pos + FRAME_SIZE] += clean_frame

            # ── adaptive noise update (only on quiet frames) ──────────────
            if self._rms(frame) < 2.0 * np.sqrt(np.mean(noise_psd)):
                noise_psd = WIENER_ALPHA * noise_psd + (1 - WIENER_ALPHA) * psd

            pos += HOP_SIZE

        # Normalise overlap-add gain
        output /= (FRAME_SIZE / HOP_SIZE) / 2.0
        return output

    # ── helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _to_float(audio: np.ndarray) -> np.ndarray:
        audio = audio.flatten().astype(np.float32)
        if audio.dtype == np.int16 or np.max(np.abs(audio)) > 1.0:
            audio = audio / 32767.0
        return audio

    @staticmethod
    def _to_int16(audio: np.ndarray) -> np.ndarray:
        return np.clip(audio * 32767, -32767, 32767).astype(np.int16)

    @staticmethod
    def _rms(audio: np.ndarray) -> float:
        return float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))
