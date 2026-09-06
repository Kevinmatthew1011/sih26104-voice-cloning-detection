#!/usr/bin/env python3
"""
Physical-Domain Acoustic Dataset & Pool Validator (Phase 5).

Validates:
1. Target quotas: 300 total samples (150 genuine microphone speech + 150 physical replay speech).
2. Human speaker diversity (target: >= 15 human speakers).
3. Provenance & Anti-Masquerading rules:
   - Genuine speech: requires human_identity; must NOT have playback_device.
   - Physical replay speech: requires playback_device, generator_name, and valid capture_type.
4. Physical file existence and SHA-256 cryptographic integrity.
5. Strict speaker and source disjointness across train/validation/test splits.
6. Audio quality parameters (silence <= 85%, duration between 1.0s and 60.0s).
"""

import sys
import os
import json
import hashlib
import argparse
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_POOL_MANIFEST = ROOT_DIR / "ml_data" / "physical_domain_pool" / "manifests" / "physical_domain_pool_manifest.json"
DEFAULT_EXPORT_MANIFEST = ROOT_DIR / "ml_data" / "physical_domain" / "manifest.json"


def calculate_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def validate_physical_manifest(manifest_path: Path, base_data_dir: Path) -> Dict[str, Any]:
    """Inspects manifest and files against all Phase 5 integrity gates."""
    if not manifest_path.exists():
        return {
            "status": "ERROR",
            "errors": [f"Manifest file not found: {manifest_path}"],
            "warnings": [],
            "metrics": {},
        }

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return {
            "status": "ERROR",
            "errors": [f"Failed to parse JSON manifest: {e}"],
            "warnings": [],
            "metrics": {},
        }

    samples: List[Dict[str, Any]] = data.get("samples", [])
    errors: List[str] = []
    warnings: List[str] = []

    total_samples = len(samples)
    real_samples = [s for s in samples if s.get("ground_truth") == "real"]
    synth_samples = [s for s in samples if s.get("ground_truth") == "synthetic"]

    # Replay samples
    physical_replays = [
        s for s in synth_samples
        if s.get("capture_type") in ["physical_replay", "physical_recapture"]
        and s.get("playback_device")
    ]

    human_speakers: Set[str] = set(s.get("human_identity") for s in real_samples if s.get("human_identity"))

    # 1. Target Quota Checks
    if total_samples < 300:
        warnings.append(f"TARGET_INCOMPLETE: Total samples {total_samples}/300.")
    if len(real_samples) < 150:
        warnings.append(f"TARGET_INCOMPLETE: Genuine microphone samples {len(real_samples)}/150.")
    if len(physical_replays) < 150:
        warnings.append(f"TARGET_INCOMPLETE: Physical replay samples {len(physical_replays)}/150.")
    if len(human_speakers) < 15:
        warnings.append(f"TARGET_INCOMPLETE: Human speakers {len(human_speakers)}/15.")

    # 2. Per-Sample Provenance & Audio Integrity
    seen_hashes: Dict[str, str] = {}
    missing_files: List[str] = []
    hash_mismatches: List[str] = []
    provenance_violations: List[str] = []
    quality_violations: List[str] = []

    splits_map: Dict[str, Set[str]] = {}
    synth_sources_map: Dict[str, Set[str]] = {}

    for s in samples:
        sid = s.get("sample_id", "UNKNOWN")
        gt = s.get("ground_truth")
        rel_path = s.get("relative_path", "")
        recorded_sha256 = s.get("capture_audio_sha256", "")
        split = s.get("split", "incoming_pool")

        # Anti-masquerading checks
        if gt == "real":
            hid = s.get("human_identity")
            if not hid:
                provenance_violations.append(f"Sample {sid}: Genuine speech missing human_identity.")
            if s.get("playback_device"):
                provenance_violations.append(f"Sample {sid}: Genuine speech cannot have playback_device.")
            if hid and split != "incoming_pool":
                splits_map.setdefault(split, set()).add(hid)
        elif gt == "synthetic":
            ctype = s.get("capture_type")
            pdev = s.get("playback_device")
            gname = s.get("generator_name")
            if ctype not in ["physical_replay", "physical_recapture"]:
                provenance_violations.append(f"Sample {sid}: Synthetic capture_type '{ctype}' must be physical_replay or physical_recapture.")
            if not pdev:
                provenance_violations.append(f"Sample {sid}: Physical replay missing playback_device.")
            if not gname:
                provenance_violations.append(f"Sample {sid}: Physical replay missing generator_name.")
            parent = s.get("parent_source_id") or s.get("source_id") or sid
            if parent and split != "incoming_pool":
                synth_sources_map.setdefault(split, set()).add(parent)
        else:
            errors.append(f"Sample {sid}: Invalid ground_truth '{gt}'. Must be 'real' or 'synthetic'.")

        # Duration & Quality telemetry
        dur = s.get("duration_seconds", 0.0)
        if dur < 1.0 or dur > 60.0:
            quality_violations.append(f"Sample {sid}: Invalid duration {dur}s (allowed: 1.0s - 60.0s).")

        telem = s.get("quality_telemetry")
        if telem:
            silence = telem.get("silence_percentage", 0.0)
            if silence > 85.0:
                quality_violations.append(f"Sample {sid}: Excessive silence {silence}% (>85.0%).")
            clipping = telem.get("clipping_percentage", 0.0)
            if clipping > 25.0:
                quality_violations.append(f"Sample {sid}: Excessive clipping {clipping}% (>25.0%).")

        # File Existence and Hash
        file_path = base_data_dir / rel_path
        if not file_path.exists():
            missing_files.append(str(file_path))
        else:
            actual_sha = calculate_sha256(file_path)
            if actual_sha in seen_hashes:
                errors.append(f"Duplicate file audio content: {file_path.name} shares SHA-256 with {seen_hashes[actual_sha]}.")
            else:
                seen_hashes[actual_sha] = sid

            if recorded_sha256 and actual_sha != recorded_sha256:
                hash_mismatches.append(f"Sample {sid}: Recorded SHA {recorded_sha256} != on-disk SHA {actual_sha}.")

    if missing_files:
        errors.append(f"Missing {len(missing_files)} physical audio files on disk (e.g. {missing_files[:2]}).")
    if hash_mismatches:
        errors.append(f"SHA-256 checksum mismatches detected in {len(hash_mismatches)} files.")
    if provenance_violations:
        errors.extend(provenance_violations)
    if quality_violations:
        errors.extend(quality_violations)

    # 3. Split Disjointness Verification
    active_splits = list(splits_map.keys())
    leakage_errors: List[str] = []
    for i in range(len(active_splits)):
        for j in range(i + 1, len(active_splits)):
            s1, s2 = active_splits[i], active_splits[j]
            overlap_spks = splits_map[s1] & splits_map[s2]
            if overlap_spks:
                leakage_errors.append(f"Speaker leakage across splits '{s1}' and '{s2}': {sorted(list(overlap_spks))}")

    active_synth_splits = list(synth_sources_map.keys())
    for i in range(len(active_synth_splits)):
        for j in range(i + 1, len(active_synth_splits)):
            s1, s2 = active_synth_splits[i], active_synth_splits[j]
            overlap_sources = synth_sources_map[s1] & synth_sources_map[s2]
            if overlap_sources:
                leakage_errors.append(f"Synthetic parent source leakage across '{s1}' and '{s2}': {sorted(list(overlap_sources))}")

    if leakage_errors:
        errors.extend(leakage_errors)

    status = "PASS" if not errors and not warnings else "WARN" if not errors else "FAIL"

    metrics = {
        "total_samples": total_samples,
        "genuine_samples": len(real_samples),
        "physical_replay_samples": len(physical_replays),
        "unique_human_speakers": len(human_speakers),
        "target_total": 300,
        "target_genuine": 150,
        "target_replay": 150,
        "target_speakers": 15,
        "active_splits": active_splits,
        "speaker_disjointness_verified": len(leakage_errors) == 0,
    }

    return {
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "metrics": metrics,
    }


def main():
    parser = argparse.ArgumentParser(description="Validate Physical Acoustic Collection & Splits (Phase 5)")
    parser.add_argument(
        "--manifest",
        type=str,
        default=None,
        help="Path to manifest file. Defaults to physical domain pool manifest if not specified.",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="Base directory for audio storage. Defaults to parent of manifest or pool directory.",
    )
    parser.add_argument(
        "--check-exported",
        action="store_true",
        help="Check exported physical domain dataset at ml_data/physical_domain/manifest.json",
    )
    args = parser.parse_args()

    if args.check_exported:
        manifest_path = DEFAULT_EXPORT_MANIFEST
        base_dir = ROOT_DIR / "ml_data" / "physical_domain"
    elif args.manifest:
        manifest_path = Path(args.manifest)
        base_dir = Path(args.data_dir) if args.data_dir else manifest_path.parent.parent
    else:
        manifest_path = DEFAULT_POOL_MANIFEST
        base_dir = ROOT_DIR / "ml_data" / "physical_domain_pool"

    print("=" * 70)
    print("VOICE-GUARD: Physical Acoustic Dataset & Staging Pool Validator")
    print("=" * 70)
    print(f"Target Manifest: {manifest_path}")
    print(f"Base Audio Dir:  {base_dir}")
    print("-" * 70)

    result = validate_physical_manifest(manifest_path, base_dir)

    metrics = result.get("metrics", {})
    if metrics:
        print(f"Total Staged Samples:     {metrics.get('total_samples', 0)} / {metrics.get('target_total', 300)}")
        print(f"Genuine Microphone:       {metrics.get('genuine_samples', 0)} / {metrics.get('target_genuine', 150)}")
        print(f"Physical Synthetic Replay:{metrics.get('physical_replay_samples', 0)} / {metrics.get('target_replay', 150)}")
        print(f"Unique Human Speakers:    {metrics.get('unique_human_speakers', 0)} / {metrics.get('target_speakers', 15)}")
        print(f"Disjointness Verified:    {metrics.get('speaker_disjointness_verified', True)}")
        print("-" * 70)

    if result["errors"]:
        print(f"[FAIL] CRITICAL INTEGRITY VIOLATIONS ({len(result['errors'])}):")
        for err in result["errors"][:15]:
            print(f"  - {err}")
        if len(result["errors"]) > 15:
            print(f"  ... and {len(result['errors']) - 15} more.")
        print("-" * 70)

    if result["warnings"]:
        print(f"[WARN] COLLECTION QUOTA / BALANCE WARNINGS ({len(result['warnings'])}):")
        for w in result["warnings"]:
            print(f"  - {w}")
        print("-" * 70)

    print(f"FINAL VALIDATION STATUS: [{result['status']}]")
    print("=" * 70)

    if result["status"] == "FAIL":
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
