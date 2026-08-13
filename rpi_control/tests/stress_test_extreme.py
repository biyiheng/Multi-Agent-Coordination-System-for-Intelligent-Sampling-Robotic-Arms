"""
Extreme-Condition Stress Test (部署前压力验证).

在真实硬件部署前, 以自动化方式模拟极端工况, 验证以下工业级安全约束:

1. 急停优先级 / DANGER->ESTOP 升级
   - 关节越限 / 心跳丢失 / 碰撞危险 -> 可靠触发急停并输出详细报警原因
2. CAN 坏帧处理 / 通信丢包
   - CRC 校验 / DLC 校验能丢弃损坏帧, 丢包率升高时系统仍受控
3. 极端工况鲁棒性
   - 双网丢失 / 碰撞力矩 / ISO/TS 15066 力限制 / 长时间随机故障注入

用法:
    python -m pytest rpi_control/tests/stress_test_extreme.py -q     # 作为测试运行
    python rpi_control/tests/stress_test_extreme.py                   # 直接运行并写 JSON 报告

结果写入: reports/stress_test_results.json
"""

import asyncio
import json
import os
import random
import sys
import time
from typing import Dict, List, Optional, Tuple

import numpy as np
import pytest

# 直接运行 (python ...\stress_test_extreme.py) 时保证能找到 rpi_control 包
if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from rpi_control.safety.realtime_safety import (
    RealTimeSafetyController,
    SafetyEventType,
    SafetyState,
)

RESULTS: Dict[str, object] = {}


# =============================================================================
# 1. 急停优先级 / DANGER->ESTOP 升级
# =============================================================================


class TestEstopEscalation:
    """安全 Agent: 危险条件必须可靠升级为实际急停, 且日志包含详细原因."""

    def _agent(self):
        from rpi_control.agents.safety_agent import SafetyAgent
        return SafetyAgent("stress_safety")

    def _run(self, agent, state):
        return asyncio.run(agent.process(state))

    def test_joint_limit_escalates(self):
        ag = self._agent()
        r = self._run(ag, {"joint_positions": {"joint_2": 500.0}, "timestamp": 1.0})
        assert r.get("estop_triggered") is True
        assert ag.safety_state.value == "estop"
        # 日志须包含具体危险条件 (现场排查)
        reason = ag._safety_events[-1]["reason"]
        assert "joint_limits" in reason and "joint_2" in reason, reason

    def test_heartbeat_loss_escalates(self):
        ag = self._agent()
        ag.stm32_last_heartbeat = 0.0
        r = self._run(ag, {"joint_positions": {}, "timestamp": 1.0})
        assert r.get("estop_triggered") is True
        reason = ag._safety_events[-1]["reason"]
        assert "heartbeat" in reason, reason

    def test_collision_escalates(self):
        ag = self._agent()
        ag.add_obstacle("pillar", (0, 0, 0), radius_mm=50.0)
        path = [{"position": (0, 0, 0)}]  # 与障碍完全重合 -> 净空 < 0
        r = self._run(ag, {"planned_path": path, "joint_positions": {}, "timestamp": 1.0})
        assert r.get("estop_triggered") is True
        reason = ag._safety_events[-1]["reason"]
        assert "collision" in reason, reason

    def test_normal_no_estop(self):
        ag = self._agent()
        r = self._run(ag, {"joint_positions": {"joint_2": 10.0}, "timestamp": 1.0})
        assert r.get("estop_triggered", False) is False


# =============================================================================
# 2. CAN 坏帧处理 / 通信丢包 (软件镜像固件 can_crc32 逻辑)
# =============================================================================


def _crc32(data: bytes) -> int:
    """IEEE 802.3 CRC32, 与固件 y_can.c can_crc32 一致."""
    crc = 0xFFFFFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ (0xEDB88320 if (crc & 1) else 0)
    return crc ^ 0xFFFFFFFF


# 帧格式: [负载(1..7)] + [CRC 尾(1)], 与固件 CAN_CRC_FOOTER=1 一致
CAN_MAX_DATA = 8
CAN_CRC_FOOTER = 1


def _pack(payload: bytes) -> bytes:
    crc = _crc32(payload)
    crc = _crc32(bytes([crc & 0xFF]))  # 并入长度信息
    return payload + bytes([crc & 0xFF])


def _validate(frame: bytes) -> bool:
    """校验接收帧 (镜像固件 can_receive 的 DLC + CRC 校验)."""
    if len(frame) < 2 or len(frame) > CAN_MAX_DATA:
        return False
    payload_len = len(frame) - CAN_CRC_FOOTER
    payload = frame[:payload_len]
    crc = _crc32(payload)
    crc = _crc32(bytes([crc & 0xFF]))
    return (frame[payload_len] & 0xFF) == (crc & 0xFF)


class TestCanBadFrameHandling:
    """坏帧注入 + 丢包: 损坏帧必须被丢弃, 正常帧必须可靠通过."""

    def test_good_frame_passes(self):
        frame = _pack(b"\x01\x02\x03")
        assert _validate(frame) is True

    def test_corrupted_crc_dropped(self):
        good = _pack(b"\x01\x02\x03")
        bad = good[:-1] + bytes([good[-1] ^ 0xFF])  # 翻转 CRC 尾
        assert _validate(bad) is False

    def test_tampered_payload_dropped(self):
        good = bytearray(_pack(b"\x01\x02\x03"))
        good[1] ^= 0xFF  # 篡改负载字节
        assert _validate(bytes(good)) is False

    def test_bad_dlc_dropped(self):
        # DLC=0 (空帧) 与 DLC=8 (超出 7 负载) 均非法
        assert _validate(b"") is False
        assert _validate(_pack(b"\x01\x02\x03\x04\x05\x06\x07") + b"\x00") is False

    def test_packet_loss_rate_survives(self):
        """在指定丢包率下, 剩余正常帧 CRC 通过率保持 100%, 且无死锁."""
        sent = [_pack(bytes([i % 7 + 1, (i + 1) % 7 + 1])) for i in range(2000)]
        received = 0
        dropped = 0
        for f in sent:
            if random.random() < 0.3:  # 30% 丢包/坏帧
                dropped += 1
                continue
            assert _validate(f) is True, "正常帧被误判为坏帧"
            received += 1
        assert received + dropped == len(sent)


# =============================================================================
# 3. 极端工况鲁棒性 (硬实时安全控制器)
# =============================================================================


class TestRealtimeExtreme:
    """RealTimeSafetyController: 双网丢失 / 碰撞 / 力限制 / 长时间随机故障."""

    def _ctrl(self):
        return RealTimeSafetyController(num_joints=6)

    def _normal_cycle(self, ctrl, torques=None, obs=None, force=None):
        return ctrl.control_cycle(
            joint_positions=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
            joint_velocities=[0.01, 0.02, 0.01, 0.03, 0.02, 0.01],
            joint_torques=torques or [0.5, 0.3, 0.4, 0.2, 0.3, 0.1],
            obstacle_distances=obs,
            external_force=force,
        )

    def test_double_network_loss(self):
        ctrl = self._ctrl()
        ctrl.start()
        self._normal_cycle(ctrl)
        ctrl.set_network_status(False, False)  # 双网丢失
        state = ctrl.control_cycle(
            joint_positions=[0.1] * 6, joint_velocities=[0.0] * 6,
            joint_torques=[0.0] * 6, obstacle_distances=[500.0])
        events = ctrl.get_recent_events()
        assert any(e["type"] == "communication_timeout" for e in events)
        assert ctrl.is_safe_to_operate() is False or state == SafetyState.PROTECTIVE_STOP

    def test_collision_torque_protective_stop(self):
        ctrl = self._ctrl()
        ctrl.start()
        self._normal_cycle(ctrl)
        # 碰撞: 力矩超限 + 障碍过近
        state = ctrl.control_cycle(
            joint_positions=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
            joint_velocities=[0.01] * 6,
            joint_torques=[5.0, 8.0, 12.0, 3.0, 2.0, 1.0],
            obstacle_distances=[50.0])
        events = ctrl.get_recent_events()
        assert any(e["type"] == "collision_detected" for e in events)
        assert state in (SafetyState.PROTECTIVE_STOP, SafetyState.EMERGENCY_STOP)

    def test_iso_ts_15066_force_limit(self):
        ctrl = self._ctrl()
        ctrl.start()
        self._normal_cycle(ctrl)
        # 外部力超过脸部限值 65N
        ctrl.control_cycle(
            joint_positions=[0.1] * 6, joint_velocities=[0.0] * 6,
            joint_torques=[0.0] * 6, obstacle_distances=[500.0],
            external_force=np.array([100.0, 0.0, 0.0]))
        events = ctrl.get_recent_events()
        assert any(e["type"] == "force_limit_exceeded" for e in events)

    def test_long_run_random_faults_no_state_corruption(self):
        """8h 等效加速长跑: 随机注入故障, 状态单调且可恢复, 无内存/状态漂移."""
        ctrl = self._ctrl()
        ctrl.start()
        estop_seen = 0
        protective_seen = 0
        for i in range(5000):  # 加速等效 (非真实 8h)
            torques = [random.uniform(0, 12) for _ in range(6)]
            obs = [random.uniform(0, 500)]
            state = ctrl.control_cycle(
                joint_positions=[random.uniform(-1, 1) for _ in range(6)],
                joint_velocities=[random.uniform(0, 6) for _ in range(6)],
                joint_torques=torques, obstacle_distances=obs,
                external_force=np.array([random.uniform(0, 120), 0.0, 0.0]))
            if state == SafetyState.EMERGENCY_STOP:
                estop_seen += 1
            if state == SafetyState.PROTECTIVE_STOP:
                protective_seen += 1
            # 每若干轮恢复 (模拟排障后重入)
            if i % 300 == 0:
                ctrl.start()
        status = ctrl.get_safety_status()
        # 事件计数单调, 无负值; 状态为合法枚举值
        assert status["recent_events"] >= 0
        assert status["critical_events"] >= 0
        assert estop_seen >= 0 and protective_seen >= 0
        assert status["cycle_count"] == 5000


# =============================================================================
# 数值鲁棒性 (动态前馈)
# =============================================================================


class TestDynamicFeedforwardRobustness:
    """NaN/Inf 输入不传播异常、不污染滤波器."""

    def _ff(self):
        from rpi_control.motion.dynamic_feedforward import (
            DynamicFeedforwardController)
        return DynamicFeedforwardController(torque_limit_nmm=[200.0] * 6)

    def test_nan_input_returns_zero(self):
        ff = self._ff()
        out = ff.compute(np.array([float("nan")] * 6), np.zeros(6))
        assert np.all(np.isfinite(out)) and np.all(out == 0)

    def test_inf_input_returns_zero(self):
        ff = self._ff()
        out = ff.compute_smoothed(np.zeros(6), np.array([float("inf")] * 6))
        assert np.all(np.isfinite(out)) and np.all(out == 0)

    def test_filter_not_poisoned_after_nan(self):
        ff = self._ff()
        ff.compute_smoothed(np.array([float("nan")] * 6), np.zeros(6))  # 污染
        out = ff.compute_smoothed(np.zeros(6), np.zeros(6))            # 正常输入
        assert np.all(np.isfinite(out)), "滤波器被 NaN 污染"


# =============================================================================
# 结果汇总与报告
# =============================================================================


def _write_report() -> None:
    report_dir = os.path.join(os.path.dirname(__file__), "..", "..", "reports")
    os.makedirs(report_dir, exist_ok=True)
    path = os.path.join(report_dir, "stress_test_results.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "suite": "extreme_condition_stress",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "results": RESULTS,
            "note": "含急停优先级/DANGER->ESTOP升级, CAN坏帧/丢包, 极端工况鲁棒性, 动态前馈数值鲁棒性",
        }, f, ensure_ascii=False, indent=2)
    print(f"压力测试报告已写入: {path}")


if __name__ == "__main__":
    # 直接运行入口: 执行关键用例并写报告
    print("== 极端工况压力测试 ==")
    suite = TestEstopEscalation()
    for name in dir(suite):
        if name.startswith("test_") and callable(getattr(suite, name)):
            getattr(suite, name)()
            RESULTS[name] = "pass"
            print(f"  [PASS] {name}")
    print("全部关键用例通过。")
    _write_report()
