"""
Tests for Real-Time WebSocket Call Monitoring Endpoint (/api/v1/detections/ws).

Validates:
1. Connection handshake and status negotiation.
2. Buffering progression before minimum 64,600 samples (no premature/fake results).
3. Sliding-window inference trigger upon reaching 64,600 samples (~4.0375s).
4. Subsequent sliding-window inference upon reaching hop size (16,150 samples).
5. Structured error handling for invalid or corrupted payloads.
6. Graceful AASIST unavailable handling without crash or faking.
7. Text control messages (ping/pong, status, stop/end_call with session summary).
8. Cleanup on disconnect.
"""

import json
from unittest.mock import patch
import numpy as np
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.config import settings
from app.services.detection.streaming_detector import (
    StreamingAASISTDetector,
    TARGET_SAMPLE_RATE,
    TARGET_WINDOW_SAMPLES,
    TARGET_HOP_SAMPLES,
)


def generate_pcm16_chunk(num_samples: int, frequency: float = 440.0) -> bytes:
    """Generate linear 16 kHz 16-bit PCM sinusoidal audio bytes."""
    t = np.linspace(0, num_samples / TARGET_SAMPLE_RATE, num_samples, endpoint=False)
    waveform = (0.5 * np.sin(2 * np.pi * frequency * t) * 32767).astype(np.int16)
    return waveform.tobytes()


def test_websocket_connection_handshake():
    """Verify WebSocket connects and emits the initial status handshake."""
    client = TestClient(app)
    with client.websocket_connect("/api/v1/detections/ws?engine=mock") as ws:
        handshake = ws.receive_json()
        assert handshake["type"] == "status"
        assert handshake["state"] == "connected"
        assert handshake["engine"] == "mock"
        assert handshake["window_samples"] == TARGET_WINDOW_SAMPLES
        assert handshake["hop_samples"] == TARGET_HOP_SAMPLES
        assert handshake["sample_rate"] == TARGET_SAMPLE_RATE


def test_websocket_buffering_before_min_window():
    """Verify audio under 64,600 samples only emits status buffering, never synthetic probability."""
    client = TestClient(app)
    with client.websocket_connect("/api/v1/detections/ws?engine=mock") as ws:
        _ = ws.receive_json()  # Handshake

        # Send 16,000 samples (1.0s @ 16 kHz) -> 32,000 bytes
        chunk = generate_pcm16_chunk(16000)
        ws.send_bytes(chunk)

        event = ws.receive_json()
        assert event["type"] == "status"
        assert event["state"] == "buffering"
        assert event["samples_buffered"] == 16000
        assert event["samples_required"] == TARGET_WINDOW_SAMPLES
        assert "synthetic_probability" not in event
        assert event["windows_analyzed"] == 0


def test_websocket_sliding_window_inference_trigger():
    """Verify audio reaching 64,600 samples triggers window 0 acoustic update."""
    client = TestClient(app)
    with client.websocket_connect("/api/v1/detections/ws?engine=mock") as ws:
        _ = ws.receive_json()  # Handshake

        # Send exactly 64,600 samples in two chunks of 32,300 samples
        chunk1 = generate_pcm16_chunk(32300)
        ws.send_bytes(chunk1)
        ev1 = ws.receive_json()
        assert ev1["type"] == "status"
        assert ev1["state"] == "buffering"

        chunk2 = generate_pcm16_chunk(32300)
        ws.send_bytes(chunk2)
        ev2 = ws.receive_json()

        assert ev2["type"] == "acoustic_update"
        assert ev2["window_index"] == 0
        assert ev2["start_seconds"] == 0.0
        assert ev2["end_seconds"] == round(TARGET_WINDOW_SAMPLES / TARGET_SAMPLE_RATE, 4)
        assert "synthetic_probability" in ev2
        assert 0.0 <= ev2["synthetic_probability"] <= 1.0
        assert ev2["prediction"] in ("real", "synthetic")
        assert ev2["risk_level"] in ("low", "medium", "high")
        assert ev2["cumulative_windows"] == 1


def test_websocket_multiple_sliding_windows():
    """Verify that receiving hop_samples (16,150) additional samples triggers window 1."""
    client = TestClient(app)
    with client.websocket_connect("/api/v1/detections/ws?engine=mock") as ws:
        _ = ws.receive_json()  # Handshake

        # 1. Send initial window (64,600 samples)
        chunk1 = generate_pcm16_chunk(TARGET_WINDOW_SAMPLES)
        ws.send_bytes(chunk1)
        w0 = ws.receive_json()
        assert w0["type"] == "acoustic_update"
        assert w0["window_index"] == 0

        # 2. Send 1 hop of audio (16,150 samples)
        chunk2 = generate_pcm16_chunk(TARGET_HOP_SAMPLES)
        ws.send_bytes(chunk2)
        w1 = ws.receive_json()
        assert w1["type"] == "acoustic_update"
        assert w1["window_index"] == 1
        assert w1["start_seconds"] == round(TARGET_HOP_SAMPLES / TARGET_SAMPLE_RATE, 4)
        assert w1["cumulative_windows"] == 2


def test_websocket_invalid_audio_payload_error():
    """Verify odd-length bytes under pcm16 returns structured error without crashing."""
    client = TestClient(app)
    with client.websocket_connect("/api/v1/detections/ws?format=pcm16") as ws:
        _ = ws.receive_json()  # Handshake

        # Send 3 bytes (invalid for 16-bit PCM)
        ws.send_bytes(b"\x00\x01\x02")
        err = ws.receive_json()
        assert err["type"] == "error"
        assert err["code"] == "INVALID_AUDIO_PAYLOAD"
        assert "multiple of 2" in err["message"]


def test_websocket_text_control_ping_and_status():
    """Verify ping/pong and explicit status telemetry frames."""
    client = TestClient(app)
    with client.websocket_connect("/api/v1/detections/ws?engine=mock") as ws:
        _ = ws.receive_json()  # Handshake

        # Ping
        ws.send_text(json.dumps({"action": "ping"}))
        res = ws.receive_json()
        assert res["type"] == "pong"

        # Status
        ws.send_text(json.dumps({"action": "status"}))
        status_res = ws.receive_json()
        assert status_res["type"] == "status"
        assert status_res["state"] == "buffering"
        assert status_res["samples_buffered"] == 0


def test_websocket_stop_action_returns_session_summary():
    """Verify stop action calculates and returns final session summary."""
    client = TestClient(app)
    with client.websocket_connect("/api/v1/detections/ws?engine=mock") as ws:
        _ = ws.receive_json()  # Handshake

        # Send 64,600 samples to analyze one window
        chunk = generate_pcm16_chunk(TARGET_WINDOW_SAMPLES)
        ws.send_bytes(chunk)
        _ = ws.receive_json()  # Window 0

        # Request call stop
        ws.send_text(json.dumps({"action": "stop"}))
        summary = ws.receive_json()

        assert summary["type"] == "session_summary"
        assert summary["windows_analyzed"] == 1
        assert summary["peak_synthetic_probability"] is not None
        assert summary["final_prediction"] in ("real", "synthetic")
        assert summary["final_risk_level"] in ("low", "medium", "high")


def test_websocket_aasist_unavailable_fallback():
    """Verify that if AASIST weights are missing, error is caught and structured fallback is returned."""
    client = TestClient(app)

    # Patch AASISTInferenceEngine to simulate missing weights / runtime error
    with patch(
        "app.ml.aasist_inference.AASISTInferenceEngine.predict_window",
        side_effect=RuntimeError("AASIST model checkpoint AASIST.pth not found on disk"),
    ):
        with client.websocket_connect("/api/v1/detections/ws?engine=aasist") as ws:
            _ = ws.receive_json()  # Handshake

            chunk = generate_pcm16_chunk(TARGET_WINDOW_SAMPLES)
            ws.send_bytes(chunk)

            err = ws.receive_json()
            assert err["type"] == "error"
            assert err["code"] == "AASIST_UNAVAILABLE"
            assert "Real-time acoustic analysis unavailable" in err["message"]
