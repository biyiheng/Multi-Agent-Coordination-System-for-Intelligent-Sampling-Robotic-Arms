"""
Sampling Strategy Definitions for the Intelligent Sampling Robotic Arm.

Defines the sampling strategy interface and concrete implementations
for various sampling strategies: grid, adaptive, targeted, random,
and stratified. Provides factory methods and coverage metrics.

Each strategy generates a list of sampling points within the workspace
bounds using an algorithm appropriate for the application.
"""

import math
import time
import uuid
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


class SamplingStrategyType(Enum):
    """Available sampling strategy types."""
    GRID = "grid"
    ADAPTIVE = "adaptive"
    TARGETED = "targeted"
    RANDOM = "random"
    STRATIFIED = "stratified"


@dataclass
class SamplingPoint:
    """A single point to be sampled in the workspace.

    Attributes:
        id: Unique identifier.
        position: (x, y, z) in mm.
        priority: Scheduling priority (higher = execute first).
        metadata: Additional strategy-specific data.
    """
    id: str
    position: Tuple[float, float, float]
    priority: int = 0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class SamplingTask:
    """A complete sampling task with strategy and bounds.

    Attributes:
        task_id: Unique task identifier.
        strategy: Sampling strategy type to use.
        bounds: Workspace bounds dict with 'x', 'y', 'z' keys.
        parameters: Additional strategy parameters.
        status: Current task status.
        created_at: Timestamp of creation.
        completed_at: Timestamp of completion.
        results: List of sampling results.
    """
    task_id: str
    strategy: SamplingStrategyType
    bounds: Dict[str, Tuple[float, float]]
    parameters: Dict[str, Any]
    status: str = "pending"
    created_at: float = 0.0
    completed_at: Optional[float] = None
    results: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()
        if self.results is None:
            self.results = []


# =============================================================================
# Abstract Base Strategy
# =============================================================================

class BaseSamplingStrategy(ABC):
    """Abstract base class for sampling strategies.

    All sampling strategies must implement the generate_points method.
    """

    @abstractmethod
    def generate_points(
        self,
        bounds: Dict[str, Tuple[float, float]],
        params: Optional[Dict[str, Any]] = None,
    ) -> List[SamplingPoint]:
        """Generate a list of sampling points within the given bounds.

        Args:
            bounds: Dict with 'x', 'y', 'z' tuples (min, max) in mm.
            params: Optional strategy-specific parameters.

        Returns:
            List of SamplingPoint objects.
        """
        ...

    @property
    @abstractmethod
    def strategy_type(self) -> SamplingStrategyType:
        """Get the strategy type enum."""
        ...

    def get_default_params(self) -> Dict[str, Any]:
        """Get default parameters for this strategy.

        Returns:
            Dict of parameter name to default value.
        """
        return {}


# =============================================================================
# Concrete Strategies
# =============================================================================

class GridSamplingStrategy(BaseSamplingStrategy):
    """Uniform grid sampling strategy.

    Places points on a regular grid with configurable spacing. The grid
    is aligned to the workspace bounds and covers the full area.

    Parameters:
        spacing: Grid spacing in mm (default 50.0).
        z_height: Fixed Z height for all points (default: mid-height).
        offset_x: X offset for grid alignment (default 0.0).
        offset_y: Y offset for grid alignment (default 0.0).
    """

    @property
    def strategy_type(self) -> SamplingStrategyType:
        return SamplingStrategyType.GRID

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "spacing": 50.0,
            "z_height": None,
            "offset_x": 0.0,
            "offset_y": 0.0,
        }

    def generate_points(
        self,
        bounds: Dict[str, Tuple[float, float]],
        params: Optional[Dict[str, Any]] = None,
    ) -> List[SamplingPoint]:
        """Generate grid sampling points.

        Args:
            bounds: Workspace bounds.
            params: Optional parameters (spacing, z_height, offsets).

        Returns:
            List of grid sampling points.
        """
        p = {**self.get_default_params(), **(params or {})}
        spacing = p["spacing"]
        offset_x = p["offset_x"]
        offset_y = p["offset_y"]

        x_min, x_max = bounds["x"]
        y_min, y_max = bounds["y"]
        z_min, z_max = bounds["z"]

        z_height = p["z_height"]
        if z_height is None:
            z_height = (z_min + z_max) / 2.0

        points = []
        point_id = 0

        # Apply offset
        x_start = x_min + offset_x
        y_start = y_min + offset_y

        x = x_start
        while x <= x_max:
            y = y_start
            while y <= y_max:
                point_id += 1
                points.append(SamplingPoint(
                    id=f"grid_{point_id:04d}",
                    position=(round(x, 1), round(y, 1), round(z_height, 1)),
                    metadata={"strategy": "grid", "spacing": spacing},
                ))
                y += spacing
            x += spacing

        return points


class AdaptiveSamplingStrategy(BaseSamplingStrategy):
    """Adaptive sampling strategy with quality-based refinement.

    Starts with a coarse grid and refines areas where quality is expected
    to be lower. Uses a multi-resolution approach.

    Parameters:
        initial_spacing: Coarse grid spacing in mm (default 100.0).
        refinement_levels: Number of refinement levels (default 2).
        refinement_factor: Spacing reduction per level (default 2.0).
        quality_threshold: Score below which refinement occurs (default 70.0).
    """

    @property
    def strategy_type(self) -> SamplingStrategyType:
        return SamplingStrategyType.ADAPTIVE

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "initial_spacing": 100.0,
            "refinement_levels": 2,
            "refinement_factor": 2.0,
            "quality_threshold": 70.0,
            "z_height": None,
        }

    def generate_points(
        self,
        bounds: Dict[str, Tuple[float, float]],
        params: Optional[Dict[str, Any]] = None,
    ) -> List[SamplingPoint]:
        """Generate adaptive sampling points with multi-level refinement.

        Args:
            bounds: Workspace bounds.
            params: Optional parameters.

        Returns:
            List of adaptive sampling points.
        """
        p = {**self.get_default_params(), **(params or {})}
        initial_spacing = p["initial_spacing"]
        refinement_levels = p["refinement_levels"]
        refinement_factor = p["refinement_factor"]

        z_min, z_max = bounds["z"]
        z_height = p["z_height"] or ((z_min + z_max) / 2.0)

        all_points: List[SamplingPoint] = []
        point_id = 0

        # Generate coarse grid
        coarse = GridSamplingStrategy().generate_points(bounds, {
            "spacing": initial_spacing,
            "z_height": z_height,
        })
        all_points.extend(coarse)

        # Generate refinement points around each coarse point
        for level in range(1, refinement_levels + 1):
            spacing = initial_spacing / (refinement_factor ** level)
            for base_point in coarse:
                bx, by, bz = base_point.position
                for dx in [-spacing, 0, spacing]:
                    for dy in [-spacing, 0, spacing]:
                        if dx == 0 and dy == 0:
                            continue
                        nx, ny = bx + dx, by + dy
                        if bounds["x"][0] <= nx <= bounds["x"][1] and bounds["y"][0] <= ny <= bounds["y"][1]:
                            point_id += 1
                            all_points.append(SamplingPoint(
                                id=f"adapt_{point_id:04d}",
                                position=(round(nx, 1), round(ny, 1), round(z_height, 1)),
                                priority=level,
                                metadata={
                                    "strategy": "adaptive",
                                    "level": level,
                                    "parent": base_point.id,
                                },
                            ))

        return all_points


class TargetedSamplingStrategy(BaseSamplingStrategy):
    """Targeted sampling strategy for specific locations.

    Samples only at explicitly provided target locations, useful for
    sampling known objects or regions of interest.

    Parameters:
        targets: List of (x, y, z) target positions.
    """

    @property
    def strategy_type(self) -> SamplingStrategyType:
        return SamplingStrategyType.TARGETED

    def get_default_params(self) -> Dict[str, Any]:
        return {"targets": []}

    def generate_points(
        self,
        bounds: Dict[str, Tuple[float, float]],
        params: Optional[Dict[str, Any]] = None,
    ) -> List[SamplingPoint]:
        """Generate points at specific target locations.

        Args:
            bounds: Workspace bounds (used for validation).
            params: Must contain 'targets' list of (x, y, z) tuples.

        Returns:
            List of targeted sampling points.
        """
        p = {**self.get_default_params(), **(params or {})}
        targets = p.get("targets", [])

        points = []
        for i, target in enumerate(targets):
            x, y, z = target
            # Validate within bounds
            if (
                bounds["x"][0] <= x <= bounds["x"][1]
                and bounds["y"][0] <= y <= bounds["y"][1]
                and bounds["z"][0] <= z <= bounds["z"][1]
            ):
                points.append(SamplingPoint(
                    id=f"target_{i + 1:04d}",
                    position=(round(x, 1), round(y, 1), round(z, 1)),
                    priority=2,
                    metadata={"strategy": "targeted", "index": i},
                ))

        return points


class RandomSamplingStrategy(BaseSamplingStrategy):
    """Random sampling strategy.

    Generates uniformly distributed random points within the workspace.
    Uses a fixed seed for reproducibility if specified.

    Parameters:
        count: Number of random points (default 25).
        seed: Random seed for reproducibility (default None).
        z_height: Fixed Z height (default: mid-height).
    """

    @property
    def strategy_type(self) -> SamplingStrategyType:
        return SamplingStrategyType.RANDOM

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "count": 25,
            "seed": None,
            "z_height": None,
        }

    def generate_points(
        self,
        bounds: Dict[str, Tuple[float, float]],
        params: Optional[Dict[str, Any]] = None,
    ) -> List[SamplingPoint]:
        """Generate random sampling points.

        Args:
            bounds: Workspace bounds.
            params: Optional parameters (count, seed, z_height).

        Returns:
            List of random sampling points.
        """
        import random as rand_module

        p = {**self.get_default_params(), **(params or {})}
        count = p["count"]
        seed = p["seed"]

        z_min, z_max = bounds["z"]
        z_height = p["z_height"] or ((z_min + z_max) / 2.0)

        rng = rand_module.Random(seed) if seed is not None else rand_module.Random()

        points = []
        for i in range(count):
            x = rng.uniform(bounds["x"][0], bounds["x"][1])
            y = rng.uniform(bounds["y"][0], bounds["y"][1])
            z = rng.uniform(bounds["z"][0], bounds["z"][1]) if z_height is None else z_height

            points.append(SamplingPoint(
                id=f"rand_{i + 1:04d}",
                position=(round(x, 1), round(y, 1), round(z, 1)),
                metadata={"strategy": "random", "index": i},
            ))

        return points


class StratifiedSamplingStrategy(BaseSamplingStrategy):
    """Stratified sampling strategy.

    Divides the workspace into strata (sub-regions) and samples within each
    stratum. Ensures coverage across the entire workspace.

    Parameters:
        strata_x: Number of strata along X axis (default 4).
        strata_y: Number of strata along Y axis (default 4).
        points_per_stratum: Points per stratum (default 1).
        z_height: Fixed Z height (default: mid-height).
    """

    @property
    def strategy_type(self) -> SamplingStrategyType:
        return SamplingStrategyType.STRATIFIED

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "strata_x": 4,
            "strata_y": 4,
            "points_per_stratum": 1,
            "z_height": None,
            "seed": None,
        }

    def generate_points(
        self,
        bounds: Dict[str, Tuple[float, float]],
        params: Optional[Dict[str, Any]] = None,
    ) -> List[SamplingPoint]:
        """Generate stratified sampling points.

        Args:
            bounds: Workspace bounds.
            params: Optional parameters.

        Returns:
            List of stratified sampling points.
        """
        import random as rand_module

        p = {**self.get_default_params(), **(params or {})}
        strata_x = p["strata_x"]
        strata_y = p["strata_y"]
        points_per = p["points_per_stratum"]
        seed = p["seed"]

        z_min, z_max = bounds["z"]
        z_height = p["z_height"] or ((z_min + z_max) / 2.0)

        x_min, x_max = bounds["x"]
        y_min, y_max = bounds["y"]
        x_step = (x_max - x_min) / strata_x
        y_step = (y_max - y_min) / strata_y

        rng = rand_module.Random(seed) if seed is not None else rand_module.Random()

        points = []
        point_id = 0

        for ix in range(strata_x):
            for iy in range(strata_y):
                for k in range(points_per):
                    # Random point within the stratum
                    x = rng.uniform(x_min + ix * x_step, x_min + (ix + 1) * x_step)
                    y = rng.uniform(y_min + iy * y_step, y_min + (iy + 1) * y_step)
                    z = z_height

                    point_id += 1
                    points.append(SamplingPoint(
                        id=f"strat_{point_id:04d}",
                        position=(round(x, 1), round(y, 1), round(z, 1)),
                        metadata={
                            "strategy": "stratified",
                            "stratum": (ix, iy),
                            "stratum_index": k,
                        },
                    ))

        return points


# =============================================================================
# Strategy Factory
# =============================================================================

def get_strategy(strategy_type: SamplingStrategyType) -> BaseSamplingStrategy:
    """Factory method to create a strategy instance by type.

    Args:
        strategy_type: The strategy type enum value.

    Returns:
        A concrete strategy instance.

    Raises:
        ValueError: If the strategy type is unknown.
    """
    strategies: Dict[SamplingStrategyType, BaseSamplingStrategy] = {
        SamplingStrategyType.GRID: GridSamplingStrategy(),
        SamplingStrategyType.ADAPTIVE: AdaptiveSamplingStrategy(),
        SamplingStrategyType.TARGETED: TargetedSamplingStrategy(),
        SamplingStrategyType.RANDOM: RandomSamplingStrategy(),
        SamplingStrategyType.STRATIFIED: StratifiedSamplingStrategy(),
    }

    if strategy_type not in strategies:
        raise ValueError(f"Unknown strategy type: {strategy_type}")

    return strategies[strategy_type]


# =============================================================================
# Coverage and Uniformity Metrics
# =============================================================================

def compute_coverage(
    sample_points: List[SamplingPoint],
    bounds: Dict[str, Tuple[float, float]],
    sample_radius_mm: float = 30.0,
) -> float:
    """Compute the fraction of workspace area covered by sampling points.

    Uses a simple circle-coverage model: each point covers a circular
    area of the given radius.

    Args:
        sample_points: List of sampling points.
        bounds: Workspace bounds.
        sample_radius_mm: Effective coverage radius per point.

    Returns:
        Coverage fraction (0.0 to 1.0).
    """
    if not sample_points:
        return 0.0

    x_range = bounds["x"][1] - bounds["x"][0]
    y_range = bounds["y"][1] - bounds["y"][0]
    total_area = x_range * y_range

    if total_area <= 0:
        return 0.0

    # Simple model: each point covers a circle of given radius
    covered_area = min(len(sample_points) * math.pi * sample_radius_mm ** 2, total_area)
    return covered_area / total_area


def compute_coverage_grid(
    sample_points: List[SamplingPoint],
    bounds: Dict[str, Tuple[float, float]],
    grid_resolution_mm: float = 10.0,
    sample_radius_mm: float = 30.0,
) -> float:
    """Compute coverage using a fine grid (more accurate but slower).

    Discretizes the workspace into a fine grid and counts cells within
    the coverage radius of any sampling point.

    Args:
        sample_points: List of sampling points.
        bounds: Workspace bounds.
        grid_resolution_mm: Grid cell size.
        sample_radius_mm: Coverage radius per point.

    Returns:
        Coverage fraction.
    """
    if not sample_points:
        return 0.0

    x_min, x_max = bounds["x"]
    y_min, y_max = bounds["y"]

    x_cells = int((x_max - x_min) / grid_resolution_mm)
    y_cells = int((y_max - y_min) / grid_resolution_mm)

    if x_cells <= 0 or y_cells <= 0:
        return 0.0

    # Build a coverage grid
    covered = np.zeros((y_cells, x_cells), dtype=bool)

    for point in sample_points:
        px, py, _ = point.position
        px_idx = int((px - x_min) / grid_resolution_mm)
        py_idx = int((py - y_min) / grid_resolution_mm)
        radius_cells = int(sample_radius_mm / grid_resolution_mm)

        for dy in range(-radius_cells, radius_cells + 1):
            for dx in range(-radius_cells, radius_cells + 1):
                if dx**2 + dy**2 <= radius_cells**2:
                    cx = px_idx + dx
                    cy = py_idx + dy
                    if 0 <= cx < x_cells and 0 <= cy < y_cells:
                        covered[cy, cx] = True

    return float(np.sum(covered)) / (x_cells * y_cells)


def compute_uniformity(sample_points: List[SamplingPoint]) -> float:
    """Compute a spatial uniformity metric for sampling points.

    Measures how evenly distributed the points are. 1.0 = perfectly
    uniform (regular grid), lower values = more clustered.

    Uses the coefficient of variation of nearest-neighbor distances.

    Args:
        sample_points: List of sampling points.

    Returns:
        Uniformity score (0.0 to 1.0).
    """
    if len(sample_points) < 2:
        return 1.0

    positions = np.array([p.position[:2] for p in sample_points])

    # Compute pairwise distances
    diffs = positions[:, np.newaxis, :] - positions[np.newaxis, :, :]
    distances = np.sqrt(np.sum(diffs ** 2, axis=2))

    # Get nearest neighbor distances
    np.fill_diagonal(distances, np.inf)
    nn_distances = np.min(distances, axis=1)

    mean_d = np.mean(nn_distances)
    if mean_d == 0:
        return 1.0

    std_d = np.std(nn_distances)
    # Coefficient of variation: lower = more uniform
    cv = std_d / mean_d

    # Map to uniformity score: 1.0 = perfect uniformity
    uniformity = max(0.0, 1.0 - cv)
    return float(uniformity)


def compute_spread(sample_points: List[SamplingPoint]) -> Dict[str, float]:
    """Compute the spatial spread of sampling points.

    Args:
        sample_points: List of sampling points.

    Returns:
        Dict with 'x_range', 'y_range', 'z_range', 'centroid', 'std_dev'.
    """
    if not sample_points:
        return {"x_range": 0, "y_range": 0, "z_range": 0, "centroid": (0, 0, 0), "std_dev": 0}

    positions = np.array([p.position for p in sample_points])
    centroid = np.mean(positions, axis=0)
    ranges = np.max(positions, axis=0) - np.min(positions, axis=0)
    std_dev = float(np.mean(np.std(positions, axis=0)))

    return {
        "x_range": float(ranges[0]),
        "y_range": float(ranges[1]),
        "z_range": float(ranges[2]),
        "centroid": tuple(float(c) for c in centroid),
        "std_dev": round(std_dev, 2),
    }