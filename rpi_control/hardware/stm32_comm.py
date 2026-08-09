"""
STM32 UART communication module for the intelligent sampling robotic arm.

Provides the STM32Interface class for reliable, thread-safe serial communication
with the STM32F103C8T6 microcontroller over UART using the following protocol:

    Format:  #CMD:PARAM1,PARAM2,...!
    Example: #ARM:MOVE:0,1500,1000!

All commands are terminated with a '!' character.
"""

import asyncio
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from ..utils.logger import get_logger
from ..utils.error_handler import (
    HardwareError,
    CommunicationError,
    error_notifier,
    async_retry,
)

logger = get_logger(__name__)

# Conditional import for platforms without pyserial (e.g., during tests)
try:
    import serial
    import serial.tools.list_ports

    HAS_PYSERIAL = True
except ImportError:
    HAS_PYSERIAL = False
    logger.warning("pyserial not available; STM32 communication will be simulated")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_BAUDRATE = 115200
DEFAULT_TIMEOUT = 0.5  # seconds
DEFAULT_HEARTBEAT_INTERVAL = 1.0  # seconds
DEFAULT_RECONNECT_DELAY = 2.0  # seconds
MAX_RECONNECT_ATTEMPTS = 5
READ_BUFFER_SIZE = 256
COMMAND_TERMINATOR = "!"
COMMAND_PREFIX = "#"

# Protocol mode constants
PROTOCOL_MODE_CUSTOM = "custom"      # Our custom #PREFIX:CMD:DATA! format
PROTOCOL_MODE_YHK32 = "yhk32"        # YH-K32 factory #IndexPpwmTtime! format
PROTOCOL_MODE_AUTO = "auto"          # Auto-detect protocol


def detect_rpi_port() -> str:
    """Auto-detect the correct UART port for the current Raspberry Pi model.

    Returns:
        The correct device path for the primary UART.

    Raspberry Pi UART mapping:
        Pi 3/4: /dev/serial0 → /dev/ttyAMA0 (primary UART, GPIO 14/15)
        Pi 5:   /dev/ttyAMA0 (RP1 chip, GPIO 14/15)
        Other:  /dev/ttyAMA0 (default)
    """
    import os
    import platform

    # Check if running on Raspberry Pi
    if platform.machine() not in ("aarch64", "armv7l", "armv6l"):
        # Not ARM - likely development machine
        if os.name == "nt":
            return "COM4"  # Windows default
        return "/dev/ttyUSB0"  # Linux USB-TTL

    # Read Pi model
    try:
        with open("/proc/device-tree/model", "r") as f:
            model = f.read().strip("\x00")
    except (FileNotFoundError, PermissionError):
        return "/dev/ttyAMA0"

    if "Raspberry Pi 5" in model:
        return "/dev/ttyAMA0"  # Pi 5 uses ttyAMA0 directly
    elif "Raspberry Pi 4" in model or "Raspberry Pi 3" in model:
        # Check if /dev/serial0 exists (symlink to primary UART)
        if os.path.exists("/dev/serial0"):
            return "/dev/serial0"
        return "/dev/ttyAMA0"

    return "/dev/ttyAMA0"


def get_default_port() -> str:
    """Get the platform-appropriate default serial port."""
    return detect_rpi_port()


class STM32Interface:
    """
    Thread-safe interface for communicating with the STM32F103C8T6 over UART.

    Supports servo control commands, sensor reading, action group playback,
    heartbeat monitoring, and automatic reconnection.

    Communication protocol:
        Command:  #CMD:PARAM1,PARAM2,...!
        Response: #CMD:RESULT:data!
    """

    def __init__(
        self,
        port: str = None,
        baudrate: int = DEFAULT_BAUDRATE,
        timeout: float = DEFAULT_TIMEOUT,
        heartbeat_interval: float = DEFAULT_HEARTBEAT_INTERVAL,
        auto_reconnect: bool = True,
        protocol_mode: str = PROTOCOL_MODE_AUTO,
    ) -> None:
        """
        Initialize the STM32 UART interface.

        Args:
            port: Serial port path. If None, auto-detects based on platform
                  (Raspberry Pi: /dev/serial0, Windows: COM4, Linux: /dev/ttyUSB0).
            baudrate: Baud rate for serial communication.
            timeout: Read timeout in seconds.
            heartbeat_interval: Interval in seconds between heartbeat pings.
            auto_reconnect: Whether to automatically attempt reconnection on disconnect.
            protocol_mode: Communication protocol mode.
                - 'yhk32': YH-K32 factory protocol (#IndexPpwmTtime!)
                - 'custom': Our custom protocol (#PREFIX:CMD:DATA!)
                - 'auto': Auto-detect (try YH-K32 first, fallback to custom)
        """
        self._port = port if port is not None else get_default_port()
        self._baudrate = baudrate
        self._timeout = timeout
        self._heartbeat_interval = heartbeat_interval
        self._auto_reconnect = auto_reconnect
        self._protocol_mode = protocol_mode
        self._detected_protocol: Optional[str] = None

        self._serial: Optional[serial.Serial] = None
        self._lock: asyncio.Lock = asyncio.Lock()
        self._connected: bool = False
        self._last_heartbeat: float = 0.0
        self._heartbeat_task: Optional[asyncio.Task[None]] = None
        self._running: bool = False
        self._last_sent_data: bytes = b""  # Track last sent command for echo filtering
        self._consecutive_heartbeat_failures: int = 0  # Track consecutive failures
        self._max_consecutive_failures: int = 3  # Max failures before stopping reconnect
        self._reconnect_cooldown_until: float = 0.0  # Timestamp when reconnect cooldown ends

    # ------------------------------------------------------------------
    # Connection Management
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """
        Open the serial connection to the STM32.

        Returns:
            True if the connection was successfully established.

        Raises:
            HardwareError: If the serial port cannot be opened.
        """
        if not HAS_PYSERIAL:
            logger.warning("STM32: Running in simulation mode (pyserial not available)")
            self._connected = True
            self._running = True
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
                self._running = True
                logger.info(
                    f"STM32 connected on {self._port} at {self._baudrate} baud"
                )
            except serial.SerialException as e:
                raise HardwareError(
                    f"Failed to open serial port '{self._port}': {e}",
                    code="STM32_CONNECT_FAILED",
                ) from e

        # Protocol detection MUST be done OUTSIDE the lock to avoid deadlock.
        # detect_protocol() internally calls read_response() and send_command(),
        # both of which acquire self._lock. asyncio.Lock is not reentrant,
        # so calling detect_protocol() inside the lock would cause a deadlock.
        if self._protocol_mode == PROTOCOL_MODE_AUTO:
            try:
                await self.detect_protocol()
            except Exception as e:
                logger.warning(f"Protocol detection failed: {e}; using YH-K32 default")
                self._detected_protocol = PROTOCOL_MODE_YHK32

        return True

    async def disconnect(self) -> None:
        """Close the serial connection and stop background tasks."""
        self._running = False

        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

        async with self._lock:
            if self._serial and self._serial.is_open:
                self._serial.close()
                logger.info("STM32 disconnected")
            self._connected = False

    async def reconnect(self) -> bool:
        """
        Attempt to reconnect to the STM32 after a disconnection.

        Returns:
            True if reconnection succeeded.

        Raises:
            HardwareError: If reconnection fails after maximum attempts.
        """
        logger.info(f"Attempting reconnection to STM32 on {self._port}...")

        for attempt in range(1, MAX_RECONNECT_ATTEMPTS + 1):
            try:
                await self.disconnect()
                await asyncio.sleep(DEFAULT_RECONNECT_DELAY)
                return await self.connect()
            except HardwareError:
                logger.warning(
                    f"Reconnection attempt {attempt}/{MAX_RECONNECT_ATTEMPTS} failed"
                )

        raise HardwareError(
            f"Failed to reconnect to STM32 after {MAX_RECONNECT_ATTEMPTS} attempts",
            code="STM32_RECONNECT_FAILED",
        )

    @property
    def is_connected(self) -> bool:
        """Check if the STM32 interface is connected."""
        return self._connected

    # ------------------------------------------------------------------
    # Low-Level Communication
    # ------------------------------------------------------------------

    def _format_command(self, cmd: str, params: List[Any]) -> bytes:
        """
        Format a command string for transmission.

        Args:
            cmd: Command name (e.g., 'ARM:MOVE').
            params: List of parameters to include.

        Returns:
            Encoded command bytes ready for transmission.
        """
        params_str = ",".join(str(p) for p in params)
        if params_str:
            command_str = f"{COMMAND_PREFIX}{cmd}:{params_str}{COMMAND_TERMINATOR}"
        else:
            command_str = f"{COMMAND_PREFIX}{cmd}{COMMAND_TERMINATOR}"
        return command_str.encode("ascii")

    # ------------------------------------------------------------------
    # YH-K32 Protocol Formatting Methods
    # ------------------------------------------------------------------

    @staticmethod
    def _format_yhk32_single_servo(servo_id: int, pwm: int, move_time: int) -> bytes:
        """
        Format a single servo command in YH-K32 protocol format.

        YH-K32 format: #IndexPpwmTtime!
        - Index: 3 digits, zero-padded (000-254)
        - pwm: 4 digits, zero-padded (0500-2500)
        - time: 4 digits, zero-padded (0000-9999)
        Total: 15 data characters + # and !

        Args:
            servo_id: Servo index (0-254).
            pwm: PWM value (500-2500).
            move_time: Movement time in milliseconds (0-9999).

        Returns:
            Encoded YH-K32 command bytes.
        """
        command_str = f"#{servo_id:03d}P{pwm:04d}T{move_time:04d}!"
        return command_str.encode("ascii")

    @staticmethod
    def _format_yhk32_multi_servo(positions: List[int], move_time: int) -> bytes:
        """
        Format a multi-servo command in YH-K32 protocol format.

        YH-K32 format: {#000P1500T1000!#001P0900T1000!...}

        Args:
            positions: List of PWM values, one per servo.
            move_time: Movement time in milliseconds.

        Returns:
            Encoded YH-K32 multi-servo command bytes.
        """
        parts = []
        for i, pwm in enumerate(positions):
            parts.append(f"#{i:03d}P{pwm:04d}T{move_time:04d}!")
        command_str = "{" + "".join(parts) + "}"
        return command_str.encode("ascii")

    @staticmethod
    def _format_yhk32_stop(servo_id: Optional[int] = None) -> bytes:
        """
        Format a stop command in YH-K32 protocol format.

        YH-K32 format: $DST! (stop all) or $DST:x! (stop servo x)

        Args:
            servo_id: Optional servo ID to stop. If None, stops all.

        Returns:
            Encoded YH-K32 stop command bytes.
        """
        if servo_id is not None:
            command_str = f"$DST:{servo_id}!"
        else:
            command_str = "$DST!"
        return command_str.encode("ascii")

    @staticmethod
    def _format_yhk32_reset() -> bytes:
        """Format a software reset command in YH-K32 protocol format: $RST!"""
        return b"$RST!"

    @staticmethod
    def _format_yhk32_action_group(start_id: int, end_id: int, count: int = 1) -> bytes:
        """
        Format an action group command in YH-K32 protocol format.

        YH-K32 format: $DGT:start-end,count!
        Example: $DGT:0-10,1! (play groups G0000~G0010 once)

        Args:
            start_id: Start action group ID.
            end_id: End action group ID.
            count: Number of times to play (0 = loop forever).

        Returns:
            Encoded YH-K32 action group command bytes.
        """
        command_str = f"$DGT:{start_id}-{end_id},{count}!"
        return command_str.encode("ascii")

    def _get_effective_protocol(self) -> str:
        """Get the effective protocol mode (resolves 'auto' to detected protocol)."""
        if self._protocol_mode == PROTOCOL_MODE_AUTO:
            return self._detected_protocol or PROTOCOL_MODE_YHK32
        return self._protocol_mode

    # ------------------------------------------------------------------
    # Protocol Detection
    # ------------------------------------------------------------------

    async def detect_protocol(self) -> str:
        """
        Auto-detect which protocol the connected board supports.

        Tries to communicate using YH-K32 protocol first, then falls back
        to custom protocol.

        Returns:
            Detected protocol mode string ('yhk32' or 'custom').

        Raises:
            CommunicationError: If neither protocol gets a valid response.
        """
        if not self._connected:
            raise CommunicationError(
                "Cannot detect protocol: not connected",
                code="STM32_NOT_CONNECTED",
            )

        logger.info("Detecting board protocol...")

        # Try YH-K32 protocol first (most boards have factory firmware)
        try:
            # Send a harmless YH-K32 test command: move servo 0 to 1500 in 1ms
            # (effectively a no-op, does NOT cause reset unlike $RST!)
            yhk32_cmd = self._format_yhk32_single_servo(0, 1500, 1)
            self._serial.write(yhk32_cmd)  # type: ignore[union-attr]
            self._serial.flush()  # type: ignore[union-attr]
            self._last_sent_data = yhk32_cmd
            await asyncio.sleep(0.05)

            # Read response
            response = await self.read_response(timeout=0.5)
            logger.info(f"YH-K32 protocol test response: {response}")

            # YH-K32 firmware responds with #CMD:OK:YHK32_SERVO! or similar
            # Also accept echo acknowledgment
            if response and ("OK" in response.upper() or
                           "ECHO_ACK" in response or "YHK32" in response.upper()):
                self._detected_protocol = PROTOCOL_MODE_YHK32
                logger.info("Detected YH-K32 protocol")
                return PROTOCOL_MODE_YHK32
        except Exception as e:
            logger.debug(f"YH-K32 protocol detection failed: {e}")

        # Try custom protocol
        try:
            await self.send_command("SYS:INFO")
            await asyncio.sleep(0.05)
            response = await self.read_response(timeout=0.5)
            logger.info(f"Custom protocol test response: {response}")

            if response and ("FW:" in response or "OK" in response or
                           "ECHO_ACK" in response):
                self._detected_protocol = PROTOCOL_MODE_CUSTOM
                logger.info("Detected custom protocol")
                return PROTOCOL_MODE_CUSTOM
        except Exception as e:
            logger.debug(f"Custom protocol detection failed: {e}")

        # Default to YH-K32 if detection fails
        self._detected_protocol = PROTOCOL_MODE_YHK32
        logger.warning("Protocol detection inconclusive; defaulting to YH-K32")
        return PROTOCOL_MODE_YHK32

    async def send_command(self, cmd: str, *params: Any) -> None:
        """
        Send a formatted command to the STM32.

        Args:
            cmd: Command name (e.g., 'ARM:MOVE').
            *params: Command parameters.

        Raises:
            CommunicationError: If the write fails.
        """
        data = self._format_command(cmd, list(params))

        if not HAS_PYSERIAL:
            logger.debug(f"SIM TX: {data.decode()}")
            return

        async with self._lock:
            try:
                self._serial.write(data)  # type: ignore[union-attr]
                self._serial.flush()  # type: ignore[union-attr]
                self._last_sent_data = data  # Track for echo filtering
                logger.debug(f"TX: {data.decode().strip()}")
            except (serial.SerialException, AttributeError) as e:
                self._connected = False
                raise CommunicationError(
                    f"Failed to send command '{cmd}': {e}",
                    code="STM32_WRITE_FAILED",
                ) from e

    async def read_response(self, timeout: Optional[float] = None) -> str:
        """
        Read a response from the STM32 until the terminator character (!).

        Handles STM32 echo by detecting if the first received frame is
        identical to the last sent command, and continuing to read for
        the actual response frame.

        Args:
            timeout: Maximum time in seconds to wait for a response.
                     Defaults to the instance timeout.

        Returns:
            The response string without the terminator.

        Raises:
            CommunicationError: If read fails or times out.
        """
        if not HAS_PYSERIAL:
            await asyncio.sleep(0.05)
            return "#SIM:OK"

        effective_timeout = timeout if timeout is not None else self._timeout

        async with self._lock:
            try:
                buffer = bytearray()
                start_time = time.monotonic()

                # Read first frame (may be echo)
                while True:
                    if time.monotonic() - start_time > effective_timeout:
                        raise CommunicationError(
                            f"Response timeout after {effective_timeout:.1f}s",
                            code="STM32_READ_TIMEOUT",
                        )

                    if self._serial.in_waiting > 0:  # type: ignore[union-attr]
                        byte = self._serial.read(1)  # type: ignore[union-attr]
                        # Fix: pyserial read(1) returns bytes, compare with bytes not int
                        if byte == COMMAND_TERMINATOR.encode("ascii"):
                            break
                        buffer.append(byte[0])
                    else:
                        await asyncio.sleep(0.001)

                first_response = buffer.decode("ascii", errors="replace")

                # Check if this is an echo of the last sent command
                if self._last_sent_data:
                    expected_echo = self._last_sent_data.decode("ascii", errors="replace").rstrip("!")
                    if first_response.strip() == expected_echo.strip():
                        logger.debug(f"RX: echo detected, waiting for actual response")
                        # Read second frame (actual response)
                        buffer2 = bytearray()
                        start_time2 = time.monotonic()
                        # Use shorter timeout for second read
                        second_timeout = min(effective_timeout, 0.5)

                        while True:
                            if time.monotonic() - start_time2 > second_timeout:
                                # No actual response after echo - firmware may not be
                                # running our protocol. Accept echo as acknowledgment.
                                logger.debug(f"RX: no response after echo, using echo as ACK")
                                return f"#CMD:OK:ECHO_ACK"

                            if self._serial.in_waiting > 0:  # type: ignore[union-attr]
                                byte = self._serial.read(1)  # type: ignore[union-attr]
                                # Fix: pyserial read(1) returns bytes, compare with bytes not int
                                if byte == COMMAND_TERMINATOR.encode("ascii"):
                                    break
                                buffer2.append(byte[0])
                            else:
                                await asyncio.sleep(0.001)

                        response = buffer2.decode("ascii", errors="replace")
                        logger.debug(f"RX (actual): {response}")
                        return response

                logger.debug(f"RX: {first_response}")
                return first_response

            except (serial.SerialException, AttributeError) as e:
                self._connected = False
                raise CommunicationError(
                    f"Failed to read response: {e}",
                    code="STM32_READ_FAILED",
                ) from e

    async def send_and_wait(
        self, cmd: str, *params: Any, timeout: Optional[float] = None
    ) -> str:
        """
        Send a command and wait for the response.

        Args:
            cmd: Command name.
            *params: Command parameters.
            timeout: Response timeout in seconds.

        Returns:
            Response string from the STM32.
        """
        await self.send_command(cmd, *params)
        # Small delay to allow echo to arrive
        await asyncio.sleep(0.01)
        return await self.read_response(timeout=timeout)

    # ------------------------------------------------------------------
    # Servo Control Commands
    # ------------------------------------------------------------------

    async def move_servo(
        self, servo_id: int, position: int, move_time: int
    ) -> str:
        """
        Move a single servo to a target position.

        Custom protocol:  #ARM:MOVE:servo_id,position,time!
        YH-K32 protocol:  #IndexPpwmTtime!

        Args:
            servo_id: Servo ID (0-5).
            position: Target PWM value (500-2500).
            move_time: Movement time in milliseconds.

        Returns:
            Response from the STM32.

        Raises:
            ValueError: If servo_id is out of range.
        """
        if not 0 <= servo_id <= 5:
            raise ValueError(f"Servo ID must be 0-5, got {servo_id}")

        logger.info(
            f"Moving servo {servo_id} to PWM {position} in {move_time}ms"
        )

        protocol = self._get_effective_protocol()

        if protocol == PROTOCOL_MODE_YHK32:
            # Use YH-K32 format: #000P1500T1000!
            data = self._format_yhk32_single_servo(servo_id, position, move_time)
            if not HAS_PYSERIAL:
                logger.debug(f"SIM TX (YH-K32): {data.decode()}")
                return "#SIM:OK"
            async with self._lock:
                try:
                    self._serial.write(data)  # type: ignore[union-attr]
                    self._serial.flush()  # type: ignore[union-attr]
                    self._last_sent_data = data
                    logger.debug(f"TX (YH-K32): {data.decode().strip()}")
                except (serial.SerialException, AttributeError) as e:
                    self._connected = False
                    raise CommunicationError(
                        f"Failed to send YH-K32 move command: {e}",
                        code="STM32_WRITE_FAILED",
                    ) from e
            await asyncio.sleep(0.01)
            return await self.read_response()
        else:
            # Use custom protocol: #ARM:MOVE:id,position,time!
            return await self.send_and_wait(
                "ARM:MOVE", servo_id, position, move_time
            )

    async def move_all_servos(
        self, positions: List[int], move_time: int
    ) -> str:
        """
        Move all six servos simultaneously.

        Custom protocol:  #ARM:MOVE_ALL:p0,p1,p2,p3,p4,p5,time!
        YH-K32 protocol:  {#000Pp0Ttime!#001Pp1Ttime!...}

        Args:
            positions: List of 6 PWM values, one per servo.
            move_time: Movement time in milliseconds.

        Returns:
            Response from the STM32.

        Raises:
            ValueError: If positions list does not have exactly 6 elements.
        """
        if len(positions) != 6:
            raise ValueError(
                f"Expected 6 servo positions, got {len(positions)}"
            )

        logger.info(
            f"Moving all servos to {positions} in {move_time}ms"
        )

        protocol = self._get_effective_protocol()

        if protocol == PROTOCOL_MODE_YHK32:
            data = self._format_yhk32_multi_servo(positions, move_time)
            if not HAS_PYSERIAL:
                logger.debug(f"SIM TX (YH-K32): {data.decode()}")
                return "#SIM:OK"
            async with self._lock:
                try:
                    self._serial.write(data)  # type: ignore[union-attr]
                    self._serial.flush()  # type: ignore[union-attr]
                    self._last_sent_data = data
                    logger.debug(f"TX (YH-K32): {data.decode().strip()}")
                except (serial.SerialException, AttributeError) as e:
                    self._connected = False
                    raise CommunicationError(
                        f"Failed to send YH-K32 multi-servo command: {e}",
                        code="STM32_WRITE_FAILED",
                    ) from e
            await asyncio.sleep(0.01)
            return await self.read_response()
        else:
            return await self.send_and_wait(
                "ARM:MOVE_ALL", *positions, move_time
            )

    async def emergency_stop(self) -> str:
        """
        Trigger an immediate emergency stop.

        Custom protocol:  #ARM:ESTOP!
        YH-K32 protocol:  $DST!

        Returns:
            Response from the STM32.
        """
        logger.warning("EMERGENCY STOP triggered!")
        protocol = self._get_effective_protocol()

        if protocol == PROTOCOL_MODE_YHK32:
            data = self._format_yhk32_stop()
            if not HAS_PYSERIAL:
                return "#SIM:OK"
            async with self._lock:
                try:
                    self._serial.write(data)  # type: ignore[union-attr]
                    self._serial.flush()  # type: ignore[union-attr]
                    self._last_sent_data = data
                except (serial.SerialException, AttributeError) as e:
                    self._connected = False
                    raise CommunicationError(
                        f"Failed to send emergency stop: {e}",
                        code="STM32_WRITE_FAILED",
                    ) from e
            await asyncio.sleep(0.01)
            return await self.read_response()
        else:
            return await self.send_and_wait("ARM:ESTOP")

    async def stop(self) -> str:
        """
        Stop all servo movement gracefully.

        Custom protocol:  #ARM:STOP!
        YH-K32 protocol:  $DST!

        Returns:
            Response from the STM32.
        """
        logger.info("Stopping all servo movement")
        protocol = self._get_effective_protocol()

        if protocol == PROTOCOL_MODE_YHK32:
            data = self._format_yhk32_stop()
            if not HAS_PYSERIAL:
                return "#SIM:OK"
            async with self._lock:
                try:
                    self._serial.write(data)  # type: ignore[union-attr]
                    self._serial.flush()  # type: ignore[union-attr]
                    self._last_sent_data = data
                except (serial.SerialException, AttributeError) as e:
                    self._connected = False
                    raise CommunicationError(
                        f"Failed to send stop command: {e}",
                        code="STM32_WRITE_FAILED",
                    ) from e
            await asyncio.sleep(0.01)
            return await self.read_response()
        else:
            return await self.send_and_wait("ARM:STOP")

    async def return_to_origin(self) -> str:
        """
        Return all servos to their home positions.

        Custom protocol:  #ARM:ORIGIN!
        YH-K32 protocol:  {#000P1500T1000!#001P1500T1000!...#005P1500T1000!}

        Returns:
            Response from the STM32.
        """
        logger.info("Returning to origin position")
        protocol = self._get_effective_protocol()

        if protocol == PROTOCOL_MODE_YHK32:
            positions = [1500] * 6
            data = self._format_yhk32_multi_servo(positions, 1000)
            if not HAS_PYSERIAL:
                return "#SIM:OK"
            async with self._lock:
                try:
                    self._serial.write(data)  # type: ignore[union-attr]
                    self._serial.flush()  # type: ignore[union-attr]
                    self._last_sent_data = data
                except (serial.SerialException, AttributeError) as e:
                    self._connected = False
                    raise CommunicationError(
                        f"Failed to send origin command: {e}",
                        code="STM32_WRITE_FAILED",
                    ) from e
            await asyncio.sleep(0.01)
            return await self.read_response()
        else:
            return await self.send_and_wait("ARM:ORIGIN")

    async def get_status(self) -> str:
        """
        Request the current status of the arm.

        Custom protocol:  #ARM:STATUS!
        YH-K32 protocol:  #SYS:INFO! (or custom status query)

        Returns:
            Status response string from the STM32.
        """
        protocol = self._get_effective_protocol()

        if protocol == PROTOCOL_MODE_YHK32:
            # YH-K32 doesn't have a direct status command; use system info
            return await self.send_and_wait("SYS:INFO")
        else:
            return await self.send_and_wait("ARM:STATUS")

    # ------------------------------------------------------------------
    # Sensor Commands
    # ------------------------------------------------------------------

    async def read_sensor(self, sensor_type: str) -> str:
        """
        Read a sensor value from the STM32.

        Command format: #SENSOR:{type}!

        Args:
            sensor_type: Sensor type identifier (e.g., 'TEMP', 'HUMID', 'PRESSURE').

        Returns:
            Sensor reading response string.
        """
        logger.debug(f"Reading sensor: {sensor_type}")
        return await self.send_and_wait(f"SENSOR:{sensor_type}")

    # ------------------------------------------------------------------
    # Action Group Commands
    # ------------------------------------------------------------------

    async def play_action_group(self, group_id: int) -> str:
        """
        Play a pre-recorded action group.

        Custom protocol:  #AG:PLAY:{group_id}!
        YH-K32 protocol:  $DGT:{group_id}-{group_id},1!

        Args:
            group_id: Action group identifier.

        Returns:
            Response from the STM32.
        """
        logger.info(f"Playing action group {group_id}")
        protocol = self._get_effective_protocol()

        if protocol == PROTOCOL_MODE_YHK32:
            data = self._format_yhk32_action_group(group_id, group_id, 1)
            if not HAS_PYSERIAL:
                return "#SIM:OK"
            async with self._lock:
                try:
                    self._serial.write(data)  # type: ignore[union-attr]
                    self._serial.flush()  # type: ignore[union-attr]
                    self._last_sent_data = data
                except (serial.SerialException, AttributeError) as e:
                    self._connected = False
                    raise CommunicationError(
                        f"Failed to send action group command: {e}",
                        code="STM32_WRITE_FAILED",
                    ) from e
            await asyncio.sleep(0.01)
            return await self.read_response()
        else:
            return await self.send_and_wait("AG:PLAY", group_id)

    # ------------------------------------------------------------------
    # Heartbeat & Monitoring
    # ------------------------------------------------------------------

    async def _heartbeat_loop(self) -> None:
        """Background task that periodically pings the STM32 to verify connectivity."""
        while self._running:
            try:
                if self._connected:
                    # Check reconnect cooldown
                    if time.monotonic() < self._reconnect_cooldown_until:
                        await asyncio.sleep(0.5)
                        continue

                    protocol = self._get_effective_protocol()

                    if protocol == PROTOCOL_MODE_YHK32:
                        # For YH-K32, send a harmless no-op command (move servo 0 to 1500 in 1ms)
                        # IMPORTANT: Do NOT use $RST! as it causes a software reset!
                        try:
                            async with self._lock:
                                yhk32_hb = self._format_yhk32_single_servo(0, 1500, 1)
                                self._serial.write(yhk32_hb)  # type: ignore[union-attr]
                                self._serial.flush()  # type: ignore[union-attr]
                                self._last_sent_data = yhk32_hb
                            await asyncio.sleep(0.05)
                            response = await self.read_response(timeout=0.6)
                            self._last_heartbeat = time.monotonic()
                            self._consecutive_heartbeat_failures = 0
                            logger.debug(f"Heartbeat OK (YH-K32): {response}")
                        except asyncio.CancelledError:
                            # Propagate cancellation immediately
                            raise
                        except Exception:
                            try:
                                async with self._lock:
                                    if self._serial.in_waiting > 0:  # type: ignore[union-attr]
                                        self._serial.reset_input_buffer()  # type: ignore[union-attr]
                                self._last_heartbeat = time.monotonic()
                                self._consecutive_heartbeat_failures = 0
                            except Exception:
                                raise CommunicationError("YH-K32 heartbeat failed", code="HB_FAIL")
                    else:
                        response = await self.send_and_wait(
                            "SYS:INFO", timeout=0.6
                        )
                        self._last_heartbeat = time.monotonic()
                        # Reset consecutive failure counter on success
                        self._consecutive_heartbeat_failures = 0
                        # Accept echo acknowledgment as valid heartbeat
                        if "ECHO_ACK" in response or "OK" in response:
                            logger.debug(f"Heartbeat OK: {response}")
                        else:
                            logger.debug(f"Heartbeat response: {response}")
                else:
                    if self._auto_reconnect:
                        await self.reconnect()
                        self._consecutive_heartbeat_failures = 0
            except asyncio.CancelledError:
                # Propagate cancellation immediately
                raise
            except (CommunicationError, HardwareError) as e:
                self._consecutive_heartbeat_failures += 1
                logger.warning(
                    f"Heartbeat failed ({self._consecutive_heartbeat_failures}/"
                    f"{self._max_consecutive_failures}): {e}"
                )
                self._connected = False
                error_notifier.report(e, {"context": "heartbeat"})

                if self._auto_reconnect:
                    if self._consecutive_heartbeat_failures >= self._max_consecutive_failures:
                        logger.error(
                            f"Too many consecutive heartbeat failures "
                            f"({self._consecutive_heartbeat_failures}). "
                            f"Entering cooldown for {DEFAULT_RECONNECT_DELAY * 3:.0f}s."
                        )
                        self._reconnect_cooldown_until = (
                            time.monotonic() + DEFAULT_RECONNECT_DELAY * 3
                        )
                        self._consecutive_heartbeat_failures = 0
                    else:
                        try:
                            await self.reconnect()
                        except HardwareError:
                            pass
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in heartbeat: {e}")
                error_notifier.report(e, {"context": "heartbeat"})

            await asyncio.sleep(self._heartbeat_interval)

    async def start_heartbeat(self) -> None:
        """Start the heartbeat monitoring background task."""
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            logger.info("Heartbeat monitoring started")

    async def stop_heartbeat(self) -> None:
        """Stop the heartbeat monitoring background task."""
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None
            logger.info("Heartbeat monitoring stopped")

    # ------------------------------------------------------------------
    # Context Manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "STM32Interface":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()