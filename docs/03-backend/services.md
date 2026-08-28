# Backend Services Specification: SIH26104

## 1. Core Services Catalog (`backend/app/services/`)

The backend isolates distinct business and computational responsibilities into modular service classes:

| Service | File | Primary Responsibility |
| :--- | :--- | :--- |
| **`AudioValidator`** | `services/audio_validator.py` | Streaming 25 MB size enforcement, magic byte header verification, MIME validation, filename sanitization. |
| **`AudioDecoder`** | `services/audio_decoder.py` | PyAV (FFmpeg) stream decoding to Float32 NumPy arrays, in-memory resampling, audio duration probing. |
| **`AudioQualityAnalyzer`**| `services/audio_quality.py` | Acoustic forensic telemetry extraction (SNR, clipping percentage, RMS energy, spectral centroid, ZCR). |
| **`AASISTDetectionService`**| `services/detection/aasist_service.py`| Multi-window temporal segmentation, SincNet + Heterogeneous GAT inference, top-$k$ risk aggregation. |
| **`DecisionEngine`** | `services/decision_engine.py` | Three-tier policy threshold mapping and capture-domain safety rules. |
| **`EvidenceReportService`**| `services/evidence_report.py` | Structured JSON forensic audit receipt generation and database record projection. |
| **`DetectionServiceFactory`**| `services/detection/factory.py`| Factory pattern for dynamically instantiating detection engines (`aasist`, `baseline`, `mock`). |

---

## 2. Service Deep Dive

### 2.1 AudioValidator
Enforces non-blocking defense-in-depth upload validation:
- Reads file chunks in 64 KB increments using `file.read(65536)`.
- If cumulative bytes exceed `MAX_FILE_SIZE_BYTES` (25 MB), immediately raises `HTTPException(413, "File exceeds maximum allowed size of 25MB")`.
- Inspects the first 16 bytes for container magic headers:
  - `RIFF` $\to$ `audio/wav`
  - `OggS` $\to$ `audio/ogg`
  - `\x1a\x45\xdf\xa3` $\to$ `audio/webm`
  - `fLaC` $\to$ `audio/flac`
  - `ID3` or `\xff\xfb` $\to$ `audio/mpeg`
- Cleanses the filename using `os.path.basename` and strips directory traversal symbols (`../`).

### 2.2 AudioDecoder
Decodes compressed or fragmented audio using PyAV:
- Decodes arbitrary containers (`.webm`, `.ogg`, `.mp3`, `.m4a`, `.aac`, `.flac`, `.wav`) directly in memory without spawning external CLI subprocesses.
- Uses `av.AudioResampler(format='fltp', layout='mono', rate=16000)` to standardize audio to 16 kHz Float32 PCM.

### 2.3 AudioQualityAnalyzer
Computes forensic signal descriptors:
- **SNR Estimation**: Compares top 90th percentile signal frames against bottom 10th percentile noise floor frames.
- **Clipping Percentage**: Counts samples where $|x[n]| \ge 0.99$.
- **Spectral Descriptors**: Computes spectral centroid, spectral bandwidth, zero-crossing rate, and dynamic range in decibels.

### 2.4 DecisionEngine
Evaluates operational risk:
```python
if synth_prob < 0.50:
    raw_action = "ALLOW"
    risk_level = "low"
elif synth_prob < 0.70:
    raw_action = "VERIFY"
    risk_level = "medium"
else:
    raw_action = "BLOCK"
    risk_level = "high"

# Capture Domain Safety Override
if input_source == "browser_microphone":
    reliability = "unvalidated"
    final_action = "VERIFY"
    reason = "Browser microphone capture domain is unvalidated. Verification required to prevent domain-shift false blocks."
else:
    reliability = "trusted_file"
    final_action = raw_action
```
