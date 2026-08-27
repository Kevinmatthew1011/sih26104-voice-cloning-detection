import pytest
from datetime import datetime, timezone
from app.schemas.detection import (
    ActionEnum,
    SecurityDecisionDTO,
    PredictionEnum,
    RiskLevelEnum,
    DetectionResultResponse,
)
from app.services.decision_engine import SecurityDecisionEngine
from app.models.detection import DetectionResult
from app.api.v1.endpoints.detections import build_detection_result_response


def test_decision_engine_threshold_boundaries():
    """Verify exact policy threshold boundaries for ALLOW, VERIFY, and BLOCK."""
    # 1. P_synth = 0.00 -> ALLOW
    dec_00 = SecurityDecisionEngine.evaluate(
        prediction="real",
        synthetic_probability=0.00,
        risk_level="low",
        engine_type="aasist",
    )
    assert dec_00.action == ActionEnum.ALLOW
    assert dec_00.synthetic_probability == 0.00
    assert "No strong synthetic voice indicators" in dec_00.decision_message
    assert dec_00.policy_version == "v1.0"

    # 2. P_synth = 0.49 -> ALLOW
    dec_49 = SecurityDecisionEngine.evaluate(
        prediction="real",
        synthetic_probability=0.49,
        risk_level="low",
        engine_type="aasist",
    )
    assert dec_49.action == ActionEnum.ALLOW
    assert dec_49.synthetic_probability == 0.49
    assert dec_49.action == ActionEnum.ALLOW

    # 3. P_synth = 0.50 -> VERIFY
    dec_50 = SecurityDecisionEngine.evaluate(
        prediction="synthetic",
        synthetic_probability=0.50,
        risk_level="medium",
        engine_type="aasist",
    )
    assert dec_50.action == ActionEnum.VERIFY
    assert dec_50.synthetic_probability == 0.50
    assert "Suspicious voice characteristics detected" in dec_50.decision_message

    # 4. P_synth = 0.69 -> VERIFY
    dec_69 = SecurityDecisionEngine.evaluate(
        prediction="synthetic",
        synthetic_probability=0.69,
        risk_level="medium",
        engine_type="aasist",
    )
    assert dec_69.action == ActionEnum.VERIFY
    assert dec_69.synthetic_probability == 0.69

    # 5. P_synth = 0.70 -> BLOCK
    dec_70 = SecurityDecisionEngine.evaluate(
        prediction="synthetic",
        synthetic_probability=0.70,
        risk_level="high",
        engine_type="aasist",
    )
    assert dec_70.action == ActionEnum.BLOCK
    assert dec_70.synthetic_probability == 0.70
    assert "Strong synthetic voice indicators detected" in dec_70.decision_message
    assert "Do not trust voice-only authorization" in dec_70.decision_message

    # 6. P_synth = 1.00 -> BLOCK
    dec_100 = SecurityDecisionEngine.evaluate(
        prediction="synthetic",
        synthetic_probability=1.00,
        risk_level="high",
        engine_type="aasist",
    )
    assert dec_100.action == ActionEnum.BLOCK
    assert dec_100.synthetic_probability == 1.00


def test_decision_engine_recommended_steps_semantics():
    """Verify operational prevention semantics for BLOCK, VERIFY, and ALLOW."""
    block_dec = SecurityDecisionEngine.evaluate("synthetic", 0.95, "high", "aasist")
    assert any("out-of-band identity verification" in step.lower() for step in block_dec.recommended_steps)
    assert any("not approve sensitive actions" in step.lower() for step in block_dec.recommended_steps)
    assert not any("call terminated" in step.lower() for step in block_dec.recommended_steps)

    verify_dec = SecurityDecisionEngine.evaluate("synthetic", 0.62, "medium", "baseline")
    assert any("step-up authentication" in step.lower() for step in verify_dec.recommended_steps)

    allow_dec = SecurityDecisionEngine.evaluate("real", 0.05, "low", "mock")
    assert any("standard authorization policy" in step.lower() for step in allow_dec.recommended_steps)


def test_build_detection_result_response_with_persisted_decision():
    """Verify deserialization of persisted decision object."""
    fake_result = DetectionResult(
        id="test-res-1",
        detection_case_id="test-case-1",
        engine_type="aasist",
        prediction="synthetic",
        confidence=0.98,
        risk_level="high",
        model_version="aasist-v1",
        processing_time_ms=25,
        created_at=datetime.now(timezone.utc),
        metadata_json={
            "synthetic_probability": 0.98,
            "decision": {
                "action": "BLOCK",
                "decision_message": "Strong synthetic voice indicators detected. Do not trust voice-only authorization.",
                "synthetic_probability": 0.98,
                "policy_version": "v1.0",
                "reason_codes": ["HIGH_CONFIDENCE_SYNTHETIC_DETECTED"],
                "recommended_steps": ["Require out-of-band identity verification."],
            },
        },
    )

    resp = build_detection_result_response(fake_result)
    assert isinstance(resp, DetectionResultResponse)
    assert resp.action == ActionEnum.BLOCK
    assert resp.decision is not None
    assert resp.decision.action == ActionEnum.BLOCK
    assert resp.decision.synthetic_probability == 0.98


def test_build_detection_result_response_legacy_record_remains_null():
    """Verify legacy database records without 'decision' metadata return action=None and decision=None."""
    fake_legacy_result = DetectionResult(
        id="legacy-res-1",
        detection_case_id="legacy-case-1",
        engine_type="baseline",
        prediction="real",
        confidence=0.92,
        risk_level="low",
        model_version="baseline-v1",
        processing_time_ms=50,
        created_at=datetime.now(timezone.utc),
        metadata_json={"legacy_info": "no decision object here"},
    )

    resp = build_detection_result_response(fake_legacy_result)
    assert isinstance(resp, DetectionResultResponse)
    assert resp.action is None
    assert resp.decision_message is None
    assert resp.decision is None
