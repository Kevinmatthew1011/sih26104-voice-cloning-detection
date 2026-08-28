# Machine Learning Engine Overview: SIH26104

## 1. Overview & Research Evolution

The **VOICE-GUARD Machine Learning Engine** provides deep learning anti-spoofing detection for synthetic speech, neural vocoder artifacts, and voice cloning attacks.

The ML subsystem has evolved through two primary phases:
1. **Phase 1 Supervised Baseline (`BaselineMLDetectionService`)**:
   - 88-dimensional classical acoustic feature extraction (MFCCs, Delta MFCCs, Spectral Centroid, Bandwidth, Rolloff, ZCR, RMS Energy).
   - Logistic Regression with L2 regularization and StandardScaler normalization.
   - Fixed 3.0-second window truncation.
2. **Phase 2 State-of-the-Art Deep Learning (`AASISTDetectionService`)**:
   - Direct raw waveform processing using **SincNet** parameterized sinc-bandpass filters.
   - Dual-branch Spectral and Temporal Graph Attention Networks (GAT).
   - Heterogeneous Spectro-Temporal Graph Attention (HtrgGAT) fusion.
   - **Multi-Window Overlapping Inference** (4.0375s windows @ 50% hop) with top-$k$ worst-case risk aggregation.
   - Official benchmark performance on ASVspoof 2019 LA: **0.8047% EER**, **0.9993 ROC-AUC**.

---

## 2. ML Engine Comparison Matrix

| Evaluation Dimension | Phase 1 Classical Baseline | Phase 2 Production AASIST |
| :--- | :--- | :--- |
| **Model Architecture** | StandardScaler + Logistic Regression | SincNet + Heterogeneous Graph Attention |
| **Input Representation** | 88-D Hand-Crafted Acoustic Features | Raw 16 kHz Waveform (64,600 samples) |
| **Feature Extraction** | Short-Time Fourier Transform (STFT) / MFCCs | Data-Driven Parametric Sinc Filters |
| **Temporal Coverage** | First 3.0 seconds (Truncated) | **Arbitrary Length** (Overlapping Multi-Window) |
| **Short Splice Detection**| Poor (Misses splices after 3.0s) | **High** (`max_v1` conservative maximum risk aggregation) |
| **ASVspoof 2019 EVAL EER**| $\approx 15.2\%$ (Baseline estimation) | **0.8047%** (Certified benchmark) |
| **ASVspoof 2019 ROC-AUC**| $\approx 0.9100$ | **0.999282** |
| **Total Parameters** | 89 parameters | **297,866 parameters** |
| **Inference Latency** | $\approx 25\text{ ms}$ | $\approx 180\text{ ms}$ (GPU) / $\approx 350\text{ ms}$ (CPU) |

---

## 3. Academic Attribution & Checkpoint Provenance

The production deep learning architecture is based on the research paper:
> **AASIST: Audio Anti-Spoofing Using Integrated Spectro-Temporal Graph Attention Networks**  
> *Jung-woo Jung, Hee-Soo Heo, Hemlata Tak, Hye-jin Shim, Joon Son Chung, Bong-Jin Lee, Ha-Jin Yu, Nicholas Evans*  
> Published in: *ICASSP 2022 - 2022 IEEE International Conference on Acoustics, Speech and Signal Processing (ICASSP)*  
> Paper DOI: [10.1109/ICASSP43922.2022.9747766](https://doi.org/10.1109/ICASSP43922.2022.9747766)

The official model weights are serialized in `ml_eval/aasist/weights/AASIST.pth`:
- **Model Checkpoint SHA-256**: `51d2d9cf0738172f61e2a384ec50a54a55363240f67c971ed55a92435bc1a1c0`
- **Model Architecture**: AASIST (`model_config` in [backend/app/ml/aasist_model.py](file:///home/kiddo/projects/sih26104-voice-cloning/backend/app/ml/aasist_model.py))
- **Backbone Status**: 100% Frozen in production.
