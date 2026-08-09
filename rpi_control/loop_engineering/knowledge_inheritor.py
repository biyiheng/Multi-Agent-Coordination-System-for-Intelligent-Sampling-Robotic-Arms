"""
Knowledge inheritance for cross-generation agent evolution.

Manages knowledge transfer between system versions, maintains a lineage
graph of agent generations, and prevents catastrophic forgetting by
selectively inheriting core knowledge while deprecating obsolete knowledge.

Key features:
1. Lineage tracking: Maintain agent version family tree
2. Core memory inheritance: Transfer critical parameters and models
3. Deprecation management: Identify and retire obsolete knowledge
4. Transfer success tracking: Measure inheritance effectiveness
5. Family tree visualization data: Export lineage data for graphing

Usage:
    inheritor = KnowledgeInheritor()
    inheritor.register_version("v2.0.0", parent="v1.0.0")
    inheritor.inherit_params(from_version="v1.0.0", to_version="v2.0.0", params={...})
    inheritor.deprecate_knowledge("old_strategy", reason="superseded")
"""

import json
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class VersionNode:
    """A node in the agent lineage tree.

    Attributes:
        version: Version string (e.g., 'v2.0.0').
        parent: Parent version string.
        children: Child version strings.
        created_at: When this version was registered.
        params: Inherited parameters keyed by name.
        models: Inherited model metadata.
        score: Overall performance score for this version.
        notes: Human-readable notes.
    """
    version: str
    parent: Optional[str] = None
    children: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    params: Dict[str, Any] = field(default_factory=dict)
    models: Dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    notes: str = ""


@dataclass
class KnowledgeTransfer:
    """A record of knowledge transfer between versions.

    Attributes:
        transfer_id: Unique transfer identifier.
        from_version: Source version.
        to_version: Target version.
        params_transferred: List of parameter names transferred.
        params_deprecated: List of parameter names deprecated.
        success_rate: Transfer success rate (0.0 - 1.0).
        timestamp: When the transfer occurred.
        notes: Human-readable notes.
    """
    transfer_id: str
    from_version: str
    to_version: str
    params_transferred: List[str] = field(default_factory=list)
    params_deprecated: List[str] = field(default_factory=list)
    success_rate: float = 0.0
    timestamp: float = field(default_factory=time.time)
    notes: str = ""


# =============================================================================
# Knowledge Inheritor
# =============================================================================


class KnowledgeInheritor:
    """Manages cross-generation knowledge inheritance.

    Tracks version lineage, selectively transfers core knowledge between
    versions, and manages knowledge deprecation to prevent catastrophic
    forgetting.

    Attributes:
        _lineage: Version family tree (version -> VersionNode).
        _transfers: History of knowledge transfers.
        _deprecated: Set of deprecated knowledge keys.
        _core_memory: Critical parameters that should always be inherited.
        _removed_at: Timestamp when each item was deprecated.
    """

    def __init__(
        self,
        core_memory_retention: float = 0.8,
        decay_threshold: float = 0.3,
        lineage_path: Optional[str] = None,
    ):
        """Initialize the knowledge inheritor.

        Args:
            core_memory_retention: Fraction of core params to retain.
            decay_threshold: Threshold below which knowledge is deprecated.
            lineage_path: Path to persist lineage data.
        """
        self.core_memory_retention = core_memory_retention
        self.decay_threshold = decay_threshold
        self.lineage_path = Path(lineage_path) if lineage_path else None

        # Data stores
        self._lineage: Dict[str, VersionNode] = {}
        self._transfers: List[KnowledgeTransfer] = []
        self._deprecated: Set[str] = set()
        self._removed_at: Dict[str, float] = {}
        self._core_memory: Dict[str, Any] = {}

        # Statistics
        self._total_transfers: int = 0
        self._total_params_transferred: int = 0
        self._total_params_deprecated: int = 0

    # =========================================================================
    # Version Management
    # =========================================================================

    def register_version(
        self,
        version: str,
        parent: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        score: float = 0.0,
        notes: str = "",
    ) -> VersionNode:
        """Register a new version in the lineage.

        Args:
            version: Version string.
            parent: Parent version (for inheritance).
            params: Initial parameters.
            score: Performance score.
            notes: Description.

        Returns:
            The created VersionNode.
        """
        node = VersionNode(
            version=version,
            parent=parent,
            params=params or {},
            score=score,
            notes=notes,
        )

        self._lineage[version] = node

        # Update parent's children
        if parent and parent in self._lineage:
            self._lineage[parent].children.append(version)

        # Auto-inherit from parent if available
        if parent and parent in self._lineage:
            self._auto_inherit(parent, version)

        return node

    def _auto_inherit(self, parent_version: str, child_version: str) -> None:
        """Automatically inherit core knowledge from parent.

        Args:
            parent_version: Source version.
            child_version: Target version.
        """
        parent = self._lineage.get(parent_version)
        child = self._lineage.get(child_version)
        if not parent or not child:
            return

        transferred = []
        deprecated = []

        # Inherit params that are not deprecated
        for key, value in parent.params.items():
            if key not in self._deprecated:
                child.params[key] = value
                transferred.append(key)
            else:
                deprecated.append(key)

        # Inherit models
        for model_name, model_data in parent.models.items():
            if model_name not in self._deprecated:
                child.models[model_name] = model_data

        # Record the transfer
        if transferred or deprecated:
            self._record_transfer(
                from_version=parent_version,
                to_version=child_version,
                transferred=transferred,
                deprecated=deprecated,
            )

    # =========================================================================
    # Knowledge Transfer
    # =========================================================================

    def inherit_params(
        self,
        from_version: str,
        to_version: str,
        params: Dict[str, Any],
        models: Optional[Dict[str, Any]] = None,
    ) -> KnowledgeTransfer:
        """Transfer parameters from one version to another.

        Args:
            from_version: Source version.
            to_version: Target version.
            params: Parameters to transfer.
            models: Optional model metadata to transfer.

        Returns:
            KnowledgeTransfer record.
        """
        transferred = []
        deprecated = []

        if to_version in self._lineage:
            target = self._lineage[to_version]
            for key, value in params.items():
                if key in self._deprecated:
                    deprecated.append(key)
                else:
                    target.params[key] = value
                    transferred.append(key)

            if models:
                for model_name, model_data in models.items():
                    if model_name not in self._deprecated:
                        target.models[model_name] = model_data

        self._total_params_transferred += len(transferred)
        self._total_params_deprecated += len(deprecated)

        return self._record_transfer(
            from_version=from_version,
            to_version=to_version,
            transferred=transferred,
            deprecated=deprecated,
        )

    def _record_transfer(
        self,
        from_version: str,
        to_version: str,
        transferred: List[str],
        deprecated: List[str],
    ) -> KnowledgeTransfer:
        """Record a knowledge transfer.

        Args:
            from_version: Source version.
            to_version: Target version.
            transferred: Transferred param names.
            deprecated: Deprecated param names.

        Returns:
            KnowledgeTransfer record.
        """
        total = len(transferred) + len(deprecated)
        success_rate = len(transferred) / total if total > 0 else 1.0

        transfer = KnowledgeTransfer(
            transfer_id=uuid.uuid4().hex[:12],
            from_version=from_version,
            to_version=to_version,
            params_transferred=transferred,
            params_deprecated=deprecated,
            success_rate=success_rate,
        )

        self._transfers.append(transfer)
        self._total_transfers += 1

        return transfer

    # =========================================================================
    # Deprecation Management
    # =========================================================================

    def deprecate_knowledge(
        self,
        key: str,
        reason: str = "",
    ) -> None:
        """Mark a knowledge item as deprecated.

        Args:
            key: Knowledge key to deprecate.
            reason: Why it's being deprecated.
        """
        self._deprecated.add(key)
        self._removed_at[key] = time.time()

        # Also remove from core memory
        if key in self._core_memory:
            del self._core_memory[key]

    def is_deprecated(self, key: str) -> bool:
        """Check if a knowledge item is deprecated.

        Args:
            key: Knowledge key.

        Returns:
            True if deprecated.
        """
        return key in self._deprecated

    def get_deprecated_count(self) -> int:
        """Get count of deprecated items.

        Returns:
            Number of deprecated knowledge items.
        """
        return len(self._deprecated)

    def cleanup_deprecated(self, max_age_days: float = 30.0) -> int:
        """Remove deprecated items older than max_age_days.

        Args:
            max_age_days: Maximum age in days.

        Returns:
            Number of items cleaned up.
        """
        now = time.time()
        max_age_seconds = max_age_days * 86400
        removed = 0

        for key in list(self._deprecated):
            removed_at = self._removed_at.get(key, 0)
            if now - removed_at > max_age_seconds:
                self._deprecated.discard(key)
                del self._removed_at[key]
                removed += 1

        return removed

    # =========================================================================
    # Core Memory
    # =========================================================================

    def set_core_memory(self, key: str, value: Any) -> None:
        """Set a core memory item (never deprecated unless explicitly).

        Args:
            key: Memory key.
            value: Memory value.
        """
        self._core_memory[key] = value

    def get_core_memory(self, key: str, default: Any = None) -> Any:
        """Get a core memory item.

        Args:
            key: Memory key.
            default: Default if not found.

        Returns:
            Memory value or default.
        """
        return self._core_memory.get(key, default)

    def get_core_memory_snapshot(self) -> Dict[str, Any]:
        """Get all core memory items.

        Returns:
            Dict of core memory.
        """
        return dict(self._core_memory)

    def apply_decay(self) -> List[str]:
        """Apply decay-based deprecation to core memory.

        Items with effectiveness below decay_threshold are deprecated.

        Returns:
            List of deprecated keys.
        """
        deprecated = []
        for key, value in list(self._core_memory.items()):
            if isinstance(value, dict):
                effectiveness = value.get("effectiveness", 1.0)
                if effectiveness < self.decay_threshold:
                    self.deprecate_knowledge(key, f"Effectiveness {effectiveness:.2f} below threshold")
                    deprecated.append(key)
        return deprecated

    # =========================================================================
    # Lineage Analysis
    # =========================================================================

    def get_lineage(self) -> Dict[str, Any]:
        """Get the full lineage tree.

        Returns:
            Dict with version tree data.
        """
        return {
            version: {
                "parent": node.parent,
                "children": node.children,
                "created_at": node.created_at,
                "param_count": len(node.params),
                "model_count": len(node.models),
                "score": node.score,
                "notes": node.notes,
            }
            for version, node in self._lineage.items()
        }

    def get_inheritance_rate(self) -> float:
        """Calculate the overall inheritance success rate.

        Returns:
            Inheritance rate (0.0 - 1.0).
        """
        if not self._transfers:
            return 0.0
        return sum(t.success_rate for t in self._transfers) / len(self._transfers)

    def get_version_chain(self, version: str) -> List[str]:
        """Get the ancestor chain for a version.

        Args:
            version: Target version.

        Returns:
            List of versions from root to target.
        """
        chain = []
        current = version
        while current and current in self._lineage:
            chain.insert(0, current)
            current = self._lineage[current].parent
        return chain

    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive inheritance statistics.

        Returns:
            Dict with inheritance metrics.
        """
        return {
            "total_versions": len(self._lineage),
            "total_transfers": self._total_transfers,
            "total_params_transferred": self._total_params_transferred,
            "total_params_deprecated": self._total_params_deprecated,
            "deprecated_count": len(self._deprecated),
            "core_memory_size": len(self._core_memory),
            "inheritance_rate": round(self.get_inheritance_rate(), 4),
            "latest_transfer": (
                self._transfers[-1].transfer_id if self._transfers else None
            ),
        }

    # =========================================================================
    # Persistence
    # =========================================================================

    def save_lineage(self) -> bool:
        """Save lineage data to disk.

        Returns:
            True if save succeeded.
        """
        if not self.lineage_path:
            return False

        try:
            self.lineage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "saved_at": time.time(),
                "lineage": {
                    version: {
                        "parent": node.parent,
                        "children": node.children,
                        "created_at": node.created_at,
                        "params": node.params,
                        "models": node.models,
                        "score": node.score,
                        "notes": node.notes,
                    }
                    for version, node in self._lineage.items()
                },
                "transfers": [
                    {
                        "transfer_id": t.transfer_id,
                        "from_version": t.from_version,
                        "to_version": t.to_version,
                        "params_transferred": t.params_transferred,
                        "params_deprecated": t.params_deprecated,
                        "success_rate": t.success_rate,
                        "timestamp": t.timestamp,
                        "notes": t.notes,
                    }
                    for t in self._transfers
                ],
                "deprecated": list(self._deprecated),
                "core_memory": self._core_memory,
                "stats": self.get_statistics(),
            }
            with open(self.lineage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def load_lineage(self) -> bool:
        """Load lineage data from disk.

        Returns:
            True if load succeeded.
        """
        if not self.lineage_path or not self.lineage_path.exists():
            return False

        try:
            with open(self.lineage_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Restore lineage
            self._lineage = {}
            for version, node_data in data.get("lineage", {}).items():
                self._lineage[version] = VersionNode(
                    version=version,
                    parent=node_data.get("parent"),
                    children=node_data.get("children", []),
                    created_at=node_data.get("created_at", time.time()),
                    params=node_data.get("params", {}),
                    models=node_data.get("models", {}),
                    score=node_data.get("score", 0.0),
                    notes=node_data.get("notes", ""),
                )

            # Restore transfers
            self._transfers = [
                KnowledgeTransfer(
                    transfer_id=t["transfer_id"],
                    from_version=t["from_version"],
                    to_version=t["to_version"],
                    params_transferred=t.get("params_transferred", []),
                    params_deprecated=t.get("params_deprecated", []),
                    success_rate=t.get("success_rate", 0.0),
                    timestamp=t.get("timestamp", time.time()),
                    notes=t.get("notes", ""),
                )
                for t in data.get("transfers", [])
            ]

            # Restore deprecated
            self._deprecated = set(data.get("deprecated", []))
            self._core_memory = data.get("core_memory", {})

            return True
        except Exception:
            return False

    def reset(self) -> None:
        """Reset all data."""
        self._lineage.clear()
        self._transfers.clear()
        self._deprecated.clear()
        self._removed_at.clear()
        self._core_memory.clear()
        self._total_transfers = 0
        self._total_params_transferred = 0
        self._total_params_deprecated = 0