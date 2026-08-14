"""Multi-end device hub: WebSocket message routing between all clients.

多端互通中枢: App / 小程序 / Web / 硬件 (RPi / ESP32 / STM32 / OpenMV)
通过 /ws/hub 建立长连接, 统一在此进行:

- 设备注册: 首个 hello 消息绑定 device_id + client_type, 写入设备中心 (online)
- 命令路由: 任意端可向 target 端 (device_id / "all" / "hardware") 下发命令
- 遥测广播: 硬件遥测广播给所有订阅端
- 离线回收: 断连时自动标记设备 offline

消息协议 (JSON):
    Client -> Hub:
      {"type":"hello",   "device_id": "...", "client_type":"app", "name":"...",
       "device_type":"...", "role":"controller|observer"}
      {"type":"command", "target":"<device_id>|all|hardware", "action":"arm.move",
       "payload": {...}, "seq": 123}
      {"type":"ping"}
    Hub -> Client:
      {"type":"welcome", "client_id":"...", "device_id":"..."}
      {"type":"command_ack", "seq":123, "status":"ok"}
      {"type":"command", "from":"<device_id>", "action":"...", "payload":{...}}
      {"type":"telemetry", "from":"<device_id>", "data":{...}}
      {"type":"device_status", "device_id":"...", "status":"online|offline"}
      {"type":"pong"}
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

from rpi_control.database.repository import DeviceRepository, db_manager
from rpi_control.web.websocket.handler import ws_manager

logger = logging.getLogger(__name__)

# Role-based command targets
ROLE_CONTROLLER = "controller"
ROLE_OBSERVER = "observer"

MAX_HUB_CLIENTS = 256


class DeviceHub:
    """Multi-end message router with device registry integration."""

    def __init__(self, max_clients: int = MAX_HUB_CLIENTS) -> None:
        self._clients: Dict[str, Dict[str, Any]] = {}  # client_id -> {ws, device_id, client_type, role, ...}
        self._lock = asyncio.Lock()
        self._max_clients = max_clients

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self, websocket: WebSocket) -> str:
        """Accept a new hub connection; returns a client_id."""
        await websocket.accept()
        async with self._lock:
            if len(self._clients) >= self._max_clients:
                await websocket.close(code=1013, reason="Max hub clients reached")
                raise RuntimeError("Max hub clients reached")
            client_id = str(uuid.uuid4())
            self._clients[client_id] = {"ws": websocket, "device_id": None,
                                        "client_type": "web", "role": ROLE_OBSERVER}
        logger.info(f"Hub client connected: {client_id} (total: {len(self._clients)})")
        return client_id

    async def _bind_device(self, client_id: str, hello: Dict[str, Any]) -> None:
        """Bind a device_id to a client connection and register in the DB."""
        device_id = hello.get("device_id") or f"client-{client_id[:8]}"
        client_type = hello.get("client_type", "web")
        device_type = hello.get("device_type", "generic")
        role = hello.get("role", ROLE_OBSERVER)
        name = hello.get("name", device_id)

        async with self._lock:
            entry = self._clients.get(client_id)
            if not entry:
                return
            entry["device_id"] = device_id
            entry["client_type"] = client_type
            entry["device_type"] = device_type
            entry["role"] = role
            entry["name"] = name

        # Register / heart-beat in the device center
        with db_manager.get_session() as session:
            DeviceRepository.upsert(session, device_id, {
                "name": name,
                "device_type": device_type,
                "client_type": client_type,
                "online": True,
            })

        logger.info(f"Hub bound {client_id} -> {device_id} ({client_type}/{device_type}, role={role})")

    async def disconnect(self, client_id: str, websocket: WebSocket) -> None:
        """Remove a client and mark its device offline."""
        device_id = None
        async with self._lock:
            entry = self._clients.pop(client_id, None)
            if entry:
                device_id = entry.get("device_id")
        logger.info(f"Hub client disconnected: {client_id} (total: {len(self._clients)})")

        if device_id:
            with db_manager.get_session() as session:
                DeviceRepository.set_offline(session, device_id)
            await self.broadcast({"type": "device_status",
                                  "device_id": device_id, "status": "offline"})

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Send a message to all hub clients."""
        async with self._lock:
            targets = list(self._clients.values())
        for entry in targets:
            try:
                await entry["ws"].send_json(message)
            except Exception:
                pass

    async def send_to(self, client_id: str, message: Dict[str, Any]) -> bool:
        """Send a message to a specific hub client."""
        async with self._lock:
            entry = self._clients.get(client_id)
            if not entry:
                return False
            try:
                await entry["ws"].send_json(message)
                return True
            except Exception:
                return False

    async def route_command(self, sender_id: str, msg: Dict[str, Any]) -> None:
        """Route a command message to its target device(s)."""
        target = msg.get("target", "all")
        action = msg.get("action", "")
        payload = msg.get("payload", {})
        seq = msg.get("seq")

        async with self._lock:
            entries = list(self._clients.values())
            sender = self._clients.get(sender_id, {})

        # 用有意义的 device_id 标识发送方, 便于接收端识别来源
        sender_device_id = sender.get("device_id") or sender_id

        sent_to: Set[str] = set()
        for entry in entries:
            dev_id = entry.get("device_id")
            ctype = entry.get("client_type", "")
            if not dev_id:
                continue
            if target == "all":
                match = True
            elif target == "hardware":
                match = ctype == "hardware"
            else:
                match = dev_id == target
            if not match:
                continue
            try:
                await entry["ws"].send_json({
                    "type": "command",
                    "from": sender_device_id,
                    "action": action,
                    "payload": payload,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                sent_to.add(dev_id)
            except Exception as e:
                logger.warning(f"Hub route to {dev_id} failed: {e}")

        # Acknowledge to the sender
        if sender_id and seq is not None:
            await self.send_to(sender_id, {
                "type": "command_ack",
                "seq": seq,
                "status": "ok" if sent_to else "no_target",
                "targets": list(sent_to),
            })

    async def forward_telemetry(self, sender_id: str, data: Dict[str, Any]) -> None:
        """Broadcast a telemetry payload from a device to all observers."""
        async with self._lock:
            sender = self._clients.get(sender_id, {})
        await self.broadcast({
            "type": "telemetry",
            "from": sender.get("device_id", sender_id),
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def get_devices(self) -> Dict[str, Dict[str, Any]]:
        """Return a snapshot of connected devices (id -> meta)."""
        result = {}
        for entry in self._clients.values():
            dev_id = entry.get("device_id")
            if dev_id:
                result[dev_id] = {
                    "client_type": entry.get("client_type"),
                    "device_type": entry.get("device_type"),
                    "role": entry.get("role"),
                    "name": entry.get("name"),
                }
        return result


device_hub = DeviceHub()


async def handle_hub_connection(websocket: WebSocket) -> None:
    """WebSocket endpoint handler for the multi-end device hub."""
    client_id = await device_hub.connect(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except (ValueError, TypeError):
                await device_hub.send_to(client_id, {"type": "error", "message": "invalid JSON"})
                continue

            mtype = msg.get("type", "")
            if mtype == "hello":
                await device_hub._bind_device(client_id, msg)
                dev_id = msg.get("device_id")
                await device_hub.send_to(client_id, {
                    "type": "welcome",
                    "client_id": client_id,
                    "device_id": dev_id,
                    "message": "Hub ready",
                })
                await device_hub.broadcast({
                    "type": "device_status",
                    "device_id": dev_id,
                    "status": "online",
                })
            elif mtype == "command":
                await device_hub.route_command(client_id, msg)
            elif mtype == "telemetry":
                await device_hub.forward_telemetry(client_id, msg.get("data", {}))
            elif mtype == "ping":
                await device_hub.send_to(client_id, {"type": "pong"})
            else:
                await device_hub.send_to(client_id, {"type": "error",
                                                     "message": f"unknown type: {mtype}"})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Hub handler error for {client_id}: {e}")
    finally:
        await device_hub.disconnect(client_id, websocket)
