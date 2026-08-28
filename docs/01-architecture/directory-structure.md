# Directory Structure & Organization: SIH26104

## 1. Current Repository Directory Structure

Below is the verified layout of the active SIH26104 codebase:

```
sih26104-voice-cloning/
├── .agents/                        # Agent skill configs and workflow rules
│   └── skills/                     # Specialized engineering skills
├── backend/                        # FastAPI backend application
│   ├── app/
│   │   ├── api/                    # API route definitions
│   │   │   └── v1/
│   │   │       ├── api.py          # V1 router aggregation
│   │   │       └── endpoints/      # detections.py, health.py
│   │   ├── core/                   # Application config and settings
│   │   │   └── config.py
│   │   ├── db/                     # Database setup and async session
│   │   │   ├── base.py
│   │   │   └── session.py
│   │   ├── ml/                     # ML modules: AASIST model, baseline, preprocessors
│   │   │   ├── aasist_model.py     # AASIST PyTorch architecture
│   │   │   ├── classifier.py       # Baseline Logistic Regression pipeline
│   │   │   ├── dataset.py          # Dataset validator & provenance loader
│   │   │   ├── features.py         # 88-D forensic feature extraction
│   │   │   ├── metrics.py          # Accuracy, EER, ROC-AUC metric calculations
│   │   │   ├── preprocessing.py    # Standardized 16 kHz mono preprocessor
│   │   │   └── train.py            # Baseline training script
│   │   ├── models/                 # SQLAlchemy database models (detection_case.py)
│   │   ├── schemas/                # Pydantic validation schemas (detection.py)
│   │   └── services/               # Core business logic services
│   │       ├── audio_decoder.py    # PyAV / FFmpeg robust stream decoder
│   │       ├── audio_quality.py    # Forensic telemetry analyzer (SNR, clipping, etc.)
│   │       ├── audio_validator.py  # File size, magic bytes, MIME validation
│   │       ├── decision_engine.py  # 3-Tier policy & capture-domain decision engine
│   │       ├── evidence_report.py  # Forensic audit report JSON generator
│   │       └── detection/          # Detection services
│   │           ├── aasist_service.py # AASIST multi-window detection service
│   │           ├── base.py         # BaseDetectionService abstract class
│   │           ├── baseline_ml.py  # Baseline ML detection service
│   │           ├── factory.py      # DetectionServiceFactory
│   │           └── mock.py         # Mock detection service for testing
│   ├── tests/                      # Pytest test suite (123 automated tests)
│   ├── uploads/                    # Temporary audio storage directory (gitignored)
│   ├── .venv/                      # Python 3.14 virtual environment
│   ├── pytest.ini                  # Pytest configuration
│   └── requirements.txt            # Python dependency specifications
├── datasets/                       # ASVspoof 2019 LA evaluation dataset (gitignored)
│   └── ASVspoof2019_LA/
├── docs/                           # Technical documentation system
├── experiments/                    # Local experimental runs & head checkpoints (gitignored)
│   └── mic_head_v1/                # Stage 3/4 classifier-head experimental artifacts
├── frontend/                       # Next.js 15 App Router web application
│   ├── src/
│   │   ├── app/                    # Next.js App Router pages
│   │   │   ├── detect/page.tsx     # Audio analysis & recording page
│   │   │   ├── detections/page.tsx # Detection case history ledger
│   │   │   ├── detections/[id]/    # Case detail & forensic evidence viewer
│   │   │   ├── layout.tsx          # Root navigation & UI shell
│   │   │   └── page.tsx            # Landing page
│   │   ├── components/             # Reusable UI components
│   │   │   ├── AudioPlayer.tsx     # Custom HTML5 waveform audio player
│   │   │   ├── DetectionCard.tsx   # Detection summary card
│   │   │   ├── Dropzone.tsx        # Drag-and-drop file upload zone
│   │   │   ├── MicRecorder.tsx     # WebRTC audio recording component
│   │   │   ├── ThreatBadge.tsx     # Risk level, operational action & domain badge
│   │   │   ├── WindowTimeline.tsx  # Multi-window risk score visualization
│   │   │   └── ui/                 # Core design system primitives
│   │   └── lib/                    # API client and utility helpers (api.ts, utils.ts)
│   ├── public/                     # Static assets and icons
│   ├── package.json                # Frontend dependencies
│   └── tsconfig.json               # TypeScript configuration
├── ml_data/                        # ML dataset directories for local baseline training (gitignored)
├── ml_eval/                        # Official AASIST benchmark evaluation scripts & weights
│   └── aasist/
│       ├── config/AASIST.conf      # Model architecture hyperparameters
│       ├── evaluate_aasist.py      # ASVspoof 2019 LA full evaluation script
│       ├── models/AASIST.py        # Official AASIST PyTorch implementation
│       ├── results/                # Official benchmark metrics (aasist_eval_metrics.json)
│       └── weights/AASIST.pth      # Official AASIST neural network weights (gitignored)
├── models/                         # Serialized baseline models (gitignored)
│   └── baseline-v1/
├── .env.example                    # Environment variable configuration template
├── .gitignore                      # Git exclusion rules
├── docker-compose.yml              # Multi-container orchestration specification
└── README.md                       # Main repository landing guide
```

---

## 2. Recommended Future Repository Organization

In future enterprise refactorings, machine learning evaluation scripts, datasets, and experiment logs can be consolidated into a unified top-level `ml/` namespace without altering backend runtime dependencies:

```
ml/ (Future Consolidated Namespace)
├── data/
│   ├── asvspoof/                   # Official ASVspoof protocols and audio
│   └── mic_domain/                 # Multi-condition physical microphone challenge pool
├── models/
│   ├── aasist/                     # AASIST architecture definitions & checkpoints
│   └── baseline/                   # Scikit-Learn baseline pipelines
├── experiments/
│   ├── stage3_head_adaptation/     # Head adaptation logs & weights
│   └── stage4_physical_eval/       # Physical capture validation results
├── evaluation/
│   ├── evaluate_asvspoof.py        # ASVspoof protocol evaluator
│   └── evaluate_mic_domain.py      # Physical microphone evaluator
└── cache/                          # Precomputed 160-D embedding cache
```

> [!NOTE]
> *No directory restructuring is performed as part of this documentation release to preserve absolute runtime and test compatibility.*
