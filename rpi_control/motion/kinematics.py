"""
Kinematics module for the 6-DOF intelligent sampling robotic arm.

Implements forward and inverse kinematics using the Denavit-Hartenberg (DH)
parameter convention, along with Jacobian computation and PWM/angle conversion
utilities. The inverse kinematics uses Pieper's method for the 6-DOF arm
with a spherical wrist.

All angles are in radians unless noted otherwise.
All lengths are in millimeters.
"""

import math
from typing import List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger
from ..utils.error_handler import KinematicsError

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NUM_JOINTS = 6
DEG_TO_RAD = math.pi / 180.0
RAD_TO_DEG = 180.0 / math.pi

# 数值 IK 单步最大关节增量 (rad)，防止一步撞上关节限位后振荡
MAX_IK_STEP = 0.3

# PWM range constants
PWM_MIN = 500
PWM_MAX = 2500
PWM_RANGE = PWM_MAX - PWM_MIN
ANGLE_RANGE_DEG = 180.0  # Typical servo angle range
ANGLE_RANGE_RAD = ANGLE_RANGE_DEG * DEG_TO_RAD

# Default DH parameters [a, alpha, d, theta_offset] (mm, degrees, mm, degrees)
DEFAULT_DH_PARAMS: List[Tuple[float, float, float, float]] = [
    (0, 90, 85, 0),      # Joint 0: Base rotation
    (120, 0, 0, -90),     # Joint 1: Shoulder
    (110, 0, 0, 0),       # Joint 2: Elbow
    (0, 90, 0, 0),        # Joint 3: Wrist pitch
    (0, -90, 95, 0),      # Joint 4: Wrist roll
    (0, 0, 65, 0),        # Joint 5: Gripper
]

# Default joint limits in radians
DEFAULT_JOINT_LIMITS: List[Tuple[float, float]] = [
    (-math.pi / 2, math.pi / 2),      # Joint 0
    (-math.pi / 2, math.pi / 2),      # Joint 1
    (-math.pi / 2, math.pi / 2),      # Joint 2
    (-math.pi / 2, math.pi / 2),      # Joint 3
    (-math.pi / 2, math.pi / 2),      # Joint 4
    (-math.pi / 4, math.pi / 4),      # Joint 5 (Gripper)
]


# ---------------------------------------------------------------------------
# DH Parameter Class
# ---------------------------------------------------------------------------


class DHParameter:
    """
    Represents a single Denavit-Hartenberg parameter set for one joint.

    Attributes:
        a: Link length along x_i-1 axis (mm).
        alpha: Link twist about x_i-1 axis (radians).
        d: Link offset along z_i axis (mm).
        theta: Joint angle about z_i axis (radians). This is the variable
               for revolute joints; the offset is subtracted in the
               transformation.
    """

    def __init__(
        self,
        a: float,
        alpha: float,
        d: float,
        theta_offset: float = 0.0,
    ) -> None:
        """
        Initialize a DH parameter set.

        Args:
            a: Link length (mm).
            alpha: Link twist (degrees, will be converted to radians).
            d: Link offset (mm).
            theta_offset: Joint angle offset (degrees, will be converted to radians).
        """
        self.a: float = a
        self.alpha: float = alpha * DEG_TO_RAD
        self.d: float = d
        self.theta_offset: float = theta_offset * DEG_TO_RAD

    def __repr__(self) -> str:
        return (
            f"DHParameter(a={self.a:.1f}, alpha={self.alpha * RAD_TO_DEG:.1f}°, "
            f"d={self.d:.1f}, theta_offset={self.theta_offset * RAD_TO_DEG:.1f}°)"
        )


# ---------------------------------------------------------------------------
# Transformation Matrix
# ---------------------------------------------------------------------------


def transformation_matrix(dh: DHParameter, theta: float) -> np.ndarray:
    """
    Compute the 4x4 homogeneous transformation matrix for a DH parameter set.

    The standard DH convention is used:
        T = Rot_z(theta) * Trans_z(d) * Trans_x(a) * Rot_x(alpha)

    Args:
        dh: DHParameter for this joint.
        theta: Current joint angle in radians (variable).

    Returns:
        4x4 homogeneous transformation matrix as a numpy array.
    """
    # 有效关节角度 = 当前角度 + DH 参数中的角度偏移
    effective_theta = theta + dh.theta_offset

    # 预计算三角函数值，避免重复调用
    ct = math.cos(effective_theta)  # cos(θ)
    st = math.sin(effective_theta)  # sin(θ)
    ca = math.cos(dh.alpha)         # cos(α)
    sa = math.sin(dh.alpha)         # sin(α)

    # 标准 DH 变换矩阵：T = Rot_z(θ) · Trans_z(d) · Trans_x(a) · Rot_x(α)
    # 矩阵各列含义：
    #   列 0: X 轴方向（旋转矩阵第一列）
    #   列 1: Y 轴方向（旋转矩阵第二列）
    #   列 2: Z 轴方向（旋转矩阵第三列）
    #   列 3: 位置向量（平移分量）
    return np.array([
        [ct, -st * ca,  st * sa, dh.a * ct],   # 第 1 行: X 分量
        [st,  ct * ca, -ct * sa, dh.a * st],   # 第 2 行: Y 分量
        [0,   sa,       ca,      dh.d],        # 第 3 行: Z 分量
        [0,   0,        0,       1],           # 第 4 行: 齐次坐标
    ], dtype=np.float64)


# ---------------------------------------------------------------------------
# Forward Kinematics
# ---------------------------------------------------------------------------


def forward_kinematics(
    joint_angles: List[float],
    dh_params: Optional[List[DHParameter]] = None,
) -> Tuple[np.ndarray, List[np.ndarray]]:
    """
    Compute the end-effector pose from joint angles using forward kinematics.

    Args:
        joint_angles: List of 6 joint angles in radians.
        dh_params: Optional list of DHParameter objects. Uses defaults if None.

    Returns:
        Tuple of (end_effector_transform, joint_transforms) where:
            - end_effector_transform: 4x4 pose matrix of the end-effector.
            - joint_transforms: List of intermediate 4x4 transform matrices.

    Raises:
        KinematicsError: If the number of joint angles is incorrect.
    """
    # 验证关节角度数量必须为 6 个
    if len(joint_angles) != NUM_JOINTS:
        raise KinematicsError(
            f"Expected {NUM_JOINTS} joint angles, got {len(joint_angles)}",
            code="IK_INVALID_JOINTS",
        )

    # 使用默认 DH 参数（如果未提供）
    if dh_params is None:
        dh_params = _get_default_dh_params()

    # 从基座开始，逐关节链式相乘变换矩阵
    T = np.eye(4, dtype=np.float64)           # 初始化为单位矩阵
    joint_transforms: List[np.ndarray] = []   # 存储每个关节的累积变换

    for i, (theta, dh) in enumerate(zip(joint_angles, dh_params)):
        T_i = transformation_matrix(dh, theta)  # 关节 i 的局部变换
        T = T @ T_i                             # 累积到末端
        joint_transforms.append(T.copy())       # 保存中间结果（用于雅可比等）

    # T 为末端执行器位姿，transforms 为各关节的位姿
    return T, joint_transforms


def get_end_effector_pose(joint_angles: List[float]) -> np.ndarray:
    """
    Get the end-effector position and orientation as a 6-element vector.

    Args:
        joint_angles: List of 6 joint angles in radians.

    Returns:
        Numpy array [x, y, z, roll, pitch, yaw] in mm and radians.
    """
    T, _ = forward_kinematics(joint_angles)

    # 提取末端位置（齐次变换矩阵的第 4 列前 3 行）
    x, y, z = T[0, 3], T[1, 3], T[2, 3]

    # 从旋转矩阵中提取 ZYX 欧拉角
    # R = T[:3, :3] 是末端执行器的 3x3 旋转矩阵
    R = T[:3, :3]
    # sy = sqrt(r00² + r10²) — 用于判断是否接近奇异姿态（万向节锁）
    sy = math.sqrt(R[0, 0] ** 2 + R[1, 0] ** 2)

    if sy > 1e-6:
        # 非奇异情况：使用标准欧拉角提取公式
        roll = math.atan2(R[2, 1], R[2, 2])   # 绕 X 轴旋转
        pitch = math.atan2(-R[2, 0], sy)       # 绕 Y 轴旋转
        yaw = math.atan2(R[1, 0], R[0, 0])     # 绕 Z 轴旋转
    else:
        # 奇异情况 (pitch ≈ ±90°)：万向节锁，roll 和 yaw 耦合
        # 此时 R[2,0] ≈ ±1, R[0,0] ≈ R[1,0] ≈ 0
        roll = math.atan2(-R[1, 2], R[1, 1])   # 使用替代公式
        pitch = math.atan2(-R[2, 0], sy)        # 保持一致性
        yaw = 0.0                               # 设为 0（自由度丢失）

    return np.array([x, y, z, roll, pitch, yaw], dtype=np.float64)


# ---------------------------------------------------------------------------
# Inverse Kinematics (Pieper's Method)
# ---------------------------------------------------------------------------


def inverse_kinematics(
    target_pose: np.ndarray,
    current_joints: Optional[List[float]] = None,
    dh_params: Optional[List[DHParameter]] = None,
    joint_limits: Optional[List[Tuple[float, float]]] = None,
) -> List[List[float]]:
    """
    Compute inverse kinematics solutions using Pieper's method for a 6-DOF
    arm with a spherical wrist.

    The algorithm decouples the inverse kinematics into:
    1. Solve for wrist center position (first 3 joints).
    2. Solve for wrist orientation (last 3 joints).

    Args:
        target_pose: 6-element array [x, y, z, roll, pitch, yaw] in mm and radians.
        current_joints: Current joint configuration for choosing the closest solution.
        dh_params: Optional list of DHParameter objects.
        joint_limits: Optional list of (min, max) angle limits in radians.

    Returns:
        List of valid joint angle solutions (each a list of 6 floats in radians),
        sorted by proximity to current_joints if provided.

    Raises:
        KinematicsError: If no valid solution is found.
    """
    if dh_params is None:
        dh_params = _get_default_dh_params()

    if joint_limits is None:
        joint_limits = DEFAULT_JOINT_LIMITS

    target = np.asarray(target_pose, dtype=np.float64)
    p_tgt = target[:3]
    R_tgt = _euler_to_rotation_matrix(target[3], target[4], target[5])

    # 数值 IK：从多个初始种子求解（每个种子代表一种臂形/腕姿），
    # 再由 FK 回环校验剔除假解。相比旧的解析 Pieper 法，数值法基于真实
    # DH 链式的 forward_kinematics / jacobian，自动计入 theta_offset 与
    # alpha 扭转，因此不受肩部旋转偏置影响。
    seeds: List[List[float]] = []
    if current_joints is not None and len(current_joints) == NUM_JOINTS:
        seeds.append(list(current_joints))
    # 多样初始种子：覆盖不同基座转向、肘部上/下、腕部翻转
    seeds.append([0.0] * NUM_JOINTS)
    seeds.append([math.pi, 0.0, 0.0, 0.0, 0.0, 0.0])
    seeds.append([0.0, 0.6, 0.6, 0.0, 0.0, 0.0])
    seeds.append([0.0, -0.6, -0.6, 0.0, 0.0, 0.0])
    seeds.append([math.pi, 0.6, 0.6, 0.0, 0.0, 0.0])
    seeds.append([math.pi, -0.6, -0.6, 0.0, 0.0, 0.0])
    seeds.append([0.0, 0.6, 0.6, math.pi, 0.0, 0.0])
    seeds.append([0.0, -0.6, -0.6, math.pi, 0.0, 0.0])
    # 随机重启种子：逃离关节限位造成的局部极小
    rng = np.random.default_rng(7)
    for _ in range(24):
        seeds.append([
            rng.uniform(joint_limits[i][0] * 0.7, joint_limits[i][1] * 0.7)
            for i in range(NUM_JOINTS)
        ])

    candidates: List[List[float]] = []
    seen = set()
    for seed in seeds:
        sol = _solve_numerical_ik(p_tgt, R_tgt, seed, dh_params, joint_limits)
        if sol is None:
            continue
        key = tuple(round(a, 6) for a in sol)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(sol)

    # FK 回环校验 + 限位过滤（仅保留真实到达目标的解）
    valid_solutions: List[List[float]] = []
    for sol in candidates:
        if not _validate_joint_limits(sol, joint_limits):
            continue
        T_check, _ = forward_kinematics(sol, dh_params)
        pos_err = float(np.linalg.norm(T_check[:3, 3] - p_tgt))
        ang_err = _rot_error_angle(T_check[:3, :3], R_tgt)
        if pos_err <= 1.0 and ang_err <= math.radians(1.0):
            valid_solutions.append(sol)

    if not valid_solutions:
        raise KinematicsError(
            f"No valid IK solution for target pose [{p_tgt[0]:.1f}, {p_tgt[1]:.1f}, {p_tgt[2]:.1f}]",
            code="IK_NO_SOLUTION",
        )

    # 如果提供了当前关节配置，按欧氏距离排序，选择最近解
    if current_joints is not None and len(current_joints) == NUM_JOINTS:
        valid_solutions.sort(
            key=lambda sol: _joint_distance(sol, current_joints)
        )

    logger.debug(f"Found {len(valid_solutions)} valid IK solution(s)")
    return valid_solutions


def _solve_numerical_ik(
    p_tgt: np.ndarray,
    R_tgt: np.ndarray,
    seed: List[float],
    dh_params: List[DHParameter],
    joint_limits: List[Tuple[float, float]],
    max_iter: int = 300,
    tol_pos: float = 0.5,
    tol_ang: float = math.radians(0.5),
) -> Optional[List[float]]:
    """基于真实 FK 的阻尼最小二乘（DLS）数值 IK.

    利用 forward_kinematics 与 jacobian（均基于真实 DH 链式），自动计入
    theta_offset / alpha 扭转；用自适应阻尼 λ 处理奇异位形。

    Returns:
        满足位置/姿态容差的关节角列表，或 None（不可达/未收敛）。
    """
    lows = np.array([l[0] for l in joint_limits], dtype=np.float64)
    highs = np.array([l[1] for l in joint_limits], dtype=np.float64)
    q = np.clip(np.asarray(seed, dtype=np.float64), lows, highs)

    lam = 1e-3
    prev_cost: Optional[float] = None

    for _ in range(max_iter):
        T, _ = forward_kinematics(list(q), dh_params)
        p_cur = T[:3, 3]
        R_cur = T[:3, :3]

        e_pos = p_tgt - p_cur
        e_ang = _rotation_error_vector(R_cur, R_tgt)

        # 位置(mm) 与 姿态(rad) 采用自然单位构成牛顿残差，二者与雅可比
        # 块（[v=mm, ω=rad]）量纲一致，避免人为加权破坏收敛性。
        e = np.concatenate([e_pos, e_ang])
        cost = float(e @ e)

        # 收敛判据
        if np.linalg.norm(e_pos) <= tol_pos and np.linalg.norm(e_ang) <= tol_ang:
            return list(q)

        if prev_cost is not None and abs(prev_cost - cost) < 1e-16:
            break  # 停滞
        prev_cost = cost

        J = jacobian(list(q), dh_params)
        JtJ = J.T @ J + lam * np.eye(NUM_JOINTS)
        try:
            dq = np.linalg.solve(JtJ, J.T @ e)
        except np.linalg.LinAlgError:
            lam = min(lam * 10.0, 1e6)
            continue

        q_new = np.clip(q + dq, lows, highs)
        # 步长限制：防止超大 Δq 一步撞上关节限位后振荡
        step = np.clip(q_new - q, -MAX_IK_STEP, MAX_IK_STEP)
        q_new = np.clip(q + step, lows, highs)
        T2, _ = forward_kinematics(list(q_new), dh_params)
        e2 = np.concatenate([
            p_tgt - T2[:3, 3],
            _rotation_error_vector(T2[:3, :3], R_tgt),
        ])
        cost2 = float(e2 @ e2)

        if cost2 < cost:
            q = q_new
            lam = max(lam * 0.5, 1e-6)
        else:
            lam = min(lam * 10.0, 1e6)

    return None


def _rotation_error_vector(R_cur: np.ndarray, R_tgt: np.ndarray) -> np.ndarray:
    """计算当前姿态到目标姿态的旋转误差向量（世界系，轴角表示）.

    R_err = R_tgt @ R_cur.T 为把当前姿态转回目标姿态的误差旋转（世界系），
    取其轴角向量作为姿态误差，避免欧拉角万向节锁与不连续问题。
    """
    R_err = R_tgt @ R_cur.T
    cos_a = np.clip((np.trace(R_err) - 1.0) / 2.0, -1.0, 1.0)
    ang = math.acos(cos_a)
    if ang < 1e-9:
        return np.zeros(3)
    S = R_err - R_err.T
    vee = np.array([S[2, 1], S[0, 2], S[1, 0]])
    n = np.linalg.norm(vee)
    if n < 1e-9:
        return np.zeros(3)
    return vee / n * ang


def _rot_error_angle(R_cur: np.ndarray, R_tgt: np.ndarray) -> float:
    """计算两个旋转矩阵间的夹角（rad）. 用于 FK 回环校验."""
    R_err = R_cur.T @ R_tgt
    cos_a = np.clip((np.trace(R_err) - 1.0) / 2.0, -1.0, 1.0)
    return math.acos(cos_a)


def _solve_position_ik(
    wrist_center: np.ndarray,
    dh_params: List[DHParameter],
    joint_limits: List[Tuple[float, float]],
) -> List[Tuple[float, float, float]]:
    """
    Solve for the first three joint angles (positioning) given the wrist center.

    Uses geometric approach with the arm's planar structure.

    Args:
        wrist_center: 3D position of the wrist center [x, y, z].
        dh_params: DH parameters for all joints.
        joint_limits: Joint angle limits.

    Returns:
        List of (theta_1, theta_2, theta_3) solutions.
    """
    x, y, z = wrist_center
    a1 = dh_params[1].a  # 连杆 1 长度（肩到肘）
    a2 = dh_params[2].a  # 连杆 2 长度（肘到腕）
    d1 = dh_params[0].d  # 基座高度

    # --- 关节 1 (θ1): 基座旋转 ---
    # θ1 = atan2(y, x) 指向腕部在 XY 平面的投影方向
    theta_1_solutions: List[float] = []
    theta_1 = math.atan2(y, x)

    # 检查两个可能的 θ1 解（相差 180°）
    theta_1_alt = math.atan2(y, x) + math.pi
    for t1 in [theta_1, theta_1_alt]:
        # 使用 atan2 归一化到 [-π, π]（替代 while 循环，更高效）
        t1 = math.atan2(math.sin(t1), math.cos(t1))

        if joint_limits[0][0] <= t1 <= joint_limits[0][1]:
            if t1 not in theta_1_solutions:
                theta_1_solutions.append(t1)

    if not theta_1_solutions:
        return []

    solutions: List[Tuple[float, float, float]] = []

    for t1 in theta_1_solutions:
        # 将腕部投影到臂的平面（XZ' 平面）
        # r = sqrt(x² + y²): 腕部在 XY 平面的投影距离
        r = math.sqrt(x ** 2 + y ** 2)
        z_prime = z - d1  # 相对于基座的高度

        # --- 关节 3 (θ3): 肘关节角度 ---
        # 使用余弦定理：cos(θ3) = (r² + z'² - a1² - a2²) / (2·a1·a2)
        # 先检查原始 cos 值，允许 1e-3 的浮点误差容限
        denom = 2 * a1 * a2
        if denom == 0:
            continue  # 无效连杆长度，跳过
        cos_raw = (r ** 2 + z_prime ** 2 - a1 ** 2 - a2 ** 2) / denom
        if abs(cos_raw) > 1.0 + 1e-3:
            continue  # 真正不可达：目标超出臂的最大伸展范围
        cos_theta_3 = max(-1.0, min(1.0, cos_raw))  # 钳制到 [-1, 1]

        if abs(cos_theta_3) > 1.0:
            continue  # 不可达

        # θ3 有两个解：肘部向上（acos）和肘部向下（-acos）
        theta_3_options = [
            math.acos(cos_theta_3),       # 肘部向上
            -math.acos(cos_theta_3),       # 肘部向下
        ]

        for theta_3 in theta_3_options:
            if not (joint_limits[2][0] <= theta_3 <= joint_limits[2][1]):
                continue  # 违反关节限制

            # --- 关节 2 (θ2): 肩关节角度 ---
            # 使用几何关系：θ2 = atan2(z', r) - atan2(k2, k1)
            # 其中 k1 = a1 + a2·cos(θ3), k2 = a2·sin(θ3)
            k1 = a1 + a2 * math.cos(theta_3)
            k2 = a2 * math.sin(theta_3)
            theta_2 = math.atan2(z_prime, r) - math.atan2(k2, k1)

            if joint_limits[1][0] <= theta_2 <= joint_limits[1][1]:
                solutions.append((t1, theta_2, theta_3))

    return solutions


def _solve_orientation_ik(
    R_36: np.ndarray,
    joint_limits: List[Tuple[float, float]],
) -> List[Tuple[float, float, float]]:
    """
    Solve for the wrist joint angles (theta_4, theta_5, theta_6) from the
    orientation matrix R_36.

    Args:
        R_36: 3x3 rotation matrix from joint 3 to joint 6.
        joint_limits: Joint angle limits.

    Returns:
        List of (theta_4, theta_5, theta_6) solutions.
    """
    solutions: List[Tuple[float, float, float]] = []

    # 从 R_36 旋转矩阵中提取腕部角度
    # θ5 = acos(R_36[2, 2]) — 腕部俯仰角
    # 钳制到 [-1, 1] 防止浮点误差导致 ValueError
    theta_5 = math.acos(max(-1.0, min(1.0, R_36[2, 2])))

    # θ5 有两个解：+acos 和 -acos（腕部向上/向下翻转）
    theta_5_options = [theta_5, -theta_5]

    for t5 in theta_5_options:
        if abs(math.sin(t5)) < 1e-6:
            # 奇异姿态 (sin(θ5) ≈ 0): 万向节锁
            # 此时 θ4 和 θ6 耦合，无法独立求解
            # 将 θ4 设为 0，θ6 从 R_36 中直接计算
            theta_4 = 0.0
            theta_6 = math.atan2(R_36[1, 0], R_36[0, 0])
        else:
            # 非奇异情况：使用标准公式
            # θ4 = atan2(R_36[1,2]/sin(θ5), R_36[0,2]/sin(θ5))
            theta_4 = math.atan2(R_36[1, 2] / math.sin(t5), R_36[0, 2] / math.sin(t5))
            # θ6 = atan2(R_36[2,1]/sin(θ5), -R_36[2,0]/sin(θ5))
            theta_6 = math.atan2(R_36[2, 1] / math.sin(t5), -R_36[2, 0] / math.sin(t5))

        if (
            joint_limits[3][0] <= theta_4 <= joint_limits[3][1]
            and joint_limits[4][0] <= t5 <= joint_limits[4][1]
            and joint_limits[5][0] <= theta_6 <= joint_limits[5][1]
        ):
            solutions.append((theta_4, t5, theta_6))

    return solutions


# ---------------------------------------------------------------------------
# Jacobian
# ---------------------------------------------------------------------------


def jacobian(
    joint_angles: List[float],
    dh_params: Optional[List[DHParameter]] = None,
) -> np.ndarray:
    """
    Compute the 6x6 geometric Jacobian matrix for the current joint configuration.

    The Jacobian relates joint velocities to end-effector spatial velocity:
        v = J * q_dot

    where v is [vx, vy, vz, wx, wy, wz] (linear and angular velocity).

    Args:
        joint_angles: List of 6 joint angles in radians.
        dh_params: Optional list of DHParameter objects.

    Returns:
        6x6 Jacobian matrix as a numpy array.
    """
    if dh_params is None:
        dh_params = _get_default_dh_params()

    # 计算所有关节的累积变换矩阵
    _, transforms = forward_kinematics(joint_angles, dh_params)
    # 初始化 6x6 雅可比矩阵（上半部分为线速度，下半部分为角速度）
    J = np.zeros((6, NUM_JOINTS), dtype=np.float64)

    # 末端执行器位置
    p_end = transforms[-1][:3, 3]

    for i in range(NUM_JOINTS):
        if i == 0:
            # 基座关节：旋转轴为 Z 轴，位置为原点
            z_i = np.array([0.0, 0.0, 1.0])
            p_i = np.array([0.0, 0.0, 0.0])
        else:
            # 关节 i 的旋转轴 z_i 和位置 p_i 从前一个关节的变换矩阵中提取
            T_prev = transforms[i - 1]
            z_i = T_prev[:3, 2]   # 第 3 列是 Z 轴方向
            p_i = T_prev[:3, 3]   # 第 4 列是位置

        # 线速度列：J_v = z_i × (p_end - p_i)
        # 物理含义：关节 i 旋转时在末端产生的线速度
        J[:3, i] = np.cross(z_i, p_end - p_i)

        # 角速度列：J_ω = z_i
        # 物理含义：关节 i 旋转时在末端产生的角速度
        J[3:, i] = z_i

    return J


# ---------------------------------------------------------------------------
# PWM / Angle Conversion
# ---------------------------------------------------------------------------


def joint_angles_to_pwm(
    angles: List[float],
    angle_range_rad: float = ANGLE_RANGE_RAD,
    pwm_min: int = PWM_MIN,
    pwm_max: int = PWM_MAX,
) -> List[int]:
    """
    Convert joint angles in radians to PWM values.

    Assumes a linear mapping: angle 0 maps to the center of the PWM range,
    with the full angle range spanning the full PWM range.

    Args:
        angles: List of joint angles in radians.
        angle_range_rad: Total angular range in radians for the PWM range.
        pwm_min: Minimum PWM value.
        pwm_max: Maximum PWM value.

    Returns:
        List of integer PWM values.
    """
    center_pwm = (pwm_min + pwm_max) // 2  # 中心 PWM 值（通常为 1500）
    half_range = (pwm_max - pwm_min) / 2   # PWM 半范围
    scale = half_range / (angle_range_rad / 2)  # 比例因子: PWM/弧度

    pwm_values = []
    for angle in angles:
        # 线性映射: pwm = center + angle * scale
        pwm = center_pwm + round(angle * scale)  # 使用 round() 而非 int() 提高精度
        # 钳制到 [pwm_min, pwm_max] 范围内
        pwm = max(pwm_min, min(pwm_max, pwm))
        pwm_values.append(pwm)

    return pwm_values


def pwm_to_joint_angles(
    pwm_values: List[int],
    angle_range_rad: float = ANGLE_RANGE_RAD,
    pwm_min: int = PWM_MIN,
    pwm_max: int = PWM_MAX,
) -> List[float]:
    """
    Convert PWM values to joint angles in radians.

    Args:
        pwm_values: List of PWM values.
        angle_range_rad: Total angular range in radians for the PWM range.
        pwm_min: Minimum PWM value.
        pwm_max: Maximum PWM value.

    Returns:
        List of joint angles in radians.
    """
    center_pwm = (pwm_min + pwm_max) // 2
    half_range = (pwm_max - pwm_min) / 2
    scale = (angle_range_rad / 2) / half_range

    angles = []
    for pwm in pwm_values:
        angle = (pwm - center_pwm) * scale
        angles.append(angle)

    return angles


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------


def _get_default_dh_params() -> List[DHParameter]:
    """Create default DHParameter objects from the default parameters."""
    return [
        DHParameter(a, alpha, d, theta_offset)
        for a, alpha, d, theta_offset in DEFAULT_DH_PARAMS
    ]


def _euler_to_rotation_matrix(
    roll: float, pitch: float, yaw: float
) -> np.ndarray:
    """
    Convert Euler angles (ZYX convention) to a 3x3 rotation matrix.

    Args:
        roll: Rotation about X axis (radians).
        pitch: Rotation about Y axis (radians).
        yaw: Rotation about Z axis (radians).

    Returns:
        3x3 rotation matrix.
    """
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)

    # 绕 X 轴旋转（roll）
    R_x = np.array([
        [1, 0, 0],
        [0, cr, -sr],
        [0, sr, cr],
    ])

    # 绕 Y 轴旋转（pitch）
    R_y = np.array([
        [cp, 0, sp],
        [0, 1, 0],
        [-sp, 0, cp],
    ])

    # 绕 Z 轴旋转（yaw）
    R_z = np.array([
        [cy, -sy, 0],
        [sy, cy, 0],
        [0, 0, 1],
    ])

    # ZYX 组合：R = R_z @ R_y @ R_x（先绕 X，再绕 Y，最后绕 Z）
    return R_z @ R_y @ R_x


def _validate_joint_limits(
    joints: List[float],
    limits: List[Tuple[float, float]],
    tolerance: float = 1e-6,
) -> bool:
    """
    Check if all joint angles are within their limits.

    Args:
        joints: List of joint angles in radians.
        limits: List of (min, max) tuples for each joint.
        tolerance: Tolerance for boundary checking.

    Returns:
        True if all joints are within limits.
    """
    for angle, (low, high) in zip(joints, limits):
        if angle < low - tolerance or angle > high + tolerance:
            return False
    return True


def _joint_distance(
    joints_a: List[float],
    joints_b: List[float],
) -> float:
    """
    Compute the Euclidean distance between two joint configurations.

    Args:
        joints_a: First joint configuration.
        joints_b: Second joint configuration.

    Returns:
        Euclidean distance (sum of squared differences).
    """
    return sum((a - b) ** 2 for a, b in zip(joints_a, joints_b))