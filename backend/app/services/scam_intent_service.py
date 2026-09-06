"""
Scam Intent Service.

Provides interface for semantic analysis of transcripts and sequential messages.
"""

from typing import List, Optional
from app.ml.scam_intent_model import ScamIntentClassifier
from app.schemas.scam_intent import ScamIntentResponse

_classifier_instance: Optional[ScamIntentClassifier] = None


def get_scam_intent_classifier() -> ScamIntentClassifier:
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = ScamIntentClassifier()
    return _classifier_instance


class ScamIntentService:
    def __init__(self):
        self.classifier = get_scam_intent_classifier()

    def analyze_text(self, text: str) -> ScamIntentResponse:
        return self.classifier.analyze(text)

    def analyze_messages(self, messages: List[str]) -> ScamIntentResponse:
        combined = " \n".join([m.strip() for m in messages if m.strip()])
        return self.classifier.analyze(combined)


_service_instance: Optional[ScamIntentService] = None


def get_scam_intent_service() -> ScamIntentService:
    global _service_instance
    if _service_instance is None:
        _service_instance = ScamIntentService()
    return _service_instance
