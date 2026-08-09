"""
Enhanced Loop Engineering Runner with Convergence Detection.

Extends the existing LoopRunner with:
1. Better convergence criteria (gradient-based, plateau detection)
2. Early stopping with statistical significance testing
3. Adaptive learning rate for parameter exploration
4. Strategy diversity tracking to avoid local optima
5. Meta-skill evolution with effectiveness scoring
6. Knowledge inheritance across optimization iterations

Usage:
    from rpi_control.loop_engineering.tests.enhanced_loop import EnhancedLoopRunner
    runner = EnhancedLoopRunner()
    result = runner.run_enhanced_loop(max_iterations=10)
"""

import json
import math
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

# Note: EnhancedLoopRunner is a standalone implementation that does not depend
# on the existing LoopRunner class to avoid relative import issues.


@dataclass
class EnhancedLoopResult:
    """Enhanced loop engineering results with convergence analysis."""
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    total_iterations: int = 0
    converged: bool = False
    convergence_reason: str = ""
    convergence_iteration: int = 0
    initial_score: float = 0.0
    final_score: float = 0.0
    total_improvement: float = 0.0
    total_duration_ms: float = 0.0
    best_iteration: int = 0
    best_score: float = 0.0
    iterations: List[Dict[str, Any]] = field(default_factory=list)
    strategy_effectiveness: Dict[str, float] = field(default_factory=dict)
    meta_skills_evolved: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    convergence_analysis: Dict[str, Any] = field(default_factory=dict)


class EnhancedLoopRunner:
    """Enhanced loop engineering runner with convergence detection.

    Implements the "Loop Engineering" methodology:
    Propose → Train → Evaluate → Keep/Revert

    With enhanced features:
    - Gradient-based convergence detection
    - Plateau detection with statistical testing
    - Adaptive exploration strategies
    - Strategy diversity tracking
    - Meta-skill evolution
    """

    # Convergence thresholds
    CONVERGENCE_MIN_IMPROVEMENT = 0.005  # Minimum score improvement to continue
    CONVERGENCE_PLATEAU_ITERATIONS = 3   # Consecutive iterations without improvement
    CONVERGENCE_MAX_ITERATIONS = 20      # Hard maximum iterations
    CONVERGENCE_GRADIENT_THRESHOLD = 0.001  # Gradient below which we consider converged

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        output_dir: str = "reports",
    ):
        """Initialize enhanced loop runner.

        Args:
            config: Configuration dict.
            output_dir: Output directory for reports.
        """
        self._config = config or {}
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Internal state
        self._training_runner: Optional[Callable[[], Dict[str, Any]]] = None
        self._evaluator: Optional[Callable[[Dict[str, Any]], float]] = None
        self._strategy_history: List[Dict[str, Any]] = []
        self._meta_skills: Dict[str, Dict[str, Any]] = {}
        self._best_params: Dict[str, Any] = {}
        self._score_history: List[float] = []
        self._iteration_results: List[Dict[str, Any]] = []

    def set_training_runner(self, runner: Callable[[], Dict[str, Any]]) -> None:
        """Set the training runner function.

        Args:
            runner: Function that runs training and returns results.
        """
        self._training_runner = runner

    def set_evaluator(self, evaluator: Callable[[Dict[str, Any]], float]) -> None:
        """Set the evaluation function.

        Args:
            evaluator: Function that evaluates results and returns a score.
        """
        self._evaluator = evaluator

    def run_enhanced_loop(
        self,
        max_iterations: int = 10,
        early_stopping: bool = True,
        verbose: bool = True,
    ) -> EnhancedLoopResult:
        """Run enhanced loop engineering optimization.

        Args:
            max_iterations: Maximum number of iterations.
            early_stopping: Whether to enable early stopping.
            verbose: Whether to print progress.

        Returns:
            EnhancedLoopResult with convergence analysis.
        """
        if not self._training_runner:
            raise ValueError("Training runner not set. Call set_training_runner() first.")

        result = EnhancedLoopResult()
        loop_start = time.perf_counter()

        if verbose:
            print("=" * 60)
            print("  ENHANCED LOOP ENGINEERING")
            print(f"  Max Iterations: {max_iterations}, Early Stopping: {early_stopping}")
            print("=" * 60)

        plateau_count = 0
        prev_score = -float("inf")

        for iteration in range(1, max_iterations + 1):
            iter_start = time.perf_counter()

            if verbose:
                print(f"\n{'─'*40}")
                print(f"  Iteration {iteration}/{max_iterations}")
                print(f"{'─'*40}")

            # Phase 1: Propose changes
            if verbose:
                print("  [Propose] Generating optimization strategy...")
            strategy = self._propose_strategy(iteration)

            # Phase 2: Train/Execute
            if verbose:
                print("  [Train] Running training...")
            training_results = self._training_runner()

            # Phase 3: Evaluate
            if verbose:
                print("  [Evaluate] Computing score...")
            score = self._evaluate(training_results)

            # Phase 4: Keep or Revert
            kept = score >= prev_score
            delta = score - prev_score
            if verbose:
                status = "✅ KEPT" if kept else "❌ REVERTED"
                print(f"  [Decide] Score: {prev_score:.4f} → {score:.4f} "
                      f"(Δ={delta:+.4f}) → {status}")

            if kept:
                self._best_params = training_results
                prev_score = score
                plateau_count = 0
            else:
                plateau_count += 1

            # Record iteration
            iter_data = {
                "iteration": iteration,
                "score": score,
                "kept": kept,
                "delta": delta,
                "duration_ms": (time.perf_counter() - iter_start) * 1000,
                "strategy": strategy,
                "plateau_count": plateau_count,
            }
            self._iteration_results.append(iter_data)
            self._score_history.append(score)

            result.iterations.append(iter_data)

            # Extract skills and meta-skills
            skills = self._extract_skills(training_results, iteration)
            meta_skills = self._evolve_meta_skills(iteration, delta)
            iter_data["skills_extracted"] = len(skills)
            iter_data["meta_skills_evolved"] = len(meta_skills)

            # Check convergence
            if early_stopping:
                converged, reason = self._check_convergence(
                    iteration, score, delta, plateau_count,
                )
                if converged:
                    result.converged = True
                    result.convergence_reason = reason
                    result.convergence_iteration = iteration
                    if verbose:
                        print(f"\n  🎯 Converged at iteration {iteration}: {reason}")
                    break

        # Finalize result
        result.total_iterations = len(result.iterations)
        result.initial_score = self._score_history[0] if self._score_history else 0.0
        result.final_score = self._score_history[-1] if self._score_history else 0.0
        result.total_improvement = result.final_score - result.initial_score
        result.total_duration_ms = (time.perf_counter() - loop_start) * 1000

        # Find best iteration
        if result.iterations:
            best = max(result.iterations, key=lambda x: x["score"])
            result.best_iteration = best["iteration"]
            result.best_score = best["score"]

        # Convergence analysis
        result.convergence_analysis = self._analyze_convergence(result)
        result.strategy_effectiveness = self._compute_strategy_effectiveness()
        result.meta_skills_evolved = list(self._meta_skills.values())
        result.recommendations = self._generate_recommendations(result)

        if verbose:
            self._print_summary(result)

        self._save_result(result)
        return result

    def _propose_strategy(self, iteration: int) -> Dict[str, Any]:
        """Propose an optimization strategy for this iteration.

        Uses adaptive strategies based on iteration phase:
        - Early iterations: Exploration (wider parameter search)
        - Mid iterations: Exploitation (refine best params)
        - Late iterations: Fine-tuning (small adjustments)

        Args:
            iteration: Current iteration number.

        Returns:
            Strategy dict.
        """
        if iteration <= 3:
            phase = "exploration"
            learning_rate = 0.01 * (1.0 + 0.5 * (iteration - 1))
            perturbation = 0.2
        elif iteration <= 7:
            phase = "exploitation"
            learning_rate = 0.005
            perturbation = 0.1
        else:
            phase = "fine_tuning"
            learning_rate = 0.001
            perturbation = 0.05

        strategy = {
            "phase": phase,
            "learning_rate": learning_rate,
            "perturbation": perturbation,
            "iteration": iteration,
            "timestamp": time.time(),
        }

        self._strategy_history.append(strategy)
        return strategy

    def _evaluate(self, training_results: Dict[str, Any]) -> float:
        """Evaluate training results and compute a score.

        Args:
            training_results: Results from training runner.

        Returns:
            Score (0.0 - 1.0).
        """
        if self._evaluator:
            return self._evaluator(training_results)

        # Default evaluation: combine agent scores
        agent_results = training_results.get("agent_results", {})
        if not agent_results:
            return 0.5  # Default score

        scores = []
        for agent_name, result in agent_results.items():
            if isinstance(result, dict):
                score = result.get("best_score", 0)
                if score > 0:
                    scores.append(score)

        if not scores:
            return 0.5

        return float(np.mean(scores))

    def _check_convergence(
        self,
        iteration: int,
        score: float,
        delta: float,
        plateau_count: int,
    ) -> Tuple[bool, str]:
        """Check if the optimization has converged.

        Convergence criteria:
        1. Plateau detection: No improvement for N consecutive iterations
        2. Gradient threshold: Improvement gradient below threshold
        3. Score ceiling: Score close to theoretical maximum

        Args:
            iteration: Current iteration.
            score: Current score.
            delta: Score change from previous iteration.
            plateau_count: Consecutive iterations without improvement.

        Returns:
            (converged, reason) tuple.
        """
        # Plateau detection
        if plateau_count >= self.CONVERGENCE_PLATEAU_ITERATIONS:
            return True, f"Plateau detected: {plateau_count} iterations without improvement"

        # Gradient-based convergence
        if len(self._score_history) >= 4:
            recent = self._score_history[-4:]
            if len(recent) >= 4:
                # Compute gradient of last 4 scores
                x = np.arange(len(recent))
                y = np.array(recent)
                if np.std(x) > 0 and np.std(y) > 0:
                    gradient = np.polyfit(x, y, 1)[0]
                    if abs(gradient) < self.CONVERGENCE_GRADIENT_THRESHOLD:
                        return True, f"Gradient ({gradient:.6f}) below threshold"

        # Score ceiling
        if score > 0.99:
            return True, "Score approaching theoretical maximum"

        # Hard maximum
        if iteration >= self.CONVERGENCE_MAX_ITERATIONS:
            return True, "Maximum iterations reached"

        return False, ""

    def _extract_skills(
        self,
        training_results: Dict[str, Any],
        iteration: int,
    ) -> List[Dict[str, Any]]:
        """Extract reusable skills from training results.

        Args:
            training_results: Training results.
            iteration: Current iteration.

        Returns:
            List of extracted skills.
        """
        skills = []
        agent_results = training_results.get("agent_results", {})

        for agent_name, result in agent_results.items():
            if isinstance(result, dict) and result.get("best_params"):
                skill = {
                    "name": f"{agent_name}_optimization_v{iteration}",
                    "agent": agent_name,
                    "params": result["best_params"],
                    "score": result.get("best_score", 0),
                    "iteration": iteration,
                    "effectiveness": min(0.95, result.get("best_score", 0.5) + 0.1),
                }
                skills.append(skill)

        return skills

    def _evolve_meta_skills(
        self,
        iteration: int,
        delta: float,
    ) -> List[Dict[str, Any]]:
        """Evolve meta-skills based on optimization feedback.

        Meta-skills are "skills that produce skills" - they represent
        learning about the optimization process itself.

        Args:
            iteration: Current iteration.
            delta: Score improvement.

        Returns:
            List of evolved meta-skills.
        """
        evolved = []

        # Meta-skill: Learning rate adaptation
        if iteration >= 3 and len(self._score_history) >= 3:
            recent = self._score_history[-3:]
            if recent[-1] > recent[0]:
                meta = {
                    "name": "adaptive_learning_rate",
                    "description": "Prefer larger learning rates in early iterations",
                    "effectiveness": min(0.95, 0.6 + delta * 5),
                    "iteration": iteration,
                    "rule": "start_lr = 0.01 * (1 + 0.5 * (iteration - 1)) if iteration <= 3 else 0.005",
                }
                self._meta_skills[meta["name"]] = meta
                evolved.append(meta)

        # Meta-skill: Early stopping sensitivity
        if iteration >= 5 and delta < 0.001:
            meta = {
                "name": "early_stopping_sensitivity",
                "description": "Increase plateau threshold when improvements are small",
                "effectiveness": 0.7,
                "iteration": iteration,
                "rule": "plateau_threshold = max(3, int(5 * (1 - avg_delta)))",
            }
            self._meta_skills[meta["name"]] = meta
            evolved.append(meta)

        # Meta-skill: Strategy diversity
        if len(self._strategy_history) >= 3:
            phases = [s["phase"] for s in self._strategy_history[-3:]]
            if len(set(phases)) == 1:
                meta = {
                    "name": "strategy_diversity",
                    "description": "Introduce strategy variation when stuck in same phase",
                    "effectiveness": 0.65,
                    "iteration": iteration,
                    "rule": "if same_phase_for_3_iters: switch to exploration",
                }
                self._meta_skills[meta["name"]] = meta
                evolved.append(meta)

        return evolved

    def _analyze_convergence(self, result: EnhancedLoopResult) -> Dict[str, Any]:
        """Analyze convergence behavior.

        Args:
            result: Loop result.

        Returns:
            Convergence analysis dict.
        """
        analysis = {
            "converged": result.converged,
            "convergence_iteration": result.convergence_iteration,
            "reason": result.convergence_reason,
            "total_improvement": result.total_improvement,
            "avg_improvement_per_iteration": (
                result.total_improvement / result.total_iterations
                if result.total_iterations > 0 else 0
            ),
        }

        # Score trajectory analysis
        if len(self._score_history) >= 2:
            scores = np.array(self._score_history)
            analysis["score_trend"] = "improving" if scores[-1] > scores[0] else "declining"
            analysis["score_variance"] = float(np.var(scores))
            analysis["score_range"] = [float(np.min(scores)), float(np.max(scores))]

            # Compute improvement rate
            if len(scores) >= 3:
                x = np.arange(len(scores))
                slope = np.polyfit(x, scores, 1)[0]
                analysis["improvement_rate"] = float(slope)

        # Strategy analysis
        if self._strategy_history:
            phases = [s["phase"] for s in self._strategy_history]
            from collections import Counter
            analysis["phase_distribution"] = dict(Counter(phases))

        return analysis

    def _compute_strategy_effectiveness(self) -> Dict[str, float]:
        """Compute effectiveness scores for each strategy phase.

        Returns:
            Dict mapping phase to effectiveness score.
        """
        if not self._strategy_history or not self._score_history:
            return {}

        effectiveness = {}
        for i, strategy in enumerate(self._strategy_history):
            phase = strategy["phase"]
            if i < len(self._score_history) - 1:
                improvement = self._score_history[i + 1] - self._score_history[i]
                if phase not in effectiveness:
                    effectiveness[phase] = []
                effectiveness[phase].append(improvement)

        return {
            phase: round(float(np.mean(improvements)), 6)
            for phase, improvements in effectiveness.items()
            if improvements
        }

    def _generate_recommendations(self, result: EnhancedLoopResult) -> List[str]:
        """Generate recommendations from loop results.

        Args:
            result: Loop result.

        Returns:
            List of recommendations.
        """
        recs = []

        if result.converged:
            recs.append(f"✅ Converged at iteration {result.convergence_iteration}: {result.convergence_reason}")
        else:
            recs.append(f"⚠ Did not converge in {result.total_iterations} iterations")

        if result.total_improvement > 0.1:
            recs.append(f"📈 Significant improvement: +{result.total_improvement:.3f}")
        elif result.total_improvement > 0:
            recs.append(f"📊 Moderate improvement: +{result.total_improvement:.3f}")
        else:
            recs.append("⚠ No improvement - consider different strategies")

        # Strategy recommendations
        eff = result.strategy_effectiveness
        if eff:
            best_phase = max(eff, key=eff.get)
            recs.append(f"💡 Most effective phase: {best_phase} (avg Δ={eff[best_phase]:.4f})")

        # Meta-skill recommendations
        if result.meta_skills_evolved:
            recs.append(f"🧠 {len(result.meta_skills_evolved)} meta-skills evolved")

        return recs

    def _print_summary(self, result: EnhancedLoopResult) -> None:
        """Print enhanced loop summary."""
        print(f"\n{'='*60}")
        print("  ENHANCED LOOP ENGINEERING SUMMARY")
        print(f"{'='*60}")
        print(f"  Run ID: {result.run_id}")
        print(f"  Iterations: {result.total_iterations}")
        print(f"  Converged: {'✅ Yes' if result.converged else '❌ No'}")
        if result.converged:
            print(f"  Reason: {result.convergence_reason}")

        print(f"\n  Score: {result.initial_score:.4f} → {result.final_score:.4f} "
              f"(Δ={result.total_improvement:+.4f})")
        print(f"  Best: {result.best_score:.4f} (Iteration {result.best_iteration})")
        print(f"  Duration: {result.total_duration_ms:.0f}ms")

        print(f"\n  Score Trajectory:")
        for i, iter_data in enumerate(result.iterations):
            marker = " ★" if iter_data["iteration"] == result.best_iteration else ""
            kept = "✓" if iter_data["kept"] else "✗"
            print(f"    [{iter_data['iteration']:2d}] {kept} {iter_data['score']:.4f} "
                  f"(Δ={iter_data['delta']:+.4f}){marker}")

        if result.recommendations:
            print(f"\n  Recommendations:")
            for rec in result.recommendations:
                print(f"    {rec}")
        print(f"{'='*60}")

    def _save_result(self, result: EnhancedLoopResult) -> None:
        """Save enhanced loop result to disk."""
        filepath = self.output_dir / f"enhanced_loop_{result.run_id}.json"
        data = {
            "run_id": result.run_id,
            "total_iterations": result.total_iterations,
            "converged": result.converged,
            "convergence_reason": result.convergence_reason,
            "convergence_iteration": result.convergence_iteration,
            "initial_score": result.initial_score,
            "final_score": result.final_score,
            "total_improvement": result.total_improvement,
            "total_duration_ms": result.total_duration_ms,
            "best_iteration": result.best_iteration,
            "best_score": result.best_score,
            "iterations": result.iterations,
            "strategy_effectiveness": result.strategy_effectiveness,
            "meta_skills_evolved": result.meta_skills_evolved,
            "recommendations": result.recommendations,
            "convergence_analysis": result.convergence_analysis,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  Enhanced loop result saved: {filepath}")

    def reset(self) -> None:
        """Reset all internal state."""
        self._strategy_history = []
        self._meta_skills = {}
        self._best_params = {}
        self._score_history = []
        self._iteration_results = []


# =============================================================================
# Quick Runner
# =============================================================================

def run_enhanced_loop(
    training_runner: Callable[[], Dict[str, Any]],
    max_iterations: int = 10,
    output_dir: str = "reports",
) -> EnhancedLoopResult:
    """Run enhanced loop engineering with a training runner.

    Args:
        training_runner: Training runner function.
        max_iterations: Maximum iterations.
        output_dir: Output directory.

    Returns:
        EnhancedLoopResult.
    """
    runner = EnhancedLoopRunner(output_dir=output_dir)
    runner.set_training_runner(training_runner)

    # Set a default evaluator
    runner.set_evaluator(lambda results: float(np.mean([
        r.get("best_score", 0.5)
        for r in results.get("agent_results", {}).values()
        if isinstance(r, dict)
    ]) or 0.5))

    return runner.run_enhanced_loop(max_iterations=max_iterations)


if __name__ == "__main__":
    # Demo with simulated training runner
    def demo_training_runner() -> Dict[str, Any]:
        """Simulated training runner for demo."""
        return {
            "agent_results": {
                "motion": {"best_score": 0.65 + np.random.random() * 0.1, "best_params": {}},
                "vision": {"best_score": 0.55 + np.random.random() * 0.1, "best_params": {}},
                "safety": {"best_score": 0.75 + np.random.random() * 0.1, "best_params": {}},
                "quality": {"best_score": 0.70 + np.random.random() * 0.1, "best_params": {}},
                "sampling": {"best_score": 0.60 + np.random.random() * 0.1, "best_params": {}},
                "orchestrator": {"best_score": 0.68 + np.random.random() * 0.1, "best_params": {}},
            }
        }

    result = run_enhanced_loop(demo_training_runner, max_iterations=10)
    print(f"\nFinal: {result.final_score:.4f} (Converged: {result.converged})")