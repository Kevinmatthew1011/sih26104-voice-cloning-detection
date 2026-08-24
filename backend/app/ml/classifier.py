from pathlib import Path
from typing import Dict, Any, Tuple, Optional
import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline


CLASS_MAPPING = {
    0: "real",
    1: "synthetic",
}

REVERSE_CLASS_MAPPING = {
    "real": 0,
    "synthetic": 1,
}


class BaselineClassifier:
    """
    Baseline ML Audio Classifier for Voice Cloning Detection.
    
    Architecture:
    StandardScaler -> Logistic Regression (with balanced class weights and L2 regularization)
    
    Binary Classification Target:
    Class 0: Organic / Real Human Voice
    Class 1: Synthetic / Cloned Voice
    """

    def __init__(
        self,
        C: float = 1.0,
        max_iter: int = 1000,
        random_state: int = 42,
    ):
        self.C = C
        self.max_iter = max_iter
        self.random_state = random_state
        self.pipeline: Pipeline = Pipeline([
            ("scaler", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    C=self.C,
                    max_iter=self.max_iter,
                    class_weight="balanced",
                    random_state=self.random_state,
                    solver="lbfgs",
                ),
            ),
        ])
        self.is_fitted: bool = False

    def fit(self, X: np.ndarray, y: np.ndarray) -> "BaselineClassifier":
        """
        Fit scaler and logistic regression classifier on training feature matrix X and labels y.
        """
        if len(np.unique(y)) < 2:
            raise ValueError("Training requires at least two distinct classes (real and synthetic).")
        self.pipeline.fit(X, y)
        self.is_fitted = True
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict class indices (0: real, 1: synthetic)."""
        if not self.is_fitted:
            raise RuntimeError("Classifier is not fitted yet.")
        return self.pipeline.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Predict class probabilities:
        Returns array of shape (n_samples, 2) where:
        col 0 = P(real), col 1 = P(synthetic)
        """
        if not self.is_fitted:
            raise RuntimeError("Classifier is not fitted yet.")
        return self.pipeline.predict_proba(X)

    def save(self, filepath: Path) -> None:
        """Save the serialized pipeline to disk using joblib."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.pipeline, filepath)

    @classmethod
    def load(cls, filepath: Path) -> "BaselineClassifier":
        """Load a trained model artifact from disk."""
        if not filepath.exists():
            raise FileNotFoundError(f"Model artifact not found at {filepath}")
        pipeline = joblib.load(filepath)
        instance = cls()
        instance.pipeline = pipeline
        instance.is_fitted = True
        return instance

    def get_params(self) -> Dict[str, Any]:
        return {
            "classifier_type": "LogisticRegression",
            "C": self.C,
            "max_iter": self.max_iter,
            "random_state": self.random_state,
            "scaler": "StandardScaler",
            "class_mapping": CLASS_MAPPING,
        }
