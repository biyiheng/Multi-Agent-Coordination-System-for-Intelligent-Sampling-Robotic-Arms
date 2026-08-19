"""Real-time telemetry streaming service for WebSocket clients."""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Set

from rpi_control.web.websocket.handler import ws_manager

logger = logging.getLogger(__name__)


class TelemetryStream:
    """Streams real-time telemetry data to connected WebSocket clients.

    Collects system state data at configurable intervals and broadcasts
    to all subscribed WebSocket clients.

    Telemetry data includes:
    - Joint positions and velocities
    - End-effector pose
    - Safety status
    - Sensor readings
    - System status
    - Task progress
    """

    # Default telemetry push interval (Hz)
    # v1.2: 10Hz -> 20Hz, 对应《改进计划.md》§4.1 状态上报任务 20Hz
    DEFAULT_PUSH_RATE = 20  # 20 Hz = 50ms interval

    def __init__(self, push_rate: float = DEFAULT_PUSH_RATE):
        """Initialize the telemetry stream.

        Args:
            push_rate: Telemetry push rate in Hz.
        """
        self._push_rate = push_rate
        self._push_interval = 1.0 / push_rate if push_rate > 0 else 0.1
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._subscribers: Set[str] = set()

        # Mock telemetry data sources (replace with real hardware interfaces)
        self._arm_state = None
        self._sensor_data = None
        self._safety_agent = None
        self._task_service = None

        # Sequence counter for telemetry messages
        self._sequence = 0

    def set_arm_state(self, arm_state):
        """Set the arm state source for telemetry data."""
        self._arm_state = arm_state

    def set_push_rate(self, push_rate: float) -> None:
        """更新遥测推送频率 (Hz), 对应《改进计划.md》状态上报任务 20Hz.

        Args:
            push_rate: 新推送频率 (Hz), <=0 时忽略.
        """
        if push_rate > 0:
            self._push_rate = push_rate
            self._push_interval = 1.0 / push_rate
            logger.info(f"Telemetry push rate updated to {push_rate} Hz")

    def set_sensor_data(self, sensor_data):
        """Set the sensor data source."""
        self._sensor_data = sensor_data

    def set_safety_agent(self, safety_agent):
        """Set the safety agent for safety status."""
        self._safety_agent = safety_agent

    def set_task_service(self, task_service):
        """Set the task service for task progress data."""
        self._task_service = task_service

    async def start_streaming(self) -> None:
        """Start the telemetry streaming loop."""
        if self._running:
            logger.warning("Telemetry streaming already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._streaming_loop())
        logger.info(f"Telemetry streaming started at {self._push_rate} Hz")

    async def stop_streaming(self) -> None:
        """Stop the telemetry streaming loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Telemetry streaming stopped")

    async def _streaming_loop(self) -> None:
        """Main telemetry streaming loop."""
        while self._running:
            try:
                # Collect telemetry data
                telemetry = self._collect_telemetry()

                # Broadcast to all connected clients
                if telemetry and ws_manager.client_count > 0:
                    await ws_manager.broadcast(telemetry)

                # Wait for next interval
                await asyncio.sleep(self._push_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Telemetry streaming error: {e}", exc_info=True)
                await asyncio.sleep(1.0)  # Back off on error

    def _collect_telemetry(self) -> Dict[str, Any]:
        """Collect current telemetry data from all sources.

        Returns:
            Telemetry data dictionary ready for broadcast.
        """
        self._sequence += 1
        timestamp = time.time()

        telemetry: Dict[str, Any] = {
            "type": "telemetry",
            "sequence": self._sequence,
            "timestamp": timestamp,
        }

        # Arm status
        arm_data = self._collect_arm_status()
        if arm_data:
            telemetry["arm"] = arm_data

        # Safety status
        safety_data = self._collect_safety_status()
        if safety_data:
            telemetry["safety"] = safety_data

        # Sensor data
        sensor_data = self._collect_sensor_data()
        if sensor_data:
            telemetry["sensors"] = sensor_data

        # System status
        system_data = self._collect_system_status()
        if system_data:
            telemetry["system"] = system_data

        return telemetry

    def _collect_arm_status(self) -> Optional[Dict[str, Any]]:
        """Collect arm status data."""
        if self._arm_state is None:
            return None

        try:
            return {
                "joints": self._arm_state.joint_positions if hasattr(self._arm_state, "joint_positions") else [1500] * 6,
                "velocities": self._arm_state.joint_velocities if hasattr(self._arm_state, "joint_velocities") else [0] * 6,
                "pose": self._arm_state.end_effector_pose if hasattr(self._arm_state, "end_effector_pose") else None,
                "is_moving": self._arm_state.is_moving if hasattr(self._arm_state, "is_moving") else False,
                "is_homed": self._arm_state.is_homed if hasattr(self._arm_state, "is_homed") else False,
                "gripper": {
                    "state": self._arm_state.gripper_state if hasattr(self._arm_state, "gripper_state") else "open",
                    "force": self._arm_state.gripper_force if hasattr(self._arm_state, "gripper_force") else 0.0,
                },
            }
        except Exception as e:
            logger.error(f"Error collecting arm status: {e}")
            return None

    def _collect_safety_status(self) -> Optional[Dict[str, Any]]:
        """Collect safety status data."""
        if self._safety_agent is None:
            return None

        try:
            return {
                "emergency_stop": getattr(self._safety_agent, "emergency_stop", False),
                "safety_level": getattr(self._safety_agent, "current_level", "OK"),
                "warnings": getattr(self._safety_agent, "warnings", []),
                "joint_limits_ok": getattr(self._safety_agent, "joint_limits_ok", True),
                "workspace_ok": getattr(self._safety_agent, "workspace_ok", True),
                "collision_risk": getattr(self._safety_agent, "collision_risk", "NONE"),
            }
        except Exception as e:
            logger.error(f"Error collecting safety status: {e}")
            return None

    def _collect_sensor_data(self) -> Optional[Dict[str, Any]]:
        """Collect sensor data."""
        if self._sensor_data is None:
            return None

        try:
            return {
                "temperature": getattr(self._sensor_data, "temperature", 25.0),
                "humidity": getattr(self._sensor_data, "humidity", 50.0),
                "voltage": getattr(self._sensor_data, "voltage", 7.4),
                "current": getattr(self._sensor_data, "current", 0.5),
                "distance": getattr(self._sensor_data, "distance", 100.0),
            }
        except Exception as e:
            logger.error(f"Error collecting sensor data: {e}")
            return None

    def _collect_system_status(self) -> Dict[str, Any]:
        """Collect system status data."""
        return {
            "cpu_usage": 0.0,  # Placeholder
            "memory_usage": 0.0,  # Placeholder
            "uptime_seconds": int(time.time()),
            "status": "running",
            "connected_clients": ws_manager.client_count,
        }

    async def send_status_change(self, event_type: str, data: Dict[str, Any]) -> None:
        """Send a status change notification to all clients.

        Args:
            event_type: Event type (e.g., 'emergency_stop', 'task_completed').
            data: Event data dictionary.
        """
        message = {
            "type": "status",
            "event": event_type,
            "data": data,
            "timestamp": time.time(),
        }
        await ws_manager.broadcast(message)
        logger.info(f"Status change broadcast: {event_type}")

    async def send_error(self, error_code: str, message: str, details: Optional[Dict] = None) -> None:
        """Send an error notification to all clients.

        Args:
            error_code: Error code identifier.
            message: Human-readable error message.
            details: Additional error details.
        """
        error_msg = {
            "type": "error",
            "error_code": error_code,
            "message": message,
            "details": details or {},
            "timestamp": time.time(),
        }
        await ws_manager.broadcast(error_msg)
        logger.error(f"Error broadcast: [{error_code}] {message}")

    def get_stream_stats(self) -> Dict[str, Any]:
        """Get telemetry streaming statistics."""
        return {
            "push_rate_hz": self._push_rate,
            "push_interval_ms": self._push_interval * 1000,
            "is_running": self._running,
            "sequence": self._sequence,
            "active_connections": len(ws_manager.active_connections),
        }


# Global telemetry stream instance
telemetry_stream = TelemetryStream()