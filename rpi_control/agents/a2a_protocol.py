"""
A2A (Agent-to-Agent) Protocol for Multi-Agent Collaborative System.

实现机械臂Agent与其它业务Agent间的标准化通信协议，包括:
- 任务合约 (Task Contract) 定义与验证
- 异常边界 (Exception Boundary) 处理
- 确定性接口 (Deterministic Interface) 抽象
- 动作调度层 (Action Dispatch Layer) 的实时任务转化
- MES (Manufacturing Execution System) 调度指令集成

协议设计原则:
1. 确定性: 相同输入 → 相同输出，无副作用
2. 可观测: 全量操作日志与状态遥测
3. 可恢复: 任务中断后安全回原位与断点续推
4. 合约化: 每个任务有明确的输入/输出/异常契约

参考:
- Google A2A Protocol: https://github.com/google/A2A
- ROS 2 Action Interface
- OPC UA 统一架构
"""

import enum
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import numpy as np


# =============================================================================
# 枚举定义
# =============================================================================


class TaskPriority(enum.IntEnum):
    """任务优先级."""
    CRITICAL = 0   # 紧急停止、安全响应
    HIGH = 1       # 生产任务
    NORMAL = 2     # 常规采样
    LOW = 3        # 后台优化、标定
    IDLE = 4       # 空闲


class TaskState(enum.Enum):
    """任务状态机."""
    PENDING = "pending"           # 等待调度
    ACCEPTED = "accepted"         # 已接受
    PLANNING = "planning"         # 规划中
    EXECUTING = "executing"       # 执行中
    PAUSED = "paused"             # 暂停
    RECOVERING = "recovering"     # 恢复中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败
    ABORTED = "aborted"           # 中止
    INTERRUPTED = "interrupted"   # 中断 (可恢复)


class ExceptionType(enum.Enum):
    """异常类型."""
    VISION_FAILURE = "vision_failure"           # 视觉检测失败
    POSE_UNCERTAINTY = "pose_uncertainty"       # 位姿不确定
    GRASP_FAILURE = "grasp_failure"             # 抓取失败
    COLLISION_RISK = "collision_risk"           # 碰撞风险
    JOINT_LIMIT = "joint_limit"                 # 关节限位
    FORCE_OVERLOAD = "force_overload"           # 力超载
    COMMUNICATION_LOSS = "communication_loss"   # 通信丢失
    HARDWARE_FAULT = "hardware_fault"           # 硬件故障
    TIMEOUT = "timeout"                         # 超时
    MATERIAL_ANOMALY = "material_anomaly"       # 来料异常
    UNKNOWN = "unknown"                         # 未知异常


class RecoveryAction(enum.Enum):
    """恢复动作."""
    RETRY = "retry"                       # 重试当前操作
    VISUAL_REINSPECT = "visual_reinspect" # 视觉重检
    POSE_ADJUST = "pose_adjust"           # 位姿调整
    RETRACT_SAFE = "retract_safe"         # 回安全位
    REQUEST_HUMAN = "request_human"       # 请求人工干预
    SWITCH_STRATEGY = "switch_strategy"   # 切换采样策略
    SKIP_SAMPLE = "skip_sample"           # 跳过当前样本
    EMERGENCY_STOP = "emergency_stop"     # 紧急停止
    RESUME_FROM_CHECKPOINT = "resume"     # 从断点恢复


# =============================================================================
# 数据模型
# =============================================================================


@dataclass
class TaskContract:
    """任务合约 - 定义任务输入/输出/异常边界.

    每个合约是 Agent 之间的确定性接口，明确:
    - 输入参数与约束
    - 预期输出与质量指标
    - 异常边界与恢复策略
    - 超时与重试策略
    """
    contract_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    task_type: str = ""  # 'pick_place', 'inspect', 'sample', 'calibrate'
    source_agent: str = ""  # 发起 Agent
    target_agent: str = ""  # 执行 Agent
    priority: TaskPriority = TaskPriority.NORMAL

    # 输入约束
    input_schema: Dict[str, Any] = field(default_factory=dict)
    required_fields: List[str] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)

    # 输出期望
    expected_output: Dict[str, Any] = field(default_factory=dict)
    quality_metrics: Dict[str, float] = field(default_factory=dict)  # 如 {'grasp_success_rate': 0.995}

    # 异常边界
    exception_handlers: Dict[ExceptionType, List[RecoveryAction]] = field(default_factory=dict)
    max_retries: int = 3
    retry_delay_s: float = 1.0

    # 超时
    timeout_s: float = 30.0
    deadline_s: float = 0.0  # 绝对截止时间 (0 = 无截止)

    # 可中断性
    is_interruptible: bool = True
    checkpoint_interval_s: float = 5.0  # 断点保存间隔

    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskExecution:
    """任务执行实例."""
    execution_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    contract: TaskContract = field(default_factory=TaskContract)
    state: TaskState = TaskState.PENDING
    progress: float = 0.0  # 0.0 - 1.0
    retry_count: int = 0
    exception_history: List[Tuple[ExceptionType, float, str]] = field(default_factory=list)
    checkpoint_data: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    started_at: float = 0.0
    completed_at: float = 0.0
    last_updated: float = field(default_factory=time.time)


@dataclass
class A2AMessage:
    """A2A 协议消息."""
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    sender: str = ""
    receiver: str = ""
    message_type: str = ""  # 'task_request', 'task_response', 'status_update', 'exception', 'heartbeat'
    contract_id: Optional[str] = None
    execution_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    correlation_id: Optional[str] = None  # 用于请求-响应关联
    ttl_s: float = 60.0  # 消息存活时间


@dataclass
class MESInstruction:
    """MES (制造执行系统) 调度指令."""
    instruction_id: str = ""
    work_order_id: str = ""
    product_type: str = ""
    sampling_strategy: str = "grid"  # 'grid', 'adaptive', 'targeted', 'random'
    sample_count: int = 1
    target_locations: List[Dict[str, float]] = field(default_factory=list)
    quality_requirements: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    deadline: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# A2A 协议栈
# =============================================================================


class A2AProtocol:
    """Agent-to-Agent 通信协议栈.

    提供:
    - 确定性消息路由
    - 请求-响应关联
    - 消息持久化与重放
    - 心跳检测
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self._message_handlers: Dict[str, Callable] = {}
        self._pending_responses: Dict[str, A2AMessage] = {}
        self._message_history: List[A2AMessage] = []
        self._max_history = 1000
        self._sequence_number = 0

    def register_handler(self, message_type: str,
                         handler: Callable[[A2AMessage], Optional[A2AMessage]]) -> None:
        """注册消息处理器."""
        self._message_handlers[message_type] = handler

    def send_request(self, receiver: str, message_type: str,
                     payload: Dict[str, Any],
                     timeout_s: float = 30.0) -> A2AMessage:
        """发送请求并等待响应.

        Args:
            receiver: 接收方 Agent ID
            message_type: 消息类型
            payload: 消息载荷
            timeout_s: 超时时间

        Returns:
            响应消息
        """
        msg = A2AMessage(
            sender=self.agent_id,
            receiver=receiver,
            message_type=message_type,
            payload=payload,
            ttl_s=timeout_s,
        )

        self._message_history.append(msg)
        self._pending_responses[msg.message_id] = msg

        # 模拟同步等待 (实际系统中使用异步回调)
        return self._wait_for_response(msg.message_id, timeout_s)

    def send_async(self, receiver: str, message_type: str,
                   payload: Dict[str, Any]) -> str:
        """异步发送消息.

        Returns:
            message_id
        """
        msg = A2AMessage(
            sender=self.agent_id,
            receiver=receiver,
            message_type=message_type,
            payload=payload,
        )
        self._message_history.append(msg)
        return msg.message_id

    def receive_message(self, message: A2AMessage) -> Optional[A2AMessage]:
        """接收并处理消息."""
        # 检查是否是响应
        if message.correlation_id and message.correlation_id in self._pending_responses:
            self._pending_responses[message.correlation_id] = message
            return None

        # 路由到处理器
        handler = self._message_handlers.get(message.message_type)
        if handler:
            return handler(message)

        return None

    def send_heartbeat(self, receiver: str) -> None:
        """发送心跳."""
        self.send_async(receiver, "heartbeat", {
            "agent_id": self.agent_id,
            "timestamp": time.time(),
            "status": "alive",
        })

    def _wait_for_response(self, message_id: str,
                           timeout_s: float) -> A2AMessage:
        """等待响应 (模拟)."""
        start = time.time()
        while time.time() - start < timeout_s:
            if message_id in self._pending_responses:
                resp = self._pending_responses.pop(message_id)
                if resp.message_type != "task_request":
                    return resp
            time.sleep(0.01)

        # 超时
        return A2AMessage(
            sender="system",
            receiver=self.agent_id,
            message_type="error",
            payload={"error": "timeout", "message_id": message_id},
        )

    def get_message_history(self,
                            message_type: Optional[str] = None,
                            sender: Optional[str] = None,
                            limit: int = 100) -> List[A2AMessage]:
        """查询消息历史."""
        history = self._message_history
        if message_type:
            history = [m for m in history if m.message_type == message_type]
        if sender:
            history = [m for m in history if m.sender == sender]
        return history[-limit:]


# =============================================================================
# 任务合约管理器
# =============================================================================


class TaskContractManager:
    """任务合约管理器.

    管理 Agent 之间的任务合约生命周期:
    1. 合约注册与验证
    2. 合约执行与状态跟踪
    3. 异常处理与恢复
    4. 断点续推
    """

    def __init__(self):
        self._contracts: Dict[str, TaskContract] = {}
        self._executions: Dict[str, TaskExecution] = {}
        self._recovery_strategies: Dict[ExceptionType, List[RecoveryAction]] = {}
        self._init_default_recovery()

    def _init_default_recovery(self) -> None:
        """初始化默认异常恢复策略."""
        self._recovery_strategies = {
            ExceptionType.VISION_FAILURE: [
                RecoveryAction.VISUAL_REINSPECT,
                RecoveryAction.RETRY,
                RecoveryAction.REQUEST_HUMAN,
            ],
            ExceptionType.POSE_UNCERTAINTY: [
                RecoveryAction.POSE_ADJUST,
                RecoveryAction.VISUAL_REINSPECT,
                RecoveryAction.REQUEST_HUMAN,
            ],
            ExceptionType.GRASP_FAILURE: [
                RecoveryAction.POSE_ADJUST,
                RecoveryAction.RETRY,
                RecoveryAction.SWITCH_STRATEGY,
                RecoveryAction.SKIP_SAMPLE,
                RecoveryAction.REQUEST_HUMAN,
            ],
            ExceptionType.COLLISION_RISK: [
                RecoveryAction.RETRACT_SAFE,
                RecoveryAction.EMERGENCY_STOP,
                RecoveryAction.REQUEST_HUMAN,
            ],
            ExceptionType.FORCE_OVERLOAD: [
                RecoveryAction.RETRACT_SAFE,
                RecoveryAction.EMERGENCY_STOP,
            ],
            ExceptionType.COMMUNICATION_LOSS: [
                RecoveryAction.RETRY,
                RecoveryAction.RESUME_FROM_CHECKPOINT,
                RecoveryAction.REQUEST_HUMAN,
            ],
            ExceptionType.MATERIAL_ANOMALY: [
                RecoveryAction.SKIP_SAMPLE,
                RecoveryAction.VISUAL_REINSPECT,
                RecoveryAction.REQUEST_HUMAN,
            ],
        }

    def register_contract(self, contract: TaskContract) -> str:
        """注册任务合约."""
        self._contracts[contract.contract_id] = contract
        return contract.contract_id

    def create_execution(self, contract_id: str) -> Optional[TaskExecution]:
        """创建任务执行实例."""
        contract = self._contracts.get(contract_id)
        if not contract:
            return None

        execution = TaskExecution(
            contract=contract,
            state=TaskState.PENDING,
        )
        self._executions[execution.execution_id] = execution
        return execution

    def update_state(self, execution_id: str, new_state: TaskState,
                     progress: Optional[float] = None) -> bool:
        """更新任务执行状态."""
        execution = self._executions.get(execution_id)
        if not execution:
            return False

        # 状态转换验证
        valid_transitions = {
            TaskState.PENDING: {TaskState.ACCEPTED, TaskState.FAILED},
            TaskState.ACCEPTED: {TaskState.PLANNING, TaskState.FAILED, TaskState.ABORTED},
            TaskState.PLANNING: {TaskState.EXECUTING, TaskState.FAILED},
            TaskState.EXECUTING: {TaskState.PAUSED, TaskState.COMPLETED, TaskState.FAILED,
                                  TaskState.INTERRUPTED, TaskState.ABORTED},
            TaskState.PAUSED: {TaskState.EXECUTING, TaskState.ABORTED, TaskState.INTERRUPTED},
            TaskState.INTERRUPTED: {TaskState.RECOVERING, TaskState.ABORTED},
            TaskState.RECOVERING: {TaskState.EXECUTING, TaskState.FAILED},
            TaskState.FAILED: {TaskState.PENDING},  # 可重新调度
            TaskState.ABORTED: set(),  # 终态
            TaskState.COMPLETED: set(),  # 终态
        }

        if new_state not in valid_transitions.get(execution.state, set()):
            return False

        execution.state = new_state
        if progress is not None:
            execution.progress = progress
        execution.last_updated = time.time()

        if new_state == TaskState.EXECUTING and execution.started_at == 0:
            execution.started_at = time.time()
        if new_state in (TaskState.COMPLETED, TaskState.FAILED, TaskState.ABORTED):
            execution.completed_at = time.time()

        return True

    def handle_exception(self, execution_id: str,
                         exception_type: ExceptionType,
                         description: str = "") -> List[RecoveryAction]:
        """处理异常并返回恢复策略.

        Args:
            execution_id: 执行ID
            exception_type: 异常类型
            description: 异常描述

        Returns:
            推荐的恢复动作列表
        """
        execution = self._executions.get(execution_id)
        if not execution:
            return [RecoveryAction.REQUEST_HUMAN]

        # 记录异常
        execution.exception_history.append(
            (exception_type, time.time(), description)
        )
        execution.retry_count += 1

        # 检查是否超过最大重试次数
        if execution.retry_count > execution.contract.max_retries:
            execution.state = TaskState.FAILED
            return [RecoveryAction.REQUEST_HUMAN]

        # 获取恢复策略
        # 优先使用合约自定义策略，否则使用默认策略
        strategies = execution.contract.exception_handlers.get(
            exception_type,
            self._recovery_strategies.get(exception_type, [RecoveryAction.REQUEST_HUMAN]),
        )

        return strategies

    def save_checkpoint(self, execution_id: str,
                        data: Dict[str, Any]) -> bool:
        """保存断点数据."""
        execution = self._executions.get(execution_id)
        if not execution:
            return False
        execution.checkpoint_data = data
        return True

    def resume_from_checkpoint(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """从断点恢复."""
        execution = self._executions.get(execution_id)
        if not execution or not execution.checkpoint_data:
            return None
        execution.state = TaskState.RECOVERING
        return execution.checkpoint_data

    def get_execution_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """获取执行状态."""
        execution = self._executions.get(execution_id)
        if not execution:
            return None

        return {
            "execution_id": execution.execution_id,
            "contract_id": execution.contract.contract_id,
            "task_type": execution.contract.task_type,
            "state": execution.state.value,
            "progress": execution.progress,
            "retry_count": execution.retry_count,
            "exception_count": len(execution.exception_history),
            "duration_s": (execution.completed_at or time.time()) - (execution.started_at or time.time()),
            "last_updated": execution.last_updated,
        }


# =============================================================================
# 动作调度层
# =============================================================================


class ActionDispatchLayer:
    """动作调度层 - 将抽象任务转化为确定性的机械臂动作.

    将调度Agent和质检Agent的抽象任务实时转化为:
    - ROS 2 下基于 MoveIt 的无碰撞、时间最优轨迹
    - 确定性接口调用
    - 同步/异步动作执行
    """

    def __init__(self):
        self._action_queue: List[Tuple[TaskPriority, Callable, Dict]] = []
        self._action_history: List[Dict[str, Any]] = []
        self._is_executing = False

    def dispatch(self, action: Callable, params: Dict[str, Any],
                 priority: TaskPriority = TaskPriority.NORMAL) -> str:
        """调度动作.

        Args:
            action: 动作函数
            params: 动作参数
            priority: 优先级

        Returns:
            action_id
        """
        action_id = uuid.uuid4().hex[:12]
        self._action_queue.append((priority, action, params, action_id))
        # 按优先级排序
        self._action_queue.sort(key=lambda x: x[0])
        return action_id

    def execute_next(self) -> Optional[Dict[str, Any]]:
        """执行队列中的下一个动作."""
        if not self._action_queue or self._is_executing:
            return None

        self._is_executing = True
        priority, action, params, action_id = self._action_queue.pop(0)

        try:
            start_time = time.time()
            result = action(**params)
            duration = time.time() - start_time

            record = {
                "action_id": action_id,
                "priority": priority.name,
                "success": True,
                "result": result,
                "duration_s": duration,
                "timestamp": start_time,
            }
        except Exception as e:
            record = {
                "action_id": action_id,
                "priority": priority.name,
                "success": False,
                "error": str(e),
                "duration_s": time.time() - start_time,
                "timestamp": start_time,
            }

        self._action_history.append(record)
        self._is_executing = False
        return record

    def get_pending_count(self) -> int:
        """获取待处理动作数."""
        return len(self._action_queue)

    def clear_queue(self) -> None:
        """清空动作队列 (紧急停止)."""
        self._action_queue.clear()


# =============================================================================
# MES 集成接口
# =============================================================================


class MESInterface:
    """MES (制造执行系统) 集成接口.

    根据 MES 调度指令自适应切换采样策略:
    - 接收工单与采样需求
    - 解析产品类型与质量要求
    - 生成对应的任务合约
    """

    # 产品类型 → 采样策略映射
    PRODUCT_STRATEGY_MAP = {
        "electronics": "grid",
        "automotive": "adaptive",
        "aerospace": "targeted",
        "consumer_goods": "random",
        "medical": "targeted",
        "default": "adaptive",
    }

    def __init__(self):
        self._active_orders: Dict[str, MESInstruction] = {}
        self._order_history: List[MESInstruction] = []

    def receive_instruction(self, instruction: MESInstruction) -> TaskContract:
        """接收 MES 调度指令并生成任务合约.

        Args:
            instruction: MES 调度指令

        Returns:
            对应的任务合约
        """
        self._active_orders[instruction.instruction_id] = instruction
        self._order_history.append(instruction)

        # 根据产品类型自适应选择采样策略
        if not instruction.sampling_strategy:
            instruction.sampling_strategy = self.PRODUCT_STRATEGY_MAP.get(
                instruction.product_type, "adaptive"
            )

        # 生成任务合约
        contract = TaskContract(
            task_type="sample",
            source_agent="mes",
            target_agent="orchestrator",
            priority=instruction.priority,
            input_schema={
                "work_order_id": instruction.work_order_id,
                "product_type": instruction.product_type,
                "sampling_strategy": instruction.sampling_strategy,
                "sample_count": instruction.sample_count,
                "target_locations": instruction.target_locations,
            },
            required_fields=["work_order_id", "product_type", "sample_count"],
            constraints={
                "min_samples": instruction.sample_count,
                "quality_requirements": instruction.quality_requirements,
            },
            expected_output={
                "sampled_count": instruction.sample_count,
                "grasp_success_rate": 0.995,
                "position_accuracy_mm": 0.5,
            },
            quality_metrics={
                "grasp_success_rate": 0.995,
                "position_accuracy_mm": 0.5,
                "cycle_time_s": 30.0,
            },
            exception_handlers={
                ExceptionType.GRASP_FAILURE: [
                    RecoveryAction.POSE_ADJUST,
                    RecoveryAction.RETRY,
                    RecoveryAction.SWITCH_STRATEGY,
                    RecoveryAction.SKIP_SAMPLE,
                ],
                ExceptionType.MATERIAL_ANOMALY: [
                    RecoveryAction.SKIP_SAMPLE,
                    RecoveryAction.VISUAL_REINSPECT,
                ],
            },
            max_retries=3,
            timeout_s=60.0,
            deadline_s=instruction.deadline,
            metadata={
                "mes_instruction_id": instruction.instruction_id,
                "work_order_id": instruction.work_order_id,
            },
        )

        return contract

    def report_completion(self, instruction_id: str,
                          result: Dict[str, Any]) -> None:
        """向 MES 上报任务完成."""
        instruction = self._active_orders.pop(instruction_id, None)
        if instruction:
            # 实际系统中通过 OPC UA / REST API 上报
            pass

    def get_active_orders(self) -> List[MESInstruction]:
        """获取活跃工单."""
        return list(self._active_orders.values())


# =============================================================================
# 快速测试
# =============================================================================

if __name__ == "__main__":
    # 测试 A2A 协议
    protocol = A2AProtocol("motion_agent")

    def handle_task(msg: A2AMessage) -> A2AMessage:
        return A2AMessage(
            sender="motion_agent",
            receiver=msg.sender,
            message_type="task_response",
            payload={"status": "accepted", "task": msg.payload},
            correlation_id=msg.message_id,
        )

    protocol.register_handler("task_request", handle_task)

    # 测试任务合约
    manager = TaskContractManager()

    contract = TaskContract(
        task_type="pick_place",
        source_agent="orchestrator",
        target_agent="motion_agent",
        priority=TaskPriority.HIGH,
        input_schema={"target_pose": [0.1, 0.2, 0.3, 0, 0, 0]},
        required_fields=["target_pose"],
        expected_output={"status": "completed"},
        timeout_s=30.0,
    )

    cid = manager.register_contract(contract)
    execution = manager.create_execution(cid)
    manager.update_state(execution.execution_id, TaskState.ACCEPTED)
    manager.update_state(execution.execution_id, TaskState.PLANNING)
    manager.update_state(execution.execution_id, TaskState.EXECUTING, progress=0.5)

    # 测试异常处理
    actions = manager.handle_exception(
        execution.execution_id,
        ExceptionType.GRASP_FAILURE,
        "Suction cup lost vacuum",
    )
    print(f"Recovery actions for grasp failure: {[a.value for a in actions]}")

    status = manager.get_execution_status(execution.execution_id)
    print(f"Execution status: {json.dumps(status, indent=2)}")

    # 测试 MES 集成
    mes = MESInterface()
    instruction = MESInstruction(
        instruction_id="MES-001",
        work_order_id="WO-2024-001",
        product_type="aerospace",
        sample_count=5,
        quality_requirements={"aql": 0.65, "critical_defects": 0},
        priority=TaskPriority.HIGH,
    )
    task_contract = mes.receive_instruction(instruction)
    print(f"\nMES Task Contract: {task_contract.task_type}")
    print(f"  Strategy: {task_contract.input_schema['sampling_strategy']}")
    print(f"  Quality: {task_contract.quality_metrics}")