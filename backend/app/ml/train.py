import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report,
)
from sklearn.model_selection import train_test_split

from app.ml.preprocessing import AudioPreprocessor
from app.ml.features import AudioFeatureExtractor
from app.ml.classifier import BaselineClassifier, REVERSE_CLASS_MAPPING


# Supported audio file formats
AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac", ".webm"}


def find_audio_files(directory: Path) -> List[Path]:
    """Recursively discover supported audio files within a directory."""
    if not directory.exists() or not directory.is_dir():
        return []
    return [
        p for p in directory.rglob("*")
        if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
    ]


def load_dataset_split(
    split_dir: Path,
    preprocessor: AudioPreprocessor,
    feature_extractor: AudioFeatureExtractor,
    max_samples_per_class: Optional[int] = None,
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """
    Loads real and synthetic audio samples from a split directory (e.g. ml_data/train),
    applies preprocessing, and extracts feature vectors.
    """
    real_dir = split_dir / "real"
    synth_dir = split_dir / "synthetic"

    real_files = find_audio_files(real_dir)
    synth_files = find_audio_files(synth_dir)

    if not real_files and not synth_files:
        raise FileNotFoundError(
            f"No audio files found in '{split_dir}'. Ensure '{real_dir}' and '{synth_dir}' contain approved audio."
        )

    if not real_files:
        raise ValueError(
            f"Dataset class 'real' is missing or contains 0 audio files in '{real_dir}'."
        )

    if not synth_files:
        raise ValueError(
            f"Dataset class 'synthetic' is missing or contains 0 audio files in '{synth_dir}'."
        )

    if max_samples_per_class:
        real_files = real_files[:max_samples_per_class]
        synth_files = synth_files[:max_samples_per_class]

    print(f"  → Found {len(real_files)} real and {len(synth_files)} synthetic audio files in '{split_dir.name}'")

    X_list: List[np.ndarray] = []
    y_list: List[int] = []
    file_paths: List[str] = []

    # Process real files (Class 0)
    for p in real_files:
        try:
            feats = feature_extractor.extract_from_file(p, preprocessor=preprocessor)
            X_list.append(feats)
            y_list.append(REVERSE_CLASS_MAPPING["real"])
            file_paths.append(str(p))
        except Exception as e:
            print(f"  [Warning] Skipping unreadable audio file {p.name}: {str(e)}", file=sys.stderr)

    # Process synthetic files (Class 1)
    for p in synth_files:
        try:
            feats = feature_extractor.extract_from_file(p, preprocessor=preprocessor)
            X_list.append(feats)
            y_list.append(REVERSE_CLASS_MAPPING["synthetic"])
            file_paths.append(str(p))
        except Exception as e:
            print(f"  [Warning] Skipping unreadable audio file {p.name}: {str(e)}", file=sys.stderr)

    if len(X_list) == 0:
        raise RuntimeError("No valid audio samples could be preprocessed from the dataset.")

    return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.int32), file_paths


def train_baseline(
    data_dir: Path,
    output_dir: Path,
    test_size: float = 0.2,
    random_state: int = 42,
    c_reg: float = 1.0,
    max_iter: int = 1000,
) -> Dict[str, Any]:
    """
    Main training execution function.
    """
    print("=" * 70)
    print("SIH26104 Voice Cloning Detection — Baseline ML Model Training")
    print("=" * 70)
    print(f"Dataset root directory: {data_dir.resolve()}")
    print(f"Output model directory: {output_dir.resolve()}")

    # 1. Dataset Directory Validation
    train_dir = data_dir / "train"
    val_dir = data_dir / "validation"
    test_dir = data_dir / "test"

    if not data_dir.exists() or not train_dir.exists():
        print(
            "\n[ERROR] No training dataset found!\n"
            f"Expected dataset structure at: {data_dir.resolve()}/\n"
            "  ├── train/\n"
            "  │   ├── real/        (Add genuine human speech files)\n"
            "  │   └── synthetic/   (Add AI/cloned speech files)\n"
            "  ├── validation/      (Optional)\n"
            "  └── test/            (Optional)\n\n"
            "Please add approved audio files before running training.\n",
            file=sys.stderr,
        )
        sys.exit(1)

    preprocessor = AudioPreprocessor()
    feature_extractor = AudioFeatureExtractor()

    # 2. Extract Training Features
    print("\n[Step 1/5] Ingesting and extracting features from training data...")
    try:
        X_train, y_train, train_paths = load_dataset_split(
            train_dir, preprocessor, feature_extractor
        )
    except Exception as e:
        print(f"\n[ERROR] Failed to load training dataset: {str(e)}\n", file=sys.stderr)
        sys.exit(1)

    # 3. Handle Validation / Test Split
    has_test_dir = test_dir.exists() and len(find_audio_files(test_dir)) > 0
    if has_test_dir:
        print("\n[Step 2/5] Ingesting dedicated test set...")
        X_test, y_test, test_paths = load_dataset_split(
            test_dir, preprocessor, feature_extractor
        )
        split_strategy = "dedicated_directory_split"
    else:
        print(f"\n[Step 2/5] Performing stratified train/test split (test_size={test_size})...")
        X_train, X_test, y_train, y_test = train_test_split(
            X_train, y_train, test_size=test_size, random_state=random_state, stratify=y_train
        )
        split_strategy = f"stratified_random_split (test_size={test_size}, seed={random_state})"
        print("  [Notice] Evaluation uses random clip split. For speaker-independent guarantees,")
        print("  ensure speakers in train and test splits do not overlap.")

    print(f"  → Training samples: {len(X_train)} (Real: {np.sum(y_train == 0)}, Synth: {np.sum(y_train == 1)})")
    print(f"  → Testing samples:  {len(X_test)} (Real: {np.sum(y_test == 0)}, Synth: {np.sum(y_test == 1)})")
    print(f"  → Feature dimensions per sample: {feature_extractor.feature_dim}")

    # 4. Train Model
    print("\n[Step 3/5] Fitting Logistic Regression with StandardScaler...")
    clf = BaselineClassifier(C=c_reg, max_iter=max_iter, random_state=random_state)
    clf.fit(X_train, y_train)

    # 5. Evaluate Model
    print("\n[Step 4/5] Evaluating model on evaluation set...")
    y_pred = clf.predict(X_test)
    y_prob = clf.predict_proba(X_test)[:, 1]

    acc = float(accuracy_score(y_test, y_pred))
    prec = float(precision_score(y_test, y_pred, zero_division=0))
    rec = float(recall_score(y_test, y_pred, zero_division=0))
    f1 = float(f1_score(y_test, y_pred, zero_division=0))
    cm = confusion_matrix(y_test, y_pred).tolist()

    print("\n" + "=" * 40)
    print("BASELINE MODEL EVALUATION METRICS")
    print("=" * 40)
    print(f"  Accuracy:         {acc:.4f} ({acc*100:.2f}%)")
    print(f"  Precision (Synth):{prec:.4f}")
    print(f"  Recall (Synth):   {rec:.4f}")
    print(f"  F1 Score (Synth): {f1:.4f}")
    print(f"  Confusion Matrix (rows: true, cols: pred):")
    print(f"    [[TN: {cm[0][0]}, FP: {cm[0][1]}],")
    print(f"     [FN: {cm[1][0]}, TP: {cm[1][1]}]]")
    print("=" * 40)

    # 6. Save Artifacts
    print("\n[Step 5/5] Saving model artifacts and forensic metadata...")
    output_dir.mkdir(parents=True, exist_ok=True)
    model_file = output_dir / "model.joblib"
    clf.save(model_file)

    metadata: Dict[str, Any] = {
        "model_version": "baseline-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "classifier": clf.get_params(),
        "preprocessing": preprocessor.get_config(),
        "features": feature_extractor.get_config(),
        "feature_names": feature_extractor.feature_names,
        "dataset": {
            "source_dir": str(data_dir.resolve()),
            "train_samples_count": len(X_train),
            "test_samples_count": len(X_test),
            "split_strategy": split_strategy,
        },
        "evaluation_metrics": {
            "accuracy": acc,
            "precision": prec,
            "recall": rec,
            "f1_score": f1,
            "confusion_matrix": cm,
        },
        "limitations": [
            "Baseline linear model; does not learn deep hierarchical temporal representations.",
            "Vulnerable to unseen TTS/VC algorithms, acoustic room reverberation, and compression codecs.",
            "Evaluation may suffer from speaker leakage if dataset lacks explicit speaker ID partition.",
        ],
    }

    meta_file = output_dir / "metadata.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"  ✓ Saved model artifact to: {model_file}")
    print(f"  ✓ Saved metadata to:       {meta_file}")
    print("\nTraining completed successfully.")
    return metadata


def main():
    parser = argparse.ArgumentParser(
        description="Train the SIH26104 Voice Cloning Detection Baseline ML Model."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent.parent.parent / "ml_data",
        help="Path to the root dataset directory containing train/real and train/synthetic folders.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent.parent.parent / "models" / "baseline-v1",
        help="Destination directory to save model.joblib and metadata.json.",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Proportion of dataset for testing if test folder is empty (default: 0.2).",
    )
    parser.add_argument(
        "--c-reg",
        type=float,
        default=1.0,
        help="Inverse regularization strength for Logistic Regression (default: 1.0).",
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=1000,
        help="Maximum iterations for Logistic Regression solver (default: 1000).",
    )

    args = parser.parse_args()
    train_baseline(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        test_size=args.test_size,
        c_reg=args.c_reg,
        max_iter=args.max_iter,
    )


if __name__ == "__main__":
    main()
