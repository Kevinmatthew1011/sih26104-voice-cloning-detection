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


class ActionEnum(str, Enum):
    ALLOW = "ALLOW"
    VERIFY = "VERIFY"
    BLOCK = "BLOCK"
    NOT_EVALUATED = "NOT_EVALUATED"


class SecurityDecisionDTO(BaseModel):
    action: ActionEnum
    decision_message: str
    synthetic_probability: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    policy_version: str = "v1.0"
    decision_source: str = "policy_v1.0"
    raw_ml_action: Optional[ActionEnum] = None
    final_operational_action: Optional[ActionEnum] = None
    analysis_reliability: Optional[str] = "reliable"
    quality_flags: List[str] = Field(default_factory=list)
    reason_codes: List[str] = Field(default_factory=list)
    recommended_steps: List[str] = Field(default_factory=list)


class WindowTelemetryDTO(BaseModel):
    """Raw model inference telemetry for an individual audio temporal window."""
    window_index: int
    start_seconds: float
    end_seconds: float
    rms_dbfs: Optional[float] = None
    active_fraction: Optional[float] = None
    activity_status: Optional[str] = "active"  # "active" | "low_energy" | "sparse_speech"
    aggregation_eligible: Optional[bool] = True
    synthetic_probability: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    real_probability: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    cm_score: Optional[float] = None
    prediction: Optional[PredictionEnum] = None


class SuspiciousSegmentDTO(BaseModel):
    """Merged contiguous time interval of elevated synthetic model activity."""
    segment_index: int
    start_seconds: float
    end_seconds: float
    peak_synthetic_probability: float = Field(..., ge=0.0, le=1.0)
    minimum_cm_score: float
    contributing_window_indices: List[int] = Field(default_factory=list)


class MultiWindowMetadataDTO(BaseModel):
    """Multi-window segmentation and aggregation audit telemetry."""
    analysis_mode: str  # "single_window" | "multi_window"
    window_count: int
    window_length_seconds: float = 4.0375
    hop_seconds: float = 1.009375
    overlap_fraction: float = 0.75
    aggregation_method: str
    aggregation_version: str = "v1.0"
    file_level_synthetic_probability: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    file_level_real_probability: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    file_level_cm_score: Optional[float] = None
    eligible_window_count: Optional[int] = None
    excluded_low_energy_window_count: Optional[int] = None
    analysis_status: Optional[str] = "completed"
    analysis_reliability: Optional[str] = "reliable"
    quality_flags: List[str] = Field(default_factory=list)
    audio_quality: Optional[Dict[str, Any]] = None
    suspicious_segments: List[SuspiciousSegmentDTO] = Field(default_factory=list)
    windows_persisted: Optional[List[WindowTelemetryDTO]] = None


class DetectionResultDTO(BaseModel):
    """Data Transfer Object returned by the Detection Service Interface."""
    engine_type: str = Field(..., description="Engine type: 'mock' | 'baseline' | 'aasist'")
    prediction: PredictionEnum
    confidence: float = Field(..., ge=0.0, le=1.0)
    risk_level: RiskLevelEnum
    model_version: str
    processing_time_ms: int
    attack_type: Optional[str] = None
    explanation: Optional[str] = None
    spectral_artifacts: Optional[Dict[str, Any]] = None
    metadata_json: Optional[Dict[str, Any]] = None
    action: Optional[ActionEnum] = None
    raw_ml_action: Optional[ActionEnum] = None
    final_operational_action: Optional[ActionEnum] = None
    analysis_status: Optional[str] = "completed"
    analysis_reliability: Optional[str] = "reliable"
    quality_flags: List[str] = Field(default_factory=list)
    audio_quality: Optional[Dict[str, Any]] = None
    decision_message: Optional[str] = None
    decision: Optional[SecurityDecisionDTO] = None


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
    action: Optional[ActionEnum] = None
    raw_ml_action: Optional[ActionEnum] = None
    final_operational_action: Optional[ActionEnum] = None
    analysis_status: Optional[str] = "completed"
    analysis_reliability: Optional[str] = "reliable"
    quality_flags: List[str] = Field(default_factory=list)
    audio_quality: Optional[Dict[str, Any]] = None
    decision_message: Optional[str] = None
    decision: Optional[SecurityDecisionDTO] = None

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

