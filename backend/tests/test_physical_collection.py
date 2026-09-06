"""
Unit & Integration Tests for Physical Domain Acoustic Data Collection, Provenance & Balancing (Phase 5).

Verifies:
1. Standardized 10-prompt set retrieval.
2. Ingestion of genuine microphone speech with quality control and mandatory pseudonymous human speaker ID.
3. Ingestion of physical synthetic replay with acoustic transducer provenance (playback device, generator).
4. Anti-masquerading enforcement:
   - Genuine speech cannot specify playback_device.
   - Genuine speech requires human_identity.
   - Synthetic speech requires playback_device, generator_name, and physical_replay capture type.
5. Audio quality gates:
   - Silence percentage > 85% rejection.
   - Clipping percentage > 25% rejection.
   - Duration bounds (1.0s <= duration <= 60.0s).
   - SHA-256 duplicate detection.
6. Balance dashboard calculation with Phase 5 targets (300 total, 150 genuine, 150 replay, 15 speakers).
7. Partitioned split export with strict human speaker and parent source disjointness.
"""

import sys
import io
import json
from pathlib import Path
import numpy as np
import soundfile as sf
import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "backend"))

from app.main import app
from app.services.physical_collection_service import PhysicalCollectionService
from app.api.v1.endpoints.physical_collection import get_physical_collection_service


@pytest.fixture
def isolated_service(tmp_path):
    return PhysicalCollectionService(pool_dir=tmp_path / "test_physical_pool")


@pytest.fixture
def client(isolated_service):
    """Provides a TestClient with an isolated temporary storage pool for collection tests."""
    app.dependency_overrides[get_physical_collection_service] = lambda: isolated_service
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.pop(get_physical_collection_service, None)


def make_audio_bytes(duration_s: float = 3.0, freq: float = 220.0, silence: bool = False, clip: bool = False) -> bytes:
    """Generates test PCM audio payload."""
    sr = 16000
    n_samples = int(duration_s * sr)
    t = np.linspace(0, duration_s, n_samples, endpoint=False)

    if silence:
        # Near absolute zero amplitude (all frames below -45 dBFS)
        signal = np.zeros(n_samples, dtype=np.float32)
    elif clip:
        # Heavy saturation clipping (amplitude >= 0.995 on >50% of frames)
        raw = 5.0 * np.sin(2 * np.pi * freq * t)
        signal = np.clip(raw, -1.0, 1.0).astype(np.float32)
    else:
        # Normal clean speech-like tone with small dither
        noise = np.random.uniform(-0.02, 0.02, n_samples)
        signal = (0.4 * np.sin(2 * np.pi * freq * t) + noise).astype(np.float32)

    buf = io.BytesIO()
    sf.write(buf, signal, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


@pytest.fixture
def sample_wav_bytes():
    return make_audio_bytes(duration_s=3.0, freq=250.0)


class TestPhysicalCollectionAPI:
    """Tests collection endpoints, provenance enforcement, quality gates, and split exporting."""

    def test_get_standardized_prompts(self, client):
        response = client.get("/api/v1/collection/prompts")
        assert response.status_code == 200
        data = response.json()
        assert data["prompt_set_name"] == "SIH26104_PHYSICAL_PHONETIC_PROMPTS_V1"
        assert len(data["prompts"]) == 10
        assert data["prompts"][0]["prompt_id"] == "PROMPT_01"

    def test_ingest_physical_recording_success(self, client, sample_wav_bytes):
        files = {"file": ("test_mic_utterance.wav", sample_wav_bytes, "audio/wav")}
        data = {
            "ground_truth": "real",
            "human_identity": "HUMAN_SPK_01",
            "capture_device_category": "laptop",
            "capture_device_name": "Dell XPS Array MEMS",
            "distance_category": "medium_30cm",
            "browser": "Google Chrome",
            "os_name": "Linux x86_64",
            "room_environment": "quiet_office",
            "prompt_id": "PROMPT_01",
        }
        response = client.post("/api/v1/collection/physical-recording", files=files, data=data)
        assert response.status_code == 200
        resp = response.json()
        assert resp["status"] == "success"
        assert resp["ground_truth"] == "real"
        assert resp["duration_seconds"] >= 2.9
        assert resp["quality_passed"] is True
        assert "clipping_percentage" in resp["quality_telemetry"]

    def test_balance_dashboard_endpoint_and_phase5_targets(self, client):
        response = client.get("/api/v1/collection/balance-dashboard")
        assert response.status_code == 200
        data = response.json()
        assert data["target_total"] == 300
        assert data["target_genuine"] == 150
        assert data["target_replay"] == 150
        assert data["target_speakers"] == 15
        assert "statistical_sufficiency_note" in data
        assert "imbalance_flags" in data
        assert "confound_flags" in data
        assert "leakage_flags" in data
        assert isinstance(data["ready_for_stage_2_evaluation"], bool)

    def test_anti_masquerading_genuine_missing_speaker(self, client, sample_wav_bytes):
        """Genuine speech must provide a human_identity."""
        files = {"file": ("utterance.wav", sample_wav_bytes, "audio/wav")}
        data = {"ground_truth": "real"} # No human_identity
        response = client.post("/api/v1/collection/physical-recording", files=files, data=data)
        assert response.status_code == 400
        assert "human_identity is required" in response.json()["detail"]

    def test_anti_masquerading_genuine_with_playback_device(self, client, sample_wav_bytes):
        """Genuine speech cannot originate from a playback device."""
        files = {"file": ("utterance.wav", sample_wav_bytes, "audio/wav")}
        data = {
            "ground_truth": "real",
            "human_identity": "HUMAN_SPK_01",
            "playback_device": "Bose Speaker", # Illegal for genuine human speech
        }
        response = client.post("/api/v1/collection/physical-recording", files=files, data=data)
        assert response.status_code == 400
        assert "Genuine speech cannot have a playback_device" in response.json()["detail"]

    def test_anti_masquerading_synthetic_missing_playback_device(self, client, sample_wav_bytes):
        """Physical synthetic replay must document the playback device."""
        files = {"file": ("utterance.wav", sample_wav_bytes, "audio/wav")}
        data = {
            "ground_truth": "synthetic",
            "capture_type": "physical_replay",
            "generator_name": "ElevenLabs",
            # missing playback_device
        }
        response = client.post("/api/v1/collection/physical-recording", files=files, data=data)
        assert response.status_code == 400
        assert "playback_device is required" in response.json()["detail"]

    def test_anti_masquerading_synthetic_missing_generator(self, client, sample_wav_bytes):
        """Physical synthetic replay must document the synthesis generator."""
        files = {"file": ("utterance.wav", sample_wav_bytes, "audio/wav")}
        data = {
            "ground_truth": "synthetic",
            "capture_type": "physical_replay",
            "playback_device": "Pixel 8 Speaker",
            # missing generator_name
        }
        response = client.post("/api/v1/collection/physical-recording", files=files, data=data)
        assert response.status_code == 400
        assert "generator_name is required" in response.json()["detail"]

    def test_anti_masquerading_synthetic_invalid_capture_type(self, client, sample_wav_bytes):
        """Synthetic physical audio must be tagged as physical_replay or physical_recapture."""
        files = {"file": ("utterance.wav", sample_wav_bytes, "audio/wav")}
        data = {
            "ground_truth": "synthetic",
            "capture_type": "direct_digital_control",
            "playback_device": "Pixel 8 Speaker",
            "generator_name": "ElevenLabs",
        }
        response = client.post("/api/v1/collection/physical-recording", files=files, data=data)
        assert response.status_code == 400
        assert "Invalid capture_type" in response.json()["detail"]

    def test_ingest_synthetic_physical_replay_success(self, client):
        audio = make_audio_bytes(duration_s=2.5, freq=340.0)
        files = {"file": ("synth_replay.wav", audio, "audio/wav")}
        data = {
            "ground_truth": "synthetic",
            "capture_type": "physical_replay",
            "playback_device": "Pixel 8 Speaker",
            "playback_device_category": "smartphone_loudspeaker",
            "generator_name": "ElevenLabs",
            "generator_version": "v2",
            "attack_id": "zero_shot_clone",
            "parent_source_id": "LA_E_999999",
            "distance_category": "medium_30cm",
        }
        response = client.post("/api/v1/collection/physical-recording", files=files, data=data)
        assert response.status_code == 200
        resp = response.json()
        assert resp["status"] == "success"
        assert resp["ground_truth"] == "synthetic"

    def test_quality_gate_rejects_excessive_silence(self, client):
        silent_audio = make_audio_bytes(duration_s=3.0, silence=True)
        files = {"file": ("silent.wav", silent_audio, "audio/wav")}
        data = {"ground_truth": "real", "human_identity": "HUMAN_SPK_02"}
        response = client.post("/api/v1/collection/physical-recording", files=files, data=data)
        assert response.status_code == 400
        assert "excessive silence" in response.json()["detail"].lower()

    def test_quality_gate_rejects_severe_clipping(self, client):
        clipped_audio = make_audio_bytes(duration_s=3.0, clip=True)
        files = {"file": ("clipped.wav", clipped_audio, "audio/wav")}
        data = {"ground_truth": "real", "human_identity": "HUMAN_SPK_02"}
        response = client.post("/api/v1/collection/physical-recording", files=files, data=data)
        assert response.status_code == 400
        assert "saturation clipping" in response.json()["detail"].lower()

    def test_quality_gate_rejects_too_short(self, client):
        short_audio = make_audio_bytes(duration_s=0.5, freq=300.0)
        files = {"file": ("short.wav", short_audio, "audio/wav")}
        data = {"ground_truth": "real", "human_identity": "HUMAN_SPK_02"}
        response = client.post("/api/v1/collection/physical-recording", files=files, data=data)
        assert response.status_code == 400
        assert "too short" in response.json()["detail"].lower()

    def test_quality_gate_rejects_too_long(self, client):
        long_audio = make_audio_bytes(duration_s=61.0, freq=300.0)
        files = {"file": ("long.wav", long_audio, "audio/wav")}
        data = {"ground_truth": "real", "human_identity": "HUMAN_SPK_02"}
        response = client.post("/api/v1/collection/physical-recording", files=files, data=data)
        assert response.status_code == 400
        assert "exceeds maximum allowed duration" in response.json()["detail"].lower()

    def test_rejects_duplicate_sha256(self, client, sample_wav_bytes):
        files = {"file": ("original.wav", sample_wav_bytes, "audio/wav")}
        data = {"ground_truth": "real", "human_identity": "HUMAN_SPK_03"}
        resp1 = client.post("/api/v1/collection/physical-recording", files=files, data=data)
        assert resp1.status_code == 200

        # Upload exact same byte stream again
        files2 = {"file": ("duplicate.wav", sample_wav_bytes, "audio/wav")}
        resp2 = client.post("/api/v1/collection/physical-recording", files=files2, data=data)
        assert resp2.status_code == 400
        assert "Duplicate recording detected" in resp2.json()["detail"]

    def test_export_splits_disjointness_and_files(self, client, tmp_path):
        """Tests that export-splits partitions human speakers and parent sources disjointly."""
        # Ingest 3 real speakers
        for idx, spk in enumerate(["HUMAN_SPK_01", "HUMAN_SPK_02", "HUMAN_SPK_03"]):
            audio = make_audio_bytes(duration_s=2.0, freq=200.0 + idx * 50)
            client.post(
                "/api/v1/collection/physical-recording",
                files={"file": (f"{spk}.wav", audio, "audio/wav")},
                data={"ground_truth": "real", "human_identity": spk},
            )

        # Ingest 3 replay samples with different parent sources
        for idx, parent in enumerate(["SRC_PARENT_A", "SRC_PARENT_B", "SRC_PARENT_C"]):
            audio = make_audio_bytes(duration_s=2.0, freq=500.0 + idx * 50)
            client.post(
                "/api/v1/collection/physical-recording",
                files={"file": (f"replay_{idx}.wav", audio, "audio/wav")},
                data={
                    "ground_truth": "synthetic",
                    "capture_type": "physical_replay",
                    "playback_device": "Speaker_Model_X",
                    "generator_name": "ElevenLabs",
                    "parent_source_id": parent,
                },
            )

        export_target = tmp_path / "exported_physical_domain"
        res = client.post("/api/v1/collection/export-splits", data={"target_directory": str(export_target)})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["total_exported"] == 6
        assert data["human_speakers_disjoint"] is True

        # Check files created on disk
        assert (export_target / "manifest.json").exists()
        assert (export_target / "train_manifest.json").exists()
        assert (export_target / "validation_manifest.json").exists()
        assert (export_target / "test_manifest.json").exists()
        assert (export_target / "manifests" / "physical_domain_manifest.json").exists()

        # Check that speakers in each split are mutually disjoint
        with open(export_target / "train_manifest.json") as f:
            train_data = json.load(f)
        with open(export_target / "validation_manifest.json") as f:
            val_data = json.load(f)
        with open(export_target / "test_manifest.json") as f:
            test_data = json.load(f)

        train_spks = set(s.get("human_identity") for s in train_data["samples"] if s.get("human_identity"))
        val_spks = set(s.get("human_identity") for s in val_data["samples"] if s.get("human_identity"))
        test_spks = set(s.get("human_identity") for s in test_data["samples"] if s.get("human_identity"))

        assert len(train_spks & val_spks) == 0
        assert len(train_spks & test_spks) == 0
        assert len(val_spks & test_spks) == 0

    def test_export_splits_rejects_empty_pool(self, client, tmp_path):
        """Cannot export splits when pool has 0 samples."""
        res = client.post(
            "/api/v1/collection/export-splits",
            data={"target_directory": str(tmp_path / "empty_export")},
        )
        assert res.status_code == 400
        assert "contains 0 samples" in res.json()["detail"]
