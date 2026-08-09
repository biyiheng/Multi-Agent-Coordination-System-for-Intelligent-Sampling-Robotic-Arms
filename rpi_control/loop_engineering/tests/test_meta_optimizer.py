"""
Unit tests for MetaOptimizer - optimization of optimization algorithms.

Tests cover:
1. Strategy recording and tracking
2. Meta-skill evolution from strategy history
3. Prompt template generation
4. Meta-skill management
5. Convergence analysis
6. Statistics
7. Persistence and reset
8. Edge cases
"""

import tempfile
from pathlib import Path

import pytest

from loop_engineering.meta_optimizer import (
    MetaOptimizer,
    MetaSkill,
    StrategyRecord,
)


class TestStrategyRecord:
    """Tests for StrategyRecord dataclass."""

    def test_default_values(self):
        """StrategyRecord should have correct defaults."""
        record = StrategyRecord(strategy_id="s1", strategy_type="grid_search")
        assert record.strategy_id == "s1"
        assert record.strategy_type == "grid_search"
        assert record.improvement == 0.0
        assert record.params == {}
        assert record.agent == ""
        assert record.success is False

    def test_success_detection(self):
        """Positive improvement should be marked as success."""
        meta = MetaOptimizer()
        record = meta.record_strategy(
            strategy_type="random",
            improvement=0.15,
            params={"samples": 50},
            agent="sampling",
        )
        assert record.success is True  # Positive improvement
        assert record.improvement == 0.15

    def test_failure_detection(self):
        """Negative improvement should be marked as failure."""
        meta = MetaOptimizer()
        record = meta.record_strategy(
            strategy_type="random",
            improvement=-0.05,
        )
        assert record.success is False


class TestMetaSkill:
    """Tests for MetaSkill dataclass."""

    def test_default_values(self):
        """MetaSkill should have correct defaults."""
        skill = MetaSkill(meta_id="m1", name="test")
        assert skill.meta_id == "m1"
        assert skill.name == "test"
        assert skill.strategy_type == ""
        assert skill.prompt_template == ""
        assert skill.rules == []
        assert skill.effectiveness == 0.0
        assert skill.application_count == 0
        assert skill.improvement_pct == 0.0

    def test_to_dict(self):
        """to_dict should serialize all fields."""
        skill = MetaSkill(
            meta_id="m1", name="Grid Optimizer",
            strategy_type="grid_search",
            prompt_template="Use grid search...",
            rules=["Rule 1", "Rule 2"],
            effectiveness=0.85,
            application_count=5,
            improvement_pct=12.5,
        )
        d = skill.to_dict()
        assert d["meta_id"] == "m1"
        assert d["name"] == "Grid Optimizer"
        assert d["prompt_template"] == "Use grid search..."
        assert len(d["rules"]) == 2
        assert d["effectiveness"] == 0.85
        assert d["application_count"] == 5

    def test_from_dict(self):
        """from_dict should deserialize correctly."""
        data = {
            "meta_id": "m1",
            "name": "Grid Optimizer",
            "strategy_type": "grid_search",
            "prompt_template": "Use grid search...",
            "rules": ["R1"],
            "effectiveness": 0.85,
            "application_count": 5,
            "improvement_pct": 12.5,
        }
        skill = MetaSkill.from_dict(data)
        assert skill.meta_id == "m1"
        assert skill.effectiveness == 0.85
        assert skill.rules == ["R1"]
        assert skill.improvement_pct == 12.5


class TestStrategyRecording:
    """Tests for strategy recording."""

    def test_record_single_strategy(self):
        """Recording a strategy should store it."""
        meta = MetaOptimizer()
        record = meta.record_strategy(
            strategy_type="grid_search",
            improvement=0.15,
            params={"spacing": 50},
            agent="sampling",
        )
        assert len(meta._strategies) == 1
        assert record.improvement == 0.15
        assert record.agent == "sampling"

    def test_record_updates_stats(self):
        """Recording should update strategy statistics."""
        meta = MetaOptimizer()
        meta.record_strategy("grid_search", 0.1)
        meta.record_strategy("grid_search", 0.2)

        stats = meta._strategy_stats["grid_search"]
        assert stats["count"] == 2
        assert stats["total_improvement"] == pytest.approx(0.3)
        assert stats["successes"] == 2

    def test_record_negative_improvement(self):
        """Negative improvement should be recorded as failure."""
        meta = MetaOptimizer()
        meta.record_strategy("grid_search", -0.05)

        stats = meta._strategy_stats["grid_search"]
        assert stats["count"] == 1
        assert stats["failures"] == 1

    def test_record_multiple_strategy_types(self):
        """Recording different strategy types should track separately."""
        meta = MetaOptimizer()
        meta.record_strategy("grid_search", 0.1)
        meta.record_strategy("bayesian", 0.15)
        meta.record_strategy("random_search", 0.05)

        assert "grid_search" in meta._strategy_stats
        assert "bayesian" in meta._strategy_stats
        assert "random_search" in meta._strategy_stats

    def test_record_with_notes(self):
        """Recording with notes should store them."""
        meta = MetaOptimizer()
        record = meta.record_strategy(
            "grid_search", 0.1, notes="Tried finer spacing"
        )
        assert record.notes == "Tried finer spacing"

    def test_improvement_history(self):
        """Improvement history should track all improvements."""
        meta = MetaOptimizer()
        meta.record_strategy("grid_search", 0.1)
        meta.record_strategy("grid_search", 0.2)
        meta.record_strategy("grid_search", -0.05)

        assert meta._improvement_history == [0.1, 0.2, -0.05]

    def test_history_size_limit(self):
        """Strategy history should be limited."""
        meta = MetaOptimizer(strategy_history_size=5)
        for i in range(10):
            meta.record_strategy("grid_search", 0.01 * i)

        assert len(meta._strategies) == 5
        # Should keep the most recent 5
        assert meta._strategies[-1].improvement == 0.09


class TestMetaSkillEvolution:
    """Tests for meta-skill evolution."""

    def test_evolve_below_threshold(self):
        """Improvements below threshold should not create meta-skills."""
        meta = MetaOptimizer(min_improvement_threshold=0.1)
        meta.record_strategy("grid_search", 0.03)
        meta.record_strategy("grid_search", 0.04)

        skills = meta.evolve_strategies()
        assert len(skills) == 0  # Average 0.035 < 0.1

    def test_evolve_above_threshold(self):
        """Improvements above threshold should create meta-skills."""
        meta = MetaOptimizer(min_improvement_threshold=0.05)
        meta.record_strategy("grid_search", 0.15)
        meta.record_strategy("grid_search", 0.25)

        skills = meta.evolve_strategies()
        assert len(skills) == 1
        assert skills[0].name == "Optimize via grid_search"
        assert skills[0].strategy_type == "grid_search"

    def test_evolve_insufficient_count(self):
        """Single strategy should not create meta-skill."""
        meta = MetaOptimizer(min_improvement_threshold=0.01)
        meta.record_strategy("grid_search", 0.5)

        skills = meta.evolve_strategies()
        assert len(skills) == 0

    def test_evolve_updates_existing(self):
        """Existing meta-skill should be updated on re-evolution."""
        meta = MetaOptimizer(min_improvement_threshold=0.05)
        meta.record_strategy("grid_search", 0.1)
        meta.record_strategy("grid_search", 0.2)
        meta.evolve_strategies()

        # Add more strategies
        meta.record_strategy("grid_search", 0.3)
        meta.record_strategy("grid_search", 0.4)
        skills = meta.evolve_strategies()

        assert len(skills) == 0  # No new skills (existing was updated)
        skill = meta.get_meta_skill("grid_search")
        assert skill is not None
        assert skill.application_count == 2
        assert skill.improvement_pct == pytest.approx(25.0)  # (0.1+0.2+0.3+0.4)/4*100

    def test_evolve_multiple_strategies(self):
        """Multiple strategy types should create multiple meta-skills."""
        meta = MetaOptimizer(min_improvement_threshold=0.05)
        meta.record_strategy("grid_search", 0.15)
        meta.record_strategy("grid_search", 0.25)
        meta.record_strategy("bayesian", 0.30)
        meta.record_strategy("bayesian", 0.40)

        skills = meta.evolve_strategies()
        assert len(skills) == 2

    def test_evolve_mixed_success(self):
        """Mixed successes and failures should affect effectiveness."""
        meta = MetaOptimizer(min_improvement_threshold=0.05)
        meta.record_strategy("grid_search", 0.1)   # success
        meta.record_strategy("grid_search", -0.05)  # failure
        meta.record_strategy("grid_search", 0.2)   # success

        skills = meta.evolve_strategies()
        assert len(skills) == 1
        assert skills[0].effectiveness == pytest.approx(2 / 3)


class TestPromptTemplateGeneration:
    """Tests for prompt template generation."""

    def test_grid_search_prompt(self):
        """Grid search should generate appropriate prompt."""
        meta = MetaOptimizer(min_improvement_threshold=0.05)
        meta.record_strategy("grid_search", 0.15)
        meta.record_strategy("grid_search", 0.25)
        meta.evolve_strategies()

        skill = meta.get_meta_skill("grid_search")
        assert "grid search" in skill.prompt_template.lower()
        assert "20.0%" in skill.prompt_template

    def test_bayesian_prompt(self):
        """Bayesian should generate appropriate prompt."""
        meta = MetaOptimizer(min_improvement_threshold=0.05)
        meta.record_strategy("bayesian", 0.3)
        meta.record_strategy("bayesian", 0.4)
        meta.evolve_strategies()

        skill = meta.get_meta_skill("bayesian")
        assert "bayesian" in skill.prompt_template.lower()

    def test_unknown_strategy_prompt(self):
        """Unknown strategy type should generate generic prompt."""
        meta = MetaOptimizer(min_improvement_threshold=0.05)
        meta.record_strategy("custom_strategy", 0.2)
        meta.record_strategy("custom_strategy", 0.3)
        meta.evolve_strategies()

        skill = meta.get_meta_skill("custom_strategy")
        assert "custom_strategy" in skill.prompt_template

    def test_generated_rules(self):
        """Rules should be generated for each strategy type."""
        meta = MetaOptimizer(min_improvement_threshold=0.05)
        meta.record_strategy("grid_search", 0.15, params={"spacing": 50})
        meta.record_strategy("grid_search", 0.25, params={"spacing": 30})
        meta.evolve_strategies()

        skill = meta.get_meta_skill("grid_search")
        assert len(skill.rules) > 0
        assert any("parameter bounds" in r.lower() for r in skill.rules)

    def test_get_prompt_templates(self):
        """Should return all prompt templates."""
        meta = MetaOptimizer(min_improvement_threshold=0.05)
        meta.record_strategy("grid_search", 0.15)
        meta.record_strategy("grid_search", 0.25)
        meta.record_strategy("bayesian", 0.3)
        meta.record_strategy("bayesian", 0.4)
        meta.evolve_strategies()

        templates = meta.get_prompt_templates()
        assert len(templates) == 2


class TestMetaSkillManagement:
    """Tests for meta-skill retrieval and management."""

    def test_get_meta_skill(self):
        """Should retrieve meta-skill by strategy type."""
        meta = MetaOptimizer(min_improvement_threshold=0.05)
        meta.record_strategy("grid_search", 0.15)
        meta.record_strategy("grid_search", 0.25)
        meta.evolve_strategies()

        skill = meta.get_meta_skill("grid_search")
        assert skill is not None
        assert skill.strategy_type == "grid_search"

    def test_get_nonexistent_meta_skill(self):
        """Getting nonexistent meta-skill should return None."""
        meta = MetaOptimizer()
        assert meta.get_meta_skill("nonexistent") is None

    def test_get_top_meta_skills(self):
        """Should return top meta-skills sorted by effectiveness * improvement."""
        meta = MetaOptimizer(min_improvement_threshold=0.05)
        meta.record_strategy("grid_search", 0.15)
        meta.record_strategy("grid_search", 0.25)
        meta.record_strategy("bayesian", 0.30)
        meta.record_strategy("bayesian", 0.40)
        meta.evolve_strategies()

        top = meta.get_top_meta_skills(2)
        assert len(top) == 2
        # Bayesian should be top (higher improvement)
        assert top[0].strategy_type == "bayesian"

    def test_get_top_meta_skills_empty(self):
        """Empty skills should return empty list."""
        meta = MetaOptimizer()
        assert meta.get_top_meta_skills() == []

    def test_get_best_strategy(self):
        """Should return best strategy type name."""
        meta = MetaOptimizer()
        meta.record_strategy("grid_search", 0.1)
        meta.record_strategy("grid_search", 0.2)
        meta.record_strategy("bayesian", 0.3)
        meta.record_strategy("bayesian", 0.4)

        best = meta.get_best_strategy()
        assert best == "bayesian"  # Higher average improvement

    def test_get_best_strategy_empty(self):
        """Empty stats should return None."""
        meta = MetaOptimizer()
        assert meta.get_best_strategy() is None


class TestConvergenceAnalysis:
    """Tests for convergence detection."""

    def test_convergence_insufficient_data(self):
        """Insufficient data should return not converged."""
        meta = MetaOptimizer()
        analysis = meta.get_convergence_analysis()
        assert not analysis["converged"]
        assert analysis["reason"] == "Insufficient data"

    def test_decreasing_trend_convergence(self):
        """Decreasing improvement trend should indicate convergence."""
        meta = MetaOptimizer()
        # Decreasing improvements
        for imp in [0.5, 0.4, 0.3, 0.2, 0.1]:
            meta.record_strategy("grid_search", imp)

        analysis = meta.get_convergence_analysis()
        assert analysis["converged"]

    def test_below_threshold_convergence(self):
        """All improvements below threshold should indicate convergence."""
        meta = MetaOptimizer(min_improvement_threshold=0.05)
        for imp in [0.01, 0.02, 0.01, 0.03, 0.01]:
            meta.record_strategy("grid_search", imp)

        analysis = meta.get_convergence_analysis()
        assert analysis["converged"]

    def test_not_converged(self):
        """Increasing improvements should indicate not converged."""
        meta = MetaOptimizer()
        for imp in [0.1, 0.2, 0.3, 0.4, 0.5]:
            meta.record_strategy("grid_search", imp)

        analysis = meta.get_convergence_analysis()
        assert not analysis["converged"]


class TestMetaOptimizerStatistics:
    """Tests for statistics."""

    def test_empty_statistics(self):
        """Empty optimizer should return zero statistics."""
        meta = MetaOptimizer()
        stats = meta.get_statistics()
        assert stats["total_strategies"] == 0
        assert stats["meta_skills_count"] == 0
        assert stats["best_strategy"] is None

    def test_statistics_with_data(self):
        """Statistics should reflect recorded data."""
        meta = MetaOptimizer()
        meta.record_strategy("grid_search", 0.15)
        meta.record_strategy("grid_search", 0.25)
        meta.record_strategy("bayesian", -0.05)

        stats = meta.get_statistics()
        assert stats["total_strategies"] == 3
        assert stats["successful_strategies"] == 2
        assert stats["strategy_success_rate"] == pytest.approx(2 / 3)
        assert "strategy_breakdown" in stats
        assert "grid_search" in stats["strategy_breakdown"]
        assert "bayesian" in stats["strategy_breakdown"]
        assert "improvement_trend" in stats

    def test_strategy_breakdown_stats(self):
        """Strategy breakdown should have correct per-type stats."""
        meta = MetaOptimizer()
        meta.record_strategy("grid_search", 0.1)
        meta.record_strategy("grid_search", 0.3)

        stats = meta.get_statistics()
        breakdown = stats["strategy_breakdown"]["grid_search"]
        assert breakdown["count"] == 2
        assert breakdown["avg_improvement"] == 0.2
        assert breakdown["success_rate"] == 1.0


class TestMetaOptimizerPersistence:
    """Tests for meta-skill persistence."""

    def test_save_meta_skills(self):
        """Should save meta-skills to disk."""
        meta = MetaOptimizer(min_improvement_threshold=0.05)
        meta.record_strategy("grid_search", 0.15)
        meta.record_strategy("grid_search", 0.25)
        meta.evolve_strategies()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "meta_skills.json"
            meta.meta_skill_path = path
            assert meta.save_meta_skills()
            assert path.exists()

    def test_save_without_path(self):
        """Save without path should return False."""
        meta = MetaOptimizer()
        assert not meta.save_meta_skills()

    def test_load_meta_skills(self):
        """Should load meta-skills from disk."""
        meta = MetaOptimizer(min_improvement_threshold=0.05)
        meta.record_strategy("grid_search", 0.15)
        meta.record_strategy("grid_search", 0.25)
        meta.evolve_strategies()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "meta_skills.json"
            meta.meta_skill_path = path
            meta.save_meta_skills()

            meta2 = MetaOptimizer(meta_skill_path=str(path))
            assert meta2.load_meta_skills()
            assert len(meta2._meta_skills) > 0
            assert meta2.get_meta_skill("grid_search") is not None

    def test_load_nonexistent_file(self):
        """Loading nonexistent file should return False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            meta = MetaOptimizer(meta_skill_path=str(Path(tmpdir) / "nonexistent.json"))
            assert not meta.load_meta_skills()

    def test_load_without_path(self):
        """Loading without path should return False."""
        meta = MetaOptimizer()
        assert not meta.load_meta_skills()


class TestMetaOptimizerReset:
    """Tests for reset functionality."""

    def test_reset_clears_all(self):
        """Reset should clear all data."""
        meta = MetaOptimizer()
        meta.record_strategy("grid_search", 0.15)
        meta.record_strategy("grid_search", 0.25)
        meta.evolve_strategies()

        meta.reset()
        assert len(meta._strategies) == 0
        assert len(meta._meta_skills) == 0
        assert len(meta._strategy_stats) == 0
        assert len(meta._improvement_history) == 0

    def test_reset_allows_new_operations(self):
        """After reset, new operations should work."""
        meta = MetaOptimizer()
        meta.record_strategy("grid_search", 0.15)
        meta.reset()

        meta.record_strategy("grid_search", 0.25)
        assert len(meta._strategies) == 1


class TestMetaOptimizerEdgeCases:
    """Edge case tests."""

    def test_zero_improvement(self):
        """Zero improvement should be recorded as failure."""
        meta = MetaOptimizer()
        meta.record_strategy("grid_search", 0.0)
        stats = meta._strategy_stats["grid_search"]
        assert stats["failures"] == 1

    def test_very_large_improvement(self):
        """Very large improvement should work."""
        meta = MetaOptimizer()
        meta.record_strategy("grid_search", 100.0)
        meta.record_strategy("grid_search", 200.0)
        stats = meta.get_statistics()
        assert stats["avg_improvement_pct"] == pytest.approx(15000.0)  # 150 * 100

    def test_many_strategy_types(self):
        """Many strategy types should work."""
        meta = MetaOptimizer(min_improvement_threshold=0.05)
        types = ["grid_search", "bayesian", "random_search", "gradient_descent"]
        for t in types:
            meta.record_strategy(t, 0.15)
            meta.record_strategy(t, 0.25)
        meta.evolve_strategies()

        assert len(meta._meta_skills) == 4
        for t in types:
            assert meta.get_meta_skill(t) is not None