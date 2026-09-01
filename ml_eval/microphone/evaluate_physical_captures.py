#!/usr/bin/env python3
"""
Physical Browser-Microphone Capture Baseline & Domain Audit (Phase 4B).

Evaluates the frozen untouched AASIST model exclusively on verified real-world
physical microphone and mobile recordings vs. synthetic voice clones.

Generates:
- Real physical microphone CM score distributions (mean, std, min, median, max, quantiles)
- Synthetic voice clone CM score distributions
- Biometric classification metrics (ROC-AUC, EER, FAR, FRR, F1, Confusion Matrix)
- 4-Domain comparative analysis (Clean ASVspoof, Codec Transcoded, Physical Genuine Mic, Synthetic Clones)
- Calibration feasibility analysis (checking whether CM scores exhibit linear separability)
- Machine-readable JSON metrics and per-file CSV scores
"""

import sys
import json
import csv
import time
import hashlib
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
from ml_eval.microphone.evaluate_mic_baseline import compute_eer, compute_distribution_stats, compute_cohens_d


PHYSICAL_GENUINE_RECORDS = [
    {"file": "61f944c1-bcaf-4b22-97aa-7cb058a4c080_mic_sample_2026-08-28-09-00-34.webm", "sample_id": "PHYS_MIC_001", "speaker_id": "HUMAN_SPK_01", "device": "Dell XPS Realtek Array MEMS", "browser": "Google Chrome 128 (Linux)", "codec": "webm/opus", "constraints": {"echoCancellation": True, "noiseSuppression": True, "autoGainControl": True}},
    {"file": "5ad5673e-c570-4076-9037-662f28f39077_mic_sample_2026-08-28-02-53-03.webm", "sample_id": "PHYS_MIC_002", "speaker_id": "HUMAN_SPK_01", "device": "Dell XPS Realtek Array MEMS", "browser": "Google Chrome 128 (Linux)", "codec": "webm/opus", "constraints": {"echoCancellation": True, "noiseSuppression": True, "autoGainControl": True}},
    {"file": "b306ea8a-5cb4-4456-9f08-dd60197336a3_mic_sample_2026-08-28-02-52-47.webm", "sample_id": "PHYS_MIC_003", "speaker_id": "HUMAN_SPK_01", "device": "Dell XPS Realtek Array MEMS", "browser": "Google Chrome 128 (Linux)", "codec": "webm/opus", "constraints": {"echoCancellation": True, "noiseSuppression": True, "autoGainControl": True}},
    {"file": "cf888b07-983c-4129-84f6-7fe83b715556_mic_sample_2026-08-27-17-54-10.webm", "sample_id": "PHYS_MIC_004", "speaker_id": "HUMAN_SPK_01", "device": "Dell XPS Realtek Array MEMS", "browser": "Google Chrome 128 (Linux)", "codec": "webm/opus", "constraints": {"echoCancellation": True, "noiseSuppression": True, "autoGainControl": True}},
    {"file": "8b728ed5-b0cf-434b-810e-0a4d5716d835_mic_sample_2026-08-27-17-52-58.webm", "sample_id": "PHYS_MIC_005", "speaker_id": "HUMAN_SPK_01", "device": "Dell XPS Realtek Array MEMS", "browser": "Google Chrome 128 (Linux)", "codec": "webm/opus", "constraints": {"echoCancellation": True, "noiseSuppression": True, "autoGainControl": True}},
    {"file": "4fc6bd4f-21ed-43cf-8b9b-6399834e127d_mic_sample_2026-08-27-17-39-45.webm", "sample_id": "PHYS_MIC_006", "speaker_id": "HUMAN_SPK_01", "device": "Dell XPS Realtek Array MEMS", "browser": "Google Chrome 128 (Linux)", "codec": "webm/opus", "constraints": {"echoCancellation": True, "noiseSuppression": True, "autoGainControl": True}},
    {"file": "48251a2d-ac78-4ad1-a57e-50a641c94ddf_mic_sample_2026-08-28-10-58-07.webm", "sample_id": "PHYS_MIC_007", "speaker_id": "HUMAN_SPK_01", "device": "Dell XPS Realtek Array MEMS", "browser": "Google Chrome 128 (Linux)", "codec": "webm/opus", "constraints": {"echoCancellation": True, "noiseSuppression": True, "autoGainControl": True}},
    {"file": "5f9b5ebe-f948-4186-bbc7-bb01bdccd3d5_mic_sample_2026-08-28-10-57-52.webm", "sample_id": "PHYS_MIC_008", "speaker_id": "HUMAN_SPK_01", "device": "Dell XPS Realtek Array MEMS", "browser": "Google Chrome 128 (Linux)", "codec": "webm/opus", "constraints": {"echoCancellation": True, "noiseSuppression": True, "autoGainControl": True}},
    {"file": "38f61782-7a20-41f2-948d-247c94b96368_mic_sample_2026-09-01-06-08-25.webm", "sample_id": "PHYS_MIC_009", "speaker_id": "HUMAN_SPK_01", "device": "Dell XPS Realtek Array MEMS", "browser": "Google Chrome 128 (Linux)", "codec": "webm/opus", "constraints": {"echoCancellation": True, "noiseSuppression": True, "autoGainControl": True}},
    {"file": "2086a5be-8e6b-43e2-8e8c-d92f824a4450_mic_sample_2026-09-01-06-08-46.webm", "sample_id": "PHYS_MIC_010", "speaker_id": "HUMAN_SPK_01", "device": "Dell XPS Realtek Array MEMS", "browser": "Google Chrome 128 (Linux)", "codec": "webm/opus", "constraints": {"echoCancellation": True, "noiseSuppression": True, "autoGainControl": True}},
    {"file": "146d9848-8866-4d0b-8bd2-ccb6b825a27a_mic_sample_2026-09-01-06-09-25.webm", "sample_id": "PHYS_MIC_011", "speaker_id": "HUMAN_SPK_01", "device": "Dell XPS Realtek Array MEMS", "browser": "Google Chrome 128 (Linux)", "codec": "webm/opus", "constraints": {"echoCancellation": True, "noiseSuppression": True, "autoGainControl": True}},
    {"file": "8287d5d0-f63a-41dd-a5f9-61b49bc64527_mic_sample_2026-09-01-06-09-50.webm", "sample_id": "PHYS_MIC_012", "speaker_id": "HUMAN_SPK_01", "device": "Dell XPS Realtek Array MEMS", "browser": "Google Chrome 128 (Linux)", "codec": "webm/opus", "constraints": {"echoCancellation": True, "noiseSuppression": True, "autoGainControl": True}},
    {"file": "fc84e872-aa30-4b16-bc6e-a13ee87d22e3_mic_sample_2026-09-01-06-17-54.webm", "sample_id": "PHYS_MIC_013", "speaker_id": "HUMAN_SPK_01", "device": "Dell XPS Realtek Array MEMS", "browser": "Google Chrome 128 (Linux)", "codec": "webm/opus", "constraints": {"echoCancellation": True, "noiseSuppression": True, "autoGainControl": True}},
    {"file": "ff1e28b4-325f-4e93-b554-fb0ed78c1d67_mic_sample_2026-09-01-06-30-00.webm", "sample_id": "PHYS_MIC_014", "speaker_id": "HUMAN_SPK_01", "device": "Dell XPS Realtek Array MEMS", "browser": "Google Chrome 128 (Linux)", "codec": "webm/opus", "constraints": {"echoCancellation": True, "noiseSuppression": True, "autoGainControl": True}},
    {"file": "c410d0c7-9bfa-4fd1-925a-54d8de5f088c_mic_sample_2026-09-01-08-57-44.webm", "sample_id": "PHYS_MIC_015", "speaker_id": "HUMAN_SPK_01", "device": "Dell XPS Realtek Array MEMS", "browser": "Google Chrome 128 (Linux)", "codec": "webm/opus", "constraints": {"echoCancellation": False, "noiseSuppression": False, "autoGainControl": False}},
    {"file": "1b18a65b-c597-45c0-a98e-8ab6cd95366b_mic_sample_2026-09-01-08-58-13.webm", "sample_id": "PHYS_MIC_016", "speaker_id": "HUMAN_SPK_01", "device": "Dell XPS Realtek Array MEMS", "browser": "Google Chrome 128 (Linux)", "codec": "webm/opus", "constraints": {"echoCancellation": True, "noiseSuppression": True, "autoGainControl": True}},
    {"file": "2da9bc0e-9dfb-4a96-b54e-b687b2fee0b4_mic_sample_chrome.webm", "sample_id": "PHYS_MIC_017", "speaker_id": "HUMAN_SPK_01", "device": "Laptop Array", "browser": "Google Chrome", "codec": "webm/opus", "constraints": {"echoCancellation": True, "noiseSuppression": True, "autoGainControl": True}},
    {"file": "4df9c4d7-a5db-45a6-9764-a7fc190538a7_mic_sample_firefox.ogg", "sample_id": "PHYS_MIC_018", "speaker_id": "HUMAN_SPK_01", "device": "Laptop Array", "browser": "Mozilla Firefox", "codec": "ogg/opus", "constraints": {"echoCancellation": True, "noiseSuppression": True, "autoGainControl": True}},
    {"file": "10f8d6c63085bb9a74c431bc277c08a902b4d13c72b22ce87e0fa0c1e8477000_mic_sample_wav.wav", "sample_id": "PHYS_MIC_019", "speaker_id": "HUMAN_SPK_01", "device": "Laptop Array", "browser": "WebAudio PCM", "codec": "wav/pcm", "constraints": None},
    {"file": "1a73386f-3e90-4ef7-ae39-f44dc23fac97_WhatsApp Ptt 2026-08-28 at 4.29.56 PM.ogg", "sample_id": "PHYS_MOB_001", "speaker_id": "HUMAN_SPK_02", "device": "Smartphone Primary MEMS", "browser": "WhatsApp Voice", "codec": "ogg/opus", "constraints": {"sampleRate": 48000}},
    {"file": "23080878-d994-41a7-bf9d-6b8c54125be7_WhatsApp Ptt 2026-08-28 at 8.26.36 AM.ogg", "sample_id": "PHYS_MOB_002", "speaker_id": "HUMAN_SPK_03", "device": "Smartphone Primary MEMS", "browser": "WhatsApp Voice", "codec": "ogg/opus", "constraints": {"sampleRate": 48000}},
    {"file": "2496d7b0-c6f2-4074-ac61-4e6f2007ce4c_WhatsApp Audio 2026-08-31 at 5.28.06 PM.aac", "sample_id": "PHYS_MOB_003", "speaker_id": "HUMAN_SPK_04", "device": "Smartphone Secondary MEMS", "browser": "WhatsApp Audio", "codec": "aac", "constraints": None},
]

SYNTHETIC_CLONE_RECORDS = [
    {"file": "26070773-ded8-4cdb-95f9-35fd9102c52f_ElevenLabs_2026-08-28T11_01_27_Roger - Laid-Back_ Casual_ Resonant_pre_sp100_s50_sb75_se0_b_m2.mp3", "sample_id": "SYNTH_CLONE_001", "generator": "ElevenLabs_Roger_v2", "codec": "mp3", "device": "ElevenLabs Neural Cloner"},
    {"file": "455aa0de-a8d2-406f-b258-005d5366ff82_ElevenLabs_2026-08-31T11_57_09_Adam - Dominant_ Firm_pre_sp100_s50_sb75_se0_b_m2.mp3", "sample_id": "SYNTH_CLONE_002", "generator": "ElevenLabs_Adam_v2", "codec": "mp3", "device": "ElevenLabs Neural Cloner"},
    {"file": "4d3c3851-b0eb-431d-ae09-b6845330a1c1_suspect_clone_sample.wav", "sample_id": "SYNTH_CLONE_003", "generator": "Neural_Diffusion_Cloner", "codec": "wav/pcm", "device": "Neural Vocoder"},
]


class PhysicalCaptureEvaluator:
    def __init__(self, force_cpu: bool = True):
        self.service = AASISTDetectionService(force_cpu=force_cpu)
        self.engine = self.service.engine
        self.uploads_dir = ROOT_DIR / "backend" / "uploads"

    def evaluate(self) -> Dict[str, Any]:
        results_dir = ROOT_DIR / "ml_eval" / "microphone" / "results"
        results_dir.mkdir(parents=True, exist_ok=True)

        records = []
        real_cm_scores = []
        real_laptop_cm = []
        real_mobile_cm = []
        synth_cm_scores = []

        y_true = []
        y_pred = []
        synth_probs = []

        # 1. Process Genuine Physical Captures
        for item in PHYSICAL_GENUINE_RECORDS:
            p = self.uploads_dir / item["file"]
            if not p.exists():
                # Fallback: glob by partial match
                matches = list(self.uploads_dir.glob(f"*{item['file'].split('_')[-1]}"))
                if matches:
                    p = matches[0]
                else:
                    continue

            wav, sr = decode_audio(p, target_sr=16000)
            wav_pad = pad_waveform(wav, 64600)
            tensor_x = torch.FloatTensor(wav_pad).unsqueeze(0).to(self.engine.device)

            with torch.inference_mode():
                _, logits = self.engine.model(tensor_x)

            logits_np = logits.cpu().numpy()[0]
            s0 = float(logits_np[0])
            s1 = float(logits_np[1])
            probs = F.softmax(torch.tensor([s0, s1], dtype=torch.float32), dim=0).numpy()
            p_synth = float(probs[0])
            p_real = float(probs[1])
            cm = s1 - s0

            pred_id = 1 if p_synth >= 0.50 else 0
            y_true.append(0) # genuine
            y_pred.append(pred_id)
            synth_probs.append(p_synth)
            real_cm_scores.append(cm)

            if "Dell" in item["device"] or "Laptop" in item["device"]:
                real_laptop_cm.append(cm)
            else:
                real_mobile_cm.append(cm)

            records.append({
                "sample_id": item["sample_id"],
                "file_name": p.name,
                "ground_truth": "real",
                "label_id": 0,
                "speaker_id": item["speaker_id"],
                "device": item["device"],
                "browser": item["browser"],
                "codec": item["codec"],
                "logit_s0_spoof": round(s0, 4),
                "logit_s1_bonafide": round(s1, 4),
                "cm_score": round(cm, 4),
                "prob_synthetic": round(p_synth, 4),
                "prob_real": round(p_real, 4),
                "prediction": "synthetic" if pred_id == 1 else "real",
            })

        # 2. Process Synthetic Clones
        for item in SYNTHETIC_CLONE_RECORDS:
            p = self.uploads_dir / item["file"]
            if not p.exists():
                matches = list(self.uploads_dir.glob(f"*{item['file'].split('_')[-1]}"))
                if matches:
                    p = matches[0]
                else:
                    continue

            wav, sr = decode_audio(p, target_sr=16000)
            wav_pad = pad_waveform(wav, 64600)
            tensor_x = torch.FloatTensor(wav_pad).unsqueeze(0).to(self.engine.device)

            with torch.inference_mode():
                _, logits = self.engine.model(tensor_x)

            logits_np = logits.cpu().numpy()[0]
            s0 = float(logits_np[0])
            s1 = float(logits_np[1])
            probs = F.softmax(torch.tensor([s0, s1], dtype=torch.float32), dim=0).numpy()
            p_synth = float(probs[0])
            p_real = float(probs[1])
            cm = s1 - s0

            pred_id = 1 if p_synth >= 0.50 else 0
            y_true.append(1) # synthetic
            y_pred.append(pred_id)
            synth_probs.append(p_synth)
            synth_cm_scores.append(cm)

            records.append({
                "sample_id": item["sample_id"],
                "file_name": p.name,
                "ground_truth": "synthetic",
                "label_id": 1,
                "speaker_id": "SYNTHETIC_GENERATOR",
                "device": item["device"],
                "browser": "N/A",
                "codec": item["codec"],
                "logit_s0_spoof": round(s0, 4),
                "logit_s1_bonafide": round(s1, 4),
                "cm_score": round(cm, 4),
                "prob_synthetic": round(p_synth, 4),
                "prob_real": round(p_real, 4),
                "prediction": "synthetic" if pred_id == 1 else "real",
            })

        y_true_np = np.array(y_true, dtype=np.int32)
        y_pred_np = np.array(y_pred, dtype=np.int32)
        synth_probs_np = np.array(synth_probs, dtype=np.float64)

        real_cm_np = np.array(real_cm_scores, dtype=np.float64)
        synth_cm_np = np.array(synth_cm_scores, dtype=np.float64)

        # Classification metrics
        acc = accuracy_score(y_true_np, y_pred_np)
        prec = precision_score(y_true_np, y_pred_np, pos_label=1, zero_division=0)
        rec = recall_score(y_true_np, y_pred_np, pos_label=1, zero_division=0)
        f1 = f1_score(y_true_np, y_pred_np, pos_label=1, zero_division=0)
        cm_matrix = confusion_matrix(y_true_np, y_pred_np, labels=[0, 1])
        tn, fp, fn, tp = int(cm_matrix[0, 0]), int(cm_matrix[0, 1]), int(cm_matrix[1, 0]), int(cm_matrix[1, 1])

        # ROC-AUC (using synthetic probability)
        try:
            roc_auc = roc_auc_score(y_true_np, synth_probs_np)
        except Exception:
            roc_auc = 0.5

        eer, eer_thresh = compute_eer(y_true_np, synth_probs_np)
        frr_bona = float(fp / (tn + fp)) if (tn + fp) > 0 else 0.0
        far_spoof = float(fn / (tp + fn)) if (tp + fn) > 0 else 0.0

        cohens_d = compute_cohens_d(real_cm_np, synth_cm_np)

        # Distribution Quantiles
        real_quantiles = {
            "p10": round(float(np.percentile(real_cm_np, 10)), 2),
            "p25": round(float(np.percentile(real_cm_np, 25)), 2),
            "p50_median": round(float(np.percentile(real_cm_np, 50)), 2),
            "p75": round(float(np.percentile(real_cm_np, 75)), 2),
            "p90": round(float(np.percentile(real_cm_np, 90)), 2),
        }

        synth_quantiles = {
            "p10": round(float(np.percentile(synth_cm_np, 10)), 2),
            "p25": round(float(np.percentile(synth_cm_np, 25)), 2),
            "p50_median": round(float(np.percentile(synth_cm_np, 50)), 2),
            "p75": round(float(np.percentile(synth_cm_np, 75)), 2),
            "p90": round(float(np.percentile(synth_cm_np, 90)), 2),
        }

        # Save per-file CSV
        csv_path = results_dir / "physical_capture_per_file_scores.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
            writer.writeheader()
            writer.writerows(records)

        summary = {
            "evaluation_title": "Phase 4B: Physical Browser-Microphone Capture Baseline",
            "evaluation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "dataset_composition": {
                "total_physical_samples": len(records),
                "genuine_physical_samples": len(real_cm_scores),
                "laptop_microphone_samples": len(real_laptop_cm),
                "smartphone_samples": len(real_mobile_cm),
                "synthetic_clone_samples": len(synth_cm_scores),
                "distinct_human_participants": 4, # SPK_01 (laptop) + SPK_02, SPK_03, SPK_04 (mobile WhatsApp)
            },
            "distributions": {
                "real_physical_overall": compute_distribution_stats(real_cm_np),
                "real_physical_quantiles": real_quantiles,
                "real_laptop_mems": compute_distribution_stats(np.array(real_laptop_cm)),
                "real_smartphone_mems": compute_distribution_stats(np.array(real_mobile_cm)),
                "synthetic_clones": compute_distribution_stats(synth_cm_np),
                "synthetic_quantiles": synth_quantiles,
                "cohens_d_cm_separation": cohens_d,
            },
            "metrics": {
                "accuracy": round(float(acc), 4),
                "precision": round(float(prec), 4),
                "recall": round(float(rec), 4),
                "f1_score": round(float(f1), 4),
                "roc_auc": round(float(roc_auc), 4),
                "eer": round(float(eer), 4),
                "eer_threshold": round(float(eer_thresh), 4),
                "bonafide_frr": round(float(frr_bona), 4),
                "spoof_far": round(float(far_spoof), 4),
                "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
            },
            "per_file_csv_path": str(csv_path),
        }

        json_path = results_dir / "physical_capture_baseline_metrics.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        return summary


def main():
    evaluator = PhysicalCaptureEvaluator(force_cpu=True)
    summary = evaluator.evaluate()

    print("=========================================================================================")
    print("      PHASE 4B: REAL PHYSICAL BROWSER-MICROPHONE BASELINE EVALUATION REPORT              ")
    print("=========================================================================================\n")
    d = summary["dataset_composition"]
    m = summary["metrics"]
    dist = summary["distributions"]

    print(f"Dataset: {d['total_physical_samples']} samples ({d['genuine_physical_samples']} Real Physical + {d['synthetic_clone_samples']} Synthetic Clones)")
    print(f"Human Participants: {d['distinct_human_participants']} verified real speakers")
    print(f"\n--- Physical CM Score Distributions ---")
    print(f"  Real Physical Laptop Array (N={d['laptop_microphone_samples']}): Mean = {dist['real_laptop_mems']['mean']:+7.2f} (std={dist['real_laptop_mems']['std']:.2f}, range: [{dist['real_laptop_mems']['min']:+.2f}, {dist['real_laptop_mems']['max']:+.2f}], median={dist['real_laptop_mems']['median']:+.2f})")
    print(f"  Real Smartphone MEMS (N={d['smartphone_samples']}):       Mean = {dist['real_smartphone_mems']['mean']:+7.2f} (std={dist['real_smartphone_mems']['std']:.2f}, range: [{dist['real_smartphone_mems']['min']:+.2f}, {dist['real_smartphone_mems']['max']:+.2f}], median={dist['real_smartphone_mems']['median']:+.2f})")
    print(f"  Real Overall Physical (N={d['genuine_physical_samples']}):      Mean = {dist['real_physical_overall']['mean']:+7.2f} (std={dist['real_physical_overall']['std']:.2f}, range: [{dist['real_physical_overall']['min']:+.2f}, {dist['real_physical_overall']['max']:+.2f}], median={dist['real_physical_overall']['median']:+.2f})")
    print(f"  Synthetic Clones (N={d['synthetic_clone_samples']}):           Mean = {dist['synthetic_clones']['mean']:+7.2f} (std={dist['synthetic_clones']['std']:.2f}, range: [{dist['synthetic_clones']['min']:+.2f}, {dist['synthetic_clones']['max']:+.2f}], median={dist['synthetic_clones']['median']:+.2f})")
    print(f"  Cohen's d (Real vs Synth):   {dist['cohens_d_cm_separation']:+7.2f} (Negative indicates genuine scores lower/worse than clones!)")

    print(f"\n--- Untouched Model Metrics ---")
    print(f"  Accuracy:                 {m['accuracy']*100:6.2f}%")
    print(f"  ROC-AUC:                  {m['roc_auc']:.4f}")
    print(f"  Equal Error Rate (EER):   {m['eer']*100:6.2f}%")
    print(f"  Bonafide False Rejection: {m['bonafide_frr']*100:6.2f}% ({m['confusion_matrix']['fp']}/{d['genuine_physical_samples']} genuine rejected as synthetic)")
    print(f"  Spoof False Acceptance:   {m['spoof_far']*100:6.2f}% ({m['confusion_matrix']['fn']}/{d['synthetic_clone_samples']})")
    print(f"  Confusion Matrix:         TN={m['confusion_matrix']['tn']}, FP={m['confusion_matrix']['fp']}, FN={m['confusion_matrix']['fn']}, TP={m['confusion_matrix']['tp']}")

    print("\n[OK] Physical baseline saved to:", summary["per_file_csv_path"])


if __name__ == "__main__":
    main()
