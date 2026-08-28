# Hackathon Live Demonstration Script: SIH26104

## 1. Demonstration Setup & Sequence

This document provides a three-part live demonstration script designed to showcase the capabilities of the **VOICE-GUARD (SIH26104)** platform to hackathon judges.

---

## 2. Live Demo Script

```mermaid
sequenceDiagram
    participant Presenter
    participant UI as VOICE-GUARD UI (/detect)
    participant Engine as AASIST & Decision Engine
    
    rect rgb(16, 185, 129, 0.15)
    note right of Presenter: DEMO 1: Genuine Human Voice Upload
    Presenter->>UI: Upload clean_bona.flac (Organic Human Voice)
    UI->>Engine: POST /api/v1/detections (input_source="uploaded_file")
    Engine-->>UI: P_synth = 0.0012, CM = +6.71, Action = ALLOW
    UI-->>Presenter: Displays: REAL SPEECH | LOW RISK | ALLOW (Green)
    end
    
    rect rgb(239, 68, 68, 0.15)
    note right of Presenter: DEMO 2: AI-Generated Voice Clone Upload
    Presenter->>UI: Upload clean_spoof.flac (Neural Vocoder Clone)
    UI->>Engine: POST /api/v1/detections (input_source="uploaded_file")
    Engine-->>UI: P_synth = 0.9984, CM = -6.44, Action = BLOCK
    UI-->>Presenter: Displays: SYNTHETIC | HIGH RISK | BLOCK (Red)
    end
    
    rect rgb(245, 158, 11, 0.15)
    note right of Presenter: DEMO 3: Live Browser Microphone Capture
    Presenter->>UI: Record live speech via browser microphone
    UI->>Engine: POST /api/v1/detections (input_source="browser_microphone")
    Engine-->>UI: Raw CM preserved, Domain: UNVALIDATED, Action = VERIFY
    UI-->>Presenter: Displays: MIC DOMAIN: UNVALIDATED | ACTION: VERIFY (MFA)
    end
```

---

## 3. Step-by-Step Presentation Points

### DEMO 1 — Genuine Human Speech Upload
- **Action**: Upload `backend/uploads/088b2c0c-ffce-43b4-9993-5055379c374b_clean_bona.flac`.
- **Expected Outcome**:
  - **Verdict**: `REAL SPEECH`
  - **Risk Rating**: `LOW RISK`
  - **Operational Action**: `ALLOW`
  - **Countermeasure Score**: Positive ($CM > +5.0$)
- **Talking Point**: *"AASIST directly inspects the raw waveform using SincNet filters. Natural glottal pulse timing and organic harmonic resonance yield a high positive countermeasure score, permitting the customer to proceed without friction."*

---

### DEMO 2 — AI-Generated Deepfake Audio Upload
- **Action**: Upload `backend/uploads/37a92068-d1b3-42b0-a2ac-c76d3caad80c_clean_spoof.flac`.
- **Expected Outcome**:
  - **Verdict**: `SYNTHETIC`
  - **Risk Rating**: `HIGH RISK`
  - **Operational Action**: `BLOCK`
  - **Countermeasure Score**: Negative ($CM < -5.0$, $P_{\text{synth}} \ge 0.70$)
- **Talking Point**: *"Even though the cloned voice sounds convincing to the human ear, SincNet and Heterogeneous Graph Attention detect sub-band phase discontinuities produced by the neural vocoder. The decision engine immediately blocks the transaction."*

---

### DEMO 3 — Live Browser Microphone Recording
- **Action**: Click **"Record Audio"**, speak for 4 seconds, and submit.
- **Expected Outcome**:
  - **Signal Quality**: `SIGNAL QUALITY: GOOD`
  - **Capture Domain**: `MIC DOMAIN: UNVALIDATED`
  - **Operational Action**: `VERIFY` (Secondary Multi-Factor Authentication Required)
- **Talking Point**: *"In live browser environments, consumer MEMS microphones and WebRTC automatic gain control introduce acoustic domain shift. Rather than falsely blocking a genuine customer, VOICE-GUARD's domain-aware policy preserves raw biometric evidence while safely prompting for secondary MFA."*
