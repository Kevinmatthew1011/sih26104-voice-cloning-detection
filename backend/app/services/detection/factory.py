import logging
from app.config import settings
from app.services.detection.base import BaseDetectionService
from app.services.detection.mock_service import MockDetectionService
from app.services.detection.baseline_service import BaselineMLDetectionService
from app.services.detection.aasist_service import AASISTDetectionService

logger = logging.getLogger(__name__)

# Global singleton or cache for the detection service instance
_detection_service_instance: BaseDetectionService | None = None


def get_detection_service() -> BaseDetectionService:
    """
    Factory function providing the active detection service implementation.
    
    Supported DETECTION_ENGINE values:
    - "mock": MockDetectionService (deterministic heuristic simulator)
    - "baseline": BaselineMLDetectionService (real scikit-learn MFCC baseline)
    - "aasist": AASISTDetectionService (deep learning graph attention network)
    """
    global _detection_service_instance
    if _detection_service_instance is not None:
        return _detection_service_instance

    engine_name = settings.DETECTION_ENGINE.strip().lower()

    if engine_name == "mock":
        logger.info(f"Initializing MockDetectionService (model_version: {settings.MOCK_MODEL_VERSION})")
        _detection_service_instance = MockDetectionService(model_version=settings.MOCK_MODEL_VERSION)
    elif engine_name == "baseline":
        logger.info("Initializing BaselineMLDetectionService (model_version: baseline-v1)")
        _detection_service_instance = BaselineMLDetectionService(model_version="baseline-v1")
    elif engine_name == "aasist":
        logger.info("Initializing AASISTDetectionService (model_version: aasist-v1)")
        _detection_service_instance = AASISTDetectionService(model_version="aasist-v1")
    else:
        raise ValueError(
            f"Unsupported DETECTION_ENGINE '{engine_name}'. "
            "Supported options are: 'mock', 'baseline', 'aasist'."
        )

    return _detection_service_instance


def reset_detection_service_cache() -> None:
    """Helper for testing to reset the singleton instance."""
    global _detection_service_instance
    _detection_service_instance = None
