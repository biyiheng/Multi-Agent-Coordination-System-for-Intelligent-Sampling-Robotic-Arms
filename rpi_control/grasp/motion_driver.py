"""
Motion Driver abstraction for the sampling robotic arm.

将“运动执行”抽象为统一接口，使 GraspPipeline 可同时运行于:
- 仿真模式 (SimulationMotionDriver): 无硬件, 用 FK 跟踪末端位姿, 仅记录运动
- 真实硬件模式 (RealArmMotionDriver): 通过 ServoController/STM32 驱动 6 关节 + 夹爪

所有方法均为 async，返回后可进行后续规划。
"""

from abc import ABC, abstractmethod
from typing import List, Optional

import numpy as np

from ..utils.logger import get_logger
from ..motion.kinematics import (
    forward_kinematics,
    joint_angles_to_pwm,
    NUM_JOINTS,
)

logger = get_logger(__name__)


class BaseMotionDriver(ABC):
    """机械臂运动执行器抽象基类."""

    name: str = "base"

    @abstractmethod
    async def move_to_joints(self, joints_rad: List[float],
                             move_time_ms: int = 1000) -> None:
        """将机械臂移动到指定关节角 (弧度)."""

    @abstractmethod
    async def open_gripper(self) -> None:
        """打开夹爪."""

    @abstractmethod
    async def close_gripper(self, force_pwm: Optional[int] = None) -> None:
        """闭合夹爪 (可指定夹持力 PWM)."""

    @abstractmethod
    async def get_joints(self) -> List[float]:
        """获取当前关节角 (弧度)."""

    def end_effector_pose(self, joints_rad: Optional[List[float]] = None) -> np.ndarray:
        """计算末端位姿 4x4 矩阵 (用于监控/校验)."""
        q = joints_rad if joints_rad is not None else None
        if q is None:
            # 默认取零位姿; 子类可重写以读取真实关节
            q = [0.0] * NUM_JOINTS
        T, _ = forward_kinematics(list(q))
        return T


class SimulationMotionDriver(BaseMotionDriver):
    """仿真运动驱动: 无硬件, 维护关节状态并记录运动轨迹.

    用于在无机械臂的机器上验证 GraspPipeline 完整逻辑。
    """

    name = "simulation"

    def __init__(self, start_joints: Optional[List[float]] = None) -> None:
        self._joints: List[float] = list(start_joints) if start_joints else [0.0] * NUM_JOINTS
        self.motion_log: List[dict] = []
        self._gripper_position_mm: float = 0.0  # 0 = 闭合, 30 = 张开

    async def move_to_joints(self, joints_rad: List[float],
                             move_time_ms: int = 1000) -> None:
        self.motion_log.append({"type": "move", "joints": list(joints_rad),
                                "move_time_ms": move_time_ms})
        self._joints = list(joints_rad)
        logger.debug(f"[sim] move to joints {[round(j, 3) for j in joints_rad]}")

    async def open_gripper(self) -> None:
        self.motion_log.append({"type": "gripper_open"})
        self._gripper_position_mm = 30.0
        logger.debug("[sim] gripper open")

    async def close_gripper(self, force_pwm: Optional[int] = None) -> None:
        self.motion_log.append({"type": "gripper_close", "force_pwm": force_pwm})
        self._gripper_position_mm = 0.0
        logger.debug(f"[sim] gripper close (force={force_pwm})")

    async def get_joints(self) -> List[float]:
        return list(self._joints)

    @property
    def gripper_position_mm(self) -> float:
        return self._gripper_position_mm

    def end_effector_pose(self, joints_rad: Optional[List[float]] = None) -> np.ndarray:
        q = joints_rad if joints_rad is not None else self._joints
        return super().end_effector_pose(q)


class RealArmMotionDriver(BaseMotionDriver):
    """真实硬件运动驱动: 通过 ServoController 驱动 6 关节 + 夹爪.

    Args:
        servo: 已连接的 ServoController 实例.
        move_time_ms: 默认单次关节移动耗时.
    """

    name = "real"

    def __init__(self, servo, move_time_ms: int = 1000) -> None:
        self._servo = servo
        self._move_time_ms = move_time_ms

    async def move_to_joints(self, joints_rad: List[float],
                             move_time_ms: int = 1000) -> None:
        pwm = joint_angles_to_pwm(joints_rad)
        await self._servo.move_to_joint_positions(pwm, move_time_ms)
        logger.info(f"[real] move joints to PWM {pwm}")

    async def open_gripper(self) -> None:
        await self._servo.open_gripper()
        logger.info("[real] gripper open")

    async def close_gripper(self, force_pwm: Optional[int] = None) -> None:
        await self._servo.close_gripper(force_pwm)
        logger.info(f"[real] gripper close force={force_pwm}")

    async def get_joints(self) -> List[float]:
        # ServoController 返回 PWM, 转回弧度
        from ..motion.kinematics import pwm_to_joint_angles
        pwm = await self._servo.get_current_positions()
        return pwm_to_joint_angles(pwm)
