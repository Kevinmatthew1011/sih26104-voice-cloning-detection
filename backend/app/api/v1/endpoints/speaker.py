"""
Speaker Verification and Impersonation Prevention Endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Form, File, UploadFile, HTTPException, status
from app.schemas.speaker_verification import (
    SpeakerEnrollmentResponse,
    SpeakerVerificationResponse,
    EnrolledSpeakerDTO,
)
from app.services.speaker_verification_service import get_speaker_verification_service
from app.services.audio_validator import AudioValidator

router = APIRouter()


@router.post(
    "/enroll",
    response_model=SpeakerEnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enroll Speaker Voice Profile",
    description="Extracts biometric acoustic-spectral embedding and registers an enrolled identity profile.",
)
async def enroll_speaker(
    speaker_id: str = Form(..., description="Unique speaker identifier (e.g. SPK_ALICE_01)"),
    speaker_name: str = Form(..., description="Display name or role (e.g. Alice - CFO)"),
    file: UploadFile = File(..., description="Reference enrollment audio sample (WAV, MP3, FLAC, WebM)"),
):
    try:
        content, _, _ = await AudioValidator.validate_file_content(file)
    except HTTPException:
        await file.seek(0)
        content = await file.read()

    if not content or len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty audio payload provided.",
        )

    service = get_speaker_verification_service()
    try:
        result = service.enroll(
            speaker_id=speaker_id.strip(),
            speaker_name=speaker_name.strip(),
            audio_source=content,
        )
        return result
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Enrollment failed: {str(e)}",
        )


@router.post(
    "/verify",
    response_model=SpeakerVerificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify Speaker Identity Against Enrolled Profile",
    description="Compares test voice sample against enrolled identity embedding to detect human impersonation.",
)
async def verify_speaker(
    speaker_id: str = Form(..., description="Enrolled speaker identifier claimed by the caller"),
    file: UploadFile = File(..., description="Incoming call audio sample"),
):
    try:
        content, _, _ = await AudioValidator.validate_file_content(file)
    except HTTPException:
        await file.seek(0)
        content = await file.read()

    if not content or len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty audio payload provided.",
        )

    service = get_speaker_verification_service()
    try:
        result = service.verify(speaker_id=speaker_id.strip(), audio_source=content)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Verification failed: {str(e)}",
        )


@router.get(
    "/enrolled",
    response_model=List[EnrolledSpeakerDTO],
    status_code=status.HTTP_200_OK,
    summary="List Enrolled Speakers",
    description="Returns registry of enrolled identities eligible for speaker verification.",
)
async def list_enrolled_speakers():
    service = get_speaker_verification_service()
    return service.list_speakers()


@router.delete(
    "/{speaker_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Enrolled Speaker",
    description="Removes a speaker profile from the enrolled registry.",
)
async def delete_enrolled_speaker(speaker_id: str):
    service = get_speaker_verification_service()
    success = service.delete_speaker(speaker_id.strip())
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Speaker '{speaker_id}' not found.",
        )
    return {"status": "DELETED", "speaker_id": speaker_id}
