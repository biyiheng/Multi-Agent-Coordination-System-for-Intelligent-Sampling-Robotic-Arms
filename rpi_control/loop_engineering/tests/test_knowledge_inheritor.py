"""
Unit tests for KnowledgeInheritor - cross-generation knowledge inheritance.

Tests cover:
1. Version registration and lineage management
2. Auto-inheritance from parent versions
3. Parameter transfer between versions
4. Deprecation management
5. Core memory management
6. Decay-based deprecation
7. Lineage analysis and statistics
8. Persistence and reset
9. Edge cases
"""

import tempfile
import time
from pathlib import Path

import pytest

from loop_engineering.knowledge_inheritor import (
    KnowledgeInheritor,
    KnowledgeTransfer,
    VersionNode,
)


class TestVersionNode:
    """Tests for VersionNode dataclass."""

    def test_default_values(self):
        """VersionNode should have correct defaults."""
        node = VersionNode(version="v1.0.0")
        assert node.version == "v1.0.0"
        assert node.parent is None
        assert node.children == []
        assert node.params == {}
        assert node.models == {}
        assert node.score == 0.0
        assert node.notes == ""

    def test_with_params(self):
        """VersionNode should accept params."""
        node = VersionNode(
            version="v2.0.0",
            parent="v1.0.0",
            params={"lr": 0.01, "batch_size": 32},
            score=0.85,
            notes="Improved accuracy",
        )
        assert node.parent == "v1.0.0"
        assert node.params["lr"] == 0.01
        assert node.score == 0.85


class TestKnowledgeTransfer:
    """Tests for KnowledgeTransfer dataclass."""

    def test_default_values(self):
        """KnowledgeTransfer should have correct defaults."""
        transfer = KnowledgeTransfer(
            transfer_id="t1",
            from_version="v1.0.0",
            to_version="v2.0.0",
        )
        assert transfer.transfer_id == "t1"
        assert transfer.from_version == "v1.0.0"
        assert transfer.to_version == "v2.0.0"
        assert transfer.params_transferred == []
        assert transfer.params_deprecated == []
        assert transfer.success_rate == 0.0

    def test_with_params(self):
        """KnowledgeTransfer should track transferred and deprecated params."""
        transfer = KnowledgeTransfer(
            transfer_id="t1",
            from_version="v1.0.0",
            to_version="v2.0.0",
            params_transferred=["lr", "batch_size"],
            params_deprecated=["old_strategy"],
            success_rate=0.67,
        )
        assert len(transfer.params_transferred) == 2
        assert "old_strategy" in transfer.params_deprecated


class TestVersionRegistration:
    """Tests for version registration."""

    def test_register_single_version(self):
        """Registering a single version should create it."""
        inheritor = KnowledgeInheritor()
        node = inheritor.register_version("v1.0.0")
        assert node.version == "v1.0.0"
        assert "v1.0.0" in inheritor._lineage

    def test_register_with_parent(self):
        """Registering with parent should link versions."""
        inheritor = KnowledgeInheritor()
        inheritor.register_version("v1.0.0")
        inheritor.register_version("v2.0.0", parent="v1.0.0")

        parent = inheritor._lineage["v1.0.0"]
        assert "v2.0.0" in parent.children
        child = inheritor._lineage["v2.0.0"]
        assert child.parent == "v1.0.0"

    def test_register_with_params(self):
        """Registering with params should store them."""
        inheritor = KnowledgeInheritor()
        inheritor.register_version(
            "v1.0.0",
            params={"lr": 0.01, "epochs": 100},
            score=0.92,
            notes="Baseline",
        )
        node = inheritor._lineage["v1.0.0"]
        assert node.params["lr"] == 0.01
        assert node.score == 0.92
        assert node.notes == "Baseline"

    def test_register_multiple_descendants(self):
        """Multiple children from same parent should work."""
        inheritor = KnowledgeInheritor()
        inheritor.register_version("v1.0.0")
        inheritor.register_version("v2.0.0", parent="v1.0.0")
        inheritor.register_version("v2.1.0", parent="v1.0.0")

        parent = inheritor._lineage["v1.0.0"]
        assert len(parent.children) == 2
        assert "v2.0.0" in parent.children
        assert "v2.1.0" in parent.children

    def test_register_with_nonexistent_parent(self):
        """Registering with nonexistent parent should not crash."""
        inheritor = KnowledgeInheritor()
        inheritor.register_version("v2.0.0", parent="v_nonexistent")
        # Should still create the version
        assert "v2.0.0" in inheritor._lineage


class TestAutoInheritance:
    """Tests for automatic inheritance from parent."""

    def test_auto_inherit_params(self):
        """Child should auto-inherit non-deprecated params from parent."""
        inheritor = KnowledgeInheritor()
        inheritor.register_version("v1.0.0", params={"lr": 0.01, "batch_size": 32, "epochs": 100})
        inheritor.register_version("v2.0.0", parent="v1.0.0")

        child = inheritor._lineage["v2.0.0"]
        assert child.params["lr"] == 0.01
        assert child.params["batch_size"] == 32
        assert child.params["epochs"] == 100

    def test_auto_inherit_skips_deprecated(self):
        """Deprecated params should not be auto-inherited."""
        inheritor = KnowledgeInheritor()
        inheritor.deprecate_knowledge("old_param", "Obsolete")
        inheritor.register_version("v1.0.0", params={"lr": 0.01, "old_param": "bad"})
        inheritor.register_version("v2.0.0", parent="v1.0.0")

        child = inheritor._lineage["v2.0.0"]
        assert "lr" in child.params
        assert "old_param" not in child.params

    def test_auto_inherit_models(self):
        """Models should also be auto-inherited."""
        inheritor = KnowledgeInheritor()
        inheritor.register_version("v1.0.0", params={"lr": 0.01})
        parent = inheritor._lineage["v1.0.0"]
        parent.models["quality_model"] = {"accuracy": 0.95}

        inheritor.register_version("v2.0.0", parent="v1.0.0")
        child = inheritor._lineage["v2.0.0"]
        assert "quality_model" in child.models
        assert child.models["quality_model"]["accuracy"] == 0.95

    def test_auto_inherit_creates_transfer_record(self):
        """Auto-inheritance should create a transfer record."""
        inheritor = KnowledgeInheritor()
        inheritor.register_version("v1.0.0", params={"lr": 0.01, "batch_size": 32})
        inheritor.register_version("v2.0.0", parent="v1.0.0")

        assert len(inheritor._transfers) == 1
        transfer = inheritor._transfers[0]
        assert transfer.from_version == "v1.0.0"
        assert transfer.to_version == "v2.0.0"
        assert "lr" in transfer.params_transferred

    def test_auto_inherit_without_parent(self):
        """Version without parent should not trigger auto-inheritance."""
        inheritor = KnowledgeInheritor()
        inheritor.register_version("v1.0.0", params={"lr": 0.01})
        # No transfer should be recorded for root version
        assert len(inheritor._transfers) == 0


class TestParameterTransfer:
    """Tests for explicit parameter transfer."""

    def test_inherit_params(self):
        """Should transfer params from source to target."""
        inheritor = KnowledgeInheritor()
        inheritor.register_version("v1.0.0")
        inheritor.register_version("v2.0.0")

        transfer = inheritor.inherit_params(
            from_version="v1.0.0",
            to_version="v2.0.0",
            params={"lr": 0.001, "optimizer": "adam"},
        )

        target = inheritor._lineage["v2.0.0"]
        assert target.params["lr"] == 0.001
        assert target.params["optimizer"] == "adam"
        assert len(transfer.params_transferred) == 2

    def test_inherit_params_skips_deprecated(self):
        """Deprecated params should be skipped during transfer."""
        inheritor = KnowledgeInheritor()
        inheritor.deprecate_knowledge("old_optimizer")
        inheritor.register_version("v1.0.0")
        inheritor.register_version("v2.0.0")

        transfer = inheritor.inherit_params(
            from_version="v1.0.0",
            to_version="v2.0.0",
            params={"lr": 0.001, "old_optimizer": "sgd"},
        )

        target = inheritor._lineage["v2.0.0"]
        assert "lr" in target.params
        assert "old_optimizer" not in target.params
        assert "old_optimizer" in transfer.params_deprecated

    def test_inherit_params_with_models(self):
        """Should transfer models as well as params."""
        inheritor = KnowledgeInheritor()
        inheritor.register_version("v1.0.0")
        inheritor.register_version("v2.0.0")

        inheritor.inherit_params(
            from_version="v1.0.0",
            to_version="v2.0.0",
            params={"lr": 0.001},
            models={"classifier": {"accuracy": 0.93}},
        )

        target = inheritor._lineage["v2.0.0"]
        assert "classifier" in target.models

    def test_inherit_to_nonexistent_version(self):
        """Transfer to nonexistent version should not crash."""
        inheritor = KnowledgeInheritor()
        transfer = inheritor.inherit_params(
            from_version="v1.0.0",
            to_version="nonexistent",
            params={"lr": 0.001},
        )
        assert transfer.success_rate == 1.0  # Nothing to transfer, rate is 1.0

    def test_transfer_success_rate(self):
        """Transfer success rate should reflect ratio of transferred to total."""
        inheritor = KnowledgeInheritor()
        inheritor.deprecate_knowledge("bad_param")
        inheritor.register_version("v1.0.0")
        inheritor.register_version("v2.0.0")

        transfer = inheritor.inherit_params(
            from_version="v1.0.0",
            to_version="v2.0.0",
            params={"good_param": 1, "bad_param": 2},
        )

        assert transfer.success_rate == 0.5  # 1 transferred, 1 deprecated = 1/2


class TestDeprecationManagement:
    """Tests for knowledge deprecation."""

    def test_deprecate_knowledge(self):
        """Should mark knowledge as deprecated."""
        inheritor = KnowledgeInheritor()
        inheritor.deprecate_knowledge("old_strategy", "Superseded by v2")
        assert inheritor.is_deprecated("old_strategy")
        assert inheritor.get_deprecated_count() == 1

    def test_deprecate_removes_from_core_memory(self):
        """Deprecation should remove from core memory."""
        inheritor = KnowledgeInheritor()
        inheritor.set_core_memory("old_strategy", {"value": 42})
        inheritor.deprecate_knowledge("old_strategy")
        assert inheritor.get_core_memory("old_strategy") is None

    def test_is_not_deprecated(self):
        """Non-deprecated items should return False."""
        inheritor = KnowledgeInheritor()
        assert not inheritor.is_deprecated("active_param")

    def test_cleanup_deprecated(self):
        """Should clean up old deprecated items."""
        inheritor = KnowledgeInheritor()
        # Manually set an old removed_at timestamp
        inheritor.deprecate_knowledge("old_item")
        inheritor._removed_at["old_item"] = time.time() - 86400 * 31  # 31 days ago

        cleaned = inheritor.cleanup_deprecated(max_age_days=30)
        assert cleaned == 1
        assert not inheritor.is_deprecated("old_item")

    def test_cleanup_fresh_deprecated(self):
        """Fresh deprecated items should not be cleaned up."""
        inheritor = KnowledgeInheritor()
        inheritor.deprecate_knowledge("fresh_item")
        cleaned = inheritor.cleanup_deprecated(max_age_days=30)
        assert cleaned == 0
        assert inheritor.is_deprecated("fresh_item")


class TestCoreMemory:
    """Tests for core memory management."""

    def test_set_and_get_core_memory(self):
        """Should set and retrieve core memory."""
        inheritor = KnowledgeInheritor()
        inheritor.set_core_memory("critical_param", {"lr": 0.001})
        assert inheritor.get_core_memory("critical_param") == {"lr": 0.001}

    def test_get_default(self):
        """Should return default for missing key."""
        inheritor = KnowledgeInheritor()
        assert inheritor.get_core_memory("missing", default="fallback") == "fallback"

    def test_get_none_default(self):
        """Should return None by default for missing key."""
        inheritor = KnowledgeInheritor()
        assert inheritor.get_core_memory("missing") is None

    def test_get_core_memory_snapshot(self):
        """Should return full snapshot."""
        inheritor = KnowledgeInheritor()
        inheritor.set_core_memory("a", 1)
        inheritor.set_core_memory("b", 2)
        snapshot = inheritor.get_core_memory_snapshot()
        assert snapshot == {"a": 1, "b": 2}

    def test_apply_decay_deprecates_low_effectiveness(self):
        """Items with low effectiveness should be deprecated."""
        inheritor = KnowledgeInheritor(decay_threshold=0.5)
        inheritor.set_core_memory("good_param", {"effectiveness": 0.8})
        inheritor.set_core_memory("bad_param", {"effectiveness": 0.2})

        deprecated = inheritor.apply_decay()
        assert "bad_param" in deprecated
        assert "good_param" not in deprecated
        assert inheritor.is_deprecated("bad_param")

    def test_apply_decay_ignores_non_dict(self):
        """Non-dict core memory items should be ignored by decay."""
        inheritor = KnowledgeInheritor(decay_threshold=0.5)
        inheritor.set_core_memory("string_param", "some_value")
        inheritor.set_core_memory("int_param", 42)

        deprecated = inheritor.apply_decay()
        assert len(deprecated) == 0  # Non-dict values are not evaluated


class TestLineageAnalysis:
    """Tests for lineage analysis."""

    def test_get_lineage(self):
        """Should return full lineage tree."""
        inheritor = KnowledgeInheritor()
        inheritor.register_version("v1.0.0", params={"lr": 0.01})
        inheritor.register_version("v2.0.0", parent="v1.0.0")
        inheritor.register_version("v3.0.0", parent="v2.0.0")

        lineage = inheritor.get_lineage()
        assert len(lineage) == 3
        assert lineage["v1.0.0"]["parent"] is None
        assert lineage["v2.0.0"]["parent"] == "v1.0.0"
        assert "v2.0.0" in lineage["v1.0.0"]["children"]

    def test_get_inheritance_rate(self):
        """Should calculate overall inheritance success rate."""
        inheritor = KnowledgeInheritor()
        inheritor.register_version("v1.0.0", params={"a": 1, "b": 2})
        inheritor.register_version("v2.0.0", parent="v1.0.0")
        inheritor.register_version("v3.0.0", parent="v2.0.0")

        rate = inheritor.get_inheritance_rate()
        assert 0.0 <= rate <= 1.0

    def test_get_inheritance_rate_empty(self):
        """Empty transfers should return 0."""
        inheritor = KnowledgeInheritor()
        assert inheritor.get_inheritance_rate() == 0.0

    def test_get_version_chain(self):
        """Should return ancestor chain."""
        inheritor = KnowledgeInheritor()
        inheritor.register_version("v1.0.0")
        inheritor.register_version("v2.0.0", parent="v1.0.0")
        inheritor.register_version("v3.0.0", parent="v2.0.0")

        chain = inheritor.get_version_chain("v3.0.0")
        assert chain == ["v1.0.0", "v2.0.0", "v3.0.0"]

    def test_get_version_chain_root(self):
        """Root version should return only itself."""
        inheritor = KnowledgeInheritor()
        inheritor.register_version("v1.0.0")
        chain = inheritor.get_version_chain("v1.0.0")
        assert chain == ["v1.0.0"]

    def test_get_version_chain_nonexistent(self):
        """Nonexistent version should return empty list."""
        inheritor = KnowledgeInheritor()
        chain = inheritor.get_version_chain("nonexistent")
        assert chain == []

    def test_get_statistics(self):
        """Should return comprehensive statistics."""
        inheritor = KnowledgeInheritor()
        inheritor.register_version("v1.0.0", params={"a": 1})
        inheritor.register_version("v2.0.0", parent="v1.0.0")
        inheritor.deprecate_knowledge("old")

        stats = inheritor.get_statistics()
        assert stats["total_versions"] == 2
        assert stats["total_transfers"] >= 1
        assert stats["deprecated_count"] >= 1
        assert "inheritance_rate" in stats


class TestKnowledgeInheritorPersistence:
    """Tests for lineage persistence."""

    def test_save_lineage(self):
        """Should save lineage to disk."""
        inheritor = KnowledgeInheritor()
        inheritor.register_version("v1.0.0", params={"lr": 0.01})
        inheritor.register_version("v2.0.0", parent="v1.0.0")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "lineage.json"
            inheritor.lineage_path = path
            assert inheritor.save_lineage()
            assert path.exists()

    def test_save_without_path(self):
        """Save without path should return False."""
        inheritor = KnowledgeInheritor()
        assert not inheritor.save_lineage()

    def test_load_lineage(self):
        """Should load lineage from disk."""
        inheritor = KnowledgeInheritor()
        inheritor.register_version("v1.0.0", params={"lr": 0.01})
        inheritor.register_version("v2.0.0", parent="v1.0.0")
        inheritor.deprecate_knowledge("old_param")
        inheritor.set_core_memory("key", "value")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "lineage.json"
            inheritor.lineage_path = path
            inheritor.save_lineage()

            inheritor2 = KnowledgeInheritor(lineage_path=str(path))
            assert inheritor2.load_lineage()
            assert len(inheritor2._lineage) == 2
            assert inheritor2._lineage["v2.0.0"].parent == "v1.0.0"
            assert "old_param" in inheritor2._deprecated
            assert inheritor2.get_core_memory("key") == "value"

    def test_load_nonexistent_file(self):
        """Loading nonexistent file should return False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            inheritor = KnowledgeInheritor(lineage_path=str(Path(tmpdir) / "nonexistent.json"))
            assert not inheritor.load_lineage()

    def test_load_without_path(self):
        """Loading without path should return False."""
        inheritor = KnowledgeInheritor()
        assert not inheritor.load_lineage()


class TestKnowledgeInheritorReset:
    """Tests for reset functionality."""

    def test_reset_clears_all(self):
        """Reset should clear all data."""
        inheritor = KnowledgeInheritor()
        inheritor.register_version("v1.0.0", params={"a": 1})
        inheritor.register_version("v2.0.0", parent="v1.0.0")
        inheritor.deprecate_knowledge("old")
        inheritor.set_core_memory("key", "value")

        inheritor.reset()
        assert len(inheritor._lineage) == 0
        assert len(inheritor._transfers) == 0
        assert len(inheritor._deprecated) == 0
        assert len(inheritor._core_memory) == 0
        assert inheritor._total_transfers == 0

    def test_reset_allows_new_operations(self):
        """After reset, new operations should work."""
        inheritor = KnowledgeInheritor()
        inheritor.register_version("v1.0.0")
        inheritor.reset()

        inheritor.register_version("v1.0.0")
        assert "v1.0.0" in inheritor._lineage


class TestKnowledgeInheritorEdgeCases:
    """Edge case tests."""

    def test_deep_lineage(self):
        """Deep lineage chain should work."""
        inheritor = KnowledgeInheritor()
        for i in range(10):
            parent = f"v{i}.0.0" if i > 0 else None
            inheritor.register_version(f"v{i+1}.0.0", parent=parent)
        chain = inheritor.get_version_chain("v10.0.0")
        assert len(chain) == 10

    def test_multiple_roots(self):
        """Multiple root versions should work."""
        inheritor = KnowledgeInheritor()
        inheritor.register_version("v1.0.0")
        inheritor.register_version("v2.0.0")  # No parent
        assert inheritor._lineage["v1.0.0"].parent is None
        assert inheritor._lineage["v2.0.0"].parent is None

    def test_register_duplicate_version(self):
        """Registering duplicate version should overwrite."""
        inheritor = KnowledgeInheritor()
        inheritor.register_version("v1.0.0", params={"a": 1})
        inheritor.register_version("v1.0.0", params={"b": 2})
        assert inheritor._lineage["v1.0.0"].params == {"b": 2}

    def test_empty_params_transfer(self):
        """Transferring empty params should work."""
        inheritor = KnowledgeInheritor()
        inheritor.register_version("v1.0.0")
        inheritor.register_version("v2.0.0")
        transfer = inheritor.inherit_params("v1.0.0", "v2.0.0", {})
        assert transfer.success_rate == 1.0