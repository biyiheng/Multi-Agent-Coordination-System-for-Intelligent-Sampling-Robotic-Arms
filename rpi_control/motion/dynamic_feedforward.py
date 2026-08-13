"""
Dynamic Feedforward Control Module.

工业级升级规划 §3.2 / S3: 动力学前馈 (重力补偿 + 关节摩擦力模型)。

本模块在现有纯运动学控制 (S 曲线/梯形轨迹) 之上叠加动力学前馈项, 用于
提升低速精度与轨迹跟踪性能。前馈力矩由三部分组成:

    tau_ff = tau_gravity(q) + tau_friction(q_dot) + tau_inertia(q, q_dot, q_ddot)

其中:
- tau_gravity(q): 重力补偿项 G(q), 基于连杆质量/质心/重力势能偏导
- tau_friction(q_dot): 摩擦补偿项 F(q_dot), 库仑 + 粘滞 (+ 可选 Stribeck)
- tau_inertia(q, q_dot, q_ddot): 惯量/速度项 M(q)·q_ddot + C(q, q_dot)·q_dot
  (作为可选的二阶前馈, 默认仅启用重力 + 摩擦, 满足 S3 验收)

设计要点:
1. 重力项通过各连杆质心位置的世界坐标 Jacobian 精确计算, 与 DH 参数一致。
2. 摩擦项在零速附近采用 tanh 平滑近似, 避免 sign() 跳变引起前馈抖动。
3. 输出带力矩限幅与一阶低通滤波, 保证前馈平稳注入底层闭环。
4. 提供参数辨识接口 (稳态力矩回归), 支持在线更新连杆/摩擦参数。

参考:
- Siciliano & Villani 1999, "Robot Dynamics and Control"
- 工业级升级规划 §3 控制算法层面重构 / S3 验收: 低速精度提升 ≥50%
"""

import math
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger
from .kinematics import (NUM_JOINTS, DEG_TO_RAD, DEFAULT_DH_PARAMS,
                         DHParameter, transformation_matrix)

logger = get_logger(__name__)

# 重力加速度 (m/s^2); 位置单位为 mm, 需统一换算
GRAVITY_MS2 = 9.81
MM_TO_M = 1e-3


# =============================================================================
# 参数数据模型
# =============================================================================


@dataclass
class LinkDynamicParams:
    """单连杆动力学参数.

    Attributes:
        mass_kg: 连杆质量 (kg)
        com_mm: 质心在连杆坐标系中的位置 (mm)
        inertia_kgmm2: 连杆绕质心坐标系的主惯性张量 (3x3, kg·mm^2)
    """
    mass_kg: float = 0.0
    com_mm: np.ndarray = field(default_factory=lambda: np.zeros(3))
    inertia_kgmm2: np.ndarray = field(
        default_factory=lambda: np.eye(3) * 1e-6)

    def __post_init__(self) -> None:
        self.com_mm = np.asarray(self.com_mm, dtype=float).reshape(3)
        self.inertia_kgmm2 = np.asarray(self.inertia_kgmm2, dtype=float).reshape(3, 3)


@dataclass
class FrictionParams:
    """关节摩擦参数 (库仑 + 粘滞 + 可选 Stribeck).

    Attributes:
        coulomb_nmm: 库仑摩擦力矩 (N·mm)
        viscous_nmm_per_rads: 粘滞摩擦系数 (N·mm·s/rad)
        stribeck_nmm: Stribeck 摩擦幅值 (N·mm)
        stribeck_vel: Stribeck 特征速度 (rad/s)
        smooth_vel: 零速平滑窗口 (rad/s), tanh 近似用
    """
    coulomb_nmm: float = 0.0
    viscous_nmm_per_rads: float = 0.0
    stribeck_nmm: float = 0.0
    stribeck_vel: float = 0.1
    smooth_vel: float = 0.05


@dataclass
class DynamicParams:
    """机械臂整体动力学参数.

    Attributes:
        link_params: 各连杆动力学参数列表 (顺序与关节一致, 长度 = NUM_JOINTS)
        friction: 各关节摩擦参数列表
        gravity_vec: 重力加速度方向 (世界坐标系, 一般 (0, 0, -g))
    """
    link_params: List[LinkDynamicParams] = field(default_factory=list)
    friction: List[FrictionParams] = field(default_factory=list)
    gravity_vec: np.ndarray = field(
        default_factory=lambda: np.array([0.0, 0.0, -GRAVITY_MS2]))


# =============================================================================
# 重力补偿
# =============================================================================


class GravityCompensator:
    """重力补偿器 - 计算重力项 G(q).

    通过各连杆质心位置在重力方向上的 Jacobian 计算势能偏导:
        U(q) = sum_i m_i * g · p_com_i(q)
        G_j(q) = dU/dq_j = sum_i m_i * g · (∂p_com_i / ∂q_j)

    连杆质心位置 p_com_i 与线性速度 Jacobian 由 DH 变换链递推求得。
    """

    def __init__(self, params: Optional[DynamicParams] = None):
        self.params = params or DynamicParams()
        # 基于 DH 参数构建连杆变换 (与 kinematics.DEFAULT_DH_PARAMS 对齐)
        self._dh = [DHParameter(a, alpha, d, theta_off)
                    for (a, alpha, d, theta_off) in DEFAULT_DH_PARAMS]

    def set_params(self, params: DynamicParams) -> None:
        """更新动力学参数 (用于在线辨识后刷新)."""
        self.params = params

    def _link_com_positions(self, q: np.ndarray) -> List[np.ndarray]:
        """计算各连杆质心的世界坐标位置 (mm).

        使用标准 DH 变换链递推各连杆坐标系位姿, 将连杆系内的质心坐标
        变换到世界系。这样肩/肘等绕水平轴转动的关节会改变质心高度,
        从而得到非零的重力项。

        Args:
            q: 关节角 (rad), 长度 = NUM_JOINTS

        Returns:
            长度 NUM_JOINTS 的列表, 每项为 3 维质心世界坐标 (mm)
        """
        n = min(len(q), NUM_JOINTS)
        positions: List[np.ndarray] = []
        T_cur = np.eye(4)  # 世界 → 当前连杆系
        for i in range(n):
            lp = self.params.link_params[i] if i < len(self.params.link_params) else \
                LinkDynamicParams()
            # 当前关节角加入 DH theta 偏移
            theta = q[i] + self._dh[i].theta_offset
            T_cur = T_cur @ transformation_matrix(self._dh[i], theta)
            # 质心在世界系 = T_cur * [com; 1]
            com_h = np.concatenate([lp.com_mm, [1.0]])
            p_com_world = (T_cur @ com_h)[:3]
            positions.append(p_com_world.copy())
        return positions

    def compute(self, q: np.ndarray) -> np.ndarray:
        """计算重力补偿力矩 G(q).

        Args:
            q: 关节角 (rad)

        Returns:
            G 向量 (N·mm), 长度 = NUM_JOINTS
        """
        q = np.asarray(q, dtype=float)
        n = min(len(q), NUM_JOINTS)
        G = np.zeros(NUM_JOINTS)
        if len(self.params.link_params) == 0:
            return G

        positions = self._link_com_positions(q)
        g = self.params.gravity_vec
        # 各质心位置的数值 Jacobian (仅重力方向分量)
        # G_j = sum_i m_i * g · dp_com_i/dq_j ; 用中心差分求 dp/dq_j
        # 单位说明: _link_com_positions 返回质心位移 dp 单位为 mm,
        # g·dp 单位为 (m/s²·mm), 再 ×m_i(kg) 得 kg·m/s²·mm = N·mm/rad ≡ N·mm,
        # 因此无需再乘换算系数 (结果即 N·mm 力矩)。
        h = 1e-6
        for j in range(n):
            qp = q.copy()
            qm = q.copy()
            qp[j] += h
            qm[j] -= h
            Pp = self._link_com_positions(qp)
            Pm = self._link_com_positions(qm)
            for i in range(n):
                m_i = self.params.link_params[i].mass_kg \
                    if i < len(self.params.link_params) else 0.0
                dp = (Pp[i] - Pm[i]) / (2.0 * h)  # mm/rad
                G[j] += m_i * (g @ dp)  # N·mm
        return G


# =============================================================================
# 摩擦模型
# =============================================================================


class FrictionModel:
    """关节摩擦模型.

    采用库仑 + 粘滞 + Stribeck 模型, 并用 tanh 平滑零速跳变:

        F(v) = F_c·tanh(v/ε) + F_v·v + F_s·exp(-(v/v_s)²)·tanh(v/ε)

    其中:
    - F_c: 库仑摩擦
    - F_v: 粘滞摩擦
    - F_s: Stribeck 幅值
    - v_s: Stribeck 特征速度
    - ε:   平滑宽度 (smooth_vel)
    """

    def __init__(self, params: Optional[FrictionParams] = None,
                 joint_count: int = NUM_JOINTS):
        self.joint_count = joint_count
        self.params = [params or FrictionParams() for _ in range(joint_count)]

    def set_joint_friction(self, joint: int, params: FrictionParams) -> None:
        """设置指定关节的摩擦参数."""
        if 0 <= joint < self.joint_count:
            self.params[joint] = params

    def compute(self, q_dot: np.ndarray) -> np.ndarray:
        """计算摩擦补偿力矩 F(q_dot).

        Args:
            q_dot: 关节速度 (rad/s)

        Returns:
            F 向量 (N·mm)
        """
        q_dot = np.asarray(q_dot, dtype=float)
        F = np.zeros(self.joint_count)
        for j in range(min(self.joint_count, len(q_dot))):
            p = self.params[j]
            v = q_dot[j]
            eps = max(p.smooth_vel, 1e-6)
            tanh_v = math.tanh(v / eps)
            viscous = p.viscous_nmm_per_rads * v
            coulomb = p.coulomb_nmm * tanh_v
            stribeck = 0.0
            if p.stribeck_nmm > 0.0:
                vs = max(p.stribeck_vel, 1e-6)
                stribeck = p.stribeck_nmm * math.exp(-(v / vs) ** 2) * tanh_v
            F[j] = coulomb + viscous + stribeck
        return F


# =============================================================================
# 动力学前馈控制器
# =============================================================================


class DynamicFeedforwardController:
    """动力学前馈控制器.

    融合重力补偿、摩擦补偿与 (可选) 惯量/科氏前馈, 在底层关节闭环
    前注入前馈力矩, 提升低速与变速精度。

    默认启用重力 + 摩擦 (满足 S3); 惯性/科氏项作为可选项 (use_inertia=True)。
    """

    def __init__(self,
                 params: Optional[DynamicParams] = None,
                 joint_limits: Optional[List[Tuple[float, float]]] = None,
                 torque_limit_nmm: Optional[np.ndarray] = None,
                 use_inertia: bool = False):
        self.gravity = GravityCompensator(params or DynamicParams())
        self.friction = FrictionModel(joint_count=NUM_JOINTS)
        # 将 DynamicParams.friction 同步到 FrictionModel
        if params is not None and params.friction:
            for j, fp in enumerate(params.friction):
                self.friction.set_joint_friction(j, fp)
        self.use_inertia = use_inertia
        self.joint_limits = joint_limits
        self.torque_limit = torque_limit_nmm
        # 前馈输出一阶低通滤波 (时间常数 s)
        self.lp_alpha = 0.5
        self._ff_prev = np.zeros(NUM_JOINTS)
        self._t_prev = None

    def set_dynamic_params(self, params: DynamicParams) -> None:
        """在线更新动力学参数."""
        self.gravity.set_params(params)
        if params.friction:
            for j, fp in enumerate(params.friction):
                self.friction.set_joint_friction(j, fp)

    def compute_gravity(self, q: np.ndarray) -> np.ndarray:
        """重力补偿项 G(q)."""
        return self.gravity.compute(q)

    def compute_friction(self, q_dot: np.ndarray) -> np.ndarray:
        """摩擦补偿项 F(q_dot)."""
        return self.friction.compute(q_dot)

    def compute_inertia(self, q: np.ndarray,
                        q_dot: np.ndarray,
                        q_ddot: np.ndarray) -> np.ndarray:
        """惯量/速度项 (简化): 对角惯量近似 M_diag·q_ddot.

        完整的 M(q)·q_ddot + C(q,q_dot)·q_dot 需辨识惯性张量与科氏项,
        本实现采用对角惯量近似, 适合低速采样任务。

        Returns:
            惯量前馈 (N·mm)
        """
        n = NUM_JOINTS
        M_diag = np.array([
            self.gravity.params.link_params[i].inertia_kgmm2[0, 0]
            if i < len(self.gravity.params.link_params) else 1e-3
            for i in range(n)
        ])
        # 转动惯量单位为 kg·mm^2, q_ddot 单位为 rad/s^2 → kg·mm^2·rad/s^2 = N·mm
        return M_diag * np.asarray(q_ddot, dtype=float)[:n]

    def compute(self, q: np.ndarray,
                q_dot: np.ndarray,
                q_ddot: Optional[np.ndarray] = None) -> np.ndarray:
        """计算总前馈力矩.

        Args:
            q: 关节角 (rad)
            q_dot: 关节速度 (rad/s)
            q_ddot: 关节加速度 (rad/s^2), 仅 use_inertia=True 时使用

        Returns:
            前馈力矩向量 (N·mm), 长度 = NUM_JOINTS
        """
        # 极端工况防护: 任一输入含 NaN/Inf 时返回零前馈, 避免在
        # 运动学层 (math.cos/sin) 抛出未捕获异常或产生 NaN 传播。
        q = np.asarray(q, dtype=float)
        q_dot = np.asarray(q_dot, dtype=float)
        if not np.all(np.isfinite(q)) or not np.all(np.isfinite(q_dot)) or \
                (q_ddot is not None and not np.all(np.isfinite(np.asarray(q_ddot, dtype=float)))):
            logger.error("DynamicFeedforward: non-finite input (NaN/Inf); "
                         "returning zero feedforward")
            return np.zeros(NUM_JOINTS)

        tau_ff = self.compute_gravity(q) + self.compute_friction(q_dot)
        if self.use_inertia and q_ddot is not None:
            tau_ff = tau_ff + self.compute_inertia(q, q_dot, q_ddot)
        return tau_ff

    def compute_smoothed(self, q: np.ndarray,
                         q_dot: np.ndarray,
                         q_ddot: Optional[np.ndarray] = None,
                         timestamp: Optional[float] = None) -> np.ndarray:
        """计算前馈力矩并做一阶低通平滑, 抑制高频注入抖动.

        Args:
            q: 关节角 (rad)
            q_dot: 关节速度 (rad/s)
            q_ddot: 关节加速度 (rad/s^2)
            timestamp: 时间戳 (s); 若与上次调用间隔变化则按间隔加权

        Returns:
            平滑后的前馈力矩 (N·mm)
        """
        raw = self.compute(q, q_dot, q_ddot)

        # 极端工况防护: 若输入含 NaN/Inf 导致前馈非法, 重置滤波状态并
        # 返回零, 避免单次非法值永久污染一阶低通滤波 (_ff_prev 递归传播 NaN)。
        if not np.all(np.isfinite(raw)):
            logger.error(
                "DynamicFeedforward: non-finite feedforward (NaN/Inf); "
                "resetting filter and returning zeros")
            self.reset_filter()
            return np.zeros(NUM_JOINTS)

        # 力矩限幅
        if self.torque_limit is not None:
            for j in range(NUM_JOINTS):
                lim = abs(self.torque_limit[j]) if j < len(self.torque_limit) else 0.0
                if lim > 0.0:
                    raw[j] = np.clip(raw[j], -lim, lim)

        # 一阶低通滤波
        if self._ff_prev is not None:
            out = self.lp_alpha * raw + (1.0 - self.lp_alpha) * self._ff_prev
        else:
            out = raw
        self._ff_prev = out
        return out

    def reset_filter(self) -> None:
        """重置前馈滤波状态."""
        self._ff_prev = np.zeros(NUM_JOINTS)
        self._t_prev = None

    # ------------------------------------------------------------------
    # 参数辨识 (稳态力矩回归)
    # ------------------------------------------------------------------

    def identify_friction_from_steady(self,
                                      samples: List[Tuple[float, float]]) -> FrictionParams:
        """从稳态匀速采样点辨识单关节摩擦参数.

        Args:
            samples: [(v, tau_steady)] 列表, v 为关节速度 (rad/s),
                     tau_steady 为匀速稳态时实测驱动力矩 (N·mm) (近似等于摩擦)

        Returns:
            拟合得到的摩擦参数 (库仑 + 粘滞)
        """
        if len(samples) < 2:
            return FrictionParams()
        v = np.array([s[0] for s in samples], dtype=float)
        t = np.array([s[1] for s in samples], dtype=float)
        # 线性拟合: tau ≈ F_c·sign(v) + F_v·v
        A = np.stack([np.sign(v), v], axis=1)
        coeff, *_ = np.linalg.lstsq(A, t, rcond=None)
        return FrictionParams(coulomb_nmm=float(coeff[0]),
                              viscous_nmm_per_rads=float(coeff[1]))


# =============================================================================
# 便捷工厂: 从 DH 参数 + 质量生成默认动力学参数
# =============================================================================


def default_dynamic_params(mass_per_link: float = 0.3,
                           com_offset_mm: float = 50.0) -> DynamicParams:
    """生成默认动力学参数 (简化均匀假设).

    Args:
        mass_per_link: 每连杆质量 (kg)
        com_offset_mm: 质心沿连杆 x 轴的偏移 (mm)

    Returns:
        DynamicParams 实例
    """
    links = []
    friction = []
    for i in range(NUM_JOINTS):
        links.append(LinkDynamicParams(
            mass_kg=mass_per_link,
            com_mm=np.array([com_offset_mm, 0.0, 0.0]),
            inertia_kgmm2=np.eye(3) * (mass_per_link * com_offset_mm ** 2),
        ))
        friction.append(FrictionParams(
            coulomb_nmm=20.0,       # 默认库仑摩擦 (N·mm)
            viscous_nmm_per_rads=2.0,
            stribeck_nmm=8.0,
            stribeck_vel=0.1,
            smooth_vel=0.05,
        ))
    return DynamicParams(link_params=links, friction=friction)


# =============================================================================
# 快速测试
# =============================================================================

if __name__ == "__main__":
    params = default_dynamic_params()
    ctrl = DynamicFeedforwardController(params=params, use_inertia=True)

    q = np.array([0.1, 0.2, 0.3, 0.0, 0.0, 0.0])
    q_dot = np.array([0.05, -0.02, 0.0, 0.0, 0.0, 0.0])
    q_ddot = np.array([0.5, -0.3, 0.0, 0.0, 0.0, 0.0])

    G = ctrl.compute_gravity(q)
    F = ctrl.compute_friction(q_dot)
    tau = ctrl.compute(q, q_dot, q_ddot)

    print("Gravity G(q):", np.round(G, 3))
    print("Friction F(q_dot):", np.round(F, 3))
    print("Feedforward tau_ff:", np.round(tau, 3))

    # 摩擦参数辨识验证
    samples = [(v, 20.0 * math.copysign(1, v) + 2.0 * v) for v in
               (-2, -1, -0.5, 0.5, 1, 2)]
    ident = ctrl.identify_friction_from_steady(samples)
    print("Identified friction:", round(ident.coulomb_nmm, 2),
          round(ident.viscous_nmm_per_rads, 2))
