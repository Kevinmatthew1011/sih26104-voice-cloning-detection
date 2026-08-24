from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import numpy as np
import librosa
from app.ml.preprocessing import AudioPreprocessor


class AudioFeatureExtractor:
    """
    Forensic Audio Feature Extraction Module for Voice Cloning Baseline Detection.
    
    Extracts a fixed-dimensional feature vector combining cepstral, delta, spectral,
    and temporal descriptors:
    
    1. MFCC Statistics (Mean & Std for 13 coefficients)      : 26 features
    2. Delta MFCC Statistics (Mean & Std for 13 coefficients) : 26 features
    3. Delta-Delta MFCC Statistics (Mean & Std)               : 26 features
    4. Spectral Centroid (Mean & Std)                         : 2 features
    5. Spectral Bandwidth (Mean & Std)                        : 2 features
    6. Spectral Rolloff (Mean & Std)                          : 2 features
    7. Zero-Crossing Rate (Mean & Std)                        : 2 features
    8. RMS Energy (Mean & Std)                                : 2 features
    -------------------------------------------------------------------------
    Total Fixed Feature Dimension                             : 88 features
    """

    FEATURE_VERSION: str = "mfcc-spectral-v1.0"

    def __init__(
        self,
        n_mfcc: int = 13,
        n_fft: int = 512,
        hop_length: int = 256,
        target_sr: int = 16000,
    ):
        self.n_mfcc = n_mfcc
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.target_sr = target_sr
        self._feature_names = self._build_feature_names()

    def _build_feature_names(self) -> List[str]:
        names = []
        # MFCC
        for i in range(self.n_mfcc):
            names.append(f"mfcc_{i+1}_mean")
            names.append(f"mfcc_{i+1}_std")
        # Delta MFCC
        for i in range(self.n_mfcc):
            names.append(f"mfcc_delta_{i+1}_mean")
            names.append(f"mfcc_delta_{i+1}_std")
        # Delta-Delta MFCC
        for i in range(self.n_mfcc):
            names.append(f"mfcc_delta2_{i+1}_mean")
            names.append(f"mfcc_delta2_{i+1}_std")
        # Spectral descriptors
        names.extend(["spectral_centroid_mean", "spectral_centroid_std"])
        names.extend(["spectral_bandwidth_mean", "spectral_bandwidth_std"])
        names.extend(["spectral_rolloff_mean", "spectral_rolloff_std"])
        names.extend(["zcr_mean", "zcr_std"])
        names.extend(["rms_mean", "rms_std"])
        return names

    @property
    def feature_dim(self) -> int:
        return len(self._feature_names)

    @property
    def feature_names(self) -> List[str]:
        return list(self._feature_names)

    def extract_features(self, y: np.ndarray, sr: Optional[int] = None) -> np.ndarray:
        """
        Extract fixed-size feature vector from a preprocessed 1D audio waveform.
        
        Args:
            y: 1D numpy array of audio samples.
            sr: Sample rate (defaults to self.target_sr).
            
        Returns:
            1D numpy array of shape (88,) containing extracted features.
        """
        if sr is None:
            sr = self.target_sr

        if y is None or len(y) == 0:
            raise ValueError("Cannot extract features from empty audio waveform.")

        feature_values: List[float] = []

        # 1. MFCCs
        mfcc = librosa.feature.mfcc(
            y=y,
            sr=sr,
            n_mfcc=self.n_mfcc,
            n_fft=self.n_fft,
            hop_length=self.hop_length,
        )
        for i in range(self.n_mfcc):
            feature_values.append(float(np.mean(mfcc[i])))
            feature_values.append(float(np.std(mfcc[i])))

        # 2. Delta MFCCs (1st order differential)
        mfcc_delta = librosa.feature.delta(mfcc)
        for i in range(self.n_mfcc):
            feature_values.append(float(np.mean(mfcc_delta[i])))
            feature_values.append(float(np.std(mfcc_delta[i])))

        # 3. Delta-Delta MFCCs (2nd order acceleration)
        mfcc_delta2 = librosa.feature.delta(mfcc, order=2)
        for i in range(self.n_mfcc):
            feature_values.append(float(np.mean(mfcc_delta2[i])))
            feature_values.append(float(np.std(mfcc_delta2[i])))

        # 4. Spectral Centroid
        cent = librosa.feature.spectral_centroid(
            y=y, sr=sr, n_fft=self.n_fft, hop_length=self.hop_length
        )
        feature_values.append(float(np.mean(cent)))
        feature_values.append(float(np.std(cent)))

        # 5. Spectral Bandwidth
        band = librosa.feature.spectral_bandwidth(
            y=y, sr=sr, n_fft=self.n_fft, hop_length=self.hop_length
        )
        feature_values.append(float(np.mean(band)))
        feature_values.append(float(np.std(band)))

        # 6. Spectral Rolloff (85% energy rolloff)
        rolloff = librosa.feature.spectral_rolloff(
            y=y, sr=sr, n_fft=self.n_fft, hop_length=self.hop_length, roll_percent=0.85
        )
        feature_values.append(float(np.mean(rolloff)))
        feature_values.append(float(np.std(rolloff)))

        # 7. Zero Crossing Rate (ZCR)
        zcr = librosa.feature.zero_crossing_rate(y=y, hop_length=self.hop_length)
        feature_values.append(float(np.mean(zcr)))
        feature_values.append(float(np.std(zcr)))

        # 8. RMS Energy
        rms = librosa.feature.rms(y=y, hop_length=self.hop_length)
        feature_values.append(float(np.mean(rms)))
        feature_values.append(float(np.std(rms)))

        vec = np.array(feature_values, dtype=np.float32)
        # Sanitize any NaNs or Infs
        vec = np.nan_to_num(vec, nan=0.0, posinf=0.0, neginf=0.0)

        return vec

    def extract_from_file(
        self,
        audio_source: Union[str, Path, bytes],
        preprocessor: Optional[AudioPreprocessor] = None,
    ) -> np.ndarray:
        """Helper to preprocess and extract features directly from audio source."""
        p = preprocessor or AudioPreprocessor(target_sr=self.target_sr)
        y = p.process(audio_source)
        return self.extract_features(y, sr=self.target_sr)

    def get_config(self) -> Dict[str, Any]:
        return {
            "feature_version": self.FEATURE_VERSION,
            "feature_dim": self.feature_dim,
            "n_mfcc": self.n_mfcc,
            "n_fft": self.n_fft,
            "hop_length": self.hop_length,
            "target_sr": self.target_sr,
        }
