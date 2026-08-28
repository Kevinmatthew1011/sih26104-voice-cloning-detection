# Hackathon Demo Audio Fixtures: SIH26104

## 1. Verified In-Repository Test Audio Files

The following audio files are available in `backend/uploads/` for live demonstration and testing:

| Filename in `backend/uploads/` | Ground Truth | Audio Format | Expected Prediction | Expected Action |
| :--- | :--- | :--- | :--- | :--- |
| `088b2c0c-ffce-43b4-9993-5055379c374b_clean_bona.flac` | Organic Human Voice | 16 kHz FLAC | `real` ($P < 0.01$) | `ALLOW` |
| `6d7dae87-4264-4ced-930d-0e941f5f9984_clean_bona.flac` | Organic Human Voice | 16 kHz FLAC | `real` ($P < 0.01$) | `ALLOW` |
| `37a92068-d1b3-42b0-a2ac-c76d3caad80c_clean_spoof.flac` | Neural Vocoder Clone | 16 kHz FLAC | `synthetic` ($P > 0.99$) | `BLOCK` |
| `8753deb3-9a0c-4b71-a6fa-0c53af78d970_clean_spoof.flac` | Neural Vocoder Clone | 16 kHz FLAC | `synthetic` ($P > 0.99$) | `BLOCK` |
| `0ea70504-ca7a-4e77-8310-3884a59f8766_LA_T_1004644.flac` | Unknown Attack A08 | 16 kHz FLAC | `synthetic` ($P > 0.99$) | `BLOCK` |
| `61f944c1-bcaf-4b22-97aa-7cb058a4c080_mic_sample_2026-08-28-09-00-34.webm`| Physical Laptop Mic | WebM / Opus | Mic Capture Domain | `VERIFY` (MFA) |
