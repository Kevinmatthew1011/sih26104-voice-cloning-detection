# Browser scam-call demo (Dual-Layer Scam Defense)

The `/call-demo` page demonstrates a dual-layer scam defense simulation unifying **Acoustic Voice Cloning Defense** (AASIST deepfake / synthetic voice detection) and **Semantic Intent Defense** (conversational heuristics). Open it from the dashboard or desktop navigation.

Simulated calls allow inspecting caller scenarios, transcript streams, and acoustic telemetry without placing real telephone carrier calls or accessing hardware lines.

## Dual-layer architecture

The defense model operates across two independent analysis planes:

1. **Layer 1: Acoustic Defense (AASIST SincNet Telemetry)**
   - Leverages the backend AASIST model (`POST /api/v1/detections` via `api.uploadAndDetect()`).
   - Analyzes raw 16 kHz audio waveforms for synthetic voice artifacts, spectral anomalies, and vocoder signatures.
   - Evaluates synthetic probability ($P_{synth}$), confidence, risk level (`low`, `medium`, `high`), and security action (`ALLOW`, `VERIFY`, `BLOCK`).
   - *Technical Honesty Principle*: AASIST assesses acoustic synthetic voice evidence; it does NOT classify conversational fraud intent.

2. **Layer 2: Semantic Defense (Conversational Intent Heuristics)**
   - Evaluates caller message streams in `frontend/src/lib/scam-demo.ts` using `assessScamTranscript()`.
   - Identifies high-risk patterns:
     - Credential theft: requests for OTPs, passwords, PINs, or verification codes.
     - Remote access takeovers: requests to install AnyDesk, TeamViewer, or enable remote control.
     - Coercive financial demands: payment or crypto transfers combined with urgency, arrest threats, or fake "safe account" claims.
   - Categorizes risk as `unassessed`, `no_indicators`, `warning`, or `high`.
   - Heuristics are illustrative rules, not calibrated probabilities. Negation advice is recognized, but paraphrases or novel phrasing may evade detection.

3. **Unified Threat Assessment**
   - Synthesizes both layers using `computeUnifiedAssessment(acoustic, semantic)` into four actionable tiers:
     - **HIGH**: Strong acoustic synthetic voice evidence ($P_{synth} \ge 0.70$ or synthetic with high risk) **AND** strong semantic scam intent. Immediate disconnection recommended; optional 2-second automatic call termination.
     - **MEDIUM**: Asymmetric or moderate risk — e.g., synthetic voice on neutral conversation, genuine/unassessed voice with overt scam demands, or moderate payment warnings. Verification required.
     - **LOW**: Likely genuine human voice ($P_{synth} < 0.50$) **AND** benign transcript. Standard handling. Never claimed as "verified safe".
     - **UNASSESSED**: Acoustic analysis unexecuted **AND** insufficient transcript content.

## Audio handling & backend integration

- Pre-packaged demo scenarios do not include committed audio files in git repository history (audio directories like `backend/uploads/` are gitignored and empty).
- By default, scenarios initialize with acoustic status `Not analyzed`.
- Users can test live acoustic inference by attaching any local audio file (`.wav`, `.mp3`, `.flac`, `.ogg`, `.m4a`) via the **Attach Audio Clip** picker in the UI. This triggers live inference against the FastAPI backend (`POST /api/v1/detections`).

## Demo procedure

1. Select a scenario (e.g., Bank impersonation, Urgent payment demand, Remote-access scam, or Ordinary conversation).
2. Optionally attach a local audio file to test live AASIST acoustic scoring.
3. Click **Simulate Incoming Call**.
4. Decline the call, or answer to receive simulated caller messages streamed at 2.5-second intervals.
5. Review the **Unified Threat Assessment** banner, matched semantic indicators, and acoustic telemetry.
6. Inject custom caller messages via the input field to test edge cases or specific phrasing.
7. With automatic termination enabled, calls reaching `HIGH` threat will terminate after a 2-second safety warning.
8. Click **New Demo Session** after ending to archive the call summary to session history and test another scenario.

## Verification

Run the test suite in `frontend`:
```bash
node --test tests/scam-demo.test.mjs
npm run lint
npm run build
```

The test suite covers:
- Synthetic voice + scam intent $\to$ `HIGH` verdict.
- Genuine voice + scam intent $\to$ `MEDIUM` verdict.
- Synthetic voice + benign content $\to$ `MEDIUM` verdict.
- Genuine voice + benign content $\to$ `LOW` verdict.
- Unanalyzed audio + empty messages $\to$ `UNASSESSED` verdict.
- Disclaimers ensuring low threat never claims caller authenticity or "verified safe".
- Schema extraction from backend `DetectionResult` and `SecurityDecisionDTO`.
