"""
Deep Raspberry Pi Compatibility Checker.

Performs comprehensive hardware and software compatibility verification
for the intelligent sampling robotic arm system on Raspberry Pi platforms.

Checks:
1. Hardware interface detection (GPIO, I2C, SPI, UART, Camera)
2. OS and kernel compatibility
3. Python dependency compatibility (ARM-specific)
4. Docker multi-architecture support
5. Memory and storage requirements
6. Real-time performance benchmarks
7. Power and thermal constraints
8. Network and connectivity options

Usage:
    python -m rpi_control.loop_engineering.tests.rpi_deep_check
"""

import json
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class RPiCheckResult:
    """Result of a single compatibility check."""
    name: str
    category: str
    passed: bool
    severity: str  # 'critical', 'warning', 'info'
    actual_value: str = ""
    expected_value: str = ""
    recommendation: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RPiDeepReport:
    """Complete RPi compatibility report."""
    timestamp: float = field(default_factory=time.time)
    platform_info: Dict[str, Any] = field(default_factory=dict)
    is_raspberry_pi: bool = False
    rpi_model: str = "unknown"
    checks: List[RPiCheckResult] = field(default_factory=list)
    total_checks: int = 0
    passed_checks: int = 0
    critical_failures: int = 0
    compatibility_score: float = 0.0
    overall_verdict: str = "unknown"
    recommendations: List[str] = field(default_factory=list)


class RPiDeepChecker:
    """Deep Raspberry Pi compatibility checker.

    Performs comprehensive hardware/software verification beyond basic
    platform detection.
    """

    # RPi model detection patterns
    RPI_MODEL_PATTERNS = {
        "RPi 5": ["BCM2712", "Raspberry Pi 5"],
        "RPi 4 Model B": ["BCM2711", "Raspberry Pi 4"],
        "RPi 3 Model B+": ["BCM2837B0", "Raspberry Pi 3 Model B Plus"],
        "RPi 3 Model B": ["BCM2837", "Raspberry Pi 3 Model B"],
        "RPi Zero 2 W": ["BCM2837", "Raspberry Pi Zero 2"],
        "RPi Zero W": ["BCM2835", "Raspberry Pi Zero W"],
        "RPi CM4": ["BCM2711", "Raspberry Pi Compute Module 4"],
    }

    # Minimum requirements per model
    MIN_REQUIREMENTS = {
        "RPi 5": {"ram_mb": 4096, "storage_mb": 8000, "python_version": "3.9"},
        "RPi 4 Model B": {"ram_mb": 2048, "storage_mb": 8000, "python_version": "3.9"},
        "RPi 3 Model B+": {"ram_mb": 512, "storage_mb": 4000, "python_version": "3.7"},
        "RPi Zero 2 W": {"ram_mb": 256, "storage_mb": 4000, "python_version": "3.7"},
    }

    # Required Python packages with ARM compatibility
    REQUIRED_PACKAGES = {
        "numpy": {"min_version": "1.21.0", "arm_compatible": True},
        "pyserial": {"min_version": "3.5", "arm_compatible": True},
        "RPi.GPIO": {"min_version": "0.7.0", "arm_compatible": True, "rpi_only": True},
        "adafruit-blinka": {"min_version": "8.0.0", "arm_compatible": True, "rpi_only": True},
        "opencv-python-headless": {"min_version": "4.5.0", "arm_compatible": True},
        "scipy": {"min_version": "1.7.0", "arm_compatible": True},
        "flask": {"min_version": "2.0.0", "arm_compatible": True},
        "sqlalchemy": {"min_version": "1.4.0", "arm_compatible": True},
    }

    # Hardware interface checks
    HARDWARE_INTERFACES = {
        "gpio": {
            "device_paths": ["/dev/gpiomem", "/dev/mem"],
            "kernel_modules": ["gpio"],
            "rpi_only": True,
        },
        "i2c": {
            "device_paths": ["/dev/i2c-1", "/dev/i2c-0"],
            "kernel_modules": ["i2c_dev", "i2c_bcm2835"],
            "config_file": "/boot/config.txt",
            "config_key": "dtparam=i2c_arm=on",
        },
        "spi": {
            "device_paths": ["/dev/spidev0.0", "/dev/spidev0.1"],
            "kernel_modules": ["spi_bcm2835"],
            "config_file": "/boot/config.txt",
            "config_key": "dtparam=spi=on",
        },
        "uart": {
            "device_paths": ["/dev/serial0", "/dev/ttyAMA0", "/dev/ttyS0"],
            "kernel_modules": [],
            "config_file": "/boot/config.txt",
            "config_key": "enable_uart=1",
        },
        "camera": {
            "device_paths": ["/dev/video0"],
            "kernel_modules": [],
            "config_file": "/boot/config.txt",
            "config_key": "start_x=1",
        },
    }

    def __init__(self, output_dir: str = "reports"):
        """Initialize the RPi deep checker.

        Args:
            output_dir: Output directory for reports.
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.checks: List[RPiCheckResult] = []

    def run_deep_check(self) -> RPiDeepReport:
        """Run comprehensive RPi compatibility check.

        Returns:
            RPiDeepReport with all check results.
        """
        print("=" * 60)
        print("  RPI DEEP COMPATIBILITY CHECK")
        print("=" * 60)

        report = RPiDeepReport()

        # 1. Platform detection
        print("\n[1/8] Platform Detection...")
        report.platform_info = self._detect_platform()
        report.is_raspberry_pi = report.platform_info.get("is_raspberry_pi", False)
        report.rpi_model = report.platform_info.get("rpi_model", "unknown")

        print(f"  Platform: {report.platform_info.get('system', 'unknown')}")
        print(f"  Machine: {report.platform_info.get('machine', 'unknown')}")
        print(f"  Is RPi: {report.is_raspberry_pi}")
        if report.is_raspberry_pi:
            print(f"  Model: {report.rpi_model}")

        # 2. OS & Kernel check
        print("\n[2/8] OS & Kernel Compatibility...")
        self.checks.extend(self._check_os_kernel())

        # 3. Hardware interfaces
        print("\n[3/8] Hardware Interfaces...")
        self.checks.extend(self._check_hardware_interfaces())

        # 4. Python & Dependencies
        print("\n[4/8] Python & Dependencies...")
        self.checks.extend(self._check_python_dependencies())

        # 5. Memory & Storage
        print("\n[5/8] Memory & Storage...")
        self.checks.extend(self._check_memory_storage(report))

        # 6. Docker compatibility
        print("\n[6/8] Docker Compatibility...")
        self.checks.extend(self._check_docker())

        # 7. Network & Connectivity
        print("\n[7/8] Network & Connectivity...")
        self.checks.extend(self._check_network())

        # 8. Performance benchmarks
        print("\n[8/8] Performance Benchmarks...")
        self.checks.extend(self._run_benchmarks())

        # Compile report
        report.checks = self.checks
        report.total_checks = len(self.checks)
        report.passed_checks = sum(1 for c in self.checks if c.passed)
        report.critical_failures = sum(
            1 for c in self.checks if not c.passed and c.severity == "critical"
        )
        report.compatibility_score = self._compute_score()
        report.overall_verdict = self._compute_verdict(report)
        report.recommendations = self._generate_recommendations(report)

        self._print_report(report)
        self._save_report(report)

        return report

    # =========================================================================
    # Platform Detection
    # =========================================================================

    def _detect_platform(self) -> Dict[str, Any]:
        """Detect platform information."""
        info = {
            "system": platform.system(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "is_raspberry_pi": False,
            "rpi_model": "unknown",
            "rpi_generation": "unknown",
        }

        # Check if running on Raspberry Pi
        try:
            # Method 1: Check /proc/cpuinfo
            if os.path.exists("/proc/cpuinfo"):
                with open("/proc/cpuinfo", "r") as f:
                    cpuinfo = f.read()
                    for model_name, patterns in self.RPI_MODEL_PATTERNS.items():
                        if any(p in cpuinfo for p in patterns):
                            info["is_raspberry_pi"] = True
                            info["rpi_model"] = model_name
                            if "5" in model_name:
                                info["rpi_generation"] = "5"
                            elif "4" in model_name:
                                info["rpi_generation"] = "4"
                            elif "3" in model_name:
                                info["rpi_generation"] = "3"
                            elif "Zero" in model_name:
                                info["rpi_generation"] = "zero"
                            break

            # Method 2: Check device tree model
            if not info["is_raspberry_pi"]:
                model_path = "/sys/firmware/devicetree/base/model"
                if os.path.exists(model_path):
                    with open(model_path, "r") as f:
                        model_str = f.read().strip("\x00")
                        for model_name, patterns in self.RPI_MODEL_PATTERNS.items():
                            if model_name in model_str:
                                info["is_raspberry_pi"] = True
                                info["rpi_model"] = model_name
                                break

            # Method 3: Check for RPi-specific files
            if not info["is_raspberry_pi"]:
                rpi_files = [
                    "/boot/config.txt",
                    "/sys/class/thermal/thermal_zone0/temp",
                ]
                if any(os.path.exists(f) for f in rpi_files):
                    info["is_raspberry_pi"] = True
                    info["rpi_model"] = "RPi (unknown model)"

        except Exception as e:
            info["detection_error"] = str(e)

        return info

    # =========================================================================
    # OS & Kernel Check
    # =========================================================================

    def _check_os_kernel(self) -> List[RPiCheckResult]:
        """Check OS and kernel compatibility.

        On non-RPi platforms (dev machines), OS checks are informational only
        since the target deployment is Raspberry Pi OS.
        """
        results = []
        on_rpi = self._is_rpi()

        # Check OS
        system = platform.system()
        is_linux = system == "Linux"
        if not on_rpi and not is_linux:
            # Non-RPi, non-Linux: dev machine — informational only
            severity = "info"
            passed = True  # Not a failure on dev machine
            recommendation = "Deploy to Raspberry Pi OS (Linux) for production"
        elif is_linux:
            severity = "info"
            passed = True
            recommendation = ""
        else:
            severity = "critical"
            passed = False
            recommendation = "Raspberry Pi OS (Linux) is required"

        results.append(RPiCheckResult(
            name="OS Type",
            category="os",
            passed=passed,
            severity=severity,
            actual_value=system,
            expected_value="Linux (Raspberry Pi OS)",
            recommendation=recommendation,
        ))

        # Check kernel version (only meaningful on Linux)
        if is_linux:
            try:
                kernel_ver = platform.release()
                major = int(kernel_ver.split(".")[0]) if kernel_ver else 0
                results.append(RPiCheckResult(
                    name="Kernel Version",
                    category="os",
                    passed=major >= 5,
                    severity="warning" if major < 5 else "info",
                    actual_value=kernel_ver,
                    expected_value=">= 5.x",
                    recommendation="Kernel 5.x+ recommended for best hardware support"
                        if major < 5 else "",
                ))
            except Exception:
                results.append(RPiCheckResult(
                    name="Kernel Version",
                    category="os",
                    passed=True,
                    severity="info",
                    actual_value="unable to detect",
                    expected_value=">= 5.x",
                ))

        # Check if running as root (needed for GPIO)
        if on_rpi:
            is_root = os.geteuid() == 0 if hasattr(os, "geteuid") else False
            results.append(RPiCheckResult(
                name="Root Access",
                category="os",
                passed=is_root,
                severity="warning" if not is_root else "info",
                actual_value="Yes" if is_root else "No",
                expected_value="Yes (for GPIO)",
                recommendation="Root access needed for GPIO operations" if not is_root else "",
            ))

        return results

    # =========================================================================
    # Hardware Interfaces
    # =========================================================================

    def _check_hardware_interfaces(self) -> List[RPiCheckResult]:
        """Check hardware interface availability.

        On non-RPi platforms, hardware checks are informational since
        the interfaces only exist on Raspberry Pi hardware.
        """
        results = []
        on_rpi = self._is_rpi()

        for interface, config in self.HARDWARE_INTERFACES.items():
            # Check device paths
            device_found = False
            for dev_path in config["device_paths"]:
                if os.path.exists(dev_path):
                    device_found = True
                    break

            # Check kernel modules
            modules_loaded = True
            for module in config["kernel_modules"]:
                if not self._check_kernel_module(module):
                    modules_loaded = False
                    break

            # Check config file
            config_enabled = True
            if "config_file" in config and "config_key" in config:
                config_enabled = self._check_boot_config(
                    config["config_file"],
                    config["config_key"],
                )

            is_rpi_only = config.get("rpi_only", False)

            if not on_rpi:
                # Non-RPi: all hardware checks are informational
                passed = True
                severity = "info"
                actual = "N/A (non-RPi platform)"
                expected = "Available on Raspberry Pi"
                recommendation = f"Verify {interface.upper()} on target RPi hardware"
            elif is_rpi_only:
                passed = device_found or modules_loaded or config_enabled
                severity = "critical" if not passed else "info"
                actual = (f"Device: {'Found' if device_found else 'Not found'}, "
                         f"Modules: {'Loaded' if modules_loaded else 'Not loaded'}")
                expected = "Available"
                recommendation = (f"Enable {interface.upper()} in /boot/config.txt"
                                 if not passed else "")
            else:
                passed = device_found or modules_loaded or config_enabled
                severity = "critical" if not passed and interface in ("gpio", "uart") else "warning"
                actual = (f"Device: {'Found' if device_found else 'Not found'}, "
                         f"Modules: {'Loaded' if modules_loaded else 'Not loaded'}")
                expected = "Available"
                recommendation = (f"Enable {interface.upper()} in /boot/config.txt"
                                 if not passed else "")

            results.append(RPiCheckResult(
                name=f"Interface: {interface.upper()}",
                category="hardware",
                passed=passed,
                severity=severity,
                actual_value=actual,
                expected_value=expected,
                recommendation=recommendation,
            ))

        return results

    def _check_kernel_module(self, module_name: str) -> bool:
        """Check if a kernel module is loaded."""
        try:
            result = subprocess.run(
                ["lsmod"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return module_name in result.stdout
        except Exception:
            # Try alternative method
            module_path = f"/sys/module/{module_name}"
            return os.path.exists(module_path)

    def _check_boot_config(self, config_file: str, config_key: str) -> bool:
        """Check if a config key is enabled in boot config."""
        try:
            if not os.path.exists(config_file):
                return False
            with open(config_file, "r") as f:
                content = f.read()
                return config_key in content and not config_key.startswith("#")
        except Exception:
            return False

    def _is_rpi(self) -> bool:
        """Check if running on Raspberry Pi."""
        try:
            return os.path.exists("/proc/device-tree/model")
        except Exception:
            return False

    # =========================================================================
    # Python Dependencies
    # =========================================================================

    def _check_python_dependencies(self) -> List[RPiCheckResult]:
        """Check Python package compatibility.

        On non-RPi platforms, missing packages are downgraded from critical
        to warning since the full environment is only needed on the target.
        """
        results = []
        on_rpi = self._is_rpi()

        # Python version
        py_ver = sys.version_info
        py_ok = py_ver >= (3, 9)
        results.append(RPiCheckResult(
            name="Python Version",
            category="dependencies",
            passed=py_ok,
            severity="critical" if (not py_ok and on_rpi) else ("warning" if not py_ok else "info"),
            actual_value=f"{py_ver.major}.{py_ver.minor}.{py_ver.micro}",
            expected_value=">= 3.9",
            recommendation="Upgrade Python to 3.9+" if not py_ok else "",
        ))

        # Check required packages
        for pkg_name, pkg_info in self.REQUIRED_PACKAGES.items():
            if pkg_info.get("rpi_only") and not on_rpi:
                continue

            try:
                module = __import__(pkg_name.replace("-", "_"), fromlist=["__version__"])
                version = getattr(module, "__version__", "unknown")
                min_ver = pkg_info["min_version"]

                # Parse version for comparison
                passed = self._compare_versions(version, min_ver) >= 0

                results.append(RPiCheckResult(
                    name=f"Package: {pkg_name}",
                    category="dependencies",
                    passed=passed,
                    severity="warning" if not passed else "info",
                    actual_value=version,
                    expected_value=f">= {min_ver}",
                    recommendation=f"Upgrade {pkg_name} to {min_ver}+" if not passed else "",
                ))
            except ImportError:
                # On non-RPi, downgrade severity for missing packages
                if on_rpi and not pkg_info.get("rpi_only", False):
                    severity = "critical"
                elif on_rpi:
                    severity = "warning"
                else:
                    severity = "warning"  # Non-RPi: informational

                results.append(RPiCheckResult(
                    name=f"Package: {pkg_name}",
                    category="dependencies",
                    passed=False,
                    severity=severity,
                    actual_value="Not installed",
                    expected_value=f">= {pkg_info['min_version']}",
                    recommendation=f"Install {pkg_name} via pip",
                ))

        # Check ARM compatibility
        machine = platform.machine()
        is_arm = machine in ("armv7l", "aarch64", "arm64")
        if on_rpi:
            passed = is_arm
            severity = "warning" if not is_arm else "info"
        else:
            passed = True  # Non-RPi: not applicable
            severity = "info"

        results.append(RPiCheckResult(
            name="ARM Architecture",
            category="dependencies",
            passed=passed,
            severity=severity,
            actual_value=machine,
            expected_value="armv7l / aarch64 (on RPi)",
            recommendation="Ensure ARM-compatible packages are installed" if not passed else "",
        ))

        return results

    def _compare_versions(self, v1: str, v2: str) -> int:
        """Compare two version strings. Returns -1, 0, or 1."""
        try:
            parts1 = [int(x) for x in v1.split(".")]
            parts2 = [int(x) for x in v2.split(".")]
            for p1, p2 in zip(parts1, parts2):
                if p1 < p2:
                    return -1
                if p1 > p2:
                    return 1
            return len(parts1) - len(parts2)
        except (ValueError, AttributeError):
            return 0

    # =========================================================================
    # Memory & Storage
    # =========================================================================

    def _check_memory_storage(self, report: RPiDeepReport) -> List[RPiCheckResult]:
        """Check memory and storage requirements."""
        results = []

        # Check RAM
        try:
            import psutil
            total_ram = psutil.virtual_memory().total / (1024 * 1024)
        except ImportError:
            # Fallback: read from /proc/meminfo
            try:
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        if "MemTotal" in line:
                            total_ram = int(line.split()[1]) / 1024
                            break
                    else:
                        total_ram = 0
            except Exception:
                total_ram = 0

        min_ram = self.MIN_REQUIREMENTS.get(report.rpi_model, {}).get("ram_mb", 512)
        results.append(RPiCheckResult(
            name="RAM",
            category="resources",
            passed=total_ram >= min_ram,
            severity="critical" if total_ram < min_ram else "info",
            actual_value=f"{total_ram:.0f} MB",
            expected_value=f">= {min_ram} MB",
            recommendation=f"Insufficient RAM for {report.rpi_model}" if total_ram < min_ram else "",
        ))

        # Check disk space
        try:
            disk = shutil.disk_usage("/")
            free_gb = disk.free / (1024**3)
            total_gb = disk.total / (1024**3)
            min_storage = self.MIN_REQUIREMENTS.get(report.rpi_model, {}).get("storage_mb", 4000) / 1024

            results.append(RPiCheckResult(
                name="Disk Space",
                category="resources",
                passed=free_gb >= min_storage,
                severity="warning",
                actual_value=f"{free_gb:.1f} GB free / {total_gb:.1f} GB total",
                expected_value=f">= {min_storage:.1f} GB free",
                recommendation="Free up disk space" if free_gb < min_storage else "",
            ))
        except Exception:
            results.append(RPiCheckResult(
                name="Disk Space",
                category="resources",
                passed=False,
                severity="warning",
                actual_value="Unable to detect",
                expected_value=">= 4 GB free",
                recommendation="Check available disk space",
            ))

        return results

    # =========================================================================
    # Docker Compatibility
    # =========================================================================

    def _check_docker(self) -> List[RPiCheckResult]:
        """Check Docker and multi-architecture support."""
        results = []

        # Check Docker installation
        docker_installed = shutil.which("docker") is not None
        results.append(RPiCheckResult(
            name="Docker Installed",
            category="docker",
            passed=docker_installed,
            severity="warning",
            actual_value="Yes" if docker_installed else "No",
            expected_value="Yes",
            recommendation="Install Docker for containerized deployment" if not docker_installed else "",
        ))

        # Check Docker Compose
        compose_installed = shutil.which("docker-compose") is not None or shutil.which("docker compose") is not None
        results.append(RPiCheckResult(
            name="Docker Compose",
            category="docker",
            passed=compose_installed,
            severity="info",
            actual_value="Yes" if compose_installed else "No",
            expected_value="Yes",
            recommendation="Install Docker Compose" if not compose_installed else "",
        ))

        # Check Dockerfile for ARM support
        dockerfile_path = Path(__file__).resolve().parent.parent.parent / "Dockerfile"
        if dockerfile_path.exists():
            with open(dockerfile_path, "r") as f:
                dockerfile_content = f.read()
                has_arm = "arm" in dockerfile_content.lower() or "aarch64" in dockerfile_content.lower()
                has_multi_arch = "--platform" in dockerfile_content

            results.append(RPiCheckResult(
                name="Dockerfile ARM Support",
                category="docker",
                passed=has_arm or has_multi_arch,
                severity="warning",
                actual_value=f"ARM refs: {'Yes' if has_arm else 'No'}, Multi-arch: {'Yes' if has_multi_arch else 'No'}",
                expected_value="ARM or multi-arch support",
                recommendation="Add ARM-compatible base images to Dockerfile" if not (has_arm or has_multi_arch) else "",
            ))

        # Check docker-compose.yml
        compose_path = Path(__file__).resolve().parent.parent.parent / "docker-compose.yml"
        if compose_path.exists():
            with open(compose_path, "r") as f:
                compose_content = f.read()
                has_rpi_config = "rpi" in compose_content.lower() or "raspberry" in compose_content.lower()

            results.append(RPiCheckResult(
                name="Docker Compose RPi Config",
                category="docker",
                passed=has_rpi_config,
                severity="info",
                actual_value="Yes" if has_rpi_config else "No",
                expected_value="RPi-specific config",
                recommendation="Add RPi-specific service configuration" if not has_rpi_config else "",
            ))

        return results

    # =========================================================================
    # Network & Connectivity
    # =========================================================================

    def _check_network(self) -> List[RPiCheckResult]:
        """Check network and connectivity options."""
        results = []

        # Check network interfaces
        try:
            import psutil
            net_ifaces = psutil.net_if_addrs()
            has_wifi = any("wlan" in name.lower() for name in net_ifaces)
            has_eth = any("eth" in name.lower() for name in net_ifaces)

            results.append(RPiCheckResult(
                name="Network Interfaces",
                category="network",
                passed=has_wifi or has_eth,
                severity="info",
                actual_value=f"WiFi: {'Yes' if has_wifi else 'No'}, Ethernet: {'Yes' if has_eth else 'No'}",
                expected_value="At least one network interface",
                recommendation="Check network connectivity" if not (has_wifi or has_eth) else "",
            ))
        except ImportError:
            results.append(RPiCheckResult(
                name="Network Interfaces",
                category="network",
                passed=True,
                severity="info",
                actual_value="psutil not available",
                expected_value="Network connectivity",
            ))

        # Check required ports
        required_ports = [5000, 8080, 8888]  # Web server, API, WebSocket
        for port in required_ports:
            try:
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(("localhost", port))
                sock.close()
                port_free = result != 0

                results.append(RPiCheckResult(
                    name=f"Port {port}",
                    category="network",
                    passed=port_free,
                    severity="info",
                    actual_value="Free" if port_free else "In use",
                    expected_value="Free",
                    recommendation=f"Port {port} is in use" if not port_free else "",
                ))
            except Exception:
                pass

        return results

    # =========================================================================
    # Performance Benchmarks
    # =========================================================================

    def _run_benchmarks(self) -> List[RPiCheckResult]:
        """Run lightweight performance benchmarks."""
        results = []

        # CPU benchmark
        try:
            start = time.perf_counter()
            # Simple matrix multiplication
            import numpy as np
            a = np.random.randn(100, 100)
            b = np.random.randn(100, 100)
            for _ in range(10):
                np.dot(a, b)
            cpu_time = (time.perf_counter() - start) * 1000

            # Acceptable thresholds per model
            if self._is_rpi():
                threshold = 100  # ms for RPi (slower)
            else:
                threshold = 30   # ms for desktop

            results.append(RPiCheckResult(
                name="CPU Benchmark (100x100 matmul x10)",
                category="performance",
                passed=cpu_time < threshold * 2,  # Allow 2x overhead
                severity="info",
                actual_value=f"{cpu_time:.1f} ms",
                expected_value=f"< {threshold} ms",
                recommendation="CPU performance may be insufficient" if cpu_time > threshold * 2 else "",
            ))
        except Exception:
            results.append(RPiCheckResult(
                name="CPU Benchmark",
                category="performance",
                passed=True,
                severity="info",
                actual_value="Skipped (numpy not available)",
                expected_value="< 100 ms",
            ))

        # File I/O benchmark
        try:
            test_file = self.output_dir / ".benchmark_test"
            data = b"x" * (1024 * 1024)  # 1 MB

            start = time.perf_counter()
            with open(test_file, "wb") as f:
                f.write(data)
            with open(test_file, "rb") as f:
                f.read()
            io_time = (time.perf_counter() - start) * 1000
            test_file.unlink(missing_ok=True)

            results.append(RPiCheckResult(
                name="File I/O (1MB read/write)",
                category="performance",
                passed=io_time < 500,
                severity="info",
                actual_value=f"{io_time:.1f} ms",
                expected_value="< 500 ms",
                recommendation="Storage performance may be slow" if io_time > 500 else "",
            ))
        except Exception:
            pass

        # Memory allocation benchmark
        try:
            start = time.perf_counter()
            arrays = [np.zeros((1000, 1000)) for _ in range(5)]
            _ = [a.sum() for a in arrays]
            mem_time = (time.perf_counter() - start) * 1000
            del arrays

            results.append(RPiCheckResult(
                name="Memory Allocation (5x 1000x1000)",
                category="performance",
                passed=mem_time < 1000,
                severity="info",
                actual_value=f"{mem_time:.1f} ms",
                expected_value="< 1000 ms",
                recommendation="Memory allocation may be slow" if mem_time > 1000 else "",
            ))
        except Exception:
            pass

        return results

    # =========================================================================
    # Scoring & Reporting
    # =========================================================================

    def _compute_score(self) -> float:
        """Compute overall compatibility score."""
        if not self.checks:
            return 0.0

        weights = {"critical": 5, "warning": 3, "info": 1}
        total_weight = sum(weights[c.severity] for c in self.checks)
        passed_weight = sum(weights[c.severity] for c in self.checks if c.passed)

        return round(passed_weight / total_weight, 4) if total_weight > 0 else 0.0

    def _compute_verdict(self, report: RPiDeepReport) -> str:
        """Compute overall compatibility verdict."""
        if not report.is_raspberry_pi:
            return "DEV PLATFORM — Deploy to Raspberry Pi for full validation"
        if report.critical_failures > 0:
            return "NOT COMPATIBLE — Critical issues found"
        if report.compatibility_score >= 0.95:
            return "FULLY COMPATIBLE — All checks passed"
        elif report.compatibility_score >= 0.80:
            return "COMPATIBLE — Minor issues found"
        elif report.compatibility_score >= 0.60:
            return "PARTIALLY COMPATIBLE — Some issues need attention"
        else:
            return "NOT RECOMMENDED — Significant compatibility issues"

    def _generate_recommendations(self, report: RPiDeepReport) -> List[str]:
        """Generate actionable recommendations."""
        recs = []

        # Non-RPi platform
        if not report.is_raspberry_pi:
            recs.append("ℹ Running on non-RPi dev platform — deploy to Raspberry Pi for full hardware validation")
            # On dev platform, only show package install recommendations
            for c in self.checks:
                if not c.passed and c.category == "dependencies" and c.severity == "warning":
                    if c.recommendation:
                        recs.append(f"🟡 [DEPS] {c.name}: {c.recommendation}")
            return recs

        # Critical failures first
        critical = [c for c in self.checks if not c.passed and c.severity == "critical"]
        for c in critical:
            recs.append(f"🔴 [CRITICAL] {c.name}: {c.recommendation}" if c.recommendation
                       else f"🔴 [CRITICAL] {c.name}: Action required")

        # Warnings
        warnings = [c for c in self.checks if not c.passed and c.severity == "warning"]
        for c in warnings[:5]:
            recs.append(f"🟡 [WARNING] {c.name}: {c.recommendation}" if c.recommendation
                       else f"🟡 [WARNING] {c.name}: Review recommended")

        # Model-specific
        if "RPi 3" in report.rpi_model:
            recs.append("⚠ RPi 3 has limited resources — consider RPi 4 or 5 for production")
        elif "Zero" in report.rpi_model:
            recs.append("⚠ RPi Zero has very limited resources — not recommended for production")

        return recs

    def _print_report(self, report: RPiDeepReport) -> None:
        """Print compatibility report."""
        print(f"\n{'='*60}")
        print("  RPI COMPATIBILITY REPORT")
        print(f"{'='*60}")
        print(f"  Platform: {report.platform_info.get('system', 'unknown')}")
        print(f"  Is RPi: {report.is_raspberry_pi}")
        if report.is_raspberry_pi:
            print(f"  Model: {report.rpi_model}")

        print(f"\n  Results: {report.passed_checks}/{report.total_checks} passed")
        print(f"  Critical Failures: {report.critical_failures}")
        print(f"  Compatibility Score: {report.compatibility_score:.2%}")
        print(f"  Verdict: {report.overall_verdict}")

        # Print failed checks
        failed = [c for c in report.checks if not c.passed]
        if failed:
            print(f"\n  Failed Checks ({len(failed)}):")
            for c in failed:
                icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(c.severity, "⚪")
                print(f"    {icon} [{c.severity.upper()}] {c.name}")
                print(f"       Actual: {c.actual_value}")
                print(f"       Expected: {c.expected_value}")
                if c.recommendation:
                    print(f"       → {c.recommendation}")

        if report.recommendations:
            print(f"\n  Recommendations:")
            for rec in report.recommendations:
                print(f"    {rec}")
        print(f"{'='*60}")

    def _save_report(self, report: RPiDeepReport) -> None:
        """Save compatibility report to disk."""
        filepath = self.output_dir / "rpi_deep_compat_report.json"
        data = {
            "timestamp": report.timestamp,
            "platform_info": report.platform_info,
            "is_raspberry_pi": report.is_raspberry_pi,
            "rpi_model": report.rpi_model,
            "total_checks": report.total_checks,
            "passed_checks": report.passed_checks,
            "critical_failures": report.critical_failures,
            "compatibility_score": report.compatibility_score,
            "overall_verdict": report.overall_verdict,
            "checks": [
                {
                    "name": c.name,
                    "category": c.category,
                    "passed": c.passed,
                    "severity": c.severity,
                    "actual_value": c.actual_value,
                    "expected_value": c.expected_value,
                    "recommendation": c.recommendation,
                }
                for c in report.checks
            ],
            "recommendations": report.recommendations,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  RPi report saved: {filepath}")


# =============================================================================
# Quick Runner
# =============================================================================

def run_rpi_deep_check(output_dir: str = "reports") -> RPiDeepReport:
    """Run deep RPi compatibility check.

    Args:
        output_dir: Output directory.

    Returns:
        RPiDeepReport.
    """
    checker = RPiDeepChecker(output_dir=output_dir)
    return checker.run_deep_check()


if __name__ == "__main__":
    report = run_rpi_deep_check()
    print(f"\nFinal Verdict: {report.overall_verdict}")