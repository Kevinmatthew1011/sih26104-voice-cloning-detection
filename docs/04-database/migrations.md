# Database Migrations & Evolution: SIH26104

## 1. Schema Initialization (`backend/app/db/session.py`)

In local development and prototype environments, database tables are automatically verified and created at application startup using SQLAlchemy's async metadata creation:

```python
async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

---

## 2. Production Migration Strategy (Alembic)

For production deployments using PostgreSQL or distributed SQL clusters, database evolution is managed via **Alembic** migration scripts to enable zero-downtime, auditable schema migrations.

### 2.1 Generating a New Migration
```bash
cd backend
source .venv/bin/activate
alembic revision --autogenerate -m "add_acoustic_telemetry_columns"
```

### 2.2 Applying Pending Migrations
```bash
alembic upgrade head
```

### 2.3 Rolling Back a Migration
```bash
alembic downgrade -1
```

---

## 3. Schema Versioning History

| Version | Milestone | Changes Introduced |
| :--- | :--- | :--- |
| **v1.0.0** | Phase 1 Foundation | Base `detection_cases` table: `id`, `filename`, `prediction`, `confidence`, `risk_level`, `created_at`. |
| **v1.1.0** | Security Hardening | Added `sha256_hash`, `file_size_bytes`, `mime_type` for tamper-evident file provenance. |
| **v1.2.0** | AASIST Integration | Added `countermeasure_score`, `synthetic_probability`, `raw_ml_action`, `operational_action`, `decision_reason`. |
| **v1.3.0** | Capture Domain Safety | Added `capture_domain_reliability`, `input_source` to support browser microphone policy overrides. |
| **v1.4.0** | Forensic Telemetry | Added `quality_metrics` JSON column (SNR, clipping, RMS) and `window_telemetry` JSON column. |
