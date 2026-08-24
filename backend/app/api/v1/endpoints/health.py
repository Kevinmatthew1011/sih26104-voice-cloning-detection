from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.config import settings
from app.database import get_db
from app.schemas.health import HealthResponse
from app.services.detection.factory import get_detection_service

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """Backend and dependency health check."""
    db_status = "connected"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {str(e)}"

    engine = get_detection_service()
    model_info = engine.get_model_info()

    return HealthResponse(
        status="healthy" if "error" not in db_status else "degraded",
        environment=settings.ENVIRONMENT,
        version=settings.VERSION,
        database=db_status,
        detection_engine=settings.DETECTION_ENGINE,
        model_version=model_info.get("version", settings.MOCK_MODEL_VERSION),
        timestamp=datetime.now(timezone.utc),
        details={
            "supported_extensions": settings.ALLOWED_EXTENSIONS,
            "max_file_size_bytes": settings.MAX_FILE_SIZE_BYTES,
            "engine_info": model_info,
        }
    )
