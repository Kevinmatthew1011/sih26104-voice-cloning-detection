# Frontend Verification & Build Testing: SIH26104

## 1. Typechecking & Build Verification

The frontend enforces strict TypeScript compilation and Next.js static asset optimization:

```bash
cd frontend
npm run build
```

### Production Build Outputs:
```
Route (app)
┌ ○ /                        (Static)
├ ○ /_not-found              (Static)
├ ○ /detect                  (Static)
├ ○ /detections              (Static)
└ ƒ /detections/[id]         (Dynamic Server-Rendered)
```

---

## 2. Frontend Component Verification Checklist

| Component | Automated / Manual Verification Method | Verified Behavior |
| :--- | :--- | :--- |
| **`ThreatBadge.tsx`** | Prop rendering unit validation | Displays `SIGNAL QUALITY: GOOD` and `MIC DOMAIN: UNVALIDATED` for browser mic captures. |
| **`Dropzone.tsx`** | Client upload event testing | Rejects non-audio extensions, enforces drag-and-drop feedback, handles upload errors. |
| **`MicRecorder.tsx`** | WebRTC hardware mock testing | Requests microphone permission, animates Canvas 2D frequency visualizer, gathers WebM chunks. |
| **`AudioPlayer.tsx`** | HTML5 audio event testing | Syncs visual playback head with audio duration, supports scrubbing and volume changes. |
| **`WindowTimeline.tsx`**| Multi-window data binding | Renders per-window risk score bars, highlights anomalous windows in red, syncs on click. |
