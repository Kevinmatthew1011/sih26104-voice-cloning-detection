# Database Schema & Entity Design: SIH26104

## 1. Overview & Data Layer Philosophy

The **VOICE-GUARD Database Layer** is implemented using **SQLAlchemy 2.0 Async ORM** with support for SQLite (development/local testing) and PostgreSQL (production). The schema is designed for:
- **Append-Only Immutability**: Detection records are immutable forensic audit trails. Once created, records are never updated or deleted by normal application workflows.
- **Structured JSON Projections**: Complex multi-dimensional telemetry (such as per-window timestamps and acoustic quality descriptors) are stored in structured JSON columns for query efficiency.
- **Cryptographic Fingerprinting**: Every record stores a SHA-256 integrity hash of the ingested audio byte stream.

---

## 2. Entity Relationship & Schema Diagram

```mermaid
erDiagram
    DETECTION_CASE {
        VARCHAR(36) id PK "UUID v4 Primary Key"
        VARCHAR(255) filename "Original Uploaded Filename"
        BIGINT file_size_bytes "Audio Size in Bytes"
        VARCHAR(50) mime_type "Audio MIME Type"
        VARCHAR(64) sha256_hash "SHA-256 Audio Integrity Hash"
        VARCHAR(20) prediction "'real' or 'synthetic'"
        FLOAT confidence "Predicted Class Probability (0.0 - 1.0)"
        VARCHAR(20) risk_level "'low', 'medium', or 'high'"
        FLOAT countermeasure_score "CM Score (logit_bona - logit_spoof)"
        FLOAT synthetic_probability "Softmax Synthetic Probability (0.0 - 1.0)"
        VARCHAR(20) raw_ml_action "'ALLOW', 'VERIFY', or 'BLOCK'"
        VARCHAR(20) operational_action "Final Action ('ALLOW', 'VERIFY', 'BLOCK')"
        TEXT decision_reason "Human-Readable Decision Rationale"
        VARCHAR(30) capture_domain_reliability "'trusted_file' or 'unvalidated'"
        VARCHAR(30) input_source "'uploaded_file' or 'browser_microphone'"
        VARCHAR(50) model_version "'aasist-v1' or 'baseline-v1'"
        DATETIME created_at "UTC Creation Timestamp"
        JSON quality_metrics "Acoustic SNR, Clipping, RMS, Centroid"
        JSON window_telemetry "Array of 4.0375s Window Breakdowns"
    }
```

---

## 3. Database Indexes

To maintain sub-50ms query response times under high case volumes, the following indexes are configured in [backend/app/models/detection_case.py](file:///home/kiddo/projects/sih26104-voice-cloning/backend/app/models/detection_case.py):

| Index Column | Type | Purpose |
| :--- | :--- | :--- |
| `id` | Primary Key / Unique | Fast O(1) single-record retrieval by UUID. |
| `created_at` | B-Tree (Descending) | Fast pagination and chronological case history sorting. |
| `sha256_hash` | B-Tree | Rapid forensic deduplication and file integrity lookups. |
| `risk_level` | B-Tree | Filter queries by risk categorization (`low`, `medium`, `high`). |
| `operational_action` | B-Tree | Filter queries by operational enforcement action (`ALLOW`, `VERIFY`, `BLOCK`). |
