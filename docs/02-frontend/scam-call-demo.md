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
     - **UNASSESSED**: Acoustic analysis unexecuted / unavailable **AND** insufficient or nominal transcript content.

## Built-in presentation scenarios

Four standardized presentation scenarios are pre-configured in `frontend/src/lib/scam-demo.ts`:

1. **OTP / Bank Impersonation (`otp`)**
   - Caller: Unverified Bank Security Officer
   - Context: Caller pressures user to reveal OTP or banking credentials under threat of immediate account suspension.
   - Expected Indicators: Private code/password request, urgency/threats/safe-account claims.

2. **Executive / Urgent Transfer Fraud (`executive`)**
   - Caller: Impersonated Executive / CXO
   - Context: Caller impersonates manager/CXO demanding urgent wire transfer to safe escrow account.
   - Expected Indicators: Coercive payment/money transfer request, urgency/threats/safe-account claims.

3. **Remote Access Scam (`support`)**
   - Caller: Unverified Technical Support
   - Context: Caller asks victim to install remote access software (AnyDesk) or share screen to fix fake infection.
   - Expected Indicators: Remote device access request.

4. **Benign Control (`ordinary`)**
   - Caller: Project Collaborator
   - Context: Ordinary non-financial conversational exchange without urgency or credential demands.
   - Expected Indicators: None.

## Presentation Automation & Demo Mode

The `/call-demo` page features a compact **Demo Mode Automation** card designed for hackathon judges and live presentations:

- **1-Click Execution**: Selecting any scenario instantly populates its transcript and resets acoustic telemetry without auto-running backend inference.
- **Run Scenario**: Clicking **Run Scenario** invokes the reusable `runScenario()` function:
  1. If `sampleAudioPath` or an attached audio clip is present, it is sent to `POST /api/v1/detections` for real 16 kHz multi-window AASIST inference.
  2. If no audio file is provided, it executes in semantic-only mode without fabricating model scores.
  3. Heuristic semantic analysis classifies conversational intent.
  4. Both layers synthesize into the unified threat assessment.
- **Sequence Progression**: Visualizes the 4-step pipeline:
  `Select Scenario` $\to$ `Run Scenario` $\to$ `Acoustic Analysis` $\to$ `Semantic Analysis` $\to$ `Unified Verdict`.
- **Error Resilience**: If the backend is offline, AASIST is unavailable, or the audio file is missing, semantic analysis is preserved and the acoustic layer reports:
  `"Acoustic analysis unavailable — semantic risk only"`.

## Audio handling & backend integration

- Pre-packaged demo scenarios do not commit audio files to git repository history to respect copyright and technical honesty guidelines.
- Optional presentation audio fixtures can be dropped into `frontend/public/demo-audio/` (e.g. `bank_impersonation.wav`, `executive_fraud.wav`, `remote_access.wav`, `benign_control.wav`).
- Evaluators can also attach any local audio file (`.wav`, `.mp3`, `.flac`, `.ogg`, `.m4a`) via the UI file picker to run live AASIST inference against the backend.

## Demo procedure

1. Select a scenario from the presentation tabs or dropdown.
2. Click **Run Scenario** for immediate 1-click dual-layer evaluation.
3. Alternatively, click **Simulate Incoming Call** and then **Answer & Stream Audio** to demonstrate real-time continuous sliding-window call monitoring:
   - Microphone captures browser audio at 16 kHz mono.
   - Stream is transmitted over WebSocket (`/api/v1/detections/ws`).
   - Sliding-window AASIST inference runs dynamically on 64,600-sample windows.
   - Live acoustic and conversational risk updates compute unified verdicts in real time.
4. Inject custom phrases to test edge cases or evasion attempts.
5. If high threat is detected during the call, review the in-call warning alert with options to **End Call Immediately** or **Continue Call (Acknowledge Risk)**.
6. Upon ending the call, review the **Final Security Explanation** card detailing acoustic telemetry, conversational indicators, and next steps.

## Phase 3: Real-Time WebSocket Call Monitoring

Phase 3 upgrades `/call-demo` from batch-only analysis to continuous, real-time sliding-window monitoring:

- **WebSocket Endpoint**: `ws://<host>:8000/api/v1/detections/ws?format=pcm16`
- **Audio Capture**: Browser `AudioContext` and `ScriptProcessorNode` capturing 16 kHz 16-bit linear PCM directly from user microphone with sub-millisecond in-memory buffering.
- **Sliding-Window Geometry**:
  - Sample Rate: 16,000 Hz.
  - Window Size: 64,600 samples (~4.0375 seconds).
  - Hop Size: 16,150 samples (~1.009375 seconds, 75% overlap).
  - Minimum audio required before inference: 64,600 samples (telemetry reports buffering state).
- **Graceful Fallback**: If microphone permission is denied or backend WebSocket is offline:
  `"Real-time acoustic analysis unavailable — semantic monitoring remains active."`
- **Zero Fabrication**: No simulated probabilities are emitted during buffering or when the model is unavailable; actual model inference is required for all synthetic probabilities.
- **Safety Framing**: Low-risk telemetry states explicitly note: *"Low risk does NOT imply verified safety. Spoof detection and keyword heuristics cannot guarantee absolute authenticity."*

## Verification

Run the test suite in `frontend`:
```bash
node --test tests/scam-demo.test.mjs
npm run lint
npm run build
```

Run backend tests:
```bash
nix-shell --run "cd backend && ./.venv/bin/pytest"
```

The test suite covers:
- 1. Built-in scam scenarios contain semantic indicators.
- 2. Benign control remains benign/low when acoustic is genuine.
- 3. Missing audio path does not fabricate acoustic assessment.
- 4. Unified verdict still works when acoustic layer is unavailable.
- 5. No scenario contains a hard-coded synthetic probability.
- 6. No scenario claims guaranteed identity verification or guaranteed safety.
- 7. Real-time WebSocket connection handshake and buffering telemetry.
- 8. Sliding-window AASIST inference triggers at $\ge 64,600$ samples and successive hops.
- 9. Structured error handling for corrupt or invalid audio frames.
- 10. AASIST unavailable fallback without crashing.
- 11. Live acoustic update parsing and dynamic unified risk escalation.
- 12. In-call high threat intervention with Continue or End Call actions.
- 13. Preserving final session summary upon termination.
- 14. Dual-mode support: both live streaming and batch file uploads remain fully functional.
