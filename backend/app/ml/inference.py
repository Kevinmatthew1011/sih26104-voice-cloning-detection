import json
import time
from pathlib import Path
from typing import Dict, Any, Union, Optional
import numpy as np

from app.ml.preprocessing import AudioPreprocessor
from app.ml.features import AudioFeatureExtractor
from app.ml.classifier import BaselineClassifier, CLASS_MAPPING


# Default model paths
DEFAULT_MODEL_DIR = Path(__file__).resolve().parent.parent.parent.parent / "models" / "baseline-v1"
DEFAULT_MODEL_FILE = DEFAULT_MODEL_DIR / "model.joblib"
DEFAULT_METADATA_FILE = DEFAULT_MODEL_DIR / "metadata.json"


class BaselineInferenceEngine:
    """
    Inference Engine for the Baseline ML Voice Cloning Detector.
    
    Loads trained model artifact, applies shared preprocessing (first 3 seconds @ 16 kHz mono),
    extracts MFCC/spectral features, and returns model probability estimates and threat risk levels.
    """

    def __init__(
        self,
        model_path: Path = DEFAULT_MODEL_FILE,
        metadata_path: Path = DEFAULT_METADATA_FILE,
    ):
        self.model_path = Path(model_path)
        self.metadata_path = Path(metadata_path)
        self.model: Optional[BaselineClassifier] = None
        self.metadata: Dict[str, Any] = {}
        self.preprocessor = AudioPreprocessor()
        self.feature_extractor = AudioFeatureExtractor()

    def is_model_available(self) -> bool:
        """Check if trained model artifact exists on disk."""
        return self.model_path.exists()

    def load_model(self) -> None:
        """Load trained model and associated metadata."""
        if not self.is_model_available():
            raise FileNotFoundError(
                f"Baseline ML model artifact not found at '{self.model_path}'. "
                "The baseline model has not been trained yet. Please train the model "
                "using 'python -m app.ml.train' on an approved dataset or set DETECTION_ENGINE=mock."
            )

        self.model = BaselineClassifier.load(self.model_path)
        if self.metadata_path.exists():
            try:
                with open(self.metadata_path, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
            except Exception:
                self.metadata = {}
        else:
            self.metadata = {}

    def predict_audio(
        self,
        audio_source: Union[str, Path, bytes],
        filename: str = "audio.wav",
        file_size_bytes: int = 0,
        duration_seconds: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Execute end-to-end inference on raw audio input.
        Analyzes the first 3.0 seconds of the recording.
        """
        if self.model is None:
            self.load_model()

        start_time = time.perf_counter()

        # 1. Preprocess audio (first 3.0s @ 16 kHz mono)
        y = self.preprocessor.process(audio_source)

        # 2. Extract fixed-size feature vector
        features = self.feature_extractor.extract_features(y, sr=self.preprocessor.target_sr)
        features_2d = features.reshape(1, -1)

        # 3. Model forward pass (predicted class probability estimates)
        probs = self.model.predict_proba(features_2d)[0]
        prob_real = float(probs[0])
        prob_synthetic = float(probs[1])

        # 4. Decision threshold
        if prob_synthetic >= 0.5:
            prediction = "synthetic"
            confidence = prob_synthetic
            risk_level = "high" if confidence >= 0.70 else "medium"
        else:
            prediction = "real"
            confidence = prob_real
            risk_level = "low"

        end_time = time.perf_counter()
        latency_ms = int((end_time - start_time) * 1000)

        # Build forensic explanation
        explanation = (
            f"Baseline ML binary classification (Logistic Regression on {self.feature_extractor.feature_dim} MFCC "
            f"and spectral envelope descriptors from the first 3 seconds). "
            f"Predicted synthetic probability: {prob_synthetic:.2%}, "
            f"Predicted genuine probability: {prob_real:.2%}. "
            "Note: Probability values represent model output estimates (uncalibrated) and do not identify specific cloning architectures."
        )

        return {
            "prediction": prediction,
            "confidence": round(confidence, 4),  # Selected-class probability estimate
            "risk_level": risk_level,
            "model_version": self.metadata.get("model_version", "baseline-v1"),
            "processing_time_ms": latency_ms,
            "attack_type": None,  # Baseline binary model cannot definitively attribute synthesis method
            "explanation": explanation,
            "probabilities": {
                "real": round(prob_real, 4),
                "synthetic": round(prob_synthetic, 4),
            },
            "spectral_artifacts": {
                "mfcc_feature_count": self.feature_extractor.feature_dim,
                "input_sample_rate_hz": self.preprocessor.target_sr,
                "spectral_centroid_mean": float(features[self.feature_extractor.feature_names.index("spectral_centroid_mean")]),
                "rms_energy_mean": float(features[self.feature_extractor.feature_names.index("rms_mean")]),
            },
            "metadata_json": {
                "engine_type": "baseline_ml",
                "synthetic_probability": round(prob_synthetic, 4),
                "real_probability": round(prob_real, 4),
                "classifier": "LogisticRegression",
                "feature_version": self.feature_extractor.FEATURE_VERSION,
                "file_size_bytes": file_size_bytes,
                "target_sample_rate": self.preprocessor.target_sr,
                "analyzed_duration_seconds": min(duration_seconds or 3.0, self.preprocessor.max_duration_seconds),
                "total_duration_seconds": duration_seconds or self.preprocessor.max_duration_seconds,
                "duration_limitation_note": "Only the first 3.0 seconds were analyzed by this baseline model.",
            },
        }
