import pytest
from starlette.testclient import TestClient
from app.main import app


def test_webrtc_signaling_room_relay():
    """Verify that WebRTC signaling relays messages between two peers in the same room."""
    client = TestClient(app)
    room_id = "test-room-42"

    with client.websocket_connect(f"/api/v1/webrtc/signal/{room_id}") as peer_a:
        with client.websocket_connect(f"/api/v1/webrtc/signal/{room_id}") as peer_b:
            # Peer A sends offer
            peer_a.send_text('{"type": "offer", "sdp": "dummy-offer-sdp", "role": "caller"}')
            msg_b = peer_b.receive_text()
            assert "dummy-offer-sdp" in msg_b
            assert '"type": "offer"' in msg_b

            # Peer B sends answer
            peer_b.send_text('{"type": "answer", "sdp": "dummy-answer-sdp", "role": "protected_user"}')
            msg_a = peer_a.receive_text()
            assert "dummy-answer-sdp" in msg_a
            assert '"type": "answer"' in msg_a
