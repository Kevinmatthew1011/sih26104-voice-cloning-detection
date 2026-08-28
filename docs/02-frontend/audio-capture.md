# Browser Microphone Capture & WebAudio: SIH26104

## 1. Overview

The **VOICE-GUARD** web interface allows operators and users to record speech directly in the browser via standard WebRTC and WebAudio APIs, providing real-time visual feedback before submitting the recording for forensic analysis.

---

## 2. Audio Capture Implementation (`MicRecorder.tsx`)

```mermaid
sequenceDiagram
    actor User
    participant Browser as Client Browser (WebRTC)
    participant AudioContext as WebAudio AudioContext
    participant Analyser as AnalyserNode (FFT)
    participant Canvas as Canvas 2D Renderer
    participant MediaRecorder as MediaRecorder API
    participant Backend as FastAPI Server
    
    User->>Browser: Click "Start Recording"
    Browser->>Browser: navigator.mediaDevices.getUserMedia({ audio: true })
    Browser->>AudioContext: Create MediaStreamSource
    AudioContext->>Analyser: Connect source -> AnalyserNode
    
    loop Every Animation Frame (60 FPS)
        Analyser->>Canvas: getByteFrequencyData()
        Canvas->>Canvas: Render smooth audio visualizer bars
    end
    
    Browser->>MediaRecorder: new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' })
    MediaRecorder->>MediaRecorder: start(100) chunk slicing
    
    User->>Browser: Click "Stop Recording"
    MediaRecorder->>MediaRecorder: stop() -> gather chunks into Blob
    Browser->>Backend: POST /api/v1/detections (input_source="browser_microphone")
```

---

## 3. Codec & Format Negotiation

The `MicRecorder` component dynamically selects the highest fidelity supported audio container across modern browsers:

1. **Chrome / Edge / Opera**: `audio/webm;codecs=opus` (High-efficiency, 48 kHz native sampling).
2. **Firefox**: `audio/ogg;codecs=opus` or `audio/webm`.
3. **Safari**: `audio/mp4` or fallback PCM stream.

```typescript
const getSupportedMimeType = (): string => {
  const types = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/mp4",
    "audio/wav",
  ];
  for (const t of types) {
    if (MediaRecorder.isTypeSupported(t)) return t;
  }
  return "";
};
```

---

## 4. Real-Time Canvas 2D Waveform Visualizer

To provide immediate acoustic feedback:
1. An `AudioContext` and `AnalyserNode` (`fftSize = 256`, `smoothingTimeConstant = 0.8`) inspect the live stream.
2. An animated `requestAnimationFrame` loop polls `getByteFrequencyData()`, rendering 32 dynamic amplitude bars in teal/cyan colors on an HTML5 `<canvas>`.
3. When recording stops, all `MediaStreamTrack` instances are stopped and the `AudioContext` is closed cleanly to release the microphone hardware.

---

## 5. Capture Domain Flagging

When recording from the browser, the form payload explicitly sets:
```typescript
formData.append("input_source", "browser_microphone");
```
This signals the backend decision engine to evaluate the recording under the **Capture-Domain Safety Protocol**, ensuring domain-shift acoustic variations do not produce unverified customer account lockouts.
