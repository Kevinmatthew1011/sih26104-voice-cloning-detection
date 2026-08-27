from datetime import datetime
from enum import Enum
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, ConfigDict, Field


class PredictionEnum(str, Enum):
    REAL = "real"
    SYNTHETIC = "synthetic"
    REPLAY = "replay"
    UNKNOWN = "unknown"


class RiskLevelEnum(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CaseStatusEnum(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DetectionResultDTO(BaseModel):
    """Data Transfer Object returned by the Detection Service Interface."""
    engine_type: str
    prediction: PredictionEnum
    confidence: float = Field(..., ge=0.0, le=1.0)
    risk_level: RiskLevelEnum
    model_version: str
    processing_time_ms: int
    attack_type: Optional[str] = None
    explanation: Optional[str] = None
    spectral_artifacts: Optional[Dict[str, Any]] = None
    metadata_json: Optional[Dict[str, Any]] = None


class DetectionResultResponse(BaseModel):
    """Exact contract required by the specification."""
    id: str
    engine_type: str
    prediction: PredictionEnum
    confidence: float
    risk_level: RiskLevelEnum
    model_version: str
    processing_time_ms: int
    created_at: datetime
    
    # Optional extensions
    attack_type: Optional[str] = None
    explanation: Optional[str] = None
    spectral_artifacts: Optional[Dict[str, Any]] = None
    metadata_json: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class DetectionCaseSummaryResponse(BaseModel):
    """Summary item for detection case history list."""
    id: str
    filename: str
    file_size_bytes: int
    mime_type: str
    duration_seconds: Optional[float] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    status: CaseStatusEnum
    created_at: datetime
    updated_at: datetime
    result: Optional[DetectionResultResponse] = None

    model_config = ConfigDict(from_attributes=True)


class DetectionCaseDetailResponse(BaseModel):
    """Complete detail view for a detection case."""
    id: str
    filename: str
    file_hash: Optional[str] = None
    file_size_bytes: int
    mime_type: str
    duration_seconds: Optional[float] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    status: CaseStatusEnum
    created_at: datetime
    updated_at: datetime
    audio_url: str
    result: Optional[DetectionResultResponse] = None

    model_config = ConfigDict(from_attributes=True)


class DetectionCaseListResponse(BaseModel):
    """Paginated / filtered detection cases list."""
    total: int
    items: List[DetectionCaseSummaryResponse]
    limit: int
    skip: int

