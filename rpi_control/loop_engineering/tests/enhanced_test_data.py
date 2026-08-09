"""
Enhanced Test Data Generator - Comprehensive test data for all evaluation dimensions.

Generates test data covering:
1. End-to-End Latency: Per-agent and per-operation timing profiles
2. Interaction Efficiency: Agent call patterns, tool usage, redundancy patterns
3. Harness Quality: Context compression, history summarization metrics
4. State Management: Context health, decay detection, persistence scenarios
5. Multi-Model Coordination: MCP protocol simulation, async communication
6. Skill Evolution: Extraction patterns, reuse scenarios, effectiveness data
7. Knowledge Inheritance: Cross-version transfer, deprecation patterns
8. Edge Cases: Boundary conditions, adversarial inputs, recovery scenarios
9. RPi Compatibility: Hardware interface metrics, ARM-specific benchmarks

Usage:
    python -m rpi_control.loop_engineering.tests.enhanced_test_data
"""

import json
import math
import random
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class LatencyProfile:
    """Per-agent latency profile for benchmarking."""
    agent_name: str
    p50_ms: float
    p95_ms: float
    p99_ms: float
    avg_ms: float
    min_ms: float
    max_ms: float
    std_ms: float
    samples: List[float] = field(default_factory=list)


@dataclass
class InteractionPattern:
    """Agent interaction pattern for efficiency testing."""
    task_id: str
    caller: str
    callee: str
    interaction_type: str  # 'agent_call', 'tool_call', 'state_query'
    context_size: int
    duration_ms: float
    is_redundant: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextHealthSample:
    """Context health tracking sample."""
    timestamp: float
    total_keys: int
    critical_keys_present: int
    decay_detected: bool
    compressed: bool
    persistence_success: bool
    snapshot_count: int


@dataclass
class SkillEvolutionSample:
    """Skill evolution tracking sample."""
    skill_name: str
    extraction_round: int
    effectiveness: float
    reuse_count: int
    is_meta_skill: bool
    parent_skills: List[str] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeTransferSample:
    """Knowledge inheritance tracking sample."""
    from_version: str
    to_version: str
    params_transferred: int
    params_deprecated: int
    success_rate: float
    core_memory_retained: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class RPiBenchmarkSample:
    """Raspberry Pi hardware benchmark sample."""
    metric_name: str
    value: float
    unit: str
    rpi_model: str
    is_compatible: bool
    threshold: float
    notes: str = ""


# =============================================================================
# Enhanced Test Data Generator
# =============================================================================

class EnhancedTestDataGenerator:
    """Generates comprehensive test data for all evaluation dimensions.

    Covers 8 major dimensions with realistic data distributions:
    1. End-to-End Latency
    2. Interaction Efficiency
    3. Harness Quality (Context Management)
    4. State Management & Context Health
    5. Multi-Model Coordination
    6. Skill Evolution
    7. Knowledge Inheritance
    8. RPi Compatibility
    """

    # Agent definitions with realistic latency profiles
    AGENTS = {
        "orchestrator": {"base_latency": 2.5, "std": 0.8, "weight": 0.10},
        "motion_agent": {"base_latency": 4.2, "std": 1.5, "weight": 0.20},
        "vision_agent": {"base_latency": 5.6, "std": 2.0, "weight": 0.25},
        "safety_agent": {"base_latency": 1.8, "std": 0.5, "weight": 0.10},
        "quality_agent": {"base_latency": 3.1, "std": 1.0, "weight": 0.15},
        "sampling_agent": {"base_latency": 3.8, "std": 1.2, "weight": 0.20},
    }

    # Interaction types
    INTERACTION_TYPES = ["agent_call", "tool_call", "state_query", "broadcast", "callback"]

    # Tool types
    TOOL_TYPES = [
        "move_to", "grab", "release", "detect_object", "read_sensor",
        "check_safety", "inspect_quality", "plan_path", "update_state",
        "query_database", "log_event", "send_alert",
    ]

    # RPi models and their specs
    RPI_MODELS = {
        "RPi 5": {"cpu": "Cortex-A76", "ram_mb": 8192, "nn_inference_ms": 12.5, "gpio_khz": 5000},
        "RPi 4B": {"cpu": "Cortex-A72", "ram_mb": 4096, "nn_inference_ms": 28.3, "gpio_khz": 3000},
        "RPi 3B+": {"cpu": "Cortex-A53", "ram_mb": 1024, "nn_inference_ms": 85.7, "gpio_khz": 1000},
        "RPi Zero 2W": {"cpu": "Cortex-A53", "ram_mb": 512, "nn_inference_ms": 120.0, "gpio_khz": 500},
    }

    def __init__(self, seed: int = 42, output_dir: str = "reports/test_data"):
        """Initialize the enhanced test data generator.

        Args:
            seed: Random seed for reproducibility.
            output_dir: Output directory for generated data.
        """
        self.seed = seed
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        random.seed(seed)
        np.random.seed(seed)

    # =========================================================================
    # 1. End-to-End Latency Data
    # =========================================================================

    def generate_latency_profiles(
        self,
        num_tasks: int = 100,
        num_samples_per_agent: int = 200,
    ) -> Dict[str, Any]:
        """Generate realistic end-to-end latency profiles.

        Creates per-agent latency distributions with realistic noise patterns,
        including occasional outliers (p99 behavior).

        Args:
            num_tasks: Number of simulated tasks.
            num_samples_per_agent: Latency samples per agent.

        Returns:
            Dict with latency profiles and task-level metrics.
        """
        print(f"  Generating latency profiles ({num_tasks} tasks, "
              f"{num_samples_per_agent} samples/agent)...")

        profiles = {}
        task_latencies = []

        for agent_name, config in self.AGENTS.items():
            base = config["base_latency"]
            std = config["std"]

            # Generate samples: log-normal distribution for realistic tail behavior
            samples = np.random.lognormal(
                mean=math.log(base),
                sigma=std / base,
                size=num_samples_per_agent,
            )

            # Add occasional outliers (p99 behavior)
            outlier_mask = np.random.random(num_samples_per_agent) < 0.01
            samples[outlier_mask] *= np.random.uniform(3, 8, sum(outlier_mask))

            samples_list = sorted(samples.tolist())

            profiles[agent_name] = LatencyProfile(
                agent_name=agent_name,
                p50_ms=float(np.percentile(samples, 50)),
                p95_ms=float(np.percentile(samples, 95)),
                p99_ms=float(np.percentile(samples, 99)),
                avg_ms=float(np.mean(samples)),
                min_ms=float(np.min(samples)),
                max_ms=float(np.max(samples)),
                std_ms=float(np.std(samples)),
                samples=samples_list,
            )

        # Generate task-level E2E latencies
        for _ in range(num_tasks):
            task_total = 0.0
            # Each task goes through a subset of agents
            active_agents = random.sample(list(self.AGENTS.keys()), k=random.randint(3, 6))
            for agent in active_agents:
                task_total += profiles[agent].avg_ms * random.uniform(0.8, 1.2)
            task_latencies.append(task_total)

        task_latencies.sort()

        result = {
            "profiles": {k: {
                "p50_ms": v.p50_ms, "p95_ms": v.p95_ms, "p99_ms": v.p99_ms,
                "avg_ms": v.avg_ms, "min_ms": v.min_ms, "max_ms": v.max_ms,
                "std_ms": v.std_ms,
            } for k, v in profiles.items()},
            "task_e2e": {
                "p50_ms": float(np.percentile(task_latencies, 50)),
                "p95_ms": float(np.percentile(task_latencies, 95)),
                "p99_ms": float(np.percentile(task_latencies, 99)),
                "avg_ms": float(np.mean(task_latencies)),
                "total_tasks": num_tasks,
            },
            "bottleneck_agent": max(profiles, key=lambda k: profiles[k].avg_ms),
            "throughput_tasks_per_sec": 1000.0 / float(np.median(task_latencies)),
        }

        return result

    # =========================================================================
    # 2. Interaction Efficiency Data
    # =========================================================================

    def generate_interaction_patterns(
        self,
        num_tasks: int = 50,
        max_interactions_per_task: int = 30,
        redundancy_rate: float = 0.15,
    ) -> Dict[str, Any]:
        """Generate realistic agent interaction patterns.

        Simulates agent-to-agent calls, tool usage, and redundancy patterns
        to test interaction efficiency metrics.

        Args:
            num_tasks: Number of simulated tasks.
            max_interactions_per_task: Max interactions per task.
            redundancy_rate: Fraction of interactions that are redundant.

        Returns:
            Dict with interaction patterns and efficiency metrics.
        """
        print(f"  Generating interaction patterns ({num_tasks} tasks)...")

        all_interactions = []
        task_patterns = {}
        call_matrix = defaultdict(lambda: defaultdict(int))
        redundant_count = 0

        for task_idx in range(num_tasks):
            task_id = f"task_{task_idx:04d}"
            n_interactions = random.randint(5, max_interactions_per_task)
            task_interactions = []

            # Build a realistic call chain
            agents = list(self.AGENTS.keys())
            for i in range(n_interactions):
                caller = random.choice(agents)
                callee = random.choice([a for a in agents if a != caller])

                # Determine interaction type
                if random.random() < 0.5:
                    itype = "agent_call"
                elif random.random() < 0.7:
                    itype = "tool_call"
                else:
                    itype = random.choice(["state_query", "broadcast", "callback"])

                # Determine redundancy
                is_redundant = random.random() < redundancy_rate
                if is_redundant:
                    redundant_count += 1

                interaction = InteractionPattern(
                    task_id=task_id,
                    caller=caller,
                    callee=callee if itype != "tool_call" else random.choice(self.TOOL_TYPES),
                    interaction_type=itype,
                    context_size=random.randint(3, 25),
                    duration_ms=random.uniform(0.5, 15.0),
                    is_redundant=is_redundant,
                    metadata={
                        "step": i,
                        "priority": random.choice(["high", "medium", "low"]),
                    },
                )
                task_interactions.append(interaction)
                all_interactions.append(interaction)
                call_matrix[caller][callee] += 1

            task_patterns[task_id] = {
                "total_interactions": n_interactions,
                "redundant": sum(1 for x in task_interactions if x.is_redundant),
                "types": {
                    t: sum(1 for x in task_interactions if x.interaction_type == t)
                    for t in self.INTERACTION_TYPES
                },
            }

        # Compute efficiency metrics
        total = len(all_interactions)
        avg_per_task = total / num_tasks
        avg_context = np.mean([x.context_size for x in all_interactions])

        result = {
            "total_interactions": total,
            "avg_interactions_per_task": round(avg_per_task, 2),
            "total_redundant": redundant_count,
            "redundancy_rate": round(redundant_count / total, 4) if total > 0 else 0,
            "avg_context_size": round(float(avg_context), 2),
            "call_matrix": {k: dict(v) for k, v in call_matrix.items()},
            "interaction_type_distribution": {
                t: sum(1 for x in all_interactions if x.interaction_type == t)
                for t in self.INTERACTION_TYPES
            },
            "task_patterns": task_patterns,
            "efficiency_score": round(1.0 - (redundant_count / total) - (avg_context / 50), 4),
        }

        return result

    # =========================================================================
    # 3. Harness Quality & Context Management Data
    # =========================================================================

    def generate_context_health_data(
        self,
        num_snapshots: int = 100,
        decay_probability: float = 0.08,
    ) -> Dict[str, Any]:
        """Generate context health tracking data.

        Simulates context state evolution, compression events, and decay
        detection to evaluate harness quality.

        Args:
            num_snapshots: Number of context snapshots.
            decay_probability: Probability of context decay per snapshot.

        Returns:
            Dict with context health metrics.
        """
        print(f"  Generating context health data ({num_snapshots} snapshots)...")

        samples = []
        current_keys = 10
        compression_count = 0
        decay_events = 0
        persistence_failures = 0

        critical_keys = {"task_id", "current_pose", "safety_state", "error", "sampling_state"}

        for i in range(num_snapshots):
            # Simulate state growth
            current_keys += random.randint(-2, 5)
            current_keys = max(5, min(current_keys, 100))

            # Simulate compression when too many keys
            compressed = current_keys > 50
            if compressed:
                current_keys = max(10, current_keys - random.randint(20, 40))
                compression_count += 1

            # Simulate decay
            decay = random.random() < decay_probability
            if decay:
                decay_events += 1

            # Simulate persistence
            persistence_ok = random.random() > 0.05
            if not persistence_ok:
                persistence_failures += 1

            sample = ContextHealthSample(
                timestamp=time.time() + i * 0.5,
                total_keys=current_keys,
                critical_keys_present=len(critical_keys) - (1 if decay else 0),
                decay_detected=decay,
                compressed=compressed,
                persistence_success=persistence_ok,
                snapshot_count=i + 1,
            )
            samples.append(sample)

        result = {
            "total_snapshots": num_snapshots,
            "compression_count": compression_count,
            "compression_rate": round(compression_count / num_snapshots, 4),
            "decay_events": decay_events,
            "decay_rate": round(decay_events / num_snapshots, 4),
            "persistence_failures": persistence_failures,
            "persistence_success_rate": round(1.0 - persistence_failures / num_snapshots, 4),
            "avg_keys_per_snapshot": round(float(np.mean([s.total_keys for s in samples])), 2),
            "max_keys": max(s.total_keys for s in samples),
            "min_keys": min(s.total_keys for s in samples),
            "context_health_score": round(
                1.0 - (decay_events / num_snapshots) * 0.5 - (persistence_failures / num_snapshots) * 0.3
                - (compression_count / num_snapshots) * 0.2, 4
            ),
            "samples": [
                {
                    "total_keys": s.total_keys,
                    "decay": s.decay_detected,
                    "compressed": s.compressed,
                    "persist_ok": s.persistence_success,
                }
                for s in samples
            ],
        }

        return result

    # =========================================================================
    # 4. Multi-Model Coordination Data
    # =========================================================================

    def generate_mcp_coordination_data(
        self,
        num_requests: int = 200,
    ) -> Dict[str, Any]:
        """Generate multi-model coordination test data.

        Simulates MCP (Model Connection Protocol) communication patterns,
        async message passing, and coordination overhead.

        Args:
            num_requests: Number of coordination requests.

        Returns:
            Dict with coordination metrics.
        """
        print(f"  Generating MCP coordination data ({num_requests} requests)...")

        models = ["motion_model", "vision_model", "safety_model", "quality_model", "sampling_model"]
        protocols = ["mcp_v1", "mcp_v2", "rest", "grpc", "websocket"]

        requests = []
        for i in range(num_requests):
            source = random.choice(models)
            targets = random.sample([m for m in models if m != source], k=random.randint(1, 3))

            for target in targets:
                protocol = random.choice(protocols)
                # MCP protocols have lower overhead
                base_overhead = 2.0 if "mcp" in protocol else 5.0
                overhead = base_overhead * random.uniform(0.8, 1.5)

                requests.append({
                    "request_id": f"req_{i:04d}",
                    "source": source,
                    "target": target,
                    "protocol": protocol,
                    "overhead_ms": round(overhead, 2),
                    "payload_size_bytes": random.randint(256, 16384),
                    "async": random.random() > 0.3,
                    "success": random.random() > 0.05,
                })

        # Compute metrics
        mcp_requests = [r for r in requests if "mcp" in r["protocol"]]
        non_mcp_requests = [r for r in requests if "mcp" not in r["protocol"]]

        mcp_avg = np.mean([r["overhead_ms"] for r in mcp_requests]) if mcp_requests else 0
        non_mcp_avg = np.mean([r["overhead_ms"] for r in non_mcp_requests]) if non_mcp_requests else 0

        result = {
            "total_requests": len(requests),
            "mcp_requests": len(mcp_requests),
            "non_mcp_requests": len(non_mcp_requests),
            "mcp_avg_overhead_ms": round(float(mcp_avg), 2),
            "non_mcp_avg_overhead_ms": round(float(non_mcp_avg), 2),
            "overhead_reduction_pct": round((1 - mcp_avg / non_mcp_avg) * 100, 1) if non_mcp_avg > 0 else 0,
            "async_rate": round(sum(1 for r in requests if r["async"]) / len(requests), 4),
            "success_rate": round(sum(1 for r in requests if r["success"]) / len(requests), 4),
            "protocol_distribution": {
                p: sum(1 for r in requests if r["protocol"] == p)
                for p in protocols
            },
            "throughput_req_per_sec": round(1000.0 / (mcp_avg if mcp_avg > 0 else 1), 2),
        }

        return result

    # =========================================================================
    # 5. Skill Evolution Data
    # =========================================================================

    def generate_skill_evolution_data(
        self,
        num_rounds: int = 10,
        skills_per_round: int = 5,
    ) -> Dict[str, Any]:
        """Generate skill evolution tracking data.

        Simulates skill extraction, reuse, and effectiveness tracking
        across multiple optimization rounds.

        Args:
            num_rounds: Number of evolution rounds.
            skills_per_round: Skills extracted per round.

        Returns:
            Dict with skill evolution metrics.
        """
        print(f"  Generating skill evolution data ({num_rounds} rounds)...")

        all_skills = []
        skill_pool = {}  # skill_name -> current effectiveness
        meta_skills = []
        round_metrics = []

        skill_templates = [
            "move_to_approach", "move_to_retract", "grab_object", "release_object",
            "detect_color", "detect_apriltag", "check_joint_limits", "check_collision",
            "inspect_surface", "inspect_dimension", "plan_grid", "plan_adaptive",
            "optimize_path", "calibrate_sensor", "validate_pose", "recover_from_error",
            "batch_detect", "parallel_move", "safe_approach", "quick_inspect",
        ]

        for round_num in range(1, num_rounds + 1):
            round_skills = []

            for _ in range(skills_per_round):
                # Either extract a new skill or evolve an existing one
                if random.random() < 0.4 and skill_pool:
                    # Evolve existing skill
                    base_name = random.choice(list(skill_pool.keys()))
                    evolved_name = f"{base_name}_v{round_num}"
                    base_effectiveness = skill_pool[base_name]
                    # Evolution improves effectiveness
                    improvement = random.uniform(0.02, 0.15)
                    new_effectiveness = min(0.99, base_effectiveness + improvement)
                else:
                    # New skill
                    evolved_name = random.choice(skill_templates)
                    new_effectiveness = random.uniform(0.5, 0.85)

                is_meta = random.random() < 0.15  # 15% chance of meta-skill

                skill = SkillEvolutionSample(
                    skill_name=evolved_name,
                    extraction_round=round_num,
                    effectiveness=new_effectiveness,
                    reuse_count=random.randint(0, 20),
                    is_meta_skill=is_meta,
                    parent_skills=[random.choice(list(skill_pool.keys()))]
                        if skill_pool and random.random() < 0.5 else [],
                    params={"confidence": random.uniform(0.6, 0.95)},
                )
                round_skills.append(skill)
                all_skills.append(skill)
                skill_pool[evolved_name] = new_effectiveness

                if is_meta:
                    meta_skills.append(skill)

            round_metrics.append({
                "round": round_num,
                "skills_extracted": len(round_skills),
                "meta_skills": sum(1 for s in round_skills if s.is_meta_skill),
                "avg_effectiveness": round(float(np.mean([s.effectiveness for s in round_skills])), 4),
                "avg_reuse": round(float(np.mean([s.reuse_count for s in round_skills])), 2),
            })

        # Compute overall metrics
        all_effectiveness = [s.effectiveness for s in all_skills]
        meta_effectiveness = [s.effectiveness for s in meta_skills]

        result = {
            "total_skills": len(all_skills),
            "total_meta_skills": len(meta_skills),
            "meta_skill_ratio": round(len(meta_skills) / len(all_skills), 4) if all_skills else 0,
            "avg_effectiveness": round(float(np.mean(all_effectiveness)), 4),
            "meta_avg_effectiveness": round(float(np.mean(meta_effectiveness)), 4) if meta_effectiveness else 0,
            "effectiveness_trend": [m["avg_effectiveness"] for m in round_metrics],
            "reuse_trend": [m["avg_reuse"] for m in round_metrics],
            "round_metrics": round_metrics,
            "skill_evolution_rate": round(
                (round_metrics[-1]["avg_effectiveness"] - round_metrics[0]["avg_effectiveness"])
                / round_metrics[0]["avg_effectiveness"] * 100, 2
            ) if round_metrics and round_metrics[0]["avg_effectiveness"] > 0 else 0,
        }

        return result

    # =========================================================================
    # 6. Knowledge Inheritance Data
    # =========================================================================

    def generate_knowledge_inheritance_data(
        self,
        num_versions: int = 8,
        params_per_version: int = 50,
    ) -> Dict[str, Any]:
        """Generate knowledge inheritance tracking data.

        Simulates cross-version knowledge transfer, deprecation, and
        core memory retention.

        Args:
            num_versions: Number of versions to simulate.
            params_per_version: Parameters per version.

        Returns:
            Dict with inheritance metrics.
        """
        print(f"  Generating knowledge inheritance data ({num_versions} versions)...")

        versions = [f"v{i}.{j}.{k}" for i in range(1, 3) for j in range(0, 4) for k in range(0, 2)]
        versions = versions[:num_versions]

        transfers = []
        all_params = set()
        deprecated_params = set()
        core_memory = {}

        for i in range(1, len(versions)):
            from_v = versions[i - 1]
            to_v = versions[i]

            # Generate new params each version
            new_params = {f"param_{j:03d}" for j in range(i * 10, (i + 1) * 10)}
            all_params |= new_params

            # Deprecate some old params
            if i > 2:
                to_deprecate = random.sample(
                    list(all_params - deprecated_params),
                    k=min(3, len(all_params - deprecated_params)),
                )
                deprecated_params |= set(to_deprecate)

            # Core memory retention
            retained = params_per_version - len(deprecated_params)
            core_memory_retained = retained / params_per_version

            transfer = KnowledgeTransferSample(
                from_version=from_v,
                to_version=to_v,
                params_transferred=retained,
                params_deprecated=len(deprecated_params),
                success_rate=round(retained / params_per_version, 4),
                core_memory_retained=round(core_memory_retained, 4),
            )
            transfers.append(transfer)

        # Compute metrics
        avg_success = float(np.mean([t.success_rate for t in transfers]))
        avg_retention = float(np.mean([t.core_memory_retained for t in transfers]))

        result = {
            "total_versions": num_versions,
            "total_transfers": len(transfers),
            "total_params_deprecated": len(deprecated_params),
            "avg_transfer_success_rate": round(avg_success, 4),
            "avg_core_memory_retention": round(avg_retention, 4),
            "catastrophic_forgetting_rate": round(1.0 - avg_retention, 4),
            "inheritance_health_score": round(avg_success * 0.6 + avg_retention * 0.4, 4),
            "transfers": [
                {
                    "from": t.from_version,
                    "to": t.to_version,
                    "transferred": t.params_transferred,
                    "deprecated": t.params_deprecated,
                    "success_rate": t.success_rate,
                    "retention": t.core_memory_retained,
                }
                for t in transfers
            ],
            "version_lineage": {
                "versions": versions,
                "deprecated_count": len(deprecated_params),
                "active_params": len(all_params - deprecated_params),
            },
        }

        return result

    # =========================================================================
    # 7. Edge Case & Robustness Data
    # =========================================================================

    def generate_edge_case_data(self) -> Dict[str, Any]:
        """Generate edge case and robustness test data.

        Covers 7 categories of edge cases with realistic failure patterns.
        """
        print("  Generating edge case data...")

        categories = {
            "boundary": {
                "tests": 12,
                "description": "Joint limits, workspace boundaries, singularity points",
                "expected_fail_rate": 0.08,
                "recovery_possible": True,
            },
            "adversarial": {
                "tests": 8,
                "description": "Invalid inputs, None values, NaN, extreme values",
                "expected_fail_rate": 0.02,
                "recovery_possible": True,
            },
            "multi_obstacle": {
                "tests": 6,
                "description": "Multiple obstacles, narrow passages, dead ends",
                "expected_fail_rate": 0.10,
                "recovery_possible": True,
            },
            "sequential": {
                "tests": 5,
                "description": "Rapid sequential motions, cumulative errors",
                "expected_fail_rate": 0.05,
                "recovery_possible": False,
            },
            "sensor_fusion": {
                "tests": 6,
                "description": "Sensor conflict, noise, dropout, latency",
                "expected_fail_rate": 0.12,
                "recovery_possible": True,
            },
            "state_corruption": {
                "tests": 5,
                "description": "State corruption, memory errors, race conditions",
                "expected_fail_rate": 0.03,
                "recovery_possible": True,
            },
            "recovery": {
                "tests": 5,
                "description": "Error recovery, rollback, checkpoint restore",
                "expected_fail_rate": 0.01,
                "recovery_possible": True,
            },
        }

        test_results = []
        for category, info in categories.items():
            for test_idx in range(info["tests"]):
                # Simulate test execution
                passed = random.random() > info["expected_fail_rate"]
                recovery_needed = not passed and info["recovery_possible"]
                recovery_successful = recovery_needed and random.random() > 0.2

                test_results.append({
                    "test_id": f"{category}_{test_idx:02d}",
                    "category": category,
                    "passed": passed,
                    "recovery_needed": recovery_needed,
                    "recovery_successful": recovery_successful,
                    "duration_ms": random.uniform(1.0, 50.0),
                    "error_message": "" if passed else f"Simulated {category} failure",
                })

        total = len(test_results)
        passed = sum(1 for t in test_results if t["passed"])
        recovered = sum(1 for t in test_results if t.get("recovery_successful"))

        result = {
            "total_tests": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": round(passed / total, 4),
            "recovered": recovered,
            "recovery_rate": round(recovered / (total - passed), 4) if total > passed else 1.0,
            "robustness_score": round((passed + recovered) / total, 4),
            "category_breakdown": {
                cat: {
                    "tests": info["tests"],
                    "passed": sum(1 for t in test_results if t["category"] == cat and t["passed"]),
                    "recovered": sum(1 for t in test_results
                                   if t["category"] == cat and t.get("recovery_successful")),
                }
                for cat, info in categories.items()
            },
            "test_results": test_results,
        }

        return result

    # =========================================================================
    # 8. RPi Compatibility Data
    # =========================================================================

    def generate_rpi_benchmark_data(self) -> Dict[str, Any]:
        """Generate Raspberry Pi hardware benchmark data.

        Creates realistic hardware performance metrics for different RPi models.
        """
        print("  Generating RPi benchmark data...")

        benchmarks = []
        for model, specs in self.RPI_MODELS.items():
            # GPIO response time
            benchmarks.append(RPiBenchmarkSample(
                metric_name="gpio_response_us",
                value=1000000.0 / specs["gpio_khz"],
                unit="us",
                rpi_model=model,
                is_compatible=specs["gpio_khz"] >= 500,
                threshold=500,
                notes=f"GPIO toggle rate: {specs['gpio_khz']} kHz",
            ))

            # I2C read speed
            i2c_speed = random.uniform(80, 400) if "5" in model or "4B" in model else random.uniform(40, 100)
            benchmarks.append(RPiBenchmarkSample(
                metric_name="i2c_read_kbps",
                value=i2c_speed,
                unit="kbps",
                rpi_model=model,
                is_compatible=i2c_speed >= 50,
                threshold=50,
                notes=f"I2C bus speed: {i2c_speed:.1f} kbps",
            ))

            # NN inference time
            benchmarks.append(RPiBenchmarkSample(
                metric_name="nn_inference_ms",
                value=specs["nn_inference_ms"],
                unit="ms",
                rpi_model=model,
                is_compatible=specs["nn_inference_ms"] <= 100,
                threshold=100,
                notes=f"NN inference on {specs['cpu']}",
            ))

            # Memory available
            benchmarks.append(RPiBenchmarkSample(
                metric_name="available_ram_mb",
                value=specs["ram_mb"] * 0.7,  # 70% available
                unit="MB",
                rpi_model=model,
                is_compatible=specs["ram_mb"] >= 1024,
                threshold=1024,
                notes=f"Total RAM: {specs['ram_mb']} MB",
            ))

            # UART throughput
            uart_speed = random.uniform(900, 115200) if "5" in model else random.uniform(900, 57600)
            benchmarks.append(RPiBenchmarkSample(
                metric_name="uart_throughput_bps",
                value=uart_speed,
                unit="bps",
                rpi_model=model,
                is_compatible=True,
                threshold=9600,
                notes=f"UART throughput: {uart_speed:.0f} bps",
            ))

        # Compute per-model compatibility
        model_compat = {}
        for model in self.RPI_MODELS:
            model_benchmarks = [b for b in benchmarks if b.rpi_model == model]
            compat_count = sum(1 for b in model_benchmarks if b.is_compatible)
            model_compat[model] = {
                "total_checks": len(model_benchmarks),
                "compatible": compat_count,
                "compatibility_score": round(compat_count / len(model_benchmarks), 4),
                "recommended": compat_count == len(model_benchmarks),
                "specs": self.RPI_MODELS[model],
            }

        result = {
            "total_benchmarks": len(benchmarks),
            "models_tested": list(self.RPI_MODELS.keys()),
            "model_compatibility": model_compat,
            "recommended_model": max(
                model_compat,
                key=lambda m: model_compat[m]["compatibility_score"],
            ),
            "benchmarks": [
                {
                    "metric": b.metric_name,
                    "value": b.value,
                    "unit": b.unit,
                    "model": b.rpi_model,
                    "compatible": b.is_compatible,
                    "threshold": b.threshold,
                    "notes": b.notes,
                }
                for b in benchmarks
            ],
            "overall_rpi_compat_score": round(
                float(np.mean([m["compatibility_score"] for m in model_compat.values()])), 4
            ),
        }

        return result

    # =========================================================================
    # Generate All Data
    # =========================================================================

    def generate_all(self) -> Dict[str, Any]:
        """Generate all test data for comprehensive evaluation.

        Returns:
            Dict with all test data categories.
        """
        print("=" * 60)
        print("  ENHANCED TEST DATA GENERATION")
        print("=" * 60)

        all_data = {
            "generated_at": time.time(),
            "seed": self.seed,
            "categories": {},
        }

        # 1. Latency profiles
        print("\n[1/8] Latency Profiles")
        all_data["categories"]["latency"] = self.generate_latency_profiles(
            num_tasks=100,
            num_samples_per_agent=200,
        )

        # 2. Interaction patterns
        print("\n[2/8] Interaction Patterns")
        all_data["categories"]["interaction"] = self.generate_interaction_patterns(
            num_tasks=50,
            max_interactions_per_task=30,
            redundancy_rate=0.15,
        )

        # 3. Context health
        print("\n[3/8] Context Health")
        all_data["categories"]["context_health"] = self.generate_context_health_data(
            num_snapshots=100,
            decay_probability=0.08,
        )

        # 4. MCP coordination
        print("\n[4/8] MCP Coordination")
        all_data["categories"]["mcp_coordination"] = self.generate_mcp_coordination_data(
            num_requests=200,
        )

        # 5. Skill evolution
        print("\n[5/8] Skill Evolution")
        all_data["categories"]["skill_evolution"] = self.generate_skill_evolution_data(
            num_rounds=10,
            skills_per_round=5,
        )

        # 6. Knowledge inheritance
        print("\n[6/8] Knowledge Inheritance")
        all_data["categories"]["knowledge_inheritance"] = self.generate_knowledge_inheritance_data(
            num_versions=8,
            params_per_version=50,
        )

        # 7. Edge cases
        print("\n[7/8] Edge Cases")
        all_data["categories"]["edge_cases"] = self.generate_edge_case_data()

        # 8. RPi benchmarks
        print("\n[8/8] RPi Benchmarks")
        all_data["categories"]["rpi_benchmarks"] = self.generate_rpi_benchmark_data()

        # Compute overall quality score
        all_data["overall_quality_score"] = self._compute_overall_score(all_data)

        # Save
        self._save(all_data)

        print(f"\n{'='*60}")
        print(f"  Generated {sum(len(str(v)) for v in all_data['categories'].values()):,} bytes of test data")
        print(f"  Overall Quality Score: {all_data['overall_quality_score']:.4f}")
        print(f"{'='*60}")

        return all_data

    def _compute_overall_score(self, data: Dict[str, Any]) -> float:
        """Compute overall quality score from all categories."""
        scores = {}

        # Latency: score based on P50
        latency = data["categories"]["latency"]
        p50 = latency["task_e2e"]["p50_ms"]
        scores["latency"] = max(0.0, min(1.0, 1.0 - (p50 - 10) / 100))

        # Interaction: efficiency score
        scores["interaction"] = data["categories"]["interaction"]["efficiency_score"]

        # Context health
        scores["context"] = data["categories"]["context_health"]["context_health_score"]

        # MCP: overhead reduction
        mcp = data["categories"]["mcp_coordination"]
        scores["mcp"] = min(1.0, mcp["overhead_reduction_pct"] / 50)

        # Skill evolution
        scores["skill"] = data["categories"]["skill_evolution"]["avg_effectiveness"]

        # Knowledge inheritance
        scores["inheritance"] = data["categories"]["knowledge_inheritance"]["inheritance_health_score"]

        # Edge cases
        scores["edge"] = data["categories"]["edge_cases"]["robustness_score"]

        # RPi
        scores["rpi"] = data["categories"]["rpi_benchmarks"]["overall_rpi_compat_score"]

        weights = {
            "latency": 0.20, "interaction": 0.15, "context": 0.10,
            "mcp": 0.10, "skill": 0.15, "inheritance": 0.10,
            "edge": 0.10, "rpi": 0.10,
        }

        return round(sum(scores[k] * weights[k] for k in weights), 4)

    def _save(self, data: Dict[str, Any]) -> None:
        """Save generated data to disk."""
        filepath = self.output_dir / f"enhanced_test_data_{uuid.uuid4().hex[:8]}.json"

        # Convert to serializable format
        serializable = {
            "generated_at": data["generated_at"],
            "seed": data["seed"],
            "overall_quality_score": data["overall_quality_score"],
            "categories": data["categories"],
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2, ensure_ascii=False, default=str)

        print(f"  Saved to: {filepath}")


# =============================================================================
# Quick Runner
# =============================================================================

def generate_all_test_data(output_dir: str = "reports/test_data") -> Dict[str, Any]:
    """Generate all enhanced test data.

    Args:
        output_dir: Output directory.

    Returns:
        Dict with all test data.
    """
    generator = EnhancedTestDataGenerator(seed=42, output_dir=output_dir)
    return generator.generate_all()


if __name__ == "__main__":
    data = generate_all_test_data()
    print(f"\nFinal Overall Score: {data['overall_quality_score']:.4f}")