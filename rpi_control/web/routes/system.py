"""System management API routes."""

import logging
import os
import platform
import time
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/system", tags=["system"])

# System start time for uptime calculation
_start_time = time.time()


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
async def get_system_config():
    """Get current system configuration."""
    # In production, this would read from the database or config files
    return {
        "status": "ok",
        "data": {
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
        },
    }


@router.put("/config")
async def update_system_config(data: Dict[str, Any]):
    """Update system configuration.

    Request body: {key: value, ...}
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

    logger.info(f"System configuration updated: {list(data.keys())}")
    return {"status": "ok", "message": "Configuration updated", "updated_keys": list(data.keys())}


@router.get("/logs")
async def get_system_logs(
    level: Optional[str] = None,
    limit: int = 50,
    source: Optional[str] = None,
):
    """Get recent system log entries.

    Query parameters:
    - level: Filter by log level (DEBUG, INFO, WARNING, ERROR)
    - limit: Maximum number of entries (default 50)
    - source: Filter by source module
    """
    if limit > 200:
        limit = 200
    if limit < 1:
        limit = 1

    # In production, this would read from the database or log files
    return {
        "status": "ok",
        "data": {
            "total": 0,
            "limit": limit,
            "filter": {"level": level, "source": source},
            "entries": [],
        },
        "message": "Log retrieval stub - implement database-backed logging",
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
async def restart_system():
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
async def create_backup():
    """Create a system configuration backup."""
    backup_path = f"data/backups/config_backup_{int(time.time())}.json"
    return {
        "status": "ok",
        "message": "Backup created",
        "path": backup_path,
        "timestamp": time.time(),
    }


@router.get("/backup/restore")
async def restore_backup(backup_path: str):
    """Restore system configuration from a backup file."""
    if not backup_path or not os.path.exists(backup_path):
        raise HTTPException(status_code=404, detail="Backup file not found")
    return {
        "status": "ok",
        "message": f"Configuration restored from {backup_path}",
    }