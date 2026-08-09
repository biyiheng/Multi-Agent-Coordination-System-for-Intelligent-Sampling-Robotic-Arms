"""Pytest configuration and shared fixtures for RPi control tests."""

import asyncio
import sys
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# Async fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Mock fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_stm32_interface():
    """Create a mock STM32 communication interface."""
    mock = MagicMock()
    mock.is_connected = True
    mock.connect = AsyncMock(return_value=True)
    mock.disconnect = AsyncMock(return_value=True)
    mock.send_command = AsyncMock(return_value="#CMD:OK!")
    mock.start_heartbeat = AsyncMock(return_value=True)
    mock.stop_heartbeat = AsyncMock(return_value=True)
    mock.get_joint_positions = AsyncMock(
        return_value=[1500, 1500, 1500, 1500, 1500, 1000]
    )
    return mock


@pytest.fixture
def mock_openmv_interface():
    """Create a mock OpenMV communication interface."""
    mock = MagicMock()
    mock.is_connected = True
    mock.connect = AsyncMock(return_value=True)
    mock.disconnect = AsyncMock(return_value=True)
    mock.detect_color = AsyncMock(
        return_value={"red": [{"x": 120, "y": 80, "area": 650}]}
    )
    mock.detect_apriltag = AsyncMock(
        return_value={"tags": [{"id": 0, "x": 100.0, "y": -50.0, "z": 300.0}]}
    )
    return mock


@pytest.fixture
def mock_servo_controller(mock_stm32_interface):
    """Create a mock servo controller."""
    from hardware.servo_controller import ServoController

    controller = ServoController(
        stm32_interface=mock_stm32_interface,
        open_pwm=500,
        close_pwm=1800,
        grip_force=1500,
        adaptive_enabled=True,
    )
    return controller


@pytest.fixture
def mock_config_loader():
    """Create a mock configuration loader."""
    from utils.config_loader import ConfigLoader

    config = ConfigLoader()
    config.config = {
        "system": {
            "name": "Test System",
            "version": "2.0.0",
            "log_level": "DEBUG",
        },
        "hardware": {
            "stm32": {"port": "/dev/ttyAMA0", "baudrate": 115200, "timeout": 0.5},
            "openmv": {"port": "/dev/ttyUSB0", "baudrate": 115200, "timeout": 1.0},
        },
        "web": {"host": "0.0.0.0", "port": 8000, "ws_port": 8001},
        "cloud": {"enabled": False, "sync_interval": 60},
        "database": {"url": "sqlite:///test.db"},
        "safety": {
            "max_joint_velocity": 500,
            "emergency_stop_timeout": 100,
            "watchdog_interval": 50,
        },
    }
    return config


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_joint_positions() -> list:
    """Sample joint positions for testing."""
    return [1500.0, 1500.0, 1500.0, 1500.0, 1500.0, 1000.0]


@pytest.fixture
def sample_cartesian_pose() -> dict:
    """Sample Cartesian pose for testing."""
    return {
        "x": 200.0,
        "y": 0.0,
        "z": 150.0,
        "roll": 0.0,
        "pitch": 0.0,
        "yaw": 0.0,
    }


@pytest.fixture
def sample_task_params() -> dict:
    """Sample task parameters for testing."""
    return {
        "name": "Test Grid Sampling",
        "type": "grid",
        "priority": "medium",
        "params": {
            "bounds": {
                "x_min": 0.0,
                "x_max": 100.0,
                "y_min": 0.0,
                "y_max": 100.0,
            },
            "spacing": 20.0,
            "z_height": 50.0,
        },
    }


@pytest.fixture
def sample_sampling_points() -> list:
    """Sample sampling points for testing."""
    return [
        {"x": 0.0, "y": 0.0, "z": 50.0},
        {"x": 20.0, "y": 0.0, "z": 50.0},
        {"x": 40.0, "y": 0.0, "z": 50.0},
        {"x": 0.0, "y": 20.0, "z": 50.0},
        {"x": 20.0, "y": 20.0, "z": 50.0},
        {"x": 40.0, "y": 20.0, "z": 50.0},
    ]


@pytest.fixture
def sample_vision_result() -> dict:
    """Sample vision detection result for testing."""
    return {
        "red": [
            {"x": 120, "y": 80, "w": 30, "h": 25, "area": 650},
        ],
        "blue": [
            {"x": 200, "y": 60, "w": 35, "h": 30, "area": 920},
        ],
        "green": [],
        "yellow": [],
    }


@pytest.fixture
def sample_quality_result() -> dict:
    """Sample quality inspection result for testing."""
    return {
        "score": 85.0,
        "passed": True,
        "defects": [],
        "dimensions": {"width": 20.0, "height": 15.0},
        "color_consistency": 0.92,
    }


# ---------------------------------------------------------------------------
# Environment fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_hardware_imports():
    """Mock hardware imports that are not available in test environment."""
    try:
        import serial
        _serial_available = True
    except ImportError:
        _serial_available = False

    patches = []
    if not _serial_available:
        patches.append(patch("serial.Serial", MagicMock()))
        patches.append(patch("serial.SerialException", type("SerialException", (Exception,), {})))

    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Create a temporary database path."""
    db_path = tmp_path / "test_sampling.db"
    return db_path


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """Create a temporary configuration directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


# ---------------------------------------------------------------------------
# pytest configuration
# ---------------------------------------------------------------------------


def pytest_configure(config):
    """Configure pytest for the project."""
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    )
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests",
    )
    config.addinivalue_line(
        "markers",
        "hardware: marks tests that require physical hardware",
    )


def pytest_collection_modifyitems(config, items):
    """Skip hardware tests by default unless --hardware flag is passed."""
    if not config.getoption("--hardware", default=False):
        skip_hardware = pytest.mark.skip(reason="Hardware not available")
        for item in items:
            if "hardware" in item.keywords:
                item.add_marker(skip_hardware)


def pytest_addoption(parser):
    """Add custom command-line options."""
    parser.addoption(
        "--hardware",
        action="store_true",
        default=False,
        help="Run tests that require physical hardware",
    )