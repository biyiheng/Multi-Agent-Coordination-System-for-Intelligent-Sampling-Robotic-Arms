"""
OpenMV H7 Plus Main Firmware for Intelligent Sampling Robotic Arm.

Main entry point for the OpenMV camera firmware. Initializes all hardware
peripherals, vision modules, and communication interfaces, then enters the
main event loop to process commands from the Raspberry Pi controller.

Architecture:
    - Sensor: QVGA (320x240) at 30 FPS
    - UART(3): 115200 baud on P4(TX)/P5(RX)
    - AprilTag: TAG36H11 family, 50mm tags
    - Color detection: LAB thresholding for red, blue, green, yellow
    - Classification: Color + shape features
    - Quality inspection: Surface, dimension, and color consistency
"""

import time
import json
from typing import Dict, Any, Optional, Tuple

import sensor

# Import communication modules
from comm.uart_protocol import UARTProtocol
from comm.command_handler import CommandHandler

# Import vision modules
from vision.color_detection import ColorDetector
from vision.apriltag_detection import AprilTagDetector
from vision.object_classification import ObjectClassifier
from vision.quality_inspection import QualityInspector

# Import configuration
from config import (
    CAMERA_RESOLUTION,
    CAMERA_FRAMERATE,
    CAMERA_PIXFORMAT,
    UART_BAUDRATE,
    UART_BUS,
    WATCHDOG_ENABLED,
    WATCHDOG_TIMEOUT_MS,
    LED_IDLE,
    LED_ACTIVE,
    LED_ERROR,
    LED_DETECTED,
    LED_TRACKING,
    STREAMING_MAX_FPS,
    STREAMING_JPEG_QUALITY,
)

# =============================================================================
# Global State
# =============================================================================

# Communication
uart_protocol: Optional[UARTProtocol] = None
command_handler: Optional[CommandHandler] = None

# Vision modules
color_detector: Optional[ColorDetector] = None
apriltag_detector: Optional[AprilTagDetector] = None
object_classifier: Optional[ObjectClassifier] = None
quality_inspector: Optional[QualityInspector] = None

# System state
streaming_mode: bool = False
tracking_target: Optional[str] = None
last_watchdog_reset: int = 0
running: bool = True


# =============================================================================
# Initialization
# =============================================================================

def init_sensor() -> None:
    """Initialize the camera sensor with configured settings."""
    sensor.reset()
    sensor.set_pixformat(getattr(sensor, CAMERA_PIXFORMAT))
    sensor.set_framesize(sensor.QVGA)
    sensor.set_framerate(CAMERA_FRAMERATE)
    sensor.skip_frames(time=2000)
    sensor.set_auto_gain(True)
    sensor.set_auto_whitebal(True)
    sensor.set_auto_exposure(True)


def init_modules() -> None:
    """Initialize all communication and vision modules."""
    global uart_protocol, command_handler
    global color_detector, apriltag_detector, object_classifier, quality_inspector

    uart_protocol = UARTProtocol(bus=UART_BUS, baudrate=UART_BAUDRATE)
    command_handler = CommandHandler(led_id=1)

    color_detector = ColorDetector()
    apriltag_detector = AprilTagDetector()
    object_classifier = ObjectClassifier()
    quality_inspector = QualityInspector()


def register_handlers() -> None:
    """Register all command handlers with the dispatcher."""
    if command_handler is None:
        return

    command_handler.register_handler("detect_color", handle_detect_color)
    command_handler.register_handler("detect_apriltag", handle_detect_apriltag)
    command_handler.register_handler("classify", handle_classify)
    command_handler.register_handler("inspect", handle_inspect)
    command_handler.register_handler("track", handle_track)
    command_handler.register_handler("set_threshold", handle_set_threshold)
    command_handler.register_handler("get_config", handle_get_config)
    command_handler.register_handler("stream_start", handle_stream_start)
    command_handler.register_handler("stream_stop", handle_stream_stop)
    command_handler.register_handler("calibrate_color", handle_calibrate_color)
    command_handler.register_handler("detect_all", handle_detect_all)


# =============================================================================
# Command Handlers
# =============================================================================

def handle_detect_color(cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Handle detect_color command.

    Format: detect_color:<color_name>[:<roi>]

    Returns detection results for the specified color.
    """
    params = cmd.get("params", [])
    color_name = params[0] if params else "red"
    roi = params[1] if len(params) > 1 else None

    if color_detector is None:
        return _error(1, "Color detector not initialized")

    blob = color_detector.find_largest_blob(color_name, roi)
    if blob is None:
        return {
            "success": True,
            "type": "color",
            "data": {
                "color": color_name,
                "found": False,
                "detection": None,
            },
        }

    return {
        "success": True,
        "type": "color",
        "data": {
            "color": color_name,
            "found": True,
            "detection": blob,
        },
    }


def handle_detect_apriltag(cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Handle detect_apriltag command.

    Format: detect_apriltag[:<tag_id>]

    Returns AprilTag detection results.
    """
    params = cmd.get("params", [])

    if apriltag_detector is None:
        return _error(1, "AprilTag detector not initialized")

    if params:
        try:
            tag_id = int(params[0])
            pose = apriltag_detector.get_tag_pose(tag_id)
            return {
                "success": True,
                "type": "apriltag",
                "data": {
                    "found": pose is not None,
                    "tag": pose,
                },
            }
        except ValueError:
            return _error(2, f"Invalid tag ID: {params[0]}")
    else:
        detections = apriltag_detector.detect_tags()
        return {
            "success": True,
            "type": "apriltag",
            "data": {
                "found": len(detections) > 0,
                "count": len(detections),
                "tags": detections,
            },
        }


def handle_classify(cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Handle classify command.

    Format: classify[:<roi>]

    Returns object classification result.
    """
    params = cmd.get("params", [])
    roi = params[0] if params else None

    if object_classifier is None:
        return _error(1, "Classifier not initialized")

    result = object_classifier.classify(roi)
    return {
        "success": True,
        "type": "classification",
        "data": result,
    }


def handle_inspect(cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Handle inspect command.

    Format: inspect[:<sample_id>]

    Returns quality inspection results.
    """
    params = cmd.get("params", [])
    sample_id = params[0] if params else ""

    if quality_inspector is None:
        return _error(1, "Quality inspector not initialized")

    result = quality_inspector.inspect(sample_id)
    return {
        "success": True,
        "type": "quality",
        "data": result,
    }


def handle_track(cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Handle track command.

    Format: track:<color_name>

    Enters tracking mode for the specified color.
    """
    global tracking_target, streaming_mode
    params = cmd.get("params", [])
    tracking_target = params[0] if params else "red"
    streaming_mode = True

    return {
        "success": True,
        "type": "tracking",
        "data": {
            "tracking": True,
            "target": tracking_target,
            "message": f"Tracking {tracking_target} started",
        },
    }


def handle_set_threshold(cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Handle set_threshold command.

    Format: set_threshold:<color_name>:<L_MIN>:<L_MAX>:<A_MIN>:<A_MAX>:<B_MIN>:<B_MAX>
    """
    return command_handler.handle_set_threshold(cmd) if command_handler else _error(1, "Handler not initialized")


def handle_get_config(cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_config command. Returns current configuration."""
    return command_handler.handle_get_config(cmd) if command_handler else _error(1, "Handler not initialized")


def handle_stream_start(cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Handle stream_start command. Begins continuous JPEG streaming."""
    global streaming_mode
    streaming_mode = True
    return {
        "success": True,
        "type": "stream",
        "data": {"streaming": True},
    }


def handle_stream_stop(cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Handle stream_stop command. Stops continuous streaming."""
    global streaming_mode, tracking_target
    streaming_mode = False
    tracking_target = None
    return {
        "success": True,
        "type": "stream",
        "data": {"streaming": False},
    }


def handle_calibrate_color(cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Handle calibrate_color command.

    Format: calibrate_color:<color_name>[:<num_samples>]

    Auto-calibrates color threshold by sampling the frame center.
    """
    params = cmd.get("params", [])
    color_name = params[0] if params else "red"
    num_samples = int(params[1]) if len(params) > 1 else 10

    if color_detector is None:
        return _error(1, "Color detector not initialized")

    try:
        new_threshold = color_detector.calibrate_color(color_name, num_samples)
        return {
            "success": True,
            "type": "config",
            "data": {
                "color": color_name,
                "threshold": list(new_threshold),
                "message": f"Calibrated {color_name} threshold",
            },
        }
    except Exception as e:
        return _error(3, f"Calibration failed: {str(e)}")


def handle_detect_all(cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Handle detect_all command.

    Format: detect_all[:<roi>]

    Detects all configured colors in a single frame.
    """
    params = cmd.get("params", [])
    roi = params[0] if params else None

    if color_detector is None:
        return _error(1, "Color detector not initialized")

    results = color_detector.detect_all_colors(roi)
    return {
        "success": True,
        "type": "color",
        "data": {
            "detections": results,
            "summary": color_detector.get_detection_summary(),
        },
    }


# =============================================================================
# Utility Functions
# =============================================================================

def _error(code: int, message: str) -> Dict[str, Any]:
    """Build an error response dict."""
    return {
        "success": False,
        "type": "error",
        "error_code": code,
        "error": message,
        "data": None,
    }


def _json_serialize(data: Dict[str, Any]) -> str:
    """Serialize a dict to JSON string, handling non-serializable values.

    Args:
        data: Dict to serialize.

    Returns:
        JSON string.
    """
    def default_serializer(obj: Any) -> Any:
        if isinstance(obj, (tuple, list)):
            return list(obj)
        if hasattr(obj, '__dict__'):
            return str(obj)
        return str(obj)

    try:
        return json.dumps(data, default=default_serializer)
    except Exception:
        return json.dumps({"error": "Serialization failed"})


def reset_watchdog() -> None:
    """Reset the watchdog timer."""
    global last_watchdog_reset
    last_watchdog_reset = time.ticks_ms()


def check_watchdog() -> bool:
    """Check if the watchdog has expired.

    Returns:
        True if the watchdog is still alive, False if expired.
    """
    if not WATCHDOG_ENABLED:
        return True
    elapsed = time.ticks_diff(time.ticks_ms(), last_watchdog_reset)
    return elapsed < WATCHDOG_TIMEOUT_MS


def set_led_pattern(pattern: Tuple[int, int, int]) -> None:
    """Set the RGB LED to a specific color pattern.

    Args:
        pattern: (R, G, B) tuple with values 0-255.
    """
    try:
        from pyb import LED
        LED(1).intensity(pattern[0] * 4)  # Red
        LED(2).intensity(pattern[1] * 4)  # Green
        LED(3).intensity(pattern[2] * 4)  # Blue
    except Exception:
        pass


def breathing_led() -> None:
    """Create a breathing effect on the LED for idle state."""
    try:
        t = time.ticks_ms() / 1000.0
        import math
        intensity = int((math.sin(t * 2.0) + 1) / 2 * 20)
        set_led_pattern((0, intensity, 0))
    except Exception:
        pass


# =============================================================================
# Streaming Loop
# =============================================================================

def run_streaming_frame() -> None:
    """Capture and send one frame in streaming mode, with optional tracking."""
    global tracking_target

    if color_detector is None or uart_protocol is None:
        return

    # Capture frame
    color_detector.capture_frame()
    frame = color_detector.current_frame

    # If tracking, find the target and send position data
    if tracking_target:
        blob = color_detector.find_largest_blob(tracking_target)
        if blob:
            data = _json_serialize({
                "tracking": True,
                "target": tracking_target,
                "cx": blob["cx"],
                "cy": blob["cy"],
                "area": blob["area"],
            })
            uart_protocol.send_response("tracking", data)
            set_led_pattern(LED_TRACKING)
            return

    # JPEG streaming
    try:
        jpeg = frame.compress(quality=STREAMING_JPEG_QUALITY)
        if jpeg:
            # Send JPEG as hex-encoded string
            jpeg_hex = jpeg.hex()
            uart_protocol.send_response("stream", jpeg_hex)
    except Exception:
        pass


# =============================================================================
# Main Loop
# =============================================================================

def main() -> None:
    """Main entry point for the OpenMV firmware.

    Initializes all hardware and modules, then enters the main event loop
    that processes commands from the Raspberry Pi and handles streaming mode.
    """
    global running, streaming_mode

    print("OpenMV H7+ Firmware Starting...")
    print(f"Resolution: {CAMERA_RESOLUTION[0]}x{CAMERA_RESOLUTION[1]} @ {CAMERA_FRAMERATE}fps")
    print(f"UART: Bus {UART_BUS} @ {UART_BAUDRATE} baud")

    # Initialize hardware
    init_sensor()
    print("Sensor initialized.")

    # Initialize modules
    init_modules()
    print("Modules initialized.")

    # Register command handlers
    register_handlers()
    print(f"Handlers registered: {len(command_handler.handlers) if command_handler else 0}")

    # Reset watchdog
    reset_watchdog()

    # Signal ready
    if uart_protocol:
        uart_protocol.send_ack("OpenMV ready")
    print("OpenMV ready. Entering main loop.")

    # === Main Event Loop ===
    while running:
        reset_watchdog()

        if streaming_mode:
            # Streaming mode: continuously capture and send frames
            run_streaming_frame()

            # Still check for commands (non-blocking)
            if uart_protocol and uart_protocol.uart.any():
                cmd = uart_protocol.receive_command(timeout_ms=10)
                if cmd is not None:
                    result = command_handler.dispatch(cmd) if command_handler else _error(1, "No handler")
                    response_data = _json_serialize(result)
                    uart_protocol.send_response(result.get("type", "response"), response_data)
                    set_led_pattern(LED_ACTIVE)

            time.sleep_ms(1000 // STREAMING_MAX_FPS)
        else:
            # Idle mode: wait for commands, show breathing LED
            breathing_led()

            if uart_protocol and uart_protocol.uart.any():
                cmd = uart_protocol.receive_command(timeout_ms=UART_BAUDRATE // 100)
                if cmd is not None:
                    set_led_pattern(LED_ACTIVE)

                    result = command_handler.dispatch(cmd) if command_handler else _error(1, "No handler")

                    response_data = _json_serialize(result)
                    response_type = result.get("type", "response")

                    if response_type == "color":
                        set_led_pattern(LED_DETECTED)
                    elif response_type == "error":
                        set_led_pattern(LED_ERROR)

                    uart_protocol.send_response(response_type, response_data)

            time.sleep_ms(50)

        # Check watchdog
        if not check_watchdog():
            print("WATCHDOG EXPIRED! Resetting...")
            set_led_pattern(LED_ERROR)
            import machine
            machine.reset()

    print("Firmware stopped.")


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    main()
else:
    # When imported (e.g., for testing), initialize but don't run
    try:
        init_sensor()
        init_modules()
        register_handlers()
    except Exception:
        pass