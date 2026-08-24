import io
from pathlib import Path
from typing import Union, Tuple, Optional
import numpy as np
import soundfile as sf
import librosa


class AudioPreprocessor:
    """
    Shared Audio Preprocessing Pipeline.
    
    Standardizes raw audio streams across training, validation, testing, and real-time inference.
    
    Specifications & Default Parameters:
    - Target Sample Rate: 16,000 Hz (16 kHz standard for forensic speech models)
    - Mono Conversion: 1 channel (averages multi-channel signals to single mono channel)
    - Fixed Max Duration: 3.0 seconds (48,000 samples at 16 kHz)
    - Amplitude Normalization: Peak normalization to [-1.0, 1.0] range
    
    IMPORTANT BASELINE LIMITATION - 3-SECOND WINDOW:
    - Audio recordings shorter than 3.0 seconds are zero-padded to 3.0 seconds.
    - Audio recordings longer than 3.0 seconds are truncated to the first 3.0 seconds.
    - Limitation: Only the initial 3 seconds of a recording are analyzed in this baseline.
      Any synthetic anomalies, voice-conversion transitions, or cloning artifacts occurring
      after the 3-second mark will not be captured by this baseline model.
    - Future enhancements should implement sliding-window segment inference with temporal aggregation.
    """

    def __init__(
        self,
        target_sr: int = 16000,
        max_duration_seconds: float = 3.0,
        normalize: bool = True,
        mono: bool = True,
    ):
        self.target_sr = target_sr
        self.max_duration_seconds = max_duration_seconds
        self.target_length_samples = int(target_sr * max_duration_seconds)
        self.normalize = normalize
        self.mono = mono

    def load_audio(
        self,
        audio_source: Union[str, Path, bytes, io.BytesIO, np.ndarray],
        source_sr: Optional[int] = None,
    ) -> Tuple[np.ndarray, int]:
        """
        Load and decode audio from a file path, raw bytes, file-like object, or numpy array.
        Converts multi-channel audio to mono safely based on loader channel convention.
        
        Returns:
            Tuple of (1D float32 audio waveform, sample_rate)
        """
        if isinstance(audio_source, np.ndarray):
            sr = source_sr or self.target_sr
            y = audio_source.astype(np.float32)
            if self.mono and y.ndim > 1:
                # Handle standard (samples, channels) vs (channels, samples)
                if y.shape[0] >= y.shape[1]:
                    y = np.mean(y, axis=1)
                else:
                    y = np.mean(y, axis=0)
            return y.flatten().astype(np.float32), sr

        try:
            if isinstance(audio_source, (str, Path)):
                path = Path(audio_source)
                if not path.exists():
                    raise FileNotFoundError(f"Audio file not found: {path}")
                if path.stat().st_size == 0:
                    raise ValueError(f"Audio file is empty (0 bytes): {path}")
                
                # Load with soundfile (standard shape: (samples,) or (samples, channels))
                try:
                    y, sr = sf.read(str(path), dtype="float32")
                    if self.mono and y.ndim > 1:
                        y = np.mean(y, axis=1)
                except Exception:
                    y, sr = librosa.load(str(path), sr=None, mono=self.mono)
                    
            elif isinstance(audio_source, (bytes, io.BytesIO)):
                bio = io.BytesIO(audio_source) if isinstance(audio_source, bytes) else audio_source
                bio.seek(0)
                if len(bio.getvalue()) == 0:
                    raise ValueError("Audio byte buffer is empty (0 bytes).")
                try:
                    y, sr = sf.read(bio, dtype="float32")
                    if self.mono and y.ndim > 1:
                        y = np.mean(y, axis=1)
                except Exception:
                    bio.seek(0)
                    y, sr = librosa.load(bio, sr=None, mono=self.mono)
            else:
                raise TypeError(f"Unsupported audio source type: {type(audio_source)}")

        except Exception as e:
            raise ValueError(f"Failed to decode audio source: {str(e)}") from e

        if y is None or len(y) == 0:
            raise ValueError("Decoded audio signal contains no samples.")

        return y.flatten().astype(np.float32), sr

    def process(
        self,
        audio_source: Union[str, Path, bytes, io.BytesIO, np.ndarray],
        source_sr: Optional[int] = None,
    ) -> np.ndarray:
        """
        Executes end-to-end preprocessing:
        1. Load & decode signal (with safe mono conversion)
        2. Resample to target sample rate (16 kHz)
        3. Peak amplitude normalization
        4. Fixed 3.0s window: zero-pad shorter audio or truncate beginning of longer audio
        
        Returns: 1D numpy array of shape (target_length_samples,)
        """
        y, sr = self.load_audio(audio_source, source_sr=source_sr)

        # Ensure 1D signal
        y = y.flatten()

        # 1. Resample if sample rate mismatches
        if sr != self.target_sr:
            y = librosa.resample(y, orig_sr=sr, target_sr=self.target_sr)

        # 2. Peak Normalization
        if self.normalize:
            max_abs = np.max(np.abs(y))
            if max_abs > 1e-6:
                y = y / max_abs
            else:
                y = np.zeros_like(y)

        # 3. Fixed Duration Trimming / Zero-Padding
        # Note: Audio longer than target_length_samples is truncated to the first 3.0 seconds.
        current_samples = len(y)
        if current_samples > self.target_length_samples:
            # Truncate to the first 3.0 seconds
            y = y[: self.target_length_samples]
        elif current_samples < self.target_length_samples:
            # Zero pad to target length
            padding = self.target_length_samples - current_samples
            y = np.pad(y, (0, padding), mode="constant")

        # Sanitize non-finite values (NaNs/Infs)
        y = np.nan_to_num(y, nan=0.0, posinf=1.0, neginf=-1.0)

        return y.astype(np.float32)

    def get_config(self) -> dict:
        return {
            "target_sr": self.target_sr,
            "max_duration_seconds": self.max_duration_seconds,
            "target_length_samples": self.target_length_samples,
            "normalize": self.normalize,
            "mono": self.mono,
            "duration_strategy": "fixed_3s_first_window_truncation_or_zero_pad",
        }
