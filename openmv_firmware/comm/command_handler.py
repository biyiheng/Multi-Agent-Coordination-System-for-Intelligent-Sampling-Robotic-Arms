"""
Command Handler / Dispatcher for OpenMV H7 Plus.

Routes incoming UART commands to the appropriate vision module handler
and formats the response for transmission back to the Raspberry Pi.

This module is the central dispatch layer that connects the communication
protocol with the vision processing modules.
"""

import json
from typing import Dict, Any, Callable, Optional, List, Set

try:
    from pyb import LED
except ImportError:
    # Mock for testing
    class LED:
        """Mock LED for testing."""
        def __init__(self, id: int) -> None:
            self.id = id
        def on(self) -> None:
            pass
        def off(self) -> None:
            pass
        def toggle(self) -> None:
            pass


# Type alias for handler functions
HandlerFunc = Callable[[Dict[str, Any]], Dict[str, Any]]


class CommandHandler:
    """Central command dispatcher for the OpenMV vision system.

    Handlers are registered for each command type and are invoked when
    a matching command is received. Results are serialized to JSON and
    returned for transmission via UART.

    Attributes:
        handlers: Mapping of command name to handler function.
        led: Status LED for visual feedback.
        registered_commands: Set of all registered command names.
    """

    # Error codes
    ERR_UNKNOWN_COMMAND: int = 1
    ERR_INVALID_PARAMS: int = 2
    ERR_HANDLER_FAILED: int = 3
    ERR_MODULE_NOT_READY: int = 4
    ERR_TIMEOUT: int = 5

    def __init__(self, led_id: int = 1) -> None:
        """Initialize the command handler.

        Args:
            led_id: Built-in LED ID for status indication (1=red, 2=green, 3=blue).
        """
        self.handlers: Dict[str, HandlerFunc] = {}
        self._led: Optional[LED] = None
        try:
            self._led = LED(led_id)
        except Exception:
            pass

    def register_handler(self, cmd: str, handler_fn: HandlerFunc) -> None:
        """Register a handler function for a specific command.

        Args:
            cmd: Command name string (e.g., 'detect_color').
            handler_fn: Callable that receives a dict with 'type' and 'params'
                        keys and returns a result dict.

        Raises:
            ValueError: If a handler is already registered for this command.
        """
        cmd = cmd.lower().strip()
        if cmd in self.handlers:
            raise ValueError(f"Handler already registered for command: {cmd}")
        self.handlers[cmd] = handler_fn

    def dispatch(self, command: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Route an incoming command to the appropriate handler.

        The command dict should have 'type' and 'params' keys, as produced
        by `UARTProtocol.parse_command()`.

        Args:
            command: Parsed command dict, or None.

        Returns:
            Result dict with 'success' (bool), 'type' (str), 'data' (Any),
            and optionally 'error' (str) and 'error_code' (int) keys.
        """
        if command is None:
            return self._error_response(
                self.ERR_TIMEOUT, "No command received (null)"
            )

        cmd_type = command.get("type", "")
        cmd_params = command.get("params", [])

        if not cmd_type:
            return self._error_response(
                self.ERR_UNKNOWN_COMMAND, "Empty command type"
            )

        if cmd_type not in self.handlers:
            return self._error_response(
                self.ERR_UNKNOWN_COMMAND, f"Unknown command: {cmd_type}"
            )

        try:
            # Build the handler input
            handler_input = {
                "type": cmd_type,
                "params": cmd_params,
            }
            result = self.handlers[cmd_type](handler_input)

            # Ensure the result has standard fields
            if "success" not in result:
                result["success"] = True
            if "type" not in result:
                result["type"] = cmd_type

            return result

        except Exception as e:
            return self._error_response(
                self.ERR_HANDLER_FAILED,
                f"Handler failed for '{cmd_type}': {str(e)}"
            )

    def handle_color_detection(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Default handler for color detection commands.

        This is a placeholder that should be overridden by registering
        a real handler from the ColorDetector module.

        Args:
            command: Parsed command dict.

        Returns:
            Structured result dict.
        """
        color_name = command["params"][0] if command["params"] else "red"
        return {
            "success": True,
            "type": "color",
            "data": {
                "color": color_name,
                "message": "Color detection handler not yet registered",
            },
        }

    def handle_apriltag_detection(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Default handler for AprilTag detection commands.

        Args:
            command: Parsed command dict.

        Returns:
            Structured result dict.
        """
        return {
            "success": True,
            "type": "apriltag",
            "data": {
                "message": "AprilTag handler not yet registered",
            },
        }

    def handle_classification(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Default handler for object classification commands.

        Args:
            command: Parsed command dict.

        Returns:
            Structured result dict.
        """
        return {
            "success": True,
            "type": "classification",
            "data": {
                "message": "Classification handler not yet registered",
            },
        }

    def handle_quality_inspection(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Default handler for quality inspection commands.

        Args:
            command: Parsed command dict.

        Returns:
            Structured result dict.
        """
        return {
            "success": True,
            "type": "quality",
            "data": {
                "message": "Quality inspection handler not yet registered",
            },
        }

    def handle_tracking(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Default handler for object tracking commands.

        Args:
            command: Parsed command dict.

        Returns:
            Structured result dict.
        """
        return {
            "success": True,
            "type": "tracking",
            "data": {
                "message": "Tracking handler not yet registered",
            },
        }

    def handle_set_threshold(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Handler for set_threshold command.

        Format: set_threshold:<color_name>:<L_MIN>:<L_MAX>:<A_MIN>:<A_MAX>:<B_MIN>:<B_MAX>

        Args:
            command: Parsed command dict.

        Returns:
            Result dict.
        """
        params = command["params"]
        if len(params) < 7:
            return self._error_response(
                self.ERR_INVALID_PARAMS,
                "set_threshold requires 7 params: color_name L_MIN L_MAX A_MIN A_MAX B_MIN B_MAX",
            )
        try:
            color_name = params[0]
            threshold = tuple(int(p) for p in params[1:7])
            from config import set_color_threshold
            set_color_threshold(color_name, threshold)
            return {
                "success": True,
                "type": "config",
                "data": {
                    "color": color_name,
                    "threshold": list(threshold),
                    "message": f"Threshold updated for {color_name}",
                },
            }
        except (ValueError, ImportError) as e:
            return self._error_response(
                self.ERR_INVALID_PARAMS, f"Invalid threshold params: {str(e)}"
            )

    def handle_get_config(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Handler for get_config command.

        Returns the current vision configuration.

        Args:
            command: Parsed command dict.

        Returns:
            Result dict with current config.
        """
        try:
            from config import get_config
            return {
                "success": True,
                "type": "config",
                "data": get_config(),
            }
        except ImportError:
            return {
                "success": True,
                "type": "config",
                "data": {"message": "Config module not available"},
            }

    def handle_unknown(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Handler for unrecognized commands.

        Args:
            command: Parsed command dict.

        Returns:
            Error result dict.
        """
        return self._error_response(
            self.ERR_UNKNOWN_COMMAND,
            f"Unknown command: {command.get('type', 'N/A')}"
        )

    def _error_response(self, code: int, message: str) -> Dict[str, Any]:
        """Build a standardized error response dict.

        Args:
            code: Integer error code.
            message: Human-readable error message.

        Returns:
            Error result dict.
        """
        return {
            "success": False,
            "type": "error",
            "error_code": code,
            "error": message,
            "data": None,
        }

    def blink_led(self, count: int = 1, delay_ms: int = 100) -> None:
        """Blink the status LED to provide visual feedback.

        Args:
            count: Number of blinks.
            delay_ms: Delay between toggles in milliseconds.
        """
        if self._led is None:
            return
        import time
        for _ in range(count):
            self._led.toggle()
            time.sleep_ms(delay_ms)
            self._led.toggle()
            time.sleep_ms(delay_ms)