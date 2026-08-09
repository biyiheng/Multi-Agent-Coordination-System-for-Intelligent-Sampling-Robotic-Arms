"""
Agent-level and end-to-end latency profiler for the multi-agent system.

Measures execution time at the agent operation level and at the task level,
identifies performance bottlenecks, and generates latency reports.

Usage:
    profiler = AgentProfiler("motion_agent")
    profiler.start_span("execute_motion")
    # ... do work ...
    record = profiler.end_span("execute_motion")
    print(profiler.get_statistics())
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class LatencyRecord:
    """A single latency measurement span.

    Attributes:
        agent_name: Name of the agent being profiled.
        operation: Name of the operation (e.g., 'process', 'execute_motion').
        start_time: Wall-clock start time (perf_counter).
        end_time: Wall-clock end time (perf_counter).
        duration_ms: Duration in milliseconds.
        metadata: Optional contextual data.
    """
    agent_name: str
    operation: str
    start_time: float
    end_time: float = 0.0
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentProfiler:
    """Profiles a single agent's operations.

    Records spans for each operation, computes latency statistics
    (p50, p95, p99, avg, max), and identifies slow operations.

    Can be integrated into BaseAgent via pre/post hooks without
    modifying the agent's core process() logic.
    """

    def __init__(self, agent_name: str, slow_threshold_ms: float = 100.0):
        """Initialize the profiler.

        Args:
            agent_name: Name of the agent to profile.
            slow_threshold_ms: Operations exceeding this are flagged as slow.
        """
        self.agent_name = agent_name
        self.slow_threshold_ms = slow_threshold_ms
        self._spans: Dict[str, List[LatencyRecord]] = defaultdict(list)
        self._active_spans: Dict[str, float] = {}  # operation -> start_time
        self._total_calls: int = 0
        self._total_duration_ms: float = 0.0

    def start_span(self, operation: str) -> None:
        """Start timing an operation.

        Args:
            operation: Name of the operation to time.
        """
        self._active_spans[operation] = time.perf_counter()

    def end_span(self, operation: str, metadata: Optional[Dict[str, Any]] = None) -> LatencyRecord:
        """End timing an operation and record the result.

        Args:
            operation: Name of the operation being timed.
            metadata: Optional contextual data to attach.

        Returns:
            The recorded LatencyRecord.

        Raises:
            ValueError: If the operation was not started.
        """
        if operation not in self._active_spans:
            raise ValueError(f"No active span for operation '{operation}'")

        start = self._active_spans.pop(operation)
        end = time.perf_counter()
        duration_ms = (end - start) * 1000.0

        record = LatencyRecord(
            agent_name=self.agent_name,
            operation=operation,
            start_time=start,
            end_time=end,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )

        self._spans[operation].append(record)
        self._total_calls += 1
        self._total_duration_ms += duration_ms

        return record

    def get_statistics(self) -> Dict[str, Any]:
        """Compute latency statistics across all operations.

        Returns:
            Dict with p50, p95, p99, avg, max, min, total_calls, total_duration_ms.
        """
        all_durations = []
        per_op_stats = {}

        for op, records in self._spans.items():
            durations = sorted(r.duration_ms for r in records)
            if durations:
                per_op_stats[op] = {
                    "count": len(durations),
                    "avg_ms": round(sum(durations) / len(durations), 2),
                    "min_ms": round(durations[0], 2),
                    "max_ms": round(durations[-1], 2),
                    "p50_ms": round(self._percentile(durations, 50), 2),
                    "p95_ms": round(self._percentile(durations, 95), 2),
                    "p99_ms": round(self._percentile(durations, 99), 2),
                    "total_ms": round(sum(durations), 2),
                }
            all_durations.extend(durations)

        sorted_all = sorted(all_durations)

        return {
            "agent_name": self.agent_name,
            "total_calls": self._total_calls,
            "total_duration_ms": round(self._total_duration_ms, 2),
            "avg_ms": round(sum(sorted_all) / len(sorted_all), 2) if sorted_all else 0,
            "p50_ms": round(self._percentile(sorted_all, 50), 2),
            "p95_ms": round(self._percentile(sorted_all, 95), 2),
            "p99_ms": round(self._percentile(sorted_all, 99), 2),
            "min_ms": round(sorted_all[0], 2) if sorted_all else 0,
            "max_ms": round(sorted_all[-1], 2) if sorted_all else 0,
            "per_operation": per_op_stats,
        }

    def get_bottleneck_report(self, top_n: int = 5) -> List[Dict[str, Any]]:
        """Identify the slowest operations.

        Args:
            top_n: Number of bottlenecks to report.

        Returns:
            List of bottleneck dicts sorted by avg duration descending.
        """
        bottlenecks = []
        for op, records in self._spans.items():
            durations = [r.duration_ms for r in records]
            avg_dur = sum(durations) / len(durations)
            slow_count = sum(1 for d in durations if d > self.slow_threshold_ms)
            bottlenecks.append({
                "operation": op,
                "count": len(durations),
                "avg_ms": round(avg_dur, 2),
                "max_ms": round(max(durations), 2),
                "slow_count": slow_count,
                "slow_ratio": round(slow_count / len(durations), 3) if durations else 0,
                "total_ms": round(sum(durations), 2),
            })

        bottlenecks.sort(key=lambda x: x["avg_ms"], reverse=True)
        return bottlenecks[:top_n]

    def get_slow_operations(self) -> List[Dict[str, Any]]:
        """Get operations that exceeded the slow threshold.

        Returns:
            List of slow operation records.
        """
        slow_ops = []
        for op, records in self._spans.items():
            for r in records:
                if r.duration_ms > self.slow_threshold_ms:
                    slow_ops.append({
                        "operation": op,
                        "duration_ms": round(r.duration_ms, 2),
                        "metadata": r.metadata,
                    })
        slow_ops.sort(key=lambda x: x["duration_ms"], reverse=True)
        return slow_ops

    def export_trace(self) -> Dict[str, Any]:
        """Export all recorded spans as a trace dict.

        Returns:
            Dict with agent_name and list of all span records.
        """
        spans = []
        for op, records in self._spans.items():
            for r in records:
                spans.append({
                    "agent_name": r.agent_name,
                    "operation": r.operation,
                    "start_time": r.start_time,
                    "duration_ms": round(r.duration_ms, 2),
                    "metadata": r.metadata,
                })
        spans.sort(key=lambda x: x["start_time"])
        return {
            "agent_name": self.agent_name,
            "total_spans": len(spans),
            "spans": spans,
        }

    def reset(self) -> None:
        """Reset all recorded data."""
        self._spans.clear()
        self._active_spans.clear()
        self._total_calls = 0
        self._total_duration_ms = 0.0

    @staticmethod
    def _percentile(sorted_data: List[float], p: float) -> float:
        """Compute the p-th percentile from sorted data.

        Args:
            sorted_data: Sorted list of values.
            p: Percentile (0-100).

        Returns:
            The p-th percentile value.
        """
        if not sorted_data:
            return 0.0
        k = (len(sorted_data) - 1) * (p / 100.0)
        f = int(k)
        c = k - f
        if f + 1 < len(sorted_data):
            return sorted_data[f] * (1 - c) + sorted_data[f + 1] * c
        return sorted_data[f]


class EndToEndProfiler:
    """Profiles end-to-end task execution latency.

    Tracks the entire task lifecycle from start to end, including
    per-state transition timing for the orchestrator state machine.
    """

    def __init__(self):
        """Initialize the end-to-end profiler."""
        self._task_start: Dict[str, float] = {}
        self._task_end: Dict[str, float] = {}
        self._state_transitions: List[Dict[str, Any]] = []
        self._completed_tasks: List[Dict[str, Any]] = []

    def start_task(self, task_id: str) -> None:
        """Mark the start of a task.

        Args:
            task_id: Unique task identifier.
        """
        self._task_start[task_id] = time.perf_counter()

    def end_task(self, task_id: str) -> float:
        """Mark the end of a task and return duration in ms.

        Args:
            task_id: Unique task identifier.

        Returns:
            Task duration in milliseconds.
        """
        self._task_end[task_id] = time.perf_counter()
        duration_ms = (self._task_end[task_id] - self._task_start[task_id]) * 1000.0
        self._completed_tasks.append({
            "task_id": task_id,
            "duration_ms": round(duration_ms, 2),
            "state_transitions": len(self._state_transitions),
        })
        return duration_ms

    def record_state_transition(
        self,
        from_state: str,
        to_state: str,
        duration_ms: float,
    ) -> None:
        """Record a state machine transition.

        Args:
            from_state: Previous state name.
            to_state: New state name.
            duration_ms: Time spent in the previous state.
        """
        self._state_transitions.append({
            "from": from_state,
            "to": to_state,
            "duration_ms": round(duration_ms, 2),
            "timestamp": time.time(),
        })

    def get_state_timeline(self) -> List[Dict[str, Any]]:
        """Get the full state transition timeline.

        Returns:
            List of state transition records.
        """
        return self._state_transitions

    def get_state_distribution(self) -> Dict[str, Dict[str, float]]:
        """Get time distribution across states.

        Returns:
            Dict mapping state name to count, total_ms, avg_ms, pct.
        """
        dist: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"count": 0, "total_ms": 0.0}
        )

        for t in self._state_transitions:
            state = t["from"]
            dist[state]["count"] += 1
            dist[state]["total_ms"] += t["duration_ms"]

        total_ms = sum(d["total_ms"] for d in dist.values())

        for state, d in dist.items():
            d["avg_ms"] = round(d["total_ms"] / d["count"], 2) if d["count"] else 0
            d["pct"] = round(d["total_ms"] / total_ms * 100, 1) if total_ms else 0

        return dict(dist)

    def get_e2e_report(self) -> Dict[str, Any]:
        """Generate an end-to-end latency report.

        Returns:
            Dict with task metrics and state distribution.
        """
        task_durations = [t["duration_ms"] for t in self._completed_tasks]
        sorted_durations = sorted(task_durations)

        return {
            "total_tasks": len(self._completed_tasks),
            "total_state_transitions": len(self._state_transitions),
            "e2e_avg_ms": round(sum(sorted_durations) / len(sorted_durations), 2) if sorted_durations else 0,
            "e2e_p50_ms": round(AgentProfiler._percentile(sorted_durations, 50), 2),
            "e2e_p95_ms": round(AgentProfiler._percentile(sorted_durations, 95), 2),
            "e2e_p99_ms": round(AgentProfiler._percentile(sorted_durations, 99), 2),
            "e2e_min_ms": round(sorted_durations[0], 2) if sorted_durations else 0,
            "e2e_max_ms": round(sorted_durations[-1], 2) if sorted_durations else 0,
            "state_distribution": self.get_state_distribution(),
            "task_details": self._completed_tasks[-10:],  # Last 10 tasks
        }

    def reset(self) -> None:
        """Reset all recorded data."""
        self._task_start.clear()
        self._task_end.clear()
        self._state_transitions.clear()
        self._completed_tasks.clear()