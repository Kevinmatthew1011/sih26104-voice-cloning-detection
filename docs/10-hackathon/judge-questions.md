# Hackathon Judge Q&A Guide: SIH26104

## 1. Machine Learning & Model Architecture Questions

### Q1: Why did you choose AASIST instead of a standard 2D CNN (like ResNet on Mel spectrograms)?
**Answer**:
> *"Standard 2D CNNs operate on Short-Time Fourier Transform (STFT) or Mel-filterbank spectrograms, which discard raw waveform phase information. Modern neural vocoders (like HiFi-GAN and BigVGAN) generate synthetic speech with realistic spectral envelopes but subtle phase discontinuities. AASIST uses **SincNet parametric bandpass filters** to operate directly on raw time-domain waveforms, preserving fine-grained phase cues. Furthermore, its **Heterogeneous Spectro-Temporal Graph Attention** models long-range harmonic and temporal dependencies that standard local CNN kernels miss."*

### Q2: What is SincNet and how does it differ from standard convolution?
**Answer**:
> *"Standard 1D convolutional layers learn arbitrary weight vectors that often produce redundant or noisy filter shapes. SincNet restricts filter kernels to mathematically formulated bandpass sinc functions $g[n, f_1, f_2] = 2f_2 \text{sinc}(2\pi f_2 n) - 2f_1 \text{sinc}(2\pi f_1 n)$. The network only learns two parameters per filter: the lower and upper cut-off frequencies ($f_1, f_2$). This drastically reduces parameter count, enforces physically meaningful acoustic filter shapes, and improves generalization on raw speech."*

### Q3: What is the ASVspoof dataset, and what are your certified benchmark results?
**Answer**:
> *"ASVspoof 2019 Logical Access (LA) is the global gold standard academic benchmark for voice anti-spoofing, containing 71,237 evaluation utterances across 13 unseen speech synthesis and voice conversion attack algorithms. On this official evaluation benchmark, our AASIST implementation achieves an **Equal Error Rate (EER) of 0.8047%**, an **ROC-AUC of 0.9993**, a **Bonafide False Positive Rate of 0.22%**, and a **Synthetic Attack Recall of 94.64%**."*

### Q4: How is the synthetic probability calculated, and what does the Countermeasure (CM) score mean?
**Answer**:
> *"AASIST outputs two unnormalized logits: $z_{\text{spoof}}$ and $z_{\text{bonafide}}$. The Countermeasure score is the logit differential $CM = z_{\text{bonafide}} - z_{\text{spoof}}$. A large positive score indicates high confidence in organic human speech, while a negative score indicates a synthetic attack. The synthetic probability estimate is computed via softmax: $P_{\text{synth}} = \frac{1}{1 + e^{CM}}$."*

---

## 2. Audio Processing & System Design Questions

### Q5: Why do you use Multi-Window Overlapping Inference instead of fixed truncation?
**Answer**:
> *"A critical real-world attack vector is **audio splicing**, where an attacker inserts a 500 ms cloned phrase into a 10-second genuine recording. If you truncate audio to the first 3 seconds, splices occurring later in the recording are completely missed. If you take an unweighted global average, the anomaly is diluted. VOICE-GUARD divides audio into **4.0375-second sliding windows with 75% overlap (16,150-sample hop)**, excludes non-speech silence windows, and applies **`max_v1` conservative maximum risk aggregation**, ensuring transient splices are reliably caught anywhere in the recording."*

### Q6: What happens when the audio contains silence or background noise?
**Answer**:
> *"Our pipeline extracts forensic acoustic telemetry, including Signal-to-Noise Ratio (SNR), RMS energy, and clipping ratios. In silent regions, our preprocessor avoids zero-padding discontinuities by using **deterministic wrap-tiling**. In noisy environments, the spectral graph attention branch inspects cross-band harmonic correlations rather than raw amplitude, providing resilience against ambient acoustic noise."*

---

## 3. Security, Domain Adaptation & Policy Questions

### Q7: Why does live browser microphone recording trigger an operational action of `VERIFY`?
**Answer**:
> *"Our research uncovered that consumer MEMS laptop microphones and browser WebRTC automatic gain control (AGC) introduce non-linear phase shifts that do not match studio condenser training distributions. Rather than falsely blocking genuine customers due to acoustic domain shift, our **Capture-Domain Safety Protocol** marks the domain as `unvalidated` and enforces `VERIFY` (prompting for secondary MFA) while preserving the raw biometric evidence. This demonstrates an honest, domain-aware security policy."*

### Q8: What prevents an attacker from crashing your server with a 10 GB file or DoS flood?
**Answer**:
> *"We enforce defense-in-depth: (1) A process-local token bucket rate limiter restricts clients to 10 requests per minute (burst capacity of 3). (2) Uploaded files are read in 64 KB streaming chunks; if bytes exceed 25 MB, the stream is aborted immediately with HTTP 413 without loading the rest into RAM. (3) Magic bytes are validated before decoding, and PyAV processes streams in-memory without shell subprocesses. (4) Temporary files are deterministically deleted in `finally` blocks."*

### Q9: How is forensic evidence preserved for audit compliance?
**Answer**:
> *"Every detection generates a SHA-256 cryptographic integrity hash of the raw audio bytes, stored alongside the model logits, per-window temporal breakdown, and acoustic telemetry. Compliance officers can export a structured JSON forensic audit receipt (`/api/v1/detections/{id}/report`) establishing chain-of-custody."*
