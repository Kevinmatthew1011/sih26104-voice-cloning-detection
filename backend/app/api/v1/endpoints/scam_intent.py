"""
Scam Intent Analysis API Endpoints.
"""

from fastapi import APIRouter, HTTPException, status
from app.schemas.scam_intent import ScamIntentRequest, ScamIntentResponse
from app.services.scam_intent_service import get_scam_intent_service

router = APIRouter()


@router.post(
    "/analyze-intent",
    response_model=ScamIntentResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze Scam Intent in Audio Transcript",
    description="Evaluates semantic fraud cues using calibrated multi-class ML classification and explainable rule heuristics.",
)
async def analyze_intent(request: ScamIntentRequest):
    service = get_scam_intent_service()
    if request.text:
        return service.analyze_text(request.text)
    elif request.messages:
        return service.analyze_messages(request.messages)
    else:
        return service.analyze_text("")
