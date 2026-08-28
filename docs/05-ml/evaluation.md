# Official Model Evaluation & Benchmarking: SIH26104

## 1. Official Evaluation Protocol

The production **AASIST** checkpoint (`AASIST.pth`) was evaluated on the complete official **ASVspoof 2019 Logical Access Evaluation Set** ($N = 71,237\text{ samples}$) using `ml_eval/aasist/evaluate_aasist.py`.

The evaluation script iterates through all 71,237 FLAC files, computing logits, raw countermeasure scores ($CM$), and synthetic probabilities ($P_{\text{synth}}$) across all unseen attack algorithms (A07–A19).

---

## 2. Certified Benchmark Results

The official certified benchmark metrics are stored in `ml_eval/aasist/results/aasist_eval_metrics.json`:

```json
{
  "benchmark": "ASVspoof 2019 Logical Access (LA) Evaluation Set",
  "model": "AASIST (Official Checkpoint)",
  "metrics": {
    "total_samples": 71237,
    "bonafide_samples": 7355,
    "spoof_samples": 63882,
    "accuracy": 0.951753,
    "precision_synthetic": 0.999735,
    "recall_synthetic": 0.946448,
    "f1_score": 0.972362,
    "roc_auc": 0.999282,
    "eer": 0.008047,
    "eer_threshold": -4.531697,
    "confusion_matrix": {
      "tn": 7339,
      "fp": 16,
      "fn": 3421,
      "tp": 60461
    },
    "bonafide_fpr": 0.002175,
    "synthetic_fnr": 0.053552
  }
}
```

---

## 3. Metric Breakdown & Discussion

| Metric | Result | Analysis |
| :--- | :--- | :--- |
| **Equal Error Rate (EER)** | **0.8047%** ($0.008047$) | State-of-the-art academic anti-spoofing performance (< 1.0% EER). |
| **ROC-AUC** | **0.999282** | Near-perfect separation between bonafide and synthetic speech distributions. |
| **Bonafide False Positive Rate (FPR)** | **0.2175%** ($16 / 7,355$) | Only 16 genuine human speech files out of 7,355 were falsely flagged as synthetic. |
| **Synthetic Recall (TPR)** | **94.6448%** ($60,461 / 63,882$)| Detected 60,461 out of 63,882 unknown zero-shot synthesis attacks. |
| **Synthetic Precision** | **99.9735%** | When flagged as synthetic, the prediction is 99.97% reliable on clean studio audio. |
| **Overall Accuracy** | **95.1753%** | Overall correct classification rate across the imbalanced evaluation partition. |
