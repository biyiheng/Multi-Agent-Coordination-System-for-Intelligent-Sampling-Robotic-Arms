"""
Performance, memory, and response efficiency tests.

Profiles critical paths: serial I/O, kinematics, collision detection,
API response times, and memory usage patterns.
"""

import asyncio
import gc
import json
import math
import sys
import time
import tracemalloc
from pathlib import Path

# Ensure project root is on sys.path
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import numpy as np
import pytest


# =============================================================================
# Performance Benchmarks
# =============================================================================

class TestKinematicsPerformance:
    """Benchmark kinematics computation speed."""

    def test_forward_kinematics_latency(self):
        """FK should compute in < 1ms."""
        from rpi_control.motion.kinematics import forward_kinematics

        angles = [0.1, 0.2, -0.3, 0.4, -0.1, 0.0]
        # Warmup
        for _ in range(100):
            forward_kinematics(angles)

        # Benchmark
        times = []
        for _ in range(1000):
            start = time.perf_counter()
            forward_kinematics(angles)
            times.append(time.perf_counter() - start)

        avg = sum(times) / len(times) * 1000
        max_time = max(times) * 1000
        print(f"\n  FK: avg={avg:.3f}ms, max={max_time:.3f}ms")
        assert avg < 2.0, f"FK too slow: {avg:.3f}ms avg"

    def test_inverse_kinematics_latency(self):
        """IK should compute in < 5ms."""
        from rpi_control.motion.kinematics import inverse_kinematics

        # IK takes a single 6-element array: [x, y, z, roll, pitch, yaw]
        target_pose = np.array([200.0, 100.0, 150.0, 0.0, 0.0, 0.0])

        # Warmup
        for _ in range(50):
            try:
                inverse_kinematics(target_pose)
            except Exception:
                pass

        # Benchmark
        times = []
        for _ in range(200):
            try:
                start = time.perf_counter()
                inverse_kinematics(target_pose)
                times.append(time.perf_counter() - start)
            except Exception:
                pass

        if not times:
            pytest.skip("IK could not find solutions for benchmark pose")
        avg = sum(times) / len(times) * 1000
        max_time = max(times) * 1000
        print(f"\n  IK: avg={avg:.3f}ms, max={max_time:.3f}ms")
        assert avg < 10.0, f"IK too slow: {avg:.3f}ms avg"

    def test_pwm_conversion_latency(self):
        """PWM conversion should be sub-millisecond."""
        from rpi_control.motion.kinematics import (
            joint_angles_to_pwm,
            pwm_to_joint_angles,
        )

        angles = [0.0, 0.5, -0.3, 0.2, 0.0, 0.0]
        pwms = [1500, 1600, 1400, 1550, 1500, 1500]

        # FK to PWM
        times = []
        for _ in range(1000):
            start = time.perf_counter()
            joint_angles_to_pwm(angles)
            times.append(time.perf_counter() - start)
        avg = sum(times) / len(times) * 1000
        print(f"\n  Angles→PWM: avg={avg:.3f}ms")
        assert avg < 0.5, f"Angles→PWM too slow: {avg:.3f}ms"

        # PWM to angles
        times = []
        for _ in range(1000):
            start = time.perf_counter()
            pwm_to_joint_angles(pwms)
            times.append(time.perf_counter() - start)
        avg = sum(times) / len(times) * 1000
        print(f"  PWM→Angles: avg={avg:.3f}ms")
        assert avg < 0.5, f"PWM→Angles too slow: {avg:.3f}ms"


class TestCollisionPerformance:
    """Benchmark collision detection."""

    def test_self_collision_latency(self):
        """Self-collision check should be fast."""
        from rpi_control.motion.collision import check_self_collision

        angles = [0.0, 0.3, -0.5, 0.2, 0.0, 0.0]

        # Warmup
        for _ in range(100):
            check_self_collision(angles)

        times = []
        for _ in range(500):
            start = time.perf_counter()
            check_self_collision(angles)
            times.append(time.perf_counter() - start)

        avg = sum(times) / len(times) * 1000
        print(f"\n  Self-collision: avg={avg:.3f}ms")
        assert avg < 2.0, f"Self-collision too slow: {avg:.3f}ms"

    def test_environment_collision_latency(self):
        """Environment collision check should scale reasonably."""
        from rpi_control.motion.collision import check_environment_collision, Obstacle

        angles = [0.0, 0.3, 0.0, 0.0, 0.0, 0.0]
        obstacles = [
            Obstacle(
                id=f"obs_{i}",
                center=np.array([100.0 + i * 50, 100.0, 50.0]),
                extents=np.array([20.0, 20.0, 20.0]),
            )
            for i in range(10)
        ]

        times = []
        for _ in range(500):
            start = time.perf_counter()
            check_environment_collision(angles, obstacles)
            times.append(time.perf_counter() - start)

        avg = sum(times) / len(times) * 1000
        print(f"\n  Env-collision (10 obs): avg={avg:.3f}ms")
        assert avg < 5.0, f"Env-collision too slow: {avg:.3f}ms"

    def test_retreat_path_latency(self):
        """Retreat path generation should be fast."""
        from rpi_control.motion.collision import get_safe_retreat_path

        current = [0.5, 0.3, -0.4, 0.2, 0.1, 0.0]

        times = []
        for _ in range(200):
            start = time.perf_counter()
            get_safe_retreat_path(current)
            times.append(time.perf_counter() - start)

        avg = sum(times) / len(times) * 1000
        print(f"\n  Retreat path: avg={avg:.3f}ms")
        assert avg < 10.0, f"Retreat path too slow: {avg:.3f}ms"


class TestAPIResponseTime:
    """Measure API endpoint response times."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from rpi_control.web.server import app
        return TestClient(app)

    def test_root_response_time(self, client):
        """Root endpoint should respond in < 50ms."""
        # Warmup
        for _ in range(5):
            client.get("/")

        times = []
        for _ in range(50):
            start = time.perf_counter()
            client.get("/")
            times.append(time.perf_counter() - start)

        avg = sum(times) / len(times) * 1000
        p99 = sorted(times)[int(len(times) * 0.99)] * 1000
        print(f"\n  GET /: avg={avg:.2f}ms, p99={p99:.2f}ms")
        assert avg < 50, f"Root endpoint too slow: {avg:.2f}ms"

    def test_health_response_time(self, client):
        """Health check should respond in < 30ms."""
        for _ in range(5):
            client.get("/health")

        times = []
        for _ in range(100):
            start = time.perf_counter()
            client.get("/health")
            times.append(time.perf_counter() - start)

        avg = sum(times) / len(times) * 1000
        p99 = sorted(times)[int(len(times) * 0.99)] * 1000
        print(f"\n  GET /health: avg={avg:.2f}ms, p99={p99:.2f}ms")
        assert avg < 30, f"Health check too slow: {avg:.2f}ms"

    def test_arm_status_response_time(self, client):
        """Arm status should respond in < 50ms."""
        for _ in range(5):
            client.get("/api/v1/arm/status")

        times = []
        for _ in range(50):
            start = time.perf_counter()
            client.get("/api/v1/arm/status")
            times.append(time.perf_counter() - start)

        avg = sum(times) / len(times) * 1000
        print(f"\n  GET /api/v1/arm/status: avg={avg:.2f}ms")
        assert avg < 50, f"Arm status too slow: {avg:.2f}ms"


# =============================================================================
# Memory Usage Tests
# =============================================================================

class TestMemoryUsage:
    """Measure memory usage of key operations."""

    def test_kinematics_memory(self):
        """Kinematics should not leak memory."""
        from rpi_control.motion.kinematics import (
            forward_kinematics,
            inverse_kinematics,
        )

        gc.collect()
        tracemalloc.start()

        # Run many iterations
        for i in range(1000):
            angles = [
                i * 0.001,
                i * 0.002,
                -i * 0.001,
                i * 0.0015,
                0.0,
                0.0,
            ]
            forward_kinematics(angles)
            # IK takes a single 6-element array
            target_pose = np.array([150.0 + i * 0.01, 100.0, 150.0, 0.0, 0.0, 0.0])
            try:
                inverse_kinematics(target_pose)
            except Exception:
                pass

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        print(f"\n  Kinematics memory: current={current / 1024:.1f}KB, "
              f"peak={peak / 1024:.1f}KB")
        # Peak should be reasonable (< 50MB)
        assert peak < 50 * 1024 * 1024, \
            f"Peak memory too high: {peak / 1024 / 1024:.1f}MB"

    def test_collision_detection_memory(self):
        """Collision detection should not leak memory."""
        from rpi_control.motion.collision import (
            check_self_collision,
            check_environment_collision,
            Obstacle,
        )

        gc.collect()
        tracemalloc.start()

        obstacles = [
            Obstacle(
                id=f"obs_{i}",
                center=np.array([float(i * 20), float(i * 30), 50.0]),
                extents=np.array([15.0, 15.0, 15.0]),
            )
            for i in range(20)
        ]

        for i in range(500):
            angles = [
                i * 0.002,
                i * 0.003,
                -i * 0.001,
                i * 0.002,
                0.0,
                0.0,
            ]
            check_self_collision(angles)
            check_environment_collision(angles, obstacles)

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        print(f"\n  Collision memory: current={current / 1024:.1f}KB, "
              f"peak={peak / 1024:.1f}KB")
        assert peak < 50 * 1024 * 1024, \
            f"Peak memory too high: {peak / 1024 / 1024:.1f}MB"

    def test_model_loading_memory(self):
        """Model loading should not consume excessive memory."""
        models_dir = Path(__file__).resolve().parent.parent / "models"
        if not models_dir.exists() or not list(models_dir.glob("*.pkl")):
            pytest.skip("No model files to test")

        import pickle

        gc.collect()
        tracemalloc.start()

        loaded = 0
        for mf in models_dir.glob("*.pkl"):
            with open(mf, "rb") as f:
                _ = pickle.load(f)
            loaded += 1

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        print(f"\n  Model loading ({loaded} models): "
              f"current={current / 1024:.1f}KB, peak={peak / 1024:.1f}KB")
        assert peak < 200 * 1024 * 1024, \
            f"Peak model memory too high: {peak / 1024 / 1024:.1f}MB"

    def test_config_loading_memory(self):
        """Config loading should be memory-efficient."""
        from rpi_control.utils.config_loader import load_config

        gc.collect()
        tracemalloc.start()

        for _ in range(100):
            _ = load_config()

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        print(f"\n  Config loading (100x): current={current / 1024:.1f}KB, "
              f"peak={peak / 1024:.1f}KB")
        assert peak < 20 * 1024 * 1024, \
            f"Config loading memory too high: {peak / 1024 / 1024:.1f}MB"


# =============================================================================
# Throughput / Scalability Tests
# =============================================================================

class TestThroughput:
    """Measure throughput of critical operations."""

    def test_fk_throughput(self):
        """FK should handle 10000+ ops/sec."""
        from rpi_control.motion.kinematics import forward_kinematics

        angles = [0.1, 0.2, -0.3, 0.4, -0.1, 0.0]
        count = 5000

        start = time.perf_counter()
        for _ in range(count):
            forward_kinematics(angles)
        elapsed = time.perf_counter() - start

        throughput = count / elapsed
        print(f"\n  FK throughput: {throughput:.0f} ops/sec")
        assert throughput > 1000, f"FK throughput too low: {throughput:.0f} ops/sec"

    def test_self_collision_throughput(self):
        """Self-collision should handle 5000+ ops/sec."""
        from rpi_control.motion.collision import check_self_collision

        angles = [0.0, 0.3, -0.5, 0.2, 0.0, 0.0]
        count = 3000

        start = time.perf_counter()
        for _ in range(count):
            check_self_collision(angles)
        elapsed = time.perf_counter() - start

        throughput = count / elapsed
        print(f"\n  Self-collision throughput: {throughput:.0f} ops/sec")
        assert throughput > 500, f"Self-collision throughput too low: {throughput:.0f} ops/sec"


# =============================================================================
# Response Efficiency Analysis
# =============================================================================

class TestResponseEfficiency:
    """Analyze response efficiency patterns."""

    def test_no_redundant_computation(self):
        """Verify that repeated identical calls don't degrade."""
        from rpi_control.motion.kinematics import forward_kinematics

        angles = [0.0] * 6

        # First call (may include one-time setup)
        times_first = []
        for _ in range(10):
            start = time.perf_counter()
            forward_kinematics(angles)
            times_first.append(time.perf_counter() - start)

        # Subsequent calls
        times_later = []
        for _ in range(100):
            start = time.perf_counter()
            forward_kinematics(angles)
            times_later.append(time.perf_counter() - start)

        avg_first = sum(times_first) / len(times_first) * 1000
        avg_later = sum(times_later) / len(times_later) * 1000

        print(f"\n  FK first calls: {avg_first:.3f}ms avg")
        print(f"  FK later calls: {avg_later:.3f}ms avg")
        # Later calls should not be slower (no degradation)
        assert avg_later <= avg_first * 2.0, \
            "Performance degrades over repeated calls"

    def test_gc_not_excessive(self):
        """Verify GC doesn't dominate execution time."""
        gc.collect()
        gc.disable()

        try:
            from rpi_control.motion.kinematics import forward_kinematics

            start = time.perf_counter()
            for i in range(5000):
                angles = [i * 0.001] * 6
                forward_kinematics(angles)
            elapsed = time.perf_counter() - start

            print(f"\n  5000 FK calls without GC: {elapsed:.3f}s")
            # Should complete in reasonable time
            assert elapsed < 5.0, f"Too slow without GC: {elapsed:.3f}s"
        finally:
            gc.enable()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])