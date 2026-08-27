"""
Robust Unified Audio Decoder.

Decodes diverse audio containers and codecs (WAV, FLAC, OGG, WebM/Opus, M4A/AAC, MP3)
into standard float32 PCM waveforms resampled to 16,000 Hz mono for ML inference.
"""

import io
from pathlib import Path
from typing import Union, Tuple, Optional, Dict, Any
import numpy as np
import soundfile as sf
import librosa

try:
    import av
    HAS_AV = True
except ImportError:
    av = None
    HAS_AV = False


def decode_audio(
    audio_source: Union[str, Path, bytes, io.BytesIO, np.ndarray],
    target_sr: int = 16000,
    mono: bool = True,
) -> Tuple[np.ndarray, int]:
    """
    Decodes audio from a file path, raw bytes, or BytesIO into a float32 numpy array.

    Robust hierarchy:
    1. If already np.ndarray, convert to float32 mono if needed.
    2. Primary: soundfile.read (uncompressed WAV, FLAC, OGG, MP3).
    3. Secondary: PyAV (av.open) for WebM/Opus, M4A/AAC, and containerized browser audio.
    4. Tertiary: librosa.load.

    Returns:
        Tuple of (1D float32 waveform, native_sample_rate).
    """
    if isinstance(audio_source, np.ndarray):
        y = audio_source.astype(np.float32)
        if mono and y.ndim > 1:
            y = np.mean(y, axis=0 if y.shape[0] < y.shape[1] else 1)
        return y.flatten(), target_sr

    sf_error = None

    # Step 1: Try soundfile (fast C libsndfile for WAV, FLAC, OGG)
    try:
        if isinstance(audio_source, (str, Path)):
            p = Path(audio_source)
            if not p.exists():
                raise FileNotFoundError(f"Audio file not found: {p}")
            y, sr = sf.read(str(p), dtype="float32")
        elif isinstance(audio_source, (bytes, io.BytesIO)):
            bio = io.BytesIO(audio_source) if isinstance(audio_source, bytes) else audio_source
            bio.seek(0)
            if len(bio.getvalue()) == 0:
                raise ValueError("Audio buffer is empty (0 bytes).")
            y, sr = sf.read(bio, dtype="float32")
        else:
            raise TypeError(f"Unsupported audio source type: {type(audio_source)}")

        native_sr = int(sr)
        if mono and y.ndim > 1:
            y = np.mean(y, axis=1)

        if sr != target_sr:
            y = librosa.resample(y.flatten().astype(np.float32), orig_sr=sr, target_sr=target_sr)
        else:
            y = y.flatten().astype(np.float32)

        return y, native_sr

    except Exception as e:
        sf_error = e

    # Step 2: Fallback to PyAV (FFmpeg libavcodec bindings) for WebM, Opus, M4A, etc.
    if HAS_AV:
        try:
            if isinstance(audio_source, (str, Path)):
                p = Path(audio_source)
                if not p.exists():
                    raise FileNotFoundError(f"Audio file not found: {p}")
                container = av.open(str(p))
            elif isinstance(audio_source, (bytes, io.BytesIO)):
                bio = io.BytesIO(audio_source) if isinstance(audio_source, bytes) else audio_source
                bio.seek(0)
                container = av.open(bio)
            else:
                raise TypeError(f"Unsupported audio source type: {type(audio_source)}")

            audio_streams = [s for s in container.streams if s.type == "audio"]
            if not audio_streams:
                container.close()
                raise ValueError("No audio stream found in media container.")

            stream = audio_streams[0]
            native_sr = int(stream.rate) if stream.rate else target_sr

            pcm_chunks = []
            for frame in container.decode(stream):
                arr = frame.to_ndarray()
                if arr.ndim > 1:
                    chunk = np.mean(arr, axis=0) if arr.shape[0] > 1 else arr[0]
                else:
                    chunk = arr
                pcm_chunks.append(chunk.astype(np.float32))
            container.close()

            if not pcm_chunks:
                raise ValueError("Decoded audio stream contains zero frames.")

            y = np.concatenate(pcm_chunks, axis=0)
            if native_sr != target_sr:
                y = librosa.resample(y, orig_sr=native_sr, target_sr=target_sr)
            return y.flatten().astype(np.float32), native_sr

        except Exception as av_err:
            pass

    # Step 3: Fallback to librosa
    try:
        if isinstance(audio_source, (str, Path)):
            y, sr = librosa.load(str(audio_source), sr=target_sr, mono=mono)
            return y.flatten().astype(np.float32), int(sr)
        elif isinstance(audio_source, (bytes, io.BytesIO)):
            bio = io.BytesIO(audio_source) if isinstance(audio_source, bytes) else audio_source
            bio.seek(0)
            y, sr = librosa.load(bio, sr=target_sr, mono=mono)
            return y.flatten().astype(np.float32), int(sr)
    except Exception:
        pass

    raise ValueError(f"Audio stream could not be decoded: {str(sf_error)}")


def probe_audio_stream(content: bytes, ext: str = ".wav") -> Dict[str, Any]:
    """
    Validates that the audio payload contains decodable audio frames and extracts basic metadata.
    Raises ValueError if stream is corrupt or unparseable.
    """
    if len(content) == 0:
        raise ValueError("Audio content is empty (0 bytes).")

    # 1. Try soundfile
    try:
        bio = io.BytesIO(content)
        info = sf.info(bio)
        if info.frames > 0 and info.samplerate > 0:
            return {
                "sample_rate": int(info.samplerate),
                "channels": int(info.channels),
                "duration": float(info.duration),
                "frames": int(info.frames),
            }
    except Exception:
        pass

    # 2. Try PyAV
    if HAS_AV:
        try:
            container = av.open(io.BytesIO(content))
            audio_streams = [s for s in container.streams if s.type == "audio"]
            if not audio_streams:
                container.close()
                raise ValueError("No audio stream found in container.")
            stream = audio_streams[0]
            sr = int(stream.rate) if stream.rate else 16000
            channels = int(stream.channels) if stream.channels else 1
            duration = None
            if stream.duration is not None and stream.time_base is not None:
                duration = float(stream.duration * stream.time_base)
            elif container.duration is not None:
                duration = float(container.duration) / 1_000_000.0

            container.close()
            if sr > 0 and channels > 0:
                return {
                    "sample_rate": sr,
                    "channels": channels,
                    "duration": duration,
                    "frames": None,
                }
        except Exception as e:
            raise ValueError(f"Container audio stream failed to decode: {e}") from e

    raise ValueError("Audio stream is corrupt or contains no decodable frames.")
