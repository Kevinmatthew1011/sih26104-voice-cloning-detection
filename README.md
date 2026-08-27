# SIH26104 — AI-Powered Voice Cloning Detection & Forensic Prevention Platform

Production-grade forensic audio analysis and voice cloning defense system engineered for Smart India Hackathon (SIH 2026) Problem Statement **SIH26104**.

The platform inspects recorded and uploaded audio to detect synthetic speech, neural voice clones, and acoustic impersonation attacks. It combines deep graph spectral-temporal neural networks (**AASIST**), multi-window temporal localization, acoustic channel quality analysis, deterministic operational policy gating, and cryptographically fingerprinted audit reports.

---

## 🏛️ System Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             Next.js 16+ Web Console                              │
│   • Dashboard Overview (/)               • Audio Forensic Studio (/detect)       │
│   • Case Audit Log (/detections)         • Detailed Forensic Report (/detections/:id)│
└────────────────────────────────────────┬─────────────────────────────────────────┘
                                         │ HTTP / REST API (CORS & Security Headers)
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              FastAPI Backend Core                                │
│                                                                                  │
│   ┌──────────────────────────────────────────────────────────────────────────┐   │
│   │                        Security Ingestion Boundary                       │   │
│   │   • Token Bucket Rate Limiter (Process-Local, 10/min, burst 3)           │   │
│   │   • Streamed Chunk Reading & 25 MB Hard Limit (HTTP 413)                 │   │
│   │   • Format-Aware Magic-Byte Validation & Safe Decoder Probe (HTTP 400)   │   │
│   │   • Path-Sanitized Storage ({case_id}_{safe_name}) & Atomic Cleanup      │   │
│   │   • SHA-256 Cryptographic Audio Fingerprinting                           │   │
│   └─────────────────────────────────────┬────────────────────────────────────┘   │
│                                         │                                        │
│                                         ▼                                        │
│   ┌──────────────────────────────────────────────────────────────────────────┐   │
│   │                       Acoustic Quality & Energy Layer                    │   │
│   │   • Native Bandwidth Inspection (8 kHz Narrowband vs. Full-Band)         │   │
│   │   • Active-Speech vs. Silence Ratio & Sample Clipping Estimation         │   │
│   │   • Pre-Inference Silence Exclusion (-55 dBFS Low-Energy Gating)         │   │
│   └─────────────────────────────────────┬────────────────────────────────────┘   │
│                                         │                                        │
│                                         ▼                                        │
│   ┌──────────────────────────────────────────────────────────────────────────┐   │
│   │                       AASIST Neural Detection Engine                     │   │
│   │   • Process-Local Admission Controller (Concurrency=1, Timeout=5s, 503)  │   │
│   │   • 16 kHz Mono Standardized Resampling                                  │   │
│   │   • 64,600-sample (~4.04s) Windows with 75% Overlap (16,150-sample hop)  │   │
│   │   • Batched Forward Pass (Batch Size = 16) with CUDA OOM CPU Fallback    │   │
│   │   • Conservative Maximum File Aggregator (max_v1)                        │   │
│   │   • Approximate Suspicious Temporal Segment Localization                 │   │
│   └─────────────────────────────────────┬────────────────────────────────────┘   │
│                                         │                                        │
│                                         ▼                                        │
│   ┌──────────────────────────────────────────────────────────────────────────┐   │
│   │                     Decision & Prevention Engine (v1.0)                  │   │
│   │   • Raw ML Action: ALLOW (<0.50), VERIFY (0.50–0.69), BLOCK (>=0.70)     │   │
│   │   • Reliability Escalation: Degraded Channel -> Operational VERIFY       │   │
│   │   • Insufficient Active Speech (<5%) -> INCONCLUSIVE / NOT_EVALUATED     │   │
│   └─────────────────────────────────────┬────────────────────────────────────┘   │
│                                         │                                        │
│                                         ▼ (SQLAlchemy 2.0 Async ORM)             │
│   ┌──────────────────────────────────────────────────────────────────────────┐   │
│   │                      PostgreSQL 16 / SQLite Storage                      │   │
│   │   • detection_cases (Acoustic metadata, SHA-256, storage paths)          │   │
│   │   • detection_results (Decision DTO, quality flags, window telemetry)    │   │
│   └──────────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Key Capabilities & Highlights

1. **AASIST Deep Learning Core**: Powered by the end-to-end Spectro-Temporal Graph Attention Network (*AASIST*), evaluating raw audio waveforms with SincNet filters, RawNet2 encoders, and heterogeneous graph attention (0.80% EER on ASVspoof 2019 LA benchmark).
2. **75% Overlapping Multi-Window Temporal Analysis**: Slices audio up to 300 seconds (5 minutes) into 64,600-sample (~4.04s) windows with 16,150-sample (~1.01s) hops. Employs `max_v1` conservative aggregation to catch brief, localized synthetic voice inserts embedded within authentic speech.
3. **Acoustic Quality & Signal Reliability Gating**: Inspects native sampling rates, sample clipping, and frame-level speech activity. Pre-inference silence gating excludes empty audio before GPU execution, and degraded channels (e.g. 8 kHz narrowband) trigger operational step-up escalation without rewriting raw ML evidence.
4. **Decoupled Security Decision & Prevention Engine**:
   - Evaluates explicit synthetic probability into **ALLOW**, **VERIFY**, or **BLOCK** directives.
   - Distinctly isolates **Raw ML Evidence** from **Final Operational Actions**.
   - Emits structured incident response steps (e.g. multi-factor challenge, step-up verification, fraud escalation).
5. **Deterministic Audit Evidence Report v1.0**: Machine-readable JSON export providing forensic evidence integrity, SHA-256 cryptographic fingerprints, acoustic quality parameters, model version provenance, and legal/forensic operational disclaimers.
6. **Multi-Layered Security Hardening**: Streamed chunk-bounded uploads (25 MB max), format-aware magic-byte container validation, decoder probing, in-memory token bucket rate limiting with `Retry-After`, process-local inference admission control (503 backpressure), strict CORS, security headers (`nosniff`, `DENY`), and sanitized production error responses.

---

## ⚖️ Decision & Prevention Engine Policy

The Decision Engine separates the raw mathematical model output from the operational authorization action to guarantee safe, risk-aligned fraud prevention.

### Policy v1.0 Thresholds (Production Code: `app/services/decision_engine.py`)

| Metric / Condition | Threshold | Raw ML Action | Final Operational Action | Operational Directive |
| :--- | :---: | :---: | :---: | :--- |
| **Low Synthetic Probability** | $P_{\text{synth}} < 0.50$ | `ALLOW` | `ALLOW` (if reliable) | Voice authorization permitted. No strong synthetic indicators. |
| **Uncertainty / Suspicious Band** | $0.50 \le P_{\text{synth}} < 0.70$ | `VERIFY` | `VERIFY` | Suspicious characteristics detected. Secondary verification required. |
| **High Synthetic Probability** | $P_{\text{synth}} \ge 0.70$ | `BLOCK` | `BLOCK` (if reliable) | High-risk clone detected. Voice-only authorization strictly denied. |
| **Degraded Channel (e.g. 8 kHz, Clipping)** | Any $P_{\text{synth}}$ | Preserved | `VERIFY` | Degraded channel reduces ML certainty; escalates to out-of-band check. |
| **Insufficient Speech / All-Silence** | Active ratio $< 0.05$ | `NOT_EVALUATED` | `VERIFY` | Inconclusive assessment. Voice-only authorization deferred. |

> [!NOTE]
> `VERIFY` indicates that automated voice-only authorization is halted and an out-of-band secondary authentication factor (e.g. SMS OTP, TOTP, push challenge, or agent callback) must be completed before approving transactions.

---

## 🔬 Real-World Robustness & Channel Degradation

The platform has been experimentally audited across common real-world acoustic conditions:

- **Robust Channels (High Accuracy)**:
  - Lossless FLAC, MP3, OGG Vorbis, and Opus audio codecs.
  - Standard resampling (22.05 kHz, 44.1 kHz, 48 kHz down to 16 kHz).
  - Stereo-to-mono downmixing and moderate acoustic gain variations.
  - Mild additive background noise ($\ge 30\text{ dB SNR}$).
- **Degraded Channels (Transparent Warning & Operational Escalation)**:
  - **8 kHz / Narrowband Telephony**: High-frequency spectral cues are missing; flagged as `narrowband_audio_8khz` with operational action escalated to `VERIFY`.
  - **Severe Clipping & Heavy Noise**: High amplitude distortion ($\ge 1.0\%$ clipped samples) is flagged with reliability set to `degraded`.
  - **Sparse Speech & Leading Silence**: Pre-inference silence gating filters non-speech windows (-55 dBFS RMS), while active speech density analysis flags short utterances ($< 45\%$ active speech) to prevent silent dilution misses.

---

## 🛡️ Security Hardening & Ingestion Defenses

1. **Streamed Upload Limiting**: Chunked 64 KB streaming bounds memory consumption; rejects payloads $> 25\text{ MB}$ immediately with `HTTP 413 Payload Too Large`.
2. **Format-Aware Magic Bytes & Decoder Probes**: Inspects binary container headers (WAV `RIFF...WAVE`, FLAC `fLaC`, OGG `OggS`, WebM EBML, MP3 ID3/MPEG sync, M4A/AAC `ftyp`/ADTS) and validates stream decodability before database records or disk files are created (rejects fakes with `HTTP 400 Bad Request`).
3. **Atomic Failure Cleanup**: Deletes newly created audio uploads if subsequent inference or database operations encounter an error, preventing orphan disk accumulation.
4. **Process-Local Rate Limiting**: In-memory token bucket on `POST /api/v1/detections` (10 requests/min, burst 3) and `GET /report` (30 requests/min) returning `HTTP 429` with `Retry-After`.
5. **Inference Admission Control**: Process-local concurrency limiter (`concurrency=1`, `timeout=5.0s`) around AASIST GPU forward passes; returns `HTTP 503 Service Unavailable` with `Retry-After: 5` under load.
6. **Security Headers & CORS**: Injects `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, and restricts CORS to authorized origins.
7. **Production Error Sanitization**: Masks stack traces, database strings, and local filesystem paths in non-debug mode.

---

## 📁 Repository Structure

```text
.
├── backend/
│   ├── alembic/                      # Database schema migrations
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── endpoints/
│   │   │   │   ├── detections.py     # Upload, history, case detail, report, audio streaming
│   │   │   │   └── health.py         # System health & engine telemetry
│   │   │   └── router.py
│   │   ├── core/                     # Security & admission controls
│   │   │   ├── admission.py          # AASIST inference admission controller & 503 backpressure
│   │   │   ├── rate_limiter.py       # In-memory token bucket rate limiter
│   │   │   └── security_headers.py   # HTTP security headers middleware
│   │   ├── ml/                       # AASIST & Baseline Machine Learning Engines
│   │   │   ├── aasist_inference.py   # Multi-window batched inference & quality analysis
│   │   │   ├── aasist_model.py       # PyTorch Spectro-Temporal Graph Attention Network
│   │   │   ├── classifier.py         # Scikit-learn MFCC baseline classifier
│   │   │   └── features.py           # 88-D acoustic feature extraction
│   │   ├── models/                   # SQLAlchemy ORM models (DetectionCase, DetectionResult)
│   │   ├── schemas/                  # Pydantic validation schemas & DTOs
│   │   ├── services/
│   │   │   ├── audio_metadata.py     # SHA-256 hashing & metadata inspection
│   │   │   ├── audio_quality.py      # Bandwidth, clipping & active-speech density analysis
│   │   │   ├── audio_validator.py    # Streamed chunk limits & container validation
│   │   │   ├── decision_engine.py    # Policy v1.0 Decision Engine (ALLOW / VERIFY / BLOCK)
│   │   │   ├── report_service.py     # Forensic Audit Evidence Report v1.0 builder
│   │   │   └── storage.py            # UUID path-isolated disk storage & atomic cleanup
│   │   ├── config.py                 # Pydantic application settings
│   │   └── main.py                   # FastAPI initialization & error handlers
│   ├── tests/                        # 106 automated unit, regression & security tests
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── detect/page.tsx       # Interactive audio upload & recording studio
│   │   │   ├── detections/
│   │   │   │   ├── page.tsx          # Audit history with search & risk filters
│   │   │   │   └── [id]/page.tsx     # Case inspection, waveform & evidence report download
│   │   │   ├── layout.tsx            # Dark cyber forensic theme layout
│   │   │   └── page.tsx              # Analytics dashboard & quick scan launcher
│   │   ├── components/               # UI components (Waveform, Gauges, Badges, Dropzone)
│   │   └── lib/                      # API client, TypeScript contracts, formatters
│   ├── Dockerfile
│   └── package.json
├── models/                           # Trained model artifact directory (.gitignored)
│   └── aasist/                       # AASIST.pth weights checkpoint & configuration
├── docker-compose.yml                # Multi-container full-stack orchestration
└── README.md
```

---

## ⚡ Quick Start & Setup

### Option A: Using Docker Compose (Full Stack)

```bash
# 1. Clone the repository
git clone https://github.com/Kevinmatthew1011/sih26104-voice-cloning-detection.git
cd sih26104-voice-cloning-detection

# 2. Configure environment
cp .env.example .env

# 3. Ensure AASIST weights are placed in models/aasist/AASIST.pth (if using AASIST engine)

# 4. Build and start services (Postgres + FastAPI + Next.js)
docker compose up --build
```

Access:
- **Frontend Web Console**: `http://localhost:3000`
- **FastAPI Backend REST API**: `http://localhost:8000`
- **Interactive Swagger Docs**: `http://localhost:8000/docs`

---

### Option B: Local Development Setup

#### 1. Backend Setup (FastAPI & PyTorch)

```bash
cd backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations (or run backend, which auto-initializes tables)
alembic upgrade head

# Run backend test suite (106 tests)
pytest -v

# Start FastAPI server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 2. Frontend Setup (Next.js 16 App Router)

```bash
cd frontend

# Install Node dependencies
npm install

# Start Next.js development server
npm run dev
```

Visit `http://localhost:3000` in your web browser.

---

## 🎬 Hackathon Live Demo Workflow

To demonstrate the full detection and prevention lifecycle to judges:

1. **Scenario A: Authentic Human Speech**
   - Upload a clean genuine audio recording.
   - Result: `REAL` | `Low Risk` | `ALLOW` | `Reliable Input` ($P_{\text{synth}} < 0.30$).
2. **Scenario B: Neural Cloned / Deepfake Voice**
   - Upload an AI voice clone (e.g. ElevenLabs, VITS, Bark).
   - Result: `SYNTHETIC` | `High Risk` | `BLOCK` | `Reliable Input` ($P_{\text{synth}} \ge 0.70$).
3. **Scenario C: Localized Voice Insertion (Long Recording)**
   - Upload a 30–60s audio file containing a short 4s cloned phrase embedded in genuine speech.
   - Result: Multi-Window AASIST isolates the suspicious window, highlights the approximate temporal interval (e.g. `approx. 12.1s – 16.1s`), and triggers `BLOCK`.
4. **Scenario D: Degraded 8 kHz / Telephony Audio**
   - Upload an 8 kHz narrowband recording.
   - Result: Quality flag `narrowband_audio_8khz` triggers `Degraded Channel` advisory, raw ML evidence is preserved, and final operational action is escalated to `VERIFY`.
5. **Scenario E: Silence / Insufficient Speech**
   - Upload an empty audio file or pure background noise.
   - Result: Pre-inference gating excludes silence windows; status becomes `INCONCLUSIVE` | `Risk Not Assessed` | `NOT_EVALUATED` | `VERIFY`.
6. **Scenario F: Forensic Audit Evidence Report**
   - Open the **Evidence & Audit Report** tab, verify the SHA-256 fingerprint, view model provenance, and click **Download Evidence Report (JSON)** for regulatory record-keeping.

---

## ⚠️ System Limitations & Forensic Boundaries

- **Input Scope**: Analyzes uploaded, streamed, or browser-recorded audio files; does not operate as an in-line telecom hardware tap or PBX signaling interceptor.
- **Narrowband & Extreme Distortions**: Bandwidth-limited (8 kHz) audio, severe clipping ($>5\%$), and dense reverberation reduce neural spectral certainty; these cases are transparently flagged as `degraded` and require secondary identity verification.
- **Adversarial Audio**: While robust against common compression and gain changes, deep learning audio models remain theoretically vulnerable to targeted gradient-based adversarial perturbations.
- **Security Assessment Role**: The system provides automated forensic threat indicators and operational countermeasures; it does not constitute a standalone legal guarantee of identity without multi-factor verification.
- **Model Checkpoints**: The official `AASIST.pth` pre-trained checkpoint (~335 MB) is placed in `models/aasist/AASIST.pth` and is tracked separately from Git source control.

---

## 📄 License & Attribution

Developed for the Smart India Hackathon (SIH 2026) under Problem Statement **SIH26104**.
AASIST architecture reference: *Jung et al., "AASIST: Audio Anti-Spoofing using Integrated Spectro-Temporal Graph Attention Networks," Interspeech 2022*.
