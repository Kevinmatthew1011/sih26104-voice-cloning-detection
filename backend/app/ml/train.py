import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import numpy as np

from app.ml.preprocessing import AudioPreprocessor
from app.ml.features import AudioFeatureExtractor
from app.ml.classifier import BaselineClassifier, REVERSE_CLASS_MAPPING
from app.ml.dataset import (
    DatasetValidator,
    DatasetValidationError,
    DatasetSummary,
    speaker_independent_split,
    extract_speaker_id_from_path,
)
from app.ml.metrics import compute_evaluation_metrics, format_evaluation_report


def load_dataset_split(
    split_dir: Path,
    preprocessor: AudioPreprocessor,
    feature_extractor: AudioFeatureExtractor,
    max_samples_per_class: Optional[int] = None,
) -> Tuple[np.ndarray, np.ndarray, List[str], List[Optional[str]]]:
    """
    Loads real and synthetic audio samples from a split directory (e.g. ml_data/train),
    applies standardized preprocessing, and extracts 88-D feature vectors.
    """
    real_dir = split_dir / "real"
    synth_dir = split_dir / "synthetic"

    real_files = sorted([p for p in real_dir.rglob("*") if p.is_file() and not p.name.startswith(".") and p.name != ".gitkeep"])
    synth_files = sorted([p for p in synth_dir.rglob("*") if p.is_file() and not p.name.startswith(".") and p.name != ".gitkeep"])

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

    print(f"  → Ingesting {len(real_files)} real and {len(synth_files)} synthetic audio files in '{split_dir.name}'")

    X_list: List[np.ndarray] = []
    y_list: List[int] = []
    file_paths: List[str] = []
    speaker_list: List[Optional[str]] = []

    # Process real files (Class 0)
    for p in real_files:
        try:
            feats = feature_extractor.extract_from_file(p, preprocessor=preprocessor)
            X_list.append(feats)
            y_list.append(REVERSE_CLASS_MAPPING["real"])
            file_paths.append(str(p))
            speaker_list.append(extract_speaker_id_from_path(p))
        except Exception as e:
            print(f"  [Warning] Skipping unreadable audio file {p.name}: {str(e)}", file=sys.stderr)

    # Process synthetic files (Class 1)
    for p in synth_files:
        try:
            feats = feature_extractor.extract_from_file(p, preprocessor=preprocessor)
            X_list.append(feats)
            y_list.append(REVERSE_CLASS_MAPPING["synthetic"])
            file_paths.append(str(p))
            speaker_list.append(extract_speaker_id_from_path(p))
        except Exception as e:
            print(f"  [Warning] Skipping unreadable audio file {p.name}: {str(e)}", file=sys.stderr)

    if len(X_list) == 0:
        raise RuntimeError("No valid audio samples could be preprocessed from the dataset split.")

    return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.int32), file_paths, speaker_list


def train_baseline(
    data_dir: Path,
    output_dir: Path,
    test_size: float = 0.2,
    random_state: int = 42,
    c_reg: float = 1.0,
    max_iter: int = 1000,
) -> Dict[str, Any]:
    """
    Main training and evaluation execution pipeline.
    """
    print("=" * 70)
    print("SIH26104 Voice Cloning Detection — Baseline ML Model Training")
    print("=" * 70)
    print(f"Dataset root directory: {data_dir.resolve()}")
    print(f"Output model directory: {output_dir.resolve()}")
    print(f"Random seed:            {random_state}")

    # 1. Dataset Integrity & Validation
    print("\n[Step 1/5] Validating dataset integrity, formats, and leakage checks...")
    validator = DatasetValidator(data_dir=data_dir, min_samples_per_class=1)
    try:
        summary: DatasetSummary = validator.validate()
        print(summary.format_report())
    except DatasetValidationError as e:
        print(
            "\n[ERROR] Dataset Validation Failed!\n"
            f"Reason: {str(e)}\n\n"
            "Action: Please place approved real and synthetic audio files under:\n"
            f"  {data_dir.resolve()}/train/real/\n"
            f"  {data_dir.resolve()}/train/synthetic/\n"
            "and verify that no duplicate files exist across splits.\n",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error during dataset validation: {str(e)}\n", file=sys.stderr)
        sys.exit(1)

    preprocessor = AudioPreprocessor()
    feature_extractor = AudioFeatureExtractor()

    # 2. Extract Training Features
    print("\n[Step 2/5] Ingesting and extracting features from training data...")
    train_dir = data_dir / "train"
    test_dir = data_dir / "test"
    try:
        X_train, y_train, train_paths, train_speakers = load_dataset_split(
            train_dir, preprocessor, feature_extractor
        )
    except Exception as e:
        print(f"\n[ERROR] Failed to load training dataset: {str(e)}\n", file=sys.stderr)
        sys.exit(1)

    # 3. Handle Validation / Test Partitioning & Speaker Leakage Prevention
    has_test_dir = test_dir.exists() and summary.splits.get("test") and summary.splits["test"].total_valid_samples > 0
    if has_test_dir:
        print("\n[Step 3/5] Ingesting dedicated test partition...")
        X_test, y_test, test_paths, test_speakers = load_dataset_split(
            test_dir, preprocessor, feature_extractor
        )
        split_strategy = "official_dedicated_directory_protocol"
        eval_protocol_desc = "Dedicated test directory partition (official protocol)"
    else:
        # Check if speaker metadata is available for speaker-disjoint partition
        non_null_speakers = [s for s in train_speakers if s is not None]
        if len(non_null_speakers) == len(train_speakers) and len(set(non_null_speakers)) >= 2:
            print(f"\n[Step 3/5] Performing speaker-independent group split (test_size={test_size}, seed={random_state})...")
            X_train, X_test, y_train, y_test, train_spks, test_spks = speaker_independent_split(
                X_train, y_train, speaker_ids=train_speakers, test_size=test_size, random_state=random_state
            )
            split_strategy = f"speaker_independent_group_split (test_size={test_size}, seed={random_state})"
            eval_protocol_desc = f"Speaker-disjoint group split ({len(train_spks)} train speakers, {len(test_spks)} test speakers)"
            print(f"  ✓ Verified: Zero speaker overlap ({len(train_spks)} train spks ∩ {len(test_spks)} test spks = ∅)")
        else:
            print(f"\n[Step 3/5] Performing stratified train/test split (test_size={test_size}, seed={random_state})...")
            from sklearn.model_selection import train_test_split
            X_train, X_test, y_train, y_test = train_test_split(
                X_train, y_train, test_size=test_size, random_state=random_state, stratify=y_train
            )
            split_strategy = f"stratified_random_split (test_size={test_size}, seed={random_state})"
            eval_protocol_desc = "Stratified random clip split (speaker identity metadata unavailable)"
            print("  [Notice] Evaluation uses random clip split. Speaker-independent evaluation cannot")
            print("  be guaranteed because speaker identity metadata is unavailable in the dataset.")

    print(f"  → Training samples: {len(X_train)} (Real: {np.sum(y_train == 0)}, Synth: {np.sum(y_train == 1)})")
    print(f"  → Testing samples:  {len(X_test)} (Real: {np.sum(y_test == 0)}, Synth: {np.sum(y_test == 1)})")
    print(f"  → Feature dimensions per sample: {feature_extractor.feature_dim}")

    # 4. Train Model
    print("\n[Step 4/5] Fitting Logistic Regression with StandardScaler...")
    clf = BaselineClassifier(C=c_reg, max_iter=max_iter, random_state=random_state)
    clf.fit(X_train, y_train)

    # 5. Evaluate Model with Research Metrics (Accuracy, Precision, Recall, F1, ROC-AUC, EER)
    print("\n[Step 5/5] Evaluating model with research metrics...")
    y_pred = clf.predict(X_test)
    y_prob = clf.predict_proba(X_test)

    eval_metadata = {
        "model_version": "baseline-v1",
        "feature_version": feature_extractor.FEATURE_VERSION,
        "evaluation_protocol": eval_protocol_desc,
        "random_seed": random_state,
    }

    metrics = compute_evaluation_metrics(y_true=y_test, y_pred=y_pred, y_prob=y_prob)
    print(format_evaluation_report(metrics, metadata=eval_metadata))

    # 6. Save Artifacts
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
            "manifest": summary.manifest_metadata,
            "train_samples_count": len(X_train),
            "test_samples_count": len(X_test),
            "split_strategy": split_strategy,
            "evaluation_protocol": eval_protocol_desc,
            "random_seed": random_state,
            "speaker_metadata_available": summary.speaker_metadata_available,
        },
        "evaluation_metrics": metrics,
        "limitations": [
            "Baseline linear model; does not learn deep hierarchical temporal representations.",
            "Only the first 3.0 seconds are analyzed per recording window.",
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
        "--random-seed",
        type=int,
        default=int(os.environ.get("DATASET_RANDOM_SEED", 42)),
        help="Random seed for reproducible dataset split and classifier initialization (default: 42).",
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
        random_state=args.random_seed,
        c_reg=args.c_reg,
        max_iter=args.max_iter,
    )


if __name__ == "__main__":
    main()
