"""
Unified Multimodal Risk Assessment API Endpoints.
"""

from fastapi import APIRouter, status
from app.schemas.multimodal import MultimodalAssessmentRequest, MultimodalAssessmentResponse
from app.services.multimodal_risk_engine import get_multimodal_risk_engine

router = APIRouter()


@router.post(
    "/evaluate",
    response_model=MultimodalAssessmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate Multimodal Threat Level",
    description="Fuses acoustic anti-spoofing telemetry, semantic fraud intent, and biometric speaker verification.",
)
async def evaluate_multimodal_risk(request: MultimodalAssessmentRequest):
    engine = get_multimodal_risk_engine()
    return engine.evaluate(
        acoustic=request.acoustic,
        semantic=request.semantic,
        speaker=request.speaker,
        context=request.context,
    )
