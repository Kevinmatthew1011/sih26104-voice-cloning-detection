# System Requirements & Specifications: SIH26104

## 1. Functional Requirements

### 1.1 Audio Ingestion & File Handling
- **FR-1.1**: The platform MUST accept multi-format audio uploads supporting `.wav`, `.mp3`, `.ogg`, `.flac`, `.m4a`, `.aac`, and `.webm`.
- **FR-1.2**: The platform MUST support live browser microphone recording via standard WebRTC `MediaStreamRecording` API with client-side visual waveform feedback.
- **FR-1.3**: The platform MUST enforce a strict **25 MB maximum file upload size limit** via streaming chunk inspection before reading entire payloads into memory.
- **FR-1.4**: The platform MUST validate magic byte headers and reject non-audio/executable files with HTTP 400 Bad Request.

### 1.2 Audio Preprocessing & Quality Analysis
- **FR-2.1**: The platform MUST decode and resample all audio streams to mono, 16,000 Hz, Float32 format in-memory using PyAV / FFmpeg.
- **FR-2.2**: The platform MUST extract comprehensive acoustic telemetry: Signal-to-Noise Ratio (SNR), clipping ratio, RMS energy, spectral centroid, zero-crossing rate, dynamic range, and frequency bandwidth.
- **FR-2.3**: If total duration is shorter than 64,600 samples (4.0375 seconds), the preprocessor MUST wrap/tile the audio deterministically to reach minimum input length.

### 1.3 Machine Learning Inference & Multi-Window Analysis
- **FR-3.1**: The platform MUST execute inference using the official AASIST neural network checkpoint (`AASIST.pth`, 297,866 parameters).
- **FR-3.2**: For audio exceeding 4.0375 seconds, the inference engine MUST extract overlapping temporal segments with a **75% overlap (16,150 samples / ~1.01 seconds hop)**.
- **FR-3.3**: The platform MUST aggregate segment scores using conservative maximum risk aggregation (`max_v1`) with low-energy silence exclusion to reliably capture short cloned splices.
- **FR-3.4**: The system MUST return both raw logits, countermeasure score ($CM = \text{logit}_{\text{bonafide}} - \text{logit}_{\text{spoof}}$), and synthetic probability estimate ($P_{\text{synth}}$).

### 1.4 Decision Engine & Policy Enforcement
- **FR-4.1**: The decision engine MUST enforce a 3-tier risk threshold policy:
  - $P_{\text{synth}} < 0.50 \implies \text{ALLOW}$ (Low Risk)
  - $0.50 \le P_{\text{synth}} < 0.70 \implies \text{VERIFY}$ (Medium Risk)
  - $P_{\text{synth}} \ge 0.70 \implies \text{BLOCK}$ (High Risk)
- **FR-4.2**: For browser microphone captures, the engine MUST mark `capture_domain_reliability = unvalidated` and enforce a final operational action of `VERIFY` while preserving raw ML evidence.

### 1.5 Forensic Audit Trail & Reporting
- **FR-5.1**: Every detection MUST persist a SHA-256 integrity hash, temporal window breakdown, forensic signal telemetry, and decision provenance in the database.
- **FR-5.2**: The system MUST export structured cryptographic audit evidence reports (`/api/v1/detections/{id}/report`) for compliance audits and incident investigation.

---

## 2. Non-Functional Requirements

### 2.1 Performance & Latency
- **NFR-1.1**: Total end-to-end API response time for a 5-second audio clip MUST be $< 500 \text{ ms}$ on standard GPU/CPU hardware.
- **NFR-1.2**: Database query response time for detection history retrieval MUST be $< 50 \text{ ms}$.

### 2.2 Security & Resilience
- **NFR-2.1**: Token bucket rate limiting MUST restrict unauthenticated clients to **10 requests per minute (burst 3)** to mitigate DoS and model inversion attacks.
- **NFR-2.2**: PyTorch inference MUST execute within an `asyncio.to_thread` worker pool with concurrency admission gating to prevent compute starvation.
- **NFR-2.3**: Temporary audio files created during processing MUST be cleaned up deterministically in `finally` blocks to prevent disk exhaustion.

### 2.3 Compatibility & Standards
- **NFR-3.1**: Frontend MUST operate on modern evergreen browsers (Chrome $\ge 120$, Firefox $\ge 120$, Safari $\ge 17$, Edge $\ge 120$).
- **NFR-3.2**: Backend MUST run on Python 3.11+ / 3.14 on Linux/POSIX containers.

---

## 3. Technology Matrix

| Layer | Component | Version / Specification |
| :--- | :--- | :--- |
| **Frontend** | Next.js App Router | Next.js 15.x / React 19 / TypeScript 5.x |
| **Styling** | Tailwind CSS & Icons | Tailwind CSS v4, Lucide React |
| **Backend** | FastAPI Framework | FastAPI 0.115+, Uvicorn, Python 3.14 |
| **ML Engine** | PyTorch / AASIST | PyTorch 2.x, TorchAudio, NumPy 2.x |
| **Audio I/O** | PyAV & SoundFile | PyAV 14.x (FFmpeg 6/7 bindings), SoundFile |
| **Database** | SQLAlchemy Async | SQLite (Development) / PostgreSQL (Production) |
| **Validation** | Pydantic v2 | Pydantic 2.10+ with strict type enforcement |
