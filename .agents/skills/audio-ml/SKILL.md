---
name: audio-ml
description: Guides audio machine learning development for the SIH-26104 voice cloning detection platform, including audio preprocessing, 88-D MFCC feature extraction, baseline classification, dataset leakage prevention, EER evaluation, and integration with BaseDetectionService.
---

# SIH-26104 Audio & Machine Learning Guidelines

This skill defines the technical standards, research practices, and safety rules for audio processing, feature engineering, model training, evaluation, and inference in the SIH-26104 Voice Cloning Detection Platform.

## Machine Learning Architecture & Engine Distinction

The platform distinguishes between three tiers of detection engines:

1. **Mock Detection Engine (`DETECTION_ENGINE=mock`)**:
   - Implemented in `backend/app/services/detection/mock_service.py`.
   - Deterministic rule-based simulator used for frontend development and automated system testing without requiring trained model weights.
2. **Baseline ML Engine (`DETECTION_ENGINE=baseline`)**:
   - Implemented in `backend/app/ml/` and `backend/app/services/detection/baseline_service.py`.
   - End-to-end scikit-learn pipeline (88-D MFCC/spectral features + StandardScaler + Logistic Regression) running on CPU.
   - Requires trained model artifacts at `models/baseline-v1/model.joblib`; raises HTTP 503 if uninitialized.
3. **Future Production Anti-Spoofing Model (`DETECTION_ENGINE=<custom>`)**:
   - A future production anti-spoofing model selected after benchmarking appropriate architectures against the project's evaluation protocol.
   - Plugs seamlessly into the platform by inheriting from `BaseDetectionService` and registering in `factory.py`.

## Core Audio Preprocessing Specifications (`app.ml.preprocessing`)

All audio files across training, evaluation, and live inference must pass through `AudioPreprocessor`:

- **Target Sample Rate**: `16,000 Hz` (16 kHz speech standard; resampled via `librosa.resample`).
- **Channels**: Single-channel `mono` (multi-channel audio is averaged across channels).
- **Window & Duration Strategy**: Fixed `3.0 seconds` (48,000 samples).
  - Audio $< 3.0\text{s}$ is zero-padded to 3.0s.
  - Audio $> 3.0\text{s}$ is truncated to the initial 3.0 seconds.
  - *Limitation Note*: Only the first 3 seconds are analyzed; subsequent artifacts are not captured by this baseline.
- **Normalization**: Peak amplitude normalized to $[-1.0, 1.0]$.
- **Sanitization**: All non-finite values (NaNs, Infs) replaced via `np.nan_to_num`.

## Feature Extraction Specifications (`app.ml.features`)

`AudioFeatureExtractor` extracts an 88-dimensional float32 vector (`FEATURE_VERSION = "mfcc-spectral-v1.0"`):

1. **MFCCs (13 coefficients, Mean & Std)**: 26 features
2. **Delta MFCCs (13 coefficients, Mean & Std)**: 26 features
3. **Delta-Delta MFCCs (13 coefficients, Mean & Std)**: 26 features
4. **Spectral Centroid (Mean & Std)**: 2 features
5. **Spectral Bandwidth (Mean & Std)**: 2 features
6. **Spectral Rolloff at 85% energy (Mean & Std)**: 2 features
7. **Zero-Crossing Rate (Mean & Std)**: 2 features
8. **RMS Energy (Mean & Std)**: 2 features

## Dataset Integrity & Leakage Prevention Rules (`app.ml.dataset`)

Dataset files reside under `ml_data/` (`train/real`, `train/synthetic`, `validation/`, `test/`).

When preparing or validating datasets:
1. **Never fabricate training data**: Datasets must be authentic audio files from approved sources.
2. **Strict File Format Check**: Only `.wav`, `.mp3`, `.ogg`, `.flac`, `.m4a`, `.aac`, `.webm`. Reject 0-byte or unreadable files.
3. **Cross-Split Hash Duplicate Prevention**: Enforce SHA-256 duplicate checking between train, validation, and test splits. Zero identical files may exist across splits.
4. **Speaker Leakage Prevention**:
   - Where speaker identity metadata or filename prefixes (`spk001_`, `speakerA-`, `id10001_`) exist, enforce speaker-independent partitioning (`speaker_independent_split`).
   - Clips from the same speaker must never appear in both training and test sets.
   - If speaker metadata is unavailable, clearly document that speaker independence is unverified.

## Evaluation & Metrics Standards (`app.ml.metrics`)

Always evaluate models using the standardized research protocol:

- **Primary Biometric Metric**: **Equal Error Rate (EER)** and optimal decision threshold ($FPR = FNR$).
- **Complementary Metrics**: ROC-AUC, Accuracy, Precision (synthetic), Recall (synthetic), F1-Score, and $2 \times 2$ Confusion Matrix.
- **Reporting**: Use `format_evaluation_report()` to output consistent, structured evaluation summaries.
- **Never claim a model is production-ready without empirical validation on a held-out test split.**

## Probability Interpretation & Confidence

- In `BaselineClassifier` / `BaselineInferenceEngine`, probability values from `predict_proba()` represent **raw, uncalibrated model score estimates**.
- The `confidence` field in `DetectionResultDTO` reflects the predicted class probability (`max(P(real), P(synthetic))`). Do not present uncalibrated estimates as certified statistical certainty.

## Integration & Extension with `BaseDetectionService`

To integrate a new ML model:
1. Create a new service under `backend/app/services/detection/` inheriting from `BaseDetectionService` (`app/services/detection/base.py`).
2. Implement `async def detect(...) -> DetectionResultDTO` and `def get_model_info() -> Dict[str, Any]`.
3. Register the new engine name in `get_detection_service()` inside `backend/app/services/detection/factory.py`.
4. For future neural models, handle the execution device explicitly with a safe CPU fallback where feasible, without introducing unnecessary dependencies into the baseline engine.
5. Export model version metadata and hyperparameters in `models/<model_version>/metadata.json`.

## Verification & Testing

Always verify ML pipeline changes with the existing test suite:

```bash
cd backend
# Run confirmed ML test suites
pytest tests/test_ml_baseline.py
pytest tests/test_dataset_and_metrics.py
```
