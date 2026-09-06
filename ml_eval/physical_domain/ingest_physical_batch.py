#!/usr/bin/env python3
"""
Batch Physical Audio Ingestion Utility (Phase 6).

Allows batch or single-file ingestion of physical acoustic recordings (genuine or replay)
directly into the physical domain pool with full validation:
- Anti-masquerading enforcement
- Audio quality gates (duration, silence <= 85%, clipping <= 25%)
- SHA-256 cryptographic deduplication
- Complete provenance logging
"""

import sys
import csv
import argparse
from pathlib import Path
from typing import Dict, Any, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "backend"))

from app.services.physical_collection_service import PhysicalCollectionService


def ingest_single_file(
    service: PhysicalCollectionService,
    audio_path: Path,
    ground_truth: str,
    human_identity: Optional[str] = None,
    capture_device_category: str = "laptop",
    capture_device_name: Optional[str] = None,
    distance_category: str = "medium_30cm",
    playback_device: Optional[str] = None,
    playback_device_category: Optional[str] = None,
    generator_name: Optional[str] = None,
    generator_version: Optional[str] = None,
    attack_id: Optional[str] = None,
    parent_source_id: Optional[str] = None,
    room_environment: str = "quiet_office",
    prompt_id: Optional[str] = None,
    session_id: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    capture_type = "physical_recapture" if ground_truth == "synthetic" else "physical_microphone"

    return service.ingest_recording(
        audio_bytes=audio_bytes,
        file_extension=audio_path.suffix,
        ground_truth=ground_truth,
        human_identity=human_identity,
        source_speaker_identity=human_identity if ground_truth == "synthetic" else None,
        source_id=audio_path.name,
        parent_source_id=parent_source_id,
        generator_name=generator_name,
        generator_version=generator_version,
        attack_id=attack_id,
        capture_type=capture_type,
        capture_device_category=capture_device_category,
        capture_device_name=capture_device_name or "External Acoustic Transducer",
        playback_device=playback_device,
        playback_device_category=playback_device_category,
        distance_category=distance_category,
        room_environment=room_environment,
        capture_session_id=session_id,
        prompt_id=prompt_id,
        notes=notes,
    )


def ingest_csv_batch(service: PhysicalCollectionService, csv_path: Path, audio_dir: Optional[Path] = None):
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV manifest not found: {csv_path}")

    base_audio_dir = audio_dir if audio_dir else csv_path.parent
    success_count = 0
    failure_count = 0
    failures = []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row_idx, row in enumerate(reader, start=1):
            raw_path = row.get("file_path") or row.get("filename")
            if not raw_path:
                print(f"[Row {row_idx}] ERROR: Missing file_path column.")
                failure_count += 1
                continue

            file_path = Path(raw_path)
            if not file_path.is_absolute():
                file_path = base_audio_dir / file_path

            gt = row.get("ground_truth", "real").strip().lower()

            try:
                result = ingest_single_file(
                    service=service,
                    audio_path=file_path,
                    ground_truth=gt,
                    human_identity=row.get("human_identity") or row.get("speaker_id"),
                    capture_device_category=row.get("capture_device_category", "laptop"),
                    capture_device_name=row.get("capture_device_name"),
                    distance_category=row.get("distance_category", "medium_30cm"),
                    playback_device=row.get("playback_device"),
                    playback_device_category=row.get("playback_device_category"),
                    generator_name=row.get("generator_name"),
                    generator_version=row.get("generator_version"),
                    attack_id=row.get("attack_id"),
                    parent_source_id=row.get("parent_source_id"),
                    room_environment=row.get("room_environment", "quiet_office"),
                    prompt_id=row.get("prompt_id"),
                    session_id=row.get("session_id"),
                    notes=row.get("notes"),
                )
                print(f"[Row {row_idx}] OK: Ingested {result['sample_id']} ({result['ground_truth']}, {result['duration_seconds']}s)")
                success_count += 1
            except Exception as e:
                print(f"[Row {row_idx}] REJECTED ({file_path.name}): {e}")
                failure_count += 1
                failures.append((file_path.name, str(e)))

    print("-" * 60)
    print(f"Batch ingestion complete: {success_count} succeeded, {failure_count} rejected.")


def main():
    parser = argparse.ArgumentParser(description="Ingest physical recordings into VOICE-GUARD staging pool")
    parser.add_argument("--csv", type=str, help="Path to CSV file with metadata rows")
    parser.add_argument("--audio-dir", type=str, help="Base directory for relative audio paths in CSV")
    parser.add_argument("--file", type=str, help="Single audio file to ingest")
    parser.add_argument("--ground-truth", choices=["real", "synthetic"], help="Ground truth class")
    parser.add_argument("--speaker", type=str, help="Pseudonymous human speaker ID (e.g. HUMAN_SPK_01)")
    parser.add_argument("--distance", default="medium_30cm", choices=["close_10cm", "medium_30cm", "far_1m"])
    parser.add_argument("--capture-device-cat", default="laptop", choices=["laptop", "mobile", "external_microphone", "other"])
    parser.add_argument("--capture-device-name", type=str)
    parser.add_argument("--playback-device", type=str, help="Playback transducer device for replay")
    parser.add_argument("--playback-device-cat", choices=["smartphone_loudspeaker", "laptop_speakers", "bluetooth_speaker", "desktop_monitors", "other_transducer"])
    parser.add_argument("--generator", type=str, help="Generator name (e.g. ElevenLabs)")
    parser.add_argument("--generator-version", type=str)
    parser.add_argument("--attack-id", type=str)
    parser.add_argument("--parent-source-id", type=str)
    parser.add_argument("--environment", default="quiet_office")
    parser.add_argument("--prompt-id", type=str)
    parser.add_argument("--session-id", type=str)

    args = parser.parse_args()
    service = PhysicalCollectionService()

    if args.csv:
        ingest_csv_batch(service, Path(args.csv), Path(args.audio_dir) if args.audio_dir else None)
    elif args.file:
        if not args.ground_truth:
            print("Error: --ground-truth (real/synthetic) required for single file ingestion.")
            sys.exit(1)
        try:
            res = ingest_single_file(
                service=service,
                audio_path=Path(args.file),
                ground_truth=args.ground_truth,
                human_identity=args.speaker,
                capture_device_category=args.capture_device_cat,
                capture_device_name=args.capture_device_name,
                distance_category=args.distance,
                playback_device=args.playback_device,
                playback_device_category=args.playback_device_cat,
                generator_name=args.generator,
                generator_version=args.generator_version,
                attack_id=args.attack_id,
                parent_source_id=args.parent_source_id,
                room_environment=args.environment,
                prompt_id=args.prompt_id,
                session_id=args.session_id,
            )
            print(f"Success: Ingested {res['sample_id']} ({res['ground_truth']}, {res['duration_seconds']}s)")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
