# DetectionCase Model Specification: SIH26104

## 1. ORM Model Definition (`backend/app/models/detection_case.py`)

The `DetectionCase` class represents the central audit record for every analyzed audio stream:

```python
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, BigInteger, Text, JSON
from app.db.base import Base

class DetectionCase(Base):
    __tablename__ = "detection_cases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    filename = Column(String(255), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    mime_type = Column(String(50), nullable=False)
    sha256_hash = Column(String(64), nullable=False, index=True)
    
    prediction = Column(String(20), nullable=False)
    confidence = Column(Float, nullable=False)
    risk_level = Column(String(20), nullable=False, index=True)
    
    countermeasure_score = Column(Float, nullable=False)
    synthetic_probability = Column(Float, nullable=False)
    
    raw_ml_action = Column(String(20), nullable=False)
    operational_action = Column(String(20), nullable=False, index=True)
    decision_reason = Column(Text, nullable=False)
    
    capture_domain_reliability = Column(String(30), nullable=False, default="trusted_file")
    input_source = Column(String(30), nullable=False, default="uploaded_file")
    
    model_version = Column(String(50), nullable=False, default="aasist-v1")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    quality_metrics = Column(JSON, nullable=True)
    window_telemetry = Column(JSON, nullable=True)
```

---

## 2. Field Specifications & Semantics

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID v4` String | Unique, non-sequential case identifier. |
| `filename` | String (255) | Sanitized original filename of the ingested recording. |
| `file_size_bytes` | BigInt | Exact size of the audio payload in bytes. |
| `mime_type` | String (50) | Validated container MIME type (e.g. `audio/wav`, `audio/webm;codecs=opus`). |
| `sha256_hash` | String (64) | SHA-256 integrity fingerprint computed over the raw ingested bytes. |
| `prediction` | String (20) | Binary classification label: `"real"` or `"synthetic"`. |
| `confidence` | Float (0.0–1.0) | Model probability estimate for the predicted class. |
| `risk_level` | String (20) | Categorical threat rating: `"low"`, `"medium"`, or `"high"`. |
| `countermeasure_score` | Float | Raw AASIST logit differential ($CM = \text{logit}_{\text{bona}} - \text{logit}_{\text{spoof}}$). |
| `synthetic_probability`| Float (0.0–1.0) | Top-$k$ aggregated synthetic probability ($P_{\text{synth}}$). |
| `raw_ml_action` | String (20) | Unconstrained machine learning policy action (`ALLOW`, `VERIFY`, `BLOCK`). |
| `operational_action` | String (20) | Final real-world enforcement action (`ALLOW`, `VERIFY`, `BLOCK`). |
| `decision_reason` | Text | Human-readable explanation justifying the policy decision. |
| `capture_domain_reliability`| String (30)| Domain verification flag (`trusted_file` vs `unvalidated`). |
| `input_source` | String (30) | Source origin: `uploaded_file` vs `browser_microphone`. |
| `quality_metrics` | JSON Object | Acoustic telemetry (SNR, clipping, RMS, spectral centroid). |
| `window_telemetry` | JSON Array | Array of temporal window timestamps and individual window anomaly scores. |
