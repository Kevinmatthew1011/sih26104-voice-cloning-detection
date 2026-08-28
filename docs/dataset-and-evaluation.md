# SIH26104: Dataset & Research-Grade Evaluation Foundation

> [!NOTE]
> This legacy foundation document is part of the historical baseline documentation. For the full production AASIST and ASVspoof documentation, see [docs/05-ml/asvspoof-dataset.md](file:///home/kiddo/projects/sih26104-voice-cloning/docs/05-ml/asvspoof-dataset.md) and the [docs/README.md](file:///home/kiddo/projects/sih26104-voice-cloning/docs/README.md) hub.

## 1. Overview & Provenance Standards

This document establishes the scientific evaluation standards, dataset integrity protocols, and metric calculation methodologies for **SIH 2026 Problem Statement SIH26104: "AI-Powered Real-Time Detection and Prevention of Voice Cloning Impersonation Attacks"**.

To ensure experimental integrity and prevent data leakage, this repository enforces strict provenance and evaluation rules before any machine learning model can be trained or evaluated.

> [!IMPORTANT]
> **No Pre-Packaged Data**: The repository contains zero training audio. Approved datasets must be placed locally in `ml_data/` by the research team and must respect all academic/commercial licensing agreements. Audio binaries are excluded from Git version control via `.gitignore`.

---

## 2. Directory Layout & Partition Structure

The dataset directory layout follows standard anti-spoofing benchmarks (e.g., ASVspoof, In-the-Wild, WaveFake):

```
ml_data/
├── manifest.json              # Dataset provenance metadata (optional, see manifest.template.json)
├── train/
│   ├── real/                  # Genuine organic human voice recordings (.wav, .mp3, .flac, etc.)
│   └── synthetic/             # Synthesized or cloned speech audio recordings
├── validation/                # Dedicated validation split (optional)
│   ├── real/
│   └── synthetic/
└── test/                      # Dedicated evaluation test split (optional)
    ├── real/
    └── synthetic/
```

Supported audio formats: `.wav`, `.mp3`, `.ogg`, `.flac`, `.m4a`, `.aac`, `.webm`.

---

## 3. Dataset Provenance Manifest (`manifest.json`)

To ensure reproducibility, researchers should document dataset provenance using `ml_data/manifest.json`. A template is provided in `ml_data/manifest.template.json`:

```json
{
  "dataset_name": "EXAMPLE_VOICE_ANTISPOOF_DATASET",
  "dataset_version": "v1.0.0",
  "source": "https://example-provenance-repo.org/datasets/voice-spoof-v1",
  "license": "CC-BY-4.0",
  "description": "Dataset provenance description for SIH26104 Voice Cloning Detection.",
  "preparation_date": "2026-08-25T00:00:00Z",
  "class_mapping": {
    "0": "real",
    "1": "synthetic"
  },
  "speaker_id_available": true,
  "recording_id_available": true,
  "protocol": "speaker_independent_disjoint_split"
}
```

---

## 4. Dataset Validation & Integrity Checks (`app.ml.dataset`)

Before any feature extraction or training occurs, `DatasetValidator` enforces strict integrity checks:

1. **Directory Structure**: Verifies that `train/real/` and `train/synthetic/` exist and contain at least one audio sample.
2. **Audio Decoding**: Verifies that files are non-empty (>0 bytes) and possess valid decodable audio headers.
3. **Intra-Split Duplicate Detection**: Computes SHA-256 hashes for each audio file to identify identical duplicate recordings within a split.
4. **Cross-Split Data Leakage Prevention**: Checks SHA-256 hashes across splits (`train` vs `validation` vs `test`). If any identical audio file exists in more than one split, validation **immediately fails with an error**.

---

## 5. Speaker Leakage Prevention & Speaker-Disjoint Splitting

### What is Speaker Leakage?
In voice cloning detection, if clips from the same speaker appear in both the training set and the test set, the classifier can memorize speaker-specific vocal tract timbre rather than detecting genuine speech synthesis artifacts. This results in artificially inflated test accuracy that collapses in real-world deployment.

### How Speaker Leakage is Prevented:
1. **Speaker Metadata Discovery**: `DatasetValidator` extracts speaker IDs from manifest mappings or file naming conventions (`spk001_...`, `speakerA_...`, `id1001_...`).
2. **Overlap Verification**: The validator checks:
   $$\text{Train Speakers} \cap \text{Validation Speakers} = \emptyset$$
   $$\text{Train Speakers} \cap \text{Test Speakers} = \emptyset$$
   $$\text{Validation Speakers} \cap \text{Test Speakers} = \emptyset$$
   If any overlap is detected, training fails with a `DatasetValidationError`.
3. **Speaker-Independent Group Splitting (`speaker_independent_split`)**: When partitioning a single dataset, `GroupShuffleSplit` groups samples by speaker identity so that all utterances from a speaker are assigned exclusively to either train or test.
4. **Missing Speaker Metadata Disclaimer**: If speaker identity metadata is unavailable, the pipeline explicitly warns:
   > *"Speaker-independent evaluation cannot be guaranteed because speaker identity metadata is unavailable in the dataset."*
   Speaker IDs are never fabricated.

---

## 6. Research-Grade Evaluation Metrics (`app.ml.metrics`)

The binary classification convention follows standard anti-spoofing literature:
- **Class 0 (Negative)**: Real / Organic Human Voice
- **Class 1 (Positive)**: Synthetic / Cloned Speech

### Standard Metrics:
- **Accuracy**: Overall classification correctness $\frac{\text{TP} + \text{TN}}{\text{TP} + \text{TN} + \text{FP} + \text{FN}}$.
- **Precision (Synthetic)**: $\frac{\text{TP}}{\text{TP} + \text{FP}}$.
- **Recall (Synthetic)**: $\frac{\text{TP}}{\text{TP} + \text{FN}}$.
- **F1 Score**: Harmonic mean of Precision and Recall $\frac{2 \cdot \text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}}$.
- **ROC-AUC**: Area Under the Receiver Operating Characteristic curve.

---

## 7. Equal Error Rate (EER) Methodology

The **Equal Error Rate (EER)** is the primary benchmark metric used in biometric voice spoofing competitions (e.g. ASVspoof):

- **False Acceptance Rate (FAR / FPR)**: The proportion of genuine human speech clips incorrectly classified as synthetic at decision threshold $\theta$.
  $$\text{FAR}(\theta) = \frac{\text{FP}}{\text{FP} + \text{TN}}$$
- **False Rejection Rate (FRR / FNR)**: The proportion of synthetic speech clips incorrectly classified as real at decision threshold $\theta$.
  $$\text{FRR}(\theta) = \frac{\text{FN}}{\text{TP} + \text{FN}}$$
- **EER Definition**: The operating point threshold $\theta^*$ where FAR equals FRR:
  $$\text{FAR}(\theta^*) = \text{FRR}(\theta^*) = \text{EER}$$

### Calculation Implementation:
`compute_eer(y_true, y_score)` computes the ROC curve via Scikit-Learn and uses continuous root-finding (`scipy.optimize.brentq` and `scipy.interpolate.interp1d`) to determine the exact threshold $\theta^*$ where $\text{FAR}(\theta^*) - \text{FRR}(\theta^*) = 0$.

> [!NOTE]
> EER provides a threshold-independent comparison metric for academic benchmarks, but operational risk tolerances in production banking/telecom fraud defense may mandate choosing an operating threshold biased towards near-zero FAR or near-zero FRR depending on business policy.

---

## 8. Reproducibility & Random Seeds

All dataset partitions, cross-validation folds, and scikit-learn solvers use explicit deterministic random seeds.
- Default Seed: `42`
- Configurable via `--random-seed <INT>` CLI argument or `DATASET_RANDOM_SEED` environment variable.
- The random seed is recorded in `models/baseline-v1/metadata.json` for model provenance.

---

## 9. Research Limitations

1. **Window Truncation**: Only the initial 3.0 seconds (48,000 samples at 16 kHz) are inspected. Synthetic artifacts occurring after 3 seconds are missed.
2. **Linear MFCC Boundaries**: Logistic Regression on MFCC summary statistics cannot model deep nonlinear phase relationships characteristic of modern zero-shot diffusion vocoders (e.g., BigVGAN, Voicebox).
3. **Lossy Compression / Telephony Codecs**: MP3/AAC compression and G.711 telephony codecs attenuate high-frequency spectral descriptors, increasing false rejection rates.
