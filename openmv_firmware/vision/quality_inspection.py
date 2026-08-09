"""
Visual Quality Inspection for OpenMV H7 Plus.

Performs surface defect detection, dimension measurement, and color
consistency checking using edge detection and blob analysis.

This module inspects objects to determine if they meet quality standards
and returns a structured pass/fail report with detailed findings.
"""

import math
from typing import Dict, List, Optional, Tuple, Any

try:
    import sensor
    import image
except ImportError:
    pass

from config import (
    QUALITY_PASS_SCORE,
    QUALITY_DEFECT_AREA_MIN,
    QUALITY_COLOR_VARIANCE_MAX,
    QUALITY_DIMENSION_TOLERANCE_MM,
    BLOB_MIN_AREA,
    get_roi,
    DEFAULT_ROI,
)


class QualityInspector:
    """Inspects objects for visual quality defects.

    Uses edge detection, blob analysis, and color statistics to detect:
    - Surface defects (scratches, spots, discoloration)
    - Dimensional inaccuracies
    - Color consistency issues

    Attributes:
        pass_score: Minimum score to pass inspection (0-100).
        defect_area_min: Minimum area for a defect to be reported.
        color_variance_max: Maximum allowed color variance.
        dimension_tolerance_mm: Allowed dimensional tolerance in mm.
        reference_dimensions: Known reference dimensions for objects.
        last_result: Most recent inspection result.
    """

    def __init__(
        self,
        pass_score: float = QUALITY_PASS_SCORE,
        defect_area_min: int = QUALITY_DEFECT_AREA_MIN,
        color_variance_max: float = QUALITY_COLOR_VARIANCE_MAX,
        dimension_tolerance_mm: float = QUALITY_DIMENSION_TOLERANCE_MM,
    ) -> None:
        """Initialize the quality inspector.

        Args:
            pass_score: Minimum score to pass (0-100).
            defect_area_min: Minimum defect area in pixels.
            color_variance_max: Maximum color variance allowed.
            dimension_tolerance_mm: Dimensional tolerance in mm.
        """
        self.pass_score: float = pass_score
        self.defect_area_min: int = defect_area_min
        self.color_variance_max: float = color_variance_max
        self.dimension_tolerance_mm: float = dimension_tolerance_mm
        self.reference_dimensions: Dict[str, Tuple[float, float]] = {}
        self.last_result: Optional[Dict[str, Any]] = None
        self._pixels_per_mm: float = 2.0  # Approximate, should be calibrated

    def capture_frame(self) -> Any:
        """Capture a new frame from the sensor.

        Returns:
            The captured frame.
        """
        return sensor.snapshot()

    def inspect(self, sample_id: str = "", roi: Optional[str] = None) -> Dict[str, Any]:
        """Perform a full quality inspection on the current frame.

        Runs all inspection checks: surface defects, dimensions, color consistency.

        Args:
            sample_id: Optional identifier for the sample being inspected.
            roi: Optional ROI region name.

        Returns:
            Inspection result dict:
                {passed, score, defects, dimensions, color_consistency, sample_id}
        """
        frame = self.capture_frame()
        roi_rect = get_roi(roi or DEFAULT_ROI)

        # Run all checks
        surface_result = self.inspect_surface(frame, roi_rect)
        dimension_result = self.check_dimensions(frame, roi_rect)
        color_result = self.check_color_consistency(frame, roi_rect)

        # Compute overall score
        score = self._compute_overall_score(surface_result, dimension_result, color_result)

        passed = score >= self.pass_score

        result = {
            "passed": passed,
            "score": round(score, 1),
            "defects": surface_result["defects"],
            "dimensions": dimension_result,
            "color_consistency": color_result,
            "sample_id": sample_id,
        }
        self.last_result = result
        return result

    def inspect_surface(self, frame: Optional[Any] = None, roi_rect: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
        """Detect surface defects such as scratches and discoloration.

        Uses edge detection to find anomalies in surface texture.

        Args:
            frame: Optional pre-captured frame.
            roi_rect: Optional ROI rectangle.

        Returns:
            Dict with 'defects' list and 'defect_count'.
        """
        if frame is None:
            frame = self.capture_frame()
        if roi_rect is None:
            roi_rect = get_roi(DEFAULT_ROI)

        defects: List[Dict[str, Any]] = []

        # Detect edges (potential scratches)
        edges = frame.find_edges(image.EDGE_CANNY, threshold=(50, 80))

        # Find blobs on the edge image to identify defect clusters
        edge_blobs = edges.find_blobs(
            [(0, 255)],  # Binary image: edges are white
            roi=roi_rect,
            pixels_threshold=self.defect_area_min,
            area_threshold=self.defect_area_min,
            merge=True,
        )

        if edge_blobs:
            for blob in edge_blobs:
                # Longer, thinner blobs are likely scratches
                w = blob.w()
                h = blob.h()
                aspect = max(w, h) / (min(w, h) + 1e-6)
                defect_type = "scratch" if aspect > 3.0 else "spot"

                defects.append({
                    "type": defect_type,
                    "cx": blob.cx(),
                    "cy": blob.cy(),
                    "area": blob.area(),
                    "width": w,
                    "height": h,
                    "severity": "minor" if blob.area() < 200 else "moderate",
                })

        # Check for discoloration (large areas of uniform anomalous color)
        color_defects = self._detect_discoloration(frame, roi_rect)
        defects.extend(color_defects)

        return {
            "defects": defects,
            "defect_count": len(defects),
            "surface_score": self._compute_surface_score(defects),
        }

    def check_dimensions(self, frame: Optional[Any] = None, roi_rect: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
        """Measure object dimensions and compare against reference.

        Args:
            frame: Optional pre-captured frame.
            roi_rect: Optional ROI rectangle.

        Returns:
            Dict with measured dimensions, reference, and deviation.
        """
        if frame is None:
            frame = self.capture_frame()
        if roi_rect is None:
            roi_rect = get_roi(DEFAULT_ROI)

        # Find the largest blob to measure
        blobs = frame.find_blobs(
            [(0, 100, -128, 127, -128, 127)],  # Broad threshold
            roi=roi_rect,
            pixels_threshold=BLOB_MIN_AREA,
            area_threshold=BLOB_MIN_AREA,
            merge=True,
        )

        if not blobs:
            return {
                "measured_width_mm": 0.0,
                "measured_height_mm": 0.0,
                "measured_area_mm2": 0.0,
                "has_reference": False,
                "within_tolerance": False,
                "dimension_score": 0.0,
            }

        largest = max(blobs, key=lambda b: b.area())
        measured_w_px = largest.w()
        measured_h_px = largest.h()

        # Convert pixels to mm
        measured_w_mm = round(measured_w_px / self._pixels_per_mm, 2)
        measured_h_mm = round(measured_h_px / self._pixels_per_mm, 2)
        measured_area_mm2 = round(largest.area() / (self._pixels_per_mm ** 2), 2)

        # Check against reference if available
        has_reference = False
        within_tolerance = True
        dimension_score = 100.0

        # Check if we have a reference for an object of this approximate size
        for ref_name, (ref_w, ref_h) in self.reference_dimensions.items():
            if abs(measured_w_mm - ref_w) < 20 and abs(measured_h_mm - ref_h) < 20:
                has_reference = True
                w_diff = abs(measured_w_mm - ref_w)
                h_diff = abs(measured_h_mm - ref_h)
                if w_diff > self.dimension_tolerance_mm or h_diff > self.dimension_tolerance_mm:
                    within_tolerance = False
                    max_deviation = max(w_diff, h_diff)
                    dimension_score = max(0.0, 100.0 * (1.0 - max_deviation / (self.dimension_tolerance_mm * 3)))
                break

        return {
            "measured_width_mm": measured_w_mm,
            "measured_height_mm": measured_h_mm,
            "measured_area_mm2": measured_area_mm2,
            "pixels_per_mm": self._pixels_per_mm,
            "has_reference": has_reference,
            "within_tolerance": within_tolerance,
            "dimension_score": round(dimension_score, 1),
        }

    def check_color_consistency(self, frame: Optional[Any] = None, roi_rect: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
        """Verify color uniformity across the object surface.

        High variance in color indicates inconsistency or defects.

        Args:
            frame: Optional pre-captured frame.
            roi_rect: Optional ROI rectangle.

        Returns:
            Dict with color statistics and consistency score.
        """
        if frame is None:
            frame = self.capture_frame()
        if roi_rect is None:
            roi_rect = get_roi(DEFAULT_ROI)

        stats = frame.get_statistics(roi=roi_rect)

        # Compute variance in LAB channels
        l_stdev = stats.l_stdev()
        a_stdev = stats.a_stdev()
        b_stdev = stats.b_stdev()

        total_variance = l_stdev + a_stdev + b_stdev

        # Score: lower variance = higher score
        if total_variance <= self.color_variance_max:
            consistency_score = 100.0
        else:
            consistency_score = max(0.0, 100.0 * (self.color_variance_max / total_variance))

        is_consistent = total_variance <= self.color_variance_max

        return {
            "l_stdev": round(l_stdev, 2),
            "a_stdev": round(a_stdev, 2),
            "b_stdev": round(b_stdev, 2),
            "total_variance": round(total_variance, 2),
            "max_allowed_variance": self.color_variance_max,
            "is_consistent": is_consistent,
            "consistency_score": round(consistency_score, 1),
        }

    def set_reference_dimensions(self, name: str, width_mm: float, height_mm: float) -> None:
        """Register reference dimensions for a known object.

        Args:
            name: Object name/identifier.
            width_mm: Expected width in mm.
            height_mm: Expected height in mm.
        """
        self.reference_dimensions[name] = (width_mm, height_mm)

    def set_pixels_per_mm(self, ppm: float) -> None:
        """Set the pixel-to-mm calibration factor.

        Args:
            ppm: Pixels per millimeter.
        """
        if ppm <= 0:
            raise ValueError("Pixels per mm must be positive")
        self._pixels_per_mm = ppm

    def _detect_discoloration(self, frame: Any, roi_rect: Tuple[int, int, int, int]) -> List[Dict[str, Any]]:
        """Detect discoloration defects by analyzing color statistics in sub-regions.

        Args:
            frame: The image frame.
            roi_rect: ROI rectangle.

        Returns:
            List of discoloration defect dicts.
        """
        defects: List[Dict[str, Any]] = []
        x, y, w, h = roi_rect

        # Divide ROI into a grid and check each cell
        grid_cols = 4
        grid_rows = 3
        cell_w = w // grid_cols
        cell_h = h // grid_rows

        color_stats = []
        for row in range(grid_rows):
            for col in range(grid_cols):
                cell_x = x + col * cell_w
                cell_y = y + row * cell_h
                cell_roi = (cell_x, cell_y, cell_w, cell_h)
                cell_stats = frame.get_statistics(roi=cell_roi)
                color_stats.append({
                    "l_mean": cell_stats.l_mean(),
                    "a_mean": cell_stats.a_mean(),
                    "b_mean": cell_stats.b_mean(),
                    "cx": cell_x + cell_w // 2,
                    "cy": cell_y + cell_h // 2,
                })

        if not color_stats:
            return defects

        # Compute mean across all cells
        mean_l = sum(s["l_mean"] for s in color_stats) / len(color_stats)
        mean_a = sum(s["a_mean"] for s in color_stats) / len(color_stats)
        mean_b = sum(s["b_mean"] for s in color_stats) / len(color_stats)

        # Flag cells with significant deviation
        for stat in color_stats:
            dev = abs(stat["l_mean"] - mean_l) + abs(stat["a_mean"] - mean_a) + abs(stat["b_mean"] - mean_b)
            if dev > 30:  # Significant deviation threshold
                defects.append({
                    "type": "discoloration",
                    "cx": stat["cx"],
                    "cy": stat["cy"],
                    "area": cell_w * cell_h,
                    "width": cell_w,
                    "height": cell_h,
                    "severity": "minor" if dev < 60 else "moderate",
                    "deviation": round(dev, 1),
                })

        return defects

    def _compute_surface_score(self, defects: List[Dict[str, Any]]) -> float:
        """Compute a surface quality score based on detected defects.

        Args:
            defects: List of defect dicts.

        Returns:
            Score from 0 to 100.
        """
        if not defects:
            return 100.0

        # Penalize based on defect count and severity
        total_penalty = 0.0
        for defect in defects:
            area = defect.get("area", 0)
            if defect.get("severity") == "moderate":
                total_penalty += min(30.0, area / 50.0)
            else:
                total_penalty += min(15.0, area / 100.0)

        return max(0.0, 100.0 - total_penalty)

    def _compute_overall_score(
        self,
        surface: Dict[str, Any],
        dimensions: Dict[str, Any],
        color: Dict[str, Any],
    ) -> float:
        """Compute the overall quality score from sub-scores.

        Weights: surface 40%, dimensions 30%, color 30%

        Args:
            surface: Surface inspection result.
            dimensions: Dimension check result.
            color: Color consistency result.

        Returns:
            Overall score from 0 to 100.
        """
        surface_score = surface.get("surface_score", 100.0)
        dimension_score = dimensions.get("dimension_score", 100.0)
        color_score = color.get("consistency_score", 100.0)

        overall = 0.4 * surface_score + 0.3 * dimension_score + 0.3 * color_score
        return round(overall, 1)

    def is_passed(self) -> bool:
        """Check if the last inspection passed.

        Returns:
            True if the last result passed, False otherwise.
        """
        if self.last_result is None:
            return False
        return self.last_result.get("passed", False)

    def get_defect_summary(self) -> Dict[str, int]:
        """Get a summary of defect types from the last inspection.

        Returns:
            Dict mapping defect type to count.
        """
        if self.last_result is None:
            return {}
        summary: Dict[str, int] = {}
        for defect in self.last_result.get("defects", []):
            dtype = defect.get("type", "unknown")
            summary[dtype] = summary.get(dtype, 0) + 1
        return summary