"""
Image Processing Utilities for Raspberry Pi Vision System.

Provides image processing functions for the sampled data coming from the
OpenMV camera, including JPEG decoding, edge detection, contour analysis,
centroid computation, monocular depth estimation, and coordinate transforms.

Designed for use on Raspberry Pi with OpenCV (cv2) as the backend.
All operations work on numpy arrays.
"""

import math
from typing import Dict, List, Optional, Tuple, Any, Union

import numpy as np

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    # Provide fallback stubs for environments without OpenCV
    class _CV2Mock:
        """Mock cv2 for environments without OpenCV."""
        COLOR_BGR2GRAY = 6
        COLOR_BGR2RGB = 4
        COLOR_RGB2BGR = 2
        CHAIN_APPROX_SIMPLE = 2
        RETR_EXTERNAL = 0
        RETR_TREE = 3
        FONT_HERSHEY_SIMPLEX = 0
        LINE_AA = 16

        @staticmethod
        def imdecode(buf: Any, flags: Any) -> Optional[np.ndarray]:
            return None

        @staticmethod
        def Canny(image: np.ndarray, t1: float, t2: float) -> np.ndarray:
            return np.zeros_like(image)

        @staticmethod
        def findContours(image: np.ndarray, mode: Any, method: Any) -> Tuple:
            return ([], None)

        @staticmethod
        def rectangle(img: np.ndarray, pt1: Tuple, pt2: Tuple, color: Tuple, thickness: int) -> np.ndarray:
            return img

        @staticmethod
        def putText(img: np.ndarray, text: str, org: Tuple, font: Any, scale: float, color: Tuple, thickness: int) -> np.ndarray:
            return img

        @staticmethod
        def circle(img: np.ndarray, center: Tuple, radius: int, color: Tuple, thickness: int) -> np.ndarray:
            return img

        @staticmethod
        def line(img: np.ndarray, pt1: Tuple, pt2: Tuple, color: Tuple, thickness: int) -> np.ndarray:
            return img

    cv2 = _CV2Mock()


class ImageProcessor:
    """Image processing utilities for the vision pipeline.

    Handles JPEG decoding from OpenMV, edge detection, contour analysis,
    depth estimation, coordinate transformations, and visualization.

    Attributes:
        focal_length: Camera focal length in pixels for depth estimation.
        known_object_sizes: Dict mapping object names to known sizes in mm.
    """

    def __init__(self, focal_length: float = 500.0) -> None:
        """Initialize the image processor.

        Args:
            focal_length: Camera focal length in pixels (default 500).
        """
        self.focal_length: float = focal_length
        self.known_object_sizes: Dict[str, float] = {
            "apriltag": 50.0,  # mm
            "block_small": 30.0,
            "block_large": 60.0,
            "cylinder": 40.0,
        }
        self._transform_chain: Dict[str, np.ndarray] = {}

    def decode_jpeg(self, data: Union[bytes, bytearray]) -> Optional[np.ndarray]:
        """Decode a JPEG byte buffer into a numpy image array.

        Args:
            data: Raw JPEG bytes (from OpenMV or file).

        Returns:
            BGR image as numpy array (H, W, 3), or None if decoding fails.
        """
        if not CV2_AVAILABLE:
            return None
        try:
            buf = np.frombuffer(data, dtype=np.uint8)
            img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
            return img
        except Exception as e:
            print(f"JPEG decode error: {e}")
            return None

    def detect_edges(
        self,
        image: np.ndarray,
        low_threshold: float = 50.0,
        high_threshold: float = 150.0,
    ) -> np.ndarray:
        """Apply Canny edge detection to an image.

        Args:
            image: Input BGR or grayscale image.
            low_threshold: Lower threshold for hysteresis.
            high_threshold: Upper threshold for hysteresis.

        Returns:
            Binary edge image.
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        return cv2.Canny(gray, low_threshold, high_threshold)

    def find_contours(
        self,
        image: np.ndarray,
        mode: Optional[int] = None,
        method: Optional[int] = None,
    ) -> List[np.ndarray]:
        """Find contours in a binary image.

        Args:
            image: Binary image (e.g., from edge detection or thresholding).
            mode: Contour retrieval mode (default RETR_EXTERNAL).
            method: Contour approximation method (default CHAIN_APPROX_SIMPLE).

        Returns:
            List of contours, each as an (N, 1, 2) numpy array.
        """
        if mode is None:
            mode = cv2.RETR_EXTERNAL
        if method is None:
            method = cv2.CHAIN_APPROX_SIMPLE
        contours, _ = cv2.findContours(image, mode, method)
        return list(contours)

    def compute_centroid(self, contour: np.ndarray) -> Tuple[float, float]:
        """Compute the centroid of a contour using image moments.

        Args:
            contour: OpenCV contour as (N, 1, 2) numpy array.

        Returns:
            (cx, cy) tuple in pixel coordinates.
        """
        M = cv2.moments(contour)
        if M["m00"] == 0:
            return (0.0, 0.0)
        cx = M["m10"] / M["m00"]
        cy = M["m01"] / M["m00"]
        return (cx, cy)

    def estimate_depth(
        self,
        bbox_size_px: float,
        known_size_mm: float,
        focal_length: Optional[float] = None,
    ) -> float:
        """Estimate depth using monocular pinhole model.

        depth = (focal_length * known_size_mm) / bbox_size_px

        Args:
            bbox_size_px: Size of the object bounding box in pixels (width or height).
            known_size_mm: Known real-world size of the object in mm.
            focal_length: Optional focal length override.

        Returns:
            Estimated depth in mm.
        """
        fl = focal_length if focal_length is not None else self.focal_length
        if bbox_size_px <= 0:
            return float("inf")
        return (fl * known_size_mm) / bbox_size_px

    def estimate_depth_from_bbox(
        self,
        bbox: Tuple[int, int, int, int],
        known_size_mm: float,
        use_dimension: str = "width",
    ) -> float:
        """Estimate depth from a bounding box and known object size.

        Args:
            bbox: (x, y, w, h) bounding box.
            known_size_mm: Known real-world size in mm.
            use_dimension: 'width' or 'height' to use for estimation.

        Returns:
            Estimated depth in mm.
        """
        _, _, w, h = bbox
        size_px = w if use_dimension == "width" else h
        return self.estimate_depth(size_px, known_size_mm)

    def register_transform(
        self,
        name: str,
        transform_matrix: np.ndarray,
    ) -> None:
        """Register a coordinate transformation matrix.

        Args:
            name: Name of the transform (e.g., 'camera_to_robot').
            transform_matrix: 4x4 homogeneous transformation matrix.
        """
        if transform_matrix.shape != (4, 4):
            raise ValueError("Transform must be a 4x4 matrix")
        self._transform_chain[name] = transform_matrix

    def coordinate_transform(
        self,
        point: Tuple[float, float, float],
        from_frame: str,
        to_frame: str,
    ) -> Tuple[float, float, float]:
        """Transform a 3D point between coordinate frames.

        Looks up registered transforms and chains them if necessary.
        Falls back to identity if no transform is registered.

        Args:
            point: (x, y, z) in the source frame.
            from_frame: Source frame name.
            to_frame: Target frame name.

        Returns:
            (x, y, z) in the target frame.
        """
        key = f"{from_frame}_to_{to_frame}"
        if key in self._transform_chain:
            T = self._transform_chain[key]
        else:
            # Try reverse
            rev_key = f"{to_frame}_to_{from_frame}"
            if rev_key in self._transform_chain:
                T = np.linalg.inv(self._transform_chain[rev_key])
            else:
                # Identity fallback
                T = np.eye(4)

        p = np.array([point[0], point[1], point[2], 1.0])
        result = T @ p
        return (float(result[0]), float(result[1]), float(result[2]))

    def visualize_detections(
        self,
        image: np.ndarray,
        detections: List[Dict[str, Any]],
        color_map: Optional[Dict[str, Tuple[int, int, int]]] = None,
    ) -> np.ndarray:
        """Draw bounding boxes and labels on an image for detected objects.

        Args:
            image: Input BGR image (modified in place).
            detections: List of detection dicts with at least 'bbox' and 'class' keys.
            color_map: Optional dict mapping class names to BGR colors.

        Returns:
            The annotated image.
        """
        if color_map is None:
            color_map = {
                "block": (0, 255, 0),
                "cylinder": (255, 0, 0),
                "sphere": (0, 0, 255),
                "irregular": (255, 255, 0),
                "default": (0, 255, 255),
            }

        for det in detections:
            bbox = det.get("bbox")
            if bbox is None:
                continue

            x, y, w, h = bbox
            class_name = det.get("class", det.get("category", "unknown"))
            confidence = det.get("confidence", 0.0)
            color = color_map.get(class_name, color_map["default"])

            # Draw bounding box
            cv2.rectangle(image, (x, y), (x + w, y + h), color, 2)

            # Draw label
            label = f"{class_name} {confidence:.2f}"
            cv2.putText(image, label, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)

            # Draw centroid if available
            cx = det.get("cx")
            cy = det.get("cy")
            if cx is not None and cy is not None:
                cv2.circle(image, (int(cx), int(cy)), 3, color, -1)

        return image

    def draw_coordinate_axes(
        self,
        image: np.ndarray,
        origin: Tuple[int, int],
        rotation: float = 0.0,
        scale: float = 50.0,
    ) -> np.ndarray:
        """Draw coordinate axes on an image for visualization.

        Args:
            image: Input image.
            origin: (x, y) pixel position of the origin.
            rotation: Rotation angle in degrees.
            scale: Length of axis lines in pixels.

        Returns:
            Annotated image.
        """
        ox, oy = origin
        rad = math.radians(rotation)
        cos_r = math.cos(rad)
        sin_r = math.sin(rad)

        # X axis (red)
        x_end = (int(ox + scale * cos_r), int(oy + scale * sin_r))
        cv2.line(image, (ox, oy), x_end, (0, 0, 255), 2)

        # Y axis (green)
        y_end = (int(ox - scale * sin_r), int(oy + scale * cos_r))
        cv2.line(image, (ox, oy), y_end, (0, 255, 0), 2)

        return image

    def compute_iou(
        self,
        bbox1: Tuple[int, int, int, int],
        bbox2: Tuple[int, int, int, int],
    ) -> float:
        """Compute Intersection over Union (IoU) of two bounding boxes.

        Args:
            bbox1: (x, y, w, h) first bounding box.
            bbox2: (x, y, w, h) second bounding box.

        Returns:
            IoU value in [0, 1].
        """
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2

        xi1 = max(x1, x2)
        yi1 = max(y1, y2)
        xi2 = min(x1 + w1, x2 + w2)
        yi2 = min(y1 + h1, y2 + h2)

        inter_w = max(0, xi2 - xi1)
        inter_h = max(0, yi2 - yi1)
        inter_area = inter_w * inter_h

        area1 = w1 * h1
        area2 = w2 * h2
        union_area = area1 + area2 - inter_area

        if union_area == 0:
            return 0.0
        return inter_area / union_area

    def resize_maintain_aspect(
        self,
        image: np.ndarray,
        target_size: Tuple[int, int],
    ) -> np.ndarray:
        """Resize an image while maintaining aspect ratio, padding with black.

        Args:
            image: Input image.
            target_size: (width, height) target dimensions.

        Returns:
            Resized and padded image.
        """
        h, w = image.shape[:2]
        tw, th = target_size
        scale = min(tw / w, th / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        resized = cv2.resize(image, (new_w, new_h))
        padded = np.zeros((th, tw, 3), dtype=np.uint8)
        x_offset = (tw - new_w) // 2
        y_offset = (th - new_h) // 2
        padded[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = resized
        return padded