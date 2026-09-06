"""
Unit and API tests for Scam Intent Detection Engine.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.scam_intent_service import get_scam_intent_service


def test_scam_intent_credential_theft():
    service = get_scam_intent_service()
    res = service.analyze_text("Please tell me your OTP to verify your bank account.")
    assert res.risk_level == "high"
    assert res.scam_probability >= 0.70
    assert len(res.detected_triggers) >= 1
    assert any("private authentication code" in t or "credential" in t for t in res.detected_triggers)


def test_scam_intent_remote_access():
    service = get_scam_intent_service()
    res = service.analyze_text("Install AnyDesk immediately and give me remote access to fix malware.")
    assert res.risk_level == "high"
    assert res.scam_probability >= 0.70
    assert any("remote access" in t for t in res.detected_triggers)


def test_scam_intent_benign_text():
    service = get_scam_intent_service()
    res = service.analyze_text("Hello, are we still meeting tomorrow for the project review?")
    assert res.risk_level == "no_indicators"
    assert res.scam_probability < 0.40
    assert len(res.detected_triggers) == 0


def test_scam_intent_empty_text():
    service = get_scam_intent_service()
    res = service.analyze_text("")
    assert res.risk_level == "unassessed"
    assert res.scam_probability == 0.0


def test_short_ambiguous_asr_fragment_is_not_high_risk():
    """Weak out-of-domain STT fragments must not become scam evidence by summing classes."""
    service = get_scam_intent_service()
    res = service.analyze_text("WHAT OTHER")
    assert res.risk_level == "unassessed"
    assert res.primary_intent == "unassessed"
    assert res.scam_probability < 0.50
    assert res.detected_triggers == []


@pytest.mark.asyncio
async def test_scam_intent_api_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"text": "Transfer money to this safe account immediately to protect your funds."}
        response = await client.post("/api/v1/semantic/analyze-intent", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["risk_level"] in ("high", "warning")
        assert data["scam_probability"] > 0.50
        assert "detected_triggers" in data
