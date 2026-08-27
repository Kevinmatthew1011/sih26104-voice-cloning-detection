import io
import struct
import json
from pathlib import Path
import pytest
import numpy as np

from app.ml.dataset import (
    ASVspoofSample,
    ASVspoofFeatures,
    DatasetValidator,
    DatasetValidationError,
    calculate_file_hash,
    load_asvspoof_protocol,
    extract_asvspoof_features,
    save_asvspoof_feature_cache,
    load_asvspoof_feature_cache,
    load_or_extract_asvspoof_features,
    speaker_independent_split,
    extract_speaker_id_from_path,
)
from app.ml.metrics import (
    compute_eer,
    compute_evaluation_metrics,
    format_evaluation_report,
    CLASS_REAL,
    CLASS_SYNTHETIC,
)


def create_dummy_wav_file(path: Path, duration_sec: float = 0.5, sr: int = 16000, freq: float = 440.0) -> Path:
    """Helper to create minimal valid WAV file strictly for dataset validation testing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    num_samples = int(sr * duration_sec)
    data_size = num_samples * 2
    header = b"RIFF" + struct.pack("<I", 36 + data_size) + b"WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
    header += struct.pack("<I", sr) + struct.pack("<I", sr * 2) + b"\x02\x00\x10\x00data" + struct.pack("<I", data_size)
    t = np.linspace(0, duration_sec, num_samples, endpoint=False)
    samples = (np.sin(2 * np.pi * freq * t) * 16000).astype(np.int16).tobytes()
    path.write_bytes(header + samples)
    return path


# ==========================================================
# 1. Dataset Directory & Class Validation Tests
# ==========================================================

def test_validator_fails_when_root_dir_missing(tmp_path: Path):
    non_existent_dir = tmp_path / "non_existent_dataset"
    validator = DatasetValidator(data_dir=non_existent_dir)
    with pytest.raises(DatasetValidationError, match="does not exist"):
        validator.validate()


def test_validator_fails_when_train_dir_missing(tmp_path: Path):
    data_dir = tmp_path / "data_no_train"
    data_dir.mkdir(parents=True)
    validator = DatasetValidator(data_dir=data_dir)
    with pytest.raises(DatasetValidationError, match="Training split directory.*required"):
        validator.validate()


def test_validator_fails_when_class_dir_missing(tmp_path: Path):
    data_dir = tmp_path / "data_missing_synth"
    train_real = data_dir / "train" / "real"
    create_dummy_wav_file(train_real / "spk01_sample1.wav", freq=300)
    
    validator = DatasetValidator(data_dir=data_dir)
    with pytest.raises(DatasetValidationError, match="Missing required class folder.*synthetic"):
        validator.validate()


def test_validator_fails_when_class_empty(tmp_path: Path):
    data_dir = tmp_path / "data_empty_synth"
    train_real = data_dir / "train" / "real"
    train_synth = data_dir / "train" / "synthetic"
    train_synth.mkdir(parents=True)
    create_dummy_wav_file(train_real / "spk01_sample1.wav", freq=350)
    
    validator = DatasetValidator(data_dir=data_dir)
    with pytest.raises(DatasetValidationError, match="contains 0 audio files"):
        validator.validate()


# ==========================================================
# 2. Audio Format & Corruption Tests
# ==========================================================

def test_validator_detects_unsupported_and_corrupted_files(tmp_path: Path):
    data_dir = tmp_path / "data_corrupt"
    train_real = data_dir / "train" / "real"
    train_synth = data_dir / "train" / "synthetic"
    
    create_dummy_wav_file(train_real / "spk01_sample1.wav", freq=400)
    create_dummy_wav_file(train_synth / "spk02_synth1.wav", freq=500)
    
    # Add an unsupported text file and a 0-byte corrupted file
    (train_real / "notes.txt").write_text("not audio")
    (train_synth / "corrupted.wav").write_bytes(b"")
    
    validator = DatasetValidator(data_dir=data_dir)
    stats = validator.validate_split("train", data_dir / "train")
    
    assert len(stats.unsupported_files) == 1
    assert stats.unsupported_files[0].name == "notes.txt"
    assert len(stats.corrupted_files) == 1
    assert stats.corrupted_files[0].name == "corrupted.wav"
    assert len(stats.real_files) == 1
    assert len(stats.synthetic_files) == 1


# ==========================================================
# 3. Duplicate & Cross-Split Leakage Tests
# ==========================================================

def test_file_hash_calculation(tmp_path: Path):
    file1 = tmp_path / "audio1.wav"
    file2 = tmp_path / "audio2.wav"
    create_dummy_wav_file(file1, freq=440)
    file2.write_bytes(file1.read_bytes())
    
    hash1 = calculate_file_hash(file1)
    hash2 = calculate_file_hash(file2)
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256


def test_validator_fails_on_cross_split_duplicates(tmp_path: Path):
    data_dir = tmp_path / "data_cross_dup"
    train_real = data_dir / "train" / "real"
    train_synth = data_dir / "train" / "synthetic"
    test_real = data_dir / "test" / "real"
    test_synth = data_dir / "test" / "synthetic"
    
    f_real = create_dummy_wav_file(train_real / "spk01_train.wav", freq=440)
    create_dummy_wav_file(train_synth / "spk02_synth.wav", freq=550)
    
    # Put identical file in test/real to simulate data leakage
    test_real.mkdir(parents=True, exist_ok=True)
    test_synth.mkdir(parents=True, exist_ok=True)
    create_dummy_wav_file(test_synth / "spk04_synth_test.wav", freq=660)
    (test_real / "leaked_clip.wav").write_bytes(f_real.read_bytes())
    
    validator = DatasetValidator(data_dir=data_dir)
    with pytest.raises(DatasetValidationError, match="Cross-split data leakage detected"):
        validator.validate()


# ==========================================================
# 4. Speaker Leakage & Speaker-Independent Partition Tests
# ==========================================================

def test_extract_speaker_id():
    assert extract_speaker_id_from_path(Path("spk001_utt01.wav")) == "spk001"
    assert extract_speaker_id_from_path(Path("speakerA-01.wav")) == "speakerA"
    assert extract_speaker_id_from_path(Path("id10001_real.wav")) == "id10001"
    assert extract_speaker_id_from_path(Path("random_recording.wav")) is None


def test_validator_fails_on_speaker_overlap(tmp_path: Path):
    data_dir = tmp_path / "data_speaker_leak"
    train_real = data_dir / "train" / "real"
    train_synth = data_dir / "train" / "synthetic"
    test_real = data_dir / "test" / "real"
    test_synth = data_dir / "test" / "synthetic"
    
    # Speaker 'spk01' placed in both train and test with different audio content (different utterances)
    create_dummy_wav_file(train_real / "spk01_train1.wav", freq=300)
    create_dummy_wav_file(train_synth / "spk02_train2.wav", freq=400)
    create_dummy_wav_file(test_real / "spk01_test1.wav", freq=500)
    create_dummy_wav_file(test_synth / "spk03_test2.wav", freq=600)
    
    validator = DatasetValidator(data_dir=data_dir, strict_speaker_separation=True)
    with pytest.raises(DatasetValidationError, match="Speaker leakage detected.*spk01"):
        validator.validate()


def test_speaker_independent_split_disjointness():
    # 20 samples across 4 distinct speakers
    X = np.random.randn(20, 88)
    y = np.array([0, 0, 1, 1] * 5)
    speaker_ids = ["spkA", "spkA", "spkA", "spkA", "spkA",
                   "spkB", "spkB", "spkB", "spkB", "spkB",
                   "spkC", "spkC", "spkC", "spkC", "spkC",
                   "spkD", "spkD", "spkD", "spkD", "spkD"]
    
    X_train, X_test, y_train, y_test, train_spks, test_spks = speaker_independent_split(
        X, y, speaker_ids=speaker_ids, test_size=0.25, random_state=42
    )
    
    assert len(X_train) + len(X_test) == 20
    assert len(train_spks) > 0
    assert len(test_spks) > 0
    # Crucial: Zero overlap between train and test speakers
    assert set(train_spks).intersection(set(test_spks)) == set()


def test_missing_speaker_metadata_reporting(tmp_path: Path):
    data_dir = tmp_path / "data_no_spk_meta"
    train_real = data_dir / "train" / "real"
    train_synth = data_dir / "train" / "synthetic"
    
    create_dummy_wav_file(train_real / "sample_real.wav", freq=350)
    create_dummy_wav_file(train_synth / "sample_synth.wav", freq=450)
    
    validator = DatasetValidator(data_dir=data_dir)
    summary = validator.validate()
    
    assert not summary.speaker_metadata_available
    report = summary.format_report()
    assert "Speaker identity metadata is unavailable" in report
    assert "Speaker-independent evaluation cannot be guaranteed" in report


# ==========================================================
# 5. Evaluation Metrics & EER Tests
# ==========================================================

def test_metrics_computation_accuracy_precision_recall_f1():
    # Ground truth: 5 real (0), 5 synthetic (1)
    y_true = np.array([0, 0, 0, 0, 0, 1, 1, 1, 1, 1])
    # Predictions: 1 false positive, 1 false negative
    y_pred = np.array([0, 0, 0, 0, 1, 0, 1, 1, 1, 1])
    
    metrics = compute_evaluation_metrics(y_true, y_pred)
    
    assert metrics["accuracy"] == 0.8
    assert metrics["precision"] == 0.8
    assert metrics["recall"] == 0.8
    assert metrics["f1_score"] == 0.8
    assert metrics["confusion_matrix"]["tn"] == 4
    assert metrics["confusion_matrix"]["fp"] == 1
    assert metrics["confusion_matrix"]["fn"] == 1
    assert metrics["confusion_matrix"]["tp"] == 4


def test_roc_auc_and_eer_perfect_separation():
    y_true = np.array([0, 0, 0, 0, 0, 1, 1, 1, 1, 1])
    # Perfectly separated probabilities
    y_prob = np.array([0.05, 0.10, 0.15, 0.20, 0.25, 0.75, 0.80, 0.85, 0.90, 0.95])
    y_pred = (y_prob >= 0.5).astype(int)
    
    metrics = compute_evaluation_metrics(y_true, y_pred, y_prob=y_prob)
    
    assert metrics["roc_auc"] == 1.0
    assert metrics["eer"] == 0.0


def test_compute_eer_known_operating_point():
    # Symmetric crossover around 0.5 threshold
    y_true = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    y_scores = np.array([0.1, 0.3, 0.6, 0.4, 0.4, 0.6, 0.7, 0.9])
    
    eer, thresh = compute_eer(y_true, y_scores)
    assert 0.0 <= eer <= 0.5
    assert 0.0 <= thresh <= 1.0


def test_metrics_report_formatting():
    y_true = np.array([0, 0, 1, 1])
    y_pred = np.array([0, 0, 1, 1])
    y_prob = np.array([0.1, 0.2, 0.8, 0.9])
    
    metrics = compute_evaluation_metrics(y_true, y_pred, y_prob=y_prob)
    report = format_evaluation_report(metrics, metadata={"model_version": "baseline-v1"})
    
    assert "MODEL EVALUATION METRICS SUMMARY" in report
    assert "Accuracy:            1.0000 (100.00%)" in report
    assert "ROC-AUC:             1.0000" in report
    assert "Equal Error Rate:    0.0000" in report


def test_reproducible_split_with_seed():
    X = np.random.randn(20, 88)
    y = np.array([0] * 10 + [1] * 10)
    spks = [f"spk_{i % 5}" for i in range(20)]
    
    # Run twice with same seed
    res1 = speaker_independent_split(X, y, spks, test_size=0.2, random_state=42)
    res2 = speaker_independent_split(X, y, spks, test_size=0.2, random_state=42)
    
    np.testing.assert_array_equal(res1[0], res2[0])
    np.testing.assert_array_equal(res1[1], res2[1])
    assert res1[4] == res2[4]  # train_spks
    assert res1[5] == res2[5]  # test_spks


# ==========================================================
# 6. ASVspoof 2019 Protocol Loader Tests
# ==========================================================

def test_asvspoof_protocol_bonafide_mapping(tmp_path: Path):
    audio_dir = tmp_path / "flac"
    audio_dir.mkdir()
    (audio_dir / "LA_T_1138215.flac").write_bytes(b"dummy_flac_content")

    protocol_file = tmp_path / "protocol.txt"
    protocol_file.write_text("LA_0079 LA_T_1138215 - - bonafide\n", encoding="utf-8")

    samples = load_asvspoof_protocol(protocol_file, audio_dir)

    assert len(samples) == 1
    sample = samples[0]
    assert isinstance(sample, ASVspoofSample)
    assert sample.speaker_id == "LA_0079"
    assert sample.audio_id == "LA_T_1138215"
    assert sample.attack_id == "-"
    assert sample.original_label == "bonafide"
    assert sample.label == "real"
    assert sample.class_id == 0
    assert sample.audio_path == audio_dir / "LA_T_1138215.flac"


def test_asvspoof_protocol_spoof_mapping(tmp_path: Path):
    audio_dir = tmp_path / "flac"
    audio_dir.mkdir()
    (audio_dir / "LA_T_1004644.flac").write_bytes(b"dummy_flac_content")

    protocol_file = tmp_path / "protocol.txt"
    protocol_file.write_text("LA_0079 LA_T_1004644 - A01 spoof\n", encoding="utf-8")

    samples = load_asvspoof_protocol(protocol_file, audio_dir)

    assert len(samples) == 1
    sample = samples[0]
    assert isinstance(sample, ASVspoofSample)
    assert sample.speaker_id == "LA_0079"
    assert sample.audio_id == "LA_T_1004644"
    assert sample.attack_id == "A01"
    assert sample.original_label == "spoof"
    assert sample.label == "synthetic"
    assert sample.class_id == 1
    assert sample.audio_path == audio_dir / "LA_T_1004644.flac"


def test_asvspoof_protocol_malformed_row(tmp_path: Path):
    audio_dir = tmp_path / "flac"
    audio_dir.mkdir()
    (audio_dir / "LA_T_1138215.flac").write_bytes(b"dummy_flac_content")

    # Only 4 columns instead of 5
    protocol_file = tmp_path / "protocol_malformed.txt"
    protocol_file.write_text("LA_0079 LA_T_1138215 - bonafide\n", encoding="utf-8")

    with pytest.raises(DatasetValidationError, match="Malformed protocol row.*expected exactly 5 columns"):
        load_asvspoof_protocol(protocol_file, audio_dir)


def test_asvspoof_protocol_unknown_label(tmp_path: Path):
    audio_dir = tmp_path / "flac"
    audio_dir.mkdir()
    (audio_dir / "LA_T_1138215.flac").write_bytes(b"dummy_flac_content")

    # Invalid label 'fake' instead of 'bonafide' or 'spoof'
    protocol_file = tmp_path / "protocol_unknown_label.txt"
    protocol_file.write_text("LA_0079 LA_T_1138215 - - fake\n", encoding="utf-8")

    with pytest.raises(DatasetValidationError, match="Unknown label 'fake'"):
        load_asvspoof_protocol(protocol_file, audio_dir)


def test_asvspoof_protocol_missing_audio_file(tmp_path: Path):
    audio_dir = tmp_path / "flac"
    audio_dir.mkdir()
    # Notice: we do NOT create LA_T_1138215.flac in audio_dir

    protocol_file = tmp_path / "protocol_missing_flac.txt"
    protocol_file.write_text("LA_0079 LA_T_1138215 - - bonafide\n", encoding="utf-8")

    with pytest.raises(DatasetValidationError, match="Referenced audio file does not exist"):
        load_asvspoof_protocol(protocol_file, audio_dir)


def test_asvspoof_protocol_missing_files_and_directories(tmp_path: Path):
    audio_dir = tmp_path / "flac"
    protocol_file = tmp_path / "non_existent_protocol.txt"

    with pytest.raises(DatasetValidationError, match="ASVspoof protocol file does not exist"):
        load_asvspoof_protocol(protocol_file, audio_dir)

    protocol_file.write_text("LA_0079 LA_T_1138215 - - bonafide\n", encoding="utf-8")
    with pytest.raises(DatasetValidationError, match="ASVspoof audio directory does not exist"):
        load_asvspoof_protocol(protocol_file, audio_dir)


# ==========================================================
# 7. ASVspoof Feature Extraction & Caching Tests
# ==========================================================

def test_extract_asvspoof_features(tmp_path: Path):
    audio_dir = tmp_path / "flac"
    audio_dir.mkdir()
    f1 = create_dummy_wav_file(audio_dir / "LA_T_001.flac", freq=300)
    f2 = create_dummy_wav_file(audio_dir / "LA_T_002.flac", freq=500)

    samples = [
        ASVspoofSample(
            speaker_id="LA_0001",
            audio_id="LA_T_001",
            attack_id="-",
            original_label="bonafide",
            label="real",
            class_id=0,
            audio_path=f1,
        ),
        ASVspoofSample(
            speaker_id="LA_0002",
            audio_id="LA_T_002",
            attack_id="A01",
            original_label="spoof",
            label="synthetic",
            class_id=1,
            audio_path=f2,
        ),
    ]

    features = extract_asvspoof_features(samples)

    assert isinstance(features, ASVspoofFeatures)
    assert features.X.shape == (2, 88)
    assert features.y.shape == (2,)
    assert features.X.dtype == np.float32
    assert features.y.dtype == np.int32
    np.testing.assert_array_equal(features.y, np.array([0, 1]))
    assert np.isfinite(features.X).all()
    assert features.speaker_ids == ["LA_0001", "LA_0002"]
    assert features.audio_ids == ["LA_T_001", "LA_T_002"]
    assert features.attack_ids == ["-", "A01"]
    assert len(features) == 2
    assert features.num_samples == 2


def test_asvspoof_features_empty_samples():
    features = extract_asvspoof_features([])
    assert features.X.shape == (0, 88)
    assert features.y.shape == (0,)
    assert len(features) == 0
    assert features.speaker_ids == []
    assert features.audio_ids == []
    assert features.attack_ids == []


def test_asvspoof_feature_caching_save_and_load(tmp_path: Path):
    X = np.random.randn(5, 88).astype(np.float32)
    y = np.array([0, 0, 1, 1, 0], dtype=np.int32)
    spks = [f"LA_000{i}" for i in range(5)]
    audios = [f"LA_T_00{i}" for i in range(5)]
    attacks = ["-", "-", "A01", "A02", "-"]

    feat = ASVspoofFeatures(
        X=X,
        y=y,
        speaker_ids=spks,
        audio_ids=audios,
        attack_ids=attacks,
    )

    cache_file = tmp_path / "subdir" / "test_features.npz"
    feat.save_cache(cache_file)
    assert cache_file.exists()

    loaded = ASVspoofFeatures.load_cache(cache_file)
    np.testing.assert_array_almost_equal(loaded.X, X, decimal=5)
    np.testing.assert_array_equal(loaded.y, y)
    assert loaded.speaker_ids == spks
    assert loaded.audio_ids == audios
    assert loaded.attack_ids == attacks


def test_load_or_extract_asvspoof_features_uses_cache(tmp_path: Path):
    audio_dir = tmp_path / "flac"
    audio_dir.mkdir()
    f1 = create_dummy_wav_file(audio_dir / "LA_T_001.flac", freq=300)

    samples = [
        ASVspoofSample(
            speaker_id="LA_0001",
            audio_id="LA_T_001",
            attack_id="-",
            original_label="bonafide",
            label="real",
            class_id=0,
            audio_path=f1,
        )
    ]

    cache_file = tmp_path / "cached_feat.npz"
    
    # 1. First run: extracts and writes cache
    res1 = load_or_extract_asvspoof_features(samples, cache_path=cache_file)
    assert cache_file.exists()
    assert res1.X.shape == (1, 88)

    # 2. Delete audio file to prove second run loads from cache without touching audio
    f1.unlink()
    assert not f1.exists()

    res2 = load_or_extract_asvspoof_features(samples, cache_path=cache_file)
    np.testing.assert_array_almost_equal(res1.X, res2.X)
    np.testing.assert_array_equal(res1.y, res2.y)

    # 3. Force recompute should fail now because audio file was deleted
    with pytest.raises(ValueError, match="Audio file not found"):
        load_or_extract_asvspoof_features(samples, cache_path=cache_file, force_recompute=True)


def test_asvspoof_features_validation_errors(tmp_path: Path):
    # Wrong feature dimension (50 != 88)
    with pytest.raises(DatasetValidationError, match="Feature matrix X must have shape \\(N, 88\\)"):
        ASVspoofFeatures(
            X=np.random.randn(2, 50).astype(np.float32),
            y=np.array([0, 1], dtype=np.int32),
            speaker_ids=["s1", "s2"],
            audio_ids=["a1", "a2"],
            attack_ids=["-", "A01"],
        )

    # Length mismatch between X and y
    with pytest.raises(DatasetValidationError, match="Label vector y length .* must match X sample count"):
        ASVspoofFeatures(
            X=np.random.randn(3, 88).astype(np.float32),
            y=np.array([0, 1], dtype=np.int32),
            speaker_ids=["s1", "s2"],
            audio_ids=["a1", "a2"],
            attack_ids=["-", "A01"],
        )

    # Non-finite values
    bad_X = np.random.randn(2, 88).astype(np.float32)
    bad_X[0, 5] = np.nan
    with pytest.raises(DatasetValidationError, match="contains non-finite values"):
        ASVspoofFeatures(
            X=bad_X,
            y=np.array([0, 1], dtype=np.int32),
            speaker_ids=["s1", "s2"],
            audio_ids=["a1", "a2"],
            attack_ids=["-", "A01"],
        )

    # Invalid class ID (e.g. 2)
    with pytest.raises(DatasetValidationError, match="Label vector y must only contain class IDs 0"):
        ASVspoofFeatures(
            X=np.random.randn(2, 88).astype(np.float32),
            y=np.array([0, 2], dtype=np.int32),
            speaker_ids=["s1", "s2"],
            audio_ids=["a1", "a2"],
            attack_ids=["-", "A01"],
        )

    # Missing cache file
    with pytest.raises(FileNotFoundError, match="Feature cache file not found"):
        load_asvspoof_feature_cache(tmp_path / "non_existent.npz")

    # Corrupted cache (missing keys)
    corrupted_file = tmp_path / "corrupted.npz"
    np.savez(corrupted_file, X=np.zeros((2, 88), dtype=np.float32), y=np.array([0, 1]))
    with pytest.raises(DatasetValidationError, match="Corrupted cache file.*missing keys"):
        load_asvspoof_feature_cache(corrupted_file)


