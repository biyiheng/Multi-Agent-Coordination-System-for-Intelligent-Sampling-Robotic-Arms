"""Tests for v1.2 agent / safety enhancements.

对应《改进计划.md》§4.1, 验证 v1.2 新增与变更:
- 实时安全: 温度 / 电流过载监控 (update_joint_sensors -> _check_sensor_overload)
- Vision Agent: EMA 多帧融合滤波 (get_smoothed_position)
- Sampling Agent: 分层采样 + 边界增强 (等距 + 边界, seen 去重角点)
"""
import asyncio
import sys
from pathlib import Path

# Ensure project root is on sys.path
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import numpy as np
import pytest

from rpi_control.safety.realtime_safety import (
    RealTimeSafetyController,
    SafetyEventType,
)
from rpi_control.agents.vision_agent import VisionAgent
from rpi_control.agents.sampling_agent import SamplingAgent


# =============================================================================
# 实时安全: 温度 / 电流过载监控 (v1.2)
# =============================================================================


def _run_cycle(controller: RealTimeSafetyController,
               temperature_c: float = 40.0,
               current_a: float = 1.0) -> None:
    """注入传感器数据并执行一个安全控制周期."""
    controller.update_joint_sensors(
        temperatures=[temperature_c] * controller.num_joints,
        currents=[current_a] * controller.num_joints,
    )
    controller.control_cycle(
        joint_positions=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
        joint_velocities=[0.01] * 6,
        joint_torques=[0.5, 0.3, 0.4, 0.2, 0.3, 0.1],
        obstacle_distances=[500.0, 300.0],
        external_force=np.array([1.0, 0.5, 2.0]),
    )


def _event_types(controller: RealTimeSafetyController):
    return {e["type"] for e in controller.get_recent_events(limit=200)}


class TestSensorOverload:
    """温度 / 电流过载检测 (对应传感器采集任务 100Hz)."""

    def test_normal_sensors_no_overload(self):
        ctrl = RealTimeSafetyController(num_joints=6)
        _run_cycle(ctrl, temperature_c=40.0, current_a=1.0)
        types = _event_types(ctrl)
        assert SafetyEventType.TEMPERATURE_OVERLOAD.value not in types
        assert SafetyEventType.CURRENT_OVERLOAD.value not in types

    def test_temperature_overload_detected(self):
        ctrl = RealTimeSafetyController(num_joints=6)
        # 关节 0 温度 85°C > 70°C 上限 -> 过载事件
        _run_cycle(ctrl, temperature_c=85.0, current_a=1.0)
        types = _event_types(ctrl)
        assert SafetyEventType.TEMPERATURE_OVERLOAD.value in types

    def test_current_overload_detected(self):
        ctrl = RealTimeSafetyController(num_joints=6)
        # 关节电流 5A > 3A 上限 -> 过载事件
        _run_cycle(ctrl, temperature_c=40.0, current_a=5.0)
        types = _event_types(ctrl)
        assert SafetyEventType.CURRENT_OVERLOAD.value in types

    def test_sensor_values_persist_across_cycles(self):
        ctrl = RealTimeSafetyController(num_joints=6)
        ctrl.update_joint_sensors(temperatures=[42.0] * 6, currents=[0.8] * 6)
        # 后续不注入时保持上一周期值
        ctrl.control_cycle(
            joint_positions=[0.0] * 6,
            joint_velocities=[0.0] * 6,
            joint_torques=[0.0] * 6,
        )
        assert all(s.temperature_c == 42.0 for s in ctrl._joint_states)
        assert all(s.current_a == 0.8 for s in ctrl._joint_states)


# =============================================================================
# Vision Agent: EMA 多帧融合滤波 (v1.2)
# =============================================================================


def _push_detection(agent: VisionAgent, cx: float, cy: float, area: float) -> None:
    """向 position_history 追加一帧检测."""
    agent.position_history.append({"cx": cx, "cy": cy, "area": area})


class TestVisionEMA:
    """EMA 多帧融合滤波提升检测稳定性."""

    def test_first_frame_initializes_ema(self):
        agent = VisionAgent()
        _push_detection(agent, 160.0, 120.0, 5000.0)
        out = agent.get_smoothed_position()
        assert out is not None
        assert out["smoothed"] is True
        assert out["ema_count"] == 1
        assert out["cx"] == pytest.approx(160.0)

    def test_ema_smooths_jitter(self):
        agent = VisionAgent()
        # 稳定目标在 (160,120), 单帧抖动到 (200,120)
        for _ in range(3):
            _push_detection(agent, 160.0, 120.0, 5000.0)
            agent.get_smoothed_position()
        _push_detection(agent, 200.0, 120.0, 5000.0)
        out = agent.get_smoothed_position()
        # 中值滤波已剔除单帧抖动, EMA 稳定在真实目标 160
        assert out["cx"] == pytest.approx(160.0)
        assert out["ema_count"] == 4

    def test_ema_recurrence_formula(self):
        agent = VisionAgent()
        agent._ema_alpha = 0.5
        _push_detection(agent, 100.0, 120.0, 5000.0)
        agent.get_smoothed_position()  # ema = 100
        # 历史整体上移到 120 -> 中值 120 -> ema = 0.5*120 + 0.5*100 = 110
        for _ in range(5):
            _push_detection(agent, 120.0, 120.0, 5000.0)
        out = agent.get_smoothed_position()
        assert out["cx"] == pytest.approx(110.0)
        assert out["ema_count"] == 2

    def test_history_gap_resets_ema(self):
        agent = VisionAgent()
        for _ in range(3):
            _push_detection(agent, 160.0, 120.0, 5000.0)
            agent.get_smoothed_position()
        assert agent._ema_count == 3
        # 历史中断 -> get_smoothed_position 重置 EMA
        agent.position_history.clear()
        assert agent.get_smoothed_position() is None
        assert agent._ema_count == 0
        assert agent._ema_state is None

    def test_reset_ema(self):
        agent = VisionAgent()
        _push_detection(agent, 160.0, 120.0, 5000.0)
        agent.get_smoothed_position()
        assert agent._ema_count == 1
        agent.reset_ema()
        assert agent._ema_count == 0
        assert agent._ema_state is None


# =============================================================================
# Sampling Agent: 分层采样 + 边界增强 (v1.2)
# =============================================================================


class TestSamplingBoundaryEnhancement:
    """等距分层 + 边界增强, 提升覆盖均匀性."""

    BOUNDS = {"x": (0.0, 100.0), "y": (0.0, 100.0), "z": (0.0, 50.0)}

    def test_point_count_matches_strata_plus_boundary(self):
        agent = SamplingAgent()
        points = asyncio.run(agent._stratified_sampling(self.BOUNDS, strata=4))
        # 等距 4x4=16 + 边界增强 16 (4角去重后 5*4-4=16)
        assert len(points) == 32

    def test_all_points_inside_bounds(self):
        agent = SamplingAgent()
        points = asyncio.run(agent._stratified_sampling(self.BOUNDS, strata=4))
        x_min, x_max = self.BOUNDS["x"]
        y_min, y_max = self.BOUNDS["y"]
        z = (self.BOUNDS["z"][0] + self.BOUNDS["z"][1]) / 2
        for p in points:
            x, y, zz = p.position
            assert x_min <= x <= x_max
            assert y_min <= y <= y_max
            assert zz == z

    def test_boundary_points_marked(self):
        agent = SamplingAgent()
        points = asyncio.run(agent._stratified_sampling(self.BOUNDS, strata=4))
        boundary = [p for p in points if p.metadata.get("boundary")]
        assert len(boundary) == 16
        assert all(p.priority == 1 for p in boundary)

    def test_no_duplicate_positions(self):
        agent = SamplingAgent()
        points = asyncio.run(agent._stratified_sampling(self.BOUNDS, strata=4))
        seen = {(round(p.position[0], 3), round(p.position[1], 3)) for p in points}
        assert len(seen) == len(points)

    def test_edge_coverage_includes_corners(self):
        agent = SamplingAgent()
        points = asyncio.run(agent._stratified_sampling(self.BOUNDS, strata=4))
        positions = {(round(p.position[0], 3), round(p.position[1], 3)) for p in points}
        # 四角必须被覆盖 (边界增强)
        for corner in [(0.0, 0.0), (100.0, 0.0), (0.0, 100.0), (100.0, 100.0)]:
            assert corner in positions
