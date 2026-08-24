# SIH 2026: AI-Powered Real-Time Detection and Prevention of Voice Cloning Impersonation Attacks (SIH26104)

Production-grade full-stack forensic application engineered for Smart India Hackathon (SIH 2026) Problem Statement **SIH26104**.

---

## 🏛️ System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Next.js 16+ Frontend                            │
│  • Dashboard (/)              • Audio Forensic Scanner (/detect)       │
│  • Audit Log (/detections)    • Detailed Case Inspection (/detections/:id)│
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / Multipart Form Data & JSON
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          FastAPI Backend                               │
│  • Audio Validation & Storage     • REST API Endpoints (/api/v1)       │
│  • Alembic DB Migrations          • Case Lifecycle Management          │
└──────────────────┬─────────────────────────────────┬───────────────────┘
                   │                                 │
                   ▼ (Dependency Inversion)          ▼ (SQLAlchemy 2.0 Async)
┌──────────────────────────────────────┐   ┌─────────────────────────────┐
│    BaseDetectionService Interface    │   │     PostgreSQL 16 Engine    │
│  ┌────────────────────────────────┐  │   │  • detection_cases          │
│  │     MockDetectionService       │  │   │  • detection_results        │
│  │ (Acoustic heuristics, spectral │  │   └─────────────────────────────┘
│  │  discontinuity, latency mock)  │  │
│  └────────────────────────────────┘  │
│  ┌────────────────────────────────┐  │
│  │ Future: Teammate's Real Model  │  │
│  │ (Wav2Vec2, RawNet2, Whisper)   │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
```

---

## 🚀 Key Capabilities & Highlights

1. **Modular ML Architecture**: The ML detection layer is isolated behind an abstract base class (`BaseDetectionService`). The ML team can plug in their PyTorch/TensorFlow models with zero friction.
2. **Interactive Audio Visualizer & Player**: WebAudio waveform visualization, frequency spectrum dynamic simulation, playback scrubbing, and volume control.
3. **Multi-Source Audio Ingestion**: Drag-and-drop audio file upload (.wav, .mp3, .ogg, .flac, .m4a, .aac, .webm) and live in-browser microphone recording via `MediaRecorder`.
4. **Forensic Telemetry & Countermeasures**: Comprehensive threat matrix displaying biometric certainty, vocoder footprint score, harmonic phase coherence, and actionable security incident response guidance.
5. **Robust Database Layer**: PostgreSQL schema with automated Alembic migrations and async SQLAlchemy 2.0 ORM.

---

## 📁 Project Structure

```
.
├── backend/
│   ├── alembic/                      # Database migrations
│   │   ├── versions/
│   │   │   └── 001_initial_schema.py # Initial Postgres schema
│   │   └── env.py
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── endpoints/
│   │   │   │   ├── detections.py     # Upload, list, detail, audio stream
│   │   │   │   └── health.py         # Health check & engine telemetry
│   │   │   └── router.py
│   │   ├── models/
│   │   │   └── detection.py          # DetectionCase & DetectionResult models
│   │   ├── schemas/
│   │   │   ├── detection.py          # Pydantic response & request contracts
│   │   │   └── health.py
│   │   ├── services/
│   │   │   ├── detection/
│   │   │   │   ├── base.py           # Abstract Base Class for ML service
│   │   │   │   ├── mock_service.py   # Acoustic simulation engine
│   │   │   │   └── factory.py        # Dependency injection factory
│   │   │   ├── audio_validator.py    # Header signature & size validation
│   │   │   └── storage.py            # Local audio file persistence
│   │   ├── config.py                 # Pydantic settings & env loader
│   │   ├── database.py               # Async SQLAlchemy engine & sessionmaker
│   │   └── main.py                   # FastAPI application initialization
│   ├── tests/
│   │   ├── conftest.py               # Fixtures & in-memory test DB
│   │   ├── test_detections.py        # API tests for uploads & listing
│   │   └── test_health.py            # Health check tests
│   ├── Dockerfile
│   ├── pytest.ini
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── detect/page.tsx       # Live audio upload & recording studio
│   │   │   ├── detections/
│   │   │   │   ├── page.tsx          # Audit history with search & filters
│   │   │   │   └── [id]/page.tsx     # Deep forensic case inspection & waveform
│   │   │   ├── layout.tsx            # Root cyber dark layout & header/footer
│   │   │   ├── page.tsx              # Dashboard overview & recent incidents
│   │   │   └── globals.css
│   │   ├── components/
│   │   │   ├── AudioWaveformVisualizer.tsx
│   │   │   ├── ConfidenceGauge.tsx
│   │   │   ├── DetectionDropzone.tsx
│   │   │   ├── Navbar.tsx
│   │   │   ├── Footer.tsx
│   │   │   ├── RecentDetectionsTable.tsx
│   │   │   └── ThreatBadge.tsx
│   │   └── lib/
│   │       ├── api.ts                # Strongly typed backend API client
│   │       └── types.ts              # TypeScript domain types
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml                # Multi-container orchestration
├── .env.example                      # Root environment configuration
└── README.md
```

---

## ⚡ Quick Start

### Option A: Using Docker Compose (Recommended for Full Stack)

```bash
# 1. Clone the repository and navigate into it
cd sih26104-voice-cloning

# 2. Copy environment template
cp .env.example .env

# 3. Build and launch all services (Postgres + FastAPI + Next.js)
docker compose up --build
```

Access points:
- **Frontend Dashboard**: `http://localhost:3000`
- **FastAPI Backend**: `http://localhost:8000`
- **Interactive Swagger API Docs**: `http://localhost:8000/docs`
- **PostgreSQL Database**: `localhost:5432`

---

### Option B: Local Development (Without Docker)

#### 1. Backend Setup (FastAPI)

```bash
cd backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Run database migrations (or run backend, which creates tables automatically)
alembic upgrade head

# Run backend unit & integration tests
pytest -v

# Start FastAPI development server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 2. Frontend Setup (Next.js)

```bash
cd frontend

# Install dependencies
npm install

# Start Next.js development server
npm run dev
```

Visit `http://localhost:3000` in your browser.

---

## 📡 REST API Documentation

### 1. Health Check
`GET /api/v1/health`
- Returns system operational status, active ML engine version, and database connectivity.

### 2. Audio Ingestion & Detection
`POST /api/v1/detections`
- **Content-Type**: `multipart/form-data`
- **Body**: `file`: Audio binary (`.wav`, `.mp3`, `.ogg`, `.flac`, `.m4a`, `.aac`, `.webm`)
- **Response**:
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "prediction": "synthetic",
  "confidence": 0.942,
  "risk_level": "high",
  "model_version": "mock-v1",
  "processing_time_ms": 185,
  "created_at": "2026-08-24T16:30:00Z",
  "attack_type": "Neural Voice Conversion (Diffusion Vocoder)",
  "explanation": "Acoustic analysis revealed anomalous high-frequency harmonic phase discontinuities...",
  "spectral_artifacts": {
    "phase_coherence_anomaly": 0.88,
    "vocoder_footprint_score": 0.94
  }
}
```

### 3. Detection Case History
`GET /api/v1/detections?skip=0&limit=20&prediction=synthetic&risk_level=high&search=keyword`
- Returns paginated list of detection cases and verdicts.

### 4. Detection Case Details
`GET /api/v1/detections/{id}`
- Returns comprehensive case details, audio stream URL, and telemetry.

### 5. Stream Audio
`GET /api/v1/detections/{id}/audio`
- Serves the original uploaded audio file for browser playback.

---

## 🗄️ Database Schema Summary

### `detection_cases` Table
| Column | Type | Description |
|---|---|---|
| `id` | `VARCHAR(36)` (PK) | Unique UUID |
| `filename` | `VARCHAR(255)` | Original uploaded filename |
| `storage_path` | `VARCHAR(512)` | File path reference |
| `file_size_bytes` | `INTEGER` | File size in bytes |
| `mime_type` | `VARCHAR(100)` | Audio MIME type |
| `duration_seconds` | `FLOAT` | Estimated or exact duration |
| `status` | `VARCHAR(30)` | PENDING, PROCESSING, COMPLETED, FAILED |
| `created_at` | `TIMESTAMPTZ` | Case creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | Last update timestamp |

### `detection_results` Table
| Column | Type | Description |
|---|---|---|
| `id` | `VARCHAR(36)` (PK) | Unique UUID |
| `detection_case_id` | `VARCHAR(36)` (FK) | Reference to `detection_cases.id` (ON DELETE CASCADE) |
| `prediction` | `VARCHAR(30)` | `real`, `synthetic`, `replay`, `unknown` |
| `confidence` | `FLOAT` | Score between 0.0 and 1.0 |
| `risk_level` | `VARCHAR(20)` | `low`, `medium`, `high` |
| `model_version` | `VARCHAR(50)` | Active model version string |
| `processing_time_ms`| `INTEGER` | Inference latency in ms |
| `attack_type` | `VARCHAR(100)` | Classification (e.g. Diffusion Vocoder, Replay) |
| `explanation` | `TEXT` | Forensic reasoning text |
| `spectral_artifacts`| `JSON` | Extensible acoustic scores |
| `metadata_json` | `JSON` | Extensible feature payload |
| `created_at` | `TIMESTAMPTZ` | Result creation timestamp |

---

## 🔌 How to Replace Mock ML with the Real ML Model

When your teammate finishes training the AI/ML voice cloning detection model, follow these **3 simple steps**:

### Step 1: Create the Real ML Service Class
In `backend/app/services/detection/`, create `real_ml_service.py` inheriting from `BaseDetectionService`:

```python
from pathlib import Path
from typing import Optional, Dict, Any
from app.services.detection.base import BaseDetectionService
from app.schemas.detection import DetectionResultDTO, PredictionEnum, RiskLevelEnum

class RealMlDetectionService(BaseDetectionService):
    def __init__(self, weights_path: str = "models/voice_guard.pt"):
        # Load your PyTorch / ONNX / TensorFlow model here
        # self.model = load_model(weights_path)
        self.model_version = "voiceguard-resnet-v1.0"

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "name": "SIH26104-RealVoiceForensics",
            "version": self.model_version,
            "architecture": "Wav2Vec2 + Spectral Temporal Graph Anomaly Detector",
            "status": "ready"
        }

    async def detect(
        self,
        audio_path: Path,
        filename: str,
        mime_type: str,
        file_size_bytes: int,
        duration_seconds: Optional[float] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> DetectionResultDTO:
        # 1. Run audio preprocessing (e.g. librosa / torchaudio)
        # 2. Run model forward pass
        # 3. Map model outputs to the DTO contract:
        
        return DetectionResultDTO(
            prediction=PredictionEnum.SYNTHETIC, # or REAL / REPLAY
            confidence=0.965,
            risk_level=RiskLevelEnum.HIGH,
            model_version=self.model_version,
            processing_time_ms=142,
            attack_type="Neural Voice Clone (Diffusion TTS)",
            explanation="Detected high-frequency phase discontinuities in upper formants.",
            spectral_artifacts={"harmonic_distortion": 0.89},
            metadata_json={"sample_rate": 16000}
        )
```

### Step 2: Register in `backend/app/services/detection/factory.py`
```python
if engine_name == "real_ml":
    from app.services.detection.real_ml_service import RealMlDetectionService
    _detection_service_instance = RealMlDetectionService()
```

### Step 3: Switch the Environment Variable
Set in `.env`:
```bash
DETECTION_ENGINE=real_ml
```
**No API routes, database tables, or frontend components need to be modified!**

---

## 🛡️ License & Acknowledgements
- Developed for **Smart India Hackathon 2026** (Problem Statement: **SIH26104**).
