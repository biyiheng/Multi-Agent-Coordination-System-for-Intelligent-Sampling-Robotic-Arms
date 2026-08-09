"""
Error handling module for the intelligent sampling robotic arm system.

Defines custom exception classes, retry decorators, and error notification
utilities for robust error management across the system.
"""

import asyncio
import functools
import time
import traceback
from collections import deque
from typing import Any, Callable, Optional, Type, TypeVar, Union

from .logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Custom Exception Hierarchy
# ---------------------------------------------------------------------------


class SystemError(Exception):
    """Base exception for all system errors."""

    def __init__(self, message: str, *args: Any, code: Optional[str] = None):
        """
        Initialize the base system error.

        Args:
            message: Human-readable error description.
            *args: Additional positional arguments passed to Exception.
            code: Optional machine-readable error code.
        """
        super().__init__(message, *args)
        self.message = message
        self.code = code

    def __str__(self) -> str:
        base = self.message
        if self.code:
            base = f"[{self.code}] {base}"
        return base


class HardwareError(SystemError):
    """Raised when a hardware-level error occurs (e.g., UART failure, sensor fault)."""

    pass


class CommunicationError(SystemError):
    """
    Raised when communication with a device fails.

    This includes timeouts, checksum errors, and protocol violations.
    """

    pass


class SafetyError(SystemError):
    """
    Raised for safety violations.

    This includes emergency stop triggers, joint limit violations, and
    workspace boundary infringements.
    """

    pass


class KinematicsError(SystemError):
    """Raised when kinematic calculations fail (e.g., unreachable pose, singularities)."""

    pass


class VisionError(SystemError):
    """Raised when vision processing fails (e.g., detection failure, camera error)."""

    pass


class ConfigurationError(SystemError):
    """Raised for configuration-related errors."""

    pass


class InitializationError(SystemError):
    """Raised when system initialization fails."""

    pass


# ---------------------------------------------------------------------------
# Retry Decorators
# ---------------------------------------------------------------------------

F = TypeVar("F", bound=Callable[..., Any])


def retry(
    max_attempts: int = 3,
    delay: float = 0.5,
    backoff: float = 2.0,
    exceptions: Union[Type[Exception], tuple[Type[Exception], ...]] = Exception,
    on_retry: Optional[Callable[[Exception, int], None]] = None,
) -> Callable[[F], F]:
    """
    Decorator that retries a function on specified exceptions with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts (including the initial call).
        delay: Initial delay between retries in seconds.
        backoff: Multiplier for delay after each retry.
        exceptions: Exception type(s) that trigger a retry.
        on_retry: Optional callback invoked on each retry: on_retry(exception, attempt).

    Returns:
        Decorated function with retry logic.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            last_exception: Optional[Exception] = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except asyncio.CancelledError:
                    # Do not retry on CancelledError - always propagate immediately
                    raise
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        logger.warning(
                            f"Attempt {attempt}/{max_attempts} for '{func.__name__}' "
                            f"failed: {e}. Retrying in {current_delay:.1f}s..."
                        )
                        if on_retry:
                            on_retry(e, attempt)
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"All {max_attempts} attempts for '{func.__name__}' "
                            f"failed. Last error: {e}"
                        )

            raise last_exception  # type: ignore[misc]

        return wrapper  # type: ignore[return-value]

    return decorator


def async_retry(
    max_attempts: int = 3,
    delay: float = 0.5,
    backoff: float = 2.0,
    exceptions: Union[Type[Exception], tuple[Type[Exception], ...]] = Exception,
    on_retry: Optional[Callable[[Exception, int], None]] = None,
) -> Callable[[F], F]:
    """
    Decorator that retries an async function on specified exceptions with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts (including the initial call).
        delay: Initial delay between retries in seconds.
        backoff: Multiplier for delay after each retry.
        exceptions: Exception type(s) that trigger a retry.
        on_retry: Optional callback invoked on each retry: on_retry(exception, attempt).

    Returns:
        Decorated async function with retry logic.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            last_exception: Optional[Exception] = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except asyncio.CancelledError:
                    # Do not retry on CancelledError - always propagate immediately
                    raise
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        logger.warning(
                            f"Attempt {attempt}/{max_attempts} for '{func.__name__}' "
                            f"failed: {e}. Retrying in {current_delay:.1f}s..."
                        )
                        if on_retry:
                            on_retry(e, attempt)
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"All {max_attempts} attempts for '{func.__name__}' "
                            f"failed. Last error: {e}"
                        )

            raise last_exception  # type: ignore[misc]

        return wrapper  # type: ignore[return-value]

    return decorator


# ---------------------------------------------------------------------------
# Error Notification Utilities
# ---------------------------------------------------------------------------


class ErrorNotifier:
    """Collects and reports errors for monitoring and alerting.

    Thread-safe: Uses asyncio.Lock for concurrent access protection.
    Uses collections.deque for O(1) truncation instead of O(n) list slicing.
    """

    def __init__(self, max_history: int = 100):
        """
        Initialize the error notifier.

        Args:
            max_history: Maximum number of error records to keep in memory.
        """
        self._errors: deque = deque(maxlen=max_history)
        self._max_history = max_history
        self._error_count: dict[str, int] = {}
        self._lock: asyncio.Lock = asyncio.Lock()

    async def report(self, error: Exception, context: Optional[dict[str, Any]] = None) -> None:
        """
        Log and record an error with optional context.

        Thread-safe: protected by asyncio.Lock.

        Args:
            error: The exception that occurred.
            context: Optional dictionary of contextual information.
        """
        error_type = type(error).__name__
        error_record = {
            "timestamp": time.time(),
            "type": error_type,
            "message": str(error),
            "traceback": traceback.format_exc(),
            "context": context or {},
        }

        async with self._lock:
            self._errors.append(error_record)
            # deque with maxlen auto-truncates, no need for manual slicing
            self._error_count[error_type] = self._error_count.get(error_type, 0) + 1

        if isinstance(error, SafetyError):
            logger.critical(f"SAFETY ERROR: {error}")
        elif isinstance(error, (HardwareError, CommunicationError)):
            logger.error(f"HARDWARE ERROR: {error}")
        else:
            logger.error(f"ERROR [{error_type}]: {error}")

    async def get_recent_errors(self, count: int = 10) -> list[dict[str, Any]]:
        """
        Get the most recent error records.

        Thread-safe: protected by asyncio.Lock.

        Args:
            count: Number of recent errors to return.

        Returns:
            List of error record dictionaries.
        """
        async with self._lock:
            items = list(self._errors)
        return items[-count:]

    def get_error_summary(self) -> dict[str, int]:
        """
        Get a summary of error counts by type.

        Returns:
            Dictionary mapping error type names to occurrence counts.
        """
        return dict(self._error_count)

    def clear(self) -> None:
        """Clear all recorded errors and counts."""
        self._errors.clear()
        self._error_count.clear()


# Global error notifier instance
error_notifier = ErrorNotifier()