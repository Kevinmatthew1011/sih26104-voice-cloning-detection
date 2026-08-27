import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from app.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DetectionCase(Base):
    __tablename__ = "detection_cases"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    filename = Column(String(255), nullable=False)
    storage_path = Column(String(512), nullable=False)
    file_hash = Column(String(64), nullable=True, index=True)
    file_size_bytes = Column(Integer, nullable=False, default=0)
    mime_type = Column(String(100), nullable=False, default="audio/wav")
    duration_seconds = Column(Float, nullable=True)
    sample_rate = Column(Integer, nullable=True)
    channels = Column(Integer, nullable=True)
    status = Column(String(30), nullable=False, default="PENDING", index=True)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    result = relationship(
        "DetectionResult",
        back_populates="case",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<DetectionCase id={self.id} filename={self.filename} status={self.status}>"


class DetectionResult(Base):
    __tablename__ = "detection_results"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    detection_case_id = Column(
        String(36),
        ForeignKey("detection_cases.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    engine_type = Column(String(50), nullable=False, index=True)
    prediction = Column(String(30), nullable=False, index=True)  # real, synthetic, replay, unknown
    confidence = Column(Float, nullable=False)  # 0.0 to 1.0
    risk_level = Column(String(20), nullable=False, index=True)  # low, medium, high
    model_version = Column(String(50), nullable=False)
    processing_time_ms = Column(Integer, nullable=False)
    
    # Extensible fields for AI/ML deep analysis
    attack_type = Column(String(100), nullable=True)  # e.g., "diffusion_tts", "neural_vocoder", "none"
    explanation = Column(Text, nullable=True)
    spectral_artifacts = Column(JSON, nullable=True)  # Acoustic anomaly scores
    metadata_json = Column(JSON, nullable=True)  # Generic extensible payload for ML features
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    # Relationships
    case = relationship("DetectionCase", back_populates="result")

    def __repr__(self) -> str:
        return f"<DetectionResult id={self.id} prediction={self.prediction} confidence={self.confidence}>"
