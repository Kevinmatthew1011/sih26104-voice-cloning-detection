# Terminology & Glossary: SIH26104

This document defines the official scientific and engineering terminology used across the **VOICE-GUARD (SIH26104)** platform.

---

## 1. Machine Learning & Biometric Anti-Spoofing Terms

### AASIST
**Audio Anti-Spoofing using Integrated Spectro-Temporal Graph Attention Networks**. A deep neural network architecture designed for voice anti-spoofing that processes raw waveforms using SincNet filters and models spectral and temporal artifact graphs simultaneously.

### Bonafide (Organic / Real)
Authentic, live human speech produced directly by a human vocal tract without algorithmic synthesis, voice conversion, or tampering. (Class 0 in standard binary classification).

### Spoof (Synthetic / Cloned)
Artificially synthesized speech, including zero-shot Text-to-Speech (TTS), voice conversion (VC), deepfake voice clones, or spliced audio. (Class 1 in standard binary classification).

### Countermeasure (CM) Score
The raw scalar logit differential output produced by the detection model:
$$CM = \text{logit}_{\text{bonafide}} - \text{logit}_{\text{spoof}}$$
A large positive score indicates high confidence in bonafide/human speech. A negative score indicates high probability of synthetic/cloned speech.

### Synthetic Probability Estimate ($P_{\text{synth}}$)
The normalized probability estimate that an audio sample is synthetic:
$$P_{\text{synth}} = \frac{e^{\text{logit}_{\text{spoof}}}}{e^{\text{logit}_{\text{spoof}}} + e^{\text{logit}_{\text{bonafide}}}} = \frac{1}{1 + e^{CM}}$$
*Note: In this platform, probability values are model estimates and are not assumed to be perfectly calibrated posterior probabilities.*

### Equal Error Rate (EER)
The threshold-independent operating point where the **False Positive Rate (FPR / False Alarm on Bonafide)** equals the **False Negative Rate (FNR / Missed Spoof)**:
$$\text{FPR}(\theta^*) = \text{FNR}(\theta^*) = \text{EER}$$

### SincNet
A convolutional neural network front-end whose filter kernels are parameterized as sinc functions:
$$g[n, f_1, f_2] = 2f_2 \text{sinc}(2\pi f_2 n) - 2f_1 \text{sinc}(2\pi f_1 n)$$
It directly learns meaningful bandpass filter cut-offs ($f_1, f_2$) directly from raw audio samples instead of using fixed Mel filterbanks.

---

## 2. Audio Processing & Quality Telemetry Terms

### Multi-Window Inference
The process of dividing an audio recording of arbitrary duration into fixed-length, overlapping 4.0375-second segments (64,600 samples @ 16 kHz) with a $75\%$ overlap (16,150-sample / ~1.01s hop) to ensure dense temporal coverage and detect localized audio splices up to 300 seconds.

### `max_v1` Conservative Maximum Aggregation
A risk-aggregation strategy where the overall file synthetic probability is determined by the maximum synthetic probability ($P_{\text{synth}} = \max(P_w)$) and minimum countermeasure score ($CM = \min(CM_w)$) across all eligible speech windows, excluding low-energy / silence windows ($\text{RMS} < -55\text{ dBFS}$ or active fraction $< 0.05$).

### Signal-to-Noise Ratio (SNR)
The ratio of signal power to background noise power expressed in decibels (dB). In VOICE-GUARD, estimated via WADA-SNR / percentile energy partitioning.

### Clipping Ratio
The percentage of audio samples reaching or exceeding the maximum digital dynamic range ($\ge 0.99$ or $\le -0.99$), indicating microphone gain saturation.

### Spectral Centroid
The center of mass of the frequency spectrum, representing the perceived "brightness" or high-frequency energy distribution of the audio signal.

---

## 3. Architecture & Security Policy Terms

### Decision Engine
The deterministic policy evaluation service in [backend/app/services/decision_engine.py](file:///home/kiddo/projects/sih26104-voice-cloning/backend/app/services/decision_engine.py) that evaluates raw ML synthetic probabilities, audio quality telemetry, and capture domain context to determine operational security actions (`ALLOW`, `VERIFY`, `BLOCK`).

### Raw ML Action
The unconstrained decision produced purely from the synthetic probability threshold:
- $P_{\text{synth}} < 0.50 \implies \text{ALLOW}$
- $0.50 \le P_{\text{synth}} < 0.70 \implies \text{VERIFY}$
- $P_{\text{synth}} \ge 0.70 \implies \text{BLOCK}$

### Capture-Domain Reliability
The verification status of the audio recording environment:
- `trusted_file`: Uploaded pre-recorded audio file matching certified distribution parameters.
- `unvalidated`: Real-time browser microphone capture where physical transducer acoustics and browser WebRTC AGC may introduce acoustic domain shift.

### Final Operational Action
The real-world operational enforcement decision emitted by the platform. If `capture_domain_reliability == "unvalidated"`, the system overrides any tentative `ALLOW` or `BLOCK` to emit `VERIFY` (requesting secondary MFA authentication) to protect against domain-shift false positives.

### Forensic Integrity Fingerprint
The SHA-256 cryptographic hash computed over the raw ingested audio byte stream, serving as an immutable identifier for chain-of-custody verification.
