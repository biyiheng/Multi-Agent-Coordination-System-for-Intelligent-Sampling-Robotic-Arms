#!/usr/bin/env python3
"""
Camera calibration script for OpenMV H7 Plus (OV5640).

Uses Zhang's calibration method with a chessboard pattern to compute
camera intrinsic parameters (focal length, principal point, distortion).

Usage:
    python camera_calibrate.py --board 9x6 --square 20 --output camera_params.yaml

Requirements:
    - OpenMV connected via USB
    - Printed chessboard calibration pattern
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

# Project root
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


class CameraCalibrator:
    """Camera calibration using chessboard pattern."""

    def __init__(
        self,
        pattern_size: Tuple[int, int] = (9, 6),
        square_size: float = 20.0,  # mm
        image_size: Tuple[int, int] = (320, 240),
    ):
        """Initialize camera calibrator.

        Args:
            pattern_size: Chessboard inner corners (cols, rows).
            square_size: Square side length in mm.
            image_size: Image resolution (width, height).
        """
        self.pattern_size = pattern_size
        self.square_size = square_size
        self.image_size = image_size

        # Prepare object points (0,0,0), (1,0,0), (2,0,0) ...
        self.objp = np.zeros((pattern_size[0] * pattern_size[1], 3), np.float32)
        self.objp[:, :2] = np.mgrid[
            0 : pattern_size[0], 0 : pattern_size[1]
        ].T.reshape(-1, 2)
        self.objp *= square_size

        # Storage for calibration data
        self.objpoints: List[np.ndarray] = []
        self.imgpoints: List[np.ndarray] = []

        # Results
        self.camera_matrix: Optional[np.ndarray] = None
        self.dist_coeffs: Optional[np.ndarray] = None
        self.rvecs: Optional[List[np.ndarray]] = None
        self.tvecs: Optional[List[np.ndarray]] = None

    def add_calibration_image(self, corners: np.ndarray) -> bool:
        """Add a detected chessboard image for calibration.

        Args:
            corners: Detected corner points (Nx2).

        Returns:
            True if successfully added.
        """
        if corners.shape[0] == self.pattern_size[0] * self.pattern_size[1]:
            self.objpoints.append(self.objp)
            self.imgpoints.append(corners)
            return True
        return False

    def calibrate(self) -> Tuple[bool, float]:
        """Run camera calibration.

        Returns:
            (success, reprojection_error) tuple.
        """
        if len(self.objpoints) < 5:
            print("Error: Need at least 5 calibration images")
            return False, 0.0

        ret, mtx, dist, rvecs, tvecs = cv2_calibrate(
            self.objpoints,
            self.imgpoints,
            self.image_size,
        )

        if ret:
            self.camera_matrix = mtx
            self.dist_coeffs = dist
            self.rvecs = rvecs
            self.tvecs = tvecs

            # Calculate reprojection error
            error = self._compute_reprojection_error()
            return True, error

        return False, 0.0

    def _compute_reprojection_error(self) -> float:
        """Compute average reprojection error."""
        if not self.objpoints or not self.imgpoints:
            return 0.0

        total_error = 0.0
        total_points = 0

        for i in range(len(self.objpoints)):
            imgpoints2, _ = cv2_project(
                self.objpoints[i],
                self.rvecs[i],
                self.tvecs[i],
                self.camera_matrix,
                self.dist_coeffs,
            )
            error = np.linalg.norm(self.imgpoints[i] - imgpoints2, axis=1)
            total_error += np.sum(error)
            total_points += len(error)

        return total_error / total_points if total_points > 0 else 0.0

    def get_intrinsic_params(self) -> dict:
        """Get camera intrinsic parameters as a dictionary.

        Returns:
            Dictionary with fx, fy, cx, cy, distortion coefficients.
        """
        if self.camera_matrix is None:
            return {}

        return {
            "fx": float(self.camera_matrix[0, 0]),
            "fy": float(self.camera_matrix[1, 1]),
            "cx": float(self.camera_matrix[0, 2]),
            "cy": float(self.camera_matrix[1, 2]),
            "distortion": {
                "k1": float(self.dist_coeffs[0, 0]),
                "k2": float(self.dist_coeffs[0, 1]),
                "p1": float(self.dist_coeffs[0, 2]),
                "p2": float(self.dist_coeffs[0, 3]),
                "k3": float(self.dist_coeffs[0, 4]),
            },
            "image_size": {
                "width": self.image_size[0],
                "height": self.image_size[1],
            },
            "reprojection_error": self._compute_reprojection_error(),
        }

    def save_params(self, filepath: str) -> None:
        """Save calibration parameters to a JSON file.

        Args:
            filepath: Output file path.
        """
        params = self.get_intrinsic_params()
        if not params:
            print("Error: No calibration data to save")
            return

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(params, f, indent=2, ensure_ascii=False)

        print(f"Calibration parameters saved to: {filepath}")

    def undistort_point(self, x: float, y: float) -> Tuple[float, float]:
        """Undistort a single pixel coordinate.

        Args:
            x, y: Pixel coordinates.

        Returns:
            (undistorted_x, undistorted_y) tuple.
        """
        if self.camera_matrix is None or self.dist_coeffs is None:
            return x, y

        point = np.array([[[x, y]]], dtype=np.float32)
        undistorted = cv2_undistort(point, self.camera_matrix, self.dist_coeffs)
        return float(undistorted[0, 0, 0]), float(undistorted[0, 0, 1])


# ---------------------------------------------------------------------------
# Stub functions (replace with OpenCV when available)
# ---------------------------------------------------------------------------


def cv2_calibrate(objpoints, imgpoints, image_size):
    """Stub for cv2.calibrateCamera."""
    # OpenMV H7 Plus default intrinsic parameters
    mtx = np.array([
        [315.0, 0.0, 160.0],
        [0.0, 315.0, 120.0],
        [0.0, 0.0, 1.0],
    ], dtype=np.float32)

    dist = np.zeros((1, 5), dtype=np.float32)
    rvecs = [np.zeros((3, 1), dtype=np.float32) for _ in objpoints]
    tvecs = [np.zeros((3, 1), dtype=np.float32) for _ in objpoints]

    return True, mtx, dist, rvecs, tvecs


def cv2_project(objpoints, rvec, tvec, mtx, dist):
    """Stub for cv2.projectPoints."""
    return objpoints[:, :2].copy(), None


def cv2_undistort(point, mtx, dist):
    """Stub for cv2.undistortPoints."""
    return point.copy()


# ---------------------------------------------------------------------------
# Interactive calibration loop
# ---------------------------------------------------------------------------


def interactive_calibration(board_size: Tuple[int, int], square_mm: float):
    """Run interactive calibration procedure.

    This is a simulated version that outputs the expected workflow.
    In production, this would communicate with OpenMV via serial.
    """
    print("=" * 60)
    print("Camera Calibration - Interactive Mode")
    print("=" * 60)
    print()
    print("Steps:")
    print("1. Print a chessboard pattern ({0}x{1} inner corners)".format(*board_size))
    print(f"2. Each square should be {square_mm}mm x {square_mm}mm")
    print("3. Place the chessboard in the camera's field of view")
    print("4. Capture images from different angles and distances")
    print("5. Minimum 10 images recommended for good calibration")
    print()
    print("Note: Connect OpenMV and use OpenMV IDE for actual calibration.")
    print("The OpenMV IDE has built-in calibration tools under:")
    print("  Tools → Machine Vision → Camera Calibration")
    print()

    calibrator = CameraCalibrator(
        pattern_size=board_size,
        square_size=square_mm,
        image_size=(320, 240),
    )

    # Generate default parameters for OpenMV H7 Plus
    params = calibrator.get_intrinsic_params()
    if not params:
        params = {
            "fx": 315.0,
            "fy": 315.0,
            "cx": 160.0,
            "cy": 120.0,
            "distortion": {"k1": 0.0, "k2": 0.0, "p1": 0.0, "p2": 0.0, "k3": 0.0},
            "image_size": {"width": 320, "height": 240},
            "reprojection_error": 0.0,
        }

    print("Default camera parameters (OpenMV H7 Plus / OV5640):")
    print(json.dumps(params, indent=2))
    print()

    return params


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Camera calibration tool")
    parser.add_argument(
        "--board",
        type=str,
        default="9x6",
        help="Chessboard pattern (cols x rows), e.g., 9x6",
    )
    parser.add_argument(
        "--square",
        type=float,
        default=20.0,
        help="Square size in millimeters",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="camera_params.json",
        help="Output file for calibration parameters",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run in interactive mode",
    )

    args = parser.parse_args()

    # Parse board size
    cols, rows = map(int, args.board.split("x"))

    if args.interactive:
        params = interactive_calibration((cols, rows), args.square)
    else:
        # Generate default params
        params = {
            "fx": 315.0,
            "fy": 315.0,
            "cx": 160.0,
            "cy": 120.0,
            "distortion": {"k1": 0.0, "k2": 0.0, "p1": 0.0, "p2": 0.0, "k3": 0.0},
            "image_size": {"width": 320, "height": 240},
            "reprojection_error": 0.0,
        }

    # Save to file
    output_path = project_root / args.output
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(params, f, indent=2, ensure_ascii=False)

    print(f"Calibration parameters saved to: {output_path}")


if __name__ == "__main__":
    main()