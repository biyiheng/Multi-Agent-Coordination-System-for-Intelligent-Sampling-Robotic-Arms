"""
Meta-optimizer for evolving optimization strategies.

Optimizes the optimization algorithms themselves (meta-learning). Records
which optimization strategies work best, produces "meta-skills" (rules
and prompt templates), and adapts future optimization based on past results.

Key features:
1. Strategy evaluation: Track which optimization strategies are effective
2. Meta-skill extraction: Produce rules/prompts from successful strategies
3. Adaptive feedback: Adjust optimization approach based on results
4. Strategy history: Maintain a record of tried strategies and outcomes
5. Prompt template generation: Create reusable optimization prompts

Usage:
    meta = MetaOptimizer()
    meta.record_strategy("grid_search", improvement=0.15, params={...})
    meta.evolve_strategies()
    prompts = meta.get_prompt_templates()
"""

import json
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class StrategyRecord:
    """A record of an optimization strategy execution.

    Attributes:
        strategy_id: Unique strategy identifier.
        strategy_type: Type (e.g., 'grid_search', 'bayesian', 'random').
        improvement: Improvement achieved (delta).
        params: Parameters used in this strategy.
        agent: Target agent name.
        timestamp: When executed.
        success: Whether the strategy improved the result.
        notes: Human-readable notes.
    """
    strategy_id: str
    strategy_type: str
    improvement: float = 0.0
    params: Dict[str, Any] = field(default_factory=dict)
    agent: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = False
    notes: str = ""


@dataclass
class MetaSkill:
    """A meta-skill: a learned optimization strategy.

    Attributes:
        meta_id: Unique meta-skill identifier.
        name: Human-readable name.
        strategy_type: Type of optimization strategy.
        prompt_template: Reusable prompt for optimization.
        rules: List of optimization rules.
        effectiveness: How effective this meta-skill is.
        application_count: How many times applied.
        improvement_pct: Average improvement achieved.
        created_at: When created.
        updated_at: When last updated.
    """
    meta_id: str
    name: str
    strategy_type: str = ""
    prompt_template: str = ""
    rules: List[str] = field(default_factory=list)
    effectiveness: float = 0.0
    application_count: int = 0
    improvement_pct: float = 0.0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "meta_id": self.meta_id,
            "name": self.name,
            "strategy_type": self.strategy_type,
            "prompt_template": self.prompt_template,
            "rules": self.rules,
            "effectiveness": self.effectiveness,
            "application_count": self.application_count,
            "improvement_pct": self.improvement_pct,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetaSkill":
        """Deserialize from dict."""
        return cls(
            meta_id=data["meta_id"],
            name=data["name"],
            strategy_type=data.get("strategy_type", ""),
            prompt_template=data.get("prompt_template", ""),
            rules=data.get("rules", []),
            effectiveness=data.get("effectiveness", 0.0),
            application_count=data.get("application_count", 0),
            improvement_pct=data.get("improvement_pct", 0.0),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )


# =============================================================================
# Meta-Optimizer
# =============================================================================


class MetaOptimizer:
    """Optimizes the optimization algorithms themselves.

    Records which strategies work best, evolves meta-skills (rules and
    prompts), and adapts future optimization based on past feedback.

    Attributes:
        _strategies: History of strategy executions.
        _meta_skills: Evolved meta-skills.
        _strategy_stats: Aggregated stats per strategy type.
        _improvement_history: Time series of improvements.
    """

    def __init__(
        self,
        strategy_history_size: int = 50,
        min_improvement_threshold: float = 0.05,
        meta_skill_path: Optional[str] = None,
    ):
        """Initialize the meta-optimizer.

        Args:
            strategy_history_size: Max strategy records to keep.
            min_improvement_threshold: Min improvement to qualify as meta-skill.
            meta_skill_path: Path to persist meta-skills.
        """
        self.strategy_history_size = strategy_history_size
        self.min_improvement_threshold = min_improvement_threshold
        self.meta_skill_path = Path(meta_skill_path) if meta_skill_path else None

        # Data stores
        self._strategies: List[StrategyRecord] = []
        self._meta_skills: Dict[str, MetaSkill] = {}
        self._strategy_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "total_improvement": 0.0, "successes": 0, "failures": 0}
        )
        self._improvement_history: List[float] = []

    # =========================================================================
    # Strategy Recording
    # =========================================================================

    def record_strategy(
        self,
        strategy_type: str,
        improvement: float,
        params: Optional[Dict[str, Any]] = None,
        agent: str = "",
        notes: str = "",
    ) -> StrategyRecord:
        """Record an optimization strategy execution.

        Args:
            strategy_type: Type of strategy used.
            improvement: Improvement achieved (delta).
            params: Parameters used.
            agent: Target agent.
            notes: Human-readable notes.

        Returns:
            The recorded StrategyRecord.
        """
        success = improvement > 0
        record = StrategyRecord(
            strategy_id=uuid.uuid4().hex[:12],
            strategy_type=strategy_type,
            improvement=improvement,
            params=params or {},
            agent=agent,
            success=success,
            notes=notes,
        )

        self._strategies.append(record)
        self._improvement_history.append(improvement)

        # Update strategy stats
        stats = self._strategy_stats[strategy_type]
        stats["count"] += 1
        stats["total_improvement"] += improvement
        if success:
            stats["successes"] += 1
        else:
            stats["failures"] += 1

        # Trim history
        if len(self._strategies) > self.strategy_history_size:
            self._strategies = self._strategies[-self.strategy_history_size:]

        return record

    # =========================================================================
    # Strategy Evolution
    # =========================================================================

    def evolve_strategies(self) -> List[MetaSkill]:
        """Evolve meta-skills from strategy history.

        Analyzes which strategies are most effective and creates/updates
        meta-skills accordingly.

        Returns:
            List of newly created/updated MetaSkills.
        """
        new_skills = []

        for strategy_type, stats in self._strategy_stats.items():
            if stats["count"] < 2:
                continue

            avg_improvement = (
                stats["total_improvement"] / stats["count"]
                if stats["count"] > 0 else 0.0
            )
            success_rate = (
                stats["successes"] / stats["count"]
                if stats["count"] > 0 else 0.0
            )

            # Only create meta-skill if improvement is significant
            if avg_improvement < self.min_improvement_threshold:
                continue

            meta_id = f"meta_{strategy_type}"

            if meta_id in self._meta_skills:
                # Update existing meta-skill
                skill = self._meta_skills[meta_id]
                skill.effectiveness = success_rate
                skill.improvement_pct = round(avg_improvement * 100, 2)
                skill.application_count += 1
                skill.updated_at = time.time()
            else:
                # Create new meta-skill
                skill = MetaSkill(
                    meta_id=meta_id,
                    name=f"Optimize via {strategy_type}",
                    strategy_type=strategy_type,
                    prompt_template=self._generate_prompt_template(strategy_type, avg_improvement),
                    rules=self._generate_rules(strategy_type),
                    effectiveness=success_rate,
                    application_count=1,
                    improvement_pct=round(avg_improvement * 100, 2),
                )
                self._meta_skills[meta_id] = skill
                new_skills.append(skill)

        return new_skills

    def _generate_prompt_template(
        self,
        strategy_type: str,
        avg_improvement: float,
    ) -> str:
        """Generate a prompt template for a strategy type.

        Args:
            strategy_type: Strategy type name.
            avg_improvement: Average improvement achieved.

        Returns:
            Prompt template string.
        """
        templates = {
            "grid_search": (
                f"Use grid search to optimize agent parameters. "
                f"Historical improvement: {avg_improvement*100:.1f}%. "
                "Define parameter ranges systematically and evaluate all combinations. "
                "Focus on parameters with highest sensitivity first."
            ),
            "bayesian": (
                f"Use Bayesian optimization to find optimal parameters. "
                f"Historical improvement: {avg_improvement*100:.1f}%. "
                "Use Gaussian Process prior and Expected Improvement acquisition. "
                "Start with 5 random points, then explore-exploit adaptively."
            ),
            "random_search": (
                f"Use random search for parameter exploration. "
                f"Historical improvement: {avg_improvement*100:.1f}%. "
                "Sample parameters from uniform distributions. "
                "Use at least 50 samples for reliable results."
            ),
            "gradient_descent": (
                f"Use gradient-based optimization for parameter tuning. "
                f"Historical improvement: {avg_improvement*100:.1f}%. "
                "Start with learning rate 0.01, use Adam optimizer. "
                "Monitor convergence and adjust learning rate if plateau."
            ),
        }
        return templates.get(
            strategy_type,
            f"Optimize using {strategy_type}. "
            f"Historical improvement: {avg_improvement*100:.1f}%.",
        )

    def _generate_rules(self, strategy_type: str) -> List[str]:
        """Generate optimization rules for a strategy type.

        Args:
            strategy_type: Strategy type name.

        Returns:
            List of rule strings.
        """
        strategy_records = [
            s for s in self._strategies
            if s.strategy_type == strategy_type
        ]

        rules = []

        if strategy_type == "grid_search":
            rules.append("Always define parameter bounds before grid search")
            rules.append("Use logarithmic spacing for wide-range parameters")
            rules.append("Limit grid size to avoid combinatorial explosion")

        elif strategy_type == "bayesian":
            rules.append("Normalize parameter space to [0, 1] for GP")
            rules.append("Use at least 5 initial random points")
            rules.append("Set exploration ratio based on remaining budget")

        elif strategy_type == "random_search":
            rules.append("Use uniform or log-uniform distributions")
            rules.append("Increase sample count for high-dimensional spaces")
            rules.append("Track best-so-far to avoid missing optima")

        # General rules from successful strategies
        if strategy_records:
            best_params = max(strategy_records, key=lambda s: s.improvement).params
            if best_params:
                rules.append(
                    f"Best params found: {json.dumps(best_params, default=str)[:100]}"
                )

        return rules

    # =========================================================================
    # Meta-Skill Management
    # =========================================================================

    def get_meta_skill(self, strategy_type: str) -> Optional[MetaSkill]:
        """Get a meta-skill by strategy type.

        Args:
            strategy_type: Strategy type name.

        Returns:
            MetaSkill or None.
        """
        meta_id = f"meta_{strategy_type}"
        return self._meta_skills.get(meta_id)

    def get_top_meta_skills(self, n: int = 3) -> List[MetaSkill]:
        """Get the most effective meta-skills.

        Args:
            n: Number to return.

        Returns:
            List of top MetaSkills.
        """
        return sorted(
            self._meta_skills.values(),
            key=lambda s: s.effectiveness * s.improvement_pct,
            reverse=True,
        )[:n]

    def get_prompt_templates(self) -> List[str]:
        """Get all available prompt templates.

        Returns:
            List of prompt template strings.
        """
        return [
            s.prompt_template
            for s in self._meta_skills.values()
            if s.prompt_template
        ]

    def get_best_strategy(self) -> Optional[str]:
        """Get the name of the best-performing strategy.

        Returns:
            Strategy type name or None.
        """
        if not self._strategy_stats:
            return None

        best = max(
            self._strategy_stats.items(),
            key=lambda x: (
                x[1]["total_improvement"] / x[1]["count"]
                if x[1]["count"] > 0 else 0
            ),
        )
        return best[0]

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive meta-optimization statistics.

        Returns:
            Dict with meta-optimization metrics.
        """
        total_strategies = len(self._strategies)
        successful = sum(1 for s in self._strategies if s.success)
        avg_improvement = (
            sum(s.improvement for s in self._strategies) / total_strategies
            if total_strategies > 0 else 0.0
        )

        return {
            "total_strategies": total_strategies,
            "successful_strategies": successful,
            "strategy_success_rate": (
                successful / total_strategies if total_strategies > 0 else 0.0
            ),
            "avg_improvement_pct": round(avg_improvement * 100, 2),
            "meta_skills_count": len(self._meta_skills),
            "best_strategy": self.get_best_strategy(),
            "strategy_breakdown": {
                stype: {
                    "count": stats["count"],
                    "avg_improvement": round(
                        stats["total_improvement"] / stats["count"], 4
                    ) if stats["count"] > 0 else 0,
                    "success_rate": round(
                        stats["successes"] / stats["count"], 2
                    ) if stats["count"] > 0 else 0,
                }
                for stype, stats in self._strategy_stats.items()
            },
            "improvement_trend": (
                self._improvement_history[-10:] if self._improvement_history else []
            ),
        }

    def get_convergence_analysis(self) -> Dict[str, Any]:
        """Analyze whether optimization is converging.

        Returns:
            Dict with convergence analysis.
        """
        if len(self._improvement_history) < 3:
            return {"converged": False, "reason": "Insufficient data"}

        # Check if recent improvements are trending down
        recent = self._improvement_history[-5:]
        if len(recent) >= 3:
            trend = all(
                recent[i] >= recent[i + 1]
                for i in range(len(recent) - 1)
            )
            if trend:
                return {
                    "converged": True,
                    "reason": "Improvement trend is decreasing",
                    "last_improvement": recent[-1],
                }

        # Check if improvements are below threshold
        if all(abs(imp) < self.min_improvement_threshold for imp in recent):
            return {
                "converged": True,
                "reason": f"All recent improvements below {self.min_improvement_threshold}",
                "last_improvement": recent[-1],
            }

        return {"converged": False, "reason": "Still improving"}

    # =========================================================================
    # Persistence
    # =========================================================================

    def save_meta_skills(self) -> bool:
        """Save meta-skills to disk.

        Returns:
            True if save succeeded.
        """
        if not self.meta_skill_path:
            return False

        try:
            self.meta_skill_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "saved_at": time.time(),
                "meta_skills": [s.to_dict() for s in self._meta_skills.values()],
                "strategy_stats": dict(self._strategy_stats),
                "stats": self.get_statistics(),
            }
            with open(self.meta_skill_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def load_meta_skills(self) -> bool:
        """Load meta-skills from disk.

        Returns:
            True if load succeeded.
        """
        if not self.meta_skill_path or not self.meta_skill_path.exists():
            return False

        try:
            with open(self.meta_skill_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._meta_skills = {}
            for skill_data in data.get("meta_skills", []):
                skill = MetaSkill.from_dict(skill_data)
                self._meta_skills[skill.meta_id] = skill

            self._strategy_stats = defaultdict(
                lambda: {"count": 0, "total_improvement": 0.0, "successes": 0, "failures": 0}
            )
            for stype, stats in data.get("strategy_stats", {}).items():
                self._strategy_stats[stype] = stats

            return True
        except Exception:
            return False

    def reset(self) -> None:
        """Reset all data."""
        self._strategies.clear()
        self._meta_skills.clear()
        self._strategy_stats.clear()
        self._improvement_history.clear()