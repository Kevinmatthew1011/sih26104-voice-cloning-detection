import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional, Any, Union
import numpy as np
from sklearn.model_selection import GroupShuffleSplit
from app.ml.preprocessing import AudioPreprocessor
from app.ml.features import AudioFeatureExtractor

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
class ASVspoofSample:
    speaker_id: str
    audio_id: str
    attack_id: str
    original_label: str
    label: str
    class_id: int
    audio_path: Path


@dataclass
class ASVspoofFeatures:
    """
    Container for extracted 88-D ASVspoof feature matrices and sample metadata.
    """
    X: np.ndarray             # shape (N, 88), float32
    y: np.ndarray             # shape (N,), int32
    speaker_ids: List[str]    # length N
    audio_ids: List[str]      # length N
    attack_ids: List[str]     # length N

    def __post_init__(self):
        self.X = np.asarray(self.X, dtype=np.float32)
        self.y = np.asarray(self.y, dtype=np.int32)
        
        if self.X.ndim != 2 or self.X.shape[1] != 88:
            raise DatasetValidationError(
                f"Feature matrix X must have shape (N, 88), got {self.X.shape}"
            )
        if self.y.ndim != 1 or len(self.y) != self.X.shape[0]:
            raise DatasetValidationError(
                f"Label vector y length ({len(self.y)}) must match X sample count ({self.X.shape[0]})"
            )
        if len(self.y) > 0 and not np.all(np.isin(self.y, [0, 1])):
            raise DatasetValidationError(
                "Label vector y must only contain class IDs 0 (real) or 1 (synthetic)"
            )
        if not np.isfinite(self.X).all():
            raise DatasetValidationError(
                "Feature matrix X contains non-finite values (NaN or Inf)"
            )
        if (
            len(self.speaker_ids) != len(self.y)
            or len(self.audio_ids) != len(self.y)
            or len(self.attack_ids) != len(self.y)
        ):
            raise DatasetValidationError(
                f"Metadata lengths mismatch: y={len(self.y)}, speaker_ids={len(self.speaker_ids)}, "
                f"audio_ids={len(self.audio_ids)}, attack_ids={len(self.attack_ids)}"
            )

    @property
    def num_samples(self) -> int:
        return len(self.y)

    def __len__(self) -> int:
        return len(self.y)

    def save_cache(self, cache_path: Union[Path, str]) -> Path:
        """Save features and metadata to a compressed .npz file."""
        return save_asvspoof_feature_cache(cache_path, self)

    @classmethod
    def load_cache(cls, cache_path: Union[Path, str]) -> "ASVspoofFeatures":
        """Load features and metadata from a compressed .npz file."""
        return load_asvspoof_feature_cache(cache_path)


def extract_asvspoof_features(
    samples: List[ASVspoofSample],
    preprocessor: Optional[AudioPreprocessor] = None,
    extractor: Optional[AudioFeatureExtractor] = None,
) -> ASVspoofFeatures:
    """
    Extracts 88-D feature vectors from a list of ASVspoofSample objects.
    """
    p = preprocessor or AudioPreprocessor()
    e = extractor or AudioFeatureExtractor()

    if not samples:
        return ASVspoofFeatures(
            X=np.empty((0, 88), dtype=np.float32),
            y=np.empty((0,), dtype=np.int32),
            speaker_ids=[],
            audio_ids=[],
            attack_ids=[],
        )

    features_list: List[np.ndarray] = []
    labels_list: List[int] = []
    speaker_ids: List[str] = []
    audio_ids: List[str] = []
    attack_ids: List[str] = []

    for s in samples:
        y_audio = p.process(s.audio_path)
        feat = e.extract_features(y_audio)
        if feat.shape != (88,):
            raise DatasetValidationError(
                f"Feature extractor returned shape {feat.shape}, expected (88,) for '{s.audio_path}'"
            )
        if not np.isfinite(feat).all():
            raise DatasetValidationError(
                f"Extracted feature vector for '{s.audio_path}' contains non-finite values"
            )
        features_list.append(feat)
        labels_list.append(s.class_id)
        speaker_ids.append(s.speaker_id)
        audio_ids.append(s.audio_id)
        attack_ids.append(s.attack_id)

    X = np.array(features_list, dtype=np.float32)
    y = np.array(labels_list, dtype=np.int32)

    return ASVspoofFeatures(
        X=X,
        y=y,
        speaker_ids=speaker_ids,
        audio_ids=audio_ids,
        attack_ids=attack_ids,
    )


def save_asvspoof_feature_cache(
    cache_path: Union[Path, str],
    features: ASVspoofFeatures,
) -> Path:
    """
    Saves ASVspoofFeatures into a compressed .npz archive.
    """
    out_path = Path(cache_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    np.savez_compressed(
        out_path,
        X=features.X,
        y=features.y,
        speaker_ids=np.array(features.speaker_ids, dtype=object),
        audio_ids=np.array(features.audio_ids, dtype=object),
        attack_ids=np.array(features.attack_ids, dtype=object),
    )
    return out_path


def load_asvspoof_feature_cache(
    cache_path: Union[Path, str],
) -> ASVspoofFeatures:
    """
    Loads ASVspoofFeatures from a compressed .npz archive.
    """
    path = Path(cache_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Feature cache file not found: '{path.resolve()}'")

    with np.load(path, allow_pickle=True) as data:
        required_keys = {"X", "y", "speaker_ids", "audio_ids", "attack_ids"}
        missing_keys = required_keys - set(data.files)
        if missing_keys:
            raise DatasetValidationError(
                f"Corrupted cache file '{path}': missing keys {missing_keys}"
            )

        X = np.asarray(data["X"], dtype=np.float32)
        y = np.asarray(data["y"], dtype=np.int32)
        speaker_ids = [str(s) for s in data["speaker_ids"]]
        audio_ids = [str(a) for a in data["audio_ids"]]
        attack_ids = [str(att) for att in data["attack_ids"]]

    return ASVspoofFeatures(
        X=X,
        y=y,
        speaker_ids=speaker_ids,
        audio_ids=audio_ids,
        attack_ids=attack_ids,
    )


def load_or_extract_asvspoof_features(
    samples: List[ASVspoofSample],
    cache_path: Optional[Union[Path, str]] = None,
    force_recompute: bool = False,
    preprocessor: Optional[AudioPreprocessor] = None,
    extractor: Optional[AudioFeatureExtractor] = None,
) -> ASVspoofFeatures:
    """
    Loads features from local .npz cache if available, or extracts them from samples
    and saves to cache.
    """
    if cache_path and not force_recompute:
        p = Path(cache_path)
        if p.exists() and p.is_file():
            return load_asvspoof_feature_cache(p)

    features = extract_asvspoof_features(
        samples=samples,
        preprocessor=preprocessor,
        extractor=extractor,
    )

    if cache_path:
        save_asvspoof_feature_cache(cache_path, features)

    return features


def load_asvspoof_protocol(
    protocol_path: Union[Path, str],
    audio_dir: Union[Path, str],
) -> List[ASVspoofSample]:
    """
    Parses and validates an official ASVspoof 2019 Logical Access protocol file.
    
    Protocol format (5 whitespace-separated columns):
        speaker_id audio_id environment attack_id label
    
    Mapping:
        bonafide -> real -> class 0
        spoof -> synthetic -> class 1
        
    Audio path convention:
        audio_dir / f"{audio_id}.flac"
        
    Raises:
        DatasetValidationError: If protocol file or audio directory is missing,
                                if any row is malformed, has an unknown label,
                                or references a nonexistent FLAC file.
    """
    protocol_file = Path(protocol_path)
    audio_directory = Path(audio_dir)

    if not protocol_file.exists() or not protocol_file.is_file():
        raise DatasetValidationError(
            f"ASVspoof protocol file does not exist or is not a file: '{protocol_file.resolve()}'"
        )

    if not audio_directory.exists() or not audio_directory.is_dir():
        raise DatasetValidationError(
            f"ASVspoof audio directory does not exist or is not a directory: '{audio_directory.resolve()}'"
        )

    samples: List[ASVspoofSample] = []
    with open(protocol_file, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line_str = line.strip()
            if not line_str:
                continue

            parts = line_str.split()
            if len(parts) != 5:
                raise DatasetValidationError(
                    f"Malformed protocol row at line {line_num} in '{protocol_file}': "
                    f"expected exactly 5 columns, got {len(parts)} ({line_str!r})"
                )

            speaker_id, audio_id, _env, attack_id, orig_label = parts

            if orig_label == "bonafide":
                label = "real"
                class_id = 0
            elif orig_label == "spoof":
                label = "synthetic"
                class_id = 1
            else:
                raise DatasetValidationError(
                    f"Unknown label '{orig_label}' at line {line_num} in '{protocol_file}'. "
                    "Expected 'bonafide' or 'spoof'."
                )

            audio_path = audio_directory / f"{audio_id}.flac"
            if not audio_path.exists() or not audio_path.is_file():
                raise DatasetValidationError(
                    f"Referenced audio file does not exist: '{audio_path}' (line {line_num})"
                )

            samples.append(
                ASVspoofSample(
                    speaker_id=speaker_id,
                    audio_id=audio_id,
                    attack_id=attack_id,
                    original_label=orig_label,
                    label=label,
                    class_id=class_id,
                    audio_path=audio_path,
                )
            )

    return samples


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
