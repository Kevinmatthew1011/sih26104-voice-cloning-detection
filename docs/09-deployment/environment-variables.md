# Environment Variables Reference: SIH26104

## 1. Backend Environment Variables

| Variable | Default | Example | Purpose |
| :--- | :--- | :--- | :--- |
| `PROJECT_NAME` | `"SIH26104 Voice Cloning Detection"` | `"VOICE-GUARD Enterprise"` | Service display name. |
| `VERSION` | `"1.0.0"` | `"1.0.0"` | API versioning string. |
| `ENVIRONMENT` | `"development"` | `"production"` | Runtime environment profile. |
| `API_V1_STR` | `"/api/v1"` | `"/api/v1"` | Route prefix. |
| `BACKEND_CORS_ORIGINS`| `["http://localhost:3000"]` | `["https://voiceguard.example.com"]` | Authorized CORS origins. |
| `DATABASE_URL` | `"sqlite+aiosqlite:///./sql_app.db"` | `"postgresql+asyncpg://user:pass@host/db"` | SQLAlchemy async database connection URI. |
| `UPLOAD_DIR` | `"./uploads"` | `"/var/data/uploads"` | Temporary storage directory for uploaded audio. |
| `MAX_FILE_SIZE_BYTES`| `26214400` (25 MB) | `26214400` | Streamed upload cap. |
| `DETECTION_ENGINE` | `"aasist"` | `"aasist"` / `"baseline"` / `"mock"` | Selected anti-spoofing engine. |
| `RATE_LIMIT_PER_MINUTE`| `10` | `20` | Max requests/min per IP. |
| `AASIST_CONFIG_PATH` | `"ml_eval/aasist/config/AASIST.conf"` | `"ml_eval/aasist/config/AASIST.conf"` | Model configuration. |
| `AASIST_WEIGHTS_PATH`| `"ml_eval/aasist/weights/AASIST.pth"` | `"ml_eval/aasist/weights/AASIST.pth"` | PyTorch model checkpoint. |
| `AASIST_DEVICE` | `"cpu"` | `"cuda"` / `"cpu"` / `"mps"` | Device for tensor computation. |

---

## 2. Frontend Environment Variables

| Variable | Default | Example | Purpose |
| :--- | :--- | :--- | :--- |
| `NEXT_PUBLIC_API_URL` | `"http://localhost:8000"` | `"https://api.voiceguard.example.com"` | Base URL of the FastAPI backend. |
