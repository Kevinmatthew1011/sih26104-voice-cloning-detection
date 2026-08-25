from typing import Dict, Any, Tuple, Optional
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    roc_curve,
    confusion_matrix,
)

# Class definitions for binary anti-spoofing
CLASS_REAL: int = 0         # Organic / Genuine Human Speech (Negative Class)
CLASS_SYNTHETIC: int = 1    # Synthetic / Cloned Speech (Positive Class)


def compute_eer(y_true: np.ndarray, y_score: np.ndarray) -> Tuple[float, float]:
    """
    Computes Equal Error Rate (EER) and the corresponding decision threshold.
    
    In biometric voice spoofing detection:
    - Positive class (1) = Synthetic Speech
    - Negative class (0) = Real Speech
    - False Acceptance Rate (FAR / FPR): Real speech incorrectly classified as synthetic.
    - False Rejection Rate (FRR / FNR): Synthetic speech incorrectly classified as real.
    - Equal Error Rate (EER): The operating threshold where FAR equals FRR.
    
    Returns:
        Tuple of (eer_value, optimal_threshold) where eer_value is between 0.0 and 1.0.
    """
    y_true = np.asarray(y_true, dtype=np.int32)
    y_score = np.asarray(y_score, dtype=np.float64)

    if len(np.unique(y_true)) < 2:
        raise ValueError("EER calculation requires both genuine (0) and synthetic (1) ground-truth samples.")

    # Compute ROC curve components (FPR = FAR, TPR = 1 - FRR)
    fpr, tpr, thresholds = roc_curve(y_true, y_score, pos_label=CLASS_SYNTHETIC)
    fnr = 1.0 - tpr

    # Edge cases: Perfect separation
    if np.any((fpr == 0.0) & (fnr == 0.0)):
        return 0.0, 0.5

    # Find point closest to FPR == FNR
    diffs = np.abs(fpr - fnr)
    min_idx = int(np.argmin(diffs))

    # Linear interpolation between min_idx and neighbor if valid
    if min_idx < len(fpr) - 1:
        # Interpolate between min_idx and min_idx + 1
        x1, x2 = fpr[min_idx], fpr[min_idx + 1]
        y1, y2 = fnr[min_idx], fnr[min_idx + 1]
        denom = (x2 - x1) - (y2 - y1)
        if abs(denom) > 1e-9:
            alpha = (y1 - x1) / denom
            if 0.0 <= alpha <= 1.0:
                eer = float(x1 + alpha * (x2 - x1))
                opt_thresh = float(thresholds[min_idx] + alpha * (thresholds[min_idx + 1] - thresholds[min_idx]))
                return float(np.clip(eer, 0.0, 1.0)), opt_thresh

    eer = float((fpr[min_idx] + fnr[min_idx]) / 2.0)
    opt_thresh = float(thresholds[min_idx]) if min_idx < len(thresholds) else 0.5
    return float(np.clip(eer, 0.0, 1.0)), opt_thresh


def compute_evaluation_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prob: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """
    Computes standard and biometric evaluation metrics for voice cloning detection.
    """
    y_true = np.asarray(y_true, dtype=np.int32)
    y_pred = np.asarray(y_pred, dtype=np.int32)

    has_both_classes = len(np.unique(y_true)) >= 2

    acc = float(accuracy_score(y_true, y_pred))
    prec = float(precision_score(y_true, y_pred, pos_label=CLASS_SYNTHETIC, zero_division=0))
    rec = float(recall_score(y_true, y_pred, pos_label=CLASS_SYNTHETIC, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, pos_label=CLASS_SYNTHETIC, zero_division=0))

    cm = confusion_matrix(y_true, y_pred, labels=[CLASS_REAL, CLASS_SYNTHETIC])
    tn, fp, fn, tp = int(cm[0, 0]), int(cm[0, 1]), int(cm[1, 0]), int(cm[1, 1])

    roc_auc_val: Optional[float] = None
    eer_val: Optional[float] = None
    eer_thresh_val: Optional[float] = None

    if y_prob is not None and has_both_classes:
        # y_prob should represent positive class (synthetic) probability
        y_prob = np.asarray(y_prob, dtype=np.float64)
        if y_prob.ndim == 2:
            y_prob_synth = y_prob[:, CLASS_SYNTHETIC]
        else:
            y_prob_synth = y_prob

        try:
            roc_auc_val = float(roc_auc_score(y_true, y_prob_synth))
        except Exception:
            roc_auc_val = None

        try:
            eer_val, eer_thresh_val = compute_eer(y_true, y_prob_synth)
        except Exception:
            eer_val, eer_thresh_val = None, None

    return {
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1_score": round(f1, 4),
        "roc_auc": round(roc_auc_val, 4) if roc_auc_val is not None else None,
        "eer": round(eer_val, 4) if eer_val is not None else None,
        "eer_threshold": round(eer_thresh_val, 4) if eer_thresh_val is not None else None,
        "confusion_matrix": {
            "tn": tn,
            "fp": fp,
            "fn": fn,
            "tp": tp,
            "matrix_2x2": [[tn, fp], [fn, tp]],
        },
        "sample_counts": {
            "total": len(y_true),
            "real_ground_truth": int(np.sum(y_true == CLASS_REAL)),
            "synthetic_ground_truth": int(np.sum(y_true == CLASS_SYNTHETIC)),
        },
    }


def format_evaluation_report(metrics: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> str:
    """Generates clean ASCII research evaluation summary for logs and CLI."""
    lines = [
        "=" * 60,
        "MODEL EVALUATION METRICS SUMMARY",
        "=" * 60,
    ]

    if metadata:
        lines.append(f"Model Version:       {metadata.get('model_version', 'N/A')}")
        lines.append(f"Feature Version:     {metadata.get('feature_version', 'N/A')}")
        lines.append(f"Evaluation Protocol: {metadata.get('evaluation_protocol', 'N/A')}")
        lines.append(f"Random Seed:         {metadata.get('random_seed', 'N/A')}")
        lines.append("-" * 60)

    counts = metrics.get("sample_counts", {})
    lines.append(f"Test Samples:        {counts.get('total', 'N/A')} (Real: {counts.get('real_ground_truth', 'N/A')}, Synthetic: {counts.get('synthetic_ground_truth', 'N/A')})")
    lines.append(f"Accuracy:            {metrics['accuracy']:.4f} ({metrics['accuracy']*100:.2f}%)")
    lines.append(f"Precision (Synth):   {metrics['precision']:.4f}")
    lines.append(f"Recall (Synth):      {metrics['recall']:.4f}")
    lines.append(f"F1 Score:            {metrics['f1_score']:.4f}")

    if metrics.get("roc_auc") is not None:
        lines.append(f"ROC-AUC:             {metrics['roc_auc']:.4f}")
    else:
        lines.append("ROC-AUC:             N/A (requires multi-class probabilities)")

    if metrics.get("eer") is not None:
        lines.append(f"Equal Error Rate:    {metrics['eer']:.4f} ({metrics['eer']*100:.2f}%) @ thresh={metrics.get('eer_threshold', 0.5):.4f}")
    else:
        lines.append("Equal Error Rate:    N/A (requires multi-class probabilities)")

    cm = metrics.get("confusion_matrix", {})
    lines.append("-" * 60)
    lines.append("Confusion Matrix:")
    lines.append(f"                 Predicted Real   Predicted Synth")
    lines.append(f"  Actual Real    {cm.get('tn', 0):<16} {cm.get('fp', 0):<16} (TN, FP)")
    lines.append(f"  Actual Synth   {cm.get('fn', 0):<16} {cm.get('tp', 0):<16} (FN, TP)")
    lines.append("=" * 60)

    return "\n".join(lines)
