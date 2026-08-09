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