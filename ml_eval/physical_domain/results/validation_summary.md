# Phase 4: Real-World Acoustic Validation Summary

**Date**: 2026-09-06 07:45:59 UTC  
**Platform**: SIH-26104 Voice Cloning Detection Platform  
**Target Engine**: AASIST (End-to-End Spectro-Temporal Graph Attention Network)  
**Evaluated Branch**: `codex/scam-call-demo`  
**Decision Gate**: **`D. INSUFFICIENT DATA`**

---

## 1. Executive Summary

Phase 4 evaluated the empirical generalization of the untouched production AASIST acoustic model across clean studio benchmarks, real-world physical microphone captures, and streaming sliding-window latency.

### Key Scientific Findings:
1. **ASVspoof 2019 Clean Benchmark**: Outstanding laboratory performance (**0.80% EER**, **99.93% ROC-AUC**, **0.22% Bonafide FPR** across 71,237 evaluation trials).
2. **Physical Microphone Domain Shift**: Severe transducer collapse. Untouched AASIST produces **100% False Positive Rate** on real human speech recorded through browser laptop and smartphone microphone arrays ($14 / 14$ genuine samples scored $P_{\text{synth}} \ge 0.999$, with countermeasure scores $CM \in [-22.36, -15.35]$).
3. **Missing Physical Replay Data**: **0 samples** currently exist in the repository for physical speaker-to-microphone replay attacks.
4. **Real-Time Streaming Latency**: Unavoidable initial buffering is **4,037.5 ms** (64,600 samples @ 16 kHz). Model inference latency on host CPU averages **438.80 ms** (RTF = **0.1087**, ~9.2x faster than real-time).

---

## 2. Comparative Benchmark Performance

| Evaluation Domain | Sample Count | Class Balance (Real / Synth) | Accuracy | EER | ROC-AUC | Genuine FPR | Synthetic Miss Rate |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Clean ASVspoof 2019 LA** | 71,237 | 7,355 / 63,882 | 95.18% | 0.80% | 0.9993 | 0.22% | 5.36% |
| **Physical Challenge (0.50 Thresh)** | 25 | 14 / 11 | 44.00% | 30.52% | 0.4675 | **100.00%** | 0.00% |
| **Physical Challenge (0.70 Thresh)** | 25 | 14 / 11 | 44.00% | 30.52% | 0.4675 | **100.00%** | 0.00% |
| **Physical Replay (Speaker $\to$ Mic)** | **0** | 0 / 0 | *N/A* | *N/A* | *N/A* | *N/A* | *N/A* |

---

## 3. Threshold Trade-off Analysis (Physical Challenge Set)

```
Threshold | TPR      | FPR      | Precision | F1-Score | Genuine FPR
------------------------------------------------------------------
0.10      | 100.00%  | 100.00%  | 44.00%    | 61.11%   | 100.00%
0.30      | 100.00%  | 100.00%  | 44.00%    | 61.11%   | 100.00%
0.50      | 100.00%  | 100.00%  | 44.00%    | 61.11%   | 100.00%
0.70      | 100.00%  | 100.00%  | 44.00%    | 61.11%   | 100.00%
0.90      | 100.00%  | 100.00%  | 44.00%    | 61.11%   | 100.00%
```

> **Root Cause**: Because SincNet filterbanks map raw browser WebRTC-processed microphone audio into the deep spoof quadrant ($CM \approx -15$ to $-22$), threshold adjustments alone cannot separate genuine microphone speech from neural vocoder synthesis.

---

## 4. Phase 3 Streaming Pipeline Latency Profile

- **Window Geometry**: 64,600 samples (~4.0375 seconds @ 16 kHz)
- **Hop Geometry**: 16,150 samples (~1.009375 seconds @ 16 kHz, 75% overlap)
- **Host Device**: CPU (x86_64 Host CPU)
- **Initial Buffering Latency**: **4037.5 ms** (unavoidable acoustic buffering)
- **Average Inference Latency**: **438.80 ms**
- **P50 Latency**: **433.57 ms**
- **P95 Latency**: **533.57 ms**
- **First-Decision Latency**: **4384.37 ms** (~4.4 seconds total from call start)
- **Effective Update Cadence**: **1448.18 ms** (~1.38s between sliding updates)
- **Real-Time Factor (RTF)**: **0.1087** (~9.2x real-time throughput)

---

## 5. Decision Gate: `D. INSUFFICIENT DATA`

### Gate Analysis:
- **Why Not Gate A (Generalization Acceptable)?** Genuine microphone speech fails catastrophically with a 100% false positive rate.
- **Why Not Gate B (Calibration Needed)?** SincNet embeddings have completely collapsed; simple score shifting or temperature scaling cannot restore class separability.
- **Why Not Gate C (Domain Adaptation Now)?** While SincNet adaptation is theoretically required, launching fine-tuning today would be premature: we currently have only 14 genuine microphone files and **0 physical speaker-to-microphone replay files**. Fine-tuning on 25 samples would cause catastrophic overfitting and immediate failure under unseen acoustic conditions.
- **GATE SELECTION**: **`D. INSUFFICIENT DATA`**
  Immediate priority must be expanding the physical collection pool via `/collect-physical-domain` before any model training or weight adjustments occur.

---

## 6. Generated Evaluation Visualizations

The following vector plots were generated into `ml_eval/physical_domain/results/`:
- `roc_curve.svg`: Anti-spoofing ROC comparison (Clean ASVspoof vs Physical Challenge)
- `score_distribution.svg`: Synthetic probability score distributions across capture regimes
- `confusion_matrix.svg`: Side-by-side classification confusion matrices
- `threshold_tradeoff.svg`: Operating threshold sensitivity across candidate decision points
