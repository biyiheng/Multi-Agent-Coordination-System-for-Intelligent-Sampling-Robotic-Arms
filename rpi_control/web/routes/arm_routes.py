"""Arm control API routes."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from rpi_control.web.models.status import ArmStatus, EndEffectorPose, JointPositions, SafetyStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/arm", tags=["arm"])

# Mock state for development
_mock_arm_status = ArmStatus()
_mock_workspace_points = [
    {"x": 200, "y": 0, "z": 50},
    {"x": 200, "y": 100, "z": 50},
    {"x": 200, "y": -100, "z": 50},
    {"x": 300, "y": 0, "z": 50},
    {"x": 300, "y": 100, "z": 50},
    {"x": 300, "y": -100, "z": 50},
    {"x": 250, "y": 0, "z": 100},
    {"x": 250, "y": 0, "z": 20},
]


@router.get("/status", response_model=ArmStatus)
async def get_arm_status():
    """Get the current arm status including joint positions and safety."""
    return _mock_arm_status


@router.get("/position", response_model=JointPositions)
async def get_joint_positions():
    """Get current joint positions."""
    return _mock_arm_status.joint_positions


@router.get("/pose", response_model=EndEffectorPose)
async def get_end_effector_pose():
    """Get current end-effector pose in Cartesian space."""
    return _mock_arm_status.ee_pose


@router.post("/move/joint")
async def move_single_joint(data: Dict[str, Any]):
    """Move a single joint to the specified position.

    Request body: {joint_id: int, position: float, time: float}
    """
    joint_id = data.get("joint_id")
    position = data.get("position")
    move_time = data.get("time", 1.0)

    if joint_id is None or position is None:
        raise HTTPException(status_code=400, detail="joint_id and position are required")

    # Validate joint_id is an integer in range
    try:
        joint_id = int(joint_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="joint_id must be an integer")

    if not (0 <= joint_id <= 5):
        raise HTTPException(status_code=400, detail="joint_id must be between 0 and 5")

    logger.info(f"Moving joint {joint_id} to {position} degrees in {move_time}s")
    _mock_arm_status.is_moving = True

    # Update mock joint position (0-based, joint_0...joint_5)
    joint_attr = f"joint_{joint_id}"
    if hasattr(_mock_arm_status.joint_positions, joint_attr):
        setattr(_mock_arm_status.joint_positions, joint_attr, position)

    return {"status": "ok", "message": f"Joint {joint_id} moving to {position} degrees"}


@router.post("/move/cartesian")
async def move_cartesian(data: Dict[str, Any]):
    """Move end-effector in Cartesian space.

    Request body: {x, y, z, roll, pitch, yaw}
    """
    logger.info(f"Cartesian move: {data}")
    _mock_arm_status.is_moving = True

    for key in ("x", "y", "z", "roll", "pitch", "yaw"):
        if key in data and hasattr(_mock_arm_status.ee_pose, key):
            setattr(_mock_arm_status.ee_pose, key, data[key])

    return {"status": "ok", "message": "Moving to target pose"}


@router.post("/move/all")
async def move_all_joints(data: Dict[str, Any]):
    """Move all joints simultaneously.

    Request body: {positions: [float x 6], time: float}
    """
    positions = data.get("positions", [])
    move_time = data.get("time", 1.0)

    if len(positions) != 6:
        raise HTTPException(status_code=400, detail="Exactly 6 joint positions required")

    for i, pos in enumerate(positions):
        joint_attr = f"joint_{i}"
        if hasattr(_mock_arm_status.joint_positions, joint_attr):
            setattr(_mock_arm_status.joint_positions, joint_attr, pos)

    _mock_arm_status.is_moving = True
    logger.info(f"Moving all joints: {positions} in {move_time}s")
    return {"status": "ok", "message": "All joints moving"}


@router.post("/stop")
async def stop_arm():
    """Soft stop - decelerate and stop the arm."""
    _mock_arm_status.is_moving = False
    logger.info("Arm soft stop")
    return {"status": "ok", "message": "Arm stopped"}


@router.post("/estop")
async def emergency_stop():
    """Emergency stop - immediately cut power."""
    _mock_arm_status.is_moving = False
    _mock_arm_status.safety_status.emergency_stop = True
    logger.warning("EMERGENCY STOP activated")
    return {"status": "ok", "message": "Emergency stop activated"}


@router.post("/origin")
async def return_to_origin():
    """Return the arm to origin/home position."""
    _mock_arm_status.joint_positions = JointPositions()
    _mock_arm_status.ee_pose = EndEffectorPose()
    _mock_arm_status.is_homed = True
    _mock_arm_status.is_moving = True
    logger.info("Returning to origin")
    return {"status": "ok", "message": "Returning to origin"}


@router.post("/gripper/open")
async def open_gripper():
    """Open the gripper."""
    _mock_arm_status.gripper_state = "open"
    _mock_arm_status.gripper_force = 0.0
    logger.info("Gripper opened")
    return {"status": "ok", "message": "Gripper opened"}


@router.post("/gripper/close")
async def close_gripper(data: Dict[str, Any]):
    """Close the gripper with specified force.

    Request body: {force: float}
    """
    force = data.get("force", 50.0)
    _mock_arm_status.gripper_state = "closed"
    _mock_arm_status.gripper_force = force
    logger.info(f"Gripper closed with force {force}")
    return {"status": "ok", "message": f"Gripper closed (force: {force})"}


@router.get("/workspace")
async def get_workspace():
    """Get workspace boundary points."""
    return {"status": "ok", "points": _mock_workspace_points}