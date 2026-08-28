# Stage 1: Microphone-Domain Audit & Evaluation Design: SIH26104

## 1. Stage 1 Overview & Goals

**Objective**: Audit the in-repository audio collection, characterize the severe performance degradation of frozen AASIST on browser microphone audio, and design a multi-condition evaluation framework without modifying production weights or decision thresholds.

---

## 2. Audio Audit & Initial Baseline Evaluation

The audit cataloged 25 real-world microphone captures:
- **Verified Physical Genuine Human Utterances**: 14 (Dell XPS laptop array, Chrome/Firefox/WebAudio, Smartphone WhatsApp PTT).
- **Direct Synthetic Voice Clones**: 11 (ElevenLabs, XTTS-v2, ASVspoof neural vocoders).

### Evaluation of Frozen Production AASIST (`AASIST.pth`):
- **Accuracy**: $44.00\%$
- **Equal Error Rate (EER)**: **$30.52\%$** (vs. $0.80\%$ on ASVspoof benchmark)
- **ROC-AUC**: **$0.4675$** (equivalent to random guessing or inverted ranking)
- **Genuine False Positive Rate**: **$100.00\%$** ($14 / 14$ genuine files scored $P_{\text{synth}} \approx 1.0$)
- **Spoof Recall (TPR)**: $100.00\%$

---

## 3. Multi-Condition Dataset Architecture Specification

Stage 1 established the formal metadata schema required for microphone domain adaptation:

| Metadata Field | Type | Description |
| :--- | :--- | :--- |
| `speaker_id` | String | Unique speaker identifier (e.g. `SPK_001`–`SPK_030`). |
| `label` | Integer | Binary ground-truth: `0` (bonafide) or `1` (synthetic). |
| `capture_device` | String | Hardware category: Laptop Array, Smartphone, USB Headset. |
| `browser` | String | Browser agent: Chrome 128, Firefox 129, Safari 17, WebAudio. |
| `native_sample_rate` | Integer | Native hardware sample rate (e.g. 48,000 Hz, 44,100 Hz). |
| `codec_container` | String | Container and encoding: `webm/opus`, `ogg/opus`, `wav/pcm`. |
| `environment` | String | Acoustic room profile: Quiet Office, Living Room, Reverberant Hall. |
| `webrtc_processing` | Object | Enabled DSP flags (`echoCancellation`, `noiseSuppression`, `autoGainControl`). |
| `provenance_class` | String | Category: `physical_genuine`, `physical_recaptured`, `direct_synthetic`, `simulated_transformed`. |
