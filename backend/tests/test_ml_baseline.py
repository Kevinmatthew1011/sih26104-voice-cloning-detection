import io
import struct
from pathlib import Path
import pytest
import numpy as np
from fastapi import HTTPException

from app.config import settings
from app.ml.preprocessing import AudioPreprocessor
from app.ml.features import AudioFeatureExtractor
from app.ml.classifier import BaselineClassifier
from app.ml.inference import BaselineInferenceEngine
from app.services.detection.base import BaseDetectionService
from app.services.detection.mock_service import MockDetectionService
from app.services.detection.baseline_service import BaselineMLDetectionService
from app.services.detection.factory import get_detection_service, reset_detection_service_cache


def generate_test_tone_waveform(duration_sec: float = 1.0, sr: int = 16000, freq: float = 440.0) -> np.ndarray:
    """Generate in-memory test sinusoidal waveform strictly for technical interface testing."""
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    return (np.sin(2 * np.pi * freq * t) * 0.7).astype(np.float32)


def generate_test_wav_bytes(duration_sec: float = 1.0, sr: int = 16000, channels: int = 1) -> bytes:
    """Generate in-memory WAV byte stream for I/O testing."""
    num_samples = int(sr * duration_sec)
    data_size = num_samples * channels * 2
    header = b"RIFF" + struct.pack("<I", 36 + data_size) + b"WAVEfmt \x10\x00\x00\x00\x01\x00"
    header += struct.pack("<H", channels)
    header += struct.pack("<I", sr) + struct.pack("<I", sr * channels * 2)
    header += struct.pack("<H", channels * 2) + struct.pack("<H", 16) + b"data" + struct.pack("<I", data_size)
    
    # Interleave channel samples if multi-channel
    sample_data = (np.sin(np.linspace(0, 10, num_samples)) * 16000).astype(np.int16)
    if channels == 2:
        stereo_data = np.empty((num_samples, 2), dtype=np.int16)
        stereo_data[:, 0] = sample_data
        stereo_data[:, 1] = sample_data // 2
        samples_bytes = stereo_data.tobytes()
    else:
        samples_bytes = sample_data.tobytes()
        
    return header + samples_bytes


# ==========================================================
# 1. Preprocessing Pipeline Tests
# ==========================================================

def test_audio_preprocessor_output_shape_and_type():
    preprocessor = AudioPreprocessor(target_sr=16000, max_duration_seconds=2.0)
    waveform = generate_test_tone_waveform(duration_sec=1.5, sr=16000)
    
    processed = preprocessor.process(waveform)
    
    assert isinstance(processed, np.ndarray)
    assert processed.ndim == 1
    assert len(processed) == 32000  # 16000 * 2.0s
    assert processed.dtype == np.float32
    assert not np.isnan(processed).any()
    assert not np.isinf(processed).any()


def test_audio_preprocessor_resampling():
    preprocessor = AudioPreprocessor(target_sr=16000, max_duration_seconds=1.0)
    # Input at 44.1 kHz
    waveform_44k = generate_test_tone_waveform(duration_sec=1.0, sr=44100)
    
    processed = preprocessor.process(waveform_44k, source_sr=44100)
    assert len(processed) == 16000


def test_audio_preprocessor_zero_padding():
    preprocessor = AudioPreprocessor(target_sr=16000, max_duration_seconds=3.0)
    # Input is only 0.5 seconds
    short_waveform = generate_test_tone_waveform(duration_sec=0.5, sr=16000)
    
    processed = preprocessor.process(short_waveform)
    assert len(processed) == 48000
    # Last part should be zero-padded
    assert np.all(processed[8000:] == 0.0)


def test_audio_preprocessor_truncation_to_3_seconds():
    preprocessor = AudioPreprocessor(target_sr=16000, max_duration_seconds=3.0)
    # Input is 6.0 seconds (long audio)
    long_waveform = generate_test_tone_waveform(duration_sec=6.0, sr=16000)
    
    processed = preprocessor.process(long_waveform)
    assert len(processed) == 48000  # Exactly 3.0 seconds @ 16 kHz
    # Verify it kept the first 3 seconds
    np.testing.assert_allclose(processed, long_waveform[:48000] / np.max(np.abs(long_waveform[:48000])), atol=1e-4)


def test_audio_preprocessor_multichannel_numpy_conversion():
    preprocessor = AudioPreprocessor(target_sr=16000, max_duration_seconds=1.0, mono=True)
    
    # 1. Test shape (samples, channels) - 2 channels
    num_samples = 16000
    ch1 = np.ones(num_samples, dtype=np.float32) * 0.8
    ch2 = np.ones(num_samples, dtype=np.float32) * 0.4
    stereo_samples_first = np.column_stack([ch1, ch2])  # (16000, 2)
    
    processed_1 = preprocessor.process(stereo_samples_first)
    assert processed_1.ndim == 1
    assert len(processed_1) == 16000
    # Average of 0.8 and 0.4 is 0.6; after peak normalization (0.6 / 0.6) = 1.0
    np.testing.assert_allclose(processed_1, 1.0, atol=1e-4)

    # 2. Test shape (channels, samples) - 2 channels
    stereo_channels_first = np.vstack([ch1, ch2])  # (2, 16000)
    processed_2 = preprocessor.process(stereo_channels_first)
    assert processed_2.ndim == 1
    assert len(processed_2) == 16000
    np.testing.assert_allclose(processed_2, 1.0, atol=1e-4)


def test_audio_preprocessor_multichannel_wav_bytes():
    preprocessor = AudioPreprocessor(target_sr=16000, max_duration_seconds=1.0, mono=True)
    stereo_wav_bytes = generate_test_wav_bytes(duration_sec=1.0, sr=16000, channels=2)
    
    processed = preprocessor.process(stereo_wav_bytes)
    assert processed.ndim == 1
    assert len(processed) == 16000
    assert not np.isnan(processed).any()


def test_audio_preprocessor_empty_input_raises_error():
    preprocessor = AudioPreprocessor()
    with pytest.raises(ValueError, match="empty|no samples"):
        preprocessor.process(b"")


# ==========================================================
# 2. Feature Extraction Tests
# ==========================================================

def test_feature_extractor_dimensions_and_validity():
    extractor = AudioFeatureExtractor(n_mfcc=13, target_sr=16000)
    waveform = generate_test_tone_waveform(duration_sec=2.0, sr=16000)
    
    feats = extractor.extract_features(waveform, sr=16000)
    
    assert isinstance(feats, np.ndarray)
    assert feats.shape == (88,)  # 26 (MFCC) + 26 (Delta) + 26 (Delta2) + 10 (Spectral)
    assert extractor.feature_dim == 88
    assert len(extractor.feature_names) == 88
    assert not np.isnan(feats).any()
    assert not np.isinf(feats).any()


def test_feature_extractor_from_bytes():
    extractor = AudioFeatureExtractor(target_sr=16000)
    wav_bytes = generate_test_wav_bytes(duration_sec=1.0, sr=16000)
    
    feats = extractor.extract_from_file(wav_bytes)
    assert feats.shape == (88,)


# ==========================================================
# 3. Classifier Pipeline Tests
# ==========================================================

def test_classifier_fit_predict_and_persistence(tmp_path: Path):
    # Minimal synthetic feature matrix for testing scikit-learn pipeline mechanics
    np.random.seed(42)
    X = np.random.randn(20, 88).astype(np.float32)
    y = np.array([0] * 10 + [1] * 10, dtype=np.int32)
    
    clf = BaselineClassifier(C=1.0, max_iter=100)
    clf.fit(X, y)
    
    preds = clf.predict(X)
    assert preds.shape == (20,)
    assert set(preds).issubset({0, 1})
    
    probs = clf.predict_proba(X)
    assert probs.shape == (20, 2)
    # Check probability sum == 1.0
    np.testing.assert_allclose(np.sum(probs, axis=1), 1.0, atol=1e-5)
    
    # Save & Load roundtrip
    model_file = tmp_path / "model.joblib"
    clf.save(model_file)
    assert model_file.exists()
    
    loaded_clf = BaselineClassifier.load(model_file)
    loaded_preds = loaded_clf.predict(X)
    np.testing.assert_array_equal(preds, loaded_preds)


# ==========================================================
# 4. Inference Engine & Missing Model Handling Tests
# ==========================================================

def test_inference_engine_raises_clear_error_when_model_missing(tmp_path: Path):
    non_existent_model = tmp_path / "non_existent_model.joblib"
    engine = BaselineInferenceEngine(model_path=non_existent_model)
    
    assert not engine.is_model_available()
    with pytest.raises(FileNotFoundError, match="Baseline ML model artifact not found"):
        engine.load_model()


def test_baseline_service_inherits_interface():
    service = BaselineMLDetectionService()
    assert isinstance(service, BaseDetectionService)


@pytest.mark.asyncio
async def test_baseline_service_raises_503_when_uninitialized(tmp_path: Path):
    service = BaselineMLDetectionService()
    # Point to a missing path to test missing model handling
    service.engine.model_path = tmp_path / "missing_model.joblib"
    
    dummy_wav = tmp_path / "test.wav"
    dummy_wav.write_bytes(generate_test_wav_bytes(1.0))
    
    with pytest.raises(HTTPException) as exc_info:
        await service.detect(
            audio_path=dummy_wav,
            filename="test.wav",
            mime_type="audio/wav",
            file_size_bytes=len(dummy_wav.read_bytes()),
            duration_seconds=1.0,
        )
    assert exc_info.value.status_code == 503
    assert "not trained" in exc_info.value.detail.lower()


# ==========================================================
# 5. Detection Engine Factory Tests
# ==========================================================

def test_factory_returns_mock_service(monkeypatch):
    monkeypatch.setattr(settings, "DETECTION_ENGINE", "mock")
    reset_detection_service_cache()
    
    service = get_detection_service()
    assert isinstance(service, MockDetectionService)
    assert service.get_model_info()["type"] == "heuristic_spectral_mock"


def test_factory_returns_baseline_service(monkeypatch):
    monkeypatch.setattr(settings, "DETECTION_ENGINE", "baseline")
    reset_detection_service_cache()
    
    service = get_detection_service()
    assert isinstance(service, BaselineMLDetectionService)
    assert service.get_model_info()["version"] == "baseline-v1"


def test_factory_rejects_invalid_engine(monkeypatch):
    monkeypatch.setattr(settings, "DETECTION_ENGINE", "unknown_engine_xyz")
    reset_detection_service_cache()
    
    with pytest.raises(ValueError, match="Unsupported DETECTION_ENGINE"):
        get_detection_service()
    
    # Restore default
    reset_detection_service_cache()
