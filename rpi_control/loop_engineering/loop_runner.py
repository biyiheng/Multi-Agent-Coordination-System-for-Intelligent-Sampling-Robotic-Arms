"""
Loop Runner - The main orchestration engine for Loop Engineering.

Implements the automated optimization loop:
    PROPOSE → TRAIN/EXECUTE → EVALUATE → KEEP/REVERT

Each iteration:
1. Collects profiling and interaction data
2. Runs the multi-dimensional evaluator
3. Extracts skills and evolves meta-strategies
4. Decides whether to keep or revert changes
5. Logs results and continues until convergence

This is the central controller that ties together all Loop Engineering
components into a cohesive automated optimization system.

Usage:
    runner = LoopRunner(config={...})
    runner.setup()
    results = runner.run_loop(max_iterations=10)
"""

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .profiler import AgentProfiler, EndToEndProfiler
from .interaction_tracker import InteractionTracker
from .evaluator import MultiDimensionEvaluator, EvaluationReport
from .context_manager import ContextManager
from .skill_extractor import SkillExtractor
from .knowledge_inheritor import KnowledgeInheritor
from .meta_optimizer import MetaOptimizer


@dataclass
class LoopIteration:
    """Result of a single loop iteration.

    Attributes:
        iteration: Iteration number (1-based).
        report: Evaluation report for this iteration.
        kept: Whether changes were kept (True) or reverted (False).
        delta: Improvement delta from previous iteration.
        skills_extracted: Number of new skills extracted.
        meta_skills_evolved: Number of meta-skills evolved.
        timestamp: When the iteration completed.
        duration_ms: Duration of this iteration.
    """
    iteration: int
    report: Optional[EvaluationReport] = None
    kept: bool = True
    delta: float = 0.0
    skills_extracted: int = 0
    meta_skills_evolved: int = 0
    timestamp: float = field(default_factory=time.time)
    duration_ms: float = 0.0


@dataclass
class LoopResult:
    """Complete result of a loop engineering run.

    Attributes:
        run_id: Unique run identifier.
        iterations: All iteration results.
        total_iterations: Total iterations performed.
        converged: Whether the loop converged.
        convergence_reason: Why the loop stopped.
        initial_score: Composite score at start.
        final_score: Composite score at end.
        total_improvement: Overall improvement.
        total_duration_ms: Total duration of the run.
        best_iteration: Iteration with the best score.
        recommendations: Final recommendations.
    """
    run_id: str
    iterations: List[LoopIteration] = field(default_factory=list)
    total_iterations: int = 0
    converged: bool = False
    convergence_reason: str = ""
    initial_score: float = 0.0
    final_score: float = 0.0
    total_improvement: float = 0.0
    total_duration_ms: float = 0.0
    best_iteration: int = 0
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "run_id": self.run_id,
            "total_iterations": self.total_iterations,
            "converged": self.converged,
            "convergence_reason": self.convergence_reason,
            "initial_score": round(self.initial_score, 4),
            "final_score": round(self.final_score, 4),
            "total_improvement": round(self.total_improvement, 4),
            "total_duration_ms": round(self.total_duration_ms, 2),
            "best_iteration": self.best_iteration,
            "iterations": [
                {
                    "iteration": it.iteration,
                    "score": (
                        round(it.report.composite_score, 4)
                        if it.report else 0.0
                    ),
                    "grade": it.report.grade if it.report else "N/A",
                    "kept": it.kept,
                    "delta": round(it.delta, 4),
                    "skills_extracted": it.skills_extracted,
                    "meta_skills_evolved": it.meta_skills_evolved,
                    "duration_ms": round(it.duration_ms, 2),
                }
                for it in self.iterations
            ],
            "recommendations": self.recommendations,
        }


# =============================================================================
# Loop Runner
# =============================================================================


class LoopRunner:
    """Main loop engineering orchestration engine.

    Coordinates all components to run the full optimization loop:
    PROPOSE → TRAIN/EXECUTE → EVALUATE → KEEP/REVERT

    Usage:
        runner = LoopRunner(config={"loop_engineering": {...}})
        result = runner.run_loop()
        print(f"Improvement: {result.total_improvement:.2%}")
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the loop runner.

        Args:
            config: Configuration dict with loop_engineering settings.
        """
        self._config = config or {}
        loop_cfg = self._config.get("loop_engineering", {})

        # Core settings
        self.max_iterations = loop_cfg.get("loop_runner", {}).get("max_iterations", 10)
        self.convergence_threshold = loop_cfg.get("loop_runner", {}).get("convergence_threshold", 0.01)
        self.convergence_patience = loop_cfg.get("loop_runner", {}).get("convergence_patience", 3)
        self.min_loop_interval = loop_cfg.get("loop_runner", {}).get("min_loop_interval", 1.0)
        self.enabled = loop_cfg.get("enabled", True)

        # Components (initialized in setup())
        self.e2e_profiler: Optional[EndToEndProfiler] = None
        self.interaction_tracker: Optional[InteractionTracker] = None
        self.evaluator: Optional[MultiDimensionEvaluator] = None
        self.context_manager: Optional[ContextManager] = None
        self.skill_extractor: Optional[SkillExtractor] = None
        self.knowledge_inheritor: Optional[KnowledgeInheritor] = None
        self.meta_optimizer: Optional[MetaOptimizer] = None

        # State
        self._iterations: List[LoopIteration] = []
        self._current_iteration: int = 0
        self._no_improvement_count: int = 0
        self._best_score: float = 0.0
        self._best_iteration: int = 0
        self._run_id: str = uuid.uuid4().hex[:12]
        self._start_time: float = 0.0

        # Callbacks
        self._on_iteration_complete: Optional[Callable[[LoopIteration], None]] = None
        self._on_convergence: Optional[Callable[[LoopResult], None]] = None

        # External data providers (set by caller)
        self._task_executor: Optional[Callable[[], Dict[str, Any]]] = None
        self._training_runner: Optional[Callable[[], Dict[str, Any]]] = None

    # =========================================================================
    # Setup
    # =========================================================================

    def setup(self) -> None:
        """Initialize all loop engineering components."""
        cfg = self._config.get("loop_engineering", {})

        # Profiler
        profiler_cfg = cfg.get("profiler", {})
        self.e2e_profiler = EndToEndProfiler()

        # Interaction tracker
        tracker_cfg = cfg.get("interaction_tracker", {})
        self.interaction_tracker = InteractionTracker(
            redundancy_threshold=tracker_cfg.get("redundancy_threshold", 3),
        )

        # Evaluator
        eval_cfg = cfg.get("evaluator", {})
        self.evaluator = MultiDimensionEvaluator(
            weights=eval_cfg.get("weights"),
            report_dir=eval_cfg.get("report_dir"),
        )

        # Context manager
        ctx_cfg = cfg.get("context_manager", {})
        self.context_manager = ContextManager(
            max_history=ctx_cfg.get("max_history", 100),
            compression_threshold=ctx_cfg.get("compression_threshold", 50),
            decay_window=ctx_cfg.get("decay_window", 20),
            state_persistence_dir=ctx_cfg.get("state_persistence_dir"),
        )

        # Skill extractor
        skill_cfg = cfg.get("skill_extractor", {})
        self.skill_extractor = SkillExtractor(
            min_reuse_threshold=skill_cfg.get("min_reuse_threshold", 2),
            similarity_threshold=skill_cfg.get("similarity_threshold", 0.7),
            library_path=skill_cfg.get("skill_library_path"),
        )

        # Knowledge inheritor
        ki_cfg = cfg.get("knowledge_inheritor", {})
        self.knowledge_inheritor = KnowledgeInheritor(
            core_memory_retention=ki_cfg.get("core_memory_retention", 0.8),
            decay_threshold=ki_cfg.get("decay_threshold", 0.3),
            lineage_path=ki_cfg.get("lineage_path"),
        )

        # Meta-optimizer
        meta_cfg = cfg.get("meta_optimizer", {})
        self.meta_optimizer = MetaOptimizer(
            strategy_history_size=meta_cfg.get("strategy_history_size", 50),
            min_improvement_threshold=meta_cfg.get("min_improvement_threshold", 0.05),
            meta_skill_path=meta_cfg.get("meta_skill_path"),
        )

    def set_task_executor(self, executor: Callable[[], Dict[str, Any]]) -> None:
        """Set the function that executes tasks.

        Args:
            executor: Async function that runs a task and returns results.
        """
        self._task_executor = executor

    def set_training_runner(self, runner: Callable[[], Dict[str, Any]]) -> None:
        """Set the function that runs training.

        Args:
            runner: Function that runs training and returns results.
        """
        self._training_runner = runner

    def set_on_iteration(self, callback: Callable[[LoopIteration], None]) -> None:
        """Set callback for iteration completion.

        Args:
            callback: Function called with LoopIteration after each iteration.
        """
        self._on_iteration_complete = callback

    def set_on_convergence(self, callback: Callable[[LoopResult], None]) -> None:
        """Set callback for loop convergence.

        Args:
            callback: Function called with LoopResult when loop converges.
        """
        self._on_convergence = callback

    # =========================================================================
    # Main Loop
    # =========================================================================

    def run_loop(self, max_iterations: Optional[int] = None) -> LoopResult:
        """Run the full loop engineering optimization cycle.

        Args:
            max_iterations: Override max iterations from config.

        Returns:
            LoopResult with complete loop data.
        """
        if not self.enabled:
            return LoopResult(
                run_id=self._run_id,
                convergence_reason="Loop engineering is disabled",
            )

        if not self.evaluator:
            self.setup()

        max_iters = max_iterations if max_iterations is not None else self.max_iterations
        self._start_time = time.perf_counter()

        for iteration in range(1, max_iters + 1):
            iter_start = time.perf_counter()

            # 1. PROPOSE: Generate changes to try
            self._propose_changes(iteration)

            # 2. TRAIN/EXECUTE: Run training or task execution
            training_result = self._execute(iteration)

            # 3. EVALUATE: Multi-dimensional evaluation
            report = self._evaluate(iteration, training_result)

            # 4. EXTRACT: Extract skills and evolve meta-strategies
            skills_count = self._extract_skills(iteration)
            meta_count = self._evolve_meta(iteration, training_result)

            # 5. KEEP/REVERT: Decide based on evaluation
            delta = self.evaluator.get_improvement_delta()
            kept = self._decide_keep_revert(delta, report)

            # Record iteration
            iter_duration = (time.perf_counter() - iter_start) * 1000.0
            loop_iter = LoopIteration(
                iteration=iteration,
                report=report,
                kept=kept,
                delta=delta,
                skills_extracted=skills_count,
                meta_skills_evolved=meta_count,
                duration_ms=iter_duration,
            )
            self._iterations.append(loop_iter)

            # Track best
            if report and report.composite_score > self._best_score:
                self._best_score = report.composite_score
                self._best_iteration = iteration

            # Callback
            if self._on_iteration_complete:
                self._on_iteration_complete(loop_iter)

            # Check convergence
            converged, reason = self._check_convergence()
            if converged:
                return self._build_result(converged=True, reason=reason)

            # Minimum interval between iterations
            elapsed = time.perf_counter() - iter_start
            if elapsed < self.min_loop_interval:
                time.sleep(self.min_loop_interval - elapsed)

        return self._build_result(converged=False, reason="Max iterations reached")

    # =========================================================================
    # Loop Steps
    # =========================================================================

    def _propose_changes(self, iteration: int) -> None:
        """Propose changes for this iteration.

        Uses meta-optimizer to suggest which strategies to try.

        Args:
            iteration: Current iteration number.
        """
        # In a real system, this would use the meta-optimizer and
        # knowledge inheritor to propose parameter changes, model
        # updates, or code modifications.
        pass

    def _execute(self, iteration: int) -> Dict[str, Any]:
        """Execute training or task execution.

        Args:
            iteration: Current iteration number.

        Returns:
            Results from training/task execution.
        """
        result: Dict[str, Any] = {"iteration": iteration}

        # Run training if available
        if self._training_runner:
            try:
                training_result = self._training_runner()
                result.update(training_result)
            except Exception as e:
                result["training_error"] = str(e)

        # Run task execution if available
        if self._task_executor:
            try:
                task_result = self._task_executor()
                result.update(task_result)
            except Exception as e:
                result["task_error"] = str(e)

        return result

    def _evaluate(
        self,
        iteration: int,
        training_result: Dict[str, Any],
    ) -> EvaluationReport:
        """Run multi-dimensional evaluation.

        Args:
            iteration: Current iteration number.
            training_result: Results from training/execution.

        Returns:
            EvaluationReport.
        """
        # Feed data to evaluator
        if self.e2e_profiler:
            self.evaluator.set_profiler_data(
                self.e2e_profiler.get_e2e_report()
            )

        if self.interaction_tracker:
            self.evaluator.set_interaction_data(
                self.interaction_tracker.get_statistics()
            )

        if self.context_manager:
            self.evaluator.set_context_data(
                self.context_manager.get_health_stats()
            )

        if self.skill_extractor:
            self.evaluator.set_skill_data(
                self.skill_extractor.get_skill_statistics()
            )

        # Task results from training
        task_results = training_result.get("task_results", [])
        if task_results:
            self.evaluator.set_task_results(task_results)
        elif "agent_results" in training_result:
            # Extract task-like results from agent training
            agent_results = training_result.get("agent_results") or {}
            simulated_results = []
            for name, result in agent_results.items():
                if isinstance(result, dict):
                    simulated_results.append({
                        "success": result.get("improvement_pct", 0) > 0,
                        "quality_score": result.get("best_score", 0) * 100,
                        "agent": name,
                    })
            if simulated_results:
                self.evaluator.set_task_results(simulated_results)

        return self.evaluator.evaluate()

    def _extract_skills(self, iteration: int) -> int:
        """Extract skills from traces.

        Args:
            iteration: Current iteration number.

        Returns:
            Number of new skills extracted.
        """
        if not self.skill_extractor or not self.interaction_tracker:
            return 0

        # Feed interaction traces to skill extractor
        traces = self.interaction_tracker.export_traces()
        if traces:
            self.skill_extractor.add_trace(
                f"loop_iter_{iteration}",
                traces,
            )

        new_skills = self.skill_extractor.extract_skills()
        return len(new_skills)

    def _evolve_meta(
        self,
        iteration: int,
        training_result: Dict[str, Any],
    ) -> int:
        """Evolve meta-strategies.

        Args:
            iteration: Current iteration number.
            training_result: Results from training.

        Returns:
            Number of meta-skills evolved.
        """
        if not self.meta_optimizer:
            return 0

        # Record strategies from training results
        agent_results = training_result.get("agent_results") or {}
        for name, result in agent_results.items():
            if isinstance(result, dict):
                self.meta_optimizer.record_strategy(
                    strategy_type="grid_search",
                    improvement=result.get("improvement_pct", 0) / 100.0,
                    params=result.get("best_params", {}),
                    agent=name,
                )

        new_meta = self.meta_optimizer.evolve_strategies()
        return len(new_meta)

    def _decide_keep_revert(
        self,
        delta: float,
        report: Optional[EvaluationReport],
    ) -> bool:
        """Decide whether to keep or revert changes.

        Args:
            delta: Improvement delta.
            report: Evaluation report.

        Returns:
            True to keep, False to revert.
        """
        # Keep if improvement is positive or composite score is good
        if delta > 0:
            self._no_improvement_count = 0
            return True

        if report and report.composite_score >= 0.6:
            self._no_improvement_count = 0
            return True

        self._no_improvement_count += 1
        return True  # Always keep for now (revert requires state management)

    def _check_convergence(self) -> Tuple[bool, str]:
        """Check if the optimization loop has converged.

        Returns:
            (converged, reason) tuple.
        """
        if self._no_improvement_count >= self.convergence_patience:
            return True, f"No improvement for {self._no_improvement_count} iterations"

        if self.meta_optimizer:
            analysis = self.meta_optimizer.get_convergence_analysis()
            if analysis.get("converged"):
                return True, analysis.get("reason", "Meta-optimizer convergence")

        return False, ""

    def _build_result(
        self,
        converged: bool = False,
        reason: str = "",
    ) -> LoopResult:
        """Build the final LoopResult.

        Args:
            converged: Whether the loop converged.
            reason: Convergence reason.

        Returns:
            LoopResult.
        """
        total_duration = (time.perf_counter() - self._start_time) * 1000.0

        initial = (
            self._iterations[0].report.composite_score
            if self._iterations and self._iterations[0].report
            else 0.0
        )
        final = (
            self._iterations[-1].report.composite_score
            if self._iterations and self._iterations[-1].report
            else 0.0
        )

        # Collect final recommendations
        recommendations = []
        if self._iterations and self._iterations[-1].report:
            recommendations = self._iterations[-1].report.recommendations

        result = LoopResult(
            run_id=self._run_id,
            iterations=self._iterations,
            total_iterations=len(self._iterations),
            converged=converged,
            convergence_reason=reason,
            initial_score=initial,
            final_score=final,
            total_improvement=final - initial,
            total_duration_ms=total_duration,
            best_iteration=self._best_iteration,
            recommendations=recommendations,
        )

        if self._on_convergence and converged:
            self._on_convergence(result)

        return result

    # =========================================================================
    # Persistence
    # =========================================================================

    def save_result(self, filepath: str) -> bool:
        """Save the loop result to disk.

        Args:
            filepath: Output file path.

        Returns:
            True if save succeeded.
        """
        if not self._iterations:
            return False

        result = self._build_result()
        try:
            path = Path(filepath)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def get_current_result(self) -> Optional[LoopResult]:
        """Get current loop result (in-progress).

        Returns:
            LoopResult or None if no iterations yet.
        """
        if not self._iterations:
            return None
        return self._build_result()

    def reset(self) -> None:
        """Reset all components and state."""
        self._iterations.clear()
        self._current_iteration = 0
        self._no_improvement_count = 0
        self._best_score = 0.0
        self._best_iteration = 0
        self._run_id = uuid.uuid4().hex[:12]
        self._start_time = 0.0

        for component in [
            self.e2e_profiler,
            self.interaction_tracker,
            self.evaluator,
            self.context_manager,
            self.skill_extractor,
            self.knowledge_inheritor,
            self.meta_optimizer,
        ]:
            if component and hasattr(component, 'reset'):
                component.reset()