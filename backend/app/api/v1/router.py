from fastapi import APIRouter
from app.api.v1.endpoints import detections, health, physical_collection

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(detections.router, prefix="/detections", tags=["Detections"])
api_router.include_router(physical_collection.router, prefix="/collection", tags=["Physical Collection"])
