---
name: testing
description: Guides testing, verification, and regression prevention for the SIH-26104 voice cloning detection platform across FastAPI async endpoints, ML pipelines, dataset integrity, and frontend build checks.
---

# SIH-26104 Testing & Verification Guidelines

This skill defines the testing standards, test execution procedures, and verification rules for the SIH-26104 Voice Cloning Detection Platform.

## Testing Architecture

- **Backend Framework**: `pytest (>=8.2.0)` with `pytest-asyncio` (`asyncio_mode = auto`), `pytest-mock`, and `pytest.ini`.
- **API & Client Simulation**: `httpx.AsyncClient` with `ASGITransport(app=app)`.
- **Database Test Isolation**: In-memory SQLite (`sqlite+aiosqlite:///:memory:`) via SQLAlchemy `AsyncSession` fixtures.
- **Frontend Verification**: TypeScript compilation (`tsc --noEmit` / `next build`) and ESLint (`eslint`). *Note: No automated frontend component test runner is currently installed.*

## Existing Test Directory Structure

```text
backend/tests/
├── conftest.py                   # Test environment setup, in-memory SQLite db_session, and AsyncClient fixtures
├── test_health.py                # Root and health endpoint tests
├── test_detections.py            # Detection upload, validation rejection, history, and audio streaming tests
├── test_ml_baseline.py           # Preprocessing, 88-D feature extraction, classifier, and inference tests
└── test_dataset_and_metrics.py   # Dataset validation, leakage prevention, speaker splitting, and EER metrics tests
```

## Core Testing Rules

### 1. Test Integrity & Honesty
- **Never modify existing tests merely to make a failing implementation pass.** If a test fails, investigate and fix the root cause in the application code.
- **Never claim a feature or fix works without executing the relevant test suite.**
- Do not introduce new testing dependencies unless explicitly requested.

### 2. Async FastAPI & Endpoint Testing
- Use the `client: AsyncClient` fixture from `conftest.py`.
- Always test both the **happy path** (200/201 responses with correct schema contracts) and failure cases.
- Test the failure cases relevant to each endpoint, including applicable validation, not-found, payload-size, and unavailable-model scenarios.
- Construct in-memory WAV byte streams using `io.BytesIO` rather than writing temporary files to disk when testing endpoints.

### 3. Database Isolation
- All database operations in backend tests run against an isolated in-memory SQLite session managed by the `db_session` fixture.
- Use the existing SQLite test fixtures for unit/integration tests. When PostgreSQL-specific behavior is required, verify it separately against the project's PostgreSQL environment rather than weakening production code for SQLite compatibility.

### 4. Audio & Machine Learning Pipeline Testing
- When modifying `AudioPreprocessor` or `AudioFeatureExtractor`:
  - Verify that audio shape, sampling rate (16 kHz mono), 3.0s windowing (zero-pad / truncate), and 88-D vector dimensions are preserved.
  - Verify that `np.isnan()` or `np.isinf()` assertions pass on all feature vectors.
- When modifying `DatasetValidator` or metrics:
  - Verify SHA-256 cross-split duplicate rejection, speaker leakage detection, and EER calculation against known operating points.

### 5. Frontend Verification
- Run static type checking and linting to ensure zero compilation or styling errors:
  - `cd frontend && npm run lint`
  - `cd frontend && npm run build`
- Perform runtime browser testing for UI interactions, audio playback, and file uploads.

## Standard Test Commands

Always run the appropriate verification commands before completing any backend or frontend task:

### Backend Tests:
```bash
cd backend
# Run all tests
pytest

# Run specific test modules
pytest tests/test_detections.py
pytest tests/test_health.py
pytest tests/test_ml_baseline.py
pytest tests/test_dataset_and_metrics.py
```

### Frontend Verification:
```bash
cd frontend
npm run lint
npm run build
```
