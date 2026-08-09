"""
Context manager for the multi-agent system.

Provides state persistence, history compression, context decay detection,
and state snapshot/restore capabilities. Helps maintain context continuity
across agent interactions and prevents "context rot" where critical
information gets lost in the middle of long conversation chains.

Key features:
1. State persistence: Save/load system state to disk
2. History compression: Summarize old entries to reduce context size
3. Decay detection: Identify when critical information is being lost
4. Snapshot/restore: Checkpoint system state for recovery
5. Context health metrics: Track context quality over time

Usage:
    ctx_mgr = ContextManager()
    ctx_mgr.update_state({"task_id": "001", "current_pose": {...}})
    ctx_mgr.snapshot("before_approach")
    ctx_mgr.check_decay(["task_id", "current_pose"])
    stats = ctx_mgr.get_health_stats()
"""

import hashlib
import json
import time
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class StateEntry:
    """A single state entry with metadata.

    Attributes:
        key: State key (e.g., 'task_id', 'current_pose').
        value: State value (any JSON-serializable type).
        timestamp: When this entry was created/updated.
        access_count: How many times this key has been accessed.
        importance: Importance score (higher = more critical).
    """
    key: str
    value: Any
    timestamp: float = field(default_factory=time.time)
    access_count: int = 0
    importance: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for persistence."""
        return {
            "key": self.key,
            "value": self.value,
            "timestamp": self.timestamp,
            "access_count": self.access_count,
            "importance": self.importance,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateEntry":
        """Deserialize from dict."""
        return cls(
            key=data["key"],
            value=data["value"],
            timestamp=data.get("timestamp", time.time()),
            access_count=data.get("access_count", 0),
            importance=data.get("importance", 0.5),
        )


@dataclass
class ContextSnapshot:
    """A point-in-time snapshot of the system state.

    Attributes:
        snapshot_id: Unique snapshot identifier.
        timestamp: When the snapshot was taken.
        label: Human-readable label.
        state: Frozen copy of state at snapshot time.
        hash: Content hash for integrity verification.
    """
    snapshot_id: str
    timestamp: float
    label: str
    state: Dict[str, Any] = field(default_factory=dict)
    hash: str = ""

    def __post_init__(self):
        if not self.hash and self.state:
            self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute a hash of the state for integrity verification."""
        state_str = json.dumps(self.state, sort_keys=True, default=str)
        return hashlib.sha256(state_str.encode()).hexdigest()[:16]


# =============================================================================
# Context Manager
# =============================================================================


class ContextManager:
    """Manages context state, persistence, compression, and decay detection.

    Maintains an ordered state dictionary with access tracking, supports
    snapshot/restore for checkpointing, and provides compression to reduce
    context size when it exceeds thresholds.

    Attributes:
        _state: Ordered state entries (newest last).
        _snapshots: List of context snapshots.
        _compression_count: Number of compressions performed.
        _decay_events: Number of decay events detected.
        _persistence_success_rate: Rate of successful persistence operations.
        max_history: Maximum number of state entries before compression.
        compression_threshold: Number of entries above which compression triggers.
        decay_window: Window size for decay detection.
    """

    def __init__(
        self,
        max_history: int = 100,
        compression_threshold: int = 50,
        decay_window: int = 20,
        state_persistence_dir: Optional[str] = None,
    ):
        """Initialize the context manager.

        Args:
            max_history: Maximum state entries to keep.
            compression_threshold: Trigger compression above this count.
            decay_window: Window size for decay detection.
            state_persistence_dir: Directory for state persistence files.
        """
        self.max_history = max_history
        self.compression_threshold = compression_threshold
        self.decay_window = decay_window
        self.persistence_dir = (
            Path(state_persistence_dir) if state_persistence_dir else None
        )

        # State storage
        self._state: OrderedDict[str, StateEntry] = OrderedDict()
        self._snapshots: List[ContextSnapshot] = []
        self._compression_count: int = 0
        self._decay_events: int = 0
        self._persistence_success_count: int = 0
        self._persistence_total_count: int = 0

        # Critical keys (never compressed away)
        self._critical_keys: Set[str] = {
            "task_id",
            "current_pose",
            "safety_state",
            "error",
            "error_history",
            "sampling_state",
        }

        # Access tracking for decay detection
        self._access_log: List[Tuple[str, float]] = []

    # =========================================================================
    # State Management
    # =========================================================================

    def update_state(self, updates: Dict[str, Any]) -> None:
        """Update state with new key-value pairs.

        Args:
            updates: Dict of key-value pairs to update.
        """
        now = time.time()
        for key, value in updates.items():
            if key in self._state:
                entry = self._state[key]
                entry.value = value
                entry.timestamp = now
                entry.access_count += 1
            else:
                self._state[key] = StateEntry(
                    key=key,
                    value=value,
                    timestamp=now,
                    access_count=1,
                    importance=self._calculate_importance(key),
                )

        # Trigger compression if needed
        if len(self._state) > self.compression_threshold:
            self._compress()

        # Trim if exceeding max history
        while len(self._state) > self.max_history:
            self._state.popitem(last=False)

    def get_state(self, key: str, default: Any = None) -> Any:
        """Get a state value by key.

        Args:
            key: State key to retrieve.
            default: Default value if key not found.

        Returns:
            State value or default.
        """
        if key in self._state:
            self._state[key].access_count += 1
            self._access_log.append((key, time.time()))
            return self._state[key].value
        return default

    def get_all_state(self) -> Dict[str, Any]:
        """Get all current state as a plain dict.

        Returns:
            Dict of all state key-value pairs.
        """
        return {k: v.value for k, v in self._state.items()}

    def get_state_summary(self) -> Dict[str, Any]:
        """Get a summary of the current state (metadata only).

        Returns:
            Dict with state metadata.
        """
        return {
            "total_keys": len(self._state),
            "critical_keys": len([k for k in self._state if k in self._critical_keys]),
            "newest_entry": (
                max(self._state.values(), key=lambda e: e.timestamp).key
                if self._state else None
            ),
            "oldest_entry": (
                min(self._state.values(), key=lambda e: e.timestamp).key
                if self._state else None
            ),
            "most_accessed": (
                max(self._state.values(), key=lambda e: e.access_count).key
                if self._state else None
            ),
        }

    def _calculate_importance(self, key: str) -> float:
        """Calculate initial importance score for a key.

        Args:
            key: State key name.

        Returns:
            Importance score (0.0 - 1.0).
        """
        # Critical keys get high importance
        if key in self._critical_keys:
            return 0.9

        # Pattern-based importance heuristics
        high_importance_patterns = [
            "error", "safety", "pose", "position",
            "task", "status", "state", "config",
            "quality", "defect", "sample",
        ]
        medium_importance_patterns = [
            "result", "history", "params", "bounds",
            "path", "target", "plan",
        ]

        key_lower = key.lower()
        for pattern in high_importance_patterns:
            if pattern in key_lower:
                return 0.7
        for pattern in medium_importance_patterns:
            if pattern in key_lower:
                return 0.5

        return 0.3

    # =========================================================================
    # Compression
    # =========================================================================

    def _compress(self) -> None:
        """Compress state history to reduce context size.

        Strategy:
        1. Preserve critical keys always
        2. Summarize old entries into aggregated stats
        3. Keep most recent entries intact
        """
        if len(self._state) <= self.compression_threshold:
            return

        # Identify entries to compress (older, less important, less accessed)
        entries = list(self._state.items())
        # Keep the most recent 60% intact
        keep_count = max(5, int(len(entries) * 0.6))
        entries_to_compress = entries[:-keep_count] if keep_count < len(entries) else []

        compressed: Dict[str, Any] = {}
        for key, entry in entries_to_compress:
            if key in self._critical_keys:
                continue  # Never compress critical keys
            # Aggregate numeric values
            if isinstance(entry.value, (int, float)):
                if key not in compressed:
                    compressed[key] = {
                        "type": "aggregated",
                        "count": 0,
                        "sum": 0.0,
                        "min": float("inf"),
                        "max": float("-inf"),
                        "last_value": entry.value,
                    }
                agg = compressed[key]
                agg["count"] += 1
                agg["sum"] += entry.value
                agg["min"] = min(agg["min"], entry.value)
                agg["max"] = max(agg["max"], entry.value)

        # Add compressed summary to state
        if compressed:
            summary = {
                "compressed_at": time.time(),
                "original_count": len(entries_to_compress),
                "aggregated_keys": len(compressed),
                "aggregates": compressed,
            }
            self._state["_compressed_summary"] = StateEntry(
                key="_compressed_summary",
                value=summary,
                timestamp=time.time(),
                importance=0.6,
            )

        # Remove compressed entries
        for key, _ in entries_to_compress:
            if key not in self._critical_keys and key != "_compressed_summary":
                del self._state[key]

        self._compression_count += 1

    def force_compress(self) -> int:
        """Force compression regardless of threshold.

        Returns:
            Number of entries compressed.
        """
        old_count = len(self._state)
        self._compress()
        return old_count - len(self._state)

    # =========================================================================
    # Decay Detection
    # =========================================================================

    def check_decay(self, critical_keys: Optional[List[str]] = None) -> Dict[str, Any]:
        """Check for context decay (information loss).

        Detects when critical information is being pushed out of the
        active context window, which can cause "context rot".

        Args:
            critical_keys: Optional list of keys to check for decay.

        Returns:
            Dict with decay analysis results.
        """
        keys_to_check = critical_keys or list(self._critical_keys)

        decayed_keys = []
        at_risk_keys = []
        healthy_keys = []

        now = time.time()
        for key in keys_to_check:
            if key not in self._state:
                decayed_keys.append(key)
                continue

            entry = self._state[key]
            age = now - entry.timestamp

            # Check if the key hasn't been accessed recently
            recent_accesses = [
                t for k, t in self._access_log[-self.decay_window:]
                if k == key
            ]

            if age > 300:  # 5 minutes without update
                at_risk_keys.append({
                    "key": key,
                    "age_seconds": round(age, 1),
                    "access_count": entry.access_count,
                    "recent_accesses": len(recent_accesses),
                })
            elif len(recent_accesses) == 0 and age > 60:
                at_risk_keys.append({
                    "key": key,
                    "age_seconds": round(age, 1),
                    "access_count": entry.access_count,
                    "recent_accesses": 0,
                })
            else:
                healthy_keys.append(key)

        # Record decay events
        if decayed_keys:
            self._decay_events += len(decayed_keys)

        return {
            "decayed": decayed_keys,
            "at_risk": at_risk_keys,
            "healthy": healthy_keys,
            "total_checked": len(keys_to_check),
            "decay_events_total": self._decay_events,
        }

    def mark_accessed(self, key: str) -> None:
        """Mark a key as recently accessed (for decay prevention).

        Args:
            key: State key that was accessed.
        """
        if key in self._state:
            self._state[key].access_count += 1
            self._access_log.append((key, time.time()))
            # Keep access log bounded
            if len(self._access_log) > self.decay_window * 10:
                self._access_log = self._access_log[-self.decay_window * 5:]

    # =========================================================================
    # Snapshot & Restore
    # =========================================================================

    def snapshot(self, label: str = "") -> ContextSnapshot:
        """Create a point-in-time snapshot of the current state.

        Args:
            label: Human-readable label for the snapshot.

        Returns:
            The created ContextSnapshot.
        """
        import uuid

        snapshot = ContextSnapshot(
            snapshot_id=uuid.uuid4().hex[:12],
            timestamp=time.time(),
            label=label,
            state=self.get_all_state(),
        )
        self._snapshots.append(snapshot)

        # Keep only last 10 snapshots
        if len(self._snapshots) > 10:
            self._snapshots = self._snapshots[-10:]

        return snapshot

    def restore(self, snapshot_id: Optional[str] = None) -> bool:
        """Restore state from a snapshot.

        Args:
            snapshot_id: Snapshot to restore. If None, restores the latest.

        Returns:
            True if restore succeeded, False otherwise.
        """
        if not self._snapshots:
            return False

        if snapshot_id:
            snapshot = next(
                (s for s in self._snapshots if s.snapshot_id == snapshot_id),
                None,
            )
        else:
            snapshot = self._snapshots[-1]

        if not snapshot:
            return False

        # Restore state
        self._state.clear()
        for key, value in snapshot.state.items():
            self._state[key] = StateEntry(
                key=key,
                value=value,
                timestamp=snapshot.timestamp,
                importance=self._calculate_importance(key),
            )

        return True

    def list_snapshots(self) -> List[Dict[str, Any]]:
        """List all available snapshots.

        Returns:
            List of snapshot metadata dicts.
        """
        return [
            {
                "id": s.snapshot_id,
                "label": s.label,
                "timestamp": s.timestamp,
                "keys": len(s.state),
                "hash": s.hash,
            }
            for s in self._snapshots
        ]

    # =========================================================================
    # Persistence
    # =========================================================================

    def save_state(self, filename: str = "state_snapshot.json") -> bool:
        """Save current state to disk.

        Args:
            filename: Output filename.

        Returns:
            True if save succeeded, False otherwise.
        """
        self._persistence_total_count += 1
        if not self.persistence_dir:
            self._persistence_success_count += 1
            return True

        try:
            self.persistence_dir.mkdir(parents=True, exist_ok=True)
            filepath = self.persistence_dir / filename

            data = {
                "saved_at": time.time(),
                "state": {
                    k: v.to_dict() for k, v in self._state.items()
                },
                "snapshots": [
                    {
                        "id": s.snapshot_id,
                        "label": s.label,
                        "timestamp": s.timestamp,
                        "hash": s.hash,
                    }
                    for s in self._snapshots
                ],
                "stats": {
                    "compression_count": self._compression_count,
                    "decay_events": self._decay_events,
                },
            }

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)

            self._persistence_success_count += 1
            return True
        except Exception:
            return False

    def load_state(self, filename: str = "state_snapshot.json") -> bool:
        """Load state from disk.

        Args:
            filename: Input filename.

        Returns:
            True if load succeeded, False otherwise.
        """
        if not self.persistence_dir:
            return False

        filepath = self.persistence_dir / filename
        if not filepath.exists():
            return False

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Restore state
            self._state.clear()
            for key, entry_data in data.get("state", {}).items():
                self._state[key] = StateEntry.from_dict(entry_data)

            # Restore stats
            stats = data.get("stats", {})
            self._compression_count = stats.get("compression_count", 0)
            self._decay_events = stats.get("decay_events", 0)

            return True
        except Exception:
            return False

    # =========================================================================
    # Health Statistics
    # =========================================================================

    def get_health_stats(self) -> Dict[str, Any]:
        """Get comprehensive context health statistics.

        Returns:
            Dict with context health metrics.
        """
        total_keys = len(self._state)
        critical_keys = [k for k in self._state if k in self._critical_keys]
        missing_critical = [
            k for k in self._critical_keys if k not in self._state
        ]

        # Access statistics
        access_counts = [e.access_count for e in self._state.values()]
        avg_access = sum(access_counts) / len(access_counts) if access_counts else 0

        # Age statistics
        now = time.time()
        ages = [now - e.timestamp for e in self._state.values()]
        avg_age = sum(ages) / len(ages) if ages else 0

        # Persistence rate
        persistence_rate = (
            self._persistence_success_count / self._persistence_total_count
            if self._persistence_total_count > 0
            else 1.0
        )

        return {
            "total_keys": total_keys,
            "critical_keys_present": len(critical_keys),
            "critical_keys_total": len(self._critical_keys),
            "missing_critical_keys": missing_critical,
            "compression_count": self._compression_count,
            "decay_events": self._decay_events,
            "snapshots_available": len(self._snapshots),
            "avg_access_count": round(avg_access, 1),
            "avg_age_seconds": round(avg_age, 1),
            "persistence_success_rate": round(persistence_rate, 4),
            "state_snapshots": len(self._snapshots),
        }

    def get_compression_report(self) -> Dict[str, Any]:
        """Get compression statistics.

        Returns:
            Dict with compression metrics.
        """
        return {
            "compression_count": self._compression_count,
            "current_size": len(self._state),
            "max_history": self.max_history,
            "compression_threshold": self.compression_threshold,
            "needs_compression": len(self._state) > self.compression_threshold,
            "compressed_summary": (
                self._state["_compressed_summary"].value
                if "_compressed_summary" in self._state
                else None
            ),
        }

    def reset(self) -> None:
        """Reset all context data."""
        self._state.clear()
        self._snapshots.clear()
        self._access_log.clear()
        self._compression_count = 0
        self._decay_events = 0
        self._persistence_success_count = 0
        self._persistence_total_count = 0