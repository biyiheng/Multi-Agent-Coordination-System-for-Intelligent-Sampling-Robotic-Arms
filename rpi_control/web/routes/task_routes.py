"""Task management API routes."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from rpi_control.web.models.task import TaskCreate, TaskProgress, TaskResponse, TaskStatus
from rpi_control.web.services import auth_service
from rpi_control.web.services.task_service import TaskService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/task", tags=["task"])

task_service = TaskService()


@router.post("/create", response_model=TaskResponse, status_code=201)
async def create_task(
    task_data: TaskCreate,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Create a new sampling task."""
    task = task_service.create_task(task_data)
    return task


@router.get("/list", response_model=List[TaskResponse])
async def list_tasks(
    status: Optional[str] = Query(None, description="Filter by task status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """List all tasks with optional status filter."""
    tasks = task_service.list_tasks(status_filter=status, limit=limit, offset=offset)
    return tasks


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Get task details by ID."""
    task = task_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/{task_id}/start")
async def start_task(
    task_id: str,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Start task execution."""
    result = task_service.start_task(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result


@router.post("/{task_id}/pause")
async def pause_task(
    task_id: str,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Pause task execution."""
    result = task_service.pause_task(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result


@router.post("/{task_id}/resume")
async def resume_task(
    task_id: str,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Resume a paused task."""
    result = task_service.resume_task(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Cancel a running or paused task."""
    result = task_service.cancel_task(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result


@router.get("/{task_id}/progress", response_model=TaskProgress)
async def get_task_progress(
    task_id: str,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Get task execution progress."""
    progress = task_service.get_progress(task_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Task not found")
    return progress


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Delete a task and its associated data."""
    result = task_service.delete_task(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "ok", "message": f"Task {task_id} deleted"}