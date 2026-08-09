"""
Object Detection Interface for Raspberry Pi Vision System.

Provides a unified interface for running object detection using TFLite
or ONNX models. Supports YOLOv8-nano and MobileNet-SSD as primary
detection backbones, with preprocessing, inference, and postprocessing
(NMS, confidence filtering).

Runs on the Raspberry Pi for higher-level detection tasks that complement
the OpenMV's low-level vision processing.
"""

import time
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field

import numpy as np

try:
    import cv2
    CV2_AVAILABLE: bool = True
except ImportError:
    CV2_AVAILABLE = False

# Try importing TFLite runtime
try:
    import tflite_runtime.interpreter as tflite
    TFLITE_AVAILABLE: bool = True
except ImportError:
    try:
        # Fallback to full TensorFlow
        import tensorflow as tf
        tflite = tf.lite
        TFLITE_AVAILABLE = True
    except ImportError:
        TFLITE_AVAILABLE = False
        tflite = None  # type: ignore


@dataclass
class DetectionResult:
    """Single detection result from the object detector.

    Attributes:
        class_name: Human-readable class name.
        class_id: Numeric class ID.
        confidence: Detection confidence (0.0 to 1.0).
        bbox: Bounding box as (x, y, w, h) in pixel coordinates.
        mask: Optional segmentation mask, if available.
    """
    class_name: str
    class_id: int
    confidence: float
    bbox: Tuple[int, int, int, int]
    mask: Optional[np.ndarray] = None


class ObjectDetector:
    """Object detection using TFLite/ONNX models.

    Wraps a TFLite model for inference with preprocessing (resize, normalize)
    and postprocessing (NMS, confidence filtering, coordinate scaling).

    Supported models:
        - YOLOv8-nano (YOLOv8n)
        - MobileNet-SSD

    Attributes:
        model_path: Path to the TFLite model file.
        input_size: (width, height) expected by the model.
        confidence_threshold: Minimum confidence for detections.
        nms_threshold: IoU threshold for Non-Maximum Suppression.
        class_names: List of class name strings.
        interpreter: The TFLite interpreter instance.
        input_details: Model input tensor metadata.
        output_details: Model output tensor metadata.
    """

    # Default COCO class names (subset for typical sampling scenarios)
    DEFAULT_CLASS_NAMES: List[str] = [
        "background",
        "block",
        "cylinder",
        "sphere",
        "irregular",
        "bottle",
        "can",
        "box",
        "bag",
        "tool",
        "electronic",
        "mechanical_part",
        "container",
        "cap",
        "label",
    ]

    def __init__(
        self,
        model_path: Optional[str] = None,
        input_size: Tuple[int, int] = (320, 320),
        confidence_threshold: float = 0.5,
        nms_threshold: float = 0.45,
        class_names: Optional[List[str]] = None,
    ) -> None:
        """Initialize the object detector.

        Args:
            model_path: Path to TFLite model file (loads immediately if provided).
            input_size: Model input dimensions (width, height).
            confidence_threshold: Minimum confidence for valid detections.
            nms_threshold: IoU threshold for NMS.
            class_names: List of class names (uses DEFAULT_CLASS_NAMES if None).
        """
        self.model_path: Optional[str] = model_path
        self.input_size: Tuple[int, int] = input_size
        self.confidence_threshold: float = confidence_threshold
        self.nms_threshold: float = nms_threshold
        self.class_names: List[str] = class_names or self.DEFAULT_CLASS_NAMES

        self.interpreter: Optional[Any] = None
        self.input_details: Optional[Any] = None
        self.output_details: Optional[Any] = None
        self._loaded: bool = False

        if model_path is not None:
            self.load_model(model_path)

    def load_model(self, model_path: str) -> bool:
        """Load a TFLite model from disk.

        Args:
            model_path: Path to the .tflite model file.

        Returns:
            True if loaded successfully, False otherwise.
        """
        if not TFLITE_AVAILABLE:
            print("TFLite runtime not available. Cannot load model.")
            return False

        try:
            self.interpreter = tflite.Interpreter(model_path=model_path)
            self.interpreter.allocate_tensors()
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
            self.model_path = model_path
            self._loaded = True
            print(f"Model loaded: {model_path}")
            print(f"  Input: {self.input_details[0]['shape']}")
            print(f"  Output: {len(self.output_details)} tensor(s)")
            return True
        except Exception as e:
            print(f"Failed to load model: {e}")
            self._loaded = False
            return False

    def detect_objects(
        self,
        image: np.ndarray,
        confidence_threshold: Optional[float] = None,
        nms_threshold: Optional[float] = None,
    ) -> List[DetectionResult]:
        """Run object detection on an image.

        Full pipeline: preprocess -> inference -> postprocess.

        Args:
            image: Input BGR image as numpy array (H, W, 3).
            confidence_threshold: Optional override for confidence threshold.
            nms_threshold: Optional override for NMS threshold.

        Returns:
            List of DetectionResult objects.
        """
        if not self._loaded or self.interpreter is None:
            print("Model not loaded. Call load_model() first.")
            return []

        conf_thresh = confidence_threshold or self.confidence_threshold
        nms_thresh = nms_threshold or self.nms_threshold

        # Preprocess
        input_tensor = self.preprocess(image)

        # Run inference
        outputs = self._inference(input_tensor)

        # Postprocess
        detections = self.postprocess(outputs, conf_thresh, nms_thresh, image.shape)

        return detections

    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """Preprocess an image for model inference.

        Steps:
        1. Convert BGR to RGB
        2. Resize to model input size
        3. Normalize to [0, 1] or [-1, 1] depending on model
        4. Add batch dimension

        Args:
            image: Input BGR image (H, W, 3).

        Returns:
            Preprocessed tensor with shape (1, H, W, 3), float32, [0, 1].
        """
        if not CV2_AVAILABLE:
            return np.zeros((1, *self.input_size[::-1], 3), dtype=np.float32)

        # Convert BGR to RGB
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Resize
        resized = cv2.resize(rgb, self.input_size)

        # Normalize to [0, 1]
        normalized = resized.astype(np.float32) / 255.0

        # Add batch dimension
        batched = np.expand_dims(normalized, axis=0)

        return batched

    def _inference(self, input_tensor: np.ndarray) -> List[np.ndarray]:
        """Run inference on the preprocessed tensor.

        Args:
            input_tensor: Preprocessed input tensor.

        Returns:
            List of output tensors from the model.
        """
        if self.interpreter is None:
            return []

        self.interpreter.set_tensor(self.input_details[0]["index"], input_tensor)
        self.interpreter.invoke()

        outputs = []
        for detail in self.output_details:
            outputs.append(self.interpreter.get_tensor(detail["index"]))

        return outputs

    def postprocess(
        self,
        outputs: List[np.ndarray],
        confidence_threshold: float,
        nms_threshold: float,
        original_shape: Tuple[int, ...],
    ) -> List[DetectionResult]:
        """Postprocess model outputs into DetectionResult objects.

        Handles both YOLO-style and SSD-style outputs. Applies NMS and
        scales bounding boxes back to the original image dimensions.

        Args:
            outputs: List of output tensors from the model.
            confidence_threshold: Minimum confidence.
            nms_threshold: IoU threshold for NMS.
            original_shape: Original image shape (H, W, C).

        Returns:
            List of DetectionResult objects.
        """
        if not outputs:
            return []

        # Try to detect output format
        output = outputs[0]
        detections_raw: List[Tuple[float, float, float, float, float, int]] = []

        if len(output.shape) == 3 and output.shape[1] > 4:
            # YOLO-style: (1, N, 4 + num_classes) or (1, N, 5 + num_classes)
            detections_raw = self._parse_yolo_output(output, confidence_threshold)
        elif len(output.shape) == 3 and output.shape[2] == 7:
            # SSD-style: (1, N, 7) where each row is [image_id, class_id, score, x, y, w, h]
            detections_raw = self._parse_ssd_output(output, confidence_threshold)
        else:
            # Generic: try to parse as detection boxes
            detections_raw = self._parse_generic_output(output, confidence_threshold)

        # Apply NMS
        filtered = self._apply_nms(detections_raw, nms_threshold)

        # Scale to original image size
        orig_h, orig_w = original_shape[:2]
        scale_x = orig_w / self.input_size[0]
        scale_y = orig_h / self.input_size[1]

        results = []
        for x, y, w, h, conf, class_id in filtered:
            # Scale coordinates
            scaled_x = int(x * scale_x)
            scaled_y = int(y * scale_y)
            scaled_w = int(w * scale_x)
            scaled_h = int(h * scale_y)

            class_name = (
                self.class_names[class_id]
                if class_id < len(self.class_names)
                else f"class_{class_id}"
            )

            results.append(DetectionResult(
                class_name=class_name,
                class_id=class_id,
                confidence=float(conf),
                bbox=(scaled_x, scaled_y, scaled_w, scaled_h),
            ))

        return results

    def _parse_yolo_output(
        self,
        output: np.ndarray,
        conf_threshold: float,
    ) -> List[Tuple[float, float, float, float, float, int]]:
        """Parse YOLO-style output.

        Assumes format: (1, N, 4 + num_classes) with [cx, cy, w, h, ...class_scores]
        or (1, N, 5 + num_classes) with [cx, cy, w, h, obj_conf, ...class_scores].

        Args:
            output: YOLO output tensor.
            conf_threshold: Confidence threshold.

        Returns:
            List of (x, y, w, h, confidence, class_id) tuples.
        """
        detections = []
        output = output[0]  # Remove batch dimension

        for detection in output:
            # Determine if there's an objectness score
            if len(detection) == 4 + len(self.class_names):
                # No objectness score: [cx, cy, w, h, ...class_scores]
                cx, cy, w, h = detection[:4]
                class_scores = detection[4:]
                obj_conf = 1.0  # No separate objectness
            elif len(detection) == 5 + len(self.class_names):
                # With objectness: [cx, cy, w, h, obj_conf, ...class_scores]
                cx, cy, w, h = detection[:4]
                obj_conf = detection[4]
                class_scores = detection[5:]
            else:
                # Assume first 4 are bbox, rest are class scores
                cx, cy, w, h = detection[:4]
                class_scores = detection[4:4 + len(self.class_names)]
                obj_conf = 1.0

            max_class_score = np.max(class_scores)
            best_class = int(np.argmax(class_scores))
            confidence = float(obj_conf) * float(max_class_score)

            if confidence >= conf_threshold:
                # Convert center-format to corner-format
                x = cx - w / 2
                y = cy - h / 2
                detections.append((float(x), float(y), float(w), float(h), confidence, best_class))

        return detections

    def _parse_ssd_output(
        self,
        output: np.ndarray,
        conf_threshold: float,
    ) -> List[Tuple[float, float, float, float, float, int]]:
        """Parse SSD-style output.

        Assumes format: (1, N, 7) with [image_id, class_id, score, xmin, ymin, xmax, ymax].

        Args:
            output: SSD output tensor.
            conf_threshold: Confidence threshold.

        Returns:
            List of (x, y, w, h, confidence, class_id) tuples.
        """
        detections = []
        output = output[0]

        for det in output:
            _, class_id, score, xmin, ymin, xmax, ymax = det
            confidence = float(score)
            if confidence >= conf_threshold:
                x = float(xmin)
                y = float(ymin)
                w = float(xmax - xmin)
                h = float(ymax - ymin)
                detections.append((x, y, w, h, confidence, int(class_id)))

        return detections

    def _parse_generic_output(
        self,
        output: np.ndarray,
        conf_threshold: float,
    ) -> List[Tuple[float, float, float, float, float, int]]:
        """Fallback parser for unknown output formats.

        Args:
            output: Output tensor.
            conf_threshold: Confidence threshold.

        Returns:
            List of parsed detections.
        """
        detections = []
        output = output[0]

        # Try to find at least 5 columns (bbox + confidence) + optional class
        if output.shape[-1] >= 5:
            for det in output:
                if len(det) >= 5:
                    if len(det) >= 6:
                        x, y, w, h, conf, class_id = det[:6]
                    else:
                        x, y, w, h, conf = det[:5]
                        class_id = 0
                    if float(conf) >= conf_threshold:
                        detections.append((float(x), float(y), float(w), float(h), float(conf), int(class_id)))

        return detections

    def _apply_nms(
        self,
        detections: List[Tuple[float, float, float, float, float, int]],
        nms_threshold: float,
    ) -> List[Tuple[float, float, float, float, float, int]]:
        """Apply Non-Maximum Suppression to filter overlapping detections.

        Args:
            detections: List of (x, y, w, h, confidence, class_id) tuples.
            nms_threshold: IoU threshold for suppression.

        Returns:
            Filtered list of detections.
        """
        if not detections:
            return []

        # Sort by confidence descending
        detections = sorted(detections, key=lambda d: d[4], reverse=True)
        kept: List[Tuple[float, float, float, float, float, int]] = []

        while detections:
            best = detections.pop(0)
            kept.append(best)
            bx, by, bw, bh = best[0], best[1], best[2], best[3]

            filtered = []
            for det in detections:
                dx, dy, dw, dh = det[0], det[1], det[2], det[3]

                # Compute IoU
                xi1 = max(bx, dx)
                yi1 = max(by, dy)
                xi2 = min(bx + bw, dx + dw)
                yi2 = min(by + bh, dy + dh)
                inter_w = max(0, xi2 - xi1)
                inter_h = max(0, yi2 - yi1)
                inter_area = inter_w * inter_h

                area1 = bw * bh
                area2 = dw * dh
                union = area1 + area2 - inter_area
                iou = inter_area / union if union > 0 else 0.0

                if iou < nms_threshold:
                    filtered.append(det)

            detections = filtered

        return kept

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model.

        Returns:
            Dict with model metadata.
        """
        if not self._loaded:
            return {"loaded": False}
        return {
            "loaded": True,
            "model_path": self.model_path,
            "input_size": self.input_size,
            "input_shape": list(self.input_details[0]["shape"]) if self.input_details else [],
            "num_outputs": len(self.output_details) if self.output_details else 0,
            "num_classes": len(self.class_names),
            "confidence_threshold": self.confidence_threshold,
            "nms_threshold": self.nms_threshold,
        }

    def benchmark(self, num_runs: int = 10) -> Dict[str, float]:
        """Benchmark inference speed on a dummy input.

        Args:
            num_runs: Number of inference runs to average.

        Returns:
            Dict with 'avg_time_ms', 'fps', 'min_time_ms', 'max_time_ms'.
        """
        if not self._loaded:
            return {"avg_time_ms": 0, "fps": 0, "min_time_ms": 0, "max_time_ms": 0}

        dummy = np.random.randn(1, self.input_size[1], self.input_size[0], 3).astype(np.float32)
        times = []

        # Warmup
        for _ in range(3):
            self._inference(dummy)

        # Benchmark
        for _ in range(num_runs):
            start = time.perf_counter()
            self._inference(dummy)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        avg = sum(times) / len(times)
        return {
            "avg_time_ms": round(avg, 2),
            "fps": round(1000.0 / avg, 1) if avg > 0 else 0,
            "min_time_ms": round(min(times), 2),
            "max_time_ms": round(max(times), 2),
        }