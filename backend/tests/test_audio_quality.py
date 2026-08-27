import io
import numpy as np
import pytest
import soundfile as sf
from datetime import datetime

from app.schemas.detection import ActionEnum, PredictionEnum, RiskLevelEnum, SecurityDecisionDTO
from app.services.audio_quality import AudioQualityAnalyzer, AudioQualityDTO
from app.services.decision_engine import SecurityDecisionEngine
from app.services.report_service import AuditReportBuilder
from app.models.detection import DetectionCase, DetectionResult


def generate_synthetic_tone(duration_sec: float, sr: int = 16000, freq: float = 440.0, amp: float = 0.5) -> np.ndarray:
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


class TestAudioQualityAnalyzer:
    """Unit tests for the deterministic AudioQualityAnalyzer service."""

    def test_clean_fullband_audio_is_reliable(self):
        wav = generate_synthetic_tone(duration_sec=3.0, sr=16000, amp=0.2)
        res = AudioQualityAnalyzer.analyze_audio(wav, native_sample_rate_hz=16000)

        assert res.native_sample_rate_hz == 16000
        assert res.effective_bandwidth_class == "fullband"
        assert res.analysis_reliability == "reliable"
        assert res.quality_flags == []
        assert res.active_speech_fraction >= 0.90
        assert res.clipped_sample_fraction == 0.0

    def test_narrowband_source_sample_rate_flagged(self):
        wav = generate_synthetic_tone(duration_sec=3.0, sr=16000, amp=0.2)
        res = AudioQualityAnalyzer.analyze_audio(wav, native_sample_rate_hz=8000)

        assert res.native_sample_rate_hz == 8000
        assert res.effective_bandwidth_class == "narrowband"
        assert "SOURCE_SAMPLE_RATE_BELOW_MODEL_TARGET" in res.quality_flags
        assert res.analysis_reliability == "degraded"

    def test_severe_clipping_flagged(self):
        wav = generate_synthetic_tone(duration_sec=3.0, sr=16000, amp=2.0)
        wav_clipped = np.clip(wav, -1.0, 1.0)
        res = AudioQualityAnalyzer.analyze_audio(wav_clipped, native_sample_rate_hz=16000)

        assert res.clipped_sample_fraction >= 0.05
        assert "SEVERE_CLIPPING" in res.quality_flags
        assert res.analysis_reliability == "degraded"

    def test_all_silence_flagged_as_insufficient_speech(self):
        wav = np.zeros(16000 * 4, dtype=np.float32)
        res = AudioQualityAnalyzer.analyze_audio(wav, native_sample_rate_hz=16000)

        assert res.active_speech_fraction == 0.0
        assert "INSUFFICIENT_ACTIVE_SPEECH" in res.quality_flags
        assert res.analysis_reliability == "insufficient_speech"

    def test_sparse_speech_dilution_flagged(self):
        # 1.0s speech + 4.0s silence = 20% active frames
        speech = generate_synthetic_tone(duration_sec=1.0, sr=16000, amp=0.2)
        silence = np.zeros(16000 * 4, dtype=np.float32)
        wav = np.concatenate([silence, speech])
        res = AudioQualityAnalyzer.analyze_audio(wav, native_sample_rate_hz=16000)

        assert 0.05 <= res.active_speech_fraction < 0.45
        assert "SPARSE_SPEECH_DILUTION" in res.quality_flags
        assert res.analysis_reliability == "degraded"


class TestSecurityDecisionEngineQualityPolicy:
    """Tests for the quality-aware operational policy separation."""

    def test_clean_reliable_allow_stays_allow(self):
        dec = SecurityDecisionEngine.evaluate(
            prediction="real",
            synthetic_probability=0.15,
            risk_level="low",
            engine_type="aasist",
            analysis_reliability="reliable",
            quality_flags=[],
        )
        assert dec.raw_ml_action == ActionEnum.ALLOW
        assert dec.final_operational_action == ActionEnum.ALLOW
        assert dec.action == ActionEnum.ALLOW
        assert dec.synthetic_probability == 0.15
        assert "No strong synthetic voice indicators detected" in dec.decision_message

    def test_clean_reliable_block_stays_block(self):
        dec = SecurityDecisionEngine.evaluate(
            prediction="synthetic",
            synthetic_probability=0.88,
            risk_level="high",
            engine_type="aasist",
            analysis_reliability="reliable",
            quality_flags=[],
        )
        assert dec.raw_ml_action == ActionEnum.BLOCK
        assert dec.final_operational_action == ActionEnum.BLOCK
        assert dec.action == ActionEnum.BLOCK
        assert dec.synthetic_probability == 0.88

    def test_degraded_raw_allow_becomes_final_verify(self):
        dec = SecurityDecisionEngine.evaluate(
            prediction="real",
            synthetic_probability=0.15,
            risk_level="low",
            engine_type="aasist",
            analysis_reliability="degraded",
            quality_flags=["SOURCE_SAMPLE_RATE_BELOW_MODEL_TARGET"],
        )
        assert dec.raw_ml_action == ActionEnum.ALLOW
        assert dec.final_operational_action == ActionEnum.VERIFY
        assert dec.action == ActionEnum.VERIFY
        assert dec.synthetic_probability == 0.15
        assert "DEGRADED_CHANNEL_STEP_UP_REQUIRED" in dec.reason_codes

    def test_degraded_raw_verify_stays_final_verify(self):
        dec = SecurityDecisionEngine.evaluate(
            prediction="synthetic",
            synthetic_probability=0.55,
            risk_level="medium",
            engine_type="aasist",
            analysis_reliability="degraded",
            quality_flags=["SPARSE_SPEECH_DILUTION"],
        )
        assert dec.raw_ml_action == ActionEnum.VERIFY
        assert dec.final_operational_action == ActionEnum.VERIFY
        assert dec.action == ActionEnum.VERIFY
        assert dec.synthetic_probability == 0.55

    def test_degraded_raw_block_becomes_final_verify_escalate(self):
        dec = SecurityDecisionEngine.evaluate(
            prediction="synthetic",
            synthetic_probability=0.92,
            risk_level="high",
            engine_type="aasist",
            analysis_reliability="degraded",
            quality_flags=["SOURCE_SAMPLE_RATE_BELOW_MODEL_TARGET", "SEVERE_CLIPPING"],
        )
        # Raw model BLOCK is preserved in telemetry, but final action requires secondary verification/escalation
        assert dec.raw_ml_action == ActionEnum.BLOCK
        assert dec.final_operational_action == ActionEnum.VERIFY
        assert dec.action == ActionEnum.VERIFY
        assert dec.synthetic_probability == 0.92
        assert "DEGRADED_QUALITY_SYNTHETIC_INDICATION" in dec.reason_codes
        assert "Escalate to Fraud/Security Operations" in dec.recommended_steps[0]

    def test_insufficient_speech_not_evaluated_final_verify(self):
        dec = SecurityDecisionEngine.evaluate(
            prediction="unknown",
            synthetic_probability=None,
            risk_level="low",
            engine_type="aasist",
            analysis_reliability="insufficient_speech",
            quality_flags=["INSUFFICIENT_ACTIVE_SPEECH"],
        )
        assert dec.raw_ml_action == ActionEnum.NOT_EVALUATED
        assert dec.final_operational_action == ActionEnum.VERIFY
        assert dec.action == ActionEnum.VERIFY
        assert dec.synthetic_probability is None
        assert "Insufficient analyzable speech" in dec.decision_message


class TestAuditReportQualityProjection:
    """Tests for audit report projection of quality facts and legacy compatibility."""

    def test_modern_detection_report_projects_quality_telemetry(self):
        case = DetectionCase(
            id="case-qual-123",
            filename="narrowband_audio.wav",
            file_size_bytes=32000,
            mime_type="audio/wav",
            duration_seconds=4.0,
            sample_rate=8000,
            channels=1,
            file_hash="sha256-narrowband",
            status="COMPLETED",
            created_at=datetime.utcnow(),
        )
        decision_dto = SecurityDecisionDTO(
            action=ActionEnum.VERIFY,
            raw_ml_action=ActionEnum.BLOCK,
            final_operational_action=ActionEnum.VERIFY,
            analysis_reliability="degraded",
            quality_flags=["SOURCE_SAMPLE_RATE_BELOW_MODEL_TARGET"],
            decision_message="Degraded quality synthetic indication.",
            synthetic_probability=0.95,
            policy_version="v1.0",
            decision_source="policy_v1.0",
            reason_codes=["DEGRADED_QUALITY_SYNTHETIC_INDICATION", "SOURCE_SAMPLE_RATE_BELOW_MODEL_TARGET"],
            recommended_steps=["Escalate to Fraud Operations."],
        )
        result = DetectionResult(
            id="res-qual-123",
            detection_case_id="case-qual-123",
            engine_type="aasist",
            prediction="synthetic",
            confidence=0.95,
            risk_level="high",
            model_version="aasist-v1",
            processing_time_ms=120,
            explanation="AASIST analysis",
            created_at=datetime.utcnow(),
            metadata_json={
                "synthetic_probability": 0.95,
                "real_probability": 0.05,
                "analysis_status": "completed",
                "analysis_reliability": "degraded",
                "quality_flags": ["SOURCE_SAMPLE_RATE_BELOW_MODEL_TARGET"],
                "audio_quality": {
                    "native_sample_rate_hz": 8000,
                    "effective_bandwidth_class": "narrowband",
                    "rms_dbfs": -22.4,
                    "peak_amplitude": 0.6,
                    "clipped_sample_fraction": 0.0,
                    "active_speech_fraction": 0.85,
                    "low_energy_fraction": 0.15,
                    "quality_flags": ["SOURCE_SAMPLE_RATE_BELOW_MODEL_TARGET"],
                    "analysis_reliability": "degraded",
                },
                "decision": decision_dto.model_dump(),
            },
        )

        report = AuditReportBuilder.build_report(case=case, result=result)

        assert report.case.case_id == "case-qual-123"
        assert report.audio_evidence.sample_rate_hz == 8000
        assert report.audio_evidence.analysis_reliability == "degraded"
        assert "SOURCE_SAMPLE_RATE_BELOW_MODEL_TARGET" in report.audio_evidence.quality_flags
        assert report.model_evidence.raw_ml_action == ActionEnum.BLOCK
        assert report.model_evidence.final_operational_action == ActionEnum.VERIFY
        assert report.security_decision.raw_ml_action == ActionEnum.BLOCK
        assert report.security_decision.final_operational_action == ActionEnum.VERIFY
        # Verify dynamic limitation injected
        assert any("narrowband" in lim for lim in report.limitations)

    def test_legacy_detection_report_remains_null_for_quality(self):
        case = DetectionCase(
            id="case-legacy-456",
            filename="legacy_file.wav",
            file_size_bytes=64000,
            mime_type="audio/wav",
            duration_seconds=4.0,
            sample_rate=16000,
            channels=1,
            file_hash="sha256-legacy",
            status="COMPLETED",
            created_at=datetime.utcnow(),
        )
        result = DetectionResult(
            id="res-legacy-456",
            detection_case_id="case-legacy-456",
            engine_type="aasist",
            prediction="synthetic",
            confidence=0.88,
            risk_level="high",
            model_version="aasist-v1",
            processing_time_ms=100,
            created_at=datetime.utcnow(),
            metadata_json={
                "synthetic_probability": 0.88,
            },
        )

        report = AuditReportBuilder.build_report(case=case, result=result)

        assert report.audio_evidence.audio_quality is None
        assert report.audio_evidence.analysis_reliability is None
        assert report.audio_evidence.quality_flags is None
        assert report.security_decision is None
        assert report.audit.provenance == "legacy_unprocessed"
        assert report.audit.decision_evaluated is False


class TestAASISTMultiWindowInferenceQualityIntegration:
    """Tests multi-window AASIST engine handling of silence, clipping, and quality facts."""

    def test_trailing_silence_windows_excluded_from_max_v1(self):
        from app.ml.aasist_inference import AASISTInferenceEngine, TARGET_SAMPLE_RATE

        engine = AASISTInferenceEngine()
        if not engine.is_model_available():
            pytest.skip("AASIST model checkpoint not available in environment.")

        # 4s speech tone + 4s pure digital silence
        speech = generate_synthetic_tone(duration_sec=4.0, sr=TARGET_SAMPLE_RATE, amp=0.2)
        silence = np.zeros(TARGET_SAMPLE_RATE * 4, dtype=np.float32)
        wav = np.concatenate([speech, silence])

        res = engine.predict_audio_multiwindow(wav)

        mw = res["metadata_json"]["multi_window"]
        assert mw["window_count"] > 1
        assert mw["excluded_low_energy_window_count"] >= 1
        assert mw["eligible_window_count"] >= 1

        # Verify excluded windows did not fabricate probabilities
        for w in mw["windows_persisted"]:
            if not w["aggregation_eligible"]:
                assert w["activity_status"] == "low_energy"
                assert w["rms_dbfs"] < -55.0 or w["active_fraction"] < 0.05

    def test_all_silence_returns_inconclusive_and_not_evaluated(self):
        from app.ml.aasist_inference import AASISTInferenceEngine, TARGET_SAMPLE_RATE

        engine = AASISTInferenceEngine()
        if not engine.is_model_available():
            pytest.skip("AASIST model checkpoint not available in environment.")

        # 6s digital silence
        silence = np.zeros(TARGET_SAMPLE_RATE * 6, dtype=np.float32)
        res = engine.predict_audio_multiwindow(silence)

        assert res["analysis_status"] == "inconclusive"
        assert res["prediction"] == "unknown"
        assert res["analysis_reliability"] == "insufficient_speech"
        assert "INSUFFICIENT_ACTIVE_SPEECH" in res["quality_flags"]
        assert res["probabilities"]["synthetic"] is None
        assert res["probabilities"]["real"] is None

        # Pass through Decision Engine
        dec = SecurityDecisionEngine.evaluate(
            prediction=res["prediction"],
            synthetic_probability=res["probabilities"]["synthetic"],
            risk_level=res["risk_level"],
            engine_type="aasist",
            analysis_reliability=res["analysis_reliability"],
            quality_flags=res["quality_flags"],
        )
        assert dec.raw_ml_action == ActionEnum.NOT_EVALUATED
        assert dec.final_operational_action == ActionEnum.VERIFY
        assert dec.action == ActionEnum.VERIFY
        assert "Insufficient analyzable speech" in dec.decision_message

    def test_narrowband_source_generates_degraded_operational_verify(self):
        from app.ml.aasist_inference import AASISTInferenceEngine

        engine = AASISTInferenceEngine()
        if not engine.is_model_available():
            pytest.skip("AASIST model checkpoint not available in environment.")

        # 8 kHz audio
        wav_8k = generate_synthetic_tone(duration_sec=3.0, sr=8000, amp=0.3)
        bio = io.BytesIO()
        sf.write(bio, wav_8k, 8000, format="WAV")
        audio_bytes = bio.getvalue()

        res = engine.predict_audio_multiwindow(audio_bytes)

        assert res["analysis_reliability"] == "degraded"
        assert "SOURCE_SAMPLE_RATE_BELOW_MODEL_TARGET" in res["quality_flags"]

        # Pass through Decision Engine
        dec = SecurityDecisionEngine.evaluate(
            prediction=res["prediction"],
            synthetic_probability=res["metadata_json"]["synthetic_probability"],
            risk_level=res["risk_level"],
            engine_type="aasist",
            analysis_reliability=res["analysis_reliability"],
            quality_flags=res["quality_flags"],
        )
        # Even if model score is high (BLOCK), operational action requires step-up VERIFY
        assert dec.final_operational_action == ActionEnum.VERIFY
        assert dec.action == ActionEnum.VERIFY

