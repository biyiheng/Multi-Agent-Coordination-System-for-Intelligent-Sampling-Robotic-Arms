"""
Trajectory planning module for the intelligent sampling robotic arm.

Provides trajectory generation in both Cartesian space and joint space,
including S-curve and trapezoidal velocity profiles, waypoint generation,
and path smoothing for smooth, collision-free motion.
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------


@dataclass
class TrajectoryPoint:
    """
    Represents a single point along a trajectory.

    Attributes:
        positions: Joint positions (PWM values or radians).
        velocities: Joint velocities.
        time: Time in seconds from trajectory start.
    """

    positions: List[float]
    velocities: List[float]
    time: float

    def __repr__(self) -> str:
        return (
            f"TrajectoryPoint(t={self.time:.3f}s, "
            f"pos={[f'{p:.1f}' for p in self.positions[:3]]}...)"
        )


@dataclass
class VelocityProfile:
    """
    Parameters for a velocity profile.

    Attributes:
        max_velocity: Maximum allowed velocity.
        max_acceleration: Maximum allowed acceleration.
        max_jerk: Maximum allowed jerk (for S-curve profiles).
    """

    max_velocity: float
    max_acceleration: float
    max_jerk: float = 0.0


# ---------------------------------------------------------------------------
# Cartesian Path Planning
# ---------------------------------------------------------------------------


def plan_linear_path(
    start_pose: np.ndarray,
    end_pose: np.ndarray,
    steps: int = 50,
) -> List[np.ndarray]:
    """
    Generate a linear Cartesian path between two poses.

    Interpolates position linearly and orientation using spherical linear
    interpolation (SLERP).

    Args:
        start_pose: Start pose [x, y, z, roll, pitch, yaw] (mm and radians).
        end_pose: End pose [x, y, z, roll, pitch, yaw] (mm and radians).
        steps: Number of interpolation steps (including start and end).

    Returns:
        List of interpolated pose arrays, length = steps.
    """
    if steps < 2:
        return [start_pose, end_pose]

    path: List[np.ndarray] = []

    for i in range(steps):
        # t ∈ [0, 1]: 归一化插值参数
        t = i / (steps - 1) if steps > 1 else 0.0

        # 位置：线性插值
        # pos = start_pos + t * (end_pos - start_pos)
        pos = start_pose[:3] + t * (end_pose[:3] - start_pose[:3])

        # 姿态：角度插值（用最短角度差，避免绕远路）
        # 对于大角度旋转，应使用四元数 SLERP，这里使用简化版本
        ori = start_pose[3:] + t * _angle_diff(end_pose[3:], start_pose[3:])

        # 拼接位置和姿态为完整的 6 元素位姿向量
        pose = np.concatenate([pos, ori])
        path.append(pose)

    return path


def _angle_diff(target: np.ndarray, source: np.ndarray) -> np.ndarray:
    """
    Compute the shortest angular difference between two orientation vectors.

    Args:
        target: Target orientation [roll, pitch, yaw].
        source: Source orientation [roll, pitch, yaw].

    Returns:
        Angular difference wrapped to [-pi, pi].
    """
    diff = target - source
    # Wrap to [-pi, pi]
    return np.arctan2(np.sin(diff), np.cos(diff))


# ---------------------------------------------------------------------------
# Joint Space Path Planning
# ---------------------------------------------------------------------------


def plan_joint_path(
    start_joints: List[float],
    end_joints: List[float],
    duration: float,
    dt: float = 0.02,
) -> List[TrajectoryPoint]:
    """
    Generate a joint-space trajectory using quintic polynomial interpolation.

    Quintic polynomials ensure zero velocity and acceleration at the endpoints,
    producing smooth, continuous motion.

    Args:
        start_joints: Starting joint positions.
        end_joints: Target joint positions.
        duration: Total trajectory duration in seconds.
        dt: Time step between trajectory points in seconds.

    Returns:
        List of TrajectoryPoint objects.
    """
    num_joints = len(start_joints)
    # 计算轨迹点数：至少 2 个点（起点和终点）
    num_steps = max(2, int(duration / dt) + 1)

    trajectory: List[TrajectoryPoint] = []

    for i in range(num_steps):
        t = i * dt
        if t > duration:
            t = duration  # 防止浮点误差导致超出

        # s = t / duration: 归一化时间 [0, 1]
        s = t / duration if duration > 0 else 0.0

        # 五次多项式混合系数: blend(s) = 10s³ - 15s⁴ + 6s⁵
        # 该函数满足: blend(0) = 0, blend(1) = 1
        #            blend'(0) = 0, blend'(1) = 0  (零速度)
        #            blend''(0) = 0, blend''(1) = 0 (零加速度)
        s3 = s ** 3
        s4 = s ** 4
        s5 = s ** 5
        blend = 10 * s3 - 15 * s4 + 6 * s5

        # 速度缩放因子: blend'(s) / duration
        # blend'(s) = 30s² - 60s³ + 30s⁴
        if duration > 0:
            blend_vel = (30 * s ** 2 - 60 * s3 + 30 * s4) / duration
        else:
            blend_vel = 0.0

        # 关节位置：线性插值，用五次多项式平滑
        positions = [
            start_joints[j] + blend * (end_joints[j] - start_joints[j])
            for j in range(num_joints)
        ]

        # 关节速度：位置变化率
        velocities = [
            blend_vel * (end_joints[j] - start_joints[j])
            for j in range(num_joints)
        ]

        trajectory.append(TrajectoryPoint(
            positions=positions,
            velocities=velocities,
            time=t,
        ))

    return trajectory


# ---------------------------------------------------------------------------
# S-Curve Velocity Profile
# ---------------------------------------------------------------------------


def s_curve_profile(
    distance: float,
    max_vel: float,
    max_accel: float,
    max_jerk: float,
    dt: float = 0.01,
) -> List[Tuple[float, float, float]]:
    """
    Generate an S-curve velocity profile for smooth motion.

    The S-curve profile has 7 phases:
        1. Jerk up (increasing acceleration)
        2. Constant acceleration
        3. Jerk down (decreasing acceleration)
        4. Constant velocity
        5. Jerk down (increasing deceleration)
        6. Constant deceleration
        7. Jerk up (decreasing deceleration to zero)

    Args:
        distance: Total distance to travel.
        max_vel: Maximum velocity.
        max_accel: Maximum acceleration.
        max_jerk: Maximum jerk (rate of change of acceleration).
        dt: Time step for profile generation.

    Returns:
        List of (time, position, velocity) tuples.
    """
    if distance <= 0 or max_vel <= 0 or max_accel <= 0 or max_jerk <= 0:
        return [(0.0, 0.0, 0.0)]

    # 第一步：计算各阶段时间
    # t_j: 加加速度时间（jerk up/down 阶段的时间）
    t_j = max_accel / max_jerk  # 达到最大加速度所需时间

    # 检查是否能在加速阶段达到最大加速度
    if max_vel < max_accel ** 2 / max_jerk:
        # 三角形加速度剖面（无恒加速度阶段）
        # 速度不足以达到最大加速度
        t_j = math.sqrt(max_vel / max_jerk)
        t_a = 2 * t_j  # 加速阶段总时间 = 2 × jerk 时间
    else:
        # 梯形加速度剖面（有恒加速度阶段）
        t_a = max_vel / max_accel + t_j

    # 加速阶段覆盖的距离
    s_accel = max_jerk * t_j ** 3 / 6 + max_accel * (t_a - 2 * t_j) * (t_a + t_j) / 2 + max_jerk * t_j ** 3 / 3

    # 第二步：检查是否有匀速阶段
    if 2 * s_accel > distance:
        # 距离太短，无法达到最大速度（三角形速度剖面）
        t_j = (distance / (2 * max_jerk)) ** (1 / 3)
        t_a = 2 * t_j
        t_v = 0.0  # 无匀速阶段
        profile_max_vel = max_jerk * t_j ** 2
    else:
        # 有匀速阶段
        t_v = (distance - 2 * s_accel) / max_vel
        profile_max_vel = max_vel

    # 总时间 = 加速 + 匀速 + 减速
    t_total = 2 * t_a + t_v

    # 第三步：生成速度剖面（7 个阶段）
    profile: List[Tuple[float, float, float]] = []
    t = 0.0
    pos = 0.0
    vel = 0.0
    accel = 0.0

    while t <= t_total + dt:
        # 根据当前时间判断所处的阶段
        if t < t_j:
            # 阶段 1: 加加速度上升（jerk > 0, accel 递增）
            j = max_jerk
        elif t < t_a - t_j:
            # 阶段 2: 恒加速度（jerk = 0, accel 恒定）
            j = 0.0
        elif t < t_a:
            # 阶段 3: 加加速度下降（jerk < 0, accel 递减到 0）
            j = -max_jerk
        elif t < t_a + t_v:
            # 阶段 4: 恒速度（jerk = 0, accel = 0, vel 恒定）
            j = 0.0
        elif t < t_a + t_v + t_j:
            # 阶段 5: 减加速度（jerk < 0, accel 负向递增）
            j = -max_jerk
        elif t < t_a + t_v + t_a - t_j:
            # 阶段 6: 恒减速度（jerk = 0, accel 恒定）
            j = 0.0
        elif t < t_total:
            # 阶段 7: 减加速度下降（jerk > 0, accel 回零）
            j = max_jerk
        else:
            j = 0.0

        # 数值积分：加速度 → 速度 → 位置
        accel += j * dt
        # 钳制加速度到 [-max_accel, max_accel]
        if j > 0:
            accel = min(accel, max_accel)
        elif j < 0:
            accel = max(accel, -max_accel)

        vel += accel * dt
        vel = max(0.0, min(vel, profile_max_vel))  # 速度不能为负

        pos += vel * dt
        pos = min(pos, distance)  # 位置不能超过目标距离

        profile.append((t, pos, vel))

        if t >= t_total:
            break

        t += dt

    return profile


# ---------------------------------------------------------------------------
# Trapezoidal Velocity Profile
# ---------------------------------------------------------------------------


def trapezoidal_profile(
    distance: float,
    max_vel: float,
    max_accel: float,
    dt: float = 0.01,
) -> List[Tuple[float, float, float]]:
    """
    Generate a trapezoidal velocity profile.

    The profile has 3 phases: acceleration, constant velocity, deceleration.

    Args:
        distance: Total distance to travel.
        max_vel: Maximum velocity.
        max_accel: Maximum acceleration.
        dt: Time step for profile generation.

    Returns:
        List of (time, position, velocity) tuples.
    """
    if distance <= 0 or max_vel <= 0 or max_accel <= 0:
        return [(0.0, 0.0, 0.0)]

    # 加速到最大速度所需时间
    t_accel = max_vel / max_accel

    # 加速阶段覆盖的距离：s = 1/2 * a * t²
    s_accel = 0.5 * max_accel * t_accel ** 2

    if 2 * s_accel > distance:
        # 三角形剖面：距离太短，达不到最大速度
        t_accel = math.sqrt(distance / max_accel)
        max_vel = max_accel * t_accel  # 实际达到的最大速度
        t_const = 0.0  # 无匀速阶段
    else:
        # 梯形剖面：有加速、匀速、减速三个阶段
        t_const = (distance - 2 * s_accel) / max_vel

    # 总时间 = 加速 + 匀速 + 减速
    t_total = 2 * t_accel + t_const

    profile: List[Tuple[float, float, float]] = []
    t = 0.0
    pos = 0.0
    vel = 0.0

    while t <= t_total + dt:
        if t < t_accel:
            # 阶段 1: 加速阶段
            vel = max_accel * t                 # v = a * t
            pos = 0.5 * max_accel * t ** 2      # s = 1/2 * a * t²
        elif t < t_accel + t_const:
            # 阶段 2: 匀速阶段
            vel = max_vel
            pos = s_accel + max_vel * (t - t_accel)  # s = s_accel + v * t_const_elapsed
        elif t <= t_total:
            # 阶段 3: 减速阶段
            t_dec = t - t_accel - t_const           # 从减速开始算起的时间
            vel = max_vel - max_accel * t_dec        # v = v_max - a * t_dec
            pos = s_accel + max_vel * t_const + max_vel * t_dec - 0.5 * max_accel * t_dec ** 2
        else:
            vel = 0.0
            pos = distance

        vel = max(0.0, vel)
        pos = min(pos, distance)

        profile.append((t, pos, vel))

        if t >= t_total:
            break

        t += dt

    return profile


# ---------------------------------------------------------------------------
# Waypoint Generation
# ---------------------------------------------------------------------------


def generate_waypoints(
    path_points: List[np.ndarray],
    time_per_point: float = 0.1,
) -> List[TrajectoryPoint]:
    """
    Generate timed waypoints from a list of path points.

    Assigns uniform time spacing to each path point.

    Args:
        path_points: List of pose vectors.
        time_per_point: Time allocated per waypoint in seconds.

    Returns:
        List of TrajectoryPoint objects with velocities computed from
        finite differences.
    """
    if len(path_points) < 2:
        return [
            TrajectoryPoint(
                positions=list(path_points[0]),
                velocities=[0.0] * len(path_points[0]),
                time=0.0,
            )
        ]

    waypoints: List[TrajectoryPoint] = []
    num_dims = len(path_points[0])

    for i, point in enumerate(path_points):
        if i == 0:
            # 第一个点：使用前向差分计算速度
            # v = (p[i+1] - p[i]) / dt
            vel = (path_points[1] - point) / time_per_point
        elif i == len(path_points) - 1:
            # 最后一个点：使用后向差分计算速度
            # v = (p[i] - p[i-1]) / dt
            vel = (point - path_points[i - 1]) / time_per_point
        else:
            # 中间点：使用中心差分计算速度（更精确）
            # v = (p[i+1] - p[i-1]) / (2 * dt)
            vel = (path_points[i + 1] - path_points[i - 1]) / (2 * time_per_point)

        waypoints.append(TrajectoryPoint(
            positions=list(point),
            velocities=list(vel),
            time=i * time_per_point,
        ))

    return waypoints


# ---------------------------------------------------------------------------
# Path Smoothing
# ---------------------------------------------------------------------------


def smooth_path(
    raw_path: List[np.ndarray],
    smoothing_factor: float = 0.5,
    iterations: int = 3,
) -> List[np.ndarray]:
    """
    Smooth a path using a moving average filter.

    This reduces jerk and sharp corners in the path.

    Args:
        raw_path: List of pose vectors to smooth.
        smoothing_factor: Smoothing strength (0 = no smoothing, 1 = max smoothing).
        iterations: Number of smoothing passes.

    Returns:
        Smoothed path as a list of pose vectors.
    """
    if len(raw_path) < 3 or smoothing_factor <= 0:
        return list(raw_path)

    # 深拷贝路径，避免修改原始数据
    path = [np.copy(p) for p in raw_path]
    n = len(path)

    for _ in range(iterations):
        # 保持第一个点不变（起点）
        new_path = [np.copy(path[0])]

        for i in range(1, n - 1):
            # 移动平均滤波器：当前点与邻居加权平均
            # smoothed[i] = (1-α) * p[i] + (α/2) * p[i-1] + (α/2) * p[i+1]
            # α = smoothing_factor, 控制平滑强度
            smoothed = (
                (1 - smoothing_factor) * path[i]
                + (smoothing_factor / 2) * path[i - 1]
                + (smoothing_factor / 2) * path[i + 1]
            )
            new_path.append(smoothed)

        # 保持最后一个点不变（终点）
        new_path.append(np.copy(path[-1]))
        path = new_path

    logger.debug(f"Path smoothed: {len(raw_path)} points, factor={smoothing_factor}")
    return path