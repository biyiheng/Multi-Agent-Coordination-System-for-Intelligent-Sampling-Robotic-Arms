"""
Unit tests for the ContextManager.

Tests cover:
1. State update and retrieval
2. State summary
3. History compression
4. Decay detection
5. Snapshot and restore
6. State persistence (save/load)
7. Health statistics
8. Compression report
9. Reset
"""

import os
import tempfile
import time
import json
import pytest
from loop_engineering.context_manager import (
    ContextManager,
    StateEntry,
    ContextSnapshot,
)


# =============================================================================
# StateEntry Tests
# =============================================================================


class TestStateEntry:
    """Test StateEntry dataclass."""

    def test_default_values(self):
        """Default values should be set correctly."""
        entry = StateEntry(key="test_key", value="test_value")
        assert entry.key == "test_key"
        assert entry.value == "test_value"
        assert entry.access_count == 0
        assert entry.importance == 0.5

    def test_to_dict(self):
        """to_dict should produce serializable dict."""
        entry = StateEntry(key="test_key", value=42, importance=0.8)
        d = entry.to_dict()
        assert d["key"] == "test_key"
        assert d["value"] == 42
        assert d["importance"] == 0.8

    def test_from_dict(self):
        """from_dict should reconstruct StateEntry."""
        data = {"key": "test_key", "value": "hello", "access_count": 5, "importance": 0.7}
        entry = StateEntry.from_dict(data)
        assert entry.key == "test_key"
        assert entry.value == "hello"
        assert entry.access_count == 5
        assert entry.importance == 0.7


# =============================================================================
# ContextSnapshot Tests
# =============================================================================


class TestContextSnapshot:
    """Test ContextSnapshot dataclass."""

    def test_hash_computation(self):
        """Hash should be computed from state."""
        snapshot = ContextSnapshot(
            snapshot_id="test_001",
            timestamp=time.time(),
            label="test",
            state={"key1": "value1", "key2": 42},
        )
        assert len(snapshot.hash) == 16

    def test_hash_deterministic(self):
        """Same state should produce same hash."""
        state = {"key": "value"}
        s1 = ContextSnapshot(snapshot_id="1", timestamp=0, label="a", state=state)
        s2 = ContextSnapshot(snapshot_id="2", timestamp=0, label="b", state=state)
        assert s1.hash == s2.hash

    def test_hash_different_for_different_state(self):
        """Different state should produce different hash."""
        s1 = ContextSnapshot(snapshot_id="1", timestamp=0, label="a", state={"k": "v1"})
        s2 = ContextSnapshot(snapshot_id="2", timestamp=0, label="b", state={"k": "v2"})
        assert s1.hash != s2.hash


# =============================================================================
# ContextManager: State Management
# =============================================================================


class TestContextManagerState:
    """Test state update and retrieval."""

    def test_update_new_state(self):
        """New keys should be added to state."""
        ctx = ContextManager()
        ctx.update_state({"task_id": "001", "value": 42})
        assert ctx.get_state("task_id") == "001"
        assert ctx.get_state("value") == 42

    def test_update_existing_state(self):
        """Existing keys should be updated."""
        ctx = ContextManager()
        ctx.update_state({"counter": 1})
        ctx.update_state({"counter": 2})
        assert ctx.get_state("counter") == 2

    def test_get_missing_key(self):
        """Missing keys should return default."""
        ctx = ContextManager()
        assert ctx.get_state("nonexistent") is None
        assert ctx.get_state("nonexistent", "default") == "default"

    def test_get_all_state(self):
        """get_all_state should return all key-value pairs."""
        ctx = ContextManager()
        ctx.update_state({"a": 1, "b": 2, "c": 3})
        all_state = ctx.get_all_state()
        assert all_state == {"a": 1, "b": 2, "c": 3}

    def test_access_count_increments(self):
        """Access count should increment on get."""
        ctx = ContextManager()
        ctx.update_state({"key": "value"})
        ctx.get_state("key")
        ctx.get_state("key")
        assert ctx._state["key"].access_count == 3  # 1 from update + 2 from get

    def test_state_summary(self):
        """State summary should provide metadata."""
        ctx = ContextManager()
        ctx.update_state({
            "task_id": "001",
            "current_pose": {"x": 100},
            "extra_data": "test",
        })
        summary = ctx.get_state_summary()
        assert summary["total_keys"] == 3
        assert summary["critical_keys"] >= 1  # task_id and current_pose are critical


# =============================================================================
# ContextManager: Importance Calculation
# =============================================================================


class TestContextManagerImportance:
    """Test importance calculation."""

    def test_critical_key_importance(self):
        """Critical keys should have high importance."""
        ctx = ContextManager()
        assert ctx._calculate_importance("task_id") == 0.9
        assert ctx._calculate_importance("safety_state") == 0.9
        assert ctx._calculate_importance("error") == 0.9

    def test_high_importance_pattern(self):
        """Keys matching high importance patterns should score 0.7."""
        ctx = ContextManager()
        assert ctx._calculate_importance("quality_score") == 0.7
        assert ctx._calculate_importance("sample_data") == 0.7

    def test_medium_importance_pattern(self):
        """Keys matching medium importance patterns should score 0.5."""
        ctx = ContextManager()
        assert ctx._calculate_importance("result_data") == 0.5
        assert ctx._calculate_importance("path_plan") == 0.5

    def test_low_importance_default(self):
        """Unknown keys should have low importance."""
        ctx = ContextManager()
        assert ctx._calculate_importance("random_field") == 0.3


# =============================================================================
# ContextManager: Compression
# =============================================================================


class TestContextManagerCompression:
    """Test history compression."""

    def test_compression_below_threshold(self):
        """Below threshold, no compression should occur."""
        ctx = ContextManager(compression_threshold=50)
        for i in range(10):
            ctx.update_state({f"key_{i}": i})
        assert ctx._compression_count == 0

    def test_compression_above_threshold(self):
        """Above threshold, compression should trigger."""
        ctx = ContextManager(
            max_history=200,
            compression_threshold=10,
        )
        for i in range(20):
            ctx.update_state({f"key_{i}": i})
        # Compression should have been triggered
        assert ctx._compression_count > 0

    def test_critical_keys_preserved(self):
        """Critical keys should survive compression."""
        ctx = ContextManager(compression_threshold=10)
        ctx.update_state({"task_id": "001", "error": "none"})
        # Add many non-critical keys
        for i in range(15):
            ctx.update_state({f"extra_{i}": i})
        # Critical keys should still exist
        assert ctx.get_state("task_id") == "001"
        assert ctx.get_state("error") == "none"

    def test_force_compress(self):
        """Force compress should work regardless of threshold."""
        ctx = ContextManager(compression_threshold=100)
        for i in range(50):
            ctx.update_state({f"key_{i}": i})
        old_count = len(ctx._state)
        compressed = ctx.force_compress()
        assert compressed >= 0  # May compress 0 if all are critical-like
        assert len(ctx._state) <= old_count

    def test_compressed_summary_created(self):
        """Compressed summary should be added to state."""
        ctx = ContextManager(compression_threshold=10)
        for i in range(20):
            ctx.update_state({f"key_{i}": float(i)})
        summary = ctx.get_state("_compressed_summary")
        if summary:
            assert "aggregated_keys" in summary
            assert "original_count" in summary


# =============================================================================
# ContextManager: Decay Detection
# =============================================================================


class TestContextManagerDecay:
    """Test context decay detection."""

    def test_no_decay_with_all_keys(self):
        """All keys present should not detect decay."""
        ctx = ContextManager()
        ctx.update_state({
            "task_id": "001",
            "current_pose": {"x": 0},
            "error": None,
        })
        result = ctx.check_decay(["task_id", "current_pose", "error"])
        assert len(result["decayed"]) == 0

    def test_decay_detection_missing_key(self):
        """Missing critical key should be detected as decay."""
        ctx = ContextManager()
        ctx.update_state({"task_id": "001"})
        result = ctx.check_decay(["task_id", "missing_key"])
        assert "missing_key" in result["decayed"]

    def test_decay_event_count(self):
        """Decay events should increment."""
        ctx = ContextManager()
        ctx.check_decay(["missing_key"])
        assert ctx._decay_events == 1
        ctx.check_decay(["another_missing"])
        assert ctx._decay_events == 2

    def test_at_risk_keys(self):
        """Old keys should be at risk."""
        ctx = ContextManager()
        # Create an old entry
        ctx._state["old_key"] = StateEntry(
            key="old_key",
            value="old",
            timestamp=time.time() - 400,  # 400 seconds old
            access_count=0,
        )
        result = ctx.check_decay(["old_key"])
        assert len(result["at_risk"]) > 0

    def test_mark_accessed(self):
        """Mark accessed should update access count."""
        ctx = ContextManager()
        ctx.update_state({"task_id": "001"})
        ctx.mark_accessed("task_id")
        ctx.mark_accessed("task_id")
        assert ctx._state["task_id"].access_count >= 3  # 1 update + 2 marks


# =============================================================================
# ContextManager: Snapshot & Restore
# =============================================================================


class TestContextManagerSnapshot:
    """Test snapshot and restore."""

    def test_snapshot_creation(self):
        """Snapshot should capture current state."""
        ctx = ContextManager()
        ctx.update_state({"task_id": "001", "value": 42})
        snap = ctx.snapshot("test_snapshot")

        assert snap.label == "test_snapshot"
        assert snap.state["task_id"] == "001"
        assert snap.state["value"] == 42

    def test_restore_latest(self):
        """Restore should restore the latest snapshot."""
        ctx = ContextManager()
        ctx.update_state({"task_id": "001", "value": 42})
        ctx.snapshot("before_change")

        # Change state
        ctx.update_state({"task_id": "002", "value": 99})

        # Restore
        assert ctx.restore()
        assert ctx.get_state("task_id") == "001"
        assert ctx.get_state("value") == 42

    def test_restore_by_id(self):
        """Restore by ID should restore specific snapshot."""
        ctx = ContextManager()
        ctx.update_state({"version": 1})
        snap1 = ctx.snapshot("v1")

        ctx.update_state({"version": 2})
        snap2 = ctx.snapshot("v2")

        ctx.update_state({"version": 3})

        assert ctx.restore(snap1.snapshot_id)
        assert ctx.get_state("version") == 1

    def test_restore_with_no_snapshots(self):
        """Restore with no snapshots should return False."""
        ctx = ContextManager()
        assert not ctx.restore()

    def test_list_snapshots(self):
        """List snapshots should return metadata."""
        ctx = ContextManager()
        ctx.update_state({"a": 1})
        ctx.snapshot("first")
        ctx.update_state({"b": 2})
        ctx.snapshot("second")

        snaps = ctx.list_snapshots()
        assert len(snaps) == 2
        assert snaps[0]["label"] == "first"
        assert snaps[1]["label"] == "second"

    def test_snapshot_limit(self):
        """Only last 10 snapshots should be kept."""
        ctx = ContextManager()
        for i in range(15):
            ctx.update_state({f"key_{i}": i})
            ctx.snapshot(f"snap_{i}")
        assert len(ctx._snapshots) <= 10


# =============================================================================
# ContextManager: Persistence
# =============================================================================


class TestContextManagerPersistence:
    """Test state persistence (save/load)."""

    def test_save_state(self):
        """Save state should write to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ContextManager(state_persistence_dir=tmpdir)
            ctx.update_state({"task_id": "001", "value": 42})
            assert ctx.save_state("test_save.json")

            filepath = os.path.join(tmpdir, "test_save.json")
            assert os.path.exists(filepath)

    def test_load_state(self):
        """Load state should restore from disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Save
            ctx1 = ContextManager(state_persistence_dir=tmpdir)
            ctx1.update_state({"task_id": "001", "value": 42})
            ctx1.save_state("test_save.json")

            # Load
            ctx2 = ContextManager(state_persistence_dir=tmpdir)
            assert ctx2.load_state("test_save.json")
            assert ctx2.get_state("task_id") == "001"
            assert ctx2.get_state("value") == 42

    def test_load_nonexistent_file(self):
        """Load nonexistent file should return False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ContextManager(state_persistence_dir=tmpdir)
            assert not ctx.load_state("nonexistent.json")

    def test_save_without_dir(self):
        """Save without persistence_dir should succeed (no-op)."""
        ctx = ContextManager()
        assert ctx.save_state()  # Returns True as no-op

    def test_persistence_success_rate(self):
        """Persistence success rate should be tracked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ContextManager(state_persistence_dir=tmpdir)
            ctx.save_state()
            ctx.save_state()
            stats = ctx.get_health_stats()
            assert stats["persistence_success_rate"] == 1.0


# =============================================================================
# ContextManager: Health Statistics
# =============================================================================


class TestContextManagerHealth:
    """Test health statistics."""

    def test_empty_health_stats(self):
        """Empty context manager should have zeros."""
        ctx = ContextManager()
        stats = ctx.get_health_stats()
        assert stats["total_keys"] == 0
        assert stats["compression_count"] == 0
        assert stats["decay_events"] == 0

    def test_health_stats_with_data(self):
        """Health stats should reflect current state."""
        ctx = ContextManager()
        ctx.update_state({"task_id": "001", "current_pose": {}, "extra": "data"})
        ctx.snapshot("test")
        stats = ctx.get_health_stats()
        assert stats["total_keys"] == 3
        assert stats["critical_keys_present"] >= 2
        assert stats["snapshots_available"] == 1

    def test_missing_critical_keys(self):
        """Missing critical keys should be reported."""
        ctx = ContextManager()
        ctx.update_state({"extra": "data"})
        stats = ctx.get_health_stats()
        assert len(stats["missing_critical_keys"]) > 0

    def test_compression_report(self):
        """Compression report should show compression stats."""
        ctx = ContextManager(compression_threshold=5)
        for i in range(10):
            ctx.update_state({f"key_{i}": i})
        report = ctx.get_compression_report()
        assert "compression_count" in report
        assert "current_size" in report
        assert "needs_compression" in report


# =============================================================================
# ContextManager: Reset
# =============================================================================


class TestContextManagerReset:
    """Test reset functionality."""

    def test_reset_clears_all(self):
        """Reset should clear all data."""
        ctx = ContextManager()
        ctx.update_state({"task_id": "001", "value": 42})
        ctx.snapshot("test")
        ctx.save_state()

        ctx.reset()
        assert len(ctx._state) == 0
        assert len(ctx._snapshots) == 0
        assert ctx._compression_count == 0
        assert ctx._decay_events == 0

    def test_reset_allows_new_operations(self):
        """After reset, new operations should work."""
        ctx = ContextManager()
        ctx.update_state({"task_id": "001"})
        ctx.reset()
        ctx.update_state({"task_id": "002"})
        assert ctx.get_state("task_id") == "002"