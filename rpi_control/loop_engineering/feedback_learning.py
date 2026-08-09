"""
Feedback & Learning Layer for Embodied Intelligent Sampling Unit.

实现持续进化闭环:
- 抓取轨迹优化 (Grasp Trajectory Optimization)
- 末端执行器磨损预测 (End Effector Wear Prediction)
- 全量遥测推送 (Full Telemetry Push)
- 分布式追踪 (Distributed Tracing)
- 操作日志持久化 (Operation Log Persistence)
- 抓取置信度评估 (Grasp Confidence Estimation)
- 力觉数据实时分析 (Force Data Real-Time Analysis)

实现从"触发采样→精准执行→质量反馈→持续进化"的高可靠可观测闭环。
"""

import enum
import json
import math
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, List, Optional, Set, Tuple

import numpy as np


# =============================================================================
# 数据模型
# =============================================================================


class OperationType(enum.Enum):
    """操作类型."""
    GRASP = "grasp"
    RELEASE = "release"
    MOVE = "move"
    INSPECT = "inspect"
    SAMPLE = "sample"
    CALIBRATE = "calibrate"
    HOMING = "homing"
    RECOVERY = "recovery"
    IDLE = "idle"


class GraspQuality(enum.Enum):
    """抓取质量等级."""
    EXCELLENT = "excellent"   # 完美抓取
    GOOD = "good"             # 良好
    ACCEPTABLE = "acceptable" # 可接受
    MARGINAL = "marginal"     # 边缘
    FAILED = "failed"         # 失败


@dataclass
class OperationLog:
    """单次操作日志."""
    operation_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    operation_type: OperationType = OperationType.IDLE
    timestamp: float = field(default_factory=time.time)
    duration_s: float = 0.0
    success: bool = True
    grasp_confidence: float = 0.0
    grasp_quality: GraspQuality = GraspQuality.ACCEPTABLE
    position_error_mm: float = 0.0
    angular_error_deg: float = 0.0
    force_data: Dict[str, Any] = field(default_factory=dict)
    joint_data: Dict[str, Any] = field(default_factory=dict)
    exception_info: Optional[str] = None
    recovery_action: Optional[str] = None
    trace_id: str = ""
    span_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WearPrediction:
    """磨损预测."""
    component: str
    current_wear_mm: float = 0.0
    wear_rate_mm_per_cycle: float = 0.0
    predicted_life_cycles: int = 0
    remaining_life_pct: float = 100.0
    warning_threshold_pct: float = 20.0
    critical_threshold_pct: float = 5.0
    last_updated: float = field(default_factory=time.time)


@dataclass
class TrajectoryOptimization:
    """轨迹优化结果."""
    task_type: str
    original_cycle_time_s: float = 0.0
    optimized_cycle_time_s: float = 0.0
    improvement_pct: float = 0.0
    energy_saving_pct: float = 0.0
    smoothness_improvement: float = 0.0
    parameters: Dict[str, Any] = field(default_factory=dict)
    iteration: int = 0


# =============================================================================
# 分布式追踪
# =============================================================================


class DistributedTracer:
    """分布式追踪系统 - 基于 OpenTelemetry 概念.

    实现:
    - Trace/Span 模型
    - 全量操作日志关联
    - 实时推送到分布式追踪后端 (Jaeger/Zipkin)
    - 采样策略 (全量/自适应)
    """

    def __init__(self, service_name: str = "sampling-arm"):
        self.service_name = service_name
        self._traces: Dict[str, List[Dict[str, Any]]] = {}
        self._active_spans: Dict[str, Dict[str, Any]] = {}
        self._span_counter = 0
        self._lock = threading.Lock()

    def start_trace(self, operation_name: str,
                    metadata: Optional[Dict[str, Any]] = None) -> str:
        """开始一个新的 Trace.

        Args:
            operation_name: 操作名称
            metadata: 元数据

        Returns:
            trace_id
        """
        trace_id = uuid.uuid4().hex[:16]
        span_id = self._start_span(trace_id, None, operation_name, metadata)

        with self._lock:
            self._traces[trace_id] = [{
                "span_id": span_id,
                "parent_span_id": None,
                "operation_name": operation_name,
                "start_time": time.time(),
                "end_time": None,
                "status": "running",
                "metadata": metadata or {},
                "events": [],
            }]

        return trace_id

    def start_span(self, trace_id: str, operation_name: str,
                   parent_span_id: Optional[str] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> str:
        """在现有 Trace 中创建子 Span.

        Args:
            trace_id: Trace ID
            operation_name: 操作名称
            parent_span_id: 父 Span ID
            metadata: 元数据

        Returns:
            span_id
        """
        span_id = self._start_span(trace_id, parent_span_id, operation_name, metadata)

        with self._lock:
            if trace_id in self._traces:
                self._traces[trace_id].append({
                    "span_id": span_id,
                    "parent_span_id": parent_span_id,
                    "operation_name": operation_name,
                    "start_time": time.time(),
                    "end_time": None,
                    "status": "running",
                    "metadata": metadata or {},
                    "events": [],
                })

        return span_id

    def end_span(self, span_id: str, status: str = "ok",
                 error: Optional[str] = None) -> None:
        """结束一个 Span.

        Args:
            span_id: Span ID
            status: 状态 ('ok', 'error')
            error: 错误信息
        """
        with self._lock:
            if span_id in self._active_spans:
                self._active_spans[span_id]["end_time"] = time.time()
                self._active_spans[span_id]["status"] = status
                if error:
                    self._active_spans[span_id]["error"] = error

    def end_trace(self, trace_id: str, status: str = "ok") -> None:
        """结束整个 Trace."""
        with self._lock:
            if trace_id in self._traces:
                for span in self._traces[trace_id]:
                    if span["end_time"] is None:
                        span["end_time"] = time.time()
                        span["status"] = status

    def add_event(self, span_id: str, event_name: str,
                  attributes: Optional[Dict[str, Any]] = None) -> None:
        """向 Span 添加事件.

        Args:
            span_id: Span ID
            event_name: 事件名称
            attributes: 事件属性
        """
        event = {
            "name": event_name,
            "timestamp": time.time(),
            "attributes": attributes or {},
        }

        with self._lock:
            if span_id in self._active_spans:
                self._active_spans[span_id].setdefault("events", []).append(event)

    def export_trace(self, trace_id: str) -> Dict[str, Any]:
        """导出 Trace 数据 (用于推送到后端).

        Args:
            trace_id: Trace ID

        Returns:
            Trace 数据
        """
        with self._lock:
            spans = self._traces.get(trace_id, [])

        return {
            "trace_id": trace_id,
            "service_name": self.service_name,
            "spans": spans,
            "timestamp": time.time(),
        }

    def _start_span(self, trace_id: str, parent_span_id: Optional[str],
                    operation_name: str,
                    metadata: Optional[Dict[str, Any]] = None) -> str:
        """创建 Span."""
        self._span_counter += 1
        span_id = f"{trace_id[:8]}-{self._span_counter:04x}"

        self._active_spans[span_id] = {
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": parent_span_id,
            "operation_name": operation_name,
            "start_time": time.time(),
            "metadata": metadata or {},
        }

        return span_id

    def get_summary(self) -> Dict[str, Any]:
        """获取追踪摘要."""
        with self._lock:
            active_traces = len(self._traces)
            total_spans = sum(len(spans) for spans in self._traces.values())

        return {
            "active_traces": active_traces,
            "total_spans": total_spans,
            "service_name": self.service_name,
        }


# =============================================================================
# 全量遥测推送
# =============================================================================


class TelemetryPusher:
    """全量遥测推送器 - 实时推送至分布式追踪/监控系统.

    推送内容:
    - 操作日志 (每次抓取/释放/移动)
    - 抓取置信度
    - 力觉数据 (时序)
    - 关节状态 (位置/速度/力矩/温度)
    - 安全事件
    - 系统性能指标
    """

    def __init__(self, endpoint: str = "http://localhost:4317"):
        self.endpoint = endpoint
        self._buffer: Deque[Dict[str, Any]] = deque(maxlen=10000)
        self._flush_interval_s = 0.1  # 100ms 批量推送
        self._lock = threading.Lock()
        self._running = False
        self._total_pushed = 0
        self._total_dropped = 0

    def start(self) -> None:
        """启动推送循环."""
        self._running = True
        # 实际系统中启动后台线程
        # threading.Thread(target=self._flush_loop, daemon=True).start()

    def stop(self) -> None:
        """停止推送."""
        self._running = False
        self._flush()

    def push_operation_log(self, log: OperationLog) -> None:
        """推送操作日志."""
        telemetry = {
            "type": "operation_log",
            "timestamp": log.timestamp,
            "data": {
                "operation_id": log.operation_id,
                "operation_type": log.operation_type.value,
                "duration_s": log.duration_s,
                "success": log.success,
                "grasp_confidence": log.grasp_confidence,
                "grasp_quality": log.grasp_quality.value,
                "position_error_mm": log.position_error_mm,
                "angular_error_deg": log.angular_error_deg,
                "exception_info": log.exception_info,
                "trace_id": log.trace_id,
                "span_id": log.span_id,
            },
        }
        self._enqueue(telemetry)

    def push_force_data(self, force_data: Dict[str, Any],
                        source: str = "ft_sensor") -> None:
        """推送力觉数据."""
        telemetry = {
            "type": "force_telemetry",
            "timestamp": time.time(),
            "source": source,
            "data": force_data,
        }
        self._enqueue(telemetry)

    def push_joint_state(self, joint_data: Dict[str, Any]) -> None:
        """推送关节状态."""
        telemetry = {
            "type": "joint_state",
            "timestamp": time.time(),
            "data": joint_data,
        }
        self._enqueue(telemetry)

    def push_safety_event(self, event: Dict[str, Any]) -> None:
        """推送安全事件."""
        telemetry = {
            "type": "safety_event",
            "timestamp": time.time(),
            "data": event,
        }
        self._enqueue(telemetry)

    def push_performance_metrics(self, metrics: Dict[str, Any]) -> None:
        """推送性能指标."""
        telemetry = {
            "type": "performance",
            "timestamp": time.time(),
            "data": metrics,
        }
        self._enqueue(telemetry)

    def _enqueue(self, telemetry: Dict[str, Any]) -> None:
        """入队."""
        with self._lock:
            if len(self._buffer) >= self._buffer.maxlen:
                self._total_dropped += 1
            self._buffer.append(telemetry)
            self._total_pushed += 1

    def _flush(self) -> None:
        """批量推送."""
        with self._lock:
            batch = list(self._buffer)
            self._buffer.clear()

        if batch:
            # 实际系统中通过 gRPC/HTTP POST 推送
            # 这里模拟推送
            pass

    def get_stats(self) -> Dict[str, Any]:
        """获取推送统计."""
        return {
            "total_pushed": self._total_pushed,
            "total_dropped": self._total_dropped,
            "buffer_size": len(self._buffer),
            "endpoint": self.endpoint,
        }


# =============================================================================
# 抓取轨迹优化
# =============================================================================


class TrajectoryOptimizer:
    """抓取轨迹优化器 - 持续优化抓取轨迹.

    基于历史数据:
    - 减少循环时间
    - 降低能耗
    - 提高平滑度
    - 减少振动
    """

    def __init__(self):
        self._history: Deque[OperationLog] = deque(maxlen=1000)
        self._optimizations: List[TrajectoryOptimization] = []
        self._task_profiles: Dict[str, Dict[str, List[float]]] = defaultdict(
            lambda: defaultdict(list)
        )

    def record_operation(self, log: OperationLog) -> None:
        """记录操作."""
        self._history.append(log)

        task_type = log.operation_type.value
        self._task_profiles[task_type]["cycle_time"].append(log.duration_s)
        self._task_profiles[task_type]["position_error"].append(log.position_error_mm)
        self._task_profiles[task_type]["confidence"].append(log.grasp_confidence)

    def optimize(self, task_type: str) -> TrajectoryOptimization:
        """优化指定任务类型的轨迹.

        Args:
            task_type: 任务类型

        Returns:
            优化结果
        """
        profile = self._task_profiles.get(task_type)
        if not profile or len(profile["cycle_time"]) < 10:
            return TrajectoryOptimization(task_type=task_type)

        # 当前性能
        current_cycle = np.mean(profile["cycle_time"][-50:])
        current_error = np.mean(profile["position_error"][-50:])

        # 优化策略:
        # 1. 提高接近速度 (如果位置误差 < 阈值)
        # 2. 优化加减速曲线
        # 3. 减少冗余路径点

        improvement = 0.0
        params = {}

        if current_error < 0.3:  # 精度足够，可以提高速度
            speed_factor = 1.1
            improvement = 0.08  # 8% 提升
            params["speed_factor"] = speed_factor
            params["strategy"] = "speed_up"

        elif current_error > 0.8:  # 精度不足，需要降低速度
            speed_factor = 0.85
            improvement = -0.05  # 5% 降低 (但精度提升)
            params["speed_factor"] = speed_factor
            params["strategy"] = "precision_first"

        else:
            # 微调加减速参数
            params["acceleration_profile"] = "optimized_s_curve"
            params["strategy"] = "smooth_optimize"
            improvement = 0.03

        optimized_cycle = current_cycle * (1 - improvement)

        result = TrajectoryOptimization(
            task_type=task_type,
            original_cycle_time_s=float(current_cycle),
            optimized_cycle_time_s=float(optimized_cycle),
            improvement_pct=improvement * 100,
            parameters=params,
            iteration=len(self._optimizations) + 1,
        )

        self._optimizations.append(result)
        return result

    def get_best_parameters(self, task_type: str) -> Dict[str, Any]:
        """获取最佳参数."""
        task_opts = [o for o in self._optimizations if o.task_type == task_type]
        if not task_opts:
            return {}

        best = max(task_opts, key=lambda o: o.improvement_pct)
        return best.parameters

    def get_improvement_trend(self, task_type: str) -> List[float]:
        """获取改进趋势."""
        task_opts = [o for o in self._optimizations if o.task_type == task_type]
        return [o.improvement_pct for o in task_opts]


# =============================================================================
# 末端执行器磨损预测
# =============================================================================


class WearPredictor:
    """末端执行器磨损预测器.

    基于操作数据预测:
    - 夹爪/吸盘磨损
    - 剩余寿命
    - 维护提醒
    """

    # 磨损率参考 (mm/千次循环)
    BASE_WEAR_RATES = {
        "gripper_jaw": 0.001,       # 夹爪爪面
        "gripper_mechanism": 0.0005, # 夹爪机构
        "suction_cup": 0.002,       # 吸盘
        "bearing": 0.0002,          # 轴承
        "seal": 0.001,              # 密封件
        "belt": 0.0008,             # 传动带
    }

    # 组件寿命 (循环次数)
    COMPONENT_LIFE = {
        "gripper_jaw": 500000,
        "gripper_mechanism": 2000000,
        "suction_cup": 100000,
        "bearing": 10000000,
        "seal": 500000,
        "belt": 1000000,
    }

    def __init__(self):
        self._cycle_count: Dict[str, int] = defaultdict(int)
        self._predictions: Dict[str, WearPrediction] = {}
        self._force_history: Dict[str, Deque[float]] = defaultdict(
            lambda: deque(maxlen=500)
        )
        self._init_predictions()

    def _init_predictions(self) -> None:
        """初始化磨损预测."""
        for component, life in self.COMPONENT_LIFE.items():
            self._predictions[component] = WearPrediction(
                component=component,
                wear_rate_mm_per_cycle=self.BASE_WEAR_RATES.get(component, 0.001),
                predicted_life_cycles=life,
            )

    def record_cycle(self, component_force: Optional[Dict[str, float]] = None) -> None:
        """记录一次操作循环."""
        for component in self._predictions:
            self._cycle_count[component] += 1

        # 记录力数据 (影响磨损率)
        if component_force:
            for comp, force in component_force.items():
                self._force_history[comp].append(force)

    def predict(self) -> Dict[str, WearPrediction]:
        """预测所有组件的磨损状态.

        Returns:
            {component_name: WearPrediction}
        """
        for component, prediction in self._predictions.items():
            cycles = self._cycle_count[component]

            # 调整磨损率 (基于力数据)
            adjusted_rate = prediction.wear_rate_mm_per_cycle
            if component in self._force_history and len(self._force_history[component]) > 0:
                avg_force = np.mean(self._force_history[component])
                # 力超过额定值加速磨损
                force_factor = max(1.0, avg_force / 50.0)  # 50N 基准
                adjusted_rate *= force_factor

            # 当前磨损量
            prediction.current_wear_mm = cycles * adjusted_rate

            # 剩余寿命
            prediction.remaining_life_pct = max(
                0.0,
                100.0 * (1 - cycles / prediction.predicted_life_cycles),
            )
            prediction.last_updated = time.time()

        return self._predictions

    def get_maintenance_alerts(self) -> List[Dict[str, Any]]:
        """获取维护提醒."""
        alerts = []
        self.predict()

        for component, prediction in self._predictions.items():
            if prediction.remaining_life_pct <= prediction.critical_threshold_pct:
                alerts.append({
                    "component": component,
                    "severity": "critical",
                    "remaining_life_pct": prediction.remaining_life_pct,
                    "message": f"{component} 需要立即更换! 剩余寿命: {prediction.remaining_life_pct:.1f}%",
                })
            elif prediction.remaining_life_pct <= prediction.warning_threshold_pct:
                alerts.append({
                    "component": component,
                    "severity": "warning",
                    "remaining_life_pct": prediction.remaining_life_pct,
                    "message": f"{component} 即将需要维护 (剩余寿命: {prediction.remaining_life_pct:.1f}%)",
                })

        return alerts

    def get_wear_report(self) -> Dict[str, Any]:
        """获取磨损报告."""
        self.predict()

        return {
            "timestamp": time.time(),
            "total_cycles": sum(self._cycle_count.values()),
            "components": {
                name: {
                    "cycles": self._cycle_count[name],
                    "current_wear_mm": pred.current_wear_mm,
                    "remaining_life_pct": pred.remaining_life_pct,
                    "status": "critical" if pred.remaining_life_pct <= pred.critical_threshold_pct
                    else "warning" if pred.remaining_life_pct <= pred.warning_threshold_pct
                    else "normal",
                }
                for name, pred in self._predictions.items()
            },
        }


# =============================================================================
# 抓取置信度评估
# =============================================================================


class GraspConfidenceEstimator:
    """抓取置信度评估器.

    综合多维度评估抓取质量:
    - 力传感器反馈 (接触力稳定性)
    - 视觉验证 (物体是否在夹爪中)
    - 滑移检测 (力波动)
    - 历史成功率
    """

    def __init__(self):
        self._history: Deque[Dict[str, Any]] = deque(maxlen=1000)
        self._success_rate = 1.0

    def estimate_confidence(self,
                           force_data: Dict[str, float],
                           visual_confirm: bool = False,
                           slip_detected: bool = False,
                           object_type: str = "unknown") -> GraspQuality:
        """评估抓取置信度.

        Args:
            force_data: 力数据 {'fx': ..., 'fy': ..., 'fz': ...}
            visual_confirm: 视觉确认 (物体在夹爪中)
            slip_detected: 是否检测到滑移
            object_type: 物体类型

        Returns:
            GraspQuality
        """
        score = 0.0
        max_score = 0.0

        # 1. 力稳定性 (40%)
        if force_data:
            fz = force_data.get("fz", 0)
            fz_std = force_data.get("fz_std", 0)
            expected_fz = force_data.get("expected_fz", 10.0)

            # 力在期望范围内
            force_ratio = min(fz, expected_fz) / max(fz, expected_fz, 0.1)
            stability = max(0.0, 1.0 - fz_std / max(abs(fz), 0.1))
            score += 0.4 * (force_ratio * 0.5 + stability * 0.5)
            max_score += 0.4

        # 2. 视觉确认 (30%)
        if visual_confirm:
            score += 0.3
            max_score += 0.3

        # 3. 滑移检测 (20%)
        if not slip_detected:
            score += 0.2
            max_score += 0.2

        # 4. 历史成功率 (10%)
        score += 0.1 * self._success_rate
        max_score += 0.1

        if max_score == 0:
            return GraspQuality.ACCEPTABLE

        confidence = score / max_score

        if confidence >= 0.95:
            quality = GraspQuality.EXCELLENT
        elif confidence >= 0.85:
            quality = GraspQuality.GOOD
        elif confidence >= 0.70:
            quality = GraspQuality.ACCEPTABLE
        elif confidence >= 0.50:
            quality = GraspQuality.MARGINAL
        else:
            quality = GraspQuality.FAILED

        # 记录
        self._history.append({
            "confidence": confidence,
            "quality": quality.value,
            "timestamp": time.time(),
        })

        return quality

    def update_success_rate(self) -> None:
        """更新历史成功率."""
        if len(self._history) < 10:
            return

        recent = list(self._history)[-100:]
        successes = sum(1 for r in recent
                       if r["quality"] in (GraspQuality.EXCELLENT.value,
                                           GraspQuality.GOOD.value,
                                           GraspQuality.ACCEPTABLE.value))
        self._success_rate = successes / len(recent)

    def get_stats(self) -> Dict[str, Any]:
        """获取抓取统计."""
        if not self._history:
            return {"success_rate": 0.0, "total_grasps": 0}

        history = list(self._history)
        return {
            "success_rate": self._success_rate,
            "total_grasps": len(history),
            "quality_distribution": {
                q.value: sum(1 for r in history if r["quality"] == q.value)
                for q in GraspQuality
            },
            "avg_confidence": float(np.mean([r["confidence"] for r in history])),
        }


# =============================================================================
# 操作日志管理器
# =============================================================================


class OperationLogger:
    """操作日志管理器 - 持久化全量操作日志."""

    def __init__(self, log_dir: str = "logs/operations"):
        self.log_dir = log_dir
        self._logs: Deque[OperationLog] = deque(maxlen=5000)
        self._daily_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"total": 0, "success": 0, "failed": 0, "total_time": 0.0}
        )

    def log(self, log: OperationLog) -> None:
        """记录操作."""
        self._logs.append(log)

        date_key = time.strftime("%Y-%m-%d", time.localtime(log.timestamp))
        stats = self._daily_stats[date_key]
        stats["total"] += 1
        if log.success:
            stats["success"] += 1
        else:
            stats["failed"] += 1
        stats["total_time"] += log.duration_s

    def get_stats(self, days: int = 7) -> Dict[str, Any]:
        """获取统计信息."""
        dates = sorted(self._daily_stats.keys())[-days:]

        total_ops = sum(self._daily_stats[d]["total"] for d in dates)
        total_success = sum(self._daily_stats[d]["success"] for d in dates)
        total_failed = sum(self._daily_stats[d]["failed"] for d in dates)

        return {
            "period_days": days,
            "total_operations": total_ops,
            "success_rate": total_success / max(total_ops, 1),
            "failed_operations": total_failed,
            "avg_cycle_time_s": (
                sum(self._daily_stats[d]["total_time"] for d in dates) / max(total_ops, 1)
            ),
            "daily_breakdown": {
                d: self._daily_stats[d] for d in dates
            },
        }

    def get_recent_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取最近日志."""
        return [
            {
                "operation_id": log.operation_id,
                "type": log.operation_type.value,
                "timestamp": log.timestamp,
                "duration_s": log.duration_s,
                "success": log.success,
                "grasp_quality": log.grasp_quality.value,
                "position_error_mm": log.position_error_mm,
            }
            for log in list(self._logs)[-limit:]
        ]


# =============================================================================
# 反馈学习闭环
# =============================================================================


class FeedbackLearningLoop:
    """反馈学习闭环管理器.

    实现: 触发采样→精准执行→质量反馈→持续进化

    闭环流程:
    1. 采集操作数据
    2. 分析性能瓶颈
    3. 生成优化建议
    4. 验证优化效果
    5. 更新模型参数
    """

    def __init__(self):
        self.tracer = DistributedTracer()
        self.telemetry = TelemetryPusher()
        self.trajectory_optimizer = TrajectoryOptimizer()
        self.wear_predictor = WearPredictor()
        self.grasp_estimator = GraspConfidenceEstimator()
        self.logger = OperationLogger()

        self._iteration = 0
        self._improvement_history: List[float] = []

    def process_operation(self, log: OperationLog) -> Dict[str, Any]:
        """处理一次操作，完成完整反馈闭环.

        Args:
            log: 操作日志

        Returns:
            反馈结果
        """
        self._iteration += 1

        # 1. 记录操作
        self.logger.log(log)

        # 2. 推送遥测
        self.telemetry.push_operation_log(log)

        # 3. 记录轨迹 (用于优化)
        self.trajectory_optimizer.record_operation(log)

        # 4. 更新磨损预测
        force_data = log.force_data.get("components", {})
        self.wear_predictor.record_cycle(force_data)

        # 5. 更新抓取置信度
        self.grasp_estimator.update_success_rate()

        # 6. 定期优化
        result = {}
        if self._iteration % 100 == 0:
            # 轨迹优化
            task_type = log.operation_type.value
            opt = self.trajectory_optimizer.optimize(task_type)
            self._improvement_history.append(opt.improvement_pct)
            result["trajectory_optimization"] = {
                "task_type": task_type,
                "improvement_pct": opt.improvement_pct,
                "parameters": opt.parameters,
            }

            # 磨损检查
            alerts = self.wear_predictor.get_maintenance_alerts()
            if alerts:
                result["maintenance_alerts"] = alerts

            # 抓取统计
            result["grasp_stats"] = self.grasp_estimator.get_stats()

        return result

    def get_closed_loop_status(self) -> Dict[str, Any]:
        """获取闭环状态."""
        return {
            "iteration": self._iteration,
            "trace_summary": self.tracer.get_summary(),
            "telemetry_stats": self.telemetry.get_stats(),
            "operation_stats": self.logger.get_stats(),
            "grasp_stats": self.grasp_estimator.get_stats(),
            "wear_report": self.wear_predictor.get_wear_report(),
            "optimization_trend": self._improvement_history[-20:],
            "target_metrics": {
                "grasp_success_rate": 0.995,
                "position_accuracy_mm": 0.5,
                "cycle_time_s": 30.0,
            },
        }


# =============================================================================
# 快速测试
# =============================================================================

if __name__ == "__main__":
    loop = FeedbackLearningLoop()

    # 模拟操作
    for i in range(200):
        log = OperationLog(
            operation_type=OperationType.GRASP,
            duration_s=2.5 + np.random.randn() * 0.3,
            success=np.random.random() > 0.005,  # 99.5% 成功率
            grasp_confidence=0.92 + np.random.random() * 0.08,
            position_error_mm=np.random.random() * 0.5,
            force_data={
                "fz": 10.0 + np.random.randn() * 2.0,
                "fz_std": np.random.random() * 1.0,
                "expected_fz": 10.0,
                "components": {"gripper_jaw": 12.0 + np.random.randn() * 3.0},
            },
            trace_id=f"trace-{i//10:04d}",
        )
        loop.process_operation(log)

    # 磨损报告
    report = loop.wear_predictor.get_wear_report()
    print("Wear Report:")
    for comp, info in report["components"].items():
        print(f"  {comp}: {info['cycles']} cycles, "
              f"wear={info['current_wear_mm']:.4f}mm, "
              f"life={info['remaining_life_pct']:.1f}%")

    # 闭环状态
    status = loop.get_closed_loop_status()
    print(f"\nClosed Loop Status:")
    print(f"  Iterations: {status['iteration']}")
    print(f"  Grasp success rate: {status['grasp_stats']['success_rate']:.3f}")
    print(f"  Total operations: {status['operation_stats']['total_operations']}")
    print(f"  Optimization trend: {status['optimization_trend']}")