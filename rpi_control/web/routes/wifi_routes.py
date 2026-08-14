"""WiFi / ESP32 provisioning API routes.

- GET  /api/v1/wifi/status   获取 ESP32 / WiFi 状态
- POST /api/v1/wifi/connect  STA 连接现有热点
- POST /api/v1/wifi/hotspot  AP 创建软热点
- GET  /api/v1/wifi/scan     扫描周边 AP
- POST /api/v1/wifi/reset    ESP32 软复位
- DELETE /api/v1/wifi/state  清除持久化的配网状态
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from rpi_control.database.repository import WifiStateRepository, db_manager
from rpi_control.web.models.wifi import (
    WifiConnectRequest,
    WifiHotspotRequest,
    WifiScanResult,
    WifiStatus,
)
from rpi_control.web.services import auth_service
from rpi_control.web.services.wifi_service import wifi_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/wifi", tags=["wifi"])


@router.get("/status", response_model=WifiStatus)
async def wifi_status(_: Dict[str, Any] = Depends(auth_service.get_current_user)):
    """Get ESP32 / WiFi module status."""
    status = await wifi_service.get_status()
    return WifiStatus(
        connected=bool(status.get("connected")),
        mode=status.get("mode") or "unknown",
        ssid=status.get("ssid"),
        ip=status.get("ip"),
        mac=status.get("mac"),
        esp32_present=bool(status.get("esp32_present")),
        detail=status,
    )


@router.post("/connect")
async def wifi_connect(
    req: WifiConnectRequest,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Connect the device to an existing AP (STA mode)."""
    result = await wifi_service.connect_ap(req.ssid, req.password, timeout=req.timeout)
    return result


@router.post("/hotspot")
async def wifi_hotspot(
    req: WifiHotspotRequest,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Create a soft-AP hotspot (AP mode)."""
    result = await wifi_service.create_hotspot(req.ssid, req.password, channel=req.channel)
    return result


@router.get("/scan", response_model=List[WifiScanResult])
async def wifi_scan(_: Dict[str, Any] = Depends(auth_service.get_current_user)):
    """Scan nearby access points."""
    results = await wifi_service.scan()
    return [
        WifiScanResult(
            ssid=r.get("ssid", ""),
            rssi=int(r.get("rssi", 0)),
            auth=str(r.get("auth", "OPEN")),
            channel=int(r.get("channel", 0)),
        )
        for r in results
    ]


@router.post("/reset")
async def wifi_reset(_: Dict[str, Any] = Depends(auth_service.get_current_user)):
    """Soft reset the ESP32 WiFi module."""
    return await wifi_service.reset()


@router.delete("/state")
async def wifi_clear_state(
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Clear the persisted WiFi provisioning state from the database."""
    with db_manager.get_session() as session:
        cleared = WifiStateRepository.clear(session)
    return {
        "status": "ok",
        "message": "已清除持久化配网状态" if cleared else "无持久化状态可清除",
        "cleared": cleared,
    }
