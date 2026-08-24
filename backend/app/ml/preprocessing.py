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
    
    Default specifications:
    - Target Sample Rate: 16,000 Hz (16 kHz standard for forensic speech models)
    - Mono Conversion: 1 channel (averages multi-channel signals)
    - Fixed Max Duration: 3.0 seconds (48,000 samples at 16 kHz)
    - Amplitude Normalization: Peak normalization to [-1.0, 1.0] range
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
        Load audio from a file path, raw bytes, file-like object, or numpy array.
        Returns: (audio_waveform, sample_rate)
        """
        if isinstance(audio_source, np.ndarray):
            sr = source_sr or self.target_sr
            return audio_source.astype(np.float32), sr

        try:
            if isinstance(audio_source, (str, Path)):
                path = Path(audio_source)
                if not path.exists():
                    raise FileNotFoundError(f"Audio file not found: {path}")
                if path.stat().st_size == 0:
                    raise ValueError(f"Audio file is empty (0 bytes): {path}")
                
                # Load with soundfile or fallback to librosa
                try:
                    y, sr = sf.read(str(path), dtype="float32")
                except Exception:
                    y, sr = librosa.load(str(path), sr=None, mono=False)
                    
            elif isinstance(audio_source, (bytes, io.BytesIO)):
                bio = io.BytesIO(audio_source) if isinstance(audio_source, bytes) else audio_source
                bio.seek(0)
                if len(bio.getvalue()) == 0:
                    raise ValueError("Audio byte buffer is empty (0 bytes).")
                try:
                    y, sr = sf.read(bio, dtype="float32")
                except Exception:
                    bio.seek(0)
                    y, sr = librosa.load(bio, sr=None, mono=False)
            else:
                raise TypeError(f"Unsupported audio source type: {type(audio_source)}")

        except Exception as e:
            raise ValueError(f"Failed to decode audio source: {str(e)}") from e

        if y is None or len(y) == 0:
            raise ValueError("Decoded audio signal contains no samples.")

        return y.astype(np.float32), sr

    def process(
        self,
        audio_source: Union[str, Path, bytes, io.BytesIO, np.ndarray],
        source_sr: Optional[int] = None,
    ) -> np.ndarray:
        """
        Executes end-to-end preprocessing:
        1. Load & decode signal
        2. Convert multi-channel to mono
        3. Resample to target sample rate (16 kHz)
        4. Trim or zero-pad to exact target length
        5. Peak amplitude normalization
        
        Returns: 1D numpy array of shape (target_length_samples,)
        """
        y, sr = self.load_audio(audio_source, source_sr=source_sr)

        # 1. Multi-channel to Mono
        if self.mono:
            if y.ndim > 1:
                # Average channels along axis 1 (or axis 0 if channels first)
                if y.shape[0] < y.shape[1] and y.shape[0] <= 4:
                    y = np.mean(y, axis=0)
                else:
                    y = np.mean(y, axis=1)

        y = y.flatten()

        # 2. Resample if sample rate mismatches
        if sr != self.target_sr:
            y = librosa.resample(y, orig_sr=sr, target_sr=self.target_sr)

        # 3. Peak Normalization
        if self.normalize:
            max_abs = np.max(np.abs(y))
            if max_abs > 1e-6:
                y = y / max_abs
            else:
                y = np.zeros_like(y)

        # 4. Fixed Duration Trimming / Zero-Padding
        current_samples = len(y)
        if current_samples > self.target_length_samples:
            # Trim from center / start
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
        }
