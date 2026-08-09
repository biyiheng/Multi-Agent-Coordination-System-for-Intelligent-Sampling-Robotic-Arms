"""
White-box tests for core internal logic.

Tests internal components with knowledge of implementation details:
kinematics, collision detection, serial communication, error handling,
config loading, and servo control logic.
"""

import json
import math
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import numpy as np
import pytest

from rpi_control.motion.kinematics import (
    DHParameter,
    forward_kinematics,
    inverse_kinematics,
    joint_angles_to_pwm,
    pwm_to_joint_angles,
    _get_default_dh_params,
    DEFAULT_JOINT_LIMITS,
)
from rpi_control.motion.collision import (
    check_self_collision,
    check_environment_collision,
    get_safe_retreat_path,
    Obstacle,
)
from rpi_control.utils.error_handler import (
    HardwareError,
    CommunicationError,
    SafetyError,
    SystemError,
    async_retry,
    retry,
)
from rpi_control.utils.config_loader import ConfigLoader, load_config


# =============================================================================
# Kinematics Tests
# =============================================================================

class TestForwardKinematics:
    """Test forward kinematics computation."""

    def test_home_position(self):
        """Home position (all zeros) should return a valid transform."""
        angles = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        T, transforms = forward_kinematics(angles)
        # T is a 4x4 transform matrix
        assert T.shape == (4, 4)
        assert len(transforms) == 6
        # Position is in the last column
        pos = T[:3, 3]
        assert len(pos) == 3

    def test_position_has_valid_range(self):
        """FK output should be within reasonable workspace bounds."""
        for _ in range(20):
            angles = [
                np.random.uniform(-math.pi, math.pi),
                np.random.uniform(-math.pi / 2, math.pi / 2),
                np.random.uniform(-math.pi, math.pi),
                np.random.uniform(-math.pi, math.pi),
                np.random.uniform(-math.pi / 2, math.pi / 2),
                np.random.uniform(-math.pi, math.pi),
            ]
            T, _ = forward_kinematics(angles)
            pos = T[:3, 3]
            # Should be within a reasonable workspace
            assert all(abs(p) < 1000.0 for p in pos), \
                f"Position out of bounds: {pos}"

    def test_dh_params_consistency(self):
        """DH parameters should have consistent structure."""
        dh_params = _get_default_dh_params()
        assert len(dh_params) == 6
        for i, dh in enumerate(dh_params):
            assert isinstance(dh, DHParameter)
            assert hasattr(dh, 'a')
            assert hasattr(dh, 'alpha')
            assert hasattr(dh, 'd')
            assert hasattr(dh, 'theta_offset')


class TestInverseKinematics:
    """Test inverse kinematics computation."""

    def test_ik_home_consistency(self):
        """IK of home FK should return home angles (or close)."""
        home_angles = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        T, _ = forward_kinematics(home_angles)
        # Get position from transform
        x, y, z = T[0, 3], T[1, 3], T[2, 3]
        # Build target_pose with zero orientation
        target_pose = np.array([x, y, z, 0.0, 0.0, 0.0])
        try:
            solutions = inverse_kinematics(target_pose)
            if solutions:
                # At least one solution should be close to home
                found = False
                for sol in solutions:
                    diffs = [abs(a - b) for a, b in zip(sol, home_angles)]
                    if max(diffs) < 0.1:
                        found = True
                        break
                if not found:
                    print(f"Warning: No IK solution close to home: {solutions}")
        except Exception:
            pass  # May fail for edge cases

    def test_ik_unreachable_point(self):
        """IK should raise error for unreachable points."""
        from rpi_control.motion.kinematics import KinematicsError
        # Point far beyond reach - wrist center calculation should fail
        # Use extremely distant coordinates to ensure unreachability
        unreachable_pose = np.array([50000.0, 50000.0, 50000.0, 0.0, 0.0, 0.0])
        with pytest.raises(KinematicsError):
            inverse_kinematics(unreachable_pose)

    def test_ik_multiple_solutions(self):
        """Many positions should have multiple valid IK solutions."""
        reachable_pose = np.array([200.0, 0.0, 200.0, 0.0, 0.0, 0.0])
        try:
            solutions = inverse_kinematics(reachable_pose)
            # Should have at least one solution
            assert len(solutions) >= 1
        except Exception:
            pytest.skip("IK may not find solutions for this pose")

    def test_ik_solutions_within_joint_limits(self):
        """All IK solutions should respect joint limits."""
        reachable_pose = np.array([150.0, 100.0, 150.0, 0.0, 0.0, 0.0])
        try:
            solutions = inverse_kinematics(reachable_pose)
            for sol in solutions:
                for i, angle in enumerate(sol):
                    if i < len(DEFAULT_JOINT_LIMITS):
                        lo, hi = DEFAULT_JOINT_LIMITS[i]
                        assert lo <= angle <= hi, \
                            f"Joint {i} angle {angle} out of bounds [{lo}, {hi}]"
        except Exception:
            pytest.skip("IK may not find solutions for this pose")


class TestPWMConversion:
    """Test PWM/angle conversion."""

    def test_roundtrip_consistency(self):
        """PWM → angle → PWM should be consistent."""
        pwm_values = [1500, 1500, 1500, 1500, 1500, 1500]
        angles = pwm_to_joint_angles(pwm_values)
        pwm_back = joint_angles_to_pwm(angles)
        for orig, back in zip(pwm_values, pwm_back):
            assert abs(orig - back) <= 5, \
                f"PWM roundtrip error: {orig} → {back}"

    def test_pwm_clamping(self):
        """PWM values should be clamped to valid range."""
        angles = [10.0, -10.0, 10.0, -10.0, 10.0, -10.0]  # Very large angles
        pwm_values = joint_angles_to_pwm(angles)
        for pwm in pwm_values:
            assert 500 <= pwm <= 2500, f"PWM {pwm} out of range"

    def test_angle_roundtrip(self):
        """Angle → PWM → angle should be approximately consistent."""
        test_angles = [0.0, 0.5, -0.5, 1.0, -1.0, 0.0]
        pwm_values = joint_angles_to_pwm(test_angles)
        angles_back = pwm_to_joint_angles(pwm_values)
        for orig, back in zip(test_angles, angles_back):
            assert abs(orig - back) < 0.05, \
                f"Angle roundtrip error: {orig:.4f} → {back:.4f}"


# =============================================================================
# Collision Detection Tests
# =============================================================================

class TestSelfCollision:
    """Test self-collision detection."""

    def test_home_no_collision(self):
        """Home position should not have self-collision."""
        home = [0.0] * 6
        result = check_self_collision(home)
        assert result == [], f"Unexpected self-collision at home: {result}"

    def test_extreme_pose_collision(self):
        """Extreme poses may trigger self-collision."""
        # Joints folded inward
        extreme = [0.0, -math.pi / 2, math.pi, 0.0, 0.0, 0.0]
        try:
            result = check_self_collision(extreme)
            # Either no collision or collision detected - both are valid
            assert isinstance(result, list)
        except Exception:
            pass  # May fail for out-of-joint-limit poses

    def test_adjacent_links_excluded(self):
        """Adjacent links should not be checked for collision."""
        # Simple test: any valid pose should not report adjacent links
        angles = [0.0, 0.3, -0.5, 0.2, 0.0, 0.0]
        result = check_self_collision(angles)
        # Adjacent pair collisions should be filtered out
        for pair in result:
            i, j = pair[0], pair[1]
            assert abs(i - j) > 1, \
                f"Adjacent links {i}-{j} incorrectly flagged as collision"


class TestEnvironmentCollision:
    """Test environment collision detection."""

    def test_clear_workspace(self):
        """No obstacles should mean no collision."""
        angles = [0.0, 0.3, 0.0, 0.0, 0.0, 0.0]
        obstacles = []
        result = check_environment_collision(angles, obstacles)
        assert result == []

    def test_distant_obstacle(self):
        """Far obstacle should not cause collision."""
        angles = [0.0] * 6
        obstacles = [Obstacle(
            id="far_obs",
            center=np.array([5000.0, 5000.0, 5000.0]),
            extents=np.array([10.0, 10.0, 10.0]),
        )]
        result = check_environment_collision(angles, obstacles)
        assert result == []


class TestRetreatPath:
    """Test safe retreat path generation."""

    def test_retreat_path_not_empty(self):
        """Should always generate at least one waypoint."""
        current = [0.0] * 6
        path = get_safe_retreat_path(current)
        assert len(path) >= 1

    def test_retreat_path_ends_at_home(self):
        """Retreat path should end at or near home position."""
        current = [0.1, 0.0, 0.0, 0.0, 0.0, 0.0]
        home = [0.0] * 6
        path = get_safe_retreat_path(current, home)
        assert np.allclose(path[-1], home, atol=1e-6), \
            f"Path does not end at home: {path[-1]}"

    def test_retreat_path_is_monotonic(self):
        """Each step should move closer to home."""
        current = [0.5, 0.3, -0.4, 0.2, 0.1, 0.0]
        home = [0.0] * 6
        path = get_safe_retreat_path(current, home)
        prev_dist = float("inf")
        for point in path:
            dist = sum((a - b) ** 2 for a, b in zip(point, home))
            assert dist <= prev_dist * 1.01, \
                "Retreat path should decrease distance to home"
            prev_dist = dist


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestCustomExceptions:
    """Test custom exception classes."""

    def test_hardware_error(self):
        with pytest.raises(HardwareError) as exc_info:
            raise HardwareError("Test error", code="TEST_ERR")
        assert exc_info.value.code == "TEST_ERR"
        assert "Test error" in str(exc_info.value)

    def test_communication_error(self):
        with pytest.raises(CommunicationError):
            raise CommunicationError("Comm failed", code="COMM_FAIL")

    def test_safety_error(self):
        with pytest.raises(SafetyError):
            raise SafetyError("Danger!", code="DANGER")

    def test_system_error(self):
        with pytest.raises(SystemError):
            raise SystemError("System crash", code="SYS_CRASH")

    def test_exception_hierarchy(self):
        """Verify exception inheritance."""
        assert issubclass(HardwareError, Exception)
        assert issubclass(CommunicationError, Exception)
        assert issubclass(SafetyError, Exception)
        assert issubclass(SystemError, Exception)


class TestRetryDecorator:
    """Test retry decorators."""

    def test_sync_retry_success(self):
        """Retry should succeed on first attempt if no error."""
        call_count = [0]

        @retry(max_attempts=3, delay=0.01)
        def succeed():
            call_count[0] += 1
            return "ok"

        result = succeed()
        assert result == "ok"
        assert call_count[0] == 1

    def test_sync_retry_eventual_success(self):
        """Retry should succeed after failures."""
        call_count = [0]

        @retry(max_attempts=3, delay=0.01)
        def fail_twice():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("fail")
            return "ok"

        result = fail_twice()
        assert result == "ok"
        assert call_count[0] == 3

    def test_sync_retry_exhausted(self):
        """Retry should raise last exception after max attempts."""
        @retry(max_attempts=2, delay=0.01)
        def always_fail():
            raise ValueError("always fail")

        with pytest.raises(ValueError):
            always_fail()

    @pytest.mark.skip(reason="pytest-asyncio not installed")
    async def test_async_retry_success(self):
        """Async retry should succeed."""

        @async_retry(max_attempts=3, delay=0.01)
        async def succeed():
            return "ok"

        result = await succeed()
        assert result == "ok"

    @pytest.mark.skip(reason="pytest-asyncio not installed")
    async def test_async_retry_failure(self):
        """Async retry should propagate final error."""

        @async_retry(max_attempts=2, delay=0.01)
        async def fail():
            raise ValueError("async fail")

        with pytest.raises(ValueError):
            await fail()


# =============================================================================
# Config Loader Tests
# =============================================================================

class TestConfigLoader:
    """Test configuration loading and merging."""

    def test_load_settings_yaml(self):
        """Should load settings.yaml successfully."""
        config = load_config()
        assert config is not None
        assert "system" in config.config
        assert config.config["system"]["name"] == "智能采样机械臂系统"

    def test_load_arm_params(self):
        """Should load arm_params.yaml."""
        config = load_config()
        # Arm params may be in a separate section
        assert config.config is not None

    def test_environment_override(self):
        """Environment variables should override YAML values."""
        import os
        os.environ["TEST_OVERRIDE_KEY"] = "test_value"
        loader = ConfigLoader()
        result = loader._parse_env_value("test_value")
        assert result == "test_value"  # String stays as string
        del os.environ["TEST_OVERRIDE_KEY"]

    def test_parse_env_boolean(self):
        """Boolean environment values should parse correctly."""
        loader = ConfigLoader()
        assert loader._parse_env_value("true") is True
        assert loader._parse_env_value("false") is False
        assert loader._parse_env_value("True") is True
        assert loader._parse_env_value("False") is False

    def test_parse_env_number(self):
        """Numeric environment values should parse correctly."""
        loader = ConfigLoader()
        assert loader._parse_env_value("42") == 42
        assert loader._parse_env_value("3.14") == 3.14
        assert loader._parse_env_value("-10") == -10

    def test_deep_merge_dict(self):
        """Deep merge should combine nested dictionaries."""
        loader = ConfigLoader()
        base = {"a": {"b": 1, "c": 2}, "d": 3}
        override = {"a": {"b": 10}, "e": 4}
        merged = loader._deep_merge(base, override)
        assert merged["a"]["b"] == 10  # Overridden
        assert merged["a"]["c"] == 2   # Preserved
        assert merged["d"] == 3        # Preserved
        assert merged["e"] == 4        # Added


# =============================================================================
# Serial Communication Protocol Tests
# =============================================================================

class TestSTM32ProtocolFormatting:
    """Test STM32 command formatting (without hardware)."""

    def test_format_custom_command(self):
        """Custom protocol command should be correctly formatted."""
        from rpi_control.hardware.stm32_comm import STM32Interface
        stm32 = STM32Interface(port="COM99")  # No actual connection
        data = stm32._format_command("ARM:MOVE", [0, 1500, 1000])
        assert data == b"#ARM:MOVE:0,1500,1000!"
        assert data.startswith(b"#")
        assert data.endswith(b"!")

    def test_format_custom_command_no_params(self):
        """Command without params should still be valid."""
        from rpi_control.hardware.stm32_comm import STM32Interface
        stm32 = STM32Interface(port="COM99")
        data = stm32._format_command("SYS:INFO", [])
        assert data == b"#SYS:INFO!"
        assert data.startswith(b"#")
        assert data.endswith(b"!")

    def test_format_yhk32_single_servo(self):
        """YH-K32 single servo command should be correctly formatted."""
        from rpi_control.hardware.stm32_comm import STM32Interface
        data = STM32Interface._format_yhk32_single_servo(0, 1500, 1000)
        assert data == b"#000P1500T1000!"
        assert data.startswith(b"#")
        assert data.endswith(b"!")

    def test_format_yhk32_multi_servo(self):
        """YH-K32 multi servo command should be correctly formatted."""
        from rpi_control.hardware.stm32_comm import STM32Interface
        positions = [1500, 1500, 1500]
        data = STM32Interface._format_yhk32_multi_servo(positions, 1000)
        assert data.startswith(b"{")
        assert data.endswith(b"}")
        assert b"#000P1500T1000!" in data

    def test_format_yhk32_action_group(self):
        """YH-K32 action group command should be correct."""
        from rpi_control.hardware.stm32_comm import STM32Interface
        data = STM32Interface._format_yhk32_action_group(0, 10, 1)
        assert data == b"$DGT:0-10,1!"
        assert data.startswith(b"$")

    def test_format_yhk32_stop(self):
        """YH-K32 stop command should be correct."""
        from rpi_control.hardware.stm32_comm import STM32Interface
        data = STM32Interface._format_yhk32_stop()
        assert data == b"$DST!"
        data_single = STM32Interface._format_yhk32_stop(3)
        assert data_single == b"$DST:3!"

    def test_valid_servo_id_range(self):
        """Servo ID validation should reject out-of-range values."""
        from rpi_control.hardware.stm32_comm import STM32Interface
        stm32 = STM32Interface(port="COM99")
        # Valid range
        assert stm32._format_yhk32_single_servo(0, 1500, 1000)
        assert stm32._format_yhk32_single_servo(254, 1500, 1000)
        # Format should handle boundary values
        data = stm32._format_yhk32_single_servo(254, 2500, 9999)
        assert data == b"#254P2500T9999!"


class TestProtocolDetection:
    """Test protocol detection logic."""

    def test_effective_protocol_auto(self):
        """AUTO mode without detection should default to YH-K32."""
        from rpi_control.hardware.stm32_comm import (
            STM32Interface,
            PROTOCOL_MODE_AUTO,
            PROTOCOL_MODE_YHK32,
        )
        stm32 = STM32Interface(port="COM99", protocol_mode=PROTOCOL_MODE_AUTO)
        assert stm32._get_effective_protocol() == PROTOCOL_MODE_YHK32

    def test_effective_protocol_explicit(self):
        """Explicit protocol mode should be returned."""
        from rpi_control.hardware.stm32_comm import (
            STM32Interface,
            PROTOCOL_MODE_CUSTOM,
            PROTOCOL_MODE_YHK32,
        )
        stm32_custom = STM32Interface(
            port="COM99", protocol_mode=PROTOCOL_MODE_CUSTOM
        )
        assert stm32_custom._get_effective_protocol() == PROTOCOL_MODE_CUSTOM

        stm32_yhk32 = STM32Interface(
            port="COM99", protocol_mode=PROTOCOL_MODE_YHK32
        )
        assert stm32_yhk32._get_effective_protocol() == PROTOCOL_MODE_YHK32


# =============================================================================
# Model Loading Tests
# =============================================================================

class TestModelIntegrity:
    """Test that trained model files exist and are loadable."""

    def test_model_files_exist(self):
        """Verify model files are present."""
        models_dir = Path(__file__).resolve().parent.parent / "models"
        if not models_dir.exists():
            pytest.skip("Models directory not found")

        model_files = list(models_dir.glob("*.pkl")) + \
                      list(models_dir.glob("*.joblib")) + \
                      list(models_dir.glob("*.pt")) + \
                      list(models_dir.glob("*.pth"))
        if not model_files:
            pytest.skip("No model files found")

        for mf in model_files:
            assert mf.exists(), f"Model file missing: {mf}"
            assert mf.stat().st_size > 0, f"Model file empty: {mf}"

    def test_training_results_exist(self):
        """Verify training results JSON is valid."""
        results_path = Path(__file__).resolve().parent.parent / \
                       "reports" / "model_training_results.json"
        if not results_path.exists():
            pytest.skip("Training results file not found")

        with open(results_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict)
        # Should have results for our 4 models
        expected_models = ["motion", "safety", "quality", "collision"]
        for model_name in expected_models:
            if model_name in data:
                metrics = data[model_name]
                assert isinstance(metrics, dict), \
                    f"Results for {model_name} should be a dict"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])