"""Task data models for the intelligent sampling robotic arm system."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Task execution status enum."""
    IDLE = "idle"
    PLANNING = "planning"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Bounds(BaseModel):
    """Sampling area bounds."""
    x_min: float = Field(..., description="Minimum X coordinate")
    x_max: float = Field(..., description="Maximum X coordinate")
    y_min: float = Field(..., description="Minimum Y coordinate")
    y_max: float = Field(..., description="Maximum Y coordinate")
    z: float = Field(default=0.0, description="Fixed Z height for sampling")


class TaskCreate(BaseModel):
    """Request model for creating a new task."""
    name: str = Field(..., min_length=1, max_length=128, description="Task name")
    strategy: str = Field(
        default="grid",
        description="Sampling strategy: grid, random, spiral, or adaptive"
    )
    bounds: Bounds = Field(..., description="Sampling area bounds")
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional strategy-specific parameters"
    )
    priority: int = Field(default=0, ge=0, le=10, description="Task priority (0-10)")


class TaskProgress(BaseModel):
    """Task progress information."""
    completed_samples: int = Field(default=0, description="Number of completed samples")
    total_samples: int = Field(default=0, description="Total planned samples")
    current_step: str = Field(default="", description="Description of current step")
    estimated_time: Optional[float] = Field(
        default=None,
        description="Estimated remaining time in seconds"
    )


class TaskResponse(BaseModel):
    """Response model for task information."""
    id: str = Field(..., description="Unique task identifier")
    name: str = Field(..., description="Task name")
    strategy: str = Field(..., description="Sampling strategy")
    status: TaskStatus = Field(..., description="Current task status")
    progress: TaskProgress = Field(
        default_factory=TaskProgress,
        description="Task progress details"
    )
    bounds: Optional[Bounds] = Field(default=None, description="Sampling area bounds")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = Field(default=None)