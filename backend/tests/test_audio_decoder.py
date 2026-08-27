import io
import pytest
import numpy as np
import soundfile as sf
import av

from app.ml.audio_decoder import decode_audio, probe_audio_stream


def make_test_webm_opus_bytes(duration_seconds: float = 2.0, sample_rate: int = 48000) -> bytes:
    output_buffer = io.BytesIO()
    output_container = av.open(output_buffer, mode="w", format="webm")
    stream = output_container.add_stream("opus", rate=sample_rate)
    stream.layout = "mono"

    num_samples = int(duration_seconds * sample_rate)
    t = np.linspace(0, duration_seconds, num_samples, endpoint=False, dtype=np.float32)
    samples = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

    frame = av.AudioFrame.from_ndarray(samples.reshape(1, -1), format="flt", layout="mono")
    frame.sample_rate = sample_rate
    frame.pts = 0

    for packet in stream.encode(frame):
        output_container.mux(packet)
    for packet in stream.encode(None):
        output_container.mux(packet)
    output_container.close()

    return output_buffer.getvalue()


def test_decode_wav_to_16k_mono():
    bio = io.BytesIO()
    t = np.linspace(0, 1.0, 16000, endpoint=False, dtype=np.float32)
    sf.write(bio, 0.5 * np.sin(2 * np.pi * 440 * t), 16000, format="WAV")
    wav, sr = decode_audio(bio.getvalue(), target_sr=16000, mono=True)
    assert sr == 16000
    assert len(wav) == 16000
    assert wav.dtype == np.float32


def test_decode_ogg_to_16k_mono():
    bio = io.BytesIO()
    t = np.linspace(0, 1.0, 16000, endpoint=False, dtype=np.float32)
    sf.write(bio, 0.5 * np.sin(2 * np.pi * 440 * t), 16000, format="OGG")
    wav, sr = decode_audio(bio.getvalue(), target_sr=16000, mono=True)
    assert sr == 16000
    assert len(wav) == 16000


def test_decode_webm_opus_to_16k_mono():
    webm_bytes = make_test_webm_opus_bytes(duration_seconds=2.0, sample_rate=48000)
    assert webm_bytes[:4] == b"\x1a\x45\xdf\xa3"

    wav, sr = decode_audio(webm_bytes, target_sr=16000, mono=True)
    assert sr == 48000
    assert abs(len(wav) - 32000) < 500
    assert wav.dtype == np.float32


def test_decode_corrupt_payload_raises_value_error():
    with pytest.raises(ValueError):
        decode_audio(b"Corrupt data not audio", target_sr=16000)


def test_probe_audio_stream_extracts_metadata():
    webm_bytes = make_test_webm_opus_bytes(duration_seconds=1.5, sample_rate=48000)
    meta = probe_audio_stream(webm_bytes, ext=".webm")
    assert meta["sample_rate"] == 48000
    assert meta["channels"] == 1
    assert meta["duration"] is not None
    assert abs(meta["duration"] - 1.5) < 0.2


def test_probe_audio_stream_corrupt_payload_raises_value_error():
    with pytest.raises(ValueError):
        probe_audio_stream(b"invalid header bytes", ext=".webm")
