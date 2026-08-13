"""
Base Agent Class for the Multi-Agent System.

Defines the abstract base class for all agents in the intelligent sampling
robotic arm system. Provides common functionality for state management,
logging, validation, and asynchronous processing.

All specialized agents (Sampling, Vision, Motion, Quality, Safety) inherit
from this base class and implement the abstract methods.
"""

import abc
import asyncio
import itertools
import logging
import math
import time
from collections import deque
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional, Set, Union
from dataclasses import dataclass, field


# Non-recoverable error types that should NOT be retried
NON_RECOVERABLE_ERRORS = (
    SyntaxError,
    ImportError,
    ModuleNotFoundError,
    NameError,
    AttributeError,
    TypeError,
    ValueError,
    KeyError,
    IndexError,
    MemoryError,
    SystemExit,
    KeyboardInterrupt,
)


class AgentStatus(Enum):
    """Status states for an agent."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"
    RECOVERING = "recovering"


@dataclass
class AgentConfig:
    """Configuration for a base agent.

    Attributes:
        name: Human-readable agent name.
        max_retries: Maximum number of retry attempts on failure.
        timeout_seconds: Timeout for agent operations.
        log_level: Logging level for this agent.
        enabled: Whether the agent is enabled.
        metadata: Arbitrary key-value metadata.
    """
    name: str = "base_agent"
    max_retries: int = 3
    timeout_seconds: float = 30.0
    log_level: int = logging.INFO
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseAgent(abc.ABC):
    """Abstract base class for all agents in the multi-agent system.

    Provides a common interface for agent lifecycle management, state
    processing, validation, and logging. Subclasses must implement the
    abstract methods to define agent-specific behavior.

    Lifecycle:
        initialize() -> process() -> validate() -> cleanup()

    Attributes:
        name: Agent name identifier.
        config: Agent configuration.
        status: Current agent status.
        logger: Logger instance for this agent.
        _state_history: Record of recent state changes.
        _pre_hooks: Functions to run before process().
        _post_hooks: Functions to run after process().
    """

    def __init__(self, name: str, config: Optional[AgentConfig] = None) -> None:
        """Initialize the base agent.

        Args:
            name: Unique agent name.
            config: Agent configuration (uses defaults if None).
        """
        self.name: str = name
        self.config: AgentConfig = config or AgentConfig(name=name)

        # Logging
        self.logger: logging.Logger = logging.getLogger(f"agent.{name}")
        self.logger.setLevel(self.config.log_level)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                f"[%(asctime)s] [{name}] %(levelname)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            ))
            self.logger.addHandler(handler)

        # State
        self.status: AgentStatus = AgentStatus.IDLE
        self._state_history: Deque[Dict[str, Any]] = deque(maxlen=100)
        self._max_history: int = 100

        # Hooks
        self._pre_hooks: List[Callable[["BaseAgent", Dict[str, Any]], None]] = []
        self._post_hooks: List[Callable[["BaseAgent", Dict[str, Any], Dict[str, Any]], None]] = []

        # Statistics
        self._process_count: int = 0
        self._error_count: int = 0
        self._total_process_time: float = 0.0

        # Loop Engineering: profiler (lazy-loaded when enabled)
        self._profiler: Any = None
        self._profiler_enabled: bool = False

    # =========================================================================
    # Abstract Methods
    # =========================================================================

    @abc.abstractmethod
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Main processing method. Must be implemented by subclasses.

        Args:
            state: Current system state dict.

        Returns:
            Updated state dict with processing results.
        """
        ...

    @abc.abstractmethod
    async def validate(self, state: Dict[str, Any]) -> bool:
        """Validate pre/post conditions. Must be implemented by subclasses.

        Args:
            state: Current system state dict.

        Returns:
            True if validation passes, False otherwise.
        """
        ...

    # =========================================================================
    # Lifecycle Methods
    # =========================================================================

    async def initialize(self) -> bool:
        """Initialize the agent before processing.

        Override in subclasses to perform setup (load models, connect hardware, etc.).

        Returns:
            True if initialization succeeded.
        """
        self.log("Initializing agent")
        self.status = AgentStatus.IDLE
        return True

    async def cleanup(self) -> None:
        """Cleanup resources after processing.

        Override in subclasses to release resources.
        """
        self.log("Cleaning up agent")
        self.status = AgentStatus.IDLE

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the full agent lifecycle: validate -> process -> validate.

        This is the primary entry point for running an agent. It handles
        retries, timeouts, and error recovery. When loop_engineering is
        enabled, profiling spans are automatically recorded.

        Args:
            state: Input state dict.

        Returns:
            Output state dict with processing results.
        """
        if not self.config.enabled:
            self.log("Agent is disabled, skipping", logging.WARNING)
            return state

        # Enforce underlying decision-making constraints (guardrail).
        constraint_error = self.check_constraints(state)
        if constraint_error is not None:
            self.log(constraint_error, logging.ERROR)
            self.status = AgentStatus.ERROR
            state["error"] = constraint_error
            return state

        self.status = AgentStatus.RUNNING
        self.log(f"Starting run with state keys: {list(state.keys())}")

        # Start profiler span if enabled
        if self._profiler_enabled and self._profiler is not None:
            self._profiler.start_span("run")

        # Pre-validation
        if not await self.validate(state):
            self.log("Pre-validation failed", logging.ERROR)
            self.status = AgentStatus.ERROR
            state["error"] = "Pre-validation failed"
            if self._profiler_enabled and self._profiler is not None:
                self._profiler.end_span("run")
            return state

        # Run pre-hooks
        for hook in self._pre_hooks:
            try:
                hook(self, state)
            except Exception as e:
                self.log(f"Pre-hook failed: {e}", logging.WARNING)

        # Process with retries
        result = state
        for attempt in range(self.config.max_retries + 1):
            try:
                # Start process span
                if self._profiler_enabled and self._profiler is not None:
                    self._profiler.start_span("process")

                start_time = time.perf_counter()
                result = await asyncio.wait_for(
                    self.process(state),
                    timeout=self.config.timeout_seconds,
                )
                elapsed = time.perf_counter() - start_time
                self._process_count += 1
                self._total_process_time += elapsed

                # End process span
                if self._profiler_enabled and self._profiler is not None:
                    self._profiler.end_span("process", {"attempt": attempt + 1, "success": True})
                break
            except asyncio.TimeoutError:
                self.log(f"Timeout on attempt {attempt + 1}", logging.WARNING)
                if self._profiler_enabled and self._profiler is not None:
                    self._profiler.end_span("process", {"attempt": attempt + 1, "timeout": True})
                if attempt >= self.config.max_retries:
                    self.status = AgentStatus.ERROR
                    result["error"] = f"Timeout after {self.config.max_retries + 1} attempts"
            except NON_RECOVERABLE_ERRORS as e:
                # Non-recoverable errors: fail immediately without retry
                self._error_count += 1
                self.log(f"Non-recoverable error: {type(e).__name__}: {e}", logging.ERROR)
                self.status = AgentStatus.ERROR
                result["error"] = f"Non-recoverable: {type(e).__name__}: {e}"
                if self._profiler_enabled and self._profiler is not None:
                    self._profiler.end_span("process", {"attempt": attempt + 1, "non_recoverable": True})
                break
            except Exception as e:
                self._error_count += 1
                self.log(f"Error on attempt {attempt + 1}: {e}", logging.ERROR)
                if self._profiler_enabled and self._profiler is not None:
                    self._profiler.end_span("process", {"attempt": attempt + 1, "error": str(e)[:100]})
                if attempt >= self.config.max_retries:
                    self.status = AgentStatus.ERROR
                    result["error"] = str(e)
                else:
                    # Exponential backoff: 0.5s, 1.0s, 2.0s...
                    backoff = 0.5 * (2 ** attempt)
                    await asyncio.sleep(backoff)

        # Post-validation
        if self.status != AgentStatus.ERROR:
            if not await self.validate(result):
                self.log("Post-validation failed", logging.WARNING)
                # Don't change status; allow caller to decide

        # Run post-hooks
        for hook in self._post_hooks:
            try:
                hook(self, state, result)
            except Exception as e:
                self.log(f"Post-hook failed: {e}", logging.WARNING)

        # Enforce output constraints (guardrail) on the produced decision, so
        # the "符合事实逻辑 / 常识性要求" clauses also cover the OUTPUT and not
        # only the input. An agent must not return physically-impossible values
        # (NaN/Inf/out-of-range) even after processing.
        out_constraint = self.check_constraints(result)
        if out_constraint is not None:
            self.log(out_constraint, logging.ERROR)
            self.status = AgentStatus.ERROR
            result["error"] = out_constraint

        # Record state
        self._record_state(result)

        if self.status != AgentStatus.ERROR:
            self.status = AgentStatus.COMPLETED

        # End profiler span
        if self._profiler_enabled and self._profiler is not None:
            self._profiler.end_span("run")

        return result

    def enable_profiler(self, profiler: Any = None) -> None:
        """Enable the loop engineering profiler for this agent.

        Args:
            profiler: Optional AgentProfiler instance. If None, one is
                      created automatically from loop_engineering.profiler.
        """
        if profiler is not None:
            self._profiler = profiler
        elif self._profiler is None:
            from loop_engineering.profiler import AgentProfiler
            self._profiler = AgentProfiler(self.name)
        self._profiler_enabled = True

    def disable_profiler(self) -> None:
        """Disable the loop engineering profiler."""
        self._profiler_enabled = False

    def get_profiler(self) -> Any:
        """Get the profiler instance, or None if not enabled.

        Returns:
            AgentProfiler instance or None.
        """
        return self._profiler if self._profiler_enabled else None

    # =========================================================================
    # Logging
    # =========================================================================

    def log(self, message: str, level: int = logging.INFO) -> None:
        """Log a message with the agent's logger.

        Args:
            message: Log message.
            level: Logging level (default INFO).
        """
        self.logger.log(level, message)

    # =========================================================================
    # Status
    # =========================================================================

    def get_status(self) -> Dict[str, Any]:
        """Get the current agent status and statistics.

        Returns:
            Dict with status, process count, error count, and timing info.
        """
        avg_time = (
            self._total_process_time / self._process_count
            if self._process_count > 0
            else 0.0
        )
        return {
            "name": self.name,
            "status": self.status.value,
            "enabled": self.config.enabled,
            "process_count": self._process_count,
            "error_count": self._error_count,
            "avg_process_time_ms": round(avg_time * 1000, 2),
            "total_process_time_s": round(self._total_process_time, 2),
        }

    def is_available(self) -> bool:
        """Check if the agent is available for processing.

        Returns:
            True if the agent is idle or completed and enabled.
        """
        return (
            self.config.enabled
            and self.status in (AgentStatus.IDLE, AgentStatus.COMPLETED)
        )

    def reset(self) -> None:
        """Reset the agent to its initial state."""
        self.status = AgentStatus.IDLE
        self._state_history = deque(maxlen=self._max_history)  # fresh deque
        self._process_count = 0
        self._error_count = 0
        self._total_process_time = 0.0

    # =========================================================================
    # Hooks
    # =========================================================================

    def add_pre_hook(self, hook: Callable[["BaseAgent", Dict[str, Any]], None]) -> None:
        """Register a function to run before process().

        Args:
            hook: Callable taking (agent, state).
        """
        self._pre_hooks.append(hook)

    def add_post_hook(
        self,
        hook: Callable[["BaseAgent", Dict[str, Any], Dict[str, Any]], None],
    ) -> None:
        """Register a function to run after process().

        Args:
            hook: Callable taking (agent, input_state, output_state).
        """
        self._post_hooks.append(hook)

    # =========================================================================
    # Underlying Decision-Making Constraints (guardrail)
    # =========================================================================

    def check_constraints(self, state: Dict[str, Any]) -> Optional[str]:
        """Enforce the underlying decision-making constraints on a state dict.

        This is a *framework-level* guardrail applied to every agent on every
        ``run()``.  Its purpose is to make sure no agent can:

        - **不可擅自决策 (no unauthorized decisions)**: a decision that carries an
          explicit ``authorization_required`` marker must not be auto-committed
          unless an ``authorization`` token has actually been provided.
        - **不可不懂装懂 (no pretending to know)**: a decision must not be based on
          data explicitly flagged as unverified / assumed (``assumed`` or
          ``unverified_assumptions``).
        - **一切必须符合事实逻辑 (must conform to factual logic)**: numeric state
          values must be finite — NaN/Inf are never physically real.
        - **辅助决策必须满足常识性要求 (common-sense sanity)**: any obviously
          impossible value (e.g. negative distance, out-of-range PWM) is rejected.

        Subclasses may call this directly or rely on ``run()`` which invokes it
        automatically before processing.

        Args:
            state: The input/output state dict to validate.

        Returns:
            An error string describing the first violated constraint, or None
            if all constraints are satisfied.
        """
        # --- 事实逻辑: finite numeric values (never NaN/Inf) ---
        # 递归扫描: 代理实际返回的物理量常嵌套于 dict/list 中
        # (vision_result / motion_result / sampling_points), 仅检查顶层
        # float 会漏掉真实运行场景中的非法值。
        non_finite = self._scan_non_finite(state)
        if non_finite is not None:
            return (
                f"Constraint violated (factual logic): field '{non_finite}' is "
                "NaN/Inf, which is not physically real"
            )

        # --- 不可不懂装懂: no decisions based on unverified assumptions ---
        assumed = state.get("assumed") or state.get("unverified_assumptions")
        if assumed:
            return (
                f"Constraint violated (no pretending to know): decision relies "
                f"on unverified assumptions: {assumed}"
            )

        # --- 不可擅自决策: authorized decisions only ---
        if state.get("authorization_required") and not state.get("authorization"):
            return (
                "Constraint violated (unauthorized decision): authorization is "
                "required but no authorization token was provided"
            )

        # --- 常识性要求: common-sense physical sanity ---
        if "joint_positions" in state and isinstance(state["joint_positions"], dict):
            for joint, angle in state["joint_positions"].items():
                if isinstance(angle, (int, float)) and abs(angle) > 360.0:
                    return (
                        f"Constraint violated (common-sense): joint '{joint}' "
                        f"angle {angle}° exceeds a physically plausible range"
                    )

        # --- 常识性要求: servo PWM range (500..2500 us is the physical span) ---
        pwm_err = self._check_pwm_range(state)
        if pwm_err is not None:
            return pwm_err

        return None

    # =========================================================================
    # Constraint Helper Checks (recursive, covers nested runtime data)
    # =========================================================================

    def _scan_non_finite(self, value: Any, path: str = "") -> Optional[str]:
        """Recursively search for NaN/Inf in a nested state structure.

        Args:
            value: The current value to inspect (dict / list / scalar).
            path: Dotted path for error reporting.

        Returns:
            The path of the first non-finite value, or None.
        """
        if isinstance(value, dict):
            for k, v in value.items():
                p = f"{path}.{k}" if path else str(k)
                hit = self._scan_non_finite(v, p)
                if hit is not None:
                    return hit
            return None
        if isinstance(value, (list, tuple)):
            for i, v in enumerate(value):
                p = f"{path}[{i}]"
                hit = self._scan_non_finite(v, p)
                if hit is not None:
                    return hit
            return None
        if isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                return path or "<value>"
        return None

    # 舵机 PWM 物理范围 (μs): 超出该范围必然无法驱动真实舵机
    SERVO_PWM_MIN = 500
    SERVO_PWM_MAX = 2500

    def _check_pwm_range(self, state: Dict[str, Any]) -> Optional[str]:
        """Validate servo PWM values are within the physical 500..2500 μs range.

        PWM 通常以 ``pwm`` 字段 (dict: 关节->PWM) 或嵌套于
        motion_result / servo_cmd 中出现。超出范围的 PWM 属于明显违背
        常识性物理约束的值。

        Args:
            state: The state dict to validate.

        Returns:
            An error string, or None if all PWM values are in range.
        """
        def walk(value: Any, path: str = "") -> Optional[str]:
            if isinstance(value, dict):
                # 关节字典形如 {joint_0: 1500}
                if path.endswith("pwm") or "pwm" in path:
                    for k, v in value.items():
                        if isinstance(v, (int, float)) and not isinstance(v, bool):
                            if not (self.SERVO_PWM_MIN <= v <= self.SERVO_PWM_MAX):
                                return (
                                    f"Constraint violated (common-sense): PWM "
                                    f"{v} for '{k}' ({path}) is outside the "
                                    f"physical range {self.SERVO_PWM_MIN}.."
                                    f"{self.SERVO_PWM_MAX} μs"
                                )
                for k, v in value.items():
                    p = f"{path}.{k}" if path else str(k)
                    hit = walk(v, p)
                    if hit is not None:
                        return hit
            elif isinstance(value, (list, tuple)):
                for i, v in enumerate(value):
                    p = f"{path}[{i}]"
                    hit = walk(v, p)
                    if hit is not None:
                        return hit
            return None
        return walk(state)

    # =========================================================================
    # Internal
    # =========================================================================

    def _record_state(self, state: Dict[str, Any]) -> None:
        """Record a state snapshot in the history.

        Uses a bounded deque for O(1) append with automatic trimming,
        avoiding the O(n) list slicing overhead of the previous approach.

        Args:
            state: State dict to record.
        """
        snapshot = {
            "timestamp": time.time(),
            "status": self.status.value,
            "state_keys": list(state.keys()),
            "error": state.get("error"),
        }
        # deque with maxlen handles automatic trimming in O(1)
        self._state_history.append(snapshot)

    def get_state_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent state history using O(k) memory where k=limit.

        Uses itertools.islice to avoid converting the entire deque to a list
        first, which would be O(n) for n items. Now O(k) for k=limit.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of state snapshots (most recent first).
        """
        total = len(self._state_history)
        start = max(0, total - limit)
        return list(itertools.islice(self._state_history, start, total))


def validate_state(required_keys: Optional[List[str]] = None, forbidden_keys: Optional[List[str]] = None):
    """Decorator to validate state before processing.

    Args:
        required_keys: Keys that must be present in the state.
        forbidden_keys: Keys that must not be present in the state.

    Returns:
        Decorator function.
    """
    def decorator(func):
        async def wrapper(self: BaseAgent, state: Dict[str, Any]) -> Dict[str, Any]:
            if required_keys:
                missing = [k for k in required_keys if k not in state]
                if missing:
                    self.log(f"Missing required state keys: {missing}", logging.ERROR)
                    state["error"] = f"Missing required keys: {missing}"
                    return state
            if forbidden_keys:
                found = [k for k in forbidden_keys if k in state]
                if found:
                    self.log(f"Forbidden state keys present: {found}", logging.ERROR)
                    state["error"] = f"Forbidden keys: {found}"
                    return state
            return await func(self, state)
        return wrapper
    return decorator


def log_execution(func):
    """Decorator to log method execution with timing.

    Args:
        func: Async method to decorate.

    Returns:
        Decorated async method.
    """
    async def wrapper(self: BaseAgent, *args, **kwargs):
        self.log(f"Entering {func.__name__}")
        start = time.perf_counter()
        try:
            result = await func(self, *args, **kwargs)
            elapsed = (time.perf_counter() - start) * 1000
            self.log(f"Exiting {func.__name__} ({elapsed:.1f}ms)")
            return result
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            self.log(f"Error in {func.__name__} ({elapsed:.1f}ms): {e}", logging.ERROR)
            raise
    return wrapper