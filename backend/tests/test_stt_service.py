"""
Unit tests for STT Service and Endpoint.
"""

import numpy as np
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.stt_service import get_stt_service, STTService
from app.schemas.stt import TranscriptionResponse


def generate_tone_wav(duration: float = 1.0, sr: int = 16000) -> bytes:
    import io
    import soundfile as sf
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    # 440 Hz sine tone with speech-like modulation
    signal = 0.5 * np.sin(2 * np.pi * 440 * t)
    bio = io.BytesIO()
    sf.write(bio, signal.astype(np.float32), sr, format="WAV", subtype="PCM_16")
    return bio.getvalue()


def test_stt_service_on_empty_audio():
    service = get_stt_service()
    res = service.transcribe(np.zeros(100, dtype=np.float32))
    assert isinstance(res, TranscriptionResponse)
    assert res.text == ""
    assert res.confidence == 0.0


def test_stt_service_on_tone_audio():
    service = get_stt_service()
    wav_bytes = generate_tone_wav(duration=1.5)
    res = service.transcribe(wav_bytes)
    assert isinstance(res, TranscriptionResponse)
    assert res.duration_seconds >= 1.4
    assert res.engine == "wav2vec2_asr_base_960h"
    assert res.tokens == []  # Greedy CTC does not provide aligned word timestamps.


@pytest.mark.asyncio
async def test_stt_api_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        wav_bytes = generate_tone_wav(duration=1.0)
        files = {"file": ("test.wav", wav_bytes, "audio/wav")}
        response = await client.post("/api/v1/stt/transcribe", files=files)
        assert response.status_code == 200
        data = response.json()
        assert "text" in data
        assert "duration_seconds" in data
        assert data["duration_seconds"] >= 0.9


def test_stt_unavailable_never_fabricates_transcript(monkeypatch):
    from app.services.stt_service import STTUnavailableError
    monkeypatch.setattr(STTService, "_init_attempted", True)
    monkeypatch.setattr(STTService, "_model", None)
    monkeypatch.setattr(STTService, "_decoder", None)
    with pytest.raises(STTUnavailableError):
        STTService().transcribe(generate_tone_wav())


@pytest.mark.asyncio
async def test_stt_api_unavailable_and_invalid_upload(monkeypatch):
    monkeypatch.setattr(STTService, "_init_attempted", True)
    monkeypatch.setattr(STTService, "_model", None)
    monkeypatch.setattr(STTService, "_decoder", None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        unavailable = await client.post("/api/v1/stt/transcribe", files={"file": ("test.wav", generate_tone_wav(), "audio/wav")})
        assert unavailable.status_code == 503
        invalid = await client.post("/api/v1/stt/transcribe", files={"file": ("test.wav", b"not an audio container", "audio/wav")})
        assert invalid.status_code == 400
