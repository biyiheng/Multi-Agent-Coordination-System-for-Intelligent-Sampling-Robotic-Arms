"""
Collision detection module for the intelligent sampling robotic arm.

Provides axis-aligned bounding box (AABB) collision detection, self-collision
checking for the arm's links, environment obstacle collision checking, and
safe retreat path generation.
"""

import math
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from .kinematics import forward_kinematics, NUM_JOINTS
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Link dimensions for self-collision detection (approximate)
# Each link is modeled as a cylinder with a radius
LINK_RADIUS = 25.0  # mm
SAFETY_MARGIN = 10.0  # mm

# =============================================================================
# Round 12: canonical collision-boundary convention.
# Shared across training (data_generator + model_trainer) and ALL deployment
# agents, guaranteeing training <-> deployment consistency:
#     clearance = min_dist - (radius + COLLISION_CLEARANCE_MM)
#     collision  <=>  clearance < 0   (i.e. min_dist < radius + COLLISION_CLEARANCE_MM)
# =============================================================================
COLLISION_CLEARANCE_MM = 30.0


def clearance(dist_mm: float, radius_mm: float) -> float:
    """Net clearance (mm). Negative => inside the collision boundary.

    Mirrors the training rule used by the Round 12 collision model
    (clearance = min_dist - (radius + 30)).
    """
    return dist_mm - (radius_mm + COLLISION_CLEARANCE_MM)


def is_collision(dist_mm: float, radius_mm: float) -> bool:
    """True if `dist_mm` is within `radius_mm + clearance` of the obstacle."""
    return clearance(dist_mm, radius_mm) < 0.0


# ---------------------------------------------------------------------------
# AABB Class
# ---------------------------------------------------------------------------


@dataclass
class AABB:
    """
    Axis-Aligned Bounding Box for collision detection.

    Attributes:
        min_point: [x_min, y_min, z_min] corner of the box.
        max_point: [x_max, y_max, z_max] corner of the box.
    """

    min_point: np.ndarray
    max_point: np.ndarray

    def __post_init__(self):
        """Ensure min_point and max_point are numpy arrays."""
        self.min_point = np.asarray(self.min_point, dtype=np.float64)
        self.max_point = np.asarray(self.max_point, dtype=np.float64)

    @classmethod
    def from_center_and_extents(
        cls, center: np.ndarray, extents: np.ndarray
    ) -> "AABB":
        """
        Create an AABB from a center point and half-extents.

        Args:
            center: Center point [x, y, z].
            extents: Half-extents [dx, dy, dz].

        Returns:
            New AABB instance.
        """
        center = np.asarray(center, dtype=np.float64)
        extents = np.asarray(extents, dtype=np.float64)
        return cls(
            min_point=center - extents,
            max_point=center + extents,
        )

    def intersects(self, other: "AABB") -> bool:
        """
        Check if this AABB intersects with another AABB.

        Args:
            other: Another AABB to test against.

        Returns:
            True if the bounding boxes overlap.
        """
        return bool(np.all(self.min_point <= other.max_point) and
                    np.all(self.max_point >= other.min_point))

    def contains_point(self, point: np.ndarray) -> bool:
        """
        Check if a point is inside this AABB.

        Args:
            point: 3D point [x, y, z].

        Returns:
            True if the point is inside or on the boundary.
        """
        point = np.asarray(point, dtype=np.float64)
        return bool(np.all(point >= self.min_point) and
                    np.all(point <= self.max_point))

    def expand(self, margin: float) -> "AABB":
        """
        Create a new AABB expanded by a margin on all sides.

        Args:
            margin: Expansion margin in mm.

        Returns:
            New expanded AABB.
        """
        margin_vec = np.array([margin, margin, margin])
        return AABB(
            min_point=self.min_point - margin_vec,
            max_point=self.max_point + margin_vec,
        )

    @property
    def center(self) -> np.ndarray:
        """Get the center point of the AABB."""
        return (self.min_point + self.max_point) / 2.0

    @property
    def extents(self) -> np.ndarray:
        """Get the half-extents of the AABB."""
        return (self.max_point - self.min_point) / 2.0

    def __repr__(self) -> str:
        return (
            f"AABB(min=[{self.min_point[0]:.1f}, {self.min_point[1]:.1f}, "
            f"{self.min_point[2]:.1f}], max=[{self.max_point[0]:.1f}, "
            f"{self.max_point[1]:.1f}, {self.max_point[2]:.1f}])"
        )


# ---------------------------------------------------------------------------
# Link Data for Self-Collision
# ---------------------------------------------------------------------------


@dataclass
class LinkSegment:
    """
    Represents a link segment of the arm for collision detection.

    Attributes:
        start_joint: Index of the starting joint.
        end_joint: Index of the ending joint.
        radius: Radius of the link cylinder in mm.
    """

    start_joint: int
    end_joint: int
    radius: float = LINK_RADIUS


# Define the arm's link segments
ARM_LINKS: List[LinkSegment] = [
    LinkSegment(0, 1, LINK_RADIUS),  # Base to shoulder
    LinkSegment(1, 2, LINK_RADIUS),  # Shoulder to elbow
    LinkSegment(2, 3, LINK_RADIUS),  # Elbow to wrist
    LinkSegment(3, 4, LINK_RADIUS),  # Wrist pitch to roll
    LinkSegment(4, 5, LINK_RADIUS),  # Wrist roll to gripper
]

# Pairs of links that should NOT be checked for self-collision
# (adjacent links are excluded)
ADJACENT_PAIRS = {(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)}


# ---------------------------------------------------------------------------
# Collision Checking
# ---------------------------------------------------------------------------


def check_self_collision(
    joint_positions: List[float],
    safety_margin: float = SAFETY_MARGIN,
) -> List[Tuple[int, int, float]]:
    """
    Check for self-collision between non-adjacent arm links.

    Models each link as a line segment with a radius and checks for
    minimum distance between non-adjacent link pairs.

    Args:
        joint_positions: List of 6 joint angles in radians.
        safety_margin: Additional safety margin in mm.

    Returns:
        List of collision tuples (link_i, link_j, penetration_distance).
        Empty list if no collisions detected.
    """
    # 计算所有关节在 3D 空间中的位置
    _, transforms = forward_kinematics(joint_positions)

    joint_points = [np.array([0.0, 0.0, 0.0])]  # 基座原点
    for T in transforms:
        joint_points.append(T[:3, 3].copy())  # 提取每个关节的 3D 位置

    collisions: List[Tuple[int, int, float]] = []

    for i, link_i in enumerate(ARM_LINKS):
        for j, link_j in enumerate(ARM_LINKS):
            if j <= i:
                continue  # 避免重复检查同一对

            # 跳过相邻连杆（它们通过关节连接，不会碰撞）
            if (i, j) in ADJACENT_PAIRS or (j, i) in ADJACENT_PAIRS:
                continue

            # 获取连杆 i 的两个端点
            p1 = joint_points[link_i.start_joint]
            p2 = joint_points[link_i.end_joint]
            # 获取连杆 j 的两个端点
            q1 = joint_points[link_j.start_joint]
            q2 = joint_points[link_j.end_joint]

            # 计算两个线段之间的最短距离
            min_dist = _segment_to_segment_distance(p1, p2, q1, q2)

            # 碰撞阈值 = 两个连杆半径之和 + 安全边距
            threshold = link_i.radius + link_j.radius + safety_margin
            if min_dist < threshold:
                penetration = threshold - min_dist  # 穿透深度
                collisions.append((i, j, penetration))
                logger.warning(
                    f"Self-collision detected: link {i} <-> link {j}, "
                    f"penetration={penetration:.1f}mm"
                )

    return collisions


def check_environment_collision(
    joint_positions: List[float],
    obstacles: List["Obstacle"],
    safety_margin: float = SAFETY_MARGIN,
) -> List[Tuple[int, str, float]]:
    """
    Check for collisions between the arm and environmental obstacles.

    Args:
        joint_positions: List of 6 joint angles in radians.
        obstacles: List of registered Obstacle objects.
        safety_margin: Additional safety margin in mm.

    Returns:
        List of collision tuples (link_index, obstacle_id, penetration_distance).
        Empty list if no collisions detected.
    """
    _, transforms = forward_kinematics(joint_positions)

    joint_points = [np.array([0.0, 0.0, 0.0])]
    for T in transforms:
        joint_points.append(T[:3, 3].copy())

    collisions: List[Tuple[int, str, float]] = []

    for i, link in enumerate(ARM_LINKS):
        p1 = joint_points[link.start_joint]
        p2 = joint_points[link.end_joint]

        for obstacle in obstacles:
            # 第一阶段：快速 AABB 粗检测
            # 为连杆创建一个扩展了安全边距的包围盒
            link_aabb = _link_to_aabb(p1, p2, link.radius + safety_margin)

            if link_aabb.intersects(obstacle.aabb):
                # 第二阶段：精确距离检测
                # 计算障碍物中心到连杆线段的最短距离
                dist = _point_to_segment_distance(obstacle.center, p1, p2)
                threshold = link.radius + obstacle.radius + safety_margin

                if dist < threshold:
                    penetration = threshold - dist
                    collisions.append((i, obstacle.id, penetration))
                    logger.warning(
                        f"Environment collision: link {i} <-> obstacle "
                        f"'{obstacle.id}', penetration={penetration:.1f}mm"
                    )

    return collisions


# ---------------------------------------------------------------------------
# Obstacle Management
# ---------------------------------------------------------------------------


@dataclass
class Obstacle:
    """
    Represents an environmental obstacle for collision detection.

    Attributes:
        id: Unique identifier for the obstacle.
        center: 3D center point [x, y, z] in mm.
        extents: Half-extents [dx, dy, dz] in mm.
        radius: Bounding sphere radius in mm.
        aabb: Axis-aligned bounding box.
    """

    id: str
    center: np.ndarray
    extents: np.ndarray
    radius: float = 0.0

    def __post_init__(self):
        self.center = np.asarray(self.center, dtype=np.float64)
        self.extents = np.asarray(self.extents, dtype=np.float64)
        if self.radius <= 0:
            self.radius = float(np.linalg.norm(self.extents))
        self.aabb = AABB(
            min_point=self.center - self.extents,
            max_point=self.center + self.extents,
        )

    def __repr__(self) -> str:
        return (
            f"Obstacle(id='{self.id}', center={self.center}, "
            f"extents={self.extents})"
        )


class ObstacleManager:
    """
    Manages registered obstacles for collision detection.

    Supports adding, removing, and querying obstacles in the workspace.
    """

    def __init__(self):
        """Initialize an empty obstacle manager."""
        self._obstacles: Dict[str, Obstacle] = {}

    def add_obstacle(
        self,
        center: np.ndarray,
        extents: np.ndarray,
        obstacle_id: Optional[str] = None,
    ) -> str:
        """
        Register a new obstacle.

        Args:
            center: 3D center point [x, y, z] in mm.
            extents: Half-extents [dx, dy, dz] in mm.
            obstacle_id: Optional unique identifier. Auto-generated if not provided.

        Returns:
            The obstacle's unique identifier.
        """
        if obstacle_id is None:
            obstacle_id = f"obs_{uuid.uuid4().hex[:8]}"

        obstacle = Obstacle(
            id=obstacle_id,
            center=np.asarray(center, dtype=np.float64),
            extents=np.asarray(extents, dtype=np.float64),
        )
        self._obstacles[obstacle_id] = obstacle
        logger.info(f"Added obstacle '{obstacle_id}' at {center}")
        return obstacle_id

    def remove_obstacle(self, obstacle_id: str) -> bool:
        """
        Remove a registered obstacle.

        Args:
            obstacle_id: Unique identifier of the obstacle to remove.

        Returns:
            True if the obstacle was found and removed.
        """
        if obstacle_id in self._obstacles:
            del self._obstacles[obstacle_id]
            logger.info(f"Removed obstacle '{obstacle_id}'")
            return True
        logger.warning(f"Obstacle '{obstacle_id}' not found")
        return False

    def get_obstacle(self, obstacle_id: str) -> Optional[Obstacle]:
        """
        Get an obstacle by its ID.

        Args:
            obstacle_id: Unique identifier.

        Returns:
            The Obstacle object, or None if not found.
        """
        return self._obstacles.get(obstacle_id)

    def get_all_obstacles(self) -> List[Obstacle]:
        """
        Get all registered obstacles.

        Returns:
            List of Obstacle objects.
        """
        return list(self._obstacles.values())

    def clear(self) -> None:
        """Remove all registered obstacles."""
        count = len(self._obstacles)
        self._obstacles.clear()
        logger.info(f"Cleared {count} obstacle(s)")

    def check_collision(
        self,
        joint_positions: List[float],
        safety_margin: float = SAFETY_MARGIN,
    ) -> bool:
        """
        Check if the arm collides with any registered obstacle.

        Args:
            joint_positions: List of joint angles.
            safety_margin: Additional safety margin.

        Returns:
            True if any collision is detected.
        """
        obstacles = self.get_all_obstacles()
        if not obstacles:
            return False

        collisions = check_environment_collision(
            joint_positions, obstacles, safety_margin
        )
        return len(collisions) > 0

    @property
    def obstacle_count(self) -> int:
        """Get the number of registered obstacles."""
        return len(self._obstacles)


# ---------------------------------------------------------------------------
# Safe Retreat Path
# ---------------------------------------------------------------------------


def get_safe_retreat_path(
    current_pos: List[float],
    home_pos: Optional[List[float]] = None,
    obstacles: Optional[List[Obstacle]] = None,
    step_size: float = 0.05,
) -> List[List[float]]:
    """
    Generate a safe retreat path from the current position to the home position.

    Uses linear interpolation in joint space, checking each intermediate
    configuration for collisions.

    Args:
        current_pos: Current joint angles in radians.
        home_pos: Target home joint angles. Defaults to all zeros.
        obstacles: List of obstacles to check against.
        step_size: Fraction of the path to advance per step (0.0 to 1.0).

    Returns:
        List of joint angle configurations forming the retreat path.
    """
    if home_pos is None:
        home_pos = [0.0] * NUM_JOINTS

    if obstacles is None:
        obstacles = []

    path: List[List[float]] = [list(current_pos)]

    # 使用整数迭代避免浮点累积误差
    num_steps = max(1, int(1.0 / step_size))
    for i in range(1, num_steps + 1):
        t = min(i * step_size, 1.0)
        # 关节空间线性插值：θ_interp = θ_current + t * (θ_home - θ_current)
        intermediate = [
            current_pos[j] + t * (home_pos[j] - current_pos[j])
            for j in range(NUM_JOINTS)
        ]
        path.append(intermediate)

        # 碰撞检测：如果沿直线路径碰撞，尝试替代路径
        if obstacles:
            env_collisions = check_environment_collision(intermediate, obstacles)
            if env_collisions:
                logger.warning(
                    f"Retreat path blocked at t={t:.2f}; attempting alternative"
                )
                # 替代策略：稍微抬高肩关节（关节 1），绕过障碍物
                alt = list(intermediate)
                alt[1] += 0.2  # 肩关节上抬 0.2 弧度
                env_collisions_alt = check_environment_collision(alt, obstacles)
                if not env_collisions_alt:
                    path[-1] = alt  # 使用替代路径
                else:
                    # 替代路径也阻塞，继续使用原路径（尽力而为）
                    logger.warning("Alternative path also blocked; proceeding anyway")

    # Ensure final position is home (use np.allclose for floating-point comparison)
    if not np.allclose(path[-1], home_pos, atol=1e-6):
        path.append(list(home_pos))

    logger.info(f"Generated retreat path: {len(path)} waypoints")
    return path


# ---------------------------------------------------------------------------
# Geometry Helpers
# ---------------------------------------------------------------------------


def _segment_to_segment_distance(
    p1: np.ndarray,
    p2: np.ndarray,
    q1: np.ndarray,
    q2: np.ndarray,
) -> float:
    """
    Compute the minimum distance between two line segments in 3D.

    Args:
        p1, p2: Endpoints of the first segment.
        q1, q2: Endpoints of the second segment.

    Returns:
        Minimum Euclidean distance between the segments.
    """
    d1 = p2 - p1  # 线段 1 的方向向量
    d2 = q2 - q1  # 线段 2 的方向向量
    r = q1 - p1   # 从 p1 到 q1 的向量

    # 计算方向向量的点积（用于后续参数化计算）
    a = float(np.dot(d1, d1))  # |d1|²
    e = float(np.dot(d2, d2))  # |d2|²
    f = float(np.dot(d2, r))   # d2 · r

    if a <= 1e-10 and e <= 1e-10:
        # 两个线段都退化为点：距离 = |r|
        return float(np.linalg.norm(r))

    if a <= 1e-10:
        # 线段 1 退化为点：参数 s = 0
        s = 0.0
        # t = clamp(f/e, 0, 1) — 线段 2 上最近点的参数
        t = max(0.0, min(1.0, f / e))
    else:
        c = float(np.dot(d1, r))  # d1 · r

        if e <= 1e-10:
            # 线段 2 退化为点：参数 t = 0
            t = 0.0
            s = max(0.0, min(1.0, -c / a))
        else:
            b = float(np.dot(d1, d2))  # d1 · d2
            denom = a * e - b * b      # 分母 = |d1|²·|d2|² - (d1·d2)²

            if abs(denom) < 1e-10:
                # 平行线段：使用简化公式
                s = 0.0
                t = max(0.0, min(1.0, f / e))
            else:
                # 一般情况：求解两个线段最近点的参数
                # s = clamp((b·f - c·e) / denom, 0, 1)
                s = max(0.0, min(1.0, (b * f - c * e) / denom))
                # t = clamp((a·f - b·c) / denom, 0, 1)
                t = max(0.0, min(1.0, (a * f - b * c) / denom))

    # 计算最近点坐标
    closest_p = p1 + s * d1  # 线段 1 上最近点
    closest_q = q1 + t * d2  # 线段 2 上最近点

    return float(np.linalg.norm(closest_p - closest_q))


def _point_to_segment_distance(
    point: np.ndarray,
    p1: np.ndarray,
    p2: np.ndarray,
) -> float:
    """
    Compute the minimum distance from a point to a line segment.

    Args:
        point: The point in 3D.
        p1, p2: Endpoints of the segment.

    Returns:
        Minimum Euclidean distance.
    """
    v = p2 - p1   # 线段方向向量
    w = point - p1  # 从线段起点到目标点的向量

    # 如果点在线段起点的"后方"（投影参数 < 0），最近点是 p1
    c1 = float(np.dot(w, v))
    if c1 <= 0:
        return float(np.linalg.norm(point - p1))

    # 如果点在线段终点的"前方"（投影参数 > 1），最近点是 p2
    c2 = float(np.dot(v, v))
    if c2 <= c1:
        return float(np.linalg.norm(point - p2))

    # 一般情况：最近点在线段内部
    # 投影参数 b = (w·v) / (v·v) ∈ [0, 1]
    b = c1 / c2
    # 投影点坐标 = p1 + b * v
    projection = p1 + b * v
    return float(np.linalg.norm(point - projection))


def _link_to_aabb(
    p1: np.ndarray,
    p2: np.ndarray,
    radius: float,
) -> AABB:
    """
    Compute the axis-aligned bounding box of a link segment.

    Args:
        p1, p2: Endpoints of the link segment.
        radius: Radius of the link.

    Returns:
        AABB enclosing the link.
    """
    min_point = np.minimum(p1, p2) - radius
    max_point = np.maximum(p1, p2) + radius
    return AABB(min_point=min_point, max_point=max_point)