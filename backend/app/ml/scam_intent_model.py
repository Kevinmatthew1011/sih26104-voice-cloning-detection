"""
ML Scam Intent Model & Inference Wrapper.

Combines calibrated statistical text classification (TF-IDF + Logistic Regression)
with an explainable pattern-matching fallback layer.
"""

import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import joblib

from app.schemas.scam_intent import ScamIntentResponse

logger = logging.getLogger(__name__)

DEFAULT_MODEL_DIR = Path("models/scam-intent-v1")

EXPLAINABLE_RULES = [
    (
        r"\b(share|tell|read|give|send|provide)\b.{0,50}\b(otp|one[ -]time password|password|pin|verification code|cvv)\b",
        "Caller requests a private authentication code or credentials.",
        "credential_theft",
    ),
    (
        r"\b(install|download|enable|open)\b.{0,60}\b(anydesk|teamviewer|ultraviewer|quickassist|remote access|remote desktop)\b",
        "Caller requests remote access software installation or screen sharing.",
        "remote_access_takeover",
    ),
    (
        r"\b(transfer|send|wire|pay|buy)\b.{0,60}\b(money|payment|funds|balance|gift card|crypto|bitcoin|safe account)\b",
        "Caller demands financial transfer or unrecoverable payment.",
        "urgent_financial_coercion",
    ),
    (
        r"\b(police|cbi|fbi|arrest|warrant|customs|narcotics|court|seizure|enforcement)\b",
        "Caller cites law enforcement authority or legal coercion.",
        "authority_impersonation",
    ),
    (
        r"\b(urgent|immediately|act now|account will be blocked|before business close|within \d+ minutes)\b",
        "Caller creates artificial urgency or coercive pressure.",
        "urgent_financial_coercion",
    ),
]


class ScamIntentClassifier:
    """
    Inference engine for Scam Intent Detection.
    """

    def __init__(self, model_dir: Optional[Path] = None):
        self.model_dir = Path(model_dir or DEFAULT_MODEL_DIR)
        self.pipeline = None
        self.classes = []
        self.model_version = "scam-intent-v1"
        self._load_model()

    def _load_model(self):
        model_path = self.model_dir / "model.joblib"
        if model_path.exists():
            try:
                self.pipeline = joblib.load(model_path)
                self.classes = list(self.pipeline.classes_)
                logger.info("Loaded ScamIntent model from %s with classes %s", model_path, self.classes)
            except Exception as e:
                logger.warning("Could not load scam intent model (%s); using heuristic fallback.", e)
        else:
            logger.warning("Scam intent model not found at %s; using heuristic fallback.", model_path)

    def analyze(self, text: str) -> ScamIntentResponse:
        """
        Analyze a text string or combined transcript.
        """
        clean_text = text.strip()
        if not clean_text:
            return ScamIntentResponse(
                scam_probability=0.0,
                risk_level="unassessed",
                primary_intent="unassessed",
                intent_scores={},
                detected_triggers=[],
                model_version=self.model_version,
                is_ml_inferred=False,
            )

        # 1. Pattern-based explainable rule evaluation
        detected_triggers: List[str] = []
        rule_categories: List[str] = []
        lower = clean_text.lower()

        # Check for educational negation ("never share OTP", "do not give password")
        is_negated = bool(re.search(r"\b(never|do not|don't|warned not to)\b", lower))

        if not is_negated:
            for pattern, trigger_desc, category in EXPLAINABLE_RULES:
                if re.search(pattern, lower, re.IGNORECASE):
                    detected_triggers.append(trigger_desc)
                    rule_categories.append(category)

        # 2. Machine Learning Inference
        if self.pipeline is not None:
            try:
                probs = self.pipeline.predict_proba([clean_text])[0]
                class_scores = {
                    cls_name: round(float(prob), 4)
                    for cls_name, prob in zip(self.classes, probs)
                }

                benign_prob = class_scores.get("benign", 0.0)
                non_benign_scores = {k: v for k, v in class_scores.items() if k != "benign"}
                max_scam_score = max(non_benign_scores.values()) if non_benign_scores else 0.0

                # Determine primary intent
                if rule_categories:
                    primary_intent = rule_categories[0]
                elif non_benign_scores and max_scam_score > benign_prob:
                    primary_intent = max(non_benign_scores.items(), key=lambda x: x[1])[0]
                else:
                    primary_intent = "benign"

                # Use the winning scam class probability, not ``1 - P(benign)``.
                # In this multi-class model the latter adds several weak, unrelated
                # scam classes together and can turn short/out-of-domain ASR fragments
                # (for example, "what other") into a high-risk determination.
                if detected_triggers:
                    scam_prob = max(1.0 - benign_prob, 0.75)
                    risk_level = "high"
                elif primary_intent == "benign":
                    scam_prob = round(max_scam_score, 4)
                    risk_level = "no_indicators"
                else:
                    scam_prob = round(max_scam_score, 4)
                    if max_scam_score >= 0.65:
                        risk_level = "high"
                    elif max_scam_score >= 0.50:
                        risk_level = "warning"
                    else:
                        # The model chose a scam class, but without enough evidence to
                        # use it in live multimodal fusion. Keep the raw class scores for
                        # inspection while reporting the semantic layer as unassessed.
                        risk_level = "unassessed"
                        primary_intent = "unassessed"

                return ScamIntentResponse(
                    scam_probability=round(scam_prob, 4),
                    risk_level=risk_level,
                    primary_intent=primary_intent,
                    intent_scores=class_scores,
                    detected_triggers=detected_triggers,
                    model_version=self.model_version,
                    is_ml_inferred=True,
                )
            except Exception as e:
                logger.error("Scam intent ML inference error: %s; falling back to rules.", e)

        # 3. Rule-only fallback
        if detected_triggers:
            risk = "high" if len(detected_triggers) >= 2 or "credentials" in detected_triggers[0] else "warning"
            p = 0.85 if risk == "high" else 0.55
            primary = rule_categories[0] if rule_categories else "credential_theft"
        else:
            risk = "no_indicators"
            p = 0.05
            primary = "benign"

        return ScamIntentResponse(
            scam_probability=p,
            risk_level=risk,
            primary_intent=primary,
            intent_scores={primary: p, "benign": round(1.0 - p, 2)},
            detected_triggers=detected_triggers,
            model_version=self.model_version,
            is_ml_inferred=False,
        )
