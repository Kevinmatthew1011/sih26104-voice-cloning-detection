import json
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Depends
from fastapi.responses import JSONResponse

from app.services.physical_collection_service import PhysicalCollectionService
from app.schemas.physical_collection import (
    IngestionResponse,
    BalanceDashboardResponse,
)

router = APIRouter()
ROOT_DIR = Path(__file__).resolve().parents[5]
PROMPTS_FILE = ROOT_DIR / "ml_data" / "prompts" / "physical_collection_prompts.json"

_default_service = PhysicalCollectionService()


def get_physical_collection_service() -> PhysicalCollectionService:
    return _default_service


@router.get("/prompts", summary="Get Standardized Utterance Prompts")
async def get_prompts():
    """Returns the standardized 10-prompt set for physical acoustic speech collection."""
    if not PROMPTS_FILE.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompts file not found.",
        )
    with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@router.post("/physical-recording", response_model=IngestionResponse, summary="Ingest Physical Recording into Pool")
async def ingest_physical_recording(
    file: UploadFile = File(..., description="Audio file payload (WebM/Opus, OGG, WAV, AAC)"),
    ground_truth: str = Form(..., description="'real' or 'synthetic'"),
    human_identity: Optional[str] = Form(None, description="Pseudonymous speaker ID, e.g. HUMAN_SPK_05"),
    source_speaker_identity: Optional[str] = Form(None),
    source_id: Optional[str] = Form(None),
    parent_source_id: Optional[str] = Form(None),
    source_audio_sha256: Optional[str] = Form(None),
    generator_name: Optional[str] = Form(None),
    generator_version: Optional[str] = Form(None),
    attack_id: Optional[str] = Form(None),
    capture_type: str = Form("physical_browser_microphone"),
    capture_device_category: str = Form("laptop"),
    capture_device_name: Optional[str] = Form(None),
    playback_device: Optional[str] = Form(None),
    browser: Optional[str] = Form(None),
    browser_version: Optional[str] = Form(None),
    os_name: Optional[str] = Form(None),
    requested_constraints_json: Optional[str] = Form(None),
    applied_settings_json: Optional[str] = Form(None),
    media_recorder_mime_type: Optional[str] = Form(None),
    input_sample_rate: Optional[int] = Form(None),
    room_environment: Optional[str] = Form(None),
    capture_session_id: Optional[str] = Form(None),
    prompt_id: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    service: PhysicalCollectionService = Depends(get_physical_collection_service),
):
    """Ingests a genuine physical or physically recaptured recording into the staging pool with quality validation."""
    if ground_truth not in ["real", "synthetic"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ground_truth must be either 'real' or 'synthetic'.",
        )

    # Parse JSON constraints if provided
    requested_constraints = None
    if requested_constraints_json:
        try:
            requested_constraints = json.loads(requested_constraints_json)
        except Exception:
            pass

    applied_settings = None
    if applied_settings_json:
        try:
            applied_settings = json.loads(applied_settings_json)
        except Exception:
            pass

    # Read audio bytes
    audio_bytes = await file.read()
    filename = file.filename or "recording.webm"
    ext = Path(filename).suffix or ".webm"

    try:
        result = service.ingest_recording(
            audio_bytes=audio_bytes,
            file_extension=ext,
            ground_truth=ground_truth,
            human_identity=human_identity,
            source_speaker_identity=source_speaker_identity,
            source_id=source_id or filename,
            parent_source_id=parent_source_id,
            source_audio_sha256=source_audio_sha256,
            generator_name=generator_name,
            generator_version=generator_version,
            attack_id=attack_id,
            capture_type=capture_type,
            capture_device_category=capture_device_category,
            capture_device_name=capture_device_name,
            playback_device=playback_device,
            browser=browser,
            browser_version=browser_version,
            os_name=os_name,
            requested_constraints=requested_constraints,
            applied_settings=applied_settings,
            media_recorder_mime_type=media_recorder_mime_type,
            input_sample_rate=input_sample_rate,
            room_environment=room_environment,
            capture_session_id=capture_session_id,
            prompt_id=prompt_id,
            notes=notes,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {e}",
        )


@router.get("/balance-dashboard", response_model=BalanceDashboardResponse, summary="Get Dataset Balance Dashboard")
async def get_balance_dashboard(
    service: PhysicalCollectionService = Depends(get_physical_collection_service),
):
    """Returns dataset balance, speaker distributions, device counts, and confound flags."""
    return service.get_balance_dashboard()


@router.post("/propose-split", summary="Generate Split Proposal")
async def propose_split(
    service: PhysicalCollectionService = Depends(get_physical_collection_service),
):
    """Generates a candidate split proposal ensuring human speaker disjointness."""
    return service.propose_split_assignment()
