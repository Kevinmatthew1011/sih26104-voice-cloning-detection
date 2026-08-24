import re
from pathlib import Path
from fastapi import HTTPException, status
from app.config import settings


def sanitize_filename(filename: str) -> str:
    """Sanitize original filename to prevent path traversal or special character injection."""
    name = Path(filename).name
    name = re.sub(r"[^\w\s\.-]", "_", name)
    return name.strip()


class AudioStorageService:
    @staticmethod
    def save_audio(case_id: str, original_filename: str, content: bytes) -> Path:
        """Store audio file locally with a unique case ID prefix."""
        safe_name = sanitize_filename(original_filename)
        dest_filename = f"{case_id}_{safe_name}"
        dest_path = settings.UPLOAD_DIR / dest_filename
        
        with open(dest_path, "wb") as f:
            f.write(content)
            
        return dest_path

    @staticmethod
    def get_audio_path(storage_path_str: str) -> Path:
        """Retrieve and verify audio file on disk."""
        path = Path(storage_path_str)
        if not path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stored audio file could not be found on disk."
            )
        return path
