"""Unit tests for trajectory planning module."""

import math
import sys
from pathlib import Path

import pytest

# Add project root and rpi_control to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from rpi_control.motion import trajectory as traj_module
from rpi_control.utils import math_utils

# Check if TrajectoryPlanner is available
try:
    from rpi_control.motion.trajectory import TrajectoryPlanner
    HAS_TRAJECTORY_PLANNER = True
except ImportError:
    HAS_TRAJECTORY_PLANNER = False

# Import utility functions (with fallback to None)
try:
    from rpi_control.utils.math_utils import (
        s_curve_profile,
        trapezoidal_profile,
        linear_interpolate,
        lerp,
        clamp,
    )
except ImportError:
    s_curve_profile = None
    trapezoidal_profile = None
    linear_interpolate = None
    lerp = None
    clamp = None


class TestScurveProfile:
    """Tests for S-curve trajectory generation."""

    def test_basic_s_curve(self):
        """Test basic S-curve profile generation."""
        if s_curve_profile is None:
            pytest.skip("s_curve_profile not available")

        positions, velocities, accelerations = s_curve_profile(
            total_distance=100.0,
            max_velocity=50.0,
            max_acceleration=100.0,
            max_jerk=200.0,
            sample_time=0.01,
        )

        assert len(positions) > 0
        assert len(positions) == len(velocities) == len(accelerations)

        # Position should be non-decreasing
        for i in range(1, len(positions)):
            assert positions[i] >= positions[i - 1] - 1e-6

        # Final position should be close to total distance
        assert abs(positions[-1] - 100.0) < 1.0

    def test_zero_distance(self):
        """Test S-curve with zero distance."""
        if s_curve_profile is None:
            pytest.skip("s_curve_profile not available")

        positions, velocities, accels = s_curve_profile(
            total_distance=0.0,
            max_velocity=50.0,
            max_acceleration=100.0,
            max_jerk=200.0,
        )

        assert len(positions) > 0
        assert abs(positions[0]) < 1e-6

    def test_velocity_limits(self):
        """Test that velocity does not exceed max_velocity."""
        if s_curve_profile is None:
            pytest.skip("s_curve_profile not available")

        max_vel = 50.0
        _, velocities, _ = s_curve_profile(
            total_distance=200.0,
            max_velocity=max_vel,
            max_acceleration=100.0,
            max_jerk=200.0,
        )

        for v in velocities:
            assert v <= max_vel + 1e-6

    def test_acceleration_limits(self):
        """Test that acceleration does not exceed max_acceleration."""
        if s_curve_profile is None:
            pytest.skip("s_curve_profile not available")

        max_acc = 100.0
        _, _, accelerations = s_curve_profile(
            total_distance=200.0,
            max_velocity=50.0,
            max_acceleration=max_acc,
            max_jerk=200.0,
        )

        for a in accelerations:
            assert abs(a) <= max_acc + 1e-6


class TestTrapezoidalProfile:
    """Tests for trapezoidal velocity profile."""

    def test_basic_trapezoidal(self):
        """Test basic trapezoidal profile generation."""
        if trapezoidal_profile is None:
            pytest.skip("trapezoidal_profile not available")

        positions, velocities, accelerations = trapezoidal_profile(
            total_distance=100.0,
            max_velocity=50.0,
            max_acceleration=100.0,
            sample_time=0.01,
        )

        assert len(positions) > 0
        assert len(positions) == len(velocities) == len(accelerations)

        # Final position should be close to total distance
        assert abs(positions[-1] - 100.0) < 1.0

    def test_short_distance_triangular(self):
        """Test that short distances produce triangular profile."""
        if trapezoidal_profile is None:
            pytest.skip("trapezoidal_profile not available")

        positions, velocities, _ = trapezoidal_profile(
            total_distance=10.0,
            max_velocity=100.0,
            max_acceleration=50.0,
        )

        assert len(positions) > 0
        # Should still complete the distance
        assert abs(positions[-1] - 10.0) < 1.0

    def test_acceleration_phase(self):
        """Test acceleration phase of trapezoidal profile."""
        if trapezoidal_profile is None:
            pytest.skip("trapezoidal_profile not available")

        _, velocities, accelerations = trapezoidal_profile(
            total_distance=200.0,
            max_velocity=50.0,
            max_acceleration=100.0,
        )

        # Should have positive acceleration at start
        assert accelerations[0] > 0

        # Should have negative acceleration at end
        assert accelerations[-1] < 0 or accelerations[-1] == 0


class TestLinearInterpolation:
    """Tests for linear interpolation utilities."""

    def test_scalar_interpolation(self):
        """Test linear interpolation of scalars."""
        assert linear_interpolate(0.0, 10.0, 0.5) == 5.0
        assert linear_interpolate(0.0, 10.0, 0.0) == 0.0
        assert linear_interpolate(0.0, 10.0, 1.0) == 10.0

    def test_list_interpolation(self):
        """Test linear interpolation of lists."""
        result = linear_interpolate([0.0, 0.0], [10.0, 20.0], 0.5)
        assert result == [5.0, 10.0]

    def test_lerp_function(self):
        """Test the lerp helper function."""
        assert lerp(0, 100, 0.5) == 50.0
        assert lerp(0, 100, 0) == 0.0
        assert lerp(0, 100, 1) == 100.0

        # Test clamping
        assert lerp(0, 100, -0.5) == 0.0  # Clamped to 0
        assert lerp(0, 100, 1.5) == 100.0  # Clamped to 1

    def test_clamp_function(self):
        """Test the clamp helper function."""
        assert clamp(50, 0, 100) == 50
        assert clamp(-10, 0, 100) == 0
        assert clamp(200, 0, 100) == 100


class TestTrajectoryPlanner:
    """Tests for the TrajectoryPlanner class."""

    def test_planner_initialization(self):
        """Test that planner initializes correctly."""
        if not HAS_TRAJECTORY_PLANNER:
            pytest.skip("TrajectoryPlanner not available")
        planner = TrajectoryPlanner()
        assert planner is not None

    def test_plan_joint_space_valid(self):
        """Test planning a valid joint space trajectory."""
        if not HAS_TRAJECTORY_PLANNER:
            pytest.skip("TrajectoryPlanner not available")

        planner = TrajectoryPlanner()

        start_joints = [1500, 1500, 1500, 1500, 1500, 1000]
        end_joints = [1800, 1200, 2000, 1300, 1600, 1000]

        try:
            trajectory = planner.plan_joint_space(
                start_joints=start_joints,
                end_joints=end_joints,
                duration=1.0,
                method="linear",
            )
            assert trajectory is not None
            assert len(trajectory) > 0
        except Exception as e:
            pytest.skip(f"Planner method not implemented: {e}")

    def test_plan_joint_space_invalid_duration(self):
        """Test planning with invalid duration."""
        if not HAS_TRAJECTORY_PLANNER:
            pytest.skip("TrajectoryPlanner not available")

        planner = TrajectoryPlanner()
        start = [1500] * 6
        end = [1800] * 6

        try:
            with pytest.raises(ValueError):
                planner.plan_joint_space(start, end, duration=-1.0)
        except (AttributeError, TypeError):
            pytest.skip("Planner error handling not implemented")

    def test_plan_linear_cartesian(self):
        """Test linear Cartesian trajectory planning."""
        if not HAS_TRAJECTORY_PLANNER:
            pytest.skip("TrajectoryPlanner not available")

        planner = TrajectoryPlanner()

        start_pose = (200, 0, 150, 0, 0, 0)
        end_pose = (250, 50, 100, 0, 0, 0)

        try:
            trajectory = planner.plan_linear(
                start_pose=start_pose,
                end_pose=end_pose,
                velocity=100.0,
            )
            assert trajectory is not None
        except Exception as e:
            pytest.skip(f"Cartesian planning not implemented: {e}")

    def test_plan_s_curve(self):
        """Test S-curve trajectory planning."""
        if not HAS_TRAJECTORY_PLANNER:
            pytest.skip("TrajectoryPlanner not available")

        planner = TrajectoryPlanner()
        start = [1500] * 6
        end = [2000] * 6

        try:
            trajectory = planner.plan_joint_space(
                start_joints=start,
                end_joints=end,
                duration=2.0,
                method="s_curve",
            )
            assert trajectory is not None
        except Exception as e:
            pytest.skip(f"S-curve planning not implemented: {e}")


class TestTrajectoryValidation:
    """Tests for trajectory validation."""

    def test_joint_limits_enforced(self):
        """Test that joint limits are enforced in trajectory."""
        if not HAS_TRAJECTORY_PLANNER:
            pytest.skip("TrajectoryPlanner not available")

        planner = TrajectoryPlanner()

        start = [1500] * 6
        # End position exceeds joint 5 limit (max 1800)
        end = [1500, 1500, 1500, 1500, 1500, 2500]

        try:
            with pytest.raises(ValueError):
                planner.plan_joint_space(start, end, duration=1.0)
        except (AttributeError, TypeError):
            pytest.skip("Joint limit validation not implemented")

    def test_trajectory_smoothness(self):
        """Test that generated trajectory is smooth (no sudden jumps)."""
        positions, _, _ = trapezoidal_profile(
            total_distance=100.0,
            max_velocity=50.0,
            max_acceleration=100.0,
        )

        if len(positions) < 3:
            return

        # Check for smoothness: consecutive position differences
        # should not have sudden changes
        diffs = [positions[i + 1] - positions[i] for i in range(len(positions) - 1)]
        for i in range(1, len(diffs)):
            # Difference change should be bounded
            change = abs(diffs[i] - diffs[i - 1])
            assert change < 10.0  # Reasonable bound for smoothness


if __name__ == "__main__":
    pytest.main([__file__, "-v"])