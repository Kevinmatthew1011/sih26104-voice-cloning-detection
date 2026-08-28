import io
import pytest
from httpx import AsyncClient
from app.services.audio_metadata import AudioMetadataService, AudioMetadata


def create_dummy_wav_bytes(duration_seconds: int = 1) -> bytes:
    """Create minimal valid RIFF WAVE PCM 16-bit mono 16000Hz header with dummy silence bytes."""
    sample_rate = 16000
    num_samples = sample_rate * duration_seconds
    bytes_per_sample = 2
    data_size = num_samples * bytes_per_sample
    riff_header = b"RIFF" + (36 + data_size).to_bytes(4, "little") + b"WAVE"
    fmt_header = (
        b"fmt \x10\x00\x00\x00"  # Subchunk1Size = 16
        + (1).to_bytes(2, "little")  # AudioFormat = 1 (PCM)
        + (1).to_bytes(2, "little")  # NumChannels = 1
        + sample_rate.to_bytes(4, "little")  # SampleRate
        + (sample_rate * bytes_per_sample).to_bytes(4, "little")  # ByteRate
        + bytes_per_sample.to_bytes(2, "little")  # BlockAlign
        + (16).to_bytes(2, "little")  # BitsPerSample
    )
    data_header = b"data" + data_size.to_bytes(4, "little") + (b"\x00" * data_size)
    return riff_header + fmt_header + data_header


def test_audio_metadata_service_extraction():
    wav_bytes = create_dummy_wav_bytes(2)
    meta = AudioMetadataService.extract_metadata(wav_bytes)
    assert isinstance(meta, AudioMetadata)
    assert len(meta.file_hash) == 64
    assert meta.sample_rate == 16000
    assert meta.channels == 1
    assert meta.duration == 2.0



@pytest.mark.asyncio
async def test_upload_and_detect_synthetic_voice(client: AsyncClient):
    wav_content = create_dummy_wav_bytes(1)
    files = {"file": ("synthetic_voice_sample.wav", io.BytesIO(wav_content), "audio/wav")}
    
    response = await client.post("/api/v1/detections", files=files)
    assert response.status_code == 201
    
    data = response.json()
    assert "id" in data
    assert data["engine_type"] == "mock"
    assert data["prediction"] == "synthetic"
    assert data["risk_level"] == "high"
    assert data["confidence"] >= 0.9
    assert data["model_version"] == "mock-v1"
    assert data["processing_time_ms"] > 0
    assert "created_at" in data


@pytest.mark.asyncio
async def test_upload_and_detect_real_voice(client: AsyncClient):
    wav_content = create_dummy_wav_bytes(1)
    files = {"file": ("genuine_human_sample.wav", io.BytesIO(wav_content), "audio/wav")}
    
    response = await client.post("/api/v1/detections", files=files)
    assert response.status_code == 201
    
    data = response.json()
    assert data["engine_type"] == "mock"
    assert data["prediction"] == "real"
    assert data["risk_level"] == "low"
    assert data["confidence"] >= 0.85


@pytest.mark.asyncio
async def test_upload_invalid_extension_rejected(client: AsyncClient):
    files = {"file": ("malicious_script.exe", io.BytesIO(b"binary_payload"), "application/x-msdownload")}
    response = await client.post("/api/v1/detections", files=files)
    assert response.status_code == 400
    assert "Unsupported audio extension" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_empty_file_rejected(client: AsyncClient):
    files = {"file": ("empty.wav", io.BytesIO(b""), "audio/wav")}
    response = await client.post("/api/v1/detections", files=files)
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_audio_exceeding_duration_limit_rejected_with_400(client: AsyncClient):
    # 301 seconds exceeds MAX_AUDIO_DURATION_SECONDS (300s)
    wav_content = create_dummy_wav_bytes(301)
    files = {"file": ("long_audio.wav", io.BytesIO(wav_content), "audio/wav")}
    response = await client.post("/api/v1/detections", files=files)
    assert response.status_code == 400
    assert "exceeds maximum allowed limit" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_detections_history_and_detail(client: AsyncClient):
    # 1. Create a detection
    wav_content = create_dummy_wav_bytes(1)
    files = {"file": ("test_recording_01.wav", io.BytesIO(wav_content), "audio/wav")}
    create_res = await client.post("/api/v1/detections", files=files)
    assert create_res.status_code == 201
    created_result = create_res.json()

    # 2. List detections
    list_res = await client.get("/api/v1/detections")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1
    assert len(list_data["items"]) >= 1

    case_item = list_data["items"][0]
    case_id = case_item["id"]
    assert case_item["filename"] == "test_recording_01.wav"
    assert case_item["status"] == "COMPLETED"
    assert case_item["sample_rate"] == 16000
    assert case_item["channels"] == 1
    assert case_item["result"] is not None
    assert case_item["result"]["engine_type"] == "mock"

    # 3. Get detail by case_id
    detail_res = await client.get(f"/api/v1/detections/{case_id}")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["id"] == case_id
    assert detail_data["filename"] == "test_recording_01.wav"
    assert detail_data["file_hash"] is not None
    assert len(detail_data["file_hash"]) == 64  # SHA-256 hex string
    assert detail_data["sample_rate"] == 16000
    assert detail_data["channels"] == 1
    assert "audio_url" in detail_data
    assert detail_data["result"]["id"] == created_result["id"]
    assert detail_data["result"]["engine_type"] == "mock"

    # 4. Stream audio
    audio_res = await client.get(f"/api/v1/detections/{case_id}/audio")
    assert audio_res.status_code == 200
    assert len(audio_res.content) == len(wav_content)


@pytest.mark.asyncio
async def test_upload_with_browser_microphone_input_source(client: AsyncClient):
    """Verify endpoint correctly binds and persists input_source='browser_microphone'."""
    wav_content = create_dummy_wav_bytes(1)
    files = {"file": ("mic_recording.wav", io.BytesIO(wav_content), "audio/wav")}
    data = {"input_source": "browser_microphone"}

    response = await client.post("/api/v1/detections", files=files, data=data)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["input_source"] == "browser_microphone"
    assert res_data["capture_domain"] == "browser_microphone"
    assert res_data["capture_domain_reliability"] == "unvalidated"
    assert res_data["action"] == "VERIFY"
    assert res_data["decision"]["input_source"] == "browser_microphone"
    assert res_data["decision"]["capture_domain_reliability"] == "unvalidated"


@pytest.mark.asyncio
async def test_upload_with_uploaded_file_input_source(client: AsyncClient):
    """Verify endpoint correctly binds and persists input_source='uploaded_file'."""
    wav_content = create_dummy_wav_bytes(1)
    files = {"file": ("clean_upload.wav", io.BytesIO(wav_content), "audio/wav")}
    data = {"input_source": "uploaded_file"}

    response = await client.post("/api/v1/detections", files=files, data=data)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["input_source"] == "uploaded_file"
    assert res_data["capture_domain"] == "file_audio"
    assert res_data["capture_domain_reliability"] == "validated"
