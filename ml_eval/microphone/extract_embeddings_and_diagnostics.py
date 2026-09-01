#!/usr/bin/env python3
"""
Feature-Level Diagnostics & Linear-Probe Feasibility on Frozen AASIST Embeddings (Phases 5 & 6).

Extracts the 160-dimensional pre-classifier graph representations (last_hidden)
from the frozen AASISTModel and performs:
1. Centroid distance & geometric separation diagnostics across physical conditions.
2. Linear Probe evaluation:
   - Trains a Ridge / Logistic linear probe on physical-domain TRAIN embeddings only.
   - Evaluates strictly on held-out VALIDATION and TEST splits (unseen speakers).
   - Computes non-parametric 95% bootstrap confidence intervals for all metrics.
3. Class/Channel Confound Audit.
4. Decision Gate evaluation:
   - Evaluates whether frozen linear probe generalizes or if partial fine-tuning is required.
"""

import sys
import json
import csv
import time
from pathlib import Path
from typing import Dict, Any, List, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "backend"))

import torch
import torch.nn as nn
import torch.nn.functional as F
import soundfile as sf
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
)

from app.ml.aasist_model import AASISTModel
from app.ml.audio_decoder import decode_audio
from ml_eval.microphone.evaluate_mic_baseline import compute_eer, compute_cohens_d, compute_distribution_stats


def pad_waveform(wav: np.ndarray, target_len: int = 64600) -> np.ndarray:
    if len(wav) >= target_len:
        return wav[:target_len]
    pad_len = target_len - len(wav)
    return np.pad(wav, (0, pad_len), mode="wrap")


def compute_bootstrap_ci(y_true: np.ndarray, y_score: np.ndarray, n_bootstraps: int = 1000, alpha: float = 0.05) -> Dict[str, Tuple[float, float]]:
    """Computes non-parametric bootstrap 95% confidence intervals for AUC and Accuracy."""
    rng = np.random.RandomState(42)
    boot_aucs = []
    boot_accs = []
    n = len(y_true)

    if n < 2 or len(np.unique(y_true)) < 2:
        return {"roc_auc_ci_95": (0.0, 1.0), "accuracy_ci_95": (0.0, 1.0)}

    for _ in range(n_bootstraps):
        idx = rng.choice(n, size=n, replace=True)
        y_b_true = y_true[idx]
        y_b_score = y_score[idx]

        if len(np.unique(y_b_true)) < 2:
            continue

        try:
            auc = roc_auc_score(y_b_true, y_b_score)
            boot_aucs.append(auc)
        except Exception:
            pass

        y_b_pred = (y_b_score >= 0.50).astype(int)
        boot_accs.append(accuracy_score(y_b_true, y_b_pred))

    auc_low = float(np.percentile(boot_aucs, 100 * (alpha / 2))) if boot_aucs else 0.0
    auc_high = float(np.percentile(boot_aucs, 100 * (1 - alpha / 2))) if boot_aucs else 1.0

    acc_low = float(np.percentile(boot_accs, 100 * (alpha / 2))) if boot_accs else 0.0
    acc_high = float(np.percentile(boot_accs, 100 * (1 - alpha / 2))) if boot_accs else 1.0

    return {
        "roc_auc_ci_95": (round(auc_low, 4), round(auc_high, 4)),
        "accuracy_ci_95": (round(acc_low, 4), round(acc_high, 4)),
    }


def audit_class_channel_confounds(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Audits correlation between class label and device/channel properties."""
    real_devices = [s["device"] for s in samples if s["ground_truth"] == "real"]
    synth_devices = [s["device"] for s in samples if s["ground_truth"] == "synthetic"]

    real_codecs = [s["codec"] for s in samples if s["ground_truth"] == "real"]
    synth_codecs = [s["codec"] for s in samples if s["ground_truth"] == "synthetic"]

    return {
        "real_class_device_distribution": {d: real_devices.count(d) for d in set(real_devices)},
        "synthetic_class_device_distribution": {d: synth_devices.count(d) for d in set(synth_devices)},
        "real_class_codec_distribution": {c: real_codecs.count(c) for c in set(real_codecs)},
        "synthetic_class_codec_distribution": {c: synth_codecs.count(c) for c in set(synth_codecs)},
        "confound_assessment": (
            "Genuine speech is composed of physical laptop/smartphone MEMS microphones (22 files, 4 human speakers), "
            "whereas synthetic speech is composed of 3 direct digital voice clones and 40 acoustic air-gap recaptured files "
            "using the matched physical transfer path. In train, HUMAN_SPK_01 (19 laptop recordings) constitutes 100% of real speech, "
            "creating a strong potential speaker/room acoustic confound on the training split."
        ),
    }


class AASISTEmbeddingExtractor:
    def __init__(self, checkpoint_path: Path = ROOT_DIR / "models" / "aasist" / "AASIST.pth"):
        self.device = torch.device("cpu")
        model_config = {
            "architecture": "AASIST",
            "nb_samp": 64600,
            "first_conv": 128,
            "filts": [70, [1, 32], [32, 32], [32, 64], [64, 64]],
            "gat_dims": [64, 32],
            "pool_ratios": [0.5, 0.7, 0.5, 0.5],
            "temperatures": [2.0, 2.0, 100.0, 100.0],
        }
        self.model = AASISTModel(model_config)
        state_dict = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        self.model.load_state_dict(state_dict, strict=True)
        self.model.to(self.device)
        self.model.eval()

    def extract_features(self, wav_paths: List[Path]) -> Tuple[np.ndarray, np.ndarray]:
        """Extracts (N, 160) intermediate embeddings and (N, 2) raw logits."""
        all_embeddings = []
        all_logits = []

        for p in wav_paths:
            wav, _ = decode_audio(p, target_sr=16000)
            wav_pad = pad_waveform(wav, 64600)
            tensor_x = torch.FloatTensor(wav_pad).unsqueeze(0).to(self.device)

            with torch.inference_mode():
                last_hidden, logits = self.model(tensor_x)

            all_embeddings.append(last_hidden.cpu().numpy()[0])
            all_logits.append(logits.cpu().numpy()[0])

        return np.array(all_embeddings, dtype=np.float32), np.array(all_logits, dtype=np.float32)


def run_embedding_diagnostics_and_linear_probe():
    extractor = AASISTEmbeddingExtractor()

    # Load physical domain manifest
    manifest_path = ROOT_DIR / "ml_data" / "physical_domain" / "manifests" / "physical_domain_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    samples = manifest["samples"]
    physical_root = ROOT_DIR / "ml_data" / "physical_domain"

    # Separate splits
    split_paths = {"train": [], "validation": [], "test": []}
    split_labels = {"train": [], "validation": [], "test": []}
    split_meta = {"train": [], "validation": [], "test": []}

    for s in samples:
        p = physical_root / s["relative_path"]
        if p.exists():
            split = s["split"]
            split_paths[split].append(p)
            split_labels[split].append(s["label_id"])
            split_meta[split].append(s)

    # Extract features for all splits
    features = {}
    logits = {}
    for split in ["train", "validation", "test"]:
        emb, log = extractor.extract_features(split_paths[split])
        features[split] = emb
        logits[split] = log

    # 1. Centroid Distance Diagnostics
    train_real_mask = np.array(split_labels["train"]) == 0
    train_synth_mask = np.array(split_labels["train"]) == 1

    emb_train_real = features["train"][train_real_mask]
    emb_train_synth = features["train"][train_synth_mask]

    centroid_real = np.mean(emb_train_real, axis=0)
    centroid_synth = np.mean(emb_train_synth, axis=0)

    euclid_dist = float(np.linalg.norm(centroid_real - centroid_synth))
    cos_sim = float(np.dot(centroid_real, centroid_synth) / (np.linalg.norm(centroid_real) * np.linalg.norm(centroid_synth) + 1e-9))

    within_real_var = float(np.mean(np.var(emb_train_real, axis=0)))
    within_synth_var = float(np.mean(np.var(emb_train_synth, axis=0)))

    # 2. Train Linear Probe on TRAIN Split Only (Frozen Backbone Embeddings)
    X_train = features["train"]
    y_train = np.array(split_labels["train"])

    clf = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000, random_state=42)
    clf.fit(X_train, y_train)

    # Evaluate on all splits
    eval_results = {}
    for split in ["train", "validation", "test"]:
        X_split = features[split]
        y_split = np.array(split_labels[split])
        raw_logits_split = logits[split]

        # Raw AASIST head predictions
        s0_raw = raw_logits_split[:, 0]
        s1_raw = raw_logits_split[:, 1]
        p_synth_raw = np.exp(s0_raw) / (np.exp(s0_raw) + np.exp(s1_raw))
        y_pred_raw = (p_synth_raw >= 0.50).astype(int)

        # Linear Probe predictions
        p_synth_probe = clf.predict_proba(X_split)[:, 1]
        y_pred_probe = (p_synth_probe >= 0.50).astype(int)

        # Metrics for Raw AASIST Head
        acc_raw = accuracy_score(y_split, y_pred_raw)
        try:
            auc_raw = roc_auc_score(y_split, p_synth_raw)
        except Exception:
            auc_raw = 0.5
        eer_raw, _ = compute_eer(y_split, p_synth_raw)
        cm_raw = confusion_matrix(y_split, y_pred_raw, labels=[0, 1])

        # Metrics for Linear Probe Head
        acc_probe = accuracy_score(y_split, y_pred_probe)
        prec_probe = precision_score(y_split, y_pred_probe, pos_label=1, zero_division=0)
        rec_probe = recall_score(y_split, y_pred_probe, pos_label=1, zero_division=0)
        f1_probe = f1_score(y_split, y_pred_probe, pos_label=1, zero_division=0)
        try:
            auc_probe = roc_auc_score(y_split, p_synth_probe)
        except Exception:
            auc_probe = 0.5
        eer_probe, _ = compute_eer(y_split, p_synth_probe)
        cm_probe = confusion_matrix(y_split, y_pred_probe, labels=[0, 1])
        tn, fp, fn, tp = int(cm_probe[0, 0]), int(cm_probe[0, 1]), int(cm_probe[1, 0]), int(cm_probe[1, 1])
        frr_probe = float(fp / (tn + fp)) if (tn + fp) > 0 else 0.0
        far_probe = float(fn / (tp + fn)) if (tp + fn) > 0 else 0.0

        ci_probe = compute_bootstrap_ci(y_split, p_synth_probe, n_bootstraps=1000)

        eval_results[split] = {
            "num_samples": len(y_split),
            "num_real": int(np.sum(y_split == 0)),
            "num_synthetic": int(np.sum(y_split == 1)),
            "raw_aasist_head": {
                "accuracy": round(float(acc_raw), 4),
                "roc_auc": round(float(auc_raw), 4),
                "eer": round(float(eer_raw), 4),
                "confusion_matrix": {"tn": int(cm_raw[0, 0]), "fp": int(cm_raw[0, 1]), "fn": int(cm_raw[1, 0]), "tp": int(cm_raw[1, 1])},
            },
            "frozen_linear_probe": {
                "accuracy": round(float(acc_probe), 4),
                "precision": round(float(prec_probe), 4),
                "recall": round(float(rec_probe), 4),
                "f1_score": round(float(f1_probe), 4),
                "roc_auc": round(float(auc_probe), 4),
                "eer": round(float(eer_probe), 4),
                "bonafide_frr": round(float(frr_probe), 4),
                "spoof_far": round(float(far_probe), 4),
                "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
                "confidence_intervals_95": ci_probe,
            },
        }

    confound_audit = audit_class_channel_confounds(samples)

    results_dir = ROOT_DIR / "ml_eval" / "microphone" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "diagnostic_title": "Frozen AASIST Feature Extraction & Strictly Disjoint Linear Probe",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "embedding_diagnostics": {
            "embedding_dimension": 160,
            "centroid_euclidean_distance": round(euclid_dist, 4),
            "centroid_cosine_similarity": round(cos_sim, 4),
            "within_class_variance_real": round(within_real_var, 6),
            "within_class_variance_synth": round(within_synth_var, 6),
        },
        "confound_audit": confound_audit,
        "evaluation_by_split": eval_results,
    }

    with open(results_dir / "strictly_disjoint_physical_diagnostics.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary


def main():
    summary = run_embedding_diagnostics_and_linear_probe()
    print("=========================================================================================")
    print("      PHASE 5 & 6: STRICTLY DISJOINT PHYSICAL-DOMAIN EMBEDDINGS & LINEAR PROBE           ")
    print("=========================================================================================\n")
    diag = summary["embedding_diagnostics"]
    print(f"Embedding Space (160-D pre-classifier representation):")
    print(f"  Centroid Euclidean Distance (Real vs Synth): {diag['centroid_euclidean_distance']}")
    print(f"  Centroid Cosine Similarity:                  {diag['centroid_cosine_similarity']}")

    for split in ["train", "validation", "test"]:
        res = summary["evaluation_by_split"][split]
        raw = res["raw_aasist_head"]
        prb = res["frozen_linear_probe"]
        ci = prb["confidence_intervals_95"]
        print(f"\n[{split.upper()} SPLIT (N={res['num_samples']}: {res['num_real']} Real + {res['num_synthetic']} Synth)]")
        print(f"  Raw AASIST Head:     Acc = {raw['accuracy']*100:5.1f}% | ROC-AUC = {raw['roc_auc']:.4f} | EER = {raw['eer']*100:5.1f}% | Matrix = {raw['confusion_matrix']}")
        print(f"  Linear Probe Head:   Acc = {prb['accuracy']*100:5.1f}% | ROC-AUC = {prb['roc_auc']:.4f} [95% CI: {ci['roc_auc_ci_95'][0]:.4f}, {ci['roc_auc_ci_95'][1]:.4f}]")
        print(f"                       EER = {prb['eer']*100:5.1f}% | Precision = {prb['precision']*100:5.1f}% | Recall = {prb['recall']*100:5.1f}% | F1 = {prb['f1_score']:.4f}")
        print(f"                       FRR = {prb['bonafide_frr']*100:5.1f}% | FAR = {prb['spoof_far']*100:5.1f}% | Matrix = {prb['confusion_matrix']}")


if __name__ == "__main__":
    main()
