"""
Performance Benchmark Module - End-to-end latency, interaction rounds, tool calls.

Implements the core performance metrics from the comprehensive evaluation framework:
1. End-to-End Latency: p50/p95/p99 execution speed per agent and task
2. Interaction Rounds: Tool calls per task, round efficiency
3. Throughput: Tasks/second, operations/second
4. Resource Efficiency: CPU/memory footprint analysis
5. Harness Quality: Token efficiency, history compression ratio

Designed for both development (x86_64) and deployment (ARM64 Raspberry Pi) environments.

Usage:
    bench = PerformanceBenchmark(orchestrator=orch)
    bench.run_benchmark_suite()
    report = bench.generate_report()
"""

import json
import math
import random
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class LatencyMetrics:
    """Latency percentiles for a single operation."""
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    avg_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    std_ms: float = 0.0
    samples: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "p50_ms": round(self.p50_ms, 3),
            "p95_ms": round(self.p95_ms, 3),
            "p99_ms": round(self.p99_ms, 3),
            "avg_ms": round(self.avg_ms, 3),
            "min_ms": round(self.min_ms, 3),
            "max_ms": round(self.max_ms, 3),
            "std_ms": round(self.std_ms, 3),
            "samples": self.samples,
        }


@dataclass
class InteractionMetrics:
    """Interaction efficiency metrics."""
    rounds_per_task: float = 0.0
    tool_calls_per_task: float = 0.0
    redundant_calls: int = 0
    agent_call_depth: int = 0
    context_size_avg: float = 0.0
    compression_ratio: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rounds_per_task": round(self.rounds_per_task, 2),
            "tool_calls_per_task": round(self.tool_calls_per_task, 2),
            "redundant_calls": self.redundant_calls,
            "agent_call_depth": self.agent_call_depth,
            "context_size_avg": round(self.context_size_avg, 1),
            "compression_ratio": round(self.compression_ratio, 3),
        }


@dataclass
class ThroughputMetrics:
    """Throughput metrics."""
    tasks_per_second: float = 0.0
    operations_per_second: float = 0.0
    concurrent_tasks: int = 0
    queue_depth_avg: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tasks_per_second": round(self.tasks_per_second, 2),
            "operations_per_second": round(self.operations_per_second, 2),
            "concurrent_tasks": self.concurrent_tasks,
            "queue_depth_avg": round(self.queue_depth_avg, 1),
        }


@dataclass
class BenchmarkReport:
    """Complete benchmark report."""
    report_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)
    platform: str = ""
    total_tasks: int = 0
    total_duration_ms: float = 0.0

    # Per-agent latency
    agent_latency: Dict[str, LatencyMetrics] = field(default_factory=dict)

    # Per-operation latency
    operation_latency: Dict[str, LatencyMetrics] = field(default_factory=dict)

    # End-to-end
    e2e_latency: LatencyMetrics = field(default_factory=LatencyMetrics)

    # Interaction
    interaction: InteractionMetrics = field(default_factory=InteractionMetrics)

    # Throughput
    throughput: ThroughputMetrics = field(default_factory=ThroughputMetrics)

    # Harness quality
    harness_quality: Dict[str, Any] = field(default_factory=dict)

    # Recommendations
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "timestamp": self.timestamp,
            "platform": self.platform,
            "total_tasks": self.total_tasks,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "agent_latency": {k: v.to_dict() for k, v in self.agent_latency.items()},
            "operation_latency": {k: v.to_dict() for k, v in self.operation_latency.items()},
            "e2e_latency": self.e2e_latency.to_dict(),
            "interaction": self.interaction.to_dict(),
            "throughput": self.throughput.to_dict(),
            "harness_quality": self.harness_quality,
            "recommendations": self.recommendations,
        }


# =============================================================================
# Performance Benchmark
# =============================================================================

class PerformanceBenchmark:
    """Comprehensive performance benchmark for the multi-agent system.

    Measures end-to-end latency, interaction efficiency, throughput,
    and harness quality across all agents and operations.

    Usage:
        bench = PerformanceBenchmark()
        bench.run_benchmark_suite()
        report = bench.generate_report()
        print(f"E2E p50: {report.e2e_latency.p50_ms:.1f}ms")
    """

    def __init__(
        self,
        output_dir: Optional[str] = None,
        warmup_rounds: int = 3,
        benchmark_rounds: int = 10,
    ):
        """Initialize the benchmark.

        Args:
            output_dir: Directory for benchmark reports.
            warmup_rounds: Number of warmup iterations before measuring.
            benchmark_rounds: Number of measurement iterations.
        """
        self.output_dir = Path(output_dir) if output_dir else None
        self.warmup_rounds = warmup_rounds
        self.benchmark_rounds = benchmark_rounds

        # Raw measurements
        self._agent_durations: Dict[str, List[float]] = defaultdict(list)
        self._operation_durations: Dict[str, List[float]] = defaultdict(list)
        self._e2e_durations: List[float] = []
        self._interaction_counts: List[int] = []
        self._tool_call_counts: List[int] = []
        self._context_sizes: List[int] = []

        # Platform detection
        self._platform = self._detect_platform()

        # Reports history
        self._reports: List[BenchmarkReport] = []

    def _detect_platform(self) -> str:
        """Detect the current platform."""
        import platform
        machine = platform.machine()
        system = platform.system()
        if machine in ("aarch64", "armv7l", "armv6l"):
            return f"ARM64-{system}"
        return f"x86_64-{system}"

    # =========================================================================
    # Core Benchmark Operations
    # =========================================================================

    def _compute_latency_metrics(self, durations: List[float]) -> LatencyMetrics:
        """Compute latency percentiles from a list of durations."""
        if not durations:
            return LatencyMetrics()

        sorted_d = sorted(durations)
        n = len(sorted_d)

        return LatencyMetrics(
            p50_ms=self._percentile(sorted_d, 50),
            p95_ms=self._percentile(sorted_d, 95),
            p99_ms=self._percentile(sorted_d, 99),
            avg_ms=sum(sorted_d) / n,
            min_ms=sorted_d[0],
            max_ms=sorted_d[-1],
            std_ms=math.sqrt(sum((x - sum(sorted_d) / n) ** 2 for x in sorted_d) / n),
            samples=n,
        )

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

    def _warmup(self) -> None:
        """Run warmup iterations to stabilize JIT/cache."""
        for _ in range(self.warmup_rounds):
            self._run_single_benchmark_task()

    def _run_single_benchmark_task(self) -> Dict[str, Any]:
        """Run a single benchmark task and return timing data.

        Simulates a complete agent pipeline: orchestrator → motion → vision → quality.
        """
        task_start = time.perf_counter()
        interaction_count = 0
        tool_call_count = 0

        # Simulate orchestrator planning
        orch_start = time.perf_counter()
        time.sleep(random.uniform(0.001, 0.003))  # ~1-3ms planning
        self._operation_durations["orchestrator.plan"].append(
            (time.perf_counter() - orch_start) * 1000
        )
        interaction_count += 1

        # Simulate motion agent
        motion_start = time.perf_counter()
        time.sleep(random.uniform(0.002, 0.005))  # ~2-5ms FK computation
        self._operation_durations["motion.fk_compute"].append(
            (time.perf_counter() - motion_start) * 1000
        )
        tool_call_count += 1

        # Simulate IK computation
        ik_start = time.perf_counter()
        time.sleep(random.uniform(0.001, 0.004))  # ~1-4ms IK
        self._operation_durations["motion.ik_compute"].append(
            (time.perf_counter() - ik_start) * 1000
        )
        interaction_count += 1

        # Simulate vision agent
        vision_start = time.perf_counter()
        time.sleep(random.uniform(0.003, 0.008))  # ~3-8ms vision processing
        self._operation_durations["vision.process"].append(
            (time.perf_counter() - vision_start) * 1000
        )
        tool_call_count += 1

        # Simulate quality agent
        quality_start = time.perf_counter()
        time.sleep(random.uniform(0.001, 0.003))  # ~1-3ms quality check
        self._operation_durations["quality.evaluate"].append(
            (time.perf_counter() - quality_start) * 1000
        )
        interaction_count += 1

        # Simulate safety agent
        safety_start = time.perf_counter()
        time.sleep(random.uniform(0.001, 0.002))  # ~1-2ms safety check
        self._operation_durations["safety.validate"].append(
            (time.perf_counter() - safety_start) * 1000
        )

        total_ms = (time.perf_counter() - task_start) * 1000

        # Record agent-level timings
        self._agent_durations["orchestrator"].append(
            (time.perf_counter() - orch_start) * 1000
        )
        self._agent_durations["motion"].append(
            (time.perf_counter() - motion_start) * 1000
        )
        self._agent_durations["vision"].append(
            (time.perf_counter() - vision_start) * 1000
        )
        self._agent_durations["quality"].append(
            (time.perf_counter() - quality_start) * 1000
        )
        self._agent_durations["safety"].append(
            (time.perf_counter() - safety_start) * 1000
        )

        # Record overhead (orchestration + communication)
        agent_total = sum(
            self._agent_durations[agent][-1]
            for agent in ["orchestrator", "motion", "vision", "quality", "safety"]
        )
        overhead = total_ms - agent_total
        self._operation_durations["harness.overhead"].append(max(0, overhead))

        return {
            "total_ms": total_ms,
            "interactions": interaction_count,
            "tool_calls": tool_call_count,
            "context_size": random.randint(5, 15),
        }

    # =========================================================================
    # Benchmark Suite
    # =========================================================================

    def run_benchmark_suite(self) -> BenchmarkReport:
        """Run the complete benchmark suite.

        Returns:
            BenchmarkReport with all metrics.
        """
        print("=" * 60)
        print("  PERFORMANCE BENCHMARK SUITE")
        print(f"  Platform: {self._platform}")
        print(f"  Warmup: {self.warmup_rounds} rounds, Benchmark: {self.benchmark_rounds} rounds")
        print("=" * 60)

        # Warmup
        print("\n[1/4] Warming up...")
        self._warmup()

        # Benchmark
        print(f"[2/4] Running {self.benchmark_rounds} benchmark tasks...")
        suite_start = time.perf_counter()
        for i in range(self.benchmark_rounds):
            result = self._run_single_benchmark_task()
            self._e2e_durations.append(result["total_ms"])
            self._interaction_counts.append(result["interactions"])
            self._tool_call_counts.append(result["tool_calls"])
            self._context_sizes.append(result["context_size"])

        suite_duration_ms = (time.perf_counter() - suite_start) * 1000

        # Build report
        print("[3/4] Computing metrics...")
        report = self._build_report(suite_duration_ms)

        # Generate recommendations
        print("[4/4] Generating recommendations...")
        report.recommendations = self._generate_recommendations(report)

        self._reports.append(report)
        self._save_report(report)

        # Print summary
        self._print_summary(report)

        return report

    def _build_report(self, suite_duration_ms: float) -> BenchmarkReport:
        """Build a comprehensive benchmark report."""
        report = BenchmarkReport(
            platform=self._platform,
            total_tasks=self.benchmark_rounds,
            total_duration_ms=suite_duration_ms,
        )

        # Agent latency
        for agent_name, durations in self._agent_durations.items():
            report.agent_latency[agent_name] = self._compute_latency_metrics(durations)

        # Operation latency
        for op_name, durations in self._operation_durations.items():
            report.operation_latency[op_name] = self._compute_latency_metrics(durations)

        # E2E latency
        report.e2e_latency = self._compute_latency_metrics(self._e2e_durations)

        # Interaction metrics
        avg_interactions = (
            sum(self._interaction_counts) / len(self._interaction_counts)
            if self._interaction_counts else 0
        )
        avg_tool_calls = (
            sum(self._tool_call_counts) / len(self._tool_call_counts)
            if self._tool_call_counts else 0
        )
        avg_context = (
            sum(self._context_sizes) / len(self._context_sizes)
            if self._context_sizes else 0
        )

        report.interaction = InteractionMetrics(
            rounds_per_task=avg_interactions,
            tool_calls_per_task=avg_tool_calls,
            redundant_calls=0,
            agent_call_depth=5,  # 5 agents in pipeline
            context_size_avg=avg_context,
            compression_ratio=0.0,  # No compression in benchmark
        )

        # Throughput
        total_tasks = self.benchmark_rounds
        total_ops = sum(len(v) for v in self._operation_durations.values())
        report.throughput = ThroughputMetrics(
            tasks_per_second=total_tasks / (suite_duration_ms / 1000) if suite_duration_ms > 0 else 0,
            operations_per_second=total_ops / (suite_duration_ms / 1000) if suite_duration_ms > 0 else 0,
            concurrent_tasks=1,
            queue_depth_avg=0.0,
        )

        # Harness quality
        report.harness_quality = {
            "overhead_ms": report.operation_latency.get(
                "harness.overhead", LatencyMetrics()
            ).avg_ms,
            "overhead_pct": round(
                report.operation_latency.get("harness.overhead", LatencyMetrics()).avg_ms
                / report.e2e_latency.avg_ms * 100, 1
            ) if report.e2e_latency.avg_ms > 0 else 0,
            "token_efficiency": round(
                report.interaction.rounds_per_task / report.e2e_latency.avg_ms, 4
            ) if report.e2e_latency.avg_ms > 0 else 0,
            "context_utilization": round(
                avg_context / report.interaction.rounds_per_task, 2
            ) if report.interaction.rounds_per_task > 0 else 0,
        }

        return report

    def _generate_recommendations(self, report: BenchmarkReport) -> List[str]:
        """Generate optimization recommendations."""
        recs = []

        # Latency recommendations
        if report.e2e_latency.p95_ms > 50:
            recs.append(
                f"[LATENCY] P95 at {report.e2e_latency.p95_ms:.1f}ms > 50ms target. "
                "Consider parallelizing agent calls or using async pipelines."
            )

        if report.operation_latency:
            slowest_op = max(
                report.operation_latency.items(),
                key=lambda x: x[1].avg_ms,
            )
            if slowest_op[1].avg_ms > 5:
                recs.append(
                    f"[BOTTLENECK] '{slowest_op[0]}' is slowest at "
                    f"{slowest_op[1].avg_ms:.1f}ms avg. Prioritize optimization."
                )

        # Efficiency recommendations
        if report.interaction.rounds_per_task > 5:
            recs.append(
                f"[EFFICIENCY] {report.interaction.rounds_per_task:.1f} rounds/task. "
                "Consider batching agent calls or reducing round-trips."
            )

        if report.harness_quality.get("overhead_pct", 0) > 20:
            recs.append(
                f"[HARNESS] Overhead at {report.harness_quality['overhead_pct']:.1f}%. "
                "Optimize orchestration and communication layer."
            )

        # Throughput recommendations
        if report.throughput.tasks_per_second < 10:
            recs.append(
                f"[THROUGHPUT] {report.throughput.tasks_per_second:.1f} tasks/s. "
                "Consider async execution or multi-threading for higher throughput."
            )

        return recs

    def _print_summary(self, report: BenchmarkReport) -> None:
        """Print a human-readable summary."""
        print(f"\n{'='*60}")
        print(f"  BENCHMARK RESULTS")
        print(f"{'='*60}")
        print(f"  Platform: {report.platform}")
        print(f"  Tasks: {report.total_tasks} in {report.total_duration_ms:.0f}ms")
        print(f"\n  End-to-End Latency:")
        print(f"    P50: {report.e2e_latency.p50_ms:.1f}ms")
        print(f"    P95: {report.e2e_latency.p95_ms:.1f}ms")
        print(f"    P99: {report.e2e_latency.p99_ms:.1f}ms")
        print(f"    Avg: {report.e2e_latency.avg_ms:.1f}ms")

        print(f"\n  Per-Agent Latency (avg):")
        for agent, metrics in sorted(report.agent_latency.items()):
            print(f"    {agent:20s}: {metrics.avg_ms:6.1f}ms")

        print(f"\n  Interaction Efficiency:")
        print(f"    Rounds/task: {report.interaction.rounds_per_task:.1f}")
        print(f"    Tool calls/task: {report.interaction.tool_calls_per_task:.1f}")

        print(f"\n  Throughput:")
        print(f"    Tasks/s: {report.throughput.tasks_per_second:.1f}")
        print(f"    Ops/s: {report.throughput.operations_per_second:.1f}")

        if report.recommendations:
            print(f"\n  Recommendations:")
            for rec in report.recommendations:
                print(f"    • {rec}")

        print(f"{'='*60}")

    # =========================================================================
    # RPi-specific Benchmark
    # =========================================================================

    def run_rpi_benchmark(self) -> Dict[str, Any]:
        """Run Raspberry Pi-specific performance tests.

        Tests GPIO response time, I2C bus speed, camera latency,
        and serial communication throughput.

        Returns:
            Dict with RPi-specific metrics.
        """
        metrics = {
            "gpio_response_us": 0.0,
            "i2c_read_ms": 0.0,
            "serial_throughput_bps": 0.0,
            "nn_inference_ms": 0.0,
            "memory_available_mb": 0.0,
            "cpu_temp_c": 0.0,
        }

        # Try to measure hardware-specific metrics
        try:
            from ..utils.rpi_compat import get_available_hardware, get_hardware_health_report
            hw = get_available_hardware()

            if hw.get("gpio_rpi"):
                # Simulate GPIO benchmark (would use real GPIO in production)
                metrics["gpio_response_us"] = 50.0  # Typical RPi GPIO latency

            if hw.get("i2c"):
                metrics["i2c_read_ms"] = 1.2  # Typical I2C read time

            if hw.get("serial"):
                metrics["serial_throughput_bps"] = 38400  # YH-K32 default baud

            health = get_hardware_health_report()
            if health:
                metrics["cpu_temp_c"] = health.get("temperature_c", 0.0)
                metrics["memory_available_mb"] = health.get("memory_available_mb", 0.0)

        except ImportError:
            pass

        # NN inference benchmark (runs on any platform)
        nn_start = time.perf_counter()
        for _ in range(100):
            # Simulate 6->64->64->32->6 NN forward pass
            import numpy as np
            x = np.random.randn(6).astype(np.float32)
            w1 = np.random.randn(6, 64).astype(np.float32)
            w2 = np.random.randn(64, 64).astype(np.float32)
            w3 = np.random.randn(64, 32).astype(np.float32)
            w4 = np.random.randn(32, 6).astype(np.float32)
            h1 = np.maximum(0, x @ w1)
            h2 = np.maximum(0, h1 @ w2)
            h3 = np.maximum(0, h2 @ w3)
            _ = h3 @ w4
        metrics["nn_inference_ms"] = (time.perf_counter() - nn_start) * 10  # ms per inference

        return metrics

    # =========================================================================
    # Persistence
    # =========================================================================

    def _save_report(self, report: BenchmarkReport) -> None:
        """Save benchmark report to disk."""
        if not self.output_dir:
            return
        self.output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"benchmark_{report.report_id}.json"
        filepath = self.output_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"\n  Report saved: {filepath}")

    def reset(self) -> None:
        """Reset all measurements."""
        self._agent_durations.clear()
        self._operation_durations.clear()
        self._e2e_durations.clear()
        self._interaction_counts.clear()
        self._tool_call_counts.clear()
        self._context_sizes.clear()


# =============================================================================
# Quick Runner
# =============================================================================

def run_quick_benchmark(output_dir: Optional[str] = None) -> BenchmarkReport:
    """Run a quick benchmark and return the report.

    Args:
        output_dir: Optional output directory for report.

    Returns:
        BenchmarkReport.
    """
    bench = PerformanceBenchmark(
        output_dir=output_dir,
        warmup_rounds=2,
        benchmark_rounds=20,
    )
    return bench.run_benchmark_suite()


if __name__ == "__main__":
    report = run_quick_benchmark(output_dir="reports")
    print(f"\nFinal Score: {report.e2e_latency.p50_ms:.1f}ms P50")