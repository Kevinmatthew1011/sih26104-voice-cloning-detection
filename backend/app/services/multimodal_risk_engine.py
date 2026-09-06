"""
Unified Multimodal Risk Engine.

Combines four telemetry evidence layers:
1. Acoustic anti-spoofing layer (AASIST synthetic probability)
2. Semantic scam-intent layer (ML classification + explainable triggers)
3. Biometric speaker verification layer (Identity match/mismatch against enrolled references)
4. Capture domain / acoustic channel reliability

Deterministic Output States:
- HIGH: Critical threat (cloned voice impersonation, confirmed scam intent, or identity mismatch).
- VERIFY: Moderate threat or conflicting signals (synthetic voice on neutral content, ambiguous identity, or warning phrasing).
- LOW: Benign conversational content with human acoustics (never labeled 'SAFE').
- UNASSESSED: Incomplete evidence streams (no audio or empty transcript).
"""

import logging
from typing import Optional, Dict, Any
from app.schemas.multimodal import (
    OverallRiskEnum,
    RecommendedActionEnum,
    AcousticEvidence,
    SemanticEvidence,
    SpeakerEvidence,
    MultimodalAssessmentResponse,
)

logger = logging.getLogger(__name__)


class MultimodalRiskEngine:
    """
    Deterministic fusion engine for multi-layer threat assessment.
    """

    def evaluate(
        self,
        acoustic: Optional[AcousticEvidence] = None,
        semantic: Optional[SemanticEvidence] = None,
        speaker: Optional[SpeakerEvidence] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> MultimodalAssessmentResponse:
        context = context or {}

        # 1. Inspect layer presence
        has_acoustic = acoustic is not None and acoustic.status not in ("unanalyzed", "not_analyzed", "error")
        has_semantic = semantic is not None and semantic.risk != "unassessed"
        has_speaker = (
            speaker is not None
            and speaker.state not in ("NOT_ENROLLED", "INSUFFICIENT_AUDIO")
            and speaker.claimed_speaker_id is not None
        )

        if not has_acoustic and not has_semantic and not has_speaker:
            return MultimodalAssessmentResponse(
                overall_risk=OverallRiskEnum.UNASSESSED,
                recommended_action=RecommendedActionEnum.VERIFY,
                confidence=0.0,
                headline="UNASSESSED — Telemetry Stream Awaiting Data",
                explanation="Acoustic and conversational telemetry streams have not received sufficient data for evaluation.",
                evidence_layers={
                    "acoustic": acoustic.model_dump() if acoustic else None,
                    "semantic": semantic.model_dump() if semantic else None,
                    "speaker": speaker.model_dump() if speaker else None,
                },
            )

        # 2. Extract state flags
        is_acoustic_synthetic = False
        p_synth = acoustic.synthetic_probability if acoustic else None
        if acoustic:
            if acoustic.status == "synthetic_detected" or (p_synth is not None and p_synth >= 0.70):
                is_acoustic_synthetic = True

        is_semantic_high = semantic.risk == "high" if semantic else False
        is_semantic_warning = semantic.risk == "warning" if semantic else False
        is_identity_mismatch = speaker.state == "IDENTITY_MISMATCH" if speaker else False
        is_identity_match = speaker.state == "IDENTITY_MATCH" if speaker else False

        evidence_layers_dict = {
            "acoustic": acoustic.model_dump() if acoustic else None,
            "semantic": semantic.model_dump() if semantic else None,
            "speaker": speaker.model_dump() if speaker else None,
            "context": context,
        }

        # 3. Rule Evaluations

        # Priority 1: Cloned Voice + Scam Intent = Critical Threat
        if is_acoustic_synthetic and is_semantic_high:
            synth_pct = f"{p_synth * 100:.1f}%" if p_synth is not None else "High"
            return MultimodalAssessmentResponse(
                overall_risk=OverallRiskEnum.HIGH,
                recommended_action=RecommendedActionEnum.BLOCK,
                confidence=0.95,
                headline="CRITICAL THREAT — AI-Cloned Impersonation Scam",
                explanation=(
                    f"Acoustic analysis flagged synthetic voice artifacts (P_synth={synth_pct}), "
                    f"and conversational analysis detected high-risk scam intent "
                    f"({', '.join(semantic.reasons) if semantic and semantic.reasons else 'coercive demands'})."
                ),
                evidence_layers=evidence_layers_dict,
            )

        # Priority 2: Speaker Identity Mismatch = Impersonator Detected
        if is_identity_mismatch:
            claimed = speaker.claimed_speaker_id if speaker else "enrolled identity"
            return MultimodalAssessmentResponse(
                overall_risk=OverallRiskEnum.HIGH,
                recommended_action=RecommendedActionEnum.BLOCK,
                confidence=0.90,
                headline="HIGH THREAT — Speaker Impersonation Detected",
                explanation=(
                    f"Caller claims identity of '{claimed}', but acoustic vocal tract biometrics "
                    "diverge significantly from the enrolled profile. Possible human impersonator."
                ),
                evidence_layers=evidence_layers_dict,
            )

        # Priority 3: Severe Semantic Scam Intent (even with organic voice acoustics)
        if is_semantic_high:
            reasons_str = ", ".join(semantic.reasons) if semantic and semantic.reasons else "credential/financial demands"
            return MultimodalAssessmentResponse(
                overall_risk=OverallRiskEnum.HIGH,
                recommended_action=RecommendedActionEnum.ALERT_HUMAN_OPERATOR,
                confidence=0.85,
                headline="HIGH THREAT — Coercive Social Engineering Fraud",
                explanation=(
                    f"High-risk conversational scam patterns detected ({reasons_str}). "
                    "Caller voice exhibits human acoustic characteristics; social engineering fraud in progress."
                ),
                evidence_layers=evidence_layers_dict,
            )

        # Priority 4: Acoustic Synthetic Detected with Benign / Neutral Semantic Content
        if is_acoustic_synthetic:
            synth_pct = f"{p_synth * 100:.1f}%" if p_synth is not None else "High"
            return MultimodalAssessmentResponse(
                overall_risk=OverallRiskEnum.VERIFY,
                recommended_action=RecommendedActionEnum.VERIFY,
                confidence=0.80,
                headline="ELEVATED RISK — Synthetic Voice Detected on Neutral Content",
                explanation=(
                    f"Acoustic models detected synthetic voice generation (P_synth={synth_pct}), "
                    "though conversational intent currently matches benign dialog. Elevated vigilance advised."
                ),
                evidence_layers=evidence_layers_dict,
            )

        # Priority 5: Semantic Warning / Ambiguous Acoustic / Uncertain Identity
        if is_semantic_warning or (speaker and speaker.state == "IDENTITY_UNCERTAIN"):
            explanation = "Moderate fraud indicators or acoustic ambiguity detected."
            if is_semantic_warning and semantic and semantic.reasons:
                explanation = f"Conversational warning triggers flagged: {', '.join(semantic.reasons)}."
            elif speaker and speaker.state == "IDENTITY_UNCERTAIN":
                explanation = "Speaker biometric similarity is inconclusive relative to enrolled profile."

            return MultimodalAssessmentResponse(
                overall_risk=OverallRiskEnum.VERIFY,
                recommended_action=RecommendedActionEnum.VERIFY,
                confidence=0.65,
                headline="VERIFY — Elevated Vigilance Advised",
                explanation=explanation,
                evidence_layers=evidence_layers_dict,
            )

        # Priority 6: Benign Content + Human Acoustics + Enrolled Identity Match
        if is_identity_match:
            return MultimodalAssessmentResponse(
                overall_risk=OverallRiskEnum.LOW,
                recommended_action=RecommendedActionEnum.ALLOW,
                confidence=0.88,
                headline="LOW RISK — Enrolled Identity Matched & Human Acoustics",
                explanation=(
                    "Acoustic characteristics are consistent with human speech, conversational content "
                    "is benign, and vocal biometrics match the enrolled profile for claimed identity."
                ),
                evidence_layers=evidence_layers_dict,
            )

        # Priority 7: Benign Content + Human Acoustics (Speaker Unenrolled)
        return MultimodalAssessmentResponse(
            overall_risk=OverallRiskEnum.LOW,
            recommended_action=RecommendedActionEnum.ALLOW,
            confidence=0.75,
            headline="LOW RISK — Organic Speech Characteristics & Benign Content",
            explanation=(
                "Acoustic characteristics are consistent with natural human speech and no scam indicators "
                "were detected. Speaker identity is unverified as no reference profile is enrolled."
            ),
            evidence_layers=evidence_layers_dict,
        )


# Global singleton instance
_risk_engine_instance: Optional[MultimodalRiskEngine] = None


def get_multimodal_risk_engine() -> MultimodalRiskEngine:
    global _risk_engine_instance
    if _risk_engine_instance is None:
        _risk_engine_instance = MultimodalRiskEngine()
    return _risk_engine_instance
