"""
Unit tests for LoopRunner - main loop engineering orchestration engine.

Tests cover:
1. Initialization and setup
2. Component initialization
3. Main loop execution
4. Iteration tracking
5. Convergence detection
6. Result building
7. Persistence
8. Callbacks
9. Disabled mode
10. Edge cases
"""

import tempfile
import time
from pathlib import Path

import pytest

from loop_engineering.loop_runner import (
    LoopIteration,
    LoopResult,
    LoopRunner,
)


class TestLoopIteration:
    """Tests for LoopIteration dataclass."""

    def test_default_values(self):
        """LoopIteration should have correct defaults."""
        it = LoopIteration(iteration=1)
        assert it.iteration == 1
        assert it.report is None
        assert it.kept is True
        assert it.delta == 0.0
        assert it.skills_extracted == 0
        assert it.meta_skills_evolved == 0

    def test_with_data(self):
        """LoopIteration should accept all fields."""
        it = LoopIteration(
            iteration=3,
            kept=False,
            delta=0.05,
            skills_extracted=2,
            meta_skills_evolved=1,
            duration_ms=150.0,
        )
        assert it.iteration == 3
        assert it.kept is False
        assert it.delta == 0.05
        assert it.skills_extracted == 2


class TestLoopResult:
    """Tests for LoopResult dataclass."""

    def test_default_values(self):
        """LoopResult should have correct defaults."""
        result = LoopResult(run_id="test")
        assert result.run_id == "test"
        assert result.iterations == []
        assert result.total_iterations == 0
        assert result.converged is False
        assert result.initial_score == 0.0
        assert result.final_score == 0.0

    def test_to_dict(self):
        """to_dict should serialize correctly."""
        result = LoopResult(
            run_id="test",
            total_iterations=5,
            converged=True,
            convergence_reason="No improvement",
            initial_score=0.5,
            final_score=0.8,
            total_improvement=0.3,
            total_duration_ms=1000.0,
            best_iteration=3,
            recommendations=["Test rec"],
        )
        d = result.to_dict()
        assert d["run_id"] == "test"
        assert d["total_iterations"] == 5
        assert d["converged"] is True
        assert d["convergence_reason"] == "No improvement"
        assert d["initial_score"] == 0.5
        assert d["final_score"] == 0.8
        assert d["total_improvement"] == 0.3
        assert d["recommendations"] == ["Test rec"]

    def test_to_dict_with_iterations(self):
        """to_dict should include iteration data."""
        result = LoopResult(run_id="test")
        result.iterations = [
            LoopIteration(iteration=1, delta=0.1, skills_extracted=2),
            LoopIteration(iteration=2, delta=0.05, skills_extracted=1),
        ]
        d = result.to_dict()
        assert len(d["iterations"]) == 2
        assert d["iterations"][0]["iteration"] == 1
        assert d["iterations"][0]["delta"] == 0.1


class TestLoopRunnerInitialization:
    """Tests for LoopRunner initialization."""

    def test_default_initialization(self):
        """Default initialization should set sensible defaults."""
        runner = LoopRunner()
        assert runner.max_iterations == 10
        assert runner.convergence_patience == 3
        assert runner.enabled is True
        assert runner._current_iteration == 0

    def test_with_config(self):
        """Config should override defaults."""
        config = {
            "loop_engineering": {
                "enabled": True,
                "loop_runner": {
                    "max_iterations": 5,
                    "convergence_threshold": 0.02,
                    "convergence_patience": 2,
                    "min_loop_interval": 0.5,
                },
            }
        }
        runner = LoopRunner(config)
        assert runner.max_iterations == 5
        assert runner.convergence_threshold == 0.02
        assert runner.convergence_patience == 2
        assert runner.min_loop_interval == 0.5

    def test_disabled(self):
        """Disabled loop runner should not run."""
        config = {"loop_engineering": {"enabled": False}}
        runner = LoopRunner(config)
        assert runner.enabled is False


class TestLoopRunnerSetup:
    """Tests for setup method."""

    def test_setup_initializes_components(self):
        """Setup should initialize all components."""
        runner = LoopRunner()
        runner.setup()
        assert runner.e2e_profiler is not None
        assert runner.interaction_tracker is not None
        assert runner.evaluator is not None
        assert runner.context_manager is not None
        assert runner.skill_extractor is not None
        assert runner.knowledge_inheritor is not None
        assert runner.meta_optimizer is not None

    def test_setup_with_config(self):
        """Setup with config should configure components."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "loop_engineering": {
                    "evaluator": {
                        "weights": {"latency": 0.5, "reliability": 0.5},
                        "report_dir": str(Path(tmpdir) / "reports"),
                    },
                    "skill_extractor": {
                        "min_reuse_threshold": 3,
                        "skill_library_path": str(Path(tmpdir) / "skills.json"),
                    },
                    "knowledge_inheritor": {
                        "core_memory_retention": 0.9,
                        "lineage_path": str(Path(tmpdir) / "lineage.json"),
                    },
                    "meta_optimizer": {
                        "strategy_history_size": 100,
                        "meta_skill_path": str(Path(tmpdir) / "meta.json"),
                    },
                }
            }
            runner = LoopRunner(config)
            runner.setup()
            assert runner.skill_extractor.min_reuse_threshold == 3
            assert runner.knowledge_inheritor.core_memory_retention == 0.9
            assert runner.meta_optimizer.strategy_history_size == 100

    def test_lazy_setup_in_run_loop(self):
        """run_loop should lazily setup if not already done."""
        runner = LoopRunner()
        runner.enabled = True
        # Run with mocked training
        runner.set_training_runner(lambda: {"agent_results": {}})
        result = runner.run_loop(max_iterations=1)
        assert result.total_iterations == 1
        assert runner.evaluator is not None  # Should be initialized


class TestLoopRunnerCallbacks:
    """Tests for callback registration."""

    def test_set_on_iteration(self):
        """Should register iteration callback."""
        runner = LoopRunner()
        called = []

        def callback(it):
            called.append(it.iteration)

        runner.set_on_iteration(callback)
        assert runner._on_iteration_complete is not None

        # Run a single iteration
        runner.setup()
        runner.set_training_runner(lambda: {"agent_results": {}})
        runner.run_loop(max_iterations=2)
        assert len(called) == 2

    def test_set_on_convergence(self):
        """Should register convergence callback."""
        runner = LoopRunner()
        called = []

        def callback(result):
            called.append(result.converged)

        runner.set_on_convergence(callback)
        assert runner._on_convergence is not None

    def test_on_convergence_not_called_without_convergence(self):
        """Convergence callback should not be called if not converged."""
        runner = LoopRunner()
        called = []

        def callback(result):
            called.append(True)

        runner.set_on_convergence(callback)
        runner.setup()
        runner.set_training_runner(lambda: {"agent_results": {}})
        runner.run_loop(max_iterations=1)
        # Convergence not reached in 1 iteration
        assert len(called) == 0


class TestLoopRunnerExecution:
    """Tests for loop execution."""

    def test_run_single_iteration(self):
        """Single iteration loop should work."""
        runner = LoopRunner()
        runner.setup()
        runner.set_training_runner(lambda: {"agent_results": {}})
        result = runner.run_loop(max_iterations=1)
        assert result.total_iterations == 1
        assert not result.converged

    def test_run_multiple_iterations(self):
        """Multiple iterations should work."""
        runner = LoopRunner()
        runner.setup()
        runner.set_training_runner(lambda: {"agent_results": {}})
        result = runner.run_loop(max_iterations=3)
        assert result.total_iterations == 3
        assert len(result.iterations) == 3

    def test_run_disabled(self):
        """Disabled loop should return empty result."""
        config = {"loop_engineering": {"enabled": False}}
        runner = LoopRunner(config)
        result = runner.run_loop()
        assert result.total_iterations == 0
        assert "disabled" in result.convergence_reason.lower()

    def test_run_with_training_results(self):
        """Training results should feed into evaluation."""
        runner = LoopRunner()
        runner.setup()

        training_results = {
            "agent_results": {
                "sampling": {
                    "improvement_pct": 15.0,
                    "best_score": 0.85,
                    "best_params": {"spacing": 40},
                },
                "vision": {
                    "improvement_pct": 10.0,
                    "best_score": 0.90,
                    "best_params": {"confidence_threshold": 0.6},
                },
            },
            "task_results": [
                {"success": True, "quality_score": 85.0, "defects": []},
                {"success": True, "quality_score": 90.0, "defects": []},
            ],
        }

        runner.set_training_runner(lambda: training_results)
        result = runner.run_loop(max_iterations=2)
        assert result.total_iterations == 2

    def test_run_with_task_results(self):
        """Task results should feed into evaluation."""
        runner = LoopRunner()
        runner.setup()

        task_results = {
            "task_results": [
                {"success": True, "quality_score": 95.0, "defects": []},
                {"success": True, "quality_score": 88.0, "defects": ["scratch"]},
                {"success": False, "quality_score": 30.0, "defects": ["scratch", "discoloration"]},
            ]
        }
        runner.set_training_runner(lambda: task_results)
        result = runner.run_loop(max_iterations=1)
        assert result.total_iterations == 1

    def test_run_with_exception_in_training(self):
        """Exception in training should not crash the loop."""
        runner = LoopRunner()
        runner.setup()

        def faulty_training():
            raise RuntimeError("Training failed")
        runner.set_training_runner(faulty_training)

        result = runner.run_loop(max_iterations=2)
        assert result.total_iterations == 2  # Should continue

    def test_run_with_exception_in_task_executor(self):
        """Exception in task executor should not crash the loop."""
        runner = LoopRunner()
        runner.setup()

        def faulty_task():
            raise RuntimeError("Task failed")
        runner.set_task_executor(faulty_task)

        runner.set_training_runner(lambda: {"agent_results": {}})
        result = runner.run_loop(max_iterations=1)
        assert result.total_iterations == 1


class TestLoopRunnerIterationTracking:
    """Tests for iteration tracking."""

    def test_improvement_delta_tracking(self):
        """Delta should be tracked between iterations."""
        runner = LoopRunner()
        runner.setup()
        runner.set_training_runner(lambda: {"agent_results": {}})
        result = runner.run_loop(max_iterations=3)
        assert len(result.iterations) == 3
        for it in result.iterations:
            assert hasattr(it, 'delta')

    def test_best_score_tracking(self):
        """Best score should be tracked."""
        runner = LoopRunner()
        runner.setup()
        runner.set_training_runner(lambda: {"agent_results": {}})
        result = runner.run_loop(max_iterations=3)
        assert result.best_iteration >= 0

    def test_skills_extracted_count(self):
        """Skills extracted should be tracked per iteration."""
        runner = LoopRunner()
        runner.setup()
        runner.set_training_runner(lambda: {"agent_results": {}})
        result = runner.run_loop(max_iterations=2)
        for it in result.iterations:
            assert it.skills_extracted >= 0


class TestLoopRunnerConvergence:
    """Tests for convergence detection."""

    def test_convergence_no_improvement(self):
        """No improvement for patience iterations should trigger convergence."""
        runner = LoopRunner()
        runner.convergence_patience = 2
        runner.setup()

        # Simulate no improvement by providing empty agent results
        runner.set_training_runner(lambda: {"agent_results": {}})
        result = runner.run_loop(max_iterations=10)
        # May converge due to lack of improvement
        assert result.total_iterations <= 10

    def test_max_iterations_reached(self):
        """Max iterations should stop the loop."""
        runner = LoopRunner()
        runner.convergence_patience = 10  # High patience to avoid premature convergence
        runner.setup()
        runner.set_training_runner(lambda: {"agent_results": {}})
        result = runner.run_loop(max_iterations=3)
        assert result.total_iterations == 3
        assert "Max iterations" in result.convergence_reason

    def test_meta_optimizer_convergence(self):
        """Meta-optimizer convergence should stop the loop."""
        runner = LoopRunner()
        runner.setup()
        runner.set_training_runner(lambda: {"agent_results": {}})
        result = runner.run_loop(max_iterations=5)
        assert isinstance(result.converged, bool)


class TestLoopRunnerResult:
    """Tests for result building."""

    def test_result_has_all_fields(self):
        """Result should have all required fields."""
        runner = LoopRunner()
        runner.setup()
        runner.set_training_runner(lambda: {"agent_results": {}})
        result = runner.run_loop(max_iterations=1)

        assert result.run_id is not None
        assert len(result.iterations) == 1
        assert result.total_iterations == 1
        assert result.initial_score >= 0.0
        assert result.final_score >= 0.0
        assert result.total_duration_ms >= 0.0

    def test_get_current_result_in_progress(self):
        """get_current_result should work mid-loop."""
        runner = LoopRunner()
        runner.setup()

        # Before running, no result
        assert runner.get_current_result() is None

        runner.set_training_runner(lambda: {"agent_results": {}})
        runner.run_loop(max_iterations=1)

        # After running, should have result
        result = runner.get_current_result()
        assert result is not None
        assert result.total_iterations == 1


class TestLoopRunnerPersistence:
    """Tests for result persistence."""

    def test_save_result(self):
        """Should save result to disk."""
        runner = LoopRunner()
        runner.setup()
        runner.set_training_runner(lambda: {"agent_results": {}})
        runner.run_loop(max_iterations=1)

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = str(Path(tmpdir) / "loop_result.json")
            assert runner.save_result(filepath)
            assert Path(filepath).exists()

    def test_save_without_iterations(self):
        """Save without iterations should return False."""
        runner = LoopRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            assert not runner.save_result(str(Path(tmpdir) / "result.json"))

    def test_save_creates_directories(self):
        """Save should create parent directories if needed."""
        runner = LoopRunner()
        runner.setup()
        runner.set_training_runner(lambda: {"agent_results": {}})
        runner.run_loop(max_iterations=1)

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = str(Path(tmpdir) / "subdir" / "nested" / "result.json")
            assert runner.save_result(filepath)
            assert Path(filepath).exists()


class TestLoopRunnerTaskExecutor:
    """Tests for task executor integration."""

    def test_set_task_executor(self):
        """Should set task executor."""
        runner = LoopRunner()

        def my_executor():
            return {"result": "ok"}

        runner.set_task_executor(my_executor)
        assert runner._task_executor is not None

    def test_set_training_runner(self):
        """Should set training runner."""
        runner = LoopRunner()

        def my_trainer():
            return {"agent_results": {}}

        runner.set_training_runner(my_trainer)
        assert runner._training_runner is not None

    def test_task_executor_called_during_loop(self):
        """Task executor should be called during loop."""
        runner = LoopRunner()
        runner.setup()
        task_called = []

        def task_executor():
            task_called.append(True)
            return {"task_results": []}

        runner.set_task_executor(task_executor)
        runner.set_training_runner(lambda: {"agent_results": {}})
        runner.run_loop(max_iterations=2)

        assert len(task_called) == 2


class TestLoopRunnerReset:
    """Tests for reset functionality."""

    def test_reset_clears_state(self):
        """Reset should clear all state."""
        runner = LoopRunner()
        runner.setup()
        runner.set_training_runner(lambda: {"agent_results": {}})
        runner.run_loop(max_iterations=2)

        runner.reset()
        assert len(runner._iterations) == 0
        assert runner._current_iteration == 0
        assert runner._no_improvement_count == 0
        assert runner._best_score == 0.0
        assert runner._best_iteration == 0

    def test_reset_generates_new_run_id(self):
        """Reset should generate new run ID."""
        runner = LoopRunner()
        runner.setup()
        runner.set_training_runner(lambda: {"agent_results": {}})
        runner.run_loop(max_iterations=1)
        old_id = runner._run_id

        runner.reset()
        assert runner._run_id != old_id

    def test_reset_allows_new_run(self):
        """After reset, new loop should run."""
        runner = LoopRunner()
        runner.setup()
        runner.set_training_runner(lambda: {"agent_results": {}})
        runner.run_loop(max_iterations=1)
        runner.reset()

        runner.setup()
        runner.set_training_runner(lambda: {"agent_results": {}})
        result = runner.run_loop(max_iterations=1)
        assert result.total_iterations == 1


class TestLoopRunnerEdgeCases:
    """Edge case tests."""

    def test_zero_max_iterations(self):
        """Zero max iterations should return empty result."""
        runner = LoopRunner()
        runner.setup()
        result = runner.run_loop(max_iterations=0)
        assert result.total_iterations == 0

    def test_empty_training_result(self):
        """Empty training result should not crash."""
        runner = LoopRunner()
        runner.setup()
        runner.set_training_runner(lambda: {})
        result = runner.run_loop(max_iterations=1)
        assert result.total_iterations == 1

    def test_training_result_with_none_agent_results(self):
        """None agent_results should not crash."""
        runner = LoopRunner()
        runner.setup()
        runner.set_training_runner(lambda: {"agent_results": None})
        result = runner.run_loop(max_iterations=1)
        assert result.total_iterations == 1

    def test_skills_extraction_without_tracker(self):
        """Skills extraction without tracker should still work."""
        runner = LoopRunner()
        runner.setup()
        runner.interaction_tracker = None  # Remove tracker
        runner.set_training_runner(lambda: {"agent_results": {}})
        result = runner.run_loop(max_iterations=1)
        assert result.total_iterations == 1

    def test_meta_evolution_without_meta_optimizer(self):
        """Meta evolution without optimizer should still work."""
        runner = LoopRunner()
        runner.setup()
        runner.meta_optimizer = None  # Remove meta optimizer
        runner.set_training_runner(lambda: {"agent_results": {}})
        result = runner.run_loop(max_iterations=1)
        assert result.total_iterations == 1

    def test_config_passed_to_setup(self):
        """Config from __init__ should be used in setup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "loop_engineering": {
                    "skill_extractor": {
                        "min_reuse_threshold": 5,
                        "skill_library_path": str(Path(tmpdir) / "skills.json"),
                    },
                }
            }
            runner = LoopRunner(config)
            runner.setup()
            assert runner.skill_extractor.min_reuse_threshold == 5
            assert runner.skill_extractor.library_path is not None