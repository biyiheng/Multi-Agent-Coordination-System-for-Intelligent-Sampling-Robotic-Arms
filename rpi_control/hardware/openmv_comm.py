"""
OpenMV H7 Plus communication module for the intelligent sampling robotic arm.

Provides the OpenMVInterface class for communicating with the OpenMV camera
module over UART, supporting color detection, AprilTag detection, object
classification, and quality inspection.
"""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Tuple

from ..utils.logger import get_logger
from ..utils.error_handler import (
    CommunicationError,
    VisionError,
    error_notifier,
    async_retry,
)

logger = get_logger(__name__)

# Conditional import for platforms without pyserial
try:
    import serial

    HAS_PYSERIAL = True
except ImportError:
    HAS_PYSERIAL = False
    logger.warning("pyserial not available; OpenMV communication will be simulated")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_BAUDRATE = 115200
DEFAULT_TIMEOUT = 1.0  # seconds
COMMAND_PREFIX = "#"
COMMAND_TERMINATOR = "!"
READ_BUFFER_SIZE = 512


class OpenMVInterface:
    """
    Asynchronous interface for communicating with the OpenMV H7 Plus camera.

    Supports color detection, AprilTag pose estimation, object classification,
    and quality inspection via structured UART commands.

    Two modes are supported:
    - Direct serial: Opens a dedicated serial port to the OpenMV.
    - STM32 passthrough: Routes commands through the STM32's UART2 bridge.
    """

    def __init__(
        self,
        port: str = "/dev/ttyUSB0",
        baudrate: int = DEFAULT_BAUDRATE,
        timeout: float = DEFAULT_TIMEOUT,
        stm32_interface: Any = None,
    ) -> None:
        """
        Initialize the OpenMV interface.

        Args:
            port: Serial port path (e.g., '/dev/ttyUSB0').
            baudrate: Baud rate for serial communication.
            timeout: Read timeout in seconds.
            stm32_interface: Optional STM32Interface for passthrough mode.
                             When provided, commands are routed through STM32
                             instead of opening a direct serial connection.
        """
        self._port = port
        self._baudrate = baudrate
        self._timeout = timeout

        self._serial: Optional[serial.Serial] = None
        self._lock: asyncio.Lock = asyncio.Lock()
        self._connected: bool = False

        # STM32 passthrough mode
        self._stm32: Any = stm32_interface
        self._passthrough_mode: bool = stm32_interface is not None

    # ------------------------------------------------------------------
    # Connection Management
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """
        Open the serial connection to the OpenMV camera.

        In passthrough mode, simply marks as connected since commands
        will be routed through the STM32 interface.

        Returns:
            True if the connection was successfully established.

        Raises:
            CommunicationError: If the serial port cannot be opened.
        """
        # Passthrough mode: use STM32 bridge
        if self._passthrough_mode and self._stm32 is not None:
            if self._stm32.is_connected:
                self._connected = True
                logger.info("OpenMV: Running in STM32 passthrough mode")
                return True
            else:
                raise CommunicationError(
                    "STM32 not connected, cannot use OpenMV passthrough",
                    code="OPENMV_PASSTHROUGH_FAILED",
                )

        if not HAS_PYSERIAL:
            logger.warning(
                "OpenMV: Running in simulation mode (pyserial not available)"
            )
            self._connected = True
            return True

        async with self._lock:
            try:
                self._serial = serial.Serial(
                    port=self._port,
                    baudrate=self._baudrate,
                    timeout=self._timeout,
                    write_timeout=self._timeout,
                )
                self._serial.reset_input_buffer()
                self._serial.reset_output_buffer()
                self._connected = True
                logger.info(
                    f"OpenMV connected on {self._port} at {self._baudrate} baud"
                )
                return True
            except serial.SerialException as e:
                raise CommunicationError(
                    f"Failed to open OpenMV serial port '{self._port}': {e}",
                    code="OPENMV_CONNECT_FAILED",
                ) from e

    async def disconnect(self) -> None:
        """Close the serial connection to the OpenMV camera."""
        async with self._lock:
            if self._serial and self._serial.is_open:
                self._serial.close()
                logger.info("OpenMV disconnected")
            self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if the OpenMV interface is connected."""
        return self._connected

    # ------------------------------------------------------------------
    # Low-Level Communication
    # ------------------------------------------------------------------

    async def _send_raw(self, command: str) -> None:
        """
        Send a raw command string to the OpenMV.

        In passthrough mode, routes the command through the STM32's UART2 bridge
        using the VISION prefix.

        Args:
            command: Command string to send (without terminator, will be appended).

        Raises:
            CommunicationError: If the write fails.
        """
        if not self._connected:
            raise CommunicationError(
                "OpenMV is not connected", code="OPENMV_NOT_CONNECTED"
            )

        data = (command + COMMAND_TERMINATOR).encode("ascii")

        # Passthrough mode: route through STM32
        if self._passthrough_mode and self._stm32 is not None:
            try:
                # Extract command type and params from the command string
                # Format: #vision:CMD:PARAMS → send as VISION:CMD,PARAMS
                cmd_parts = command.lstrip(COMMAND_PREFIX).split(":", 2)
                if len(cmd_parts) >= 2:
                    vision_cmd = cmd_parts[1]
                    vision_data = cmd_parts[2] if len(cmd_parts) > 2 else ""
                    await self._stm32.send_and_wait(
                        f"VISION:{vision_cmd}", vision_data, timeout=self._timeout
                    )
                else:
                    await self._stm32.send_and_wait(
                        "VISION:DETECT", "", timeout=self._timeout
                    )
                logger.debug(f"OpenMV STM32 TX: {command}")
                return
            except Exception as e:
                raise CommunicationError(
                    f"Failed to send OpenMV command via STM32: {e}",
                    code="OPENMV_PASSTHROUGH_WRITE_FAILED",
                ) from e

        if not HAS_PYSERIAL:
            logger.debug(f"SIM OpenMV TX: {data.decode()}")
            await asyncio.sleep(0.02)
            return

        async with self._lock:
            try:
                self._serial.write(data)  # type: ignore[union-attr]
                self._serial.flush()  # type: ignore[union-attr]
                logger.debug(f"OpenMV TX: {data.decode().strip()}")
            except serial.SerialException as e:
                self._connected = False
                raise CommunicationError(
                    f"Failed to send to OpenMV: {e}",
                    code="OPENMV_WRITE_FAILED",
                ) from e

    async def _read_response(self) -> str:
        """
        Read a response from the OpenMV until the terminator character.

        In passthrough mode, returns a simulated response since the STM32
        firmware acknowledges forwarding but does not relay OpenMV responses
        synchronously. Full response relay requires STM32 firmware update.

        Returns:
            Response string without the terminator.

        Raises:
            CommunicationError: If read fails or times out.
        """
        # Passthrough mode: return simulation response
        if self._passthrough_mode:
            await asyncio.sleep(0.05)
            return json.dumps({"status": "ok", "detections": [], "note": "passthrough_sim"})

        if not HAS_PYSERIAL:
            await asyncio.sleep(0.05)
            return json.dumps({"status": "ok", "detections": []})

        async with self._lock:
            try:
                buffer = bytearray()
                start_time = time.monotonic()

                while True:
                    if time.monotonic() - start_time > self._timeout:
                        raise CommunicationError(
                            f"OpenMV response timeout after {self._timeout:.1f}s",
                            code="OPENMV_READ_TIMEOUT",
                        )

                    if self._serial.in_waiting > 0:  # type: ignore[union-attr]
                        byte = self._serial.read(1)  # type: ignore[union-attr]
                        # Fix: pyserial read(1) returns bytes, compare with bytes not int
                        if byte == COMMAND_TERMINATOR.encode("ascii"):
                            break
                        buffer.append(byte[0])
                    else:
                        await asyncio.sleep(0.001)

                response = buffer.decode("ascii", errors="replace")
                logger.debug(f"OpenMV RX: {response}")
                return response

            except serial.SerialException as e:
                self._connected = False
                raise CommunicationError(
                    f"Failed to read from OpenMV: {e}",
                    code="OPENMV_READ_FAILED",
                ) from e

    async def request_vision(self, vision_type: str, *args: Any) -> Dict[str, Any]:
        """
        Send a vision processing request and parse the response.

        Args:
            vision_type: Vision command type (e.g., 'detect_color', 'detect_apriltag').
            *args: Additional arguments for the command.

        Returns:
            Parsed response dictionary.

        Raises:
            VisionError: If the vision request fails.
        """
        if args:
            params = ",".join(str(a) for a in args)
            command = f"{COMMAND_PREFIX}vision:{vision_type}:{params}"
        else:
            command = f"{COMMAND_PREFIX}vision:{vision_type}"

        try:
            await self._send_raw(command)
            raw_response = await self._read_response()
            return self.parse_response(raw_response)
        except CommunicationError:
            raise
        except Exception as e:
            raise VisionError(
                f"Vision request '{vision_type}' failed: {e}",
                code="OPENMV_VISION_FAILED",
            ) from e

    @staticmethod
    def parse_response(data: str) -> Dict[str, Any]:
        """
        Parse a raw response string into a structured dictionary.

        Supports both JSON responses and simple key:value formats.

        Args:
            data: Raw response string from the OpenMV.

        Returns:
            Parsed dictionary with at minimum a 'status' key.

        Raises:
            VisionError: If the response cannot be parsed.
        """
        try:
            # Try JSON parsing first
            result = json.loads(data)
            if not isinstance(result, dict):
                return {"status": "ok", "raw": result}
            return result
        except json.JSONDecodeError:
            # Fall back to key:value parsing
            result: Dict[str, Any] = {"status": "unknown", "raw": data}
            try:
                pairs = data.split(",")
                for pair in pairs:
                    if ":" in pair:
                        key, value = pair.split(":", 1)
                        key = key.strip()
                        value = value.strip()
                        # Attempt numeric conversion
                        try:
                            value = int(value)
                        except ValueError:
                            try:
                                value = float(value)
                            except ValueError:
                                pass
                        result[key] = value
                    else:
                        result["status"] = pair.strip()
            except Exception:
                raise VisionError(
                    f"Failed to parse OpenMV response: {data}",
                    code="OPENMV_PARSE_FAILED",
                )
            return result

    # ------------------------------------------------------------------
    # Vision Detection Commands
    # ------------------------------------------------------------------

    async def detect_color(self, color_name: str) -> Dict[str, Any]:
        """
        Request color detection from the OpenMV camera.

        Args:
            color_name: Color to detect (e.g., 'red', 'blue', 'green').

        Returns:
            Detection results dictionary with bounding boxes and confidence scores.
        """
        logger.info(f"Requesting color detection: {color_name}")
        return await self.request_vision("detect_color", color_name)

    async def detect_apriltag(self, tag_family: str = "TAG36H11") -> Dict[str, Any]:
        """
        Request AprilTag detection from the OpenMV camera.

        Args:
            tag_family: AprilTag family to detect (e.g., 'TAG36H11', 'TAG25H9').

        Returns:
            Detection results with tag IDs, positions, and orientations.
        """
        logger.info(f"Requesting AprilTag detection: {tag_family}")
        return await self.request_vision("detect_apriltag", tag_family)

    async def classify_object(self) -> Dict[str, Any]:
        """
        Request object classification from the OpenMV camera.

        The camera runs a pre-trained model to classify objects in view.

        Returns:
            Classification results with class labels and confidence scores.
        """
        logger.info("Requesting object classification")
        return await self.request_vision("classify")

    async def inspect_quality(self) -> Dict[str, Any]:
        """
        Request quality inspection from the OpenMV camera.

        Performs visual inspection of the current sample or workpiece.

        Returns:
            Inspection results with quality metrics.
        """
        logger.info("Requesting quality inspection")
        return await self.request_vision("inspect")

    async def set_threshold(
        self,
        color: str,
        threshold: List[List[int]],
    ) -> Dict[str, Any]:
        """
        Configure color threshold values for detection.

        Args:
            color: Color name to configure.
            threshold: Threshold values in LAB color space format
                       [[L_min, L_max, A_min, A_max, B_min, B_max]].

        Returns:
            Configuration confirmation response.
        """
        threshold_str = json.dumps(threshold)
        logger.info(f"Setting threshold for '{color}': {threshold_str}")
        return await self.request_vision("set_threshold", color, threshold_str)

    async def get_image(self) -> Dict[str, Any]:
        """
        Request a snapshot or image data from the OpenMV camera.

        Returns:
            Image data response (may include base64-encoded image).
        """
        logger.debug("Requesting image capture")
        return await self.request_vision("get_image")

    async def get_version(self) -> Dict[str, Any]:
        """
        Request firmware version information from the OpenMV.

        Returns:
            Version information dictionary.
        """
        return await self.request_vision("version")

    # ------------------------------------------------------------------
    # Context Manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "OpenMVInterface":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()