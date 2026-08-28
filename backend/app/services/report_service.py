"""
Audit Evidence & Detection Report Builder.

Pure, stateless projection service that synthesizes immutable persisted
DetectionCase and DetectionResult records into a structured audit report.

Design Constraints:
- Zero ML / PyTorch / audio framework imports.
- Zero disk file reads or runtime model invocations.
- Zero current-time request timestamp injection (deterministic report output).
- Zero runtime state contamination (only persisted DB attributes are used).
- Sensitive path and token sanitization.
"""

from typing import Optional, Dict, Any
from app.models.detection import DetectionCase, DetectionResult
from app.schemas.detection import PredictionEnum, SecurityDecisionDTO
from app.schemas.report import (
    DetectionEvidenceReportResponse,
    ReportCaseMetadata,
    ReportAudioEvidence,
    ReportModelEvidence,
    ReportAuditProvenance,
)


class AuditReportBuilder:
    """Pure, deterministic evidence projection builder."""

    @classmethod
    def build_report(
        cls,
        case: DetectionCase,
        result: Optional[DetectionResult] = None,
    ) -> DetectionEvidenceReportResponse:
        """
        Synthesize a deterministic audit evidence report from persisted database entities.
        """
        # If result is not explicitly passed, use the relationship if loaded
        res = result or getattr(case, "result", None)

        # 1. Case Identification Metadata
        case_meta = ReportCaseMetadata(
            case_id=case.id,
            result_id=res.id if res else None,
            filename=case.filename,
            status=case.status,
            created_at=case.created_at,
        )

        # 2. Model Evidence & Security Decision (if result exists)
        model_evidence: Optional[ReportModelEvidence] = None
        security_decision: Optional[SecurityDecisionDTO] = None
        audit_provenance: ReportAuditProvenance
        audio_quality: Optional[Dict[str, Any]] = None
        analysis_rel: Optional[str] = None
        q_flags: Optional[list[str]] = None

        if res:
            meta = res.metadata_json or {}
            spectral = res.spectral_artifacts or {}

            # Extract persisted probabilities
            synth_prob = meta.get("synthetic_probability")
            real_prob = meta.get("real_probability")

            # Extract persisted checkpoint hash & architecture
            checkpoint_sha = meta.get("checkpoint_sha256")
            architecture = spectral.get("architecture") or meta.get("classifier")

            # Extract CM score & analyzed window
            cm_score = meta.get("cm_score") or spectral.get("cm_score")
            analyzed_duration = meta.get("analyzed_duration_seconds")

            # Extract device used during the original inference
            device_used = meta.get("device") or spectral.get("device_used")

            # Extract quality and activity telemetry
            audio_quality = meta.get("audio_quality")
            analysis_rel = meta.get("analysis_reliability")
            q_flags = meta.get("quality_flags")
            analysis_status = meta.get("analysis_status")

            # Extract multi-window telemetry if persisted
            multi_window = meta.get("multi_window")
            analysis_mode = None
            window_count = None
            eligible_window_count = None
            excluded_window_count = None
            window_len = None
            hop_len = None
            agg_method = None
            suspicious_segs = None

            if multi_window and isinstance(multi_window, dict):
                analysis_mode = multi_window.get("analysis_mode")
                window_count = multi_window.get("window_count")
                eligible_window_count = multi_window.get("eligible_window_count")
                excluded_window_count = multi_window.get("excluded_low_energy_window_count")
                window_len = multi_window.get("window_length_seconds")
                hop_len = multi_window.get("hop_seconds")
                agg_method = multi_window.get("aggregation_method")
                if not audio_quality and "audio_quality" in multi_window:
                    audio_quality = multi_window.get("audio_quality")
                if not analysis_rel and "analysis_reliability" in multi_window:
                    analysis_rel = multi_window.get("analysis_reliability")
                if not q_flags and "quality_flags" in multi_window:
                    q_flags = multi_window.get("quality_flags")
                if not analysis_status and "analysis_status" in multi_window:
                    analysis_status = multi_window.get("analysis_status")

                raw_segs = multi_window.get("suspicious_segments")
                if raw_segs and isinstance(raw_segs, list):
                    suspicious_segs = []
                    for seg in raw_segs:
                        try:
                            from app.schemas.detection import SuspiciousSegmentDTO
                            suspicious_segs.append(SuspiciousSegmentDTO(**seg))
                        except Exception:
                            pass

            raw_ml_action = None
            final_op_action = None

            # Deserialization of persisted decision object (strict provenance)
            decision_data = meta.get("decision")
            if decision_data and isinstance(decision_data, dict):
                try:
                    security_decision = SecurityDecisionDTO(**decision_data)
                    raw_ml_action = security_decision.raw_ml_action
                    final_op_action = security_decision.final_operational_action or security_decision.action
                    if not analysis_rel and security_decision.analysis_reliability:
                        analysis_rel = security_decision.analysis_reliability
                    if not q_flags and security_decision.quality_flags:
                        q_flags = security_decision.quality_flags
                    audit_provenance = ReportAuditProvenance(
                        provenance="policy_evaluated",
                        decision_evaluated=True,
                        device_used=device_used,
                    )
                except Exception:
                    security_decision = None
                    audit_provenance = ReportAuditProvenance(
                        provenance="legacy_unprocessed",
                        decision_evaluated=False,
                        device_used=device_used,
                    )
            else:
                # Historical legacy record without persisted decision metadata
                security_decision = None
                audit_provenance = ReportAuditProvenance(
                    provenance="legacy_unprocessed",
                    decision_evaluated=False,
                    device_used=device_used,
                )

            model_evidence = ReportModelEvidence(
                engine_type=res.engine_type,
                model_version=res.model_version,
                architecture=architecture,
                checkpoint_sha256=checkpoint_sha,
                prediction=PredictionEnum(res.prediction),
                confidence=res.confidence,
                synthetic_probability=synth_prob,
                real_probability=real_prob,
                cm_score=cm_score,
                analyzed_duration_seconds=analyzed_duration,
                processing_latency_ms=res.processing_time_ms,
                attack_type=res.attack_type,
                explanation=res.explanation,
                scoring_note=meta.get("uncalibrated_softmax_note") or "Probability estimates represent uncalibrated model score transformations.",
                analysis_mode=analysis_mode,
                analysis_status=analysis_status,
                window_count=window_count,
                eligible_window_count=eligible_window_count,
                excluded_low_energy_window_count=excluded_window_count,
                window_length_seconds=window_len,
                hop_seconds=hop_len,
                aggregation_method=agg_method,
                raw_ml_action=raw_ml_action,
                final_operational_action=final_op_action,
                suspicious_segments=suspicious_segs,
            )
        else:
            # Case pending/failed without detection result
            audit_provenance = ReportAuditProvenance(
                provenance="unprocessed",
                decision_evaluated=False,
                device_used=None,
            )

        # 3. Audio Forensics Evidence
        input_source = None
        capture_domain = None
        capture_domain_rel = None
        if res:
            meta = res.metadata_json or {}
            input_source = meta.get("input_source")
            capture_domain = meta.get("capture_domain")
            capture_domain_rel = meta.get("capture_domain_reliability")
            if security_decision:
                if not input_source and security_decision.input_source:
                    input_source = security_decision.input_source
                if not capture_domain and security_decision.capture_domain:
                    capture_domain = security_decision.capture_domain
                if not capture_domain_rel and security_decision.capture_domain_reliability:
                    capture_domain_rel = security_decision.capture_domain_reliability

        audio_evidence = ReportAudioEvidence(
            file_size_bytes=case.file_size_bytes,
            mime_type=case.mime_type,
            duration_seconds=case.duration_seconds,
            sample_rate_hz=case.sample_rate,
            channels=case.channels,
            file_sha256=case.file_hash,
            audio_quality=audio_quality,
            analysis_reliability=analysis_rel,
            quality_flags=q_flags,
            input_source=input_source or "uploaded_file",
            capture_domain=capture_domain or "file_audio",
            capture_domain_reliability=capture_domain_rel or "validated",
        )

        limitations = [
            "This report is a machine-generated automated security assessment and audit evidence summary.",
            "Probability scores represent uncalibrated model estimates and do not reflect definitive biometric identification.",
            "Performance may vary under domain shift, acoustic noise, lossy codecs, and unseen attack vectors.",
            "Browser microphone capture is supported, but the current AASIST checkpoint has not been calibrated across diverse consumer microphone and WebRTC device pipelines. Raw model evidence is preserved; secondary verification is recommended when microphone-domain reliability is uncertain.",
            "This report does not constitute certified legal testimony or definitive judicial attribution.",
        ]
        if q_flags:
            if "SOURCE_SAMPLE_RATE_BELOW_MODEL_TARGET" in q_flags:
                limitations.append("Input audio is narrowband (<16 kHz). Robustness analysis established reduced reliability for sub-16 kHz speech; secondary verification is recommended.")
            if "SEVERE_CLIPPING" in q_flags:
                limitations.append("Input audio exhibits severe digital clipping (>5% clipped samples). Harmonic distortion may reduce spoof classification reliability.")
            if "INSUFFICIENT_ACTIVE_SPEECH" in q_flags:
                limitations.append("Input audio contains insufficient active speech for conclusive forensic analysis.")

        return DetectionEvidenceReportResponse(
            report_version="v1.0",
            report_type="machine_generated_security_analysis",
            case=case_meta,
            audio_evidence=audio_evidence,
            model_evidence=model_evidence,
            security_decision=security_decision,
            audit=audit_provenance,
            limitations=limitations,
        )
