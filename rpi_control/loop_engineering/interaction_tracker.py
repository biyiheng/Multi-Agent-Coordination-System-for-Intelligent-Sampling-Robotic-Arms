"""
Interaction and tool call tracker for the multi-agent system.

Tracks all agent-to-agent interactions, tool calls, and state queries
to identify redundant steps, measure interaction efficiency, and
generate agent dependency graphs.

Usage:
    tracker = InteractionTracker()
    tracker.record_interaction("orchestrator", "motion_agent",
                               "agent_call", {"motion_type": "approach"})
    print(tracker.get_statistics())
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class InteractionRecord:
    """A single interaction between agents or with tools.

    Attributes:
        caller: Name of the calling agent.
        callee: Name of the called agent/tool.
        interaction_type: Type of interaction ('agent_call', 'tool_call', 'state_query').
        timestamp: When the interaction occurred.
        context_size: Approximate context size (number of state keys).
        duration_ms: Duration of the interaction.
        metadata: Optional contextual data.
    """
    caller: str
    callee: str
    interaction_type: str
    timestamp: float = field(default_factory=time.time)
    context_size: int = 0
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class InteractionTracker:
    """Tracks all interactions between agents and with tools.

    Provides statistics on interaction rounds, tool call counts,
    redundancy detection, and dependency graph generation.
    """

    def __init__(self, redundancy_threshold: int = 3):
        """Initialize the tracker.

        Args:
            redundancy_threshold: Number of identical calls before
                                  flagging as redundant.
        """
        self._interactions: List[InteractionRecord] = []
        self._redundancy_threshold = redundancy_threshold
        self._call_signatures: Dict[str, int] = defaultdict(int)
        self._agent_calls: Dict[str, Dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self._task_interactions: Dict[str, List[InteractionRecord]] = defaultdict(list)

    def record_interaction(
        self,
        caller: str,
        callee: str,
        interaction_type: str = "agent_call",
        context_size: int = 0,
        duration_ms: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None,
    ) -> InteractionRecord:
        """Record a single interaction.

        Args:
            caller: Name of the calling agent.
            callee: Name of the called agent/tool.
            interaction_type: Type of interaction.
            context_size: Approximate number of state keys passed.
            duration_ms: Duration of the interaction in ms.
            metadata: Optional contextual data.
            task_id: Optional task ID for per-task grouping.

        Returns:
            The recorded InteractionRecord.
        """
        record = InteractionRecord(
            caller=caller,
            callee=callee,
            interaction_type=interaction_type,
            timestamp=time.time(),
            context_size=context_size,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )

        self._interactions.append(record)

        # Update call signature for redundancy detection
        sig = f"{caller}->{callee}:{interaction_type}"
        if metadata:
            # Include key metadata values in the signature
            sorted_meta = tuple(sorted(
                (k, str(v)) for k, v in metadata.items()
                if isinstance(v, (str, int, float, bool))
            ))
            sig += f":{sorted_meta}"
        self._call_signatures[sig] += 1

        # Update dependency graph
        self._agent_calls[caller][callee] += 1

        # Per-task grouping
        if task_id:
            self._task_interactions[task_id].append(record)

        return record

    def get_total_interactions(self) -> int:
        """Get total number of interactions recorded.

        Returns:
            Total interaction count.
        """
        return len(self._interactions)

    def get_rounds_by_type(self) -> Dict[str, int]:
        """Get interaction count by type.

        Returns:
            Dict mapping interaction_type to count.
        """
        counts: Dict[str, int] = defaultdict(int)
        for r in self._interactions:
            counts[r.interaction_type] += 1
        return dict(counts)

    def get_agent_call_counts(self) -> Dict[str, Dict[str, int]]:
        """Get the agent-to-agent call count matrix.

        Returns:
            Nested dict: caller -> {callee -> count}.
        """
        return {
            caller: dict(callees)
            for caller, callees in self._agent_calls.items()
        }

    def get_agent_dependency_graph(self) -> Dict[str, List[str]]:
        """Generate a simplified dependency graph.

        Returns:
            Dict mapping agent name to list of agents it depends on.
        """
        graph: Dict[str, List[str]] = {}
        for caller, callees in self._agent_calls.items():
            graph[caller] = list(callees.keys())
        return graph

    def get_redundant_calls(self) -> List[Dict[str, Any]]:
        """Identify redundant calls (same signature called multiple times).

        Returns:
            List of redundant call info dicts.
        """
        redundant = []
        for sig, count in self._call_signatures.items():
            if count >= self._redundancy_threshold:
                parts = sig.split(":")
                redundant.append({
                    "signature": sig,
                    "count": count,
                    "caller": parts[0].split("->")[0] if "->" in parts[0] else parts[0],
                    "callee": parts[0].split("->")[1] if "->" in parts[0] else "",
                    "type": parts[1] if len(parts) > 1 else "unknown",
                })
        redundant.sort(key=lambda x: x["count"], reverse=True)
        return redundant

    def get_rounds_per_task(self) -> float:
        """Calculate average interactions per task.

        Returns:
            Average interaction count per task.
        """
        if not self._task_interactions:
            return 0.0
        total = sum(len(v) for v in self._task_interactions.values())
        return total / len(self._task_interactions)

    def get_context_size_stats(self) -> Dict[str, float]:
        """Get statistics about context sizes passed between agents.

        Returns:
            Dict with avg, min, max context sizes.
        """
        sizes = [r.context_size for r in self._interactions if r.context_size > 0]
        if not sizes:
            return {"avg": 0, "min": 0, "max": 0}
        return {
            "avg": round(sum(sizes) / len(sizes), 1),
            "min": min(sizes),
            "max": max(sizes),
        }

    def get_compression_suggestions(self) -> List[str]:
        """Generate suggestions for reducing interaction overhead.

        Returns:
            List of suggestion strings.
        """
        suggestions = []

        # Check for redundant calls
        redundant = self.get_redundant_calls()
        if redundant:
            suggestions.append(
                f"Found {len(redundant)} redundant call patterns. "
                f"Top: {redundant[0]['signature']} ({redundant[0]['count']}x) - "
                "consider caching results."
            )

        # Check for high context sizes
        size_stats = self.get_context_size_stats()
        if size_stats["avg"] > 20:
            suggestions.append(
                f"Average context size is {size_stats['avg']:.0f} keys. "
                "Consider passing only necessary state keys."
            )

        # Check for many agent_call types
        call_counts = self.get_agent_call_counts()
        for caller, callees in call_counts.items():
            for callee, count in callees.items():
                if count > 10:
                    suggestions.append(
                        f"Agent '{caller}' called '{callee}' {count} times. "
                        "Consider batching requests."
                    )

        return suggestions

    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive interaction statistics.

        Returns:
            Dict with all interaction metrics.
        """
        return {
            "total_interactions": self.get_total_interactions(),
            "rounds_by_type": self.get_rounds_by_type(),
            "rounds_per_task": round(self.get_rounds_per_task(), 2),
            "context_size_stats": self.get_context_size_stats(),
            "redundant_calls": len(self.get_redundant_calls()),
            "top_redundant": self.get_redundant_calls()[:5],
            "dependency_graph": self.get_agent_dependency_graph(),
            "suggestions": self.get_compression_suggestions(),
        }

    def export_traces(self, task_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Export interaction traces as a list of dicts.

        Args:
            task_id: Optional task ID to filter by.

        Returns:
            List of interaction dicts.
        """
        records = (
            self._task_interactions.get(task_id, [])
            if task_id
            else self._interactions
        )
        return [
            {
                "caller": r.caller,
                "callee": r.callee,
                "interaction_type": r.interaction_type,
                "timestamp": r.timestamp,
                "context_size": r.context_size,
                "duration_ms": r.duration_ms,
                "metadata": r.metadata,
            }
            for r in records
        ]

    def reset(self) -> None:
        """Reset all recorded data."""
        self._interactions.clear()
        self._call_signatures.clear()
        self._agent_calls.clear()
        self._task_interactions.clear()