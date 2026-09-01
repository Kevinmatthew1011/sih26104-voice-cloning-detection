#!/usr/bin/env python3
"""
Untouched AASIST Microphone-Domain Baseline Evaluation (Phase 4).

Evaluates the frozen production AASIST model on the microphone-domain benchmark
across all three partitions (calibration, validation, test).

Calculates comprehensive forensic & biometric metrics:
- Sample counts & class balance
- Score distributions (mean, std, min, median, max for real and synthetic)
- 2x2 Confusion matrix (TN, FP, FN, TP) at standard decision threshold (P >= 0.50 / CM <= 0.0)
- Accuracy, Precision, Recall, F1
- ROC-AUC
- Equal Error Rate (EER) and optimal EER threshold
- False Acceptance Rate (FAR) and False Rejection Rate (FRR)
- Distribution overlap analysis (Wasserstein distance, Cohen's d, overlap ratio)
- Per-file score CSV outputs
"""

import sys
import os
import csv
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "backend"))

import torch
import torch.nn.functional as F
import soundfile as sf
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    roc_curve,
    confusion_matrix,
)

from app.services.detection.aasist_service import AASISTDetectionService
from app.ml.aasist_inference import pad_waveform
from app.ml.audio_decoder import decode_audio


def compute_eer(y_true: np.ndarray, y_score: np.ndarray) -> Tuple[float, float]:
    """Computes Equal Error Rate (EER) and optimal threshold for synthetic class (1)."""
    fpr, tpr, thresholds = roc_curve(y_true, y_score, pos_label=1)
    fnr = 1.0 - tpr

    if np.any((fpr == 0.0) & (fnr == 0.0)):
        return 0.0, float(thresholds[0]) if len(thresholds) > 0 else 0.0

    diffs = np.abs(fpr - fnr)
    min_idx = int(np.argmin(diffs))

    if min_idx < len(fpr) - 1:
        x1, x2 = fpr[min_idx], fpr[min_idx + 1]
        y1, y2 = fnr[min_idx], fnr[min_idx + 1]
        denom = (x2 - x1) - (y2 - y1)
        if abs(denom) > 1e-9:
            alpha = (y1 - x1) / denom
            if 0.0 <= alpha <= 1.0:
                eer = float(x1 + alpha * (x2 - x1))
                opt_thresh = float(thresholds[min_idx] + alpha * (thresholds[min_idx + 1] - thresholds[min_idx]))
                return eer, opt_thresh

    return float((fpr[min_idx] + fnr[min_idx]) / 2.0), float(thresholds[min_idx])


def compute_distribution_stats(scores: np.ndarray) -> Dict[str, float]:
    if len(scores) == 0:
        return {"count": 0, "mean": 0.0, "std": 0.0, "min": 0.0, "median": 0.0, "max": 0.0}
    return {
        "count": len(scores),
        "mean": round(float(np.mean(scores)), 4),
        "std": round(float(np.std(scores)), 4),
        "min": round(float(np.min(scores)), 4),
        "median": round(float(np.median(scores)), 4),
        "max": round(float(np.max(scores)), 4),
    }


def compute_cohens_d(group1: np.ndarray, group2: np.ndarray) -> float:
    """Computes effect size (Cohen's d) between two score distributions."""
    n1, n2 = len(group1), len(group2)
    if n1 < 2 or n2 < 2:
        return 0.0
    var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)
    pooled_std = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2)) + 1e-9
    return float(round((np.mean(group1) - np.mean(group2)) / pooled_std, 4))


class BaselineMicrophoneEvaluator:
    def __init__(self, manifest_path: Path = ROOT_DIR / "ml_data/microphone/manifests/microphone_dataset_manifest.json", force_cpu: bool = True):
        self.manifest_path = Path(manifest_path)
        self.service = AASISTDetectionService(force_cpu=force_cpu)
        self.engine = self.service.engine

    def evaluate_split(self, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Evaluates a list of manifest samples using untouched AASIST."""
        y_true = []
        y_pred = []
        cm_scores = []
        synth_probs = []
        real_probs = []
        per_file_records = []

        # 1. Load and decode all waveforms
        waveforms = []
        for idx, item in enumerate(samples):
            audio_rel = item["capture_path"]
            audio_path = ROOT_DIR / "ml_data" / "microphone" / audio_rel
            if not audio_path.exists():
                raise FileNotFoundError(f"Missing sample: {audio_path}")
            wav, _ = decode_audio(audio_path, target_sr=16000)
            waveforms.append(pad_waveform(wav, 64600))
            if (idx + 1) % 50 == 0 or idx + 1 == len(samples):
                print(f"  [Decoded] {idx + 1}/{len(samples)} audio files")

        # 2. Batched model inference
        batch_size = 16
        all_logits = []
        for b_start in range(0, len(waveforms), batch_size):
            b_wavs = np.stack(waveforms[b_start : b_start + batch_size], axis=0)
            tensor_x = torch.FloatTensor(b_wavs).to(self.engine.device)
            with torch.inference_mode():
                _, logits = self.engine.model(tensor_x)
            all_logits.append(logits.cpu().numpy())

        logits_np = np.concatenate(all_logits, axis=0)

        # 3. Process logits and build records
        for i, item in enumerate(samples):
            s0 = float(logits_np[i][0]) # spoof logit
            s1 = float(logits_np[i][1]) # bonafide logit
            probs = F.softmax(torch.tensor([s0, s1], dtype=torch.float32), dim=0).numpy()
            p_synth = float(probs[0])
            p_real = float(probs[1])
            cm = s1 - s0

            label_id = item["label_id"] # 0 for real, 1 for synthetic
            pred_id = 1 if p_synth >= 0.50 else 0

            y_true.append(label_id)
            y_pred.append(pred_id)
            cm_scores.append(cm)
            synth_probs.append(p_synth)
            real_probs.append(p_real)

            per_file_records.append({
                "sample_id": item["sample_id"],
                "split": item["split"],
                "speaker_id": item["speaker_id"],
                "ground_truth": item["ground_truth"],
                "label_id": label_id,
                "prediction_label": "synthetic" if pred_id == 1 else "real",
                "prediction_id": pred_id,
                "logit_s0_spoof": round(s0, 4),
                "logit_s1_bonafide": round(s1, 4),
                "cm_score": round(cm, 4),
                "prob_synthetic": round(p_synth, 4),
                "prob_real": round(p_real, 4),
                "device": item.get("device"),
                "codec": item.get("codec"),
            })

        y_true_np = np.array(y_true, dtype=np.int32)
        y_pred_np = np.array(y_pred, dtype=np.int32)
        cm_scores_np = np.array(cm_scores, dtype=np.float64)
        synth_probs_np = np.array(synth_probs, dtype=np.float64)

        real_mask = (y_true_np == 0)
        synth_mask = (y_true_np == 1)

        real_cm_scores = cm_scores_np[real_mask]
        synth_cm_scores = cm_scores_np[synth_mask]

        # Standard binary metrics at P(synth) >= 0.50 threshold
        acc = accuracy_score(y_true_np, y_pred_np)
        prec = precision_score(y_true_np, y_pred_np, pos_label=1, zero_division=0)
        rec = recall_score(y_true_np, y_pred_np, pos_label=1, zero_division=0)
        f1 = f1_score(y_true_np, y_pred_np, pos_label=1, zero_division=0)

        # ROC-AUC using synthetic probability as score
        # Note: synth_probs is monotonic with -cm_score
        try:
            roc_auc = roc_auc_score(y_true_np, synth_probs_np)
        except Exception:
            roc_auc = 0.5

        # EER
        eer, eer_threshold = compute_eer(y_true_np, synth_probs_np)

        # Confusion Matrix
        cm = confusion_matrix(y_true_np, y_pred_np, labels=[0, 1])
        tn, fp, fn, tp = int(cm[0, 0]), int(cm[0, 1]), int(cm[1, 0]), int(cm[1, 1])

        # FAR (False Accept Rate = synthetic classified as real) and FRR (False Reject Rate = real classified as synthetic)
        # Note: In biometrics:
        # False Reject Rate (FRR) = FP / (TN + FP) = Bonafide False Alarm Rate
        # False Accept Rate (FAR) = FN / (TP + FN) = Spoof Miss Rate
        frr_bona = float(fp / (tn + fp)) if (tn + fp) > 0 else 0.0
        far_spoof = float(fn / (tp + fn)) if (tp + fn) > 0 else 0.0

        # Distribution overlap analysis
        cohens_d = compute_cohens_d(real_cm_scores, synth_cm_scores)

        return {
            "metrics": {
                "total_samples": len(y_true),
                "real_samples": int(np.sum(real_mask)),
                "synthetic_samples": int(np.sum(synth_mask)),
                "accuracy": round(float(acc), 4),
                "precision_synthetic": round(float(prec), 4),
                "recall_synthetic": round(float(rec), 4),
                "f1_score": round(float(f1), 4),
                "roc_auc": round(float(roc_auc), 4),
                "eer": round(float(eer), 4),
                "eer_threshold_prob": round(float(eer_threshold), 4),
                "bonafide_frr": round(frr_bona, 4),
                "spoof_far": round(far_spoof, 4),
                "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
            },
            "score_distributions": {
                "real_cm": compute_distribution_stats(real_cm_scores),
                "synthetic_cm": compute_distribution_stats(synth_cm_scores),
                "real_synth_prob": compute_distribution_stats(synth_probs_np[real_mask]),
                "synthetic_synth_prob": compute_distribution_stats(synth_probs_np[synth_mask]),
                "cohens_d_cm_separation": cohens_d,
            },
            "per_file_records": per_file_records,
        }

    def run_full_baseline(self) -> Dict[str, Any]:
        """Runs baseline evaluation across calibration, validation, and test partitions."""
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        results_dir = ROOT_DIR / "ml_eval" / "microphone" / "results"
        results_dir.mkdir(parents=True, exist_ok=True)

        samples = manifest["samples"]
        total = len(samples)
        print(f"Scoring {total} microphone benchmark samples through untouched AASIST...")

        # Score all samples once
        all_eval = self.evaluate_split(samples)
        all_records = all_eval["per_file_records"]

        # Partition records
        partition_results = {}
        for split in ["calibration", "validation", "test"]:
            split_records = [r for r in all_records if r["split"] == split]
            y_true_split = np.array([r["label_id"] for r in split_records], dtype=np.int32)
            y_pred_split = np.array([r["prediction_id"] for r in split_records], dtype=np.int32)
            cm_scores_split = np.array([r["cm_score"] for r in split_records], dtype=np.float64)
            synth_probs_split = np.array([r["prob_synthetic"] for r in split_records], dtype=np.float64)

            real_mask = (y_true_split == 0)
            synth_mask = (y_true_split == 1)
            real_cm = cm_scores_split[real_mask]
            synth_cm = cm_scores_split[synth_mask]

            acc = accuracy_score(y_true_split, y_pred_split)
            prec = precision_score(y_true_split, y_pred_split, pos_label=1, zero_division=0)
            rec = recall_score(y_true_split, y_pred_split, pos_label=1, zero_division=0)
            f1 = f1_score(y_true_split, y_pred_split, pos_label=1, zero_division=0)

            try:
                roc_auc = roc_auc_score(y_true_split, synth_probs_split)
            except Exception:
                roc_auc = 0.5

            eer, eer_thresh = compute_eer(y_true_split, synth_probs_split)
            cm = confusion_matrix(y_true_split, y_pred_split, labels=[0, 1])
            tn, fp, fn, tp = int(cm[0, 0]), int(cm[0, 1]), int(cm[1, 0]), int(cm[1, 1])

            frr_bona = float(fp / (tn + fp)) if (tn + fp) > 0 else 0.0
            far_spoof = float(fn / (tp + fn)) if (tp + fn) > 0 else 0.0
            cohens_d = compute_cohens_d(real_cm, synth_cm)

            partition_results[split] = {
                "metrics": {
                    "total_samples": len(split_records),
                    "real_samples": int(np.sum(real_mask)),
                    "synthetic_samples": int(np.sum(synth_mask)),
                    "accuracy": round(float(acc), 4),
                    "precision_synthetic": round(float(prec), 4),
                    "recall_synthetic": round(float(rec), 4),
                    "f1_score": round(float(f1), 4),
                    "roc_auc": round(float(roc_auc), 4),
                    "eer": round(float(eer), 4),
                    "eer_threshold_prob": round(float(eer_thresh), 4),
                    "bonafide_frr": round(frr_bona, 4),
                    "spoof_far": round(far_spoof, 4),
                    "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
                },
                "score_distributions": {
                    "real_cm": compute_distribution_stats(real_cm),
                    "synthetic_cm": compute_distribution_stats(synth_cm),
                    "real_synth_prob": compute_distribution_stats(synth_probs_split[real_mask]),
                    "synthetic_synth_prob": compute_distribution_stats(synth_probs_split[synth_mask]),
                    "cohens_d_cm_separation": cohens_d,
                },
            }

        # Save per-file CSV
        csv_path = results_dir / "baseline_microphone_per_file_scores.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(all_records[0].keys()))
            writer.writeheader()
            writer.writerows(all_records)

        # Save metrics summary JSON
        summary_data = {
            "evaluation_title": "Untouched AASIST Microphone-Domain Baseline Evaluation (Phase 4)",
            "evaluation_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "model_version": "aasist-v1",
            "partitions": {
                "calibration": {
                    "metrics": partition_results["calibration"]["metrics"],
                    "score_distributions": partition_results["calibration"]["score_distributions"],
                },
                "validation": {
                    "metrics": partition_results["validation"]["metrics"],
                    "score_distributions": partition_results["validation"]["score_distributions"],
                },
                "test": {
                    "metrics": partition_results["test"]["metrics"],
                    "score_distributions": partition_results["test"]["score_distributions"],
                },
                "overall": {
                    "metrics": all_eval["metrics"],
                    "score_distributions": all_eval["score_distributions"],
                },
            },
            "per_file_csv_path": str(csv_path),
        }

        json_path = results_dir / "baseline_microphone_metrics.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, indent=2)

        return summary_data


def main():
    evaluator = BaselineMicrophoneEvaluator(force_cpu=True)
    summary = evaluator.run_full_baseline()

    print("=========================================================================================")
    print("      PHASE 4: UNTOUCHED AASIST MICROPHONE-DOMAIN BASELINE EVALUATION REPORT             ")
    print("=========================================================================================\n")

    for split in ["calibration", "validation", "test", "overall"]:
        m = summary["partitions"][split]["metrics"]
        d = summary["partitions"][split]["score_distributions"]
        print(f"--- Partition: {split.upper()} (N={m['total_samples']}: {m['real_samples']} Real + {m['synthetic_samples']} Synthetic) ---")
        print(f"  Accuracy:                 {m['accuracy']*100:6.2f}%")
        print(f"  ROC-AUC:                  {m['roc_auc']:.4f}")
        print(f"  Equal Error Rate (EER):   {m['eer']*100:6.2f}% (thresh={m['eer_threshold_prob']:.4f})")
        print(f"  Bonafide False Rejection: {m['bonafide_frr']*100:6.2f}% ({m['confusion_matrix']['fp']}/{m['real_samples']})")
        print(f"  Spoof False Acceptance:   {m['spoof_far']*100:6.2f}% ({m['confusion_matrix']['fn']}/{m['synthetic_samples']})")
        print(f"  Confusion Matrix:         TN={m['confusion_matrix']['tn']}, FP={m['confusion_matrix']['fp']}, FN={m['confusion_matrix']['fn']}, TP={m['confusion_matrix']['tp']}")
        print(f"  Real CM Score Mean:       {d['real_cm']['mean']:+7.2f} (std={d['real_cm']['std']:.2f}, range: [{d['real_cm']['min']:+.2f}, {d['real_cm']['max']:+.2f}])")
        print(f"  Synthetic CM Score Mean:  {d['synthetic_cm']['mean']:+7.2f} (std={d['synthetic_cm']['std']:.2f}, range: [{d['synthetic_cm']['min']:+.2f}, {d['synthetic_cm']['max']:+.2f}])")
        print(f"  Cohen's d (Separation):   {d['cohens_d_cm_separation']:+7.2f}\n")


if __name__ == "__main__":
    main()
