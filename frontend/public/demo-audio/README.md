# Demo Audio Directory

This directory is designated for optional local audio sample fixtures used in the `/call-demo` presentation scenario runner.

## Audio Asset Policy & Technical Honesty

In accordance with project guidelines:
- No artificial or copyrighted audio fixtures are fabricated or committed into git repository history.
- Pre-packaged scenarios initialize with `sampleAudioPath: null`.
- Presenters or evaluators can place presentation-safe audio files (16 kHz mono WAV recommended, or MP3/FLAC/OGG/M4A) into this folder.

## Suggested Filenames

- `bank_impersonation.wav` (for Scenario 1: OTP / Bank Impersonation)
- `executive_fraud.wav` (for Scenario 2: Executive / Urgent Transfer Fraud)
- `remote_access.wav` (for Scenario 3: Remote Access Scam)
- `benign_control.wav` (for Scenario 4: Benign Control)

## Usage

When an audio file is placed here and linked in `sampleAudioPath` (or attached manually in the `/call-demo` UI), clicking **"Run Scenario"** will:
1. Fetch the local audio file blob.
2. Transmit it to the real backend inference endpoint (`POST /api/v1/detections`).
3. Run 16 kHz multi-window AASIST feature extraction and classification.
4. Synthesize acoustic results with conversational heuristics for unified threat evaluation.

If no audio file is provided, the scenario runner runs in semantic-only mode and displays:
`"Acoustic analysis unavailable — semantic risk only"`
