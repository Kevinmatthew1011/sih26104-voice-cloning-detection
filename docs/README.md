# VOICE-GUARD Documentation Hub: SIH26104

Welcome to the **VOICE-GUARD (SIH26104)** technical documentation index. This documentation is organized into modular sections covering the entire architecture, machine learning models, security controls, testing suites, deployment instructions, and hackathon presentation guides.

---

## 📚 Categorized Documentation Index

### [00. Overview](file:///home/kiddo/projects/sih26104-voice-cloning/docs/00-overview/)
- [Project Overview](file:///home/kiddo/projects/sih26104-voice-cloning/docs/00-overview/project-overview.md) — Executive summary, value propositions, and high-level architecture.
- [Problem Statement & Threat Landscape](file:///home/kiddo/projects/sih26104-voice-cloning/docs/00-overview/problem-statement.md) — SIH26104 problem breakdown and generative AI threat taxonomy.
- [System Requirements & Specifications](file:///home/kiddo/projects/sih26104-voice-cloning/docs/00-overview/requirements.md) — Functional and non-functional engineering requirements.
- [Terminology & Glossary](file:///home/kiddo/projects/sih26104-voice-cloning/docs/00-overview/terminology.md) — Formal definitions of biometric and ML concepts.

### [01. Architecture](file:///home/kiddo/projects/sih26104-voice-cloning/docs/01-architecture/)
- [System Architecture](file:///home/kiddo/projects/sih26104-voice-cloning/docs/01-architecture/system-architecture.md) — Multi-tier topology, core subsystems, and design patterns.
- [Request Flow & Lifecycle](file:///home/kiddo/projects/sih26104-voice-cloning/docs/01-architecture/request-flow.md) — Sequence diagrams and step-by-step request execution.
- [Detection Pipeline](file:///home/kiddo/projects/sih26104-voice-cloning/docs/01-architecture/detection-pipeline.md) — Multi-stage pipeline from audio stream to decision action.
- [Directory Structure](file:///home/kiddo/projects/sih26104-voice-cloning/docs/01-architecture/directory-structure.md) — Current repository layout and future organizational roadmap.

### [02. Frontend Application](file:///home/kiddo/projects/sih26104-voice-cloning/docs/02-frontend/)
- [Frontend Architecture](file:///home/kiddo/projects/sih26104-voice-cloning/docs/02-frontend/frontend-architecture.md) — Next.js 15 App Router, React 19, and Tailwind CSS v4 design system.
- [Pages & Components Guide](file:///home/kiddo/projects/sih26104-voice-cloning/docs/02-frontend/pages-and-components.md) — Page routes, visualizers, and interactive components.
- [API Integration & Contracts](file:///home/kiddo/projects/sih26104-voice-cloning/docs/02-frontend/api-integration.md) — Typed API client and TypeScript interfaces.
- [Browser Microphone Capture](file:///home/kiddo/projects/sih26104-voice-cloning/docs/02-frontend/audio-capture.md) — WebRTC audio streaming and Canvas 2D waveform animation.

### [03. Backend Services](file:///home/kiddo/projects/sih26104-voice-cloning/docs/03-backend/)
- [Backend Architecture](file:///home/kiddo/projects/sih26104-voice-cloning/docs/03-backend/backend-architecture.md) — FastAPI asynchronous runtime and service layer conventions.
- [API Reference](file:///home/kiddo/projects/sih26104-voice-cloning/docs/03-backend/api-reference.md) — Complete REST endpoint documentation and JSON payloads.
- [Services Specification](file:///home/kiddo/projects/sih26104-voice-cloning/docs/03-backend/services.md) — Deep dive into Validators, Decoders, Analyzers, and Factories.
- [Configuration Reference](file:///home/kiddo/projects/sih26104-voice-cloning/docs/03-backend/configuration.md) — Environment variables catalog and `.env` template.
- [Error Handling & Resilience](file:///home/kiddo/projects/sih26104-voice-cloning/docs/03-backend/error-handling.md) — Sanitized error responses and guaranteed cleanup.

### [04. Database & Persistence](file:///home/kiddo/projects/sih26104-voice-cloning/docs/04-database/)
- [Database Schema](file:///home/kiddo/projects/sih26104-voice-cloning/docs/04-database/database-schema.md) — Entity design, indexes, and data layer philosophy.
- [DetectionCase Model](file:///home/kiddo/projects/sih26104-voice-cloning/docs/04-database/detection-case.md) — ORM fields, semantics, and JSON columns.
- [Database Migrations](file:///home/kiddo/projects/sih26104-voice-cloning/docs/04-database/migrations.md) — Schema initialization and Alembic migration strategy.
- [Forensic Audit Evidence](file:///home/kiddo/projects/sih26104-voice-cloning/docs/04-database/audit-evidence.md) — Cryptographic SHA-256 receipts and report schemas.

### [05. Machine Learning Engine](file:///home/kiddo/projects/sih26104-voice-cloning/docs/05-ml/)
- [ML Engine Overview](file:///home/kiddo/projects/sih26104-voice-cloning/docs/05-ml/ml-overview.md) — Evolution from baseline to deep learning AASIST.
- [AASIST Architecture](file:///home/kiddo/projects/sih26104-voice-cloning/docs/05-ml/aasist-architecture.md) — SincNet filters, residual encoders, and graph attention fusion.
- [Audio Preprocessing](file:///home/kiddo/projects/sih26104-voice-cloning/docs/05-ml/preprocessing.md) — 16 kHz standardization, mono conversion, and wrap-tiling.
- [Multi-Window Inference](file:///home/kiddo/projects/sih26104-voice-cloning/docs/05-ml/multi-window-inference.md) — 4.0375s sliding windows (75% overlap / 16,150 hop) and `max_v1` aggregation.
- [Model Outputs & Scores](file:///home/kiddo/projects/sih26104-voice-cloning/docs/05-ml/model-output.md) — CM scores, probability formulas, and calibration disclaimers.
- [ASVspoof 2019 Dataset](file:///home/kiddo/projects/sih26104-voice-cloning/docs/05-ml/asvspoof-dataset.md) — Academic benchmark partitions and attack taxonomy.
- [Official Evaluation Benchmark](file:///home/kiddo/projects/sih26104-voice-cloning/docs/05-ml/evaluation.md) — Certified results: 0.80% EER, 0.9993 ROC-AUC.
- [Machine Learning Limitations](file:///home/kiddo/projects/sih26104-voice-cloning/docs/05-ml/limitations.md) — Threat boundaries, telephony codec loss, and replay attacks.

### [06. Microphone Domain Adaptation Research](file:///home/kiddo/projects/sih26104-voice-cloning/docs/06-microphone-domain/)
- [The Microphone Domain-Shift Problem](file:///home/kiddo/projects/sih26104-voice-cloning/docs/06-microphone-domain/microphone-domain-problem.md) — Discovery of raw microphone phase shifts.
- [Stage 1: Diagnosis & Evaluation Design](file:///home/kiddo/projects/sih26104-voice-cloning/docs/06-microphone-domain/stage-1-design.md) — Initial audit and metadata schema.
- [Stage 2: Pilot Dataset Build](file:///home/kiddo/projects/sih26104-voice-cloning/docs/06-microphone-domain/stage-2-pilot.md) — 30-speaker pilot and frozen diagnostic probe.
- [Stage 3: Classifier-Head Adaptation](file:///home/kiddo/projects/sih26104-voice-cloning/docs/06-microphone-domain/stage-3-head-adaptation.md) — Multi-seed training of experimental head.
- [Stage 4: Physical Transducer Validation](file:///home/kiddo/projects/sih26104-voice-cloning/docs/06-microphone-domain/stage-4-physical-validation.md) — Live physical microphone challenge and finding that head adaptation is insufficient.
- [Future Domain Adaptation Roadmap](file:///home/kiddo/projects/sih26104-voice-cloning/docs/06-microphone-domain/future-domain-adaptation.md) — Partial SincNet unfreezing and physical dataset expansion.

### [07. Security Hardening](file:///home/kiddo/projects/sih26104-voice-cloning/docs/07-security/)
- [Security Architecture](file:///home/kiddo/projects/sih26104-voice-cloning/docs/07-security/security-architecture.md) — Defense-in-depth security controls matrix.
- [Upload Security & Validation](file:///home/kiddo/projects/sih26104-voice-cloning/docs/07-security/upload-security.md) — Streamed 25 MB cap, magic bytes, path sanitization.
- [Rate Limiting & Abuse Prevention](file:///home/kiddo/projects/sih26104-voice-cloning/docs/07-security/rate-limiting.md) — Process-local token bucket rate limiter (10 req/min, burst 3).
- [Inference Admission Control](file:///home/kiddo/projects/sih26104-voice-cloning/docs/07-security/inference-admission-control.md) — ThreadPool offloading and memory bounding.
- [Decision Engine & Security Policies](file:///home/kiddo/projects/sih26104-voice-cloning/docs/07-security/decision-engine.md) — 3-tier policy thresholds and domain overrides.
- [Threat Model & STRIDE Analysis](file:///home/kiddo/projects/sih26104-voice-cloning/docs/07-security/threat-model.md) — Vulnerability analysis and mitigations.

### [08. Testing & Quality Assurance](file:///home/kiddo/projects/sih26104-voice-cloning/docs/08-testing/)
- [Testing Strategy](file:///home/kiddo/projects/sih26104-voice-cloning/docs/08-testing/testing-strategy.md) — Test pyramid and quality release gates.
- [Backend Test Suite Guide](file:///home/kiddo/projects/sih26104-voice-cloning/docs/08-testing/backend-tests.md) — 123 automated tests breakdown.
- [Frontend Verification Guide](file:///home/kiddo/projects/sih26104-voice-cloning/docs/08-testing/frontend-tests.md) — Typechecking, build, and component verification.
- [ML Validation Scripts](file:///home/kiddo/projects/sih26104-voice-cloning/docs/08-testing/ml-validation.md) — ASVspoof reproduction and dataset integrity tools.

### [09. Deployment & Operations](file:///home/kiddo/projects/sih26104-voice-cloning/docs/09-deployment/)
- [Local Development Setup](file:///home/kiddo/projects/sih26104-voice-cloning/docs/09-deployment/local-development.md) — Step-by-step setup for backend and frontend.
- [Environment Variables](file:///home/kiddo/projects/sih26104-voice-cloning/docs/09-deployment/environment-variables.md) — Complete environment reference.
- [Docker & Container Orchestration](file:///home/kiddo/projects/sih26104-voice-cloning/docs/09-deployment/docker.md) — Docker Compose multi-container setup.
- [Production Readiness](file:///home/kiddo/projects/sih26104-voice-cloning/docs/09-deployment/production-considerations.md) — Gunicorn scaling, CUDA GPU acceleration, privacy.

### [10. Hackathon & Presentation](file:///home/kiddo/projects/sih26104-voice-cloning/docs/10-hackathon/)
- [Live Demonstration Script](file:///home/kiddo/projects/sih26104-voice-cloning/docs/10-hackathon/demo-guide.md) — 3-part live demo sequence.
- [Demo Test Audio Fixtures](file:///home/kiddo/projects/sih26104-voice-cloning/docs/10-hackathon/demo-test-audio.md) — Catalog of verified test audio files.
- [Judge Q&A Preparation](file:///home/kiddo/projects/sih26104-voice-cloning/docs/10-hackathon/judge-questions.md) — Concise technical answers for judges.
- [Limitations & Future Roadmap](file:///home/kiddo/projects/sih26104-voice-cloning/docs/10-hackathon/limitations-and-future-work.md) — Transparent technical boundaries.
- [Technical Innovation Highlights](file:///home/kiddo/projects/sih26104-voice-cloning/docs/10-hackathon/technical-highlights.md) — Key differentiators and metrics.
