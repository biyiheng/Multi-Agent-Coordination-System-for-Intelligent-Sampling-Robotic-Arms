"""
Force/Impedance Control & Compliant Grasping Module.

实现力位混合控制与柔顺抓取，保障精密零件无损伤操作:
- 导纳控制 (Admittance Control): 力→位置修正
- 阻抗控制 (Impedance Control): 位置→力响应
- 力位混合控制 (Hybrid Force/Position Control)
- 柔顺抓取策略 (Compliant Grasping)
- 末端执行器管理 (快换+自动标定)
- 真空吸盘/夹爪力控

参考:
- Hogan 1985, "Impedance Control: An Approach to Manipulation"
- Siciliano & Villani 1999, "Robot Force Control"
- 工业机器人力控最佳实践
"""

import math
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# 枚举与数据模型
# =============================================================================


class EndEffectorType(Enum):
    """末端执行器类型."""
    PARALLEL_GRIPPER = "parallel_gripper"   # 平行夹爪
    SUCTION_CUP = "suction_cup"             # 真空吸盘
    MAGNETIC = "magnetic"                   # 电磁吸盘
    SOFT_GRIPPER = "soft_gripper"           # 软体夹爪
    CUSTOM = "custom"                       # 自定义


class ControlMode(Enum):
    """控制模式."""
    POSITION = "position"           # 纯位置控制
    VELOCITY = "velocity"           # 速度控制
    TORQUE = "torque"              # 力矩控制
    IMPEDANCE = "impedance"        # 阻抗控制
    ADMITTANCE = "admittance"      # 导纳控制
    HYBRID = "hybrid"              # 力位混合控制


class GraspState(Enum):
    """抓取状态."""
    APPROACH = "approach"          # 接近
    CONTACT = "contact"            # 接触
    GRASPING = "grasping"          # 抓取中
    GRASPED = "grasped"            # 已抓取
    RELEASING = "releasing"        # 释放中
    RELEASED = "released"          # 已释放
    FAILED = "failed"              # 失败


@dataclass
class EndEffectorSpec:
    """末端执行器规格."""
    name: str
    ee_type: EndEffectorType
    max_grip_force_n: float = 50.0
    min_grip_force_n: float = 1.0
    max_opening_mm: float = 100.0
    min_opening_mm: float = 0.0
    closing_speed_mm_s: float = 50.0
    mass_kg: float = 0.5
    center_of_mass: np.ndarray = field(default_factory=lambda: np.zeros(3))
    tool_center_point: np.ndarray = field(default_factory=lambda: np.zeros(3))
    vacuum_pressure_kpa: float = -60.0  # 仅吸盘
    suction_cup_diameter_mm: float = 20.0  # 仅吸盘
    quick_change_compatible: bool = True
    calibration_id: str = ""


@dataclass
class ImpedanceParams:
    """阻抗控制参数."""
    stiffness: np.ndarray = field(default_factory=lambda: np.array([500, 500, 500, 50, 50, 50]))
    damping: np.ndarray = field(default_factory=lambda: np.array([50, 50, 50, 10, 10, 10]))
    inertia: np.ndarray = field(default_factory=lambda: np.array([1, 1, 1, 0.1, 0.1, 0.1]))


@dataclass
class ForceTorque:
    """六维力/力矩传感器读数."""
    fx: float = 0.0; fy: float = 0.0; fz: float = 0.0
    tx: float = 0.0; ty: float = 0.0; tz: float = 0.0
    timestamp: float = field(default_factory=time.time)

    @property
    def force_vector(self) -> np.ndarray:
        return np.array([self.fx, self.fy, self.fz])

    @property
    def torque_vector(self) -> np.ndarray:
        return np.array([self.tx, self.ty, self.tz])

    @property
    def force_magnitude(self) -> float:
        return float(np.linalg.norm(self.force_vector))


# =============================================================================
# 末端执行器管理
# =============================================================================


class EndEffectorManager:
    """末端执行器管理器 - 快换与自动标定."""

    def __init__(self):
        self._effectors: Dict[str, EndEffectorSpec] = {}
        self._active: Optional[EndEffectorSpec] = None
        self._calibration_matrix: Dict[str, np.ndarray] = {}  # 标定变换矩阵

    def register_effector(self, spec: EndEffectorSpec) -> None:
        """注册末端执行器."""
        self._effectors[spec.name] = spec

    def switch_effector(self, name: str) -> bool:
        """切换末端执行器 (快换).

        Args:
            name: 执行器名称

        Returns:
            是否切换成功
        """
        if name not in self._effectors:
            return False

        self._active = self._effectors[name]
        return True

    def calibrate(self, effector_name: str,
                  measured_points: np.ndarray,
                  nominal_points: np.ndarray) -> Optional[np.ndarray]:
        """自动标定末端执行器 TCP.

        Args:
            effector_name: 执行器名称
            measured_points: Nx3 实测点
            nominal_points: Nx3 名义点

        Returns:
            4x4 标定变换矩阵
        """
        if len(measured_points) < 3:
            return None

        # 使用 SVD 求解刚性变换
        centroid_m = np.mean(measured_points, axis=0)
        centroid_n = np.mean(nominal_points, axis=0)

        H = (measured_points - centroid_m).T @ (nominal_points - centroid_n)
        U, _, Vt = np.linalg.svd(H)
        R = Vt.T @ U.T

        if np.linalg.det(R) < 0:
            Vt[-1, :] *= -1
            R = Vt.T @ U.T

        t = centroid_n - R @ centroid_m

        T = np.eye(4)
        T[:3, :3] = R
        T[:3, 3] = t

        self._calibration_matrix[effector_name] = T
        return T

    def get_active_tcp(self) -> np.ndarray:
        """获取当前 TCP 位姿 (在世界坐标系中)."""
        if self._active is None:
            return np.eye(4)

        T = np.eye(4)
        T[:3, 3] = self._active.tool_center_point

        # 应用标定修正
        if self._active.name in self._calibration_matrix:
            T = T @ self._calibration_matrix[self._active.name]

        return T

    def get_grip_force_limits(self) -> Tuple[float, float]:
        """获取当前夹爪力限值."""
        if self._active is None:
            return (1.0, 50.0)
        return (self._active.min_grip_force_n, self._active.max_grip_force_n)

    def compute_suction_force(self, safety_factor: float = 0.5) -> float:
        """计算吸盘理论吸附力.

        F = ΔP × A × safety_factor
        ΔP = 大气压 - 真空度
        A = π × (d/2)²

        Args:
            safety_factor: 安全系数

        Returns:
            吸附力 (N)
        """
        if self._active is None or self._active.ee_type != EndEffectorType.SUCTION_CUP:
            return 0.0

        atm_pressure = 101.325  # kPa
        delta_p = atm_pressure - abs(self._active.vacuum_pressure_kpa)
        radius_m = self._active.suction_cup_diameter_mm / 2000.0  # mm → m
        area = math.pi * radius_m ** 2

        return delta_p * 1000 * area * safety_factor  # kPa → Pa, N


# =============================================================================
# 阻抗控制
# =============================================================================


class ImpedanceController:
    """阻抗控制器 - 实现柔顺交互.

    质量-弹簧-阻尼模型:
    M·ẍ + D·ẋ + K·(x - x_d) = F_ext

    其中:
    M: 惯性矩阵
    D: 阻尼矩阵
    K: 刚度矩阵
    x_d: 期望位置
    F_ext: 外部力/力矩
    """

    def __init__(self, params: Optional[ImpedanceParams] = None):
        self.params = params or ImpedanceParams()
        self._x_d = np.zeros(6)  # 期望位姿
        self._x = np.zeros(6)    # 当前位姿
        self._dx = np.zeros(6)   # 当前速度
        self._ddx = np.zeros(6)  # 当前加速度
        self._dt = 0.001         # 控制周期 (1ms)

    def set_desired_pose(self, pose: np.ndarray) -> None:
        """设置期望位姿 [x, y, z, roll, pitch, yaw]."""
        self._x_d = pose.copy()

    def update(self, current_pose: np.ndarray,
               current_velocity: np.ndarray,
               external_force: np.ndarray) -> np.ndarray:
        """计算阻抗控制修正量.

        Args:
            current_pose: 当前位姿 [x, y, z, roll, pitch, yaw]
            current_velocity: 当前速度
            external_force: 外部力/力矩 [Fx, Fy, Fz, Tx, Ty, Tz]

        Returns:
            位姿修正量 [Δx, Δy, Δz, Δroll, Δpitch, Δyaw]
        """
        self._x = current_pose.copy()
        self._dx = current_velocity.copy()

        # 阻抗控制律：M·ẍ + D·ẋ + K·(x - x_d) = F_ext
        # 重排为：ẍ = M⁻¹ · (F_ext - D·ẋ - K·(x - x_d))
        pos_error = self._x - self._x_d                              # 位置误差
        accel = (external_force - self.params.damping * self._dx -   # 力 - 阻尼力
                 self.params.stiffness * pos_error) / (self.params.inertia + 1e-10)  # 除以惯性（+1e-10 防止除零）

        self._ddx = accel

        # 位置修正（二阶积分）：Δx = v·dt + 1/2·a·dt²
        dx = self._dx * self._dt + 0.5 * accel * self._dt ** 2
        return dx

    def compute_stiffness(self, direction: np.ndarray,
                          base_stiffness: float = 500.0) -> np.ndarray:
        """计算方向性刚度矩阵.

        Args:
            direction: 方向向量 (6维)
            base_stiffness: 基础刚度

        Returns:
            6x6 刚度矩阵
        """
        # 基础刚度矩阵（对角矩阵）
        K = np.eye(6) * base_stiffness

        # 归一化方向向量
        direction_norm = direction / (np.linalg.norm(direction) + 1e-10)

        # 在指定方向上降低刚度（提高柔顺性）
        # K_effective = K - 0.8 * base_stiffness * (d·d^T)
        # 外积 d·d^T 将刚度降低集中在指定方向
        K -= np.outer(direction_norm, direction_norm) * base_stiffness * 0.8

        return K


# =============================================================================
# 导纳控制
# =============================================================================


class AdmittanceController:
    """导纳控制器 - 力→位置修正.

    与阻抗控制互补，适用于:
    - 高刚度环境 (机械臂本身刚度高)
    - 力传感器精度高的场景
    - 装配、抛光等接触作业

    导纳模型:
    M_d·ẍ + D_d·ẋ = F_ext - F_d
    → 计算期望加速度 → 积分得到位置修正
    """

    def __init__(self,
                 mass: np.ndarray = None,
                 damping: np.ndarray = None):
        self.mass = mass if mass is not None else np.array([1, 1, 1, 0.1, 0.1, 0.1])
        self.damping = damping if damping is not None else np.array([20, 20, 20, 5, 5, 5])
        self._desired_force = np.zeros(6)
        self._dx = np.zeros(6)
        self._ddx = np.zeros(6)
        self._dt = 0.001

    def set_desired_force(self, force: np.ndarray) -> None:
        """设置期望接触力."""
        self._desired_force = force.copy()

    def update(self, measured_force: np.ndarray) -> np.ndarray:
        """计算位置修正量.

        Args:
            measured_force: 实测力/力矩

        Returns:
            位置修正量 [Δx, Δy, Δz, Δroll, Δpitch, Δyaw]
        """
        force_error = measured_force - self._desired_force

        # 导纳控制律: M_d·ẍ + D_d·ẋ = F_ext - F_d
        # → ẍ = (F_error - D_d·ẋ) / M_d
        accel = (force_error - self.damping * self._dx) / (self.mass + 1e-10)
        self._ddx = accel

        # 位置修正（二阶积分）
        dx = self._dx * self._dt + 0.5 * accel * self._dt ** 2
        self._dx = dx  # 更新速度状态
        return dx


# =============================================================================
# 力位混合控制
# =============================================================================


class HybridForcePositionController:
    """力位混合控制器.

    在约束方向上进行力控制，在自由方向上进行位置控制。

    选择矩阵 S:
    S = diag(s1, s2, ..., s6)
    si = 0: 力控制方向
    si = 1: 位置控制方向

    控制律:
    τ = S · τ_pos + (I - S) · τ_force
    """

    def __init__(self):
        self._position_controller = ImpedanceController()
        self._force_controller = AdmittanceController()
        self._selection_matrix = np.eye(6)  # 默认全位置控制
        self._control_mode = ControlMode.HYBRID

    def set_selection_matrix(self, S: np.ndarray) -> None:
        """设置力/位置选择矩阵.

        Args:
            S: 6x6 对角矩阵
               1 = 位置控制, 0 = 力控制
        """
        self._selection_matrix = S

    def set_force_control_axis(self, axes: List[int]) -> None:
        """设置力控制轴.

        Args:
            axes: 力控制的轴索引 (0=X, 1=Y, 2=Z, 3=RX, 4=RY, 5=RZ)
        """
        S = np.eye(6)
        for axis in axes:
            S[axis, axis] = 0
        self._selection_matrix = S

    def set_position_control_axis(self, axes: List[int]) -> None:
        """设置位置控制轴."""
        S = np.zeros(6)
        for axis in axes:
            S[axis] = 1
        self._selection_matrix = np.diag(S)

    def update(self,
               current_pose: np.ndarray,
               current_velocity: np.ndarray,
               desired_pose: np.ndarray,
               measured_force: np.ndarray,
               desired_force: np.ndarray) -> np.ndarray:
        """计算混合控制输出.

        Args:
            current_pose: 当前位姿
            current_velocity: 当前速度
            desired_pose: 期望位姿
            measured_force: 实测力
            desired_force: 期望力

        Returns:
            位姿修正量
        """
        # 设置期望位姿和期望力
        self._position_controller.set_desired_pose(desired_pose)
        self._force_controller.set_desired_force(desired_force)

        # 位置控制修正量（在自由方向上）
        dx_pos = self._position_controller.update(
            current_pose, current_velocity, measured_force,
        )

        # 力控制修正量（在约束方向上）
        dx_force = self._force_controller.update(measured_force)

        # 混合控制律：τ = S · τ_pos + (I - S) · τ_force
        # S: 选择矩阵，对角线元素 = 1 表示位置控制，= 0 表示力控制
        I = np.eye(6)
        dx_hybrid = self._selection_matrix @ dx_pos + (I - self._selection_matrix) @ dx_force

        return dx_hybrid


# =============================================================================
# 柔顺抓取策略
# =============================================================================


class CompliantGraspingController:
    """柔顺抓取控制器 - 实现无损伤精密抓取.

    策略:
    1. 接近阶段: 快速接近到安全距离
    2. 接触检测: 力传感器检测接触
    3. 柔顺抓取: 导纳控制跟随物体表面
    4. 力控夹持: 精确控制夹持力
    5. 提升验证: 检测滑移
    """

    # 接触检测阈值
    CONTACT_FORCE_THRESHOLD = 1.5  # N
    # 滑移检测阈值
    SLIP_FORCE_DROP = 0.3  # N
    # 最大接近速度
    MAX_APPROACH_SPEED_MM_S = 50.0
    # 柔顺接近速度
    COMPLIANT_SPEED_MM_S = 5.0

    # ---- 力控异常告警阈值 (可在 __init__ 通过 alert_config 覆盖) ----
    FORCE_SPIKE_DELTA_N = 5.0    # 相邻采样力突增阈值 (N), 疑似碰撞/冲击
    FORCE_OVERLOAD_N = 40.0      # 力超载硬阈值 (N), 疑似过夹/卡死
    ALERT_DEBOUNCE_STEPS = 3     # 连续触发确认次数, 抑制瞬时噪声误报
    ALERT_COOLDOWN_STEPS = 30    # 告警冷却步数, 防止告警风暴

    def __init__(self, alert_config: Optional[Dict[str, float]] = None):
        self._ee_manager = EndEffectorManager()
        self._admittance = AdmittanceController()
        self._state = GraspState.APPROACH
        self._grip_force = 0.0
        self._contact_force_history: List[float] = []

        # ---- 力控异常告警状态 ----
        self._last_force = 0.0
        self._anomaly_counts: Dict[str, int] = {}
        self._cooldown = 0
        self._alert_callback = None
        self._alerts: List[Dict[str, Any]] = []
        if alert_config:
            for k, v in alert_config.items():
                if hasattr(self, k):
                    setattr(self, k, float(v))

    def plan_grasp(self,
                   target_pose: np.ndarray,
                   object_size_mm: float,
                   surface_normal: Optional[np.ndarray] = None) -> Dict[str, Any]:
        """规划抓取策略.

        Args:
            target_pose: 目标位姿 [x, y, z, roll, pitch, yaw]
            object_size_mm: 物体尺寸
            surface_normal: 表面法向量 (用于吸盘)

        Returns:
            抓取计划
        """
        ee = self._ee_manager._active

        plan = {
            "target_pose": target_pose,
            "approach_distance_mm": 50.0,  # 接近距离
            "approach_speed_mm_s": self.MAX_APPROACH_SPEED_MM_S,
            "compliant_speed_mm_s": self.COMPLIANT_SPEED_MM_S,
            "grip_force_n": 0.0,
            "stages": [],
        }

        if ee is None:
            return plan

        if ee.ee_type == EndEffectorType.SUCTION_CUP:
            # 吸盘策略: 沿法线方向接近
            suction_force = self._ee_manager.compute_suction_force()
            plan["grip_force_n"] = 0.0  # 吸盘无夹持力，靠真空
            plan["suction_force_n"] = suction_force
            plan["stages"] = [
                {"stage": "approach", "distance": 50.0, "speed": 50.0},
                {"stage": "contact", "force_threshold": 1.0},
                {"stage": "vacuum_on", "pressure_kpa": ee.vacuum_pressure_kpa},
                {"stage": "lift_verify", "lift_height": 20.0, "slip_threshold": 0.3},
            ]

        elif ee.ee_type == EndEffectorType.PARALLEL_GRIPPER:
            # 夹爪策略: 力控夹持
            grip_force = min(ee.max_grip_force_n * 0.6,
                             max(ee.min_grip_force_n, object_size_mm * 0.5))
            plan["grip_force_n"] = grip_force
            plan["stages"] = [
                {"stage": "approach", "distance": 50.0, "speed": 50.0},
                {"stage": "pre_grasp", "opening": object_size_mm + 5.0},
                {"stage": "close_grip", "force": grip_force, "speed": 20.0},
                {"stage": "lift_verify", "lift_height": 20.0, "slip_threshold": 0.3},
            ]

        return plan

    def update_state(self, measured_force: ForceTorque,
                     gripper_position_mm: float = 0.0) -> GraspState:
        """更新抓取状态机.

        Args:
            measured_force: 力传感器读数
            gripper_position_mm: 夹爪位置

        Returns:
            当前抓取状态
        """
        force_mag = measured_force.force_magnitude
        self._contact_force_history.append(force_mag)
        # 保持最近 50 个力采样点，用于滑移检测和趋势分析
        if len(self._contact_force_history) > 50:
            self._contact_force_history = self._contact_force_history[-50:]

        # 力控异常自动检测 (力突增/力超载) -> 触发告警
        self.check_force_anomalies(force_mag)

        # 状态转换表：根据当前状态分派对应的检查函数
        transitions = {
            GraspState.APPROACH: self._check_approach_to_contact,
            GraspState.CONTACT: self._check_contact_to_grasping,
            GraspState.GRASPING: self._check_grasping_to_grasped,
            GraspState.GRASPED: self._check_grasped_stable,
            GraspState.RELEASING: self._check_releasing_to_released,
        }

        checker = transitions.get(self._state)
        prev_state = self._state
        if checker:
            self._state = checker(force_mag, gripper_position_mm)

        # 结构化输出节点: 力控状态迁移 (力控解算的权威事件源)
        if self._state != prev_state:
            logger.info(
                "[力控] 状态迁移 %s -> %s | 力=%.2fN | 夹爪开度=%.2fmm",
                prev_state.value, self._state.value, force_mag, gripper_position_mm,
                extra={
                    "event": "force_transition",
                    "from_state": prev_state.value,
                    "to_state": self._state.value,
                    "force_n": round(float(force_mag), 2),
                    "gripper_mm": round(float(gripper_position_mm), 2),
                },
            )

        return self._state

    def _check_approach_to_contact(self, force_mag: float,
                                   gripper_pos: float) -> GraspState:
        """APPROACH → CONTACT: 力超过阈值表示已接触物体。"""
        if force_mag > self.CONTACT_FORCE_THRESHOLD:
            return GraspState.CONTACT
        return GraspState.APPROACH

    def _check_contact_to_grasping(self, force_mag: float,
                                   gripper_pos: float) -> GraspState:
        """CONTACT → GRASPING: 接触后立即进入抓取阶段。"""
        return GraspState.GRASPING

    def _check_grasping_to_grasped(self, force_mag: float,
                                   gripper_pos: float) -> GraspState:
        """GRASPING → GRASPED: 力超过 2 倍接触阈值表示已抓稳。"""
        if force_mag > self.CONTACT_FORCE_THRESHOLD * 2:
            return GraspState.GRASPED
        return GraspState.GRASPING

    def _check_grasped_stable(self, force_mag: float,
                              gripper_pos: float) -> GraspState:
        """GRASPED → FAILED: 力突然下降表示滑移/掉落。"""
        # 滑移检测：比较最近 10 个采样点与之前 10 个采样点的平均力
        # 需要至少 20 个采样点，确保 [−20:−10] 切片非空
        if len(self._contact_force_history) >= 20:
            recent_avg = np.mean(self._contact_force_history[-10:])
            older_avg = np.mean(self._contact_force_history[-20:-10])
            if older_avg - recent_avg > self.SLIP_FORCE_DROP:
                return GraspState.FAILED
        return GraspState.GRASPED

    def _check_releasing_to_released(self, force_mag: float,
                                     gripper_pos: float) -> GraspState:
        """RELEASING → RELEASED: 力接近零且夹爪已打开。"""
        if force_mag < 0.1 and gripper_pos > 10.0:
            return GraspState.RELEASED
        return GraspState.RELEASING

    def detect_slip(self) -> bool:
        """检测滑移。

        通过比较接触力历史中的近期和远期数据：
        - 力平均值下降超过阈值
        - 力波动增大（标准差上升）

        这两个特征同时出现时，判定为滑移。

        Returns:
            True 如果检测到滑移
        """
        if len(self._contact_force_history) < 20:
            return False

        # 最近 10 个采样点 vs 之前 10 个采样点
        recent = np.array(self._contact_force_history[-10:])
        older = np.array(self._contact_force_history[-20:-10])

        recent_std = np.std(recent)  # 近期力波动
        older_std = np.std(older)    # 早期力波动

        # 滑移特征：力平均值下降 + 力波动增大
        force_drop = np.mean(older) - np.mean(recent)
        std_increase = recent_std - older_std

        return force_drop > self.SLIP_FORCE_DROP and std_increase > 0.1

    # ------------------------------------------------------------------
    # 力控异常告警
    # ------------------------------------------------------------------

    def set_alert_callback(self, callback) -> None:
        """注册力控异常告警回调 (供后端/上位机订阅).

        Args:
            callback: callable(alert_type: str, payload: dict),
                      在每次触发告警时同步调用。
        """
        self._alert_callback = callback

    def get_recent_alerts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的力控告警列表 (用于状态查询/上报)."""
        return self._alerts[-limit:]

    def check_force_anomalies(self, force_mag: float) -> List[Dict[str, Any]]:
        """检测力控异常并触发告警.

        支持两类异常:
        - spike:    相邻采样力突增超过 FORCE_SPIKE_DELTA_N (疑似碰撞/冲击)
        - overload: 力超过 FORCE_OVERLOAD_N 硬阈值 (疑似过夹/卡死)

        采用连续 ALERT_DEBOUNCE_STEPS 次确认抑制噪声误报, 触发后进入
        ALERT_COOLDOWN_STEPS 冷却防止告警风暴。每次告警会:
        1) 输出结构化 JSON 日志 (event=force_alert, 对接监控)
        2) 调用注册的外部回调 (set_alert_callback)

        Returns:
            本次新触发的告警字典列表 (未触发则为空列表)。
        """
        alerts: List[Dict[str, Any]] = []
        if self._cooldown > 0:
            self._cooldown -= 1
            self._last_force = force_mag
            return alerts

        delta = force_mag - self._last_force
        # 力突增需同时满足: 瞬时增量大 + 已处于一定受力水平 (排除静默噪声)
        spike = delta > self.FORCE_SPIKE_DELTA_N and force_mag > 2.0
        overload = force_mag > self.FORCE_OVERLOAD_N

        for kind, cond in (("spike", spike), ("overload", overload)):
            self._anomaly_counts[kind] = (
                self._anomaly_counts.get(kind, 0) + 1 if cond else 0
            )
            if self._anomaly_counts[kind] < self.ALERT_DEBOUNCE_STEPS:
                continue

            alert = {
                "type": kind,
                "severity": "critical" if kind == "overload" else "warning",
                "force_n": round(float(force_mag), 2),
                "delta_n": round(float(delta), 2),
                "threshold_n": (self.FORCE_OVERLOAD_N
                                if kind == "overload" else self.FORCE_SPIKE_DELTA_N),
                "grasp_state": self._state.value,
                "timestamp": time.time(),
            }
            alerts.append(alert)
            self._alerts.append(alert)
            self._anomaly_counts[kind] = 0
            self._cooldown = self.ALERT_COOLDOWN_STEPS

            # 结构化 JSON 日志 (对接监控系统)
            logger.warning(
                "[力控] 异常告警 type=%s force=%.2fN delta=%.2fN state=%s",
                kind, force_mag, delta, self._state.value,
                extra={
                    "event": "force_alert",
                    "alert_type": kind,
                    "severity": alert["severity"],
                    "force_n": alert["force_n"],
                    "delta_n": alert["delta_n"],
                    "threshold_n": alert["threshold_n"],
                    "grasp_state": self._state.value,
                },
            )
            # 外部回调 (后端/上位机订阅)
            if self._alert_callback is not None:
                try:
                    self._alert_callback(kind, alert)
                except Exception as e:  # 回调异常不应影响主流程
                    logger.error("[力控] 告警回调异常: %s", e)

        self._last_force = force_mag
        return alerts


# =============================================================================
# 力控装配
# =============================================================================


class ForceGuidedAssembly:
    """力觉引导装配 - 精密零件柔顺装配.

    使用导纳控制实现:
    - 轴孔装配 (Peg-in-Hole)
    - 齿轮啮合
    - 精密对位
    """

    def __init__(self):
        self._admittance = AdmittanceController(
            mass=np.array([0.5, 0.5, 0.5, 0.05, 0.05, 0.05]),
            damping=np.array([10, 10, 10, 2, 2, 2]),
        )
        self._hybrid = HybridForcePositionController()

    def peg_in_hole_search(self,
                           current_pose: np.ndarray,
                           measured_force: ForceTorque,
                           hole_center: np.ndarray) -> np.ndarray:
        """轴孔装配搜索策略.

        使用螺旋搜索 + 力反馈:
        1. 在 XY 平面螺旋搜索
        2. Z 方向柔顺下压
        3. 力反馈检测插入成功

        Args:
            current_pose: 当前位姿
            measured_force: 力传感器读数
            hole_center: 孔中心位置

        Returns:
            位姿修正量
        """
        # Z方向力控制，XY方向位置控制
        self._hybrid.set_force_control_axis([2])  # Z 轴力控

        # 期望力: Z方向轻微下压
        desired_force = np.array([0, 0, 5.0, 0, 0, 0])  # 5N 下压力

        # 期望位姿必须是 6 维 [x, y, z, roll, pitch, yaw]。
        # hole_center 应为 3 维 [x, y, z]；兼容 2 维 [x, y] 输入时补 Z=0。
        hole_center = np.asarray(hole_center, dtype=float).ravel()
        if hole_center.size == 2:
            center_pose = np.array([hole_center[0], hole_center[1], 0.0])
        elif hole_center.size >= 3:
            center_pose = hole_center[:3]
        else:
            raise ValueError("hole_center must be a 2D [x,y] or 3D [x,y,z] vector")
        desired_pose = np.concatenate([center_pose, np.zeros(3)])

        return self._hybrid.update(
            current_pose=current_pose,
            current_velocity=np.zeros(6),
            desired_pose=desired_pose,
            measured_force=np.append(measured_force.force_vector,
                                     measured_force.torque_vector),
            desired_force=desired_force,
        )

    def spiral_search_path(self, center: np.ndarray,
                           radius_mm: float = 5.0,
                           pitch_mm: float = 0.5,
                           num_turns: int = 3) -> List[np.ndarray]:
        """生成螺旋搜索路径.

        Args:
            center: 搜索中心 [x, y]
            radius_mm: 最大搜索半径
            pitch_mm: 螺距
            num_turns: 圈数

        Returns:
            搜索路径点列表
        """
        points = []
        total_angle = num_turns * 2 * math.pi  # 总旋转角度（弧度）
        # 每圈的点数 = 2π * radius / pitch（每螺距一圈的点数）
        num_points = int(total_angle / (pitch_mm / (radius_mm / num_turns)))

        for i in range(num_points + 1):
            # t ∈ [0, total_angle]: 均匀分布的采样角度
            t = i / num_points * total_angle
            # 阿基米德螺旋线：r = R_max * t / total_angle（半径从 0 线性增长到 R_max）
            r = radius_mm * t / total_angle
            x = center[0] + r * math.cos(t)
            y = center[1] + r * math.sin(t)
            points.append(np.array([x, y]))

        return points


# =============================================================================
# 快速测试
# =============================================================================

if __name__ == "__main__":
    # 测试阻抗控制
    imp = ImpedanceController()
    imp.set_desired_pose(np.array([0.1, 0.2, 0.3, 0, 0, 0]))
    dx = imp.update(
        np.array([0.11, 0.21, 0.31, 0, 0, 0]),
        np.zeros(6),
        np.array([2.0, 0, 0, 0, 0, 0]),  # 2N X方向力
    )
    print(f"Impedance correction: {dx}")

    # 测试末端执行器管理
    manager = EndEffectorManager()
    gripper = EndEffectorSpec(
        name="Robotiq_2F_85",
        ee_type=EndEffectorType.PARALLEL_GRIPPER,
        max_grip_force_n=85.0,
        max_opening_mm=85.0,
    )
    suction = EndEffectorSpec(
        name="Piab_20mm",
        ee_type=EndEffectorType.SUCTION_CUP,
        vacuum_pressure_kpa=-60.0,
        suction_cup_diameter_mm=20.0,
    )
    manager.register_effector(gripper)
    manager.register_effector(suction)

    manager.switch_effector("Piab_20mm")
    suction_force = manager.compute_suction_force()
    print(f"\nSuction force: {suction_force:.2f} N")

    # 测试柔顺抓取
    grasp_ctrl = CompliantGraspingController()
    grasp_ctrl._ee_manager = manager
    plan = grasp_ctrl.plan_grasp(
        np.array([0.1, 0.2, 0.3, 0, 0, 0]),
        object_size_mm=30.0,
        surface_normal=np.array([0, 0, 1]),
    )
    print(f"\nGrasp plan: {plan['stages']}")