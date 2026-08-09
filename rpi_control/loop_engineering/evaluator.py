"""
Multi-dimensional evaluation system for the multi-agent system.

Implements a 7-dimensional evaluation framework:
1. Latency: End-to-end execution speed
2. Reliability: Task success rate and error recovery
3. Quality: Output quality and correctness
4. Efficiency: Interaction efficiency and tool call count
5. Robustness: Stability under edge cases and adversarial inputs
6. Context Health: State continuity and context decay
7. Reusability: Skill reuse and knowledge transfer

The evaluator aggregates metrics from the profiler, interaction tracker,
and context manager to produce a weighted composite score. This drives
the Loop Engineering optimization cycle.

Usage:
    evaluator = MultiDimensionEvaluator(weights={...})
    evaluator.set_profiler_data(profiler_stats)
    evaluator.set_interaction_data(interaction_stats)
    report = evaluator.evaluate()
    print(report.composite_score)
"""

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class DimensionScore:
    """Score for a single evaluation dimension.

    Attributes:
        name: Dimension name (e.g., 'latency', 'reliability').
        score: Normalized score (0.0 - 1.0, higher is better).
        weight: Weight in the composite score.
        details: Detailed breakdown of sub-metrics.
        flags: Warning or info flags.
    """
    name: str
    score: float = 0.0
    weight: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    flags: List[str] = field(default_factory=list)

    @property
    def weighted_score(self) -> float:
        """Compute weighted score: score * weight."""
        return self.score * self.weight


@dataclass
class EvaluationReport:
    """Complete multi-dimensional evaluation report.

    Attributes:
        report_id: Unique report identifier.
        timestamp: When the evaluation was performed.
        dimensions: Per-dimension scores.
        composite_score: Weighted composite score (0.0 - 1.0).
        grade: Letter grade (A+ through F).
        summary: Human-readable summary.
        recommendations: Actionable improvement recommendations.
        raw_data: Original input data for traceability.
    """
    report_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)
    dimensions: Dict[str, DimensionScore] = field(default_factory=dict)
    composite_score: float = 0.0
    grade: str = "N/A"
    summary: str = ""
    recommendations: List[str] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to a serializable dict."""
        return {
            "report_id": self.report_id,
            "timestamp": datetime.fromtimestamp(self.timestamp).isoformat(),
            "composite_score": round(self.composite_score, 4),
            "grade": self.grade,
            "summary": self.summary,
            "dimensions": {
                name: {
                    "score": round(d.score, 4),
                    "weight": d.weight,
                    "weighted_score": round(d.weighted_score, 4),
                    "details": d.details,
                    "flags": d.flags,
                }
                for name, d in self.dimensions.items()
            },
            "recommendations": self.recommendations,
        }


# =============================================================================
# Multi-dimension Evaluator
# =============================================================================


class MultiDimensionEvaluator:
    """7-dimensional evaluation system for the multi-agent system.

    Evaluates the system across seven dimensions and produces a weighted
    composite score. Each dimension is scored from 0.0 (worst) to 1.0 (best).

    Dimensions:
        1. Latency (重量15%): End-to-end speed; lower is better.
        2. Reliability (重量20%): Task success rate and error recovery.
        3. Quality (重量15%): Output quality and correctness.
        4. Efficiency (重量15%): Interaction efficiency and tool calls.
        5. Robustness (重量15%): Stability under edge cases.
        6. Context Health (重量10%): State continuity and context decay.
        7. Reusability (重量10%): Skill reuse and knowledge transfer.
    """

    # Default weights (sum to 1.0)
    DEFAULT_WEIGHTS = {
        "latency": 0.15,
        "reliability": 0.20,
        "quality": 0.15,
        "efficiency": 0.15,
        "robustness": 0.15,
        "context_health": 0.10,
        "reusability": 0.10,
    }

    # Grading scale
    GRADE_THRESHOLDS = [
        (0.95, "A+"),
        (0.90, "A"),
        (0.85, "A-"),
        (0.80, "B+"),
        (0.75, "B"),
        (0.70, "B-"),
        (0.65, "C+"),
        (0.60, "C"),
        (0.50, "D"),
        (0.0, "F"),
    ]

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        report_dir: Optional[str] = None,
    ):
        """Initialize the evaluator.

        Args:
            weights: Optional dimension weights. Must sum to ~1.0.
            report_dir: Directory to save evaluation reports.
        """
        self.weights = weights or dict(self.DEFAULT_WEIGHTS)
        self._validate_weights()
        self.report_dir = Path(report_dir) if report_dir else None

        # Data sources
        self._profiler_data: Dict[str, Any] = {}
        self._interaction_data: Dict[str, Any] = {}
        self._context_data: Dict[str, Any] = {}
        self._task_results: List[Dict[str, Any]] = []
        self._skill_data: Dict[str, Any] = {}

        # History
        self._reports: List[EvaluationReport] = []
        self._score_history: List[Dict[str, float]] = []

    def _validate_weights(self) -> None:
        """Validate that weights sum to approximately 1.0."""
        total = sum(self.weights.values())
        if abs(total - 1.0) > 0.01:
            # Normalize weights
            self.weights = {k: v / total for k, v in self.weights.items()}

    # =========================================================================
    # Data Input
    # =========================================================================

    def set_profiler_data(self, stats: Dict[str, Any]) -> None:
        """Set profiler statistics for latency dimension.

        Args:
            stats: Statistics dict from AgentProfiler or EndToEndProfiler.
        """
        self._profiler_data = stats

    def set_interaction_data(self, stats: Dict[str, Any]) -> None:
        """Set interaction tracker statistics for efficiency dimension.

        Args:
            stats: Statistics dict from InteractionTracker.
        """
        self._interaction_data = stats

    def set_context_data(self, stats: Dict[str, Any]) -> None:
        """Set context manager statistics for context_health dimension.

        Args:
            stats: Statistics dict from ContextManager.
        """
        self._context_data = stats

    def set_task_results(self, results: List[Dict[str, Any]]) -> None:
        """Set task execution results for reliability/quality dimensions.

        Args:
            results: List of task result dicts with 'success', 'error', etc.
        """
        self._task_results = results

    def set_skill_data(self, stats: Dict[str, Any]) -> None:
        """Set skill extraction statistics for reusability dimension.

        Args:
            stats: Statistics dict from SkillExtractor.
        """
        self._skill_data = stats

    # =========================================================================
    # Dimension Scoring
    # =========================================================================

    def _score_latency(self) -> DimensionScore:
        """Score end-to-end latency.

        Lower latency is better. Uses p50, p95, p99 from profiler data.
        Ideal: p50 < 50ms, p95 < 200ms, p99 < 500ms.
        """
        dim = DimensionScore(
            name="latency",
            weight=self.weights.get("latency", 0.15),
        )

        data = self._profiler_data
        if not data:
            dim.flags.append("No profiler data available")
            return dim

        p50 = data.get("p50_ms", data.get("e2e_p50_ms", data.get("avg_ms", 1000)))
        p95 = data.get("p95_ms", data.get("e2e_p95_ms", 1000))
        p99 = data.get("p99_ms", data.get("e2e_p99_ms", 1000))

        # Score each percentile: 1.0 at ideal, decays to 0.0
        p50_score = max(0.0, 1.0 - p50 / 100.0) if p50 > 0 else 0.0
        p95_score = max(0.0, 1.0 - p95 / 400.0) if p95 > 0 else 0.0
        p99_score = max(0.0, 1.0 - p99 / 1000.0) if p99 > 0 else 0.0

        dim.score = 0.4 * p50_score + 0.35 * p95_score + 0.25 * p99_score
        dim.score = max(0.0, min(1.0, dim.score))

        dim.details = {
            "p50_ms": round(p50, 2),
            "p95_ms": round(p95, 2),
            "p99_ms": round(p99, 2),
            "p50_score": round(p50_score, 4),
            "p95_score": round(p95_score, 4),
            "p99_score": round(p99_score, 4),
        }

        if p95 > 200:
            dim.flags.append(f"P95 latency ({p95:.0f}ms) exceeds 200ms threshold")
        if p99 > 500:
            dim.flags.append(f"P99 latency ({p99:.0f}ms) exceeds 500ms threshold")

        return dim

    def _score_reliability(self) -> DimensionScore:
        """Score task reliability.

        Measures task success rate, error recovery rate, and consistency.
        """
        dim = DimensionScore(
            name="reliability",
            weight=self.weights.get("reliability", 0.20),
        )

        results = self._task_results
        if not results:
            dim.flags.append("No task results available")
            return dim

        total = len(results)
        successes = sum(1 for r in results if r.get("success", False) in (True, 1))
        errors = sum(1 for r in results if r.get("error"))
        recovered = sum(1 for r in results if r.get("recovered", False))
        aborts = sum(1 for r in results if r.get("aborted", False))

        success_rate = successes / total if total > 0 else 0.0
        recovery_rate = recovered / errors if errors > 0 else 1.0
        abort_rate = aborts / total if total > 0 else 0.0

        # Composite: 60% success, 25% recovery, -15% abort penalty
        dim.score = 0.6 * success_rate + 0.25 * recovery_rate - 0.15 * abort_rate
        dim.score = max(0.0, min(1.0, dim.score))

        dim.details = {
            "total_tasks": total,
            "successes": successes,
            "errors": errors,
            "recovered": recovered,
            "aborts": aborts,
            "success_rate": round(success_rate, 4),
            "recovery_rate": round(recovery_rate, 4),
            "abort_rate": round(abort_rate, 4),
        }

        if success_rate < 0.8:
            dim.flags.append(f"Success rate ({success_rate:.1%}) below 80%")
        if abort_rate > 0.1:
            dim.flags.append(f"Abort rate ({abort_rate:.1%}) above 10%")

        return dim

    def _score_quality(self) -> DimensionScore:
        """Score output quality.

        Measures quality scores, defect rates, and inspection results.
        """
        dim = DimensionScore(
            name="quality",
            weight=self.weights.get("quality", 0.15),
        )

        results = self._task_results
        if not results:
            dim.flags.append("No task results for quality assessment")
            return dim

        quality_scores = [
            r.get("quality_score", 0.0)
            for r in results
            if isinstance(r.get("quality_score"), (int, float))
        ]
        defect_counts = [
            len(r.get("defects", [])) if isinstance(r.get("defects"), list) else 0
            for r in results
            if "defects" in r
        ]
        passed = sum(
            1 for r in results
            if r.get("quality_passed", r.get("success", False))
        )

        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
        avg_defects = sum(defect_counts) / len(defect_counts) if defect_counts else 0
        pass_rate = passed / len(results) if results else 0.0

        # Normalize quality score (assuming 0-100 scale)
        quality_norm = avg_quality / 100.0 if avg_quality > 0 else 0.0
        # Defect penalty: 0 defects = 1.0, 5+ defects = 0.0
        defect_score = max(0.0, 1.0 - avg_defects / 5.0)

        dim.score = 0.5 * quality_norm + 0.3 * defect_score + 0.2 * pass_rate
        dim.score = max(0.0, min(1.0, dim.score))

        dim.details = {
            "avg_quality_score": round(avg_quality, 2),
            "avg_defects": round(avg_defects, 2),
            "pass_rate": round(pass_rate, 4),
            "samples_evaluated": len(quality_scores),
        }

        if avg_quality < 70:
            dim.flags.append(f"Average quality score ({avg_quality:.1f}) below 70")
        if avg_defects > 1:
            dim.flags.append(f"Average defects ({avg_defects:.1f}) above 1")

        return dim

    def _score_efficiency(self) -> DimensionScore:
        """Score interaction efficiency.

        Measures interaction rounds, tool calls, redundancy, and context size.
        """
        dim = DimensionScore(
            name="efficiency",
            weight=self.weights.get("efficiency", 0.15),
        )

        data = self._interaction_data
        if not data:
            dim.flags.append("No interaction data available")
            return dim

        total = data.get("total_interactions", 0)
        rounds_per_task = data.get("rounds_per_task", 0)
        redundant = data.get("redundant_calls", 0)
        context_size = data.get("context_size_stats", {}).get("avg", 0)

        # Ideal: < 10 rounds per task, no redundancy, small context
        round_score = max(0.0, 1.0 - rounds_per_task / 20.0)
        redundant_score = max(0.0, 1.0 - redundant / 10.0)
        context_score = max(0.0, 1.0 - context_size / 50.0)

        dim.score = 0.4 * round_score + 0.3 * redundant_score + 0.3 * context_score
        dim.score = max(0.0, min(1.0, dim.score))

        dim.details = {
            "total_interactions": total,
            "rounds_per_task": round(rounds_per_task, 2),
            "redundant_calls": redundant,
            "avg_context_size": round(context_size, 1),
            "round_score": round(round_score, 4),
            "redundant_score": round(redundant_score, 4),
            "context_score": round(context_score, 4),
        }

        if rounds_per_task > 10:
            dim.flags.append(f"High rounds per task ({rounds_per_task:.1f})")
        if redundant > 3:
            dim.flags.append(f"Redundant calls detected ({redundant})")
        if context_size > 20:
            dim.flags.append(f"Large context size ({context_size:.0f} keys)")

        return dim

    def _score_robustness(self) -> DimensionScore:
        """Score system robustness.

        Measures stability under errors, edge cases, and adversarial inputs.
        """
        dim = DimensionScore(
            name="robustness",
            weight=self.weights.get("robustness", 0.15),
        )

        results = self._task_results
        data = self._profiler_data

        if not results:
            dim.flags.append("No task results for robustness assessment")
            return dim

        total = len(results)

        # Error handling: how many errors were gracefully handled
        errors = sum(1 for r in results if r.get("error"))
        unhandled = sum(1 for r in results if r.get("error") and not r.get("recovered", False))
        graceful = sum(1 for r in results if r.get("error") and r.get("recovered", False))

        # Consistency: variance in execution time
        per_op = data.get("per_operation", {}) if data else {}
        consistency_scores = []
        for op_stats in per_op.values():
            if op_stats.get("count", 0) > 1:
                # Lower coefficient of variation = more consistent
                avg = op_stats.get("avg_ms", 0)
                max_ms = op_stats.get("max_ms", 0)
                if avg > 0:
                    cv = (max_ms - avg) / avg
                    consistency_scores.append(max(0.0, 1.0 - cv))

        consistency = (
            sum(consistency_scores) / len(consistency_scores)
            if consistency_scores else 0.5
        )

        # Error handling score
        error_rate = errors / total if total > 0 else 0.0
        graceful_rate = graceful / errors if errors > 0 else 1.0
        error_score = max(0.0, 1.0 - error_rate * 2.0) * 0.5 + graceful_rate * 0.5

        dim.score = 0.5 * error_score + 0.5 * consistency
        dim.score = max(0.0, min(1.0, dim.score))

        dim.details = {
            "total_tasks": total,
            "errors": errors,
            "graceful_recoveries": graceful,
            "unhandled_errors": unhandled,
            "error_rate": round(error_rate, 4),
            "graceful_rate": round(graceful_rate, 4),
            "consistency": round(consistency, 4),
        }

        if unhandled > 0:
            dim.flags.append(f"Unhandled errors detected ({unhandled})")
        if consistency < 0.5:
            dim.flags.append("Low execution consistency")

        return dim

    def _score_context_health(self) -> DimensionScore:
        """Score context health.

        Measures context continuity, decay detection, and state persistence.
        """
        dim = DimensionScore(
            name="context_health",
            weight=self.weights.get("context_health", 0.10),
        )

        data = self._context_data
        if not data:
            # Use interaction data as fallback
            data = self._interaction_data

        if not data:
            dim.flags.append("No context data available")
            return dim

        # Context health factors
        state_snapshots = data.get("state_snapshots", 0)
        compression_count = data.get("compression_count", 0)
        decay_events = data.get("decay_events", 0)
        persistence_success = data.get("persistence_success_rate", 1.0)

        # Score: more snapshots = better, fewer decay events = better
        snapshot_score = min(1.0, state_snapshots / 10.0)
        decay_score = max(0.0, 1.0 - decay_events / 5.0)
        compression_score = min(1.0, compression_count / 3.0)  # Active compression is good

        dim.score = 0.4 * persistence_success + 0.3 * snapshot_score + 0.3 * decay_score
        dim.score = max(0.0, min(1.0, dim.score))

        dim.details = {
            "state_snapshots": state_snapshots,
            "compression_count": compression_count,
            "decay_events": decay_events,
            "persistence_success_rate": round(persistence_success, 4),
            "snapshot_score": round(snapshot_score, 4),
            "decay_score": round(decay_score, 4),
        }

        if decay_events > 0:
            dim.flags.append(f"Context decay detected ({decay_events} events)")
        if persistence_success < 0.9:
            dim.flags.append("State persistence failures detected")

        return dim

    def _score_reusability(self) -> DimensionScore:
        """Score skill reusability.

        Measures skill extraction, reuse rate, and knowledge transfer.
        """
        dim = DimensionScore(
            name="reusability",
            weight=self.weights.get("reusability", 0.10),
        )

        data = self._skill_data
        if not data:
            dim.flags.append("No skill data available")
            return dim

        skills_extracted = data.get("skills_extracted", 0)
        skills_reused = data.get("skills_reused", 0)
        reuse_rate = data.get("reuse_rate", 0.0)
        skill_effectiveness = data.get("skill_effectiveness", 0.0)

        # Score: more skills extracted and reused = better
        extraction_score = min(1.0, skills_extracted / 5.0)
        reuse_score = min(1.0, skills_reused / 3.0)

        dim.score = 0.4 * reuse_rate + 0.3 * extraction_score + 0.3 * skill_effectiveness
        dim.score = max(0.0, min(1.0, dim.score))

        dim.details = {
            "skills_extracted": skills_extracted,
            "skills_reused": skills_reused,
            "reuse_rate": round(reuse_rate, 4),
            "skill_effectiveness": round(skill_effectiveness, 4),
        }

        if skills_extracted == 0:
            dim.flags.append("No skills extracted yet")
        if reuse_rate < 0.3 and skills_extracted > 0:
            dim.flags.append(f"Low skill reuse rate ({reuse_rate:.1%})")

        return dim

    # =========================================================================
    # Evaluation
    # =========================================================================

    def evaluate(self) -> EvaluationReport:
        """Run the full multi-dimensional evaluation.

        Returns:
            EvaluationReport with all dimension scores and composite score.
        """
        report = EvaluationReport()

        # Score each dimension
        report.dimensions["latency"] = self._score_latency()
        report.dimensions["reliability"] = self._score_reliability()
        report.dimensions["quality"] = self._score_quality()
        report.dimensions["efficiency"] = self._score_efficiency()
        report.dimensions["robustness"] = self._score_robustness()
        report.dimensions["context_health"] = self._score_context_health()
        report.dimensions["reusability"] = self._score_reusability()

        # Compute composite score
        report.composite_score = sum(
            d.weighted_score for d in report.dimensions.values()
        )

        # Assign grade
        report.grade = self._compute_grade(report.composite_score)

        # Generate summary
        report.summary = self._generate_summary(report)

        # Generate recommendations
        report.recommendations = self._generate_recommendations(report)

        # Store raw data for traceability
        report.raw_data = {
            "profiler": self._profiler_data,
            "interactions": self._interaction_data,
            "context": self._context_data,
            "tasks": self._task_results,
            "skills": self._skill_data,
        }

        # Save to history
        self._reports.append(report)
        self._score_history.append({
            "composite": report.composite_score,
            **{name: d.score for name, d in report.dimensions.items()},
        })

        # Save to disk if report_dir is set
        if self.report_dir:
            self._save_report(report)

        return report

    def _compute_grade(self, score: float) -> str:
        """Map composite score to letter grade.

        Args:
            score: Composite score (0.0 - 1.0).

        Returns:
            Letter grade string.
        """
        for threshold, grade in self.GRADE_THRESHOLDS:
            if score >= threshold:
                return grade
        return "F"

    def _generate_summary(self, report: EvaluationReport) -> str:
        """Generate a human-readable summary.

        Args:
            report: The evaluation report.

        Returns:
            Summary string.
        """
        strengths = []
        weaknesses = []

        for name, dim in report.dimensions.items():
            if dim.score >= 0.8:
                strengths.append(name)
            elif dim.score < 0.5:
                weaknesses.append(name)

        parts = [f"Composite Score: {report.composite_score:.3f} ({report.grade})"]

        if strengths:
            parts.append(f"Strengths: {', '.join(strengths)}")
        if weaknesses:
            parts.append(f"Needs Improvement: {', '.join(weaknesses)}")

        return " | ".join(parts)

    def _generate_recommendations(self, report: EvaluationReport) -> List[str]:
        """Generate actionable recommendations based on evaluation.

        Processes all dimensions in a single pass (previously two passes).

        Args:
            report: The evaluation report.

        Returns:
            List of recommendation strings.
        """
        recommendations = []

        for name, dim in report.dimensions.items():
            # Low-score recommendations
            if dim.score < 0.5:
                if name == "latency":
                    recommendations.append(
                        f"[LATENCY] Score {dim.score:.2f}: "
                        "Optimize slow operations, consider caching or parallel execution."
                    )
                elif name == "reliability":
                    recommendations.append(
                        f"[RELIABILITY] Score {dim.score:.2f}: "
                        "Improve error handling, add more recovery paths, reduce abort rate."
                    )
                elif name == "quality":
                    recommendations.append(
                        f"[QUALITY] Score {dim.score:.2f}: "
                        "Tune quality thresholds, improve defect detection, enhance inspection."
                    )
                elif name == "efficiency":
                    recommendations.append(
                        f"[EFFICIENCY] Score {dim.score:.2f}: "
                        "Reduce interaction rounds, eliminate redundant calls, compress context."
                    )
                elif name == "robustness":
                    recommendations.append(
                        f"[ROBUSTNESS] Score {dim.score:.2f}: "
                        "Add edge case testing, improve error recovery, increase consistency."
                    )
                elif name == "context_health":
                    recommendations.append(
                        f"[CONTEXT] Score {dim.score:.2f}: "
                        "Enable state snapshots, reduce context decay, improve persistence."
                    )
                elif name == "reusability":
                    recommendations.append(
                        f"[REUSABILITY] Score {dim.score:.2f}: "
                        "Extract reusable skills from execution traces, improve skill reuse."
                    )
            # Flag-based recommendations (combined from second pass)
            for flag in dim.flags:
                recommendations.append(f"[{name.upper()}] {flag}")

        return recommendations

    # =========================================================================
    # History & Persistence
    # =========================================================================

    def get_trend(self, metric: str = "composite") -> List[float]:
        """Get score trend over time for a specific metric.

        Args:
            metric: Metric name (composite or dimension name).

        Returns:
            List of scores in chronological order.
        """
        if metric == "composite":
            return [r["composite"] for r in self._score_history]
        return [
            r.get(metric, 0.0)
            for r in self._score_history
            if metric in r
        ]

    def get_improvement_delta(self) -> float:
        """Get the improvement delta between the last two evaluations.

        Returns:
            Difference in composite score (positive = improvement).
        """
        if len(self._score_history) < 2:
            return 0.0
        return self._score_history[-1]["composite"] - self._score_history[-2]["composite"]

    def _save_report(self, report: EvaluationReport) -> None:
        """Save evaluation report to disk.

        Args:
            report: The evaluation report to save.
        """
        if not self.report_dir:
            return
        self.report_dir.mkdir(parents=True, exist_ok=True)
        filename = (
            f"eval_{datetime.fromtimestamp(report.timestamp).strftime('%Y%m%d_%H%M%S')}"
            f"_{report.report_id}.json"
        )
        filepath = self.report_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)

    def get_latest_report(self) -> Optional[EvaluationReport]:
        """Get the most recent evaluation report.

        Returns:
            Latest EvaluationReport or None.
        """
        return self._reports[-1] if self._reports else None

    def reset(self) -> None:
        """Reset all evaluation data."""
        self._profiler_data = {}
        self._interaction_data = {}
        self._context_data = {}
        self._task_results = []
        self._skill_data = {}
        # Don't reset history for trend analysis