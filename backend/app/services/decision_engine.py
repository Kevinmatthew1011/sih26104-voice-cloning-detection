"""
Security Decision & Prevention Engine.

Evaluates anti-spoofing telemetry against operational risk policies to issue actionable
authorization directives (ALLOW, VERIFY, BLOCK).

Policy Thresholds (Operational policy rules, not calibrated probability guarantees):
- P_synth < 0.50          -> ALLOW  (No strong synthetic voice indicators detected)
- 0.50 <= P_synth < 0.70  -> VERIFY (Suspicious voice characteristics detected. Perform additional identity verification)
- P_synth >= 0.70         -> BLOCK  (Strong synthetic voice indicators detected. Do not trust voice-only authorization)
"""

from typing import Optional, List, Dict, Any
from app.schemas.detection import ActionEnum, SecurityDecisionDTO


class SecurityDecisionEngine:
    """
    Decoupled Security Decision & Fraud Prevention Policy Engine.
    
    Consumes explicit synthetic probability, acoustic signal quality, and capture-domain
    provenance telemetry from underlying detection engines and issues separate raw ML
    and final operational policy directives.
    """
    POLICY_VERSION: str = "v1.0"

    @classmethod
    def evaluate(
        cls,
        prediction: str,
        synthetic_probability: Optional[float],
        risk_level: str,
        engine_type: str,
        extra_telemetry: Optional[Dict[str, Any]] = None,
        analysis_reliability: Optional[str] = "reliable",
        quality_flags: Optional[List[str]] = None,
        input_source: Optional[str] = "uploaded_file",
        capture_domain_reliability: Optional[str] = None,
    ) -> SecurityDecisionDTO:
        """
        Evaluate operational security policy given an explicit synthetic probability, signal quality,
        and capture domain reliability provenance.
        
        Threshold rules (Raw ML Policy):
        - synthetic_probability < 0.50        -> ALLOW
        - 0.50 <= synthetic_probability < 0.70 -> VERIFY
        - synthetic_probability >= 0.70       -> BLOCK
        - insufficient_speech                  -> NOT_EVALUATED
        """
        reliability = analysis_reliability or "reliable"
        flags = quality_flags or []
        src = input_source or "uploaded_file"

        # Resolve capture domain and domain reliability
        if src == "browser_microphone":
            capture_domain = "browser_microphone"
            cap_domain_rel = capture_domain_reliability or "unvalidated"
        else:
            capture_domain = "file_audio"
            cap_domain_rel = capture_domain_reliability or "validated"

        # 1. Raw ML Action determination (UNTOUCHED)
        if synthetic_probability is None or reliability == "insufficient_speech":
            p_synth = None
            raw_ml_action = ActionEnum.NOT_EVALUATED
        else:
            p_synth = float(round(synthetic_probability, 4))
            p_synth = max(0.0, min(1.0, p_synth))
            if p_synth >= 0.70:
                raw_ml_action = ActionEnum.BLOCK
            elif p_synth >= 0.50:
                raw_ml_action = ActionEnum.VERIFY
            else:
                raw_ml_action = ActionEnum.ALLOW

        # 2. Quality-Aware & Domain-Aware Final Operational Action determination
        if reliability == "insufficient_speech":
            final_action = ActionEnum.VERIFY
            msg = "Insufficient analyzable speech. Voice authenticity could not be assessed. Perform secondary identity verification."
            reasons = ["INSUFFICIENT_ACTIVE_SPEECH"] + flags
            steps = [
                "Request a new voice recording with clear, continuous speech.",
                "Perform out-of-band step-up authentication.",
            ]
        elif cap_domain_rel == "unvalidated" or src == "browser_microphone":
            # Real-world physical microphone domain shift hardening:
            # Automated blocking is deferred; raw ML evidence is preserved while requiring out-of-band verification.
            final_action = ActionEnum.VERIFY
            if raw_ml_action == ActionEnum.BLOCK:
                msg = (
                    "Strong synthetic indicators were produced on a browser microphone recording. "
                    "Physical microphone and device processing characteristics may reduce model-domain reliability. "
                    "Preserve the raw model result and require secondary identity verification."
                )
                reasons = ["UNVALIDATED_MICROPHONE_DOMAIN", "HIGH_CONFIDENCE_SYNTHETIC_DETECTED"] + flags
                steps = [
                    "Preserve the raw model evidence and detection metadata for review.",
                    "Require out-of-band secondary identity verification (MFA / step-up challenge).",
                    "Do not rely solely on microphone-domain automated blocking without secondary corroboration.",
                ]
            elif raw_ml_action == ActionEnum.VERIFY:
                msg = (
                    "Suspicious voice characteristics detected on a browser microphone recording. "
                    "Secondary identity verification required."
                )
                reasons = ["UNVALIDATED_MICROPHONE_DOMAIN", "SUSPICIOUS_VOICE_CHARACTERISTICS"] + flags
                steps = [
                    "Trigger out-of-band step-up authentication (SMS/TOTP/Push challenge).",
                    "Request secondary knowledge-based verification.",
                    "Defer high-value transaction approvals.",
                    "Preserve the recording and detection metadata for review.",
                ]
            else:  # ALLOW
                msg = (
                    "No strong synthetic voice indicators detected on a browser microphone recording. "
                    "Because consumer microphone capture characteristics may reduce model-domain certainty, "
                    "secondary verification is advised before voice-only authorization."
                )
                reasons = ["UNVALIDATED_MICROPHONE_DOMAIN", "NO_STRONG_SYNTHETIC_INDICATORS"] + flags
                steps = [
                    "Perform standard secondary verification before approving high-risk actions.",
                    "Maintain standard transaction monitoring.",
                    "Preserve the recording and detection metadata for review.",
                ]
        elif reliability == "degraded":
            final_action = ActionEnum.VERIFY
            if raw_ml_action == ActionEnum.BLOCK:
                msg = (
                    "Synthetic voice indicators detected, but audio channel is degraded. "
                    "Degraded quality reduces confidence; secondary identity verification and escalation required."
                )
                reasons = ["DEGRADED_QUALITY_SYNTHETIC_INDICATION"] + flags
                steps = [
                    "Escalate to Fraud/Security Operations for secondary review.",
                    "Require out-of-band multi-factor authentication.",
                    "Preserve the recording and detection metadata for review.",
                ]
            else:
                msg = (
                    "No strong synthetic voice indicators detected, but audio channel is degraded. "
                    "Out-of-band verification required."
                )
                reasons = ["DEGRADED_CHANNEL_STEP_UP_REQUIRED"] + flags
                steps = [
                    "Perform out-of-band secondary identity verification.",
                    "Request uncompressed or full-band recording if available.",
                    "Maintain standard transaction monitoring.",
                ]
        else:  # reliable + validated domain
            if raw_ml_action == ActionEnum.BLOCK:
                final_action = ActionEnum.BLOCK
                msg = "Strong synthetic voice indicators detected. Do not trust voice-only authorization."
                reasons = ["HIGH_CONFIDENCE_SYNTHETIC_DETECTED"]
                steps = [
                    "Do not approve sensitive actions based only on this voice recording.",
                    "Require out-of-band identity verification.",
                    "Escalate the event to Fraud/Security Operations.",
                    "Preserve the recording and detection metadata for review.",
                ]
            elif raw_ml_action == ActionEnum.VERIFY:
                final_action = ActionEnum.VERIFY
                msg = "Suspicious voice characteristics detected. Perform additional identity verification."
                reasons = ["SUSPICIOUS_VOICE_CHARACTERISTICS"]
                steps = [
                    "Trigger out-of-band step-up authentication (SMS/TOTP/Push challenge).",
                    "Request secondary knowledge-based verification.",
                    "Defer high-value transaction approvals.",
                    "Preserve the recording and detection metadata for review.",
                ]
            else:
                final_action = ActionEnum.ALLOW
                msg = "No strong synthetic voice indicators detected under nominal input-quality conditions."
                reasons = ["NO_STRONG_SYNTHETIC_INDICATORS"]
                steps = [
                    "No strong synthetic voice indicators detected under nominal input-quality conditions. Continue according to standard authorization policy.",
                    "Maintain standard transaction monitoring.",
                ]

        return SecurityDecisionDTO(
            action=final_action,
            decision_message=msg,
            synthetic_probability=p_synth,
            policy_version=cls.POLICY_VERSION,
            decision_source="policy_v1.0",
            raw_ml_action=raw_ml_action,
            final_operational_action=final_action,
            analysis_reliability=reliability,
            input_source=src,
            capture_domain=capture_domain,
            capture_domain_reliability=cap_domain_rel,
            quality_flags=flags,
            reason_codes=reasons,
            recommended_steps=steps,
        )
