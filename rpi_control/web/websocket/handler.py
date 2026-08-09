"""WebSocket handler for real-time telemetry."""

import asyncio
import json
import logging
import random
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# Maximum number of concurrent WebSocket connections
MAX_CLIENTS = 100


class WebSocketManager:
    """Manages WebSocket client connections and message broadcasting.

    Enforces a maximum client limit to prevent resource exhaustion.
    """

    def __init__(self, max_clients: int = MAX_CLIENTS):
        self._clients: Dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()
        self._max_clients = max_clients

    async def connect(self, websocket: WebSocket) -> str:
        """Register a new WebSocket client.

        Raises:
            RuntimeError: If the maximum number of clients is reached.
        """
        await websocket.accept()
        async with self._lock:
            if len(self._clients) >= self._max_clients:
                await websocket.close(code=1013, reason="Max clients reached")
                raise RuntimeError(f"Max clients ({self._max_clients}) reached, connection rejected")
            client_id = str(uuid.uuid4())
            self._clients[client_id] = websocket
        logger.info(f"WebSocket client connected: {client_id} (total: {len(self._clients)})")
        return client_id

    async def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket client."""
        async with self._lock:
            client_id = None
            for cid, ws in self._clients.items():
                if ws == websocket:
                    client_id = cid
                    break
            if client_id:
                del self._clients[client_id]
                logger.info(f"WebSocket client disconnected: {client_id} (total: {len(self._clients)})")

    async def broadcast(self, message: Dict[str, Any]):
        """Send a message to all connected clients."""
        async with self._lock:
            disconnected = []
            for client_id, websocket in self._clients.items():
                try:
                    await websocket.send_json(message)
                except Exception:
                    disconnected.append(client_id)

            for client_id in disconnected:
                del self._clients[client_id]
                logger.warning(f"Removed disconnected client: {client_id}")

    async def send_to_client(self, client_id: str, message: Dict[str, Any]):
        """Send a message to a specific client."""
        async with self._lock:
            websocket = self._clients.get(client_id)
            if websocket:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to send to client {client_id}: {e}")
                    del self._clients[client_id]

    @property
    def client_count(self) -> int:
        return len(self._clients)


ws_manager = WebSocketManager()


class TelemetryStream:
    """Periodic telemetry data pusher for WebSocket clients."""

    def __init__(self, interval: float = 0.5):
        self.interval = interval
        self._streaming = False
        self._task: Optional[asyncio.Task] = None

    async def start_streaming(self):
        """Start periodic telemetry push to all clients."""
        if self._streaming:
            return
        self._streaming = True
        self._task = asyncio.create_task(self._stream_loop())
        logger.info(f"Telemetry streaming started (interval: {self.interval}s)")

    async def stop_streaming(self):
        """Stop telemetry streaming."""
        self._streaming = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Telemetry streaming stopped")

    async def _stream_loop(self):
        """Main telemetry streaming loop."""
        while self._streaming:
            try:
                await self.push_arm_status()
                await self.push_sensor_data()
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Telemetry stream error: {e}")
                await asyncio.sleep(1.0)

    async def push_arm_status(self):
        """Send current arm joint positions."""
        await ws_manager.broadcast({
            "type": "arm_status",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "joint_positions": {
                    "joint_1": 0.0,
                    "joint_2": 0.0,
                    "joint_3": 0.0,
                    "joint_4": 0.0,
                    "joint_5": 0.0,
                    "joint_6": 0.0,
                },
                "ee_pose": {"x": 200.0, "y": 0.0, "z": 150.0, "roll": 0.0, "pitch": 0.0, "yaw": 0.0},
                "is_moving": False,
                "gripper_state": "open",
            },
        })

    async def push_sensor_data(self):
        """Send current sensor readings."""
        import random
        await ws_manager.broadcast({
            "type": "sensor_data",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "temperature": round(25.0 + random.uniform(-1.0, 1.0), 1),
                "humidity": round(50.0 + random.uniform(-5.0, 5.0), 1),
                "distance": round(random.uniform(100.0, 500.0), 1),
                "voltage": round(12.0 + random.uniform(-0.2, 0.2), 2),
                "current": round(random.uniform(0.5, 3.0), 2),
            },
        })

    async def push_task_progress(self, task_id: str, progress: Dict[str, Any]):
        """Send task progress update."""
        await ws_manager.broadcast({
            "type": "task_progress",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task_id": task_id,
            "data": progress,
        })

    async def push_camera_frame(self, frame_data: str):
        """Send latest camera snapshot (base64)."""
        await ws_manager.broadcast({
            "type": "camera_frame",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": frame_data,
        })

    async def push_safety_alerts(self, alerts: List[Dict[str, Any]]):
        """Send safety warnings or alerts."""
        await ws_manager.broadcast({
            "type": "safety_alert",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "alerts": alerts,
        })


telemetry_stream = TelemetryStream()