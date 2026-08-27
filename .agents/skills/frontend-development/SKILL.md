---
name: frontend-development
description: Guides frontend development for the SIH-26104 voice cloning detection web application, including Next.js App Router, React 19, TypeScript, Tailwind CSS v4, shadcn/ui patterns where applicable, component standards, and API client integration.
---

# SIH-26104 Frontend Development Guidelines

This skill defines the technical standards, file structure conventions, and safety rules for developing and modifying the frontend of the SIH-26104 Voice Cloning Detection system.

## Frontend Technology Stack

- **Framework**: Next.js 16 (App Router) + React 19
- **Language**: TypeScript (Strict Mode enabled)
- **Styling**: Tailwind CSS v4 + PostCSS (`@tailwindcss/postcss`)
- **UI & Icons**: `lucide-react`, `clsx`, `tailwind-merge`, and shadcn/ui patterns where applicable
- **Audio Processing / Visuals**: HTML5 Web Audio API, Canvas-based waveform visualization
- **State & Networking**: Native `fetch` with typed API client wrapper (`src/lib/api.ts`)

## Directory Structure & Conventions

Always place frontend code in its designated location under `frontend/src/`:

```text
frontend/
├── src/
│   ├── app/                    # Next.js App Router pages and layouts
│   │   ├── layout.tsx          # Root layout with dark theme & navbar/footer
│   │   ├── page.tsx            # Landing & dashboard overview page
│   │   ├── detect/page.tsx     # Audio upload and live forensic analysis
│   │   ├── detections/page.tsx # Detection history and case review
│   │   └── globals.css         # Tailwind v4 import and theme variables
│   ├── components/             # Reusable modular UI components
│   │   ├── AudioWaveformVisualizer.tsx
│   │   ├── ConfidenceGauge.tsx
│   │   ├── DetectionDropzone.tsx
│   │   ├── ThreatBadge.tsx
│   │   ├── RecentDetectionsTable.tsx
│   │   └── Navbar.tsx / Footer.tsx
│   └── lib/                    # Core utilities, API clients, and shared types
│       ├── api.ts              # Backend REST API client
│       └── types.ts            # Frontend TypeScript models and enums
```

## Core Frontend Rules

### 1. Component & Client/Server Boundaries
- Add `"use client"` at the top of components that use React hooks (`useState`, `useEffect`, `useRef`), browser APIs (Web Audio, Canvas, File API), or event handlers.
- Keep components focused and single-responsibility. Extract heavy UI chunks into `src/components/`.
- Use TypeScript interfaces for all component props. Export props interfaces when reusable.
- Preserve existing component architecture and naming conventions across `src/components/`.

### 2. Styling & Design Consistency
- Maintain the forensic dark theme (`dark` class on `<html>`, `bg-slate-950`, `text-slate-100`).
- Apply shadcn/ui patterns where applicable alongside Tailwind CSS v4 utilities.
- Use standardized semantic colors for detection statuses:
  - **Synthetic / Fake**: Red palette (`text-red-400`, `bg-red-950/40`, `border-red-500/30`)
  - **Real Speech**: Emerald palette (`text-emerald-400`, `bg-emerald-950/40`, `border-emerald-500/30`)
  - **Replay Attack / Warning**: Amber palette (`text-amber-400`, `bg-amber-950/40`, `border-amber-500/30`)
  - **Inconclusive / Neutral**: Slate palette (`text-slate-300`, `bg-slate-900`, `border-slate-700`)
- Use `clsx` and `tailwind-merge` for dynamic or conditional class merging.

### 3. API & Data Handling
- Do not make raw ad-hoc `fetch` calls scattered across components. Always route through `src/lib/api.ts`.
- When updating API responses, synchronize types in `src/lib/types.ts` with backend schemas (`backend/app/schemas/`).
- Handle loading, error, and empty states gracefully in all UI views.
- Audio file upload must validate file type (WAV, MP3, FLAC, OGG, M4A, AAC, WEBM) and size constraints before submission.

### 4. Audio & Media Handling
- Clean up Web Audio `AudioContext`, animation frames, and object URLs in `useEffect` cleanup return functions to prevent memory leaks.
- Ensure audio players and visualizers handle cross-origin playback and failure states smoothly.

## Verification & Quality Checks

Run these commands in `frontend/` before completing frontend tasks:
1. **Type Check**: `npm run build` or `npx tsc --noEmit`
2. **Linting**: `npm run lint`
3. **Dev Verification**: `npm run dev` to verify UI responsiveness and console cleanliness
