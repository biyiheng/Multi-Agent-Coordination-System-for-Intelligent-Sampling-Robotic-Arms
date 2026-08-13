"""
Synthetic dataset generator for multi-agent robotic arm training.

Round 11: Super-massive data expansion (~300K+ total samples).
- Data cleaning: NaN/Inf removal, deduplication, outlier clipping (4-sigma)
- Data preprocessing: 3x noise augmentation, class balancing
- 15 datasets covering motion, IK, vision, safety, quality, collision, etc.

Generates realistic training data for:
- Motion: 6-DOF joint angles with IK solutions
- Vision: Object detection, AprilTag poses, quality inspection results
- Safety: Joint limit violations, collision events, velocity profiles
- Quality: Defect classifications, quality scores, acceptance decisions
- Sampling: Grid/adaptive/random sampling point distributions

Uses the DH parameters from the arm configuration to generate physically
consistent data.
"""

import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


# =============================================================================
# Real DH Parameters & Kinematic Specifications
# =============================================================================
# 基于真实工业机器人参数:
#   - UR5 (Universal Robots): 官方文档 + CSDN技术博客
#   - KUKA KR 6 R700: KUKA 官方数据手册 0000-210-361
#   - ABB IRB 120: AIMS Mathematics 2024, doi:10.3934/math.2024678
#   - 6-DOF协作机器人: SAGE Journals 2024, doi:10.1177/17298806241228372
#
# 默认使用 UR5 参数作为基准（最广泛使用的协作机器人）
# 可通过 set_robot_model() 切换到其他机器人模型

# -- UR5 DH Parameters (Universal Robots) --
# 来源: Universal Robots 官方文档
# 注意: 原始UR5参数单位为米，此处转换为毫米以匹配项目坐标系
UR5_DH_PARAMS = [
    {"a": 0.0,      "alpha": math.pi / 2,  "d": 89.159,  "theta_offset": 0.0},         # Joint 1: d=89.159mm
    {"a": -425.0,   "alpha": 0.0,          "d": 0.0,      "theta_offset": 0.0},         # Joint 2: a=425mm
    {"a": -392.25,  "alpha": 0.0,          "d": 0.0,      "theta_offset": 0.0},         # Joint 3: a=392.25mm
    {"a": 0.0,      "alpha": math.pi / 2,  "d": 109.15,   "theta_offset": 0.0},         # Joint 4: d=109.15mm
    {"a": 0.0,      "alpha": -math.pi / 2, "d": 94.65,    "theta_offset": 0.0},         # Joint 5: d=94.65mm
    {"a": 0.0,      "alpha": 0.0,          "d": 82.3,     "theta_offset": 0.0},         # Joint 6: d=82.3mm
]

# -- KUKA KR 6 R700 Modified DH Parameters --
# 来源: KUKA 官方数据手册 + GitHub Janga786/kuka-kr6-kinematics
# 注意: 原始单位为米，此处转换为毫米
KUKA_DH_PARAMS = [
    {"a": 25.0,   "alpha": -math.pi / 2, "d": 400.0, "theta_offset": 0.0},
    {"a": 455.0,  "alpha": 0.0,          "d": 0.0,   "theta_offset": -math.pi / 2},
    {"a": 35.0,   "alpha": -math.pi / 2, "d": 0.0,   "theta_offset": 0.0},
    {"a": 0.0,    "alpha": math.pi / 2,  "d": 420.0, "theta_offset": 0.0},
    {"a": 0.0,    "alpha": -math.pi / 2, "d": 0.0,   "theta_offset": 0.0},
    {"a": 0.0,    "alpha": 0.0,          "d": 80.0,  "theta_offset": 0.0},
]

# Default: use CUSTOM parameters (known to work with IK solver)
# Real UR5/KUKA parameters available via set_robot_model() for reference
DH_PARAMS = [
    {"a": 0, "alpha": 0, "d": 80, "theta_offset": 0},
    {"a": 0, "alpha": -math.pi/2, "d": 0, "theta_offset": -math.pi/2},
    {"a": 135, "alpha": 0, "d": 0, "theta_offset": 0},
    {"a": 120, "alpha": 0, "d": 0, "theta_offset": 0},
    {"a": 0, "alpha": -math.pi/2, "d": 0, "theta_offset": 0},
    {"a": 0, "alpha": 0, "d": 60, "theta_offset": 0},
]

JOINT_LIMITS = [
    (-170, 170), (-130, 130), (-150, 150),
    (-180, 180), (-120, 120), (-180, 180),
]

# UR5 real joint limits (degrees) - 来源: Universal Robots 官方文档
UR5_JOINT_LIMITS = [
    (-360, 360),   # Joint 1: ±360°
    (-360, 360),   # Joint 2: ±360°
    (-360, 360),   # Joint 3: ±360°
    (-360, 360),   # Joint 4: ±360°
    (-360, 360),   # Joint 5: ±360°
    (-360, 360),   # Joint 6: ±360° (infinite rotation)
]

# KUKA KR 6 R700 real joint limits (degrees) - 来源: KUKA 官方数据手册
KUKA_JOINT_LIMITS = [
    (-170, 170),    # A1: ±170°
    (-190, 45),     # A2: -190° to +45°
    (-120, 156),    # A3: -120° to +156°
    (-185, 185),    # A4: ±185°
    (-120, 120),    # A5: ±120°
    (-350, 350),    # A6: ±350°
]

# 默认训练工作空间对齐 RPi 运行时 orchestrator.workspace_bounds (0~500, 0~500, 0~300)
# 使 IK/运动/安全/碰撞模型训练与部署一致。
WORKSPACE_BOUNDS = {"x": (0.0, 500.0), "y": (0.0, 500.0), "z": (0.0, 300.0)}

# =============================================================================
# 相机内参 + 手眼标定 (与 rpi_control/config/settings.yaml 及 vision/calibration.py 一致)
# =============================================================================
# 本会话修复: 视觉目标坐标必须经 像素 -> 相机系(K⁻¹) -> 机器人基座系(手眼 R,t) 链路,
# 而不是把像素当 mm 直接线性外推 (原 735.5mm 误差的根源)。
CAMERA_INTRINSICS = {"fx": 320.0, "fy": 320.0, "cx": 160.0, "cy": 120.0}
HAND_EYE_ROTATION = np.array([[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]])
HAND_EYE_TRANSLATION = np.array([-100.0, -200.0, 50.0])  # mm


def pixel_to_robot(u: float, v: float, z_cam: float) -> Tuple[float, float, float]:
    """像素 + 相机深度 -> 机器人基座系 (手眼正向链路)。

    先 像素->相机系 (K⁻¹): x_cam=(u-cx)/fx*z, y_cam=(v-cy)/fy*z, z_cam=z;
    再 相机->机器人: robot = R @ cam + t。单位 mm。
    """
    fx, fy, cx, cy = (CAMERA_INTRINSICS["fx"], CAMERA_INTRINSICS["fy"],
                      CAMERA_INTRINSICS["cx"], CAMERA_INTRINSICS["cy"])
    cam = np.array([(u - cx) * z_cam / fx, (v - cy) * z_cam / fy, z_cam], dtype=float)
    return tuple(HAND_EYE_ROTATION @ cam + HAND_EYE_TRANSLATION)


def robot_to_camera(robot: Tuple[float, float, float]) -> np.ndarray:
    """机器人基座系 -> 相机系 (手眼逆向): cam = R^T (robot - t)。返回相机系坐标 (mm)。"""
    r = np.array(robot, dtype=float)
    return HAND_EYE_ROTATION.T @ (r - HAND_EYE_TRANSLATION)


def robot_to_pixel(robot: Tuple[float, float, float]) -> Optional[Tuple[float, float, float]]:
    """机器人基座系 -> 像素 (针孔反投影)。返回 (u, v, z_cam)；相机后方(z<=0)返回 None。"""
    fx, fy, cx, cy = (CAMERA_INTRINSICS["fx"], CAMERA_INTRINSICS["fy"],
                      CAMERA_INTRINSICS["cx"], CAMERA_INTRINSICS["cy"])
    cam = robot_to_camera(robot)
    z = float(cam[2])
    if z <= 1e-6:
        return None
    u = fx * cam[0] / z + cx
    v = fy * cam[1] / z + cy
    return (u, v, z)

# -- Real Servo Specs (MG996R) --
# 来源: Tower Pro 数据手册 + 实测数据
SERVO_SPECS = {
    "MG996R": {
        "pwm_range_us": (500, 2500),
        "pwm_frequency_hz": 50.0,
        "dead_band_us": (1.0, 5.0),
        "voltage_range": (4.8, 7.2),
        "torque_kgcm": {4.8: 11.0, 5.0: 12.1, 5.5: 12.9, 6.0: 13.0},
        "speed_s60": {4.8: 0.17, 5.0: 0.19, 5.5: 0.17, 6.0: 0.14},
        "rotation_range_deg": 180.0,
    },
    "SG90": {
        "pwm_range_us": (500, 2400),
        "pwm_frequency_hz": 50.0,
        "dead_band_us": (5.0, 10.0),
        "voltage_range": (3.0, 6.0),
        "torque_kgcm": {4.8: 1.8},
        "speed_s60": {4.8: 0.12},
        "rotation_range_deg": 180.0,
    },
}

# -- Real Industrial Quality Benchmarks (ISO 2859) --
# 不同行业的 AQL (Acceptable Quality Level) 标准
INDUSTRY_QUALITY_BENCHMARKS = {
    "electronics": {"aql": 1.0, "pass_rate": 0.95, "avg_defect_rate": 0.02},
    "automotive": {"aql": 1.5, "pass_rate": 0.92, "avg_defect_rate": 0.03},
    "aerospace": {"aql": 0.65, "pass_rate": 0.98, "avg_defect_rate": 0.01},
    "consumer_goods": {"aql": 2.5, "pass_rate": 0.88, "avg_defect_rate": 0.05},
    "medical": {"aql": 0.4, "pass_rate": 0.99, "avg_defect_rate": 0.005},
}

# -- Real Defect Type Distribution (NEU-DET database) --
REAL_DEFECT_TYPES = {
    "crazing": {"frequency": 0.18, "avg_area_px": 2500},
    "inclusion": {"frequency": 0.15, "avg_area_px": 800},
    "patches": {"frequency": 0.17, "avg_area_px": 5000},
    "pitted_surface": {"frequency": 0.16, "avg_area_px": 400},
    "rolled_in_scale": {"frequency": 0.17, "avg_area_px": 3500},
    "scratches": {"frequency": 0.17, "avg_area_px": 1200},
}


def set_robot_model(model: str = "UR5") -> None:
    """Switch to a different robot model's DH parameters and limits.

    Args:
        model: 'UR5', 'KUKA', or 'CUSTOM' (original synthetic params).
    """
    global DH_PARAMS, JOINT_LIMITS, WORKSPACE_BOUNDS
    if model == "KUKA":
        DH_PARAMS = KUKA_DH_PARAMS
        JOINT_LIMITS = KUKA_JOINT_LIMITS
        WORKSPACE_BOUNDS = {"x": (-706.7, 706.7), "y": (-706.7, 706.7), "z": (0.0, 706.7)}
    elif model == "CUSTOM":
        DH_PARAMS = [
            {"a": 0, "alpha": 0, "d": 80, "theta_offset": 0},
            {"a": 0, "alpha": -math.pi/2, "d": 0, "theta_offset": -math.pi/2},
            {"a": 135, "alpha": 0, "d": 0, "theta_offset": 0},
            {"a": 120, "alpha": 0, "d": 0, "theta_offset": 0},
            {"a": 0, "alpha": -math.pi/2, "d": 0, "theta_offset": 0},
            {"a": 0, "alpha": 0, "d": 60, "theta_offset": 0},
        ]
        JOINT_LIMITS = [
            (-170, 170), (-130, 130), (-150, 150),
            (-180, 180), (-120, 120), (-180, 180),
        ]
        WORKSPACE_BOUNDS = {"x": (-500.0, 500.0), "y": (-500.0, 500.0), "z": (0.0, 500.0)}
    else:  # UR5 (default)
        DH_PARAMS = UR5_DH_PARAMS
        JOINT_LIMITS = UR5_JOINT_LIMITS
        WORKSPACE_BOUNDS = {"x": (-850.0, 850.0), "y": (-850.0, 850.0), "z": (0.0, 850.0)}

# =============================================================================
# Forward Kinematics
# =============================================================================


def dh_transform(a: float, alpha: float, d: float, theta: float) -> np.ndarray:
    """Compute a single DH transformation matrix."""
    ct = math.cos(theta)
    st = math.sin(theta)
    ca = math.cos(alpha)
    sa = math.sin(alpha)

    return np.array([
        [ct, -st * ca,  st * sa, a * ct],
        [st,  ct * ca, -ct * sa, a * st],
        [0,        sa,      ca,      d],
        [0,         0,       0,      1],
    ])


def forward_kinematics(joint_angles: List[float]) -> Tuple[np.ndarray, List[np.ndarray]]:
    """Compute forward kinematics for 6-DOF arm.

    Args:
        joint_angles: 6 joint angles in radians.

    Returns:
        (end_effector_pose_4x4, list_of_transforms)
    """
    T = np.eye(4)
    transforms = [T.copy()]

    for i, angle in enumerate(joint_angles):
        params = DH_PARAMS[i]
        theta = angle + params["theta_offset"]
        Ti = dh_transform(params["a"], params["alpha"], params["d"], theta)
        T = T @ Ti
        transforms.append(T.copy())

    return T, transforms


def inverse_kinematics_analytical(
    target_pose: List[float],
    current_joints: Optional[List[float]] = None,
) -> Optional[List[float]]:
    """Analytical IK using Pieper's method for 6-DOF with spherical wrist.

    Args:
        target_pose: [x, y, z, roll, pitch, yaw] in mm and radians.
        current_joints: Current joint angles for nearest solution selection.

    Returns:
        6 joint angles in radians, or None if unreachable.
    """
    x, y, z, roll, pitch, yaw = target_pose

    # Wrist center position
    d6 = DH_PARAMS[5]["d"]
    R = rotation_matrix_from_euler(roll, pitch, yaw)
    wrist_center = np.array([x, y, z]) - d6 * R[:3, 2]

    xw, yw, zw = wrist_center

    # Joint 1
    theta1 = math.atan2(yw, xw)

    # Joint 2 and 3 - planar 2R problem
    r = math.sqrt(xw**2 + yw**2)
    h = zw - DH_PARAMS[0]["d"]
    a2 = DH_PARAMS[2]["a"]
    a3 = DH_PARAMS[3]["a"]

    D = (r**2 + h**2 - a2**2 - a3**2) / (2 * a2 * a3)
    if abs(D) > 1.0:
        return None  # Unreachable

    theta3 = math.atan2(math.sqrt(1 - D**2), D)
    alpha = math.atan2(h, r)
    beta = math.atan2(a3 * math.sin(theta3), a2 + a3 * math.cos(theta3))
    theta2 = alpha - beta - math.pi / 2

    # Joint 4, 5, 6 - spherical wrist
    T01 = dh_transform(DH_PARAMS[0]["a"], DH_PARAMS[0]["alpha"], DH_PARAMS[0]["d"], theta1 + DH_PARAMS[0]["theta_offset"])
    T12 = dh_transform(DH_PARAMS[1]["a"], DH_PARAMS[1]["alpha"], DH_PARAMS[1]["d"], theta2 + DH_PARAMS[1]["theta_offset"])
    T23 = dh_transform(DH_PARAMS[2]["a"], DH_PARAMS[2]["alpha"], DH_PARAMS[2]["d"], theta3 + DH_PARAMS[2]["theta_offset"])

    R03 = (T01 @ T12 @ T23)[:3, :3]
    R36 = R03.T @ R[:3, :3]

    theta4 = math.atan2(R36[1, 2], R36[0, 2])
    theta5 = math.atan2(math.sqrt(R36[0, 2]**2 + R36[1, 2]**2), R36[2, 2])
    theta6 = math.atan2(R36[2, 1], -R36[2, 0])

    angles = [theta1, theta2, theta3, theta4, theta5, theta6]

    # Validate joint limits
    for i, angle in enumerate(angles):
        if angle < math.radians(JOINT_LIMITS[i][0]) or angle > math.radians(JOINT_LIMITS[i][1]):
            return None

    return angles


def rotation_matrix_from_euler(roll: float, pitch: float, yaw: float) -> np.ndarray:
    """Create rotation matrix from Euler angles (ZYX)."""
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)

    return np.array([
        [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
        [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
        [-sp,     cp * sr,                cp * cr],
    ])


# =============================================================================
# Dataset Generators
# =============================================================================


@dataclass
class MotionSample:
    """A single motion training sample."""
    joint_angles: List[float]  # 6 joint angles in radians
    end_effector_pose: List[float]  # [x, y, z, roll, pitch, yaw]
    reachable: bool = True
    timestamp: float = 0.0


@dataclass
class VisionSample:
    """A single vision training sample."""
    detection_type: str  # 'color', 'apriltag', 'classify', 'inspect'
    detection_result: Dict[str, Any]
    object_position: Optional[Tuple[float, float, float]] = None
    confidence: float = 0.0
    timestamp: float = 0.0


@dataclass
class SafetySample:
    """A single safety training sample."""
    joint_positions: List[float]
    joint_velocities: List[float]
    is_safe: bool
    violation_type: Optional[str] = None
    timestamp: float = 0.0


@dataclass
class QualitySample:
    """A single quality inspection sample."""
    quality_score: float
    defects: List[Dict[str, Any]]
    decision: str  # 'accept', 'rework', 'reject'
    product_type: str = "default"
    industry: str = "electronics"  # ISO 2859 industry category
    timestamp: float = 0.0


@dataclass
class CollisionSample:
    """A single collision detection training sample."""
    joint_positions: List[float]
    obstacle_position: List[float]  # [x, y, z, radius]
    collision_detected: bool
    distance_mm: float
    timestamp: float = 0.0


class DatasetGenerator:
    """Generates synthetic training datasets for all agents."""

    def __init__(self, seed: int = 42, output_dir: str = "data/training"):
        """Initialize the dataset generator.

        Args:
            seed: Random seed for reproducibility.
            output_dir: Output directory for datasets.
        """
        self.seed = seed
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        random.seed(seed)
        np.random.seed(seed)

    # =========================================================================
    # Motion Dataset Generation
    # =========================================================================

    def generate_motion_dataset(self, num_samples: int = 15000) -> List[MotionSample]:
        """Generate motion training data (joint angles → end-effector poses).

        Uses forward kinematics to generate labeled data pairs.
        Increased from 5000 to 15000 for better model convergence.

        Args:
            num_samples: Number of samples to generate.

        Returns:
            List of MotionSample objects.
        """
        samples = []
        for _ in range(num_samples):
            # Generate random joint angles within limits
            angles = [
                random.uniform(
                    math.radians(limits[0]),
                    math.radians(limits[1]),
                )
                for limits in JOINT_LIMITS
            ]

            # Compute forward kinematics
            try:
                T, _ = forward_kinematics(angles)
                position = T[:3, 3].tolist()
                # Extract Euler angles from rotation matrix
                R = T[:3, :3]
                sy = math.sqrt(R[0, 0]**2 + R[1, 0]**2)
                if sy > 1e-6:
                    roll = math.atan2(R[2, 1], R[2, 2])
                    pitch = math.atan2(-R[2, 0], sy)
                    yaw = math.atan2(R[1, 0], R[0, 0])
                else:
                    roll = math.atan2(-R[1, 2], R[1, 1])
                    pitch = math.atan2(-R[2, 0], sy)
                    yaw = 0.0

                # Check workspace bounds
                px, py, pz = position
                reachable = (
                    WORKSPACE_BOUNDS["x"][0] <= px <= WORKSPACE_BOUNDS["x"][1]
                    and WORKSPACE_BOUNDS["y"][0] <= py <= WORKSPACE_BOUNDS["y"][1]
                    and WORKSPACE_BOUNDS["z"][0] <= pz <= WORKSPACE_BOUNDS["z"][1]
                )

                samples.append(MotionSample(
                    joint_angles=angles,
                    end_effector_pose=position + [roll, pitch, yaw],
                    reachable=reachable,
                    timestamp=time.time(),
                ))
            except Exception:
                continue

        return samples

    def generate_ik_dataset(self, num_samples: int = 10000) -> List[Dict[str, Any]]:
        """Generate inverse kinematics training data.

        Uses FK-first approach: generate valid joint angles, compute FK,
        then use resulting poses as IK targets. This guarantees all poses
        are physically reachable by the robot arm.

        Args:
            num_samples: Number of samples.

        Returns:
            List of {pose, joints, reachable} dicts.
        """
        samples = []

        for _ in range(num_samples):
            # Generate valid joint angles within limits
            angles = [
                random.uniform(
                    math.radians(limits[0]),
                    math.radians(limits[1]),
                )
                for limits in JOINT_LIMITS
            ]

            try:
                # Forward kinematics to get valid end-effector pose
                T, _ = forward_kinematics(angles)
                position = T[:3, 3].tolist()
                R = T[:3, :3]
                sy = math.sqrt(R[0, 0]**2 + R[1, 0]**2)
                if sy > 1e-6:
                    roll = math.atan2(R[2, 1], R[2, 2])
                    pitch = math.atan2(-R[2, 0], sy)
                    yaw = math.atan2(R[1, 0], R[0, 0])
                else:
                    roll = math.atan2(-R[1, 2], R[1, 1])
                    pitch = math.atan2(-R[2, 0], sy)
                    yaw = 0.0

                pose = position + [roll, pitch, yaw]

                # Solve IK for this pose (should be reachable)
                ik_joints = inverse_kinematics_analytical(pose)

                samples.append({
                    "pose": pose,
                    "joints": ik_joints if ik_joints else [],
                    "reachable": ik_joints is not None,
                    "timestamp": time.time(),
                })
            except Exception:
                continue

        return samples

    # =========================================================================
    # Vision Dataset Generation
    # =========================================================================

    def generate_vision_dataset(self, num_samples: int = 8000) -> List[VisionSample]:
        """Generate vision detection training data.

        Simulates realistic camera detection results with noise.
        Increased from 2000 to 8000 with more noise variations.

        Args:
            num_samples: Number of samples.

        Returns:
            List of VisionSample objects.
        """
        samples = []
        colors = ["red", "blue", "green", "yellow"]
        detection_types = ["detect_color", "detect_apriltag", "classify", "inspect"]

        for _ in range(num_samples):
            det_type = random.choice(detection_types)
            obj_pos = None  # 机器人基座系目标位置, detect_color 分支内赋值

            if det_type == "detect_color":
                color = random.choice(colors)
                found = random.random() > 0.1  # 90% chance of detection
                # Use Beta distribution for confidence (bounded [0,1], more realistic)
                # Beta(8, 2) gives mean ~0.8 with most values in [0.4, 0.99]
                confidence = np.random.beta(8, 2) if found else np.random.beta(2, 5)
                # 修复: 生成工作空间内目标(机器人基座系), 再经手眼/内参反投影得到像素,
                # 保证像素与机器人坐标自洽, 而非把像素当 mm 线性外推。
                # 当 found=True 时重试生成, 确保目标位于相机视场内(投影有效)。
                obj_robot = None
                proj = None
                if found:
                    for _retry in range(50):
                        _cand = (
                            random.uniform(*WORKSPACE_BOUNDS["x"]),
                            random.uniform(*WORKSPACE_BOUNDS["y"]),
                            random.uniform(0.0, 200.0),  # 相机可见高度范围内
                        )
                        _p = robot_to_pixel(_cand)
                        if _p is not None:
                            obj_robot, proj = _cand, _p
                            break
                if proj is not None:
                    cx, cy, z_cam = proj
                    det = {
                        "cx": cx, "cy": cy, "z_cam": z_cam,
                        "width": random.gauss(30, 10),
                        "height": random.gauss(30, 10),
                        "area": random.gauss(900, 300),
                        "confidence": round(float(confidence), 4),
                    }
                    obj_pos = obj_robot
                else:
                    found = False  # 视场内无有效投影, 视为未检出
                    det = {
                        "cx": 0, "cy": 0, "z_cam": 0,
                        "width": 0, "height": 0, "area": 0,
                        "confidence": round(float(confidence), 4),
                    }
                    obj_pos = None
                result = {
                    "found": found,
                    "type": "color",
                    "data": {"color": color, "detection": det},
                }

            elif det_type == "detect_apriltag":
                tag_found = random.random() > 0.2
                # Beta(10, 1.5) gives mean ~0.87 with tight distribution
                tag_conf = float(np.random.beta(10, 1.5)) if tag_found else float(np.random.beta(2, 5))
                result = {
                    "found": tag_found,
                    "type": "apriltag",
                    "data": {
                        "tags": [
                            {
                                "id": random.randint(0, 9),
                                "x": random.gauss(0, 30) if tag_found else 0,
                                "y": random.gauss(0, 30) if tag_found else 0,
                                "z": random.gauss(300, 50) if tag_found else 0,
                                "confidence": round(tag_conf, 4),
                            },
                        ] if tag_found else [],
                    },
                }

            elif det_type == "classify":
                # Beta(6, 2) gives mean ~0.75, realistic for classification
                cls_conf = float(np.random.beta(6, 2))
                result = {
                    "found": True,
                    "type": "classification",
                    "data": {
                        "category": random.choice(["block", "cylinder", "sphere", "irregular"]),
                        "confidence": round(cls_conf, 4),
                        "color": random.choice(colors),
                        "bbox": (
                            random.gauss(100, 20),
                            random.gauss(80, 20),
                            random.gauss(50, 10),
                            random.gauss(50, 10),
                        ),
                    },
                }

            else:  # inspect
                quality_score = random.gauss(75, 15)
                defects = []
                if random.random() > 0.6:
                    num_defects = random.randint(1, 3)
                    for _ in range(num_defects):
                        defects.append({
                            "type": random.choice(["scratch", "spot", "discoloration"]),
                            "severity": random.choice(["minor", "moderate", "severe"]),
                            "area": random.gauss(100, 50),
                        })
                result = {
                    "found": True,
                    "type": "quality",
                    "data": {
                        "passed": quality_score >= 70,
                        "score": round(quality_score, 1),
                        "defects": defects,
                        "dimensions": {
                            "measured_width_mm": random.gauss(30, 2),
                            "measured_height_mm": random.gauss(30, 2),
                        },
                    },
                }

            # 注意: detect_color 的 obj_pos 已在分支内经 像素->相机(K⁻¹)->机器人(手眼) 链路计算,
            # 此处无需再线性外推, 直接沿用分支内已计算的 obj_pos。

            # Extract confidence correctly for each detection type
            sample_confidence = 0.0
            data = result.get("data", {})
            if det_type == "detect_color":
                sample_confidence = data.get("detection", {}).get("confidence", 0.0)
            elif det_type == "detect_apriltag":
                tags = data.get("tags", [])
                sample_confidence = tags[0].get("confidence", 0.0) if tags else 0.0
            elif det_type == "classify":
                sample_confidence = data.get("confidence", 0.0)
            elif det_type == "inspect":
                # Quality inspection: confidence derived from score
                score = data.get("score", 0)
                sample_confidence = min(0.99, max(0.1, score / 100.0))

            samples.append(VisionSample(
                detection_type=det_type,
                detection_result=result,
                object_position=obj_pos,
                confidence=sample_confidence,
                timestamp=time.time(),
            ))

        return samples

    # =========================================================================
    # Safety Dataset Generation
    # =========================================================================

    def generate_safety_dataset(self, num_samples: int = 10000) -> List[SafetySample]:
        """Generate safety training data with labeled violations.

        Generates both safe and unsafe joint configurations.
        Increased from 3000 to 10000 with more violation types.

        Args:
            num_samples: Number of samples.

        Returns:
            List of SafetySample objects.
        """
        samples = []

        for _ in range(num_samples):
            # 70% safe, 30% unsafe samples
            is_safe = random.random() > 0.3

            if is_safe:
                # Round 6: Ultra-hard boundary-safe samples (0.1-1° from limits)
                if random.random() < 0.25:  # 25% ultra-close boundary-safe cases
                    positions = []
                    # Pick 3 joints to be close to limit (even harder)
                    boundary_joints = random.sample(range(6), 3)
                    for j, limits in enumerate(JOINT_LIMITS):
                        if j in boundary_joints:
                            # 0.1-1° from limit but still safe (extremely hard to classify)
                            if random.random() > 0.5:
                                pos = math.radians(limits[1] - random.uniform(0.1, 1.0))
                            else:
                                pos = math.radians(limits[0] + random.uniform(0.1, 1.0))
                        else:
                            pos = random.uniform(
                                math.radians(limits[0] + 10),
                                math.radians(limits[1] - 10),
                            )
                        positions.append(pos)
                    velocities = [random.gauss(0, 30) for _ in range(6)]
                else:
                    # Generate safe joint positions within limits (10° margin)
                    positions = [
                        random.uniform(
                            math.radians(limits[0] + 10),
                            math.radians(limits[1] - 10),
                        )
                        for limits in JOINT_LIMITS
                    ]
                    velocities = [random.gauss(0, 30) for _ in range(6)]
                violation_type = None
            else:
                # Generate unsafe positions
                positions = []
                violation_type = random.choice([
                    "over_limit", "over_speed", "workspace_violation",
                    "boundary_violation",  # NEW: Hard case (1-5° beyond limit)
                ])

                if violation_type == "over_limit":
                    # One joint exceeds its limit by 10-50 degrees (obvious)
                    viol_idx = random.randint(0, 5)
                    positions = [
                        random.uniform(
                            math.radians(limits[0]),
                            math.radians(limits[1]),
                        )
                        for limits in JOINT_LIMITS
                    ]
                    if random.random() > 0.5:
                        positions[viol_idx] = math.radians(
                            JOINT_LIMITS[viol_idx][1] + random.uniform(10, 50)
                        )
                    else:
                        positions[viol_idx] = math.radians(
                            JOINT_LIMITS[viol_idx][0] - random.uniform(10, 50)
                        )
                elif violation_type == "boundary_violation":
                    # NEW: Hard case - barely beyond limit (1-5°), hard to classify
                    viol_idx = random.randint(0, 5)
                    positions = [
                        random.uniform(
                            math.radians(limits[0]),
                            math.radians(limits[1]),
                        )
                        for limits in JOINT_LIMITS
                    ]
                    if random.random() > 0.5:
                        positions[viol_idx] = math.radians(
                            JOINT_LIMITS[viol_idx][1] + random.uniform(1, 5)
                        )
                    else:
                        positions[viol_idx] = math.radians(
                            JOINT_LIMITS[viol_idx][0] - random.uniform(1, 5)
                        )
                    # Also add a close-to-limit safe joint to confuse the model
                    safe_idx = (viol_idx + 1) % 6
                    lo, hi = JOINT_LIMITS[safe_idx]
                    positions[safe_idx] = math.radians(
                        hi - random.uniform(0.5, 3)  # Very close to limit but safe
                    )
                elif violation_type == "over_speed":
                    positions = [
                        random.uniform(
                            math.radians(limits[0]),
                            math.radians(limits[1]),
                        )
                        for limits in JOINT_LIMITS
                    ]
                    velocities = [random.gauss(200, 50) for _ in range(6)]
                else:
                    # Workspace violation - generate positions that go out of bounds
                    positions = [
                        math.radians(random.uniform(-180, 180))
                        for _ in range(6)
                    ]
                    velocities = [random.gauss(0, 20) for _ in range(6)]

            if not is_safe and violation_type != "over_speed":
                velocities = [random.gauss(0, 20) for _ in range(6)]

            samples.append(SafetySample(
                joint_positions=[math.degrees(p) for p in positions],
                joint_velocities=velocities,
                is_safe=is_safe,
                violation_type=violation_type,
                timestamp=time.time(),
            ))

        return samples

    # =========================================================================
    # Quality Dataset Generation
    # =========================================================================

    def generate_quality_dataset(self, num_samples: int = 15000) -> List[QualitySample]:
        """Generate quality inspection training data with real industry benchmarks.

        Uses real defect type distributions from NEU-DET database and
        ISO 2859 quality inspection standards for realistic data.

        Args:
            num_samples: Number of samples.

        Returns:
            List of QualitySample objects.
        """
        samples = []
        product_types = ["default", "precision", "coarse"]
        thresholds = {
            "default": {"pass": 75, "resample": 50, "reject": 35},
            "precision": {"pass": 88, "resample": 65, "reject": 45},
            "coarse": {"pass": 65, "resample": 40, "reject": 25},
        }

        # Real defect types from NEU-DET with frequency weights
        defect_type_names = list(REAL_DEFECT_TYPES.keys())
        defect_weights = [REAL_DEFECT_TYPES[d]["frequency"] for d in defect_type_names]

        # Industry types for benchmark tagging
        industries = list(INDUSTRY_QUALITY_BENCHMARKS.keys())

        for _ in range(num_samples):
            product_type = random.choice(product_types)
            industry = random.choice(industries)
            benchmark = INDUSTRY_QUALITY_BENCHMARKS[industry]
            thresh = thresholds[product_type]

            # Round 7: Generate defects FIRST, then compute deterministic quality score
            # This makes the defect→score relationship more learnable
            if random.random() < 0.25:
                # 25% defective samples: generate more defects
                base_defects = random.randint(3, 8)
                severity_dist = [0.2, 0.3, 0.5]  # more severe
            else:
                # 75% normal samples: fewer defects
                base_defects = random.randint(0, 3)
                severity_dist = [0.7, 0.25, 0.05]  # mostly minor
            
            # Generate defects
            defects = []
            cluster_center = (random.uniform(50, 270), random.uniform(30, 210))
            cluster_spread = random.uniform(20, 80)
            
            for _ in range(base_defects):
                defect_type = random.choices(
                    defect_type_names, weights=defect_weights, k=1
                )[0]
                
                severity = random.choices(
                    ["minor", "moderate", "severe"],
                    weights=severity_dist,
                )[0]
                
                avg_area = REAL_DEFECT_TYPES.get(
                    defect_type, {"avg_area_px": 200}
                )["avg_area_px"]
                if severity == "severe":
                    area = random.uniform(avg_area * 0.5, avg_area * 2.0)
                elif severity == "moderate":
                    area = random.uniform(avg_area * 0.2, avg_area * 0.8)
                else:
                    area = random.uniform(avg_area * 0.05, avg_area * 0.3)
                
                pos_x = random.gauss(cluster_center[0], cluster_spread)
                pos_y = random.gauss(cluster_center[1], cluster_spread)
                pos_x = max(0, min(320, pos_x))
                pos_y = max(0, min(240, pos_y))
                
                defects.append({
                    "type": defect_type,
                    "severity": severity,
                    "area": round(area, 2),
                    "position": (round(pos_x, 2), round(pos_y, 2)),
                })
            
            # Round 7: Compute deterministic quality score from defects
            severity_weights_map = {"severe": 9.0, "moderate": 4.0, "minor": 1.0}
            total_penalty = sum(
                severity_weights_map.get(d["severity"], 1.0) * math.log1p(d["area"])
                for d in defects
            )
            
            # Base score depends on product type
            base_scores = {"precision": 95.0, "default": 90.0, "coarse": 85.0}
            base_score = base_scores.get(product_type, 90.0)
            
            # Quality score = base - penalty + small noise
            quality_score = base_score - total_penalty * 0.5 + random.gauss(0, 3)
            quality_score = min(100.0, max(0.0, quality_score))
            quality_score = round(quality_score, 1)

            # Determine decision
            if quality_score >= thresh["pass"]:
                decision = "accept"
            elif quality_score >= thresh["reject"]:
                decision = "rework"
            else:
                decision = "reject"

            samples.append(QualitySample(
                quality_score=quality_score,  # Already rounded to 1 decimal above
                defects=defects,
                decision=decision,
                product_type=product_type,
                industry=industry,
                timestamp=time.time(),
            ))

        return samples

    # =========================================================================
    # Sampling Dataset Generation
    # =========================================================================

    def generate_sampling_dataset(
        self,
        num_configs: int = 500,
    ) -> List[Dict[str, Any]]:
        """Generate sampling configuration and result data.

        Creates diverse workspace configurations with sampling results.
        Increased from 100 to 500 for better coverage.

        Args:
            num_configs: Number of workspace configurations.

        Returns:
            List of sampling config + result dicts.
        """
        configs = []
        strategies = ["grid", "adaptive", "random", "stratified"]

        for _ in range(num_configs):
            # Random workspace
            wx = random.uniform(0, 100)
            wy = random.uniform(0, 100)
            ww = random.uniform(200, 400)
            wh = random.uniform(200, 400)

            bounds = {
                "x": (wx, wx + ww),
                "y": (wy, wy + wh),
                "z": (0.0, 200.0),
            }

            strategy = random.choice(strategies)

            # Generate sampling points
            if strategy == "grid":
                spacing = random.choice([30, 40, 50, 60, 80, 100])
                num_points = int((ww / spacing) * (wh / spacing))
            elif strategy == "random":
                num_points = random.randint(10, 50)
            elif strategy == "stratified":
                strata = random.randint(2, 5)
                num_points = strata * strata
            else:
                num_points = random.randint(20, 80)

            # Simulate sampling results
            coverage = min(1.0, num_points * 0.01 + random.gauss(0, 0.05))
            avg_quality = random.gauss(75, 10)
            pass_rate = min(1.0, max(0.0, random.gauss(0.85, 0.1)))

            configs.append({
                "bounds": bounds,
                "strategy": strategy,
                "num_points": num_points,
                "results": {
                    "coverage": round(coverage, 3),
                    "avg_quality": round(avg_quality, 1),
                    "pass_rate": round(pass_rate, 3),
                    "uniformity": round(random.gauss(0.7, 0.15), 3),
                },
            })

        return configs

    # =========================================================================
    # Collision Detection Dataset Generation (NEW)
    # =========================================================================

    def generate_collision_dataset(self, num_samples: int = 5000) -> List[CollisionSample]:
        """Generate collision detection training data.

        Creates scenarios with obstacles in the workspace and computes
        whether the robot arm would collide with them.

        Args:
            num_samples: Number of samples.

        Returns:
            List of CollisionSample objects.
        """
        samples = []
        for _ in range(num_samples):
            # Generate random joint positions
            angles = [
                random.uniform(math.radians(limits[0]), math.radians(limits[1]))
                for limits in JOINT_LIMITS
            ]

            # Compute end-effector position
            try:
                T, transforms = forward_kinematics(angles)
                ee_pos = T[:3, 3].tolist()
            except Exception:
                continue

            # Generate random obstacle in workspace with diverse shapes
            # Round 9: Add obstacle shape diversity (small, medium, large, irregular)
            shape_type = random.choice(["small", "medium", "large", "irregular"])
            if shape_type == "small":
                obstacle_radius = random.uniform(5, 25)
            elif shape_type == "medium":
                obstacle_radius = random.uniform(25, 55)
            elif shape_type == "large":
                obstacle_radius = random.uniform(55, 90)
            else:  # irregular
                obstacle_radius = random.uniform(10, 70)
            obstacle_pos = [
                random.uniform(WORKSPACE_BOUNDS["x"][0] + 50, WORKSPACE_BOUNDS["x"][1] - 50),
                random.uniform(WORKSPACE_BOUNDS["y"][0] + 50, WORKSPACE_BOUNDS["y"][1] - 50),
                random.uniform(20, 250),
            ]

            # Check collision at each link
            collision_detected = False
            min_distance = float("inf")

            for transform in transforms[1:]:  # Skip base frame
                link_pos = transform[:3, 3].tolist()
                dist = math.sqrt(
                    (link_pos[0] - obstacle_pos[0]) ** 2
                    + (link_pos[1] - obstacle_pos[1]) ** 2
                    + (link_pos[2] - obstacle_pos[2]) ** 2
                )
                min_distance = min(min_distance, dist)
                if dist < obstacle_radius + 30:  # 30mm link radius
                    collision_detected = True
                    break

            samples.append(CollisionSample(
                joint_positions=[math.degrees(a) for a in angles],
                obstacle_position=obstacle_pos + [obstacle_radius],
                collision_detected=collision_detected,
                distance_mm=round(min_distance, 2),
                timestamp=time.time(),
            ))

        return samples

    # =========================================================================
    # Trajectory Optimization Dataset (NEW)
    # =========================================================================

    def generate_trajectory_dataset(self, num_samples: int = 3000) -> List[Dict[str, Any]]:
        """Generate trajectory optimization training data.

        Creates start→end pose pairs with corresponding trajectory
        quality metrics for training trajectory planners.

        Args:
            num_samples: Number of samples.

        Returns:
            List of trajectory sample dicts.
        """
        samples = []
        for _ in range(num_samples):
            # Generate start pose
            start_angles = [
                random.uniform(math.radians(limits[0]), math.radians(limits[1]))
                for limits in JOINT_LIMITS
            ]
            T_start, _ = forward_kinematics(start_angles)
            start_pos = T_start[:3, 3].tolist()

            # Generate end pose (within reasonable distance)
            end_pos = [
                start_pos[0] + random.uniform(-200, 200),
                start_pos[1] + random.uniform(-200, 200),
                start_pos[2] + random.uniform(-100, 100),
            ]
            end_pos[0] = max(WORKSPACE_BOUNDS["x"][0], min(WORKSPACE_BOUNDS["x"][1], end_pos[0]))
            end_pos[1] = max(WORKSPACE_BOUNDS["y"][0], min(WORKSPACE_BOUNDS["y"][1], end_pos[1]))
            end_pos[2] = max(WORKSPACE_BOUNDS["z"][0], min(WORKSPACE_BOUNDS["z"][1], end_pos[2]))

            # Try IK for end pose
            end_pose = end_pos + [0.0, 0.0, 0.0]  # [x, y, z, roll, pitch, yaw]
            end_angles = inverse_kinematics_analytical(end_pose)

            if end_angles is None:
                continue

            # Compute trajectory metrics
            joint_distance = sum(
                (e - s) ** 2 for s, e in zip(start_angles, end_angles)
            ) ** 0.5
            cartesian_distance = math.sqrt(
                sum((e - s) ** 2 for s, e in zip(start_pos, end_pos))
            )

            # Simulated trajectory quality
            smoothness = random.gauss(0.8, 0.15)
            energy_cost = joint_distance * random.gauss(1.0, 0.2)
            execution_time = cartesian_distance / random.uniform(50, 200)

            samples.append({
                "start_angles": [math.degrees(a) for a in start_angles],
                "end_angles": [math.degrees(a) for a in end_angles],
                "start_pos": start_pos,
                "end_pos": end_pos,
                "joint_distance": round(joint_distance, 4),
                "cartesian_distance": round(cartesian_distance, 2),
                "smoothness": round(smoothness, 3),
                "energy_cost": round(energy_cost, 3),
                "execution_time": round(execution_time, 3),
                "timestamp": time.time(),
            })

        return samples

    # =========================================================================
    # Edge Case & Diverse Scenario Generators (NEW)
    # =========================================================================

    def generate_edge_case_ik(self, num_samples: int = 2000) -> List[Dict[str, Any]]:
        """Generate IK edge cases: boundary workspace, near-singularity, extreme poses.

        Args:
            num_samples: Number of edge case samples.

        Returns:
            List of edge case IK dicts.
        """
        samples = []
        edge_types = ["boundary", "near_singularity", "extreme_orientation", "full_reach"]

        for _ in range(num_samples):
            edge_type = random.choice(edge_types)

            if edge_type == "boundary":
                # Poses at workspace boundary
                x = random.choice([WORKSPACE_BOUNDS["x"][0], WORKSPACE_BOUNDS["x"][1]])
                y = random.choice([WORKSPACE_BOUNDS["y"][0], WORKSPACE_BOUNDS["y"][1]])
                z = random.choice([WORKSPACE_BOUNDS["z"][0], WORKSPACE_BOUNDS["z"][1]])
            elif edge_type == "near_singularity":
                # Near wrist singularity (pitch ≈ 0)
                x = random.uniform(100, 400)
                y = random.uniform(100, 400)
                z = random.uniform(50, 200)
                roll = random.uniform(-0.1, 0.1)
                pitch = random.uniform(-0.05, 0.05)  # Near zero pitch
                yaw = random.uniform(-math.pi, math.pi)
            elif edge_type == "extreme_orientation":
                # Extreme roll/pitch/yaw
                x = random.uniform(150, 350)
                y = random.uniform(150, 350)
                z = random.uniform(80, 200)
                roll = random.uniform(-math.pi * 0.9, math.pi * 0.9)
                pitch = random.uniform(-math.pi * 0.4, math.pi * 0.4)
                yaw = random.uniform(-math.pi * 0.9, math.pi * 0.9)
            else:  # full_reach
                x = random.uniform(350, WORKSPACE_BOUNDS["x"][1])
                y = random.uniform(350, WORKSPACE_BOUNDS["y"][1])
                z = random.uniform(200, WORKSPACE_BOUNDS["z"][1])

            if edge_type != "near_singularity" and edge_type != "extreme_orientation":
                roll = random.uniform(-math.pi, math.pi)
                pitch = random.uniform(-math.pi / 2, math.pi / 2)
                yaw = random.uniform(-math.pi, math.pi)

            pose = [x, y, z, roll, pitch, yaw]
            joints = inverse_kinematics_analytical(pose)

            samples.append({
                "pose": pose,
                "joints": joints if joints else [],
                "reachable": joints is not None,
                "edge_type": edge_type,
                "timestamp": time.time(),
            })

        return samples

    def generate_noisy_vision_dataset(self, num_samples: int = 3000) -> List[VisionSample]:
        """Generate vision data with realistic noise: motion blur, low light, partial occlusion.

        Args:
            num_samples: Number of noisy samples.

        Returns:
            List of noisy VisionSample objects.
        """
        samples = []
        noise_types = ["motion_blur", "low_light", "partial_occlusion", "glare", "normal"]
        colors = ["red", "blue", "green", "yellow"]

        for _ in range(num_samples):
            noise_type = random.choice(noise_types)
            color = random.choice(colors)
            found = random.random() > 0.15

            # Base confidence affected by noise type (Beta distribution for bounded [0,1])
            if noise_type == "motion_blur":
                confidence = float(np.random.beta(3, 3))  # mean ~0.5, wide spread
                cx_noise = random.gauss(0, 20)
                cy_noise = random.gauss(0, 15)
            elif noise_type == "low_light":
                confidence = float(np.random.beta(2, 3))  # mean ~0.4
                cx_noise = random.gauss(0, 15)
                cy_noise = random.gauss(0, 15)
            elif noise_type == "partial_occlusion":
                confidence = float(np.random.beta(3.5, 3))  # mean ~0.54
                cx_noise = random.gauss(0, 10)
                cy_noise = random.gauss(0, 10)
            elif noise_type == "glare":
                confidence = float(np.random.beta(2, 2.5))  # mean ~0.44, wide spread
                cx_noise = random.gauss(0, 30)
                cy_noise = random.gauss(0, 25)
            else:  # normal
                confidence = float(np.random.beta(8, 2))  # mean ~0.8
                cx_noise = random.gauss(0, 5)
                cy_noise = random.gauss(0, 5)

            confidence = round(confidence, 4)

            # 生成工作空间内目标并经手眼/内参反投影得到像素(含噪声),
            # 保证像素与机器人坐标自洽; found 时重试确保目标在相机视场内。
            obj_robot = None
            proj = None
            if found:
                for _retry in range(50):
                    _cand = (
                        random.uniform(*WORKSPACE_BOUNDS["x"]),
                        random.uniform(*WORKSPACE_BOUNDS["y"]),
                        random.uniform(0.0, 200.0),
                    )
                    _p = robot_to_pixel(_cand)
                    if _p is not None:
                        obj_robot, proj = _cand, _p
                        break
            if proj is not None:
                det = {
                    "cx": proj[0] + cx_noise,
                    "cy": proj[1] + cy_noise,
                    "z_cam": proj[2],
                    "width": random.gauss(30, 10),
                    "height": random.gauss(30, 10),
                    "area": random.gauss(900, 300),
                    "confidence": confidence,
                }
            else:
                found = False
                det = {
                    "cx": 0, "cy": 0, "z_cam": 0,
                    "width": 0, "height": 0, "area": 0,
                    "confidence": confidence,
                }

            result = {
                "found": found,
                "type": "color",
                "noise_type": noise_type,
                "data": {"color": color, "detection": det},
            }

            obj_pos = obj_robot if proj is not None else None

            samples.append(VisionSample(
                detection_type="detect_color",
                detection_result=result,
                object_position=obj_pos,
                confidence=confidence,
                timestamp=time.time(),
            ))

        return samples

    def generate_multi_obstacle_collision(self, num_samples: int = 3000) -> List[CollisionSample]:
        """Generate collision data with multiple obstacles (2-4 obstacles per scene).

        Args:
            num_samples: Number of samples.

        Returns:
            List of CollisionSample objects.
        """
        samples = []
        for _ in range(num_samples):
            angles = [
                random.uniform(math.radians(limits[0]), math.radians(limits[1]))
                for limits in JOINT_LIMITS
            ]

            try:
                T, transforms = forward_kinematics(angles)
            except Exception:
                continue

            # Generate 2-4 obstacles
            num_obstacles = random.randint(2, 4)
            obstacles = []
            for _ in range(num_obstacles):
                obstacles.append({
                    "pos": [
                        random.uniform(WORKSPACE_BOUNDS["x"][0] + 20, WORKSPACE_BOUNDS["x"][1] - 20),
                        random.uniform(WORKSPACE_BOUNDS["y"][0] + 20, WORKSPACE_BOUNDS["y"][1] - 20),
                        random.uniform(10, 200),
                    ],
                    "radius": random.uniform(10, 60),
                })

            # Check collision against all obstacles
            collision_detected = False
            min_distance = float("inf")
            for transform in transforms[1:]:
                link_pos = transform[:3, 3].tolist()
                for obs in obstacles:
                    dist = math.sqrt(
                        (link_pos[0] - obs["pos"][0]) ** 2
                        + (link_pos[1] - obs["pos"][1]) ** 2
                        + (link_pos[2] - obs["pos"][2]) ** 2
                    )
                    min_distance = min(min_distance, dist)
                    if dist < obs["radius"] + 30:
                        collision_detected = True
                        break
                if collision_detected:
                    break

            samples.append(CollisionSample(
                joint_positions=[math.degrees(a) for a in angles],
                obstacle_position=obstacles[0]["pos"] + [obstacles[0]["radius"]],
                collision_detected=collision_detected,
                distance_mm=round(min_distance, 2),
                timestamp=time.time(),
            ))

        return samples

    # =========================================================================
    # Sequential Motion Data Generator (NEW)
    # =========================================================================

    def generate_sequential_motion(self, num_sequences: int = 2000, seq_length: int = 10) -> List[Dict[str, Any]]:
        """Generate sequential motion data (time-series pose sequences).

        Creates smooth trajectories of consecutive poses for training
        trajectory prediction and dynamics models.

        Args:
            num_sequences: Number of motion sequences.
            seq_length: Number of poses per sequence.

        Returns:
            List of sequence dicts with timestamped poses.
        """
        sequences = []
        for seq_idx in range(num_sequences):
            # Generate start pose
            start_angles = [
                random.uniform(math.radians(limits[0] + 20), math.radians(limits[1] - 20))
                for limits in JOINT_LIMITS
            ]

            # Generate a smooth trajectory
            # Random direction with small step sizes
            direction = [
                random.uniform(-0.05, 0.05) for _ in range(6)
            ]

            frames = []
            current_angles = list(start_angles)
            for t in range(seq_length):
                try:
                    T, _ = forward_kinematics(current_angles)
                    pos = T[:3, 3].tolist()
                    R = T[:3, :3]
                    sy = math.sqrt(R[0, 0]**2 + R[1, 0]**2)
                    if sy > 1e-6:
                        roll = math.atan2(R[2, 1], R[2, 2])
                        pitch = math.atan2(-R[2, 0], sy)
                        yaw = math.atan2(R[1, 0], R[0, 0])
                    else:
                        roll = math.atan2(-R[1, 2], R[1, 1])
                        pitch = math.atan2(-R[2, 0], sy)
                        yaw = 0.0

                    # Compute velocities (difference from previous frame)
                    if t > 0:
                        velocities = [
                            current_angles[j] - prev_angles[j]
                            for j in range(6)
                        ]
                    else:
                        velocities = [0.0] * 6

                    frames.append({
                        "timestep": t,
                        "joint_angles_deg": [math.degrees(a) for a in current_angles],
                        "joint_angles_rad": [round(a, 6) for a in current_angles],
                        "end_effector_pos": [round(p, 2) for p in pos],
                        "end_effector_ori": [round(roll, 4), round(pitch, 4), round(yaw, 4)],
                        "joint_velocities": [round(v, 6) for v in velocities],
                        "timestamp": time.time(),
                    })

                    prev_angles = list(current_angles)

                    # Update angles with direction + small noise
                    for j in range(6):
                        current_angles[j] += direction[j] + random.gauss(0, 0.01)
                        # Clamp to joint limits
                        lo, hi = JOINT_LIMITS[j]
                        current_angles[j] = max(math.radians(lo), min(math.radians(hi), current_angles[j]))

                    # Slightly change direction for smoothness
                    direction = [
                        d * 0.95 + random.gauss(0, 0.005)
                        for d in direction
                    ]
                except Exception:
                    break

            if len(frames) >= 3:
                sequences.append({
                    "sequence_id": f"SEQ_{seq_idx:05d}",
                    "num_frames": len(frames),
                    "frames": frames,
                    "timestamp": time.time(),
                })

        return sequences

    def generate_velocity_profile(self, num_profiles: int = 3000) -> List[Dict[str, Any]]:
        """Generate velocity/acceleration profile data for dynamics learning.

        Creates realistic velocity profiles with acceleration, constant velocity,
        and deceleration phases for trajectory optimization.

        Args:
            num_profiles: Number of velocity profiles.

        Returns:
            List of velocity profile dicts.
        """
        profiles = []
        profile_types = ["trapezoidal", "s_curve", "constant", "variable"]

        for _ in range(num_profiles):
            profile_type = random.choice(profile_types)

            # Random joint to profile
            joint_idx = random.randint(0, 5)
            start_angle = random.uniform(math.radians(JOINT_LIMITS[joint_idx][0] + 20),
                                         math.radians(JOINT_LIMITS[joint_idx][1] - 20))
            end_angle = start_angle + random.uniform(-0.5, 0.5)
            end_angle = max(math.radians(JOINT_LIMITS[joint_idx][0]),
                           min(math.radians(JOINT_LIMITS[joint_idx][1]), end_angle))

            # Generate time points (0 to 1 normalized)
            num_points = random.randint(20, 50)
            time_points = np.linspace(0, 1, num_points)

            if profile_type == "trapezoidal":
                # Trapezoidal: accelerate → constant → decelerate
                accel_ratio = random.uniform(0.1, 0.3)
                decel_ratio = random.uniform(0.1, 0.3)
                max_vel = random.uniform(50, 300)  # deg/s

                velocities = []
                positions = []
                for t in time_points:
                    if t < accel_ratio:
                        vel = max_vel * (t / accel_ratio)
                    elif t < 1 - decel_ratio:
                        vel = max_vel
                    else:
                        vel = max_vel * ((1 - t) / decel_ratio)
                    velocities.append(vel + random.gauss(0, 5))
                    positions.append(start_angle + (end_angle - start_angle) * t)

            elif profile_type == "s_curve":
                # S-curve: smooth acceleration
                max_vel = random.uniform(50, 300)
                velocities = []
                positions = []
                for t in time_points:
                    # S-curve using sine
                    vel = max_vel * math.sin(math.pi * t) * (1 + random.gauss(0, 0.02))
                    velocities.append(vel)
                    positions.append(start_angle + (end_angle - start_angle) * t)

            elif profile_type == "constant":
                # Constant velocity
                vel = random.uniform(10, 200)
                velocities = [vel + random.gauss(0, 3) for _ in time_points]
                positions = [start_angle + (end_angle - start_angle) * t for t in time_points]

            else:  # variable
                # Variable velocity with random changes
                base_vel = random.uniform(20, 250)
                velocities = []
                positions = []
                for t in time_points:
                    vel = base_vel * (0.5 + 0.5 * math.sin(t * random.uniform(2, 6) * math.pi))
                    vel += random.gauss(0, 10)
                    velocities.append(max(0, vel))
                    positions.append(start_angle + (end_angle - start_angle) * t)

            # Compute accelerations
            accelerations = [0.0]
            for i in range(1, len(velocities)):
                dt = time_points[i] - time_points[i - 1]
                if dt > 0:
                    acc = (velocities[i] - velocities[i - 1]) / dt
                else:
                    acc = 0.0
                accelerations.append(acc)

            profiles.append({
                "profile_type": profile_type,
                "joint_index": joint_idx,
                "start_angle_deg": math.degrees(start_angle),
                "end_angle_deg": math.degrees(end_angle),
                "max_velocity_dps": round(max(velocities), 2) if velocities else 0,
                "max_acceleration_dps2": round(max(abs(a) for a in accelerations) if accelerations else 0, 2),
                "time_points": [round(t, 4) for t in time_points],
                "velocities": [round(v, 2) for v in velocities],
                "accelerations": [round(a, 2) for a in accelerations],
                "positions": [round(math.degrees(p), 2) for p in positions],
                "timestamp": time.time(),
            })

        return profiles

    def generate_multi_sensor_fusion(self, num_samples: int = 3000) -> List[Dict[str, Any]]:
        """Generate multi-sensor fusion data combining vision, kinematics, and safety.

        Creates realistic sensor fusion scenarios where:
        - Vision detects objects
        - Kinematics provides arm state
        - Safety monitors for violations
        All three streams are synchronized by timestamp.

        Args:
            num_samples: Number of fusion scenarios.

        Returns:
            List of multi-sensor fusion dicts.
        """
        colors = ["red", "blue", "green", "yellow"]
        samples = []

        for fus_idx in range(num_samples):
            # Generate arm state
            angles = [
                random.uniform(math.radians(limits[0]), math.radians(limits[1]))
                for limits in JOINT_LIMITS
            ]
            try:
                T, _ = forward_kinematics(angles)
                ee_pos = T[:3, 3].tolist()
            except Exception:
                continue

            # Generate vision detection (Beta distribution for confidence)
            color = random.choice(colors)
            obj_detected = random.random() > 0.15
            fusion_conf = float(np.random.beta(6, 2)) if obj_detected else float(np.random.beta(2, 5))
            detection = {
                "found": obj_detected,
                "color": color,
                "position_px": {
                    "cx": random.gauss(160, 40) if obj_detected else 0,
                    "cy": random.gauss(120, 30) if obj_detected else 0,
                },
                "confidence": round(fusion_conf, 4),
            }

            # Generate safety status
            positions_deg = [math.degrees(a) for a in angles]
            is_safe = True
            violation = None
            for j, pos in enumerate(positions_deg):
                lo, hi = JOINT_LIMITS[j]
                if pos < lo + 5 or pos > hi - 5:
                    is_safe = False
                    violation = "joint_limit"
                    break

            if is_safe and random.random() < 0.1:
                is_safe = False
                violation = "over_speed"

            # Sensor fusion timestamp
            fusion_time = time.time()

            samples.append({
                "fusion_id": f"FUS_{fus_idx:05d}",
                "timestamp": fusion_time,
                "kinematics": {
                    "joint_angles_deg": [round(d, 2) for d in positions_deg],
                    "end_effector_pos_mm": [round(p, 2) for p in ee_pos],
                },
                "vision": {
                    "detection": detection,
                    "camera_id": "cam_0",
                },
                "safety": {
                    "is_safe": is_safe,
                    "violation_type": violation,
                    "joint_velocities_dps": [round(random.gauss(0, 20), 2) for _ in range(6)],
                },
                "decision": {
                    "can_proceed": is_safe and obj_detected,
                    "requires_intervention": not is_safe,
                    "confidence": detection["confidence"],
                },
            })

        return samples

    def generate_workspace_diversity(self, num_configs: int = 500) -> List[Dict[str, Any]]:
        """Generate diverse workspace configurations for generalization.

        Creates varied workspace setups with different:
        - Workspace sizes (small, medium, large, extreme)
        - Obstacle placements
        - Target zone configurations
        - Multi-zone layouts

        Args:
            num_configs: Number of workspace configurations.

        Returns:
            List of workspace config dicts.
        """
        configs = []
        config_types = ["compact", "standard", "spacious", "narrow", "tall", "multi_zone"]

        for ws_idx in range(num_configs):
            config_type = random.choice(config_types)

            if config_type == "compact":
                ws = {"x": (50, 250), "y": (50, 250), "z": (0, 150)}
            elif config_type == "standard":
                ws = {"x": (0, 400), "y": (0, 400), "z": (0, 250)}
            elif config_type == "spacious":
                ws = {"x": (0, 500), "y": (0, 500), "z": (0, 300)}
            elif config_type == "narrow":
                ws = {"x": (100, 200), "y": (0, 500), "z": (0, 200)}
            elif config_type == "tall":
                ws = {"x": (0, 300), "y": (0, 300), "z": (100, 300)}
            else:  # multi_zone
                ws = {"x": (0, 500), "y": (0, 500), "z": (0, 300)}

            # Generate obstacles
            num_obstacles = random.randint(0, 4)
            obstacles = []
            for obs_i in range(num_obstacles):
                obstacles.append({
                    "position": [
                        random.uniform(ws["x"][0] + 20, ws["x"][1] - 20),
                        random.uniform(ws["y"][0] + 20, ws["y"][1] - 20),
                        random.uniform(10, ws["z"][1] - 10),
                    ],
                    "radius": random.uniform(10, 60),
                    "type": random.choice(["cylinder", "box", "sphere"]),
                })

            # Generate target zones
            num_zones = random.randint(1, 3)
            zones = []
            for zone_i in range(num_zones):
                zx = random.uniform(ws["x"][0], ws["x"][1] - 100)
                zy = random.uniform(ws["y"][0], ws["y"][1] - 100)
                zones.append({
                    "bounds": {
                        "x": (zx, zx + random.uniform(50, 150)),
                        "y": (zy, zy + random.uniform(50, 150)),
                        "z": (random.uniform(0, 50), random.uniform(100, 200)),
                    },
                    "priority": random.randint(1, 5),
                    "label": f"zone_{ws_idx}",
                })

            configs.append({
                "config_type": config_type,
                "workspace": ws,
                "obstacles": obstacles,
                "target_zones": zones,
                "num_obstacles": num_obstacles,
                "num_zones": num_zones,
                "timestamp": time.time(),
            })

        return configs

    # =========================================================================
    # Data Cleaning & Preprocessing Pipeline (Round 10)
    # =========================================================================

    def clean_dataset(self, data: List[Dict[str, Any]], dataset_name: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Clean dataset: remove NaN/Inf, deduplicate, clip outliers.

        Args:
            data: List of sample dicts.
            dataset_name: Name of dataset for reporting.

        Returns:
            (cleaned_data, cleaning_stats)
        """
        stats = {
            "original_count": len(data),
            "removed_nan": 0,
            "removed_inf": 0,
            "removed_duplicate": 0,
            "removed_outlier": 0,
            "final_count": 0,
        }

        if not data:
            return data, stats

        cleaned = []

        # Step 1: Remove NaN and Inf values
        for item in data:
            has_nan = False
            has_inf = False
            for key, val in item.items():
                if isinstance(val, bool):
                    continue  # Skip boolean values
                if isinstance(val, (int, float)):
                    if math.isnan(val):
                        has_nan = True
                    elif math.isinf(val):
                        has_inf = True
                elif isinstance(val, list):
                    for v in val:
                        if isinstance(v, bool):
                            continue
                        if isinstance(v, (int, float)):
                            if math.isnan(v):
                                has_nan = True
                            elif math.isinf(v):
                                has_inf = True
            if has_nan:
                stats["removed_nan"] += 1
                continue
            if has_inf:
                stats["removed_inf"] += 1
                continue
            cleaned.append(item)

        # Step 2: Deduplicate
        seen = set()
        deduped = []
        for item in cleaned:
            key = json.dumps(item, sort_keys=True, default=str)
            if key not in seen:
                seen.add(key)
                deduped.append(item)
            else:
                stats["removed_duplicate"] += 1
        cleaned = deduped

        # Step 3: Remove outliers (beyond 3 sigma for numerical fields)
        # Only for datasets with numerical features
        if len(cleaned) > 100:
            numeric_fields = self._get_numeric_fields(cleaned, dataset_name)
            if numeric_fields:
                for field in numeric_fields:
                    values = []
                    for item in cleaned:
                        val = self._get_nested_value(item, field)
                        if val is not None and isinstance(val, (int, float)):
                            values.append(val)
                    if len(values) > 10:
                        mean_val = np.mean(values)
                        std_val = np.std(values)
                        if std_val > 0:
                            lower = mean_val - 4 * std_val
                            upper = mean_val + 4 * std_val
                            outlier_cleaned = []
                            for item in cleaned:
                                val = self._get_nested_value(item, field)
                                if val is not None and isinstance(val, (int, float)):
                                    if val < lower or val > upper:
                                        stats["removed_outlier"] += 1
                                        continue
                                outlier_cleaned.append(item)
                            cleaned = outlier_cleaned

        stats["final_count"] = len(cleaned)
        if stats["removed_nan"] + stats["removed_inf"] + stats["removed_duplicate"] + stats["removed_outlier"] > 0:
            print(f"  [Clean] {dataset_name}: {stats['original_count']} → {stats['final_count']} "
                  f"(NaN:{stats['removed_nan']}, Inf:{stats['removed_inf']}, "
                  f"Dup:{stats['removed_duplicate']}, Outlier:{stats['removed_outlier']})")

        return cleaned, stats

    def _get_numeric_fields(self, data: List[Dict], dataset_name: str) -> List[str]:
        """Identify numeric fields for outlier detection based on dataset type."""
        if not data:
            return []
        sample = data[0]
        fields = []
        for key, val in sample.items():
            # Skip boolean values (bool is subclass of int in Python)
            if isinstance(val, bool):
                continue
            if isinstance(val, (int, float)):
                fields.append(key)
            elif isinstance(val, list) and len(val) > 0 and not isinstance(val[0], bool):
                if isinstance(val[0], (int, float)) and len(val) <= 10:
                    for i in range(len(val)):
                        fields.append(f"{key}[{i}]")
        return fields

    def _get_nested_value(self, item: Dict, field: str) -> Optional[float]:
        """Get nested value from dict using field path like 'positions[0]'."""
        if "[" in field:
            base = field[:field.index("[")]
            idx = int(field[field.index("[") + 1:field.index("]")])
            val = item.get(base, [])
            if isinstance(val, list) and idx < len(val):
                v = val[idx]
                if isinstance(v, bool):
                    return None
                return float(v) if isinstance(v, (int, float)) else None
            return None
        v = item.get(field)
        if isinstance(v, bool):
            return None
        return float(v) if isinstance(v, (int, float)) else None

    def compute_data_statistics(self, data: List[Dict], dataset_name: str) -> Dict[str, Any]:
        """Compute comprehensive data quality statistics.

        Args:
            data: List of sample dicts.
            dataset_name: Dataset name.

        Returns:
            Statistics dict with distribution info.
        """
        stats = {
            "dataset": dataset_name,
            "total_samples": len(data),
            "numeric_fields": {},
        }

        if not data:
            return stats

        # Analyze numeric fields
        numeric_fields = self._get_numeric_fields(data, dataset_name)
        for field in numeric_fields:
            values = []
            for item in data:
                val = self._get_nested_value(item, field)
                if val is not None and isinstance(val, (int, float)) and not isinstance(val, bool):
                    values.append(float(val))
            if len(values) > 1:
                stats["numeric_fields"][field] = {
                    "count": len(values),
                    "mean": float(np.mean(values)),
                    "std": float(np.std(values)),
                    "min": float(np.min(values)),
                    "max": float(np.max(values)),
                    "p25": float(np.percentile(values, 25)),
                    "p50": float(np.percentile(values, 50)),
                    "p75": float(np.percentile(values, 75)),
                }

        # Analyze categorical fields
        for key in data[0].keys():
            if key not in numeric_fields or not any("[" in f for f in numeric_fields if f.startswith(key)):
                vals = [str(item.get(key)) for item in data]
                unique = len(set(vals))
                if unique < 50:
                    stats[f"categorical_{key}"] = {"unique_values": unique}

        # Class balance for binary labels
        if "is_safe" in data[0]:
            safe_count = sum(1 for d in data if d.get("is_safe"))
            stats["class_balance"] = {
                "safe": safe_count,
                "unsafe": len(data) - safe_count,
                "safe_ratio": safe_count / len(data) if data else 0,
            }
        elif "collision_detected" in data[0]:
            collision_count = sum(1 for d in data if d.get("collision_detected"))
            stats["class_balance"] = {
                "collision": collision_count,
                "safe": len(data) - collision_count,
                "collision_ratio": collision_count / len(data) if data else 0,
            }

        return stats

    def preprocess_dataset(
        self, data: List[Dict], dataset_name: str,
        augment_noise: bool = True, augment_factor: int = 2,
    ) -> List[Dict]:
        """Preprocess dataset: normalize, augment, balance.

        Args:
            data: Cleaned dataset.
            dataset_name: Dataset name.
            augment_noise: Whether to add noise-based augmentation.
            augment_factor: Augmentation multiplier.

        Returns:
            Preprocessed dataset.
        """
        if not data:
            return data

        processed = list(data)

        # Add noise-based augmentation for robustness
        if augment_noise and len(data) > 100:
            for _ in range(augment_factor - 1):
                for item in data:
                    noisy = dict(item)
                    for key, val in item.items():
                        if isinstance(val, list) and len(val) > 0 and isinstance(val[0], (int, float)):
                            noisy[key] = [
                                v + np.random.normal(0, abs(v) * 0.01 + 0.001)
                                for v in val
                            ]
                        elif isinstance(val, float):
                            noisy[key] = val + np.random.normal(0, abs(val) * 0.01 + 0.001)
                        elif isinstance(val, int):
                            noisy[key] = val  # Keep ints as-is
                    processed.append(noisy)

        print(f"  [Preprocess] {dataset_name}: {len(data)} → {len(processed)} "
              f"(augmentation: {augment_factor}x)")

        return processed

    def save_all_datasets(self) -> Dict[str, int]:
        """Generate, clean, preprocess, and save all datasets to disk.

        Round 11: Super-massive data expansion with enhanced diversity.
        - motion: 40000 → 60000
        - ik: 25000 → 40000
        - vision: 20000 → 30000
        - safety: 25000 → 40000
        - quality: 25000 → 40000
        - sampling: 1500 → 2500
        - collision: 15000 → 25000
        - trajectory: 8000 → 12000
        - edge_ik: 6000 → 10000
        - noisy_vision: 8000 → 12000
        - multi_obstacle: 10000 → 15000
        - sequential_motion: 5000 → 8000
        - velocity_profile: 8000 → 12000
        - multi_sensor_fusion: 8000 → 12000
        - workspace_diversity: 2000 → 3000

        Returns:
            Dict with dataset name → number of samples.
        """
        counts = {}
        cleaning_report = {}
        stats_report = {}

        print("\n" + "=" * 60)
        print("  Phase 1: Data Generation (Round 11 - Super-Expanded)")
        print("=" * 60)

        # Motion dataset (increased to 60000)
        motion_data = self.generate_motion_dataset(60000)
        self._save_json("motion_dataset.json", [
            {
                "joint_angles": [math.degrees(a) for a in s.joint_angles],
                "end_effector_pose": s.end_effector_pose,
                "reachable": s.reachable,
            }
            for s in motion_data
        ])
        counts["motion"] = len(motion_data)

        # IK dataset (increased to 40000)
        ik_data = self.generate_ik_dataset(40000)
        self._save_json("ik_dataset.json", ik_data)
        counts["ik"] = len(ik_data)

        # Vision dataset (increased to 30000)
        vision_data = self.generate_vision_dataset(30000)
        self._save_json("vision_dataset.json", [
            {
                "detection_type": s.detection_type,
                "detection_result": s.detection_result,
                "object_position": s.object_position,
                "confidence": s.confidence,
            }
            for s in vision_data
        ])
        counts["vision"] = len(vision_data)

        # Safety dataset (increased to 40000)
        safety_data = self.generate_safety_dataset(40000)
        self._save_json("safety_dataset.json", [
            {
                "joint_positions": s.joint_positions,
                "joint_velocities": s.joint_velocities,
                "is_safe": s.is_safe,
                "violation_type": s.violation_type,
            }
            for s in safety_data
        ])
        counts["safety"] = len(safety_data)

        # Quality dataset (increased to 40000)
        quality_data = self.generate_quality_dataset(40000)
        self._save_json("quality_dataset.json", [
            {
                "quality_score": s.quality_score,
                "defects": s.defects,
                "decision": s.decision,
                "product_type": s.product_type,
                "industry": s.industry,
            }
            for s in quality_data
        ])
        counts["quality"] = len(quality_data)

        # Sampling dataset
        sampling_data = self.generate_sampling_dataset(2500)
        self._save_json("sampling_dataset.json", sampling_data)
        counts["sampling"] = len(sampling_data)

        # Collision dataset
        collision_data = self.generate_collision_dataset(25000)
        self._save_json("collision_dataset.json", [
            {
                "joint_positions": s.joint_positions,
                "obstacle_position": s.obstacle_position,
                "collision_detected": s.collision_detected,
                "distance_mm": s.distance_mm,
            }
            for s in collision_data
        ])
        counts["collision"] = len(collision_data)

        # Trajectory dataset
        trajectory_data = self.generate_trajectory_dataset(12000)
        self._save_json("trajectory_dataset.json", trajectory_data)
        counts["trajectory"] = len(trajectory_data)

        # Edge case IK dataset
        edge_ik_data = self.generate_edge_case_ik(10000)
        self._save_json("edge_case_ik.json", edge_ik_data)
        counts["edge_ik"] = len(edge_ik_data)

        # Noisy vision dataset
        noisy_vision_data = self.generate_noisy_vision_dataset(12000)
        self._save_json("noisy_vision_dataset.json", [
            {
                "detection_type": s.detection_type,
                "detection_result": s.detection_result,
                "object_position": s.object_position,
                "confidence": s.confidence,
            }
            for s in noisy_vision_data
        ])
        counts["noisy_vision"] = len(noisy_vision_data)

        # Multi-obstacle collision dataset
        multi_collision_data = self.generate_multi_obstacle_collision(15000)
        self._save_json("multi_obstacle_collision.json", [
            {
                "joint_positions": s.joint_positions,
                "obstacle_position": s.obstacle_position,
                "collision_detected": s.collision_detected,
                "distance_mm": s.distance_mm,
            }
            for s in multi_collision_data
        ])
        counts["multi_obstacle"] = len(multi_collision_data)

        # Sequential motion dataset
        seq_motion_data = self.generate_sequential_motion(8000, seq_length=10)
        self._save_json("sequential_motion.json", seq_motion_data)
        counts["sequential_motion"] = len(seq_motion_data)

        # Velocity profile dataset
        vel_profile_data = self.generate_velocity_profile(12000)
        self._save_json("velocity_profile.json", vel_profile_data)
        counts["velocity_profile"] = len(vel_profile_data)

        # Multi-sensor fusion dataset
        fusion_data = self.generate_multi_sensor_fusion(12000)
        self._save_json("multi_sensor_fusion.json", fusion_data)
        counts["multi_sensor_fusion"] = len(fusion_data)

        # Workspace diversity dataset
        workspace_data = self.generate_workspace_diversity(3000)
        self._save_json("workspace_diversity.json", workspace_data)
        counts["workspace_diversity"] = len(workspace_data)

        # =========================================================================
        # Phase 2: Data Cleaning & Quality Statistics
        # =========================================================================
        print("\n" + "=" * 60)
        print("  Phase 2: Data Cleaning & Quality Statistics (Round 11)")
        print("=" * 60)

        # Clean and compute stats for core training datasets
        # Load saved JSON data back for cleaning (raw data may be dataclass objects)
        core_datasets = [
            ("ik", "ik_dataset.json"),
            ("safety", "safety_dataset.json"),
            ("quality", "quality_dataset.json"),
            ("collision", "collision_dataset.json"),
            ("multi_obstacle", "multi_obstacle_collision.json"),
        ]

        for name, filename in core_datasets:
            raw_data = self._load_json(filename)
            if not raw_data:
                print(f"  [Skip] {name}: no data found")
                continue

            # Clean
            cleaned, clean_stats = self.clean_dataset(raw_data, name)
            cleaning_report[name] = clean_stats

            # Compute statistics
            stats = self.compute_data_statistics(cleaned, name)
            stats_report[name] = stats

            # Print key stats
            if "class_balance" in stats:
                cb = stats["class_balance"]
                print(f"  [Stats] {name}: {stats['total_samples']} samples, class_balance={cb}")

            # Re-save cleaned data
            self._save_json(filename, cleaned)
            counts[name] = len(cleaned)

        # Save cleaning report
        report_path = self.output_dir / "data_quality_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump({
                "cleaning_report": cleaning_report,
                "statistics_report": stats_report,
                "total_datasets": len(counts),
                "total_samples": sum(counts.values()),
            }, f, indent=2, ensure_ascii=False)
        print(f"\n  Data quality report saved to: {report_path}")

        # =========================================================================
        # Phase 3: Data Preprocessing (Augmentation)
        # =========================================================================
        print("\n" + "=" * 60)
        print("  Phase 3: Data Preprocessing (Noise Augmentation 3x - Round 11)")
        print("=" * 60)

        # Apply preprocessing to core datasets
        for name, filename in core_datasets:
            loaded = self._load_json(filename)
            if loaded:
                processed = self.preprocess_dataset(loaded, name, augment_factor=3)
                counts[name] = len(processed)
                self._save_json(filename, processed)

        return counts

    def _load_json(self, filename: str) -> List[Dict]:
        """Load dataset from JSON file."""
        filepath = self.output_dir / filename
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def _save_json(self, filename: str, data: Any) -> None:
        """Save data to a JSON file with deduplication."""
        filepath = self.output_dir / filename
        # Deduplicate if data is a list of dicts
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            seen = set()
            deduped = []
            dup_count = 0
            for item in data:
                key = json.dumps(item, sort_keys=True, default=str)
                if key not in seen:
                    seen.add(key)
                    deduped.append(item)
                else:
                    dup_count += 1
            if dup_count > 0:
                print(f"  Removed {dup_count} duplicate samples from {filename}")
            data = deduped
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  Saved {len(data)} samples to {filepath}")


# =============================================================================
# Main
# =============================================================================


if __name__ == "__main__":
    print("=" * 60)
    print("Generating Training Datasets")
    print("=" * 60)

    generator = DatasetGenerator(seed=42)
    counts = generator.save_all_datasets()

    print("\n" + "=" * 60)
    print("Dataset Generation Complete")
    print("=" * 60)
    total = sum(counts.values())
    for name, count in counts.items():
        print(f"  {name}: {count} samples")
    print(f"  Total: {total} samples")