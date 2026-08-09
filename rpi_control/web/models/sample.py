"""Sample data models for the intelligent sampling robotic arm system."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SampleCreate(BaseModel):
    """Request model for creating a sample record."""
    task_id: str = Field(..., description="Associated task ID")
    position: Dict[str, float] = Field(
        ...,
        description="Sample position {x, y, z}"
    )
    type: str = Field(default="unknown", description="Sample type")


class SampleQuality(BaseModel):
    """Sample quality assessment."""
    score: float = Field(default=0.0, ge=0.0, le=1.0, description="Quality score 0-1")
    defects: List[str] = Field(default_factory=list, description="Detected defects")
    dimensions: Dict[str, float] = Field(
        default_factory=dict,
        description="Measured dimensions"
    )
    passed: bool = Field(default=True, description="Whether quality check passed")


class SampleResponse(BaseModel):
    """Response model for sample information."""
    id: str = Field(..., description="Unique sample identifier")
    task_id: str = Field(..., description="Associated task ID")
    position: Dict[str, float] = Field(..., description="Sample position {x, y, z}")
    quality_score: float = Field(default=0.0, description="Overall quality score")
    quality: Optional[SampleQuality] = Field(
        default=None,
        description="Detailed quality assessment"
    )
    status: str = Field(default="pending", description="Sample status")
    image_url: Optional[str] = Field(default=None, description="Sample image URL")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: Optional[str] = Field(default=None, description="Additional notes")