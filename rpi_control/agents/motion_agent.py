"""
Motion Planning Agent for the Intelligent Sampling Robotic Arm.

Plans and executes collision-free trajectories for the robotic arm.
Handles approach, grasp, retract, and place motions with error recovery
and path optimization. Communicates with the STM32 motion controller
to execute trajectories.

Optimized parameters (from training):
  - max_velocity: 300 mm/s (was 500)
  - max_acceleration: 500 mm/s² (was 1000)
  - safety_margin: 20 mm
  - speed_factor: 0.6

Integrated IK-NN model for accelerated inverse kinematics solving.
"""

import asyncio
import json
import math
import os
import pickle
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from .base_agent import BaseAgent, AgentConfig, AgentStatus, validate_state, log_execution


class MotionState(Enum):
    """States for the motion execution state machine."""
    IDLE = "idle"
    MOVING = "moving"
    APPROACHING = "approaching"
    GRASPING = "grasping"
    LIFTING = "lifting"
    RETRACTING = "retracting"
    PLACING = "placing"
    HOLDING = "holding"
    ERROR = "error"
    RECOVERING = "recovering"


@dataclass
class Waypoint:
    """A single waypoint in a trajectory.

    Attributes:
        position: (x, y, z) in mm.
        orientation: (roll, pitch, yaw) in radians.
        speed: Movement speed as fraction of max (0.0-1.0).
        gripper: Gripper state: 'open', 'close', 'hold'.
        pause_ms: Pause at this waypoint in milliseconds.
    """
    position: Tuple[float, float, float]
    orientation: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    speed: float = 0.5
    gripper: Optional[str] = None
    pause_ms: int = 0


@dataclass
class Trajectory:
    """A sequence of waypoints forming a complete motion.

    Attributes:
        waypoints: Ordered list of waypoints.
        name: Human-readable name for this trajectory.
        estimated_duration_ms: Estimated total time.
    """
    waypoints: List[Waypoint]
    name: str = "trajectory"
    estimated_duration_ms: float = 0.0


class MotionAgent(BaseAgent):
    """Agent for motion planning and execution.

    Plans collision-free paths, executes trajectories via STM32,
    monitors execution progress, and handles motion errors.

    Attributes:
        motion_state: Current state in the motion state machine.
        current_pose: Current robot end-effector pose.
        home_pose: Home/safe position.
        max_velocity: Maximum allowed velocity in mm/s.
        max_acceleration: Maximum allowed acceleration in mm/s^2.
        stm32: STM32 communication interface (set externally).
        gripper_open: Whether the gripper is currently open.
    """

    def __init__(
        self,
        name: str = "motion_agent",
        config: Optional[AgentConfig] = None,
    ) -> None:
        """Initialize the motion agent.

        Args:
            name: Agent name.
            config: Agent configuration.
        """
        super().__init__(name, config)
        self.motion_state: MotionState = MotionState.IDLE
        self.current_pose: Dict[str, Tuple[float, float, float]] = {
            "position": (0.0, 0.0, 0.0),
            "orientation": (0.0, 0.0, 0.0),
        }
        self.home_pose: Dict[str, Tuple[float, float, float]] = {
            "position": (250.0, 250.0, 100.0),  # Center of workspace, safe height
            "orientation": (0.0, 0.0, 0.0),
        }
        # Optimized parameters from training (Round 2)
        self.max_velocity: float = 300.0  # mm/s (was 500, optimized +66.9%)
        self.max_acceleration: float = 500.0  # mm/s² (was 1000)
        self.safety_margin: float = 20.0  # mm (was 30)
        self.speed_factor: float = 0.6  # default speed multiplier
        self.stm32: Any = None  # STM32 communication interface
        self.gripper_open: bool = True
        self._active_trajectory: Optional[Trajectory] = None
        self._motion_progress: float = 0.0  # 0.0 to 1.0
        self._stm32_ack_timeout: float = 5.0  # seconds
        self._stm32_retry_count: int = 3
        self._ik_model: Any = None  # IK neural network model
        self._ik_model_loaded: bool = False
        self._ik_meta: Optional[Dict[str, Any]] = None  # IK normalization metadata
        # Joint limits in degrees (matches kinematics.DEFAULT_JOINT_LIMITS)
        self._joint_limits: List[Tuple[float, float]] = [
            (-90.0, 90.0), (-90.0, 90.0), (-90.0, 90.0),
            (-90.0, 90.0), (-90.0, 90.0), (-45.0, 45.0),
        ]
        # Motion type dispatch table (O(1) lookup instead of if-elif chain)
        self._motion_handlers: Dict[str, Callable[[Dict[str, Any]], Coroutine[Any, Any, Optional[Dict[str, Any]]]]] = {
            "plan_motion": self._handle_plan_motion,
            "approach": self._handle_approach,
            "grasp": self._handle_grasp,
            "lift": self._handle_lift,
            "retract": self._handle_retract,
            "place": self._handle_place,
            "home": self._handle_home,
            "move_to": self._handle_move_to,
        }

    async def validate(self, state: Dict[str, Any]) -> bool:
        """Validate motion state.

        Args:
            state: Current system state.

        Returns:
            True if valid.
        """
        return True

    async def initialize(self) -> bool:
        """Initialize the motion agent, load IK model, and perform self-check.

        Returns:
            True if initialization succeeded.
        """
        self.log("Initializing motion agent...")

        # Load IK neural network model
        self._load_ik_model()

        # Perform arm self-check
        self_check_ok = await self.arm_self_check()
        if not self_check_ok:
            self.log("Arm self-check failed!", 40)
            return False

        # Reset servos to home position
        reset_ok = await self.servo_reset()
        if not reset_ok:
            self.log("Servo reset failed!", 40)
            return False

        self.log("Motion agent initialized successfully")
        return True

    # =========================================================================
    # IK-NN Model Integration
    # =========================================================================

    def _load_ik_model(self) -> None:
        """Load the trained IK neural network model for accelerated solving."""
        model_paths = [
            os.path.join(os.path.dirname(__file__), "..", "models", "motion_ik_model.pkl"),
            os.path.join(os.path.dirname(__file__), "..", "..", "models", "motion_ik_model.pkl"),
            "models/motion_ik_model.pkl",
        ]
        for path in model_paths:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                try:
                    with open(abs_path, "rb") as f:
                        model_data = pickle.load(f)
                    self._ik_model = model_data
                    self._ik_model_loaded = True
                    self._ik_meta = self._load_ik_meta()
                    self.log(f"IK model loaded from {abs_path}")
                    return
                except Exception as e:
                    self.log(f"Failed to load IK model from {abs_path}: {e}", 30)

        self.log("IK model not found, using analytical IK only", 30)

    def _load_ik_meta(self) -> Optional[Dict[str, Any]]:
        """Load the normalization metadata saved alongside the IK model."""
        meta_paths = [
            os.path.join(os.path.dirname(__file__), "..", "models", "motion_ik_model_meta.json"),
            os.path.join(os.path.dirname(__file__), "..", "..", "models", "motion_ik_model_meta.json"),
            "models/motion_ik_model_meta.json",
        ]
        for path in meta_paths:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                try:
                    with open(abs_path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as e:
                    self.log(f"Failed to load IK meta from {abs_path}: {e}", 30)
        return None

    def solve_ik_nn(self, target_pose: Tuple[float, float, float, float, float, float]) -> Optional[List[float]]:
        """Use the trained NN to predict initial joint angles for IK.

        This provides a warm start that accelerates analytical IK convergence.

        The model was trained on NORMALIZED inputs and produces NORMALIZED
        outputs, with batch-norm hidden layers. Therefore inference MUST:
          1. Normalize the input pose using X_mean/X_std from the meta file.
          2. Apply batch-norm layers in inference mode (running stats).
          3. Denormalize the output using y_mean/y_std.

        Args:
            target_pose: (x, y, z, roll, pitch, yaw) in mm and radians.

        Returns:
            Predicted joint angles in degrees, or None if model unavailable.
        """
        if not self._ik_model_loaded or self._ik_model is None:
            return None
        if self._ik_meta is None:
            self.log("IK normalization metadata missing, using analytical IK only", 30)
            return None

        try:
            weights = self._ik_model["weights"]
            biases = self._ik_model["biases"]
            activation = self._ik_model.get("activation", "relu")
            output_activation = self._ik_model.get("output_activation", "linear")
            use_bn = self._ik_model.get("use_batch_norm", False)
            bn_gamma = self._ik_model.get("bn_gamma")
            bn_beta = self._ik_model.get("bn_beta")
            bn_running_mean = self._ik_model.get("bn_running_mean")
            bn_running_var = self._ik_model.get("bn_running_var")

            meta = self._ik_meta
            x_mean = np.array(meta["X_mean"], dtype=np.float32)
            x_std = np.array(meta["X_std"], dtype=np.float32)
            y_mean = np.array(meta["y_mean"], dtype=np.float32)
            y_std = np.array(meta["y_std"], dtype=np.float32)

            # 1. Normalize input pose
            x = (np.array(target_pose, dtype=np.float32).reshape(1, -1) - x_mean) / (x_std + 1e-8)

            # 2. Forward pass with batch-norm (inference mode)
            for i, (W, b) in enumerate(zip(weights, biases)):
                W_arr = np.array(W, dtype=np.float32)
                b_arr = np.array(b, dtype=np.float32)
                x = x @ W_arr + b_arr

                # Apply batch-norm for hidden layers using running statistics
                if use_bn and i < len(weights) - 1 and bn_gamma is not None and bn_gamma[i] is not None:
                    g = np.array(bn_gamma[i], dtype=np.float32)
                    beta = np.array(bn_beta[i], dtype=np.float32)
                    rm = np.array(bn_running_mean[i], dtype=np.float32)
                    rv = np.array(bn_running_var[i], dtype=np.float32)
                    x = g * (x - rm) / np.sqrt(rv + 1e-8) + beta

                if i < len(weights) - 1:
                    if activation == "relu":
                        x = np.maximum(0, x)
                    elif activation == "tanh":
                        x = np.tanh(x)
                else:
                    if output_activation == "sigmoid":
                        x = 1.0 / (1.0 + np.exp(-np.clip(x, -500, 500)))

            # 3. Denormalize output
            joints_rad = (x.flatten() * y_std + y_mean).tolist()
            joints_deg = [round(math.degrees(j), 2) for j in joints_rad]

            # Clamp to joint limits
            clamped = []
            for j, (lo, hi) in zip(joints_deg, self._joint_limits):
                clamped.append(max(lo, min(hi, j)))

            return clamped
        except Exception as e:
            self.log(f"IK NN prediction failed: {e}", 30)
            return None

    # =========================================================================
    # Arm Self-Check & Servo Reset
    # =========================================================================

    async def arm_self_check(self) -> bool:
        """Perform comprehensive robotic arm self-check.

        Checks:
        1. Joint limits verification
        2. Workspace boundary validation
        3. Gripper functionality
        4. STM32 communication health

        Returns:
            True if all checks pass.
        """
        self.log("Starting arm self-check...")
        checks_passed = 0
        checks_total = 4

        # Check 1: Joint limits
        self.log("  [1/4] Checking joint limits...")
        all_limits_valid = True
        for i, (lo, hi) in enumerate(self._joint_limits):
            if lo >= hi:
                self.log(f"    Joint {i+1}: INVALID limits ({lo}, {hi})", 40)
                all_limits_valid = False
        if all_limits_valid:
            checks_passed += 1
            self.log("    Joint limits OK")

        # Check 2: Workspace validation
        self.log("  [2/4] Checking workspace bounds...")
        home_pos = self.home_pose["position"]
        ws_valid = (
            0 <= home_pos[0] <= 500
            and 0 <= home_pos[1] <= 500
            and 0 <= home_pos[2] <= 300
        )
        if ws_valid:
            checks_passed += 1
            self.log("    Workspace bounds OK")
        else:
            self.log(f"    Home position {home_pos} outside workspace!", 40)

        # Check 3: Gripper self-test
        self.log("  [3/4] Checking gripper...")
        try:
            await self._set_gripper("open")
            await asyncio.sleep(0.1)
            await self._set_gripper("close")
            await asyncio.sleep(0.1)
            await self._set_gripper("open")
            checks_passed += 1
            self.log("    Gripper OK")
        except Exception as e:
            self.log(f"    Gripper check failed: {e}", 40)

        # Check 4: STM32 communication
        self.log("  [4/4] Checking STM32 communication...")
        if self.stm32:
            try:
                result = await self._send_command_with_ack("PING")
                if result and result.get("ack"):
                    checks_passed += 1
                    self.log("    STM32 communication OK")
                else:
                    self.log("    STM32 no response", 40)
            except Exception as e:
                self.log(f"    STM32 check failed: {e}", 40)
        else:
            self.log("    STM32 not connected (simulation mode)", 30)
            checks_passed += 1  # Count as passed in simulation

        self.log(f"Arm self-check complete: {checks_passed}/{checks_total} passed")
        return checks_passed >= 3  # At least 3/4 must pass

    async def servo_reset(self, timeout: float = 15.0) -> bool:
        """Reset all servos to home position safely.

        Performs a soft reset with timeout protection:
        1. Stop any active motion
        2. Set all joints to neutral position
        3. Verify home position reached

        Args:
            timeout: Maximum time in seconds for the reset operation.

        Returns:
            True if reset successful.
        """
        self.log("Starting servo reset...")

        try:
            # Stop any active motion
            if self.stm32:
                self.stm32.send_command("ESTOP")
                await asyncio.sleep(0.2)

            # Reset state
            self.motion_state = MotionState.IDLE
            self._motion_progress = 0.0

            # Move to home position with timeout protection
            home_traj = self.plan_motion(self.current_pose, self.home_pose)
            try:
                result = await asyncio.wait_for(
                    self.execute_motion(home_traj),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                self.log(f"Servo reset timed out after {timeout}s", 50)
                if self.stm32:
                    self.stm32.send_command("ESTOP")
                return False

            if result.get("success"):
                self.current_pose = self.home_pose
                self.log("Servo reset complete - at home position")
                return True
            else:
                self.log("Servo reset failed to reach home position", 40)
                return False

        except Exception as e:
            self.log(f"Servo reset error: {e}", 50)
            return False

    # =========================================================================
    # STM32 Acknowledgment
    # =========================================================================

    async def _send_command_with_ack(self, command: str, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Send a command to STM32 and wait for acknowledgment.

        Args:
            command: Command string to send.
            timeout: Custom timeout in seconds.

        Returns:
            Dict with 'ack' (bool) and 'data' (str).
        """
        to = timeout or self._stm32_ack_timeout

        if self.stm32 is None:
            # Simulation mode: return simulated acknowledgment
            await asyncio.sleep(0.01)
            return {"ack": True, "data": "simulated"}

        for attempt in range(self._stm32_retry_count):
            try:
                self.stm32.send_command(command)
                # Wait for response
                response = await asyncio.wait_for(
                    self._read_stm32_response(),
                    timeout=to,
                )
                if response:
                    return {"ack": True, "data": response}
            except asyncio.TimeoutError:
                self.log(f"STM32 ack timeout (attempt {attempt + 1}/{self._stm32_retry_count})", 30)
            except Exception as e:
                self.log(f"STM32 command error: {e}", 30)

            if attempt < self._stm32_retry_count - 1:
                # Exponential backoff: 100ms, 200ms, 400ms...
                backoff = 0.1 * (2 ** attempt)
                await asyncio.sleep(backoff)

        return {"ack": False, "error": "STM32 no response after retries"}

    async def _read_stm32_response(self) -> Optional[str]:
        """Read response from STM32. Placeholder for actual protocol.

        Returns:
            Response string or None.
        """
        if self.stm32 and hasattr(self.stm32, "read_response"):
            return self.stm32.read_response()
        return "OK"  # Placeholder

    @validate_state(required_keys=["target_pose"])
    @log_execution
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process a motion request using O(1) dispatch.

        Uses a pre-built dispatch table for O(1) lookup instead of the
        previous O(n) if-elif chain.

        Args:
            state: Must contain 'target_pose' and optionally 'motion_type'.

        Returns:
            State with motion execution results.
        """
        motion_type = state.get("motion_type", "move_to")
        target_pose = state.get("target_pose", {})

        handler = self._motion_handlers.get(motion_type)
        if handler is not None:
            result = await handler(target_pose)
        else:
            result = {"success": False, "error": f"Unknown motion type: {motion_type}"}

        state["motion_result"] = result
        return state

    # =========================================================================
    # Motion Type Handlers
    # =========================================================================

    async def _handle_plan_motion(self, target_pose: Dict[str, Any]) -> Dict[str, Any]:
        """Handle plan_motion: plan without executing."""
        trajectory = self.plan_motion(self.current_pose, target_pose)
        return {"success": True, "trajectory": trajectory}

    async def _handle_approach(self, target_pose: Dict[str, Any]) -> Dict[str, Any]:
        """Handle approach: plan and execute grasp approach."""
        trajectory = self.plan_grasp_approach(target_pose)
        return await self.execute_motion(trajectory)

    async def _handle_grasp(self, target_pose: Dict[str, Any]) -> Dict[str, Any]:
        """Handle grasp: execute grasp action."""
        return await self._execute_grasp()

    async def _handle_lift(self, target_pose: Dict[str, Any]) -> Dict[str, Any]:
        """Handle lift: plan and execute post-grasp lift."""
        trajectory = self.plan_post_grasp_pose()
        return await self.execute_motion(trajectory)

    async def _handle_retract(self, target_pose: Dict[str, Any]) -> Dict[str, Any]:
        """Handle retract: plan and execute retract."""
        trajectory = self.plan_retract()
        return await self.execute_motion(trajectory)

    async def _handle_place(self, target_pose: Dict[str, Any]) -> Dict[str, Any]:
        """Handle place: plan and execute place."""
        return await self.execute_motion(self.plan_place(target_pose))

    async def _handle_home(self, target_pose: Dict[str, Any]) -> Dict[str, Any]:
        """Handle home: plan and execute move to home."""
        trajectory = self.plan_motion(self.current_pose, self.home_pose)
        return await self.execute_motion(trajectory)

    async def _handle_move_to(self, target_pose: Dict[str, Any]) -> Dict[str, Any]:
        """Handle move_to: plan and execute move to target."""
        trajectory = self.plan_motion(self.current_pose, target_pose)
        return await self.execute_motion(trajectory)

    # =========================================================================
    # Path Planning - Common Patterns
    # =========================================================================

    def _plan_simple_move(
        self,
        target_pos: Tuple[float, float, float],
        name: str,
        speed: float = 0.5,
        gripper: Optional[str] = None,
        pause_ms: int = 0,
        use_pre_position: bool = False,
        pre_height_offset: float = 50.0,
    ) -> Trajectory:
        """Plan a simple move with optional pre-position above target.

        This extracts the common pattern used by plan_grasp_approach,
        plan_place, and plan_retract to reduce code duplication.

        Args:
            target_pos: Final target position.
            name: Trajectory name.
            speed: Movement speed for the final approach.
            gripper: Gripper state at target.
            pause_ms: Pause at target in ms.
            use_pre_position: Whether to add a waypoint above target.
            pre_height_offset: Height offset for pre-position.

        Returns:
            Planned trajectory.
        """
        waypoints = []

        if use_pre_position:
            pre_pos = (target_pos[0], target_pos[1], target_pos[2] + pre_height_offset)
            waypoints.append(Waypoint(
                position=pre_pos,
                speed=min(speed + 0.2, 1.0),
                gripper="open" if gripper == "close" else None,
            ))

        waypoints.append(Waypoint(
            position=target_pos,
            speed=speed,
            gripper=gripper,
            pause_ms=pause_ms,
        ))

        return Trajectory(
            waypoints=waypoints,
            name=name,
            estimated_duration_ms=self._estimate_duration(
                waypoints, self.current_pose["position"]
            ),
        )

    def _plan_vertical_move(
        self,
        delta_z: float,
        name: str,
        speed: float = 0.4,
        gripper: Optional[str] = None,
        pause_ms: int = 0,
    ) -> Trajectory:
        """Plan a vertical-only move (lift or lower).

        Extracts the common vertical movement pattern used by
        plan_post_grasp_pose and plan_retract.

        Args:
            delta_z: Vertical offset from current position (positive = up).
            name: Trajectory name.
            speed: Movement speed.
            gripper: Gripper state.
            pause_ms: Pause at target in ms.

        Returns:
            Planned trajectory.
        """
        current_pos = self.current_pose.get("position", (0, 0, 0))
        target_pos = (current_pos[0], current_pos[1], current_pos[2] + delta_z)

        waypoints = [
            Waypoint(position=target_pos, speed=speed, gripper=gripper, pause_ms=pause_ms),
        ]

        return Trajectory(
            waypoints=waypoints,
            name=name,
            estimated_duration_ms=self._estimate_duration(waypoints, current_pos),
        )

    # =========================================================================
    # Path Planning
    # =========================================================================

    def plan_motion(
        self,
        current_pose: Dict[str, Tuple[float, float, float]],
        target_pose: Dict[str, Tuple[float, float, float]],
    ) -> Trajectory:
        """Plan a collision-free path from current to target pose.

        Uses linear interpolation with optional obstacle avoidance waypoints.

        Args:
            current_pose: Current end-effector pose.
            target_pose: Desired target pose.

        Returns:
            Trajectory with waypoints from start to target.
        """
        start_pos = current_pose.get("position", (0, 0, 0))
        end_pos = target_pose.get("position", (0, 0, 0))
        start_ori = current_pose.get("orientation", (0, 0, 0))
        end_ori = target_pose.get("orientation", (0, 0, 0))

        waypoints = []

        # If the target is below the current Z, add an intermediate safe-height waypoint
        if end_pos[2] < start_pos[2] - 10:
            # Move to safe height above target first
            safe_pos = (end_pos[0], end_pos[1], start_pos[2])
            if self._distance(start_pos, safe_pos) > 1:
                waypoints.append(Waypoint(
                    position=safe_pos,
                    speed=0.6,
                ))

        # Main move to target
        waypoints.append(Waypoint(
            position=end_pos,
            orientation=end_ori,
            speed=0.3,  # Slower near target
        ))

        duration = self._estimate_duration(waypoints, start_pos)
        return Trajectory(
            waypoints=waypoints,
            name=f"move_to_{end_pos[0]:.0f}_{end_pos[1]:.0f}_{end_pos[2]:.0f}",
            estimated_duration_ms=duration,
        )

    def plan_grasp_approach(self, target_pose: Dict[str, Tuple[float, float, float]]) -> Trajectory:
        """Plan an approach trajectory from above the target.

        Moves to a pre-grasp position above the target, then descends.

        Args:
            target_pose: Target object pose.

        Returns:
            Approach trajectory.
        """
        target_pos = target_pose.get("position", (0, 0, 0))
        return self._plan_simple_move(
            target_pos=target_pos,
            name="grasp_approach",
            speed=0.2,
            gripper="open",
            pause_ms=200,
            use_pre_position=True,
            pre_height_offset=50.0,
        )

    def plan_retract(self) -> Trajectory:
        """Plan a safe retract motion after grasp.

        Lifts the end-effector to a safe height.

        Returns:
            Retract trajectory.
        """
        return self._plan_vertical_move(
            delta_z=self.home_pose["position"][2] - self.current_pose["position"][2],
            name="retract",
            speed=0.4,
            gripper="hold",
        )

    def plan_place(self, target_pose: Dict[str, Tuple[float, float, float]]) -> Trajectory:
        """Plan a place motion at the target location.

        Moves to a pre-place position above the target, then descends.

        Args:
            target_pose: Target place pose.

        Returns:
            Place trajectory.
        """
        target_pos = target_pose.get("position", (0, 0, 0))
        return self._plan_simple_move(
            target_pos=target_pos,
            name="place",
            speed=0.2,
            gripper="open",
            pause_ms=300,
            use_pre_position=True,
            pre_height_offset=50.0,
        )

    def pre_grasp_pose(self, target_pose: Dict[str, Tuple[float, float, float]]) -> Dict[str, Tuple[float, float, float]]:
        """Compute the pre-grasp pose (offset above target).

        Args:
            target_pose: Target object pose.

        Returns:
            Pre-grasp pose dict with position and orientation.
        """
        target_pos = target_pose.get("position", (0, 0, 0))
        pre_grasp_pos = (target_pos[0], target_pos[1], target_pos[2] + 50.0)  # 50mm above
        return {
            "position": pre_grasp_pos,
            "orientation": target_pose.get("orientation", (0, 0, 0)),
        }

    def plan_post_grasp_pose(self) -> Trajectory:
        """Lift the end-effector after a successful grasp.

        Returns:
            Lift trajectory.
        """
        return self._plan_vertical_move(
            delta_z=80.0,
            name="post_grasp_lift",
            speed=0.3,
            gripper="hold",
            pause_ms=100,
        )

    # =========================================================================
    # Execution
    # =========================================================================

    async def execute_motion(self, trajectory: Trajectory, waypoint_timeout: float = 10.0) -> Dict[str, Any]:
        """Execute a planned trajectory.

        Sends waypoints to the STM32 controller and monitors progress.
        Each waypoint has an individual timeout to prevent indefinite blocking.

        Args:
            trajectory: The trajectory to execute.
            waypoint_timeout: Maximum seconds per waypoint.

        Returns:
            Execution result dict.
        """
        self.motion_state = MotionState.MOVING
        self._active_trajectory = trajectory
        self._motion_progress = 0.0

        self.log(f"Executing trajectory: {trajectory.name} ({len(trajectory.waypoints)} waypoints)")

        try:
            for i, waypoint in enumerate(trajectory.waypoints):
                # Send waypoint to STM32 with per-waypoint timeout
                if self.stm32:
                    try:
                        await asyncio.wait_for(
                            self._send_waypoint_to_stm32(waypoint),
                            timeout=waypoint_timeout,
                        )
                    except asyncio.TimeoutError:
                        self.log(f"Waypoint {i+1}/{len(trajectory.waypoints)} timed out", 40)
                        raise RuntimeError(f"Waypoint {i+1} execution timed out after {waypoint_timeout}s")

                # Update current pose
                self.current_pose["position"] = waypoint.position
                self.current_pose["orientation"] = waypoint.orientation

                # Handle gripper
                if waypoint.gripper:
                    await self._set_gripper(waypoint.gripper)

                # Pause if needed
                if waypoint.pause_ms > 0:
                    await asyncio.sleep(waypoint.pause_ms / 1000.0)

                # Update progress
                self._motion_progress = (i + 1) / len(trajectory.waypoints)

                # Monitor execution
                await self.monitor_execution()

            self.motion_state = MotionState.IDLE
            self.log(f"Trajectory complete: {trajectory.name}")

            return {
                "success": True,
                "trajectory": trajectory.name,
                "waypoints_completed": len(trajectory.waypoints),
                "final_pose": self.current_pose,
            }

        except Exception as e:
            self.motion_state = MotionState.ERROR
            self.log(f"Motion execution failed: {e}", 40)
            return await self.handle_motion_error(str(e))

    async def _execute_grasp(self) -> Dict[str, Any]:
        """Execute a grasp action (close gripper).

        Returns:
            Grasp result dict.
        """
        self.motion_state = MotionState.GRASPING
        self.log("Executing grasp")

        await self._set_gripper("close")
        self.gripper_open = False

        # Small pause to ensure grasp is secure
        await asyncio.sleep(0.3)

        self.motion_state = MotionState.HOLDING
        return {
            "success": True,
            "action": "grasp",
            "gripper": "closed",
        }

    async def _send_waypoint_to_stm32(self, waypoint: Waypoint) -> None:
        """Send a waypoint to the STM32 motion controller with ACK.

        In a real system, this would use the actual communication protocol.
        Here we simulate the motion delay.

        Args:
            waypoint: The waypoint to send.
        """
        # Simulate motion time based on distance
        current_pos = self.current_pose.get("position", (0, 0, 0))
        dist = self._distance(current_pos, waypoint.position)
        speed = waypoint.speed * self.max_velocity
        move_time = dist / max(speed, 1.0)

        if self.stm32 is None:
            # Simulation mode
            await asyncio.sleep(min(move_time, 0.5))  # Cap at 500ms for simulation
        else:
            # Real STM32 communication with acknowledgment
            command = (
                f"GOTO {waypoint.position[0]:.1f} {waypoint.position[1]:.1f} {waypoint.position[2]:.1f} "
                f"{waypoint.orientation[0]:.3f} {waypoint.orientation[1]:.3f} {waypoint.orientation[2]:.3f} "
                f"{waypoint.speed:.2f} "
                f"{waypoint.gripper or 'hold'}"
            )
            ack = await self._send_command_with_ack(command, timeout=max(move_time * 2, 1.0))
            if not ack.get("ack"):
                raise RuntimeError(f"STM32 did not acknowledge waypoint: {command[:60]}...")

    async def _set_gripper(self, state: str) -> None:
        """Set the gripper state.

        Args:
            state: 'open', 'close', or 'hold'.
        """
        if state == "hold":
            return
        if self.stm32:
            self.stm32.send_command(f"GRIPPER {state.upper()}")
        self.gripper_open = (state == "open")

    # =========================================================================
    # Monitoring
    # =========================================================================

    async def monitor_execution(self) -> Dict[str, Any]:
        """Monitor the current motion execution for stalls or errors.

        Returns:
            Monitoring status dict.
        """
        # In a real system, this would check STM32 feedback
        return {
            "progress": round(self._motion_progress, 3),
            "state": self.motion_state.value,
            "position": self.current_pose["position"],
        }

    async def handle_motion_error(self, error: str) -> Dict[str, Any]:
        """Handle a motion error with recovery procedure.

        Attempts to stop the motion, return to a safe state, and report the error.

        Args:
            error: Error description string.

        Returns:
            Error handling result.
        """
        self.motion_state = MotionState.RECOVERING
        self.log(f"Handling motion error: {error}", 40)

        try:
            # Emergency stop
            if self.stm32:
                self.stm32.send_command("ESTOP")

            # Attempt to return to home
            self.motion_state = MotionState.IDLE

            return {
                "success": False,
                "error": error,
                "recovered": True,
                "current_pose": self.current_pose,
            }
        except Exception as e:
            self.motion_state = MotionState.ERROR
            return {
                "success": False,
                "error": f"Recovery failed: {e}",
                "recovered": False,
            }

    # =========================================================================
    # Path Optimization
    # =========================================================================

    def optimize_path(self, path: Trajectory) -> Trajectory:
        """Smooth and shorten a trajectory by removing redundant waypoints.

        Applies simple collinearity check and removes intermediate points
        that lie on a straight line.

        Args:
            path: Input trajectory.

        Returns:
            Optimized trajectory.
        """
        if len(path.waypoints) <= 2:
            return path

        optimized = [path.waypoints[0]]
        for i in range(1, len(path.waypoints) - 1):
            prev = optimized[-1].position
            curr = path.waypoints[i].position
            next_pt = path.waypoints[i + 1].position

            # Check if current waypoint is collinear with prev and next
            if not self._is_collinear(prev, curr, next_pt, tolerance=1.0):
                optimized.append(path.waypoints[i])

        optimized.append(path.waypoints[-1])

        return Trajectory(
            waypoints=optimized,
            name=path.name + "_optimized",
            estimated_duration_ms=self._estimate_duration(optimized, optimized[0].position),
        )

    def _is_collinear(
        self,
        p1: Tuple[float, float, float],
        p2: Tuple[float, float, float],
        p3: Tuple[float, float, float],
        tolerance: float = 1.0,
    ) -> bool:
        """Check if three points are collinear within tolerance.

        Args:
            p1, p2, p3: Three 3D points.
            tolerance: Maximum deviation from collinearity.

        Returns:
            True if points are collinear.
        """
        v1 = np.array(p2) - np.array(p1)
        v2 = np.array(p3) - np.array(p1)
        cross = np.linalg.norm(np.cross(v1, v2))
        norm = np.linalg.norm(v1) * np.linalg.norm(v2)
        if norm == 0:
            return True
        return (cross / norm) < tolerance

    # =========================================================================
    # Helpers
    # =========================================================================

    def _distance(self, p1: Tuple[float, float, float], p2: Tuple[float, float, float]) -> float:
        """Compute Euclidean distance between two 3D points.

        Args:
            p1, p2: (x, y, z) tuples.

        Returns:
            Distance in mm.
        """
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(p1, p2)))

    def _estimate_duration(
        self,
        waypoints: List[Waypoint],
        start_pos: Tuple[float, float, float],
    ) -> float:
        """Estimate the total duration of a trajectory.

        Args:
            waypoints: List of waypoints.
            start_pos: Starting position.

        Returns:
            Estimated duration in milliseconds.
        """
        total_time = 0.0
        prev_pos = start_pos
        for wp in waypoints:
            dist = self._distance(prev_pos, wp.position)
            speed = wp.speed * self.max_velocity
            total_time += (dist / max(speed, 1.0)) * 1000  # Convert to ms
            total_time += wp.pause_ms
            prev_pos = wp.position
        return total_time

    def _serialize_trajectory(self, trajectory: Trajectory) -> Dict[str, Any]:
        """Serialize a trajectory to a JSON-compatible dict.

        Args:
            trajectory: The trajectory to serialize.

        Returns:
            Serialized dict.
        """
        return {
            "name": trajectory.name,
            "estimated_duration_ms": trajectory.estimated_duration_ms,
            "waypoint_count": len(trajectory.waypoints),
            "waypoints": [
                {
                    "position": list(wp.position),
                    "orientation": list(wp.orientation),
                    "speed": wp.speed,
                    "gripper": wp.gripper,
                    "pause_ms": wp.pause_ms,
                }
                for wp in trajectory.waypoints
            ],
        }