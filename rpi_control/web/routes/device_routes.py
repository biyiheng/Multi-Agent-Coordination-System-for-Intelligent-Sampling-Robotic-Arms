"""Device registry API routes (multi-end device center).

多端互通: App / 小程序 / Web / 硬件 (RPi / ESP32 / STM32 / OpenMV) 统一注册到
设备中心, 通过 device_id + client_type 路由遥测与命令。

- POST /api/v1/devices/register  注册 / 心跳上报
- GET  /api/v1/devices           设备列表 (可按类型/状态过滤)
- GET  /api/v1/devices/{id}      单个设备详情
- POST /api/v1/devices/{id}/offline  标记设备离线
"""

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from rpi_control.database.repository import (
    DeviceRepository,
    db_manager,
)
from rpi_control.web.models.device import DeviceInfo, DeviceRegisterRequest
from rpi_control.web.services import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])


def _to_device_info(device) -> Dict[str, Any]:
    """Convert a DeviceModel row into a serializable dict."""
    extra = {}
    if device.extra_json:
        try:
            extra = json.loads(device.extra_json)
        except (ValueError, TypeError):
            extra = {}
    return {
        "id": device.id,
        "name": device.name,
        "device_type": device.device_type,
        "client_type": device.client_type,
        "mac": device.mac,
        "ip": device.ip,
        "status": device.status,
        "firmware_version": device.firmware_version,
        "extra": extra,
        "last_seen": device.last_seen,
    }


@router.post("/register", response_model=DeviceInfo)
async def register_device(
    req: DeviceRegisterRequest,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Register (or heart-beat update) a client/hardware device."""
    device_id = req.device_id or f"{req.client_type}-{req.device_type}-{req.mac or 'anon'}"
    data = req.model_dump()
    data["online"] = True
    with db_manager.get_session() as session:
        device = DeviceRepository.upsert(session, device_id, data)
        session.refresh(device)
        info = _to_device_info(device)
    logger.info(f"Device registered/heartbeat: {device_id} ({req.client_type}/{req.device_type})")
    return info


@router.get("", response_model=List[DeviceInfo])
async def list_devices(
    client_type: Optional[str] = Query(None, description="app/miniprogram/web/hardware"),
    status: Optional[str] = Query(None, description="online/offline"),
    limit: int = Query(200, ge=1, le=1000),
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """List all registered devices, optionally filtered."""
    with db_manager.get_session() as session:
        rows = DeviceRepository.list_all(
            session, client_type=client_type, status=status, limit=limit
        )
        return [_to_device_info(r) for r in rows]


@router.get("/{device_id}", response_model=DeviceInfo)
async def get_device(
    device_id: str,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Get a single device's details."""
    with db_manager.get_session() as session:
        device = DeviceRepository.get(session, device_id)
        if not device:
            raise HTTPException(status_code=404, detail=f"设备不存在: {device_id}")
        return _to_device_info(device)


@router.post("/{device_id}/offline")
async def mark_offline(
    device_id: str,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Manually mark a device as offline."""
    with db_manager.get_session() as session:
        DeviceRepository.set_offline(session, device_id)
    logger.info(f"Device marked offline: {device_id}")
    return {"status": "ok", "device_id": device_id, "status": "offline"}


@router.put("/{device_id}")
async def update_device(
    device_id: str,
    updates: Dict[str, Any],
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Update device metadata (name, status, firmware, extra, etc.)."""
    with db_manager.get_session() as session:
        device = DeviceRepository.update(session, device_id, updates)
        if not device:
            raise HTTPException(status_code=404, detail=f"设备不存在: {device_id}")
        return _to_device_info(device)


@router.delete("/{device_id}")
async def delete_device(
    device_id: str,
    admin: Dict[str, Any] = Depends(auth_service.require_admin),
):
    """Unregister a device (admin only)."""
    with db_manager.get_session() as session:
        if not DeviceRepository.delete(session, device_id):
            raise HTTPException(status_code=404, detail=f"设备不存在: {device_id}")
    logger.info(f"Device unregistered: {device_id}")
    return {"status": "ok", "message": f"设备 {device_id} 已注销"}
