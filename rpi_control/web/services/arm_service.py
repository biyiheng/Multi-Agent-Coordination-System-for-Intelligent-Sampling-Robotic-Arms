"""Arm service - business logic for mechanical arm operations."""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class JointLimits:
    """Joint limit configuration."""
    joint_id: int
    min_pwm: int = 500
    max_pwm: int = 2500
    home_pwm: int = 1500
    max_velocity: float = 500.0  # PWM/s


@dataclass
class ArmState:
    """Current arm state."""
    is_moving: bool = False
    is_homed: bool = False
    emergency_stop: bool = False
    joint_positions: List[float] = field(default_factory=lambda: [1500.0] * 6)
    joint_velocities: List[float] = field(default_factory=lambda: [0.0] * 6)
    end_effector_pose: Dict[str, float] = field(default_factory=lambda: {
        "x": 200.0, "y": 0.0, "z": 150.0,
        "roll": 0.0, "pitch": 0.0, "yaw": 0.0,
    })
    gripper_state: str = "open"  # open, closed, holding
    gripper_force: float = 0.0


class ArmService:
    """High-level arm control service with safety checks and IK preprocessing."""

    # Joint limits configuration
    JOINT_LIMITS: Dict[int, JointLimits] = {
        0: JointLimits(joint_id=0, min_pwm=500, max_pwm=2500, home_pwm=1500),
        1: JointLimits(joint_id=1, min_pwm=600, max_pwm=2400, home_pwm=1500),
        2: JointLimits(joint_id=2, min_pwm=600, max_pwm=2400, home_pwm=1500),
        3: JointLimits(joint_id=3, min_pwm=500, max_pwm=2500, home_pwm=1500),
        4: JointLimits(joint_id=4, min_pwm=500, max_pwm=2500, home_pwm=1500),
        5: JointLimits(joint_id=5, min_pwm=500, max_pwm=1800, home_pwm=1000),
    }

    # Workspace boundaries (mm)
    WORKSPACE_BOUNDS = {
        "x": (-200.0, 200.0),
        "y": (-200.0, 200.0),
        "z": (0.0, 300.0),
    }

    def __init__(self, stm32_interface=None, servo_controller=None):
        """Initialize the arm service.

        Args:
            stm32_interface: STM32 communication interface.
            servo_controller: Servo controller instance.
        """
        self._stm32 = stm32_interface
        self._servo = servo_controller
        self._state = ArmState()
        self._move_timeout: float = 10.0  # seconds
        self._speed_coefficient: float = 0.5  # 50% speed
        self._acceleration_coefficient: float = 0.3  # 30% acceleration

    @property
    def state(self) -> ArmState:
        """Get current arm state."""
        return self._state

    def validate_joint_position(self, joint_id: int, pwm: float) -> Tuple[bool, str]:
        """Validate a joint position against limits.

        Args:
            joint_id: Joint ID (0-5).
            pwm: Target PWM value.

        Returns:
            (is_valid, error_message) tuple.
        """
        if joint_id not in self.JOINT_LIMITS:
            return False, f"Invalid joint_id: {joint_id}"

        limits = self.JOINT_LIMITS[joint_id]
        if pwm < limits.min_pwm:
            return False, f"Joint {joint_id}: PWM {pwm} below minimum {limits.min_pwm}"
        if pwm > limits.max_pwm:
            return False, f"Joint {joint_id}: PWM {pwm} exceeds maximum {limits.max_pwm}"

        return True, ""

    def validate_all_joints(self, positions: List[float]) -> Tuple[bool, str]:
        """Validate all joint positions against limits.

        Args:
            positions: List of 6 PWM values.

        Returns:
            (is_valid, error_message) tuple.
        """
        if len(positions) != 6:
            return False, "Exactly 6 joint positions required"

        for i, pwm in enumerate(positions):
            valid, msg = self.validate_joint_position(i, pwm)
            if not valid:
                return False, msg

        return True, ""

    def validate_workspace(self, x: float, y: float, z: float) -> Tuple[bool, str]:
        """Validate that a Cartesian point is within the workspace.

        Args:
            x, y, z: Target coordinates in mm.

        Returns:
            (is_valid, error_message) tuple.
        """
        bounds = self.WORKSPACE_BOUNDS
        if not (bounds["x"][0] <= x <= bounds["x"][1]):
            return False, f"X coordinate {x} out of workspace bounds {bounds['x']}"
        if not (bounds["y"][0] <= y <= bounds["y"][1]):
            return False, f"Y coordinate {y} out of workspace bounds {bounds['y']}"
        if not (bounds["z"][0] <= z <= bounds["z"][1]):
            return False, f"Z coordinate {z} out of workspace bounds {bounds['z']}"

        return True, ""

    def limit_speed(self, current_pwm: float, target_pwm: float, time_ms: float) -> float:
        """Limit joint speed to safe values.

        Args:
            current_pwm: Current PWM value.
            target_pwm: Target PWM value.
            time_ms: Movement time in milliseconds.

        Returns:
            Speed-limited intermediate PWM value, or target if within limits.
        """
        if time_ms <= 0:
            return target_pwm

        delta = abs(target_pwm - current_pwm)
        max_delta = self._speed_coefficient * 500 * (time_ms / 1000.0)

        if delta <= max_delta:
            return target_pwm

        # Clamp to maximum safe speed
        direction = 1 if target_pwm > current_pwm else -1
        return current_pwm + direction * max_delta

    async def move_joint(
        self, joint_id: int, pwm: float, time_ms: float = 1000.0
    ) -> Dict[str, Any]:
        """Move a single joint to the specified position.

        Args:
            joint_id: Joint ID (0-5).
            pwm: Target PWM value.
            time_ms: Movement time in milliseconds.

        Returns:
            Operation result dictionary.
        """
        if self._state.emergency_stop:
            return {"status": "error", "message": "System is in emergency stop state"}

        valid, msg = self.validate_joint_position(joint_id, pwm)
        if not valid:
            return {"status": "error", "message": msg}

        # Apply speed limiting
        current_pwm = self._state.joint_positions[joint_id]
        safe_pwm = self.limit_speed(current_pwm, pwm, time_ms)

        # Update state
        self._state.joint_positions[joint_id] = safe_pwm
        self._state.is_moving = True

        logger.info(
            f"Moving joint {joint_id}: {current_pwm:.0f} -> {safe_pwm:.0f} "
            f"(target: {pwm:.0f}) in {time_ms:.0f}ms"
        )

        return {
            "status": "ok",
            "joint_id": joint_id,
            "from": current_pwm,
            "to": safe_pwm,
            "target": pwm,
            "time_ms": time_ms,
        }

    async def move_all(
        self, positions: List[float], time_ms: float = 1000.0
    ) -> Dict[str, Any]:
        """Move all joints simultaneously.

        Args:
            positions: List of 6 PWM values.
            time_ms: Movement time in milliseconds.

        Returns:
            Operation result dictionary.
        """
        if self._state.emergency_stop:
            return {"status": "error", "message": "System is in emergency stop state"}

        valid, msg = self.validate_all_joints(positions)
        if not valid:
            return {"status": "error", "message": msg}

        # Apply speed limiting to each joint
        safe_positions = []
        for i, target in enumerate(positions):
            current = self._state.joint_positions[i]
            safe = self.limit_speed(current, target, time_ms)
            safe_positions.append(safe)

        self._state.joint_positions = safe_positions
        self._state.is_moving = True

        logger.info(f"Moving all joints to {safe_positions} in {time_ms:.0f}ms")

        return {
            "status": "ok",
            "positions": safe_positions,
            "time_ms": time_ms,
        }

    async def move_cartesian(
        self,
        x: float,
        y: float,
        z: float,
        roll: float = 0.0,
        pitch: float = 0.0,
        yaw: float = 0.0,
        time_ms: float = 2000.0,
    ) -> Dict[str, Any]:
        """Move end-effector to a Cartesian position.

        Args:
            x, y, z: Target coordinates in mm.
            roll, pitch, yaw: Target orientation in radians.
            time_ms: Movement time in milliseconds.

        Returns:
            Operation result dictionary.
        """
        if self._state.emergency_stop:
            return {"status": "error", "message": "System is in emergency stop state"}

        valid, msg = self.validate_workspace(x, y, z)
        if not valid:
            return {"status": "error", "message": msg}

        # In production, this would call inverse kinematics
        # For now, update the pose state
        self._state.end_effector_pose = {
            "x": x, "y": y, "z": z,
            "roll": roll, "pitch": pitch, "yaw": yaw,
        }
        self._state.is_moving = True

        logger.info(f"Cartesian move to ({x:.1f}, {y:.1f}, {z:.1f}) in {time_ms:.0f}ms")

        return {
            "status": "ok",
            "position": {"x": x, "y": y, "z": z},
            "orientation": {"roll": roll, "pitch": pitch, "yaw": yaw},
            "time_ms": time_ms,
        }

    async def home_all(self) -> Dict[str, Any]:
        """Return all joints to home position.

        Returns:
            Operation result dictionary.
        """
        if self._state.emergency_stop:
            return {"status": "error", "message": "System is in emergency stop state"}

        home_positions = [limits.home_pwm for limits in self.JOINT_LIMITS.values()]
        self._state.joint_positions = [float(p) for p in home_positions]
        self._state.is_moving = True
        self._state.is_homed = True

        logger.info("Returning all joints to home position")

        return {
            "status": "ok",
            "message": "Homing all joints",
            "home_positions": home_positions,
        }

    async def emergency_stop(self) -> Dict[str, Any]:
        """Trigger emergency stop.

        Returns:
            Operation result dictionary.
        """
        self._state.emergency_stop = True
        self._state.is_moving = False

        logger.warning("EMERGENCY STOP triggered")

        return {
            "status": "ok",
            "message": "Emergency stop activated",
            "timestamp": "now",
        }

    async def stop(self) -> Dict[str, Any]:
        """Soft stop - decelerate and stop all movement.

        Returns:
            Operation result dictionary.
        """
        self._state.is_moving = False
        logger.info("Arm soft stop")
        return {"status": "ok", "message": "Arm stopped"}

    async def open_gripper(self) -> Dict[str, Any]:
        """Open the gripper.

        Returns:
            Operation result dictionary.
        """
        if self._state.emergency_stop:
            return {"status": "error", "message": "System is in emergency stop state"}

        self._state.gripper_state = "open"
        self._state.gripper_force = 0.0
        self._state.joint_positions[5] = 500.0

        logger.info("Gripper opened")
        return {"status": "ok", "message": "Gripper opened"}

    async def close_gripper(self, force: float = 50.0) -> Dict[str, Any]:
        """Close the gripper with specified force.

        Args:
            force: Grip force (0-100).

        Returns:
            Operation result dictionary.
        """
        if self._state.emergency_stop:
            return {"status": "error", "message": "System is in emergency stop state"}

        force = max(0.0, min(100.0, force))
        self._state.gripper_state = "closed"
        self._state.gripper_force = force
        self._state.joint_positions[5] = 1800.0

        logger.info(f"Gripper closed with force {force:.1f}%")
        return {"status": "ok", "message": f"Gripper closed (force: {force:.1f}%)"}

    async def clear_emergency_stop(self) -> Dict[str, Any]:
        """Clear emergency stop state after manual reset.

        Returns:
            Operation result dictionary.
        """
        self._state.emergency_stop = False
        logger.info("Emergency stop cleared")
        return {"status": "ok", "message": "Emergency stop cleared"}

    def get_joint_positions(self) -> List[float]:
        """Get current joint positions."""
        return self._state.joint_positions.copy()

    def get_end_effector_pose(self) -> Dict[str, float]:
        """Get current end-effector pose."""
        return self._state.end_effector_pose.copy()

    def get_safety_status(self) -> Dict[str, Any]:
        """Get current safety status."""
        return {
            "emergency_stop": self._state.emergency_stop,
            "is_moving": self._state.is_moving,
            "is_homed": self._state.is_homed,
            "joint_positions_ok": all(
                self.JOINT_LIMITS[i].min_pwm <= pos <= self.JOINT_LIMITS[i].max_pwm
                for i, pos in enumerate(self._state.joint_positions)
            ),
        }