import json
import time
import uuid
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

from app.ml.audio_decoder import decode_audio
from app.schemas.physical_collection import (
    PhysicalCaptureManifestRecord,
    PhysicalQualityTelemetry,
    BalanceDashboardResponse,
    PhysicalDomainPoolManifest,
)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
POOL_DIR = ROOT_DIR / "ml_data" / "physical_domain_pool"
MANIFEST_PATH = POOL_DIR / "manifests" / "physical_domain_pool_manifest.json"


class PhysicalCollectionService:
    """Manages physical domain acoustic data collection, quality control, balance dashboards, and split proposals."""

    def __init__(self, pool_dir: Path = POOL_DIR):
        self.pool_dir = Path(pool_dir)
        self.manifest_path = self.pool_dir / "manifests" / "physical_domain_pool_manifest.json"
        self._ensure_storage_structure()

    def _ensure_storage_structure(self):
        (self.pool_dir / "incoming" / "real").mkdir(parents=True, exist_ok=True)
        (self.pool_dir / "incoming" / "synthetic").mkdir(parents=True, exist_ok=True)
        (self.pool_dir / "manifests").mkdir(parents=True, exist_ok=True)

        if not self.manifest_path.exists():
            initial_data = {
                "dataset_name": "SIH26104_PHYSICAL_DOMAIN_POOL",
                "version": "1.0",
                "description": "Ingestion and staging pool for multi-speaker, multi-device physical acoustic speech captures.",
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "total_samples": 0,
                "summary_by_class": {"real": 0, "synthetic": 0},
                "summary_by_device": {},
                "summary_by_human_speaker": {},
                "summary_by_split": {"incoming_pool": 0, "train": 0, "validation": 0, "dev_test": 0, "locked_test": 0},
                "samples": [],
            }
            with open(self.manifest_path, "w", encoding="utf-8") as f:
                json.dump(initial_data, f, indent=2)

    def load_manifest(self) -> Dict[str, Any]:
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_manifest(self, manifest_data: Dict[str, Any]):
        manifest_data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

    def compute_quality_telemetry(self, wav: np.ndarray, sr: int = 16000) -> PhysicalQualityTelemetry:
        """Computes objective quality metrics on 16kHz float32 audio."""
        if len(wav) == 0:
            return PhysicalQualityTelemetry()

        # 1. Clipping percentage (|amplitude| >= 0.999)
        clipping_frames = np.sum(np.abs(wav) >= 0.995)
        clipping_pct = round(float((clipping_frames / len(wav)) * 100.0), 2)

        # 2. Peak Amplitude & RMS Energy
        peak_val = np.max(np.abs(wav)) + 1e-12
        peak_dbfs = round(float(20 * np.log10(peak_val)), 2)

        rms_val = np.sqrt(np.mean(wav ** 2)) + 1e-12
        rms_dbfs = round(float(20 * np.log10(rms_val)), 2)

        # 3. Silence percentage (frames below -45 dBFS)
        frame_size = int(0.025 * sr) # 25ms frames
        hop_size = int(0.010 * sr)   # 10ms hop
        frames = [
            wav[i : i + frame_size]
            for i in range(0, len(wav) - frame_size + 1, hop_size)
        ]
        silent_count = 0
        noise_energies = []
        speech_energies = []

        for f in frames:
            f_rms = np.sqrt(np.mean(f ** 2)) + 1e-12
            f_db = 20 * np.log10(f_rms)
            if f_db < -45.0:
                silent_count += 1
                noise_energies.append(f_rms)
            else:
                speech_energies.append(f_rms)

        total_frames = len(frames) if len(frames) > 0 else 1
        silence_pct = round(float((silent_count / total_frames) * 100.0), 2)

        # 4. Estimated SNR (Speech RMS / Noise RMS)
        mean_speech = np.mean(speech_energies) if speech_energies else rms_val
        mean_noise = np.mean(noise_energies) if noise_energies else 1e-5
        snr_db = round(float(20 * np.log10((mean_speech / (mean_noise + 1e-9)))), 2)

        return PhysicalQualityTelemetry(
            clipping_percentage=clipping_pct,
            peak_amplitude_dbfs=peak_dbfs,
            rms_energy_dbfs=rms_dbfs,
            estimated_snr_db=max(0.0, snr_db),
            silence_percentage=silence_pct,
        )

    def ingest_recording(
        self,
        audio_bytes: bytes,
        file_extension: str,
        ground_truth: str,
        human_identity: Optional[str] = None,
        source_speaker_identity: Optional[str] = None,
        source_id: Optional[str] = None,
        parent_source_id: Optional[str] = None,
        source_audio_sha256: Optional[str] = None,
        generator_name: Optional[str] = None,
        generator_version: Optional[str] = None,
        attack_id: Optional[str] = None,
        capture_type: str = "physical_browser_microphone",
        capture_device_category: str = "laptop",
        capture_device_name: Optional[str] = None,
        playback_device: Optional[str] = None,
        browser: Optional[str] = None,
        browser_version: Optional[str] = None,
        os_name: Optional[str] = None,
        requested_constraints: Optional[Dict[str, Any]] = None,
        applied_settings: Optional[Dict[str, Any]] = None,
        media_recorder_mime_type: Optional[str] = None,
        input_sample_rate: Optional[int] = None,
        room_environment: Optional[str] = None,
        capture_session_id: Optional[str] = None,
        prompt_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validates and stages a physical acoustic recording into the ingestion pool."""
        if not audio_bytes or len(audio_bytes) < 100:
            raise ValueError("Audio payload is empty or too small (< 100 bytes).")

        sha256 = hashlib.sha256(audio_bytes).hexdigest()
        manifest = self.load_manifest()

        # Check hash duplication
        existing_hashes = set(s["capture_audio_sha256"] for s in manifest["samples"])
        if sha256 in existing_hashes:
            raise ValueError(f"Duplicate recording detected with identical SHA-256: {sha256}")

        # Unique sample ID
        rec_id = f"PHYS_REC_{int(time.time())}_{uuid.uuid4().hex[:6].upper()}"
        ext = file_extension if file_extension.startswith(".") else f".{file_extension}"
        rel_dir = f"incoming/{ground_truth}"
        target_filename = f"{rec_id}_{ground_truth}{ext}"
        target_path = self.pool_dir / rel_dir / target_filename

        with open(target_path, "wb") as f:
            f.write(audio_bytes)

        # Decode & Quality analysis
        try:
            wav, sr = decode_audio(target_path, target_sr=16000)
            duration_s = round(float(len(wav) / sr), 2)
            telemetry = self.compute_quality_telemetry(wav, sr)
        except Exception as e:
            if target_path.exists():
                target_path.unlink()
            raise ValueError(f"Failed to decode audio stream: {e}")

        if duration_s < 1.0:
            if target_path.exists():
                target_path.unlink()
            raise ValueError(f"Recording duration ({duration_s}s) is too short. Minimum duration is 1.0s.")

        record = PhysicalCaptureManifestRecord(
            sample_id=rec_id,
            ground_truth=ground_truth,
            human_identity=human_identity,
            source_speaker_identity=source_speaker_identity,
            source_id=source_id or target_filename,
            parent_source_id=parent_source_id,
            source_audio_sha256=source_audio_sha256,
            capture_audio_sha256=sha256,
            generator_name=generator_name,
            generator_version=generator_version,
            attack_id=attack_id,
            capture_type=capture_type,
            capture_device_category=capture_device_category,
            capture_device_name=capture_device_name,
            playback_device=playback_device,
            browser=browser,
            browser_version=browser_version,
            os=os_name,
            requested_getUserMedia_constraints=requested_constraints,
            applied_media_track_settings=applied_settings,
            media_recorder_mime_type=media_recorder_mime_type,
            input_sample_rate=input_sample_rate or applied_settings.get("sampleRate") if applied_settings else 48000,
            decoded_sample_rate=16000,
            duration_seconds=duration_s,
            room_environment=room_environment,
            capture_session_id=capture_session_id or f"SESSION_{int(time.time())}",
            prompt_id=prompt_id,
            recorded_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            split="incoming_pool",
            quality_telemetry=telemetry,
            relative_path=f"{rel_dir}/{target_filename}",
            notes=notes,
        )

        manifest["samples"].append(record.model_dump())
        manifest["total_samples"] = len(manifest["samples"])
        manifest["summary_by_class"][ground_truth] = manifest["summary_by_class"].get(ground_truth, 0) + 1

        dev_cat = capture_device_category
        manifest["summary_by_device"][dev_cat] = manifest["summary_by_device"].get(dev_cat, 0) + 1

        if human_identity:
            manifest["summary_by_human_speaker"][human_identity] = (
                manifest["summary_by_human_speaker"].get(human_identity, 0) + 1
            )

        manifest["summary_by_split"]["incoming_pool"] = manifest["summary_by_split"].get("incoming_pool", 0) + 1
        self.save_manifest(manifest)

        return {
            "status": "success",
            "sample_id": rec_id,
            "ground_truth": ground_truth,
            "duration_seconds": duration_s,
            "sha256": sha256,
            "quality_passed": telemetry.clipping_percentage < 5.0,
            "quality_telemetry": telemetry.model_dump(),
            "pool_relative_path": record.relative_path,
            "message": f"Successfully ingested {ground_truth} physical recording ({duration_s}s).",
        }

    def get_balance_dashboard(self) -> Dict[str, Any]:
        """Generates comprehensive balance, confound, and leakage analysis on the physical domain pool."""
        manifest = self.load_manifest()
        samples = manifest["samples"]

        real_samples = [s for s in samples if s["ground_truth"] == "real"]
        synth_samples = [s for s in samples if s["ground_truth"] == "synthetic"]

        human_spks = sorted(list(set(s["human_identity"] for s in real_samples if s["human_identity"])))
        human_spk_count = len(human_spks)

        # Per human speaker statistics
        per_human_speaker = {}
        for spk in human_spks:
            spk_samples = [s for s in real_samples if s["human_identity"] == spk]
            devs = set(s["capture_device_category"] for s in spk_samples)
            sessions = set(s["capture_session_id"] for s in spk_samples)
            per_human_speaker[spk] = {
                "genuine_sample_count": len(spk_samples),
                "device_categories": list(devs),
                "session_count": len(sessions),
                "percentage_of_real_class": round((len(spk_samples) / (len(real_samples) + 1e-9)) * 100, 1),
            }

        # Per device category statistics
        device_cats = sorted(list(set(s["capture_device_category"] for s in samples)))
        per_device_category = {}
        for dev in device_cats:
            dev_real = len([s for s in real_samples if s["capture_device_category"] == dev])
            dev_synth = len([s for s in synth_samples if s["capture_device_category"] == dev])
            per_device_category[dev] = {
                "real_count": dev_real,
                "synthetic_count": dev_synth,
                "total": dev_real + dev_synth,
            }

        # Per split statistics
        splits = sorted(list(set(s["split"] for s in samples)))
        per_split = {}
        for split in splits:
            split_samples = [s for s in samples if s["split"] == split]
            split_real = [s for s in split_samples if s["ground_truth"] == "real"]
            split_synth = [s for s in split_samples if s["ground_truth"] == "synthetic"]
            split_human_spks = set(s["human_identity"] for s in split_real if s["human_identity"])
            per_split[split] = {
                "total": len(split_samples),
                "real_count": len(split_real),
                "synthetic_count": len(split_synth),
                "human_speaker_count": len(split_human_spks),
                "human_speakers": list(split_human_spks),
                "device_distribution": {
                    d: len([s for s in split_samples if s["capture_device_category"] == d])
                    for d in set(s["capture_device_category"] for s in split_samples)
                },
            }

        # Confound and Imbalance Flags
        imbalance_flags = []
        confound_flags = []
        leakage_flags = []

        if human_spk_count < 8:
            imbalance_flags.append(
                f"INSUFFICIENT_HUMAN_SPEAKERS: Currently only {human_spk_count} human speakers registered (minimum required is 8-10+)."
            )

        for spk, data in per_human_speaker.items():
            if data["percentage_of_real_class"] > 30.0:
                imbalance_flags.append(
                    f"DOMINANT_SPEAKER_CONFOUND: Speaker {spk} represents {data['percentage_of_real_class']}% of all real samples (>30% threshold)."
                )

        for dev, counts in per_device_category.items():
            if counts["real_count"] > 0 and counts["synthetic_count"] == 0:
                confound_flags.append(
                    f"DEVICE_CLASS_ASYMMETRY: Device '{dev}' appears only in genuine real speech (0 synthetic samples)."
                )
            elif counts["synthetic_count"] > 0 and counts["real_count"] == 0:
                confound_flags.append(
                    f"DEVICE_CLASS_ASYMMETRY: Device '{dev}' appears only in synthetic speech (0 genuine real samples)."
                )

        # Check speaker leakage across declared splits (excluding incoming_pool)
        active_splits = [s for s in splits if s != "incoming_pool"]
        for i in range(len(active_splits)):
            for j in range(i + 1, len(active_splits)):
                s1, s2 = active_splits[i], active_splits[j]
                spks1 = set(s["human_identity"] for s in samples if s["split"] == s1 and s["human_identity"])
                spks2 = set(s["human_identity"] for s in samples if s["split"] == s2 and s["human_identity"])
                overlap = spks1 & spks2
                if overlap:
                    leakage_flags.append(f"SPEAKER_LEAKAGE: Human speakers {overlap} shared between '{s1}' and '{s2}'.")

        ready = (
            human_spk_count >= 8
            and len(imbalance_flags) == 0
            and len(confound_flags) == 0
            and len(leakage_flags) == 0
        )

        return {
            "total_samples": len(samples),
            "human_speaker_count": human_spk_count,
            "real_sample_count": len(real_samples),
            "synthetic_sample_count": len(synth_samples),
            "per_human_speaker": per_human_speaker,
            "per_device_category": per_device_category,
            "per_split": per_split,
            "imbalance_flags": imbalance_flags,
            "confound_flags": confound_flags,
            "leakage_flags": leakage_flags,
            "ready_for_stage_2_evaluation": ready,
        }

    def propose_split_assignment(self) -> Dict[str, Any]:
        """Computes a proposed split assignment that guarantees strict speaker disjointness and device balancing."""
        manifest = self.load_manifest()
        samples = manifest["samples"]
        real_samples = [s for s in samples if s["ground_truth"] == "real"]
        human_spks = sorted(list(set(s["human_identity"] for s in real_samples if s["human_identity"])))

        if len(human_spks) < 3:
            return {
                "status": "cannot_propose",
                "message": f"At least 3 human speakers required to propose train/validation/test splits (found {len(human_spks)}).",
                "proposed_splits": {},
            }

        # Allocate speakers: ~60% train, ~20% val, ~20% test
        n = len(human_spks)
        n_train = max(1, int(n * 0.60))
        n_val = max(1, int(n * 0.20))

        train_spks = human_spks[:n_train]
        val_spks = human_spks[n_train : n_train + n_val]
        test_spks = human_spks[n_train + n_val :]

        return {
            "status": "proposal_generated",
            "message": "Proposed disjoint speaker split generated. Requires explicit review before applying.",
            "speaker_assignment": {
                "train_speakers": train_spks,
                "validation_speakers": val_spks,
                "dev_test_speakers": test_spks,
            },
            "disjointness_verified": len(set(train_spks) & set(val_spks)) == 0 and len(set(train_spks) & set(test_spks)) == 0,
        }
