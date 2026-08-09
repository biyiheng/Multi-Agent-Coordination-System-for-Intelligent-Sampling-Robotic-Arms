"""Tests for robot arm kinematics."""

import math
import unittest


class KinematicsSimulator:
    """Simple kinematic simulator for 6-DOF robotic arm."""

    LINK_LENGTHS = [0, 50, 100, 80, 0, 0]  # mm

    @staticmethod
    def forward_kinematics(joints):
        """Compute end-effector pose from joint angles (simplified DH model)."""
        if len(joints) != 6:
            raise ValueError("Expected 6 joint angles")

        j1, j2, j3, j4, j5, j6 = [math.radians(j) for j in joints]

        # Simplified kinematics for a 6-DOF arm
        l1 = KinematicsSimulator.LINK_LENGTHS[1]
        l2 = KinematicsSimulator.LINK_LENGTHS[2]
        l3 = KinematicsSimulator.LINK_LENGTHS[3]

        x = math.cos(j1) * (l2 * math.cos(j2) + l3 * math.cos(j2 + j3))
        y = math.sin(j1) * (l2 * math.cos(j2) + l3 * math.cos(j2 + j3))
        z = l1 + l2 * math.sin(j2) + l3 * math.sin(j2 + j3)

        roll = j4
        pitch = j5
        yaw = j1 + j6

        return (x, y, z, roll, pitch, yaw)

    @staticmethod
    def inverse_kinematics(pose):
        """Compute joint angles from end-effector pose (simplified)."""
        x, y, z, roll, pitch, yaw = pose

        l1 = KinematicsSimulator.LINK_LENGTHS[1]
        l2 = KinematicsSimulator.LINK_LENGTHS[2]
        l3 = KinematicsSimulator.LINK_LENGTHS[3]

        j1 = math.atan2(y, x)

        r = math.sqrt(x**2 + y**2)
        d = math.sqrt(r**2 + (z - l1)**2)

        if d > (l2 + l3) or d < abs(l2 - l3):
            raise ValueError("Position out of reachable workspace")

        cos_j3 = (d**2 - l2**2 - l3**2) / (2 * l2 * l3)
        cos_j3 = max(-1.0, min(1.0, cos_j3))
        j3 = math.acos(cos_j3)

        alpha = math.atan2(z - l1, r)
        beta = math.atan2(l3 * math.sin(j3), l2 + l3 * math.cos(j3))
        j2 = alpha - beta

        j4 = roll
        j5 = pitch
        j6 = yaw - j1

        return tuple(math.degrees(a) for a in (j1, j2, j3, j4, j5, j6))

    @staticmethod
    def check_joint_limits(joints):
        """Check if joints are within limits."""
        limits = [
            (-180, 180),   # joint 1: base rotation
            (-90, 90),     # joint 2: shoulder
            (-135, 135),   # joint 3: elbow
            (-180, 180),   # joint 4: wrist rotation
            (-90, 90),     # joint 5: wrist pitch
            (-180, 180),   # joint 6: wrist roll
        ]

        for i, (joint, (lo, hi)) in enumerate(zip(joints, limits)):
            if joint < lo or joint > hi:
                return False, f"Joint {i+1} out of limits: {joint} not in [{lo}, {hi}]"
        return True, "All joints within limits"

    @staticmethod
    def is_singular(joints, threshold=5.0):
        """Check if the arm is near a singular configuration."""
        _, j2, j3, _, j5, _ = joints
        # Singularity when wrist pitch is near 0 (wrist alignment)
        if abs(j5) < threshold:
            return True, "Wrist singularity: j5 near 0"
        # Singularity when elbow is near 0 or 180
        if abs(j3) < threshold:
            return True, "Elbow singularity: j3 near 0"
        if abs(abs(j3) - 180) < threshold:
            return True, "Elbow singularity: j3 near 180"
        return False, "No singularity"


class TestKinematics(unittest.TestCase):
    """Test kinematics calculations."""

    def setUp(self):
        self.kin = KinematicsSimulator()

    def test_forward_kinematics_home(self):
        """Test forward kinematics at home position (all zeros)."""
        joints = [0, 0, 0, 0, 0, 0]
        x, y, z, roll, pitch, yaw = self.kin.forward_kinematics(joints)

        # Link lengths: [0, 50, 100, 80, 0, 0]
        # At all zeros: z = l1 + l2*sin(0) + l3*sin(0+0) = 50 + 0 + 0 = 50
        self.assertAlmostEqual(z, 50, delta=1.0, msg="Z should be l1 = 50mm at home")
        self.assertAlmostEqual(y, 0, delta=0.01)

    def test_forward_kinematics_base_rotation(self):
        """Test forward kinematics with base rotation only."""
        joints = [90, 0, 0, 0, 0, 0]
        x, y, z, _, _, _ = self.kin.forward_kinematics(joints)

        self.assertAlmostEqual(x, 0, delta=1.0)
        self.assertGreater(y, 0)

    def test_forward_kinematics_shoulder_up(self):
        """Test forward kinematics with shoulder moved up."""
        joints = [0, 45, 0, 0, 0, 0]
        x, y, z, _, _, _ = self.kin.forward_kinematics(joints)

        self.assertGreater(z, 100)

    def test_inverse_roundtrip(self):
        """Test inverse kinematics roundtrip: forward -> inverse -> forward."""
        test_joints = [(0, 0, 0, 0, 0, 0), (30, 15, 45, 0, 0, 0), (0, 45, -30, 10, 0, 0)]

        for original in test_joints:
            pose = self.kin.forward_kinematics(original)
            computed = self.kin.inverse_kinematics(pose)
            pose_computed = self.kin.forward_kinematics(computed)

            for i, (p_orig, p_comp) in enumerate(zip(pose, pose_computed)):
                self.assertAlmostEqual(
                    p_orig, p_comp, delta=1.0,
                    msg=f"Roundtrip failed for {original} at position {i}"
                )

    def test_joint_limits_valid(self):
        """Test joint limit checking with valid positions."""
        joints = [0, 0, 0, 0, 0, 0]
        valid, msg = self.kin.check_joint_limits(joints)
        self.assertTrue(valid, msg)

    def test_joint_limits_exceeded(self):
        """Test joint limit checking with exceeded limits."""
        joints = [200, 0, 0, 0, 0, 0]  # joint 1 exceeds 180
        valid, msg = self.kin.check_joint_limits(joints)
        self.assertFalse(valid)

    def test_joint_limits_negative(self):
        """Test joint limit checking with negative exceeded limits."""
        joints = [0, -100, 0, 0, 0, 0]  # joint 2 below -90
        valid, msg = self.kin.check_joint_limits(joints)
        self.assertFalse(valid)

    def test_singular_configuration(self):
        """Test singularity detection at known singular pose."""
        # Wrist pitch at 0 is singular
        joints = [0, 30, 45, 0, 0, 0]
        singular, msg = self.kin.is_singular(joints)
        self.assertTrue(singular, msg)

    def test_nonsingular_configuration(self):
        """Test that normal pose is not singular."""
        joints = [0, 30, 45, 0, 30, 0]
        singular, msg = self.kin.is_singular(joints)
        self.assertFalse(singular, msg)

    def test_out_of_workspace(self):
        """Test inverse kinematics with unreachable position."""
        # Very far position
        pose = (1000, 0, 0, 0, 0, 0)
        with self.assertRaises(ValueError):
            self.kin.inverse_kinematics(pose)


if __name__ == "__main__":
    unittest.main()