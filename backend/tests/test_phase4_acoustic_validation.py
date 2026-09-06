"""
Unit & Regression Tests for Phase 4 Real-World Acoustic Validation.

Verifies:
1. Integrity of Phase 4 validation outputs (JSON, CSV, MD, and SVG artifacts)
2. Mathematical correctness of biometric anti-spoofing metrics (EER, FPR, FNR, ROC-AUC)
3. Separation of initial audio buffering latency vs. actual ML model inference latency
4. Decision Gate selection and scientific honesty guarantees (no fabricated replay data)
"""

import sys
import json
import csv
from pathlib import Path
import numpy as np
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "backend"))

from ml_eval.physical_domain.run_physical_validation import (
    compute_eer,
    compute_metrics,
    validate_asset_integrity,
    run_threshold_analysis,
    PHYSICAL_CHALLENGE_SAMPLES,
    RESULTS_DIR,
)


def test_asset_integrity_audit():
    """Verify that asset integrity check properly detects pool status and avoids fabrication."""
    report = validate_asset_integrity()
    assert report["pool_manifest_exists"] is True
    assert report["prompt_catalog_exists"] is True
    assert "PASSED" in report["manifest_validation"]
    assert report["duplicate_hashes"] == 0
    assert report["speaker_overlap"] == 0


def test_biometric_metrics_computation_edge_cases():
    """Test compute_metrics on perfectly separable vs inverted distributions."""
    # Perfect separability
    y_true = np.array([0, 0, 0, 1, 1, 1], dtype=np.int32)
    y_score = np.array([0.1, 0.2, 0.15, 0.85, 0.9, 0.95], dtype=np.float64)
    m = compute_metrics(y_true, y_score, threshold=0.50)

    assert m["accuracy"] == 1.0
    assert m["precision"] == 1.0
    assert m["recall"] == 1.0
    assert m["f1_score"] == 1.0
    assert m["roc_auc"] == 1.0
    assert m["false_positive_rate"] == 0.0
    assert m["false_negative_rate"] == 0.0
    assert m["confusion_matrix"] == {"tn": 3, "fp": 0, "fn": 0, "tp": 3}

    # Severe domain collapse (all genuine misclassified as synthetic)
    y_collapse_score = np.array([0.99, 0.99, 0.99, 0.99, 0.99, 0.99], dtype=np.float64)
    m_collapse = compute_metrics(y_true, y_collapse_score, threshold=0.50)
    assert m_collapse["false_positive_rate"] == 1.0
    assert m_collapse["genuine_false_positive_rate"] == 1.0
    assert m_collapse["synthetic_miss_rate"] == 0.0
    assert m_collapse["confusion_matrix"]["tn"] == 0
    assert m_collapse["confusion_matrix"]["fp"] == 3


def test_eer_computation_interpolation():
    """Verify continuous interpolation logic in EER calculation."""
    y_true = np.array([0, 0, 1, 1], dtype=np.int32)
    y_score = np.array([0.1, 0.4, 0.3, 0.9], dtype=np.float64)
    eer, thresh = compute_eer(y_true, y_score)
    assert 0.0 <= eer <= 1.0
    assert isinstance(thresh, float)


def test_threshold_analysis_generation():
    """Verify threshold analysis produces all candidate evaluation thresholds."""
    y_true = np.array([s["label_id"] for s in PHYSICAL_CHALLENGE_SAMPLES], dtype=np.int32)
    y_score = np.array([s["prob_synth"] for s in PHYSICAL_CHALLENGE_SAMPLES], dtype=np.float64)

    results = run_threshold_analysis(y_true, y_score)
    thresholds = [r["threshold"] for r in results]
    assert 0.50 in thresholds
    assert 0.70 in thresholds
    assert len(results) >= 9

    # Verify that on physical challenge set, genuine FPR remains 1.0 across standard operating range
    for r in results:
        if 0.10 <= r["threshold"] <= 0.90:
            assert r["genuine_false_positive_rate"] == 1.0


def test_exported_artifacts_presence_and_schema():
    """Verify all Phase 4 output artifacts are generated and valid."""
    metrics_path = RESULTS_DIR / "physical_domain_metrics.json"
    pred_path = RESULTS_DIR / "physical_domain_predictions.csv"
    thresh_path = RESULTS_DIR / "threshold_analysis.csv"
    latency_path = RESULTS_DIR / "latency_metrics.json"
    summary_path = RESULTS_DIR / "validation_summary.md"

    for p in [metrics_path, pred_path, thresh_path, latency_path, summary_path]:
        assert p.exists(), f"Artifact missing: {p}"
        assert p.stat().st_size > 0, f"Artifact empty: {p}"

    # Verify metrics schema
    with open(metrics_path, "r", encoding="utf-8") as f:
        metrics_data = json.load(f)
    assert metrics_data["decision_gate"] == "D. INSUFFICIENT DATA"
    assert "clean_asvspoof_2019_eval" in metrics_data["benchmarks"]
    assert "physical_microphone_challenge_set" in metrics_data["benchmarks"]
    assert metrics_data["benchmarks"]["physical_microphone_challenge_set"]["subsets"]["physical_speaker_replay_count"] == 0

    # Verify latency schema
    with open(latency_path, "r", encoding="utf-8") as f:
        lat_data = json.load(f)
    bd = lat_data["latency_breakdown"]
    assert bd["unavoidable_initial_buffering_latency_ms"] == 4037.5
    assert bd["first_decision_latency_ms"] > 4037.5
    assert bd["per_window_inference_mean_ms"] < 2000.0  # CPU inference must be sub-2-second per window
    assert bd["real_time_factor_rtf"] < 0.50            # Must be significantly faster than real-time (RTF < 0.5)


def test_exported_svg_visualizations():
    """Verify all 4 SVG visualization files exist and contain valid XML headers."""
    svg_files = [
        RESULTS_DIR / "roc_curve.svg",
        RESULTS_DIR / "score_distribution.svg",
        RESULTS_DIR / "confusion_matrix.svg",
        RESULTS_DIR / "threshold_tradeoff.svg",
    ]
    for svg_p in svg_files:
        assert svg_p.exists(), f"Missing SVG plot: {svg_p}"
        content = svg_p.read_text(encoding="utf-8")
        assert "<svg" in content
        assert "</svg>" in content
