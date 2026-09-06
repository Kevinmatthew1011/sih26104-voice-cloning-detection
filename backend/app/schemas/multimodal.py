from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field


class OverallRiskEnum(str, Enum):
    LOW = "LOW"
    VERIFY = "VERIFY"
    HIGH = "HIGH"
    UNASSESSED = "UNASSESSED"


class RecommendedActionEnum(str, Enum):
    ALLOW = "allow"
    VERIFY = "verify"
    BLOCK = "block"
    ALERT_HUMAN_OPERATOR = "alert_human_operator"


class AcousticEvidence(BaseModel):
    status: str = Field(..., description="synthetic_detected, likely_genuine, inconclusive, unanalyzed")
    synthetic_probability: Optional[float] = Field(None, ge=0.0, le=1.0)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    engine: str = Field(default="AASIST", description="Detection engine used")
    channel_reliability: str = Field(default="CLEAN", description="Acoustic channel condition")


class SemanticEvidence(BaseModel):
    risk: str = Field(..., description="high, warning, no_indicators, unassessed")
    scam_probability: Optional[float] = Field(None, ge=0.0, le=1.0)
    primary_intent: str = Field(default="benign")
    reasons: List[str] = Field(default_factory=list)


class SpeakerEvidence(BaseModel):
    state: str = Field(
        default="NOT_ENROLLED",
        description="IDENTITY_MATCH, IDENTITY_MISMATCH, IDENTITY_UNCERTAIN, NOT_ENROLLED, INSUFFICIENT_AUDIO",
    )
    claimed_speaker_id: Optional[str] = None
    similarity_score: Optional[float] = None
    explanation: Optional[str] = None


class MultimodalAssessmentRequest(BaseModel):
    acoustic: Optional[AcousticEvidence] = None
    semantic: Optional[SemanticEvidence] = None
    speaker: Optional[SpeakerEvidence] = None
    context: Dict[str, Any] = Field(default_factory=dict)


class MultimodalAssessmentResponse(BaseModel):
    overall_risk: OverallRiskEnum
    recommended_action: RecommendedActionEnum
    confidence: float = Field(..., ge=0.0, le=1.0, description="Unified confidence score")
    headline: str
    explanation: str
    evidence_layers: Dict[str, Any]
    disclaimer: str = Field(
        default=(
            "Multimodal risk assessment synthesizes acoustic biometrics, conversational semantics, "
            "and identity verification. Low risk does not guarantee absolute safety. Identity is only "
            "verified against explicitly enrolled voice profiles."
        )
    )
