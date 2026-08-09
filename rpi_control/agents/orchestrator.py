"""
Multi-Agent Orchestrator for the Intelligent Sampling Robotic Arm.

Coordinates all agents (Sampling, Vision, Motion, Quality, Safety) through
a LangGraph-inspired state machine to execute complete sampling tasks.

State Machine:
    IDLE -> PLANNING -> APPROACHING -> DETECTING -> GRASPING ->
    LIFTING -> INSPECTING -> PLACING -> EVALUATING -> DONE

Error States:
    RECOVERY, ABORT (with conditional transitions)

The orchestrator manages task queues, priority-based scheduling, state
persistence for recovery, and real-time status updates via callbacks.
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple

from .base_agent import BaseAgent, AgentConfig, AgentStatus
from .sampling_agent import SamplingAgent, SamplingState
from .vision_agent import VisionAgent
from .motion_agent import MotionAgent, MotionState
from .quality_agent import QualityAgent, QualityDecision
from .safety_agent import SafetyAgent, SafetyState


class OrchestratorState(Enum):
    """States for the orchestrator's task execution state machine."""
    IDLE = "idle"
    PLANNING = "planning"
    APPROACHING = "approaching"
    DETECTING = "detecting"
    GRASPING = "grasping"
    LIFTING = "lifting"
    INSPECTING = "inspecting"
    PLACING = "placing"
    EVALUATING = "evaluating"
    DONE = "done"
    RECOVERY = "recovery"
    ABORT = "abort"


class TaskPriority(Enum):
    """Priority levels for tasks."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class TaskRequest:
    """A task request to be executed by the orchestrator.

    Attributes:
        task_id: Unique task identifier.
        task_type: Type of task (e.g., 'sample', 'inspect', 'calibrate').
        params: Task parameters.
        priority: Priority level.
        created_at: Timestamp of creation.
        timeout_seconds: Maximum execution time.
        status: Current task status.
    """
    task_id: str
    task_type: str
    params: Dict[str, Any]
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: float = 0.0
    timeout_seconds: float = 300.0
    status: str = "pending"

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()


class Orchestrator:
    """Central orchestrator for the multi-agent robotic arm system.

    Manages the lifecycle of all agents, coordinates task execution through
    a state machine, and provides real-time status updates.

    Attributes:
        config: Orchestrator configuration.
        agents: Dict of all registered agents.
        state: Current orchestrator state.
        task_queue: Queue of pending tasks.
        current_task: Currently executing task.
        state_history: Record of state transitions.
        status_callback: Optional callback for real-time status updates.
        _running: Whether the orchestrator loop is running.
    """

    # State transition graph
    STATE_TRANSITIONS: Dict[OrchestratorState, List[OrchestratorState]] = {
        OrchestratorState.IDLE: [OrchestratorState.PLANNING],
        OrchestratorState.PLANNING: [OrchestratorState.APPROACHING, OrchestratorState.RECOVERY, OrchestratorState.ABORT],
        OrchestratorState.APPROACHING: [OrchestratorState.DETECTING, OrchestratorState.EVALUATING, OrchestratorState.RECOVERY, OrchestratorState.ABORT],
        OrchestratorState.DETECTING: [OrchestratorState.GRASPING, OrchestratorState.EVALUATING, OrchestratorState.RECOVERY, OrchestratorState.ABORT],
        OrchestratorState.GRASPING: [OrchestratorState.LIFTING, OrchestratorState.RECOVERY, OrchestratorState.ABORT],
        OrchestratorState.LIFTING: [OrchestratorState.INSPECTING, OrchestratorState.RECOVERY, OrchestratorState.ABORT],
        OrchestratorState.INSPECTING: [OrchestratorState.PLACING, OrchestratorState.ABORT],
        OrchestratorState.PLACING: [OrchestratorState.EVALUATING, OrchestratorState.RECOVERY, OrchestratorState.ABORT],
        OrchestratorState.EVALUATING: [OrchestratorState.PLANNING, OrchestratorState.DONE, OrchestratorState.ABORT],
        OrchestratorState.DONE: [OrchestratorState.IDLE],
        OrchestratorState.RECOVERY: [OrchestratorState.PLANNING, OrchestratorState.ABORT],
        OrchestratorState.ABORT: [OrchestratorState.IDLE],
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the orchestrator with all agents.

        Args:
            config: Optional configuration dict.
        """
        self.config: Dict[str, Any] = config or {}
        self.state: OrchestratorState = OrchestratorState.IDLE
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.current_task: Optional[TaskRequest] = None
        self.state_history: List[Dict[str, Any]] = []
        self.status_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self._running: bool = False

        # Safety check debouncing: avoid redundant checks on every state transition
        self._last_safety_check_time: float = 0.0
        self._safety_check_interval: float = 0.1  # minimum 100ms between safety checks
        self._last_safety_result: Optional[Dict[str, Any]] = None

        # Task error recovery tracking
        self._consecutive_errors: int = 0
        self._max_consecutive_errors: int = 3

        # Loop Engineering: profiling and interaction tracking
        self._loop_enabled: bool = False
        self._e2e_profiler: Any = None
        self._interaction_tracker: Any = None
        self._context_manager: Any = None

        # Initialize all agents with error tracking
        self.agents: Dict[str, BaseAgent] = {}
        self._agent_init_errors: Dict[str, str] = {}
        self._init_agents()

        # Cached agent references for fast access in state handlers
        self._sampling_agent: Optional[SamplingAgent] = self.agents.get("sampling")  # type: ignore
        self._vision_agent: Optional[VisionAgent] = self.agents.get("vision")  # type: ignore
        self._motion_agent: Optional[MotionAgent] = self.agents.get("motion")  # type: ignore
        self._quality_agent: Optional[QualityAgent] = self.agents.get("quality")  # type: ignore
        self._safety_agent: Optional[SafetyAgent] = self.agents.get("safety")  # type: ignore

        # State handler dispatch table (O(1) lookup instead of if-elif chain)
        self._state_handlers: Dict[OrchestratorState, Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]] = {
            OrchestratorState.IDLE: self._do_idle,
            OrchestratorState.PLANNING: self._do_planning,
            OrchestratorState.APPROACHING: self._do_approaching,
            OrchestratorState.DETECTING: self._do_detecting,
            OrchestratorState.GRASPING: self._do_grasping,
            OrchestratorState.LIFTING: self._do_lifting,
            OrchestratorState.INSPECTING: self._do_inspecting,
            OrchestratorState.PLACING: self._do_placing,
            OrchestratorState.EVALUATING: self._do_evaluating,
            OrchestratorState.RECOVERY: self._do_recovery,
            OrchestratorState.ABORT: self._do_abort,
        }

        # Shared system state
        self.system_state: Dict[str, Any] = {
            "task_id": "",
            "current_pose": {
                "position": (250.0, 250.0, 100.0),
                "orientation": (0.0, 0.0, 0.0),
            },
            "workspace_bounds": {
                "x": (0.0, 500.0),
                "y": (0.0, 500.0),
                "z": (0.0, 300.0),
            },
            "safety_state": SafetyState.OK.value,
            "sampling_state": "idle",
            "vision_result": None,
            "quality_score": 0.0,
            "error": None,
            "error_history": [],  # Persist error history for recovery analysis
        }

    # =========================================================================
    # Agent Initialization
    # =========================================================================

    def _init_agents(self) -> None:
        """Initialize all agents with fault isolation.

        Each agent is initialized independently. If one fails, the error is
        recorded but other agents continue initialization. Critical agents
        (safety, motion) failures are logged at ERROR level.
        """
        agent_definitions = [
            ("sampling", SamplingAgent, AgentConfig(name="sampling_agent", timeout_seconds=60.0), False),
            ("vision", VisionAgent, AgentConfig(name="vision_agent", timeout_seconds=10.0), False),
            ("motion", MotionAgent, AgentConfig(name="motion_agent", timeout_seconds=30.0), True),
            ("quality", QualityAgent, AgentConfig(name="quality_agent", timeout_seconds=15.0), False),
            ("safety", SafetyAgent, AgentConfig(name="safety_agent", timeout_seconds=5.0), True),
        ]

        for name, agent_cls, config, is_critical in agent_definitions:
            try:
                self.agents[name] = agent_cls(config=config)
                self._log(f"Agent '{name}' initialized successfully")
            except Exception as e:
                self._agent_init_errors[name] = str(e)
                level = 40 if is_critical else 30
                self._log(f"Failed to initialize agent '{name}': {e}", level)

        # Log summary
        if self._agent_init_errors:
            failed = list(self._agent_init_errors.keys())
            self._log(f"Agent initialization completed with {len(failed)} failures: {failed}", 30)
        else:
            self._log(f"All {len(self.agents)} agents initialized successfully")

    # =========================================================================
    # Task Execution
    # =========================================================================

    async def run_task(self, task: TaskRequest) -> Dict[str, Any]:
        """Execute a complete sampling task.

        This is the primary entry point. It runs the full state machine
        from PLANNING through DONE with debounced safety checks.

        Args:
            task: The task request to execute.

        Returns:
            Final task result dict.
        """
        self.current_task = task
        self.system_state["task_id"] = task.task_id
        self.system_state["error"] = None
        self._consecutive_errors = 0

        self._log(f"Starting task: {task.task_id} (type={task.task_type})")

        try:
            # Transition to PLANNING
            await self._transition_to(OrchestratorState.PLANNING)

            # Run the state machine until terminal state
            while self.state not in (OrchestratorState.DONE, OrchestratorState.ABORT):
                await self.process_state(self.system_state)

                # Debounced safety check (not on every state transition)
                now = time.time()
                if now - self._last_safety_check_time >= self._safety_check_interval:
                    safety_agent = self._safety_agent
                    if safety_agent is not None:
                        safety_state = {
                            "current_pose": self.system_state.get("current_pose", {}),
                            "joint_positions": self.system_state.get("joint_positions", {}),
                            "planned_path": self.system_state.get("planned_path", []),
                            "timestamp": now,
                        }
                        safety_result = await safety_agent.run(safety_state)
                        self._last_safety_result = safety_result
                        self._last_safety_check_time = now
                        self.system_state["safety_state"] = safety_result.get("safety_state", SafetyState.OK.value)

                        if safety_result.get("safety_state") == SafetyState.ESTOP.value:
                            self._log("ESTOP triggered by safety agent, aborting task", 40)
                            await self._transition_to(OrchestratorState.ABORT)
                            break
                        elif safety_result.get("safety_state") == SafetyState.DANGER.value:
                            self._log("DANGER state detected, attempting recovery", 40)
                            # 仅当当前状态允许进入 RECOVERY 时才恢复; 否则 (如
                            # PLANNING/IDLE/DONE 等未定义 RECOVERY 转移的状态) 直接安全中止,
                            # 避免抛出 "Invalid state transition" 使状态机崩溃。
                            valid_next = self.STATE_TRANSITIONS.get(self.state, [])
                            if OrchestratorState.RECOVERY in valid_next:
                                await self._transition_to(OrchestratorState.RECOVERY)
                                await self.process_state(self.system_state)
                            else:
                                self._log(
                                    f"DANGER 发生在不可恢复状态 ({self.state.value}), 直接安全中止", 40,
                                )
                                await self._transition_to(OrchestratorState.ABORT)
                                break
                    else:
                        self._log("Safety agent not available, skipping safety check", 30)

                # Timeout check
                elapsed = time.time() - task.created_at
                if elapsed > task.timeout_seconds:
                    self._log(f"Task timeout ({elapsed:.1f}s > {task.timeout_seconds}s)", 40)
                    await self._transition_to(OrchestratorState.ABORT)
                    break

            # Build result
            result = self._build_task_result()
            self._log(f"Task completed: {task.task_id}, state={self.state.value}")
            return result

        except Exception as e:
            self._consecutive_errors += 1
            self._log(f"Task failed: {e} (consecutive errors: {self._consecutive_errors})", 50)
            self.system_state["error"] = str(e)

            # Persist error in history for recovery analysis
            error_entry = {
                "timestamp": time.time(),
                "error": str(e),
                "state": self.state.value,
                "consecutive_count": self._consecutive_errors,
                "task_id": task.task_id,
            }
            if "error_history" not in self.system_state:
                self.system_state["error_history"] = []
            self.system_state["error_history"].append(error_entry)
            # Keep last 50 errors
            if len(self.system_state["error_history"]) > 50:
                self.system_state["error_history"] = self.system_state["error_history"][-50:]

            # If too many consecutive errors, escalate to abort
            if self._consecutive_errors >= self._max_consecutive_errors:
                self._log(f"Too many consecutive errors ({self._consecutive_errors}), forcing abort", 50)
            await self._transition_to(OrchestratorState.ABORT)
            return self._build_task_result()

        finally:
            self.current_task = None
            self._notify_status()

    async def process_state(self, state: Dict[str, Any]) -> None:
        """Run one iteration of the state machine using O(1) dispatch.

        Uses a pre-built dispatch table for O(1) lookup instead of the
        previous O(n) if-elif chain.

        Args:
            state: Current system state dict (modified in place).
        """
        self._log(f"Processing state: {self.state.value}")

        handler = self._state_handlers.get(self.state)
        if handler is not None:
            await handler(state)

        self._notify_status()

    # =========================================================================
    # Agent Availability Check
    # =========================================================================

    def _require_agent(self, agent: Any, agent_name: str) -> None:
        """Validate that an agent is available before use.

        If the agent is None (initialization failed), transitions to ABORT
        by raising a RuntimeError that is caught by the state machine.

        Args:
            agent: The agent instance to check (may be None).
            agent_name: Human-readable agent name for error messages.

        Raises:
            RuntimeError: If the agent is None.
        """
        if agent is None:
            self._log(f"Critical agent '{agent_name}' is not available (init failed)", 50)
            raise RuntimeError(f"Agent '{agent_name}' is not available")

    def _require_agents(self, *agent_tuples: Tuple[Any, str]) -> None:
        """Validate multiple agents at once.

        Args:
            *agent_tuples: Tuples of (agent_instance, agent_name).

        Raises:
            RuntimeError: If any agent is None.
        """
        for agent, name in agent_tuples:
            if agent is None:
                self._log(f"Critical agent '{name}' is not available (init failed)", 50)
                raise RuntimeError(f"Agent '{name}' is not available")

    # =========================================================================
    # State Handlers
    # =========================================================================

    async def _do_idle(self, state: Dict[str, Any]) -> None:
        """IDLE state: transition to planning."""
        await self._transition_to(OrchestratorState.PLANNING)

    async def _do_planning(self, state: Dict[str, Any]) -> None:
        """Execute the PLANNING state: generate sampling plan."""
        safety_agent = self._safety_agent
        sampling_agent = self._sampling_agent
        self._require_agents((safety_agent, "safety"), (sampling_agent, "sampling"))

        # Check safety before planning
        if safety_agent.safety_state != SafetyState.OK:  # type: ignore[union-attr]
            await self._transition_to(OrchestratorState.RECOVERY)
            return

        # Run the sampling agent to generate a plan
        plan_state = {
            "task_id": state["task_id"],
            "workspace_bounds": state["workspace_bounds"],
            "sampling_strategy": state.get("sampling_strategy", "grid"),
        }
        result = await sampling_agent.run(plan_state)  # type: ignore[union-attr]

        state["sampling_points"] = result.get("sampling_points", [])
        state["sampling_state"] = result.get("sampling_state", "planning")

        if result.get("error"):
            await self._transition_to(OrchestratorState.ABORT)
        else:
            await self._transition_to(OrchestratorState.APPROACHING)

    async def _do_approaching(self, state: Dict[str, Any]) -> None:
        """Execute the APPROACHING state: move to next sampling point."""
        motion_agent = self._motion_agent
        self._require_agent(motion_agent, "motion")

        # Get next target from sampling plan
        sampling_points = state.get("sampling_points", [])
        pending = [p for p in sampling_points if p.get("status") == "pending"]
        if not pending:
            await self._transition_to(OrchestratorState.EVALUATING)
            return

        next_target = pending[0]
        target_position = tuple(next_target.get("position", (0, 0, 0)))

        # Plan and execute approach motion
        target_pose = {"position": target_position}
        motion_state = {
            "target_pose": target_pose,
            "motion_type": "approach",
        }
        result = await motion_agent.run(motion_state)  # type: ignore[union-attr]

        if result.get("motion_result", {}).get("success"):
            state["current_pose"] = motion_agent.current_pose  # type: ignore[union-attr]
            state["current_target"] = next_target
            await self._transition_to(OrchestratorState.DETECTING)
        else:
            self._log(f"Approach failed: {result.get('error')}", 40)
            await self._transition_to(OrchestratorState.RECOVERY)

    async def _do_detecting(self, state: Dict[str, Any]) -> None:
        """Execute the DETECTING state: run vision detection."""
        vision_agent = self._vision_agent
        self._require_agent(vision_agent, "vision")

        # 首次进入前确保已接入相机内参 + 手眼标定 (像素/相机 -> 机器人基座系)
        self._ensure_vision_calibration(vision_agent)

        # Request color detection at the current position
        vision_state = {
            "detection_type": "detect_color",
            "vision_params": {
                "color_name": state.get("target_color", "red"),
            },
        }
        result = await vision_agent.run(vision_state)  # type: ignore[union-attr]
        vision_result = result.get("vision_result")
        state["vision_result"] = vision_result

        if vision_result and vision_result.get("found"):
            # 关键: 把检测结果转换为机器人基座系坐标 (mm), 供抓取/采样复用。
            # 之前版本把像素 cx/cy 直接当 mm 下发, 是坐标断链的根源。
            robot_pose = vision_agent.pose_in_robot_frame(vision_result)  # type: ignore[union-attr]
            state["vision_target_robot"] = robot_pose
            await self._transition_to(OrchestratorState.GRASPING)
        else:
            # No object detected at this point; skip to next
            state["vision_target_robot"] = None
            self._log("No object detected at current position, skipping", 30)
            await self._transition_to(OrchestratorState.EVALUATING)

    def _ensure_vision_calibration(self, vision_agent: Optional[VisionAgent]) -> None:
        """确保 vision agent 已接入相机内参与手眼标定 (仅配置一次)。

        从 self.config 的 'vision' 节读取; 若未提供, 回退到与 settings.yaml
        中 grasp 一致的默认手眼参数, 保证坐标系同步开箱即用。
        """
        if vision_agent is None or vision_agent.calibration is not None:
            return

        cfg = (self.config or {}).get("vision", {})
        camera_matrix = cfg.get("camera_matrix")
        hand_eye_R = cfg.get("hand_eye_rotation")
        hand_eye_t = cfg.get("hand_eye_translation")

        if camera_matrix is None:
            camera_matrix = [[320.0, 0, 160.0], [0, 320.0, 120.0], [0, 0, 1.0]]
        if hand_eye_R is None:
            hand_eye_R = [[1, 0, 0], [0, -1, 0], [0, 0, -1]]
        if hand_eye_t is None:
            hand_eye_t = [-100.0, -200.0, 50.0]

        vision_agent.configure_calibration(
            camera_matrix=camera_matrix,
            hand_eye_rotation=hand_eye_R,
            hand_eye_translation=hand_eye_t,
            image_width=cfg.get("image_width", 320),
            image_height=cfg.get("image_height", 240),
        )

    async def _do_grasping(self, state: Dict[str, Any]) -> None:
        """Execute the GRASPING state: close gripper on object."""
        motion_agent = self._motion_agent
        self._require_agent(motion_agent, "motion")

        # Get precise target from vision (机器人基座系, mm)
        vision_target = state.get("vision_target_robot") or {}
        robot_pos = vision_target.get("position")
        if robot_pos:
            target_position = tuple(robot_pos)
        else:
            # 无视觉目标时回退到采样点位置
            target_position = state.get("current_target", {}).get("position", (0, 0, 0))

        # Move to precise grasp position
        motion_state = {
            "target_pose": {"position": target_position},
            "motion_type": "move_to",
        }
        result = await motion_agent.run(motion_state)  # type: ignore[union-attr]

        if result.get("motion_result", {}).get("success"):
            # Execute grasp
            grasp_result = await motion_agent.run({  # type: ignore[union-attr]
                "target_pose": {"position": target_position},
                "motion_type": "grasp",
            })
            if grasp_result.get("motion_result", {}).get("success"):
                state["object_grasped"] = True
                await self._transition_to(OrchestratorState.LIFTING)
            else:
                await self._transition_to(OrchestratorState.RECOVERY)
        else:
            await self._transition_to(OrchestratorState.RECOVERY)

    async def _do_lifting(self, state: Dict[str, Any]) -> None:
        """Execute the LIFTING state: raise the object."""
        motion_agent = self._motion_agent
        self._require_agent(motion_agent, "motion")

        motion_state = {
            "target_pose": motion_agent.current_pose,  # type: ignore[union-attr]
            "motion_type": "lift",
        }
        result = await motion_agent.run(motion_state)  # type: ignore[union-attr]

        if result.get("motion_result", {}).get("success"):
            state["current_pose"] = motion_agent.current_pose  # type: ignore[union-attr]
            await self._transition_to(OrchestratorState.INSPECTING)
        else:
            await self._transition_to(OrchestratorState.RECOVERY)

    async def _do_inspecting(self, state: Dict[str, Any]) -> None:
        """Execute the INSPECTING state: quality inspection of the grasped object."""
        vision_agent = self._vision_agent
        quality_agent = self._quality_agent
        self._require_agents((vision_agent, "vision"), (quality_agent, "quality"))

        # Request inspection from OpenMV
        vision_state = {
            "detection_type": "inspect",
            "vision_params": {"sample_id": state["task_id"]},
        }
        vision_result = await vision_agent.run(vision_state)
        inspection_data = vision_result.get("vision_result", {})

        # Evaluate quality
        quality_state = {
            "sample_id": state["task_id"],
            "inspection_result": inspection_data,
            "product_type": state.get("product_type", "default"),
        }
        quality_result = await quality_agent.run(quality_state)

        state["quality_score"] = quality_result.get("quality_score", 0.0)
        state["quality_decision"] = quality_result.get("quality_decision", "pending")
        state["resample_needed"] = quality_result.get("resample_needed", False)

        await self._transition_to(OrchestratorState.PLACING)

    async def _do_placing(self, state: Dict[str, Any]) -> None:
        """Execute the PLACING state: move to place location and release."""
        motion_agent = self._motion_agent
        self._require_agent(motion_agent, "motion")

        # Determine place location based on quality decision
        decision = state.get("quality_decision", "accept")
        if decision == "accept":
            place_pos = (450.0, 250.0, 50.0)  # Accept bin
        elif decision == "rework":
            place_pos = (450.0, 150.0, 50.0)  # Rework area
        else:
            place_pos = (450.0, 50.0, 50.0)   # Reject bin

        place_pose = {"position": place_pos}

        motion_state = {
            "target_pose": place_pose,
            "motion_type": "place",
        }
        result = await motion_agent.run(motion_state)  # type: ignore[union-attr]

        if result.get("motion_result", {}).get("success"):
            state["current_pose"] = motion_agent.current_pose  # type: ignore[union-attr]
            state["object_placed"] = True
            await self._transition_to(OrchestratorState.EVALUATING)
        else:
            await self._transition_to(OrchestratorState.RECOVERY)

    async def _do_evaluating(self, state: Dict[str, Any]) -> None:
        """Execute the EVALUATING state: check if more samples are needed."""
        sampling_agent = self._sampling_agent
        self._require_agent(sampling_agent, "sampling")

        # Run sampling evaluation
        eval_state = {
            "task_id": state["task_id"],
            "command": "evaluate",
            "quality_score": state.get("quality_score", 0.0),
            "resample_needed": state.get("resample_needed", False),
        }

        # Update sampling agent with current point completion
        sampling_agent.state_machine_state = SamplingState.EVALUATING  # type: ignore[union-attr]
        eval_result = await sampling_agent.run(eval_state)  # type: ignore[union-attr]

        state["evaluation"] = eval_result.get("evaluation", {})
        state["sampling_state"] = eval_result.get("sampling_state", "done")

        if eval_result.get("sampling_complete"):
            await self._transition_to(OrchestratorState.DONE)
        else:
            # More samples needed
            await self._transition_to(OrchestratorState.PLANNING)

    async def _do_recovery(self, state: Dict[str, Any]) -> None:
        """Execute the RECOVERY state: attempt error recovery."""
        motion_agent = self._motion_agent
        safety_agent = self._safety_agent
        self._require_agent(motion_agent, "motion")

        self._log("Attempting recovery", 40)

        # Return to home position
        home_state = {
            "target_pose": motion_agent.home_pose,  # type: ignore[union-attr]
            "motion_type": "home",
        }

        try:
            result = await motion_agent.run(home_state)  # type: ignore[union-attr]
            if result.get("motion_result", {}).get("success"):
                state["current_pose"] = motion_agent.home_pose  # type: ignore[union-attr]
                # 回到已知安全位姿后, 重置安全 agent 的缓存状态, 避免遗留的
                # DANGER 标志在下次 PLANNING 时造成"恢复->再恢复"死循环。
                if safety_agent is not None:
                    safety_agent.safety_state = SafetyState.OK
                    safety_agent._previous_positions = None
                    safety_agent._previous_time = 0.0
                self._log("Recovery successful, resuming", 30)
                await self._transition_to(OrchestratorState.PLANNING)
            else:
                self._log("Recovery failed, aborting", 50)
                await self._transition_to(OrchestratorState.ABORT)
        except Exception as e:
            self._log(f"Recovery error: {e}", 50)
            await self._transition_to(OrchestratorState.ABORT)

    async def _do_abort(self, state: Dict[str, Any]) -> None:
        """Execute the ABORT state: clean shutdown."""
        motion_agent = self._motion_agent
        safety_agent = self._safety_agent

        self._log("Aborting task", 50)

        # Trigger safety stop (safety_agent may be None, handle gracefully)
        if safety_agent is not None:
            try:
                await safety_agent.emergency_stop()
            except Exception as e:
                self._log(f"Emergency stop failed: {e}", 50)

        # Try to return home (motion_agent may be None, handle gracefully)
        if motion_agent is not None:
            try:
                await motion_agent.run({
                    "target_pose": motion_agent.home_pose,
                    "motion_type": "home",
                })
            except Exception:
                pass

        state["aborted"] = True
        state["error"] = state.get("error", "Task aborted")

    # =========================================================================
    # State Management
    # =========================================================================

    async def _transition_to(self, new_state: OrchestratorState) -> None:
        """Transition to a new state, validating the transition.

        Args:
            new_state: Target state.

        Raises:
            ValueError: If the transition is invalid.
        """
        valid_next = self.STATE_TRANSITIONS.get(self.state, [])
        if new_state not in valid_next and self.state != new_state:
            error_msg = f"Invalid state transition: {self.state.value} -> {new_state.value}. Valid: {[s.value for s in valid_next]}"
            self._log(error_msg, 40)
            raise ValueError(error_msg)

        old_state = self.state
        self.state = new_state

        self.state_history.append({
            "timestamp": time.time(),
            "from": old_state.value,
            "to": new_state.value,
            "task_id": self.system_state.get("task_id", ""),
        })

        self._log(f"State: {old_state.value} -> {new_state.value}")

    def build_state_graph(self) -> Dict[str, List[str]]:
        """Return the state machine graph definition.

        Returns:
            Dict mapping state names to lists of valid next states.
        """
        return {
            state.value: [s.value for s in transitions]
            for state, transitions in self.STATE_TRANSITIONS.items()
        }

    # =========================================================================
    # Task Queue
    # =========================================================================

    async def enqueue_task(self, task: TaskRequest) -> None:
        """Add a task to the execution queue.

        Args:
            task: The task to enqueue.
        """
        await self.task_queue.put(task)
        self._log(f"Task enqueued: {task.task_id} (queue size: {self.task_queue.qsize()})")

    async def run(self) -> None:
        """Start the main orchestrator loop, processing tasks from the queue.

        Runs until stop() is called. Processes tasks with priority-based
        scheduling from the task queue.
        """
        self._running = True
        self._log("Orchestrator started")

        while self._running:
            try:
                # Wait for a task with a timeout to allow checking _running
                try:
                    task = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                # Execute the task
                try:
                    result = await self.run_task(task)
                    # Notify completion
                    self._log(f"Task result: {task.task_id} -> {result.get('status', 'unknown')}")
                except Exception as e:
                    self._log(f"Task execution error: {e}", 50)
                finally:
                    # CRITICAL: task_done() MUST always be called, even on exception.
                    # asyncio.Queue.join() depends on task_done() to track pending
                    # items; missing calls cause join() to block forever.
                    self.task_queue.task_done()

            except Exception as e:
                self._log(f"Orchestrator loop error: {e}", 50)

        self._log("Orchestrator stopped")

    async def stop(self) -> None:
        """Stop the orchestrator loop gracefully."""
        self._running = False
        self._log("Orchestrator stop requested")

    # =========================================================================
    # Status and Callbacks
    # =========================================================================

    def set_status_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback for real-time status updates.

        Args:
            callback: Function that receives a status dict.
        """
        self.status_callback = callback

    def _notify_status(self) -> None:
        """Send a status update to the registered callback."""
        if self.status_callback:
            try:
                self.status_callback(self.get_status())
            except Exception as e:
                self._log(f"Status callback error: {e}", 40)

    def get_status(self) -> Dict[str, Any]:
        """Get the current orchestrator status.

        Returns:
            Comprehensive status dict.
        """
        return {
            "state": self.state.value,
            "task_id": self.system_state.get("task_id", ""),
            "current_task": self.current_task.task_id if self.current_task else None,
            "queue_size": self.task_queue.qsize(),
            "system_state": {
                "safety_state": self.system_state.get("safety_state"),
                "quality_score": self.system_state.get("quality_score"),
                "error": self.system_state.get("error"),
            },
            "agents": {
                name: agent.get_status()
                for name, agent in self.agents.items()
            },
            "state_history": self.state_history[-20:],
        }

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """Get a specific agent by name.

        Args:
            name: Agent name (e.g., 'vision', 'motion').

        Returns:
            The agent instance, or None if not found.
        """
        return self.agents.get(name)

    def get_state_history(self) -> List[Dict[str, Any]]:
        """Get the full state transition history.

        Returns:
            List of state transition records.
        """
        return self.state_history

    # =========================================================================
    # Persistence
    # =========================================================================

    def save_state(self, path: str) -> bool:
        """Save the current orchestrator state to disk for recovery.

        Args:
            path: File path to save to.

        Returns:
            True if saved successfully.
        """
        try:
            state_data = {
                "state": self.state.value,
                "system_state": self.system_state,
                "state_history": self.state_history[-100:],
                "timestamp": time.time(),
            }
            with open(path, "w") as f:
                json.dump(state_data, f, indent=2, default=str)
            self._log(f"State saved to {path}")
            return True
        except Exception as e:
            self._log(f"Failed to save state: {e}", 40)
            return False

    def load_state(self, path: str) -> bool:
        """Load orchestrator state from disk for recovery.

        Args:
            path: File path to load from.

        Returns:
            True if loaded successfully.
        """
        try:
            with open(path, "r") as f:
                data = json.load(f)

            # Restore state
            state_str = data.get("state", "idle")
            try:
                self.state = OrchestratorState(state_str)
            except ValueError:
                self.state = OrchestratorState.IDLE

            self.system_state = data.get("system_state", self.system_state)
            self.state_history = data.get("state_history", [])

            self._log(f"State loaded from {path}")
            return True
        except Exception as e:
            self._log(f"Failed to load state: {e}", 40)
            return False

    # =========================================================================
    # Helpers
    # =========================================================================

    def _log(self, message: str, level: int = 20) -> None:
        """Log a message with the orchestrator prefix.

        Args:
            message: Log message.
            level: Log level (default INFO=20).
        """
        logging.log(level, f"[Orchestrator] {message}")

    def _build_task_result(self) -> Dict[str, Any]:
        """Build the final result dict for the current task.

        Returns:
            Result dict with task status and data.
        """
        raw_quality = self.system_state.get("quality_score", 0.0)
        quality_score = float(raw_quality) if isinstance(raw_quality, (int, float)) else 0.0

        return {
            "task_id": self.system_state.get("task_id", ""),
            "status": "completed" if self.state == OrchestratorState.DONE else "failed",
            "final_state": self.state.value,
            "quality_score": quality_score,
            "quality_decision": self.system_state.get("quality_decision", "unknown"),
            "error": self.system_state.get("error"),
            "state_history_length": len(self.state_history),
            "timestamp": time.time(),
        }