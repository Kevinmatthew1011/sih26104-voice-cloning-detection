# Machine Learning Validation & Benchmark Scripts: SIH26104

## 1. Official AASIST Benchmark Verification

To evaluate and reproduce the official academic benchmark metrics on the ASVspoof 2019 Logical Access Evaluation set:

```bash
cd ml_eval/aasist
python evaluate_aasist.py
```

### Script Operations:
1. Loads the official PyTorch model checkpoint (`ml_eval/aasist/weights/AASIST.pth`).
2. Iterates over all 71,237 FLAC audio files in `datasets/ASVspoof2019_LA/LA/ASVspoof2019_LA_eval/flac/`.
3. Evaluates raw model countermeasure scores ($CM$) against the ground-truth key protocol (`ASVspoof2019.LA.cm.eval.trl.txt`).
4. Computes Equal Error Rate (EER) via continuous interpolation and exports `ml_eval/aasist/results/aasist_eval_metrics.json`.

---

## 2. Dataset Leakage & Integrity Validation

The automated test `test_dataset_and_metrics.py` validates that:
1. **Intra-Split Duplication**: Identifies duplicate files within the same split via SHA-256 hashing.
2. **Cross-Split Leakage**: Throws a `DatasetValidationError` if any identical file exists in both training and test partitions.
3. **Speaker Identity Disjointness**: Guarantees zero speaker overlap across partitions:
   $$\text{Train Speakers} \cap \text{Test Speakers} = \emptyset$$
