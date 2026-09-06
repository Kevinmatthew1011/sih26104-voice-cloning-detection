"""
Unit and API tests for Speaker Verification & Impersonation Engine.
"""

import io
import numpy as np
import pytest
import soundfile as sf
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.speaker_verification_service import (
    SpeakerVerificationService,
    MATCH_THRESHOLD,
    MISMATCH_THRESHOLD,
)
from app.schemas.speaker_verification import VerificationStateEnum


def make_test_wav(freq: float, duration: float = 3.0, sr: int = 16000) -> bytes:
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    # Harmonics to give distinct acoustic spectral fingerprints
    signal = 0.4 * np.sin(2 * np.pi * freq * t) + 0.2 * np.sin(2 * np.pi * 2 * freq * t) + 0.1 * np.sin(2 * np.pi * 3 * freq * t)
    bio = io.BytesIO()
    sf.write(bio, signal.astype(np.float32), sr, format="WAV", subtype="PCM_16")
    return bio.getvalue()


@pytest.fixture
def temp_speaker_service(tmp_path):
    store_file = tmp_path / "test_speakers.json"
    return SpeakerVerificationService(store_path=store_file)


def test_enroll_and_verify_match(temp_speaker_service):
    speaker_audio = make_test_wav(freq=150.0, duration=3.0)
    enroll_res = temp_speaker_service.enroll("SPK_TEST_01", "Alice - CFO", speaker_audio)
    assert enroll_res.speaker_id == "SPK_TEST_01"
    assert enroll_res.embedding_dim == 36

    # Verify identical voice
    verify_res = temp_speaker_service.verify("SPK_TEST_01", speaker_audio)
    assert verify_res.state == VerificationStateEnum.IDENTITY_MATCH
    assert verify_res.similarity_score is not None
    assert verify_res.similarity_score >= MATCH_THRESHOLD


def test_verify_mismatch_impersonation(temp_speaker_service):
    alice_audio = make_test_wav(freq=120.0, duration=3.0)
    temp_speaker_service.enroll("SPK_ALICE", "Alice", alice_audio)

    # Impersonator with completely different vocal frequency & formant profile
    impersonator_audio = make_test_wav(freq=350.0, duration=3.0)
    verify_res = temp_speaker_service.verify("SPK_ALICE", impersonator_audio)
    assert verify_res.state in (VerificationStateEnum.IDENTITY_MISMATCH, VerificationStateEnum.IDENTITY_UNCERTAIN)
    assert verify_res.similarity_score < MATCH_THRESHOLD


def test_verify_unenrolled_speaker(temp_speaker_service):
    some_audio = make_test_wav(freq=200.0, duration=2.0)
    verify_res = temp_speaker_service.verify("SPK_NONEXISTENT", some_audio)
    assert verify_res.state == VerificationStateEnum.NOT_ENROLLED


def test_verify_insufficient_audio(temp_speaker_service):
    speaker_audio = make_test_wav(freq=150.0, duration=3.0)
    temp_speaker_service.enroll("SPK_TEST_02", "Bob", speaker_audio)

    short_audio = make_test_wav(freq=150.0, duration=0.3)
    verify_res = temp_speaker_service.verify("SPK_TEST_02", short_audio)
    assert verify_res.state == VerificationStateEnum.INSUFFICIENT_AUDIO


@pytest.mark.asyncio
async def test_speaker_api_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        wav_bytes = make_test_wav(freq=180.0, duration=2.5)

        # 1. Enroll
        enroll_data = {"speaker_id": "SPK_API_01", "speaker_name": "Carol Manager"}
        files = {"file": ("enroll.wav", wav_bytes, "audio/wav")}
        res = await client.post("/api/v1/speaker/enroll", data=enroll_data, files=files)
        assert res.status_code == 201
        assert res.json()["speaker_id"] == "SPK_API_01"

        # 2. List
        list_res = await client.get("/api/v1/speaker/enrolled")
        assert list_res.status_code == 200
        speakers = list_res.json()
        assert any(s["speaker_id"] == "SPK_API_01" for s in speakers)

        # 3. Verify
        verify_data = {"speaker_id": "SPK_API_01"}
        files_verify = {"file": ("verify.wav", wav_bytes, "audio/wav")}
        ver_res = await client.post("/api/v1/speaker/verify", data=verify_data, files=files_verify)
        assert ver_res.status_code == 200
        assert ver_res.json()["state"] == "IDENTITY_MATCH"

        # 4. Clean up / delete
        del_res = await client.delete("/api/v1/speaker/SPK_API_01")
        assert del_res.status_code == 200
