from typing import List, Optional
from pydantic import BaseModel, Field


class WordToken(BaseModel):
    word: str
    start: float = 0.0
    end: float = 0.0
    confidence: float = 1.0


class TranscriptionResponse(BaseModel):
    text: str = Field(..., description="Transcribed speech text")
    language: str = Field(default="en", description="Detected or requested language code")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Transcription confidence score")
    duration_seconds: float = Field(..., ge=0.0, description="Audio duration in seconds")
    engine: str = Field(default="local_stt", description="STT engine identifier")
    tokens: List[WordToken] = Field(default_factory=list, description="Word-level timestamps if available")
