"""
Speech-to-Text (STT) Endpoints.
"""

from fastapi import APIRouter, File, UploadFile, HTTPException, status
from app.schemas.stt import TranscriptionResponse
from app.services.stt_service import get_stt_service, STTUnavailableError
from starlette.concurrency import run_in_threadpool
from app.services.audio_validator import AudioValidator

router = APIRouter()


@router.post(
    "/transcribe",
    response_model=TranscriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Transcribe Audio File or Chunk",
    description="Decodes an audio file or stream chunk and returns transcribed text with confidence score.",
)
async def transcribe_audio(
    file: UploadFile = File(..., description="Audio file (WAV, MP3, WebM, OGG, FLAC)"),
):
    AudioValidator.validate_filename_extension(file.filename or "")
    content, _, _ = await AudioValidator.validate_file_content(file)

    if not content or len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty audio payload provided.",
        )

    try:
        result = await run_in_threadpool(lambda: get_stt_service().transcribe(content))
        return result
    except STTUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Speech transcription failed: {str(e)}",
        )
