"""Status data models for the intelligent sampling robotic arm system."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SafetyLevel(str, Enum):
    """Safety level enum."""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


class JointPositions(BaseModel):
    """Joint positions for a 6-DOF arm."""
    joint_1: float = Field(default=0.0, description="Base rotation (degrees)")
    joint_2: float = Field(default=0.0, description="Shoulder (degrees)")
    joint_3: float = Field(default=0.0, description="Elbow (degrees)")
    joint_4: float = Field(default=0.0, description="Wrist rotation (degrees)")
    joint_5: float = Field(default=0.0, description="Wrist pitch (degrees)")
    joint_6: float = Field(default=0.0, description="Wrist roll (degrees)")


class EndEffectorPose(BaseModel):
    """End-effector pose in Cartesian space."""
    x: float = Field(default=0.0, description="X position (mm)")
    y: float = Field(default=0.0, description="Y position (mm)")
    z: float = Field(default=0.0, description="Z position (mm)")
    roll: float = Field(default=0.0, description="Roll angle (degrees)")
    pitch: float = Field(default=0.0, description="Pitch angle (degrees)")
    yaw: float = Field(default=0.0, description="Yaw angle (degrees)")


class SafetyStatus(BaseModel):
    """Safety system status."""
    level: SafetyLevel = Field(default=SafetyLevel.NORMAL)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    emergency_stop: bool = Field(default=False)
    collision_detected: bool = Field(default=False)
    limit_switch_triggered: bool = Field(default=False)


class ArmStatus(BaseModel):
    """Arm status information."""
    joint_positions: JointPositions = Field(default_factory=JointPositions)
    ee_pose: EndEffectorPose = Field(default_factory=EndEffectorPose)
    is_moving: bool = Field(default=False)
    is_homed: bool = Field(default=False)
    gripper_state: str = Field(default="unknown")
    gripper_force: float = Field(default=0.0)
    safety_status: SafetyStatus = Field(default_factory=SafetyStatus)
    temperature: float = Field(default=25.0, description="Motor temperature (C)")


class SensorData(BaseModel):
    """Sensor readings."""
    temperature: float = Field(default=25.0, description="Ambient temperature (C)")
    humidity: float = Field(default=50.0, description="Humidity (%)")
    distance: float = Field(default=0.0, description="Distance sensor (mm)")
    voltage: float = Field(default=12.0, description="System voltage (V)")
    current: float = Field(default=0.0, description="System current (A)")
    pressure: Optional[float] = Field(default=None, description="Pressure sensor (kPa)")
    additional: Dict[str, Any] = Field(default_factory=dict)


class VisionStatus(BaseModel):
    """Vision system status."""
    camera_connected: bool = Field(default=False)
    camera_resolution: str = Field(default="640x480")
    fps: float = Field(default=0.0)
    last_detection: Optional[datetime] = Field(default=None)
    active_filters: List[str] = Field(default_factory=list)


class SystemStatus(BaseModel):
    """Full system status aggregation."""
    arm: ArmStatus = Field(default_factory=ArmStatus)
    vision: VisionStatus = Field(default_factory=VisionStatus)
    sensors: SensorData = Field(default_factory=SensorData)
    safety: SafetyStatus = Field(default_factory=SafetyStatus)
    uptime: float = Field(default=0.0, description="System uptime in seconds")
    version: str = Field(default="1.0.0", description="System version")
    current_task_id: Optional[str] = Field(default=None)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))