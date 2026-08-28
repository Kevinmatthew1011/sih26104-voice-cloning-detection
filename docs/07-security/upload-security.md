# Upload Security & Audio Validation: SIH26104

## 1. Streaming Upload Security (`backend/app/services/audio_validator.py`)

To prevent memory exhaustion attacks (where a malicious actor uploads a 10 GB file to trigger an Out-Of-Memory kernel crash), uploads are read in **64 KB streaming chunks**:

```python
async def validate_and_save_stream(upload_file: UploadFile) -> Tuple[str, str, int]:
    total_bytes = 0
    sha = hashlib.sha256()
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".tmp", dir=settings.UPLOAD_DIR)
    
    try:
        first_chunk = True
        while chunk := await upload_file.read(65536):
            total_bytes += len(chunk)
            if total_bytes > settings.MAX_FILE_SIZE_BYTES:
                raise HTTPException(status_code=413, detail="File exceeds maximum allowed size of 25MB")
            if first_chunk:
                validate_magic_bytes(chunk)
                first_chunk = False
            sha.update(chunk)
            temp_file.write(chunk)
    finally:
        temp_file.close()
```

---

## 2. Magic Byte Signatures

MIME types declared in HTTP headers are trivially forged. The validator inspects the first 16 bytes of the payload against known binary magic numbers:

| Format | Magic Byte Signature | Offset | Validated MIME |
| :--- | :--- | :--- | :--- |
| **WAV** | `RIFF....WAVE` | Byte 0–3, 8–11 | `audio/wav` |
| **OGG / Opus**| `OggS` (`\x4f\x67\x67\x53`) | Byte 0–3 | `audio/ogg` |
| **WebM / EBML**| `\x1a\x45\xdf\xa3` | Byte 0–3 | `audio/webm` |
| **FLAC** | `fLaC` (`\x66\x4c\x61\x43`) | Byte 0–3 | `audio/flac` |
| **MP3** | `ID3` (`\x49\x44\x33`) or Sync `\xff\xfb` / `\xff\xf3` | Byte 0–2 | `audio/mpeg` |
| **M4A / MP4** | `....ftypM4A ` or `....ftypmp42` | Byte 4–11 | `audio/mp4` |

If the magic bytes do not match an approved audio container, the request is terminated with **HTTP 400 Bad Request**.

---

## 3. Path Traversal Defense

Uploaded filenames are sanitized via `os.path.basename` and stripped of null bytes (`\x00`), relative path sequences (`../`, `..\\`), and shell control characters to guarantee that files are written exclusively inside the isolated `UPLOAD_DIR`.
