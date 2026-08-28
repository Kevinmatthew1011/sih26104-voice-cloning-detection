# Pages & Components Guide: SIH26104

## 1. App Router Pages

### 1.1 Landing Page (`/frontend/src/app/page.tsx`)
- **Route**: `/`
- **Purpose**: Welcomes users, summarizes system capabilities, displays real-time architecture diagrams, and provides quick navigation to detection workflows.
- **Key Elements**: Hero section with dynamic feature pills, threat matrix preview, technology highlights, and call-to-action buttons.

### 1.2 Detection & Analysis Page (`/frontend/src/app/detect/page.tsx`)
- **Route**: `/detect`
- **Purpose**: Primary operational workspace for submitting audio to the detection engine.
- **Interactive Tabs**:
  - **Upload Audio File**: Drag-and-drop zone supporting `.wav`, `.mp3`, `.ogg`, `.flac`, `.m4a`, `.aac`, `.webm` up to 25 MB.
  - **Record Live Microphone**: Direct WebRTC microphone recorder with real-time waveform animation.
- **Real-Time Result Panel**: Renders detection outcomes immediately upon analysis completion, including threat level, operational action (`ALLOW`/`VERIFY`/`BLOCK`), synthetic probability gauge, audio quality scorecards, and temporal anomaly breakdown.

### 1.3 Detection History Ledger (`/frontend/src/app/detections/page.tsx`)
- **Route**: `/detections`
- **Purpose**: Historical audit trail of all previous voice verification cases.
- **Features**: Search by filename or UUID, risk level filtering (`low`, `medium`, `high`), operational action filtering (`ALLOW`, `VERIFY`, `BLOCK`), and pagination.

### 1.4 Case Detail & Evidence Page (`/frontend/src/app/detections/[id]/page.tsx`)
- **Route**: `/detections/[id]`
- **Purpose**: Deep forensic drill-down for security investigators and compliance officers.
- **Forensic Sections**:
  - **Header Card**: Displays Case ID, timestamp, filename, SHA-256 fingerprint, and threat status badges.
  - **Audio Player**: Interactive HTML5 audio player with seeking, playback speed control, and synchronized waveform display.
  - **Multi-Window Timeline**: Interactive bar chart displaying synthetic probability per 4.0375-second window. Clicking a window scrubs the audio player to that timestamp.
  - **Acoustic Quality Metrics**: Signal-to-Noise Ratio (SNR), clipping percentage, RMS energy, and spectral centroid.
  - **Cryptographic Audit Report Export**: One-click download button for `/api/v1/detections/{id}/report`.

---

## 2. Reusable UI Components (`/frontend/src/components/`)

| Component | Path | Description & Responsibilities |
| :--- | :--- | :--- |
| **`ThreatBadge.tsx`** | `components/ThreatBadge.tsx` | Renders standardized status badges for Risk Levels (`low`/`medium`/`high`), Operational Actions (`ALLOW`/`VERIFY`/`BLOCK`), and Capture Domain Reliability (`TRUSTED FILE` vs `SIGNAL QUALITY: GOOD / MIC DOMAIN: UNVALIDATED`). |
| **`Dropzone.tsx`** | `components/Dropzone.tsx` | Drag-and-drop file upload zone with client-side format validation, file size checks, and upload progress feedback. |
| **`MicRecorder.tsx`** | `components/MicRecorder.tsx` | WebRTC audio recorder using `navigator.mediaDevices.getUserMedia()`, Canvas 2D live frequency visualizer, timer, and recording state machine. |
| **`AudioPlayer.tsx`** | `components/AudioPlayer.tsx` | Full-featured audio player with seek bar, play/pause, time display, volume control, and visual playback cursor. |
| **`WindowTimeline.tsx`**| `components/WindowTimeline.tsx`| Interactive temporal window chart visualizing anomaly scores across time segments with clickable window inspection. |
