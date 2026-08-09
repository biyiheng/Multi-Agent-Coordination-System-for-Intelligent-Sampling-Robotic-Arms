"""
Test data generator for Loop Engineering framework.

Generates realistic synthetic test data for:
1. Profiler latency data across different agent operations
2. Interaction tracker data with agent-to-agent calls
3. Task execution results with varying success/failure patterns
4. Context manager state snapshots
5. Skill extraction traces

The data is designed to be realistic enough to test the full evaluation
pipeline and loop engineering cycle.

Usage:
    generator = TestDataGenerator(seed=42)
    profiler_data = generator.generate_profiler_data()
    interaction_data = generator.generate_interaction_data()
    task_results = generator.generate_task_results()
"""

import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class GeneratedProfile:
    """Complete generated profile data for testing."""
    agent_profilers: Dict[str, Dict[str, Any]]
    e2e_profile: Dict[str, Any]
    interaction_stats: Dict[str, Any]
    task_results: List[Dict[str, Any]]
    context_data: Dict[str, Any]
    skill_data: Dict[str, Any]


class TestDataGenerator:
    """Generates synthetic test data for Loop Engineering testing.

    Produces realistic data across all components to enable end-to-end
    testing of the evaluation and optimization pipeline.
    """
    __test__ = False  # Not a pytest test class

    AGENTS = ["sampling", "vision", "motion", "quality", "safety", "orchestrator"]
    OPERATIONS = ["process", "validate", "initialize", "cleanup", "execute"]
    STATES = ["IDLE", "PLANNING", "APPROACHING", "DETECTING", "GRASPING",
              "LIFTING", "INSPECTING", "PLACING", "EVALUATING", "DONE"]

    def __init__(
        self,
        seed: int = 42,
        num_tasks: int = 20,
        quality_level: str = "medium",
    ):
        """Initialize the data generator.

        Args:
            seed: Random seed for reproducibility.
            num_tasks: Number of tasks to simulate.
            quality_level: Data quality level ('low', 'medium', 'high').
        """
        self.seed = seed
        self.num_tasks = num_tasks
        self.quality_level = quality_level
        random.seed(seed)

        # Quality multipliers
        self._quality_multipliers = {
            "low": {"latency": 2.0, "success_rate": 0.6, "defect_rate": 0.3},
            "medium": {"latency": 1.0, "success_rate": 0.85, "defect_rate": 0.1},
            "high": {"latency": 0.5, "success_rate": 0.95, "defect_rate": 0.02},
        }
        self._qm = self._quality_multipliers[quality_level]

    # =========================================================================
    # Profiler Data
    # =========================================================================

    def generate_profiler_data(self) -> Dict[str, Dict[str, Any]]:
        """Generate per-agent profiler statistics.

        Returns:
            Dict mapping agent_name to profiler statistics.
        """
        profiles = {}

        for agent in self.AGENTS:
            # Base latency varies by agent
            base_latency = {
                "sampling": 80.0,
                "vision": 40.0,
                "motion": 60.0,
                "quality": 30.0,
                "safety": 15.0,
                "orchestrator": 20.0,
            }.get(agent, 50.0)

            per_op = {}
            all_durations = []
            total_calls = 0

            for op in self.OPERATIONS:
                count = random.randint(10, 30)
                base = base_latency * self._qm["latency"]
                # Generate durations with some variance
                durations = sorted([
                    max(1.0, random.gauss(base, base * 0.3))
                    for _ in range(count)
                ])
                per_op[op] = {
                    "count": count,
                    "avg_ms": round(sum(durations) / len(durations), 2),
                    "min_ms": round(durations[0], 2),
                    "max_ms": round(durations[-1], 2),
                    "p50_ms": round(self._percentile(durations, 50), 2),
                    "p95_ms": round(self._percentile(durations, 95), 2),
                    "p99_ms": round(self._percentile(durations, 99), 2),
                    "total_ms": round(sum(durations), 2),
                }
                all_durations.extend(durations)
                total_calls += count

            sorted_all = sorted(all_durations)
            profiles[agent] = {
                "agent_name": agent,
                "total_calls": total_calls,
                "total_duration_ms": round(sum(sorted_all), 2),
                "avg_ms": round(sum(sorted_all) / len(sorted_all), 2) if sorted_all else 0,
                "p50_ms": round(self._percentile(sorted_all, 50), 2),
                "p95_ms": round(self._percentile(sorted_all, 95), 2),
                "p99_ms": round(self._percentile(sorted_all, 99), 2),
                "min_ms": round(sorted_all[0], 2) if sorted_all else 0,
                "max_ms": round(sorted_all[-1], 2) if sorted_all else 0,
                "per_operation": per_op,
            }

        return profiles

    def generate_e2e_profile(self) -> Dict[str, Any]:
        """Generate end-to-end profiling data.

        Returns:
            Dict with e2e report data.
        """
        task_durations = []
        state_transitions = []

        for i in range(self.num_tasks):
            # Total task duration
            base_duration = 500.0 * self._qm["latency"]
            duration = max(50.0, random.gauss(base_duration, base_duration * 0.2))
            task_durations.append(duration)

            # State transitions
            for j, state in enumerate(self.STATES[:-1]):
                next_state = self.STATES[j + 1]
                state_duration = duration / len(self.STATES) * random.uniform(0.5, 1.5)
                state_transitions.append({
                    "from": state,
                    "to": next_state,
                    "duration_ms": round(state_duration, 2),
                    "timestamp": time.time(),
                })

        sorted_durations = sorted(task_durations)

        return {
            "total_tasks": self.num_tasks,
            "total_state_transitions": len(state_transitions),
            "e2e_avg_ms": round(sum(sorted_durations) / len(sorted_durations), 2),
            "e2e_p50_ms": round(self._percentile(sorted_durations, 50), 2),
            "e2e_p95_ms": round(self._percentile(sorted_durations, 95), 2),
            "e2e_p99_ms": round(self._percentile(sorted_durations, 99), 2),
            "e2e_min_ms": round(sorted_durations[0], 2),
            "e2e_max_ms": round(sorted_durations[-1], 2),
            "state_distribution": self._compute_state_distribution(state_transitions),
            "task_details": [
                {"task_id": f"task_{i}", "duration_ms": round(d, 2)}
                for i, d in enumerate(task_durations[-10:])
            ],
        }

    def _compute_state_distribution(
        self,
        transitions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Compute state distribution from transitions."""
        dist: Dict[str, Dict[str, float]] = {}
        for t in transitions:
            state = t["from"]
            if state not in dist:
                dist[state] = {"count": 0, "total_ms": 0.0}
            dist[state]["count"] += 1
            dist[state]["total_ms"] += t["duration_ms"]

        total_ms = sum(d["total_ms"] for d in dist.values())
        for state, d in dist.items():
            d["avg_ms"] = round(d["total_ms"] / d["count"], 2) if d["count"] else 0
            d["pct"] = round(d["total_ms"] / total_ms * 100, 1) if total_ms else 0

        return dist

    # =========================================================================
    # Interaction Data
    # =========================================================================

    def generate_interaction_data(self) -> Dict[str, Any]:
        """Generate interaction tracker statistics.

        Returns:
            Dict with interaction statistics.
        """
        # agent_call patterns
        call_patterns = [
            ("orchestrator", "motion_agent"),
            ("orchestrator", "vision_agent"),
            ("orchestrator", "safety_agent"),
            ("orchestrator", "quality_agent"),
            ("orchestrator", "sampling_agent"),
            ("motion_agent", "safety_agent"),
            ("quality_agent", "vision_agent"),
        ]

        total_interactions = 0
        rounds_by_type = {"agent_call": 0, "tool_call": 0, "state_query": 0}
        agent_calls: Dict[str, Dict[str, int]] = {}
        context_sizes = []
        redundant_count = 0

        for _ in range(self.num_tasks):
            # Each task has some interactions
            num_calls = random.randint(5, 15)
            for _ in range(num_calls):
                caller, callee = random.choice(call_patterns)
                itype = random.choice(["agent_call", "agent_call", "agent_call", "tool_call", "state_query"])
                rounds_by_type[itype] += 1
                total_interactions += 1

                # Track agent calls
                if caller not in agent_calls:
                    agent_calls[caller] = {}
                agent_calls[caller][callee] = agent_calls[caller].get(callee, 0) + 1

                # Context size
                context_sizes.append(random.randint(5, 30))

                # Redundancy: some calls repeat
                if random.random() < 0.1:
                    redundant_count += 1

        return {
            "total_interactions": total_interactions,
            "rounds_per_task": round(total_interactions / self.num_tasks, 2),
            "rounds_by_type": rounds_by_type,
            "redundant_calls": redundant_count,
            "context_size_stats": {
                "avg": round(sum(context_sizes) / len(context_sizes), 1) if context_sizes else 0,
                "min": min(context_sizes) if context_sizes else 0,
                "max": max(context_sizes) if context_sizes else 0,
            },
            "dependency_graph": {
                caller: list(callees.keys())
                for caller, callees in agent_calls.items()
            },
        }

    # =========================================================================
    # Task Results
    # =========================================================================

    def generate_task_results(self) -> List[Dict[str, Any]]:
        """Generate task execution results.

        Returns:
            List of task result dicts.
        """
        results = []
        success_rate = self._qm["success_rate"]
        defect_rate = self._qm["defect_rate"]

        for i in range(self.num_tasks):
            success = random.random() < success_rate
            has_error = not success
            recovered = has_error and random.random() < 0.5
            aborted = has_error and not recovered and random.random() < 0.3

            # Quality score
            quality = random.gauss(80, 15) if success else random.gauss(30, 20)
            quality = max(0, min(100, quality))

            # Defects
            defects = []
            if random.random() < defect_rate:
                defect_types = ["scratch", "discoloration", "size_deviation", "edge_defect"]
                defects = random.sample(defect_types, random.randint(1, min(2, len(defect_types))))

            results.append({
                "task_id": f"task_{i:03d}",
                "success": success,
                "error": "TimeoutError" if has_error and not recovered else (
                    "SafetyError" if aborted else None
                ),
                "recovered": recovered,
                "aborted": aborted,
                "quality_score": round(quality, 2),
                "defects": defects,
                "quality_passed": quality >= 70 and len(defects) == 0,
                "duration_ms": random.gauss(500, 100),
            })

        return results

    # =========================================================================
    # Context Data
    # =========================================================================

    def generate_context_data(self) -> Dict[str, Any]:
        """Generate context manager health statistics.

        Returns:
            Dict with context health data.
        """
        return {
            "total_keys": random.randint(20, 50),
            "critical_keys_present": random.randint(5, 7),
            "critical_keys_total": 7,
            "missing_critical_keys": [],
            "compression_count": random.randint(0, 3),
            "decay_events": random.randint(0, 2),
            "snapshots_available": random.randint(1, 5),
            "avg_access_count": round(random.uniform(1.0, 10.0), 1),
            "avg_age_seconds": round(random.uniform(10.0, 200.0), 1),
            "persistence_success_rate": round(random.uniform(0.9, 1.0), 4),
            "state_snapshots": random.randint(1, 5),
        }

    # =========================================================================
    # Skill Data
    # =========================================================================

    def generate_skill_data(self) -> Dict[str, Any]:
        """Generate skill extraction statistics.

        Returns:
            Dict with skill data.
        """
        skills_extracted = random.randint(0, 5)
        skills_reused = skills_extracted - random.randint(0, min(2, skills_extracted))

        total_executions = random.randint(5, 20)
        successful = random.randint(
            int(total_executions * 0.6),
            total_executions,
        )

        return {
            "skills_extracted": skills_extracted,
            "total_skills": skills_extracted,
            "skills_reused": skills_reused,
            "reuse_rate": (
                skills_reused / skills_extracted
                if skills_extracted > 0 else 0.0
            ),
            "skill_effectiveness": round(random.uniform(0.5, 0.95), 4),
            "total_reuses": skills_reused,
            "total_executions": total_executions,
            "successful_executions": successful,
            "execution_success_rate": (
                successful / total_executions
                if total_executions > 0 else 0.0
            ),
            "patterns_analyzed": random.randint(10, 50),
        }

    # =========================================================================
    # Complete Dataset
    # =========================================================================

    def generate_all(self) -> GeneratedProfile:
        """Generate a complete dataset for testing.

        Returns:
            GeneratedProfile with all data.
        """
        return GeneratedProfile(
            agent_profilers=self.generate_profiler_data(),
            e2e_profile=self.generate_e2e_profile(),
            interaction_stats=self.generate_interaction_data(),
            task_results=self.generate_task_results(),
            context_data=self.generate_context_data(),
            skill_data=self.generate_skill_data(),
        )

    # =========================================================================
    # Edge Cases
    # =========================================================================

    def generate_edge_cases(self) -> List[Dict[str, Any]]:
        """Generate edge case task results for robustness testing.

        Returns:
            List of edge case result dicts.
        """
        edge_cases = [
            # --- Dimension 1: Latency Edge Cases ---
            # Empty result
            {},
            # Extremely fast execution (possible measurement error)
            {"success": True, "quality_score": 85.0, "duration_ms": 0.0001},
            # Extremely slow execution (timeout scenario)
            {"success": False, "quality_score": 0.0, "duration_ms": 999999.0, "error": "TimeoutError"},
            # Negative duration (data corruption)
            {"success": True, "quality_score": 70.0, "duration_ms": -100.0},

            # --- Dimension 2: Reliability Edge Cases ---
            # All failures
            {"success": False, "error": "CriticalError", "recovered": False, "aborted": True},
            # Recovery scenario
            {"success": True, "error": "RecoverableError", "recovered": True, "aborted": False},
            # Multiple errors in one task
            {"success": False, "error": "MultiError", "recovered": False, "aborted": True,
             "error_chain": ["ConnectionError", "TimeoutError", "SafetyError"]},

            # --- Dimension 3: Quality Edge Cases ---
            # Zero quality
            {"success": False, "quality_score": 0.0,
             "defects": ["scratch", "discoloration", "size_deviation", "edge_defect"]},
            # Perfect quality
            {"success": True, "quality_score": 100.0, "defects": []},
            # Negative quality score (calibration error)
            {"success": False, "quality_score": -1.0, "defects": ["defect"] * 10},
            # Missing fields
            {"success": True},
            # Only defects, no quality_score
            {"success": False, "defects": ["fatal_defect"]},

            # --- Dimension 4: Robustness Edge Cases ---
            # Malformed data - string where float expected
            {"success": "yes", "quality_score": "high"},
            # Boolean confusion
            {"success": 1, "quality_score": 0},  # 1/0 instead of True/False
            # None values
            {"success": None, "quality_score": None},
            # Very large context
            {"success": True, "quality_score": 50.0, "context": [{"k": "v"}] * 100},
            # Nested malformed data
            {"success": True, "quality_score": 75.0,
             "defects": [None, "", 0, {"nested": "bad"}]},

            # --- Dimension 5: Long-tail / Rare Scenarios ---
            # Adversarial: score exactly on boundary
            {"success": True, "quality_score": 70.0, "defects": []},  # Pass threshold
            {"success": False, "quality_score": 69.99, "defects": []},  # Just below
            # Adversarial: missing required safety check
            {"success": True, "quality_score": 90.0, "safety_checked": False},
            # Adversarial: simultaneous success and error
            {"success": True, "error": "NonCriticalWarning"},
            # Adversarial: extremely long defect list
            {"success": False, "quality_score": 20.0, "defects": [f"defect_{i}" for i in range(1000)]},
            # Adversarial: empty string keys
            {"success": True, "quality_score": 50.0, "": "empty_key"},
            # Adversarial: NaN-like values
            {"success": False, "quality_score": float("nan") if False else "NaN"},
            # Adversarial: Infinity
            {"success": False, "quality_score": float("inf") if False else "Infinity"},

            # --- Dimension 6: Context Health Edge Cases ---
            # State with extremely old timestamps
            {"success": True, "quality_score": 60.0,
             "state_age_days": 365, "last_accessed": "1970-01-01"},
            # State with critical keys all missing
            {"success": False, "quality_score": 0.0,
             "missing_critical": ["task_id", "safety_status", "robot_pose", "joint_angles"]},

            # --- Dimension 7: Reusability Edge Cases ---
            # Skill with zero reuse
            {"success": True, "quality_score": 80.0,
             "skill_data": {"total_skills": 0, "reuse_rate": 0.0}},
            # Skill with 100% reuse rate but low effectiveness
            {"success": True, "quality_score": 80.0,
             "skill_data": {"total_skills": 10, "reuse_rate": 1.0,
                           "skill_effectiveness": 0.1}},
        ]
        return edge_cases

    def generate_adversarial_samples(self, num_samples: int = 20) -> List[Dict[str, Any]]:
        """Generate adversarial samples designed to test system robustness.

        These samples are crafted to probe boundary conditions, type confusion,
        and edge cases that might cause evaluation failures.

        Args:
            num_samples: Number of adversarial samples to generate.

        Returns:
            List of adversarial task result dicts.
        """
        adversarial_templates = [
            # Type confusion attacks
            lambda: {"success": random.choice([True, False, "yes", 1, 0, None])},
            lambda: {"quality_score": random.choice([50.0, "good", None, [], {}])},
            lambda: {"defects": random.choice([[], None, "scratch", 42])},
            lambda: {"duration_ms": random.choice([500.0, -1.0, "fast", None])},

            # Boundary probing
            lambda: {"success": random.random() < 0.5,
                     "quality_score": random.uniform(-10, 110)},
            lambda: {"success": True, "quality_score": random.uniform(69.9, 70.1),
                     "defects": []},

            # Missing key fields
            lambda: {k: v for k, v in
                     {"success": True, "quality_score": 80.0, "defects": [],
                      "duration_ms": 500.0, "error": None, "recovered": False}.items()
                     if random.random() > 0.3},

            # Large payloads
            lambda: {"success": True, "quality_score": 50.0,
                     "payload": "x" * random.randint(1000, 10000)},

            # Deeply nested structures
            lambda: {"success": True, "quality_score": 50.0,
                     "nested": {"a": {"b": {"c": {"d": {"e": "deep"}}}}}},

            # Unicode/encoding attacks
            lambda: {"success": True, "quality_score": 50.0,
                     "unicode": "测试数据🎯\u0000\x00"},
        ]

        samples = []
        for i in range(num_samples):
            template = random.choice(adversarial_templates)
            sample = template()
            sample["task_id"] = f"adv_{i:03d}"
            samples.append(sample)

        return samples

    def generate_robustness_scenarios(self) -> Dict[str, List[Dict[str, Any]]]:
        """Generate robustness testing scenarios for multi-dimensional evaluation.

        Simulates different failure modes: network degradation, sensor noise,
        actuator degradation, and human error.

        Returns:
            Dict mapping scenario name to list of task results.
        """
        scenarios = {}

        # Scenario 1: Network degradation (intermittent failures)
        scenarios["network_degradation"] = []
        for i in range(10):
            success = random.random() > 0.4  # 60% success rate
            scenarios["network_degradation"].append({
                "task_id": f"net_{i}",
                "success": success,
                "error": "NetworkTimeout" if not success else None,
                "recovered": not success and random.random() > 0.5,
                "quality_score": random.gauss(70, 20) if success else random.gauss(20, 15),
                "defects": [],
                "duration_ms": random.gauss(800, 300) if success else random.gauss(5000, 2000),
            })

        # Scenario 2: Sensor noise (reduced quality but still passing)
        scenarios["sensor_noise"] = []
        for i in range(10):
            quality = random.gauss(60, 15)  # Lower quality due to noise
            scenarios["sensor_noise"].append({
                "task_id": f"sensor_{i}",
                "success": quality > 40,
                "quality_score": max(0, min(100, quality)),
                "defects": ["noise_artifact"] if random.random() < 0.3 else [],
                "quality_passed": quality >= 65,
                "duration_ms": random.gauss(600, 100),
            })

        # Scenario 3: Actuator degradation (slower but still functional)
        scenarios["actuator_degradation"] = []
        for i in range(10):
            slow_factor = random.uniform(1.5, 3.0)
            scenarios["actuator_degradation"].append({
                "task_id": f"actuator_{i}",
                "success": True,
                "quality_score": random.gauss(75, 10),
                "defects": [],
                "duration_ms": 500 * slow_factor,
                "metadata": {"wear_level": random.uniform(0.3, 0.8)},
            })

        # Scenario 4: Human error (incorrect parameters)
        scenarios["human_error"] = []
        for i in range(10):
            is_corrected = random.random() > 0.5
            scenarios["human_error"].append({
                "task_id": f"human_{i}",
                "success": is_corrected,
                "error": "ParameterError" if not is_corrected else None,
                "recovered": is_corrected,
                "quality_score": random.gauss(80, 10) if is_corrected else 0.0,
                "defects": [],
                "duration_ms": random.gauss(400, 100) if is_corrected else random.gauss(100, 20),
            })

        # Scenario 5: Perfect conditions (baseline)
        scenarios["perfect_conditions"] = []
        for i in range(10):
            scenarios["perfect_conditions"].append({
                "task_id": f"perfect_{i}",
                "success": True,
                "quality_score": random.gauss(95, 3),
                "defects": [],
                "quality_passed": True,
                "duration_ms": random.gauss(300, 50),
            })

        return scenarios

    def generate_multi_round_conversation(self, num_rounds: int = 5) -> List[Dict[str, Any]]:
        """Generate multi-round conversation simulation data.

        Simulates a multi-turn interaction between orchestrator and agents
        with context accumulating over rounds.

        Args:
            num_rounds: Number of conversation rounds.

        Returns:
            List of round data dicts with context and interaction info.
        """
        rounds = []
        context_size = 0

        for r in range(num_rounds):
            # Each round adds more context
            context_size += random.randint(5, 15)
            interactions = random.randint(3, 8)

            rounds.append({
                "round": r + 1,
                "context_size": context_size,
                "interactions_this_round": interactions,
                "key_states_updated": random.randint(1, 5),
                "critical_keys_accessed": random.randint(1, 3),
                "decay_risk": "low" if r < 3 else ("medium" if r < 4 else "high"),
                "compression_triggered": context_size > 30,
                "success": random.random() > 0.1 * r,  # Success rate degrades over rounds
                "quality_score": max(0, random.gauss(85 - r * 5, 10)),
                "duration_ms": random.gauss(300 + r * 50, 50),
            })

        return rounds

    def generate_long_tail_scenarios(self) -> Dict[str, List[Dict[str, Any]]]:
        """Generate long-tail / rare scenarios for edge coverage testing.

        Returns:
            Dict mapping scenario name to list of task results.
        """
        scenarios = {}

        # Rare: Emergency stop during task
        scenarios["emergency_stop"] = [
            {"task_id": "emergency_1", "success": False, "aborted": True,
             "error": "EmergencyStop", "quality_score": 0.0, "defects": [],
             "duration_ms": 50.0, "stop_reason": "Manual button press"},
            {"task_id": "emergency_2", "success": False, "aborted": True,
             "error": "EmergencyStop", "quality_score": 45.0, "defects": ["incomplete"],
             "duration_ms": 200.0, "stop_reason": "Safety zone violation"},
        ]

        # Rare: Power fluctuation during operation
        scenarios["power_fluctuation"] = [
            {"task_id": "power_1", "success": False, "recovered": True,
             "error": "PowerWarning", "quality_score": 78.0, "defects": [],
             "duration_ms": 1200.0},
            {"task_id": "power_2", "success": False, "recovered": False,
             "error": "PowerLoss", "quality_score": 0.0, "defects": ["incomplete"],
             "duration_ms": 300.0},
        ]

        # Rare: Multiple simultaneous tasks
        scenarios["simultaneous_tasks"] = [
            {"task_id": "multi_1", "success": True, "quality_score": 82.0,
             "defects": [], "concurrent_tasks": 3},
            {"task_id": "multi_2", "success": True, "quality_score": 76.0,
             "defects": ["slight_delay"], "concurrent_tasks": 5},
            {"task_id": "multi_3", "success": False, "quality_score": 55.0,
             "defects": ["resource_conflict"], "concurrent_tasks": 8},
        ]

        # Rare: Environmental extremes
        scenarios["environmental_extremes"] = [
            {"task_id": "env_1", "success": True, "quality_score": 80.0,
             "defects": [], "temperature_c": 45.0, "humidity_pct": 90},
            {"task_id": "env_2", "success": False, "quality_score": 30.0,
             "defects": ["thermal_error"], "temperature_c": 55.0, "humidity_pct": 95},
            {"task_id": "env_3", "success": True, "quality_score": 85.0,
             "defects": [], "temperature_c": -5.0, "humidity_pct": 10},
        ]

        # Rare: Calibration drift over time
        scenarios["calibration_drift"] = []
        for i in range(8):
            drift = i * 0.5  # Increasing drift over time
            quality = max(0, 90 - drift * 10)
            scenarios["calibration_drift"].append({
                "task_id": f"drift_{i}",
                "success": quality > 50,
                "quality_score": quality,
                "defects": ["drift_artifact"] if drift > 2.0 else [],
                "calibration_drift_mm": drift,
                "duration_ms": random.gauss(500, 50),
            })

        return scenarios

    # =========================================================================
    # Helpers
    # =========================================================================

    @staticmethod
    def _percentile(sorted_data: List[float], p: float) -> float:
        """Compute the p-th percentile."""
        if not sorted_data:
            return 0.0
        k = (len(sorted_data) - 1) * (p / 100.0)
        f = int(k)
        c = k - f
        if f + 1 < len(sorted_data):
            return sorted_data[f] * (1 - c) + sorted_data[f + 1] * c
        return sorted_data[f]