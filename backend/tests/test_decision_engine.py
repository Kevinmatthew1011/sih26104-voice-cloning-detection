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
    assert resp.input_source == "uploaded_file"
    assert resp.capture_domain == "file_audio"
    assert resp.capture_domain_reliability == "validated"


def test_uploaded_file_domain_policy():
    """Verify standard uploaded audio with validated capture domain retains nominal ALLOW/BLOCK policy."""
    # 1. Uploaded reliable + raw ALLOW -> final ALLOW
    allow_dec = SecurityDecisionEngine.evaluate(
        prediction="real",
        synthetic_probability=0.05,
        risk_level="low",
        engine_type="aasist",
        analysis_reliability="reliable",
        input_source="uploaded_file",
    )
    assert allow_dec.raw_ml_action == ActionEnum.ALLOW
    assert allow_dec.final_operational_action == ActionEnum.ALLOW
    assert allow_dec.action == ActionEnum.ALLOW
    assert allow_dec.input_source == "uploaded_file"
    assert allow_dec.capture_domain == "file_audio"
    assert allow_dec.capture_domain_reliability == "validated"

    # 2. Uploaded reliable + raw BLOCK -> final BLOCK
    block_dec = SecurityDecisionEngine.evaluate(
        prediction="synthetic",
        synthetic_probability=0.98,
        risk_level="high",
        engine_type="aasist",
        analysis_reliability="reliable",
        input_source="uploaded_file",
    )
    assert block_dec.raw_ml_action == ActionEnum.BLOCK
    assert block_dec.final_operational_action == ActionEnum.BLOCK
    assert block_dec.action == ActionEnum.BLOCK
    assert block_dec.input_source == "uploaded_file"
    assert block_dec.capture_domain == "file_audio"
    assert block_dec.capture_domain_reliability == "validated"


def test_browser_microphone_domain_shift_policy():
    """Verify real-world microphone domain-shift hardening: raw ML evidence is preserved, but final action is VERIFY."""
    # 1. browser_microphone + raw BLOCK -> raw_ml_action=BLOCK, final=VERIFY, P_synth=1.00 untouched
    mic_block = SecurityDecisionEngine.evaluate(
        prediction="synthetic",
        synthetic_probability=1.00,
        risk_level="high",
        engine_type="aasist",
        analysis_reliability="reliable",
        input_source="browser_microphone",
    )
    assert mic_block.synthetic_probability == 1.00
    assert mic_block.raw_ml_action == ActionEnum.BLOCK
    assert mic_block.final_operational_action == ActionEnum.VERIFY
    assert mic_block.action == ActionEnum.VERIFY
    assert mic_block.input_source == "browser_microphone"
    assert mic_block.capture_domain == "browser_microphone"
    assert mic_block.capture_domain_reliability == "unvalidated"
    assert "UNVALIDATED_MICROPHONE_DOMAIN" in mic_block.reason_codes
    assert "HIGH_CONFIDENCE_SYNTHETIC_DETECTED" in mic_block.reason_codes
    assert "Strong synthetic indicators were produced on a browser microphone recording" in mic_block.decision_message

    # 2. browser_microphone + raw VERIFY -> raw_ml_action=VERIFY, final=VERIFY
    mic_verify = SecurityDecisionEngine.evaluate(
        prediction="synthetic",
        synthetic_probability=0.60,
        risk_level="medium",
        engine_type="aasist",
        analysis_reliability="reliable",
        input_source="browser_microphone",
    )
    assert mic_verify.synthetic_probability == 0.60
    assert mic_verify.raw_ml_action == ActionEnum.VERIFY
    assert mic_verify.final_operational_action == ActionEnum.VERIFY
    assert mic_verify.action == ActionEnum.VERIFY
    assert mic_verify.input_source == "browser_microphone"
    assert mic_verify.capture_domain == "browser_microphone"
    assert mic_verify.capture_domain_reliability == "unvalidated"

    # 3. browser_microphone + raw ALLOW -> raw_ml_action=ALLOW, final=VERIFY
    mic_allow = SecurityDecisionEngine.evaluate(
        prediction="real",
        synthetic_probability=0.10,
        risk_level="low",
        engine_type="aasist",
        analysis_reliability="reliable",
        input_source="browser_microphone",
    )
    assert mic_allow.synthetic_probability == 0.10
    assert mic_allow.raw_ml_action == ActionEnum.ALLOW
    assert mic_allow.final_operational_action == ActionEnum.VERIFY
    assert mic_allow.action == ActionEnum.VERIFY
    assert mic_allow.input_source == "browser_microphone"
    assert mic_allow.capture_domain == "browser_microphone"
    assert mic_allow.capture_domain_reliability == "unvalidated"


def test_browser_microphone_insufficient_speech():
    """Verify insufficient speech under microphone capture results in VERIFY with NOT_EVALUATED raw ML action."""
    mic_insufficient = SecurityDecisionEngine.evaluate(
        prediction="unknown",
        synthetic_probability=None,
        risk_level="low",
        engine_type="aasist",
        analysis_reliability="insufficient_speech",
        quality_flags=["INSUFFICIENT_ACTIVE_SPEECH"],
        input_source="browser_microphone",
    )
    assert mic_insufficient.synthetic_probability is None
    assert mic_insufficient.raw_ml_action == ActionEnum.NOT_EVALUATED
    assert mic_insufficient.final_operational_action == ActionEnum.VERIFY
    assert mic_insufficient.action == ActionEnum.VERIFY
    assert "INSUFFICIENT_ACTIVE_SPEECH" in mic_insufficient.reason_codes
