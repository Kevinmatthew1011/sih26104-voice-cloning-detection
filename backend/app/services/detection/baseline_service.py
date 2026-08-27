from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from app.schemas.detection import (
    DetectionResultDTO,
    PredictionEnum,
    RiskLevelEnum,
)
from app.services.detection.base import BaseDetectionService
from app.ml.inference import BaselineInferenceEngine, DEFAULT_MODEL_FILE


class BaselineMLDetectionService(BaseDetectionService):
    """
    Real ML Baseline Detection Service.
    
    Implements the BaseDetectionService interface using the trained scikit-learn
    MFCC + Logistic Regression pipeline.
    
    Notes on Baseline Behavior:
    - Probability estimates: The 'confidence' field in DetectionResultDTO represents the
      uncalibrated class probability estimate produced by LogisticRegression.predict_proba().
    - 3-Second Window: Only the first 3.0 seconds of audio are analyzed by this baseline.
    - If the model artifact has not been trained, it fails loudly with HTTP 503 and clear guidance.
    """

    def __init__(self, model_version: str = "baseline-v1"):
        self.model_version = model_version
        self.engine = BaselineInferenceEngine()

    def get_model_info(self) -> Dict[str, Any]:
        is_available = self.engine.is_model_available()
        return {
            "name": "SIH26104-BaselineMLDetectionService",
            "version": self.model_version,
            "type": "scikit_learn_logistic_regression",
            "feature_extractor": "MFCC + Delta + Spectral Descriptors (88-dim)",
            "analyzed_duration_seconds": 3.0,
            "model_trained": is_available,
            "status": "ready" if is_available else "model_not_trained",
        }

    async def detect(
        self,
        audio_path: Path,
        filename: str,
        mime_type: str,
        file_size_bytes: int,
        duration_seconds: Optional[float] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> DetectionResultDTO:
        if not self.engine.is_model_available():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    f"Baseline ML model is not trained. Model artifact '{DEFAULT_MODEL_FILE}' "
                    "was not found. Please train the baseline model using 'python -m app.ml.train' "
                    "on an approved dataset, or set DETECTION_ENGINE=mock in your configuration."
                ),
            )

        try:
            inference_result = self.engine.predict_audio(
                audio_source=audio_path,
                filename=filename,
                file_size_bytes=file_size_bytes,
                duration_seconds=duration_seconds,
            )

            prediction_str = inference_result["prediction"]
            risk_level_str = inference_result["risk_level"]

            return DetectionResultDTO(
                engine_type="baseline",
                prediction=PredictionEnum(prediction_str),
                confidence=inference_result["confidence"],  # Model probability estimate
                risk_level=RiskLevelEnum(risk_level_str),
                model_version=self.model_version,
                processing_time_ms=inference_result["processing_time_ms"],
                attack_type=inference_result.get("attack_type"),
                explanation=inference_result.get("explanation"),
                spectral_artifacts=inference_result.get("spectral_artifacts"),
                metadata_json=inference_result.get("metadata_json"),
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Baseline ML inference failed: {str(e)}",
            ) from e
