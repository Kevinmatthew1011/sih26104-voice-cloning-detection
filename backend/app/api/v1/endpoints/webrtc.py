"""
WebRTC Signaling Endpoints for Real Multi-Client VoIP Calling.

Provides WebSocket-based room signaling (SDP offer/answer and ICE candidate exchange)
between Tab A (Caller) and Tab B (Protected User).
"""

import logging
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()


class WebRTCSignalingManager:
    """Manages active WebRTC peers in ephemeral rooms for call negotiation."""

    def __init__(self):
        self.rooms: Dict[str, Set[WebSocket]] = {}

    async def connect(self, room_id: str, websocket: WebSocket):
        await websocket.accept()
        if room_id not in self.rooms:
            self.rooms[room_id] = set()
        self.rooms[room_id].add(websocket)
        logger.info("Peer joined signaling room '%s' (room size: %d)", room_id, len(self.rooms[room_id]))

    def disconnect(self, room_id: str, websocket: WebSocket):
        if room_id in self.rooms:
            self.rooms[room_id].discard(websocket)
            if not self.rooms[room_id]:
                del self.rooms[room_id]
        logger.info("Peer left signaling room '%s'", room_id)

    async def broadcast(self, room_id: str, sender: WebSocket, message: str):
        if room_id in self.rooms:
            for peer in list(self.rooms[room_id]):
                if peer != sender:
                    try:
                        await peer.send_text(message)
                    except Exception as e:
                        logger.warning("Failed forwarding signaling message in room '%s': %s", room_id, e)


signaling_manager = WebRTCSignalingManager()


@router.websocket("/signal/{room_id}")
async def webrtc_signal_endpoint(websocket: WebSocket, room_id: str):
    """
    WebSocket signaling channel for room_id.
    Relays SDP offers, SDP answers, and ICE candidate events between peers.
    """
    clean_room_id = room_id.strip().lower() or "voiceguard-test"
    await signaling_manager.connect(clean_room_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await signaling_manager.broadcast(clean_room_id, websocket, data)
    except WebSocketDisconnect:
        signaling_manager.disconnect(clean_room_id, websocket)
    except Exception as exc:
        logger.warning("WebRTC signaling connection ended with exception: %s", exc)
        signaling_manager.disconnect(clean_room_id, websocket)
