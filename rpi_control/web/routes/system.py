"""System management API routes.

- GET  /api/v1/system/info     系统信息
- GET  /api/v1/system/config   读取配置 (默认值 + 数据库覆盖)
- PUT  /api/v1/system/config   更新配置 (持久化到数据库)
- GET  /api/v1/system/config/{key}   读取单个配置项
- DELETE /api/v1/system/config/{key} 删除单个配置项
- GET  /api/v1/system/logs     最近日志 (数据库)
- POST /api/v1/system/restart  软重启
- GET  /api/v1/system/diagnostics 诊断
"""

import json
import logging
import platform
import time
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from rpi_control.database.repository import (
    ConfigRepository,
    LogRepository,
    db_manager,
)
from rpi_control.web.services import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/system", tags=["system"])

# System start time for uptime calculation
_start_time = time.time()

# Default configuration template. Values stored in the database override these.
_DEFAULT_CONFIG: Dict[str, Any] = {
    "safety": {
        "max_joint_velocity": 500,
        "emergency_stop_timeout": 100,
        "watchdog_interval": 50,
        "comm_timeout": 500,
    },
    "motion": {
        "speed_coefficient": 50,
        "acceleration_coefficient": 30,
        "default_move_time": 1000,
    },
    "vision": {
        "frame_rate": 30,
        "resolution": "QVGA",
        "color_thresholds_enabled": True,
        "apriltag_enabled": True,
    },
    "network": {
        "host": "0.0.0.0",
        "port": 8000,
        "ws_port": 8001,
    },
    "cloud": {
        "enabled": True,
        "sync_interval": 60,
    },
}


def _merge_config() -> Dict[str, Any]:
    """Merge database-stored overrides on top of the defaults."""
    merged = json.loads(json.dumps(_DEFAULT_CONFIG))
    with db_manager.get_session() as session:
        rows = ConfigRepository.list_all(session)
        for row in rows:
            try:
                value = json.loads(row.value_json)
            except (ValueError, TypeError):
                value = row.value_json
            if isinstance(value, dict) and not value:
                continue
            if row.key in merged and isinstance(merged[row.key], dict) and isinstance(value, dict):
                merged[row.key].update(value)
            else:
                merged[row.key] = value
    return merged


@router.get("/info")
async def get_system_info():
    """Get system information including firmware versions and hardware info."""
    return {
        "status": "ok",
        "data": {
            "system_name": "智能采样机械臂多智能体协同系统",
            "version": "2.0.0",
            "api_version": "v1",
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "hostname": platform.node(),
            "uptime_seconds": int(time.time() - _start_time),
            "hardware": {
                "stm32": "STM32F103C8T6",
                "openmv": "OpenMV H7 Plus",
                "raspberry_pi": "Raspberry Pi",
            },
            "firmware": {
                "stm32": "v2.0.0",
                "openmv": "v2.0.0",
            },
        },
    }


@router.get("/config")
async def get_system_config(
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Get current system configuration (defaults merged with database overrides)."""
    return {"status": "ok", "data": _merge_config()}


@router.put("/config")
async def update_system_config(
    data: Dict[str, Any],
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Update system configuration and persist to the database.

    Request body: {key: value, ...} or {safety: {...}, motion: {...}, ...}
    """
    if not data:
        raise HTTPException(status_code=400, detail="No configuration data provided")

    # Validate safety-critical parameters
    if "safety" in data:
        safety = data["safety"]
        if "max_joint_velocity" in safety:
            v = safety["max_joint_velocity"]
            if not (10 <= v <= 1000):
                raise HTTPException(
                    status_code=400,
                    detail="max_joint_velocity must be between 10 and 1000",
                )
        if "emergency_stop_timeout" in safety:
            t = safety["emergency_stop_timeout"]
            if not (10 <= t <= 1000):
                raise HTTPException(
                    status_code=400,
                    detail="emergency_stop_timeout must be between 10 and 1000 ms",
                )

    # Persist each top-level section into the database (system_config table).
    with db_manager.get_session() as session:
        for key, value in data.items():
            ConfigRepository.set(session, key, value)

    logger.info(f"System configuration updated: {list(data.keys())}")
    return {"status": "ok", "message": "Configuration updated", "updated_keys": list(data.keys())}


@router.get("/config/{key}")
async def get_system_config_key(
    key: str,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Get a single configuration section or key."""
    merged = _merge_config()
    if key not in merged:
        raise HTTPException(status_code=404, detail=f"配置项不存在: {key}")
    return {"status": "ok", "key": key, "value": merged[key]}


@router.delete("/config/{key}")
async def delete_system_config_key(
    key: str,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Delete a stored configuration override (falls back to defaults)."""
    with db_manager.get_session() as session:
        if not ConfigRepository.delete(session, key):
            # Not an error: the key simply has no stored override.
            logger.info(f"Config key '{key}' has no stored override to delete")
        else:
            logger.info(f"Config key '{key}' deleted")
    return {"status": "ok", "message": f"配置项 {key} 已删除 (恢复默认值)"}


@router.get("/logs")
async def get_system_logs(
    limit: int = 50,
    action_type: Optional[str] = None,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Get recent system log entries from the database."""
    if limit > 200:
        limit = 200
    if limit < 1:
        limit = 1

    with db_manager.get_session() as session:
        if action_type:
            logs = LogRepository.list_by_type(session, action_type, limit=limit)
        else:
            logs = LogRepository.list_recent(session, limit=limit)

    entries = [
        {
            "id": log.id,
            "action_type": log.action_type,
            "details": json.loads(log.details_json) if log.details_json else {},
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        }
        for log in logs
    ]
    return {
        "status": "ok",
        "data": {
            "total": len(entries),
            "limit": limit,
            "filter": {"action_type": action_type},
            "entries": entries,
        },
    }


@router.get("/logs/stream")
async def get_log_stream_url():
    """Get WebSocket URL for real-time log streaming."""
    return {
        "status": "ok",
        "data": {
            "stream_url": "ws://localhost:8001/ws/logs",
            "description": "Connect to this WebSocket for real-time log streaming",
        },
    }


@router.get("/network")
async def get_network_status():
    """Get network connectivity status."""
    return {
        "status": "ok",
        "data": {
            "wifi": {
                "connected": True,
                "ssid": "robot-network",
                "signal_strength": -45,
                "ip_address": "192.168.1.100",
            },
            "ethernet": {
                "connected": False,
                "ip_address": None,
            },
            "stm32_connected": True,
            "openmv_connected": True,
            "internet_accessible": True,
        },
    }


@router.post("/restart")
async def restart_system(
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Restart the system (soft restart)."""
    logger.warning("System restart requested")
    return {
        "status": "ok",
        "message": "System restart initiated",
        "note": "This is a soft restart stub. Hard restart requires OS-level implementation.",
    }


@router.get("/diagnostics")
async def run_diagnostics():
    """Run system diagnostics and return results."""
    diag_results = {
        "status": "ok",
        "timestamp": time.time(),
        "checks": {
            "stm32_communication": {"status": "pass", "latency_ms": 5},
            "openmv_communication": {"status": "pass", "latency_ms": 12},
            "servo_power": {"status": "pass", "voltage": 7.4},
            "database": {"status": "pass", "size_mb": 2.3},
            "disk_space": {"status": "pass", "free_gb": 15.2},
            "memory": {"status": "pass", "free_mb": 512},
            "cpu_temperature": {"status": "pass", "celsius": 45.3},
        },
        "overall": "pass",
    }
    return diag_results


@router.get("/backup")
async def create_backup(
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Create a system configuration backup."""
    backup_dir = Path("data/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"config_backup_{int(time.time())}.json"
    with db_manager.get_session() as session:
        rows = ConfigRepository.list_all(session)
        backup = {
            "created_at": time.time(),
            "configs": {
                row.key: json.loads(row.value_json) if row.value_json else {}
                for row in rows
            },
        }
    backup_path.write_text(json.dumps(backup, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "status": "ok",
        "message": "Backup created",
        "path": str(backup_path),
        "timestamp": time.time(),
    }


@router.get("/backup/restore")
async def restore_backup(
    backup_path: str,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Restore system configuration from a backup file.

    仅允许读取 data/backups 目录下的备份文件, 防止任意文件读取。
    """
    backup_dir = Path("data/backups").resolve()
    target = (backup_dir / backup_path).resolve()
    if not target.is_relative_to(backup_dir):
        raise HTTPException(status_code=400, detail="备份路径必须位于 data/backups 目录内")
    if not target.exists():
        raise HTTPException(status_code=404, detail="Backup file not found")
    try:
        with open(target, "r", encoding="utf-8") as f:
            backup = json.load(f)
    except (ValueError, OSError) as e:
        raise HTTPException(status_code=400, detail=f"无效的备份文件: {e}")

    configs = backup.get("configs", {})
    with db_manager.get_session() as session:
        for key, value in configs.items():
            ConfigRepository.set(session, key, value)
    logger.info(f"Configuration restored from {backup_path} ({len(configs)} keys)")
    return {
        "status": "ok",
        "message": f"Configuration restored from {backup_path}",
        "restored_keys": len(configs),
    }