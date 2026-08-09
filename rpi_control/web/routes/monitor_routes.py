"""Monitoring API routes."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

from rpi_control.web.models.status import SafetyStatus, SensorData, SystemStatus
from rpi_control.web.services.monitoring_service import MonitoringService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/monitor", tags=["monitor"])

monitoring_service = MonitoringService()


@router.get("/status", response_model=SystemStatus)
async def get_system_status():
    """Get full system status including arm, vision, sensors, and safety."""
    return monitoring_service.get_system_status()


@router.get("/sensors", response_model=SensorData)
async def get_sensor_readings():
    """Get all sensor readings."""
    return monitoring_service.get_sensor_readings()


@router.get("/safety", response_model=SafetyStatus)
async def get_safety_status():
    """Get current safety status."""
    return monitoring_service.get_safety_status()


@router.get("/logs")
async def get_recent_logs(
    limit: int = Query(100, ge=1, le=1000),
    action_type: Optional[str] = Query(None),
):
    """Get recent log entries with optional type filter."""
    logs = monitoring_service.get_recent_logs(n=limit, action_type=action_type)
    return {"status": "ok", "logs": logs}


@router.get("/statistics")
async def get_statistics():
    """Get system operation statistics."""
    stats = monitoring_service.get_statistics()
    return {"status": "ok", "statistics": stats}


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "uptime": monitoring_service.get_uptime(),
    }