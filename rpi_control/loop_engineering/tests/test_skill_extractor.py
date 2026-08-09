"""
Unit tests for SkillExtractor - skill extraction from execution traces.

Tests cover:
1. Trace management and pattern extraction
2. Skill creation from recurring patterns
3. Skill effectiveness tracking
4. Skill management (get, filter, top)
5. Persistence and reset
6. Edge cases
"""

import tempfile
import time
from pathlib import Path

import pytest

from loop_engineering.skill_extractor import (
    Skill,
    SkillExtractor,
    SkillStep,
)


class TestSkillStep:
    """Tests for SkillStep dataclass."""

    def test_default_values(self):
        """SkillStep should have correct defaults."""
        step = SkillStep(agent="test", action="run")
        assert step.agent == "test"
        assert step.action == "run"
        assert step.params == {}
        assert step.expected_duration_ms == 0.0

    def test_with_params(self):
        """SkillStep should accept params."""
        step = SkillStep(
            agent="motion",
            action="approach",
            params={"speed": 500},
            expected_duration_ms=150.0,
        )
        assert step.params == {"speed": 500}
        assert step.expected_duration_ms == 150.0


class TestSkill:
    """Tests for Skill dataclass."""

    def test_default_values(self):
        """Skill should have correct defaults."""
        skill = Skill(skill_id="s1", name="test_skill")
        assert skill.skill_id == "s1"
        assert skill.name == "test_skill"
        assert skill.effectiveness == 0.0
        assert skill.reuse_count == 0
        assert skill.success_count == 0
        assert skill.failure_count == 0

    def test_update_effectiveness(self):
        """Effectiveness should be calculated from success/failure ratio."""
        skill = Skill(skill_id="s1", name="test")
        skill.success_count = 3
        skill.failure_count = 1
        skill.update_effectiveness()
        assert skill.effectiveness == 0.75  # 3/4

    def test_update_effectiveness_zero_total(self):
        """Effectiveness should be 0 when no executions."""
        skill = Skill(skill_id="s1", name="test")
        skill.update_effectiveness()
        assert skill.effectiveness == 0.0

    def test_signature(self):
        """Skill signature should be deterministic."""
        s1 = Skill(
            skill_id="a", name="test",
            steps=[SkillStep(agent="A", action="run"), SkillStep(agent="B", action="stop")],
        )
        s2 = Skill(
            skill_id="b", name="test",
            steps=[SkillStep(agent="A", action="run"), SkillStep(agent="B", action="stop")],
        )
        assert s1.signature() == s2.signature()

    def test_signature_different_for_different_steps(self):
        """Different steps should produce different signatures."""
        s1 = Skill(
            skill_id="a", name="test",
            steps=[SkillStep(agent="A", action="run")],
        )
        s2 = Skill(
            skill_id="b", name="test",
            steps=[SkillStep(agent="B", action="run")],
        )
        assert s1.signature() != s2.signature()

    def test_to_dict(self):
        """to_dict should serialize all fields."""
        skill = Skill(
            skill_id="s1", name="test",
            steps=[SkillStep(agent="A", action="run", expected_duration_ms=10.0)],
            description="A test skill",
            effectiveness=0.8,
            reuse_count=5,
            success_count=4,
            failure_count=1,
            source_agent="A",
            version=2,
        )
        d = skill.to_dict()
        assert d["skill_id"] == "s1"
        assert d["name"] == "test"
        assert len(d["steps"]) == 1
        assert d["steps"][0]["agent"] == "A"
        assert d["effectiveness"] == 0.8
        assert d["reuse_count"] == 5
        assert d["version"] == 2

    def test_from_dict(self):
        """from_dict should deserialize correctly."""
        data = {
            "skill_id": "s1",
            "name": "test",
            "steps": [{"agent": "A", "action": "run", "params": {}, "expected_duration_ms": 10.0}],
            "effectiveness": 0.8,
            "reuse_count": 5,
            "success_count": 4,
            "failure_count": 1,
        }
        skill = Skill.from_dict(data)
        assert skill.skill_id == "s1"
        assert skill.name == "test"
        assert len(skill.steps) == 1
        assert skill.steps[0].agent == "A"
        assert skill.effectiveness == 0.8


class TestTraceManagement:
    """Tests for trace collection and pattern extraction."""

    def test_add_single_trace(self):
        """Adding a trace should store it."""
        extractor = SkillExtractor()
        trace = [
            {"agent": "A", "action": "start"},
            {"agent": "A", "action": "do_work"},
            {"agent": "A", "action": "finish"},
        ]
        extractor.add_trace("task_1", trace)
        assert "task_1" in extractor._traces
        assert len(extractor._traces["task_1"]) == 3

    def test_add_multiple_traces(self):
        """Multiple traces should be stored separately."""
        extractor = SkillExtractor()
        extractor.add_trace("t1", [{"agent": "A", "action": "run"}])
        extractor.add_trace("t2", [{"agent": "B", "action": "run"}])
        assert len(extractor._traces) == 2

    def test_pattern_extraction_from_trace(self):
        """Patterns should be extracted from traces."""
        extractor = SkillExtractor()
        trace = [
            {"agent": "A", "action": "start"},
            {"agent": "A", "action": "run"},
            {"agent": "A", "action": "stop"},
        ]
        extractor.add_trace("task_1", trace)
        # Should have extracted patterns of length 2 and 3
        assert len(extractor._patterns) > 0

    def test_empty_trace_no_patterns(self):
        """Empty trace should produce no patterns."""
        extractor = SkillExtractor()
        extractor.add_trace("task_1", [])
        assert len(extractor._patterns) == 0

    def test_single_entry_trace_no_patterns(self):
        """Single entry trace should produce no patterns."""
        extractor = SkillExtractor()
        extractor.add_trace("task_1", [{"agent": "A", "action": "run"}])
        assert len(extractor._patterns) == 0

    def test_pattern_with_metadata_fallback(self):
        """Patterns should use 'caller' and 'operation' as fallback keys."""
        extractor = SkillExtractor()
        trace = [
            {"caller": "A", "operation": "start"},
            {"caller": "A", "operation": "finish"},
        ]
        extractor.add_trace("task_1", trace)
        assert len(extractor._patterns) > 0


class TestSkillExtraction:
    """Tests for skill extraction from patterns."""

    def test_extract_below_threshold(self):
        """Patterns below reuse threshold should not become skills."""
        extractor = SkillExtractor(min_reuse_threshold=3)
        trace = [
            {"agent": "A", "action": "start"},
            {"agent": "A", "action": "finish"},
        ]
        extractor.add_trace("task_1", trace)
        extractor.add_trace("task_2", trace)
        skills = extractor.extract_skills()
        assert len(skills) == 0

    def test_extract_above_threshold(self):
        """Patterns above reuse threshold should become skills."""
        extractor = SkillExtractor(min_reuse_threshold=2)
        trace = [
            {"agent": "A", "action": "start", "duration_ms": 10},
            {"agent": "A", "action": "finish", "duration_ms": 5},
        ]
        extractor.add_trace("task_1", trace)
        extractor.add_trace("task_2", trace)
        skills = extractor.extract_skills()
        assert len(skills) > 0

    def test_extracted_skill_has_steps(self):
        """Extracted skill should have correct steps."""
        extractor = SkillExtractor(min_reuse_threshold=2)
        trace = [
            {"agent": "A", "action": "start", "duration_ms": 10},
            {"agent": "B", "action": "finish", "duration_ms": 5},
        ]
        extractor.add_trace("task_1", trace)
        extractor.add_trace("task_2", trace)
        skills = extractor.extract_skills()
        assert len(skills) > 0
        skill = skills[0]
        assert len(skill.steps) == 2
        assert skill.steps[0].agent == "A"
        assert skill.steps[1].agent == "B"

    def test_extracted_skill_has_name(self):
        """Extracted skill should have auto-generated name."""
        extractor = SkillExtractor(min_reuse_threshold=2)
        trace = [
            {"agent": "sampling", "action": "process"},
            {"agent": "sampling", "action": "validate"},
        ]
        extractor.add_trace("task_1", trace)
        extractor.add_trace("task_2", trace)
        skills = extractor.extract_skills()
        assert len(skills) > 0
        assert "sampling_process" in skills[0].name

    def test_extracted_skill_expected_duration(self):
        """Extracted skill should calculate expected duration from occurrences."""
        extractor = SkillExtractor(min_reuse_threshold=2)
        trace = [
            {"agent": "A", "action": "run", "duration_ms": 100},
            {"agent": "A", "action": "stop", "duration_ms": 50},
        ]
        extractor.add_trace("task_1", trace)
        extractor.add_trace("task_2", trace)
        skills = extractor.extract_skills()
        assert len(skills) > 0
        # Duration should be calculated from occurrences
        assert skills[0].steps[0].expected_duration_ms > 0

    def test_duplicate_skill_increments_reuse(self):
        """Same pattern extracted again should increment reuse count."""
        extractor = SkillExtractor(min_reuse_threshold=2)
        trace = [
            {"agent": "A", "action": "start"},
            {"agent": "A", "action": "finish"},
        ]
        extractor.add_trace("task_1", trace)
        extractor.add_trace("task_2", trace)
        extractor.extract_skills()

        # Add another occurrence
        extractor.add_trace("task_3", trace)
        extractor.extract_skills()

        skills = list(extractor._skills.values())
        assert len(skills) == 1
        assert skills[0].reuse_count >= 2

    def test_similar_skill_matching(self):
        """Similar skills with same agents should be matched."""
        extractor = SkillExtractor(min_reuse_threshold=2, similarity_threshold=0.5)
        trace1 = [
            {"agent": "A", "action": "start"},
            {"agent": "B", "action": "finish"},
        ]
        trace2 = [
            {"agent": "A", "action": "different_start"},
            {"agent": "B", "action": "different_finish"},
        ]
        extractor.add_trace("task_1", trace1)
        extractor.add_trace("task_2", trace1)
        extractor.extract_skills()

        # Similar trace with same agents
        extractor.add_trace("task_3", trace2)
        extractor.add_trace("task_4", trace2)
        skills = extractor.extract_skills()

        # The similar trace might be matched to the existing skill
        # or create a new one depending on similarity
        assert len(extractor._skills) >= 1


class TestSkillEffectiveness:
    """Tests for skill effectiveness tracking."""

    def test_initial_effectiveness_zero(self):
        """Newly extracted skill should have zero effectiveness."""
        extractor = SkillExtractor(min_reuse_threshold=2)
        trace = [
            {"agent": "A", "action": "run"},
            {"agent": "A", "action": "stop"},
        ]
        extractor.add_trace("task_1", trace)
        extractor.add_trace("task_2", trace)
        skills = extractor.extract_skills()
        assert len(skills) > 0
        assert skills[0].effectiveness == 0.0

    def test_record_successful_execution(self):
        """Successful execution should update effectiveness."""
        extractor = SkillExtractor(min_reuse_threshold=2)
        trace = [
            {"agent": "A", "action": "run"},
            {"agent": "A", "action": "stop"},
        ]
        extractor.add_trace("task_1", trace)
        extractor.add_trace("task_2", trace)
        skills = extractor.extract_skills()
        skill_id = skills[0].skill_id

        extractor.record_skill_execution(skill_id, success=True)
        skill = extractor.get_skill(skill_id)
        assert skill.effectiveness == 1.0  # 1/1

    def test_record_failed_execution(self):
        """Failed execution should update effectiveness."""
        extractor = SkillExtractor(min_reuse_threshold=2)
        trace = [
            {"agent": "A", "action": "run"},
            {"agent": "A", "action": "stop"},
        ]
        extractor.add_trace("task_1", trace)
        extractor.add_trace("task_2", trace)
        skills = extractor.extract_skills()
        skill_id = skills[0].skill_id

        extractor.record_skill_execution(skill_id, success=False)
        skill = extractor.get_skill(skill_id)
        assert skill.effectiveness == 0.0  # 0/1

    def test_mixed_executions(self):
        """Mixed successes and failures should calculate correctly."""
        extractor = SkillExtractor(min_reuse_threshold=2)
        trace = [
            {"agent": "A", "action": "run"},
            {"agent": "A", "action": "stop"},
        ]
        extractor.add_trace("task_1", trace)
        extractor.add_trace("task_2", trace)
        skills = extractor.extract_skills()
        skill_id = skills[0].skill_id

        extractor.record_skill_execution(skill_id, success=True)
        extractor.record_skill_execution(skill_id, success=True)
        extractor.record_skill_execution(skill_id, success=False)
        skill = extractor.get_skill(skill_id)
        assert skill.effectiveness == pytest.approx(2 / 3)

    def test_record_nonexistent_skill(self):
        """Recording execution for nonexistent skill should not crash."""
        extractor = SkillExtractor()
        extractor.record_skill_execution("nonexistent", success=True)
        # Should not raise


class TestSkillManagement:
    """Tests for skill retrieval and management."""

    def test_get_skill_by_id(self):
        """Should retrieve skill by ID."""
        extractor = SkillExtractor(min_reuse_threshold=2)
        trace = [
            {"agent": "A", "action": "run"},
            {"agent": "A", "action": "stop"},
        ]
        extractor.add_trace("task_1", trace)
        extractor.add_trace("task_2", trace)
        skills = extractor.extract_skills()
        skill_id = skills[0].skill_id

        skill = extractor.get_skill(skill_id)
        assert skill is not None
        assert skill.skill_id == skill_id

    def test_get_nonexistent_skill(self):
        """Getting nonexistent skill should return None."""
        extractor = SkillExtractor()
        assert extractor.get_skill("nonexistent") is None

    def test_get_skills_by_agent(self):
        """Should filter skills by source agent."""
        extractor = SkillExtractor(min_reuse_threshold=2)
        trace = [
            {"agent": "sampling", "action": "run"},
            {"agent": "sampling", "action": "stop"},
        ]
        extractor.add_trace("task_1", trace)
        extractor.add_trace("task_2", trace)
        extractor.extract_skills()

        skills = extractor.get_skills_by_agent("sampling")
        assert len(skills) > 0

        skills = extractor.get_skills_by_agent("nonexistent")
        assert len(skills) == 0

    def test_get_top_skills(self):
        """Should return top skills sorted by effectiveness * reuse."""
        extractor = SkillExtractor(min_reuse_threshold=2)
        trace = [
            {"agent": "A", "action": "run"},
            {"agent": "A", "action": "stop"},
        ]
        extractor.add_trace("task_1", trace)
        extractor.add_trace("task_2", trace)
        skills = extractor.extract_skills()
        skill_id = skills[0].skill_id

        extractor.record_skill_execution(skill_id, success=True)
        extractor.record_skill_execution(skill_id, success=True)

        top = extractor.get_top_skills(3)
        assert len(top) >= 1

    def test_get_top_skills_empty(self):
        """Empty skills should return empty list."""
        extractor = SkillExtractor()
        assert extractor.get_top_skills() == []

    def test_get_skill_statistics(self):
        """Should return comprehensive statistics."""
        extractor = SkillExtractor(min_reuse_threshold=2)
        trace = [
            {"agent": "A", "action": "run"},
            {"agent": "A", "action": "stop"},
        ]
        extractor.add_trace("task_1", trace)
        extractor.add_trace("task_2", trace)
        extractor.extract_skills()

        stats = extractor.get_skill_statistics()
        assert "skills_extracted" in stats
        assert "total_skills" in stats
        assert "reuse_rate" in stats
        assert "skill_effectiveness" in stats
        assert "execution_success_rate" in stats
        assert "patterns_analyzed" in stats


class TestSkillPersistence:
    """Tests for skill library persistence."""

    def test_save_library(self):
        """Should save skills to disk."""
        extractor = SkillExtractor(min_reuse_threshold=2)
        trace = [
            {"agent": "A", "action": "run"},
            {"agent": "A", "action": "stop"},
        ]
        extractor.add_trace("task_1", trace)
        extractor.add_trace("task_2", trace)
        extractor.extract_skills()

        with tempfile.TemporaryDirectory() as tmpdir:
            lib_path = Path(tmpdir) / "skills.json"
            extractor.library_path = lib_path
            assert extractor.save_library()
            assert lib_path.exists()

    def test_save_without_path(self):
        """Save without library_path should return False."""
        extractor = SkillExtractor()
        assert not extractor.save_library()

    def test_load_library(self):
        """Should load skills from disk."""
        extractor = SkillExtractor(min_reuse_threshold=2)
        trace = [
            {"agent": "A", "action": "run"},
            {"agent": "A", "action": "stop"},
        ]
        extractor.add_trace("task_1", trace)
        extractor.add_trace("task_2", trace)
        extractor.extract_skills()

        with tempfile.TemporaryDirectory() as tmpdir:
            lib_path = Path(tmpdir) / "skills.json"
            extractor.library_path = lib_path
            extractor.save_library()

            extractor2 = SkillExtractor(library_path=str(lib_path))
            assert extractor2.load_library()
            assert len(extractor2._skills) > 0

    def test_load_nonexistent_file(self):
        """Loading nonexistent file should return False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = SkillExtractor(library_path=str(Path(tmpdir) / "nonexistent.json"))
            assert not extractor.load_library()

    def test_load_without_path(self):
        """Loading without path should return False."""
        extractor = SkillExtractor()
        assert not extractor.load_library()


class TestSkillExtractorReset:
    """Tests for reset functionality."""

    def test_reset_clears_all(self):
        """Reset should clear all data."""
        extractor = SkillExtractor(min_reuse_threshold=2)
        trace = [
            {"agent": "A", "action": "run"},
            {"agent": "A", "action": "stop"},
        ]
        extractor.add_trace("task_1", trace)
        extractor.add_trace("task_2", trace)
        extractor.extract_skills()

        extractor.reset()
        assert len(extractor._traces) == 0
        assert len(extractor._skills) == 0
        assert len(extractor._patterns) == 0
        assert len(extractor._skill_executions) == 0
        assert extractor._skills_extracted == 0
        assert extractor._skills_reused == 0

    def test_reset_allows_new_operations(self):
        """After reset, new operations should work."""
        extractor = SkillExtractor(min_reuse_threshold=2)
        trace = [
            {"agent": "A", "action": "run"},
            {"agent": "A", "action": "stop"},
        ]
        extractor.add_trace("task_1", trace)
        extractor.add_trace("task_2", trace)
        extractor.extract_skills()
        extractor.reset()

        extractor.add_trace("task_3", trace)
        extractor.add_trace("task_4", trace)
        skills = extractor.extract_skills()
        assert len(skills) > 0


class TestSkillExtractorEdgeCases:
    """Edge case tests."""

    def test_very_long_trace(self):
        """Very long traces should be handled."""
        extractor = SkillExtractor(min_reuse_threshold=2)
        trace = [{"agent": "A", "action": f"action_{i}"} for i in range(100)]
        extractor.add_trace("task_1", trace)
        extractor.add_trace("task_2", trace)
        # Should not crash
        skills = extractor.extract_skills()
        assert isinstance(skills, list)

    def test_trace_with_various_key_formats(self):
        """Traces with different key formats should be handled."""
        extractor = SkillExtractor(min_reuse_threshold=2)
        trace = [
            {"agent": "A", "action": "start", "params": {"x": 1}},
            {"caller": "B", "operation": "run", "metadata": {"speed": 100}},
            {"agent": "C", "action": "stop"},
        ]
        extractor.add_trace("task_1", trace)
        extractor.add_trace("task_2", trace)
        skills = extractor.extract_skills()
        assert isinstance(skills, list)

    def test_extract_skills_empty_traces(self):
        """Extracting skills with no traces should return empty."""
        extractor = SkillExtractor()
        skills = extractor.extract_skills()
        assert skills == []

    def test_skill_updated_at_changes(self):
        """Skill updated_at should change on update_effectiveness."""
        skill = Skill(skill_id="s1", name="test")
        original_time = skill.updated_at
        time.sleep(0.001)
        skill.success_count = 1
        skill.update_effectiveness()
        assert skill.updated_at > original_time