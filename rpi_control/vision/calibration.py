"""
Camera Calibration for Raspberry Pi Vision System.

Implements Zhang's camera calibration method using chessboard patterns,
hand-eye calibration (AX=XB), and lens distortion correction. Stores
calibration data in YAML format for persistence.

Supports both monocular camera calibration and robot-camera hand-eye
calibration for accurate coordinate transforms.
"""

import os
import json
from typing import Dict, List, Optional, Tuple, Any

import numpy as np

try:
    import cv2
    CV2_AVAILABLE: bool = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import yaml
    YAML_AVAILABLE: bool = True
except ImportError:
    YAML_AVAILABLE = False


class CameraCalibration:
    """Camera calibration using Zhang's method and hand-eye calibration.

    Provides:
    - Chessboard-based intrinsic calibration
    - Lens distortion coefficient estimation
    - Undistortion of images and points
    - Hand-eye calibration (AX=XB)
    - YAML persistence of calibration data

    Attributes:
        camera_matrix: 3x3 intrinsic matrix K.
        dist_coeffs: Distortion coefficients (k1, k2, p1, p2, k3, ...).
        rotation_matrix: 3x3 rotation from camera to robot base.
        translation_vector: 3x1 translation from camera to robot base.
        image_size: (width, height) of the calibrated image resolution.
        rms_error: Reprojection error from calibration.
    """

    def __init__(self) -> None:
        """Initialize empty calibration."""
        self.camera_matrix: Optional[np.ndarray] = None
        self.dist_coeffs: Optional[np.ndarray] = None
        self.rotation_matrix: Optional[np.ndarray] = None
        self.translation_vector: Optional[np.ndarray] = None
        self.image_size: Optional[Tuple[int, int]] = None
        self.rms_error: float = 0.0
        self._calibrated: bool = False

    def calibrate_from_chessboard(
        self,
        images: List[np.ndarray],
        pattern_size: Tuple[int, int] = (9, 6),
        square_size_mm: float = 25.0,
    ) -> bool:
        """Calibrate camera using chessboard images (Zhang's method).

        Args:
            images: List of calibration images (BGR) containing the chessboard.
            pattern_size: (cols, rows) of inner corners on the chessboard.
            square_size_mm: Physical size of each square in mm.

        Returns:
            True if calibration succeeded, False otherwise.
        """
        if not CV2_AVAILABLE:
            print("OpenCV not available. Cannot calibrate.")
            return False

        if len(images) < 3:
            print(f"Need at least 3 images for calibration, got {len(images)}")
            return False

        # Prepare object points (3D points in real-world space)
        objp = np.zeros((pattern_size[0] * pattern_size[1], 3), np.float32)
        objp[:, :2] = np.mgrid[0:pattern_size[0], 0:pattern_size[1]].T.reshape(-1, 2)
        objp *= square_size_mm

        obj_points: List[np.ndarray] = []  # 3D points in real world
        img_points: List[np.ndarray] = []  # 2D points in image plane

        h, w = images[0].shape[:2]
        self.image_size = (w, h)

        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

        for img in images:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            ret, corners = cv2.findChessboardCorners(gray, pattern_size, None)

            if ret:
                obj_points.append(objp)
                corners_refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
                img_points.append(corners_refined)

        if len(obj_points) < 3:
            print(f"Only {len(obj_points)} images with detected chessboard. Need at least 3.")
            return False

        # Calibrate
        ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
            obj_points, img_points, (w, h), None, None,
        )

        self.camera_matrix = mtx
        self.dist_coeffs = dist
        self.rms_error = ret
        self._calibrated = True

        print(f"Calibration successful. RMS error: {ret:.4f} pixels")
        print(f"Camera matrix:\n{mtx}")
        print(f"Distortion coefficients: {dist.ravel()}")

        return True

    def get_intrinsic_matrix(self) -> Optional[np.ndarray]:
        """Get the 3x3 camera intrinsic matrix K.

        K = [[fx, 0,  cx],
             [0,  fy, cy],
             [0,  0,  1 ]]

        Returns:
            3x3 numpy array, or None if not calibrated.
        """
        return self.camera_matrix

    def get_distortion_coeffs(self) -> Optional[np.ndarray]:
        """Get the distortion coefficients.

        Returns (k1, k2, p1, p2, k3, ...) as a 1D array.

        Returns:
            Distortion coefficients array, or None if not calibrated.
        """
        return self.dist_coeffs

    def undistort(self, image: np.ndarray) -> np.ndarray:
        """Remove lens distortion from an image.

        Args:
            image: Distorted input image.

        Returns:
            Undistorted image.
        """
        if not self._calibrated or self.camera_matrix is None or self.dist_coeffs is None:
            return image
        if not CV2_AVAILABLE:
            return image
        h, w = image.shape[:2]
        new_camera_mtx, roi = cv2.getOptimalNewCameraMatrix(
            self.camera_matrix, self.dist_coeffs, (w, h), 1, (w, h),
        )
        undistorted = cv2.undistort(image, self.camera_matrix, self.dist_coeffs, None, new_camera_mtx)
        return undistorted

    def undistort_points(
        self,
        points: np.ndarray,
    ) -> np.ndarray:
        """Undistort 2D image points.

        Args:
            points: (N, 1, 2) or (N, 2) array of distorted image points.

        Returns:
            Undistorted points in the same shape.
        """
        if not self._calibrated or self.camera_matrix is None or self.dist_coeffs is None:
            return points
        if not CV2_AVAILABLE:
            return points

        original_shape = points.shape
        if points.ndim == 2:
            points = points.reshape(-1, 1, 2)

        undistorted = cv2.undistortPoints(
            points.astype(np.float32),
            self.camera_matrix,
            self.dist_coeffs,
            P=self.camera_matrix,
        )

        if original_shape != undistorted.shape:
            undistorted = undistorted.reshape(original_shape)

        return undistorted

    def hand_eye_calibration(
        self,
        robot_poses: List[np.ndarray],
        camera_poses: List[np.ndarray],
        method: Optional[int] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Solve the hand-eye calibration problem (AX=XB).

        Estimates the transformation from camera frame to robot end-effector
        frame given pairs of robot and camera poses.

        Args:
            robot_poses: List of 4x4 robot end-effector pose matrices.
            camera_poses: List of 4x4 camera pose matrices (relative to calibration target).
            method: OpenCV calibration method (default: CALIB_HAND_EYE_TSAI).

        Returns:
            (R, t) tuple: 3x3 rotation matrix and 3x1 translation vector.
        """
        if not CV2_AVAILABLE:
            print("OpenCV not available. Cannot perform hand-eye calibration.")
            return (np.eye(3), np.zeros((3, 1)))

        if len(robot_poses) != len(camera_poses):
            raise ValueError(
                f"Mismatch: {len(robot_poses)} robot poses vs {len(camera_poses)} camera poses"
            )
        if len(robot_poses) < 3:
            raise ValueError(f"Need at least 3 pose pairs, got {len(robot_poses)}")

        if method is None:
            method = cv2.CALIB_HAND_EYE_TSAI

        # Extract rotation vectors and translation vectors
        rvecs_robot = []
        tvecs_robot = []
        rvecs_camera = []
        tvecs_camera = []

        for R_robot, R_camera in zip(robot_poses, camera_poses):
            r_robot = cv2.Rodrigues(R_robot[:3, :3])[0]
            t_robot = R_robot[:3, 3].reshape(3, 1)
            r_camera = cv2.Rodrigues(R_camera[:3, :3])[0]
            t_camera = R_camera[:3, 3].reshape(3, 1)

            rvecs_robot.append(r_robot)
            tvecs_robot.append(t_robot)
            rvecs_camera.append(r_camera)
            tvecs_camera.append(t_camera)

        R, t = cv2.calibrateHandEye(
            rvecs_robot, tvecs_robot,
            rvecs_camera, tvecs_camera,
            method=method,
        )

        self.rotation_matrix = R
        self.translation_vector = t

        print("Hand-eye calibration complete.")
        print(f"Rotation:\n{R}")
        print(f"Translation:\n{t.ravel()}")

        return (R, t)

    def get_transform_matrix(self) -> Optional[np.ndarray]:
        """Get the 4x4 homogeneous transformation matrix from camera to robot base.

        Returns:
            4x4 homogeneous matrix, or None if hand-eye calibration not done.
        """
        if self.rotation_matrix is None or self.translation_vector is None:
            return None
        T = np.eye(4)
        T[:3, :3] = self.rotation_matrix
        T[:3, 3] = self.translation_vector.ravel()
        return T

    def pixel_to_camera(
        self,
        pixel: Tuple[float, float],
        depth: float,
    ) -> Tuple[float, float, float]:
        """Convert a pixel coordinate to a 3D point in camera frame.

        Uses the pinhole camera model: X_c = (u - cx) * Z / fx, etc.

        Args:
            pixel: (u, v) pixel coordinates.
            depth: Depth Z in mm.

        Returns:
            (X, Y, Z) in camera frame (mm).
        """
        if self.camera_matrix is None:
            return (0.0, 0.0, depth)

        fx = self.camera_matrix[0, 0]
        fy = self.camera_matrix[1, 1]
        cx = self.camera_matrix[0, 2]
        cy = self.camera_matrix[1, 2]

        u, v = pixel
        x = (u - cx) * depth / fx
        y = (v - cy) * depth / fy

        return (x, y, depth)

    def camera_to_robot(
        self,
        point: Tuple[float, float, float],
    ) -> Optional[Tuple[float, float, float]]:
        """Transform a point from camera frame to robot base frame.

        Args:
            point: (x, y, z) in camera frame.

        Returns:
            (x, y, z) in robot base frame, or None if not calibrated.
        """
        T = self.get_transform_matrix()
        if T is None:
            return None
        p = np.array([point[0], point[1], point[2], 1.0])
        result = T @ p
        return (float(result[0]), float(result[1]), float(result[2]))

    def save_calibration(self, path: str) -> bool:
        """Save calibration data to a YAML or JSON file.

        Args:
            path: Output file path (.yaml or .json).

        Returns:
            True if saved successfully.
        """
        data: Dict[str, Any] = {
            "calibrated": self._calibrated,
            "rms_error": self.rms_error,
        }

        if self.camera_matrix is not None:
            data["camera_matrix"] = self.camera_matrix.tolist()
        if self.dist_coeffs is not None:
            data["dist_coeffs"] = self.dist_coeffs.ravel().tolist()
        if self.image_size is not None:
            data["image_size"] = list(self.image_size)
        if self.rotation_matrix is not None:
            data["rotation_matrix"] = self.rotation_matrix.tolist()
        if self.translation_vector is not None:
            data["translation_vector"] = self.translation_vector.ravel().tolist()

        try:
            ext = os.path.splitext(path)[1].lower()
            if ext in (".yaml", ".yml") and YAML_AVAILABLE:
                with open(path, "w") as f:
                    yaml.dump(data, f, default_flow_style=False)
            else:
                # Fallback to JSON
                with open(path, "w") as f:
                    json.dump(data, f, indent=2)
            print(f"Calibration saved to {path}")
            return True
        except Exception as e:
            print(f"Failed to save calibration: {e}")
            return False

    def load_calibration(self, path: str) -> bool:
        """Load calibration data from a YAML or JSON file.

        Args:
            path: Input file path.

        Returns:
            True if loaded successfully.
        """
        try:
            ext = os.path.splitext(path)[1].lower()
            if ext in (".yaml", ".yml") and YAML_AVAILABLE:
                with open(path, "r") as f:
                    data = yaml.safe_load(f)
            else:
                with open(path, "r") as f:
                    data = json.load(f)

            self._calibrated = data.get("calibrated", False)
            self.rms_error = data.get("rms_error", 0.0)

            if "camera_matrix" in data:
                self.camera_matrix = np.array(data["camera_matrix"])
            if "dist_coeffs" in data:
                self.dist_coeffs = np.array(data["dist_coeffs"])
            if "image_size" in data:
                self.image_size = tuple(data["image_size"])
            if "rotation_matrix" in data:
                self.rotation_matrix = np.array(data["rotation_matrix"])
            if "translation_vector" in data:
                self.translation_vector = np.array(data["translation_vector"]).reshape(3, 1)

            print(f"Calibration loaded from {path}")
            return True
        except Exception as e:
            print(f"Failed to load calibration: {e}")
            return False

    def is_calibrated(self) -> bool:
        """Check if the camera has been calibrated.

        Returns:
            True if intrinsic calibration is complete.
        """
        return self._calibrated and self.camera_matrix is not None

    def is_hand_eye_calibrated(self) -> bool:
        """Check if hand-eye calibration has been performed.

        Returns:
            True if hand-eye calibration is complete.
        """
        return self.rotation_matrix is not None and self.translation_vector is not None

    def get_focal_length(self) -> Optional[float]:
        """Get the average focal length in pixels.

        Returns:
            (fx + fy) / 2, or None if not calibrated.
        """
        if self.camera_matrix is None:
            return None
        return float((self.camera_matrix[0, 0] + self.camera_matrix[1, 1]) / 2.0)

    def get_principal_point(self) -> Optional[Tuple[float, float]]:
        """Get the principal point (cx, cy) in pixels.

        Returns:
            (cx, cy) tuple, or None if not calibrated.
        """
        if self.camera_matrix is None:
            return None
        return (float(self.camera_matrix[0, 2]), float(self.camera_matrix[1, 2]))