"""Arm control API routes.

机械臂状态 (关节位置 / 末端位姿 / 夹爪 / 安全状态) 通过 ConfigRepository
持久化到数据库 (system_config 表, key="arm_status"), 保证重启后状态可恢复。
"""

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from rpi_control.database.repository import (
    ConfigRepository,
    LogRepository,
    db_manager,
)
from rpi_control.web.models.status import ArmStatus, EndEffectorPose, JointPositions, SafetyStatus
from rpi_control.web.services import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/arm", tags=["arm"])

_ARM_STATUS_KEY = "arm_status"

# Mock workspace points for development
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


def _load_arm_status() -> ArmStatus:
    """Load the persisted arm status from the database (or use defaults)."""
    with db_manager.get_session() as session:
        saved = ConfigRepository.get(session, _ARM_STATUS_KEY)
    if not saved or not isinstance(saved, dict):
        return ArmStatus()
    try:
        return ArmStatus(**saved)
    except Exception as e:  # pragma: no cover - defensive fallback
        logger.warning(f"Failed to restore arm status from DB: {e}")
        return ArmStatus()


def _save_arm_status(status: ArmStatus) -> None:
    """Persist the current arm status to the database."""
    with db_manager.get_session() as session:
        ConfigRepository.set(session, _ARM_STATUS_KEY, status.model_dump())


def _reset_arm_status() -> ArmStatus:
    """Reset to defaults and persist."""
    status = ArmStatus()
    _save_arm_status(status)
    return status


@router.get("/status", response_model=ArmStatus)
async def get_arm_status():
    """Get the current arm status including joint positions and safety."""
    return _load_arm_status()


@router.get("/position", response_model=JointPositions)
async def get_joint_positions():
    """Get current joint positions."""
    return _load_arm_status().joint_positions


@router.get("/pose", response_model=EndEffectorPose)
async def get_end_effector_pose():
    """Get current end-effector pose in Cartesian space."""
    return _load_arm_status().ee_pose


@router.post("/move/joint")
async def move_single_joint(
    data: Dict[str, Any],
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
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

    status = _load_arm_status()
    status.is_moving = True

    # Update joint position (1-based joint_1...joint_6)
    joint_attr = f"joint_{joint_id + 1}"
    if hasattr(status.joint_positions, joint_attr):
        setattr(status.joint_positions, joint_attr, position)
    _save_arm_status(status)

    with db_manager.get_session() as session:
        LogRepository.create(session, "arm_joint_move", {
            "joint_id": joint_id, "position": position, "time": move_time,
        })

    return {"status": "ok", "message": f"Joint {joint_id} moving to {position} degrees"}


@router.post("/move/cartesian")
async def move_cartesian(
    data: Dict[str, Any],
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Move end-effector in Cartesian space.

    Request body: {x, y, z, roll, pitch, yaw}
    """
    logger.info(f"Cartesian move: {data}")
    status = _load_arm_status()
    status.is_moving = True

    for key in ("x", "y", "z", "roll", "pitch", "yaw"):
        if key in data and hasattr(status.ee_pose, key):
            setattr(status.ee_pose, key, data[key])
    _save_arm_status(status)

    with db_manager.get_session() as session:
        LogRepository.create(session, "arm_cartesian_move", data)

    return {"status": "ok", "message": "Moving to target pose"}


@router.post("/move/all")
async def move_all_joints(
    data: Dict[str, Any],
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Move all joints simultaneously.

    Request body: {positions: [float x 6], time: float}
    """
    positions = data.get("positions", [])
    move_time = data.get("time", 1.0)

    if len(positions) != 6:
        raise HTTPException(status_code=400, detail="Exactly 6 joint positions required")

    status = _load_arm_status()
    for i, pos in enumerate(positions):
        joint_attr = f"joint_{i + 1}"
        if hasattr(status.joint_positions, joint_attr):
            setattr(status.joint_positions, joint_attr, pos)

    status.is_moving = True
    _save_arm_status(status)

    logger.info(f"Moving all joints: {positions} in {move_time}s")
    return {"status": "ok", "message": "All joints moving"}


@router.post("/stop")
async def stop_arm(
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Soft stop - decelerate and stop the arm."""
    status = _load_arm_status()
    status.is_moving = False
    _save_arm_status(status)
    logger.info("Arm soft stop")
    return {"status": "ok", "message": "Arm stopped"}


@router.post("/estop")
async def emergency_stop(
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Emergency stop - immediately cut power."""
    status = _load_arm_status()
    status.is_moving = False
    status.safety_status.emergency_stop = True
    _save_arm_status(status)
    logger.warning("EMERGENCY STOP activated")
    return {"status": "ok", "message": "Emergency stop activated"}


@router.post("/estop/clear")
async def clear_emergency_stop(
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Clear the emergency stop state after manual reset."""
    status = _load_arm_status()
    status.safety_status.emergency_stop = False
    _save_arm_status(status)
    logger.info("Emergency stop cleared")
    return {"status": "ok", "message": "Emergency stop cleared"}


@router.post("/origin")
async def return_to_origin(
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Return the arm to origin/home position."""
    status = _load_arm_status()
    status.joint_positions = JointPositions()
    status.ee_pose = EndEffectorPose()
    status.is_homed = True
    status.is_moving = True
    _save_arm_status(status)
    logger.info("Returning to origin")
    return {"status": "ok", "message": "Returning to origin"}


@router.post("/gripper/open")
async def open_gripper(
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Open the gripper."""
    status = _load_arm_status()
    status.gripper_state = "open"
    status.gripper_force = 0.0
    _save_arm_status(status)
    logger.info("Gripper opened")
    return {"status": "ok", "message": "Gripper opened"}


@router.post("/gripper/close")
async def close_gripper(
    data: Dict[str, Any],
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Close the gripper with specified force.

    Request body: {force: float}
    """
    force = data.get("force", 50.0)
    status = _load_arm_status()
    status.gripper_state = "closed"
    status.gripper_force = force
    _save_arm_status(status)
    logger.info(f"Gripper closed with force {force}")
    return {"status": "ok", "message": f"Gripper closed (force: {force})"}


@router.get("/workspace")
async def get_workspace():
    """Get workspace boundary points."""
    return {"status": "ok", "points": _mock_workspace_points}
