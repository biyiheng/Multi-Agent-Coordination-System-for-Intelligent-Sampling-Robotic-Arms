"""
Color-Based Object Detection for OpenMV H7 Plus.

Performs threshold-based blob detection in the LAB color space to locate
and identify objects by their color. Supports single-color, multi-color,
and color calibration modes.

The module uses OpenMV's built-in `find_blobs()` function with configurable
thresholds from `config.py`.
"""

import time
from typing import Dict, List, Optional, Tuple, Any, Union

try:
    import sensor
    import image
except ImportError:
    # Mock for testing/development on non-OpenMV platforms
    pass

from config import (
    COLOR_THRESHOLDS,
    COLOR_NAMES,
    BLOB_MIN_AREA,
    BLOB_MAX_AREA,
    BLOB_MAX_BLOBS,
    BLOB_MERGE,
    BLOB_MARGIN,
    DEFAULT_ROI,
    get_roi,
    get_color_threshold,
)


class ColorDetector:
    """Detects colored objects using LAB color-space thresholding.

    Provides methods for single-color detection, multi-color scanning,
    largest blob identification, and color calibration.

    Attributes:
        current_frame: The most recently captured sensor frame.
        blob_settings: Dict of blob-finding parameters.
        calibration_mode: Whether auto-calibration is active.
    """

    def __init__(self) -> None:
        """Initialize the color detector with default settings."""
        self.current_frame: Any = None
        self.blob_settings: Dict[str, Any] = {
            "pixels_threshold": BLOB_MIN_AREA,
            "area_threshold": BLOB_MIN_AREA,
            "merge": BLOB_MERGE,
            "margin": BLOB_MARGIN,
        }
        self.calibration_mode: bool = False
        self._last_detections: Dict[str, List[Dict[str, Any]]] = {}

    def capture_frame(self) -> None:
        """Capture a new frame from the sensor for processing."""
        self.current_frame = sensor.snapshot()

    def detect_color(
        self,
        color_name: str,
        roi: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Detect all blobs of the specified color in the current frame.

        Args:
            color_name: Name of the color to detect (e.g., 'red', 'blue').
            roi: Optional ROI region name. Defaults to 'full'.

        Returns:
            List of detection dicts sorted by area (descending).
            Each dict: {color, cx, cy, width, height, area, density, confidence}
        """
        threshold = get_color_threshold(color_name)
        if threshold is None:
            return []

        roi_rect = get_roi(roi or DEFAULT_ROI)

        self.capture_frame()

        blobs = self.current_frame.find_blobs(
            [threshold],
            roi=roi_rect,
            pixels_threshold=self.blob_settings["pixels_threshold"],
            area_threshold=self.blob_settings["area_threshold"],
            merge=self.blob_settings["merge"],
            margin=self.blob_settings["margin"],
        )

        if not blobs:
            return []

        detections = []
        for blob in blobs[:BLOB_MAX_BLOBS]:
            confidence = min(1.0, blob.density() / 255.0)
            detections.append({
                "color": color_name,
                "cx": blob.cx(),
                "cy": blob.cy(),
                "width": blob.w(),
                "height": blob.h(),
                "area": blob.area(),
                "density": blob.density(),
                "confidence": round(confidence, 3),
                "rotation": blob.rotation_deg(),
                "corners": list(blob.corners()),
            })

        # Sort by area descending
        detections.sort(key=lambda d: d["area"], reverse=True)
        self._last_detections[color_name] = detections
        return detections

    def find_largest_blob(
        self,
        color_name: str,
        roi: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Find the largest blob of the specified color.

        Args:
            color_name: Color name to search for.
            roi: Optional ROI region.

        Returns:
            Detection dict for the largest blob, or None if none found.
        """
        detections = self.detect_color(color_name, roi)
        return detections[0] if detections else None

    def find_all_blobs(
        self,
        color_name: str,
        roi: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return all blobs of the specified color, sorted by area descending.

        Args:
            color_name: Color name to search for.
            roi: Optional ROI region.

        Returns:
            List of detection dicts.
        """
        return self.detect_color(color_name, roi)

    def get_color_position(
        self,
        color_name: str,
        roi: Optional[str] = None,
    ) -> Optional[Tuple[int, int, int]]:
        """Get the (cx, cy, area) of the largest blob of the specified color.

        Args:
            color_name: Color name to search for.
            roi: Optional ROI region.

        Returns:
            (cx, cy, area) tuple or None if no blob found.
        """
        blob = self.find_largest_blob(color_name, roi)
        if blob is None:
            return None
        return (blob["cx"], blob["cy"], blob["area"])

    def detect_all_colors(
        self,
        roi: Optional[str] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Detect objects of all configured colors in a single frame.

        Captures one frame and scans for all color thresholds.

        Args:
            roi: Optional ROI region.

        Returns:
            Dict mapping color_name -> list of detection dicts.
        """
        self.capture_frame()
        results: Dict[str, List[Dict[str, Any]]] = {}
        roi_rect = get_roi(roi or DEFAULT_ROI)

        for color_name in COLOR_NAMES:
            threshold = get_color_threshold(color_name)
            if threshold is None:
                continue
            blobs = self.current_frame.find_blobs(
                [threshold],
                roi=roi_rect,
                pixels_threshold=self.blob_settings["pixels_threshold"],
                area_threshold=self.blob_settings["area_threshold"],
                merge=self.blob_settings["merge"],
                margin=self.blob_settings["margin"],
            )
            dets = []
            for blob in (blobs or [])[:BLOB_MAX_BLOBS]:
                dets.append({
                    "color": color_name,
                    "cx": blob.cx(),
                    "cy": blob.cy(),
                    "width": blob.w(),
                    "height": blob.h(),
                    "area": blob.area(),
                    "density": blob.density(),
                    "confidence": round(min(1.0, blob.density() / 255.0), 3),
                })
            dets.sort(key=lambda d: d["area"], reverse=True)
            results[color_name] = dets

        self._last_detections = results
        return results

    def calibrate_color(
        self,
        color_name: str,
        num_samples: int = 10,
        roi: Optional[str] = None,
    ) -> Tuple[int, int, int, int, int, int]:
        """Auto-calibrate the threshold for a color by sampling the frame center.

        Captures several frames, averages the LAB values at the center region,
        and generates a new threshold with appropriate margins.

        Args:
            color_name: The color name to calibrate.
            num_samples: Number of frames to sample.
            roi: ROI to sample from (defaults to center).

        Returns:
            New (L_MIN, L_MAX, A_MIN, A_MAX, B_MIN, B_MAX) threshold tuple.
        """
        roi_rect = get_roi(roi or "center")
        samples_l: List[int] = []
        samples_a: List[int] = []
        samples_b: List[int] = []

        for _ in range(num_samples):
            self.capture_frame()
            stats = self.current_frame.get_statistics(roi=roi_rect)
            samples_l.append(stats.l_mean())
            samples_a.append(stats.a_mean())
            samples_b.append(stats.b_mean())
            time.sleep_ms(50)

        l_mean = sum(samples_l) // len(samples_l)
        a_mean = sum(samples_a) // len(samples_a)
        b_mean = sum(samples_b) // len(samples_b)

        # Apply margins around the mean
        margin_l = 20
        margin_a = 30
        margin_b = 30

        new_threshold = (
            max(0, l_mean - margin_l),
            min(100, l_mean + margin_l),
            max(-128, a_mean - margin_a),
            min(127, a_mean + margin_a),
            max(-128, b_mean - margin_b),
            min(127, b_mean + margin_b),
        )

        from config import set_color_threshold
        set_color_threshold(color_name, new_threshold)

        return new_threshold

    def get_detection_summary(self) -> Dict[str, Any]:
        """Get a summary of the most recent detections.

        Returns:
            Dict with summary of last detection results.
        """
        summary: Dict[str, Any] = {
            "total_objects": 0,
            "colors_detected": [],
            "largest": None,
        }
        largest_area = 0
        for color_name, dets in self._last_detections.items():
            if dets:
                summary["total_objects"] += len(dets)
                summary["colors_detected"].append(color_name)
                for d in dets:
                    if d["area"] > largest_area:
                        largest_area = d["area"]
                        summary["largest"] = d
        return summary

    def is_visible(self, color_name: str, min_area: int = BLOB_MIN_AREA) -> bool:
        """Quick check if a colored object is visible.

        Args:
            color_name: Color to check.
            min_area: Minimum blob area to consider visible.

        Returns:
            True if a blob of the color is detected.
        """
        blob = self.find_largest_blob(color_name)
        return blob is not None and blob["area"] >= min_area

    def get_blob_bbox(self, color_name: str) -> Optional[Tuple[int, int, int, int]]:
        """Get the bounding box of the largest blob of a color.

        Args:
            color_name: Color to search for.

        Returns:
            (x, y, w, h) bbox tuple or None.
        """
        blob = self.find_largest_blob(color_name)
        if blob is None:
            return None
        x = blob["cx"] - blob["width"] // 2
        y = blob["cy"] - blob["height"] // 2
        return (x, y, blob["width"], blob["height"])