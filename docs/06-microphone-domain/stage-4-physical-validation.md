# Stage 4: Physical Transducer Challenge & Empirical Validation: SIH26104

## 1. Critical Finding: The Physical Reality Check

To verify whether the adapted head (`aasist-mic-head-v1-exp`) truly generalized to real physical hardware, a dedicated **Physical Challenge Set** ($N=25$) was evaluated:
- **Verified Physical Genuine Captures**: 14 samples (Laptop array, Smartphone WhatsApp PTT, Chrome/Firefox/WebAudio).
- **Verified Physical Re-captured Spoofs**: **0 samples** (No physical re-captures were present in this challenge set).
- **Direct Synthetic Attacks**: 11 samples (Unprocessed neural vocoder synthesis files from ASVspoof 2019 LA A07–A08).
- **Total Challenge Samples**: 25 samples.

---

## 2. Same-Device Live Physical Microphone Test

We evaluated the exact same physical laptop microphone array (Dell XPS Laptop Array, Google Chrome 128, WebM/Opus) that previously triggered false blocks on genuine speech:

| Physical Recording (Genuine Human Speech) | Baseline `aasist-v1` (Production) | Adapted Head (`aasist-mic-head-v1-exp`) |
| :--- | :--- | :--- |
| `mic_sample_2026-08-28-09-00-34.webm` | $CM = -22.36 \mid P = 1.0000 \to \mathbf{BLOCK}$ | $CM = -29.33 \mid P = 1.0000 \to \mathbf{BLOCK}$ |
| `mic_sample_2026-08-28-02-53-03.webm` | $CM = -15.47 \mid P = 1.0000 \to \mathbf{BLOCK}$ | $CM = -19.79 \mid P = 1.0000 \to \mathbf{BLOCK}$ |
| `mic_sample_2026-08-28-02-52-47.webm` | $CM = -16.80 \mid P = 1.0000 \to \mathbf{BLOCK}$ | $CM = -21.84 \mid P = 1.0000 \to \mathbf{BLOCK}$ |
| `mic_sample_2026-08-27-17-54-10.webm` | $CM = -16.45 \mid P = 1.0000 \to \mathbf{BLOCK}$ | $CM = -21.04 \mid P = 1.0000 \to \mathbf{BLOCK}$ |
| `mic_sample_2026-08-27-17-52-58.webm` | $CM = -18.00 \mid P = 1.0000 \to \mathbf{BLOCK}$ | $CM = -24.66 \mid P = 1.0000 \to \mathbf{BLOCK}$ |

> [!CAUTION]
> **Key Scientific Discovery**:  
> **Classifier-head adaptation alone (`out_layer` fine-tuning) DOES NOT fix the live physical microphone failure.**  
> Because the frozen SincNet front-end extracts 160-D embeddings for live microphone audio that are already deeply collapsed into the spoof quadrant ($CM \approx -20$), linear probing cannot recover genuine speech without distorting clean anti-spoofing boundaries.

---

## 3. Physical Challenge Performance Comparison

| Evaluation Metric | Baseline `aasist-v1` | Adapted Head (`aasist-mic-head-v1-exp`) | Promotion Gate | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Accuracy** | 44.00% | 44.00% | $> 90.00\%$ | **FAILED** |
| **Equal Error Rate (EER)** | 30.52% | 34.09% | $\le 3.00\%$ | **FAILED** |
| **ROC-AUC** | 0.4675 | 0.6136 | $\ge 0.9000$ | **FAILED** |
| **Genuine False BLOCK Rate ($P \ge 0.70$)** | **100.00%** | **100.00%** | $\le \mathbf{5.00\%}$ | **FAILED** |
| **Spoof Recall (TPR)** | 100.00% | 100.00% | $\ge 90.00\%$ | **PASSED** |

---

## 4. Engineering Decision: Promotion Blocked

1. **Model Promotion Blocked**: `aasist-mic-head-v1-exp` was **NOT promoted to production** and remains an offline research artifact in `experiments/mic_head_v1/`.
2. **Production Safety Guaranteed**: The production Decision Engine continues to enforce `capture_domain_reliability = "unvalidated"` and an operational action of `VERIFY` for browser microphone input.
