import json
import time
import uuid
import hashlib
import shutil
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
        playback_device_category: Optional[str] = None,
        distance_category: Optional[str] = "medium_30cm",
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
        """Validates and stages a physical acoustic recording into the ingestion pool with strict anti-masquerading and audio quality gates."""
        if not audio_bytes or len(audio_bytes) < 100:
            raise ValueError("Audio payload is empty or too small (< 100 bytes).")

        # Anti-masquerading & provenance validation
        if ground_truth == "real":
            if not human_identity or not human_identity.strip():
                raise ValueError("human_identity is required for genuine real speech (e.g. HUMAN_SPK_01).")
            if playback_device and playback_device.strip():
                raise ValueError("Genuine speech cannot have a playback_device; genuine speech must be captured directly from a human speaker.")
        elif ground_truth == "synthetic":
            valid_replay_types = {"physical_replay", "physical_recapture"}
            if capture_type not in valid_replay_types:
                raise ValueError(
                    f"Invalid capture_type '{capture_type}' for synthetic physical audio. "
                    "Physical synthetic samples must be 'physical_replay' or 'physical_recapture'."
                )
            if not playback_device or not playback_device.strip():
                raise ValueError("playback_device is required for physical replay recordings to document acoustic transducer provenance.")
            if not generator_name or not generator_name.strip():
                raise ValueError("generator_name is required for physical replay recordings to document the source synthesis engine.")

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

        # Quality & Duration Gates
        if duration_s < 1.0:
            if target_path.exists():
                target_path.unlink()
            raise ValueError(f"Recording duration ({duration_s}s) is too short. Minimum duration is 1.0s.")

        if duration_s > 60.0:
            if target_path.exists():
                target_path.unlink()
            raise ValueError(f"Recording duration ({duration_s}s) exceeds maximum allowed duration of 60.0s.")

        if telemetry.silence_percentage > 85.0:
            if target_path.exists():
                target_path.unlink()
            raise ValueError(
                f"Recording rejected: excessive silence ({telemetry.silence_percentage}% > 85.0%). "
                "Please speak or play audio continuously throughout the recording."
            )

        if telemetry.clipping_percentage > 25.0:
            if target_path.exists():
                target_path.unlink()
            raise ValueError(
                f"Recording rejected: severe saturation clipping ({telemetry.clipping_percentage}% > 25.0%). "
                "Please lower microphone input gain and re-record."
            )

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
            playback_device_category=playback_device_category,
            distance_category=distance_category or "medium_30cm",
            browser=browser,
            browser_version=browser_version,
            os=os_name,
            requested_getUserMedia_constraints=requested_constraints,
            applied_media_track_settings=applied_settings,
            media_recorder_mime_type=media_recorder_mime_type,
            input_sample_rate=input_sample_rate or (applied_settings.get("sampleRate") if applied_settings else 48000),
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

        real_samples = [s for s in samples if s.get("ground_truth") == "real"]
        synth_samples = [s for s in samples if s.get("ground_truth") == "synthetic"]

        # Physical replay count: synthetic samples captured via physical replay with playback device
        replay_samples = [
            s for s in synth_samples
            if s.get("capture_type") in ["physical_replay", "physical_recapture"]
            and s.get("playback_device")
        ]
        physical_replay_count = len(replay_samples)

        human_spks = sorted(list(set(s["human_identity"] for s in real_samples if s.get("human_identity"))))
        human_spk_count = len(human_spks)

        # Per human speaker statistics
        per_human_speaker = {}
        for spk in human_spks:
            spk_samples = [s for s in real_samples if s.get("human_identity") == spk]
            devs = sorted(list(set(s.get("capture_device_category", "unknown") for s in spk_samples)))
            sessions = set(s.get("capture_session_id") for s in spk_samples if s.get("capture_session_id"))
            per_human_speaker[spk] = {
                "genuine_sample_count": len(spk_samples),
                "device_categories": devs,
                "session_count": len(sessions),
                "percentage_of_real_class": round((len(spk_samples) / (len(real_samples) + 1e-9)) * 100, 1),
            }

        # Per device category statistics
        device_cats = sorted(list(set(s.get("capture_device_category", "unknown") for s in samples)))
        per_device_category = {}
        for dev in device_cats:
            dev_real = len([s for s in real_samples if s.get("capture_device_category") == dev])
            dev_synth = len([s for s in synth_samples if s.get("capture_device_category") == dev])
            per_device_category[dev] = {
                "real_count": dev_real,
                "synthetic_count": dev_synth,
                "total": dev_real + dev_synth,
            }

        # Per split statistics
        splits = sorted(list(set(s.get("split", "incoming_pool") for s in samples)))
        per_split = {}
        for split in splits:
            split_samples = [s for s in samples if s.get("split") == split]
            split_real = [s for s in split_samples if s.get("ground_truth") == "real"]
            split_synth = [s for s in split_samples if s.get("ground_truth") == "synthetic"]
            split_human_spks = set(s.get("human_identity") for s in split_real if s.get("human_identity"))
            per_split[split] = {
                "total": len(split_samples),
                "real_count": len(split_real),
                "synthetic_count": len(split_synth),
                "human_speaker_count": len(split_human_spks),
                "human_speakers": sorted(list(split_human_spks)),
                "device_distribution": {
                    d: len([s for s in split_samples if s.get("capture_device_category") == d])
                    for d in set(s.get("capture_device_category", "unknown") for s in split_samples)
                },
            }

        # Detailed distributions
        generator_dist: Dict[str, int] = {}
        playback_device_dist: Dict[str, int] = {}
        distance_dist: Dict[str, int] = {}
        environment_dist: Dict[str, int] = {}

        for s in samples:
            gen = s.get("generator_name")
            if gen:
                generator_dist[gen] = generator_dist.get(gen, 0) + 1
            pb = s.get("playback_device")
            if pb:
                playback_device_dist[pb] = playback_device_dist.get(pb, 0) + 1
            dist = s.get("distance_category")
            if dist:
                distance_dist[dist] = distance_dist.get(dist, 0) + 1
            env = s.get("room_environment")
            if env:
                environment_dist[env] = environment_dist.get(env, 0) + 1

        # Confound and Imbalance Flags
        imbalance_flags = []
        confound_flags = []
        leakage_flags = []

        if human_spk_count < 15:
            imbalance_flags.append(
                f"INSUFFICIENT_HUMAN_SPEAKERS: Currently {human_spk_count}/15 target human speakers registered."
            )

        if len(real_samples) < 150:
            imbalance_flags.append(
                f"INSUFFICIENT_GENUINE_SAMPLES: Currently {len(real_samples)}/150 target genuine microphone samples collected."
            )

        if physical_replay_count < 150:
            imbalance_flags.append(
                f"INSUFFICIENT_PHYSICAL_REPLAY_SAMPLES: Currently {physical_replay_count}/150 target physical replay samples collected."
            )

        if len(real_samples) >= 10:
            for spk, data in per_human_speaker.items():
                if data["percentage_of_real_class"] > 25.0:
                    imbalance_flags.append(
                        f"DOMINANT_SPEAKER_CONFOUND: Speaker {spk} represents {data['percentage_of_real_class']}% of all real samples (>25% threshold)."
                    )

        for dev, counts in per_device_category.items():
            if counts["real_count"] > 0 and counts["synthetic_count"] == 0:
                confound_flags.append(
                    f"DEVICE_CLASS_ASYMMETRY: Device category '{dev}' has {counts['real_count']} real samples but 0 synthetic samples."
                )
            elif counts["synthetic_count"] > 0 and counts["real_count"] == 0:
                confound_flags.append(
                    f"DEVICE_CLASS_ASYMMETRY: Device category '{dev}' has {counts['synthetic_count']} synthetic samples but 0 real samples."
                )

        # Check speaker & source leakage across declared active splits
        active_splits = [s for s in splits if s != "incoming_pool"]
        for i in range(len(active_splits)):
            for j in range(i + 1, len(active_splits)):
                s1, s2 = active_splits[i], active_splits[j]
                spks1 = set(s.get("human_identity") for s in samples if s.get("split") == s1 and s.get("human_identity"))
                spks2 = set(s.get("human_identity") for s in samples if s.get("split") == s2 and s.get("human_identity"))
                overlap_spks = spks1 & spks2
                if overlap_spks:
                    leakage_flags.append(f"SPEAKER_LEAKAGE: Human speakers {sorted(list(overlap_spks))} shared between '{s1}' and '{s2}'.")

                src1 = set(s.get("parent_source_id") for s in samples if s.get("split") == s1 and s.get("parent_source_id"))
                src2 = set(s.get("parent_source_id") for s in samples if s.get("split") == s2 and s.get("parent_source_id"))
                overlap_src = src1 & src2
                if overlap_src:
                    leakage_flags.append(f"SOURCE_LEAKAGE: Parent source IDs {sorted(list(overlap_src))} shared between '{s1}' and '{s2}'.")

        ready = (
            human_spk_count >= 15
            and len(real_samples) >= 150
            and physical_replay_count >= 150
            and len(confound_flags) == 0
            and len(leakage_flags) == 0
        )

        return {
            "total_samples": len(samples),
            "target_total": 300,
            "human_speaker_count": human_spk_count,
            "target_speakers": 15,
            "real_sample_count": len(real_samples),
            "target_genuine": 150,
            "synthetic_sample_count": len(synth_samples),
            "physical_replay_count": physical_replay_count,
            "target_replay": 150,
            "per_human_speaker": per_human_speaker,
            "per_device_category": per_device_category,
            "per_split": per_split,
            "generator_distribution": generator_dist,
            "playback_device_distribution": playback_device_dist,
            "distance_distribution": distance_dist,
            "environment_distribution": environment_dist,
            "imbalance_flags": imbalance_flags,
            "confound_flags": confound_flags,
            "leakage_flags": leakage_flags,
            "ready_for_stage_2_evaluation": ready,
            "statistical_sufficiency_note": (
                "Collection target: 150 genuine + 150 physical replay samples across 15+ speakers. "
                "Meeting target progress does NOT imply statistical sufficiency or production readiness; "
                "re-evaluation on held-out test splits is mandatory before any adaptation decisions."
            ),
        }

    def propose_split_assignment(self) -> Dict[str, Any]:
        """Computes a proposed split assignment that guarantees strict speaker disjointness and device balancing."""
        manifest = self.load_manifest()
        samples = manifest["samples"]
        real_samples = [s for s in samples if s.get("ground_truth") == "real"]
        human_spks = sorted(list(set(s["human_identity"] for s in real_samples if s.get("human_identity"))))

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

    def export_splits(self, export_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        Exports collected pool samples into partitioned splits (train, validation, test)
        guaranteeing strict human speaker disjointness and parent source disjointness.
        Writes:
        - manifest.json
        - train_manifest.json
        - validation_manifest.json
        - test_manifest.json
        - manifests/physical_domain_manifest.json
        And populates split directories with audio files so standard DatasetValidator can validate the dataset.
        """
        target_dir = Path(export_dir) if export_dir else (ROOT_DIR / "ml_data" / "physical_domain")
        manifest = self.load_manifest()
        samples = manifest["samples"]

        if not samples:
            raise ValueError("Cannot export splits: physical domain pool contains 0 samples.")

        real_samples = [s for s in samples if s.get("ground_truth") == "real"]
        synth_samples = [s for s in samples if s.get("ground_truth") == "synthetic"]

        human_spks = sorted(list(set(s["human_identity"] for s in real_samples if s.get("human_identity"))))

        # Disjoint human speaker assignment
        train_spks: set = set()
        val_spks: set = set()
        test_spks: set = set()

        if len(human_spks) >= 3:
            n = len(human_spks)
            n_train = max(1, int(n * 0.60))
            n_val = max(1, int(n * 0.20))
            train_spks = set(human_spks[:n_train])
            val_spks = set(human_spks[n_train : n_train + n_val])
            test_spks = set(human_spks[n_train + n_val :])
        elif len(human_spks) == 2:
            train_spks = {human_spks[0]}
            test_spks = {human_spks[1]}
        elif len(human_spks) == 1:
            test_spks = {human_spks[0]}

        # Disjoint synthetic parent source assignment
        synth_parent_sources = sorted(list(set(
            s.get("parent_source_id") or s.get("source_id") or s["sample_id"]
            for s in synth_samples
        )))
        train_synth_sources: set = set()
        val_synth_sources: set = set()
        test_synth_sources: set = set()

        if len(synth_parent_sources) >= 3:
            n = len(synth_parent_sources)
            n_train = max(1, int(n * 0.60))
            n_val = max(1, int(n * 0.20))
            train_synth_sources = set(synth_parent_sources[:n_train])
            val_synth_sources = set(synth_parent_sources[n_train : n_train + n_val])
            test_synth_sources = set(synth_parent_sources[n_train + n_val :])
        elif len(synth_parent_sources) == 2:
            train_synth_sources = {synth_parent_sources[0]}
            test_synth_sources = {synth_parent_sources[1]}
        elif len(synth_parent_sources) == 1:
            test_synth_sources = {synth_parent_sources[0]}

        # Assign split to each sample
        split_records: Dict[str, List[Dict[str, Any]]] = {
            "train": [],
            "validation": [],
            "test": [],
        }

        for s in real_samples:
            spk = s.get("human_identity")
            if spk in train_spks:
                target_split = "train"
            elif spk in val_spks:
                target_split = "validation"
            else:
                target_split = "test"
            s_copy = dict(s)
            s_copy["split"] = target_split
            split_records[target_split].append(s_copy)

        for s in synth_samples:
            parent = s.get("parent_source_id") or s.get("source_id") or s["sample_id"]
            if parent in train_synth_sources:
                target_split = "train"
            elif parent in val_synth_sources:
                target_split = "validation"
            else:
                target_split = "test"
            s_copy = dict(s)
            s_copy["split"] = target_split
            split_records[target_split].append(s_copy)

        # Prepare directory structure
        for split in ["train", "validation", "test"]:
            (target_dir / split / "real").mkdir(parents=True, exist_ok=True)
            (target_dir / split / "synthetic").mkdir(parents=True, exist_ok=True)
        (target_dir / "manifests").mkdir(parents=True, exist_ok=True)

        # Copy audio files into structure
        exported_samples = []
        for split_name, records in split_records.items():
            for rec in records:
                src_path = self.pool_dir / rec["relative_path"]
                gt = rec["ground_truth"]
                dst_filename = Path(rec["relative_path"]).name
                dst_path = target_dir / split_name / gt / dst_filename
                if src_path.exists():
                    shutil.copy2(src_path, dst_path)
                rec_exported = dict(rec)
                rec_exported["relative_path"] = f"{split_name}/{gt}/{dst_filename}"
                exported_samples.append(rec_exported)

        # Write individual manifests
        all_manifest_data = {
            "dataset_name": "SIH26104_PHYSICAL_DOMAIN",
            "version": "1.0",
            "description": "Multi-speaker, multi-device physical acoustic speech dataset with strictly disjoint human speakers.",
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_samples": len(exported_samples),
            "speakers_partitioning": {
                "train": {
                    "total": len(split_records["train"]),
                    "real_samples": len([r for r in split_records["train"] if r["ground_truth"] == "real"]),
                    "synthetic_samples": len([r for r in split_records["train"] if r["ground_truth"] == "synthetic"]),
                    "speaker_count": len(train_spks),
                    "speakers": sorted(list(train_spks)),
                },
                "validation": {
                    "total": len(split_records["validation"]),
                    "real_samples": len([r for r in split_records["validation"] if r["ground_truth"] == "real"]),
                    "synthetic_samples": len([r for r in split_records["validation"] if r["ground_truth"] == "synthetic"]),
                    "speaker_count": len(val_spks),
                    "speakers": sorted(list(val_spks)),
                },
                "test": {
                    "total": len(split_records["test"]),
                    "real_samples": len([r for r in split_records["test"] if r["ground_truth"] == "real"]),
                    "synthetic_samples": len([r for r in split_records["test"] if r["ground_truth"] == "synthetic"]),
                    "speaker_count": len(test_spks),
                    "speakers": sorted(list(test_spks)),
                },
            },
            "samples": exported_samples,
        }

        manifest_paths = {
            "manifest": str(target_dir / "manifest.json"),
            "train_manifest": str(target_dir / "train_manifest.json"),
            "validation_manifest": str(target_dir / "validation_manifest.json"),
            "test_manifest": str(target_dir / "test_manifest.json"),
            "physical_domain_manifest": str(target_dir / "manifests" / "physical_domain_manifest.json"),
        }

        with open(target_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(all_manifest_data, f, indent=2)

        with open(target_dir / "manifests" / "physical_domain_manifest.json", "w", encoding="utf-8") as f:
            json.dump(all_manifest_data, f, indent=2)

        for s_name in ["train", "validation", "test"]:
            s_data = dict(all_manifest_data)
            s_data["samples"] = [s for s in exported_samples if s["split"] == s_name]
            s_data["total_samples"] = len(s_data["samples"])
            with open(target_dir / f"{s_name}_manifest.json", "w", encoding="utf-8") as f:
                json.dump(s_data, f, indent=2)

        # Disjointness check
        disjoint = (
            len(train_spks & val_spks) == 0
            and len(train_spks & test_spks) == 0
            and len(val_spks & test_spks) == 0
        )

        return {
            "status": "success",
            "exported_at": all_manifest_data["exported_at"],
            "total_exported": len(exported_samples),
            "train_count": len(split_records["train"]),
            "validation_count": len(split_records["validation"]),
            "test_count": len(split_records["test"]),
            "export_directory": str(target_dir),
            "manifest_paths": manifest_paths,
            "human_speakers_disjoint": disjoint,
            "message": f"Successfully exported {len(exported_samples)} samples to {target_dir} with strict speaker disjointness.",
        }
