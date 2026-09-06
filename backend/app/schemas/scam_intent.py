from typing import List, Dict, Optional
from pydantic import BaseModel, Field


class ScamIntentRequest(BaseModel):
    text: Optional[str] = Field(None, description="Full transcript text to analyze")
    messages: Optional[List[str]] = Field(None, description="List of sequential transcript messages")


class ScamIntentResponse(BaseModel):
    scam_probability: float = Field(..., ge=0.0, le=1.0, description="Raw, uncalibrated winning scam-class probability")
    risk_level: str = Field(..., description="Risk category: no_indicators, warning, high, unassessed")
    primary_intent: str = Field(..., description="Top identified intent class")
    intent_scores: Dict[str, float] = Field(default_factory=dict, description="Class probabilities across categories")
    detected_triggers: List[str] = Field(default_factory=list, description="Explainable matched heuristic triggers")
    model_version: str = Field(default="scam-intent-v1", description="Model version")
    is_ml_inferred: bool = Field(default=True, description="Whether ML inference was executed")
