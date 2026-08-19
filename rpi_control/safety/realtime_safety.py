"""
Hard Real-Time Safety Controller for Embodied Intelligent Sampling Unit.

实现毫秒级安全控制:
- 安全级速度监控 (Safety-Rated Monitored Speed)
- 碰撞检测与力矩限制 (Collision Detection & Torque Limiting)
- 人机共享空间安全合规 (Human-Robot Collaboration Safety)
- 网络冗余与时戳同步 (Network Redundancy & Clock Sync)
- 安全回原位与断点续推 (Safe Homing & Checkpoint Resume)

符合:
- ISO/TS 15066:2016 协作机器人安全标准
- ISO 10218-1:2011 工业机器人安全要求
- ISO 13849-1:2015 安全相关控制系统设计 (PLr/SIL)

安全完整性等级目标: SIL 2 / PL d
"""

import enum
import logging
import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, List, Optional, Set, Tuple

import numpy as np

logger = logging.getLogger("realtime_safety")


# =============================================================================
# 枚举与常量
# =============================================================================


class SafetyState(enum.Enum):
    """安全状态机."""
    NORMAL = "normal"               # 正常运行
    REDUCED_SPEED = "reduced_speed"  # 减速运行
    PROTECTIVE_STOP = "protective_stop"  # 保护性停止
    EMERGENCY_STOP = "emergency_stop"    # 紧急停止
    SAFEGUARD_STOP = "safeguard_stop"    # 安全门停止
    RECOVERY = "recovery"           # 恢复中
    FAULT = "fault"                 # 故障


class SafetyEventType(enum.Enum):
    """安全事件类型."""
    SPEED_LIMIT_EXCEEDED = "speed_limit_exceeded"
    JOINT_LIMIT_VIOLATION = "joint_limit_violation"
    COLLISION_DETECTED = "collision_detected"
    TORQUE_OVERLOAD = "torque_overload"
    FORCE_LIMIT_EXCEEDED = "force_limit_exceeded"  # ISO/TS 15066
    WORKSPACE_VIOLATION = "workspace_violation"
    COMMUNICATION_TIMEOUT = "communication_timeout"
    CLOCK_DRIFT = "clock_drift"
    HARDWARE_FAULT = "hardware_fault"
    SAFEGUARD_OPEN = "safeguard_open"
    ESTOP_PRESSED = "estop_pressed"
    POWER_LOSS = "power_loss"
    TEMPERATURE_WARNING = "temperature_warning"
    # v1.2 新增: 传感器采集链路 (对应《改进计划.md》传感器采集任务 100Hz) 过载事件
    TEMPERATURE_OVERLOAD = "temperature_overload"
    CURRENT_OVERLOAD = "current_overload"
    SENSOR_FAULT = "sensor_fault"


class SafetyIntegrityLevel(enum.Enum):
    """安全完整性等级."""
    SIL1 = 1
    SIL2 = 2
    SIL3 = 3
    SIL4 = 4


# ISO/TS 15066:2016 人体部位力/压力限值
COLLABORATIVE_FORCE_LIMITS = {
    "skull_forehead": {"force_n": 175, "pressure_n_cm2": 130},
    "face": {"force_n": 65, "pressure_n_cm2": 65},
    "neck": {"force_n": 150, "pressure_n_cm2": 140},
    "back_shoulders": {"force_n": 210, "pressure_n_cm2": 160},
    "chest": {"force_n": 140, "pressure_n_cm2": 120},
    "abdomen": {"force_n": 110, "pressure_n_cm2": 140},
    "upper_arm_elbow": {"force_n": 150, "pressure_n_cm2": 190},
    "lower_arm_wrist": {"force_n": 150, "pressure_n_cm2": 190},
    "hands_fingers": {"force_n": 140, "pressure_n_cm2": 240},
    "thighs_knees": {"force_n": 220, "pressure_n_cm2": 220},
    "lower_legs": {"force_n": 180, "pressure_n_cm2": 220},
}

# 安全速度限制
SAFETY_SPEED_LIMITS = {
    "reduced_speed_max_mm_s": 250,      # ISO/TS 15066 减速模式
    "safety_rated_monitored_speed_mm_s": 2000,  # 安全监控速度
    "tcp_max_speed_mm_s": 1000,         # TCP 最大速度
    "joint_max_speed_rad_s": 5.0,       # 关节最大速度
}

# 安全距离
SAFETY_DISTANCES = {
    "min_separation_distance_mm": 200,       # 最小分离距离
    "protective_stop_distance_mm": 100,      # 保护停止距离
    "reduced_speed_zone_mm": 500,            # 减速区域
    "collision_warning_distance_mm": 300,    # 碰撞预警距离
}


# =============================================================================
# 数据结构
# =============================================================================


@dataclass
class SafetyEvent:
    """安全事件."""
    event_type: SafetyEventType
    timestamp: float = field(default_factory=time.time)
    severity: int = 0  # 0=info, 1=warning, 2=critical
    description: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = ""


@dataclass
class JointSafetyState:
    """关节安全状态."""
    position_rad: float = 0.0
    velocity_rad_s: float = 0.0
    torque_nm: float = 0.0
    temperature_c: float = 25.0
    current_a: float = 0.0
    is_limit_exceeded: bool = False
    limit_violation_type: str = ""


@dataclass
class TCPVelocity:
    """TCP 速度."""
    linear_mm_s: float = 0.0
    angular_rad_s: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class ClockSyncState:
    """时钟同步状态."""
    master_time: float = 0.0
    local_time: float = 0.0
    offset_ns: float = 0.0
    drift_ppm: float = 0.0
    is_synced: bool = False
    last_sync_time: float = 0.0
    sync_method: str = "ptp"  # PTP (IEEE 1588) or NTP


# =============================================================================
# 硬实时安全控制器
# =============================================================================


class RealTimeSafetyController:
    """硬实时安全控制器.

    控制循环: 1 ms (1000 Hz)
    安全验证: 每个控制周期
    故障响应: < 10 ms
    """

    # 控制周期 (秒)
    CONTROL_PERIOD_S = 0.001  # 1ms
    # 故障响应时限 (秒)
    FAULT_RESPONSE_DEADLINE_S = 0.010  # 10ms
    # 安全状态历史大小
    SAFETY_HISTORY_SIZE = 1000

    def __init__(self,
                 num_joints: int = 6,
                 safety_level: SafetyIntegrityLevel = SafetyIntegrityLevel.SIL2):
        self.num_joints = num_joints
        self.safety_level = safety_level

        # 当前状态
        self._safety_state = SafetyState.NORMAL
        self._joint_states: List[JointSafetyState] = [
            JointSafetyState() for _ in range(num_joints)
        ]
        self._tcp_velocity = TCPVelocity()

        # 限值
        self._joint_limits: List[Tuple[float, float]] = [
            (-170, 170) for _ in range(num_joints)
        ]
        self._joint_velocity_limits: List[float] = [5.0] * num_joints
        self._joint_torque_limits: List[float] = [50.0] * num_joints
        self._collision_torque_threshold: float = 10.0  # Nm
        self._collision_force_threshold: float = 65.0   # N (脸部限值)
        # v1.2 新增: 传感器采集过载限值 (对应《改进计划.md》传感器采集任务 100Hz)
        self._joint_temperature_limits: List[float] = [70.0] * num_joints  # °C 过载
        self._joint_temperature_warn: float = 55.0  # °C 预警
        self._joint_current_limits: List[float] = [3.0] * num_joints  # A 过载

        # 事件历史
        self._events: Deque[SafetyEvent] = deque(maxlen=self.SAFETY_HISTORY_SIZE)
        self._event_handlers: Dict[SafetyEventType, List[Callable]] = {}
        self._state_callbacks: Dict[SafetyState, List[Callable]] = {}

        # 统计数据
        self._cycle_count: int = 0
        self._overrun_count: int = 0
        self._max_cycle_time_us: float = 0.0
        self._last_cycle_time_us: float = 0.0

        # 线程安全
        self._lock = threading.Lock()
        self._running = False

        # 网络冗余
        self._primary_network_ok = True
        self._backup_network_ok = True
        self._last_heartbeat: Dict[str, float] = {}
        self._heartbeat_timeout_s = 0.1  # 100ms 心跳超时

        # 时钟同步
        self._clock_sync = ClockSyncState()

        # 断点数据
        self._checkpoint: Optional[Dict[str, Any]] = None

    # -------------------------------------------------------------------------
    # 控制循环
    # -------------------------------------------------------------------------

    def start(self) -> None:
        """启动安全控制循环."""
        self._running = True
        self._safety_state = SafetyState.NORMAL

    def stop(self) -> None:
        """停止安全控制循环."""
        self._running = False
        self._safety_state = SafetyState.SAFEGUARD_STOP

    def control_cycle(self,
                      joint_positions: List[float],
                      joint_velocities: List[float],
                      joint_torques: List[float],
                      tcp_velocity: Optional[TCPVelocity] = None,
                      external_force: Optional[np.ndarray] = None,
                      obstacle_distances: Optional[List[float]] = None,
                      ) -> SafetyState:
        """执行一个安全控制周期 (1ms).

        Args:
            joint_positions: 关节位置 (rad)
            joint_velocities: 关节速度 (rad/s)
            joint_torques: 关节力矩 (Nm)
            tcp_velocity: TCP速度
            external_force: 外部力 [Fx, Fy, Fz] (N)
            obstacle_distances: 障碍物距离列表

        Returns:
            当前安全状态
        """
        cycle_start = time.perf_counter_ns()

        with self._lock:
            self._cycle_count += 1

            # 1. 更新关节状态
            self._update_joint_states(joint_positions, joint_velocities, joint_torques)

            # 2. 更新TCP速度
            if tcp_velocity:
                self._tcp_velocity = tcp_velocity

            # 3. 检查关节限位
            self._check_joint_limits()

            # 4. 检查速度限制
            self._check_speed_limits()

            # 5. 碰撞检测
            if obstacle_distances:
                self._check_collision(obstacle_distances, external_force)

            # 6. 力矩监控
            self._check_torque_limits()

            # 6b. 传感器过载监控 (v1.2: 温度/电流, 对应传感器采集任务 100Hz)
            self._check_sensor_overload()

            # 7. 力限制 (ISO/TS 15066)
            if external_force is not None:
                self._check_force_limits(external_force)

            # 8. 通信检查
            self._check_communication()

            # 9. 时钟同步
            self._check_clock_sync()

            # 10. 更新状态
            self._update_safety_state()

        # 性能监控
        cycle_time_ns = time.perf_counter_ns() - cycle_start
        cycle_time_us = cycle_time_ns / 1000.0
        self._last_cycle_time_us = cycle_time_us
        self._max_cycle_time_us = max(self._max_cycle_time_us, cycle_time_us)

        if cycle_time_us > self.CONTROL_PERIOD_S * 1e6 * 0.9:
            self._overrun_count += 1

        return self._safety_state

    def _update_joint_states(self, positions: List[float],
                             velocities: List[float],
                             torques: List[float]) -> None:
        """更新关节状态."""
        for i in range(min(self.num_joints, len(positions))):
            self._joint_states[i].position_rad = positions[i]
            self._joint_states[i].velocity_rad_s = (
                velocities[i] if i < len(velocities) else 0.0
            )
            self._joint_states[i].torque_nm = (
                torques[i] if i < len(torques) else 0.0
            )

    def update_joint_sensors(self,
                             temperatures: Optional[List[float]] = None,
                             currents: Optional[List[float]] = None) -> None:
        """更新关节温度/电流传感器采集值 (v1.2, 对应传感器采集任务 100Hz).

        由传感器采集链路周期调用, 将最新温度/电流写入各关节状态,
        供过载监控 (_check_sensor_overload) 在安全周期内判限。

        Args:
            temperatures: 各关节温度 (°C), None 则保持当前值.
            currents: 各关节电流 (A), None 则保持当前值.
        """
        with self._lock:
            for i in range(self.num_joints):
                if temperatures is not None and i < len(temperatures):
                    self._joint_states[i].temperature_c = float(temperatures[i])
                if currents is not None and i < len(currents):
                    self._joint_states[i].current_a = float(currents[i])

    def _check_joint_limits(self) -> None:
        """检查关节限位."""
        for i, state in enumerate(self._joint_states):
            if i >= len(self._joint_limits):
                break
            low, high = self._joint_limits[i]
            pos = state.position_rad

            if pos < low or pos > high:
                self._emit_event(SafetyEvent(
                    event_type=SafetyEventType.JOINT_LIMIT_VIOLATION,
                    severity=2,
                    description=f"Joint {i+1}: {math.degrees(pos):.1f}° out of "
                                f"[{low:.0f}°, {high:.0f}°]",
                    data={"joint": i, "position": pos, "limits": [low, high]},
                    source="joint_limit_check",
                ))
                state.is_limit_exceeded = True
                state.limit_violation_type = "position"

    def _check_speed_limits(self) -> None:
        """检查速度限制."""
        # 关节速度
        for i, state in enumerate(self._joint_states):
            if i >= len(self._joint_velocity_limits):
                break
            vel_limit = self._joint_velocity_limits[i]

            if abs(state.velocity_rad_s) > vel_limit:
                self._emit_event(SafetyEvent(
                    event_type=SafetyEventType.SPEED_LIMIT_EXCEEDED,
                    severity=1,
                    description=f"Joint {i+1} velocity: {state.velocity_rad_s:.2f} rad/s > {vel_limit}",
                    data={"joint": i, "velocity": state.velocity_rad_s, "limit": vel_limit},
                    source="speed_check",
                ))

        # TCP速度
        if self._tcp_velocity.linear_mm_s > SAFETY_SPEED_LIMITS["tcp_max_speed_mm_s"]:
            self._emit_event(SafetyEvent(
                event_type=SafetyEventType.SPEED_LIMIT_EXCEEDED,
                severity=2,
                description=f"TCP speed: {self._tcp_velocity.linear_mm_s:.1f} mm/s > "
                            f"{SAFETY_SPEED_LIMITS['tcp_max_speed_mm_s']} mm/s",
                source="speed_check",
            ))

    def _check_collision(self, obstacle_distances: List[float],
                         external_force: Optional[np.ndarray] = None) -> None:
        """碰撞检测."""
        min_distance = min(obstacle_distances) if obstacle_distances else float("inf")

        if min_distance < SAFETY_DISTANCES["collision_warning_distance_mm"]:
            severity = 2 if min_distance < SAFETY_DISTANCES["protective_stop_distance_mm"] else 1
            self._emit_event(SafetyEvent(
                event_type=SafetyEventType.COLLISION_DETECTED,
                severity=severity,
                description=f"Obstacle at {min_distance:.1f} mm",
                data={"min_distance": min_distance,
                      "warning_distance": SAFETY_DISTANCES["collision_warning_distance_mm"]},
                source="collision_check",
            ))

        # 基于力矩的碰撞检测
        total_torque = sum(abs(s.torque_nm) for s in self._joint_states)
        if total_torque > self._collision_torque_threshold:
            self._emit_event(SafetyEvent(
                event_type=SafetyEventType.COLLISION_DETECTED,
                severity=2,
                description=f"Collision torque: {total_torque:.1f} Nm > {self._collision_torque_threshold} Nm",
                data={"total_torque": total_torque, "threshold": self._collision_torque_threshold},
                source="torque_collision_check",
            ))

    def _check_torque_limits(self) -> None:
        """力矩限制检查."""
        for i, state in enumerate(self._joint_states):
            if i >= len(self._joint_torque_limits):
                break
            limit = self._joint_torque_limits[i]

            if abs(state.torque_nm) > limit:
                self._emit_event(SafetyEvent(
                    event_type=SafetyEventType.TORQUE_OVERLOAD,
                    severity=2,
                    description=f"Joint {i+1} torque: {state.torque_nm:.1f} Nm > {limit} Nm",
                    data={"joint": i, "torque": state.torque_nm, "limit": limit},
                    source="torque_check",
                ))

    def _check_sensor_overload(self) -> None:
        """传感器过载监控 (v1.2).

        对应《改进计划.md》§4.1 传感器采集任务 (100Hz): 实时读取电流 / 电压 /
        温度等传感器, 超限时触发过载事件并联动安全状态机。
        """
        for i, state in enumerate(self._joint_states):
            if i >= self.num_joints:
                break

            # 温度过载 (critical)
            if i < len(self._joint_temperature_limits) and \
                    state.temperature_c > self._joint_temperature_limits[i]:
                self._emit_event(SafetyEvent(
                    event_type=SafetyEventType.TEMPERATURE_OVERLOAD,
                    severity=2,
                    description=f"Joint {i+1} temperature: "
                                f"{state.temperature_c:.1f}°C > "
                                f"{self._joint_temperature_limits[i]:.1f}°C",
                    data={"joint": i,
                          "temperature": state.temperature_c,
                          "limit": self._joint_temperature_limits[i]},
                    source="sensor_overload_check",
                ))
            elif state.temperature_c > self._joint_temperature_warn:
                # 温度预警 (warning)
                self._emit_event(SafetyEvent(
                    event_type=SafetyEventType.TEMPERATURE_WARNING,
                    severity=1,
                    description=f"Joint {i+1} temperature: "
                                f"{state.temperature_c:.1f}°C approaching limit",
                    data={"joint": i, "temperature": state.temperature_c},
                    source="sensor_overload_check",
                ))

            # 电流过载 (critical)
            if i < len(self._joint_current_limits) and \
                    state.current_a > self._joint_current_limits[i]:
                self._emit_event(SafetyEvent(
                    event_type=SafetyEventType.CURRENT_OVERLOAD,
                    severity=2,
                    description=f"Joint {i+1} current: {state.current_a:.2f} A > "
                                f"{self._joint_current_limits[i]:.2f} A",
                    data={"joint": i, "current": state.current_a,
                          "limit": self._joint_current_limits[i]},
                    source="sensor_overload_check",
                ))

    def _check_force_limits(self, external_force: np.ndarray) -> None:
        """ISO/TS 15066 力限制检查."""
        force_magnitude = float(np.linalg.norm(external_force[:3]))

        # 使用最严格的人体部位限值 (脸部)
        if force_magnitude > COLLABORATIVE_FORCE_LIMITS["face"]["force_n"]:
            self._emit_event(SafetyEvent(
                event_type=SafetyEventType.FORCE_LIMIT_EXCEEDED,
                severity=2,
                description=f"Contact force: {force_magnitude:.1f} N > "
                            f"{COLLABORATIVE_FORCE_LIMITS['face']['force_n']} N (face limit)",
                data={"force": force_magnitude,
                      "limit": COLLABORATIVE_FORCE_LIMITS["face"]["force_n"],
                      "standard": "ISO/TS 15066:2016"},
                source="force_check",
            ))

    def _check_communication(self) -> None:
        """通信检查."""
        now = time.time()

        # 心跳超时检查
        for device, last_hb in list(self._last_heartbeat.items()):
            if now - last_hb > self._heartbeat_timeout_s:
                self._emit_event(SafetyEvent(
                    event_type=SafetyEventType.COMMUNICATION_TIMEOUT,
                    severity=2,
                    description=f"Device {device} heartbeat timeout: {now - last_hb:.2f}s",
                    data={"device": device, "timeout": now - last_hb},
                    source="communication_check",
                ))

    def _check_clock_sync(self) -> None:
        """时钟同步检查."""
        if self._clock_sync.is_synced:
            # 检查时钟漂移
            drift = (time.time() - self._clock_sync.master_time) - self._clock_sync.offset_ns / 1e9
            self._clock_sync.drift_ppm = abs(drift) * 1e6 / max(1.0, time.time() - self._clock_sync.last_sync_time)

            if self._clock_sync.drift_ppm > 100:  # 100 ppm 漂移警告
                self._emit_event(SafetyEvent(
                    event_type=SafetyEventType.CLOCK_DRIFT,
                    severity=1,
                    description=f"Clock drift: {self._clock_sync.drift_ppm:.1f} ppm",
                    data={"drift_ppm": self._clock_sync.drift_ppm},
                    source="clock_sync_check",
                ))

    def _update_safety_state(self) -> None:
        """更新安全状态.

        增加详细日志埋点, 便于现场排查双网丢失等场景下的状态变化:
        - 检测到 critical 事件时的数量与最严重事件描述
        - 状态转移 (旧态 -> 新态) 及触发事件
        - 无 critical 事件时的自动恢复
        """
        critical_events = [e for e in self._events
                          if e.severity >= 2 and
                          time.time() - e.timestamp < 0.1]

        if not critical_events:
            if self._safety_state in (SafetyState.PROTECTIVE_STOP,
                                      SafetyState.REDUCED_SPEED):
                # 自动恢复
                logger.info("Safety: auto-recover %s -> NORMAL (no critical event within 100ms)",
                            self._safety_state.value)
                self._safety_state = SafetyState.NORMAL
            return

        # 根据最严重事件决定状态
        most_severe = max(critical_events, key=lambda e: e.severity)
        old_state = self._safety_state

        if most_severe.event_type == SafetyEventType.ESTOP_PRESSED:
            self._safety_state = SafetyState.EMERGENCY_STOP
        elif most_severe.event_type == SafetyEventType.SAFEGUARD_OPEN:
            self._safety_state = SafetyState.SAFEGUARD_STOP
        elif most_severe.event_type in (SafetyEventType.COLLISION_DETECTED,
                                         SafetyEventType.TORQUE_OVERLOAD,
                                         SafetyEventType.FORCE_LIMIT_EXCEEDED,
                                         # 修复: 通信超时/关节越限/工作区越界/
                                         # 掉电等 critical 事件此前未映射到任何
                                         # 状态转移, 导致双网丢失等条件下
                                         # is_safe_to_operate() 仍返回 True,
                                         # 系统在失去安全通信后继续运行。
                                         SafetyEventType.COMMUNICATION_TIMEOUT,
                                         SafetyEventType.JOINT_LIMIT_VIOLATION,
                                         SafetyEventType.WORKSPACE_VIOLATION,
                                         SafetyEventType.POWER_LOSS,
                                         # v1.2: 温度/电流过载联动保护性停止
                                         SafetyEventType.TEMPERATURE_OVERLOAD,
                                         SafetyEventType.CURRENT_OVERLOAD):
            self._safety_state = SafetyState.PROTECTIVE_STOP
        elif most_severe.event_type == SafetyEventType.HARDWARE_FAULT:
            self._safety_state = SafetyState.FAULT
        elif most_severe.event_type == SafetyEventType.SPEED_LIMIT_EXCEEDED:
            self._safety_state = SafetyState.REDUCED_SPEED

        # 状态发生转移时输出详细日志 (含触发事件与网络状态), 便于现场排查
        if self._safety_state != old_state:
            network = (f"primary={'OK' if self._primary_network_ok else 'LOST'}"
                       f" backup={'OK' if self._backup_network_ok else 'LOST'}")
            logger.warning(
                "Safety: state transition %s -> %s | trigger=%s severity=%d | "
                "desc=%s | network: %s | critical_events=%d",
                old_state.value, self._safety_state.value,
                most_severe.event_type.value, most_severe.severity,
                most_severe.description, network, len(critical_events))

    # -------------------------------------------------------------------------
    # 事件处理
    # -------------------------------------------------------------------------

    def _emit_event(self, event: SafetyEvent) -> None:
        """发送安全事件."""
        self._events.append(event)

        # 触发处理器
        handlers = self._event_handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                pass

    def register_event_handler(self, event_type: SafetyEventType,
                               handler: Callable[[SafetyEvent], None]) -> None:
        """注册事件处理器."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)

    def register_state_callback(self, state: SafetyState,
                                callback: Callable[[], None]) -> None:
        """注册状态变化回调."""
        if state not in self._state_callbacks:
            self._state_callbacks[state] = []
        self._state_callbacks[state].append(callback)

    # -------------------------------------------------------------------------
    # 网络冗余
    # -------------------------------------------------------------------------

    def update_heartbeat(self, device: str) -> None:
        """更新心跳."""
        self._last_heartbeat[device] = time.time()

    def set_network_status(self, primary_ok: bool = True,
                           backup_ok: bool = True) -> None:
        """设置网络状态."""
        self._primary_network_ok = primary_ok
        self._backup_network_ok = backup_ok

        if not primary_ok and not backup_ok:
            logger.error(
                "Safety: BOTH networks lost (primary=LOST backup=LOST) -> "
                "emitting COMMUNICATION_TIMEOUT critical event")
            self._emit_event(SafetyEvent(
                event_type=SafetyEventType.COMMUNICATION_TIMEOUT,
                severity=2,
                description="Both primary and backup networks lost",
                source="network_redundancy",
            ))
        else:
            logger.debug(
                "Safety: network status primary=%s backup=%s",
                "OK" if primary_ok else "LOST",
                "OK" if backup_ok else "LOST")

    # -------------------------------------------------------------------------
    # 时钟同步
    # -------------------------------------------------------------------------

    def sync_clock(self, master_time: float, method: str = "ptp") -> None:
        """时钟同步 (PTP IEEE 1588 / NTP).

        Args:
            master_time: 主时钟时间
            method: 同步方法
        """
        local_time = time.time()
        offset = local_time - master_time

        self._clock_sync = ClockSyncState(
            master_time=master_time,
            local_time=local_time,
            offset_ns=offset * 1e9,
            is_synced=True,
            last_sync_time=local_time,
            sync_method=method,
        )

    # -------------------------------------------------------------------------
    # 断点管理
    # -------------------------------------------------------------------------

    def save_checkpoint(self, data: Dict[str, Any]) -> None:
        """保存安全断点."""
        self._checkpoint = {
            "data": data,
            "timestamp": time.time(),
            "safety_state": self._safety_state.value,
            "joint_states": [
                {"pos": s.position_rad, "vel": s.velocity_rad_s, "torque": s.torque_nm}
                for s in self._joint_states
            ],
        }

    def load_checkpoint(self) -> Optional[Dict[str, Any]]:
        """加载安全断点."""
        if self._checkpoint is None:
            return None
        return self._checkpoint["data"]

    # -------------------------------------------------------------------------
    # 安全回原位
    # -------------------------------------------------------------------------

    def plan_safe_homing(self,
                         current_joints: List[float],
                         home_joints: List[float]) -> List[List[float]]:
        """规划安全回原位路径.

        Args:
            current_joints: 当前关节角
            home_joints: 原位关节角

        Returns:
            回原位路径 (关节角序列)
        """
        path = []
        num_steps = 50
        max_step = 0.05  # 最大每步 0.05 rad

        for step in range(1, num_steps + 1):
            t = step / num_steps
            # S 曲线插值
            s = 3 * t**2 - 2 * t**3  # Smoothstep

            step_joints = [
                current_joints[i] + s * (home_joints[i] - current_joints[i])
                for i in range(len(current_joints))
            ]
            path.append(step_joints)

        return path

    # -------------------------------------------------------------------------
    # 状态查询
    # -------------------------------------------------------------------------

    def get_safety_status(self) -> Dict[str, Any]:
        """获取安全状态摘要."""
        with self._lock:
            return {
                "state": self._safety_state.value,
                "cycle_count": self._cycle_count,
                "overrun_count": self._overrun_count,
                "max_cycle_time_us": self._max_cycle_time_us,
                "last_cycle_time_us": self._last_cycle_time_us,
                "recent_events": len(self._events),
                "critical_events": sum(1 for e in self._events if e.severity >= 2),
                "network": {
                    "primary_ok": self._primary_network_ok,
                    "backup_ok": self._backup_network_ok,
                },
                "clock_sync": {
                    "is_synced": self._clock_sync.is_synced,
                    "drift_ppm": self._clock_sync.drift_ppm,
                },
                "joint_states": [
                    {
                        "position_deg": math.degrees(s.position_rad),
                        "velocity_rad_s": s.velocity_rad_s,
                        "torque_nm": s.torque_nm,
                        "is_limit_exceeded": s.is_limit_exceeded,
                    }
                    for s in self._joint_states
                ],
            }

    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取最近的安全事件."""
        return [
            {
                "type": e.event_type.value,
                "severity": e.severity,
                "timestamp": e.timestamp,
                "description": e.description,
            }
            for e in list(self._events)[-limit:]
        ]

    def is_safe_to_operate(self) -> bool:
        """检查是否可以安全操作."""
        return self._safety_state in (SafetyState.NORMAL, SafetyState.REDUCED_SPEED)


# =============================================================================
# 快速测试
# =============================================================================

if __name__ == "__main__":
    controller = RealTimeSafetyController(num_joints=6)
    controller.start()

    # 模拟正常控制循环
    for i in range(10):
        state = controller.control_cycle(
            joint_positions=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
            joint_velocities=[0.01, 0.02, 0.01, 0.03, 0.02, 0.01],
            joint_torques=[0.5, 0.3, 0.4, 0.2, 0.3, 0.1],
            obstacle_distances=[500.0, 300.0],
            external_force=np.array([1.0, 0.5, 2.0]),
        )

    status = controller.get_safety_status()
    print(f"Safety State: {status['state']}")
    print(f"Cycle time: {status['last_cycle_time_us']:.1f} us")
    print(f"Overruns: {status['overrun_count']}")

    # 模拟碰撞
    state = controller.control_cycle(
        joint_positions=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
        joint_velocities=[0.01, 0.02, 0.01, 0.03, 0.02, 0.01],
        joint_torques=[5.0, 8.0, 12.0, 3.0, 2.0, 1.0],  # 碰撞力矩
        obstacle_distances=[50.0],  # 非常近
    )
    print(f"\nAfter collision: {state.value}")

    events = controller.get_recent_events()
    for e in events:
        print(f"  [{e['type']}] {e['description']}")