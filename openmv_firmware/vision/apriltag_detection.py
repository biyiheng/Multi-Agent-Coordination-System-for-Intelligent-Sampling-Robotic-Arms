"""
AprilTag Detection and Pose Estimation for OpenMV H7 Plus.

Detects AprilTags from the TAG36H11 family and computes 6-DOF pose
relative to the camera. Supports coordinate transformation to a
defined world frame and multi-tag scenes.

Uses OpenMV's built-in `find_apriltags()` function with known tag size
for accurate pose estimation.
"""

import math
from typing import Dict, List, Optional, Tuple, Any

try:
    import sensor
    import image
    import time
except ImportError:
    pass

from config import (
    APRILTAG_FAMILY,
    APRILTAG_TAG_SIZE,
    APRILTAG_MAX_TAGS,
    APRILTAG_FX,
    APRILTAG_FY,
    APRILTAG_CX,
    APRILTAG_CY,
    CAMERA_RESOLUTION,
)


class AprilTagDetector:
    """Detects AprilTags and computes 6-DOF pose.

    Supports TAG36H11 family with 50mm x 50mm physical tags. Can detect
    multiple tags simultaneously and transform coordinates to a world frame.

    Attributes:
        tag_size_mm: Physical size of the AprilTag in millimeters.
        tag_family: AprilTag family string.
        last_detections: Results from the most recent detection call.
        world_to_camera: 4x4 homogeneous transformation matrix (world-frame to camera-frame).
    """

    def __init__(self, tag_size_mm: float = APRILTAG_TAG_SIZE, tag_family: str = APRILTAG_FAMILY) -> None:
        """Initialize the AprilTag detector.

        Args:
            tag_size_mm: Physical tag size in millimeters (default 50.0).
            tag_family: Tag family name (default 'TAG36H11').
        """
        self.tag_size_mm: float = tag_size_mm
        self.tag_family: str = tag_family
        self.last_detections: List[Dict[str, Any]] = []
        self._fx: Optional[float] = APRILTAG_FX
        self._fy: Optional[float] = APRILTAG_FY
        self._cx: Optional[float] = APRILTAG_CX or (CAMERA_RESOLUTION[0] / 2.0)
        self._cy: Optional[float] = APRILTAG_CY or (CAMERA_RESOLUTION[1] / 2.0)
        # Identity world-to-camera transform (4x4, row-major)
        self.world_to_camera: List[List[float]] = [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]

    def capture_frame(self) -> Any:
        """Capture a new frame from the sensor.

        Returns:
            The captured frame.
        """
        return sensor.snapshot()

    def detect_tags(self) -> List[Dict[str, Any]]:
        """Detect all AprilTags in the current frame.

        Captures a frame and finds all visible AprilTags, computing
        their 2D image positions and 6-DOF poses.

        Returns:
            List of detection dicts, each with keys:
                id, cx, cy, x, y, z, roll, pitch, yaw, confidence,
                rotation_matrix, translation_vector
        """
        frame = self.capture_frame()

        tags = frame.find_apriltags(
            families=image.TAG36H11 if self.tag_family == "TAG36H11" else None,
            fx=self._fx,
            fy=self._fy,
            cx=self._cx,
            cy=self._cy,
        )

        if not tags:
            self.last_detections = []
            return []

        detections = []
        for tag in tags[:APRILTAG_MAX_TAGS]:
            # Extract pose in camera frame
            x = tag.x_translation()  # mm
            y = tag.y_translation()  # mm
            z = tag.z_translation()  # mm

            # Rotation matrix from tag to camera (3x3)
            rot = tag.rotation()
            roll, pitch, yaw = self._rotation_matrix_to_euler(rot)

            # Convert to world frame
            world_pos = self._camera_to_world(x, y, z)
            world_rpy = self._camera_to_world_rotation(roll, pitch, yaw)

            detection = {
                "id": tag.id(),
                "cx": tag.cx(),
                "cy": tag.cy(),
                # Camera-frame pose
                "x": round(x, 2),
                "y": round(y, 2),
                "z": round(z, 2),
                "roll": round(roll, 4),
                "pitch": round(pitch, 4),
                "yaw": round(yaw, 4),
                # World-frame pose
                "world_x": round(world_pos[0], 2),
                "world_y": round(world_pos[1], 2),
                "world_z": round(world_pos[2], 2),
                "world_roll": round(world_rpy[0], 4),
                "world_pitch": round(world_rpy[1], 4),
                "world_yaw": round(world_rpy[2], 4),
                "confidence": round(tag.goodness(), 3),
                "rotation_matrix": rot,
                "corners": list(tag.corners()),
            }
            detections.append(detection)

        self.last_detections = detections
        return detections

    def get_tag_pose(self, tag_id: int) -> Optional[Dict[str, Any]]:
        """Get the 6-DOF pose of a specific tag by its ID.

        Args:
            tag_id: The AprilTag ID to look for.

        Returns:
            Detection dict for the requested tag, or None if not found.
        """
        detections = self.detect_tags()
        for det in detections:
            if det["id"] == tag_id:
                return det
        return None

    def get_tag_position(self, tag_id: int) -> Optional[Tuple[float, float, float]]:
        """Get the (x, y, z) position of a specific tag in camera frame.

        Args:
            tag_id: The AprilTag ID to look for.

        Returns:
            (x, y, z) tuple in mm, or None if tag not found.
        """
        pose = self.get_tag_pose(tag_id)
        if pose is None:
            return None
        return (pose["x"], pose["y"], pose["z"])

    def get_all_tag_ids(self) -> List[int]:
        """Get the IDs of all detected tags.

        Returns:
            List of tag IDs.
        """
        detections = self.detect_tags()
        return [d["id"] for d in detections]

    def get_closest_tag(self) -> Optional[Dict[str, Any]]:
        """Get the tag closest to the camera (smallest z).

        Returns:
            Detection dict for the closest tag, or None.
        """
        detections = self.detect_tags()
        if not detections:
            return None
        return min(detections, key=lambda d: d["z"])

    def set_world_transform(self, transform: List[List[float]]) -> None:
        """Set the world-to-camera transformation matrix.

        Args:
            transform: 4x4 homogeneous transformation matrix (row-major).
        """
        if len(transform) != 4 or any(len(row) != 4 for row in transform):
            raise ValueError("Transform must be a 4x4 matrix")
        self.world_to_camera = transform

    def _camera_to_world(self, x: float, y: float, z: float) -> Tuple[float, float, float]:
        """Transform a point from camera frame to world frame.

        Args:
            x, y, z: Point in camera frame (mm).

        Returns:
            (wx, wy, wz) in world frame (mm).
        """
        T = self.world_to_camera  # T_wc: world -> camera (4x4)
        # P_world = T_wc^-1 * P_cam. 由齐次变换的逆解析求得 (避免依赖除法/数值库):
        #   R_inv = R^T,  t_inv = -R^T * t
        # 之前版本直接左乘 T (未取逆), 当 T 非单位矩阵时坐标会算错。
        r00, r01, r02 = T[0][0], T[0][1], T[0][2]
        r10, r11, r12 = T[1][0], T[1][1], T[1][2]
        r20, r21, r22 = T[2][0], T[2][1], T[2][2]
        t0, t1, t2 = T[0][3], T[1][3], T[2][3]

        # 逆旋转 (转置)
        pc = (x, y, z)
        rx = r00 * pc[0] + r10 * pc[1] + r20 * pc[2]
        ry = r01 * pc[0] + r11 * pc[1] + r21 * pc[2]
        rz = r02 * pc[0] + r12 * pc[1] + r22 * pc[2]
        # 逆平移: t_world = -R^T * t_cam
        ox = -(r00 * t0 + r10 * t1 + r20 * t2)
        oy = -(r01 * t0 + r11 * t1 + r21 * t2)
        oz = -(r02 * t0 + r12 * t1 + r22 * t2)
        return (rx + ox, ry + oy, rz + oz)

    @staticmethod
    def _euler_to_rotation_matrix(roll: float, pitch: float, yaw: float) -> Any:
        """Convert ZYX Euler angles (radians) to a 3x3 rotation matrix."""
        cr, sr = math.cos(roll), math.sin(roll)
        cp, sp = math.cos(pitch), math.sin(pitch)
        cy, sy = math.cos(yaw), math.sin(yaw)
        # R = Rz(yaw) @ Ry(pitch) @ Rx(roll)
        return [
            [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
            [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
            [-sp, cp * sr, cp * cr],
        ]

    def _camera_to_world_rotation(
        self, roll: float, pitch: float, yaw: float,
    ) -> Tuple[float, float, float]:
        """Transform Euler angles from camera frame to world frame.

        正确做法: 将欧拉角构造成旋转矩阵 R_cam, 用 R_world = R_wc^T @ R_cam
        得到世界系旋转矩阵, 再提取欧拉角。之前版本把欧拉角当成 3 维向量
        直接线性组合, 这在数学上不成立 (旋转合成不能对角度做线性叠加)。

        Args:
            roll, pitch, yaw: Euler angles in camera frame (radians).

        Returns:
            (w_roll, w_pitch, w_yaw) in world frame (radians).
        """
        R_cam = self._euler_to_rotation_matrix(roll, pitch, yaw)
        T = self.world_to_camera
        # R_world = R_wc^T @ R_cam (R_wc 是 world->camera 旋转)
        Rw = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
        for i in range(3):
            for j in range(3):
                Rw[i][j] = T[0][i] * R_cam[0][j] + T[1][i] * R_cam[1][j] + T[2][i] * R_cam[2][j]
        return self._rotation_matrix_to_euler(Rw)

    @staticmethod
    def _rotation_matrix_to_euler(R: Any) -> Tuple[float, float, float]:
        """Convert a 3x3 rotation matrix to Euler angles (roll, pitch, yaw).

        Uses the ZYX convention (intrinsic rotations).

        Args:
            R: 3x3 rotation matrix (list of lists or array-like).

        Returns:
            (roll, pitch, yaw) tuple in radians.
        """
        try:
            # Extract matrix elements
            r00, r01, r02 = R[0][0], R[0][1], R[0][2]
            r10, r11, r12 = R[1][0], R[1][1], R[1][2]
            r20, r21, r22 = R[2][0], R[2][1], R[2][2]

            # Pitch
            pitch = math.asin(-r20)
            # Roll
            roll = math.atan2(r21, r22)
            # Yaw
            yaw = math.atan2(r10, r00)

            return (roll, pitch, yaw)
        except Exception:
            return (0.0, 0.0, 0.0)

    def distance_to_tag(self, tag_id: int) -> Optional[float]:
        """Compute Euclidean distance from camera to a specific tag.

        Args:
            tag_id: The AprilTag ID.

        Returns:
            Distance in mm, or None if tag not found.
        """
        pos = self.get_tag_position(tag_id)
        if pos is None:
            return None
        return math.sqrt(pos[0] ** 2 + pos[1] ** 2 + pos[2] ** 2)

    def get_detection_count(self) -> int:
        """Get the number of tags detected in the last scan.

        Returns:
            Number of detected tags.
        """
        return len(self.last_detections)