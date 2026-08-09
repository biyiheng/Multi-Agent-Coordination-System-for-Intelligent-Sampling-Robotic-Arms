"""
Vision Parameters Configuration for OpenMV H7 Plus.

This module defines all vision-related constants, thresholds, and camera
settings used across the firmware modules.
"""

from typing import Dict, Tuple, List, Optional, Any

# =============================================================================
# Camera Settings
# =============================================================================

CAMERA_RESOLUTION: Tuple[int, int] = (320, 240)  # QVGA
CAMERA_FRAMERATE: int = 30
CAMERA_PIXFORMAT: str = "RGB565"
CAMERA_BRIGHTNESS: int = 0
CAMERA_CONTRAST: int = 0
CAMERA_SATURATION: int = 0
CAMERA_GAIN_CEILING: int = 8

# =============================================================================
# UART Settings
# =============================================================================

UART_BAUDRATE: int = 115200
UART_BUS: int = 3  # UART(3) on P4(TX)/P5(RX)
UART_TIMEOUT: int = 1000  # ms
UART_BUF_SIZE: int = 256

# =============================================================================
# AprilTag Settings
# =============================================================================

APRILTAG_FAMILY: str = "TAG36H11"
APRILTAG_TAG_SIZE: float = 50.0  # mm (50mm × 50mm)
APRILTAG_MAX_TAGS: int = 10
APRILTAG_FX: Optional[float] = None  # Auto-calculated from calibration
APRILTAG_FY: Optional[float] = None
APRILTAG_CX: Optional[float] = None  # Center of image
APRILTAG_CY: Optional[float] = None

# =============================================================================
# Color Thresholds (LAB color space)
# Format: (L_MIN, L_MAX, A_MIN, A_MAX, B_MIN, B_MAX)
# =============================================================================

COLOR_THRESHOLDS: Dict[str, Tuple[int, int, int, int, int, int]] = {
    "red": (20, 80, 40, 80, 20, 80),       # Red objects
    "red2": (0, 40, 30, 70, -80, -10),     # Red (alternative, for wrap-around)
    "blue": (15, 70, -40, 10, -80, -20),   # Blue objects
    "green": (20, 75, -60, -10, 10, 60),   # Green objects
    "yellow": (50, 95, -20, 20, 40, 80),   # Yellow objects
    "white": (70, 100, -20, 20, -20, 20),  # White objects
    "black": (0, 30, -20, 20, -20, 20),    # Black objects
}

# Friendly color names for results
COLOR_NAMES: List[str] = ["red", "blue", "green", "yellow"]

# =============================================================================
# ROI Regions (Format: (x, y, w, h))
# =============================================================================

ROI_FULL_FRAME: Tuple[int, int, int, int] = (0, 0, 320, 240)
ROI_CENTER: Tuple[int, int, int, int] = (80, 60, 160, 120)
ROI_TOP_HALF: Tuple[int, int, int, int] = (0, 0, 320, 120)
ROI_BOTTOM_HALF: Tuple[int, int, int, int] = (0, 120, 320, 120)

ROI_REGIONS: Dict[str, Tuple[int, int, int, int]] = {
    "full": ROI_FULL_FRAME,
    "center": ROI_CENTER,
    "top": ROI_TOP_HALF,
    "bottom": ROI_BOTTOM_HALF,
}

# Default ROI for detection
DEFAULT_ROI: str = "full"

# =============================================================================
# Blob Detection Settings
# =============================================================================

BLOB_MIN_AREA: int = 100       # Minimum blob area in pixels
BLOB_MAX_AREA: int = 50000     # Maximum blob area in pixels
BLOB_MIN_DENSITY: int = 20     # Minimum density (0-255)
BLOB_MARGIN: int = 5           # Merge margin
BLOB_MAX_BLOBS: int = 20       # Maximum blobs to find
BLOB_MERGE: bool = True        # Merge overlapping blobs
BLOB_PIXELS_THRESHOLD: int = 50  # Pixel count threshold
BLOB_AREA_THRESHOLD: int = 50  # Area threshold

# =============================================================================
# Quality Inspection Settings
# =============================================================================

QUALITY_PASS_SCORE: float = 70.0       # Minimum score to pass
QUALITY_DEFECT_AREA_MIN: int = 20      # Minimum defect area (pixels)
QUALITY_COLOR_VARIANCE_MAX: float = 30.0  # Maximum color variance allowed
QUALITY_DIMENSION_TOLERANCE_MM: float = 2.0  # mm tolerance

# =============================================================================
# Classification Settings
# =============================================================================

CLASSIFICATION_CATEGORIES: List[str] = [
    "block",
    "cylinder",
    "sphere",
    "irregular",
]

CLASSIFICATION_CONFIDENCE_THRESHOLD: float = 0.5

# Aspect ratio ranges for shape classification
SHAPE_ASPECT_RATIOS: Dict[str, Tuple[float, float]] = {
    "block": (0.5, 2.0),       # Rectangular, aspect ratio near 1
    "cylinder": (0.3, 3.0),    # Elongated
    "sphere": (0.8, 1.2),      # Nearly circular
    "irregular": (0.0, 10.0),  # Anything goes
}

# =============================================================================
# Tracking Settings
# =============================================================================

TRACKING_MAX_OBJECTS: int = 5
TRACKING_HISTORY_LENGTH: int = 10
TRACKING_POSITION_THRESHOLD: int = 50  # Max pixel distance for re-identification
TRACKING_TIMEOUT_MS: int = 2000        # Object lost timeout

# =============================================================================
# LED Patterns
# =============================================================================

LED_IDLE: Tuple[int, int, int] = (0, 20, 0)     # Dim green breathing
LED_ACTIVE: Tuple[int, int, int] = (0, 50, 0)    # Bright green
LED_ERROR: Tuple[int, int, int] = (50, 0, 0)     # Red
LED_DETECTED: Tuple[int, int, int] = (0, 0, 50)  # Blue
LED_TRACKING: Tuple[int, int, int] = (50, 50, 0) # Yellow

# =============================================================================
# Watchdog Settings
# =============================================================================

WATCHDOG_TIMEOUT_MS: int = 5000
WATCHDOG_ENABLED: bool = True

# =============================================================================
# Continuous Streaming Mode
# =============================================================================

STREAMING_MAX_FPS: int = 15
STREAMING_JPEG_QUALITY: int = 75

# =============================================================================
# Helper Functions
# =============================================================================

def get_color_threshold(color_name: str) -> Optional[Tuple[int, int, int, int, int, int]]:
    """Get the LAB threshold tuple for a given color name.

    Args:
        color_name: Name of the color (e.g., 'red', 'blue').

    Returns:
        Threshold tuple or None if color not found.
    """
    return COLOR_THRESHOLDS.get(color_name.lower())


def set_color_threshold(color_name: str, threshold: Tuple[int, int, int, int, int, int]) -> None:
    """Update the LAB threshold for a given color name.

    Args:
        color_name: Name of the color to update.
        threshold: New (L_MIN, L_MAX, A_MIN, A_MAX, B_MIN, B_MAX) tuple.
    """
    if len(threshold) != 6:
        raise ValueError("Threshold must be a 6-tuple (L_MIN, L_MAX, A_MIN, A_MAX, B_MIN, B_MAX)")
    COLOR_THRESHOLDS[color_name.lower()] = threshold


def get_roi(region_name: str) -> Tuple[int, int, int, int]:
    """Get the ROI rectangle for a named region.

    Args:
        region_name: Name of the ROI region.

    Returns:
        (x, y, w, h) tuple.
    """
    return ROI_REGIONS.get(region_name, ROI_FULL_FRAME)


def get_config() -> Dict[str, Any]:
    """Return the current configuration as a dictionary.

    Returns:
        Dict with all current config values.
    """
    return {
        "camera": {
            "resolution": CAMERA_RESOLUTION,
            "framerate": CAMERA_FRAMERATE,
            "pixformat": CAMERA_PIXFORMAT,
        },
        "uart": {
            "baudrate": UART_BAUDRATE,
            "bus": UART_BUS,
        },
        "apriltag": {
            "family": APRILTAG_FAMILY,
            "tag_size_mm": APRILTAG_TAG_SIZE,
        },
        "color_thresholds": dict(COLOR_THRESHOLDS),
        "blob": {
            "min_area": BLOB_MIN_AREA,
            "max_area": BLOB_MAX_AREA,
        },
        "quality": {
            "pass_score": QUALITY_PASS_SCORE,
        },
    }