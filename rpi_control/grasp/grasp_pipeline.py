"""
Grasp Pipeline: 将视觉位姿估计、手眼变换、运动学、轨迹规划与力控抓取
集成为一套完整的抓取流程，供主控制流程调用。

流程:
    视觉 (相机系, 米) -> PnP 位姿 -> 手眼变换 (机器人系, 毫米)
    -> 抓取/接近/放置位姿规划 -> IK -> 关节轨迹 -> 力控抓取 -> 放置 -> 释放

通过注入 MotionDriver 与 ForceSource, 同一套流程可运行于仿真或真实硬件。
"""

import asyncio
import math
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger
from ..vision.pose_estimator import PoseEstimator, Pose6D
from ..vision.calibration import CameraCalibration
from ..motion.kinematics import (
    inverse_kinematics,
    forward_kinematics,
    KinematicsError,
)
from ..motion.trajectory import plan_joint_path
from ..motion.force_control import (
    CompliantGraspingController,
    EndEffectorSpec,
    EndEffectorType,
    ForceTorque,
    GraspState,
)

logger = get_logger(__name__)


# =============================================================================
# 力传感器数据源抽象
# =============================================================================


class ForceSource(ABC):
    """力传感器读数来源抽象."""

    @abstractmethod
    def read(self) -> ForceTorque:
        """读取当前六维力/力矩."""


class ScriptedForceSource(ForceSource):
    """仿真力源: 按预置力谱逐次输出, 用于无硬件时驱动抓取状态机."""

    def __init__(self, profile: Optional[List[float]] = None) -> None:
        # 默认力谱: 接近(0N) -> 接触(1.5N) -> 夹紧(6N) -> 稳定
        self._profile = profile if profile is not None else [
            0.0, 0.0, 0.0, 1.5, 3.0, 6.0, 6.0, 6.0, 6.0, 6.0, 6.0,
        ]
        self._idx = 0

    def read(self) -> ForceTorque:
        f = self._profile[min(self._idx, len(self._profile) - 1)]
        self._idx += 1
        return ForceTorque(fx=f)


class CallbackForceSource(ForceSource):
    """回调力源: 从外部读取函数获取真实力传感器读数 (如 STM32)."""

    def __init__(self, read_fn) -> None:
        self._read_fn = read_fn

    def read(self) -> ForceTorque:
        return self._read_fn()


# =============================================================================
# 抓取流水线
# =============================================================================


class GraspPipeline:
    """端到端视觉引导抓取流水线."""

    def __init__(self,
                 driver,
                 camera_matrix: Optional[np.ndarray] = None,
                 hand_eye_rotation: Optional[np.ndarray] = None,
                 hand_eye_translation: Optional[np.ndarray] = None,
                 config: Optional[Dict[str, Any]] = None) -> None:
        """初始化流水线.

        Args:
            driver: MotionDriver 实例 (仿真或真实硬件).
            camera_matrix: 3x3 相机内参, 缺省用 OpenMV 默认内参.
            hand_eye_rotation: 相机->机器人 旋转矩阵 (3x3).
            hand_eye_translation: 相机->机器人 平移向量 (mm, 3x1).
            config: 抓取配置 (object/offsets/place 等).
        """
        self.config = config or {}

        # 相机内参
        if camera_matrix is None:
            camera_matrix = np.array([[320, 0, 160], [0, 320, 120], [0, 0, 1]],
                                     dtype=np.float64)
        self.camera_matrix = np.asarray(camera_matrix, dtype=np.float64)

        # 手眼标定
        self.cal = CameraCalibration()
        self.cal.camera_matrix = self.camera_matrix
        self.cal.dist_coeffs = np.zeros(5)
        if hand_eye_rotation is not None:
            self.cal.rotation_matrix = np.asarray(hand_eye_rotation, dtype=np.float64)
        if hand_eye_translation is not None:
            self.cal.translation_vector = np.asarray(hand_eye_translation,
                                                     dtype=np.float64).reshape(3, 1)

        # 位姿估计器
        self.estimator = PoseEstimator(camera_matrix=self.camera_matrix)

        # 运动驱动
        self.driver = driver

        # 力控抓取控制器
        self.grasp_ctrl = CompliantGraspingController()
        self._gripper_ready = False

        # 配置项
        self.approach_offset_mm = float(self.config.get("approach_offset_mm", 50.0))
        self.grasp_offset_mm = float(self.config.get("grasp_offset_mm", 10.0))
        self.place_pose = np.asarray(
            self.config.get("place_pose", [-50.0, 50.0, -50.0, 0.0, math.pi, 0.0]),
            dtype=np.float64,
        )
        self.home_joints = list(self.config.get("home_joints", [0.0] * 6))

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------

    def initialize_gripper(self,
                           name: str = "gripper",
                           max_force_n: float = 30.0,
                           min_force_n: float = 1.0) -> None:
        """注册并启用平行夹爪执行器."""
        self.grasp_ctrl._ee_manager.register_effector(EndEffectorSpec(
            name=name,
            ee_type=EndEffectorType.PARALLEL_GRIPPER,
            max_grip_force_n=max_force_n,
            min_grip_force_n=min_force_n,
        ))
        self.grasp_ctrl._ee_manager.switch_effector(name)
        self._gripper_ready = True

    def register_object(self, name: str, model_points: np.ndarray) -> None:
        """注册物体 3D 模型点 (物体坐标系, 米)."""
        self.estimator.register_object_model(name, np.asarray(model_points,
                                                              dtype=np.float64))

    def load_calibration(self, path: str) -> bool:
        """从 JSON/YAML 加载相机内参与手眼标定."""
        return self.cal.load_calibration(path)

    # ------------------------------------------------------------------
    # 视觉定位
    # ------------------------------------------------------------------

    def localize_object(self,
                        image_points: np.ndarray,
                        object_name: str) -> Optional[np.ndarray]:
        """由 2D-3D 对应点定位物体中心 (机器人基座, mm).

        Args:
            image_points: Nx2 图像角点坐标.
            object_name: 已注册的物体模型名.

        Returns:
            物体中心在机器人基座系的坐标 (mm), 或 None (定位失败).
        """
        logger.debug(f"[PnP] 输入: object='{object_name}', 图像点数={len(image_points)}")
        pose = self.estimator.estimate_pose_pnp(image_points, object_name)
        if pose is None:
            logger.error("PnP 位姿估计失败")
            return None

        R = pose.to_matrix()[:3, :3]
        model = self.estimator.object_model_points[object_name]
        half = np.array([model[:, 0].max(), model[:, 1].max(),
                         model[:, 2].max()]) / 2.0

        # 物体中心 (相机系, 米)
        center_cam_m = pose.position + R @ half
        center_cam_mm = center_cam_m * 1000.0
        logger.debug("[PnP] 物体中心(相机系,mm)=[%.2f, %.2f, %.2f]",
                     center_cam_mm[0], center_cam_mm[1], center_cam_mm[2])

        # 手眼变换 -> 机器人系 (mm)
        center_robot = self.cal.camera_to_robot(tuple(center_cam_mm))
        if center_robot is None:
            logger.error("手眼标定未就绪, 无法变换到机器人系")
            return None

        logger.info("[手眼] 相机系(mm) -> 机器人系(mm): "
                    "[%.2f, %.2f, %.2f] -> [%.2f, %.2f, %.2f]",
                    center_cam_mm[0], center_cam_mm[1], center_cam_mm[2],
                    center_robot[0], center_robot[1], center_robot[2])
        logger.info("物体定位 (机器人系): ({:.1f}, {:.1f}, {:.1f}) mm | 置信度 {:.3f}".format(
            center_robot[0], center_robot[1], center_robot[2], pose.confidence))
        return np.array(center_robot, dtype=np.float64)

    # ------------------------------------------------------------------
    # 抓取规划
    # ------------------------------------------------------------------

    def plan(self, obj_center_robot_mm: np.ndarray) -> Optional[Dict[str, Any]]:
        """规划抓取位姿并求解逆运动学.

        Args:
            obj_center_robot_mm: 物体中心 (机器人系, mm).

        Returns:
            包含 approach/grasp/place 关节角与轨迹的规划字典, 或 None (不可达).
        """
        grasp_pos = np.array(obj_center_robot_mm) + np.array([0, 0, self.grasp_offset_mm])
        grasp_pose = np.array([grasp_pos[0], grasp_pos[1], grasp_pos[2],
                               0.0, math.pi, 0.0])  # 夹爪朝下
        approach_pose = grasp_pose.copy()
        approach_pose[2] += self.approach_offset_mm

        logger.debug("[规划] 抓取目标位姿=[%.1f, %.1f, %.1f, 0, π, 0] 接近点=[%.1f, %.1f, %.1f]",
                     grasp_pose[0], grasp_pose[1], grasp_pose[2],
                     approach_pose[0], approach_pose[1], approach_pose[2])

        try:
            approach_joints = inverse_kinematics(approach_pose)
            grasp_joints = inverse_kinematics(grasp_pose)
            place_joints = inverse_kinematics(self.place_pose)
        except KinematicsError as e:
            logger.error("IK 规划失败: %s", e)
            return None

        # ---- IK 求解节点 (便于排查可达性与多解) ----
        logger.info(
            "[IK] 接近点: %d 解 -> %s\n"
            "[IK] 抓取点: %d 解 -> %s\n"
            "[IK] 放置点: %d 解 -> %s",
            len(approach_joints), np.round(approach_joints[0], 3).tolist(),
            len(grasp_joints), np.round(grasp_joints[0], 3).tolist(),
            len(place_joints), np.round(place_joints[0], 3).tolist(),
        )
        approach_joints = approach_joints[0]
        grasp_joints = grasp_joints[0]
        place_joints = place_joints[0]

        plan = {
            "grasp_pos": grasp_pos,
            "grasp_pose": grasp_pose,
            "approach_pose": approach_pose,
            "place_pose": self.place_pose,
            "approach_joints": approach_joints,
            "grasp_joints": grasp_joints,
            "place_joints": place_joints,
        }
        logger.info(f"抓取规划完成: 接近点可达, 抓取点可达, 放置点可达")
        return plan

    # ------------------------------------------------------------------
    # 执行
    # ------------------------------------------------------------------

    async def _run_force_grasp(self, force_source: ForceSource,
                               max_steps: int = 400) -> GraspState:
        """在夹爪闭合过程中, 用力反馈驱动抓取状态机直至抓稳/失败.

        状态迁移的结构化日志由 force_control.update_state 权威输出
        (event=force_transition), 此处仅保留逐拍 DEBUG 与起止 INFO。
        """
        state = GraspState.APPROACH
        logger.info("[力控] 开始力控抓取, max_steps=%d", max_steps,
                    extra={"event": "force_start"})
        for step in range(max_steps):
            f = force_source.read()
            # 实测接触力幅值 (Fx 为主向; 视传感器而定)
            f_mag = float(getattr(f, "fx", 0.0))
            gripper_mm = self.driver.gripper_position_mm
            state = self.grasp_ctrl.update_state(f, gripper_mm)

            logger.debug("[力控] step=%03d 力=%.2fN 夹爪开度=%.2fmm 状态=%s",
                         step, f_mag, gripper_mm, state.value)

            if state in (GraspState.GRASPED, GraspState.FAILED):
                break
            await asyncio.sleep(0.02)

        logger.info("[力控] 结束: 最终状态=%s (共 %d 步, 最大 %d)",
                    state.value, step + 1, max_steps,
                    extra={"event": "force_end",
                           "final_state": state.value,
                           "steps": step + 1})
        return state

    async def execute(self, plan: Dict[str, Any],
                      force_source: Optional[ForceSource] = None) -> Dict[str, Any]:
        """执行抓取流程: 归零 -> 接近 -> 力控抓取 -> 提升 -> 放置 -> 释放.

        Returns:
            执行结果字典 (阶段状态, 搬运位移, 抓取状态等).
        """
        result: Dict[str, Any] = {"stages": [], "success": False}
        if not self._gripper_ready:
            logger.error("夹爪执行器未初始化, 请先调用 initialize_gripper()")
            return result

        def _ee(target_joints, tag):
            """FK 计算末端位姿并记录 (便于排查运动段)."""
            T, _ = forward_kinematics(list(target_joints))
            p = T[:3, 3]
            logger.debug("[运动][%s] 末端位置(mm)=[%.2f, %.2f, %.2f]", tag,
                         p[0], p[1], p[2])
            return p

        # 打开夹爪, 回到归零位
        await self.driver.open_gripper()
        logger.info("[执行] 夹爪已打开, 返回归零位")
        await self.driver.move_to_joints(self.home_joints, move_time_ms=800)
        result["stages"].append("home")
        _ee(self.home_joints, "home")

        # 归零 -> 接近
        approach_joints = plan["approach_joints"]
        grasp_joints = plan["grasp_joints"]
        place_joints = plan["place_joints"]
        _ee(approach_joints, "approach")
        _ee(grasp_joints, "grasp")
        _ee(place_joints, "place")

        traj1 = plan_joint_path(self.home_joints, approach_joints, duration=1.0, dt=0.05)
        logger.info("[执行] 阶段1: 归零 -> 接近点 (轨迹 %d 点)", len(traj1))
        for pt in traj1:
            await self.driver.move_to_joints(pt.positions, move_time_ms=40)
        result["stages"].append("approach")

        # 接近 -> 抓取
        traj2 = plan_joint_path(approach_joints, grasp_joints, duration=0.5, dt=0.05)
        logger.info("[执行] 阶段2: 接近点 -> 抓取点 (轨迹 %d 点)", len(traj2))
        for pt in traj2:
            await self.driver.move_to_joints(pt.positions, move_time_ms=40)
        result["stages"].append("pre_grasp")

        # 力控抓取
        if force_source is None:
            force_source = ScriptedForceSource()
        grasp_state = await self._run_force_grasp(force_source)
        result["grasp_state"] = grasp_state.value
        if grasp_state == GraspState.FAILED:
            logger.error("抓取失败 (检测到滑移/掉落)")
            result["stages"].append("failed")
            await self.driver.move_to_joints(self.home_joints, move_time_ms=800)
            return result
        logger.info("[执行] 抓取成功, 闭合夹爪")
        await self.driver.close_gripper()
        result["stages"].append("grasped")

        # 抓取 -> 放置
        traj3 = plan_joint_path(grasp_joints, place_joints, duration=1.5, dt=0.05)
        logger.info("[执行] 阶段3: 抓取点 -> 放置点 (轨迹 %d 点)", len(traj3))
        for pt in traj3:
            await self.driver.move_to_joints(pt.positions, move_time_ms=50)
        result["stages"].append("place")

        # 搬运位移 (FK 校验)
        T_end = forward_kinematics(place_joints)[0]
        T_start = forward_kinematics(grasp_joints)[0]
        travel = float(np.linalg.norm(T_end[:3, 3] - T_start[:3, 3]))
        result["travel_mm"] = round(travel, 1)

        # 释放
        await self.driver.open_gripper()
        result["stages"].append("release")
        result["success"] = True

        # 回到归零位
        await self.driver.move_to_joints(self.home_joints, move_time_ms=800)
        result["stages"].append("home")

        logger.info("抓取流程完成: 搬运 %s mm | 阶段 %s",
                    result.get('travel_mm'), ' -> '.join(result['stages']),
                    extra={
                        "event": "grasp_result",
                        "success": result.get("success"),
                        "travel_mm": result.get("travel_mm"),
                        "grasp_state": result.get("grasp_state"),
                        "stages": result.get("stages"),
                    })
        return result

    # ------------------------------------------------------------------
    # 完整流程
    # ------------------------------------------------------------------

    async def run_cycle(self,
                        image_points: np.ndarray,
                        object_name: str,
                        force_source: Optional[ForceSource] = None) -> Dict[str, Any]:
        """执行一个完整的视觉引导抓取循环.

        Args:
            image_points: Nx2 图像点 (2D-3D 对应).
            object_name: 已注册物体名.
            force_source: 力源 (缺省用仿真脚本力谱).

        Returns:
            结果字典.
        """
        result: Dict[str, Any] = {"success": False}

        # 1. 视觉定位
        obj_center = self.localize_object(image_points, object_name)
        if obj_center is None:
            result["error"] = "vision_localization_failed"
            return result
        result["object_center_mm"] = obj_center.tolist()

        # 2. 抓取规划
        plan = self.plan(obj_center)
        if plan is None:
            result["error"] = "ik_no_solution"
            return result
        result["grasp_pos_mm"] = plan["grasp_pos"].tolist()

        # 3. 执行
        exec_result = await self.execute(plan, force_source)
        result.update(exec_result)
        return result
