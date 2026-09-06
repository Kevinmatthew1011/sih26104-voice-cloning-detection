from fastapi import APIRouter
from app.api.v1.endpoints import (
    detections,
    health,
    physical_collection,
    stt,
    scam_intent,
    speaker,
    multimodal,
    webrtc,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(detections.router, prefix="/detections", tags=["Detections"])
api_router.include_router(physical_collection.router, prefix="/collection", tags=["Physical Collection"])
api_router.include_router(stt.router, prefix="/stt", tags=["Speech-to-Text"])
api_router.include_router(scam_intent.router, prefix="/semantic", tags=["Scam Intent"])
api_router.include_router(speaker.router, prefix="/speaker", tags=["Speaker Verification"])
api_router.include_router(multimodal.router, prefix="/multimodal", tags=["Multimodal Threat Engine"])
api_router.include_router(webrtc.router, prefix="/webrtc", tags=["WebRTC Signaling"])
