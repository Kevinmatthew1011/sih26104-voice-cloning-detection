"""
Unit and Integration tests for Multimodal Threat Assessment Engine and Real-Time WebSocket.
"""

import json
import numpy as np
import pytest
from httpx import AsyncClient, ASGITransport
from starlette.testclient import TestClient

from app.main import app
from app.services.multimodal_risk_engine import get_multimodal_risk_engine
from app.schemas.multimodal import (
    OverallRiskEnum,
    RecommendedActionEnum,
    AcousticEvidence,
    SemanticEvidence,
    SpeakerEvidence,
)


def test_multimodal_cloned_voice_plus_scam_intent():
    engine = get_multimodal_risk_engine()
    acoustic = AcousticEvidence(status="synthetic_detected", synthetic_probability=0.92, engine="AASIST")
    semantic = SemanticEvidence(risk="high", scam_probability=0.88, reasons=["Caller requests a private code or password."])

    res = engine.evaluate(acoustic=acoustic, semantic=semantic)
    assert res.overall_risk == OverallRiskEnum.HIGH
    assert res.recommended_action == RecommendedActionEnum.BLOCK
    assert "AI-Cloned Impersonation Scam" in res.headline


def test_multimodal_human_voice_plus_scam_intent():
    engine = get_multimodal_risk_engine()
    acoustic = AcousticEvidence(status="likely_genuine", synthetic_probability=0.08, engine="AASIST")
    semantic = SemanticEvidence(risk="high", scam_probability=0.85, reasons=["Caller demands financial transfer."])

    res = engine.evaluate(acoustic=acoustic, semantic=semantic)
    assert res.overall_risk == OverallRiskEnum.HIGH
    assert res.recommended_action == RecommendedActionEnum.ALERT_HUMAN_OPERATOR
    assert "Social Engineering Fraud" in res.headline


def test_multimodal_speaker_impersonation():
    engine = get_multimodal_risk_engine()
    speaker = SpeakerEvidence(
        state="IDENTITY_MISMATCH",
        claimed_speaker_id="SPK_ALICE",
        similarity_score=0.32,
    )

    res = engine.evaluate(speaker=speaker)
    assert res.overall_risk == OverallRiskEnum.HIGH
    assert res.recommended_action == RecommendedActionEnum.BLOCK
    assert "Speaker Impersonation Detected" in res.headline


def test_multimodal_cloned_voice_on_benign_content():
    engine = get_multimodal_risk_engine()
    acoustic = AcousticEvidence(status="synthetic_detected", synthetic_probability=0.89, engine="AASIST")
    semantic = SemanticEvidence(risk="no_indicators", scam_probability=0.05, reasons=[])

    res = engine.evaluate(acoustic=acoustic, semantic=semantic)
    assert res.overall_risk == OverallRiskEnum.VERIFY
    assert res.recommended_action == RecommendedActionEnum.VERIFY
    assert "Neutral Content" in res.headline


def test_multimodal_benign_speech_never_safe():
    engine = get_multimodal_risk_engine()
    acoustic = AcousticEvidence(status="likely_genuine", synthetic_probability=0.04, engine="AASIST")
    semantic = SemanticEvidence(risk="no_indicators", scam_probability=0.02, reasons=[])

    res = engine.evaluate(acoustic=acoustic, semantic=semantic)
    assert res.overall_risk == OverallRiskEnum.LOW
    assert res.overall_risk != "SAFE"  # Platform rule: Never label any call as 'SAFE'
    assert res.recommended_action == RecommendedActionEnum.ALLOW


def test_multimodal_unassessed():
    engine = get_multimodal_risk_engine()
    res = engine.evaluate()
    assert res.overall_risk == OverallRiskEnum.UNASSESSED


@pytest.mark.asyncio
async def test_multimodal_api_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "acoustic": {
                "status": "synthetic_detected",
                "synthetic_probability": 0.85,
                "engine": "AASIST",
            },
            "semantic": {
                "risk": "high",
                "scam_probability": 0.90,
                "reasons": ["Caller requests remote access."],
            },
        }
        res = await client.post("/api/v1/multimodal/evaluate", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["overall_risk"] == "HIGH"
        assert data["recommended_action"] == "block"


def test_websocket_multimodal_streaming():
    client = TestClient(app)
    with client.websocket_connect("/api/v1/detections/ws?engine=mock") as ws:
        # Initial status
        init_msg = ws.receive_json()
        assert init_msg["type"] == "status"
        assert init_msg["state"] == "connected"

        # Send transcript context update
        ws.send_text(
            json.dumps({
                "action": "update_context",
                "transcript": "Please transfer money to this safe account immediately.",
            })
        )

        mm_msg = ws.receive_json()
        assert mm_msg["type"] == "multimodal_update"
        assert mm_msg["overall_risk"] in ("HIGH", "VERIFY")
        assert mm_msg["recommended_action"] in ("alert_human_operator", "block", "verify")

        # Send stop
        ws.send_text(json.dumps({"action": "stop"}))
        summary = ws.receive_json()
        assert summary["type"] == "session_summary"
