"""Task management service for the intelligent sampling robotic arm system."""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from rpi_control.database.repository import (
    DatabaseManager, TaskRepository, SampleRepository, LogRepository, db_manager
)
from rpi_control.web.models.task import (
    TaskCreate, TaskProgress, TaskResponse, TaskStatus, Bounds
)

logger = logging.getLogger(__name__)


class TaskService:
    """Manages task lifecycle: create, start, pause, resume, cancel, delete."""

    def __init__(self):
        self._active_tasks: Dict[str, Any] = {}
        db_manager.init_db()

    def create_task(self, task_data: TaskCreate) -> TaskResponse:
        """Create a new task and persist it."""
        with db_manager.get_session() as session:
            task_dict = {
                "id": str(uuid.uuid4()),
                "name": task_data.name,
                "strategy": task_data.strategy,
                "status": TaskStatus.IDLE.value,
                "bounds": task_data.bounds.model_dump() if task_data.bounds else {},
                "parameters": task_data.parameters,
                "priority": task_data.priority,
            }
            task_model = TaskRepository.create(session, task_dict)
            LogRepository.create(session, "task_created", {"task_id": task_model.id, "name": task_model.name})

            return TaskResponse(
                id=task_model.id,
                name=task_model.name,
                strategy=task_model.strategy,
                status=TaskStatus(task_model.status),
                progress=TaskProgress(),
                bounds=task_data.bounds,
                parameters=task_data.parameters,
                priority=task_model.priority,
                created_at=task_model.created_at,
                updated_at=task_model.updated_at,
            )

    def get_task(self, task_id: str) -> Optional[TaskResponse]:
        """Retrieve a task by ID."""
        with db_manager.get_session() as session:
            task = TaskRepository.get(session, task_id)
            if not task:
                return None
            return self._model_to_response(task)

    def list_tasks(
        self,
        status_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[TaskResponse]:
        """List tasks with optional status filter."""
        with db_manager.get_session() as session:
            tasks = TaskRepository.list_all(session, status_filter=status_filter, limit=limit, offset=offset)
            return [self._model_to_response(t) for t in tasks]

    def start_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Start task execution."""
        with db_manager.get_session() as session:
            task = TaskRepository.get(session, task_id)
            if not task:
                return None
            if task.status not in (TaskStatus.IDLE.value, TaskStatus.PAUSED.value):
                return {"status": "error", "message": f"Cannot start task in status: {task.status}"}

            TaskRepository.update(session, task_id, {
                "status": TaskStatus.RUNNING.value,
                "updated_at": datetime.now(timezone.utc),
            })
            LogRepository.create(session, "task_started", {"task_id": task_id})

            self._active_tasks[task_id] = {
                "status": TaskStatus.RUNNING,
                "started_at": datetime.now(timezone.utc),
            }

            return {"status": "ok", "message": f"Task {task_id} started"}

    def pause_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Pause task execution."""
        with db_manager.get_session() as session:
            task = TaskRepository.get(session, task_id)
            if not task:
                return None
            if task.status != TaskStatus.RUNNING.value:
                return {"status": "error", "message": "Task is not running"}

            TaskRepository.update(session, task_id, {"status": TaskStatus.PAUSED.value})
            LogRepository.create(session, "task_paused", {"task_id": task_id})

            if task_id in self._active_tasks:
                self._active_tasks[task_id]["status"] = TaskStatus.PAUSED

            return {"status": "ok", "message": f"Task {task_id} paused"}

    def resume_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Resume a paused task."""
        with db_manager.get_session() as session:
            task = TaskRepository.get(session, task_id)
            if not task:
                return None
            if task.status != TaskStatus.PAUSED.value:
                return {"status": "error", "message": "Task is not paused"}

            TaskRepository.update(session, task_id, {"status": TaskStatus.RUNNING.value})
            LogRepository.create(session, "task_resumed", {"task_id": task_id})

            if task_id in self._active_tasks:
                self._active_tasks[task_id]["status"] = TaskStatus.RUNNING

            return {"status": "ok", "message": f"Task {task_id} resumed"}

    def cancel_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Cancel a running or paused task."""
        with db_manager.get_session() as session:
            task = TaskRepository.get(session, task_id)
            if not task:
                return None
            if task.status not in (TaskStatus.RUNNING.value, TaskStatus.PAUSED.value, TaskStatus.IDLE.value):
                return {"status": "error", "message": f"Cannot cancel task in status: {task.status}"}

            TaskRepository.update(session, task_id, {
                "status": TaskStatus.CANCELLED.value,
                "completed_at": datetime.now(timezone.utc),
            })
            LogRepository.create(session, "task_cancelled", {"task_id": task_id})

            self._active_tasks.pop(task_id, None)
            return {"status": "ok", "message": f"Task {task_id} cancelled"}

    def get_progress(self, task_id: str) -> Optional[TaskProgress]:
        """Get current task progress."""
        with db_manager.get_session() as session:
            task = TaskRepository.get(session, task_id)
            if not task:
                return None

            samples = SampleRepository.list_by_task(session, task_id)
            bounds = json.loads(task.bounds_json) if task.bounds_json else {}

            total = 0
            if bounds and task.strategy == "grid":
                # Estimate grid points
                x_range = bounds.get("x_max", 0) - bounds.get("x_min", 0)
                y_range = bounds.get("y_max", 0) - bounds.get("y_min", 0)
                step = json.loads(task.params_json).get("step", 50) if task.params_json else 50
                if step > 0:
                    total = max(1, int(x_range / step) + 1) * max(1, int(y_range / step) + 1)
            else:
                total = json.loads(task.params_json).get("count", 10) if task.params_json else 10

            completed = sum(1 for s in samples if s.status == "completed")

            return TaskProgress(
                completed_samples=completed,
                total_samples=total,
                current_step="sampling" if task.status == TaskStatus.RUNNING.value else "",
                estimated_time=None,
            )

    def delete_task(self, task_id: str) -> bool:
        """Delete a task and its samples."""
        with db_manager.get_session() as session:
            task = TaskRepository.get(session, task_id)
            if not task:
                return False
            LogRepository.create(session, "task_deleted", {"task_id": task_id})
            self._active_tasks.pop(task_id, None)
            return TaskRepository.delete(session, task_id)

    def _model_to_response(self, task) -> TaskResponse:
        """Convert a database model to a response model."""
        bounds_dict = json.loads(task.bounds_json) if task.bounds_json else {}
        params_dict = json.loads(task.params_json) if task.params_json else {}
        bounds = Bounds(**bounds_dict) if bounds_dict else None

        return TaskResponse(
            id=task.id,
            name=task.name,
            strategy=task.strategy,
            status=TaskStatus(task.status),
            progress=TaskProgress(),
            bounds=bounds,
            parameters=params_dict,
            priority=task.priority,
            created_at=task.created_at,
            updated_at=task.updated_at,
            completed_at=task.completed_at,
        )