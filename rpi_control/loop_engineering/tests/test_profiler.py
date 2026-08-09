"""
Unit tests for the AgentProfiler and EndToEndProfiler.

Tests cover:
1. Span lifecycle (start, end, error handling)
2. Statistics computation (p50, p95, p99, avg, min, max)
3. Bottleneck detection
4. Slow operation flagging
5. Trace export
6. Reset functionality
7. End-to-end task profiling
8. State transition tracking
9. State distribution analysis
"""

import time
import pytest
from loop_engineering.profiler import (
    AgentProfiler,
    EndToEndProfiler,
    LatencyRecord,
)


# =============================================================================
# AgentProfiler Tests
# =============================================================================


class TestAgentProfilerSpanLifecycle:
    """Test span start/end lifecycle."""

    def test_start_end_span_returns_record(self):
        """end_span should return a valid LatencyRecord."""
        profiler = AgentProfiler("test_agent")
        profiler.start_span("test_op")
        time.sleep(0.01)  # Small delay for measurable duration
        record = profiler.end_span("test_op")

        assert isinstance(record, LatencyRecord)
        assert record.agent_name == "test_agent"
        assert record.operation == "test_op"
        assert record.duration_ms > 0
        assert record.end_time > record.start_time

    def test_end_span_without_start_raises(self):
        """Ending a span that was never started should raise ValueError."""
        profiler = AgentProfiler("test_agent")
        with pytest.raises(ValueError, match="No active span"):
            profiler.end_span("nonexistent")

    def test_end_span_twice_raises(self):
        """Ending the same span twice should raise ValueError."""
        profiler = AgentProfiler("test_agent")
        profiler.start_span("test_op")
        profiler.end_span("test_op")
        with pytest.raises(ValueError, match="No active span"):
            profiler.end_span("test_op")

    def test_multiple_operations(self):
        """Multiple operations should be tracked independently."""
        profiler = AgentProfiler("test_agent")
        profiler.start_span("op_a")
        time.sleep(0.01)
        profiler.end_span("op_a")

        profiler.start_span("op_b")
        time.sleep(0.02)
        profiler.end_span("op_b")

        stats = profiler.get_statistics()
        assert stats["total_calls"] == 2
        assert "op_a" in stats["per_operation"]
        assert "op_b" in stats["per_operation"]

    def test_metadata_attachment(self):
        """Metadata should be attached to the LatencyRecord."""
        profiler = AgentProfiler("test_agent")
        profiler.start_span("test_op")
        record = profiler.end_span("test_op", {"attempt": 1, "success": True})

        assert record.metadata["attempt"] == 1
        assert record.metadata["success"] is True


class TestAgentProfilerStatistics:
    """Test statistics computation."""

    def test_empty_statistics(self):
        """Empty profiler should return zero statistics."""
        profiler = AgentProfiler("test_agent")
        stats = profiler.get_statistics()

        assert stats["total_calls"] == 0
        assert stats["total_duration_ms"] == 0
        assert stats["avg_ms"] == 0
        assert stats["p50_ms"] == 0
        assert stats["p95_ms"] == 0
        assert stats["p99_ms"] == 0
        assert stats["min_ms"] == 0
        assert stats["max_ms"] == 0

    def test_single_call_statistics(self):
        """Single call should have all percentiles equal to its duration."""
        profiler = AgentProfiler("test_agent")
        profiler.start_span("test_op")
        time.sleep(0.05)
        profiler.end_span("test_op")

        stats = profiler.get_statistics()
        assert stats["total_calls"] == 1
        assert stats["avg_ms"] > 0
        # All percentiles should be the same for single data point
        assert stats["p50_ms"] == stats["p95_ms"] == stats["p99_ms"]

    def test_multiple_calls_percentiles(self):
        """Multiple calls should compute correct percentiles."""
        profiler = AgentProfiler("test_agent")
        # Record 10 spans with increasing durations
        for i in range(1, 11):
            profiler.start_span(f"op_{i}")
            time.sleep(0.001 * i)
            profiler.end_span(f"op_{i}")

        stats = profiler.get_statistics()
        assert stats["total_calls"] == 10
        assert stats["min_ms"] < stats["max_ms"]
        assert stats["p50_ms"] > stats["min_ms"]
        assert stats["p95_ms"] >= stats["p50_ms"]

    def test_per_operation_statistics(self):
        """Per-operation statistics should be computed correctly."""
        profiler = AgentProfiler("test_agent")

        # Operation A: 3 calls
        for _ in range(3):
            profiler.start_span("op_a")
            time.sleep(0.01)
            profiler.end_span("op_a")

        # Operation B: 2 calls
        for _ in range(2):
            profiler.start_span("op_b")
            time.sleep(0.02)
            profiler.end_span("op_b")

        stats = profiler.get_statistics()
        assert stats["per_operation"]["op_a"]["count"] == 3
        assert stats["per_operation"]["op_b"]["count"] == 2

    def test_total_duration_accumulation(self):
        """Total duration should accumulate across all calls."""
        profiler = AgentProfiler("test_agent")
        profiler.start_span("op")
        time.sleep(0.03)
        profiler.end_span("op")

        profiler.start_span("op")
        time.sleep(0.03)
        profiler.end_span("op")

        stats = profiler.get_statistics()
        assert stats["total_duration_ms"] > 50  # Should be at least ~60ms


class TestAgentProfilerBottleneck:
    """Test bottleneck detection."""

    def test_bottleneck_report_ordering(self):
        """Bottleneck report should be sorted by avg duration descending."""
        profiler = AgentProfiler("test_agent")

        # Fast op
        profiler.start_span("fast")
        time.sleep(0.005)
        profiler.end_span("fast")

        # Slow op
        profiler.start_span("slow")
        time.sleep(0.05)
        profiler.end_span("slow")

        # Medium op
        profiler.start_span("medium")
        time.sleep(0.02)
        profiler.end_span("medium")

        bottlenecks = profiler.get_bottleneck_report(top_n=3)
        assert len(bottlenecks) == 3
        # Should be sorted: slow > medium > fast
        assert bottlenecks[0]["operation"] == "slow"
        assert bottlenecks[2]["operation"] == "fast"

    def test_bottleneck_top_n_limit(self):
        """Bottleneck report should respect top_n limit."""
        profiler = AgentProfiler("test_agent")
        for i in range(10):
            profiler.start_span(f"op_{i}")
            time.sleep(0.001)
            profiler.end_span(f"op_{i}")

        bottlenecks = profiler.get_bottleneck_report(top_n=3)
        assert len(bottlenecks) == 3

    def test_bottleneck_slow_count(self):
        """Operations exceeding slow_threshold should be counted."""
        profiler = AgentProfiler("test_agent", slow_threshold_ms=10)

        # Fast calls (below threshold)
        for _ in range(3):
            profiler.start_span("fast")
            time.sleep(0.001)
            profiler.end_span("fast")

        # Slow calls (above threshold)
        for _ in range(2):
            profiler.start_span("slow")
            time.sleep(0.02)
            profiler.end_span("slow")

        bottlenecks = profiler.get_bottleneck_report()
        slow_bn = [b for b in bottlenecks if b["operation"] == "slow"][0]
        assert slow_bn["slow_count"] == 2
        fast_bn = [b for b in bottlenecks if b["operation"] == "fast"][0]
        assert fast_bn["slow_count"] == 0


class TestAgentProfilerSlowOperations:
    """Test slow operation detection."""

    def test_slow_operations_detection(self):
        """Operations exceeding threshold should be in slow list."""
        profiler = AgentProfiler("test_agent", slow_threshold_ms=10)

        profiler.start_span("fast")
        time.sleep(0.001)
        profiler.end_span("fast")

        profiler.start_span("slow")
        time.sleep(0.02)
        profiler.end_span("slow")

        slow_ops = profiler.get_slow_operations()
        assert len(slow_ops) == 1
        assert slow_ops[0]["operation"] == "slow"

    def test_slow_operations_sorted(self):
        """Slow operations should be sorted by duration descending."""
        profiler = AgentProfiler("test_agent", slow_threshold_ms=5)

        profiler.start_span("op1")
        time.sleep(0.01)
        profiler.end_span("op1")

        profiler.start_span("op2")
        time.sleep(0.03)
        profiler.end_span("op2")

        slow_ops = profiler.get_slow_operations()
        assert slow_ops[0]["duration_ms"] >= slow_ops[-1]["duration_ms"]


class TestAgentProfilerTraceExport:
    """Test trace export functionality."""

    def test_export_trace_format(self):
        """Export should produce correctly formatted trace dict."""
        profiler = AgentProfiler("test_agent")
        profiler.start_span("op_a")
        time.sleep(0.01)
        profiler.end_span("op_a")

        profiler.start_span("op_b")
        time.sleep(0.02)
        profiler.end_span("op_b")

        trace = profiler.export_trace()
        assert trace["agent_name"] == "test_agent"
        assert trace["total_spans"] == 2
        assert len(trace["spans"]) == 2

        # Check span structure
        span = trace["spans"][0]
        assert "agent_name" in span
        assert "operation" in span
        assert "start_time" in span
        assert "duration_ms" in span
        assert "metadata" in span

    def test_export_trace_sorted_by_time(self):
        """Spans should be sorted by start_time."""
        profiler = AgentProfiler("test_agent")
        profiler.start_span("first")
        time.sleep(0.01)
        profiler.end_span("first")

        profiler.start_span("second")
        time.sleep(0.01)
        profiler.end_span("second")

        trace = profiler.export_trace()
        spans = trace["spans"]
        for i in range(len(spans) - 1):
            assert spans[i]["start_time"] <= spans[i + 1]["start_time"]


class TestAgentProfilerReset:
    """Test reset functionality."""

    def test_reset_clears_all_data(self):
        """Reset should clear all recorded data."""
        profiler = AgentProfiler("test_agent")
        profiler.start_span("op")
        time.sleep(0.01)
        profiler.end_span("op")

        profiler.reset()

        stats = profiler.get_statistics()
        assert stats["total_calls"] == 0
        assert stats["total_duration_ms"] == 0
        assert len(profiler._active_spans) == 0
        assert len(profiler._spans) == 0

    def test_reset_allows_new_spans(self):
        """After reset, new spans should work correctly."""
        profiler = AgentProfiler("test_agent")
        profiler.start_span("op")
        profiler.end_span("op")
        profiler.reset()

        profiler.start_span("new_op")
        time.sleep(0.01)
        profiler.end_span("new_op")

        stats = profiler.get_statistics()
        assert stats["total_calls"] == 1


class TestAgentProfilerPercentile:
    """Test percentile computation edge cases."""

    def test_percentile_empty_data(self):
        """Empty data should return 0."""
        assert AgentProfiler._percentile([], 50) == 0.0

    def test_percentile_single_value(self):
        """Single value should return that value."""
        assert AgentProfiler._percentile([10.0], 50) == 10.0
        assert AgentProfiler._percentile([10.0], 95) == 10.0

    def test_percentile_known_values(self):
        """Percentile should compute correctly for known data."""
        data = sorted([1.0, 2.0, 3.0, 4.0, 5.0])
        # Median of [1,2,3,4,5] = 3.0
        assert AgentProfiler._percentile(data, 50) == 3.0
        # P25 of [1,2,3,4,5] = 2.0
        assert AgentProfiler._percentile(data, 25) == 2.0

    def test_percentile_interpolation(self):
        """Percentile should interpolate between values."""
        data = sorted([1.0, 2.0, 3.0, 4.0])
        # P50 of [1,2,3,4]: k = 1.5, f=1, c=0.5 → 2.5
        assert AgentProfiler._percentile(data, 50) == 2.5


# =============================================================================
# EndToEndProfiler Tests
# =============================================================================


class TestEndToEndProfilerTaskLifecycle:
    """Test end-to-end task profiling."""

    def test_start_end_task_returns_duration(self):
        """End task should return the duration in ms."""
        e2e = EndToEndProfiler()
        e2e.start_task("task_001")
        time.sleep(0.02)
        duration = e2e.end_task("task_001")

        assert duration > 15  # At least 20ms
        assert duration < 100  # Not too much overhead

    def test_multiple_tasks(self):
        """Multiple tasks should be tracked independently."""
        e2e = EndToEndProfiler()

        e2e.start_task("task_a")
        time.sleep(0.01)
        e2e.end_task("task_a")

        e2e.start_task("task_b")
        time.sleep(0.02)
        e2e.end_task("task_b")

        report = e2e.get_e2e_report()
        assert report["total_tasks"] == 2

    def test_task_details_limited_to_last_10(self):
        """Task details should keep only last 10 tasks."""
        e2e = EndToEndProfiler()
        for i in range(15):
            e2e.start_task(f"task_{i}")
            e2e.end_task(f"task_{i}")

        report = e2e.get_e2e_report()
        assert len(report["task_details"]) <= 10


class TestEndToEndProfilerStateTracking:
    """Test state transition tracking."""

    def test_record_state_transition(self):
        """State transitions should be recorded correctly."""
        e2e = EndToEndProfiler()
        e2e.record_state_transition("IDLE", "PLANNING", 5.0)
        e2e.record_state_transition("PLANNING", "APPROACHING", 12.0)

        timeline = e2e.get_state_timeline()
        assert len(timeline) == 2
        assert timeline[0]["from"] == "IDLE"
        assert timeline[0]["to"] == "PLANNING"
        assert timeline[1]["from"] == "PLANNING"
        assert timeline[1]["to"] == "APPROACHING"

    def test_state_distribution(self):
        """State distribution should compute correctly."""
        e2e = EndToEndProfiler()
        # IDLE → PLANNING: 10ms
        e2e.record_state_transition("IDLE", "PLANNING", 10.0)
        # PLANNING → APPROACHING: 20ms
        e2e.record_state_transition("PLANNING", "APPROACHING", 20.0)
        # APPROACHING → DETECTING: 30ms
        e2e.record_state_transition("APPROACHING", "DETECTING", 30.0)

        dist = e2e.get_state_distribution()
        assert "IDLE" in dist
        assert dist["IDLE"]["count"] == 1
        assert dist["IDLE"]["total_ms"] == 10.0
        # Total = 60ms, IDLE = 10/60 = 16.7%
        assert 16.0 < dist["IDLE"]["pct"] < 17.0


class TestEndToEndProfilerReport:
    """Test end-to-end report generation."""

    def test_empty_report(self):
        """Empty profiler should return zeros."""
        e2e = EndToEndProfiler()
        report = e2e.get_e2e_report()

        assert report["total_tasks"] == 0
        assert report["e2e_avg_ms"] == 0
        assert report["e2e_p50_ms"] == 0

    def test_report_with_data(self):
        """Report with data should contain correct metrics."""
        e2e = EndToEndProfiler()
        e2e.start_task("task_001")
        time.sleep(0.01)
        e2e.end_task("task_001")
        e2e.record_state_transition("IDLE", "PLANNING", 5.0)

        report = e2e.get_e2e_report()
        assert report["total_tasks"] == 1
        assert report["total_state_transitions"] == 1
        assert report["e2e_avg_ms"] > 0
        assert "state_distribution" in report

    def test_report_percentiles(self):
        """Report should compute correct percentiles."""
        e2e = EndToEndProfiler()
        for i in range(5):
            e2e.start_task(f"task_{i}")
            time.sleep(0.001 * (i + 1))
            e2e.end_task(f"task_{i}")

        report = e2e.get_e2e_report()
        assert report["e2e_min_ms"] < report["e2e_max_ms"]
        assert report["e2e_p50_ms"] >= report["e2e_min_ms"]
        assert report["e2e_p95_ms"] >= report["e2e_p50_ms"]


class TestEndToEndProfilerReset:
    """Test reset functionality."""

    def test_reset_clears_all(self):
        """Reset should clear all data."""
        e2e = EndToEndProfiler()
        e2e.start_task("task_001")
        e2e.end_task("task_001")
        e2e.record_state_transition("IDLE", "PLANNING", 5.0)
        e2e.reset()

        report = e2e.get_e2e_report()
        assert report["total_tasks"] == 0
        assert report["total_state_transitions"] == 0
        assert len(e2e._task_start) == 0
        assert len(e2e._task_end) == 0