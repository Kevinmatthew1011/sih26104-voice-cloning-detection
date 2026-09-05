# Browser scam-call demo

The `/call-demo` page demonstrates incoming, answered, declined, and ended calls. Open it from the dashboard or desktop navigation. No real telephone connection, microphone capture, speech transcription, or AASIST inference is involved.

## Requirements and design

The demo adds content-based scam warnings alongside the existing audio-analysis product. It uses the existing Next.js/React stack without new dependencies. A pure frontend assessment function evaluates sample or custom English caller messages. Call state and the last ten previous call summaries live in page memory; no database changes or backend endpoints are needed. Reloading or leaving the page clears them.

The rules identify credential requests and remote-access requests as high risk. A payment request produces a warning; a payment request combined with urgency or threats produces high risk. Results are heuristic categories, not calibrated probabilities. Common negative safety advice is excluded, but complex negation, context, other languages, and paraphrases can produce misses or false warnings. No matches never means a caller is verified safe.

## Demo procedure

1. Select a scenario and simulate an incoming call.
2. Decline it, or answer to receive a sample caller message every 2.5 seconds.
3. Observe warnings and their specific reasons. With automatic ending enabled, high risk ends the simulated call after a two-second warning. Disable the option to retain manual control.
4. Add a custom message while connected to test other phrases. Inputs are limited to 500 characters and 50 messages per call.
5. Choose New demo after ending to move the call summary into session history and select another scenario.

Timers stop when the call ends or the page unmounts. Transcript events cannot reopen ended calls. The existing audio detection policy and audit records remain independent.

## Verification

Run `node --experimental-strip-types --test tests/scam-demo.test.mjs` in `frontend` with a Node runtime supporting type stripping, then `npm run lint` and `npm run build`. Browser checks cover answering, declining, automatic ending, manual override, custom messages, resetting, and ordinary-call behavior.

Real call support would require an authorized call-control integration, speech transcription, evaluated scam detection, and persistent call audit records.
