"""WiFi / ESP32 provisioning service for the multi-end platform.

封装 ESP32Interface (AT 指令层) 与 WifiStateRepository (状态持久化):

- connect_ap   : STA 模式连接现有热点
- create_hotspot : AP 模式创建软热点
- scan         : 扫描周边 AP
- get_status   : 聚合 ESP32 / WiFi 状态并读取持久化记录
- 所有写操作成功后自动落库, 供 /api/v1/wifi/* 查询与恢复
"""

import logging
from typing import Any, Dict, List, Optional

from rpi_control.database.repository import WifiStateRepository, db_manager
from rpi_control.hardware.esp32_wifi import ESP32Interface
from rpi_control.utils.error_handler import (
    CommunicationError,
    HardwareError,
    error_notifier,
)

logger = logging.getLogger(__name__)


class WifiService:
    """High-level WiFi management service backed by the ESP32 AT module."""

    def __init__(self, esp32: Optional[ESP32Interface] = None) -> None:
        self._esp32 = esp32 or ESP32Interface()
        self._connected = False

    @property
    def esp32(self) -> ESP32Interface:
        return self._esp32

    async def _ensure_connected(self) -> None:
        """Lazily connect to the ESP32 module on first use."""
        if not self._esp32.is_connected:
            await self._esp32.connect()
            self._connected = True

    async def connect_ap(self, ssid: str, password: str,
                         timeout: float = 15.0) -> Dict[str, Any]:
        """Connect the device to an existing AP (STA mode)."""
        try:
            await self._ensure_connected()
            await self._esp32.join_ap(ssid, password, timeout=timeout)
            ip = await self._esp32.get_ip()
            with db_manager.get_session() as session:
                WifiStateRepository.save(
                    session, ssid=ssid, password=password,
                    mode="sta", ip=ip, esp32_connected=True,
                )
            logger.info(f"WiFi STA connected: {ssid} (ip={ip})")
            return {"status": "ok", "ssid": ssid, "ip": ip, "mode": "sta"}
        except (CommunicationError, HardwareError) as e:
            logger.warning(f"WiFi STA connect failed: {e}")
            return {"status": "error", "message": str(e), "ssid": ssid}

    async def create_hotspot(self, ssid: str, password: str = "",
                             channel: int = 6) -> Dict[str, Any]:
        """Create a soft-AP hotspot (AP mode)."""
        try:
            await self._ensure_connected()
            await self._esp32.create_ap(ssid, password, channel=channel)
            with db_manager.get_session() as session:
                WifiStateRepository.save(
                    session, ssid=ssid, password=password,
                    mode="ap", ip=None, esp32_connected=True,
                )
            logger.info(f"WiFi AP created: {ssid} (ch {channel})")
            return {"status": "ok", "ssid": ssid, "mode": "ap", "channel": channel}
        except (CommunicationError, HardwareError) as e:
            logger.warning(f"WiFi AP create failed: {e}")
            return {"status": "error", "message": str(e), "ssid": ssid}

    async def scan(self) -> List[Dict[str, Any]]:
        """Scan nearby access points."""
        try:
            await self._ensure_connected()
            return await self._esp32.scan()
        except (CommunicationError, HardwareError) as e:
            logger.warning(f"WiFi scan failed: {e}")
            return []

    async def get_status(self) -> Dict[str, Any]:
        """Aggregate ESP32 live status + persisted provisioning state."""
        live: Dict[str, Any] = {}
        try:
            await self._ensure_connected()
            live = await self._esp32.get_status()
        except (CommunicationError, HardwareError) as e:
            logger.warning(f"WiFi status query failed: {e}")
            live = {"esp32_present": False, "connected": False, "mode": "unknown"}

        saved: Optional[Dict[str, Any]] = None
        with db_manager.get_session() as session:
            state = WifiStateRepository.get(session)
            if state:
                saved = {
                    "ssid": state.ssid,
                    "mode": state.mode,
                    "ip": state.ip,
                    "esp32_connected": bool(state.esp32_connected),
                }

        # Merge: live values take priority, fallback to persisted state
        merged: Dict[str, Any] = {
            "connected": bool(live.get("connected", saved.get("esp32_connected", False) if saved else False)),
            "mode": live.get("mode") or (saved.get("mode") if saved else "unknown"),
            "ssid": live.get("ssid") or (saved.get("ssid") if saved else None),
            "ip": live.get("ip") or (saved.get("ip") if saved else None),
            "mac": live.get("mac"),
            "esp32_present": bool(live.get("esp32_present", False)),
            "persisted": saved,
        }
        return merged

    async def reset(self) -> Dict[str, Any]:
        """Soft reset the ESP32 module."""
        try:
            await self._ensure_connected()
            await self._esp32.reset()
            return {"status": "ok", "message": "ESP32 reset issued"}
        except (CommunicationError, HardwareError) as e:
            logger.warning(f"WiFi reset failed: {e}")
            return {"status": "error", "message": str(e)}


wifi_service = WifiService()
