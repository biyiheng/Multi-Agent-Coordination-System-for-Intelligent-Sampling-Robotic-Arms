"""
Unit tests for the MultiDimensionEvaluator.

Tests cover:
1. Dimension scoring (latency, reliability, quality, efficiency, robustness, context_health, reusability)
2. Weight validation and normalization
3. Composite score computation
4. Grade assignment
5. Report generation
6. Trend tracking
7. Improvement delta
8. Report persistence
"""

import json
import os
import tempfile
import pytest
from loop_engineering.evaluator import (
    MultiDimensionEvaluator,
    DimensionScore,
    EvaluationReport,
)


# =============================================================================
# Test Data Fixtures
# =============================================================================


@pytest.fixture
def sample_profiler_data():
    """Sample profiler statistics for testing."""
    return {
        "total_calls": 50,
        "total_duration_ms": 2500.0,
        "avg_ms": 50.0,
        "p50_ms": 45.0,
        "p95_ms": 120.0,
        "p99_ms": 300.0,
        "min_ms": 10.0,
        "max_ms": 500.0,
        "per_operation": {
            "process": {
                "count": 25,
                "avg_ms": 40.0,
                "max_ms": 100.0,
                "min_ms": 10.0,
            },
            "validate": {
                "count": 25,
                "avg_ms": 60.0,
                "max_ms": 150.0,
                "min_ms": 20.0,
            },
        },
    }


@pytest.fixture
def sample_interaction_data():
    """Sample interaction tracker statistics for testing."""
    return {
        "total_interactions": 30,
        "rounds_per_task": 8.0,
        "rounds_by_type": {"agent_call": 20, "tool_call": 7, "state_query": 3},
        "redundant_calls": 2,
        "context_size_stats": {"avg": 15.0, "min": 5, "max": 30},
        "dependency_graph": {
            "orchestrator": ["motion", "vision", "safety"],
            "motion": ["safety"],
        },
    }


@pytest.fixture
def sample_task_results():
    """Sample task execution results for testing."""
    return [
        {"success": True, "error": None, "quality_score": 85.0, "defects": [], "quality_passed": True},
        {"success": True, "error": None, "quality_score": 90.0, "defects": [], "quality_passed": True},
        {"success": True, "error": None, "quality_score": 78.0, "defects": ["scratch"], "quality_passed": True},
        {"success": False, "error": "TimeoutError", "recovered": True, "quality_score": 0.0},
        {"success": True, "error": None, "quality_score": 92.0, "defects": [], "quality_passed": True},
        {"success": False, "error": "SafetyError", "recovered": False, "aborted": True, "quality_score": 0.0},
        {"success": True, "error": None, "quality_score": 88.0, "defects": [], "quality_passed": True},
        {"success": True, "error": None, "quality_score": 75.0, "defects": ["discoloration"], "quality_passed": False},
        {"success": True, "error": None, "quality_score": 95.0, "defects": [], "quality_passed": True},
        {"success": True, "error": None, "quality_score": 82.0, "defects": [], "quality_passed": True},
    ]


@pytest.fixture
def sample_context_data():
    """Sample context manager statistics for testing."""
    return {
        "state_snapshots": 5,
        "compression_count": 2,
        "decay_events": 1,
        "persistence_success_rate": 0.95,
    }


@pytest.fixture
def sample_skill_data():
    """Sample skill extraction statistics for testing."""
    return {
        "skills_extracted": 3,
        "skills_reused": 2,
        "reuse_rate": 0.67,
        "skill_effectiveness": 0.85,
    }


# =============================================================================
# DimensionScore Tests
# =============================================================================


class TestDimensionScore:
    """Test DimensionScore dataclass."""

    def test_weighted_score_computation(self):
        """Weighted score should be score * weight."""
        dim = DimensionScore(name="test", score=0.8, weight=0.2)
        assert dim.weighted_score == pytest.approx(0.16)

    def test_default_values(self):
        """Default values should be zero."""
        dim = DimensionScore(name="test")
        assert dim.score == 0.0
        assert dim.weight == 0.0
        assert dim.weighted_score == 0.0
        assert dim.flags == []


# =============================================================================
# EvaluationReport Tests
# =============================================================================


class TestEvaluationReport:
    """Test EvaluationReport dataclass."""

    def test_to_dict(self):
        """to_dict should produce correctly structured dict."""
        report = EvaluationReport(
            composite_score=0.85,
            grade="A-",
            summary="Test summary",
            recommendations=["Improve X"],
            dimensions={
                "latency": DimensionScore(name="latency", score=0.9, weight=0.15),
            },
        )
        d = report.to_dict()
        assert d["composite_score"] == 0.85
        assert d["grade"] == "A-"
        assert d["summary"] == "Test summary"
        assert "latency" in d["dimensions"]
        assert d["dimensions"]["latency"]["score"] == 0.9


# =============================================================================
# MultiDimensionEvaluator Tests
# =============================================================================


class TestEvaluatorInitialization:
    """Test evaluator initialization and weight validation."""

    def test_default_weights(self):
        """Default weights should be set correctly."""
        evaluator = MultiDimensionEvaluator()
        assert abs(sum(evaluator.weights.values()) - 1.0) < 0.01
        assert "latency" in evaluator.weights

    def test_custom_weights(self):
        """Custom weights should be accepted."""
        custom = {"latency": 0.5, "reliability": 0.5}
        evaluator = MultiDimensionEvaluator(weights=custom)
        assert abs(sum(evaluator.weights.values()) - 1.0) < 0.01

    def test_weight_normalization(self):
        """Weights that don't sum to 1.0 should be normalized."""
        custom = {"latency": 2.0, "reliability": 2.0}
        evaluator = MultiDimensionEvaluator(weights=custom)
        assert abs(evaluator.weights["latency"] - 0.5) < 0.01
        assert abs(evaluator.weights["reliability"] - 0.5) < 0.01


class TestLatencyScoring:
    """Test latency dimension scoring."""

    def test_latency_with_good_metrics(self, sample_profiler_data):
        """Good latency metrics should score high."""
        evaluator = MultiDimensionEvaluator()
        evaluator.set_profiler_data(sample_profiler_data)
        dim = evaluator._score_latency()
        assert dim.score > 0.6
        assert "p50_ms" in dim.details
        assert "p95_ms" in dim.details

    def test_latency_with_poor_metrics(self):
        """Poor latency metrics should score low."""
        evaluator = MultiDimensionEvaluator()
        evaluator.set_profiler_data({
            "p50_ms": 200.0,
            "p95_ms": 500.0,
            "p99_ms": 1200.0,
        })
        dim = evaluator._score_latency()
        assert dim.score < 0.5

    def test_latency_with_no_data(self):
        """No data should return zero score with warning."""
        evaluator = MultiDimensionEvaluator()
        dim = evaluator._score_latency()
        assert dim.score == 0.0
        assert len(dim.flags) > 0


class TestReliabilityScoring:
    """Test reliability dimension scoring."""

    def test_reliability_with_good_tasks(self, sample_task_results):
        """Good task results should score high."""
        evaluator = MultiDimensionEvaluator()
        evaluator.set_task_results(sample_task_results)
        dim = evaluator._score_reliability()
        # 8/10 successes, 1/2 recovered, 1/10 aborted
        assert dim.score > 0.5
        assert dim.details["total_tasks"] == 10

    def test_reliability_all_success(self):
        """All successes should score high."""
        evaluator = MultiDimensionEvaluator()
        results = [{"success": True} for _ in range(10)]
        evaluator.set_task_results(results)
        dim = evaluator._score_reliability()
        # 0.6*1.0 + 0.25*1.0 - 0.15*0 = 0.85
        assert dim.score == pytest.approx(0.85)

    def test_reliability_all_failures(self):
        """All failures should score low."""
        evaluator = MultiDimensionEvaluator()
        results = [{"success": False, "error": "Error"} for _ in range(10)]
        evaluator.set_task_results(results)
        dim = evaluator._score_reliability()
        assert dim.score < 0.3

    def test_reliability_no_data(self):
        """No data should return zero with warning."""
        evaluator = MultiDimensionEvaluator()
        dim = evaluator._score_reliability()
        assert dim.score == 0.0


class TestQualityScoring:
    """Test quality dimension scoring."""

    def test_quality_with_good_results(self, sample_task_results):
        """Good quality results should score high."""
        evaluator = MultiDimensionEvaluator()
        evaluator.set_task_results(sample_task_results)
        dim = evaluator._score_quality()
        assert dim.score > 0.5
        assert "avg_quality_score" in dim.details

    def test_quality_with_defects(self):
        """Many defects should lower the score."""
        evaluator = MultiDimensionEvaluator()
        results = [
            {"quality_score": 50.0, "defects": ["defect1", "defect2", "defect3"], "quality_passed": False},
            {"quality_score": 40.0, "defects": ["defect1", "defect2"], "quality_passed": False},
        ]
        evaluator.set_task_results(results)
        dim = evaluator._score_quality()
        assert dim.score < 0.5

    def test_quality_no_data(self):
        """No data should return zero with warning."""
        evaluator = MultiDimensionEvaluator()
        dim = evaluator._score_quality()
        assert dim.score == 0.0


class TestEfficiencyScoring:
    """Test efficiency dimension scoring."""

    def test_efficiency_with_good_metrics(self, sample_interaction_data):
        """Good efficiency metrics should score high."""
        evaluator = MultiDimensionEvaluator()
        evaluator.set_interaction_data(sample_interaction_data)
        dim = evaluator._score_efficiency()
        assert dim.score > 0.5
        assert "rounds_per_task" in dim.details

    def test_efficiency_with_high_redundancy(self):
        """High redundancy should lower the score."""
        evaluator = MultiDimensionEvaluator()
        evaluator.set_interaction_data({
            "total_interactions": 100,
            "rounds_per_task": 25.0,
            "redundant_calls": 15,
            "context_size_stats": {"avg": 40.0},
        })
        dim = evaluator._score_efficiency()
        assert dim.score < 0.4

    def test_efficiency_no_data(self):
        """No data should return zero with warning."""
        evaluator = MultiDimensionEvaluator()
        dim = evaluator._score_efficiency()
        assert dim.score == 0.0


class TestRobustnessScoring:
    """Test robustness dimension scoring."""

    def test_robustness_with_mixed_results(self, sample_task_results, sample_profiler_data):
        """Mixed results should produce a moderate score."""
        evaluator = MultiDimensionEvaluator()
        evaluator.set_task_results(sample_task_results)
        evaluator.set_profiler_data(sample_profiler_data)
        dim = evaluator._score_robustness()
        assert 0.0 <= dim.score <= 1.0
        assert "graceful_recoveries" in dim.details

    def test_robustness_all_graceful(self):
        """All errors recovered gracefully should score high."""
        evaluator = MultiDimensionEvaluator()
        results = [
            {"success": True},
            {"success": False, "error": "Error", "recovered": True},
            {"success": True},
        ]
        evaluator.set_task_results(results)
        dim = evaluator._score_robustness()
        assert dim.score > 0.5

    def test_robustness_no_data(self):
        """No data should return zero with warning."""
        evaluator = MultiDimensionEvaluator()
        dim = evaluator._score_robustness()
        assert dim.score == 0.0


class TestContextHealthScoring:
    """Test context health dimension scoring."""

    def test_context_health_with_good_data(self, sample_context_data):
        """Good context data should score high."""
        evaluator = MultiDimensionEvaluator()
        evaluator.set_context_data(sample_context_data)
        dim = evaluator._score_context_health()
        assert dim.score > 0.5
        assert "decay_events" in dim.details

    def test_context_health_with_decay(self):
        """Many decay events should lower the score."""
        evaluator = MultiDimensionEvaluator()
        evaluator.set_context_data({
            "state_snapshots": 1,
            "compression_count": 0,
            "decay_events": 5,
            "persistence_success_rate": 0.5,
        })
        dim = evaluator._score_context_health()
        assert dim.score < 0.5

    def test_context_health_no_data(self):
        """No data should return zero with warning."""
        evaluator = MultiDimensionEvaluator()
        dim = evaluator._score_context_health()
        assert dim.score == 0.0


class TestReusabilityScoring:
    """Test reusability dimension scoring."""

    def test_reusability_with_good_data(self, sample_skill_data):
        """Good skill data should score high."""
        evaluator = MultiDimensionEvaluator()
        evaluator.set_skill_data(sample_skill_data)
        dim = evaluator._score_reusability()
        assert dim.score > 0.5
        assert "reuse_rate" in dim.details

    def test_reusability_no_skills(self):
        """No skills extracted should score low."""
        evaluator = MultiDimensionEvaluator()
        evaluator.set_skill_data({
            "skills_extracted": 0,
            "skills_reused": 0,
            "reuse_rate": 0.0,
            "skill_effectiveness": 0.0,
        })
        dim = evaluator._score_reusability()
        assert dim.score < 0.3

    def test_reusability_no_data(self):
        """No data should return zero with warning."""
        evaluator = MultiDimensionEvaluator()
        dim = evaluator._score_reusability()
        assert dim.score == 0.0


class TestFullEvaluation:
    """Test full evaluation pipeline."""

    def test_full_evaluation(
        self, sample_profiler_data, sample_interaction_data,
        sample_task_results, sample_context_data, sample_skill_data,
    ):
        """Full evaluation should produce a complete report."""
        evaluator = MultiDimensionEvaluator()
        evaluator.set_profiler_data(sample_profiler_data)
        evaluator.set_interaction_data(sample_interaction_data)
        evaluator.set_task_results(sample_task_results)
        evaluator.set_context_data(sample_context_data)
        evaluator.set_skill_data(sample_skill_data)

        report = evaluator.evaluate()
        assert isinstance(report, EvaluationReport)
        assert len(report.dimensions) == 7
        assert 0.0 <= report.composite_score <= 1.0
        assert report.grade != "N/A"
        assert len(report.summary) > 0
        assert len(report.recommendations) > 0

    def test_evaluation_consistency(self):
        """Same data should produce same score."""
        evaluator1 = MultiDimensionEvaluator()
        evaluator1.set_task_results([{"success": True} for _ in range(5)])
        report1 = evaluator1.evaluate()

        evaluator2 = MultiDimensionEvaluator()
        evaluator2.set_task_results([{"success": True} for _ in range(5)])
        report2 = evaluator2.evaluate()

        assert report1.composite_score == report2.composite_score


class TestGradeAssignment:
    """Test grade computation."""

    def test_a_plus_grade(self):
        """Score >= 0.95 should get A+."""
        evaluator = MultiDimensionEvaluator()
        assert evaluator._compute_grade(0.96) == "A+"
        assert evaluator._compute_grade(0.95) == "A+"

    def test_a_grade(self):
        """Score >= 0.90 should get A."""
        evaluator = MultiDimensionEvaluator()
        assert evaluator._compute_grade(0.92) == "A"

    def test_b_grade(self):
        """Score >= 0.75 should get B."""
        evaluator = MultiDimensionEvaluator()
        assert evaluator._compute_grade(0.78) == "B"

    def test_f_grade(self):
        """Score < 0.0 should get F."""
        evaluator = MultiDimensionEvaluator()
        assert evaluator._compute_grade(-0.1) == "F"


class TestTrendTracking:
    """Test evaluation trend tracking."""

    def test_trend_empty(self):
        """Empty history should return empty trend."""
        evaluator = MultiDimensionEvaluator()
        assert evaluator.get_trend() == []

    def test_trend_after_evaluations(self, sample_task_results):
        """Trend should accumulate after evaluations."""
        evaluator = MultiDimensionEvaluator()
        evaluator.set_task_results(sample_task_results)
        evaluator.evaluate()
        evaluator.evaluate()

        trend = evaluator.get_trend()
        assert len(trend) == 2

    def test_trend_by_dimension(self, sample_task_results):
        """Trend should support per-dimension queries."""
        evaluator = MultiDimensionEvaluator()
        evaluator.set_task_results(sample_task_results)
        evaluator.evaluate()

        trend = evaluator.get_trend("reliability")
        assert len(trend) == 1

    def test_improvement_delta(self, sample_task_results):
        """Improvement delta should show difference between last two."""
        evaluator = MultiDimensionEvaluator()
        evaluator.set_task_results(sample_task_results)
        evaluator.evaluate()
        # Same data = same score = delta 0
        evaluator.evaluate()
        assert evaluator.get_improvement_delta() == 0.0

    def test_improvement_delta_single(self):
        """Single evaluation should return delta 0."""
        evaluator = MultiDimensionEvaluator()
        evaluator.set_task_results([{"success": True}])
        evaluator.evaluate()
        assert evaluator.get_improvement_delta() == 0.0


class TestReportPersistence:
    """Test report saving to disk."""

    def test_save_report(self, sample_task_results):
        """Report should be saved when report_dir is set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            evaluator = MultiDimensionEvaluator(report_dir=tmpdir)
            evaluator.set_task_results(sample_task_results)
            evaluator.evaluate()

            # Check that a file was created
            files = os.listdir(tmpdir)
            assert len(files) == 1
            assert files[0].endswith(".json")

    def test_no_save_without_dir(self, sample_task_results):
        """No save should occur without report_dir."""
        evaluator = MultiDimensionEvaluator()
        evaluator.set_task_results(sample_task_results)
        evaluator.evaluate()
        # Should not raise any error


class TestEvaluatorReset:
    """Test reset functionality."""

    def test_reset_clears_data(self, sample_task_results):
        """Reset should clear input data but not history."""
        evaluator = MultiDimensionEvaluator()
        evaluator.set_task_results(sample_task_results)
        evaluator.evaluate()
        evaluator.reset()

        # Data should be cleared
        assert evaluator._task_results == []
        assert evaluator._profiler_data == {}
        # History should be preserved
        assert len(evaluator._reports) == 1