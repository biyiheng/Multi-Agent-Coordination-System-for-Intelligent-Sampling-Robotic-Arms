"""
Sampling Strategy Agent for the Intelligent Sampling Robotic Arm.

Plans and manages sampling operations: generates sampling points using
various strategies (grid, adaptive, targeted), evaluates coverage quality,
and integrates vision results to dynamically update the sampling plan.

Uses a LangGraph-inspired state machine:
    IDLE -> PLANNING -> SAMPLING -> EVALUATING -> DONE
"""

import asyncio
import math
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from .base_agent import BaseAgent, AgentConfig, AgentStatus, validate_state, log_execution


class SamplingState(Enum):
    """States for the sampling state machine."""
    IDLE = "idle"
    PLANNING = "planning"
    SAMPLING = "sampling"
    EVALUATING = "evaluating"
    DONE = "done"
    ERROR = "error"


class SamplingStrategy(Enum):
    """Available sampling strategies."""
    GRID = "grid"
    ADAPTIVE = "adaptive"
    TARGETED = "targeted"
    RANDOM = "random"
    STRATIFIED = "stratified"


@dataclass
class SamplingPoint:
    """A single sampling point in the workspace.

    Attributes:
        id: Unique identifier.
        position: (x, y, z) coordinates in mm.
        status: Current status of this point.
        quality_score: Quality score from inspection (0-100).
        priority: Priority for scheduling (higher = more important).
        retry_count: Number of retry attempts.
        metadata: Additional data about this point.
    """
    id: str
    position: Tuple[float, float, float]
    status: str = "pending"  # pending, in_progress, completed, skipped, failed
    quality_score: float = 0.0
    priority: int = 0
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class SamplingAgent(BaseAgent):
    """Agent responsible for planning and managing sampling operations.

    Generates sampling points based on configurable strategies, evaluates
    the quality of completed samples, and dynamically adjusts the plan
    based on vision feedback.

    Attributes:
        state_machine_state: Current state in the sampling FSM.
        points: List of all sampling points.
        completed_points: List of completed sampling points.
        workspace_bounds: Bounds of the workspace in mm.
        strategy: Current sampling strategy.
        quality_threshold: Minimum quality score for a sample to be considered good.
    """

    def __init__(
        self,
        name: str = "sampling_agent",
        config: Optional[AgentConfig] = None,
    ) -> None:
        """Initialize the sampling agent.

        Args:
            name: Agent name.
            config: Agent configuration.
        """
        super().__init__(name, config)
        self.state_machine_state: SamplingState = SamplingState.IDLE
        self.points: List[SamplingPoint] = []
        self.completed_points: List[SamplingPoint] = []
        self.workspace_bounds: Dict[str, Tuple[float, float]] = {
            "x": (0.0, 500.0),
            "y": (0.0, 500.0),
            "z": (0.0, 300.0),
        }
        self.strategy: SamplingStrategy = SamplingStrategy.GRID
        self.quality_threshold: float = 70.0
        self._point_counter: int = 0

    async def initialize(self) -> bool:
        """Initialize the sampling agent."""
        self.log("Initializing sampling agent")
        self.state_machine_state = SamplingState.IDLE
        self.points.clear()
        self.completed_points.clear()
        return True

    @validate_state(required_keys=["task_id"])
    @log_execution
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Main processing method. Runs one step of the sampling state machine.

        Args:
            state: System state dict with at least 'task_id'.

        Returns:
            Updated state with sampling results.
        """
        # Extract task parameters
        task_id = state.get("task_id", "unknown")
        command = state.get("command", "plan")

        # State machine dispatch
        if self.state_machine_state == SamplingState.IDLE:
            self.state_machine_state = SamplingState.PLANNING

        if self.state_machine_state == SamplingState.PLANNING:
            await self._do_planning(state)
        elif self.state_machine_state == SamplingState.SAMPLING:
            await self._do_sampling(state)
        elif self.state_machine_state == SamplingState.EVALUATING:
            await self._do_evaluating(state)
        elif self.state_machine_state == SamplingState.DONE:
            state["sampling_complete"] = True
            state["sampling_result"] = self._build_result()
            return state

        # Update state with sampling data
        state["sampling_points"] = self._serialize_points()
        state["sampling_state"] = self.state_machine_state.value
        state["sampling_progress"] = self._compute_progress()

        return state

    async def validate(self, state: Dict[str, Any]) -> bool:
        """Validate sampling state.

        Args:
            state: Current system state.

        Returns:
            True if state is valid.
        """
        if "task_id" not in state:
            self.log("Missing task_id in state", 30)
            return False
        return True

    # =========================================================================
    # Planning
    # =========================================================================

    async def plan_sampling(
        self,
        workspace_bounds: Dict[str, Tuple[float, float]],
        object_locations: Optional[List[Tuple[float, float, float]]] = None,
        strategy: Optional[SamplingStrategy] = None,
    ) -> List[SamplingPoint]:
        """Generate sampling points based on the workspace and strategy.

        Args:
            workspace_bounds: Dict with 'x', 'y', 'z' bounds.
            object_locations: Optional list of known object positions.
            strategy: Sampling strategy to use.

        Returns:
            List of generated SamplingPoint objects.
        """
        self.workspace_bounds = workspace_bounds
        if strategy is not None:
            self.strategy = strategy

        if self.strategy == SamplingStrategy.GRID:
            points = await self.grid_sampling(workspace_bounds, spacing=50.0)
        elif self.strategy == SamplingStrategy.ADAPTIVE:
            points = await self.adaptive_sampling(
                workspace_bounds, initial_spacing=100.0, quality_threshold=self.quality_threshold,
            )
        elif self.strategy == SamplingStrategy.TARGETED:
            points = await self.targeted_sampling(object_locations or [])
        elif self.strategy == SamplingStrategy.STRATIFIED:
            points = await self._stratified_sampling(workspace_bounds, strata=4)
        else:  # RANDOM
            points = await self._random_sampling(workspace_bounds, count=25)

        self.points = points
        self.state_machine_state = SamplingState.SAMPLING
        self.log(f"Planned {len(points)} sampling points using {self.strategy.value} strategy")
        return points

    async def grid_sampling(
        self,
        bounds: Dict[str, Tuple[float, float]],
        spacing: float = 50.0,
    ) -> List[SamplingPoint]:
        """Generate uniform grid sampling points.

        Args:
            bounds: Workspace bounds.
            spacing: Grid spacing in mm.

        Returns:
            List of grid sampling points.
        """
        points = []
        x_min, x_max = bounds["x"]
        y_min, y_max = bounds["y"]
        z = (bounds["z"][0] + bounds["z"][1]) / 2  # Mid-height

        x = x_min
        while x <= x_max:
            y = y_min
            while y <= y_max:
                point_id = self._next_point_id()
                points.append(SamplingPoint(
                    id=point_id,
                    position=(x, y, z),
                ))
                y += spacing
            x += spacing

        return points

    async def adaptive_sampling(
        self,
        bounds: Dict[str, Tuple[float, float]],
        initial_spacing: float = 100.0,
        quality_threshold: float = 70.0,
    ) -> List[SamplingPoint]:
        """Generate points with adaptive refinement.

        Starts with coarse grid and refines around areas of interest
        based on quality feedback.

        Args:
            bounds: Workspace bounds.
            initial_spacing: Initial coarse grid spacing in mm.
            quality_threshold: Quality score below which refinement occurs.

        Returns:
            List of adaptive sampling points.
        """
        # Start with coarse grid
        points = await self.grid_sampling(bounds, initial_spacing)

        # Mark refinement points - areas where quality is expected to be lower
        # In practice, this would use historical data; here we use a heuristic
        refined = list(points)
        for pt in points:
            # Add refined points around each coarse point (simulated)
            px, py, pz = pt.position
            for dx in [-initial_spacing / 4, initial_spacing / 4]:
                for dy in [-initial_spacing / 4, initial_spacing / 4]:
                    nx, ny = px + dx, py + dy
                    if bounds["x"][0] <= nx <= bounds["x"][1] and bounds["y"][0] <= ny <= bounds["y"][1]:
                        refined.append(SamplingPoint(
                            id=f"{pt.id}_refined_{len(refined)}",
                            position=(nx, ny, pz),
                            priority=1,
                            metadata={"refined": True},
                        ))

        return refined

    async def targeted_sampling(
        self,
        target_locations: List[Tuple[float, float, float]],
    ) -> List[SamplingPoint]:
        """Generate sampling points at specific target locations.

        Args:
            target_locations: List of (x, y, z) target positions.

        Returns:
            List of targeted sampling points.
        """
        return [
            SamplingPoint(
                id=self._next_point_id(),
                position=loc,
                priority=2,
            )
            for loc in target_locations
        ]

    async def _stratified_sampling(
        self,
        bounds: Dict[str, Tuple[float, float]],
        strata: int = 4,
    ) -> List[SamplingPoint]:
        """Generate stratified sampling points.

        Divides the workspace into strata and samples within each.

        Args:
            bounds: Workspace bounds.
            strata: Number of strata per dimension.

        Returns:
            List of stratified sampling points.
        """
        points = []
        x_min, x_max = bounds["x"]
        y_min, y_max = bounds["y"]
        z = (bounds["z"][0] + bounds["z"][1]) / 2

        x_step = (x_max - x_min) / strata
        y_step = (y_max - y_min) / strata

        for i in range(strata):
            for j in range(strata):
                # Random point within each stratum
                x = x_min + i * x_step + x_step / 2
                y = y_min + j * y_step + y_step / 2
                points.append(SamplingPoint(
                    id=self._next_point_id(),
                    position=(x, y, z),
                    metadata={"stratum": (i, j)},
                ))

        return points

    async def _random_sampling(
        self,
        bounds: Dict[str, Tuple[float, float]],
        count: int = 25,
    ) -> List[SamplingPoint]:
        """Generate random sampling points within bounds.

        Args:
            bounds: Workspace bounds.
            count: Number of random points.

        Returns:
            List of random sampling points.
        """
        points = []
        for _ in range(count):
            x = random.uniform(bounds["x"][0], bounds["x"][1])
            y = random.uniform(bounds["y"][0], bounds["y"][1])
            z = random.uniform(bounds["z"][0], bounds["z"][1])
            points.append(SamplingPoint(
                id=self._next_point_id(),
                position=(x, y, z),
            ))
        return points

    # =========================================================================
    # Prioritization
    # =========================================================================

    def prioritize_targets(
        self,
        targets: List[SamplingPoint],
        criteria: Optional[List[str]] = None,
    ) -> List[SamplingPoint]:
        """Rank sampling points by importance.

        Args:
            targets: List of sampling points to prioritize.
            criteria: List of criteria to sort by (e.g., ['priority', 'quality_score']).

        Returns:
            Sorted list of sampling points (highest priority first).
        """
        if criteria is None:
            criteria = ["priority", "quality_score"]

        def sort_key(pt: SamplingPoint) -> Tuple:
            keys = []
            for c in criteria:
                if c == "priority":
                    keys.append(-pt.priority)
                elif c == "quality_score":
                    keys.append(pt.quality_score)
                elif c == "retry_count":
                    keys.append(pt.retry_count)
                else:
                    keys.append(0)
            return tuple(keys)

        return sorted(targets, key=sort_key)

    # =========================================================================
    # Evaluation
    # =========================================================================

    def evaluate_sampling_quality(self, completed_samples: List[SamplingPoint]) -> Dict[str, Any]:
        """Analyze the quality of completed samples.

        Computes coverage metrics, uniformity, and quality statistics.

        Args:
            completed_samples: List of completed sampling points.

        Returns:
            Dict with coverage, uniformity, and quality metrics.
        """
        if not completed_samples:
            return {"coverage": 0.0, "uniformity": 0.0, "avg_quality": 0.0, "pass_rate": 0.0}

        # Coverage: fraction of workspace covered
        coverage = self._compute_coverage(completed_samples)

        # Uniformity: spatial distribution metric
        uniformity = self._compute_uniformity(completed_samples)

        # Quality statistics
        scores = [s.quality_score for s in completed_samples]
        avg_quality = sum(scores) / len(scores)
        pass_rate = sum(1 for s in scores if s >= self.quality_threshold) / len(scores)

        return {
            "coverage": round(coverage, 3),
            "uniformity": round(uniformity, 3),
            "avg_quality": round(avg_quality, 1),
            "pass_rate": round(pass_rate, 3),
            "total_samples": len(completed_samples),
            "passed_samples": sum(1 for s in scores if s >= self.quality_threshold),
        }

    def handle_vision_result(self, result: Dict[str, Any]) -> None:
        """Update the sampling plan based on a vision-detected robot target.

        消费的是已经过手眼标定转换为机器人基座系的位姿 (由 orchestrator 通过
        vision_target_robot 传入, 含 'position' 键, 单位 mm), 不再在此处做
        粗略的像素→mm 线性外推, 保证坐标与运动链路一致。

        Args:
            result: 机器人基座系目标位姿 dict (含 'position' (x, y, z) mm)。
        """
        position = result.get("position")
        if not position:
            return

        # Add the vision-detected target as a high-priority sampling point
        new_point = SamplingPoint(
            id=self._next_point_id(),
            position=tuple(position),
            priority=3,  # High priority for vision-detected targets
            metadata={"source": "vision"},
        )
        self.points.append(new_point)
        self.log(
            f"Added vision-detected point at ({position[0]:.1f}, {position[1]:.1f}, {position[2]:.1f})"
        )

    # =========================================================================
    # State Machine
    # =========================================================================

    async def _do_planning(self, state: Dict[str, Any]) -> None:
        """Execute the PLANNING state of the state machine."""
        bounds = state.get("workspace_bounds", self.workspace_bounds)
        strategy_str = state.get("sampling_strategy", "grid")
        try:
            strategy = SamplingStrategy(strategy_str)
        except ValueError:
            strategy = SamplingStrategy.GRID

        object_locations = state.get("object_locations")
        await self.plan_sampling(bounds, object_locations, strategy)
        self.state_machine_state = SamplingState.SAMPLING

    async def _do_sampling(self, state: Dict[str, Any]) -> None:
        """Execute the SAMPLING state of the state machine."""
        # Fix: also handle in_progress points that might be stuck
        # If any point has been in_progress for too long, reset it to pending
        stuck_points = [p for p in self.points if p.status == "in_progress" and p.retry_count >= 3]
        for p in stuck_points:
            p.status = "failed"
            self.log(f"Point {p.id} stuck in_progress, marking as failed after {p.retry_count} retries", 30)

        # Get the next pending point
        pending = [p for p in self.points if p.status == "pending"]
        if not pending:
            self.state_machine_state = SamplingState.EVALUATING
            return

        # Prioritize and select next point
        prioritized = self.prioritize_targets(pending)
        next_point = prioritized[0]
        next_point.status = "in_progress"
        next_point.retry_count += 1  # Track retry attempts for timeout detection

        # Set the current target in state
        state["current_target"] = {
            "id": next_point.id,
            "position": next_point.position,
            "priority": next_point.priority,
        }
        state["pending_count"] = len(pending) - 1

        # Check if a vision result needs to be processed
        # 使用已经过手眼标定转换的机器人基座系目标位置 (由 orchestrator 生成),
        # 而不是在采样侧再做粗略的像素→mm 近似 (那是坐标断链的根源)。
        vision_robot = state.get("vision_target_robot")
        if vision_robot and vision_robot.get("position"):
            self.handle_vision_result(vision_robot)

    async def _do_evaluating(self, state: Dict[str, Any]) -> None:
        """Execute the EVALUATING state of the state machine."""
        # Mark the current target as completed
        current_target = state.get("current_target")
        if current_target:
            for pt in self.points:
                if pt.id == current_target.get("id"):
                    pt.status = "completed"
                    pt.quality_score = state.get("quality_score", 0.0)
                    self.completed_points.append(pt)
                    break

        # Evaluate overall quality
        evaluation = self.evaluate_sampling_quality(self.completed_points)
        state["evaluation"] = evaluation

        # Check if we should continue or finish
        pending = [p for p in self.points if p.status not in ("completed", "skipped", "failed")]
        if not pending:
            self.state_machine_state = SamplingState.DONE
        elif evaluation.get("coverage", 0) >= 0.95 and evaluation.get("pass_rate", 0) >= 0.9:
            self.state_machine_state = SamplingState.DONE
        else:
            # Back to sampling for more points
            self.state_machine_state = SamplingState.SAMPLING

    # =========================================================================
    # Helpers
    # =========================================================================

    def _next_point_id(self) -> str:
        """Generate a unique point ID."""
        self._point_counter += 1
        return f"SP_{self._point_counter:04d}"

    def _compute_coverage(self, samples: List[SamplingPoint]) -> float:
        """Compute the fraction of workspace area covered by samples.

        Args:
            samples: List of completed sampling points.

        Returns:
            Coverage fraction (0.0 to 1.0).
        """
        if not samples:
            return 0.0
        x_range = self.workspace_bounds["x"][1] - self.workspace_bounds["x"][0]
        y_range = self.workspace_bounds["y"][1] - self.workspace_bounds["y"][0]
        total_area = x_range * y_range
        if total_area <= 0:
            return 0.0
        # Simple approximation: each sample covers a radius
        sample_radius = 30.0  # mm
        covered_area = min(len(samples) * math.pi * sample_radius ** 2, total_area)
        return covered_area / total_area

    def _compute_uniformity(self, samples: List[SamplingPoint]) -> float:
        """Compute a spatial uniformity metric.

        Lower variance in distances between neighboring points = higher uniformity.

        Args:
            samples: List of completed sampling points.

        Returns:
            Uniformity score (0.0 to 1.0, 1.0 = perfectly uniform).
        """
        if len(samples) < 2:
            return 1.0
        positions = np.array([s.position[:2] for s in samples])
        # Compute pairwise distances
        diffs = positions[:, np.newaxis, :] - positions[np.newaxis, :, :]
        distances = np.sqrt(np.sum(diffs ** 2, axis=2))
        # Get nearest neighbor distances
        np.fill_diagonal(distances, np.inf)
        nn_distances = np.min(distances, axis=1)
        # Uniformity = 1 - (std / mean)
        mean_d = np.mean(nn_distances)
        if mean_d == 0:
            return 1.0
        std_d = np.std(nn_distances)
        uniformity = max(0.0, 1.0 - (std_d / mean_d))
        return float(uniformity)

    def _compute_progress(self) -> Dict[str, Any]:
        """Compute the current progress of the sampling task.

        Returns:
            Dict with progress metrics.
        """
        total = len(self.points)
        completed = len([p for p in self.points if p.status == "completed"])
        failed = len([p for p in self.points if p.status == "failed"])
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "pending": total - completed - failed,
            "percent": round(completed / total * 100, 1) if total > 0 else 0.0,
        }

    def _serialize_points(self) -> List[Dict[str, Any]]:
        """Serialize sampling points to JSON-compatible dicts.

        Returns:
            List of serialized point dicts.
        """
        return [
            {
                "id": pt.id,
                "position": list(pt.position),
                "status": pt.status,
                "quality_score": pt.quality_score,
                "priority": pt.priority,
                "retry_count": pt.retry_count,
                "metadata": pt.metadata,
            }
            for pt in self.points
        ]

    def _build_result(self) -> Dict[str, Any]:
        """Build the final sampling result.

        Returns:
            Dict with final sampling results.
        """
        return {
            "strategy": self.strategy.value,
            "total_points": len(self.points),
            "completed_points": len(self.completed_points),
            "evaluation": self.evaluate_sampling_quality(self.completed_points),
            "points": self._serialize_points(),
        }