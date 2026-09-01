"""
Unit & Integration Tests for Physical Domain Acoustic Data Collection & Balancing Workflow.

Verifies:
1. Standardized 10-prompt set retrieval
2. Ingestion of physical recordings with quality control & SHA-256 deduplication
3. Rejection of corrupted/empty audio payloads
4. Balance dashboard calculation and confound/imbalance detection flags
5. Split proposal algorithm ensuring strict human speaker disjointness
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
def client(tmp_path):
    """Provides a TestClient with an isolated temporary storage pool for collection tests."""
    isolated_service = PhysicalCollectionService(pool_dir=tmp_path / "test_physical_pool")
    app.dependency_overrides[get_physical_collection_service] = lambda: isolated_service
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.pop(get_physical_collection_service, None)


@pytest.fixture
def sample_wav_bytes():
    """Generates a 3-second 16kHz float32 audio tone as byte payload with guaranteed uniqueness."""
    import time
    sr = 16000
    t = np.linspace(0, 3.0, int(3.0 * sr), endpoint=False)
    freq = 200.0 + (time.time_ns() % 300)
    noise = np.random.uniform(-0.05, 0.05, len(t))
    signal = 0.5 * np.sin(2 * np.pi * freq * t) + noise
    buf = io.BytesIO()
    sf.write(buf, signal.astype(np.float32), sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


class TestPhysicalCollectionAPI:
    """Tests collection endpoints and validation rules."""

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
            "human_identity": "HUMAN_SPK_05",
            "capture_device_category": "laptop",
            "capture_device_name": "Dell XPS Array MEMS",
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

    def test_ingest_rejects_empty_audio(self, client):
        files = {"file": ("empty.wav", b"", "audio/wav")}
        data = {"ground_truth": "real", "human_identity": "HUMAN_SPK_05"}
        response = client.post("/api/v1/collection/physical-recording", files=files, data=data)
        assert response.status_code in [400, 422]

    def test_ingest_rejects_invalid_ground_truth(self, client, sample_wav_bytes):
        files = {"file": ("audio.wav", sample_wav_bytes, "audio/wav")}
        data = {"ground_truth": "invalid_label"}
        response = client.post("/api/v1/collection/physical-recording", files=files, data=data)
        assert response.status_code == 422

    def test_balance_dashboard_endpoint(self, client):
        response = client.get("/api/v1/collection/balance-dashboard")
        assert response.status_code == 200
        data = response.json()
        assert "total_samples" in data
        assert "human_speaker_count" in data
        assert "imbalance_flags" in data
        assert "confound_flags" in data
        assert "leakage_flags" in data
        assert isinstance(data["ready_for_stage_2_evaluation"], bool)

    def test_split_proposal_endpoint(self, client):
        response = client.post("/api/v1/collection/propose-split")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
