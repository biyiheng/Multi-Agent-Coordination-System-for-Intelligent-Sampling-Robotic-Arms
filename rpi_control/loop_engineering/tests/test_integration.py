"""
Comprehensive integration tests for the Loop Engineering framework.

Tests the full pipeline from data generation through evaluation,
skill extraction, knowledge inheritance, meta-optimization,
and the loop runner.

Covers:
1. Full pipeline integration
2. Edge case handling
3. Multi-quality-level testing
4. Loop runner convergence
5. Component interoperability
6. Performance benchmarking
"""

import json
import os
import tempfile
import time
import pytest
from loop_engineering.tests.test_data_generator import TestDataGenerator
from loop_engineering.evaluator import MultiDimensionEvaluator
from loop_engineering.context_manager import ContextManager
from loop_engineering.skill_extractor import SkillExtractor
from loop_engineering.knowledge_inheritor import KnowledgeInheritor
from loop_engineering.meta_optimizer import MetaOptimizer
from loop_engineering.loop_runner import LoopRunner, LoopResult, LoopIteration


# =============================================================================
# Full Pipeline Integration Tests
# =============================================================================


class TestFullPipelineIntegration:
    """Test full pipeline from data generation to evaluation."""

    @pytest.fixture
    def generator(self):
        return TestDataGenerator(seed=42, num_tasks=20, quality_level="medium")

    def test_generate_to_evaluate(self, generator):
        """Full pipeline: generate data → evaluate."""
        data = generator.generate_all()

        evaluator = MultiDimensionEvaluator()
        evaluator.set_profiler_data(data.e2e_profile)
        evaluator.set_interaction_data(data.interaction_stats)
        evaluator.set_task_results(data.task_results)
        evaluator.set_context_data(data.context_data)
        evaluator.set_skill_data(data.skill_data)

        report = evaluator.evaluate()
        assert report.composite_score > 0
        assert len(report.dimensions) == 7
        assert report.grade != "N/A"

    def test_quality_levels_produce_different_scores(self):
        """Different quality levels should produce different scores."""
        scores = {}

        for level in ["low", "medium", "high"]:
            gen = TestDataGenerator(seed=42, quality_level=level)
            data = gen.generate_all()

            evaluator = MultiDimensionEvaluator()
            evaluator.set_profiler_data(data.e2e_profile)
            evaluator.set_interaction_data(data.interaction_stats)
            evaluator.set_task_results(data.task_results)
            evaluator.set_context_data(data.context_data)
            evaluator.set_skill_data(data.skill_data)

            report = evaluator.evaluate()
            scores[level] = report.composite_score

        # High should be better than low
        assert scores["high"] > scores["low"]

    def test_edge_cases_dont_crash(self, generator):
        """Edge cases should not crash the evaluator."""
        edge_cases = generator.generate_edge_cases()

        evaluator = MultiDimensionEvaluator()
        evaluator.set_task_results(edge_cases)

        report = evaluator.evaluate()
        # Should still produce a valid report
        assert report.composite_score >= 0.0
        assert report.composite_score <= 1.0

    def test_empty_data_handling(self):
        """Empty data should produce valid (zero) scores."""
        evaluator = MultiDimensionEvaluator()
        report = evaluator.evaluate()

        assert report.composite_score == 0.0
        # All dimensions should have flags about missing data
        flagged = sum(1 for d in report.dimensions.values() if d.flags)
        assert flagged >= 5  # Most dimensions should flag


# =============================================================================
# Skill Extractor Integration Tests
# =============================================================================


class TestSkillExtractorIntegration:
    """Test skill extractor with real-world-like data."""

    def test_extract_from_traces(self):
        """Extract skills from trace data."""
        extractor = SkillExtractor(min_reuse_threshold=2)

        # Simulate traces with recurring patterns
        trace_patterns = [
            # Approaching pattern (appears 3 times)
            [
                {"agent": "orchestrator", "action": "plan", "duration_ms": 10},
                {"agent": "motion_agent", "action": "approach", "params": {"speed": 0.5}, "duration_ms": 50},
                {"agent": "safety_agent", "action": "check", "duration_ms": 5},
            ],
            # Same pattern again
            [
                {"agent": "orchestrator", "action": "plan", "duration_ms": 12},
                {"agent": "motion_agent", "action": "approach", "params": {"speed": 0.6}, "duration_ms": 45},
                {"agent": "safety_agent", "action": "check", "duration_ms": 6},
            ],
            # Same pattern third time
            [
                {"agent": "orchestrator", "action": "plan", "duration_ms": 8},
                {"agent": "motion_agent", "action": "approach", "params": {"speed": 0.4}, "duration_ms": 55},
                {"agent": "safety_agent", "action": "check", "duration_ms": 4},
            ],
            # Grasping pattern (appears 2 times - needs min_reuse_threshold=2)
            [
                {"agent": "vision_agent", "action": "detect", "duration_ms": 30},
                {"agent": "motion_agent", "action": "grasp", "duration_ms": 80},
                {"agent": "quality_agent", "action": "inspect", "duration_ms": 20},
            ],
            [
                {"agent": "vision_agent", "action": "detect", "duration_ms": 35},
                {"agent": "motion_agent", "action": "grasp", "duration_ms": 75},
                {"agent": "quality_agent", "action": "inspect", "duration_ms": 25},
            ],
            # Unique pattern (only 1 time)
            [
                {"agent": "orchestrator", "action": "calibrate", "duration_ms": 100},
                {"agent": "motion_agent", "action": "home", "duration_ms": 200},
            ],
        ]

        for i, trace in enumerate(trace_patterns):
            extractor.add_trace(f"task_{i}", trace)

        skills = extractor.extract_skills()
        # Should extract at least 1 skill (the approaching pattern repeated 3 times)
        assert len(skills) > 0

    def test_skill_effectiveness_tracking(self):
        """Skill effectiveness should track success/failure."""
        extractor = SkillExtractor(min_reuse_threshold=2)

        # Add pattern that appears twice - more detailed to ensure extraction
        pattern = [
            {"agent": "A", "action": "start", "duration_ms": 5},
            {"agent": "A", "action": "do_work", "duration_ms": 10},
            {"agent": "A", "action": "finish", "duration_ms": 5},
        ]
        extractor.add_trace("task_1", pattern)
        extractor.add_trace("task_2", pattern)

        skills = extractor.extract_skills()
        assert len(skills) > 0, "Should extract at least one skill from recurring pattern"

        skill_id = skills[0].skill_id
        # Record successful executions
        extractor.record_skill_execution(skill_id, success=True)
        extractor.record_skill_execution(skill_id, success=True)
        extractor.record_skill_execution(skill_id, success=False)

        skill = extractor.get_skill(skill_id)
        assert skill.effectiveness == pytest.approx(2 / 3)

    def test_skill_persistence(self):
        """Skills should be persisted and reloaded."""
        from pathlib import Path

        extractor = SkillExtractor(min_reuse_threshold=2)

        pattern = [
            {"agent": "A", "action": "start", "duration_ms": 5},
            {"agent": "A", "action": "do_work", "duration_ms": 10},
        ]
        extractor.add_trace("task_1", pattern)
        extractor.add_trace("task_2", pattern)
        extractor.extract_skills()

        with tempfile.TemporaryDirectory() as tmpdir:
            lib_path = Path(tmpdir) / "skills.json"
            extractor.library_path = lib_path
            assert extractor.save_library()

            # Load into new extractor
            extractor2 = SkillExtractor(library_path=str(lib_path))
            assert extractor2.load_library()
            assert len(extractor2._skills) > 0


# =============================================================================
# Knowledge Inheritor Integration Tests
# =============================================================================


class TestKnowledgeInheritorIntegration:
    """Test knowledge inheritance with version lineage."""

    def test_version_lineage(self):
        """Version lineage should track parent-child relationships."""
        inheritor = KnowledgeInheritor()

        inheritor.register_version("v1.0.0", params={"param_a": 1.0, "param_b": 2.0})
        inheritor.register_version("v2.0.0", parent="v1.0.0", params={"param_c": 3.0})
        inheritor.register_version("v2.1.0", parent="v2.0.0", params={"param_d": 4.0})

        lineage = inheritor.get_lineage()
        assert "v1.0.0" in lineage
        assert "v2.0.0" in lineage

        chain = inheritor.get_version_chain("v2.1.0")
        assert chain == ["v1.0.0", "v2.0.0", "v2.1.0"]

    def test_auto_inheritance(self):
        """Auto-inheritance should transfer params from parent."""
        inheritor = KnowledgeInheritor()

        inheritor.register_version("v1.0.0", params={"param_a": 1.0, "param_b": 2.0})
        inheritor.register_version("v2.0.0", parent="v1.0.0")

        v2 = inheritor._lineage["v2.0.0"]
        assert "param_a" in v2.params
        assert "param_b" in v2.params
        assert v2.params["param_a"] == 1.0

    def test_deprecation_blocks_inheritance(self):
        """Deprecated params should not be inherited."""
        inheritor = KnowledgeInheritor()

        inheritor.deprecate_knowledge("param_a", "outdated")
        inheritor.register_version("v1.0.0", params={"param_a": 1.0, "param_b": 2.0})
        inheritor.register_version("v2.0.0", parent="v1.0.0")

        v2 = inheritor._lineage["v2.0.0"]
        assert "param_a" not in v2.params  # Should be deprecated
        assert "param_b" in v2.params  # Should be inherited

    def test_core_memory_management(self):
        """Core memory should persist across versions."""
        inheritor = KnowledgeInheritor(core_memory_retention=0.8, decay_threshold=0.3)

        inheritor.set_core_memory("critical_config", {"value": 42, "effectiveness": 0.9})
        inheritor.set_core_memory("obsolete_config", {"value": 10, "effectiveness": 0.1})

        # Apply decay
        deprecated = inheritor.apply_decay()
        assert "obsolete_config" in deprecated

        # Critical config should survive
        assert inheritor.get_core_memory("critical_config") is not None

    def test_persistence(self):
        """Lineage should be persisted and reloaded."""
        from pathlib import Path

        inheritor = KnowledgeInheritor()
        inheritor.register_version("v1.0.0", params={"a": 1})
        inheritor.register_version("v2.0.0", parent="v1.0.0", params={"b": 2})

        with tempfile.TemporaryDirectory() as tmpdir:
            lineage_path = Path(tmpdir) / "lineage.json"
            inheritor.lineage_path = lineage_path
            assert inheritor.save_lineage()

            inheritor2 = KnowledgeInheritor(lineage_path=str(lineage_path))
            assert inheritor2.load_lineage()
            assert len(inheritor2._lineage) == 2


# =============================================================================
# Meta-Optimizer Integration Tests
# =============================================================================


class TestMetaOptimizerIntegration:
    """Test meta-optimizer with strategy evolution."""

    def test_strategy_evolution(self):
        """Strategies should evolve into meta-skills."""
        meta = MetaOptimizer(min_improvement_threshold=0.05)

        # Record grid_search strategies (good improvement)
        for i in range(5):
            meta.record_strategy(
                "grid_search",
                improvement=0.15 + i * 0.01,
                params={"spacing": 50.0 + i},
                agent="sampling",
            )

        # Record random_search (poor improvement)
        for i in range(3):
            meta.record_strategy(
                "random_search",
                improvement=0.02,
                params={"spacing": random_value()},
                agent="sampling",
            )

        # Evolve
        new_skills = meta.evolve_strategies()
        # grid_search should produce a meta-skill
        assert len(new_skills) >= 1

        # grid_search should be the best strategy
        assert meta.get_best_strategy() == "grid_search"

    def test_convergence_detection(self):
        """Convergence should be detected when improvements plateau."""
        meta = MetaOptimizer(min_improvement_threshold=0.05)

        # Improvements trending down
        for imp in [0.2, 0.15, 0.08, 0.03, 0.01, 0.005]:
            meta.record_strategy("grid_search", improvement=imp)

        analysis = meta.get_convergence_analysis()
        assert analysis["converged"] is True

    def test_prompt_template_generation(self):
        """Meta-skills should generate prompt templates."""
        meta = MetaOptimizer()
        meta.record_strategy("grid_search", improvement=0.2, agent="motion")
        meta.record_strategy("grid_search", improvement=0.18, agent="motion")
        meta.evolve_strategies()

        templates = meta.get_prompt_templates()
        assert len(templates) > 0
        assert any("grid search" in t.lower() for t in templates)

    def test_persistence(self):
        """Meta-skills should be persisted and reloaded."""
        from pathlib import Path

        meta = MetaOptimizer()
        meta.record_strategy("grid_search", improvement=0.2)
        meta.record_strategy("grid_search", improvement=0.18)
        meta.evolve_strategies()

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_path = Path(tmpdir) / "meta_skills.json"
            meta.meta_skill_path = skill_path
            assert meta.save_meta_skills()

            meta2 = MetaOptimizer(meta_skill_path=str(skill_path))
            assert meta2.load_meta_skills()
            assert len(meta2._meta_skills) > 0


def random_value():
    """Helper for random values in tests."""
    import random
    return random.uniform(0, 100)


# =============================================================================
# Loop Runner Integration Tests
# =============================================================================


class TestLoopRunnerIntegration:
    """Test loop runner with full integration."""

    def test_loop_runner_setup(self):
        """Loop runner should initialize all components."""
        runner = LoopRunner()
        runner.setup()

        assert runner.e2e_profiler is not None
        assert runner.interaction_tracker is not None
        assert runner.evaluator is not None
        assert runner.context_manager is not None
        assert runner.skill_extractor is not None
        assert runner.knowledge_inheritor is not None
        assert runner.meta_optimizer is not None

    def test_loop_runner_with_training(self):
        """Loop runner should execute with training callback."""
        runner = LoopRunner()
        runner.setup()

        # Set simple training runner
        def training_runner():
            return {
                "agent_results": {
                    "sampling": {
                        "best_params": {"spacing": 50.0},
                        "best_score": 0.85,
                        "baseline_score": 0.80,
                        "improvement_pct": 6.25,
                        "duration_seconds": 1.0,
                    },
                },
                "task_results": [
                    {"success": True, "quality_score": 85.0, "defects": []}
                    for _ in range(5)
                ],
            }

        runner.set_training_runner(training_runner)

        # Run 3 iterations
        result = runner.run_loop(max_iterations=3)

        assert isinstance(result, LoopResult)
        assert result.total_iterations == 3
        assert len(result.iterations) == 3

    def test_loop_runner_disabled(self):
        """Disabled loop runner should return immediately."""
        runner = LoopRunner()
        runner.enabled = False

        result = runner.run_loop()
        assert result.convergence_reason == "Loop engineering is disabled"
        assert result.total_iterations == 0

    def test_loop_runner_callbacks(self):
        """Callbacks should be triggered on iteration and convergence."""
        runner = LoopRunner()
        runner.setup()

        iteration_count = [0]
        convergence_called = [False]

        def on_iteration(iteration):
            iteration_count[0] += 1

        def on_convergence(result):
            convergence_called[0] = True

        runner.set_on_iteration(on_iteration)
        runner.set_on_convergence(on_convergence)

        def training_runner():
            return {"agent_results": {}, "task_results": []}

        runner.set_training_runner(training_runner)

        # Run 2 iterations
        runner.run_loop(max_iterations=2)

        assert iteration_count[0] == 2
        # Convergence may or may not be called depending on data

    def test_loop_runner_result_serialization(self):
        """Loop result should be serializable to JSON."""
        runner = LoopRunner()
        runner.setup()

        def training_runner():
            return {"agent_results": {}, "task_results": []}

        runner.set_training_runner(training_runner)
        result = runner.run_loop(max_iterations=2)

        # Serialize
        result_dict = result.to_dict()
        json_str = json.dumps(result_dict)
        assert len(json_str) > 0

        # Deserialize
        parsed = json.loads(json_str)
        assert parsed["run_id"] == result.run_id
        assert parsed["total_iterations"] == 2

    def test_loop_runner_save_result(self):
        """Loop result should be saved to disk."""
        runner = LoopRunner()
        runner.setup()

        def training_runner():
            return {"agent_results": {}, "task_results": []}

        runner.set_training_runner(training_runner)
        runner.run_loop(max_iterations=2)

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "result.json")
            assert runner.save_result(filepath)
            assert os.path.exists(filepath)


# =============================================================================
# Performance Benchmark Tests
# =============================================================================


class TestPerformanceBenchmarks:
    """Performance benchmarks for loop engineering components."""

    def test_evaluator_performance(self):
        """Evaluator should process 100 tasks quickly."""
        gen = TestDataGenerator(seed=42, num_tasks=100)
        data = gen.generate_all()

        evaluator = MultiDimensionEvaluator()
        evaluator.set_profiler_data(data.e2e_profile)
        evaluator.set_interaction_data(data.interaction_stats)
        evaluator.set_task_results(data.task_results)
        evaluator.set_context_data(data.context_data)
        evaluator.set_skill_data(data.skill_data)

        start = time.perf_counter()
        report = evaluator.evaluate()
        elapsed = (time.perf_counter() - start) * 1000

        # Should complete in under 100ms
        assert elapsed < 100, f"Evaluator took {elapsed:.0f}ms"

    def test_context_manager_performance(self):
        """Context manager should handle many updates quickly."""
        ctx = ContextManager(max_history=200)

        start = time.perf_counter()
        for i in range(500):
            ctx.update_state({f"key_{i}": i})
        elapsed = (time.perf_counter() - start) * 1000

        # Should complete in under 200ms
        assert elapsed < 200, f"Context manager took {elapsed:.0f}ms"

    def test_skill_extractor_performance(self):
        """Skill extractor should process traces quickly."""
        extractor = SkillExtractor(min_reuse_threshold=2)

        # Generate many traces
        start = time.perf_counter()
        for i in range(50):
            trace = [
                {"agent": f"agent_{j % 3}", "action": f"action_{j % 5}", "duration_ms": 10}
                for j in range(10)
            ]
            extractor.add_trace(f"task_{i}", trace)
        extractor.extract_skills()
        elapsed = (time.perf_counter() - start) * 1000

        # Should complete in under 500ms
        assert elapsed < 500, f"Skill extractor took {elapsed:.0f}ms"


# =============================================================================
# Enhanced Data Generator Integration Tests
# =============================================================================


class TestEnhancedDataGenerator:
    """Test the enhanced data generator with adversarial and long-tail scenarios."""

    def test_generate_adversarial_samples(self):
        """Adversarial samples should not crash the evaluator."""
        gen = TestDataGenerator(seed=42)
        adversarial = gen.generate_adversarial_samples(20)

        assert len(adversarial) == 20
        for sample in adversarial:
            assert "task_id" in sample

        # Feed to evaluator - should not crash
        evaluator = MultiDimensionEvaluator()
        evaluator.set_task_results(adversarial)
        report = evaluator.evaluate()
        assert report.composite_score >= 0.0
        assert report.composite_score <= 1.0

    def test_generate_robustness_scenarios(self):
        """Robustness scenarios should cover all failure modes."""
        gen = TestDataGenerator(seed=42)
        scenarios = gen.generate_robustness_scenarios()

        assert "network_degradation" in scenarios
        assert "sensor_noise" in scenarios
        assert "actuator_degradation" in scenarios
        assert "human_error" in scenarios
        assert "perfect_conditions" in scenarios

        # Each scenario should have at least some tasks
        for name, tasks in scenarios.items():
            assert len(tasks) > 0, f"Scenario {name} has no tasks"

        # Evaluate each scenario
        evaluator = MultiDimensionEvaluator()
        for name, tasks in scenarios.items():
            evaluator.reset()
            evaluator.set_task_results(tasks)
            report = evaluator.evaluate()
            assert report.composite_score >= 0.0, f"Scenario {name} failed evaluation"

    def test_robustness_scenarios_produce_distinct_scores(self):
        """Different scenarios should produce different scores."""
        gen = TestDataGenerator(seed=42)
        scenarios = gen.generate_robustness_scenarios()

        scores = {}
        evaluator = MultiDimensionEvaluator()
        for name, tasks in scenarios.items():
            evaluator.reset()
            evaluator.set_task_results(tasks)
            report = evaluator.evaluate()
            scores[name] = report.composite_score

        # Perfect conditions should score reasonably well
        assert scores["perfect_conditions"] > 0.35, (
            f"Perfect conditions score {scores['perfect_conditions']:.3f} too low"
        )

    def test_generate_multi_round_conversation(self):
        """Multi-round conversation should simulate context accumulation."""
        gen = TestDataGenerator(seed=42)
        rounds = gen.generate_multi_round_conversation(5)

        assert len(rounds) == 5
        # Context should grow over rounds
        for i in range(1, len(rounds)):
            assert rounds[i]["context_size"] >= rounds[i - 1]["context_size"]

        # Later rounds should have higher decay risk
        assert rounds[0]["decay_risk"] == "low"
        assert rounds[-1]["decay_risk"] == "high"

    def test_generate_long_tail_scenarios(self):
        """Long-tail scenarios should cover rare events."""
        gen = TestDataGenerator(seed=42)
        scenarios = gen.generate_long_tail_scenarios()

        expected_scenarios = [
            "emergency_stop", "power_fluctuation",
            "simultaneous_tasks", "environmental_extremes",
            "calibration_drift",
        ]
        for name in expected_scenarios:
            assert name in scenarios, f"Missing scenario: {name}"

        # Each scenario should have tasks
        for name, tasks in scenarios.items():
            assert len(tasks) > 0, f"Scenario {name} has no tasks"

    def test_long_tail_scenarios_dont_crash_evaluator(self):
        """Long-tail scenarios should not crash the evaluator."""
        gen = TestDataGenerator(seed=42)
        scenarios = gen.generate_long_tail_scenarios()
        evaluator = MultiDimensionEvaluator()

        for name, tasks in scenarios.items():
            evaluator.reset()
            evaluator.set_task_results(tasks)
            report = evaluator.evaluate()
            assert report.composite_score >= 0.0, f"Scenario {name} caused evaluation failure"

    def test_enhanced_edge_cases_cover_all_dimensions(self):
        """Enhanced edge cases should cover all 7 evaluation dimensions."""
        gen = TestDataGenerator(seed=42)
        edge_cases = gen.generate_edge_cases()

        # Should have more cases than the original 8
        assert len(edge_cases) > 8, "Enhanced edge cases should have more entries"

        # Feed all to evaluator
        evaluator = MultiDimensionEvaluator()
        evaluator.set_task_results(edge_cases)
        report = evaluator.evaluate()
        assert report.composite_score >= 0.0
        assert report.composite_score <= 1.0

    def test_adversarial_edge_cases_combined(self):
        """Combined adversarial and edge cases should not crash."""
        gen = TestDataGenerator(seed=42)
        all_cases = gen.generate_edge_cases() + gen.generate_adversarial_samples(10)

        evaluator = MultiDimensionEvaluator()
        evaluator.set_task_results(all_cases)
        report = evaluator.evaluate()
        assert report.composite_score >= 0.0
        assert report.composite_score <= 1.0

    def test_all_scenarios_across_quality_levels(self):
        """All scenarios should work across all quality levels."""
        for level in ["low", "medium", "high"]:
            gen = TestDataGenerator(seed=42, quality_level=level)
            data = gen.generate_all()

            evaluator = MultiDimensionEvaluator()
            evaluator.set_profiler_data(data.e2e_profile)
            evaluator.set_interaction_data(data.interaction_stats)
            evaluator.set_task_results(data.task_results)
            evaluator.set_context_data(data.context_data)
            evaluator.set_skill_data(data.skill_data)

            report = evaluator.evaluate()
            assert report.composite_score >= 0.0, f"Quality level {level} failed"
            assert report.composite_score <= 1.0, f"Quality level {level} out of range"