from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict
from app.schemas.detection import PredictionEnum, RiskLevelEnum, ActionEnum, SecurityDecisionDTO


class ReportCaseMetadata(BaseModel):
    case_id: str
    result_id: Optional[str] = None
    filename: str
    status: str
    created_at: datetime


class ReportAudioEvidence(BaseModel):
    file_size_bytes: int
    mime_type: str
    duration_seconds: Optional[float] = None
    sample_rate_hz: Optional[int] = None
    channels: Optional[int] = None
    file_sha256: Optional[str] = None


class ReportModelEvidence(BaseModel):
    engine_type: str
    model_version: str
    architecture: Optional[str] = None
    checkpoint_sha256: Optional[str] = None
    prediction: PredictionEnum
    confidence: float
    synthetic_probability: Optional[float] = None
    real_probability: Optional[float] = None
    cm_score: Optional[float] = None
    analyzed_duration_seconds: Optional[float] = None
    processing_latency_ms: int
    attack_type: Optional[str] = None
    explanation: Optional[str] = None
    scoring_note: Optional[str] = "Probability estimates represent uncalibrated model score transformations."


class ReportAuditProvenance(BaseModel):
    provenance: str  # "policy_evaluated" or "legacy_unprocessed"
    decision_evaluated: bool
    device_used: Optional[str] = None


class DetectionEvidenceReportResponse(BaseModel):
    """
    Deterministic Audit Evidence Report for a detection case.
    
    A pure projection of immutable persisted database records without
    request-time timestamps or runtime state injection.
    """
    report_version: str = "v1.0"
    report_type: str = "machine_generated_security_analysis"
    case: ReportCaseMetadata
    audio_evidence: ReportAudioEvidence
    model_evidence: Optional[ReportModelEvidence] = None
    security_decision: Optional[SecurityDecisionDTO] = None
    audit: ReportAuditProvenance
    limitations: List[str] = [
        "This report is a machine-generated automated security assessment and audit evidence summary.",
        "Probability scores represent uncalibrated model estimates and do not reflect definitive biometric identification.",
        "Performance may vary under domain shift, acoustic noise, lossy codecs, and unseen attack vectors.",
        "This report does not constitute certified legal testimony or definitive judicial attribution."
    ]

    model_config = ConfigDict(from_attributes=True)
