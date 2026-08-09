"""
Workspace analysis module for the intelligent sampling robotic arm.

Performs Monte Carlo workspace boundary computation, reachability checks,
dexterity/manipulability analysis, sampling grid generation, and
TSP-based sampling order optimization.
"""

import math
import random
from typing import List, Optional, Tuple

import numpy as np

from .kinematics import (
    forward_kinematics,
    jacobian,
    NUM_JOINTS,
    DEFAULT_JOINT_LIMITS,
)
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Default workspace bounds in mm
DEFAULT_BOUNDS = {
    "x_range": (-200, 200),
    "y_range": (-200, 200),
    "z_range": (0, 300),
}

# Monte Carlo sampling defaults
DEFAULT_MC_SAMPLES = 10000


# ---------------------------------------------------------------------------
# Workspace Boundary Computation
# ---------------------------------------------------------------------------


def compute_workspace_boundary(
    num_samples: int = DEFAULT_MC_SAMPLES,
    joint_limits: Optional[List[Tuple[float, float]]] = None,
    resolution: float = 5.0,
) -> np.ndarray:
    """
    Compute the workspace boundary using Monte Carlo sampling.

    Randomly samples joint configurations within limits and computes
    the corresponding end-effector positions. The resulting point cloud
    represents the reachable workspace.

    Args:
        num_samples: Number of random joint configurations to sample.
        joint_limits: Joint angle limits in radians. Uses defaults if None.
        resolution: Grid resolution in mm for boundary discretization.

    Returns:
        Nx3 numpy array of reachable end-effector positions (x, y, z) in mm.
    """
    if joint_limits is None:
        joint_limits = DEFAULT_JOINT_LIMITS

    points: List[np.ndarray] = []

    for _ in range(num_samples):
        # 在关节限制范围内随机生成一组关节角度
        angles = [
            random.uniform(low, high)
            for low, high in joint_limits
        ]

        try:
            # 通过正运动学计算末端执行器位置
            T, _ = forward_kinematics(angles)
            pos = T[:3, 3].copy()  # 提取位置向量 [x, y, z]
            points.append(pos)
        except Exception:
            continue  # 忽略无效的关节配置

    if not points:
        logger.warning("No valid workspace points found; returning empty array")
        return np.array([])

    # 返回 N×3 的点云数组
    return np.array(points)


# ---------------------------------------------------------------------------
# Reachability Check
# ---------------------------------------------------------------------------


def is_point_reachable(
    x: float,
    y: float,
    z: float,
    joint_limits: Optional[List[Tuple[float, float]]] = None,
) -> bool:
    """
    Determine if a point (x, y, z) is within the robot's reachable workspace.

    Uses a geometric approach: the point must be within the spherical shell
    defined by the arm's minimum and maximum reach.

    Args:
        x: X coordinate in mm.
        y: Y coordinate in mm.
        z: Z coordinate in mm.
        joint_limits: Joint angle limits.

    Returns:
        True if the point is reachable.
    """
    from .kinematics import inverse_kinematics

    # Simple geometric check first
    target_pose = np.array([x, y, z, 0.0, 0.0, 0.0])

    try:
        solutions = inverse_kinematics(target_pose, joint_limits=joint_limits)
        return len(solutions) > 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Dexterity / Manipulability
# ---------------------------------------------------------------------------


def compute_dexterity(
    point: np.ndarray,
    joint_limits: Optional[List[Tuple[float, float]]] = None,
) -> float:
    """
    Compute the manipulability measure at a given point in the workspace.

    The manipulability measure is defined as:
        w = sqrt(det(J * J^T))

    Higher values indicate better dexterity (farther from singularities).

    Args:
        point: 3D point [x, y, z] in mm.
        joint_limits: Joint angle limits.

    Returns:
        Manipulability measure (non-negative float). Returns 0.0 if unreachable
        or at a singularity.
    """
    from .kinematics import inverse_kinematics

    target_pose = np.array([point[0], point[1], point[2], 0.0, 0.0, 0.0])

    try:
        solutions = inverse_kinematics(target_pose, joint_limits=joint_limits)
        if not solutions:
            return 0.0

        # Use the first valid solution
        J = jacobian(solutions[0])
        JJt = J @ J.T
        det = np.linalg.det(JJt)
        if det <= 0:
            return 0.0

        return math.sqrt(det)

    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Sampling Grid Generation
# ---------------------------------------------------------------------------


def generate_sampling_grid(
    bounds: Optional[dict] = None,
    spacing: float = 20.0,
    pattern: str = "rectangular",
) -> List[np.ndarray]:
    """
    Generate a grid of sampling points within the workspace.

    Args:
        bounds: Dictionary with 'x_range', 'y_range', 'z_range' keys.
                Each value is a (min, max) tuple in mm.
        spacing: Spacing between grid points in mm.
        pattern: Grid pattern type: 'rectangular' or 'hexagonal'.

    Returns:
        List of numpy arrays, each representing a sampling point [x, y, z].
    """
    if bounds is None:
        bounds = DEFAULT_BOUNDS

    x_min, x_max = bounds["x_range"]
    y_min, y_max = bounds["y_range"]
    z_min, z_max = bounds["z_range"]

    points: List[np.ndarray] = []

    if pattern == "rectangular":
        # 矩形网格：三层嵌套循环，按 Z → Y → X 顺序扫描
        z = z_min
        while z <= z_max:
            y = y_min
            while y <= y_max:
                x = x_min
                while x <= x_max:
                    # 只添加可达的点（通过 IK 验证）
                    if is_point_reachable(x, y, z):
                        points.append(np.array([x, y, z]))
                    x += spacing
                y += spacing
            z += spacing

    elif pattern == "hexagonal":
        # 六边形网格：奇偶行错位排列，覆盖更均匀
        hex_spacing_x = spacing
        hex_spacing_y = spacing * math.sqrt(3) / 2  # 行间距 = spacing * √3/2

        z = z_min
        while z <= z_max:
            row = 0
            y = y_min
            while y <= y_max:
                # 奇数行偏移半个间距，形成六边形排列
                x_offset = (spacing / 2) if row % 2 == 1 else 0
                x = x_min + x_offset
                while x <= x_max:
                    if is_point_reachable(x, y, z):
                        points.append(np.array([x, y, z]))
                    x += hex_spacing_x
                y += hex_spacing_y
                row += 1
            z += spacing

    else:
        logger.warning(f"Unknown pattern '{pattern}'; falling back to rectangular")
        return generate_sampling_grid(bounds, spacing, "rectangular")

    logger.info(
        f"Generated {len(points)} sampling points with {pattern} pattern "
        f"(spacing={spacing}mm)"
    )
    return points


# ---------------------------------------------------------------------------
# Sampling Order Optimization (TSP-like)
# ---------------------------------------------------------------------------


def optimize_sampling_order(
    points: List[np.ndarray],
    start_pos: Optional[np.ndarray] = None,
) -> List[np.ndarray]:
    """
    Optimize the order of sampling points using a nearest-neighbor heuristic.

    This is a greedy TSP (Traveling Salesman Problem) approximation that
    minimizes total travel distance.

    Args:
        points: List of 3D sample points to order.
        start_pos: Starting position. If None, starts from the first point.

    Returns:
        Ordered list of points.
    """
    if len(points) <= 2:
        return list(points)

    remaining = list(points)  # 未访问的点集合
    ordered: List[np.ndarray] = []

    # 确定起始点
    if start_pos is not None:
        current = start_pos
    else:
        # 默认从第一个点开始
        current = remaining.pop(0)
        ordered.append(current)

    # 贪心最近邻算法：每次选择距离当前点最近的未访问点
    while remaining:
        distances = [np.linalg.norm(current - p) for p in remaining]
        nearest_idx = int(np.argmin(distances))  # 找到最近点的索引

        current = remaining.pop(nearest_idx)
        ordered.append(current)

    # 计算总路径长度（用于日志）
    total_distance = sum(
        np.linalg.norm(ordered[i] - ordered[i - 1])
        for i in range(1, len(ordered))
    )
    logger.info(
        f"Optimized sampling order: {len(ordered)} points, "
        f"total distance: {total_distance:.1f} mm"
    )

    return ordered


# ---------------------------------------------------------------------------
# Workspace Statistics
# ---------------------------------------------------------------------------


def compute_workspace_statistics(
    points: Optional[np.ndarray] = None,
    num_samples: int = DEFAULT_MC_SAMPLES,
) -> dict:
    """
    Compute statistical properties of the workspace.

    Args:
        points: Pre-computed workspace points. If None, compute via Monte Carlo.
        num_samples: Number of samples for Monte Carlo (if points is None).

    Returns:
        Dictionary with workspace statistics (volume estimate, centroid, extents).
    """
    if points is None:
        points = compute_workspace_boundary(num_samples=num_samples)

    if len(points) == 0:
        return {
            "num_points": 0,
            "centroid": np.array([0.0, 0.0, 0.0]),
            "extents": np.array([0.0, 0.0, 0.0]),
            "volume_estimate": 0.0,
        }

    # 质心：所有点的平均值
    centroid = np.mean(points, axis=0)
    # 范围：各轴方向上的跨度 = max - min
    extents = np.max(points, axis=0) - np.min(points, axis=0)

    # 体积估计：使用包围盒体积（粗略估计可达工作空间体积）
    volume = float(np.prod(extents))

    return {
        "num_points": len(points),
        "centroid": centroid,
        "extents": extents,
        "volume_estimate": volume,
    }