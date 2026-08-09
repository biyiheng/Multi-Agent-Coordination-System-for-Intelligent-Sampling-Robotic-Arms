#!/usr/bin/env python3
"""
Hand-eye calibration script.

Solves the AX = XB hand-eye calibration problem to determine the
transformation between the camera and the robot end-effector.

Usage:
    python hand_eye_calibrate.py --poses poses.json --output hand_eye.yaml

Input format (poses.json):
    [
        {
            "robot_pose": [x, y, z, roll, pitch, yaw],
            "camera_pose": [x, y, z, roll, pitch, yaw]
        },
        ...
    ]
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Tuple

import numpy as np

# Project root
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def pose_to_transform(pose: List[float]) -> np.ndarray:
    """Convert a 6-DOF pose [x, y, z, roll, pitch, yaw] to a 4x4 transform.

    Args:
        pose: [x, y, z, roll, pitch, yaw] in mm and radians.

    Returns:
        4x4 homogeneous transformation matrix.
    """
    x, y, z, roll, pitch, yaw = pose

    # Rotation matrices
    Rx = np.array([
        [1, 0, 0],
        [0, np.cos(roll), -np.sin(roll)],
        [0, np.sin(roll), np.cos(roll)],
    ])

    Ry = np.array([
        [np.cos(pitch), 0, np.sin(pitch)],
        [0, 1, 0],
        [-np.sin(pitch), 0, np.cos(pitch)],
    ])

    Rz = np.array([
        [np.cos(yaw), -np.sin(yaw), 0],
        [np.sin(yaw), np.cos(yaw), 0],
        [0, 0, 1],
    ])

    R = Rz @ Ry @ Rx

    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = [x, y, z]

    return T


def solve_hand_eye_tsai(
    A_list: List[np.ndarray], B_list: List[np.ndarray]
) -> np.ndarray:
    """Solve hand-eye calibration using Tsai's method.

    Solves AX = XB where:
    - A: Robot end-effector motion between poses
    - B: Camera motion between poses
    - X: Unknown hand-eye transformation (camera to end-effector)

    Args:
        A_list: List of robot motion transforms (4x4).
        B_list: List of camera motion transforms (4x4).

    Returns:
        Hand-eye transformation X (4x4).
    """
    n = len(A_list)
    if n < 3:
        raise ValueError("Need at least 3 pose pairs for hand-eye calibration")

    # Extract rotation and translation from relative motions
    P = np.zeros((3 * n, 3))
    Q = np.zeros((3 * n, 1))

    for i in range(n):
        # Extract rotation axes from A and B
        Ra = A_list[i][:3, :3]
        Rb = B_list[i][:3, :3]

        # Rodrigues: rotation vector from rotation matrix
        theta_a = np.arccos(np.clip((np.trace(Ra) - 1) / 2, -1, 1))
        theta_b = np.arccos(np.clip((np.trace(Rb) - 1) / 2, -1, 1))

        if abs(theta_a) < 1e-6 or abs(theta_b) < 1e-6:
            continue

        ra = (theta_a / (2 * np.sin(theta_a))) * np.array([
            Ra[2, 1] - Ra[1, 2],
            Ra[0, 2] - Ra[2, 0],
            Ra[1, 0] - Ra[0, 1],
        ])

        rb = (theta_b / (2 * np.sin(theta_b))) * np.array([
            Rb[2, 1] - Rb[1, 2],
            Rb[0, 2] - Rb[2, 0],
            Rb[1, 0] - Rb[0, 1],
        ])

        # Skew-symmetric matrix from ra + rb
        skew = np.array([
            [0, -(ra[2] + rb[2]), ra[1] + rb[1]],
            [ra[2] + rb[2], 0, -(ra[0] + rb[0])],
            [-(ra[1] + rb[1]), ra[0] + rb[0], 0],
        ])

        P[3 * i : 3 * i + 3, :] = skew
        Q[3 * i : 3 * i + 3, 0] = ra - rb

    # Solve for rotation: P * pR = Q
    try:
        pR, _, _, _ = np.linalg.lstsq(P, Q, rcond=None)
    except np.linalg.LinAlgError:
        pR = np.zeros((3, 1))

    # Convert rotation vector to rotation matrix
    theta = np.linalg.norm(pR)
    if theta < 1e-6:
        Rx = np.eye(3)
    else:
        k = pR.flatten() / theta
        K = np.array([
            [0, -k[2], k[1]],
            [k[2], 0, -k[0]],
            [-k[1], k[0], 0],
        ])
        Rx = np.eye(3) + np.sin(theta) * K + (1 - np.cos(theta)) * (K @ K)

    # Solve for translation
    P_t = np.zeros((3 * n, 3))
    Q_t = np.zeros((3 * n, 1))

    for i in range(n):
        Ra = A_list[i][:3, :3]
        ta = A_list[i][:3, 3]
        tb = B_list[i][:3, 3]

        P_t[3 * i : 3 * i + 3, :] = Ra - np.eye(3)
        Q_t[3 * i : 3 * i + 3, 0] = Rx @ tb - ta

    try:
        pt, _, _, _ = np.linalg.lstsq(P_t, Q_t, rcond=None)
    except np.linalg.LinAlgError:
        pt = np.zeros((3, 1))

    # Build final transformation
    X = np.eye(4)
    X[:3, :3] = Rx
    X[:3, 3] = pt.flatten()

    return X


def compute_relative_motion(poses: List[np.ndarray]) -> List[np.ndarray]:
    """Compute relative motions between consecutive poses.

    Args:
        poses: List of absolute poses (4x4 transforms).

    Returns:
        List of relative motions (4x4 transforms).
    """
    motions = []
    for i in range(1, len(poses)):
        # A_i = inv(T_{i-1}) * T_i
        motion = np.linalg.inv(poses[i - 1]) @ poses[i]
        motions.append(motion)
    return motions


def calibrate_hand_eye(
    robot_poses: List[List[float]],
    camera_poses: List[List[float]],
) -> dict:
    """Perform hand-eye calibration.

    Args:
        robot_poses: List of robot end-effector poses [x, y, z, r, p, y].
        camera_poses: List of camera-to-target poses [x, y, z, r, p, y].

    Returns:
        Calibration result dictionary with transformation matrix and errors.
    """
    if len(robot_poses) != len(camera_poses):
        raise ValueError("Number of robot and camera poses must match")

    if len(robot_poses) < 3:
        raise ValueError("Need at least 3 pose pairs")

    # Convert all poses to transforms
    T_robot = [pose_to_transform(p) for p in robot_poses]
    T_camera = [pose_to_transform(p) for p in camera_poses]

    # Compute relative motions
    A = compute_relative_motion(T_robot)  # Robot motion
    B = compute_relative_motion(T_camera)  # Camera motion

    # Solve AX = XB
    X = solve_hand_eye_tsai(A, B)

    # Extract rotation and translation
    R = X[:3, :3]
    t = X[:3, 3]

    # Compute roll, pitch, yaw from rotation matrix
    sy = np.sqrt(R[0, 0] ** 2 + R[1, 0] ** 2)
    if sy > 1e-6:
        roll = np.arctan2(R[2, 1], R[2, 2])
        pitch = np.arctan2(-R[2, 0], sy)
        yaw = np.arctan2(R[1, 0], R[0, 0])
    else:
        roll = np.arctan2(-R[1, 2], R[1, 1])
        pitch = np.arctan2(-R[2, 0], sy)
        yaw = 0.0

    # Compute residual error
    errors = []
    for i in range(len(A)):
        error = np.linalg.norm(A[i] @ X - X @ B[i])
        errors.append(float(error))

    result = {
        "transformation": {
            "x": float(t[0]),
            "y": float(t[1]),
            "z": float(t[2]),
            "roll": float(roll),
            "pitch": float(pitch),
            "yaw": float(yaw),
        },
        "rotation_matrix": R.tolist(),
        "translation": t.tolist(),
        "matrix_4x4": X.tolist(),
        "residual_errors": errors,
        "mean_error": float(np.mean(errors)),
        "max_error": float(np.max(errors)),
        "num_pose_pairs": len(A),
    }

    return result


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Hand-eye calibration tool")
    parser.add_argument(
        "--poses",
        type=str,
        required=True,
        help="JSON file with robot and camera pose pairs",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="hand_eye_result.json",
        help="Output file for calibration results",
    )

    args = parser.parse_args()

    # Load pose data
    with open(args.poses, "r", encoding="utf-8") as f:
        data = json.load(f)

    robot_poses = [entry["robot_pose"] for entry in data]
    camera_poses = [entry["camera_pose"] for entry in data]

    print("=" * 60)
    print("Hand-Eye Calibration (AX = XB)")
    print("=" * 60)
    print(f"Number of pose pairs: {len(robot_poses)}")
    print()

    try:
        result = calibrate_hand_eye(robot_poses, camera_poses)

        print("Calibration Result:")
        print(f"  Translation: x={result['transformation']['x']:.3f}mm, "
              f"y={result['transformation']['y']:.3f}mm, "
              f"z={result['transformation']['z']:.3f}mm")
        print(f"  Rotation:    roll={np.degrees(result['transformation']['roll']):.2f}°, "
              f"pitch={np.degrees(result['transformation']['pitch']):.2f}°, "
              f"yaw={np.degrees(result['transformation']['yaw']):.2f}°")
        print(f"  Mean Error:  {result['mean_error']:.4f}")
        print(f"  Max Error:   {result['max_error']:.4f}")
        print()

        # Save results
        output_path = project_root / args.output
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"Results saved to: {output_path}")
        print("=" * 60)

    except Exception as e:
        print(f"Calibration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()