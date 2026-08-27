import io
import pytest
from pathlib import Path
import numpy as np
import torch
from fastapi import HTTPException

from app.config import settings
from app.schemas.detection import DetectionResultDTO, PredictionEnum, RiskLevelEnum
from app.ml.aasist_model import AASISTModel
from app.ml.aasist_inference import (
    AASISTInferenceEngine,
    DEFAULT_AASIST_WEIGHTS,
    DEFAULT_AASIST_CONFIG,
    OFFICIAL_AASIST_SHA256,
    TARGET_SAMPLE_COUNT,
    pad_waveform,
    compute_file_sha256,
)
from app.services.detection.aasist_service import AASISTDetectionService
from app.services.detection.factory import get_detection_service, reset_detection_service_cache


def create_synthetic_sine_wav_bytes(duration_seconds: float = 1.0, sample_rate: int = 16000) -> bytes:
    """Helper to create dummy 16 kHz WAV bytes for unit tests."""
    import soundfile as sf
    t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds), endpoint=False)
    audio = 0.5 * np.sin(2 * np.pi * 440.0 * t).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, audio, sample_rate, format="WAV")
    return buf.getvalue()


def test_aasist_pad_waveform():
    """Verify official 64,600-sample padding and truncation logic."""
    # Shorter audio (< 64,600) -> repeat tiled to 64,600
    short_audio = np.ones(16000, dtype=np.float32)
    padded = pad_waveform(short_audio, TARGET_SAMPLE_COUNT)
    assert padded.shape == (TARGET_SAMPLE_COUNT,)

    # Longer audio (> 64,600) -> truncated to 64,600
    long_audio = np.ones(80000, dtype=np.float32)
    truncated = pad_waveform(long_audio, TARGET_SAMPLE_COUNT)
    assert truncated.shape == (TARGET_SAMPLE_COUNT,)

    # Exact length
    exact_audio = np.ones(TARGET_SAMPLE_COUNT, dtype=np.float32)
    exact = pad_waveform(exact_audio, TARGET_SAMPLE_COUNT)
    assert exact.shape == (TARGET_SAMPLE_COUNT,)


def test_aasist_checkpoint_sha256_hash():
    """Verify that the official AASIST.pth checkpoint matches the expected SHA-256."""
    if not DEFAULT_AASIST_WEIGHTS.exists():
        pytest.skip(f"AASIST.pth not present at {DEFAULT_AASIST_WEIGHTS}")
    file_hash = compute_file_sha256(DEFAULT_AASIST_WEIGHTS)
    assert file_hash == OFFICIAL_AASIST_SHA256


def test_aasist_inference_engine_singleton_and_cpu_fallback():
    """Verify singleton reuse and CPU forward path."""
    if not DEFAULT_AASIST_WEIGHTS.exists() or not DEFAULT_AASIST_CONFIG.exists():
        pytest.skip("AASIST weights/config not present")

    engine1 = AASISTInferenceEngine()
    engine2 = AASISTInferenceEngine()
    assert engine1 is engine2

    # Test CPU forward pass
    wav_bytes = create_synthetic_sine_wav_bytes(1.0)
    result = engine1.predict_audio(wav_bytes, filename="test_sine.wav")

    assert "prediction" in result
    assert result["prediction"] in ["real", "synthetic"]
    assert 0.0 <= result["confidence"] <= 1.0
    assert result["risk_level"] in ["low", "medium", "high"]
    assert "probabilities" in result
    assert np.isclose(result["probabilities"]["real"] + result["probabilities"]["synthetic"], 1.0, atol=1e-4)
    assert result["metadata_json"]["engine_type"] == "aasist"
    assert result["metadata_json"]["checkpoint_sha256"] == OFFICIAL_AASIST_SHA256


@pytest.mark.asyncio
async def test_aasist_detection_service_detect_dto(tmp_path):
    """Verify AASISTDetectionService produces valid DetectionResultDTO."""
    if not DEFAULT_AASIST_WEIGHTS.exists():
        pytest.skip("AASIST weights not present")

    service = AASISTDetectionService(model_version="aasist-v1")
    info = service.get_model_info()
    assert info["version"] == "aasist-v1"
    assert info["architecture"] == "AASIST (SincNet + RawNet2 + H-GAT)"
    assert info["status"] == "ready"

    # Create temporary WAV file
    test_wav_path = tmp_path / "test_sample.wav"
    test_wav_path.write_bytes(create_synthetic_sine_wav_bytes(1.5))

    dto = await service.detect(
        audio_path=test_wav_path,
        filename="test_sample.wav",
        mime_type="audio/wav",
        file_size_bytes=test_wav_path.stat().st_size,
        duration_seconds=1.5,
    )

    assert isinstance(dto, DetectionResultDTO)
    assert dto.engine_type == "aasist"
    assert dto.prediction in [PredictionEnum.REAL, PredictionEnum.SYNTHETIC]
    assert dto.risk_level in [RiskLevelEnum.LOW, RiskLevelEnum.MEDIUM, RiskLevelEnum.HIGH]
    assert 0.0 <= dto.confidence <= 1.0
    assert dto.model_version == "aasist-v1"
    assert dto.processing_time_ms > 0
    assert dto.spectral_artifacts is not None
    assert "cm_score" in dto.spectral_artifacts


def test_aasist_factory_selection():
    """Verify factory returns AASISTDetectionService when DETECTION_ENGINE=aasist."""
    reset_detection_service_cache()
    orig_engine = settings.DETECTION_ENGINE
    try:
        settings.DETECTION_ENGINE = "aasist"
        service = get_detection_service()
        assert isinstance(service, AASISTDetectionService)
        assert service.model_version == "aasist-v1"
    finally:
        reset_detection_service_cache()
        settings.DETECTION_ENGINE = orig_engine


@pytest.mark.asyncio
async def test_aasist_missing_checkpoint_raises_503(tmp_path, monkeypatch):
    """Verify missing checkpoint raises HTTP 503."""
    dummy_missing_weights = tmp_path / "non_existent_AASIST.pth"
    dummy_missing_config = tmp_path / "non_existent_AASIST.conf"

    # Instantiate separate uninitialized engine instance with bad paths
    class MockEngine:
        def is_model_available(self):
            return False

    service = AASISTDetectionService()
    monkeypatch.setattr(service, "engine", MockEngine())

    test_wav = tmp_path / "audio.wav"
    test_wav.write_bytes(create_synthetic_sine_wav_bytes(1.0))

    with pytest.raises(HTTPException) as exc_info:
        await service.detect(
            audio_path=test_wav,
            filename="audio.wav",
            mime_type="audio/wav",
            file_size_bytes=100,
        )
    assert exc_info.value.status_code == 503
    assert "not available" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_known_bonafide_sample_if_available():
    """Verify inference on known bonafide sample LA_T_1138215.flac (if dataset available)."""
    dataset_root = Path(__file__).resolve().parent.parent.parent / "datasets" / "ASVspoof2019_LA" / "LA"
    bona_path = dataset_root / "ASVspoof2019_LA_train" / "flac" / "LA_T_1138215.flac"
    if not bona_path.exists() or not DEFAULT_AASIST_WEIGHTS.exists():
        pytest.skip("ASVspoof dataset or AASIST weights not present on disk")

    service = AASISTDetectionService()
    dto = await service.detect(
        audio_path=bona_path,
        filename="LA_T_1138215.flac",
        mime_type="audio/flac",
        file_size_bytes=bona_path.stat().st_size,
    )
    assert dto.prediction == PredictionEnum.REAL
    assert dto.risk_level == RiskLevelEnum.LOW
    assert dto.confidence >= 0.90


@pytest.mark.asyncio
async def test_known_spoof_sample_if_available():
    """Verify inference on known spoof sample LA_T_1004644.flac (if dataset available)."""
    dataset_root = Path(__file__).resolve().parent.parent.parent / "datasets" / "ASVspoof2019_LA" / "LA"
    spoof_path = dataset_root / "ASVspoof2019_LA_train" / "flac" / "LA_T_1004644.flac"
    if not spoof_path.exists() or not DEFAULT_AASIST_WEIGHTS.exists():
        pytest.skip("ASVspoof dataset or AASIST weights not present on disk")

    service = AASISTDetectionService()
    dto = await service.detect(
        audio_path=spoof_path,
        filename="LA_T_1004644.flac",
        mime_type="audio/flac",
        file_size_bytes=spoof_path.stat().st_size,
    )
    assert dto.prediction == PredictionEnum.SYNTHETIC
    assert dto.risk_level == RiskLevelEnum.HIGH
    assert dto.confidence >= 0.90
