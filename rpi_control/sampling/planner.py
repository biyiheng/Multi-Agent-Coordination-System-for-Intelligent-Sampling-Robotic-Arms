"""
Sampling Path Planner for the Intelligent Sampling Robotic Arm.

Orders sampling points optimally to minimize travel time using
greedy nearest-neighbor and 2-opt improvement algorithms. Generates
transfer motions between points and inserts obstacle avoidance waypoints.

Designed for the robot arm's end-effector moving between sampling
locations in the workspace.
"""

import math
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .strategy import SamplingPoint


@dataclass
class MotionSegment:
    """A single motion segment between two sampling points.

    Attributes:
        from_point: Starting sampling point.
        to_point: Target sampling point.
        distance_mm: Euclidean distance in mm.
        estimated_time_ms: Estimated travel time.
        waypoints: Intermediate waypoints for obstacle avoidance.
    """
    from_point: SamplingPoint
    to_point: SamplingPoint
    distance_mm: float = 0.0
    estimated_time_ms: float = 0.0
    waypoints: List[Tuple[float, float, float]] = None

    def __post_init__(self):
        if self.distance_mm == 0.0:
            self.distance_mm = SamplingPlanner.distance_3d(
                self.from_point.position, self.to_point.position,
            )
        if self.waypoints is None:
            self.waypoints = []


@dataclass
class SamplingPath:
    """A complete ordered path through sampling points.

    Attributes:
        points: Ordered list of sampling points.
        segments: Motion segments between consecutive points.
        total_distance_mm: Total path length.
        total_time_ms: Estimated total cycle time.
        start_pose: Starting position of the robot.
    """
    points: List[SamplingPoint]
    segments: List[MotionSegment]
    total_distance_mm: float = 0.0
    total_time_ms: float = 0.0
    start_pose: Tuple[float, float, float] = (0.0, 0.0, 0.0)


class SamplingPlanner:
    """Plans optimal paths through sampling points.

    Uses nearest-neighbor greedy ordering and 2-opt improvement to
    minimize total travel distance. Can insert obstacle avoidance
    waypoints and estimate cycle times.

    Attributes:
        travel_speed_mm_s: Travel speed in mm/s (default 200).
        z_safe_height: Safe Z height for transfer moves.
        obstacles: List of known obstacles for avoidance.
    """

    def __init__(
        self,
        travel_speed_mm_s: float = 200.0,
        z_safe_height: float = 100.0,
    ) -> None:
        """Initialize the sampling planner.

        Args:
            travel_speed_mm_s: Default travel speed in mm/s.
            z_safe_height: Safe Z height for transfer between points.
        """
        self.travel_speed_mm_s: float = travel_speed_mm_s
        self.z_safe_height: float = z_safe_height
        self.obstacles: List[Dict[str, Any]] = []

    @staticmethod
    def distance_3d(p1: Tuple[float, float, float], p2: Tuple[float, float, float]) -> float:
        """Compute Euclidean distance between two 3D points.

        Args:
            p1, p2: (x, y, z) tuples.

        Returns:
            Distance in mm.
        """
        return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2 + (p1[2] - p2[2])**2)

    # =========================================================================
    # Path Planning
    # =========================================================================

    def plan_path(
        self,
        sampling_points: List[SamplingPoint],
        start_pose: Tuple[float, float, float],
        optimize: bool = True,
    ) -> SamplingPath:
        """Plan an optimal path through all sampling points.

        Orders points using nearest-neighbor, then optionally applies
        2-opt improvement. Generates motion segments between points.

        Args:
            sampling_points: List of sampling points to visit.
            start_pose: Starting position of the robot (x, y, z).
            optimize: Whether to apply 2-opt optimization.

        Returns:
            A complete SamplingPath with ordered points and segments.
        """
        if not sampling_points:
            return SamplingPath(
                points=[],
                segments=[],
                start_pose=start_pose,
            )

        # Order points using nearest-neighbor
        ordered = self.nearest_neighbor_ordering(sampling_points, start_pose)

        # Apply 2-opt improvement
        if optimize and len(ordered) > 2:
            ordered = self.tsp_2opt(ordered, start_pose)

        # Generate motion segments
        segments = self.generate_transfer_motions(ordered, start_pose)

        # Calculate totals
        total_distance = sum(s.distance_mm for s in segments)
        total_time = sum(s.estimated_time_ms for s in segments)

        return SamplingPath(
            points=ordered,
            segments=segments,
            total_distance_mm=round(total_distance, 1),
            total_time_ms=round(total_time, 1),
            start_pose=start_pose,
        )

    # =========================================================================
    # Ordering
    # =========================================================================

    def nearest_neighbor_ordering(
        self,
        points: List[SamplingPoint],
        start: Tuple[float, float, float],
    ) -> List[SamplingPoint]:
        """Order points using greedy nearest-neighbor (TSP heuristic).

        Starting from the start position, repeatedly selects the nearest
        unvisited point.

        Args:
            points: List of sampling points.
            start: Starting position (x, y, z).

        Returns:
            Ordered list of sampling points.
        """
        if not points:
            return []

        remaining = list(points)
        ordered = []
        current = start

        while remaining:
            # Find nearest point
            nearest = min(remaining, key=lambda p: self.distance_3d(current, p.position))
            ordered.append(nearest)
            remaining.remove(nearest)
            current = nearest.position

        return ordered

    def tsp_2opt(
        self,
        points: List[SamplingPoint],
        start: Tuple[float, float, float],
        max_iterations: int = 100,
    ) -> List[SamplingPoint]:
        """Improve point ordering using 2-opt local search.

        Iteratively swaps pairs of edges to reduce total path length.
        Stops when no improvement is found or max iterations reached.

        Args:
            points: Ordered list of sampling points.
            start: Starting position.
            max_iterations: Maximum number of iterations.

        Returns:
            Improved ordering of sampling points.
        """
        if len(points) <= 2:
            return points

        n = len(points)

        def path_length(pts: List[SamplingPoint]) -> float:
            total = self.distance_3d(start, pts[0].position)
            for i in range(n - 1):
                total += self.distance_3d(pts[i].position, pts[i + 1].position)
            return total

        best = list(points)
        best_length = path_length(best)

        improved = True
        iteration = 0
        while improved and iteration < max_iterations:
            improved = False
            iteration += 1

            for i in range(n - 1):
                for j in range(i + 1, n):
                    # Create a new ordering by reversing the segment between i and j
                    new_order = best[:i] + best[i:j + 1][::-1] + best[j + 1:]
                    new_length = path_length(new_order)

                    if new_length < best_length - 0.01:  # Small tolerance
                        best = new_order
                        best_length = new_length
                        improved = True

        return best

    # =========================================================================
    # Motion Generation
    # =========================================================================

    def generate_transfer_motions(
        self,
        ordered_points: List[SamplingPoint],
        start_pose: Tuple[float, float, float],
    ) -> List[MotionSegment]:
        """Generate motion segments between consecutive points.

        Creates transfer motions that go up to safe height, move horizontally,
        then descend to the next point. This is the standard pick-and-place
        transfer pattern.

        Args:
            ordered_points: Ordered list of sampling points.
            start_pose: Starting robot position.

        Returns:
            List of MotionSegment objects.
        """
        segments = []
        prev = start_pose

        for i, point in enumerate(ordered_points):
            dist = self.distance_3d(prev, point.position)
            time_ms = (dist / self.travel_speed_mm_s) * 1000

            # Generate transfer waypoints: up -> across -> down
            waypoints = []
            z_prev = prev[2]
            z_target = point.position[2]
            safe_z = self.z_safe_height

            if z_prev < safe_z:
                waypoints.append((prev[0], prev[1], safe_z))
            waypoints.append((point.position[0], point.position[1], safe_z))
            if z_target < safe_z:
                waypoints.append(point.position)

            previous_point = SamplingPoint(id="start", position=prev) if i == 0 else ordered_points[i - 1]

            segments.append(MotionSegment(
                from_point=previous_point,
                to_point=point,
                distance_mm=round(dist, 1),
                estimated_time_ms=round(time_ms, 1),
                waypoints=waypoints,
            ))
            prev = point.position

        return segments

    # =========================================================================
    # Obstacle Avoidance
    # =========================================================================

    def insert_obstacle_avoidance(
        self,
        path: SamplingPath,
        obstacles: Optional[List[Dict[str, Any]]] = None,
    ) -> SamplingPath:
        """Insert obstacle avoidance waypoints into a path.

        For each segment that passes near an obstacle, adds intermediate
        waypoints to route around it.

        Args:
            path: The original sampling path.
            obstacles: List of obstacle dicts with 'position' and 'radius_mm'.

        Returns:
            Modified path with obstacle avoidance waypoints.
        """
        obs = obstacles or self.obstacles
        if not obs:
            return path

        new_segments = []
        for segment in path.segments:
            wp = list(segment.waypoints)

            for obstacle in obs:
                obs_pos = obstacle.get("position", (0, 0, 0))
                obs_radius = obstacle.get("radius_mm", 50.0)

                # Check each waypoint against this obstacle
                modified_wp = []
                for w in wp:
                    dist = self.distance_3d(w, obs_pos)
                    if dist < obs_radius + 20.0:
                        # Add avoidance point: push away from obstacle
                        direction = np.array(w) - np.array(obs_pos)
                        norm = np.linalg.norm(direction)
                        if norm > 0:
                            direction = direction / norm
                        avoid_point = tuple(np.array(obs_pos) + direction * (obs_radius + 30.0))
                        modified_wp.append(avoid_point)
                    modified_wp.append(w)
                wp = modified_wp

            new_segments.append(MotionSegment(
                from_point=segment.from_point,
                to_point=segment.to_point,
                distance_mm=segment.distance_mm,
                estimated_time_ms=segment.estimated_time_ms,
                waypoints=wp,
            ))

        return SamplingPath(
            points=path.points,
            segments=new_segments,
            total_distance_mm=sum(s.distance_mm for s in new_segments),
            total_time_ms=sum(s.estimated_time_ms for s in new_segments),
            start_pose=path.start_pose,
        )

    # =========================================================================
    # Time Estimation
    # =========================================================================

    def estimate_cycle_time(self, path: SamplingPath) -> Dict[str, float]:
        """Estimate the total cycle time for a path.

        Includes travel time, sampling time (per point), and overhead.

        Args:
            path: The sampling path.

        Returns:
            Dict with detailed time breakdown.
        """
        travel_time_s = path.total_time_ms / 1000.0
        sample_time_per_point_s = 2.0  # Assume 2 seconds per sample
        sample_time_s = len(path.points) * sample_time_per_point_s

        # Overhead: approach, grasp, inspect, place
        overhead_per_point_s = 5.0
        overhead_s = len(path.points) * overhead_per_point_s

        total_s = travel_time_s + sample_time_s + overhead_s

        return {
            "total_time_s": round(total_s, 1),
            "travel_time_s": round(travel_time_s, 1),
            "sample_time_s": round(sample_time_s, 1),
            "overhead_time_s": round(overhead_s, 1),
            "num_points": len(path.points),
            "num_segments": len(path.segments),
        }

    def optimize_for_throughput(self, path: SamplingPath) -> SamplingPath:
        """Optimize the path for maximum throughput (minimum total time).

        Re-orders points to minimize total travel + sampling time. This
        is equivalent to the standard TSP optimization.

        Args:
            path: The input sampling path.

        Returns:
            Optimized path.
        """
        # Re-run 2-opt with more iterations
        optimized = self.tsp_2opt(path.points, path.start_pose, max_iterations=500)

        segments = self.generate_transfer_motions(optimized, path.start_pose)

        return SamplingPath(
            points=optimized,
            segments=segments,
            total_distance_mm=round(sum(s.distance_mm for s in segments), 1),
            total_time_ms=round(sum(s.estimated_time_ms for s in segments), 1),
            start_pose=path.start_pose,
        )

    # =========================================================================
    # Helpers
    # =========================================================================

    def add_obstacle(self, name: str, position: Tuple[float, float, float], radius_mm: float = 50.0) -> None:
        """Register an obstacle for avoidance.

        Args:
            name: Obstacle identifier.
            position: (x, y, z) position in mm.
            radius_mm: Safety radius.
        """
        self.obstacles.append({
            "name": name,
            "position": position,
            "radius_mm": radius_mm,
        })

    def clear_obstacles(self) -> None:
        """Remove all registered obstacles."""
        self.obstacles.clear()

    def get_path_summary(self, path: SamplingPath) -> Dict[str, Any]:
        """Get a summary of a sampling path.

        Args:
            path: The sampling path.

        Returns:
            Dict with path summary.
        """
        return {
            "num_points": len(path.points),
            "num_segments": len(path.segments),
            "total_distance_mm": path.total_distance_mm,
            "total_time_ms": path.total_time_ms,
            "avg_segment_distance_mm": round(
                path.total_distance_mm / len(path.segments), 1,
            ) if path.segments else 0.0,
            "start_pose": path.start_pose,
            "end_pose": path.points[-1].position if path.points else path.start_pose,
            "point_ids": [p.id for p in path.points],
        }