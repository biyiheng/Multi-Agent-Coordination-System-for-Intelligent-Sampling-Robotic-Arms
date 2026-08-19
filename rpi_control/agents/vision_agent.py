"""
Vision Guidance Agent for the Intelligent Sampling Robotic Arm.

Manages communication with the OpenMV camera, sends vision detection
requests, parses responses, and transforms results into robot-frame
coordinates for motion planning.

Provides: object detection, AprilTag pose estimation, tracking, outlier
filtering, and multi-view fusion for robust perception.
"""

import asyncio
import json
import math
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Set, Tuple

import numpy as np

from .base_agent import BaseAgent, AgentConfig, validate_state, log_execution


class VisionAgent(BaseAgent):
    """Agent for vision-based perception and guidance.

    Communicates with the OpenMV H7+ camera over UART to request:
    - Color-based object detection
    - AprilTag detection and pose estimation
    - Object classification
    - Quality inspection
    - Continuous tracking

    Transforms vision results from camera frame to robot frame using
    calibrated coordinate transforms.

    Attributes:
        uart: UART communication interface (set externally).
        calibration: CameraCalibration instance (set externally).
        tracking_active: Whether continuous tracking is active.
        position_history: Recent position estimates for filtering.
        workspace_bounds: Valid workspace bounds for position validation.
    """

    def __init__(
        self,
        name: str = "vision_agent",
        config: Optional[AgentConfig] = None,
    ) -> None:
        """Initialize the vision agent.

        Args:
            name: Agent name.
            config: Agent configuration.
        """
        super().__init__(name, config)
        self.uart: Any = None  # UART protocol interface to OpenMV
        self.calibration: Any = None  # CameraCalibration instance
        self.tracking_active: bool = False
        self.tracking_target: Optional[str] = None
        self.position_history: Deque[Dict[str, Any]] = deque(maxlen=20)
        self.workspace_bounds: Dict[str, Tuple[float, float]] = {
            "x": (0.0, 500.0),
            "y": (0.0, 500.0),
            "z": (0.0, 300.0),
        }
        self._outlier_threshold: float = 3.0  # Standard deviations for outlier detection
        # v1.2: EMA (指数移动平均) 多帧融合滤波, 提升连续检测稳定性
        self._ema_alpha: float = 0.3  # 平滑因子 (越大越跟随最新帧)
        self._ema_state: Optional[np.ndarray] = None  # (cx, cy, depth) 滑动均值
        self._ema_count: int = 0
        # Calibrated camera parameters (for depth estimation)
        # OpenMV H7+ camera: OV5640 sensor, typical values for 320x240 resolution
        self._focal_length: float = 800.0  # pixels (will be updated by calibration)
        self._real_object_diameter: float = 30.0  # mm (known object size)
        self._pixel_to_mm_ratio: float = 0.5  # mm/pixel (approximate)
        # Camera intrinsic matrix (for precise coordinate transformation)
        self._camera_matrix: Optional[np.ndarray] = None  # 3x3 intrinsic matrix
        self._dist_coeffs: Optional[np.ndarray] = None  # Distortion coefficients
        self._image_width: int = 320  # OpenMV default resolution
        self._image_height: int = 240
        # Depth estimation calibration
        self._depth_scale: float = 1.0  # Scale factor for depth correction
        self._depth_offset: float = 0.0  # Offset for depth correction (mm)
        self._use_stereo_depth: bool = False  # Whether to use stereo depth if available

    async def validate(self, state: Dict[str, Any]) -> bool:
        """Validate that the vision agent is ready.

        Args:
            state: Current system state.

        Returns:
            True if ready.
        """
        return True

    @validate_state(required_keys=["detection_type"])
    @log_execution
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process a vision request based on the detection_type in state.

        Args:
            state: Must contain 'detection_type' and optional parameters.

        Returns:
            State dict with 'vision_result' key.
        """
        detection_type = state.get("detection_type", "detect_color")
        params = state.get("vision_params", {})

        result = None

        if detection_type == "detect_color":
            result = await self.request_detection("detect_color", params)
        elif detection_type == "detect_apriltag":
            result = await self.request_detection("detect_apriltag", params)
        elif detection_type == "classify":
            result = await self.request_detection("classify", params)
        elif detection_type == "inspect":
            result = await self.request_detection("inspect", params)
        elif detection_type == "track":
            result = await self.track_object(params.get("object_id", "red"))
        elif detection_type == "detect_all":
            result = await self.request_detection("detect_all", params)
        else:
            result = {"error": f"Unknown detection type: {detection_type}"}

        state["vision_result"] = result
        return state

    # =========================================================================
    # Detection Requests
    # =========================================================================

    async def request_detection(
        self,
        detection_type: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Send a vision detection request to the OpenMV camera.

        Args:
            detection_type: Type of detection to perform.
            params: Parameters for the detection command.

        Returns:
            Parsed vision result dict.
        """
        # Build command string
        command_parts = [detection_type]
        if detection_type == "detect_color":
            command_parts.append(params.get("color_name", "red"))
            if params.get("roi"):
                command_parts.append(params["roi"])
        elif detection_type == "detect_apriltag":
            if params.get("tag_id") is not None:
                command_parts.append(str(params["tag_id"]))
        elif detection_type == "inspect":
            if params.get("sample_id"):
                command_parts.append(params["sample_id"])

        command_str = ":".join(command_parts)

        # Send over UART
        raw_response = await self._send_uart_command(command_str)

        # Parse the response
        result = self.parse_vision_result(raw_response)

        return result

    async def _send_uart_command(self, command: str) -> Optional[str]:
        """Send a command over UART and wait for response.

        In a real implementation, this would use the actual UART interface.
        Here we provide a simulated interface that can be overridden.

        Args:
            command: Command string to send.

        Returns:
            Raw response string.
        """
        if self.uart is None:
            self.log("UART not available, returning simulated response", 30)
            return self._simulate_response(command)

        try:
            # Send command: #command!
            self.uart.write(f"#{command}!")
            # Wait for response
            response = self.uart.receive_command(timeout_ms=2000)
            if response:
                return json.dumps(response)
            return None
        except Exception as e:
            self.log(f"UART command failed: {e}", 40)
            return None

    def _simulate_response(self, command: str) -> str:
        """Generate a simulated response for testing without hardware.

        Args:
            command: The command that was sent.

        Returns:
            Simulated JSON response string.
        """
        import random
        if command.startswith("detect_color"):
            return json.dumps({
                "success": True,
                "type": "color",
                "data": {
                    "color": command.split(":")[1] if ":" in command else "red",
                    "found": True,
                    "detection": {
                        "color": "red",
                        "cx": random.randint(100, 220),
                        "cy": random.randint(80, 160),
                        "width": random.randint(20, 60),
                        "height": random.randint(20, 60),
                        "area": random.randint(500, 3000),
                        "confidence": round(random.uniform(0.7, 0.99), 3),
                    },
                },
            })
        elif command.startswith("detect_apriltag"):
            return json.dumps({
                "success": True,
                "type": "apriltag",
                "data": {
                    "found": True,
                    "count": 1,
                    "tags": [{
                        "id": 0,
                        "cx": 160, "cy": 120,
                        "x": random.uniform(-50, 50),
                        "y": random.uniform(-50, 50),
                        "z": random.uniform(200, 400),
                        "roll": 0, "pitch": 0, "yaw": 0,
                        "confidence": 0.95,
                    }],
                },
            })
        elif command.startswith("classify"):
            return json.dumps({
                "success": True,
                "type": "classification",
                "data": {
                    "category": random.choice(["block", "cylinder", "sphere"]),
                    "confidence": round(random.uniform(0.6, 0.95), 3),
                    "color": random.choice(["red", "blue", "green"]),
                    "bbox": (100, 80, 50, 50),
                },
            })
        elif command.startswith("inspect"):
            return json.dumps({
                "success": True,
                "type": "quality",
                "data": {
                    "passed": True,
                    "score": round(random.uniform(75, 98), 1),
                    "defects": [],
                    "dimensions": {"measured_width_mm": 30.0, "measured_height_mm": 30.0},
                },
            })
        return json.dumps({"success": False, "error": "Unknown command"})

    # =========================================================================
    # Response Parsing
    # =========================================================================

    def parse_vision_result(self, raw_data: Optional[str]) -> Dict[str, Any]:
        """Parse the raw response from OpenMV into a structured dict.

        Args:
            raw_data: Raw JSON response string.

        Returns:
            Parsed result dict.
        """
        if raw_data is None:
            return {"success": False, "error": "No response from OpenMV"}

        try:
            result = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
        except json.JSONDecodeError:
            return {"success": False, "error": f"Invalid JSON: {raw_data[:100]}"}

        # Extract the data payload
        if isinstance(result, dict):
            if "data" in result:
                return result["data"]
            return result

        return {"success": False, "error": "Unexpected response format"}

    # =========================================================================
    # Position Validation
    # =========================================================================

    def validate_target_position(
        self,
        position: Tuple[float, float, float],
        workspace: Optional[Dict[str, Tuple[float, float]]] = None,
    ) -> bool:
        """Check if a position is within the valid workspace.

        Args:
            position: (x, y, z) in mm.
            workspace: Optional workspace bounds override.

        Returns:
            True if position is valid.
        """
        bounds = workspace or self.workspace_bounds
        x, y, z = position
        return (
            bounds["x"][0] <= x <= bounds["x"][1]
            and bounds["y"][0] <= y <= bounds["y"][1]
            and bounds["z"][0] <= z <= bounds["z"][1]
        )

    # =========================================================================
    # Pose Estimation
    # =========================================================================

    def estimate_object_pose(self, detection_result: Dict[str, Any]) -> Dict[str, Any]:
        """Compute the 6-DOF pose of a detected object with calibrated depth.

        Uses three tiers of depth estimation (ordered by priority):
        1. Stereo depth (if available): most accurate
        2. AprilTag pose: direct 6-DOF from tag detection
        3. Calibrated monocular: pinhole model with calibration correction

        Args:
            detection_result: Vision detection result dict.

        Returns:
            Dict with position (x, y, z) in mm and orientation (roll, pitch, yaw).
        """
        # Tier 1: AprilTag detection - use tag pose directly (most accurate)
        if "tags" in detection_result:
            tag = detection_result["tags"][0] if detection_result["tags"] else {}
            return {
                "position": (
                    tag.get("x", 0.0),
                    tag.get("y", 0.0),
                    tag.get("z", 0.0),
                ),
                "orientation": (
                    tag.get("roll", 0.0),
                    tag.get("pitch", 0.0),
                    tag.get("yaw", 0.0),
                ),
                "source": "apriltag",
                "depth_method": "tag_pose",
                "confidence": tag.get("confidence", 0.0),
            }

        if "detection" in detection_result:
            det = detection_result["detection"]
            if det is None:
                return {"position": (0.0, 0.0, 0.0), "orientation": (0.0, 0.0, 0.0),
                        "source": "none", "depth_method": "none"}

            cx = det.get("cx", 0.0)
            cy = det.get("cy", 0.0)
            area = det.get("area", 0)
            confidence = det.get("confidence", 0.0)

            # Tier 2: Stereo depth (if available from multi-view)
            stereo_z = None
            if self._use_stereo_depth and "disparity" in det:
                stereo_z = self._depth_from_disparity(det["disparity"])

            # Tier 3: Calibrated monocular depth estimation
            if stereo_z is not None:
                z_est = stereo_z
                depth_method = "stereo"
            elif area and area > 0:
                z_est = self._depth_from_blob_area(area)
                depth_method = "monocular_blob"
            else:
                z_est = 300.0  # Default safe depth
                depth_method = "default"

            # Apply calibration correction
            z_est = z_est * self._depth_scale + self._depth_offset

            # Convert pixel coordinates to real-world mm using depth
            x_mm, y_mm = self._pixel_to_world(cx, cy, z_est)

            return {
                "position": (x_mm, y_mm, z_est),
                "orientation": (0.0, 0.0, 0.0),
                "source": "blob",
                "depth_method": depth_method,
                "confidence": confidence,
                "pixel_coords": (cx, cy),
                "blob_area": area,
            }

        return {"position": (0.0, 0.0, 0.0), "orientation": (0.0, 0.0, 0.0),
                "source": "unknown", "depth_method": "none"}

    def _depth_from_blob_area(self, area: float) -> float:
        """Estimate depth from blob area using calibrated pinhole camera model.

        Uses the formula: z = (focal_length * real_diameter) / blob_diameter
        where blob_diameter is derived from the detected blob area.

        Args:
            area: Detected blob area in pixels².

        Returns:
            Estimated depth in mm.
        """
        # Blob diameter from area (assuming circular blob)
        blob_diameter = math.sqrt(4.0 * area / math.pi)
        # Depth = (focal_length * real_diameter) / blob_diameter
        z_est = (self._focal_length * self._real_object_diameter) / max(blob_diameter, 1.0)
        # Clamp to valid range
        return max(10.0, min(1000.0, z_est))

    def _depth_from_disparity(self, disparity: float) -> float:
        """Estimate depth from stereo disparity.

        Uses the formula: z = (focal_length * baseline) / disparity

        Args:
            disparity: Disparity value in pixels.

        Returns:
            Estimated depth in mm.
        """
        baseline = 60.0  # mm, typical stereo baseline
        if disparity <= 0:
            return 300.0  # Default
        z_est = (self._focal_length * baseline) / disparity
        return max(10.0, min(1000.0, z_est))

    def _pixel_to_world(self, cx: float, cy: float, depth: float) -> Tuple[float, float]:
        """Convert pixel coordinates to world coordinates using camera intrinsics.

        Uses the pinhole camera model:
        x_world = (cx - cx_principal) * depth / fx
        y_world = (cy - cy_principal) * depth / fy

        If camera matrix is not calibrated, falls back to simple ratio conversion.

        Args:
            cx: Pixel x-coordinate.
            cy: Pixel y-coordinate.
            depth: Estimated depth in mm.

        Returns:
            (x_mm, y_mm) world coordinates in mm.
        """
        if self._camera_matrix is not None:
            # Use calibrated camera intrinsics
            fx = self._camera_matrix[0, 0]
            fy = self._camera_matrix[1, 1]
            cx_principal = self._camera_matrix[0, 2]
            cy_principal = self._camera_matrix[1, 2]

            x_mm = (cx - cx_principal) * depth / fx
            y_mm = (cy - cy_principal) * depth / fy
        else:
            # Fallback: simple ratio conversion using image center
            x_mm = (cx - self._image_width / 2) * self._pixel_to_mm_ratio
            y_mm = (cy - self._image_height / 2) * self._pixel_to_mm_ratio

        return (x_mm, y_mm)

    # =========================================================================
    # Tracking
    # =========================================================================

    async def track_object(self, object_id: str) -> Dict[str, Any]:
        """Start or continue tracking an object.

        In tracking mode, the OpenMV continuously sends position updates
        for the specified object.

        Args:
            object_id: Identifier for the object to track (color name or tag ID).

        Returns:
            Latest tracking data.
        """
        if not self.tracking_active:
            self.tracking_active = True
            self.tracking_target = object_id
            self.log(f"Starting tracking for: {object_id}")

        # Request tracking data
        result = await self.request_detection("track", {"object_id": object_id})
        if result.get("found"):
            self.position_history.append(result)

        return result

    def stop_tracking(self) -> None:
        """Stop the continuous tracking mode."""
        self.tracking_active = False
        self.tracking_target = None
        self.position_history.clear()
        self.reset_ema()  # v1.2: 停止跟踪时重置 EMA 融合状态
        self.log("Tracking stopped")

    # =========================================================================
    # Coordinate Transform
    # =========================================================================

    def coordinate_transform_to_robot(
        self,
        camera_pose: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Transform a camera-frame pose to robot base frame.

        Uses the hand-eye calibration if available.

        Args:
            camera_pose: Dict with 'position' and 'orientation' keys.

        Returns:
            Dict with robot-frame position and orientation.
        """
        if self.calibration is None or not self.calibration.is_hand_eye_calibrated():
            self.log("Hand-eye calibration not available, returning camera-frame pose", 30)
            return camera_pose

        pos = camera_pose.get("position", (0.0, 0.0, 0.0))
        robot_pos = self.calibration.camera_to_robot(pos)

        if robot_pos is None:
            return camera_pose

        return {
            "position": robot_pos,
            "orientation": camera_pose.get("orientation", (0.0, 0.0, 0.0)),
            "source": camera_pose.get("source", "unknown"),
            "frame": "robot",
        }

    def configure_calibration(
        self,
        camera_matrix: Any,
        hand_eye_rotation: Any,
        hand_eye_translation: Any,
        image_width: Optional[int] = None,
        image_height: Optional[int] = None,
        dist_coeffs: Any = None,
    ) -> None:
        """从内参与手眼标定参数构建并接入 CameraCalibration。

        将配置中的相机内参 K 与手眼变换 (R, t) 组装进 self.calibration,
        使 coordinate_transform_to_robot / pose_in_robot_frame 能真正工作。
        单位约定: hand_eye_translation 为 mm (与机器人基座系一致)。

        Args:
            camera_matrix: 3x3 相机内参矩阵 (list / np.ndarray)。
            hand_eye_rotation: 3x3 相机->机器人旋转矩阵。
            hand_eye_translation: 3x1 相机->机器人平移向量 (mm)。
            image_width: 图像宽度 (像素), 默认 320。
            image_height: 图像高度 (像素), 默认 240。
            dist_coeffs: 可选畸变系数。
        """
        from ..vision.calibration import CameraCalibration

        cal = CameraCalibration()
        cal.camera_matrix = np.array(camera_matrix, dtype=np.float64).reshape(3, 3)
        cal.rotation_matrix = np.array(hand_eye_rotation, dtype=np.float64).reshape(3, 3)
        cal.translation_vector = np.array(
            hand_eye_translation, dtype=np.float64
        ).reshape(3, 1)
        cal.image_size = (image_width or 320, image_height or 240)
        if dist_coeffs is not None:
            cal.dist_coeffs = np.array(dist_coeffs, dtype=np.float64)

        self.calibration = cal
        self._camera_matrix = cal.camera_matrix
        self._image_width = cal.image_size[0]
        self._image_height = cal.image_size[1]
        # 同步焦距: 确保 Blob 深度估计 (_depth_from_blob_area) 与像素->世界
        # 换算 (_pixel_to_world) 使用同一内参焦距, 避免两者 800 vs 320 失配。
        self._focal_length = float(
            (cal.camera_matrix[0, 0] + cal.camera_matrix[1, 1]) / 2.0
        )
        self.log(
            "已接入相机标定: fx=%.1f fy=%.1f cx=%.1f cy=%.1f, 手眼t=(%.1f, %.1f, %.1f)mm"
            % (cal.camera_matrix[0, 0], cal.camera_matrix[1, 1],
               cal.camera_matrix[0, 2], cal.camera_matrix[1, 2],
               cal.translation_vector[0, 0], cal.translation_vector[1, 0],
               cal.translation_vector[2, 0])
        )

    def pose_in_robot_frame(self, detection_result: Dict[str, Any]) -> Dict[str, Any]:
        """把一次检测结果转换为机器人基座系位姿 (单位 mm)。

        完整链路: 检测结果 -> estimate_object_pose(相机系, mm)
                         -> coordinate_transform_to_robot(机器人基座系, mm)。

        Args:
            detection_result: 检测结果 dict (来自 OpenMV 的 blob / apriltag)。

        Returns:
            含 'position' (x, y, z) 的位姿 dict (mm, 机器人基座系);
            若未配置手眼标定则退回相机系位姿并在日志中警告。
        """
        camera_pose = self.estimate_object_pose(detection_result)
        robot_pose = self.coordinate_transform_to_robot(camera_pose)

        if robot_pose.get("frame") != "robot":
            self.log(
                "手眼标定不可用, 目标坐标仍处于相机系 (不可直接用于运动)", 30,
            )
        else:
            pos = robot_pose.get("position", (0.0, 0.0, 0.0))
            self.log(
                "目标坐标 -> 机器人基座系 (x=%.1f, y=%.1f, z=%.1f) mm"
                % (pos[0], pos[1], pos[2])
            )
        return robot_pose

    # =========================================================================
    # Filtering
    # =========================================================================

    def filter_outliers(self, positions: List[Tuple[float, float, float]]) -> List[Tuple[float, float, float]]:
        """Remove outlier positions using median absolute deviation.

        Filters out positions that deviate significantly from the median
        in any dimension.

        Args:
            positions: List of (x, y, z) position tuples.

        Returns:
            Filtered list of positions.
        """
        if len(positions) < 3:
            return positions

        arr = np.array(positions)
        medians = np.median(arr, axis=0)
        mads = np.median(np.abs(arr - medians), axis=0)
        # Scale MAD to approximate standard deviation
        std_approx = mads * 1.4826

        # Keep points within threshold
        mask = np.all(np.abs(arr - medians) <= self._outlier_threshold * std_approx, axis=1)
        return [positions[i] for i in range(len(positions)) if mask[i]]

    def get_filtered_position(self) -> Optional[Dict[str, Any]]:
        """Get the median-filtered position from recent tracking history.

        Returns:
            Filtered position dict, or None if no history.
        """
        if not self.position_history:
            return None

        positions = []
        for entry in self.position_history:
            det = entry.get("detection", entry)
            if det and "cx" in det and "cy" in det:
                positions.append((det["cx"], det["cy"], det.get("area", 0)))

        if not positions:
            return None

        filtered = self.filter_outliers(positions)
        if not filtered:
            return None

        arr = np.array(filtered)
        median_pos = np.median(arr, axis=0)
        return {
            "cx": float(median_pos[0]),
            "cy": float(median_pos[1]),
            "area": float(median_pos[2]),
            "num_samples": len(filtered),
        }

    # =========================================================================
    # EMA 多帧融合滤波 (v1.2)
    # =========================================================================

    def get_smoothed_position(self) -> Optional[Dict[str, Any]]:
        """基于 EMA (指数移动平均) 的多帧融合滤波位置.

        在 `get_filtered_position` 中值滤波基础上, 对 (cx, cy, depth)
        做指数移动平均, 抑制帧间抖动, 提升抓取引导的稳定性。
        每调用一次推进一帧; 无有效历史或历史中断时自动重置。

        Returns:
            平滑后的位置 dict (含 ema_alpha / ema_count), 或 None。
        """
        filtered = self.get_filtered_position()
        if filtered is None:
            # 历史中断, 重置 EMA 状态, 避免陈旧均值污染
            self._ema_state = None
            self._ema_count = 0
            return None

        current = np.array([filtered["cx"], filtered["cy"], filtered["area"]])
        if self._ema_state is None:
            self._ema_state = current.copy()
            self._ema_count = 1
        else:
            self._ema_state = (
                self._ema_alpha * current
                + (1.0 - self._ema_alpha) * self._ema_state
            )
            self._ema_count += 1

        return {
            "cx": float(self._ema_state[0]),
            "cy": float(self._ema_state[1]),
            "area": float(self._ema_state[2]),
            "num_samples": filtered["num_samples"],
            "smoothed": True,
            "ema_alpha": self._ema_alpha,
            "ema_count": self._ema_count,
        }

    def reset_ema(self) -> None:
        """重置 EMA 融合状态 (目标切换 / 停止跟踪时调用)."""
        self._ema_state = None
        self._ema_count = 0

    # =========================================================================
    # Multi-View Fusion
    # =========================================================================

    def fuse_multiple_detections(
        self,
        detections: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Combine multiple detection results from different views.

        Uses weighted averaging based on confidence scores.

        Args:
            detections: List of detection result dicts.

        Returns:
            Fused result dict with averaged position and confidence.
        """
        if not detections:
            return {"found": False, "error": "No detections to fuse"}

        if len(detections) == 1:
            return detections[0]

        # Extract positions and confidences
        positions = []
        confidences = []
        for det in detections:
            pose = self.estimate_object_pose(det)
            pos = pose.get("position", (0, 0, 0))
            positions.append(pos)
            conf = det.get("detection", {}).get("confidence", 0.5)
            confidences.append(conf)

        total_conf = sum(confidences)
        if total_conf == 0:
            return detections[0]

        # Weighted average
        fused_pos = (
            sum(p[0] * c for p, c in zip(positions, confidences)) / total_conf,
            sum(p[1] * c for p, c in zip(positions, confidences)) / total_conf,
            sum(p[2] * c for p, c in zip(positions, confidences)) / total_conf,
        )

        return {
            "found": True,
            "detection": {
                "cx": fused_pos[0],
                "cy": fused_pos[1],
                "z": fused_pos[2],
                "confidence": round(total_conf / len(detections), 3),
                "fused": True,
                "num_views": len(detections),
            },
        }

    # =========================================================================
    # Camera Calibration
    # =========================================================================

    def set_camera_params(
        self,
        focal_length: Optional[float] = None,
        real_object_diameter: Optional[float] = None,
        pixel_to_mm_ratio: Optional[float] = None,
        camera_matrix: Optional[np.ndarray] = None,
        dist_coeffs: Optional[np.ndarray] = None,
        depth_scale: Optional[float] = None,
        depth_offset: Optional[float] = None,
        image_width: Optional[int] = None,
        image_height: Optional[int] = None,
    ) -> None:
        """Update camera calibration parameters.

        Supports both simple parameters and full camera intrinsic calibration.

        Args:
            focal_length: Camera focal length in pixels.
            real_object_diameter: Known object diameter in mm.
            pixel_to_mm_ratio: Conversion ratio from pixels to mm.
            camera_matrix: 3x3 camera intrinsic matrix.
            dist_coeffs: Distortion coefficients (k1, k2, p1, p2, k3).
            depth_scale: Scale factor for depth correction.
            depth_offset: Offset for depth correction in mm.
            image_width: Camera image width in pixels.
            image_height: Camera image height in pixels.
        """
        if focal_length is not None:
            self._focal_length = focal_length
        if real_object_diameter is not None:
            self._real_object_diameter = real_object_diameter
        if pixel_to_mm_ratio is not None:
            self._pixel_to_mm_ratio = pixel_to_mm_ratio
        if camera_matrix is not None:
            self._camera_matrix = np.array(camera_matrix, dtype=np.float64)
        if dist_coeffs is not None:
            self._dist_coeffs = np.array(dist_coeffs, dtype=np.float64)
        if depth_scale is not None:
            self._depth_scale = depth_scale
        if depth_offset is not None:
            self._depth_offset = depth_offset
        if image_width is not None:
            self._image_width = image_width
        if image_height is not None:
            self._image_height = image_height

        params_str = (
            f"f={self._focal_length}px, D={self._real_object_diameter}mm, "
            f"ratio={self._pixel_to_mm_ratio}mm/px, "
            f"depth_scale={self._depth_scale}, depth_offset={self._depth_offset}"
        )
        if self._camera_matrix is not None:
            params_str += f", camera_matrix={self._camera_matrix.tolist()}"
        self.log(f"Camera params updated: {params_str}")

    def check_camera_health(self) -> Dict[str, Any]:
        """Check camera health status.

        Returns:
            Dict with camera health metrics.
        """
        return {
            "focal_length": self._focal_length,
            "real_object_diameter": self._real_object_diameter,
            "pixel_to_mm_ratio": self._pixel_to_mm_ratio,
            "depth_scale": self._depth_scale,
            "depth_offset": self._depth_offset,
            "has_camera_matrix": self._camera_matrix is not None,
            "has_dist_coeffs": self._dist_coeffs is not None,
            "image_resolution": (self._image_width, self._image_height),
            "tracking_active": self.tracking_active,
            "position_history_size": len(self.position_history),
            "calibration_available": self.calibration is not None,
            "uart_connected": self.uart is not None,
        }