"""
Object Classification for OpenMV H7 Plus.

Classifies objects in the field of view using simple color + shape
feature extraction. Due to memory constraints on the OpenMV H7,
this module uses traditional computer vision features rather than
TFLite models.

Categories: block, cylinder, sphere, irregular
"""

import math
from typing import Dict, List, Optional, Tuple, Any

try:
    import sensor
    import image
except ImportError:
    pass

from config import (
    CLASSIFICATION_CATEGORIES,
    CLASSIFICATION_CONFIDENCE_THRESHOLD,
    SHAPE_ASPECT_RATIOS,
    BLOB_MIN_AREA,
    BLOB_MAX_BLOBS,
    get_roi,
    DEFAULT_ROI,
)


class ObjectClassifier:
    """Classifies objects using color and shape features.

    Uses blob analysis to extract features (area, perimeter, aspect ratio,
    circularity, convexity) and maps them to predefined categories.

    Attributes:
        categories: List of supported classification categories.
        confidence_threshold: Minimum confidence for valid classification.
        last_result: Most recent classification result.
    """

    def __init__(self) -> None:
        """Initialize the object classifier."""
        self.categories: List[str] = CLASSIFICATION_CATEGORIES
        self.confidence_threshold: float = CLASSIFICATION_CONFIDENCE_THRESHOLD
        self.last_result: Optional[Dict[str, Any]] = None

    def capture_frame(self) -> Any:
        """Capture a current frame from the sensor.

        Returns:
            The captured frame.
        """
        return sensor.snapshot()

    def classify(self, roi: Optional[str] = None) -> Dict[str, Any]:
        """Classify the dominant object in the current frame.

        Finds the largest blob in the frame, extracts shape features,
        and classifies it into one of the predefined categories.

        Args:
            roi: Optional ROI region name.

        Returns:
            Classification result dict:
                {category, confidence, color, bbox, features, all_scores}
        """
        frame = self.capture_frame()
        roi_rect = get_roi(roi or DEFAULT_ROI)

        # Find the largest blob regardless of color
        blobs = frame.find_blobs(
            [self._get_broad_threshold()],
            roi=roi_rect,
            pixels_threshold=BLOB_MIN_AREA,
            area_threshold=BLOB_MIN_AREA,
            merge=True,
            margin=10,
        )

        if not blobs:
            result = {
                "category": "none",
                "confidence": 0.0,
                "color": "unknown",
                "bbox": None,
                "features": {},
                "all_scores": {},
            }
            self.last_result = result
            return result

        # Use the largest blob
        largest = max(blobs, key=lambda b: b.area())

        # Extract features
        features = self._extract_features(largest, frame)

        # Classify based on features
        scores = self._compute_scores(features)
        best_category = max(scores, key=scores.get)
        best_confidence = scores[best_category]

        # Determine dominant color
        color = self._determine_color(frame, largest)

        bbox = (largest.x(), largest.y(), largest.w(), largest.h())

        result = {
            "category": best_category if best_confidence >= self.confidence_threshold else "irregular",
            "confidence": round(best_confidence, 3),
            "color": color,
            "bbox": bbox,
            "features": features,
            "all_scores": {k: round(v, 3) for k, v in scores.items()},
        }
        self.last_result = result
        return result

    def classify_all(self, roi: Optional[str] = None) -> List[Dict[str, Any]]:
        """Classify all visible objects in the frame.

        Args:
            roi: Optional ROI region name.

        Returns:
            List of classification result dicts.
        """
        frame = self.capture_frame()
        roi_rect = get_roi(roi or DEFAULT_ROI)

        blobs = frame.find_blobs(
            [self._get_broad_threshold()],
            roi=roi_rect,
            pixels_threshold=BLOB_MIN_AREA,
            area_threshold=BLOB_MIN_AREA,
            merge=True,
            margin=10,
        )

        if not blobs:
            return []

        results = []
        for blob in blobs[:BLOB_MAX_BLOBS]:
            features = self._extract_features(blob, frame)
            scores = self._compute_scores(features)
            best_category = max(scores, key=scores.get)
            best_confidence = scores[best_category]
            color = self._determine_color(frame, blob)

            results.append({
                "category": best_category if best_confidence >= self.confidence_threshold else "irregular",
                "confidence": round(best_confidence, 3),
                "color": color,
                "bbox": (blob.x(), blob.y(), blob.w(), blob.h()),
                "features": features,
                "all_scores": {k: round(v, 3) for k, v in scores.items()},
            })

        return results

    def _extract_features(self, blob: Any, frame: Any) -> Dict[str, float]:
        """Extract shape features from a blob.

        Computes: area, perimeter, aspect_ratio, circularity, convexity,
        solidity, extent, rectangularity.

        Args:
            blob: OpenMV blob object.
            frame: Current image frame.

        Returns:
            Dict of feature name to float value.
        """
        area = float(blob.area())
        w = float(blob.w())
        h = float(blob.h())
        perimeter = float(blob.perimeter())

        # Aspect ratio (width / height, normalized so >= 1)
        aspect_ratio = max(w, h) / (min(w, h) + 1e-6)

        # Circularity: 4*pi*area / perimeter^2 (1.0 = perfect circle)
        circularity = (4.0 * math.pi * area) / (perimeter * perimeter + 1e-6)

        # Roundness (approximation from built-in)
        roundness = float(blob.roundness())

        # Solidity: area / convex_hull_area (approximate)
        solidity = float(blob.solidity()) if hasattr(blob, 'solidity') else circularity

        # Extent: area / bounding_box_area
        extent = area / (w * h + 1e-6)

        # Rectangularity: area / (w * h) — similar to extent
        rectangularity = area / (w * h + 1e-6)

        # Compactness: perimeter^2 / area
        compactness = (perimeter * perimeter) / (area + 1e-6)

        # Elongation
        elongation = 1.0 - (min(w, h) / (max(w, h) + 1e-6))

        return {
            "area": round(area, 1),
            "perimeter": round(perimeter, 1),
            "aspect_ratio": round(aspect_ratio, 3),
            "circularity": round(circularity, 3),
            "roundness": round(roundness, 3),
            "solidity": round(solidity, 3),
            "extent": round(extent, 3),
            "rectangularity": round(rectangularity, 3),
            "compactness": round(compactness, 1),
            "elongation": round(elongation, 3),
        }

    def _compute_scores(self, features: Dict[str, float]) -> Dict[str, float]:
        """Compute classification scores for each category based on features.

        Uses simple heuristic rules based on shape features.

        Args:
            features: Dict of extracted shape features.

        Returns:
            Dict of category -> score (0.0 to 1.0).
        """
        ar = features["aspect_ratio"]
        circ = features["circularity"]
        roundness = features["roundness"]
        elongation = features["elongation"]
        extent = features["extent"]

        scores: Dict[str, float] = {}

        # Sphere: high circularity, aspect ratio near 1, high roundness
        sphere_score = circ * roundness * (1.0 - abs(ar - 1.0) / 2.0)
        sphere_score = min(1.0, max(0.0, sphere_score))

        # Block: moderate aspect ratio, low circularity, high rectangularity
        block_score = extent * (1.0 - circ) * max(0.0, 1.0 - abs(ar - 1.0) / 1.5)
        block_score = min(1.0, max(0.0, block_score))

        # Cylinder: high elongation, low circularity, aspect ratio far from 1
        cylinder_score = elongation * (1.0 - circ) * min(ar / 3.0, 1.0)
        cylinder_score = min(1.0, max(0.0, cylinder_score))

        # Irregular: everything else gets a baseline
        irregular_score = 0.3  # Default low score

        # If no category clearly matches, irregular wins
        if sphere_score < 0.3 and block_score < 0.3 and cylinder_score < 0.3:
            irregular_score = 0.6

        scores["sphere"] = sphere_score
        scores["block"] = block_score
        scores["cylinder"] = cylinder_score
        scores["irregular"] = irregular_score

        return scores

    def _determine_color(self, frame: Any, blob: Any) -> str:
        """Determine the dominant color of a blob region.

        Samples the center of the blob and maps LAB values to color names.

        Args:
            frame: Current image frame.
            blob: OpenMV blob object.

        Returns:
            Color name string (e.g., 'red', 'blue', 'unknown').
        """
        try:
            # Sample a small region at the blob center
            cx = blob.cx()
            cy = blob.cy()
            roi = (max(0, cx - 5), max(0, cy - 5), 10, 10)
            stats = frame.get_statistics(roi=roi)

            a_mean = stats.a_mean()
            b_mean = stats.b_mean()

            # Simple LAB-to-color mapping
            if a_mean > 20 and b_mean > -20:
                return "red"
            elif b_mean < -20 and a_mean < 20:
                return "blue"
            elif a_mean < -20 and b_mean > 10:
                return "green"
            elif b_mean > 30:
                return "yellow"
            else:
                return "unknown"
        except Exception:
            return "unknown"

    def _get_broad_threshold(self) -> Tuple[int, int, int, int, int, int]:
        """Get a broad threshold that captures most colored objects.

        Returns:
            LAB threshold tuple.
        """
        # Broad threshold to capture most non-background objects
        return (0, 100, -128, 127, -128, 127)

    def get_last_category(self) -> Optional[str]:
        """Get the category from the last classification result.

        Returns:
            Category string or None.
        """
        if self.last_result is None:
            return None
        return self.last_result.get("category")