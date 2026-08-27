---
name: project-workflow
description: Guides development of the SIH-26104 voice cloning detection project using a structured IDEA, PRD, TECH STACK, ARCHITECTURE, DATABASE, BUILD, TEST, REVIEW, and DEBUG workflow.
---

# SIH Project Development Workflow

## Project

AI-Powered Real-Time Detection and Prevention of Voice Cloning Impersonation Attacks.

Problem Statement:
SIH-26104

## Mandatory Development Workflow

Always follow:

IDEA
→ PRD
→ TECH STACK
→ ARCHITECTURE
→ DATABASE
→ BUILD
→ TEST
→ REVIEW
→ DEBUG

Do not skip stages when they are relevant.

## Before Coding

Before implementing a feature:

1. Understand the requirement.
2. Inspect the existing codebase.
3. Identify affected components.
4. Check existing architecture and conventions.
5. Identify dependencies.
6. Identify security implications.
7. Decide the smallest safe implementation.
8. Explain the implementation plan before making major changes.

## Build Rules

1. Build one feature at a time.
2. Make small, focused changes.
3. Do not rewrite working code unnecessarily.
4. Do not modify unrelated files.
5. Reuse existing utilities and components where appropriate.
6. Keep frontend, backend, ML, database, and infrastructure responsibilities separated.
7. Maintain existing project conventions.

## Technology Stack

Frontend:
- React
- TypeScript
- Vite
- Tailwind CSS
- shadcn/ui

Backend:
- Python
- FastAPI

Machine Learning:
- PyTorch
- Audio preprocessing
- Voice anti-spoofing / deepfake detection

Audio:
- FFmpeg
- Librosa

Database:
- PostgreSQL

Infrastructure:
- Docker
- NVIDIA GPU support when required

## ML Rules

For ML-related work:

1. Never invent model performance numbers.
2. Never claim a model is production-ready without evaluation.
3. Keep training and inference pipelines reproducible.
4. Separate training data from validation and test data.
5. Prevent speaker/data leakage.
6. Record evaluation metrics.
7. Document preprocessing assumptions.
8. Make model thresholds configurable rather than hard-coded without justification.
9. Preserve model provenance and dataset provenance.

## Security Rules

For security-sensitive features:

1. Validate all user input.
2. Treat uploaded audio as untrusted input.
3. Validate file type and size.
4. Avoid arbitrary file execution.
5. Prevent path traversal.
6. Do not expose secrets.
7. Use environment variables for credentials.
8. Apply authentication and authorization where required.
9. Consider rate limiting for expensive ML inference.
10. Never log sensitive user data unnecessarily.

## Testing

After implementing a feature:

1. Run relevant unit tests.
2. Run integration tests where applicable.
3. Test failure cases.
4. Test invalid input.
5. Test security-sensitive edge cases.
6. Verify that existing functionality still works.

Never claim a feature is complete without verification.

## Debugging

When something fails:

1. Reproduce the problem.
2. Read the actual error.
3. Identify the root cause.
4. Check relevant code and configuration.
5. Apply the smallest appropriate fix.
6. Run the failing test again.
7. Run related tests.
8. Confirm the fix did not introduce regressions.

Do not hide errors or bypass failing tests merely to make the project appear successful.

## Git Rules

Before significant changes:

1. Inspect git status.
2. Understand existing changes.
3. Do not overwrite unrelated work.
4. Keep commits focused.
5. Do not commit secrets, datasets, model weights, generated files, or environment files unless explicitly required.

## Completion Criteria

A feature is complete only when:

- The implementation works.
- Relevant tests pass.
- Error cases have been considered.
- Security has been reviewed where applicable.
- Documentation is updated when necessary.
- Existing functionality remains intact.