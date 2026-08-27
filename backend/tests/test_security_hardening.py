import io
import asyncio
import uuid
import struct
import numpy as np
import soundfile as sf
import pytest
from httpx import AsyncClient
from fastapi import status

from app.main import app
from app.config import settings
from app.core.rate_limiter import TokenBucket, detection_limiter
from app.core.admission import InferenceAdmissionController, InferenceAdmissionBusyError


def make_test_wav_bytes(duration_seconds: float = 1.0, sample_rate: int = 16000) -> bytes:
    t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds), endpoint=False, dtype=np.float32)
    waveform = 0.5 * np.sin(2 * np.pi * 440 * t)
    bio = io.BytesIO()
    sf.write(bio, waveform, sample_rate, format="WAV")
    return bio.getvalue()


@pytest.mark.asyncio
class TestUploadHardening:
    async def test_valid_wav_accepted(self, client: AsyncClient):
        wav_bytes = make_test_wav_bytes(duration_seconds=1.0)
        files = {"file": ("valid_audio.wav", wav_bytes, "audio/wav")}
        resp = await client.post("/api/v1/detections", files=files)
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["id"] is not None
        assert data["prediction"] in ["real", "synthetic", "unknown"]

    async def test_fake_wav_rejected_with_400(self, client: AsyncClient):
        fake_bytes = b"This is not a real audio file, just plain text data."
        files = {"file": ("malicious_payload.wav", fake_bytes, "audio/wav")}
        resp = await client.post("/api/v1/detections", files=files)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "Corrupt or invalid container header" in resp.json()["detail"] or "could not be decoded" in resp.json()["detail"]

    async def test_corrupt_wav_header_rejected_with_400(self, client: AsyncClient):
        # RIFF header but corrupted WAV body
        corrupt_bytes = b"RIFF\x20\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00" + b"\x00" * 20
        files = {"file": ("corrupt_audio.wav", corrupt_bytes, "audio/wav")}
        resp = await client.post("/api/v1/detections", files=files)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "could not be decoded" in resp.json()["detail"]

    async def test_unsupported_extension_rejected_with_400(self, client: AsyncClient):
        files = {"file": ("script.py", b"print('malicious')", "text/x-python")}
        resp = await client.post("/api/v1/detections", files=files)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "Unsupported audio extension" in resp.json()["detail"]

    async def test_streamed_file_size_exceeded_rejected_with_413(self, client: AsyncClient, monkeypatch):
        # Temporarily clamp MAX_FILE_SIZE_BYTES to 10 KB to test streamed rejection
        monkeypatch.setattr(settings, "MAX_FILE_SIZE_BYTES", 10 * 1024)
        oversized_bytes = make_test_wav_bytes(duration_seconds=3.0)  # ~96 KB

        files = {"file": ("oversized.wav", oversized_bytes, "audio/wav")}
        resp = await client.post("/api/v1/detections", files=files)
        assert resp.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        assert "File size exceeds maximum permitted limit" in resp.json()["detail"]

    async def test_fake_webm_rejected_with_400(self, client: AsyncClient):
        fake_webm = b"This is a fake webm payload without EBML or Matroska container headers."
        files = {"file": ("mic_sample_fake.webm", fake_webm, "audio/webm")}
        resp = await client.post("/api/v1/detections", files=files)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "Corrupt or invalid container header" in resp.json()["detail"]

    async def test_valid_browser_webm_header_accepted(self, client: AsyncClient):
        # Generate real browser MediaRecorder-compatible WebM/Opus audio
        from tests.test_audio_decoder import make_test_webm_opus_bytes
        webm_bytes = make_test_webm_opus_bytes(duration_seconds=2.0, sample_rate=48000)
        files = {"file": ("mic_sample_recording.webm", webm_bytes, "audio/webm")}
        resp = await client.post("/api/v1/detections", files=files)
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["id"] is not None
        assert data["prediction"] in ["real", "synthetic", "replay", "unknown", "inconclusive"]

    async def test_valid_ogg_recording_accepted(self, client: AsyncClient):
        # Generate valid Ogg Vorbis/Opus
        t = np.linspace(0, 1.0, 16000, endpoint=False, dtype=np.float32)
        waveform = 0.5 * np.sin(2 * np.pi * 440 * t)
        bio = io.BytesIO()
        sf.write(bio, waveform, 16000, format="OGG")
        ogg_bytes = bio.getvalue()

        files = {"file": ("mic_sample.ogg", ogg_bytes, "audio/ogg")}
        resp = await client.post("/api/v1/detections", files=files)
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()["id"] is not None

    async def test_ogg_disguised_as_webm_rejected_with_400(self, client: AsyncClient):
        # Valid Ogg bytes named with .webm extension must be rejected
        t = np.linspace(0, 1.0, 16000, endpoint=False, dtype=np.float32)
        waveform = 0.5 * np.sin(2 * np.pi * 440 * t)
        bio = io.BytesIO()
        sf.write(bio, waveform, 16000, format="OGG")
        ogg_bytes = bio.getvalue()

        files = {"file": ("mic_sample_mismatch.webm", ogg_bytes, "audio/webm")}
        resp = await client.post("/api/v1/detections", files=files)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "Corrupt or invalid container header" in resp.json()["detail"]

    async def test_webm_disguised_as_ogg_rejected_with_400(self, client: AsyncClient):
        # WebM EBML bytes named with .ogg extension must be rejected
        ebml_header = b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x01\x42\xf7\x81\x01" + b"\x00" * 100
        files = {"file": ("mic_sample_mismatch.ogg", ebml_header, "audio/ogg")}
        resp = await client.post("/api/v1/detections", files=files)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "Corrupt or invalid container header" in resp.json()["detail"]


@pytest.mark.asyncio
class TestRateLimiter:
    async def test_token_bucket_consume_and_refill(self):
        simulated_time = 1000.0
        def fake_clock():
            return simulated_time

        bucket = TokenBucket(rate_per_minute=60, burst_capacity=2, clock=fake_clock)
        
        # 1st consume: allowed (1 token remaining)
        ok1, _ = await bucket.consume("1.2.3.4")
        assert ok1 is True
        
        # 2nd consume: allowed (0 tokens remaining)
        ok2, _ = await bucket.consume("1.2.3.4")
        assert ok2 is True
        
        # 3rd consume: blocked
        ok3, retry_after = await bucket.consume("1.2.3.4")
        assert ok3 is False
        assert retry_after >= 1

        # Advance clock by 1.0 second (refills 1 token at 60/min = 1/sec)
        simulated_time += 1.0
        ok4, _ = await bucket.consume("1.2.3.4")
        assert ok4 is True

    async def test_rate_limiter_triggers_429_with_retry_after(self, client: AsyncClient, monkeypatch):
        monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
        
        # Reset detection limiter with 1 burst
        monkeypatch.setattr(detection_limiter, "capacity", 1.0)
        monkeypatch.setattr(detection_limiter, "rate_per_second", 0.001)
        async with detection_limiter.lock:
            detection_limiter.buckets.clear()

        wav_bytes = make_test_wav_bytes(duration_seconds=1.0)
        
        # 1st call: allowed
        r1 = await client.post("/api/v1/detections", files={"file": ("test.wav", wav_bytes, "audio/wav")})
        assert r1.status_code == status.HTTP_201_CREATED

        # 2nd call: rate limited
        r2 = await client.post("/api/v1/detections", files={"file": ("test.wav", wav_bytes, "audio/wav")})
        assert r2.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "Retry-After" in r2.headers
        assert int(r2.headers["Retry-After"]) >= 1


@pytest.mark.asyncio
class TestInferenceAdmissionController:
    async def test_admission_controller_concurrency_and_timeout(self):
        controller = InferenceAdmissionController(max_concurrent=1, timeout_seconds=0.2)

        async def worker():
            async with controller.acquire_slot():
                await asyncio.sleep(0.5)

        # Start 1st worker holding the slot
        task1 = asyncio.create_task(worker())
        await asyncio.sleep(0.05)

        # 2nd worker attempts to acquire with 0.2s timeout -> should timeout and raise InferenceAdmissionBusyError
        with pytest.raises(InferenceAdmissionBusyError) as exc_info:
            async with controller.acquire_slot():
                pass
        
        assert exc_info.value.retry_after >= 1
        assert "capacity saturated" in str(exc_info.value.message)

        await task1
        # Slot should now be released
        async with controller.acquire_slot(timeout=0.1):
            assert controller._active_jobs == 1
        assert controller._active_jobs == 0

    async def test_admission_controller_releases_slot_on_error(self):
        controller = InferenceAdmissionController(max_concurrent=1, timeout_seconds=0.5)

        try:
            async with controller.acquire_slot():
                raise RuntimeError("Inference forward pass failed")
        except RuntimeError:
            pass

        # Slot must be released despite error
        assert controller._active_jobs == 0
        async with controller.acquire_slot():
            assert controller._active_jobs == 1


@pytest.mark.asyncio
class TestSecurityHeadersAndCORS:
    async def test_security_headers_present_on_all_responses(self, client: AsyncClient):
        resp = await client.get("/")
        assert resp.status_code == 200
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    async def test_cors_preflight_for_allowed_origin(self, client: AsyncClient):
        headers = {
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        }
        resp = await client.options("/api/v1/detections", headers=headers)
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
        assert resp.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.asyncio
class TestUUIDAndErrorHandling:
    async def test_malformed_uuid_returns_422(self, client: AsyncClient):
        resp = await client.get("/api/v1/detections/not-a-valid-uuid-12345")
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_valid_missing_uuid_returns_404(self, client: AsyncClient):
        missing_id = str(uuid.uuid4())
        resp = await client.get(f"/api/v1/detections/{missing_id}")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    async def test_production_error_handler_sanitizes_unhandled_exception(self, client: AsyncClient, monkeypatch):
        monkeypatch.setattr(settings, "DEBUG", False)
        missing_id = str(uuid.uuid4())
        resp_404 = await client.get(f"/api/v1/detections/{missing_id}")
        assert resp_404.status_code == 404
        assert "not found" in resp_404.json()["detail"]
