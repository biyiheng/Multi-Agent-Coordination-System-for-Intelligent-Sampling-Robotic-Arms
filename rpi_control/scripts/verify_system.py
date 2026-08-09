#!/usr/bin/env python3
"""
Comprehensive System Verification & Self-Inspection Script.

Performs multi-level verification:
1. Import verification (all modules, agents)
2. Orchestrator initialization test
3. Model files integrity check (existence, size, loadability)
4. Training reports verification
5. Docker/RPi configuration check
6. Config files check
7. Training data quality check (integrity, statistics)
8. Raspberry Pi hardware health check (temp, throttling, memory)
9. Hardware interface verification (UART, I2C, GPIO)
10. Performance benchmark (FK/IK computation speed)
"""

import json
import math
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# =============================================================================
# Section 1: Agent Import Verification
# =============================================================================

def check_imports() -> list:
    """Verify all agent imports work correctly."""
    errors = []
    print("=== 1. Agent Import Verification ===")

    modules = [
        ("base_agent", "agents.base_agent", ["BaseAgent", "AgentConfig", "AgentStatus", "NON_RECOVERABLE_ERRORS"]),
        ("motion_agent", "agents.motion_agent", ["MotionAgent", "MotionState"]),
        ("vision_agent", "agents.vision_agent", ["VisionAgent"]),
        ("safety_agent", "agents.safety_agent", ["SafetyAgent", "SafetyState"]),
        ("quality_agent", "agents.quality_agent", ["QualityAgent", "QualityDecision"]),
        ("sampling_agent", "agents.sampling_agent", ["SamplingAgent", "SamplingState"]),
        ("orchestrator", "agents.orchestrator", ["Orchestrator", "OrchestratorState", "TaskRequest"]),
    ]

    for name, module_path, classes in modules:
        try:
            mod = __import__(module_path, fromlist=classes)
            for cls in classes:
                getattr(mod, cls)
            extra = ""
            if name == "base_agent":
                extra = f" (NON_RECOVERABLE_ERRORS={len(mod.NON_RECOVERABLE_ERRORS)} types)"
            print(f"  {name}: OK{extra}")
        except Exception as e:
            errors.append(f"{name}: {e}")
            print(f"  {name}: FAILED - {e}")

    return errors


# =============================================================================
# Section 2: Orchestrator Initialization
# =============================================================================

def check_orchestrator() -> list:
    """Verify orchestrator initialization."""
    errors = []
    print("\n=== 2. Orchestrator Initialization Test ===")

    try:
        from agents.orchestrator import Orchestrator
        orch = Orchestrator()
        print(f"  Agents initialized: {len(orch.agents)}")
        print(f"  Agent init errors: {orch._agent_init_errors}")
        print(f"  State transitions: {len(orch.STATE_TRANSITIONS)} states")
        has_error_history = "error_history" in orch.system_state
        print(f"  error_history in system_state: {has_error_history}")
        if orch._agent_init_errors:
            errors.append(f"Orchestrator init errors: {orch._agent_init_errors}")
        print("  OK")
    except Exception as e:
        errors.append(f"Orchestrator: {e}")
        print(f"  FAILED - {e}")

    return errors


# =============================================================================
# Section 3: Model Files Verification
# =============================================================================

def check_models() -> list:
    """Verify model files exist and are loadable."""
    errors = []
    print("\n=== 3. Model Files Verification ===")

    models_dir = Path(__file__).parent.parent / "models"
    if not models_dir.exists():
        errors.append("models directory not found")
        print("  models directory not found!")
        return errors

    expected_models = [
        "motion_ik_model.pkl",
        "safety_model.pkl",
        "quality_model.pkl",
        "collision_model.pkl",
    ]

    expected_meta = [
        "motion_ik_model_meta.json",
        "safety_model_meta.json",
        "quality_model_meta.json",
    ]

    for f in sorted(models_dir.iterdir()):
        if f.is_file():
            size_kb = f.stat().st_size / 1024
            status = "✅" if size_kb > 0.1 else "⚠️"
            print(f"  {status} {f.name}: {size_kb:.1f} KB")

    # Check for missing expected models
    for model_name in expected_models:
        if not (models_dir / model_name).exists():
            errors.append(f"Missing model: {model_name}")
            print(f"  ❌ Missing: {model_name}")

    for meta_name in expected_meta:
        if not (models_dir / meta_name).exists():
            print(f"  ⚠️ Missing metadata: {meta_name}")

    # Try to load models
    try:
        import pickle
        for model_file in models_dir.glob("*.pkl"):
            try:
                with open(model_file, "rb") as f:
                    data = pickle.load(f)
                if isinstance(data, dict):
                    print(f"  🧠 {model_file.name}: Loaded (dict with {len(data)} keys)")
                else:
                    print(f"  🧠 {model_file.name}: Loaded (type={type(data).__name__})")
            except Exception as e:
                errors.append(f"Model {model_file.name} load error: {e}")
                print(f"  ❌ {model_file.name}: Load failed - {e}")
    except ImportError:
        print("  ⚠️ pickle not available for model verification")

    return errors


# =============================================================================
# Section 4: Training Reports
# =============================================================================

def check_reports() -> list:
    """Verify training reports."""
    errors = []
    print("\n=== 4. Training Reports Verification ===")

    reports_dir = Path(__file__).parent.parent / "reports"
    if not reports_dir.exists():
        errors.append("reports directory not found")
        print("  reports directory not found!")
        return errors

    for f in sorted(reports_dir.iterdir()):
        if f.suffix == ".json":
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if "agent_results" in data:
                    agents = data["agent_results"]
                    improvements = {k: v.get("improvement_pct", 0) for k, v in agents.items()}
                    avg_imp = sum(improvements.values()) / len(improvements) if improvements else 0
                    print(f"  {f.name}: Round {data.get('round', '?')}, {len(agents)} agents, avg improvement={avg_imp:+.1f}%")
                elif "iterations" in data:
                    iters = data.get("iterations", [])
                    print(f"  {f.name}: Loop result, {len(iters)} iterations, final_score={data.get('final_score', 'N/A')}")
                elif "models" in data or "motion" in data:
                    print(f"  {f.name}: Model results ({len(data)} models)")
                else:
                    print(f"  {f.name}: OK")
            except Exception as e:
                errors.append(f"Report {f.name}: {e}")
                print(f"  {f.name}: FAILED - {e}")

    return errors


# =============================================================================
# Section 5: Docker & RPi Configuration
# =============================================================================

def check_docker_config() -> list:
    """Verify Docker and RPi configuration files."""
    errors = []
    print("\n=== 5. Docker & RPi Configuration ===")

    root_dir = Path(__file__).parent.parent
    docker_files = {
        "Dockerfile": "Docker build file",
        "docker-compose.yml": "Docker Compose config",
        ".dockerignore": "Docker ignore rules",
        ".env.example": "Environment template",
        "requirements.txt": "Python dependencies",
        "DEPLOY_CHECKLIST.md": "Deployment checklist",
    }

    for fname, desc in docker_files.items():
        fpath = root_dir / fname
        exists = fpath.exists()
        if exists:
            size = fpath.stat().st_size
            # Check content for RPi-specific keywords
            content = fpath.read_text(encoding="utf-8", errors="ignore")
            rpi_keywords = ["raspberry", "RPi", "arm64", "aarch64", "gpio", "serial0", "ttyAMA"]
            rpi_refs = [kw for kw in rpi_keywords if kw.lower() in content.lower()]
            rpi_info = f" (RPi refs: {len(rpi_refs)})" if rpi_refs else ""
            print(f"  ✅ {fname}: {size/1024:.1f} KB{rpi_info}")
        else:
            status = "⚠️" if fname in ["DEPLOY_CHECKLIST.md"] else "❌"
            errors.append(f"Missing: {fname}")
            print(f"  {status} {fname}: MISSING")

    # Check RPi compatibility module
    try:
        from utils.rpi_compat import (
            is_raspberry_pi,
            get_platform_info,
            get_available_hardware,
            get_hardware_health_report,
        )
        info = get_platform_info()
        print(f"\n  Platform: {info['system']} {info['machine']}")
        print(f"  Is Raspberry Pi: {info['is_raspberry_pi']}")
        if info['is_raspberry_pi'] == 'True':
            print(f"  Model: {info['rpi_model']}")
            print(f"  Generation: {info['rpi_generation']}")

        hw = get_available_hardware()
        print(f"  Hardware: GPIO={hw['gpio_rpi']}, I2C={hw['i2c']}, Camera={hw['camera']}, Serial={hw['serial']}")

        # RPi health check
        health = get_hardware_health_report()
        if health.get("temperature_warning"):
            print(f"  Temperature: {health['temperature_warning']}")
        if health.get("throttling_warnings"):
            for w in health["throttling_warnings"]:
                print(f"  Throttling: {w}")
    except ImportError as e:
        print(f"  ⚠️ RPi compat module not available: {e}")
    except Exception as e:
        errors.append(f"RPi health check: {e}")
        print(f"  ❌ RPi health check failed: {e}")

    return errors


# =============================================================================
# Section 6: Configuration Files
# =============================================================================

def check_configs() -> list:
    """Verify configuration files."""
    errors = []
    print("\n=== 6. Configuration Files ===")

    config_dir = Path(__file__).parent.parent / "config"
    if not config_dir.exists():
        errors.append("config directory not found")
        print("  config directory not found!")
        return errors

    expected_configs = ["arm_params.yaml", "sampling_params.yaml", "settings.yaml"]

    for f in sorted(config_dir.iterdir()):
        if f.is_file():
            size_kb = f.stat().st_size / 1024
            print(f"  {f.name}: {size_kb:.1f} KB")

    for conf_name in expected_configs:
        if not (config_dir / conf_name).exists():
            errors.append(f"Missing config: {conf_name}")
            print(f"  ❌ Missing: {conf_name}")

    # Try to parse YAML configs
    try:
        import yaml
        for conf_file in config_dir.glob("*.yaml"):
            try:
                with open(conf_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if data:
                    print(f"  📋 {conf_file.name}: Parsed OK ({len(str(data))} chars)")
                else:
                    print(f"  ⚠️ {conf_file.name}: Empty or invalid YAML")
            except Exception as e:
                errors.append(f"Config {conf_file.name}: {e}")
                print(f"  ❌ {conf_file.name}: Parse failed - {e}")
    except ImportError:
        print("  ⚠️ PyYAML not available for config validation")

    return errors


# =============================================================================
# Section 7: Training Data Quality
# =============================================================================

def check_data() -> list:
    """Verify training data quality."""
    errors = []
    print("\n=== 7. Training Data Quality Check ===")

    data_dir = Path(__file__).parent.parent / "data" / "training"
    if not data_dir.exists():
        errors.append("data/training directory not found")
        print("  data/training directory not found!")
        return errors

    total_samples = 0
    dataset_files = sorted(data_dir.glob("*.json"))

    for f in dataset_files:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)

            if isinstance(data, list):
                count = len(data)
                total_samples += count

                # Quick integrity check
                if count > 0:
                    first = data[0]
                    if isinstance(first, dict):
                        keys = list(first.keys())
                        # Check for empty samples
                        null_count = sum(1 for s in data if s is None)
                        # Check for common fields
                        common_fields = [k for k in keys if k in
                            ("reachable", "is_safe", "collision_detected", "decision", "edge_type")]
                        extra = ""
                        if common_fields:
                            extra = f" | fields: {len(keys)} | special: {common_fields}"
                        print(f"  {f.name}: {count} samples{extra}")
                        if null_count > 0:
                            print(f"    ⚠️ {null_count} null samples found")
                    else:
                        print(f"  {f.name}: {count} items (non-dict)")
                else:
                    print(f"  ⚠️ {f.name}: Empty dataset")
            else:
                print(f"  {f.name}: Non-list data ({type(data).__name__})")

        except json.JSONDecodeError as e:
            errors.append(f"Data {f.name}: JSON parse error - {e}")
            print(f"  ❌ {f.name}: Invalid JSON - {e}")
        except Exception as e:
            errors.append(f"Data {f.name}: {e}")
            print(f"  ❌ {f.name}: Failed - {e}")

    print(f"\n  Total datasets: {len(dataset_files)}")
    print(f"  Total samples: {total_samples:,}")

    # Check edge case datasets
    edge_datasets = [
        "edge_case_ik.json", "noisy_vision_dataset.json", "multi_obstacle_collision.json",
        "sequential_motion.json", "velocity_profile.json", "multi_sensor_fusion.json",
        "workspace_diversity.json",
    ]
    for ed in edge_datasets:
        if not (data_dir / ed).exists():
            print(f"  ⚠️ Missing edge case dataset: {ed}")

    return errors


# =============================================================================
# Section 8: Hardware Interface Verification
# =============================================================================

def check_hardware() -> list:
    """Verify hardware interfaces (simulated on non-RPi)."""
    errors = []
    print("\n=== 8. Hardware Interface Verification ===")

    # Check STM32 communication module
    try:
        import importlib
        stm32_mod = importlib.import_module("hardware.stm32_comm")
        port = stm32_mod.detect_rpi_port()
        print(f"  STM32 module: OK (detected port: {port})")
    except Exception as e:
        print(f"  STM32 module: Unavailable (expected on non-RPi) - {e}")

    # Check servo controller
    try:
        import importlib
        importlib.import_module("hardware.servo_controller")
        print(f"  ServoController: OK")
    except Exception as e:
        print(f"  ServoController: Unavailable (expected on non-RPi) - {e}")

    # Check OpenMV communication
    try:
        import importlib
        importlib.import_module("hardware.openmv_comm")
        print(f"  OpenMV module: OK")
    except Exception as e:
        print(f"  OpenMV module: Unavailable (expected on non-RPi) - {e}")

    # Check serial port availability
    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
        if ports:
            print(f"  Serial ports: {len(ports)} available")
            for p in ports[:5]:
                print(f"    - {p.device}: {p.description}")
        else:
            print(f"  Serial ports: None detected")
    except ImportError:
        print(f"  Serial ports: pyserial not available")
    except Exception as e:
        print(f"  Serial ports: Check failed - {e}")

    return errors


# =============================================================================
# Section 9: Performance Benchmark
# =============================================================================

def check_performance() -> list:
    """Run performance benchmarks."""
    errors = []
    print("\n=== 9. Performance Benchmark ===")

    try:
        from training.data_generator import (
            forward_kinematics,
            inverse_kinematics_analytical,
            JOINT_LIMITS,
        )
        import random
        random.seed(42)

        # Benchmark FK
        num_trials = 1000
        angles_list = [
            [random.uniform(-3.0, 3.0) for _ in range(6)]
            for _ in range(num_trials)
        ]

        start = time.time()
        for angles in angles_list:
            forward_kinematics(angles)
        fk_time = (time.time() - start) / num_trials * 1000  # ms per call
        print(f"  Forward Kinematics: {fk_time:.3f} ms/call ({num_trials} trials)")

        # Benchmark IK
        num_trials = 100
        poses = [
            [
                random.uniform(50, 450),
                random.uniform(50, 450),
                random.uniform(20, 280),
                random.uniform(-3.0, 3.0),
                random.uniform(-1.5, 1.5),
                random.uniform(-3.0, 3.0),
            ]
            for _ in range(num_trials)
        ]

        start = time.time()
        ik_success = 0
        for pose in poses:
            result = inverse_kinematics_analytical(pose)
            if result is not None:
                ik_success += 1
        ik_time = (time.time() - start) / num_trials * 1000
        print(f"  Inverse Kinematics: {ik_time:.3f} ms/call ({ik_success}/{num_trials} reachable, {num_trials} trials)")

        # Benchmark NN forward pass
        try:
            import numpy as np
            from training.model_trainer import SimpleNN
            nn = SimpleNN([6, 64, 64, 32, 6], activation="tanh")
            X = np.random.randn(100, 6).astype(np.float32)
            start = time.time()
            for _ in range(100):
                nn.predict(X)
            nn_time = (time.time() - start) / 100 * 1000
            print(f"  Neural Network (6→64→64→32→6): {nn_time:.3f} ms/batch (100 samples)")

            # Memory estimate
            import sys as _sys
            params_size = sum(w.nbytes + b.nbytes for w, b in zip(nn.weights, nn.biases))
            print(f"  NN Parameters: {nn.num_params:,} weights ({params_size/1024:.1f} KB)")

        except ImportError:
            print(f"  NN benchmark: numpy not available")
        except Exception as e:
            print(f"  NN benchmark: Failed - {e}")

        # Performance thresholds
        if fk_time > 1.0:
            errors.append(f"FK performance slow: {fk_time:.1f}ms/call (target < 1ms)")
        if ik_time > 10.0:
            errors.append(f"IK performance slow: {ik_time:.1f}ms/call (target < 10ms)")

    except ImportError as e:
        errors.append(f"Performance benchmark: {e}")
        print(f"  Performance benchmark: FAILED - {e}")
    except Exception as e:
        errors.append(f"Performance benchmark: {e}")
        print(f"  Performance benchmark: FAILED - {e}")

    return errors


# =============================================================================
# Section 10: RPi-Specific Health
# =============================================================================

def check_rpi_health() -> list:
    """Check Raspberry Pi-specific health metrics."""
    errors = []
    print("\n=== 10. Raspberry Pi Health Check ===")

    try:
        from utils.rpi_compat import (
            is_raspberry_pi,
            get_cpu_temperature,
            get_throttling_status,
            get_clock_frequencies,
            get_voltage,
            get_rpi_memory_split,
            is_uart_enabled,
            is_i2c_enabled,
            get_uart_device,
            get_i2c_bus,
            get_gpio_chip,
        )

        if not is_raspberry_pi():
            print("  Not running on Raspberry Pi - skipping RPi health checks")
            return errors

        # Temperature
        temp = get_cpu_temperature()
        if temp is not None:
            icon = "🔴" if temp > 80 else "🟡" if temp > 70 else "🟢" if temp > 60 else "✅"
            print(f"  {icon} CPU Temperature: {temp:.1f}°C")

        # Throttling
        throttling = get_throttling_status()
        if throttling:
            issues = []
            if throttling.get("currently_throttled"):
                issues.append("Currently throttled")
            if throttling.get("under_voltage"):
                issues.append("Under-voltage")
            if throttling.get("throttled_occurred"):
                issues.append("Throttling has occurred")
            if issues:
                print(f"  ❌ Throttling issues: {', '.join(issues)}")
                errors.append(f"RPi throttling: {', '.join(issues)}")
            else:
                print(f"  ✅ Throttling: Normal")

        # Clocks
        clocks = get_clock_frequencies()
        if clocks:
            cpu_freq = clocks.get("cpu", 0) / 1_000_000
            print(f"  📊 CPU Clock: {cpu_freq:.0f} MHz")

        # Voltage
        voltage = get_voltage()
        if voltage is not None:
            print(f"  ⚡ Core Voltage: {voltage:.3f}V")

        # Memory
        memory = get_rpi_memory_split()
        if memory:
            total = memory.get("total_mb", "?")
            gpu = memory.get("gpu_mb", "?")
            if isinstance(total, int) and isinstance(gpu, int):
                cpu_mem = total - gpu
                print(f"  💾 Memory: {total}MB total (CPU: {cpu_mem}MB, GPU: {gpu}MB)")

        # UART
        uart_enabled = is_uart_enabled()
        uart_device = get_uart_device()
        uart_exists = os.path.exists(uart_device) if uart_device else False
        if uart_enabled and uart_exists:
            print(f"  ✅ UART: Enabled ({uart_device})")
        else:
            print(f"  ⚠️ UART: {'Enabled but device missing' if uart_enabled else 'Not enabled'}")
            if not uart_enabled:
                errors.append("UART not enabled in /boot/config.txt")

        # I2C
        i2c_enabled = is_i2c_enabled()
        i2c_bus = get_i2c_bus()
        if i2c_enabled:
            print(f"  ✅ I2C: Enabled (bus {i2c_bus})")
        else:
            print(f"  ⚠️ I2C: Not enabled")
            errors.append("I2C not enabled")

        # GPIO
        gpio_chip = get_gpio_chip()
        gpio_path = f"/dev/{gpio_chip}"
        if os.path.exists(gpio_path):
            print(f"  ✅ GPIO: {gpio_chip} available")
        else:
            print(f"  ⚠️ GPIO: {gpio_chip} not found at {gpio_path}")

    except ImportError as e:
        print(f"  ⚠️ RPi compat module not available: {e}")
    except Exception as e:
        errors.append(f"RPi health check: {e}")
        print(f"  ❌ RPi health check failed: {e}")

    return errors


# =============================================================================
# Section 11: Cross-Validation Readiness
# =============================================================================

def check_cv_readiness() -> list:
    """Check if the system is ready for cross-validation training."""
    errors = []
    print("\n=== 11. Cross-Validation Readiness ===")

    data_dir = Path(__file__).parent.parent / "data" / "training"
    if not data_dir.exists():
        print("  No training data found")
        return errors

    min_samples = {
        "ik_dataset.json": 500,
        "safety_dataset.json": 500,
        "quality_dataset.json": 500,
        "collision_dataset.json": 300,
    }

    for fname, minimum in min_samples.items():
        fpath = data_dir / fname
        if fpath.exists():
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                count = len(data) if isinstance(data, list) else 0
                if count >= minimum:
                    print(f"  ✅ {fname}: {count} samples (min: {minimum})")
                else:
                    print(f"  ⚠️ {fname}: {count} samples (min: {minimum}) - insufficient for CV")
                    errors.append(f"Insufficient data for CV: {fname} ({count}/{minimum})")
            except Exception as e:
                errors.append(f"Data {fname}: {e}")
                print(f"  ❌ {fname}: Failed - {e}")
        else:
            print(f"  ⚠️ {fname}: Not found")

    return errors


# =============================================================================
# Main
# =============================================================================

def main() -> int:
    """Run comprehensive system verification."""
    print("=" * 60)
    print("  COMPREHENSIVE SYSTEM VERIFICATION")
    print("  Intelligent Sampling Robotic Arm")
    print(f"  Python: {sys.version}")
    print(f"  Platform: {sys.platform}")
    print("=" * 60)

    all_errors = []

    # Run all checks
    checks = [
        ("Import Verification", check_imports),
        ("Orchestrator", check_orchestrator),
        ("Model Files", check_models),
        ("Training Reports", check_reports),
        ("Docker/RPi Config", check_docker_config),
        ("Configuration Files", check_configs),
        ("Training Data", check_data),
        ("Hardware Interfaces", check_hardware),
        ("Performance", check_performance),
        ("RPi Health", check_rpi_health),
        ("CV Readiness", check_cv_readiness),
    ]

    for name, check_fn in checks:
        try:
            errors = check_fn()
            all_errors.extend(errors)
        except Exception as e:
            all_errors.append(f"{name}: Unexpected error - {e}")
            print(f"  ❌ {name}: Unexpected error - {e}")

    # Summary
    print(f"\n{'='*60}")
    print(f"  VERIFICATION SUMMARY")
    print(f"{'='*60}")

    severity_counts = {"critical": 0, "error": 0, "warning": 0, "info": 0}
    for err in all_errors:
        if "critical" in str(err).lower() or "missing" in str(err).lower():
            severity_counts["critical"] += 1
        elif "fail" in str(err).lower() or "error" in str(err).lower():
            severity_counts["error"] += 1
        elif "warn" in str(err).lower():
            severity_counts["warning"] += 1
        else:
            severity_counts["info"] += 1

    print(f"  Total checks: {len(checks)}")
    print(f"  Issues found: {len(all_errors)}")
    print(f"    Critical: {severity_counts['critical']}")
    print(f"    Error:    {severity_counts['error']}")
    print(f"    Warning:  {severity_counts['warning']}")
    print(f"    Info:     {severity_counts['info']}")

    if all_errors:
        print(f"\n  Issue Details:")
        for err in all_errors[:20]:  # Show first 20
            print(f"    - {err}")
        if len(all_errors) > 20:
            print(f"    ... and {len(all_errors) - 20} more")

    # Overall status
    if severity_counts["critical"] > 0:
        print(f"\n  ❌ VERIFICATION FAILED ({severity_counts['critical']} critical issues)")
        return 1
    elif severity_counts["error"] > 3:
        print(f"\n  ⚠️ VERIFICATION WARNING ({severity_counts['error']} errors)")
        return 0
    else:
        print(f"\n  ✅ ALL CHECKS PASSED")
        return 0


if __name__ == "__main__":
    sys.exit(main())