"""
High-level servo controller module for the intelligent sampling robotic arm.

Wraps the STM32Interface to provide convenient, abstracted servo control
operations including joint-space movement, gripper control with adaptive
grip, position feedback, and motion monitoring.
"""

import asyncio
import time
from typing import Any, Dict, List, Optional

from .stm32_comm import STM32Interface
from ..utils.logger import get_logger
from ..utils.error_handler import (
    HardwareError,
    SafetyError,
    CommunicationError,
    error_notifier,
)

logger = get_logger(__name__)

# Default servo configuration
NUM_SERVOS = 6
DEFAULT_OPEN_PWM = 500
DEFAULT_CLOSE_PWM = 1800
DEFAULT_GRIP_FORCE = 1500
DEFAULT_MOVE_TIME = 1000  # ms
ADAPTIVE_GRIP_STEP = 50  # PWM step per iteration
ADAPTIVE_GRIP_DELAY = 0.1  # seconds between steps
DEFAULT_TIMEOUT = 5000  # ms


class ServoController:
    """
    High-level controller for the 6-DOF robotic arm servos.

    Provides methods for coordinated joint movement, gripper operations,
    adaptive grip with force feedback, and motion status monitoring.

    All methods are async and thread-safe via the underlying STM32Interface lock.
    """

    def __init__(
        self,
        stm32_interface: STM32Interface,
        open_pwm: int = DEFAULT_OPEN_PWM,
        close_pwm: int = DEFAULT_CLOSE_PWM,
        grip_force: int = DEFAULT_GRIP_FORCE,
        adaptive_enabled: bool = True,
    ) -> None:
        """
        Initialize the servo controller.

        Args:
            stm32_interface: Connected STM32Interface instance.
            open_pwm: PWM value for open gripper position.
            close_pwm: PWM value for fully closed gripper position.
            grip_force: PWM threshold for adaptive grip force detection.
            adaptive_enabled: Whether adaptive gripping is enabled by default.
        """
        self._stm32 = stm32_interface
        self._open_pwm = open_pwm
        self._close_pwm = close_pwm
        self._grip_force = grip_force
        self._adaptive_enabled = adaptive_enabled

        self._current_positions: List[int] = [1500] * NUM_SERVOS
        self._moving: bool = False
        self._last_move_start: float = 0.0
        self._estimated_move_duration: float = 0.0

    # ------------------------------------------------------------------
    # Joint Movement
    # ------------------------------------------------------------------

    async def move_to_joint_positions(
        self,
        positions: List[int],
        move_time: int = DEFAULT_MOVE_TIME,
    ) -> None:
        """
        Move all six joints to the specified PWM positions simultaneously.

        Args:
            positions: List of 6 PWM values, one per servo joint.
            move_time: Movement time in milliseconds.

        Raises:
            ValueError: If positions list does not have exactly 6 elements.
            SafetyError: If any position exceeds servo limits.
            CommunicationError: If the STM32 communication fails.
        """
        if len(positions) != NUM_SERVOS:
            raise ValueError(
                f"Expected {NUM_SERVOS} positions, got {len(positions)}"
            )

        # Validate PWM ranges
        for i, pos in enumerate(positions):
            if not 500 <= pos <= 2500:
                raise SafetyError(
                    f"Joint {i} position {pos} outside valid range [500, 2500]",
                    code="JOINT_LIMIT_VIOLATION",
                )

        logger.info(
            f"Moving all joints to {positions} over {move_time}ms"
        )

        self._moving = True
        self._last_move_start = time.monotonic()
        self._estimated_move_duration = move_time / 1000.0

        try:
            await self._stm32.move_all_servos(positions, move_time)
            self._current_positions = list(positions)
        except CommunicationError:
            self._moving = False
            raise
        except Exception as e:
            self._moving = False
            raise HardwareError(
                f"Failed to move joints: {e}",
                code="SERVO_MOVE_FAILED",
            ) from e

    async def move_single_joint(
        self,
        joint_id: int,
        position: int,
        move_time: int = DEFAULT_MOVE_TIME,
    ) -> None:
        """
        Move a single joint to the specified PWM position.

        Args:
            joint_id: Joint index (0-5).
            position: Target PWM value.
            move_time: Movement time in milliseconds.

        Raises:
            ValueError: If joint_id is out of range.
            SafetyError: If position exceeds servo limits.
        """
        if not 0 <= joint_id < NUM_SERVOS:
            raise ValueError(f"Joint ID must be 0-{NUM_SERVOS - 1}, got {joint_id}")

        if not 500 <= position <= 2500:
            raise SafetyError(
                f"Joint {joint_id} position {position} outside valid range [500, 2500]",
                code="JOINT_LIMIT_VIOLATION",
            )

        logger.info(
            f"Moving joint {joint_id} to PWM {position} over {move_time}ms"
        )

        try:
            await self._stm32.move_servo(joint_id, position, move_time)
            self._current_positions[joint_id] = position
        except CommunicationError:
            raise
        except Exception as e:
            raise HardwareError(
                f"Failed to move joint {joint_id}: {e}",
                code="SERVO_MOVE_FAILED",
            ) from e

    # ------------------------------------------------------------------
    # Gripper Operations
    # ------------------------------------------------------------------

    async def open_gripper(self) -> None:
        """
        Open the gripper to the configured open position.

        Joint 5 is the gripper servo.
        """
        logger.info(f"Opening gripper to PWM {self._open_pwm}")
        await self.move_single_joint(5, self._open_pwm)

    async def close_gripper(self, force: Optional[int] = None) -> None:
        """
        Close the gripper to the configured close position with optional force.

        Args:
            force: Override PWM value for closing force. If None, uses default close_pwm.
        """
        close_value = force if force is not None else self._close_pwm
        logger.info(f"Closing gripper to PWM {close_value}")
        await self.move_single_joint(5, close_value)

    async def adaptive_grip(self, force: Optional[int] = None) -> None:
        """
        Gradually close the gripper until resistance is detected.

        This method incrementally closes the gripper in steps, checking for
        resistance (stall current) at each step. This allows the gripper to
        adapt to objects of varying sizes without crushing them.

        Args:
            force: Maximum closing force PWM value. If None, uses grip_force.

        Raises:
            HardwareError: If adaptive grip fails.
        """
        if not self._adaptive_enabled:
            logger.warning("Adaptive grip disabled; using standard close")
            await self.close_gripper(force)
            return

        max_force = force if force is not None else self._grip_force
        logger.info(
            f"Starting adaptive grip from PWM {self._current_positions[5]} "
            f"to {max_force}"
        )

        current = self._current_positions[5]

        if current >= max_force:
            logger.info("Gripper already at or beyond target force; no action needed")
            return

        try:
            step = ADAPTIVE_GRIP_STEP
            while current < max_force:
                next_position = min(current + step, max_force)
                await self.move_single_joint(5, next_position, move_time=200)
                await asyncio.sleep(ADAPTIVE_GRIP_DELAY)

                # Check for stall detection via status
                status = await self._stm32.get_status()
                if self._check_stall(status):
                    logger.info(
                        f"Adaptive grip: stall detected at PWM {next_position}"
                    )
                    break

                current = next_position

            logger.info(f"Adaptive grip complete at PWM {self._current_positions[5]}")

        except Exception as e:
            raise HardwareError(
                f"Adaptive grip failed: {e}",
                code="ADAPTIVE_GRIP_FAILED",
            ) from e

    @staticmethod
    def _check_stall(status_response: str) -> bool:
        """
        Check if the status response indicates a stall condition.

        Args:
            status_response: Raw status string from the STM32.

        Returns:
            True if a stall is detected.
        """
        try:
            if "STALL" in status_response.upper():
                return True
            if "OVERLOAD" in status_response.upper():
                return True
            # Parse structured status if available
            data = status_response.split(",")
            for item in data:
                if ":" in item:
                    key, value = item.split(":", 1)
                    if key.strip().upper() == "GRIPPER_STALL" and value.strip() == "1":
                        return True
        except Exception:
            pass
        return False

    # ------------------------------------------------------------------
    # Position Feedback
    # ------------------------------------------------------------------

    async def get_current_positions(self) -> List[int]:
        """
        Query the current positions of all servos.

        Returns:
            List of 6 PWM values representing current joint positions.

        Raises:
            CommunicationError: If the STM32 communication fails.
        """
        try:
            response = await self._stm32.get_status()

            # Try to parse positions from status response
            # Expected format: #ARM:STATUS:POS:1500,1500,1500,1500,1500,1500!
            positions = self._parse_positions(response)
            if positions:
                self._current_positions = positions
                return positions

            # Fall back to cached positions
            logger.warning("Could not parse positions from status; using cached values")
            return list(self._current_positions)

        except CommunicationError:
            logger.warning("Failed to get positions; returning cached values")
            return list(self._current_positions)

    @staticmethod
    def _parse_positions(response: str) -> Optional[List[int]]:
        """
        Parse joint positions from a status response string.

        Args:
            response: Status response string from the STM32.

        Returns:
            List of 6 PWM values or None if parsing fails.
        """
        try:
            # Look for POS: prefix in the response
            if "POS:" in response:
                pos_start = response.index("POS:") + 4
                pos_str = response[pos_start:].split(",")[:NUM_SERVOS]
                positions = [int(p.strip()) for p in pos_str]
                if len(positions) == NUM_SERVOS:
                    return positions
        except (ValueError, IndexError):
            pass
        return None

    # ------------------------------------------------------------------
    # Motion Status
    # ------------------------------------------------------------------

    def is_moving(self) -> bool:
        """
        Check if the arm is currently in motion.

        Returns:
            True if a movement command was recently issued and may still be executing.
        """
        if not self._moving:
            return False

        elapsed = time.monotonic() - self._last_move_start
        if elapsed >= self._estimated_move_duration + 0.1:  # 100ms buffer
            self._moving = False
            return False

        return True

    async def wait_for_completion(
        self, timeout: float = DEFAULT_TIMEOUT / 1000.0
    ) -> bool:
        """
        Wait for the current movement to complete or timeout.

        Args:
            timeout: Maximum time to wait in seconds.

        Returns:
            True if the movement completed, False on timeout.
        """
        start = time.monotonic()
        while self.is_moving():
            if time.monotonic() - start > timeout:
                logger.warning(
                    f"Wait for completion timed out after {timeout:.1f}s"
                )
                return False
            await asyncio.sleep(0.01)

        logger.debug("Movement completed")
        return True

    # ------------------------------------------------------------------
    # Convenience Methods
    # ------------------------------------------------------------------

    async def home_all(self) -> None:
        """
        Move all servos to their home positions (PWM 1500).

        This sends the ORIGIN command to the STM32, which moves all servos
        to their pre-configured home positions.
        """
        logger.info("Returning all joints to home positions")
        self._moving = True
        self._last_move_start = time.monotonic()
        self._estimated_move_duration = 2.0  # estimated 2 seconds

        try:
            await self._stm32.return_to_origin()
            self._current_positions = [1500] * NUM_SERVOS
        except CommunicationError:
            self._moving = False
            raise

    async def emergency_stop(self) -> None:
        """
        Immediately stop all servo movement.

        Sends the emergency stop command to the STM32.
        """
        logger.critical("EMERGENCY STOP - Halting all servos!")
        self._moving = False
        await self._stm32.emergency_stop()

    async def stop(self) -> None:
        """Gracefully stop all servo movement."""
        logger.info("Stopping all servo movement")
        self._moving = False
        await self._stm32.stop()

    @property
    def current_positions(self) -> List[int]:
        """Get the cached current positions (last known values)."""
        return list(self._current_positions)

    @property
    def open_pwm(self) -> int:
        """Get the PWM value for the open gripper position."""
        return self._open_pwm

    @property
    def close_pwm(self) -> int:
        """Get the PWM value for the closed gripper position."""
        return self._close_pwm