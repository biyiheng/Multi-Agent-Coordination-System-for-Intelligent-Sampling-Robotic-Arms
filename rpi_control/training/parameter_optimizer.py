"""
Parameter optimizer for multi-agent system using grid search and
Bayesian optimization.

Optimizes decision thresholds, weights, and parameters for each agent
to maximize performance metrics (accuracy, speed, safety).
"""

import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class OptimizationResult:
    """Result of a parameter optimization run."""
    agent_name: str
    best_params: Dict[str, Any]
    best_score: float
    baseline_score: float
    improvement_pct: float
    num_iterations: int
    history: List[Dict[str, float]]
    duration_seconds: float


class ParameterOptimizer:
    """Grid search and Bayesian parameter optimizer for agents."""

    def __init__(
        self,
        agent_name: str,
        param_grid: Dict[str, List[float]],
        objective_fn: Callable[[Dict[str, float]], float],
        maximize: bool = True,
        enable_cache: bool = True,
    ):
        """Initialize the parameter optimizer.

        Args:
            agent_name: Name of the agent being optimized.
            param_grid: Dict mapping parameter names to lists of values.
            objective_fn: Function that takes param dict and returns score.
            maximize: True to maximize score, False to minimize.
            enable_cache: Enable caching of objective evaluations (avoid
                          recomputing same params in repeated runs).
        """
        self.agent_name = agent_name
        self.param_grid = param_grid
        self.objective_fn = objective_fn
        self.maximize = maximize
        self.enable_cache = enable_cache
        self.history: List[Dict[str, Any]] = []
        self._cache: Dict[str, float] = {}  # Cache for (param_key -> score)

    def grid_search(self, n_jobs: int = 1) -> OptimizationResult:
        """Perform exhaustive grid search over parameter space.

        Args:
            n_jobs: Number of parallel jobs (simulated).

        Returns:
            OptimizationResult with best parameters.
        """
        start_time = time.time()

        # Generate all parameter combinations
        param_names = list(self.param_grid.keys())
        param_values = list(self.param_grid.values())

        best_score = -float("inf") if self.maximize else float("inf")
        best_params = {}
        iterations = 0

        # Use itertools.product equivalent
        from itertools import product

        for combo in product(*param_values):
            params = dict(zip(param_names, combo))

            # Check cache for this parameter combination
            cache_key = json.dumps(params, sort_keys=True, default=str)
            if self.enable_cache and cache_key in self._cache:
                score = self._cache[cache_key]
                cache_hit = True
            else:
                score = self.objective_fn(params)
                if self.enable_cache:
                    self._cache[cache_key] = score
                cache_hit = False

            iterations += 1

            self.history.append({
                **params,
                "score": score,
            })

            if (self.maximize and score > best_score) or (not self.maximize and score < best_score):
                best_score = score
                best_params = params.copy()

            # Progress indicator
            if iterations % 100 == 0:
                print(f"  [{self.agent_name}] Grid search: {iterations} iterations, best={best_score:.4f}")

        # Calculate baseline (first result)
        baseline_score = self.history[0]["score"] if self.history else 0.0

        duration = time.time() - start_time

        return OptimizationResult(
            agent_name=self.agent_name,
            best_params=best_params,
            best_score=best_score,
            baseline_score=baseline_score,
            improvement_pct=((best_score - baseline_score) / abs(baseline_score) * 100) if baseline_score != 0 else 0,
            num_iterations=iterations,
            history=self.history,
            duration_seconds=duration,
        )

    def random_search(self, n_iterations: int = 500) -> OptimizationResult:
        """Perform random search over parameter space.

        Args:
            n_iterations: Number of random trials.

        Returns:
            OptimizationResult with best parameters.
        """
        start_time = time.time()

        best_score = -float("inf") if self.maximize else float("inf")
        best_params = {}

        param_names = list(self.param_grid.keys())

        for i in range(n_iterations):
            params = {}
            for name, values in self.param_grid.items():
                if isinstance(values[0], (int, float)):
                    min_val, max_val = min(values), max(values)
                    if isinstance(values[0], int):
                        params[name] = np.random.randint(min_val, max_val + 1)
                    else:
                        params[name] = np.random.uniform(min_val, max_val)
                else:
                    params[name] = np.random.choice(values)

            score = self.objective_fn(params)

            self.history.append({
                **params,
                "score": score,
            })

            if (self.maximize and score > best_score) or (not self.maximize and score < best_score):
                best_score = score
                best_params = params.copy()

            if (i + 1) % 100 == 0:
                print(f"  [{self.agent_name}] Random search: {i+1}/{n_iterations}, best={best_score:.4f}")

        baseline_score = self.history[0]["score"] if self.history else 0.0
        duration = time.time() - start_time

        return OptimizationResult(
            agent_name=self.agent_name,
            best_params=best_params,
            best_score=best_score,
            baseline_score=baseline_score,
            improvement_pct=((best_score - baseline_score) / abs(baseline_score) * 100) if baseline_score != 0 else 0,
            num_iterations=n_iterations,
            history=self.history,
            duration_seconds=duration,
        )

    def bayesian_optimization(self, n_iterations: int = 100) -> OptimizationResult:
        """Perform Bayesian optimization using Gaussian Process.

        Simplified implementation using expected improvement.

        Args:
            n_iterations: Number of optimization iterations.

        Returns:
            OptimizationResult with best parameters.
        """
        start_time = time.time()

        param_names = list(self.param_grid.keys())
        n_params = len(param_names)

        # Normalize parameter space to [0, 1]
        bounds = []
        for name in param_names:
            values = self.param_grid[name]
            if isinstance(values[0], (int, float)):
                bounds.append((min(values), max(values)))
            else:
                # Categorical: map to indices
                bounds.append((0, len(values) - 1))

        # Initial random samples
        n_init = min(20, n_iterations // 2)
        X = np.random.uniform(0, 1, (n_init, n_params))
        y = np.array([self._evaluate_params(X[i], param_names) for i in range(n_init)])

        best_idx = np.argmax(y) if self.maximize else np.argmin(y)
        best_score = y[best_idx]
        best_x = X[best_idx]

        for iteration in range(n_iterations - n_init):
            # Simple GP approximation: use RBF kernel
            K = self._rbf_kernel(X, X)

            try:
                K_inv = np.linalg.inv(K + 1e-6 * np.eye(len(X)))
            except np.linalg.LinAlgError:
                K_inv = np.linalg.pinv(K + 1e-6 * np.eye(len(X)))

            # Expected improvement
            n_candidates = 1000
            candidates = np.random.uniform(0, 1, (n_candidates, n_params))

            best_ei = -float("inf")
            best_candidate = candidates[0]

            for candidate in candidates:
                k = self._rbf_kernel(X, candidate.reshape(1, -1)).flatten()
                mu = k @ K_inv @ y
                sigma = math.sqrt(max(0, 1.0 - k @ K_inv @ k))

                if sigma < 1e-6:
                    ei = 0.0
                else:
                    best_y = np.max(y) if self.maximize else np.min(y)
                    z = (mu - best_y) / sigma
                    ei = (mu - best_y) * (0.5 + 0.5 * math.erf(z / math.sqrt(2))) + sigma * (1 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * z**2)

                if ei > best_ei:
                    best_ei = ei
                    best_candidate = candidate

            new_score = self._evaluate_params(best_candidate, param_names)
            X = np.vstack([X, best_candidate])
            y = np.append(y, new_score)

            if (self.maximize and new_score > best_score) or (not self.maximize and new_score < best_score):
                best_score = new_score
                best_x = best_candidate

            self.history.append({
                **{param_names[i]: self._denormalize(best_candidate[i], bounds[i]) for i in range(n_params)},
                "score": new_score,
            })

            if (iteration + 1) % 20 == 0:
                print(f"  [{self.agent_name}] BO: {iteration+1}/{n_iterations-n_init}, best={best_score:.4f}")

        best_params = {param_names[i]: self._denormalize(best_x[i], bounds[i]) for i in range(n_params)}

        baseline_score = self.history[0]["score"] if self.history else 0.0
        duration = time.time() - start_time

        return OptimizationResult(
            agent_name=self.agent_name,
            best_params=best_params,
            best_score=best_score,
            baseline_score=baseline_score,
            improvement_pct=((best_score - baseline_score) / abs(baseline_score) * 100) if baseline_score != 0 else 0,
            num_iterations=n_iterations,
            history=self.history,
            duration_seconds=duration,
        )

    def _evaluate_params(self, x: np.ndarray, param_names: List[str]) -> float:
        """Evaluate a parameter vector."""
        params = {}
        for i, name in enumerate(param_names):
            values = self.param_grid[name]
            if isinstance(values[0], (int, float)):
                min_val, max_val = min(values), max(values)
                params[name] = min_val + x[i] * (max_val - min_val)
            else:
                idx = int(np.clip(x[i], 0, len(values) - 1))
                params[name] = values[idx]
        return self.objective_fn(params)

    def _denormalize(self, x: float, bound: Tuple[float, float]) -> float:
        """Denormalize a parameter value."""
        if isinstance(bound[0], (int, float)):
            return bound[0] + x * (bound[1] - bound[0])
        return bound[int(x)]

    def _rbf_kernel(self, X1: np.ndarray, X2: np.ndarray, length_scale: float = 1.0) -> np.ndarray:
        """RBF kernel matrix."""
        sqdist = (
            np.sum(X1**2, 1).reshape(-1, 1)
            + np.sum(X2**2, 1)
            - 2 * X1 @ X2.T
        )
        return np.exp(-0.5 * sqdist / length_scale**2)


def print_optimization_report(result: OptimizationResult) -> None:
    """Print a formatted optimization report.

    Args:
        result: OptimizationResult from the optimizer.
    """
    print(f"\n{'='*60}")
    print(f"  Optimization Report: {result.agent_name}")
    print(f"{'='*60}")
    print(f"  Baseline score:    {result.baseline_score:.4f}")
    print(f"  Best score:        {result.best_score:.4f}")
    print(f"  Improvement:       {result.improvement_pct:+.2f}%")
    print(f"  Iterations:        {result.num_iterations}")
    print(f"  Duration:          {result.duration_seconds:.2f}s")
    print(f"\n  Best parameters:")
    for key, value in result.best_params.items():
        print(f"    {key}: {value}")
    print(f"{'='*60}")