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
    
    Consumes explicit synthetic probability and normalized telemetry from any
    underlying detection engine (AASIST, baseline, mock) and issues policy directives.
    """
    POLICY_VERSION: str = "v1.0"

    @classmethod
    def evaluate(
        cls,
        prediction: str,
        synthetic_probability: float,
        risk_level: str,
        engine_type: str,
        extra_telemetry: Optional[Dict[str, Any]] = None,
    ) -> SecurityDecisionDTO:
        """
        Evaluate operational security policy given an explicit synthetic probability.
        
        Threshold rules:
        - synthetic_probability < 0.50        -> ALLOW
        - 0.50 <= synthetic_probability < 0.70 -> VERIFY
        - synthetic_probability >= 0.70       -> BLOCK
        """
        p_synth = float(round(synthetic_probability, 4))
        # Ensure clamped range [0.0, 1.0]
        p_synth = max(0.0, min(1.0, p_synth))

        if p_synth >= 0.70:
            return SecurityDecisionDTO(
                action=ActionEnum.BLOCK,
                decision_message="Strong synthetic voice indicators detected. Do not trust voice-only authorization.",
                synthetic_probability=p_synth,
                policy_version=cls.POLICY_VERSION,
                reason_codes=["HIGH_CONFIDENCE_SYNTHETIC_DETECTED"],
                recommended_steps=[
                    "Do not approve sensitive actions based only on this voice recording.",
                    "Require out-of-band identity verification.",
                    "Escalate the event to Fraud/Security Operations.",
                    "Preserve the recording and detection metadata for review.",
                ],
            )
        elif 0.50 <= p_synth < 0.70:
            return SecurityDecisionDTO(
                action=ActionEnum.VERIFY,
                decision_message="Suspicious voice characteristics detected. Perform additional identity verification.",
                synthetic_probability=p_synth,
                policy_version=cls.POLICY_VERSION,
                reason_codes=["SUSPICIOUS_VOICE_CHARACTERISTICS"],
                recommended_steps=[
                    "Trigger out-of-band step-up authentication (SMS/TOTP/Push challenge).",
                    "Request secondary knowledge-based verification.",
                    "Defer high-value transaction approvals.",
                    "Preserve the recording and detection metadata for review.",
                ],
            )
        else:
            return SecurityDecisionDTO(
                action=ActionEnum.ALLOW,
                decision_message="No strong synthetic voice indicators detected.",
                synthetic_probability=p_synth,
                policy_version=cls.POLICY_VERSION,
                reason_codes=["NO_STRONG_SYNTHETIC_INDICATORS"],
                recommended_steps=[
                    "No strong synthetic voice indicators detected. Continue according to standard authorization policy.",
                    "Maintain standard transaction monitoring.",
                ],
            )
