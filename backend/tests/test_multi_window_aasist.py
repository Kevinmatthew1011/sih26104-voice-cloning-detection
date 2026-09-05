import pytest
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.ml.aasist_inference import (
    segment_audio_windows,
    aggregate_max_v1,
    aggregate_top_k_mean,
    aggregate_mean_v1,
    aggregate_majority_vote_v1,
    extract_suspicious_segments,
    get_bounded_persisted_windows,
    AASISTInferenceEngine,
    TARGET_SAMPLE_COUNT,
    TARGET_HOP_COUNT,
)
from app.models.detection import DetectionCase, DetectionResult
from app.services.report_service import AuditReportBuilder
from app.schemas.report import DetectionEvidenceReportResponse


def test_segment_audio_windows_boundary_lengths():
    """
    Verify exact segmentation boundary coverage:
    - L - 1 (64,599) -> 1 window
    - L (64,600) -> 1 window
    - L + 1 (64,601) -> 2 windows (with tail)
    - L + H (96,900) -> 2 windows (exact hop, no duplicate tail)
    - L + H + 1 (96,901) -> 3 windows (with tail)
    """
    L = TARGET_SAMPLE_COUNT  # 64600
    H = TARGET_HOP_COUNT     # 32300
    sr = 16000

    # 1. L - 1 (64,599 samples)
    wav_lm1 = np.ones(L - 1, dtype=np.float32)
    win_lm1 = segment_audio_windows(wav_lm1, window_length=L, hop_length=H, sample_rate=sr)
    assert len(win_lm1) == 1
    assert len(win_lm1[0].waveform) == L
    assert win_lm1[0].start_seconds == 0.0
    assert abs(win_lm1[0].end_seconds - (L - 1) / sr) < 1e-4

    # 2. L (64,600 samples)
    wav_l = np.ones(L, dtype=np.float32)
    win_l = segment_audio_windows(wav_l, window_length=L, hop_length=H, sample_rate=sr)
    assert len(win_l) == 1
    assert len(win_l[0].waveform) == L
    assert win_l[0].start_seconds == 0.0
    assert abs(win_l[0].end_seconds - L / sr) < 1e-4

    # 3. L + 1 (64,601 samples)
    wav_lp1 = np.arange(L + 1, dtype=np.float32)
    win_lp1 = segment_audio_windows(wav_lp1, window_length=L, hop_length=H, sample_rate=sr)
    assert len(win_lp1) == 2
    assert win_lp1[0].start_seconds == 0.0
    assert win_lp1[0].end_seconds == round(L / sr, 4)
    # Tail window must end at exact EOF
    assert win_lp1[1].is_tail is True
    assert win_lp1[1].end_seconds == round((L + 1) / sr, 4)
    assert win_lp1[1].start_seconds == round(1 / sr, 4)
    assert win_lp1[1].waveform[-1] == L  # Matches last sample

    # 4. L + H (96,900 samples) -> Exact hop landing, no duplicate tail
    wav_lph = np.ones(L + H, dtype=np.float32)
    win_lph = segment_audio_windows(wav_lph, window_length=L, hop_length=H, sample_rate=sr)
    assert len(win_lph) == 2
    assert win_lph[0].start_seconds == 0.0
    assert win_lph[1].start_seconds == round(H / sr, 4)
    assert win_lph[1].end_seconds == round((L + H) / sr, 4)
    assert win_lph[1].is_tail is False

    # 5. L + H + 1 (96,901 samples) -> 2 regular + 1 tail window
    wav_lphp1 = np.ones(L + H + 1, dtype=np.float32)
    win_lphp1 = segment_audio_windows(wav_lphp1, window_length=L, hop_length=H, sample_rate=sr)
    assert len(win_lphp1) == 3
    assert win_lphp1[0].start_seconds == 0.0
    assert win_lphp1[1].start_seconds == round(H / sr, 4)
    assert win_lphp1[2].is_tail is True
    assert win_lphp1[2].end_seconds == round((L + H + 1) / sr, 4)


def test_candidate_aggregation_functions():
    """Verify isolated candidate aggregation pure functions."""
    probs = [0.10, 0.95, 0.85, 0.20]
    cms = [8.5, -12.4, -9.1, 7.2]

    # 1. Max v1
    synth_max, real_max, cm_max = aggregate_max_v1(probs, cms)
    assert synth_max == 0.95
    assert real_max == 0.05
    assert cm_max == -12.4

    # 2. Top-2 mean
    synth_top2, real_top2, cm_top2 = aggregate_top_k_mean(probs, cms, k=2)
    assert synth_top2 == (0.95 + 0.85) / 2
    assert cm_top2 == (-12.4 + -9.1) / 2

    # 3. Simple mean
    synth_mean, real_mean, cm_mean = aggregate_mean_v1(probs, cms)
    assert synth_mean == (0.10 + 0.95 + 0.85 + 0.20) / 4

    # 4. Majority vote
    synth_vote, real_vote, cm_vote = aggregate_majority_vote_v1(probs, cms)
    assert synth_vote == 2 / 4  # 2 windows >= 0.50


def test_suspicious_segment_merger():
    """Verify merging of contiguous and disjoint suspicious windows."""
    windows = [
        {"window_index": 0, "start_seconds": 0.0, "end_seconds": 4.04, "synthetic_probability": 0.05, "cm_score": 10.0},
        {"window_index": 1, "start_seconds": 2.02, "end_seconds": 6.06, "synthetic_probability": 0.12, "cm_score": 8.0},
        # Suspicious cluster 1: Windows 2 & 3
        {"window_index": 2, "start_seconds": 4.04, "end_seconds": 8.08, "synthetic_probability": 0.88, "cm_score": -10.0},
        {"window_index": 3, "start_seconds": 6.06, "end_seconds": 10.10, "synthetic_probability": 0.94, "cm_score": -13.5},
        # Normal windows 4 & 5
        {"window_index": 4, "start_seconds": 8.08, "end_seconds": 12.12, "synthetic_probability": 0.15, "cm_score": 6.0},
        {"window_index": 5, "start_seconds": 10.10, "end_seconds": 14.14, "synthetic_probability": 0.20, "cm_score": 5.5},
        # Suspicious cluster 2: Window 6
        {"window_index": 6, "start_seconds": 12.12, "end_seconds": 16.16, "synthetic_probability": 0.72, "cm_score": -6.0},
    ]

    segments = extract_suspicious_segments(windows, threshold=0.50)
    assert len(segments) == 2

    # Segment 0: Merged Windows 2 & 3
    assert segments[0]["segment_index"] == 0
    assert segments[0]["start_seconds"] == 4.04
    assert segments[0]["end_seconds"] == 10.10
    assert segments[0]["peak_synthetic_probability"] == 0.94
    assert segments[0]["minimum_cm_score"] == -13.5
    assert segments[0]["contributing_window_indices"] == [2, 3]

    # Segment 1: Isolated Window 6
    assert segments[1]["segment_index"] == 1
    assert segments[1]["start_seconds"] == 12.12
    assert segments[1]["end_seconds"] == 16.16
    assert segments[1]["peak_synthetic_probability"] == 0.72
    assert segments[1]["minimum_cm_score"] == -6.0
    assert segments[1]["contributing_window_indices"] == [6]


def test_bounded_persisted_windows():
    """Verify bounded window metadata storage policy."""
    # Under 60 windows: persist all
    small_list = [{"window_index": i, "synthetic_probability": 0.1} for i in range(20)]
    bounded_small = get_bounded_persisted_windows(small_list, max_full_persist=60)
    assert len(bounded_small) == 20

    # Over 60 windows (e.g. 100 windows): persist suspicious + top 10
    large_list = [{"window_index": i, "synthetic_probability": 0.05} for i in range(100)]
    # Mark 3 suspicious windows
    large_list[15]["synthetic_probability"] = 0.85
    large_list[40]["synthetic_probability"] = 0.92
    large_list[80]["synthetic_probability"] = 0.65
    # Mark a few moderately elevated
    large_list[2]["synthetic_probability"] = 0.40
    large_list[3]["synthetic_probability"] = 0.35

    bounded_large = get_bounded_persisted_windows(large_list, max_full_persist=60, top_k_fallback=5)
    # Must include all 3 suspicious windows
    indices = [w["window_index"] for w in bounded_large]
    assert 15 in indices
    assert 40 in indices
    assert 80 in indices
    # Must bounded to <= 10 items
    assert len(bounded_large) <= 10


def test_evidence_report_with_multiwindow_metadata():
    """Verify AuditReportBuilder projects multi-window metadata into ReportModelEvidence."""
    case = DetectionCase(
        id="case-mw-1",
        filename="long_recording.flac",
        file_hash="sha256hash",
        file_size_bytes=160000,
        mime_type="audio/flac",
        duration_seconds=10.0,
        sample_rate=16000,
        channels=1,
        status="COMPLETED",
        created_at=datetime(2026, 8, 27, 13, 0, 0, tzinfo=timezone.utc),
    )
    result = DetectionResult(
        id="res-mw-1",
        detection_case_id="case-mw-1",
        engine_type="aasist",
        prediction="synthetic",
        confidence=0.95,
        risk_level="high",
        model_version="aasist-v1",
        processing_time_ms=45,
        created_at=datetime(2026, 8, 27, 13, 0, 1, tzinfo=timezone.utc),
        metadata_json={
            "synthetic_probability": 0.95,
            "real_probability": 0.05,
            "checkpoint_sha256": "51d2d9cf0738172f61e2a384ec50a54a55363240f67c971ed55a92435bc1a1c0",
            "cm_score": -12.4,
            "decision": {
                "action": "BLOCK",
                "decision_message": "Strong synthetic voice indicators detected. Do not trust voice-only authorization.",
                "synthetic_probability": 0.95,
                "policy_version": "v1.0",
                "decision_source": "policy_v1.0",
                "reason_codes": ["HIGH_CONFIDENCE_SYNTHETIC_DETECTED"],
                "recommended_steps": ["Require out-of-band identity verification."],
            },
            "multi_window": {
                "analysis_mode": "multi_window",
                "window_count": 4,
                "window_length_seconds": 4.0375,
                "hop_seconds": 2.01875,
                "overlap_fraction": 0.50,
                "aggregation_method": "max_v1",
                "aggregation_version": "v1.0",
                "file_level_synthetic_probability": 0.95,
                "file_level_real_probability": 0.05,
                "file_level_cm_score": -12.4,
                "suspicious_segments": [
                    {
                        "segment_index": 0,
                        "start_seconds": 4.04,
                        "end_seconds": 8.08,
                        "peak_synthetic_probability": 0.95,
                        "minimum_cm_score": -12.4,
                        "contributing_window_indices": [2],
                    }
                ],
            },
        },
    )

    report = AuditReportBuilder.build_report(case, result)
    assert isinstance(report, DetectionEvidenceReportResponse)
    assert report.model_evidence.analysis_mode == "multi_window"
    assert report.model_evidence.window_count == 4
    assert report.model_evidence.aggregation_method == "max_v1"
    assert report.model_evidence.suspicious_segments is not None
    assert len(report.model_evidence.suspicious_segments) == 1
    assert report.model_evidence.suspicious_segments[0].start_seconds == 4.04


def test_300s_maximum_audio_duration_and_window_limit_safety():
    """
    Verify that:
    1. 300.0s audio segments into exactly 295 windows at 75% overlap (Hop=16150)
       and is within the safety limit (MAX_MULTIWINDOW_WINDOWS=350).
    2. Audio over 300.0s raises a clear validation error without silent truncation.
    """
    sr = 16000
    H_75 = 16150
    L = 64600

    # 1. Exact 300.0s segmentation
    wav_300s = np.zeros(300 * sr, dtype=np.float32)
    slices_300s = segment_audio_windows(wav_300s, window_length=L, hop_length=H_75, sample_rate=sr)
    assert len(slices_300s) == 295
    assert slices_300s[0].start_seconds == 0.0
    assert slices_300s[-1].end_seconds == 300.0
    assert slices_300s[-1].is_tail is True

    # 2. Rejection of audio > 300s
    engine = AASISTInferenceEngine()
    engine.is_loaded = True
    engine.model = MagicMock()
    wav_301s = np.zeros(301 * sr, dtype=np.float32)
    with pytest.raises(ValueError, match="exceeds maximum allowed limit"):
        engine.predict_audio_multiwindow(wav_301s, hop_length=H_75)
