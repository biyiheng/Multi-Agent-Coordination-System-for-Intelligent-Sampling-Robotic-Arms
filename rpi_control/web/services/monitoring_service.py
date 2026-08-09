"""Monitoring service for the intelligent sampling robotic arm system."""

import json
import logging
import time
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from rpi_control.database.repository import (
    DatabaseManager, LogRepository, db_manager
)
from rpi_control.web.models.status import (
    ArmStatus, EndEffectorPose, JointPositions, SafetyStatus,
    SafetyLevel, SensorData, SystemStatus, VisionStatus
)

logger = logging.getLogger(__name__)


class MonitoringService:
    """Collects and aggregates system monitoring data."""

    def __init__(self):
        self._start_time = time.time()
        self._monitoring_active = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._latest_sensor_data = SensorData()
        self._latest_arm_status = ArmStatus()
        self._latest_safety_status = SafetyStatus()
        self._lock = threading.Lock()
        db_manager.init_db()

    def get_system_status(self) -> SystemStatus:
        """Aggregate full system status."""
        return SystemStatus(
            arm=self._latest_arm_status,
            vision=VisionStatus(
                camera_connected=True,
                camera_resolution="640x480",
                fps=30.0,
            ),
            sensors=self._latest_sensor_data,
            safety=self._latest_safety_status,
            uptime=self.get_uptime(),
            version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )

    def get_sensor_readings(self) -> SensorData:
        """Get latest sensor data."""
        with self._lock:
            return self._latest_sensor_data

    def get_safety_status(self) -> SafetyStatus:
        """Get current safety status."""
        with self._lock:
            return self._latest_safety_status

    def get_uptime(self) -> float:
        """Get system uptime in seconds."""
        return time.time() - self._start_time

    def get_statistics(self) -> Dict[str, Any]:
        """Get system operation statistics."""
        with db_manager.get_session() as session:
            all_logs = LogRepository.list_recent(session, limit=1000)
            task_logs = [l for l in all_logs if l.action_type.startswith("task_")]
            error_logs = [l for l in all_logs if "error" in l.action_type.lower()]

            return {
                "total_actions": len(all_logs),
                "total_tasks": len(set(l.action_type for l in task_logs)),
                "total_errors": len(error_logs),
                "uptime_seconds": self.get_uptime(),
                "uptime_formatted": f"{self.get_uptime() / 3600:.1f}h",
                "safety_events": sum(
                    1 for l in all_logs if l.action_type.startswith("safety_")
                ),
                "last_24h_actions": len([
                    l for l in all_logs
                    if (datetime.now(timezone.utc).replace(tzinfo=None) - l.timestamp).total_seconds() < 86400
                ]),
            }

    def get_recent_logs(
        self,
        n: int = 100,
        action_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get recent log entries."""
        with db_manager.get_session() as session:
            if action_type:
                logs = LogRepository.list_by_type(session, action_type, limit=n)
            else:
                logs = LogRepository.list_recent(session, limit=n)

            return [
                {
                    "id": log.id,
                    "action_type": log.action_type,
                    "details": json.loads(log.details_json) if log.details_json else {},
                    "timestamp": log.timestamp.isoformat(),
                }
                for log in logs
            ]

    def start_monitoring(self, interval: float = 1.0):
        """Begin periodic sensor data collection."""
        if self._monitoring_active:
            return
        self._monitoring_active = True
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(interval,),
            daemon=True,
        )
        self._monitor_thread.start()
        logger.info(f"Monitoring started with interval {interval}s")

    def stop_monitoring(self):
        """Stop periodic monitoring."""
        self._monitoring_active = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
        logger.info("Monitoring stopped")

    def _monitoring_loop(self, interval: float):
        """Internal monitoring loop for sensor data collection."""
        while self._monitoring_active:
            try:
                self._collect_sensor_data()
            except Exception as e:
                logger.error(f"Error collecting sensor data: {e}")
            time.sleep(interval)

    def _collect_sensor_data(self):
        """Collect sensor data from hardware (mock implementation)."""
        import random
        with self._lock:
            self._latest_sensor_data = SensorData(
                temperature=25.0 + random.uniform(-1.0, 1.0),
                humidity=50.0 + random.uniform(-5.0, 5.0),
                distance=random.uniform(100.0, 500.0),
                voltage=12.0 + random.uniform(-0.2, 0.2),
                current=random.uniform(0.5, 3.0),
            )

    def update_arm_status(self, status: ArmStatus):
        """Update the latest arm status."""
        with self._lock:
            self._latest_arm_status = status

    def update_safety_status(self, status: SafetyStatus):
        """Update safety status."""
        with self._lock:
            self._latest_safety_status = status
            if status.level in (SafetyLevel.WARNING, SafetyLevel.CRITICAL):
                with db_manager.get_session() as session:
                    LogRepository.create(session, "safety_event", {
                        "level": status.level.value,
                        "warnings": status.warnings,
                        "errors": status.errors,
                    })