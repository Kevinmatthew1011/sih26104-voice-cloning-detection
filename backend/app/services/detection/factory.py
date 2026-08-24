import logging
from app.config import settings
from app.services.detection.base import BaseDetectionService
from app.services.detection.mock_service import MockDetectionService

logger = logging.getLogger(__name__)

# Global singleton or cache for the detection service instance
_detection_service_instance: BaseDetectionService | None = None


def get_detection_service() -> BaseDetectionService:
    """
    Factory function providing the active detection service implementation.
    
    To replace the Mock with the Teammate's real AI/ML model:
    1. Implement a class inheriting from BaseDetectionService (e.g. RealMlDetectionService).
    2. Register it in this factory function.
    3. Update the DETECTION_ENGINE environment variable (e.g. DETECTION_ENGINE=real_ml).
    
    No other API or DB code needs to be modified!
    """
    global _detection_service_instance
    if _detection_service_instance is not None:
        return _detection_service_instance

    engine_name = settings.DETECTION_ENGINE.lower()
    
    if engine_name == "mock":
        logger.info(f"Initializing MockDetectionService with version {settings.MOCK_MODEL_VERSION}")
        _detection_service_instance = MockDetectionService(model_version=settings.MOCK_MODEL_VERSION)
    else:
        # Placeholder for teammate's real model implementation
        # e.g., from app.services.detection.real_ml_service import RealMlDetectionService
        # _detection_service_instance = RealMlDetectionService()
        logger.warning(
            f"Requested engine '{engine_name}' not yet registered. Falling back to MockDetectionService."
        )
        _detection_service_instance = MockDetectionService(model_version=settings.MOCK_MODEL_VERSION)

    return _detection_service_instance
