"""Mathematical utility functions for motion planning and kinematics.

Provides matrix operations, vector math, quaternion conversions, and
interpolation utilities used throughout the motion planning pipeline.
"""

import math
from typing import List, Tuple, Union

import numpy as np


# ---------------------------------------------------------------------------
# Vector Operations
# ---------------------------------------------------------------------------


def normalize(v: Union[List[float], np.ndarray]) -> np.ndarray:
    """Normalize a vector to unit length.

    Args:
        v: Input vector (list or numpy array).

    Returns:
        Normalized vector as numpy array.
    """
    v = np.asarray(v, dtype=np.float64)
    norm = np.linalg.norm(v)
    if norm < 1e-10:
        return v
    return v / norm


def cross_product(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Compute cross product of two 3D vectors.

    Args:
        a: First vector (3,).
        b: Second vector (3,).

    Returns:
        Cross product vector (3,).
    """
    return np.cross(a, b)


def dot_product(a: np.ndarray, b: np.ndarray) -> float:
    """Compute dot product of two vectors.

    Args:
        a: First vector.
        b: Second vector.

    Returns:
        Dot product scalar.
    """
    return float(np.dot(a, b))


def angle_between(v1: np.ndarray, v2: np.ndarray) -> float:
    """Compute angle between two vectors in radians.

    Args:
        v1: First vector.
        v2: Second vector.

    Returns:
        Angle in radians [0, π].
    """
    v1_n = normalize(v1)
    v2_n = normalize(v2)
    cos_theta = np.clip(dot_product(v1_n, v2_n), -1.0, 1.0)
    return math.acos(cos_theta)


def distance(p1: np.ndarray, p2: np.ndarray) -> float:
    """Compute Euclidean distance between two points.

    Args:
        p1: First point.
        p2: Second point.

    Returns:
        Euclidean distance.
    """
    return float(np.linalg.norm(np.asarray(p1) - np.asarray(p2)))


# ---------------------------------------------------------------------------
# Matrix Operations
# ---------------------------------------------------------------------------


def rotation_matrix_x(angle: float) -> np.ndarray:
    """Create a rotation matrix around the X axis.

    Args:
        angle: Rotation angle in radians.

    Returns:
        3x3 rotation matrix.
    """
    c = math.cos(angle)
    s = math.sin(angle)
    return np.array([
        [1, 0, 0],
        [0, c, -s],
        [0, s, c],
    ], dtype=np.float64)


def rotation_matrix_y(angle: float) -> np.ndarray:
    """Create a rotation matrix around the Y axis.

    Args:
        angle: Rotation angle in radians.

    Returns:
        3x3 rotation matrix.
    """
    c = math.cos(angle)
    s = math.sin(angle)
    return np.array([
        [c, 0, s],
        [0, 1, 0],
        [-s, 0, c],
    ], dtype=np.float64)


def rotation_matrix_z(angle: float) -> np.ndarray:
    """Create a rotation matrix around the Z axis.

    Args:
        angle: Rotation angle in radians.

    Returns:
        3x3 rotation matrix.
    """
    c = math.cos(angle)
    s = math.sin(angle)
    return np.array([
        [c, -s, 0],
        [s, c, 0],
        [0, 0, 1],
    ], dtype=np.float64)


def rotation_matrix_from_euler(
    roll: float, pitch: float, yaw: float, order: str = "zyx"
) -> np.ndarray:
    """Create a rotation matrix from Euler angles.

    Args:
        roll: Roll angle in radians.
        pitch: Pitch angle in radians.
        yaw: Yaw angle in radians.
        order: Rotation order ('zyx', 'xyz', etc.).

    Returns:
        3x3 rotation matrix.
    """
    Rx = rotation_matrix_x(roll)
    Ry = rotation_matrix_y(pitch)
    Rz = rotation_matrix_z(yaw)

    if order == "zyx":
        return Rz @ Ry @ Rx
    elif order == "xyz":
        return Rx @ Ry @ Rz
    elif order == "zyz":
        return Rz @ Ry @ Rz
    else:
        raise ValueError(f"Unsupported rotation order: {order}")


def euler_from_rotation_matrix(R: np.ndarray, order: str = "zyx") -> Tuple[float, float, float]:
    """Extract Euler angles from a rotation matrix.

    Args:
        R: 3x3 rotation matrix.
        order: Rotation order ('zyx' or 'xyz').

    Returns:
        (roll, pitch, yaw) tuple in radians.
    """
    if order == "zyx":
        sy = math.sqrt(R[0, 0] ** 2 + R[1, 0] ** 2)
        singular = sy < 1e-6
        if not singular:
            roll = math.atan2(R[2, 1], R[2, 2])
            pitch = math.atan2(-R[2, 0], sy)
            yaw = math.atan2(R[1, 0], R[0, 0])
        else:
            roll = math.atan2(-R[1, 2], R[1, 1])
            pitch = math.atan2(-R[2, 0], sy)
            yaw = 0.0
        return roll, pitch, yaw
    else:
        raise ValueError(f"Unsupported rotation order: {order}")


def homogeneous_transform(R: np.ndarray, t: np.ndarray) -> np.ndarray:
    """Create a 4x4 homogeneous transformation matrix.

    Args:
        R: 3x3 rotation matrix.
        t: 3x1 translation vector.

    Returns:
        4x4 homogeneous transformation matrix.
    """
    T = np.eye(4, dtype=np.float64)
    T[:3, :3] = R
    T[:3, 3] = t
    return T


# ---------------------------------------------------------------------------
# Quaternion Operations
# ---------------------------------------------------------------------------


def quaternion_to_rotation_matrix(q: List[float]) -> np.ndarray:
    """Convert a quaternion to a rotation matrix.

    Args:
        q: Quaternion [w, x, y, z].

    Returns:
        3x3 rotation matrix.
    """
    w, x, y, z = q
    return np.array([
        [1 - 2*y*y - 2*z*z, 2*x*y - 2*w*z,     2*x*z + 2*w*y],
        [2*x*y + 2*w*z,     1 - 2*x*x - 2*z*z, 2*y*z - 2*w*x],
        [2*x*z - 2*w*y,     2*y*z + 2*w*x,     1 - 2*x*x - 2*y*y],
    ], dtype=np.float64)


def rotation_matrix_to_quaternion(R: np.ndarray) -> List[float]:
    """Convert a rotation matrix to a quaternion.

    Args:
        R: 3x3 rotation matrix.

    Returns:
        Quaternion [w, x, y, z].
    """
    trace = np.trace(R)
    if trace > 0:
        s = 0.5 / math.sqrt(trace + 1.0)
        w = 0.25 / s
        x = (R[2, 1] - R[1, 2]) * s
        y = (R[0, 2] - R[2, 0]) * s
        z = (R[1, 0] - R[0, 1]) * s
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = 2.0 * math.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2])
        w = (R[2, 1] - R[1, 2]) / s
        x = 0.25 * s
        y = (R[0, 1] + R[1, 0]) / s
        z = (R[0, 2] + R[2, 0]) / s
    elif R[1, 1] > R[2, 2]:
        s = 2.0 * math.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2])
        w = (R[0, 2] - R[2, 0]) / s
        x = (R[0, 1] + R[1, 0]) / s
        y = 0.25 * s
        z = (R[1, 2] + R[2, 1]) / s
    else:
        s = 2.0 * math.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1])
        w = (R[1, 0] - R[0, 1]) / s
        x = (R[0, 2] + R[2, 0]) / s
        y = (R[1, 2] + R[2, 1]) / s
        z = 0.25 * s
    return [w, x, y, z]


def slerp(q1: List[float], q2: List[float], t: float) -> List[float]:
    """Spherical linear interpolation between two quaternions.

    Args:
        q1: Start quaternion [w, x, y, z].
        q2: End quaternion [w, x, y, z].
        t: Interpolation parameter [0, 1].

    Returns:
        Interpolated quaternion [w, x, y, z].
    """
    q1 = np.asarray(q1, dtype=np.float64)
    q2 = np.asarray(q2, dtype=np.float64)

    cos_theta = np.dot(q1, q2)
    if cos_theta < 0:
        q2 = -q2
        cos_theta = -cos_theta

    if cos_theta > 0.9995:
        # Linear interpolation for small angles
        result = q1 + t * (q2 - q1)
        return list(result / np.linalg.norm(result))

    theta = math.acos(cos_theta)
    sin_theta = math.sin(theta)

    w1 = math.sin((1 - t) * theta) / sin_theta
    w2 = math.sin(t * theta) / sin_theta

    return list(w1 * q1 + w2 * q2)


# ---------------------------------------------------------------------------
# Interpolation Functions
# ---------------------------------------------------------------------------


def linear_interpolate(
    start: Union[float, List[float]],
    end: Union[float, List[float]],
    t: float,
) -> Union[float, List[float]]:
    """Linear interpolation between two values.

    Args:
        start: Start value.
        end: End value.
        t: Interpolation parameter [0, 1].

    Returns:
        Interpolated value.
    """
    if isinstance(start, (int, float)):
        return start + (end - start) * t
    return [s + (e - s) * t for s, e in zip(start, end)]


def s_curve_profile(
    total_distance: float,
    max_velocity: float,
    max_acceleration: float,
    max_jerk: float,
    sample_time: float = 0.01,
) -> Tuple[List[float], List[float], List[float]]:
    """Generate a symmetric S-curve motion profile (7-phase).

    Phases: T1(jerk+) → T2(const accel) → T3(jerk-) → T4(const vel)
            → T5(jerk-) → T6(const decel) → T7(jerk+)

    Args:
        total_distance: Total distance to travel.
        max_velocity: Maximum velocity.
        max_acceleration: Maximum acceleration.
        max_jerk: Maximum jerk.
        sample_time: Time step for sampling.

    Returns:
        (positions, velocities, accelerations) lists.
    """
    positions: List[float] = []
    velocities: List[float] = []
    accelerations: List[float] = []

    if total_distance <= 0:
        positions.append(0.0)
        velocities.append(0.0)
        accelerations.append(0.0)
        return positions, velocities, accelerations

    # Time to reach max acceleration at max jerk
    Tj = max_acceleration / max_jerk if max_jerk > 0 else 0.0
    # Time to reach max velocity
    Ta = max_velocity / max_acceleration if max_acceleration > 0 else 0.0

    # Check if we can reach max acceleration
    if Ta < Tj:
        # Max velocity is too low → triangular acceleration profile
        Tj = math.sqrt(max_velocity / max_jerk) if max_jerk > 0 else 0.0
        Ta = 2 * Tj

    # Distance covered during acceleration phase
    d_accel = max_velocity * (Ta + Tj) if (Ta + Tj) > 0 else 0.0

    if total_distance < 2 * d_accel:
        # Too short for max velocity → reduce velocity
        # Use simplified triangular S-curve
        max_velocity = math.sqrt(total_distance * max_jerk) if max_jerk > 0 else total_distance
        Tj = math.sqrt(max_velocity / max_jerk) if max_jerk > 0 else math.sqrt(total_distance / max_acceleration)
        Ta = 2 * Tj

    # Phase times
    T1 = Tj           # Jerk up
    T2 = Ta - Tj       # Constant accel
    T3 = Tj           # Jerk down
    T4 = max(0.0, (total_distance - 2 * max_velocity * (Ta + Tj)) / max_velocity) if max_velocity > 0 else 0.0
    T5 = Tj           # Jerk down (decel)
    T6 = T2           # Constant decel
    T7 = Tj           # Jerk up (to zero)

    t_points = [T1, T1 + T2, T1 + T2 + T3, T1 + T2 + T3 + T4,
                T1 + T2 + T3 + T4 + T5, T1 + T2 + T3 + T4 + T5 + T6,
                T1 + T2 + T3 + T4 + T5 + T6 + T7]

    t = 0.0
    t_total = t_points[-1] if t_points[-1] > 0 else 1.0

    while t <= t_total + sample_time * 0.5:
        if t <= t_points[0]:
            # Phase 1: Jerk up (increasing acceleration to +Amax)
            a = max_jerk * t
            v = 0.5 * max_jerk * t * t
            p = (1.0 / 6.0) * max_jerk * t * t * t
        elif t <= t_points[1]:
            # Phase 2: Constant +Amax
            dt = t - t_points[0]
            a = max_acceleration
            v = 0.5 * max_jerk * Tj * Tj + max_acceleration * dt
            p = (1.0 / 6.0) * max_jerk * Tj * Tj * Tj + v * dt - 0.5 * max_acceleration * dt * dt
            # Fix: use proper kinematics
            v0_T1 = 0.5 * max_jerk * Tj * Tj
            p0_T1 = (1.0 / 6.0) * max_jerk * Tj * Tj * Tj
            v = v0_T1 + max_acceleration * dt
            p = p0_T1 + v0_T1 * dt + 0.5 * max_acceleration * dt * dt
        elif t <= t_points[2]:
            # Phase 3: Jerk down (decreasing acceleration to 0)
            dt = t - t_points[1]
            a = max_acceleration - max_jerk * dt
            v0_T2 = 0.5 * max_jerk * Tj * Tj + max_acceleration * T2
            p0_T2 = (1.0 / 6.0) * max_jerk * Tj * Tj * Tj + \
                    (0.5 * max_jerk * Tj * Tj) * T2 + 0.5 * max_acceleration * T2 * T2
            v = v0_T2 + max_acceleration * dt - 0.5 * max_jerk * dt * dt
            p = p0_T2 + v0_T2 * dt + 0.5 * max_acceleration * dt * dt - (1.0 / 6.0) * max_jerk * dt * dt * dt
        elif t <= t_points[3]:
            # Phase 4: Constant velocity
            dt = t - t_points[2]
            a = 0.0
            v = max_velocity
            p0_T3 = (1.0 / 6.0) * max_jerk * Tj * Tj * Tj + \
                    (0.5 * max_jerk * Tj * Tj) * T2 + 0.5 * max_acceleration * T2 * T2 + \
                    (max_velocity - 0.5 * max_jerk * Tj * Tj) * Tj + \
                    0.5 * max_acceleration * Tj * Tj - (1.0 / 6.0) * max_jerk * Tj * Tj * Tj
            p = p0_T3 + max_velocity * dt
        elif t <= t_points[4]:
            # Phase 5: Jerk down (deceleration)
            dt = t - t_points[3]
            a = -max_jerk * dt
            p0_T4 = total_distance / 2.0  # Approximate midpoint
            p = p0_T4 + max_velocity * dt - (1.0 / 6.0) * max_jerk * dt * dt * dt
            v = max_velocity - 0.5 * max_jerk * dt * dt
        elif t <= t_points[5]:
            # Phase 6: Constant -Amax
            dt = t - t_points[4]
            a = -max_acceleration
            v0_T5 = max_velocity - 0.5 * max_jerk * Tj * Tj
            p0_T5 = total_distance - max_velocity * (T5 + T6 + T7) * 0.5
            v = v0_T5 - max_acceleration * dt
            p = p0_T5 + v0_T5 * dt - 0.5 * max_acceleration * dt * dt
        else:
            # Phase 7: Jerk up to zero
            dt = t - t_points[5]
            a = -max_acceleration + max_jerk * dt
            v0_T6 = max_velocity - 0.5 * max_jerk * Tj * Tj - max_acceleration * T6
            p0_T6 = total_distance - max_velocity * T7 * 0.3
            v = v0_T6 - max_acceleration * dt + 0.5 * max_jerk * dt * dt
            p = p0_T6 + v0_T6 * dt - 0.5 * max_acceleration * dt * dt + (1.0 / 6.0) * max_jerk * dt * dt * dt

        # Clamp and finalize
        p = max(0.0, min(total_distance, p))
        v = max(0.0, v)

        positions.append(p)
        velocities.append(v)
        accelerations.append(a)

        t += sample_time

    # Ensure final position is exactly total_distance
    if positions and abs(positions[-1] - total_distance) > 0.5:
        positions[-1] = total_distance
        if velocities:
            velocities[-1] = 0.0
        if accelerations:
            accelerations[-1] = 0.0

    return positions, velocities, accelerations


def trapezoidal_profile(
    total_distance: float,
    max_velocity: float,
    max_acceleration: float,
    sample_time: float = 0.01,
) -> Tuple[List[float], List[float], List[float]]:
    """Generate a trapezoidal velocity profile.

    Args:
        total_distance: Total distance to travel.
        max_velocity: Maximum velocity.
        max_acceleration: Maximum acceleration.
        sample_time: Time step for sampling.

    Returns:
        (positions, velocities, accelerations) lists.
    """
    # Acceleration phase time
    t_accel = max_velocity / max_acceleration
    # Distance covered during acceleration
    d_accel = 0.5 * max_acceleration * t_accel * t_accel

    if 2 * d_accel > total_distance:
        # Triangular profile (no constant velocity phase)
        t_accel = math.sqrt(total_distance / max_acceleration)
        max_velocity = max_acceleration * t_accel
        t_const = 0.0
    else:
        t_const = (total_distance - 2 * d_accel) / max_velocity

    positions = []
    velocities = []
    accelerations = []

    t = 0.0
    while t < 2 * t_accel + t_const:
        if t < t_accel:
            # Acceleration phase
            a = max_acceleration
            v = max_acceleration * t
            p = 0.5 * max_acceleration * t * t
        elif t < t_accel + t_const:
            # Constant velocity phase
            a = 0.0
            v = max_velocity
            p = d_accel + max_velocity * (t - t_accel)
        else:
            # Deceleration phase
            dt = t - t_accel - t_const
            a = -max_acceleration
            v = max_velocity - max_acceleration * dt
            p = d_accel + max_velocity * t_const + max_velocity * dt - 0.5 * max_acceleration * dt * dt

        if p > total_distance:
            p = total_distance

        positions.append(p)
        velocities.append(max(0, v))
        accelerations.append(a)

        t += sample_time

    return positions, velocities, accelerations


# ---------------------------------------------------------------------------
# PWM Conversion
# ---------------------------------------------------------------------------


def pwm_to_angle(pwm: float, center: float = 1500.0, gain: float = 11.11) -> float:
    """Convert PWM value to joint angle in degrees.

    Args:
        pwm: PWM value (500-2500).
        center: Center PWM value.
        gain: PWM-to-angle gain (大约 11.11 PWM/度).

    Returns:
        Joint angle in degrees.
    """
    return (pwm - center) / gain


def angle_to_pwm(angle: float, center: float = 1500.0, gain: float = 11.11) -> float:
    """Convert joint angle to PWM value.

    Args:
        angle: Joint angle in degrees.
        center: Center PWM value.
        gain: PWM-to-angle gain.

    Returns:
        PWM value.
    """
    pwm = center + angle * gain
    return max(500.0, min(2500.0, pwm))


def pwm_to_radian(pwm: float, center: float = 1500.0, gain: float = 11.11) -> float:
    """Convert PWM value to joint angle in radians.

    Args:
        pwm: PWM value.
        center: Center PWM value.
        gain: PWM-to-angle gain.

    Returns:
        Joint angle in radians.
    """
    return math.radians(pwm_to_angle(pwm, center, gain))


def radian_to_pwm(rad: float, center: float = 1500.0, gain: float = 11.11) -> float:
    """Convert joint angle in radians to PWM value.

    Args:
        rad: Joint angle in radians.
        center: Center PWM value.
        gain: PWM-to-angle gain.

    Returns:
        PWM value.
    """
    return angle_to_pwm(math.degrees(rad), center, gain)


# ---------------------------------------------------------------------------
# Clamping Utilities
# ---------------------------------------------------------------------------


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value between min and max.

    Args:
        value: Input value.
        min_val: Minimum allowed value.
        max_val: Maximum allowed value.

    Returns:
        Clamped value.
    """
    return max(min_val, min(max_val, value))


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation (lerp).

    Args:
        a: Start value.
        b: End value.
        t: Interpolation parameter [0, 1].

    Returns:
        Interpolated value.
    """
    return a + (b - a) * clamp(t, 0.0, 1.0)