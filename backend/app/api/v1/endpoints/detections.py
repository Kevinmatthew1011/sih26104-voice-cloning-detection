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
    ActionEnum,
    SecurityDecisionDTO,
)
from app.schemas.report import DetectionEvidenceReportResponse
from app.services.audio_validator import AudioValidator
from app.services.audio_metadata import AudioMetadataService
from app.services.storage import AudioStorageService
from app.services.detection.factory import get_detection_service
from app.services.decision_engine import SecurityDecisionEngine
from app.services.report_service import AuditReportBuilder


def build_detection_result_response(result: DetectionResult) -> DetectionResultResponse:
    """
    Helper to deserialize detection result response.

    Auditability Policy:
    - If metadata_json contains 'decision', returns the verified persisted SecurityDecisionDTO.
    - If metadata_json lacks 'decision' (legacy historical record), action and decision remain None.
      Historical records are never silently forged or misrepresented as Policy v1.0 decisions.
    """
    meta = result.metadata_json or {}
    decision_data = meta.get("decision")
    decision_dto: Optional[SecurityDecisionDTO] = None
    action_val: Optional[ActionEnum] = None
    decision_msg: Optional[str] = None

    if decision_data and isinstance(decision_data, dict):
        try:
            decision_dto = SecurityDecisionDTO(**decision_data)
            action_val = decision_dto.action
            decision_msg = decision_dto.decision_message
        except Exception:
            decision_dto = None

    return DetectionResultResponse(
        id=result.id,
        engine_type=result.engine_type,
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
        action=action_val,
        decision_message=decision_msg,
        decision=decision_dto,
    )

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
    2. Extracts acoustic metadata (SHA-256 fingerprint, sample rate, channels, duration).
    3. Persists the audio file and creates a detection case.
    4. Executes the Detection Service (Mock or Production Model).
    5. Persists the forensic detection result.
    6. Returns the structured detection result.
    """
    # 1. Validate filename and content
    filename = file.filename or "unknown_audio.wav"
    AudioValidator.validate_filename_extension(filename)
    
    content, mime_type, file_size = await AudioValidator.validate_file_content(file)

    # 2. Extract acoustic metadata and compute SHA-256 integrity fingerprint
    metadata = AudioMetadataService.extract_metadata(content)

    # 3. Initialize Detection Case record
    case = DetectionCase(
        filename=filename,
        storage_path="",  # Temporary placeholder until saved
        file_hash=metadata.file_hash,
        file_size_bytes=file_size,
        mime_type=mime_type,
        duration_seconds=metadata.duration,
        sample_rate=metadata.sample_rate,
        channels=metadata.channels,
        status="PROCESSING",
    )
    db.add(case)
    await db.flush()  # Generate case.id

    try:
        # 4. Store the audio file securely
        saved_path = AudioStorageService.save_audio(case.id, filename, content)
        case.storage_path = str(saved_path)

        # 5. Invoke ML Detection Service
        detection_service = get_detection_service()
        dto = await detection_service.detect(
            audio_path=saved_path,
            filename=filename,
            mime_type=mime_type,
            file_size_bytes=file_size,
            duration_seconds=metadata.duration,
        )

        # 6. Evaluate Security Decision & Prevention Policy
        synth_prob = None
        if dto.metadata_json and "synthetic_probability" in dto.metadata_json:
            synth_prob = float(dto.metadata_json["synthetic_probability"])
        elif dto.prediction == PredictionEnum.SYNTHETIC:
            synth_prob = float(dto.confidence)
        else:
            synth_prob = float(round(1.0 - dto.confidence, 4))

        decision = SecurityDecisionEngine.evaluate(
            prediction=dto.prediction.value,
            synthetic_probability=synth_prob,
            risk_level=dto.risk_level.value,
            engine_type=dto.engine_type,
            extra_telemetry=dto.metadata_json,
        )

        meta_payload = dict(dto.metadata_json or {})
        meta_payload["decision"] = decision.model_dump()
        meta_payload["synthetic_probability"] = synth_prob

        # 7. Persist Detection Result
        result = DetectionResult(
            detection_case_id=case.id,
            engine_type=dto.engine_type,
            prediction=dto.prediction.value,
            confidence=dto.confidence,
            risk_level=dto.risk_level.value,
            model_version=dto.model_version,
            processing_time_ms=dto.processing_time_ms,
            attack_type=dto.attack_type,
            explanation=dto.explanation,
            spectral_artifacts=dto.spectral_artifacts,
            metadata_json=meta_payload,
        )
        case.status = "COMPLETED"
        db.add(result)
        await db.commit()
        await db.refresh(result)

        return build_detection_result_response(result)

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
        result_dto = build_detection_result_response(c.result) if c.result else None
        items.append(
            DetectionCaseSummaryResponse(
                id=c.id,
                filename=c.filename,
                file_size_bytes=c.file_size_bytes,
                mime_type=c.mime_type,
                duration_seconds=c.duration_seconds,
                sample_rate=c.sample_rate,
                channels=c.channels,
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

    result_dto = build_detection_result_response(case.result) if case.result else None

    return DetectionCaseDetailResponse(
        id=case.id,
        filename=case.filename,
        file_hash=case.file_hash,
        file_size_bytes=case.file_size_bytes,
        mime_type=case.mime_type,
        duration_seconds=case.duration_seconds,
        sample_rate=case.sample_rate,
        channels=case.channels,
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


@router.get(
    "/{case_id}/report",
    response_model=DetectionEvidenceReportResponse,
    summary="Get structured, deterministic audit evidence report for a detection case",
)
async def get_detection_report(
    case_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a deterministic machine-readable audit evidence report
    from persisted DetectionCase and DetectionResult records.
    """
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
            detail=f"Detection case '{case_id}' not found for report generation."
        )

    return AuditReportBuilder.build_report(case)
