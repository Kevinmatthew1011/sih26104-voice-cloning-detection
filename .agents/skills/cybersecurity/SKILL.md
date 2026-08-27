---
name: cybersecurity
description: Guides cybersecurity best practices, untrusted audio validation, path traversal prevention, API security, secrets protection, and defense-in-depth for the SIH-26104 voice cloning detection platform.
---

# SIH-26104 Cybersecurity & Defensive Engineering Guidelines

This skill defines the security principles, defensive coding practices, and threat boundaries for the SIH-26104 Voice Cloning Detection Platform.

## Security Architecture & Threat Boundaries

The platform processes **untrusted binary audio files** submitted over HTTP and executes CPU/GPU-intensive feature extraction and machine learning inference.

### Core Security Principle
> Treat all user-submitted audio files, filenames, and query parameters as untrusted, hostile input.

## Currently Implemented Defenses

1. **Audio File Validation (`app.services.audio_validator`)**:
   - Extension whitelist verification (`.wav`, `.mp3`, `.ogg`, `.flac`, `.m4a`, `.aac`, `.webm`).
   - File size ceiling enforcement (`MAX_FILE_SIZE_BYTES`, default 25 MB).
   - Empty file rejection (0-byte payload check).
   - Binary magic-byte signature validation (`RIFF`, `ID3`, `\xff\xfb`, `OggS`, `fLaC`, `\x1a\x45\xdf\xa3`).
2. **Path Traversal & Collision Prevention (`app.services.storage`)**:
   - Stripping path components via `Path(filename).name` and regex sanitization (`re.sub(r"[^\w\s\.-]", "_", name)`).
   - Prepending unique UUID4 case identifiers (`{case_id}_{safe_name}`) to isolate files.
3. **SQL Injection Prevention (`app.database`, `app.models`)**:
   - Parameterized SQLAlchemy 2.0 ORM queries; no raw SQL string concatenation.
4. **Secrets & Dataset Isolation (`.gitignore`)**:
   - All `.env` files, audio samples (`ml_data/**/*.wav`), and model artifacts and weights such as `*.joblib` and any future model-weight formats configured by the project are excluded from version control.

## Known Security Gaps & Threat Mitigations

| Threat Vector | Current Status | Required Mitigation / Development Rule |
|---|---|---|
| **Compute Exhaustion / DoS** | No rate limiting currently active | Heavy ML endpoints (`POST /api/v1/detections`) must not be called in tight unthrottled loops; rate limiting should be introduced for production. |
| **Authentication & Access Control** | Endpoints are currently public forensics tools | When user accounts or API keys are introduced, implement via reusable FastAPI dependencies (`Depends(get_current_user)`) without breaking unauthenticated endpoints unless requested. |
| **Information Disclosure** | Internal exception strings in HTTP 500 | Sanitize user-facing error details when `DEBUG=False`. Log detailed stack traces server-side only. |
| **CORS Misconfiguration** | Default includes wildcard in dev config | Ensure explicit origins are passed via `CORS_ORIGINS` environment variable in production deployments. |
| **Container Privilege** | Containers run as default user | Future Docker enhancements should define an unprivileged non-root user (`USER appuser`). |

## Secure Coding Rules

### 1. Untrusted File Handling
- Never pass client filenames directly to OS filesystem operations or shell commands. Always route through `AudioStorageService.save_audio()`.
- Never bypass `AudioValidator.validate_filename_extension()` or `AudioValidator.validate_file_content()`.
- Treat audio decoding as an untrusted-resource operation. Preserve existing decoder behavior, enforce configured file/resource limits where supported, and evaluate decoder/resource-exhaustion risks before introducing new formats or processing paths.

### 2. API & Controller Security
- Validate all incoming request fields using Pydantic schemas.
- Do not expose internal server paths, database connection strings, or system environment variables in API responses or logs.
- Use explicit HTTP status codes: HTTP 400 (Bad Request), HTTP 404 (Not Found), HTTP 413 (Payload Too Large), HTTP 422 (Validation Error), HTTP 503 (Service Unavailable).

### 3. Secrets & Configuration
- Store credentials and secret keys exclusively in environment variables managed by `app/config.py` (`pydantic-settings`).
- Never commit `.env` files or hardcode API keys, passwords, or tokens in source code.

### 4. Safe Logging
- Log security-relevant events (validation failures, rejected file uploads, internal exceptions) with appropriate severity levels.
- Never log full binary payloads, raw audio content, or sensitive user headers in application logs.

### 5. Verification & Security Testing
- Verify that invalid extensions, oversized files, 0-byte files, and corrupted headers return expected error codes:
  ```bash
  cd backend && pytest tests/test_detections.py tests/test_health.py
  ```
