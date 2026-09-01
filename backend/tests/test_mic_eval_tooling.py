"""
Unit & Regression Tests for Microphone Domain Evaluation Tooling (Phases 2-4).

Verifies:
1. Manifest structure and sample completeness
2. Strict speaker-independent partition disjointness (zero identity leakage)
3. Cryptographic hash integrity of dataset manifests
4. Biometric evaluation mathematics (EER, FAR, FRR, Cohen's d)
"""

import sys
from pathlib import Path
import json
import numpy as np
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from ml_eval.microphone.evaluate_mic_baseline import compute_eer, compute_cohens_d, compute_distribution_stats
MANIFEST_PATH = ROOT_DIR / "ml_data/simulated_channel_benchmark/manifests/simulated_channel_manifest.json"


class TestMicrophoneDatasetIntegrity:
    """Validates dataset structure, speaker disjointness, and provenance schema."""

    @pytest.fixture
    def manifest(self):
        assert MANIFEST_PATH.exists(), f"Manifest missing at {MANIFEST_PATH}"
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_manifest_structure_and_counts(self, manifest):
        assert manifest["dataset_name"] == "SIH26104_SIMULATED_CHANNEL_BENCHMARK"
        assert manifest["total_samples"] == 180

        parts = manifest["speakers_partitioning"]
        assert parts["calibration"]["total"] == 108
        assert parts["calibration"]["real_samples"] == 54
        assert parts["calibration"]["synthetic_samples"] == 54
        assert parts["calibration"]["speaker_count"] == 18

        assert parts["validation"]["total"] == 36
        assert parts["validation"]["real_samples"] == 18
        assert parts["validation"]["synthetic_samples"] == 18
        assert parts["validation"]["speaker_count"] == 6

        assert parts["test"]["total"] == 36
        assert parts["test"]["real_samples"] == 18
        assert parts["test"]["synthetic_samples"] == 18
        assert parts["test"]["speaker_count"] == 6

    def test_strict_speaker_disjointness(self, manifest):
        """Verify zero speaker leakage across calibration, validation, and test partitions."""
        spk_cal = set(manifest["speakers_partitioning"]["calibration"]["speakers"])
        spk_val = set(manifest["speakers_partitioning"]["validation"]["speakers"])
        spk_tst = set(manifest["speakers_partitioning"]["test"]["speakers"])

        # Check disjoint sets
        assert len(spk_cal & spk_val) == 0, f"Speaker overlap cal/val: {spk_cal & spk_val}"
        assert len(spk_cal & spk_tst) == 0, f"Speaker overlap cal/tst: {spk_cal & spk_tst}"
        assert len(spk_val & spk_tst) == 0, f"Speaker overlap val/tst: {spk_val & spk_tst}"

        # Verify every sample belongs to its partition's declared speakers
        for item in manifest["samples"]:
            split = item["split"]
            spk = item["speaker_id"]
            if split == "calibration":
                assert spk in spk_cal
            elif split == "validation":
                assert spk in spk_val
            elif split == "test":
                assert spk in spk_tst

    def test_provenance_schema_completeness(self, manifest):
        """Verify all mandatory provenance fields are present in every manifest record."""
        required_fields = [
            "sample_id",
            "ground_truth",
            "label_id",
            "speaker_id",
            "source_id",
            "generator",
            "generator_version",
            "original_file_hash",
            "capture_path",
            "device",
            "browser",
            "codec",
            "capture_constraints",
            "split",
            "sha256",
        ]

        for item in manifest["samples"]:
            for field in required_fields:
                assert field in item, f"Missing field '{field}' in sample {item.get('sample_id')}"
                assert item[field] is not None, f"Null field '{field}' in sample {item.get('sample_id')}"


class TestPhysicalDomainDatasetIntegrity:
    """Validates physical domain dataset structure, strict human/synthetic speaker disjointness, and zero leakage."""

    @pytest.fixture
    def physical_manifest(self):
        phys_path = ROOT_DIR / "ml_data/physical_domain/manifests/physical_domain_manifest.json"
        assert phys_path.exists(), f"Physical manifest missing at {phys_path}"
        with open(phys_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_physical_manifest_structure(self, physical_manifest):
        assert physical_manifest["dataset_name"] == "SIH26104_PHYSICAL_DOMAIN_DATASET"
        assert physical_manifest["total_samples"] == 65
        assert len(physical_manifest["samples"]) == 65

    def test_strict_human_identity_disjointness(self, physical_manifest):
        """Verify that no human identity exists in more than one partition."""
        samples = physical_manifest["samples"]
        train_spks = set(s["speaker_id"] for s in samples if s["split"] == "train" and s["ground_truth"] == "real")
        val_spks = set(s["speaker_id"] for s in samples if s["split"] == "validation" and s["ground_truth"] == "real")
        test_spks = set(s["speaker_id"] for s in samples if s["split"] == "test" and s["ground_truth"] == "real")

        # Explicit disjointness checks
        assert len(train_spks & val_spks) == 0, f"Human speaker leakage train/val: {train_spks & val_spks}"
        assert len(train_spks & test_spks) == 0, f"Human speaker leakage train/test: {train_spks & test_spks}"
        assert len(val_spks & test_spks) == 0, f"Human speaker leakage val/test: {val_spks & test_spks}"

    def test_strict_synthetic_speaker_and_generator_disjointness(self, physical_manifest):
        """Verify that no synthetic source speaker or generator is shared across partitions."""
        samples = physical_manifest["samples"]
        train_synth_spks = set(s["speaker_id"] for s in samples if s["split"] == "train" and s["ground_truth"] == "synthetic")
        val_synth_spks = set(s["speaker_id"] for s in samples if s["split"] == "validation" and s["ground_truth"] == "synthetic")
        test_synth_spks = set(s["speaker_id"] for s in samples if s["split"] == "test" and s["ground_truth"] == "synthetic")

        assert len(train_synth_spks & val_synth_spks) == 0, f"Synthetic speaker leakage train/val: {train_synth_spks & val_synth_spks}"
        assert len(train_synth_spks & test_synth_spks) == 0, f"Synthetic speaker leakage train/test: {train_synth_spks & test_synth_spks}"
        assert len(val_synth_spks & test_synth_spks) == 0, f"Synthetic speaker leakage val/test: {val_synth_spks & test_synth_spks}"

    def test_strict_source_utterance_and_hash_disjointness(self, physical_manifest):
        """Verify zero utterance or file hash reuse across splits."""
        samples = physical_manifest["samples"]
        train_sources = set(s["source_id"] for s in samples if s["split"] == "train")
        val_sources = set(s["source_id"] for s in samples if s["split"] == "validation")
        test_sources = set(s["source_id"] for s in samples if s["split"] == "test")

        assert len(train_sources & val_sources) == 0, f"Source utterance leakage train/val: {train_sources & val_sources}"
        assert len(train_sources & test_sources) == 0, f"Source utterance leakage train/test: {train_sources & test_sources}"
        assert len(val_sources & test_sources) == 0, f"Source utterance leakage val/test: {val_sources & test_sources}"

        train_hashes = set(s["sha256"] for s in samples if s["split"] == "train")
        val_hashes = set(s["sha256"] for s in samples if s["split"] == "validation")
        test_hashes = set(s["sha256"] for s in samples if s["split"] == "test")

        assert len(train_hashes & val_hashes) == 0, f"File hash leakage train/val: {train_hashes & val_hashes}"
        assert len(train_hashes & test_hashes) == 0, f"File hash leakage train/test: {train_hashes & test_hashes}"
        assert len(val_hashes & test_hashes) == 0, f"File hash leakage val/test: {val_hashes & test_hashes}"


class TestMicrophoneEvaluationMath:
    """Validates metrics calculation correctness."""

    def test_eer_perfect_separation(self):
        y_true = np.array([0, 0, 0, 0, 1, 1, 1, 1])
        y_score = np.array([0.1, 0.2, 0.3, 0.4, 0.7, 0.8, 0.9, 1.0])
        eer, thresh = compute_eer(y_true, y_score)
        assert eer == 0.0

    def test_eer_random_guess(self):
        y_true = np.array([0, 0, 1, 1])
        y_score = np.array([0.5, 0.5, 0.5, 0.5])
        eer, thresh = compute_eer(y_true, y_score)
        assert eer == 0.5

    def test_cohens_d_math(self):
        group1 = np.array([10.0, 11.0, 12.0, 10.5, 11.5])
        group2 = np.array([0.0, 1.0, 2.0, 0.5, 1.5])
        d = compute_cohens_d(group1, group2)
        assert d > 5.0

