# Backend Test Suite Guide: SIH26104

## 1. Running the Test Suite

Execute the full backend test suite using `pytest`:

```bash
cd backend
source .venv/bin/activate
pytest
```

---

## 2. Test Module Breakdown (`backend/tests/`)

| Test Module | Coverage & Test Scenarios |
| :--- | :--- |
| **`test_aasist_service.py`** | AASIST neural network loading, SincNet tensor forward pass, device placement (CPU/CUDA), and error handling when checkpoint files are missing. |
| **`test_audio_decoder.py`** | PyAV stream decoding across `.wav`, `.mp3`, `.ogg`, `.flac`, `.webm`, 16 kHz Float32 resampling, and corrupted container handling. |
| **`test_audio_quality.py`** | SNR estimation, clipping sample detection, RMS energy, spectral centroid calculations, and legacy database record compatibility. |
| **`test_dataset_and_metrics.py`**| Dataset validation, SHA-256 duplicate detection, cross-split data leakage prevention, and EER / ROC-AUC calculation routines. |
| **`test_decision_engine.py`** | Three-tier policy thresholds ($P < 0.50, 0.50 \le P < 0.70, P \ge 0.70$), risk level mappings, and browser microphone domain overrides. |
| **`test_detections.py`** | API endpoint integration (`POST /api/v1/detections`, `GET /api/v1/detections`, `GET /api/v1/detections/{id}`), payload validation, and database persistence. |
| **`test_evidence_report.py`** | JSON audit report generation (`/report`), schema validation, and acoustic telemetry projections. |
| **`test_health.py`** | Health check probe (`GET /health`) and engine status verification. |
| **`test_ml_baseline.py`** | Baseline 88-D feature extraction, Logistic Regression training, serialized model saving, and inference. |
| **`test_multi_window_aasist.py`**| Overlapping temporal window segmentation (64,600 samples @ 50% hop), top-$k$ ($k=5$) worst-case risk aggregation, and short splice detection. |
| **`test_security_hardening.py`**| 25 MB stream size enforcement (HTTP 413), magic byte validation (HTTP 400), rate limiting (HTTP 429), path traversal sanitization, and UUID validation (HTTP 422). |
