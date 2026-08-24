from datetime import datetime
from typing import Dict, Any
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    environment: str
    version: str
    database: str
    detection_engine: str
    model_version: str
    timestamp: datetime
    details: Dict[str, Any] = {}
