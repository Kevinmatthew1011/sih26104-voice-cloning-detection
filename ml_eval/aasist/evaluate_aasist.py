import sys
import os
import csv
import json
import time
import hashlib
from pathlib import Path
from typing import Tuple, List, Dict, Any
from collections import Counter

import numpy as np
import soundfile as sf
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    roc_curve,
    confusion_matrix,
)

def compute_sha256(filepath: Path) -> str:
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()

def pad_audio(x: np.ndarray, max_len: int = 64600) -> np.ndarray:
    x_len = x.shape[0]
    if x_len >= max_len:
        return x[:max_len]
    num_repeats = int(max_len / x_len) + 1
    padded_x = np.tile(x, num_repeats)[:max_len]
    return padded_x

def compute_eer(y_true: np.ndarray, y_score: np.ndarray) -> Tuple[float, float]:
    """Computes Equal Error Rate (EER) and optimal threshold for synthetic class (1)."""
    fpr, tpr, thresholds = roc_curve(y_true, y_score, pos_label=1)
    fnr = 1.0 - tpr

    if np.any((fpr == 0.0) & (fnr == 0.0)):
        return 0.0, 0.0

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

class ASVspoofEvalDataset(Dataset):
    def __init__(self, samples: List[Tuple[str, str, str, str, str, Path]], max_len: int = 64600):
        self.samples = samples
        self.max_len = max_len

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        spk, audio_id, env, att, orig_label, audio_path = self.samples[idx]
        wav, sr = sf.read(str(audio_path))
        if sr != 16000:
            raise ValueError(f"Unexpected sample rate {sr} for {audio_path}")
        wav_pad = pad_audio(wav, self.max_len)
        label_id = 0 if orig_label == "bonafide" else 1
        return (
            torch.FloatTensor(wav_pad),
            label_id,
            audio_id,
            att,
            spk
        )

def main():
    t_global_start = time.perf_counter()

    root = Path(__file__).resolve().parent.parent.parent
    aasist_dir = root / "ml_eval" / "aasist"
    sys.path.insert(0, str(aasist_dir))

    from models.AASIST import Model

    results_dir = aasist_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    metrics_out_file = results_dir / "aasist_eval_metrics.json"
    scores_out_file = results_dir / "aasist_eval_scores.csv"

    config_file = aasist_dir / "config" / "AASIST.conf"
    weights_file = aasist_dir / "weights" / "AASIST.pth"

    eval_proto = root / "datasets" / "ASVspoof2019_LA" / "LA" / "ASVspoof2019_LA_cm_protocols" / "ASVspoof2019.LA.cm.eval.trl.txt"
    eval_audio_dir = root / "datasets" / "ASVspoof2019_LA" / "LA" / "ASVspoof2019_LA_eval" / "flac"

    print("=================================================================")
    print("      PHASE 3: FULL OFFICIAL AASIST EVALUATION BENCHMARK         ")
    print("=================================================================\n")

    # 1. Checkpoint Pre-Evaluation Hash Verification
    assert weights_file.exists(), f"Weights missing: {weights_file}"
    initial_hash = compute_sha256(weights_file)
    print(f"1. MODEL INTEGRITY CHECK (PRE-EVALUATION):")
    print(f"   - Checkpoint Path:      {weights_file}")
    print(f"   - Checkpoint SHA-256:   {initial_hash}")
    assert initial_hash == "51d2d9cf0738172f61e2a384ec50a54a55363240f67c971ed55a92435bc1a1c0", "Unexpected checkpoint hash!"

    # 2. Protocol Parsing & Dataset Verification
    print(f"\n2. DATASET PROTOCOL PARSING & VERIFICATION:")
    assert eval_proto.exists(), f"Protocol missing: {eval_proto}"
    assert eval_audio_dir.exists(), f"Audio directory missing: {eval_audio_dir}"

    samples = []
    bonafide_count = 0
    spoof_count = 0
    attack_counts = Counter()

    with open(eval_proto, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            parts = line.strip().split()
            if len(parts) != 5:
                raise ValueError(f"Malformed protocol line {line_num}: {line}")
            spk, audio_id, env, att, label = parts
            audio_path = eval_audio_dir / f"{audio_id}.flac"
            if not audio_path.exists():
                raise FileNotFoundError(f"Audio file missing: {audio_path}")
            if label == "bonafide":
                bonafide_count += 1
            elif label == "spoof":
                spoof_count += 1
                attack_counts[att] += 1
            else:
                raise ValueError(f"Unknown label {label}")
            samples.append((spk, audio_id, env, att, label, audio_path))

    total_samples = len(samples)
    print(f"   - Total EVAL Protocol Samples: {total_samples}")
    print(f"   - Bonafide Samples:            {bonafide_count}")
    print(f"   - Spoof Samples:               {spoof_count}")
    print(f"   - Attacks Present:             {sorted(list(attack_counts.keys()))}")

    assert total_samples == 71237, f"Expected 71237 samples, got {total_samples}"
    assert bonafide_count == 7355, f"Expected 7355 bonafide, got {bonafide_count}"
    assert spoof_count == 63882, f"Expected 63882 spoof, got {spoof_count}"
    assert sorted(list(attack_counts.keys())) == [f"A{i:02d}" for i in range(7, 20)], "Attack IDs mismatch"
    for att, count in attack_counts.items():
        assert count == 4914, f"Attack {att} count {count} != 4914"

    print("   [OK] Protocol counts and all 71,237 audio paths verified.")

    # 3. Environment & Hardware Setup
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"\n3. EXECUTION ENVIRONMENT:")
    print(f"   - Device:               {device} ({torch.cuda.get_device_name(0)})")
    print(f"   - PyTorch:              {torch.__version__}")
    print(f"   - CUDA Driver/Runtime:  {torch.version.cuda}")

    with open(config_file, "r") as f:
        config = json.load(f)

    model = Model(config["model_config"])
    state_dict = torch.load(weights_file, map_location=device, weights_only=True)
    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()

    # 4. DataLoader Setup
    # Batch size 24 as in official config, 4 worker threads
    batch_size = 24
    num_workers = 4
    eval_dataset = ASVspoofEvalDataset(samples, max_len=64600)
    eval_loader = DataLoader(
        eval_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True,
        prefetch_factor=2
    )

    print(f"\n4. INFERENCE EXECUTION ON FULL EVAL (71,237 SAMPLES):")
    print(f"   - Batch Size:           {batch_size}")
    print(f"   - DataLoader Workers:   {num_workers}")
    print(f"   - Total Batches:        {len(eval_loader)}")

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()

    t0_inference = time.perf_counter()

    all_audio_ids = []
    all_speakers = []
    all_attacks = []
    all_y_true = []
    all_logit_spoof = []
    all_logit_bona = []
    all_bonafide_scores = []
    all_synth_scores = []
    all_y_pred = []

    last_log_time = time.perf_counter()
    processed_count = 0

    with torch.no_grad():
        for batch_idx, (batch_x, batch_y, batch_audio_ids, batch_atts, batch_spks) in enumerate(eval_loader):
            batch_x = batch_x.to(device, non_blocking=True)
            _, batch_out = model(batch_x)

            # batch_out[:, 0] = spoof logit, batch_out[:, 1] = bonafide logit
            bout_np = batch_out.cpu().numpy()
            spoof_logits = bout_np[:, 0]
            bona_logits = bout_np[:, 1]

            # Official CM score (higher = bonafide)
            cm_scores = bona_logits - spoof_logits
            # Synthetic score for standard binary scoring (higher = synthetic)
            synth_scores = spoof_logits - bona_logits

            # Decision rule: spoof (1) if spoof_logit > bona_logit else bonafide (0)
            preds = (spoof_logits > bona_logits).astype(np.int32)

            all_audio_ids.extend(batch_audio_ids)
            all_speakers.extend(batch_spks)
            all_attacks.extend(batch_atts)
            all_y_true.extend(batch_y.numpy())
            all_logit_spoof.extend(spoof_logits)
            all_logit_bona.extend(bona_logits)
            all_bonafide_scores.extend(cm_scores)
            all_synth_scores.extend(synth_scores)
            all_y_pred.extend(preds)

            processed_count += len(batch_audio_ids)

            now = time.perf_counter()
            if now - last_log_time >= 15.0 or processed_count == total_samples:
                elapsed_so_far = now - t0_inference
                rate = processed_count / elapsed_so_far
                percent = (processed_count / total_samples) * 100
                print(f"   [Progress] {processed_count:5d}/{total_samples} samples ({percent:5.1f}%) | Speed: {rate:5.1f} samples/s | Elapsed: {elapsed_so_far:5.1f}s")
                last_log_time = now

    if torch.cuda.is_available():
        torch.cuda.synchronize()
    t_inference = time.perf_counter() - t0_inference

    peak_vram_mb = torch.cuda.max_memory_allocated() / (1024 * 1024) if torch.cuda.is_available() else 0.0

    y_true_np = np.array(all_y_true, dtype=np.int32)
    y_pred_np = np.array(all_y_pred, dtype=np.int32)
    synth_scores_np = np.array(all_synth_scores, dtype=np.float64)
    bona_scores_np = np.array(all_bonafide_scores, dtype=np.float64)
    attacks_np = np.array(all_attacks)

    assert len(y_true_np) == 71237
    assert np.isfinite(synth_scores_np).all(), "Non-finite scores detected!"
    assert np.isfinite(bona_scores_np).all(), "Non-finite bona scores detected!"

    # 5. Global Metrics Calculation
    print(f"\n5. COMPUTING OFFICIAL EVALUATION METRICS:")
    acc = accuracy_score(y_true_np, y_pred_np)
    prec_synth = precision_score(y_true_np, y_pred_np, pos_label=1, zero_division=0)
    rec_synth = recall_score(y_true_np, y_pred_np, pos_label=1, zero_division=0)
    f1 = f1_score(y_true_np, y_pred_np, pos_label=1, zero_division=0)
    roc_auc = roc_auc_score(y_true_np, synth_scores_np)
    eer, eer_threshold = compute_eer(y_true_np, synth_scores_np)

    cm = confusion_matrix(y_true_np, y_pred_np)
    tn, fp, fn, tp = int(cm[0, 0]), int(cm[0, 1]), int(cm[1, 0]), int(cm[1, 1])
    fpr = fp / (tn + fp)
    fnr = fn / (tp + fn)

    print(f"   Accuracy:                 {acc:.4f} ({acc*100:.2f}%)")
    print(f"   Precision (Synthetic):    {prec_synth:.4f}")
    print(f"   Recall (Synthetic):       {rec_synth:.4f} ({rec_synth*100:.2f}%)")
    print(f"   F1 Score:                 {f1:.4f}")
    print(f"   ROC-AUC:                  {roc_auc:.4f}")
    print(f"   Equal Error Rate (EER):   {eer:.4f} ({eer*100:.2f}%) @ score_thresh={eer_threshold:.4f}")
    print(f"   Bonafide FPR (FAR):       {fpr:.4f} ({fpr*100:.2f}%)")
    print(f"   Synthetic FNR (FRR):      {fnr:.4f} ({fnr*100:.2f}%)")
    print(f"   Confusion Matrix:         TN={tn}, FP={fp}, FN={fn}, TP={tp}")

    # 6. Attack-Level Analysis (A07 - A19)
    print("\n6. ATTACK-LEVEL SPOOF DETECTION BREAKDOWN:")
    print("-" * 75)
    print(f"{'Attack ID':<10} | {'Category':<10} | {'Total':<8} | {'Correct (TP)':<14} | {'Missed (FN)':<12} | {'Recall (%)':<10}")
    print("-" * 75)

    unseen_tts_attacks = [f"A{i:02d}" for i in range(7, 17)]
    unseen_vc_attacks = ["A17", "A18", "A19"]
    all_unseen_attacks = [f"A{i:02d}" for i in range(7, 20)]

    attack_results = {}
    tts_total = 0
    tts_correct = 0
    vc_total = 0
    vc_correct = 0

    for att in all_unseen_attacks:
        mask = (attacks_np == att)
        total_att = int(np.sum(mask))
        preds_att = y_pred_np[mask]
        correct_att = int(np.sum(preds_att == 1))
        missed_att = int(np.sum(preds_att == 0))
        rec_att = correct_att / total_att if total_att > 0 else 0.0

        cat = "VC" if att in unseen_vc_attacks else "TTS/Hybrid"
        if att in unseen_vc_attacks:
            vc_total += total_att
            vc_correct += correct_att
        else:
            tts_total += total_att
            tts_correct += correct_att

        attack_results[att] = {
            "category": cat,
            "total": total_att,
            "correct": correct_att,
            "missed": missed_att,
            "recall": round(rec_att, 6),
            "recall_pct": round(rec_att * 100, 2)
        }
        print(f"{att:<10} | {cat:<10} | {total_att:<8} | {correct_att:<14} | {missed_att:<12} | {rec_att*100:6.2f}%")

    print("-" * 75)
    tts_recall = tts_correct / tts_total if tts_total > 0 else 0.0
    vc_recall = vc_correct / vc_total if vc_total > 0 else 0.0
    all_unseen_recall = (tts_correct + vc_correct) / (tts_total + vc_total)

    print(f"A07–A16 (Unseen TTS / Hybrid) Recall: {tts_correct}/{tts_total} ({tts_recall*100:.2f}%)")
    print(f"A17–A19 (Voice Conversion) Recall:   {vc_correct}/{vc_total} ({vc_recall*100:.2f}%)")
    print(f"A07–A19 (All Unseen Spoof) Recall:    {tts_correct + vc_correct}/{tts_total + vc_total} ({all_unseen_recall*100:.2f}%)")

    # 7. Post-Evaluation Model Integrity Verification
    final_hash = compute_sha256(weights_file)
    print(f"\n7. POST-EVALUATION MODEL INTEGRITY CHECK:")
    print(f"   - Checkpoint SHA-256:   {final_hash}")
    assert initial_hash == final_hash == "51d2d9cf0738172f61e2a384ec50a54a55363240f67c971ed55a92435bc1a1c0", "Model file modified!"
    print("   [OK] Model hash identically matches pre-evaluation hash.")

    # 8. Save CSV Scores and JSON Metrics
    print(f"\n8. SAVING MACHINE-READABLE RESULTS:")
    # Compact metrics JSON
    metrics_data = {
        "model_name": "AASIST",
        "checkpoint_sha256": final_hash,
        "evaluation_protocol": "ASVspoof 2019 LA Full EVAL (71,237 samples)",
        "hardware": {
            "device": str(device),
            "device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
            "pytorch_version": torch.__version__,
            "cuda_version": str(torch.version.cuda),
            "batch_size": batch_size,
            "peak_vram_mb": round(peak_vram_mb, 2),
            "inference_duration_seconds": round(t_inference, 4),
            "throughput_samples_per_sec": round(total_samples / t_inference, 2),
            "avg_latency_ms_per_sample": round((t_inference / total_samples) * 1000, 4)
        },
        "metrics": {
            "total_samples": total_samples,
            "bonafide_samples": bonafide_count,
            "spoof_samples": spoof_count,
            "accuracy": round(acc, 6),
            "precision_synthetic": round(prec_synth, 6),
            "recall_synthetic": round(rec_synth, 6),
            "f1_score": round(f1, 6),
            "roc_auc": round(roc_auc, 6),
            "eer": round(eer, 6),
            "eer_threshold": round(eer_threshold, 6),
            "confusion_matrix": {
                "tn": tn,
                "fp": fp,
                "fn": fn,
                "tp": tp
            },
            "bonafide_fpr": round(fpr, 6),
            "synthetic_fnr": round(fnr, 6)
        },
        "grouped_generalization": {
            "unseen_tts_a07_a16": {
                "total": tts_total,
                "correct": tts_correct,
                "recall": round(tts_recall, 6)
            },
            "unseen_vc_a17_a19": {
                "total": vc_total,
                "correct": vc_correct,
                "recall": round(vc_recall, 6)
            },
            "all_unseen_a07_a19": {
                "total": tts_total + vc_total,
                "correct": tts_correct + vc_correct,
                "recall": round(all_unseen_recall, 6)
            }
        },
        "attack_breakdown": attack_results
    }

    with open(metrics_out_file, "w", encoding="utf-8") as f:
        json.dump(metrics_data, f, indent=2)
    print(f"   - Metrics JSON saved:   {metrics_out_file} ({metrics_out_file.stat().st_size / 1024:.2f} KB)")

    # CSV scores
    with open(scores_out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["audio_id", "speaker_id", "attack_id", "label_name", "label_id", "prediction_id", "logit_spoof", "logit_bonafide", "bonafide_score", "synth_score"])
        for i in range(total_samples):
            writer.writerow([
                all_audio_ids[i],
                all_speakers[i],
                all_attacks[i],
                "bonafide" if y_true_np[i] == 0 else "spoof",
                y_true_np[i],
                y_pred_np[i],
                round(float(all_logit_spoof[i]), 5),
                round(float(all_logit_bona[i]), 5),
                round(float(all_bonafide_scores[i]), 5),
                round(float(all_synth_scores[i]), 5)
            ])
    print(f"   - CSV Scores saved:     {scores_out_file} ({scores_out_file.stat().st_size / (1024*1024):.2f} MB)")

    t_global = time.perf_counter() - t_global_start
    print(f"\nTotal Pipeline Completed in {t_global:.2f}s ({t_global/60:.2f} mins)")

if __name__ == "__main__":
    main()
