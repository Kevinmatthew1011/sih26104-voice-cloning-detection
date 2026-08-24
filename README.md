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
│  │   BaselineMLDetectionService   │  │
│  │  (MFCCs + Logistic Regression) │  │
│  └────────────────────────────────┘  │
│  ┌────────────────────────────────┐  │
│  │ Future: Teammate's Real Model  │  │
│  │ (Wav2Vec2, RawNet2, Whisper)   │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
```

---

## 🚀 Key Capabilities & Highlights

1. **Modular ML Architecture**: The ML detection layer is isolated behind an abstract base class (`BaseDetectionService`). Switch between mock simulation and real trained ML models using `DETECTION_ENGINE=mock` or `DETECTION_ENGINE=baseline`.
2. **Supervised ML Baseline Pipeline**: Complete MFCC and spectral envelope feature extractor (88-dimensional vector), standardized preprocessor (16 kHz, mono, 3.0s window), and scikit-learn classifier pipeline.
3. **Interactive Audio Visualizer & Player**: WebAudio waveform visualization, frequency spectrum dynamic simulation, playback scrubbing, and volume control.
4. **Multi-Source Audio Ingestion**: Drag-and-drop audio file upload (.wav, .mp3, .ogg, .flac, .m4a, .aac, .webm) and live in-browser microphone recording via `MediaRecorder`.
5. **Forensic Telemetry & Countermeasures**: Comprehensive threat matrix displaying biometric certainty, vocoder footprint score, harmonic phase coherence, and actionable security incident response guidance.
6. **Robust Database Layer**: PostgreSQL schema with automated Alembic migrations and async SQLAlchemy 2.0 ORM.

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
│   │   ├── ml/                       # Machine Learning Baseline Pipeline
│   │   │   ├── preprocessing.py      # Audio loading, resampling & 3s windowing
│   │   │   ├── features.py           # 88-dim MFCC + Spectral Extractor
│   │   │   ├── classifier.py         # StandardScaler + Logistic Regression
│   │   │   ├── inference.py          # Model inference engine
│   │   │   └── train.py              # CLI training & evaluation script
│   │   ├── models/
│   │   │   └── detection.py          # DetectionCase & DetectionResult models
│   │   ├── schemas/
│   │   │   ├── detection.py          # Pydantic response & request contracts
│   │   │   └── health.py
│   │   ├── services/
│   │   │   ├── detection/
│   │   │   │   ├── base.py           # Abstract Base Class for ML service
│   │   │   │   ├── mock_service.py   # Acoustic simulation engine
│   │   │   │   ├── baseline_service.py # Scikit-Learn baseline service
│   │   │   │   └── factory.py        # Dependency injection factory
│   │   │   ├── audio_validator.py    # Header signature & size validation
│   │   │   └── storage.py            # Local audio file persistence
│   │   ├── config.py                 # Pydantic settings & env loader
│   │   ├── database.py               # Async SQLAlchemy engine & sessionmaker
│   │   └── main.py                   # FastAPI application initialization
│   ├── tests/
│   │   ├── conftest.py               # Fixtures & in-memory test DB
│   │   ├── test_detections.py        # API tests for uploads & listing
│   │   ├── test_health.py            # Health check tests
│   │   └── test_ml_baseline.py       # ML unit & integration test suite
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
├── ml_data/                          # Clean dataset directory structure (git-tracked empty)
│   ├── train/
│   │   ├── real/
│   │   └── synthetic/
│   ├── validation/
│   └── test/
├── models/                           # Trained model artifact directory (.gitignored)
│   └── baseline-v1/                  # Contains model.joblib & metadata.json once trained
├── docs/
│   └── ml-baseline.md                # In-depth ML baseline documentation
├── docker-compose.yml                # Multi-container orchestration
├── .env.example                      # Root environment configuration
└── README.md
```

---

## ⚡ Quick Start

### Option A: Using Docker Compose (Full Stack)

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

# Run full test suite (API + ML Baseline)
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

## 🧠 ML Baseline Training & Usage

The repository provides a modular, reproducible baseline machine learning pipeline.

> [!NOTE]
> **Dataset Rule**: The repository does not include audio training data. You must add approved audio files into `ml_data/train/real/` and `ml_data/train/synthetic/` before running the training script.

### 1. Training the Model
```bash
cd backend
source .venv/bin/activate

# Train baseline model on approved dataset
python -m app.ml.train
```

When training completes, it generates:
- `models/baseline-v1/model.joblib`: Serialized StandardScaler + Logistic Regression model.
- `models/baseline-v1/metadata.json`: Model hyperparameters, evaluation metrics (Accuracy, Precision, Recall, F1), and training details.

### 2. Activating the Baseline Engine
Set in `.env`:
```bash
DETECTION_ENGINE=baseline
```

### 3. Baseline Pipeline Limitations:
- **3-Second Window**: Only the first 3.0 seconds (48,000 samples at 16 kHz) of an audio file are analyzed. Audio longer than 3 seconds is truncated.
- **Probability Estimates**: Output probabilities from `predict_proba()` represent raw model score estimates and are not calibrated confidence metrics.

For comprehensive ML documentation, architecture parameters, and research limitations, see [docs/ml-baseline.md](file:///home/kiddo/projects/sih26104-voice-cloning/docs/ml-baseline.md).

---

## 📡 REST API Documentation

### 1. Health Check
`GET /api/v1/health`
- Returns system operational status, active ML engine version, and database connectivity.

### 2. Audio Ingestion & Detection
`POST /api/v1/detections`
- **Content-Type**: `multipart/form-data`
- **Body**: `file`: Audio binary (`.wav`, `.mp3`, `.ogg`, `.flac`, `.m4a`, `.aac`, `.webm`)
- **Response Contract**:
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "prediction": "synthetic",
  "confidence": 0.942,
  "risk_level": "high",
  "model_version": "baseline-v1",
  "processing_time_ms": 185,
  "created_at": "2026-08-24T16:30:00Z",
  "attack_type": null,
  "explanation": "Baseline ML binary classification (Logistic Regression on 88 MFCC and spectral envelope descriptors)...",
  "spectral_artifacts": {
    "mfcc_feature_count": 88,
    "input_sample_rate_hz": 16000
  }
}
```
*Note: The `confidence` field returns the predicted class probability estimate ($0.0 - 1.0$) for the selected prediction from the active classifier.*

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

## 🔌 How to Replace Baseline with Teammate's Real ML Model

When your teammate develops an advanced neural network (e.g. Wav2Vec 2.0, RawNet2):

### Step 1: Create the Model Class
In `backend/app/services/detection/`, create `deep_ml_service.py` inheriting from `BaseDetectionService`:

```python
from pathlib import Path
from typing import Optional, Dict, Any
from app.services.detection.base import BaseDetectionService
from app.schemas.detection import DetectionResultDTO, PredictionEnum, RiskLevelEnum

class DeepMlDetectionService(BaseDetectionService):
    def __init__(self, weights_path: str = "models/deep_model.pt"):
        self.model_version = "wav2vec2-forensic-v1.0"

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "name": "SIH26104-DeepVoiceForensics",
            "version": self.model_version,
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
        # Preprocess, run forward pass, return DTO
        return DetectionResultDTO(
            prediction=PredictionEnum.SYNTHETIC,
            confidence=0.965,
            risk_level=RiskLevelEnum.HIGH,
            model_version=self.model_version,
            processing_time_ms=142,
            attack_type="Neural Voice Clone (Diffusion TTS)",
            explanation="Detected high-frequency phase discontinuities in upper formants.",
            spectral_artifacts={"vocoder_footprint_score": 0.94},
            metadata_json={"sample_rate": 16000}
        )
```

### Step 2: Register in `backend/app/services/detection/factory.py`
```python
if engine_name == "deep_ml":
    from app.services.detection.deep_ml_service import DeepMlDetectionService
    _detection_service_instance = DeepMlDetectionService()
```

### Step 3: Switch the Environment Variable
Set in `.env`:
```bash
DETECTION_ENGINE=deep_ml
```

**Zero changes required across frontend, API routes, or database models.**

---

## 🛡️ License & Acknowledgements
- Developed for **Smart India Hackathon 2026** (Problem Statement: **SIH26104**).
