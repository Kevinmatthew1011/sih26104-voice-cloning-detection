import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional, Any
import numpy as np
from sklearn.model_selection import GroupShuffleSplit

# Supported audio file formats
SUPPORTED_AUDIO_EXTENSIONS: Set[str] = {
    ".wav",
    ".mp3",
    ".ogg",
    ".flac",
    ".m4a",
    ".aac",
    ".webm",
}


class DatasetValidationError(ValueError):
    """Raised when a dataset fails integrity, structure, or leakage validation checks."""
    pass


@dataclass
class SplitStats:
    split_name: str
    real_files: List[Path] = field(default_factory=list)
    synthetic_files: List[Path] = field(default_factory=list)
    unsupported_files: List[Path] = field(default_factory=list)
    corrupted_files: List[Path] = field(default_factory=list)
    file_hashes: Dict[str, Path] = field(default_factory=dict)
    speaker_ids: Set[str] = field(default_factory=set)
    file_to_speaker: Dict[Path, str] = field(default_factory=dict)

    @property
    def total_valid_samples(self) -> int:
        return len(self.real_files) + len(self.synthetic_files)

    @property
    def real_count(self) -> int:
        return len(self.real_files)

    @property
    def synthetic_count(self) -> int:
        return len(self.synthetic_files)

    @property
    def speaker_count(self) -> int:
        return len(self.speaker_ids)


@dataclass
class DatasetSummary:
    dataset_root: Path
    splits: Dict[str, SplitStats]
    speaker_metadata_available: bool
    speaker_leakage_detected: bool
    cross_split_duplicates: List[Tuple[str, str, str, Path, Path]]  # (split1, split2, hash, path1, path2)
    speaker_overlaps: List[Tuple[str, str, str]]  # (split1, split2, speaker_id)
    manifest_metadata: Optional[Dict[str, Any]] = None

    @property
    def total_samples(self) -> int:
        return sum(s.total_valid_samples for s in self.splits.values())

    def format_report(self) -> str:
        lines = [
            "=" * 60,
            "DATASET INTEGRITY & DISTRIBUTION SUMMARY",
            "=" * 60,
            f"Dataset Root: {self.dataset_root.resolve()}",
        ]

        if self.manifest_metadata:
            name = self.manifest_metadata.get("dataset_name", "N/A")
            version = self.manifest_metadata.get("dataset_version", "N/A")
            license_str = self.manifest_metadata.get("license", "N/A")
            lines.append(f"Dataset Manifest: {name} (Version: {version}, License: {license_str})")

        lines.append("-" * 60)
        lines.append(f"{'Split':<12} | {'Real':<8} | {'Synthetic':<10} | {'Total':<8} | {'Speakers':<8}")
        lines.append("-" * 60)

        for split_name in ["train", "validation", "test"]:
            if split_name in self.splits:
                s = self.splits[split_name]
                spk_str = str(s.speaker_count) if self.speaker_metadata_available else "N/A"
                lines.append(
                    f"{split_name:<12} | {s.real_count:<8} | {s.synthetic_count:<10} | {s.total_valid_samples:<8} | {spk_str:<8}"
                )

        lines.append("-" * 60)

        if self.speaker_metadata_available:
            lines.append("Speaker Leakage Verification:")
            if self.speaker_overlaps:
                lines.append(f"  ❌ CRITICAL: {len(self.speaker_overlaps)} overlapping speaker IDs found between splits!")
                for s1, s2, spk in self.speaker_overlaps[:5]:
                    lines.append(f"     - Speaker '{spk}' present in both '{s1}' and '{s2}'")
            else:
                lines.append("  ✓ Verified: Zero speaker overlap (Train ∩ Val = ∅, Train ∩ Test = ∅, Val ∩ Test = ∅)")
        else:
            lines.append(
                "Speaker Metadata Notice:\n"
                "  [Notice] Speaker identity metadata is unavailable.\n"
                "  Speaker-independent evaluation cannot be guaranteed because speaker identity metadata is unavailable."
            )

        if self.cross_split_duplicates:
            lines.append(f"Cross-Split Data Leakage:\n  ❌ CRITICAL: {len(self.cross_split_duplicates)} duplicate files detected across splits!")

        lines.append("=" * 60)
        return "\n".join(lines)


def calculate_file_hash(filepath: Path) -> str:
    """Compute SHA-256 hash of a file for exact duplicate and leakage detection."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


def extract_speaker_id_from_path(filepath: Path, speaker_mapping: Optional[Dict[str, str]] = None) -> Optional[str]:
    """
    Attempts to extract speaker ID from optional mapping or filename convention.
    Conventions supported:
    - mapping dict: filepath.name -> speaker_id
    - prefix convention: 'spk001_utt01.wav' or 'speaker123-session.wav' or 'id10001_real_001.wav'
    """
    if speaker_mapping:
        if filepath.name in speaker_mapping:
            return speaker_mapping[filepath.name]
        if str(filepath) in speaker_mapping:
            return speaker_mapping[str(filepath)]

    stem = filepath.stem
    # Standard voice antispoof dataset naming conventions (e.g. spk01_real.wav or ID001_synthetic.wav)
    if "_" in stem:
        prefix = stem.split("_")[0]
        if prefix.lower().startswith(("spk", "id", "speaker", "client", "user")) or prefix.isdigit():
            return prefix
    elif "-" in stem:
        prefix = stem.split("-")[0]
        if prefix.lower().startswith(("spk", "id", "speaker", "client", "user")):
            return prefix

    return None


class DatasetValidator:
    """
    Reusable Research-Grade Dataset Validation and Integrity Enforcement Module.
    
    Verifies:
    1. Directory structure and required class folders
    2. Audio format compatibility
    3. Corrupted / 0-byte audio file detection
    4. Exact file duplicate detection within splits
    5. Cross-split data leakage detection (SHA-256 hash collisions across train/val/test)
    6. Speaker ID metadata discovery and speaker overlap / leakage detection
    """

    def __init__(
        self,
        data_dir: Path,
        min_samples_per_class: int = 1,
        strict_speaker_separation: bool = True,
    ):
        self.data_dir = Path(data_dir)
        self.min_samples_per_class = min_samples_per_class
        self.strict_speaker_separation = strict_speaker_separation

    def load_manifest(self) -> Optional[Dict[str, Any]]:
        manifest_path = self.data_dir / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def validate_split(
        self,
        split_name: str,
        split_dir: Path,
        speaker_mapping: Optional[Dict[str, str]] = None,
    ) -> SplitStats:
        stats = SplitStats(split_name=split_name)
        if not split_dir.exists() or not split_dir.is_dir():
            return stats

        real_dir = split_dir / "real"
        synth_dir = split_dir / "synthetic"

        if not real_dir.exists():
            raise DatasetValidationError(
                f"Missing required class folder: '{real_dir}' does not exist."
            )
        if not synth_dir.exists():
            raise DatasetValidationError(
                f"Missing required class folder: '{synth_dir}' does not exist."
            )

        # Inspect all files in split
        for class_name, folder in [("real", real_dir), ("synthetic", synth_dir)]:
            for file_path in sorted(folder.rglob("*")):
                if not file_path.is_file() or file_path.name.startswith(".") or file_path.name == ".gitkeep":
                    continue

                # Format check
                ext = file_path.suffix.lower()
                if ext not in SUPPORTED_AUDIO_EXTENSIONS:
                    stats.unsupported_files.append(file_path)
                    continue

                # Size & corruption check
                try:
                    if file_path.stat().st_size == 0:
                        stats.corrupted_files.append(file_path)
                        continue
                except OSError:
                    stats.corrupted_files.append(file_path)
                    continue

                # Duplicate / Hash check
                try:
                    file_hash = calculate_file_hash(file_path)
                    if file_hash in stats.file_hashes:
                        # Intra-split duplicate (same audio content in same split)
                        stats.corrupted_files.append(file_path)
                    else:
                        stats.file_hashes[file_hash] = file_path
                except Exception:
                    stats.corrupted_files.append(file_path)
                    continue

                # Speaker extraction
                spk = extract_speaker_id_from_path(file_path, speaker_mapping)
                if spk:
                    stats.speaker_ids.add(spk)
                    stats.file_to_speaker[file_path] = spk

                if class_name == "real":
                    stats.real_files.append(file_path)
                else:
                    stats.synthetic_files.append(file_path)

        return stats

    def validate(self, speaker_mapping: Optional[Dict[str, str]] = None) -> DatasetSummary:
        """
        Executes full dataset validation across train, validation, and test splits.
        Raises DatasetValidationError if any critical integrity or leakage flaw is discovered.
        """
        if not self.data_dir.exists() or not self.data_dir.is_dir():
            raise DatasetValidationError(
                f"Dataset root directory does not exist: '{self.data_dir.resolve()}'"
            )

        train_dir = self.data_dir / "train"
        val_dir = self.data_dir / "validation"
        test_dir = self.data_dir / "test"

        if not train_dir.exists():
            raise DatasetValidationError(
                f"Training split directory '{train_dir}' is required but was not found."
            )

        manifest = self.load_manifest()

        # Validate splits
        splits: Dict[str, SplitStats] = {}
        for s_name, s_dir in [("train", train_dir), ("validation", val_dir), ("test", test_dir)]:
            if s_dir.exists():
                splits[s_name] = self.validate_split(s_name, s_dir, speaker_mapping)

        train_stats = splits["train"]

        # Minimum files check on train split
        if train_stats.real_count < self.min_samples_per_class:
            raise DatasetValidationError(
                f"Training class 'real' in '{train_dir / 'real'}' contains {train_stats.real_count} audio files, "
                f"which is less than the required minimum of {self.min_samples_per_class}."
            )
        if train_stats.synthetic_count < self.min_samples_per_class:
            raise DatasetValidationError(
                f"Training class 'synthetic' in '{train_dir / 'synthetic'}' contains {train_stats.synthetic_count} audio files, "
                f"which is less than the required minimum of {self.min_samples_per_class}."
            )

        # 1. Cross-Split Duplicate / Leakage Checks
        cross_split_duplicates: List[Tuple[str, str, str, Path, Path]] = []
        split_names = list(splits.keys())
        for i in range(len(split_names)):
            for j in range(i + 1, len(split_names)):
                s1_name, s2_name = split_names[i], split_names[j]
                s1, s2 = splits[s1_name], splits[s2_name]
                common_hashes = set(s1.file_hashes.keys()).intersection(set(s2.file_hashes.keys()))
                for h in common_hashes:
                    cross_split_duplicates.append(
                        (s1_name, s2_name, h, s1.file_hashes[h], s2.file_hashes[h])
                    )

        if cross_split_duplicates:
            dup = cross_split_duplicates[0]
            raise DatasetValidationError(
                f"Cross-split data leakage detected! File '{dup[3].name}' in '{dup[0]}' "
                f"is identical (SHA-256: {dup[2][:12]}...) to '{dup[4].name}' in '{dup[1]}'. "
                "Evaluation integrity requires strictly disjoint splits."
            )

        # 2. Speaker Leakage Checks
        speaker_overlaps: List[Tuple[str, str, str]] = []
        has_speaker_metadata = any(s.speaker_count > 0 for s in splits.values())

        if has_speaker_metadata:
            for i in range(len(split_names)):
                for j in range(i + 1, len(split_names)):
                    s1_name, s2_name = split_names[i], split_names[j]
                    common_speakers = splits[s1_name].speaker_ids.intersection(splits[s2_name].speaker_ids)
                    for spk in common_speakers:
                        speaker_overlaps.append((s1_name, s2_name, spk))

            if speaker_overlaps and self.strict_speaker_separation:
                first_ov = speaker_overlaps[0]
                raise DatasetValidationError(
                    f"Speaker leakage detected! Speaker '{first_ov[2]}' is present in both '{first_ov[0]}' "
                    f"and '{first_ov[1]}' splits. Clips from the same speaker must never overlap between train and test."
                )

        summary = DatasetSummary(
            dataset_root=self.data_dir,
            splits=splits,
            speaker_metadata_available=has_speaker_metadata,
            speaker_leakage_detected=len(speaker_overlaps) > 0,
            cross_split_duplicates=cross_split_duplicates,
            speaker_overlaps=speaker_overlaps,
            manifest_metadata=manifest,
        )

        return summary


def speaker_independent_split(
    X: np.ndarray,
    y: np.ndarray,
    speaker_ids: List[str],
    test_size: float = 0.2,
    random_state: int = 42,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, List[str], List[str]]:
    """
    Performs speaker-disjoint partition so that no speaker in the training split
    appears in the evaluation test split.
    
    Returns:
        (X_train, X_test, y_train, y_test, train_speakers, test_speakers)
    """
    if len(X) != len(speaker_ids) or len(y) != len(speaker_ids):
        raise ValueError("X, y, and speaker_ids must have identical lengths.")

    unique_speakers = np.unique(speaker_ids)
    if len(unique_speakers) < 2:
        raise ValueError("Speaker-independent split requires at least 2 distinct speakers.")

    gss = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=random_state)
    train_idx, test_idx = next(gss.split(X, y, groups=speaker_ids))

    train_spks = sorted(list(set(speaker_ids[i] for i in train_idx)))
    test_spks = sorted(list(set(speaker_ids[i] for i in test_idx)))

    # Verify disjointness
    overlap = set(train_spks).intersection(set(test_spks))
    if overlap:
        raise RuntimeError(f"Speaker-independent split failed; overlapping speakers: {overlap}")

    return X[train_idx], X[test_idx], y[train_idx], y[test_idx], train_spks, test_spks
