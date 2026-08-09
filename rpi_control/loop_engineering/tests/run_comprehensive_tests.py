"""
Comprehensive Test Suite - Integrates all evaluation components.

Orchestrates the complete testing pipeline:
1. Enhanced test data generation (8 dimensions)
2. Multi-round data screening with self-inspection (5 rounds)
3. Real model training pipeline (replaces simulated runner)
4. Enhanced loop engineering optimization (convergence detection)
5. Deep RPi compatibility check (hardware + software)
6. Full system verification and report generation

Usage:
    python -m rpi_control.loop_engineering.tests.run_comprehensive_tests
"""

import json
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from .enhanced_test_data import EnhancedTestDataGenerator
from .enhanced_screening import EnhancedScreener, run_enhanced_screening
from .real_training_pipeline import RealTrainingPipeline
from .enhanced_loop import EnhancedLoopRunner
from .rpi_deep_check import RPiDeepChecker


@dataclass
class ComprehensiveTestReport:
    """Complete comprehensive test report."""
    report_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)
    platform: str = ""

    # Phase results
    test_data: Dict[str, Any] = field(default_factory=dict)
    screening: Dict[str, Any] = field(default_factory=dict)
    training: Dict[str, Any] = field(default_factory=dict)
    loop_engineering: Dict[str, Any] = field(default_factory=dict)
    rpi_compatibility: Dict[str, Any] = field(default_factory=dict)

    # Composite metrics
    composite_score: float = 0.0
    grade: str = "N/A"
    total_duration_s: float = 0.0

    # Issues and recommendations
    issues: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    summary: str = ""


class ComprehensiveTestSuite:
    """Comprehensive test suite for the multi-agent system.

    Runs all evaluation phases in sequence:
    1. Test Data Generation
    2. Data Screening & Self-Inspection
    3. Model Training
    4. Loop Engineering Optimization
    5. RPi Compatibility Check
    """

    # Composite weights
    WEIGHTS = {
        "test_data": 0.15,
        "screening": 0.20,
        "training": 0.25,
        "loop_engineering": 0.25,
        "rpi_compatibility": 0.15,
    }

    def __init__(self, output_dir: str = "reports"):
        """Initialize the comprehensive test suite.

        Args:
            output_dir: Output directory for all reports.
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        import platform
        self._platform = platform.machine()

    def run_all(self) -> ComprehensiveTestReport:
        """Run the complete comprehensive test suite.

        Returns:
            ComprehensiveTestReport with all results.
        """
        print("=" * 70)
        print("  COMPREHENSIVE TEST SUITE")
        print("  Intelligent Sampling Robotic Arm Multi-Agent System")
        print(f"  Platform: {self._platform}")
        print(f"  Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

        report = ComprehensiveTestReport(platform=self._platform)
        suite_start = time.time()

        # Phase 1: Test Data Generation
        print(f"\n{'#'*50}")
        print(f"#  PHASE 1/5: Enhanced Test Data Generation")
        print(f"{'#'*50}")
        report.test_data = self._run_phase1_test_data()

        # Phase 2: Model Training (generates data, then screens & trains)
        # NOTE: Training runs BEFORE standalone screening so that
        # the screening phase has actual data to analyze on disk.
        print(f"\n{'#'*50}")
        print(f"#  PHASE 2/5: Real Model Training Pipeline")
        print(f"{'#'*50}")
        report.training = self._run_phase3_training()

        # Phase 3: Data Screening & Self-Inspection
        # Runs AFTER training data generation to detect actual data quality issues
        print(f"\n{'#'*50}")
        print(f"#  PHASE 3/5: Data Screening & Self-Inspection")
        print(f"{'#'*50}")
        report.screening = self._run_phase2_screening()

        # Phase 4: Loop Engineering Optimization
        print(f"\n{'#'*50}")
        print(f"#  PHASE 4/5: Enhanced Loop Engineering")
        print(f"{'#'*50}")
        report.loop_engineering = self._run_phase4_loop_engineering()

        # Phase 5: RPi Compatibility Check
        print(f"\n{'#'*50}")
        print(f"#  PHASE 5/5: Deep RPi Compatibility Check")
        print(f"{'#'*50}")
        report.rpi_compatibility = self._run_phase5_rpi_check()

        # Compute composite
        report.total_duration_s = time.time() - suite_start
        report.composite_score = self._compute_composite(report)
        report.grade = self._compute_grade(report.composite_score)
        report.recommendations = self._collect_recommendations(report)
        report.summary = self._generate_summary(report)

        # Save
        self._save_report(report)

        # Print final summary
        self._print_final_summary(report)

        return report

    # =========================================================================
    # Phase 1: Test Data Generation
    # =========================================================================

    def _run_phase1_test_data(self) -> Dict[str, Any]:
        """Generate comprehensive test data."""
        try:
            generator = EnhancedTestDataGenerator(
                seed=42,
                output_dir=str(self.output_dir / "test_data"),
            )
            data = generator.generate_all()
            return {
                "status": "completed",
                "overall_quality_score": data.get("overall_quality_score", 0),
                "categories": list(data.get("categories", {}).keys()),
                "duration_s": 0,
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    # =========================================================================
    # Phase 2: Data Screening
    # =========================================================================

    def _run_phase2_screening(self) -> Dict[str, Any]:
        """Run enhanced data screening."""
        try:
            result = run_enhanced_screening(
                data_dir="data/training",
                output_dir=str(self.output_dir),
                num_rounds=5,
            )
            return {
                "status": "completed",
                "total_rounds": result.get("total_rounds", 0),
                "all_passed": result.get("all_passed", False),
                "final_score": result.get("final_score", 0),
                "self_inspection": result.get("self_inspection", ""),
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    # =========================================================================
    # Phase 3: Model Training
    # =========================================================================

    def _run_phase3_training(self) -> Dict[str, Any]:
        """Run real model training pipeline."""
        try:
            pipeline = RealTrainingPipeline(
                data_dir="data/training",
                output_dir=str(self.output_dir),
            )
            result = pipeline.run_full_training(
                num_rounds=3,
                samples_per_round=5000,
            )
            return {
                "status": "completed",
                "pipeline_id": result.pipeline_id,
                "total_rounds": result.total_rounds,
                "best_round": result.best_round,
                "best_score": result.best_score,
                "total_samples": result.total_samples_generated,
                "duration_s": result.total_duration_s,
                "recommendations": result.recommendations,
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    # =========================================================================
    # Phase 4: Loop Engineering
    # =========================================================================

    def _run_phase4_loop_engineering(self) -> Dict[str, Any]:
        """Run enhanced loop engineering optimization."""
        try:
            # Create training runner that uses real pipeline
            pipeline = RealTrainingPipeline(output_dir=str(self.output_dir))
            training_runner = pipeline.create_training_runner()

            loop_runner = EnhancedLoopRunner(output_dir=str(self.output_dir))
            loop_runner.set_training_runner(training_runner)

            loop_runner.set_evaluator(lambda results: float(np.mean([
                r.get("best_score", 0.5)
                for r in results.get("agent_results", {}).values()
                if isinstance(r, dict)
            ]) or 0.5))

            result = loop_runner.run_enhanced_loop(max_iterations=10)

            return {
                "status": "completed",
                "run_id": result.run_id,
                "total_iterations": result.total_iterations,
                "converged": result.converged,
                "convergence_reason": result.convergence_reason,
                "initial_score": result.initial_score,
                "final_score": result.final_score,
                "total_improvement": result.total_improvement,
                "best_score": result.best_score,
                "best_iteration": result.best_iteration,
                "duration_ms": result.total_duration_ms,
                "meta_skills_evolved": len(result.meta_skills_evolved),
                "recommendations": result.recommendations,
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    # =========================================================================
    # Phase 5: RPi Compatibility
    # =========================================================================

    def _run_phase5_rpi_check(self) -> Dict[str, Any]:
        """Run deep RPi compatibility check."""
        try:
            checker = RPiDeepChecker(output_dir=str(self.output_dir))
            report = checker.run_deep_check()

            return {
                "status": "completed",
                "is_raspberry_pi": report.is_raspberry_pi,
                "rpi_model": report.rpi_model,
                "total_checks": report.total_checks,
                "passed_checks": report.passed_checks,
                "compatibility_score": report.compatibility_score,
                "overall_verdict": report.overall_verdict,
                "critical_failures": report.critical_failures,
                "recommendations": report.recommendations,
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    # =========================================================================
    # Scoring & Reporting
    # =========================================================================

    def _compute_composite(self, report: ComprehensiveTestReport) -> float:
        """Compute weighted composite score."""
        scores = {}

        # Test data quality
        td = report.test_data
        scores["test_data"] = td.get("overall_quality_score", 0.5)

        # Screening quality
        scr = report.screening
        scores["screening"] = scr.get("final_score", 0) / 100.0 if scr.get("final_score") else 0.5

        # Training quality
        tr = report.training
        scores["training"] = tr.get("best_score", 0.5)

        # Loop engineering
        le = report.loop_engineering
        scores["loop_engineering"] = le.get("final_score", 0.5)

        # RPi compatibility
        rpi = report.rpi_compatibility
        scores["rpi_compatibility"] = rpi.get("compatibility_score", 0.5)

        composite = sum(
            scores[key] * self.WEIGHTS[key]
            for key in self.WEIGHTS
        )
        return round(composite, 4)

    def _compute_grade(self, score: float) -> str:
        """Map score to grade."""
        thresholds = [
            (0.95, "A+"), (0.90, "A"), (0.85, "A-"),
            (0.80, "B+"), (0.75, "B"), (0.70, "B-"),
            (0.65, "C+"), (0.60, "C"), (0.50, "D"), (0.0, "F"),
        ]
        for t, g in thresholds:
            if score >= t:
                return g
        return "F"

    def _collect_recommendations(self, report: ComprehensiveTestReport) -> List[str]:
        """Collect all recommendations."""
        recs = []

        # From training
        tr = report.training
        if tr.get("recommendations"):
            recs.extend(tr["recommendations"])

        # From loop engineering
        le = report.loop_engineering
        if le.get("recommendations"):
            recs.extend(le["recommendations"])

        # From RPi
        rpi = report.rpi_compatibility
        if rpi.get("recommendations"):
            recs.extend(rpi["recommendations"])

        # Deduplicate
        seen = set()
        unique = []
        for r in recs:
            if r not in seen:
                seen.add(r)
                unique.append(r)

        return unique[:10]

    def _generate_summary(self, report: ComprehensiveTestReport) -> str:
        """Generate human-readable summary."""
        parts = [
            f"Comprehensive Test Suite Complete",
            f"Platform: {report.platform}",
            f"Composite Score: {report.composite_score:.3f} ({report.grade})",
            f"Duration: {report.total_duration_s:.1f}s",
        ]

        # Phase statuses
        phases = {
            "Test Data": report.test_data.get("status"),
            "Screening": report.screening.get("status"),
            "Training": report.training.get("status"),
            "Loop Eng": report.loop_engineering.get("status"),
            "RPi Check": report.rpi_compatibility.get("status"),
        }

        failed = [k for k, v in phases.items() if v == "failed"]
        if failed:
            parts.append(f"Failed Phases: {', '.join(failed)}")
        else:
            parts.append("All phases completed successfully")

        return " | ".join(parts)

    def _print_final_summary(self, report: ComprehensiveTestReport) -> None:
        """Print final comprehensive summary."""
        print(f"\n{'='*70}")
        print(f"  FINAL COMPREHENSIVE TEST SUMMARY")
        print(f"{'='*70}")
        print(f"  Report ID: {report.report_id}")
        print(f"  Platform: {report.platform}")
        print(f"  Composite Score: {report.composite_score:.3f} ({report.grade})")
        print(f"  Total Duration: {report.total_duration_s:.1f}s")

        print(f"\n  Phase Results:")
        print(f"    [1] Test Data:      {report.test_data.get('status', 'N/A')}")
        if report.test_data.get("overall_quality_score"):
            print(f"        Quality Score: {report.test_data['overall_quality_score']:.4f}")

        print(f"    [2] Training:       {report.training.get('status', 'N/A')}")
        if report.training.get("best_score"):
            print(f"        Best Score: {report.training['best_score']:.4f}")
            print(f"        Total Samples: {report.training.get('total_samples', 0):,}")

        print(f"    [3] Screening:      {report.screening.get('status', 'N/A')}")
        if report.screening.get("final_score"):
            print(f"        Final Score: {report.screening['final_score']:.0f}/100")
            print(f"        All Passed: {report.screening.get('all_passed', False)}")

        print(f"    [4] Loop Eng:       {report.loop_engineering.get('status', 'N/A')}")
        if report.loop_engineering.get("final_score"):
            le = report.loop_engineering
            print(f"        Score: {le['initial_score']:.4f} → {le['final_score']:.4f}")
            print(f"        Converged: {le.get('converged', False)}")
            print(f"        Meta-Skills: {le.get('meta_skills_evolved', 0)}")

        print(f"    [5] RPi Check:      {report.rpi_compatibility.get('status', 'N/A')}")
        if report.rpi_compatibility.get("compatibility_score"):
            rpi = report.rpi_compatibility
            print(f"        Score: {rpi['compatibility_score']:.2%}")
            print(f"        Verdict: {rpi.get('overall_verdict', 'N/A')}")

        print(f"\n  Score Breakdown:")
        for key, weight in self.WEIGHTS.items():
            phase_scores = {
                "test_data": report.test_data.get("overall_quality_score", 0),
                "screening": report.screening.get("final_score", 0) / 100.0,
                "training": report.training.get("best_score", 0),
                "loop_engineering": report.loop_engineering.get("final_score", 0),
                "rpi_compatibility": report.rpi_compatibility.get("compatibility_score", 0),
            }
            score = phase_scores.get(key, 0)
            print(f"    {key:20s}: {score:.4f} × {weight:.2f} = {score * weight:.4f}")

        if report.recommendations:
            print(f"\n  Top Recommendations:")
            for rec in report.recommendations[:5]:
                print(f"    • {rec}")

        print(f"\n  Summary: {report.summary}")
        print(f"{'='*70}")

    def _save_report(self, report: ComprehensiveTestReport) -> None:
        """Save comprehensive test report to disk."""
        filepath = self.output_dir / f"comprehensive_test_{report.report_id}.json"
        data = {
            "report_id": report.report_id,
            "timestamp": report.timestamp,
            "platform": report.platform,
            "composite_score": report.composite_score,
            "grade": report.grade,
            "total_duration_s": report.total_duration_s,
            "summary": report.summary,
            "phases": {
                "test_data": report.test_data,
                "screening": report.screening,
                "training": report.training,
                "loop_engineering": report.loop_engineering,
                "rpi_compatibility": report.rpi_compatibility,
            },
            "recommendations": report.recommendations,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"\n  Comprehensive report saved: {filepath}")


# =============================================================================
# Quick Runner
# =============================================================================

def run_comprehensive_tests(output_dir: str = "reports") -> ComprehensiveTestReport:
    """Run all comprehensive tests.

    Args:
        output_dir: Output directory.

    Returns:
        ComprehensiveTestReport.
    """
    suite = ComprehensiveTestSuite(output_dir=output_dir)
    return suite.run_all()


if __name__ == "__main__":
    report = run_comprehensive_tests()
    print(f"\n{'='*70}")
    print(f"  ALL TESTS COMPLETE")
    print(f"  Final Score: {report.composite_score:.3f} ({report.grade})")
    print(f"{'='*70}")