"""
UART Communication Protocol for OpenMV H7 Plus.

Implements a simple but robust text-based protocol over UART(3) for
communication between the OpenMV camera and the Raspberry Pi controller.

Protocol format:
    Request:  #command:param1:param2:...!
    Response: #vision:type:payload!

The protocol uses `#` as start marker, `:` as field separator, and `!` as
end marker to ensure reliable framing on a serial line.
"""

import time
from typing import Optional, Tuple, List, Dict, Any, Union

try:
    from pyb import UART
except ImportError:
    # Allow running on non-OpenMV platforms for testing
    class UART:
        """Mock UART for testing."""
        def __init__(self, bus: int, baudrate: int, **kwargs: Any) -> None:
            self.bus = bus
            self.baudrate = baudrate
            self._buf: bytearray = bytearray()

        def write(self, data: Union[str, bytes]) -> None:
            pass

        def readline(self) -> Optional[bytes]:
            return None

        def any(self) -> int:
            return 0

        def read(self, nbytes: int) -> Optional[bytes]:
            return None


# Protocol constants
PROTOCOL_START: str = "#"
PROTOCOL_END: str = "!"
PROTOCOL_SEPARATOR: str = ":"
PROTOCOL_PREFIX: str = "vision"
MAX_MESSAGE_LENGTH: int = 256
COMMAND_TIMEOUT_MS: int = 1000


class UARTProtocol:
    """UART communication protocol handler.

    Manages bidirectional communication over UART(3) at 115200 baud,
    using the `#vision:type:data!` framing format.

    Supported commands:
        - detect_color:<color_name>[:<roi>]
        - detect_apriltag[:<tag_id>]
        - classify
        - inspect[:<sample_id>]
        - track:<object_id>
        - set_threshold:<color_name>:<L_MIN>:<L_MAX>:<A_MIN>:<A_MAX>:<B_MIN>:<B_MAX>
        - get_config

    Attributes:
        uart: The UART peripheral instance.
        baudrate: Current baud rate.
        buf: Internal receive buffer.
    """

    def __init__(self, bus: int = 3, baudrate: int = 115200) -> None:
        """Initialize UART protocol on the specified bus.

        Args:
            bus: UART bus number (default 3, uses P4/P5).
            baudrate: Baud rate (default 115200).
        """
        self.bus: int = bus
        self.baudrate: int = baudrate
        self.uart: UART = UART(bus, baudrate, timeout=1000, timeout_char=1000)
        self._buf: str = ""
        self._last_error: Optional[str] = None

    def send_response(self, data_type: str, data: str) -> None:
        """Send a response frame over UART.

        Formats the message as `#vision:<type>:<data>!` and writes it
        to the UART bus.

        Args:
            data_type: Response type string (e.g., 'color', 'apriltag', 'error').
            data: Payload string to send.
        """
        message = f"{PROTOCOL_START}{PROTOCOL_PREFIX}{PROTOCOL_SEPARATOR}{data_type}{PROTOCOL_SEPARATOR}{data}{PROTOCOL_END}"
        encoded = message.encode("utf-8")
        if len(encoded) > MAX_MESSAGE_LENGTH:
            # Truncation would corrupt the frame; raise an error
            raise ValueError(f"Message exceeds {MAX_MESSAGE_LENGTH} bytes: {len(encoded)} bytes")
        self.uart.write(encoded)

    def send_error(self, error_code: int, error_message: str) -> None:
        """Send an error response.

        Args:
            error_code: Integer error code.
            error_message: Human-readable error description.
        """
        self.send_response("error", f"{error_code}:{error_message}")

    def send_ack(self, message: str = "ok") -> None:
        """Send an acknowledgment response.

        Args:
            message: Acknowledgment message text.
        """
        self.send_response("ack", message)

    def receive_command(self, timeout_ms: int = COMMAND_TIMEOUT_MS) -> Optional[Dict[str, Any]]:
        """Block until a complete command frame is received or timeout.

        Reads from UART character by character until a complete
        `#...!` frame is assembled, then parses it.

        Args:
            timeout_ms: Maximum time to wait in milliseconds.

        Returns:
            Parsed command dict with keys 'type' and 'params', or None on timeout.
        """
        start_time = time.ticks_ms()
        self._buf = ""

        while time.ticks_diff(time.ticks_ms(), start_time) < timeout_ms:
            if self.uart.any():
                char = self.uart.read(1)
                if char is not None:
                    ch = char.decode("utf-8", errors="replace")
                    if ch == PROTOCOL_START:
                        # Start of new frame; reset buffer
                        self._buf = ""
                    elif ch == PROTOCOL_END:
                        # End of frame; parse and return
                        if self._buf:
                            return self.parse_command(self._buf)
                        return None
                    else:
                        self._buf += ch
                        if len(self._buf) > MAX_MESSAGE_LENGTH:
                            # Buffer overflow; reset
                            self._buf = ""

            time.sleep_ms(1)

        return None  # Timeout

    def parse_command(self, data: str) -> Optional[Dict[str, Any]]:
        """Parse a raw command string into a structured dict.

        Expected format: `command:param1:param2:...`
        If the string starts with the protocol prefix, it is stripped.

        Args:
            data: Raw command string (without start/end markers).

        Returns:
            Dict with 'type' (str) and 'params' (List[str]) keys, or None if invalid.
        """
        if not data:
            return None

        # Strip protocol prefix if present
        if data.startswith(PROTOCOL_PREFIX + PROTOCOL_SEPARATOR):
            data = data[len(PROTOCOL_PREFIX + PROTOCOL_SEPARATOR):]

        parts = data.split(PROTOCOL_SEPARATOR)
        if len(parts) < 1:
            return None

        command_type = parts[0].strip().lower()
        params = [p.strip() for p in parts[1:] if p.strip()]

        return {
            "type": command_type,
            "params": params,
        }

    def get_supported_commands(self) -> List[str]:
        """Return the list of supported command types.

        Returns:
            List of command name strings.
        """
        return [
            "detect_color",
            "detect_apriltag",
            "classify",
            "inspect",
            "track",
            "set_threshold",
            "get_config",
        ]

    def flush_input(self) -> None:
        """Discard any pending data in the UART receive buffer."""
        while self.uart.any():
            self.uart.read(1)
        self._buf = ""

    @property
    def last_error(self) -> Optional[str]:
        """Get the last error message, if any."""
        return self._last_error