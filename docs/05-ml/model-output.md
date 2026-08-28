# Model Outputs, Scores & Probability Interpretation: SIH26104

## 1. Output Metrics & Mathematical Definitions

The deep learning engine produces two core mathematical outputs:
1. **Countermeasure Score ($CM$)**: Logit difference indicating anti-spoofing margin.
2. **Synthetic Probability ($P_{\text{synth}}$)**: Softmax normalized probability estimate of algorithmic synthesis.

---

## 2. Mathematical Formulations

Given raw model output logits $\mathbf{z} = [z_{\text{spoof}}, z_{\text{bonafide}}]$ from the linear readout layer:

### 2.1 Countermeasure (CM) Score
$$CM = z_{\text{bonafide}} - z_{\text{spoof}}$$
- $CM \gg 0$ (e.g. $+10.0$ to $+20.0$): High confidence in authentic human speech.
- $CM \ll 0$ (e.g. $-10.0$ to $-20.0$): High confidence in synthetic / cloned speech.

### 2.2 Synthetic Probability Estimate ($P_{\text{synth}}$)
$$P_{\text{synth}} = \text{Softmax}(\mathbf{z})_0 = \frac{e^{z_{\text{spoof}}}}{e^{z_{\text{spoof}}} + e^{z_{\text{bonafide}}}} = \frac{1}{1 + e^{CM}}$$

### 2.3 Real Probability Estimate ($P_{\text{real}}$)
$$P_{\text{real}} = \text{Softmax}(\mathbf{z})_1 = \frac{e^{z_{\text{bonafide}}}}{e^{z_{\text{spoof}}} + e^{z_{\text{bonafide}}}} = \frac{1}{1 + e^{-CM}} = 1 - P_{\text{synth}}$$

---

## 3. Probability Calibration Disclaimer

> [!IMPORTANT]
> **Model Probability Estimates vs. Certified Posterior Probabilities**:  
> The displayed probabilities ($P_{\text{synth}}$ and $P_{\text{real}}$) represent **raw model softmax estimates** derived from the neural network's logit outputs. Under out-of-distribution conditions (such as uncalibrated browser microphones or extreme acoustic reverberation), raw logits can saturate near $1.0000$ or $0.0000$ due to feature shift. They should be interpreted as **relative anomaly ranking scores**, which the Decision Engine governs via conservative policy thresholds and domain reliability overrides.

---

## 4. UI Metric Projections

| Metric in API Response | Type | Range | Description |
| :--- | :--- | :--- | :--- |
| `prediction` | String | `"real"` / `"synthetic"` | Binary verdict based on $P_{\text{synth}} \ge 0.50$. |
| `confidence` | Float | `0.0 - 1.0` | Probability estimate of the predicted class: $\max(P_{\text{real}}, P_{\text{synth}})$. |
| `countermeasure_score`| Float | `-\infty` to `+\infty` | Unnormalized scalar $CM = \text{logit}_{\text{bona}} - \text{logit}_{\text{spoof}}$. |
| `synthetic_probability`| Float | `0.0 - 1.0` | Direct probability of synthesis ($P_{\text{synth}}$). |
| `raw_ml_action` | Enum | `ALLOW`/`VERIFY`/`BLOCK` | Unconstrained policy action based strictly on $P_{\text{synth}}$. |
| `operational_action` | Enum | `ALLOW`/`VERIFY`/`BLOCK` | Final operational security enforcement action after domain checks. |
