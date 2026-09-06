from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field


class VerificationStateEnum(str, Enum):
    IDENTITY_MATCH = "IDENTITY_MATCH"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    IDENTITY_UNCERTAIN = "IDENTITY_UNCERTAIN"
    NOT_ENROLLED = "NOT_ENROLLED"
    INSUFFICIENT_AUDIO = "INSUFFICIENT_AUDIO"


class SpeakerEnrollmentResponse(BaseModel):
    speaker_id: str
    speaker_name: str
    embedding_dim: int
    duration_seconds: float
    status: str = "ENROLLED"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SpeakerVerificationResponse(BaseModel):
    speaker_id: str
    state: VerificationStateEnum
    similarity_score: Optional[float] = Field(None, ge=-1.0, le=1.0, description="Cosine similarity score")
    thresholds: Dict[str, float] = Field(
        default_factory=lambda: {"match_threshold": 0.75, "mismatch_threshold": 0.50}
    )
    explanation: str
    duration_seconds: float


class EnrolledSpeakerDTO(BaseModel):
    speaker_id: str
    speaker_name: str
    enrolled_at: str
    duration_seconds: float
    sample_count: int = 1
