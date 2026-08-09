"""
Skill extraction from execution traces for the multi-agent system.

Extracts reusable operation sequences from agent execution traces, evaluates
their effectiveness, and maintains a skill library. Skills are extracted
without modifying agent parameters - they represent learned operational
patterns that can be reused in future tasks.

Key features:
1. Pattern mining: Identify recurring operation sequences from traces
2. Skill abstraction: Generalize specific sequences into reusable skills
3. Effectiveness scoring: Evaluate skill success rate over time
4. Similarity matching: Find existing skills similar to new patterns
5. Skill library management: Persist, version, and retrieve skills

Usage:
    extractor = SkillExtractor()
    extractor.add_trace(task_id, trace_data)
    skills = extractor.extract_skills()
    extractor.save_library()
"""

import hashlib
import json
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union


@dataclass
class SkillStep:
    """A single step within a skill.

    Attributes:
        agent: Agent that performs the step.
        action: Action name (e.g., 'process', 'validate', 'approach').
        params: Key parameters used in this step.
        expected_duration_ms: Expected duration based on historical data.
    """
    agent: str
    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    expected_duration_ms: float = 0.0


@dataclass
class Skill:
    """A reusable skill extracted from execution traces.

    Attributes:
        skill_id: Unique skill identifier.
        name: Human-readable skill name.
        description: What the skill does.
        steps: Ordered list of steps.
        preconditions: Conditions required before executing.
        postconditions: Expected results after execution.
        effectiveness: Success rate (0.0 - 1.0).
        reuse_count: How many times this skill has been reused.
        success_count: Number of successful executions.
        failure_count: Number of failed executions.
        source_agent: Primary agent this skill is associated with.
        version: Skill version number.
        extracted_from: Trace IDs this skill was extracted from.
        created_at: When the skill was created.
        updated_at: When the skill was last updated.
    """
    skill_id: str
    name: str
    description: str = ""
    steps: List[SkillStep] = field(default_factory=list)
    preconditions: Dict[str, Any] = field(default_factory=dict)
    postconditions: Dict[str, Any] = field(default_factory=dict)
    effectiveness: float = 0.0
    reuse_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    source_agent: str = ""
    version: int = 1
    extracted_from: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize skill to dict."""
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "steps": [
                {
                    "agent": s.agent,
                    "action": s.action,
                    "params": s.params,
                    "expected_duration_ms": s.expected_duration_ms,
                }
                for s in self.steps
            ],
            "preconditions": self.preconditions,
            "postconditions": self.postconditions,
            "effectiveness": self.effectiveness,
            "reuse_count": self.reuse_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "source_agent": self.source_agent,
            "version": self.version,
            "extracted_from": self.extracted_from,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Skill":
        """Deserialize skill from dict."""
        steps = [
            SkillStep(
                agent=s["agent"],
                action=s["action"],
                params=s.get("params", {}),
                expected_duration_ms=s.get("expected_duration_ms", 0.0),
            )
            for s in data.get("steps", [])
        ]
        return cls(
            skill_id=data["skill_id"],
            name=data["name"],
            description=data.get("description", ""),
            steps=steps,
            preconditions=data.get("preconditions", {}),
            postconditions=data.get("postconditions", {}),
            effectiveness=data.get("effectiveness", 0.0),
            reuse_count=data.get("reuse_count", 0),
            success_count=data.get("success_count", 0),
            failure_count=data.get("failure_count", 0),
            source_agent=data.get("source_agent", ""),
            version=data.get("version", 1),
            extracted_from=data.get("extracted_from", []),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )

    def signature(self) -> str:
        """Generate a unique signature for this skill based on steps."""
        parts = [f"{s.agent}:{s.action}" for s in self.steps]
        return hashlib.md5("|".join(parts).encode()).hexdigest()[:12]

    def update_effectiveness(self) -> None:
        """Recalculate effectiveness based on success/failure counts."""
        total = self.success_count + self.failure_count
        if total > 0:
            self.effectiveness = self.success_count / total
        self.updated_at = time.time()


# =============================================================================
# Skill Extractor
# =============================================================================


class SkillExtractor:
    """Extracts reusable skills from agent execution traces.

    Analyzes execution traces to identify recurring operation patterns,
    abstracts them into skills, and manages a skill library for reuse.

    Attributes:
        _traces: Collected execution traces keyed by task_id.
        _skills: Extracted skills library keyed by skill_id.
        _patterns: Intermediate operation patterns being analyzed.
        min_reuse_threshold: Minimum times a pattern must appear to become a skill.
        similarity_threshold: Threshold for matching similar skills.
        library_path: Path to persist the skill library.
    """

    def __init__(
        self,
        min_reuse_threshold: int = 2,
        similarity_threshold: float = 0.7,
        library_path: Optional[str] = None,
    ):
        """Initialize the skill extractor.

        Args:
            min_reuse_threshold: Min occurrences for a pattern to become a skill.
            similarity_threshold: Threshold for matching similar skills.
            library_path: Path to persist the skill library.
        """
        self.min_reuse_threshold = min_reuse_threshold
        self.similarity_threshold = similarity_threshold
        self.library_path = Path(library_path) if library_path else None

        # Data stores
        self._traces: Dict[str, List[Dict[str, Any]]] = {}
        self._skills: Dict[str, Skill] = {}
        self._patterns: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        # Statistics
        self._skills_extracted: int = 0
        self._skills_reused: int = 0
        self._skill_executions: List[Dict[str, Any]] = []

    # =========================================================================
    # Trace Management
    # =========================================================================

    def add_trace(
        self,
        task_id: str,
        trace_data: List[Dict[str, Any]],
    ) -> None:
        """Add an execution trace for analysis.

        Args:
            task_id: Unique task identifier.
            trace_data: List of trace entries with agent, action, params, etc.
        """
        self._traces[task_id] = trace_data

        # Extract raw patterns from trace
        patterns = self._extract_patterns(trace_data)
        for pattern in patterns:
            sig = self._pattern_signature(pattern)
            self._patterns[sig].append({
                "task_id": task_id,
                "pattern": pattern,
                "timestamp": time.time(),
            })

    def _extract_patterns(
        self,
        trace_data: List[Dict[str, Any]],
    ) -> List[List[Dict[str, Any]]]:
        """Extract operation patterns from a trace.

        Finds consecutive sequences of operations that form meaningful
        sub-tasks. Uses a sliding window approach.

        Args:
            trace_data: Raw trace data.

        Returns:
            List of pattern segments (each is a list of operations).
        """
        if len(trace_data) < 2:
            return []

        patterns = []
        # Extract patterns of length 2-5
        for window_size in range(2, min(6, len(trace_data) + 1)):
            for i in range(len(trace_data) - window_size + 1):
                segment = trace_data[i:i + window_size]
                patterns.append(segment)

        return patterns

    def _pattern_signature(self, pattern: List[Dict[str, Any]]) -> str:
        """Generate a signature for a pattern.

        Args:
            pattern: List of operations.

        Returns:
            Signature string.
        """
        parts = []
        for op in pattern:
            agent = op.get("agent", op.get("caller", "unknown"))
            action = op.get("action", op.get("operation", "unknown"))
            parts.append(f"{agent}:{action}")

        return hashlib.md5("|".join(parts).encode()).hexdigest()[:12]

    # =========================================================================
    # Skill Extraction
    # =========================================================================

    def extract_skills(self) -> List[Skill]:
        """Extract skills from collected patterns.

        Returns:
            List of newly extracted skills.
        """
        new_skills = []

        for sig, occurrences in self._patterns.items():
            # Only extract if pattern appears enough times
            if len(occurrences) < self.min_reuse_threshold:
                continue

            # Check if this pattern already exists as a skill
            existing = self._find_similar_skill(sig, occurrences)
            if existing:
                # Update existing skill
                existing.reuse_count += 1
                existing.extracted_from.append(occurrences[-1]["task_id"])
                existing.updated_at = time.time()
                self._skills_reused += 1
                continue

            # Create new skill
            pattern = occurrences[0]["pattern"]
            skill = self._create_skill_from_pattern(sig, pattern, occurrences)
            self._skills[skill.skill_id] = skill
            new_skills.append(skill)
            self._skills_extracted += 1

        return new_skills

    def _create_skill_from_pattern(
        self,
        sig: str,
        pattern: List[Dict[str, Any]],
        occurrences: List[Dict[str, Any]],
    ) -> Skill:
        """Create a Skill from a recurring pattern.

        Args:
            sig: Pattern signature.
            pattern: The pattern operations.
            occurrences: All occurrences of this pattern.

        Returns:
            New Skill instance.
        """
        steps = []
        for op in pattern:
            agent = op.get("agent", op.get("caller", "unknown"))
            action = op.get("action", op.get("operation", "unknown"))
            params = op.get("params", op.get("metadata", {}))

            # Calculate expected duration from historical data
            durations = []
            for occ in occurrences:
                for occ_op in occ["pattern"]:
                    occ_agent = occ_op.get("agent", occ_op.get("caller", ""))
                    occ_action = occ_op.get("action", occ_op.get("operation", ""))
                    if occ_agent == agent and occ_action == action:
                        dur = occ_op.get("duration_ms", 0)
                        if dur > 0:
                            durations.append(dur)

            avg_duration = sum(durations) / len(durations) if durations else 0.0

            steps.append(SkillStep(
                agent=agent,
                action=action,
                params=params,
                expected_duration_ms=round(avg_duration, 2),
            ))

        # Generate name from steps
        name_parts = [f"{s.agent}_{s.action}" for s in steps[:3]]
        name = "->".join(name_parts)

        skill = Skill(
            skill_id=f"skill_{sig}",
            name=name,
            description=f"Automatically extracted skill: {name}",
            steps=steps,
            source_agent=steps[0].agent if steps else "",
            reuse_count=1,
            success_count=0,
            failure_count=0,
            extracted_from=[o["task_id"] for o in occurrences],
        )
        skill.update_effectiveness()

        return skill

    def _find_similar_skill(
        self,
        sig: str,
        occurrences: List[Dict[str, Any]],
    ) -> Optional[Skill]:
        """Find an existing skill similar to the given pattern.

        Args:
            sig: Pattern signature.
            occurrences: Pattern occurrences.

        Returns:
            Matching Skill or None.
        """
        # Exact match by signature
        if sig in self._skills:
            return self._skills[sig]

        # Fuzzy match by step similarity
        pattern = occurrences[0]["pattern"]
        pattern_agents = {
            op.get("agent", op.get("caller", ""))
            for op in pattern
        }

        for skill in self._skills.values():
            skill_agents = {s.agent for s in skill.steps}
            if not pattern_agents or not skill_agents:
                continue

            # Jaccard similarity
            intersection = pattern_agents & skill_agents
            union = pattern_agents | skill_agents
            similarity = len(intersection) / len(union) if union else 0.0

            if similarity >= self.similarity_threshold:
                return skill

        return None

    # =========================================================================
    # Skill Management
    # =========================================================================

    def record_skill_execution(
        self,
        skill_id: str,
        success: bool,
        duration_ms: float = 0.0,
    ) -> None:
        """Record a skill execution result.

        Args:
            skill_id: Skill identifier.
            success: Whether execution succeeded.
            duration_ms: Execution duration.
        """
        if skill_id in self._skills:
            skill = self._skills[skill_id]
            if success:
                skill.success_count += 1
            else:
                skill.failure_count += 1
            skill.update_effectiveness()

        self._skill_executions.append({
            "skill_id": skill_id,
            "success": success,
            "duration_ms": duration_ms,
            "timestamp": time.time(),
        })

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """Get a skill by ID.

        Args:
            skill_id: Skill identifier.

        Returns:
            Skill or None.
        """
        return self._skills.get(skill_id)

    def get_skills_by_agent(self, agent_name: str) -> List[Skill]:
        """Get all skills associated with an agent.

        Args:
            agent_name: Agent name to filter by.

        Returns:
            List of matching skills.
        """
        return [
            s for s in self._skills.values()
            if s.source_agent == agent_name or
            any(step.agent == agent_name for step in s.steps)
        ]

    def get_top_skills(self, n: int = 5) -> List[Skill]:
        """Get the most effective skills.

        Args:
            n: Number of skills to return.

        Returns:
            List of top skills sorted by effectiveness * reuse_count.
        """
        return sorted(
            self._skills.values(),
            key=lambda s: s.effectiveness * s.reuse_count,
            reverse=True,
        )[:n]

    def get_skill_statistics(self) -> Dict[str, Any]:
        """Get skill extraction statistics.

        Returns:
            Dict with skill metrics.
        """
        total_skills = len(self._skills)
        avg_effectiveness = (
            sum(s.effectiveness for s in self._skills.values()) / total_skills
            if total_skills > 0 else 0.0
        )
        total_reuses = sum(s.reuse_count for s in self._skills.values())
        total_executions = len(self._skill_executions)
        successful_executions = sum(
            1 for e in self._skill_executions if e["success"]
        )

        return {
            "skills_extracted": self._skills_extracted,
            "total_skills": total_skills,
            "skills_reused": self._skills_reused,
            "reuse_rate": (
                self._skills_reused / self._skills_extracted
                if self._skills_extracted > 0 else 0.0
            ),
            "skill_effectiveness": round(avg_effectiveness, 4),
            "total_reuses": total_reuses,
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "execution_success_rate": (
                successful_executions / total_executions
                if total_executions > 0 else 0.0
            ),
            "patterns_analyzed": len(self._patterns),
        }

    # =========================================================================
    # Persistence
    # =========================================================================

    def save_library(self) -> bool:
        """Save skill library to disk.

        Returns:
            True if save succeeded.
        """
        if not self.library_path:
            return False

        try:
            self.library_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "saved_at": time.time(),
                "skills": [s.to_dict() for s in self._skills.values()],
                "stats": self.get_skill_statistics(),
            }
            with open(self.library_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def load_library(self) -> bool:
        """Load skill library from disk.

        Returns:
            True if load succeeded.
        """
        if not self.library_path or not self.library_path.exists():
            return False

        try:
            with open(self.library_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._skills = {}
            for skill_data in data.get("skills", []):
                skill = Skill.from_dict(skill_data)
                self._skills[skill.skill_id] = skill

            self._skills_extracted = len(self._skills)
            return True
        except Exception:
            return False

    def reset(self) -> None:
        """Reset all data."""
        self._traces.clear()
        self._skills.clear()
        self._patterns.clear()
        self._skill_executions.clear()
        self._skills_extracted = 0
        self._skills_reused = 0