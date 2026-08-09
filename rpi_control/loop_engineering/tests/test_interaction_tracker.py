"""
Unit tests for the InteractionTracker.

Tests cover:
1. Recording interactions
2. Statistics by type
3. Agent call counts and dependency graph
4. Redundancy detection
5. Per-task grouping
6. Context size statistics
7. Compression suggestions
8. Trace export
9. Reset functionality
"""

import pytest
from loop_engineering.interaction_tracker import (
    InteractionTracker,
    InteractionRecord,
)


# =============================================================================
# InteractionRecord Tests
# =============================================================================


class TestInteractionRecord:
    """Test InteractionRecord dataclass."""

    def test_default_values(self):
        """Default values should be set correctly."""
        record = InteractionRecord(
            caller="orchestrator",
            callee="motion_agent",
            interaction_type="agent_call",
        )
        assert record.caller == "orchestrator"
        assert record.callee == "motion_agent"
        assert record.interaction_type == "agent_call"
        assert record.timestamp > 0
        assert record.context_size == 0
        assert record.duration_ms == 0.0
        assert record.metadata == {}

    def test_metadata_passing(self):
        """Metadata should be stored correctly."""
        record = InteractionRecord(
            caller="orchestrator",
            callee="vision_agent",
            interaction_type="agent_call",
            metadata={"motion_type": "approach", "priority": 1},
        )
        assert record.metadata["motion_type"] == "approach"
        assert record.metadata["priority"] == 1


# =============================================================================
# InteractionTracker: Recording
# =============================================================================


class TestInteractionTrackerRecording:
    """Test interaction recording."""

    def test_record_single_interaction(self):
        """Single interaction should be recorded."""
        tracker = InteractionTracker()
        record = tracker.record_interaction(
            "orchestrator", "motion_agent", "agent_call"
        )
        assert isinstance(record, InteractionRecord)
        assert tracker.get_total_interactions() == 1

    def test_record_multiple_interactions(self):
        """Multiple interactions should all be recorded."""
        tracker = InteractionTracker()
        for i in range(10):
            tracker.record_interaction(
                f"agent_{i % 3}", f"agent_{(i + 1) % 3}", "agent_call"
            )
        assert tracker.get_total_interactions() == 10

    def test_record_with_context_size(self):
        """Context size should be recorded."""
        tracker = InteractionTracker()
        tracker.record_interaction(
            "orchestrator", "motion_agent", "agent_call",
            context_size=25,
        )
        stats = tracker.get_context_size_stats()
        assert stats["avg"] == 25.0
        assert stats["min"] == 25
        assert stats["max"] == 25

    def test_record_with_duration(self):
        """Duration should be recorded."""
        tracker = InteractionTracker()
        tracker.record_interaction(
            "orchestrator", "motion_agent", "agent_call",
            duration_ms=150.0,
        )
        # Duration is stored in the record
        assert tracker._interactions[0].duration_ms == 150.0


# =============================================================================
# InteractionTracker: Statistics
# =============================================================================


class TestInteractionTrackerStatistics:
    """Test statistics computation."""

    def test_empty_statistics(self):
        """Empty tracker should return zero statistics."""
        tracker = InteractionTracker()
        stats = tracker.get_statistics()

        assert stats["total_interactions"] == 0
        assert stats["rounds_per_task"] == 0.0
        assert stats["redundant_calls"] == 0

    def test_rounds_by_type(self):
        """Rounds should be grouped by interaction type."""
        tracker = InteractionTracker()
        tracker.record_interaction("A", "B", "agent_call")
        tracker.record_interaction("A", "B", "agent_call")
        tracker.record_interaction("A", "C", "tool_call")
        tracker.record_interaction("B", "D", "state_query")

        rounds = tracker.get_rounds_by_type()
        assert rounds["agent_call"] == 2
        assert rounds["tool_call"] == 1
        assert rounds["state_query"] == 1

    def test_rounds_per_task(self):
        """Average rounds per task should be computed correctly."""
        tracker = InteractionTracker()
        # Task 1: 3 interactions
        tracker.record_interaction("A", "B", "agent_call", task_id="task_1")
        tracker.record_interaction("A", "C", "agent_call", task_id="task_1")
        tracker.record_interaction("B", "D", "tool_call", task_id="task_1")
        # Task 2: 2 interactions
        tracker.record_interaction("A", "B", "agent_call", task_id="task_2")
        tracker.record_interaction("A", "C", "agent_call", task_id="task_2")

        assert tracker.get_rounds_per_task() == 2.5  # (3+2)/2


# =============================================================================
# InteractionTracker: Agent Call Graph
# =============================================================================


class TestInteractionTrackerAgentCalls:
    """Test agent call counting and dependency graph."""

    def test_agent_call_counts(self):
        """Agent call counts should be tracked correctly."""
        tracker = InteractionTracker()
        tracker.record_interaction("orchestrator", "motion", "agent_call")
        tracker.record_interaction("orchestrator", "motion", "agent_call")
        tracker.record_interaction("orchestrator", "vision", "agent_call")
        tracker.record_interaction("motion", "safety", "agent_call")

        counts = tracker.get_agent_call_counts()
        assert counts["orchestrator"]["motion"] == 2
        assert counts["orchestrator"]["vision"] == 1
        assert counts["motion"]["safety"] == 1

    def test_agent_dependency_graph(self):
        """Dependency graph should show agent relationships."""
        tracker = InteractionTracker()
        tracker.record_interaction("orchestrator", "motion", "agent_call")
        tracker.record_interaction("orchestrator", "vision", "agent_call")
        tracker.record_interaction("motion", "safety", "agent_call")

        graph = tracker.get_agent_dependency_graph()
        assert "orchestrator" in graph
        assert "motion" in graph["orchestrator"]
        assert "vision" in graph["orchestrator"]
        assert "safety" in graph["motion"]

    def test_empty_dependency_graph(self):
        """Empty tracker should have empty graph."""
        tracker = InteractionTracker()
        graph = tracker.get_agent_dependency_graph()
        assert graph == {}


# =============================================================================
# InteractionTracker: Redundancy Detection
# =============================================================================


class TestInteractionTrackerRedundancy:
    """Test redundancy detection."""

    def test_no_redundancy_below_threshold(self):
        """Calls below threshold should not be flagged."""
        tracker = InteractionTracker(redundancy_threshold=3)
        tracker.record_interaction("A", "B", "agent_call")
        tracker.record_interaction("A", "B", "agent_call")

        redundant = tracker.get_redundant_calls()
        assert len(redundant) == 0

    def test_redundancy_above_threshold(self):
        """Calls above threshold should be flagged."""
        tracker = InteractionTracker(redundancy_threshold=3)
        for _ in range(4):
            tracker.record_interaction("A", "B", "agent_call")

        redundant = tracker.get_redundant_calls()
        assert len(redundant) >= 1
        assert redundant[0]["count"] == 4

    def test_redundancy_different_metadata(self):
        """Different metadata creates different signatures."""
        tracker = InteractionTracker(redundancy_threshold=2)
        tracker.record_interaction("A", "B", "agent_call", metadata={"type": "approach"})
        tracker.record_interaction("A", "B", "agent_call", metadata={"type": "approach"})
        tracker.record_interaction("A", "B", "agent_call", metadata={"type": "grasp"})

        # Only the "approach" calls should be flagged (2 calls)
        redundant = tracker.get_redundant_calls()
        # With threshold 2, the approach calls (2x) should be flagged
        for r in redundant:
            assert r["count"] >= 2

    def test_redundancy_sorted_by_count(self):
        """Redundant calls should be sorted by count descending."""
        tracker = InteractionTracker(redundancy_threshold=2)
        # 5 calls to same signature
        for _ in range(5):
            tracker.record_interaction("A", "B", "agent_call")
        # 3 calls to different signature
        for _ in range(3):
            tracker.record_interaction("A", "C", "tool_call")

        redundant = tracker.get_redundant_calls()
        assert redundant[0]["count"] >= redundant[-1]["count"]


# =============================================================================
# InteractionTracker: Context Size
# =============================================================================


class TestInteractionTrackerContextSize:
    """Test context size statistics."""

    def test_context_size_with_no_data(self):
        """No context size data should return zeros."""
        tracker = InteractionTracker()
        stats = tracker.get_context_size_stats()
        assert stats["avg"] == 0
        assert stats["min"] == 0
        assert stats["max"] == 0

    def test_context_size_ignores_zero(self):
        """Zero context sizes should be ignored."""
        tracker = InteractionTracker()
        tracker.record_interaction("A", "B", "agent_call", context_size=0)
        tracker.record_interaction("A", "B", "agent_call", context_size=10)

        stats = tracker.get_context_size_stats()
        assert stats["avg"] == 10.0
        assert stats["min"] == 10
        assert stats["max"] == 10

    def test_context_size_statistics(self):
        """Context size statistics should be correct."""
        tracker = InteractionTracker()
        tracker.record_interaction("A", "B", "agent_call", context_size=5)
        tracker.record_interaction("A", "B", "agent_call", context_size=15)

        stats = tracker.get_context_size_stats()
        assert stats["avg"] == 10.0
        assert stats["min"] == 5
        assert stats["max"] == 15


# =============================================================================
# InteractionTracker: Suggestions
# =============================================================================


class TestInteractionTrackerSuggestions:
    """Test compression suggestions."""

    def test_empty_suggestions(self):
        """No data should produce no suggestions."""
        tracker = InteractionTracker()
        suggestions = tracker.get_compression_suggestions()
        assert len(suggestions) == 0

    def test_redundancy_suggestion(self):
        """Redundant calls should trigger a suggestion."""
        tracker = InteractionTracker(redundancy_threshold=2)
        for _ in range(3):
            tracker.record_interaction("A", "B", "agent_call")

        suggestions = tracker.get_compression_suggestions()
        assert any("redundant" in s.lower() for s in suggestions)

    def test_high_context_suggestion(self):
        """High average context size should trigger a suggestion."""
        tracker = InteractionTracker()
        for _ in range(5):
            tracker.record_interaction("A", "B", "agent_call", context_size=30)

        suggestions = tracker.get_compression_suggestions()
        assert any("context size" in s.lower() for s in suggestions)

    def test_high_call_count_suggestion(self):
        """High call count between agents should trigger a suggestion."""
        tracker = InteractionTracker()
        for _ in range(15):
            tracker.record_interaction("A", "B", "agent_call")

        suggestions = tracker.get_compression_suggestions()
        assert any("batching" in s.lower() for s in suggestions)


# =============================================================================
# InteractionTracker: Trace Export
# =============================================================================


class TestInteractionTrackerExport:
    """Test trace export functionality."""

    def test_export_all_traces(self):
        """Export all traces should return all interactions."""
        tracker = InteractionTracker()
        tracker.record_interaction("A", "B", "agent_call")
        tracker.record_interaction("A", "C", "tool_call")

        traces = tracker.export_traces()
        assert len(traces) == 2
        assert traces[0]["caller"] == "A"
        assert traces[0]["callee"] == "B"

    def test_export_by_task_id(self):
        """Export by task_id should filter correctly."""
        tracker = InteractionTracker()
        tracker.record_interaction("A", "B", "agent_call", task_id="task_1")
        tracker.record_interaction("A", "C", "tool_call", task_id="task_2")

        traces = tracker.export_traces(task_id="task_1")
        assert len(traces) == 1
        assert traces[0]["callee"] == "B"

    def test_export_nonexistent_task(self):
        """Export for nonexistent task should return empty list."""
        tracker = InteractionTracker()
        traces = tracker.export_traces(task_id="nonexistent")
        assert traces == []


# =============================================================================
# InteractionTracker: Reset
# =============================================================================


class TestInteractionTrackerReset:
    """Test reset functionality."""

    def test_reset_clears_all(self):
        """Reset should clear all data."""
        tracker = InteractionTracker()
        tracker.record_interaction("A", "B", "agent_call")
        tracker.record_interaction("A", "C", "tool_call", task_id="task_1")

        tracker.reset()
        assert tracker.get_total_interactions() == 0
        assert tracker.get_rounds_per_task() == 0.0
        assert tracker.get_agent_dependency_graph() == {}
        assert len(tracker._interactions) == 0
        assert len(tracker._task_interactions) == 0

    def test_reset_allows_new_records(self):
        """After reset, new records should work correctly."""
        tracker = InteractionTracker()
        tracker.record_interaction("A", "B", "agent_call")
        tracker.reset()
        tracker.record_interaction("C", "D", "agent_call")

        assert tracker.get_total_interactions() == 1
        assert tracker.get_agent_dependency_graph() == {"C": ["D"]}