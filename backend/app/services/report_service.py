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

        # 2. Audio Forensics Evidence
        audio_evidence = ReportAudioEvidence(
            file_size_bytes=case.file_size_bytes,
            mime_type=case.mime_type,
            duration_seconds=case.duration_seconds,
            sample_rate_hz=case.sample_rate,
            channels=case.channels,
            file_sha256=case.file_hash,
        )

        # 3. Model Evidence & Security Decision (if result exists)
        model_evidence: Optional[ReportModelEvidence] = None
        security_decision: Optional[SecurityDecisionDTO] = None
        audit_provenance: ReportAuditProvenance

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

            # Extract multi-window telemetry if persisted
            multi_window = meta.get("multi_window")
            analysis_mode = None
            window_count = None
            window_len = None
            hop_len = None
            agg_method = None
            suspicious_segs = None

            if multi_window and isinstance(multi_window, dict):
                analysis_mode = multi_window.get("analysis_mode")
                window_count = multi_window.get("window_count")
                window_len = multi_window.get("window_length_seconds")
                hop_len = multi_window.get("hop_seconds")
                agg_method = multi_window.get("aggregation_method")
                raw_segs = multi_window.get("suspicious_segments")
                if raw_segs and isinstance(raw_segs, list):
                    suspicious_segs = []
                    for seg in raw_segs:
                        try:
                            from app.schemas.detection import SuspiciousSegmentDTO
                            suspicious_segs.append(SuspiciousSegmentDTO(**seg))
                        except Exception:
                            pass

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
                window_count=window_count,
                window_length_seconds=window_len,
                hop_seconds=hop_len,
                aggregation_method=agg_method,
                suspicious_segments=suspicious_segs,
            )

            # Deserialization of persisted decision object (strict provenance)
            decision_data = meta.get("decision")
            if decision_data and isinstance(decision_data, dict):
                try:
                    security_decision = SecurityDecisionDTO(**decision_data)
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
        else:
            # Case pending/failed without detection result
            audit_provenance = ReportAuditProvenance(
                provenance="unprocessed",
                decision_evaluated=False,
                device_used=None,
            )

        return DetectionEvidenceReportResponse(
            report_version="v1.0",
            report_type="machine_generated_security_analysis",
            case=case_meta,
            audio_evidence=audio_evidence,
            model_evidence=model_evidence,
            security_decision=security_decision,
            audit=audit_provenance,
        )
