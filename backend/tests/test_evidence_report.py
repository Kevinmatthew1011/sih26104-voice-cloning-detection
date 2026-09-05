import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.models.detection import DetectionCase, DetectionResult
from app.schemas.detection import PredictionEnum, RiskLevelEnum, ActionEnum
from app.schemas.report import DetectionEvidenceReportResponse
from app.services.report_service import AuditReportBuilder
from app.main import app


def test_aasist_report_projection():
    """Verify AASIST evidence report synthesis from persisted records."""
    case = DetectionCase(
        id="case-aasist-1",
        filename="test_sample.flac",
        file_hash="51d2d9cf0738172f61e2a384ec50a54a55363240f67c971ed55a92435bc1a1c0",
        file_size_bytes=64600 * 2,
        mime_type="audio/flac",
        duration_seconds=4.0375,
        sample_rate=16000,
        channels=1,
        status="COMPLETED",
        created_at=datetime(2026, 8, 27, 12, 0, 0, tzinfo=timezone.utc),
    )
    result = DetectionResult(
        id="res-aasist-1",
        detection_case_id="case-aasist-1",
        engine_type="aasist",
        prediction="synthetic",
        confidence=1.0,
        risk_level="high",
        model_version="aasist-v1",
        processing_time_ms=23,
        attack_type="Neural Voice Conversion",
        explanation="AASIST deep graph attention network classification.",
        created_at=datetime(2026, 8, 27, 12, 0, 1, tzinfo=timezone.utc),
        spectral_artifacts={
            "architecture": "AASIST (SincNet + RawNet2 + H-GAT)",
            "cm_score": -14.3196,
            "device_used": "cuda:0",
        },
        metadata_json={
            "engine_type": "aasist",
            "synthetic_probability": 1.0,
            "real_probability": 0.0,
            "checkpoint_sha256": "51d2d9cf0738172f61e2a384ec50a54a55363240f67c971ed55a92435bc1a1c0",
            "cm_score": -14.3196,
            "analyzed_duration_seconds": 4.0375,
            "device": "cuda:0",
            "decision": {
                "action": "BLOCK",
                "decision_message": "Strong synthetic voice indicators detected. Do not trust voice-only authorization.",
                "synthetic_probability": 1.0,
                "policy_version": "v1.0",
                "decision_source": "policy_v1.0",
                "reason_codes": ["HIGH_CONFIDENCE_SYNTHETIC_DETECTED"],
                "recommended_steps": ["Require out-of-band identity verification."],
            },
        },
    )

    report = AuditReportBuilder.build_report(case, result)
    assert isinstance(report, DetectionEvidenceReportResponse)
    assert report.report_version == "v1.0"
    assert report.case.case_id == "case-aasist-1"
    assert report.case.filename == "test_sample.flac"
    assert report.audio_evidence.file_sha256 == "51d2d9cf0738172f61e2a384ec50a54a55363240f67c971ed55a92435bc1a1c0"
    assert report.model_evidence.engine_type == "aasist"
    assert report.model_evidence.checkpoint_sha256 == "51d2d9cf0738172f61e2a384ec50a54a55363240f67c971ed55a92435bc1a1c0"
    assert report.model_evidence.cm_score == -14.3196
    assert report.model_evidence.synthetic_probability == 1.0
    assert report.security_decision.action == ActionEnum.BLOCK
    assert report.audit.provenance == "policy_evaluated"
    assert report.audit.decision_evaluated is True
    assert report.audit.device_used == "cuda:0"

    # Security check: Ensure no local filesystem paths or database URLs are leaked
    report_json = report.model_dump_json()
    assert "/home/" not in report_json
    assert "postgresql" not in report_json
    assert "password" not in report_json


def test_legacy_report_with_no_decision():
    """Verify legacy historical record without decision metadata returns security_decision=None and legacy_unprocessed."""
    case = DetectionCase(
        id="case-legacy-1",
        filename="legacy_audio.wav",
        file_hash="abc123sha",
        file_size_bytes=32000,
        mime_type="audio/wav",
        duration_seconds=2.0,
        sample_rate=16000,
        channels=1,
        status="COMPLETED",
        created_at=datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc),
    )
    result = DetectionResult(
        id="res-legacy-1",
        detection_case_id="case-legacy-1",
        engine_type="baseline",
        prediction="real",
        confidence=0.88,
        risk_level="low",
        model_version="baseline-v1",
        processing_time_ms=45,
        created_at=datetime(2026, 8, 20, 10, 0, 1, tzinfo=timezone.utc),
        metadata_json={"legacy_field": "no decision here"},
    )

    report = AuditReportBuilder.build_report(case, result)
    assert report.security_decision is None
    assert report.audit.decision_evaluated is False
    assert report.audit.provenance == "legacy_unprocessed"
    assert report.model_evidence.engine_type == "baseline"


def test_missing_optional_telemetry_maps_to_none():
    """Verify missing optional attributes safely map to None without crashing."""
    case = DetectionCase(
        id="case-minimal-1",
        filename="minimal.wav",
        file_hash=None,
        file_size_bytes=100,
        mime_type="audio/wav",
        duration_seconds=None,
        sample_rate=None,
        channels=None,
        status="COMPLETED",
        created_at=datetime.now(timezone.utc),
    )
    result = DetectionResult(
        id="res-minimal-1",
        detection_case_id="case-minimal-1",
        engine_type="mock",
        prediction="real",
        confidence=0.5,
        risk_level="low",
        model_version="mock-v1",
        processing_time_ms=10,
        created_at=datetime.now(timezone.utc),
        metadata_json=None,
        spectral_artifacts=None,
    )

    report = AuditReportBuilder.build_report(case, result)
    assert report.audio_evidence.file_sha256 is None
    assert report.audio_evidence.duration_seconds is None
    assert report.model_evidence.cm_score is None
    assert report.model_evidence.synthetic_probability is None
    assert report.security_decision is None
    assert report.audit.provenance == "legacy_unprocessed"


def test_report_builder_is_deterministic_and_independent_of_runtime():
    """Verify calling build_report twice on same entity produces identical results."""
    case = DetectionCase(
        id="case-det-1",
        filename="det.wav",
        file_hash="hash123",
        file_size_bytes=1000,
        mime_type="audio/wav",
        status="COMPLETED",
        created_at=datetime(2026, 8, 27, 10, 0, 0, tzinfo=timezone.utc),
    )
    result = DetectionResult(
        id="res-det-1",
        detection_case_id="case-det-1",
        engine_type="aasist",
        prediction="real",
        confidence=0.99,
        risk_level="low",
        model_version="aasist-v1",
        processing_time_ms=20,
        created_at=datetime(2026, 8, 27, 10, 0, 1, tzinfo=timezone.utc),
        metadata_json={"synthetic_probability": 0.01},
    )

    rep1 = AuditReportBuilder.build_report(case, result)
    rep2 = AuditReportBuilder.build_report(case, result)

    assert rep1.model_dump() == rep2.model_dump()


@pytest.mark.asyncio
async def test_report_api_404_for_missing_case(client: AsyncClient):
    """Verify GET /api/v1/detections/{id}/report returns 404 for unknown IDs."""
    import uuid
    missing_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/detections/{missing_id}/report")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_report_api_integration_on_created_case(client: AsyncClient):
    """Verify end-to-end report generation for a newly uploaded detection."""
    import io
    # Minimal dummy wav
    sample_rate = 16000
    riff_header = b"RIFF" + (36 + 32000).to_bytes(4, "little") + b"WAVE"
    fmt_header = (
        b"fmt \x10\x00\x00\x00\x01\x00\x01\x00"
        + sample_rate.to_bytes(4, "little")
        + (sample_rate * 2).to_bytes(4, "little")
        + (2).to_bytes(2, "little")
        + (16).to_bytes(2, "little")
    )
    data_header = b"data" + (32000).to_bytes(4, "little") + (b"\x00" * 32000)
    wav_bytes = riff_header + fmt_header + data_header

    files = {"file": ("report_test.wav", io.BytesIO(wav_bytes), "audio/wav")}
    upload_res = await client.post("/api/v1/detections", files=files)
    assert upload_res.status_code == 201
    result_id = upload_res.json()["id"]

    # Fetch report by result_id or case_id
    report_res = await client.get(f"/api/v1/detections/{result_id}/report")
    assert report_res.status_code == 200
    report = report_res.json()

    assert report["report_version"] == "v1.0"
    assert report["report_type"] == "machine_generated_security_analysis"
    assert report["case"]["filename"] == "report_test.wav"
    assert "audio_evidence" in report
    assert "model_evidence" in report
    assert "security_decision" in report
    assert "audit" in report
    assert len(report["limitations"]) > 0


def test_browser_microphone_report_provenance_and_limitations():
    """Verify evidence report reflects unvalidated microphone capture domain and includes domain limitation."""
    case = DetectionCase(
        id="case-mic-1",
        filename="mic_sample_2026-08-28.webm",
        file_hash="mic123sha",
        file_size_bytes=48000,
        mime_type="audio/webm",
        duration_seconds=3.0,
        sample_rate=48000,
        channels=1,
        status="COMPLETED",
        created_at=datetime(2026, 8, 28, 2, 0, 0, tzinfo=timezone.utc),
    )
    result = DetectionResult(
        id="res-mic-1",
        detection_case_id="case-mic-1",
        engine_type="aasist",
        prediction="synthetic",
        confidence=0.99,
        risk_level="high",
        model_version="aasist-v1",
        processing_time_ms=30,
        created_at=datetime(2026, 8, 28, 2, 0, 1, tzinfo=timezone.utc),
        metadata_json={
            "input_source": "browser_microphone",
            "capture_domain": "browser_microphone",
            "capture_domain_reliability": "unvalidated",
            "decision": {
                "action": "VERIFY",
                "decision_message": "Strong synthetic indicators were produced on a browser microphone recording. Physical microphone and device processing characteristics may reduce model-domain reliability.",
                "synthetic_probability": 0.99,
                "raw_ml_action": "BLOCK",
                "final_operational_action": "VERIFY",
                "input_source": "browser_microphone",
                "capture_domain": "browser_microphone",
                "capture_domain_reliability": "unvalidated",
                "policy_version": "v1.0",
                "reason_codes": ["UNVALIDATED_MICROPHONE_DOMAIN", "HIGH_CONFIDENCE_SYNTHETIC_DETECTED"],
                "recommended_steps": ["Require out-of-band secondary identity verification."],
            },
        },
    )

    report = AuditReportBuilder.build_report(case, result)
    assert report.audio_evidence.input_source == "browser_microphone"
    assert report.audio_evidence.capture_domain == "browser_microphone"
    assert report.audio_evidence.capture_domain_reliability == "unvalidated"
    assert report.security_decision.action == ActionEnum.VERIFY
    assert report.security_decision.raw_ml_action == ActionEnum.BLOCK
    assert report.security_decision.final_operational_action == ActionEnum.VERIFY
    assert any("Browser microphone capture is supported" in lim for lim in report.limitations)
