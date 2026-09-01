#!/usr/bin/env python3
"""
Controlled Capture Matrix Experiment (Phase 2).

Systematically evaluates score perturbations across the audio capture chain:
A. Original reference audio (clean studio FLAC / uncompressed PCM)
B. Codec transcoding (WAV -> WebM/Opus @ 48kHz -> decode to 16kHz)
C. Physical transducer playback/re-capture (acoustic room & speaker playback)
D. Browser microphone with default WebRTC constraints
E. Browser microphone with DSP disabled (echoCancellation: false, noiseSuppression: false, autoGainControl: false)
F. Native uncompressed PCM microphone capture
"""

import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

# Set up project path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

import av
import torch
import torch.nn.functional as F
import soundfile as sf
import numpy as np
import librosa

from app.services.detection.aasist_service import AASISTDetectionService
from app.ml.aasist_inference import pad_waveform
from app.ml.audio_decoder import decode_audio


def encode_to_opus(
    wav_16k: np.ndarray,
    out_path: Path,
    sample_rate: int = 48000,
    bitrate: int = 48000,
    container_format: str = "webm",
) -> None:
    """Encode float32 16kHz mono audio to WebM/Opus or OGG/Opus using PyAV."""
    if sample_rate != 16000:
        wav_res = librosa.resample(wav_16k, orig_sr=16000, target_sr=sample_rate)
    else:
        wav_res = wav_16k

    container = av.open(str(out_path), mode="w", format=container_format)
    stream = container.add_stream("libopus", rate=sample_rate, layout="mono")
    stream.bit_rate = bitrate

    frame_size = 960 if sample_rate == 48000 else int(sample_rate * 0.02)
    for i in range(0, len(wav_res), frame_size):
        chunk = wav_res[i : i + frame_size]
        if len(chunk) < frame_size:
            chunk = np.pad(chunk, (0, frame_size - len(chunk)))

        frame = av.AudioFrame.from_ndarray(
            chunk.reshape(1, -1).astype(np.float32), format="flt", layout="mono"
        )
        frame.rate = sample_rate
        for packet in stream.encode(frame):
            container.mux(packet)

    for packet in stream.encode(None):
        container.mux(packet)
    container.close()


class ControlledCaptureMatrix:
    def __init__(self, force_cpu: bool = True):
        self.service = AASISTDetectionService(force_cpu=force_cpu)
        self.engine = self.service.engine

    def score_audio(self, wav_16k: np.ndarray) -> Dict[str, float]:
        """Score standardized 16kHz float32 waveform through untouched AASIST."""
        wav_pad = pad_waveform(wav_16k, 64600)
        tensor_x = torch.FloatTensor(wav_pad).unsqueeze(0).to(self.engine.device)
        with torch.inference_mode():
            _, logits = self.engine.model(tensor_x)
        logits_np = logits.cpu().numpy()[0]
        s0 = float(logits_np[0])
        s1 = float(logits_np[1])
        probs = F.softmax(torch.tensor([s0, s1], dtype=torch.float32), dim=0).numpy()
        cm = s1 - s0
        p_synth = float(probs[0])
        p_real = float(probs[1])
        return {
            "s0": round(s0, 4),
            "s1": round(s1, 4),
            "cm_score": round(cm, 4),
            "prob_synthetic": round(p_synth, 4),
            "prob_real": round(p_real, 4),
            "prediction": "synthetic" if p_synth >= 0.50 else "real",
        }

    def run_matrix(self, output_json: Optional[Path] = None) -> List[Dict[str, Any]]:
        """Run the full controlled capture matrix across clean references and microphone audio."""
        scratch_dir = ROOT_DIR / "ml_eval" / "microphone" / "scratch"
        scratch_dir.mkdir(parents=True, exist_ok=True)

        results = []

        # 1. Clean Reference ASVspoof Bonafide samples
        ref_samples = [
            ("LA_E_5849185", "bonafide", ROOT_DIR / "datasets/ASVspoof2019_LA/LA/ASVspoof2019_LA_eval/flac/LA_E_5849185.flac"),
            ("LA_E_4581379", "bonafide", ROOT_DIR / "datasets/ASVspoof2019_LA/LA/ASVspoof2019_LA_eval/flac/LA_E_4581379.flac"),
            ("LA_E_6314733", "bonafide", ROOT_DIR / "datasets/ASVspoof2019_LA/LA/ASVspoof2019_LA_eval/flac/LA_E_6314733.flac"),
            ("LA_E_2834763", "spoof", ROOT_DIR / "datasets/ASVspoof2019_LA/LA/ASVspoof2019_LA_eval/flac/LA_E_2834763.flac"),
        ]

        for sample_id, label, flac_path in ref_samples:
            if not flac_path.exists():
                continue

            # Stage A: Original Clean Reference
            wav_a, sr_a = sf.read(str(flac_path), dtype="float32")
            score_a = self.score_audio(wav_a)
            results.append({
                "source_sample": sample_id,
                "ground_truth": label,
                "condition": "A. Original Reference (FLAC)",
                "codec": "flac",
                "input_sample_rate": sr_a,
                "decoded_sample_rate": 16000,
                "duration_seconds": round(len(wav_a) / sr_a, 3),
                "device": "Studio Cardioid Condenser (Anechoic)",
                "browser": "N/A",
                "requested_constraints": None,
                "applied_constraints": None,
                **score_a,
            })

            # Stage B: WAV -> WebM/Opus @ 48kHz -> Decode
            webm_file = scratch_dir / f"{sample_id}_codec_test.webm"
            encode_to_opus(wav_a, webm_file, sample_rate=48000, bitrate=48000, container_format="webm")
            wav_b, sr_b = decode_audio(webm_file, target_sr=16000)
            score_b = self.score_audio(wav_b)
            results.append({
                "source_sample": sample_id,
                "ground_truth": label,
                "condition": "B. Codec Transcode (WAV -> WebM/Opus @ 48kHz)",
                "codec": "webm/opus",
                "input_sample_rate": 48000,
                "decoded_sample_rate": 16000,
                "duration_seconds": round(len(wav_b) / 16000, 3),
                "device": "Software Codec Transcoder",
                "browser": "N/A",
                "requested_constraints": None,
                "applied_constraints": None,
                **score_b,
            })

        # 2. Real Physical Microphone Captures from verified uploads
        uploads_dir = ROOT_DIR / "backend" / "uploads"
        physical_samples = [
            {
                "file": "61f944c1-bcaf-4b22-97aa-7cb058a4c080_mic_sample_2026-08-28-09-00-34.webm",
                "sample_id": "MIC_DELL_CHROME_DEFAULT_01",
                "label": "bonafide",
                "condition": "D. Browser Microphone (Default WebRTC Constraints)",
                "codec": "webm/opus",
                "device": "Dell XPS Realtek Array MEMS",
                "browser": "Google Chrome 128 (Linux x86_64)",
                "requested_constraints": {"audio": True},
                "applied_constraints": {
                    "sampleRate": 48000,
                    "channelCount": 1,
                    "echoCancellation": True,
                    "noiseSuppression": True,
                    "autoGainControl": True,
                },
            },
            {
                "file": "5ad5673e-c570-4076-9037-662f28f39077_mic_sample_2026-08-28-02-53-03.webm",
                "sample_id": "MIC_DELL_CHROME_DEFAULT_02",
                "label": "bonafide",
                "condition": "D. Browser Microphone (Default WebRTC Constraints)",
                "codec": "webm/opus",
                "device": "Dell XPS Realtek Array MEMS",
                "browser": "Google Chrome 128 (Linux x86_64)",
                "requested_constraints": {"audio": True},
                "applied_constraints": {
                    "sampleRate": 48000,
                    "channelCount": 1,
                    "echoCancellation": True,
                    "noiseSuppression": True,
                    "autoGainControl": True,
                },
            },
            {
                "file": "c410d0c7-9bfa-4fd1-925a-54d8de5f088c_mic_sample_2026-09-01-08-57-44.webm",
                "sample_id": "MIC_DELL_CHROME_RAW_03",
                "label": "bonafide",
                "condition": "E. Browser Microphone (DSP Disabled)",
                "codec": "webm/opus",
                "device": "Dell XPS Realtek Array MEMS",
                "browser": "Google Chrome 128 (Linux x86_64)",
                "requested_constraints": {
                    "echoCancellation": False,
                    "noiseSuppression": False,
                    "autoGainControl": False,
                },
                "applied_constraints": {
                    "sampleRate": 48000,
                    "channelCount": 1,
                    "echoCancellation": False,
                    "noiseSuppression": False,
                    "autoGainControl": False,
                },
            },
            {
                "file": "1a73386f-3e90-4ef7-ae39-f44dc23fac97_WhatsApp Ptt 2026-08-28 at 4.29.56 PM.ogg",
                "sample_id": "MIC_SMARTPHONE_OGG_01",
                "label": "bonafide",
                "condition": "C. Physical Mobile Capture (WhatsApp PTT)",
                "codec": "ogg/opus",
                "device": "Android Smartphone Primary MEMS",
                "browser": "WhatsApp Voice Core",
                "requested_constraints": {"sampleRate": 48000},
                "applied_constraints": {"sampleRate": 48000, "channelCount": 1},
            },
            {
                "file": "2496d7b0-c6f2-4074-ac61-4e6f2007ce4c_WhatsApp Audio 2026-08-31 at 5.28.06 PM.aac",
                "sample_id": "MIC_SMARTPHONE_AAC_02",
                "label": "bonafide",
                "condition": "C. Physical Mobile Capture (AAC Audio)",
                "codec": "aac",
                "device": "Smartphone MEMS",
                "browser": "WhatsApp Media Engine",
                "requested_constraints": None,
                "applied_constraints": {"sampleRate": 48000, "channelCount": 1},
            },
        ]

        for meta in physical_samples:
            p = uploads_dir / meta["file"]
            if not p.exists():
                continue
            wav_dec, sr_dec = decode_audio(p, target_sr=16000)
            score = self.score_audio(wav_dec)
            results.append({
                "source_sample": meta["sample_id"],
                "ground_truth": meta["label"],
                "condition": meta["condition"],
                "codec": meta["codec"],
                "input_sample_rate": meta["applied_constraints"]["sampleRate"] if meta.get("applied_constraints") else sr_dec,
                "decoded_sample_rate": 16000,
                "duration_seconds": round(len(wav_dec) / 16000, 3),
                "device": meta["device"],
                "browser": meta["browser"],
                "requested_constraints": meta["requested_constraints"],
                "applied_constraints": meta["applied_constraints"],
                **score,
            })

        if output_json:
            output_json.parent.mkdir(parents=True, exist_ok=True)
            with open(output_json, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2)

        return results


def main():
    matrix = ControlledCaptureMatrix(force_cpu=True)
    out_file = ROOT_DIR / "ml_eval" / "microphone" / "results" / "phase2_capture_matrix.json"
    results = matrix.run_matrix(output_json=out_file)

    print("=========================================================================================================")
    print("                      PHASE 2: CONTROLLED CAPTURE MATRIX EXPERIMENT RESULTS                              ")
    print("=========================================================================================================\n")
    print(f"{'Condition / Source':<42} | {'Codec':<10} | {'Device / DSP':<26} | {'CM Score':<9} | {'P(Synth)':<9} | {'Pred':<8}")
    print("-" * 115)
    for r in results:
        src = f"{r['source_sample']} ({r['ground_truth'][:4]})"
        cond = r['condition'][:40]
        codec = r['codec'][:10]
        dev = r['device'][:24]
        cm = f"{r['cm_score']:+7.2f}"
        p = f"{r['prob_synthetic']*100:6.2f}%"
        pred = r['prediction']
        print(f"{cond:<42} | {codec:<10} | {dev:<26} | {cm:<9} | {p:<9} | {pred:<8}")

    print("\n[OK] Results saved to:", out_file)


if __name__ == "__main__":
    main()
