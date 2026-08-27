import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "SIH26104 Voice Cloning Detection Platform"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # Database
    # Default to local SQLite fallback if PostgreSQL is not configured, or use standard PostgreSQL connection
    DATABASE_URL: str = "sqlite+aiosqlite:///./voice_cloning.db"
    
    # ML Detection Service ("mock" | "baseline" | "aasist")
    DETECTION_ENGINE: str = "mock"
    MOCK_MODEL_VERSION: str = "mock-v1"
    
    # Multi-Window & Audio Limits
    MAX_AUDIO_DURATION_SECONDS: float = 300.0  # 5 minutes
    MAX_MULTIWINDOW_WINDOWS: int = 350
    AASIST_WINDOW_HOP_SAMPLES: int = 16150  # 75% overlap (1.009375s)
    AASIST_MULTIWINDOW_BATCH_SIZE: int = 16
    AASIST_DEFAULT_AGGREGATION: str = "max_v1"

    # Rate Limiting & Concurrency (Security Hardening)
    RATE_LIMIT_ENABLED: bool = False
    DETECTION_RATE_LIMIT_PER_MINUTE: int = 10
    DETECTION_RATE_LIMIT_BURST: int = 3
    REPORT_RATE_LIMIT_PER_MINUTE: int = 30
    HISTORY_RATE_LIMIT_PER_MINUTE: int = 60
    MAX_CONCURRENT_INFERENCE_JOBS: int = 1
    ADMISSION_TIMEOUT_SECONDS: float = 5.0

    # Audio Upload Constraints
    UPLOAD_DIR: Path = Path(__file__).resolve().parent.parent / "uploads"
    MAX_FILE_SIZE_BYTES: int = 25 * 1024 * 1024  # 25 MB
    ALLOWED_EXTENSIONS: List[str] = [".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac", ".webm"]
    ALLOWED_MIME_TYPES: List[str] = [
        "audio/wav",
        "audio/x-wav",
        "audio/wave",
        "audio/mpeg",
        "audio/mp3",
        "audio/ogg",
        "audio/flac",
        "audio/x-flac",
        "audio/mp4",
        "audio/m4a",
        "audio/x-m4a",
        "audio/aac",
        "audio/webm",
        "application/octet-stream",  # often provided by browsers for audio blobs
    ]
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    model_config = SettingsConfigDict(
        env_file=(
            Path(__file__).resolve().parent.parent / ".env",
            ".env",
        ),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

# Ensure uploads directory exists
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
