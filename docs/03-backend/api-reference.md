# API Reference: SIH26104

## 1. Base URL & API Versioning

- **Base URL**: `http://localhost:8000/api/v1`
- **Interactive Documentation**: Swagger UI at `http://localhost:8000/docs`, ReDoc at `http://localhost:8000/redoc`

---

## 2. Endpoints Specification

### 2.1 Submit Audio for Detection
- **Path**: `POST /api/v1/detections`
- **Content-Type**: `multipart/form-data`
- **Rate Limit**: 10 requests / minute per client IP.

#### Form Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `file` | `UploadFile` (Binary) | **Yes** | Audio binary stream (`.wav`, `.mp3`, `.ogg`, `.flac`, `.m4a`, `.aac`, `.webm`, max 25 MB). |
| `input_source` | `string` | No | Source category: `"uploaded_file"` (default) or `"browser_microphone"`. |

#### Response (`201 Created`)
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "filename": "suspicious_audio.wav",
  "file_size_bytes": 1048576,
  "mime_type": "audio/wav",
  "sha256_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "prediction": "synthetic",
  "confidence": 0.9421,
  "risk_level": "high",
  "countermeasure_score": -2.7845,
  "synthetic_probability": 0.9421,
  "raw_ml_action": "BLOCK",
  "operational_action": "BLOCK",
  "decision_reason": "High probability of AI voice cloning detected by AASIST deep learning engine.",
  "capture_domain_reliability": "trusted_file",
  "input_source": "uploaded_file",
  "model_version": "aasist-v1",
  "created_at": "2026-08-28T12:00:00Z",
  "quality": {
    "snr_db": 28.45,
    "clipping_ratio": 0.0001,
    "rms_energy": 0.0842,
    "spectral_centroid_hz": 2450.2,
    "zero_crossing_rate": 0.0612,
    "dynamic_range_db": 42.1,
    "bandwidth_hz": 3800.0
  },
  "windows": [
    {
      "window_index": 0,
      "start_sec": 0.0,
      "end_sec": 4.0375,
      "synthetic_probability": 0.9521,
      "countermeasure_score": -2.9912,
      "is_anomaly": true
    }
  ]
}
```

---

### 2.2 List Detection Cases
- **Path**: `GET /api/v1/detections`
- **Query Parameters**:
  - `skip` (`integer`, default: 0)
  - `limit` (`integer`, default: 50, max: 100)
- **Response (`200 OK`)**: Array of `DetectionResponseDTO` objects ordered by creation date descending.

---

### 2.3 Get Detection Case by ID
- **Path**: `GET /api/v1/detections/{id}`
- **Path Parameter**: `id` (UUID string)
- **Response (`200 OK`)**: Single `DetectionResponseDTO`.
- **Errors**: `404 Not Found` if UUID does not exist; `422 Unprocessable Content` if UUID is malformed.

---

### 2.4 Download Cryptographic Audit Evidence Report
- **Path**: `GET /api/v1/detections/{id}/report`
- **Path Parameter**: `id` (UUID string)
- **Response (`200 OK`)**: Structured JSON audit evidence receipt.

#### Sample Audit Report Output
```json
{
  "report_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "detection_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "timestamp": "2026-08-28T12:00:00Z",
  "integrity_fingerprint": {
    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "file_size_bytes": 1048576,
    "mime_type": "audio/wav",
    "filename": "suspicious_audio.wav"
  },
  "forensic_verdict": {
    "prediction": "synthetic",
    "confidence": 0.9421,
    "risk_level": "high",
    "synthetic_probability": 0.9421,
    "countermeasure_score": -2.7845,
    "model_version": "aasist-v1"
  },
  "operational_policy": {
    "raw_ml_action": "BLOCK",
    "final_action": "BLOCK",
    "decision_reason": "High probability of AI voice cloning detected by AASIST deep learning engine.",
    "capture_domain_reliability": "trusted_file",
    "input_source": "uploaded_file"
  },
  "acoustic_telemetry": {
    "snr_db": 28.45,
    "clipping_ratio": 0.0001,
    "rms_energy": 0.0842,
    "spectral_centroid_hz": 2450.2
  },
  "temporal_window_analysis": {
    "window_count": 1,
    "window_length_seconds": 4.0375,
    "hop_size_seconds": 2.01875,
    "windows": [...]
  }
}
```

---

### 2.5 Health Check
- **Path**: `GET /health`
- **Response (`200 OK`)**:
```json
{
  "status": "healthy",
  "environment": "production",
  "active_engine": "aasist",
  "version": "1.0.0"
}
```
