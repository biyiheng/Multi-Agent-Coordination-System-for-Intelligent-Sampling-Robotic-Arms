"""
Sampling Optimization Algorithms for the Intelligent Sampling Robotic Arm.

Provides optimization utilities for balancing coverage vs. time,
adapting strategies based on historical results, recommending optimal
strategies, and evaluating multi-criteria tradeoffs.

Uses heuristic and statistical methods to optimize the sampling process
without requiring a full ML pipeline.
"""

import math
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .strategy import (
    SamplingPoint,
    SamplingStrategyType,
    BaseSamplingStrategy,
    get_strategy,
    compute_coverage,
    compute_uniformity,
    compute_spread,
)


class SamplingOptimizer:
    """Optimizes sampling parameters and strategy selection.

    Balances coverage quality against time constraints, learns from
    previous sampling results, and recommends strategies based on
    task parameters.

    Attributes:
        history: Record of previous sampling results.
        strategy_performance: Performance metrics per strategy.
        time_budget_s: Default time budget for sampling.
    """

    def __init__(self, time_budget_s: float = 300.0) -> None:
        """Initialize the sampling optimizer.

        Args:
            time_budget_s: Default time budget in seconds.
        """
        self.time_budget_s: float = time_budget_s
        self.history: List[Dict[str, Any]] = []
        self.strategy_performance: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.max_history: int = 1000

    # =========================================================================
    # Grid Spacing Optimization
    # =========================================================================

    def optimize_grid_spacing(
        self,
        bounds: Dict[str, Tuple[float, float]],
        time_budget: Optional[float] = None,
        min_spacing: float = 10.0,
        max_spacing: float = 200.0,
    ) -> Dict[str, Any]:
        """Find the optimal grid spacing for a given time budget.

        Balances finer spacing (more points = better coverage) against
        the time required to visit all points.

        Args:
            bounds: Workspace bounds.
            time_budget: Available time in seconds.
            min_spacing: Minimum grid spacing in mm.
            max_spacing: Maximum grid spacing in mm.

        Returns:
            Dict with optimal spacing, coverage, and point count.
        """
        budget = time_budget if time_budget is not None else self.time_budget_s
        x_range = bounds["x"][1] - bounds["x"][0]
        y_range = bounds["y"][1] - bounds["y"][0]

        # Estimated time per point (seconds)
        time_per_point = 7.0  # Approximate: approach + sample + inspect + place

        def estimate_points(spacing: float) -> int:
            nx = math.ceil(x_range / spacing) + 1
            ny = math.ceil(y_range / spacing) + 1
            return nx * ny

        def estimate_time(spacing: float) -> float:
            return estimate_points(spacing) * time_per_point

        # Binary search for optimal spacing
        best_spacing = max_spacing
        best_coverage = 0.0

        for spacing in np.linspace(min_spacing, max_spacing, 50):
            est_time = estimate_time(spacing)
            if est_time <= budget:
                points = estimate_points(spacing)
                # Coverage estimate (simplified)
                area_per_point = math.pi * 30.0 ** 2  # 30mm radius
                total_area = x_range * y_range
                coverage = min(1.0, points * area_per_point / total_area)

                if coverage > best_coverage:
                    best_coverage = coverage
                    best_spacing = spacing

        return {
            "optimal_spacing_mm": round(best_spacing, 1),
            "estimated_coverage": round(best_coverage, 3),
            "estimated_points": estimate_points(best_spacing),
            "estimated_time_s": round(estimate_time(best_spacing), 1),
            "time_budget_s": budget,
        }

    # =========================================================================
    # Coverage vs. Time Balancing
    # =========================================================================

    def balance_coverage_vs_time(
        self,
        points: List[SamplingPoint],
        time_limit: float,
        points_per_second: float = 0.15,
    ) -> Dict[str, Any]:
        """Find the Pareto-optimal tradeoff between coverage and time.

        Given a set of sampling points, determines which subset to
        visit to maximize coverage within the time limit.

        Args:
            points: All available sampling points.
            time_limit: Maximum allowed time in seconds.
            points_per_second: Points that can be sampled per second.

        Returns:
            Dict with selected points, coverage, time, and tradeoff metrics.
        """
        if not points:
            return {"selected_points": [], "coverage": 0.0, "time_s": 0.0}

        max_points = int(time_limit * points_per_second)

        if max_points >= len(points):
            return {
                "selected_points": points,
                "coverage": 1.0,
                "time_s": len(points) / points_per_second,
                "all_points_covered": True,
            }

        # Select highest priority points first
        sorted_points = sorted(points, key=lambda p: p.priority, reverse=True)
        selected = sorted_points[:max_points]

        return {
            "selected_points": selected,
            "coverage": len(selected) / len(points),
            "time_s": round(len(selected) / points_per_second, 1),
            "total_points": len(points),
            "selected_count": len(selected),
            "all_points_covered": False,
        }

    # =========================================================================
    # Adaptive Learning
    # =========================================================================

    def adapt_to_previous_results(
        self,
        history: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Learn from past sampling results to improve future plans.

        Analyzes historical data to identify patterns in quality scores,
        spatial distributions, and defect locations.

        Args:
            history: List of previous sampling result dicts.

        Returns:
            Dict with learned insights and recommendations.
        """
        if not history:
            return {"insights": [], "recommendations": []}

        insights = []

        # Analyze quality score trends
        scores = [h.get("quality_score", 0) for h in history if "quality_score" in h]
        if scores:
            mean_score = np.mean(scores)
            std_score = np.std(scores)

            if mean_score < 60:
                insights.append("Overall quality is low; consider adjusting thresholds")
            if std_score > 20:
                insights.append("High quality variability; check process consistency")

            # Trend analysis
            if len(scores) >= 10:
                first_half = np.mean(scores[:len(scores)//2])
                second_half = np.mean(scores[len(scores)//2:])
                if second_half < first_half - 5:
                    insights.append("Quality is declining; investigate root cause")

        # Analyze defect patterns
        defect_locations = []
        for h in history:
            for defect in h.get("defects", []):
                pos = defect.get("position")
                if pos:
                    defect_locations.append(pos)

        if defect_locations:
            locs = np.array(defect_locations)
            centroid = np.mean(locs, axis=0)
            spread = np.std(locs, axis=0)
            if np.max(spread) < 50:
                insights.append(f"Defects cluster near ({centroid[0]:.1f}, {centroid[1]:.1f})")

        # Analyze strategy performance
        for strategy_name, perf_list in self.strategy_performance.items():
            if len(perf_list) >= 3:
                avg_cov = np.mean([p.get("coverage", 0) for p in perf_list])
                if avg_cov < 0.5:
                    insights.append(f"Strategy '{strategy_name}' has low coverage ({avg_cov:.1%})")

        # Generate recommendations
        recommendations = []
        if scores and np.mean(scores) < 70:
            recommendations.append("Increase sampling density in low-quality areas")
        if len(history) < 5:
            recommendations.append("Insufficient data for reliable recommendations")
        else:
            recommendations.append("Consider adaptive sampling for better efficiency")

        return {
            "insights": insights,
            "recommendations": recommendations,
            "data_points": len(history),
        }

    # =========================================================================
    # Strategy Recommendation
    # =========================================================================

    def recommend_strategy(self, task_params: Dict[str, Any]) -> Dict[str, Any]:
        """Recommend the best sampling strategy based on task parameters.

        Uses heuristic rules and past performance data to recommend
        the most appropriate strategy.

        Args:
            task_params: Dict with task parameters:
                - workspace_size_mm: (width, height) in mm
                - time_budget_s: Available time
                - has_targets: Whether specific targets are known
                - precision_required: Whether high precision is needed
                - previous_quality: Average quality from previous runs

        Returns:
            Dict with recommended strategy, rationale, and scores.
        """
        workspace_size = task_params.get("workspace_size_mm", (500, 500))
        time_budget = task_params.get("time_budget_s", self.time_budget_s)
        has_targets = task_params.get("has_targets", False)
        precision = task_params.get("precision_required", False)
        prev_quality = task_params.get("previous_quality", 80.0)

        area = workspace_size[0] * workspace_size[1]
        scores: Dict[SamplingStrategyType, float] = {}

        # Score each strategy based on heuristics
        # Grid: good for large, uniform areas with moderate time
        grid_score = 0.7
        if area > 250000:  # Large workspace
            grid_score += 0.1
        if precision:
            grid_score += 0.1
        if time_budget > 600:
            grid_score += 0.1
        scores[SamplingStrategyType.GRID] = grid_score

        # Adaptive: good when quality is variable or unknown
        adaptive_score = 0.5
        if prev_quality < 80:
            adaptive_score += 0.3
        if time_budget > 300:
            adaptive_score += 0.1
        if precision:
            adaptive_score += 0.1
        scores[SamplingStrategyType.ADAPTIVE] = adaptive_score

        # Targeted: best when specific targets are known
        targeted_score = 0.3
        if has_targets:
            targeted_score += 0.6
        if time_budget < 60:
            targeted_score += 0.1
        scores[SamplingStrategyType.TARGETED] = targeted_score

        # Stratified: good for heterogeneous areas
        stratified_score = 0.5
        if area > 100000:
            stratified_score += 0.2
        if time_budget > 300:
            stratified_score += 0.1
        scores[SamplingStrategyType.STRATIFIED] = stratified_score

        # Random: good for exploration or when nothing is known
        random_score = 0.3
        if prev_quality < 50:
            random_score += 0.2
        if not has_targets and time_budget < 120:
            random_score += 0.2
        scores[SamplingStrategyType.RANDOM] = random_score

        # Find the best
        best_strategy = max(scores, key=scores.get)
        best_score = scores[best_strategy]

        # Build rationale
        rationale = []
        if best_strategy == SamplingStrategyType.GRID:
            rationale.append("Uniform grid provides systematic coverage")
        elif best_strategy == SamplingStrategyType.ADAPTIVE:
            rationale.append("Adaptive strategy refines sampling in critical areas")
        elif best_strategy == SamplingStrategyType.TARGETED:
            rationale.append("Targeted sampling focuses on known locations")
        elif best_strategy == SamplingStrategyType.STRATIFIED:
            rationale.append("Stratified sampling ensures balanced coverage")
        else:
            rationale.append("Random sampling provides exploratory coverage")

        return {
            "recommended_strategy": best_strategy.value,
            "confidence": round(best_score, 3),
            "all_scores": {k.value: round(v, 3) for k, v in scores.items()},
            "rationale": rationale,
        }

    # =========================================================================
    # Tradeoff Evaluation
    # =========================================================================

    def evaluate_tradeoffs(
        self,
        options: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Evaluate multiple sampling options using multi-criteria decision.

        Each option is evaluated on: coverage, time, uniformity, cost.
        Returns a ranked list of options.

        Args:
            options: List of option dicts, each with:
                - name: Option name
                - coverage: Estimated coverage (0-1)
                - time_s: Estimated time in seconds
                - uniformity: Estimated uniformity (0-1)
                - cost: Relative cost (0-1, lower is better)

        Returns:
            Dict with ranked options and tradeoff analysis.
        """
        if not options:
            return {"ranked_options": [], "best_option": None}

        # Normalize criteria
        coverages = [o.get("coverage", 0) for o in options]
        times = [o.get("time_s", 0) for o in options]
        uniformities = [o.get("uniformity", 0) for o in options]
        costs = [o.get("cost", 0) for o in options]

        def normalize(values: List[float], invert: bool = False) -> List[float]:
            min_v = min(values)
            max_v = max(values)
            if max_v == min_v:
                return [0.5] * len(values)
            norm = [(v - min_v) / (max_v - min_v) for v in values]
            if invert:
                norm = [1.0 - n for n in norm]
            return norm

        norm_cov = normalize(coverages)
        norm_time = normalize(times, invert=True)  # Lower time is better
        norm_unif = normalize(uniformities)
        norm_cost = normalize(costs, invert=True)  # Lower cost is better

        # Weights for each criterion
        w_coverage = 0.35
        w_time = 0.30
        w_uniformity = 0.15
        w_cost = 0.20

        # Compute weighted scores
        ranked = []
        for i, opt in enumerate(options):
            score = (
                w_coverage * norm_cov[i]
                + w_time * norm_time[i]
                + w_uniformity * norm_unif[i]
                + w_cost * norm_cost[i]
            )
            ranked.append({
                "name": opt["name"],
                "score": round(score, 3),
                "coverage": opt.get("coverage", 0),
                "time_s": opt.get("time_s", 0),
                "uniformity": opt.get("uniformity", 0),
                "cost": opt.get("cost", 0),
            })

        ranked.sort(key=lambda x: x["score"], reverse=True)

        return {
            "ranked_options": ranked,
            "best_option": ranked[0]["name"] if ranked else None,
            "top_score": ranked[0]["score"] if ranked else 0.0,
        }

    # =========================================================================
    # History Management
    # =========================================================================

    def record_result(self, result: Dict[str, Any]) -> None:
        """Record a sampling result for future learning.

        Args:
            result: Sampling result dict.
        """
        self.history.append(result)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

        # Update strategy performance
        strategy = result.get("strategy", "unknown")
        self.strategy_performance[strategy].append({
            "coverage": result.get("coverage", 0.0),
            "uniformity": result.get("uniformity", 0.0),
            "quality_score": result.get("quality_score", 0.0),
            "time_s": result.get("time_s", 0.0),
            "timestamp": result.get("timestamp", time.time()),
        })

    def get_strategy_stats(self) -> Dict[str, Dict[str, float]]:
        """Get performance statistics for each strategy.

        Returns:
            Dict mapping strategy names to their stats.
        """
        stats = {}
        for strategy_name, perf_list in self.strategy_performance.items():
            if not perf_list:
                continue
            coverages = [p["coverage"] for p in perf_list]
            qualities = [p["quality_score"] for p in perf_list]
            times = [p["time_s"] for p in perf_list]

            stats[strategy_name] = {
                "count": len(perf_list),
                "avg_coverage": round(np.mean(coverages), 3),
                "avg_quality": round(np.mean(qualities), 1),
                "avg_time_s": round(np.mean(times), 1),
                "best_quality": round(max(qualities), 1),
                "worst_quality": round(min(qualities), 1),
            }
        return stats

    def clear_history(self) -> None:
        """Clear all history and performance data."""
        self.history.clear()
        self.strategy_performance.clear()