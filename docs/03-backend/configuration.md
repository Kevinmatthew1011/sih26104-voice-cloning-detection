# Backend Configuration: SIH26104

## 1. Configuration Architecture (`backend/app/core/config.py`)

Configuration settings are managed using `pydantic_settings.BaseSettings`. Settings are initialized once at server startup, loading values from environment variables or a local `.env` file with validated type coercions and default fallbacks.

---

## 2. Environment Variables Catalog

| Variable Name | Default Value | Allowed Values | Description |
| :--- | :--- | :--- | :--- |
| **`PROJECT_NAME`** | `"SIH26104 Voice Cloning Detection"` | String | Name of the platform displayed in OpenAPI docs. |
| **`VERSION`** | `"1.0.0"` | SemVer String | API version string. |
| **`ENVIRONMENT`** | `"development"` | `"development"`, `"staging"`, `"production"` | Operational environment mode. |
| **`API_V1_STR`** | `"/api/v1"` | Path String | API v1 route prefix. |
| **`BACKEND_CORS_ORIGINS`** | `["http://localhost:3000"]` | JSON Array of URLs | Allowed CORS origins for frontend requests. |
| **`DATABASE_URL`** | `"sqlite+aiosqlite:///./sql_app.db"` | Valid DB URI | Async database connection string (SQLite / PostgreSQL). |
| **`UPLOAD_DIR`** | `"./uploads"` | Directory Path | Temporary directory for streaming audio files. |
| **`MAX_FILE_SIZE_BYTES`** | `26214400` (25 MB) | Integer Bytes | Maximum permitted audio upload size. |
| **`DETECTION_ENGINE`** | `"aasist"` | `"aasist"`, `"baseline"`, `"mock"` | Active anti-spoofing engine. |
| **`RATE_LIMIT_PER_MINUTE`**| `10` | Integer | Maximum API requests allowed per minute per client IP. |
| **`AASIST_CONFIG_PATH`** | `"ml_eval/aasist/config/AASIST.conf"`| Path | Hyperparameter configuration for AASIST architecture. |
| **`AASIST_WEIGHTS_PATH`** | `"ml_eval/aasist/weights/AASIST.pth"`| Path | Serialized PyTorch weights checkpoint for AASIST. |
| **`AASIST_DEVICE`** | `"cpu"` | `"cpu"`, `"cuda"`, `"mps"` | Compute device for PyTorch tensor inference. |

---

## 3. Example `.env` File

```bash
PROJECT_NAME="SIH26104 Voice Cloning Detection"
VERSION="1.0.0"
ENVIRONMENT="development"
API_V1_STR="/api/v1"
BACKEND_CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
DATABASE_URL="sqlite+aiosqlite:///./sql_app.db"
UPLOAD_DIR="./uploads"
MAX_FILE_SIZE_BYTES=26214400
DETECTION_ENGINE="aasist"
RATE_LIMIT_PER_MINUTE=10
AASIST_CONFIG_PATH="ml_eval/aasist/config/AASIST.conf"
AASIST_WEIGHTS_PATH="ml_eval/aasist/weights/AASIST.pth"
AASIST_DEVICE="cpu"
```
