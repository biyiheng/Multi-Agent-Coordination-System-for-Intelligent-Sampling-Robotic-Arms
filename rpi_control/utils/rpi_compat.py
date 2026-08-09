"""
Raspberry Pi Compatibility Module.

Provides platform-aware imports and hardware detection for seamless
cross-platform operation (Windows/Linux x86_64 → Raspberry Pi ARM).

Features:
- Automatic platform detection (RPi model, OS, architecture)
- Conditional GPIO/I2C/UART/SPI imports
- Hardware resource monitoring (CPU temp, memory, throttling)
- Graceful degradation when RPi hardware is not available
"""

import os
import platform
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


# =============================================================================
# Platform Detection
# =============================================================================

def is_raspberry_pi() -> bool:
    """Check if the code is running on a Raspberry Pi.

    Returns:
        True if running on any Raspberry Pi model.
    """
    # Check architecture
    if platform.machine() not in ("aarch64", "armv7l", "armv6l"):
        return False

    # Check for Raspberry Pi model file
    try:
        with open("/proc/device-tree/model", "r") as f:
            model = f.read().strip("\x00")
        return "Raspberry Pi" in model
    except (FileNotFoundError, PermissionError):
        pass

    # Check for Raspberry Pi-specific files
    if os.path.exists("/sys/firmware/devicetree/base/model"):
        try:
            with open("/sys/firmware/devicetree/base/model", "r") as f:
                model = f.read().strip("\x00")
            return "Raspberry Pi" in model
        except (FileNotFoundError, PermissionError):
            pass

    return False


def get_rpi_model() -> str:
    """Get the Raspberry Pi model name.

    Returns:
        Model string like 'Raspberry Pi 5 Model B Rev 1.0' or 'unknown'.
    """
    try:
        with open("/proc/device-tree/model", "r") as f:
            return f.read().strip("\x00")
    except (FileNotFoundError, PermissionError):
        pass

    try:
        with open("/sys/firmware/devicetree/base/model", "r") as f:
            return f.read().strip("\x00")
    except (FileNotFoundError, PermissionError):
        pass

    return "unknown"


def get_rpi_generation() -> str:
    """Get the Raspberry Pi generation.

    Returns:
        One of: 'pi5', 'pi4', 'pi3', 'pi2', 'pi1', 'zero', 'generic'
    """
    model = get_rpi_model()
    if "Raspberry Pi 5" in model:
        return "pi5"
    elif "Raspberry Pi 4" in model:
        return "pi4"
    elif "Raspberry Pi 3" in model:
        return "pi3"
    elif "Raspberry Pi 2" in model:
        return "pi2"
    elif "Raspberry Pi Zero 2" in model:
        return "zero2"
    elif "Raspberry Pi Zero" in model:
        return "zero"
    elif "Raspberry Pi" in model:
        return "pi1"
    return "generic"


def get_platform_info() -> Dict[str, str]:
    """Get comprehensive platform information.

    Returns:
        Dict with platform details.
    """
    info = {
        "system": platform.system(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "is_raspberry_pi": str(is_raspberry_pi()),
        "rpi_model": get_rpi_model() if is_raspberry_pi() else "N/A",
        "rpi_generation": get_rpi_generation() if is_raspberry_pi() else "N/A",
    }

    # Memory info
    try:
        import psutil
        mem = psutil.virtual_memory()
        info["total_memory_mb"] = str(mem.total // (1024 * 1024))
        info["available_memory_mb"] = str(mem.available // (1024 * 1024))
    except ImportError:
        info["total_memory_mb"] = "unknown"
        info["available_memory_mb"] = "unknown"

    return info


# =============================================================================
# Hardware Interface Imports (Conditional)
# =============================================================================

# GPIO
HAS_RPI_GPIO = False
HAS_GPIOZERO = False
try:
    if is_raspberry_pi():
        import RPi.GPIO as GPIO  # noqa: F401
        HAS_RPI_GPIO = True
except ImportError:
    pass

try:
    if is_raspberry_pi():
        import gpiozero  # noqa: F401
        HAS_GPIOZERO = True
except ImportError:
    pass

# I2C
HAS_SMBUS2 = False
try:
    if is_raspberry_pi():
        import smbus2  # noqa: F401
        HAS_SMBUS2 = True
except ImportError:
    pass

# Camera
HAS_PICAMERA2 = False
try:
    if is_raspberry_pi():
        import picamera2  # noqa: F401
        HAS_PICAMERA2 = True
except ImportError:
    pass

# Serial
HAS_PYSERIAL = False
try:
    import serial  # noqa: F401
    HAS_PYSERIAL = True
except ImportError:
    pass


def get_available_hardware() -> Dict[str, bool]:
    """Get which hardware interfaces are available.

    Returns:
        Dict mapping interface name to availability.
    """
    return {
        "gpio_rpi": HAS_RPI_GPIO,
        "gpio_zero": HAS_GPIOZERO,
        "i2c": HAS_SMBUS2,
        "camera": HAS_PICAMERA2,
        "serial": HAS_PYSERIAL,
        "is_raspberry_pi": is_raspberry_pi(),
    }


# =============================================================================
# RPi Hardware Monitoring
# =============================================================================

def get_cpu_temperature() -> Optional[float]:
    """Get Raspberry Pi CPU temperature.

    Returns:
        CPU temperature in Celsius, or None if not available.
    """
    if not is_raspberry_pi():
        return None

    # Try standard thermal zone path
    thermal_paths = [
        "/sys/class/thermal/thermal_zone0/temp",
        "/sys/class/hwmon/hwmon0/temp1_input",
    ]

    for path in thermal_paths:
        try:
            with open(path, "r") as f:
                temp_raw = f.read().strip()
                return float(temp_raw) / 1000.0
        except (FileNotFoundError, PermissionError, ValueError):
            continue

    return None


def get_throttling_status() -> Optional[Dict[str, bool]]:
    """Get Raspberry Pi throttling status.

    Returns:
        Dict with throttling flags, or None if not available.
    """
    if not is_raspberry_pi():
        return None

    try:
        with open("/sys/devices/platform/soc/soc:firmware/get_throttled", "r") as f:
            throttled = int(f.read().strip(), 16)

        return {
            "under_voltage": bool(throttled & 0x1),
            "arm_freq_capped": bool(throttled & 0x2),
            "currently_throttled": bool(throttled & 0x4),
            "soft_temp_limit": bool(throttled & 0x8),
            "under_voltage_occurred": bool(throttled & 0x10000),
            "arm_freq_capped_occurred": bool(throttled & 0x20000),
            "throttled_occurred": bool(throttled & 0x40000),
            "soft_temp_limit_occurred": bool(throttled & 0x80000),
        }
    except (FileNotFoundError, PermissionError, ValueError):
        return None


def get_clock_frequencies() -> Optional[Dict[str, int]]:
    """Get Raspberry Pi clock frequencies.

    Returns:
        Dict with clock frequencies in Hz, or None if not available.
    """
    if not is_raspberry_pi():
        return None

    clocks = {}
    clock_names = {
        "arm": "cpu",
        "core": "gpu_core",
        "h264": "h264",
        "isp": "isp",
        "v3d": "v3d",
        "uart": "uart",
        "pwm": "pwm",
        "emmc": "emmc",
        "pixel": "pixel",
        "vec": "vec",
        "hdmi": "hdmi",
        "dpi": "dpi",
    }

    for clock_id, name in clock_names.items():
        try:
            path = f"/sys/devices/platform/soc/soc:firmware/get_{clock_id}"
            with open(path, "r") as f:
                clocks[name] = int(f.read().strip())
        except (FileNotFoundError, PermissionError):
            pass

    return clocks if clocks else None


def get_voltage() -> Optional[float]:
    """Get Raspberry Pi core voltage.

    Returns:
        Core voltage in volts, or None if not available.
    """
    if not is_raspberry_pi():
        return None

    try:
        with open("/sys/devices/platform/soc/soc:firmware/get_voltage", "r") as f:
            voltage_uv = int(f.read().strip())
            return voltage_uv / 1_000_000.0
    except (FileNotFoundError, PermissionError, ValueError):
        return None


def get_rpi_memory_split() -> Optional[Dict[str, int]]:
    """Get Raspberry Pi GPU/CPU memory split.

    Returns:
        Dict with memory info in MB, or None if not available.
    """
    if not is_raspberry_pi():
        return None

    result = {}

    # Total memory
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    result["total_mb"] = int(line.split()[1]) // 1024
                    break
    except (FileNotFoundError, PermissionError):
        pass

    # GPU memory
    try:
        with open("/boot/config.txt", "r") as f:
            for line in f:
                if line.startswith("gpu_mem="):
                    result["gpu_mb"] = int(line.strip().split("=")[1])
                    break
    except (FileNotFoundError, PermissionError):
        pass

    return result if result else None


# =============================================================================
# Storage & Disk Checks (2GB Raspberry Pi Compatibility)
# =============================================================================

def get_disk_usage(path: str = "/") -> Optional[Dict[str, Any]]:
    """Get disk usage information for the given path.

    Designed for 2GB Raspberry Pi compatibility checks.

    Args:
        path: Filesystem path to check (default: root).

    Returns:
        Dict with disk usage info, or None if unavailable.
    """
    try:
        import shutil
        usage = shutil.disk_usage(path)
        total_gb = usage.total / (1024 ** 3)
        used_gb = usage.used / (1024 ** 3)
        free_gb = usage.free / (1024 ** 3)
        used_pct = (usage.used / usage.total) * 100

        return {
            "path": path,
            "total_gb": round(total_gb, 2),
            "used_gb": round(used_gb, 2),
            "free_gb": round(free_gb, 2),
            "used_percent": round(used_pct, 1),
            "is_low_space": free_gb < 2.0,
            "is_critical": free_gb < 0.5,
            "warning": (
                "CRITICAL: Less than 500MB free disk space"
                if free_gb < 0.5
                else "WARNING: Less than 2GB free disk space"
                if free_gb < 2.0
                else "OK"
            ),
        }
    except Exception:
        return None


def check_2gb_compatibility() -> Dict[str, Any]:
    """Check if the system meets 2GB Raspberry Pi requirements.

    Performs comprehensive checks for:
    - Total memory (RAM)
    - Available disk space
    - CPU architecture
    - Required directories

    Returns:
        Dict with compatibility check results.
    """
    result = {
        "passed": True,
        "checks": {},
        "warnings": [],
        "recommendations": [],
    }

    # 1. Memory check
    try:
        import psutil
        mem = psutil.virtual_memory()
        total_mb = mem.total // (1024 * 1024)
        available_mb = mem.available // (1024 * 1024)
        result["checks"]["memory"] = {
            "total_mb": total_mb,
            "available_mb": available_mb,
            "sufficient": total_mb >= 2048,
            "status": "pass" if total_mb >= 2048 else "warn",
        }
        if total_mb < 2048:
            result["warnings"].append(
                f"Only {total_mb}MB RAM available (recommended: 2048MB+). "
                "Consider using swap space or reducing memory limits."
            )
            result["recommendations"].append(
                "Reduce Docker memory limit to 512M: export RPI_MEMORY_LIMIT=512M"
            )
    except ImportError:
        result["checks"]["memory"] = {"status": "unknown", "note": "psutil not installed"}

    # 2. Disk space check
    disk = get_disk_usage("/")
    if disk:
        result["checks"]["disk"] = {
            "free_gb": disk["free_gb"],
            "total_gb": disk["total_gb"],
            "used_percent": disk["used_percent"],
            "sufficient": not disk["is_low_space"],
            "status": (
                "fail" if disk["is_critical"]
                else "warn" if disk["is_low_space"]
                else "pass"
            ),
        }
        if disk["is_low_space"]:
            result["warnings"].append(disk["warning"])
            result["recommendations"].append(
                "Clean up old logs: rm -rf logs/*.log"
            )
            result["recommendations"].append(
                "Remove old Docker images: docker system prune -a"
            )
            if disk["is_critical"]:
                result["passed"] = False
    else:
        result["checks"]["disk"] = {"status": "unknown", "note": "shutil.disk_usage failed"}

    # 3. Architecture check
    import platform as _platform
    arch = _platform.machine()
    result["checks"]["architecture"] = {
        "arch": arch,
        "is_arm": arch in ("aarch64", "armv7l", "armv6l"),
        "status": "pass" if arch in ("aarch64", "armv7l", "armv6l", "x86_64") else "warn",
    }

    # 4. Project directory check
    project_dir = Path(__file__).resolve().parent.parent
    result["checks"]["project_dir"] = {
        "path": str(project_dir),
        "exists": project_dir.exists(),
        "status": "pass" if project_dir.exists() else "fail",
    }

    # 5. Data directories check
    required_dirs = ["data", "logs", "models", "reports"]
    for d in required_dirs:
        dir_path = project_dir / d
        result["checks"][f"dir_{d}"] = {
            "path": str(dir_path),
            "exists": dir_path.exists(),
            "status": "pass" if dir_path.exists() else "warn",
        }
        if not dir_path.exists():
            result["warnings"].append(f"Directory missing: {dir_path}. Will be auto-created.")

    # 6. Overall assessment
    if not result["warnings"]:
        result["assessment"] = "System meets 2GB Raspberry Pi requirements."
    else:
        result["assessment"] = (
            f"System has {len(result['warnings'])} warning(s). "
            "May still run but with reduced performance."
        )

    return result


def get_hardware_health_report() -> Dict[str, Any]:
    """Generate a comprehensive hardware health report.

    Returns:
        Dict with hardware health information.
    """
    report: Dict[str, Any] = {
        "platform": get_platform_info(),
        "hardware_interfaces": get_available_hardware(),
    }

    if is_raspberry_pi():
        report["cpu_temperature_c"] = get_cpu_temperature()
        report["throttling"] = get_throttling_status()
        report["clocks"] = get_clock_frequencies()
        report["voltage"] = get_voltage()
        report["memory"] = get_rpi_memory_split()

        # Temperature warnings
        temp = report.get("cpu_temperature_c")
        if temp is not None:
            if temp > 80:
                report["temperature_warning"] = "CRITICAL: CPU temperature above 80°C"
            elif temp > 70:
                report["temperature_warning"] = "WARNING: CPU temperature above 70°C"
            elif temp > 60:
                report["temperature_warning"] = "INFO: CPU temperature above 60°C"
            else:
                report["temperature_warning"] = "OK"

        # Throttling warnings
        throttling = report.get("throttling")
        if throttling:
            warnings = []
            if throttling.get("currently_throttled"):
                warnings.append("CPU is currently throttled")
            if throttling.get("under_voltage"):
                warnings.append("Under-voltage detected")
            if throttling.get("throttled_occurred"):
                warnings.append("CPU throttling has occurred")
            report["throttling_warnings"] = warnings if warnings else ["OK"]

    return report


# =============================================================================
# Conditional Import Helper
# =============================================================================

def install_rpi_dependencies() -> Tuple[bool, str]:
    """Attempt to install Raspberry Pi-specific dependencies.

    Uses pip to install RPi.GPIO, gpiozero, smbus2, and picamera2
    if running on a Raspberry Pi.

    Returns:
        (success, message)
    """
    if not is_raspberry_pi():
        return False, "Not running on a Raspberry Pi"

    import subprocess

    packages = ["RPi.GPIO", "gpiozero", "smbus2"]
    rpi_gen = get_rpi_generation()

    # picamera2 only works on Bullseye+ (Pi 4/5)
    if rpi_gen in ("pi4", "pi5"):
        packages.append("picamera2")

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet"] + packages,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            return True, f"Successfully installed: {', '.join(packages)}"
        else:
            return False, f"Installation failed: {result.stderr}"
    except subprocess.TimeoutExpired:
        return False, "Installation timed out"
    except Exception as e:
        return False, f"Installation error: {e}"


# =============================================================================
# UART/I2C/SPI Helpers
# =============================================================================

def get_uart_device() -> str:
    """Get the correct UART device path for the current platform.

    Returns:
        Device path string.
    """
    if not is_raspberry_pi():
        if os.name == "nt":
            return "COM4"
        return "/dev/ttyUSB0"

    rpi_gen = get_rpi_generation()

    if rpi_gen in ("pi3", "pi4"):
        if os.path.exists("/dev/serial0"):
            return "/dev/serial0"
        return "/dev/ttyAMA0"
    elif rpi_gen == "pi5":
        return "/dev/ttyAMA0"
    elif rpi_gen in ("pi1", "pi2", "zero"):
        return "/dev/ttyAMA0"

    return "/dev/ttyAMA0"


def get_i2c_bus() -> int:
    """Get the I2C bus number for the current Raspberry Pi model.

    Returns:
        I2C bus number (usually 1 for modern Pi models).
    """
    if not is_raspberry_pi():
        return 1

    rpi_gen = get_rpi_generation()
    # Pi 1 Rev 1 used bus 0, all others use bus 1
    if rpi_gen == "pi1":
        model = get_rpi_model()
        if "Rev 1" in model or "0002" in model or "0003" in model:
            return 0
    return 1


def get_gpio_chip() -> str:
    """Get the GPIO chip device path for the current platform.

    Returns:
        GPIO chip path (e.g., 'gpiochip4' for Pi 5, 'gpiochip0' for Pi 4).
    """
    if not is_raspberry_pi():
        return "gpiochip0"

    rpi_gen = get_rpi_generation()
    if rpi_gen == "pi5":
        return "gpiochip4"
    return "gpiochip0"


def is_uart_enabled() -> bool:
    """Check if UART is enabled on the Raspberry Pi.

    Returns:
        True if UART is enabled.
    """
    if not is_raspberry_pi():
        return True  # Assume enabled on non-RPi

    # Check /boot/config.txt
    try:
        with open("/boot/config.txt", "r") as f:
            content = f.read()
            if "enable_uart=1" in content:
                return True
    except (FileNotFoundError, PermissionError):
        pass

    # Check /boot/firmware/config.txt (Pi 5 Bookworm)
    try:
        with open("/boot/firmware/config.txt", "r") as f:
            content = f.read()
            if "enable_uart=1" in content:
                return True
    except (FileNotFoundError, PermissionError):
        pass

    return False


def is_i2c_enabled() -> bool:
    """Check if I2C is enabled on the Raspberry Pi.

    Returns:
        True if I2C is enabled.
    """
    if not is_raspberry_pi():
        return True  # Assume enabled on non-RPi

    # Check if I2C devices exist
    if os.path.exists("/dev/i2c-1"):
        return True

    # Check /boot/config.txt
    try:
        with open("/boot/config.txt", "r") as f:
            content = f.read()
            if "dtparam=i2c_arm=on" in content:
                return True
    except (FileNotFoundError, PermissionError):
        pass

    try:
        with open("/boot/firmware/config.txt", "r") as f:
            content = f.read()
            if "dtparam=i2c_arm=on" in content:
                return True
    except (FileNotFoundError, PermissionError):
        pass

    return False


# =============================================================================
# Main (for testing)
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Raspberry Pi Compatibility Check")
    print("=" * 60)

    info = get_platform_info()
    print("\nPlatform Info:")
    for key, value in info.items():
        print(f"  {key}: {value}")

    print("\nHardware Interfaces:")
    for name, available in get_available_hardware().items():
        status = "✅" if available else "❌"
        print(f"  {status} {name}")

    if is_raspberry_pi():
        print(f"\nUART Device: {get_uart_device()}")
        print(f"I2C Bus: {get_i2c_bus()}")
        print(f"GPIO Chip: {get_gpio_chip()}")
        print(f"UART Enabled: {is_uart_enabled()}")
        print(f"I2C Enabled: {is_i2c_enabled()}")

        temp = get_cpu_temperature()
        if temp is not None:
            print(f"CPU Temperature: {temp:.1f}°C")

        throttling = get_throttling_status()
        if throttling:
            print(f"Throttling: {throttling}")

    print("\nHealth Report:")
    report = get_hardware_health_report()
    print(f"  Temperature: {report.get('temperature_warning', 'N/A')}")
    throttle_warnings = report.get("throttling_warnings", ["N/A"])
    for w in throttle_warnings:
        print(f"  Throttling: {w}")