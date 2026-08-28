# SIH26104: Machine Learning Baseline Pipeline Documentation

> [!NOTE]
> This document details the Phase 1 Supervised Classical Baseline. For the current production deep learning AASIST architecture, see [docs/05-ml/aasist-architecture.md](file:///home/kiddo/projects/sih26104-voice-cloning/docs/05-ml/aasist-architecture.md) and the [docs/README.md](file:///home/kiddo/projects/sih26104-voice-cloning/docs/README.md) hub.

## 1. Overview & Purpose

This document outlines the **Phase 2 Supervised Machine Learning Baseline** for **SIH 2026 Problem Statement SIH26104: "AI-Powered Real-Time Detection and Prevention of Voice Cloning Impersonation Attacks"**.

The goal of this baseline is to establish a genuine, reproducible, end-to-end AI/ML pipeline—from raw audio ingestion and preprocessing to acoustic feature extraction, statistical classification, and inference service integration. It serves as an empirical benchmark that can later be extended, iterated upon, or replaced with deep neural architectures (e.g. Wav2Vec 2.0, RawNet2, AASIST) by the AI/ML research team.

> [!IMPORTANT]
> **Dataset Notice**: The repository does **not** include a training dataset. The dataset must be selected, approved, and supplied separately by placing audio samples in the `ml_data/` directory structure. No fake training data or fabricated models are generated.

---

## 2. Architecture & Pipeline

```
Raw Audio Input (.wav, .mp3, .ogg, .flac, .m4a, .aac, .webm)
                          ↓
┌──────────────────────────────────────────────────────────┐
│      1. Shared Audio Preprocessor (preprocessing.py)     │
│   • Load & decode audio stream                           │
│   • Convert multi-channel to mono (1 channel)            │
│   • Resample to 16,000 Hz (16 kHz speech standard)       │
│   • Fixed length 3.0s: zero-pad or truncate to first 3s  │
│   • Peak amplitude normalization ([-1.0, 1.0])           │
└─────────────────────────┬────────────────────────────────┘
                          │ 1D Array (48,000 samples @ 16 kHz)
                          ▼
┌──────────────────────────────────────────────────────────┐
│     2. Forensic Feature Extractor (features.py)          │
│   • 13 MFCCs (Mean & Std)                        : 26-d  │
│   • 13 Delta MFCCs (Mean & Std)                  : 26-d  │
│   • 13 Delta-Delta MFCCs (Mean & Std)            : 26-d  │
│   • Spectral Centroid (Mean & Std)               : 2-d   │
│   • Spectral Bandwidth (Mean & Std)              : 2-d   │
│   • Spectral Rolloff @ 85% (Mean & Std)          : 2-d   │
│   • Zero-Crossing Rate (Mean & Std)              : 2-d   │
│   • RMS Energy (Mean & Std)                      : 2-d   │
└─────────────────────────┬────────────────────────────────┘
                          │ 88-dimensional Feature Vector
                          ▼
┌──────────────────────────────────────────────────────────┐
│       3. ML Classifier Pipeline (classifier.py)          │
│   • StandardScaler (Z-score feature normalization)       │
│   • Logistic Regression (L2 penalty, balanced weights)   │
└─────────────────────────┬────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────┐
│        4. Detection Output Contract & Inference          │
│   • Prediction: "real" (0) or "synthetic" (1)            │
│   • Confidence: Predicted class probability estimate     │
│     (Note: uncalibrated model estimate from 0.0 - 1.0)   │
│   • Risk Level: "low" | "medium" | "high"                │
│   • Model Version: "baseline-v1"                         │
└──────────────────────────────────────────────────────────┘
```

---

## 3. Preprocessing Specifications (`app.ml.preprocessing`)

All audio files across training, evaluation, and production inference pass through the exact same deterministic preprocessor:

| Parameter | Default Value | Rationale |
|---|---|---|
| `target_sr` | `16000` Hz | 16 kHz captures fundamental human speech frequencies up to 8 kHz (Nyquist frequency) while minimizing feature matrix memory. |
| `mono` | `True` | Eliminates stereo phase artifacts and ensures microphone channel consistency. Multi-channel inputs are averaged to single mono channel. |
| `max_duration_seconds`| `3.0` seconds | 48,000 samples provide sufficient phonetic coverage for spectral statistics while keeping inference latency < 200 ms. |
| `normalize` | `True` | Peak amplitude normalization prevents recording volume variations from skewing acoustic energy descriptors. |

### ⚠️ Critical 3-Second Truncation Limitation
- **Zero-Padding**: Audio clips shorter than 3.0 seconds are zero-padded to 3.0 seconds (48,000 samples).
- **Truncation**: Audio clips longer than 3.0 seconds are **truncated to the first 3.0 seconds**.
- **Implication**: Only the initial 3 seconds of a recording are analyzed in this baseline. If synthetic artifacts, voice-conversion transitions, or cloning glitches occur later in the recording (e.g. after the 3-second mark), they will be missed by this baseline model.
- **Future Recommendation**: Future neural architectures should implement sliding-window segment inference with temporal probability aggregation (e.g., max-pooling or attention-weighted pooling over multiple segments).

---

## 4. Probability Interpretation & Terminology

The baseline model uses `LogisticRegression.predict_proba()` to compute output scores.

> [!IMPORTANT]
> **Not Calibrated**: These probability values are **raw model probability estimates** (model score outputs) and are **not calibrated** (no Platt scaling, isotonic regression, or temperature scaling has been applied).
>
> The API response contract includes a `confidence` field for backwards compatibility with the full-stack interface. In this baseline implementation, `confidence` represents the **predicted class probability estimate** for the selected class (`max(P(real), P(synthetic))`), not a certified or calibrated confidence metric.

---

## 5. Feature Extraction Specifications (`app.ml.features`)

The feature extraction pipeline computes an **88-dimensional fixed vector**:

1. **Mel-Frequency Cepstral Coefficients (MFCCs)**: Captures the short-term spectral envelope and vocal tract resonance characteristics ($13 \text{ coefficients} \times 2 = 26$).
2. **Delta MFCCs (1st order differential)**: Measures speech velocity and temporal trajectory changes ($13 \text{ coefficients} \times 2 = 26$).
3. **Delta-Delta MFCCs (2nd order differential)**: Measures speech acceleration across frame transitions ($13 \text{ coefficients} \times 2 = 26$).
4. **Spectral Centroid**: Represents the "center of mass" of the frequency spectrum ($2$).
5. **Spectral Bandwidth**: Measures the frequency spread around the spectral centroid ($2$).
6. **Spectral Rolloff (85%)**: Measures the frequency below which 85% of spectral energy lies ($2$).
7. **Zero-Crossing Rate (ZCR)**: Quantifies the rate of sign-changes in the signal ($2$).
8. **Root-Mean-Square (RMS) Energy**: Quantifies the physical signal energy contour ($2$).

---

## 6. Dataset Structure & Research Provenance

The dataset directory layout is located at the workspace root in `ml_data/`:

```
ml_data/
├── manifest.json              # Dataset provenance & protocol (see manifest.template.json)
├── train/
│   ├── real/                  # Place genuine human audio recordings (.wav, .mp3, etc.)
│   └── synthetic/             # Place AI voice clones / synthesized speech audio
├── validation/                # Optional dedicated validation set
│   ├── real/
│   └── synthetic/
└── test/                      # Optional dedicated test set
    ├── real/
    └── synthetic/
```

> [!CAUTION]
> If `ml_data/train/real` or `ml_data/train/synthetic` is missing or contains 0 audio files, the training script will terminate immediately with an actionable error.

For comprehensive dataset provenance standards, speaker leakage prevention, SHA-256 duplicate detection, and Equal Error Rate (EER) methodology, see [docs/dataset-and-evaluation.md](file:///home/kiddo/projects/sih26104-voice-cloning/docs/dataset-and-evaluation.md).

---

## 7. Training & Evaluating the Baseline Model

Once you have added approved real and synthetic audio files into `ml_data/train/`:

```bash
cd backend
source .venv/bin/activate

# Execute training pipeline (runs validation, feature extraction, training, and EER evaluation)
python -m app.ml.train
```

### Optional Command Line Arguments:
```bash
python -m app.ml.train \
    --data-dir ../ml_data \
    --output-dir ../models/baseline-v1 \
    --test-size 0.2 \
    --random-seed 42 \
    --c-reg 1.0 \
    --max-iter 1000
```

### Outputs Produced:
When training completes successfully on a real dataset, it exports:
1. `models/baseline-v1/model.joblib`: Serialized `StandardScaler` + `LogisticRegression` pipeline.
2. `models/baseline-v1/metadata.json`: Full model provenance, hyperparameters, evaluation metrics (Accuracy, Precision, Recall, F1, ROC-AUC, EER, Confusion Matrix), dataset split strategies, and speaker partition records.

---

## 8. Configuration & Engine Activation

In `.env` or environment variables:

### Activate Mock Detection Engine:
```bash
DETECTION_ENGINE=mock
```

### Activate Real Baseline ML Detection Engine:
```bash
DETECTION_ENGINE=baseline
```

> [!IMPORTANT]
> If `DETECTION_ENGINE=baseline` is configured but the model artifact (`models/baseline-v1/model.joblib`) does not exist on disk, the backend will return an HTTP 503 error stating that the model must first be trained. It will **not** silently fall back to mock data.

---

## 9. Research Limitations & Vulnerabilities

While this baseline establishes a clean, extensible machine learning foundation, it has several known scientific limitations:

1. **Fixed 3-Second Window**: Only the initial 3 seconds of a recording are inspected; cloning anomalies occurring later in the file will not be detected.
2. **Uncalibrated Probability Estimates**: Raw logistic regression probabilities are sensitive to class imbalance and feature correlation and do not represent calibrated confidence.
3. **Speaker Leakage**: Clip-level random splitting across speakers causes the model to memorize speaker identities rather than detecting synthetic artifacts. A true benchmark requires speaker-independent splitting (e.g. ASVspoof protocol).
4. **Unseen Neural Vocoders**: Linear classifiers on MFCCs struggle to generalize to modern diffusion vocoders (e.g., HiFi-GAN, BigVGAN, Voicebox) that were not present in the training distribution.
5. **Lossy Compression / Codec Mismatch**: MP3/AAC compression and telephony codecs (G.711) discard high-frequency phase information, significantly degrading MFCC statistical separation.
6. **Acoustic Replay Attacks**: A binary synthetic/real classifier cannot distinguish between direct digital synthesis and physical loudspeaker playback in a reverberant room.
7. **Adversarial & Background Noise**: Ambient room noise lowers the Signal-to-Noise Ratio (SNR), increasing false positive rates on authentic voices.

---

## 10. Replacing the Baseline with Advanced Deep Learning Models

To replace `BaselineMLDetectionService` with your teammate's neural network (e.g., PyTorch / Hugging Face Wav2Vec 2.0):

1. Inherit from `BaseDetectionService` in `backend/app/services/detection/deep_model_service.py`.
2. Implement `detect(audio_path, ...)` to output `DetectionResultDTO`.
3. Register the class in `backend/app/services/detection/factory.py`.
4. Set `DETECTION_ENGINE=deep_model` in `.env`.
