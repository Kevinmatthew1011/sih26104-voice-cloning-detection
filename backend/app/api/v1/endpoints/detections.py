from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.detection import DetectionCase, DetectionResult
from app.schemas.detection import (
    DetectionResultResponse,
    DetectionCaseDetailResponse,
    DetectionCaseListResponse,
    DetectionCaseSummaryResponse,
    PredictionEnum,
    RiskLevelEnum,
)
from app.services.audio_validator import AudioValidator
from app.services.storage import AudioStorageService
from app.services.detection.factory import get_detection_service

router = APIRouter()


@router.post(
    "",
    response_model=DetectionResultResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload audio and run voice cloning detection",
)
async def create_detection(
    file: UploadFile = File(..., description="Audio file to analyze for synthetic voice cloning"),
    db: AsyncSession = Depends(get_db),
):
    """
    Core detection endpoint:
    1. Validates audio format, size, and integrity.
    2. Persists the audio file and creates a detection case.
    3. Executes the Detection Service (Mock or Production Model).
    4. Persists the forensic detection result.
    5. Returns the structured detection result.
    """
    # 1. Validate filename and content
    filename = file.filename or "unknown_audio.wav"
    AudioValidator.validate_filename_extension(filename)
    
    content, mime_type, file_size, duration = await AudioValidator.validate_file_content(file)

    # 2. Initialize Detection Case record
    case = DetectionCase(
        filename=filename,
        storage_path="",  # Temporary placeholder until saved
        file_size_bytes=file_size,
        mime_type=mime_type,
        duration_seconds=duration,
        status="PROCESSING",
    )
    db.add(case)
    await db.flush()  # Generate case.id

    try:
        # 3. Store the audio file securely
        saved_path = AudioStorageService.save_audio(case.id, filename, content)
        case.storage_path = str(saved_path)

        # 4. Invoke ML Detection Service
        detection_service = get_detection_service()
        dto = await detection_service.detect(
            audio_path=saved_path,
            filename=filename,
            mime_type=mime_type,
            file_size_bytes=file_size,
            duration_seconds=duration,
        )

        # 5. Persist Detection Result
        result = DetectionResult(
            detection_case_id=case.id,
            prediction=dto.prediction.value,
            confidence=dto.confidence,
            risk_level=dto.risk_level.value,
            model_version=dto.model_version,
            processing_time_ms=dto.processing_time_ms,
            attack_type=dto.attack_type,
            explanation=dto.explanation,
            spectral_artifacts=dto.spectral_artifacts,
            metadata_json=dto.metadata_json,
        )
        case.status = "COMPLETED"
        db.add(result)
        await db.commit()
        await db.refresh(result)

        return DetectionResultResponse(
            id=result.id,
            prediction=PredictionEnum(result.prediction),
            confidence=result.confidence,
            risk_level=RiskLevelEnum(result.risk_level),
            model_version=result.model_version,
            processing_time_ms=result.processing_time_ms,
            created_at=result.created_at,
            attack_type=result.attack_type,
            explanation=result.explanation,
            spectral_artifacts=result.spectral_artifacts,
            metadata_json=result.metadata_json,
        )

    except Exception as e:
        case.status = "FAILED"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Detection processing failed: {str(e)}"
        )


@router.get(
    "",
    response_model=DetectionCaseListResponse,
    summary="Get detection case history with optional filtering",
)
async def list_detections(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    prediction: Optional[PredictionEnum] = None,
    risk_level: Optional[RiskLevelEnum] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve historical detection cases and their results."""
    query = select(DetectionCase).options(selectinload(DetectionCase.result))

    if search:
        query = query.where(DetectionCase.filename.ilike(f"%{search.strip()}%"))

    if prediction or risk_level:
        query = query.join(DetectionCase.result)
        if prediction:
            query = query.where(DetectionResult.prediction == prediction.value)
        if risk_level:
            query = query.where(DetectionResult.risk_level == risk_level.value)

    # Count total
    count_query = select(func.count(DetectionCase.id))
    if search:
        count_query = count_query.where(DetectionCase.filename.ilike(f"%{search.strip()}%"))
    if prediction or risk_level:
        count_query = count_query.join(DetectionCase.result)
        if prediction:
            count_query = count_query.where(DetectionResult.prediction == prediction.value)
        if risk_level:
            count_query = count_query.where(DetectionResult.risk_level == risk_level.value)

    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0

    # Paginate and order by newest first
    query = query.order_by(desc(DetectionCase.created_at)).offset(skip).limit(limit)
    res = await db.execute(query)
    cases = res.scalars().all()

    items = []
    for c in cases:
        result_dto = None
        if c.result:
            result_dto = DetectionResultResponse(
                id=c.result.id,
                prediction=PredictionEnum(c.result.prediction),
                confidence=c.result.confidence,
                risk_level=RiskLevelEnum(c.result.risk_level),
                model_version=c.result.model_version,
                processing_time_ms=c.result.processing_time_ms,
                created_at=c.result.created_at,
                attack_type=c.result.attack_type,
                explanation=c.result.explanation,
                spectral_artifacts=c.result.spectral_artifacts,
                metadata_json=c.result.metadata_json,
            )
        items.append(
            DetectionCaseSummaryResponse(
                id=c.id,
                filename=c.filename,
                file_size_bytes=c.file_size_bytes,
                mime_type=c.mime_type,
                duration_seconds=c.duration_seconds,
                status=c.status,
                created_at=c.created_at,
                updated_at=c.updated_at,
                result=result_dto,
            )
        )

    return DetectionCaseListResponse(
        total=total,
        items=items,
        limit=limit,
        skip=skip
    )


@router.get(
    "/{case_id}",
    response_model=DetectionCaseDetailResponse,
    summary="Get complete forensic details for a detection case",
)
async def get_detection(
    case_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full details of a specific detection case and result."""
    # First search by case_id, fallback to searching by result_id
    query = select(DetectionCase).options(selectinload(DetectionCase.result)).where(DetectionCase.id == case_id)
    res = await db.execute(query)
    case = res.scalar_one_or_none()

    if not case:
        # Check if caller passed a result_id
        res_query = select(DetectionResult).where(DetectionResult.id == case_id)
        res_obj = (await db.execute(res_query)).scalar_one_or_none()
        if res_obj:
            case = (await db.execute(
                select(DetectionCase).options(selectinload(DetectionCase.result)).where(DetectionCase.id == res_obj.detection_case_id)
            )).scalar_one_or_none()

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Detection case '{case_id}' not found."
        )

    result_dto = None
    if case.result:
        result_dto = DetectionResultResponse(
            id=case.result.id,
            prediction=PredictionEnum(case.result.prediction),
            confidence=case.result.confidence,
            risk_level=RiskLevelEnum(case.result.risk_level),
            model_version=case.result.model_version,
            processing_time_ms=case.result.processing_time_ms,
            created_at=case.result.created_at,
            attack_type=case.result.attack_type,
            explanation=case.result.explanation,
            spectral_artifacts=case.result.spectral_artifacts,
            metadata_json=case.result.metadata_json,
        )

    return DetectionCaseDetailResponse(
        id=case.id,
        filename=case.filename,
        file_size_bytes=case.file_size_bytes,
        mime_type=case.mime_type,
        duration_seconds=case.duration_seconds,
        status=case.status,
        created_at=case.created_at,
        updated_at=case.updated_at,
        audio_url=f"/api/v1/detections/{case.id}/audio",
        result=result_dto,
    )


@router.get(
    "/{case_id}/audio",
    summary="Stream stored audio file for browser playback",
)
async def stream_audio(
    case_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Serve the original uploaded audio file for frontend playback."""
    query = select(DetectionCase).where(DetectionCase.id == case_id)
    res = await db.execute(query)
    case = res.scalar_one_or_none()

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Detection case '{case_id}' not found."
        )

    audio_path = AudioStorageService.get_audio_path(case.storage_path)
    return FileResponse(
        path=audio_path,
        media_type=case.mime_type,
        filename=case.filename,
    )
