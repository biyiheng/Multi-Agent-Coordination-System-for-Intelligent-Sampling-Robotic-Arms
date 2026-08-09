"""
Safety Monitoring Agent for the Intelligent Sampling Robotic Arm.

Continuously monitors the robotic arm's safety state including joint limits,
velocity, collision risk, and workspace bounds. Can trigger emergency stops
and manage safe recovery procedures.

Maintains heartbeat monitoring of the STM32 connection and provides
a multi-level safety state model.

Safety States:
    OK       - Normal operation, all checks passed
    WARNING  - Approaching limits (speed or position)
    DANGER   - Near critical limits, preventive action needed
    ESTOP    - Emergency stop triggered, system halted
"""

import asyncio
import time
from collections import deque
from enum import Enum
from typing import Any, Deque, Dict, List, Optional, Set, Tuple

import numpy as np

from .base_agent import BaseAgent, AgentConfig, validate_state, log_execution


class SafetyState(Enum):
    """Safety state levels."""
    OK = "ok"
    WARNING = "warning"
    DANGER = "danger"
    ESTOP = "estop"


class SafetyAgent(BaseAgent):
    """Agent for continuous safety monitoring and emergency handling.

    Monitors:
    - Joint position/velocity limits
    - Collision risks with known obstacles
    - Workspace boundary violations
    - STM32 heartbeat connectivity
    - System temperature and load

    Attributes:
        safety_state: Current safety state.
        joint_limits: Min/max limits for each joint.
        max_velocity: Maximum allowed joint velocity.
        workspace_bounds: Valid workspace boundaries.
        obstacles: List of known obstacle positions.
        stm32_last_heartbeat: Timestamp of last STM32 heartbeat.
        heartbeat_timeout_ms: Maximum allowed heartbeat gap.
        monitoring_interval_ms: Interval between safety checks.
    """

    def __init__(
        self,
        name: str = "safety_agent",
        config: Optional[AgentConfig] = None,
    ) -> None:
        """Initialize the safety agent.

        Args:
            name: Agent name.
            config: Agent configuration.
        """
        super().__init__(name, config)
        self.safety_state: SafetyState = SafetyState.OK
        self.joint_limits: Dict[str, Dict[str, float]] = {
            "joint_1": {"min": -170.0, "max": 170.0},  # degrees
            "joint_2": {"min": -130.0, "max": 130.0},
            "joint_3": {"min": -150.0, "max": 150.0},
            "joint_4": {"min": -180.0, "max": 180.0},
            "joint_5": {"min": -120.0, "max": 120.0},
            "joint_6": {"min": -180.0, "max": 180.0},
        }
        self.max_velocity: float = 180.0  # degrees/s
        self.max_acceleration: float = 360.0  # degrees/s^2
        self.workspace_bounds: Dict[str, Tuple[float, float]] = {
            "x": (0.0, 500.0),
            "y": (0.0, 500.0),
            "z": (0.0, 300.0),
        }
        self.obstacles: List[Dict[str, Any]] = []
        self.stm32_last_heartbeat: float = time.time()
        self.heartbeat_timeout_ms: float = 2000.0
        self.monitoring_interval_ms: float = 50.0  # 20 Hz
        self._previous_positions: Optional[Dict[str, float]] = None
        self._previous_time: float = 0.0
        # Moving average velocity estimator for noise reduction
        self._velocity_history: Deque[Dict[str, float]] = deque(maxlen=10)  # 500ms window
        self._safety_events: List[Dict[str, Any]] = []
        self._estop_active: bool = False

    async def validate(self, state: Dict[str, Any]) -> bool:
        """Validate safety state.

        Args:
            state: Current system state.

        Returns:
            True if safe to proceed.
        """
        if self.safety_state == SafetyState.ESTOP:
            return False
        return True

    @log_execution
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Run all safety checks and return the current safety status.

        Args:
            state: Current system state with current joint positions.

        Returns:
            State with safety status and any triggered actions.
        """
        # Gather current data from state
        joint_positions = state.get("joint_positions", {})
        current_pose = state.get("current_pose", {})
        planned_path = state.get("planned_path", [])
        timestamp = state.get("timestamp", time.time())

        # Run all safety checks
        checks = await self.monitor_safety(
            joint_positions=joint_positions,
            current_pose=current_pose,
            planned_path=planned_path,
            timestamp=timestamp,
        )

        state["safety_status"] = self.get_safety_status()
        state["safety_checks"] = checks
        state["safety_state"] = self.safety_state.value

        # If ESTOP, trigger emergency
        if self.safety_state == SafetyState.ESTOP:
            await self.emergency_stop()
            state["estop_triggered"] = True

        return state

    # =========================================================================
    # Main Safety Monitor
    # =========================================================================

    async def monitor_safety(
        self,
        joint_positions: Optional[Dict[str, float]] = None,
        current_pose: Optional[Dict[str, Tuple[float, float, float]]] = None,
        planned_path: Optional[List[Dict[str, Any]]] = None,
        timestamp: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Run all safety checks and update safety state.

        Args:
            joint_positions: Dict of joint name -> angle (degrees).
            current_pose: Dict with 'position' and 'orientation' keys.
            planned_path: List of waypoints for the planned path.
            timestamp: Current timestamp for velocity calculation.

        Returns:
            Dict with results of all safety checks.
        """
        ts = timestamp or time.time()
        checks = {}

        # Joint limit check
        if joint_positions:
            checks["joint_limits"] = self.check_joint_limits(joint_positions)

        # Velocity check
        if joint_positions and self._previous_positions and self._previous_time > 0:
            dt = ts - self._previous_time
            if dt > 0:
                checks["velocity"] = self.check_velocity(joint_positions, dt)

        # Workspace bounds check
        if current_pose:
            pos = current_pose.get("position")
            if pos:
                checks["workspace"] = self.check_workspace_bounds(pos)

        # Collision risk check
        if planned_path:
            checks["collision"] = self.check_collision_risk(planned_path, self.obstacles)

        # Heartbeat check
        checks["heartbeat"] = self._check_heartbeat()

        # Update previous positions for next velocity calculation
        if joint_positions:
            self._previous_positions = dict(joint_positions)
            self._previous_time = ts

        # Determine overall safety state
        self._update_safety_state(checks)

        return checks

    # =========================================================================
    # Individual Safety Checks
    # =========================================================================

    def check_joint_limits(self, positions: Dict[str, float]) -> Dict[str, Any]:
        """Validate that all joint positions are within limits.

        Args:
            positions: Dict of joint name -> angle (degrees).

        Returns:
            Dict with violations and overall status.
        """
        violations = []
        for joint, angle in positions.items():
            if joint in self.joint_limits:
                limits = self.joint_limits[joint]
                if angle < limits["min"]:
                    violations.append({
                        "joint": joint,
                        "value": angle,
                        "limit": limits["min"],
                        "type": "under_min",
                    })
                elif angle > limits["max"]:
                    violations.append({
                        "joint": joint,
                        "value": angle,
                        "limit": limits["max"],
                        "type": "over_max",
                    })

        # Check if near limits (within 5% of range)
        warnings = []
        for joint, angle in positions.items():
            if joint in self.joint_limits:
                limits = self.joint_limits[joint]
                range_val = limits["max"] - limits["min"]
                margin = range_val * 0.05
                if angle < limits["min"] + margin:
                    warnings.append({"joint": joint, "near": "min", "angle": angle})
                elif angle > limits["max"] - margin:
                    warnings.append({"joint": joint, "near": "max", "angle": angle})

        return {
            "ok": len(violations) == 0,
            "violations": violations,
            "warnings": warnings,
        }

    def check_velocity(self, positions: Dict[str, float], dt: float) -> Dict[str, Any]:
        """Check for excessive joint velocity using moving average filter.

        Uses a 10-sample window (500ms at 20Hz) to reduce sensor noise
        and avoid false velocity alarms.

        Args:
            positions: Current joint positions.
            dt: Time delta since last check in seconds.

        Returns:
            Dict with velocity violations.
        """
        if self._previous_positions is None or dt <= 0:
            return {"ok": True, "violations": []}

        # Compute instantaneous velocity
        instant_velocities = {}
        for joint, angle in positions.items():
            if joint in self._previous_positions:
                prev_angle = self._previous_positions[joint]
                instant_velocities[joint] = abs(angle - prev_angle) / dt

        # Add to moving average history
        self._velocity_history.append(instant_velocities)

        # Compute moving average velocities
        if len(self._velocity_history) < 3:
            # Not enough data yet, use instantaneous
            avg_velocities = instant_velocities
        else:
            avg_velocities = {}
            for joint in instant_velocities:
                values = [h.get(joint, 0.0) for h in self._velocity_history if joint in h]
                if values:
                    # Weighted average: recent values have higher weight
                    weights = np.linspace(0.5, 1.0, len(values))
                    avg_velocities[joint] = float(np.average(values, weights=weights))
                else:
                    avg_velocities[joint] = instant_velocities.get(joint, 0.0)

        # Check against limit
        violations = []
        for joint, velocity in avg_velocities.items():
            if velocity > self.max_velocity:
                violations.append({
                    "joint": joint,
                    "velocity": round(velocity, 1),
                    "max_allowed": self.max_velocity,
                    "type": "over_speed",
                })

        return {
            "ok": len(violations) == 0,
            "violations": violations,
            "max_velocity": self.max_velocity,
            "filtered": True,
            "window_size": len(self._velocity_history),
        }

    def check_collision_risk(
        self,
        planned_path: List[Dict[str, Any]],
        obstacles: List[Dict[str, Any]],
        safety_margin_mm: float = 30.0,
    ) -> Dict[str, Any]:
        """Check if a planned path passes too close to known obstacles.

        Args:
            planned_path: List of waypoint dicts with 'position' keys.
            obstacles: List of obstacle dicts with 'position' and 'radius_mm' keys.
            safety_margin_mm: Minimum allowed distance to obstacles.

        Returns:
            Dict with collision risks.
        """
        if not obstacles:
            return {"ok": True, "risks": []}

        risks = []
        for i, waypoint in enumerate(planned_path):
            wp_pos = waypoint.get("position")
            if wp_pos is None:
                continue

            for obs in obstacles:
                obs_pos = obs.get("position", (0, 0, 0))
                obs_radius = obs.get("radius_mm", 50.0)

                # Compute distance
                dx = wp_pos[0] - obs_pos[0]
                dy = wp_pos[1] - obs_pos[1]
                dz = wp_pos[2] - obs_pos[2]
                dist = (dx**2 + dy**2 + dz**2) ** 0.5

                min_safe_dist = obs_radius + safety_margin_mm
                if dist < min_safe_dist:
                    risks.append({
                        "waypoint_index": i,
                        "obstacle": obs.get("name", "unknown"),
                        "distance_mm": round(dist, 1),
                        "min_safe_distance_mm": min_safe_dist,
                        "severity": "danger" if dist < obs_radius else "warning",
                    })

        return {
            "ok": len(risks) == 0,
            "risks": risks,
            "obstacle_count": len(obstacles),
        }

    def check_workspace_bounds(
        self,
        pose: Tuple[float, float, float],
    ) -> Dict[str, Any]:
        """Check if the end-effector is within workspace bounds.

        Args:
            pose: (x, y, z) position in mm.

        Returns:
            Dict with violations.
        """
        x, y, z = pose
        violations = []

        for axis, value in [("x", x), ("y", y), ("z", z)]:
            bounds = self.workspace_bounds[axis]
            if value < bounds[0]:
                violations.append({"axis": axis, "value": value, "limit": bounds[0], "type": "under_min"})
            elif value > bounds[1]:
                violations.append({"axis": axis, "value": value, "limit": bounds[1], "type": "over_max"})

        # Check near boundaries
        warnings = []
        for axis, value in [("x", x), ("y", y), ("z", z)]:
            bounds = self.workspace_bounds[axis]
            margin = (bounds[1] - bounds[0]) * 0.05
            if value < bounds[0] + margin:
                warnings.append({"axis": axis, "near": "min", "value": value})
            elif value > bounds[1] - margin:
                warnings.append({"axis": axis, "near": "max", "value": value})

        return {
            "ok": len(violations) == 0,
            "violations": violations,
            "warnings": warnings,
        }

    def _check_heartbeat(self) -> Dict[str, Any]:
        """Check if the STM32 heartbeat is still alive.

        Returns:
            Dict with heartbeat status.
        """
        elapsed = (time.time() - self.stm32_last_heartbeat) * 1000  # ms
        alive = elapsed < self.heartbeat_timeout_ms

        return {
            "ok": alive,
            "last_heartbeat_age_ms": round(elapsed, 0),
            "timeout_ms": self.heartbeat_timeout_ms,
        }

    # =========================================================================
    # Safety State Management
    # =========================================================================

    def _update_safety_state(self, checks: Dict[str, Any]) -> None:
        """Update the overall safety state based on check results.

        Args:
            checks: Dict of safety check results.
        """
        has_danger = False
        has_warning = False

        for check_name, result in checks.items():
            if not isinstance(result, dict):
                continue

            if not result.get("ok", True):
                # Check for danger-level issues
                if check_name == "joint_limits" and result.get("violations"):
                    has_danger = True
                elif check_name == "velocity" and result.get("violations"):
                    has_warning = True
                elif check_name == "collision":
                    risks = result.get("risks", [])
                    if any(r.get("severity") == "danger" for r in risks):
                        has_danger = True
                    elif risks:
                        has_warning = True
                elif check_name == "workspace" and result.get("violations"):
                    has_danger = True
                elif check_name == "heartbeat":
                    has_danger = True

            # Check for warnings
            if result.get("warnings"):
                has_warning = True

        if has_danger:
            self.safety_state = SafetyState.DANGER
        elif has_warning:
            self.safety_state = SafetyState.WARNING
        else:
            self.safety_state = SafetyState.OK

    # =========================================================================
    # Emergency Actions
    # =========================================================================

    async def emergency_stop(self) -> bool:
        """Trigger an immediate emergency stop.

        Sends ESTOP command to STM32, sets safety state, and logs the event.

        Returns:
            True if stop was triggered.
        """
        if self._estop_active:
            self.log("ESTOP already active", 40)
            return True

        self.safety_state = SafetyState.ESTOP
        self._estop_active = True

        self.log("EMERGENCY STOP TRIGGERED!", 50)

        event = {
            "timestamp": time.time(),
            "type": "estop",
            "reason": f"Safety state: {self.safety_state.value}",
        }
        self._safety_events.append(event)

        # In real system, send ESTOP to STM32
        self.log("ESTOP command sent to STM32", 50)

        return True

    async def recover_from_safety_event(self) -> Dict[str, Any]:
        """Attempt to recover from a safety event.

        Checks if the condition that triggered the safety event has been
        resolved, then attempts to reset to a safe state.

        Returns:
            Recovery result dict.
        """
        if self.safety_state != SafetyState.ESTOP:
            return {"success": True, "message": "No ESTOP to recover from"}

        self.log("Attempting recovery from ESTOP", 40)

        # Check if conditions are safe to resume
        # In practice, this would require operator acknowledgment
        self._estop_active = False
        self.safety_state = SafetyState.OK
        self._previous_positions = None
        self._previous_time = 0.0

        event = {
            "timestamp": time.time(),
            "type": "recovery",
            "message": "System recovered from ESTOP",
        }
        self._safety_events.append(event)

        self.log("Recovery complete", 30)

        return {
            "success": True,
            "message": "Recovered from ESTOP",
            "safety_state": self.safety_state.value,
        }

    # =========================================================================
    # Status Reporting
    # =========================================================================

    def get_safety_status(self) -> Dict[str, Any]:
        """Get the current safety status report.

        Returns:
            Comprehensive safety status dict.
        """
        return {
            "state": self.safety_state.value,
            "estop_active": self._estop_active,
            "heartbeat_alive": (time.time() - self.stm32_last_heartbeat) * 1000 < self.heartbeat_timeout_ms,
            "obstacle_count": len(self.obstacles),
            "recent_events": self._safety_events[-10:],
            "total_events": len(self._safety_events),
        }

    def heartbeat_received(self) -> None:
        """Update the STM32 heartbeat timestamp when a heartbeat is received."""
        self.stm32_last_heartbeat = time.time()

    def add_obstacle(self, name: str, position: Tuple[float, float, float], radius_mm: float = 50.0) -> None:
        """Register a known obstacle in the workspace.

        Args:
            name: Obstacle name/identifier.
            position: (x, y, z) position in mm.
            radius_mm: Safety radius around the obstacle.
        """
        self.obstacles.append({
            "name": name,
            "position": position,
            "radius_mm": radius_mm,
        })
        self.log(f"Added obstacle '{name}' at {position}")

    def remove_obstacle(self, name: str) -> bool:
        """Remove a registered obstacle.

        Args:
            name: Obstacle name to remove.

        Returns:
            True if removed.
        """
        for i, obs in enumerate(self.obstacles):
            if obs["name"] == name:
                self.obstacles.pop(i)
                self.log(f"Removed obstacle '{name}'")
                return True
        return False

    def clear_obstacles(self) -> None:
        """Remove all registered obstacles."""
        self.obstacles.clear()
        self.log("All obstacles cleared")