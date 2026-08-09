"""Data access layer for the intelligent sampling robotic arm system."""

import json
import logging
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from rpi_control.database.models import (
    Base, TaskModel, SampleModel, ActionLogModel, SystemConfigModel
)

logger = logging.getLogger(__name__)


def _ensure_db_directory(db_url: str) -> None:
    """Ensure the parent directory for a SQLite database exists."""
    if db_url.startswith("sqlite:///"):
        db_path = db_url[len("sqlite:///"):]
        if db_path.startswith("./"):
            db_path = db_path[2:]
        parent_dir = Path(db_path).parent
        if parent_dir and str(parent_dir) != ".":
            parent_dir.mkdir(parents=True, exist_ok=True)


class DatabaseManager:
    """Manages database connection and initialization."""

    def __init__(self, db_url: str = "sqlite:///./data/sampling.db"):
        _ensure_db_directory(db_url)
        self.engine = create_engine(db_url, connect_args={"check_same_thread": False})
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def init_db(self):
        """Create all database tables."""
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database tables created successfully")

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get a database session as a context manager."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


db_manager = DatabaseManager()


class TaskRepository:
    """CRUD operations for tasks."""

    @staticmethod
    def create(session: Session, task_data: Dict[str, Any]) -> TaskModel:
        task_id = task_data.get("id") or str(uuid.uuid4())
        task = TaskModel(
            id=task_id,
            name=task_data["name"],
            strategy=task_data.get("strategy", "grid"),
            status=task_data.get("status", "idle"),
            bounds_json=json.dumps(task_data.get("bounds", {})),
            params_json=json.dumps(task_data.get("parameters", {})),
            priority=task_data.get("priority", 0),
        )
        session.add(task)
        session.flush()
        return task

    @staticmethod
    def get(session: Session, task_id: str) -> Optional[TaskModel]:
        return session.query(TaskModel).filter(TaskModel.id == task_id).first()

    @staticmethod
    def list_all(
        session: Session,
        status_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[TaskModel]:
        query = session.query(TaskModel)
        if status_filter:
            query = query.filter(TaskModel.status == status_filter)
        return query.order_by(TaskModel.created_at.desc()).offset(offset).limit(limit).all()

    @staticmethod
    def update(session: Session, task_id: str, updates: Dict[str, Any]) -> Optional[TaskModel]:
        task = session.query(TaskModel).filter(TaskModel.id == task_id).first()
        if not task:
            return None
        for key, value in updates.items():
            if key == "bounds":
                task.bounds_json = json.dumps(value) if isinstance(value, dict) else value
            elif key == "parameters":
                task.params_json = json.dumps(value) if isinstance(value, dict) else value
            elif hasattr(task, key):
                setattr(task, key, value)
        task.updated_at = datetime.now(timezone.utc)
        session.flush()
        return task

    @staticmethod
    def delete(session: Session, task_id: str) -> bool:
        task = session.query(TaskModel).filter(TaskModel.id == task_id).first()
        if not task:
            return False
        session.delete(task)
        session.flush()
        return True


class SampleRepository:
    """CRUD operations for samples."""

    @staticmethod
    def create(session: Session, sample_data: Dict[str, Any]) -> SampleModel:
        sample_id = sample_data.get("id") or str(uuid.uuid4())
        position = sample_data.get("position", {})
        sample = SampleModel(
            id=sample_id,
            task_id=sample_data["task_id"],
            position_x=position.get("x", 0.0),
            position_y=position.get("y", 0.0),
            position_z=position.get("z", 0.0),
            quality_score=sample_data.get("quality_score", 0.0),
            status=sample_data.get("status", "pending"),
            defects_json=json.dumps(sample_data.get("defects", [])),
            sample_type=sample_data.get("type", "unknown"),
            image_path=sample_data.get("image_path"),
            notes=sample_data.get("notes"),
        )
        session.add(sample)
        session.flush()
        return sample

    @staticmethod
    def get(session: Session, sample_id: str) -> Optional[SampleModel]:
        return session.query(SampleModel).filter(SampleModel.id == sample_id).first()

    @staticmethod
    def list_by_task(
        session: Session,
        task_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[SampleModel]:
        return (
            session.query(SampleModel)
            .filter(SampleModel.task_id == task_id)
            .order_by(SampleModel.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    @staticmethod
    def list_all(
        session: Session,
        task_id: Optional[str] = None,
        quality_min: Optional[float] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[SampleModel]:
        query = session.query(SampleModel)
        if task_id:
            query = query.filter(SampleModel.task_id == task_id)
        if quality_min is not None:
            query = query.filter(SampleModel.quality_score >= quality_min)
        return query.order_by(SampleModel.created_at.desc()).offset(offset).limit(limit).all()

    @staticmethod
    def update(session: Session, sample_id: str, updates: Dict[str, Any]) -> Optional[SampleModel]:
        sample = session.query(SampleModel).filter(SampleModel.id == sample_id).first()
        if not sample:
            return None
        for key, value in updates.items():
            if key == "defects":
                sample.defects_json = json.dumps(value) if isinstance(value, list) else value
            elif key == "position":
                sample.position_x = value.get("x", sample.position_x)
                sample.position_y = value.get("y", sample.position_y)
                sample.position_z = value.get("z", sample.position_z)
            elif hasattr(sample, key):
                setattr(sample, key, value)
        session.flush()
        return sample


class LogRepository:
    """Write and query action logs."""

    @staticmethod
    def create(session: Session, action_type: str, details: Dict[str, Any]) -> ActionLogModel:
        log = ActionLogModel(
            action_type=action_type,
            details_json=json.dumps(details),
        )
        session.add(log)
        session.flush()
        return log

    @staticmethod
    def list_recent(session: Session, limit: int = 100) -> List[ActionLogModel]:
        return (
            session.query(ActionLogModel)
            .order_by(ActionLogModel.timestamp.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def list_by_type(
        session: Session,
        action_type: str,
        limit: int = 50
    ) -> List[ActionLogModel]:
        return (
            session.query(ActionLogModel)
            .filter(ActionLogModel.action_type == action_type)
            .order_by(ActionLogModel.timestamp.desc())
            .limit(limit)
            .all()
        )


class ConfigRepository:
    """Get/set system configuration values."""

    @staticmethod
    def get(session: Session, key: str) -> Optional[Dict[str, Any]]:
        config = (
            session.query(SystemConfigModel)
            .filter(SystemConfigModel.key == key)
            .first()
        )
        if config:
            return json.loads(config.value_json)
        return None

    @staticmethod
    def set(session: Session, key: str, value: Any) -> SystemConfigModel:
        config = (
            session.query(SystemConfigModel)
            .filter(SystemConfigModel.key == key)
            .first()
        )
        value_json = json.dumps(value)
        if config:
            config.value_json = value_json
            config.updated_at = datetime.now(timezone.utc)
        else:
            config = SystemConfigModel(key=key, value_json=value_json)
            session.add(config)
        session.flush()
        return config

    @staticmethod
    def list_all(session: Session) -> List[SystemConfigModel]:
        return session.query(SystemConfigModel).all()