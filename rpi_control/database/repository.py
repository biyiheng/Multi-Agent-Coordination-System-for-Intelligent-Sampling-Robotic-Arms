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
    Base, TaskModel, SampleModel, ActionLogModel, SystemConfigModel,
    UserModel, AuthTokenModel, DeviceModel, WifiStateModel,
    EvaluationReportModel, PerformanceProfileModel, InteractionLogModel,
    SkillModel, KnowledgeLineageModel, MetaSkillModel,
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

    @staticmethod
    def delete(session: Session, sample_id: str) -> bool:
        sample = session.query(SampleModel).filter(SampleModel.id == sample_id).first()
        if not sample:
            return False
        session.delete(sample)
        session.flush()
        return True

    @staticmethod
    def delete_by_task(session: Session, task_id: str) -> int:
        """Delete all samples belonging to a task; returns the deleted count."""
        result = (
            session.query(SampleModel)
            .filter(SampleModel.task_id == task_id)
            .delete(synchronize_session=False)
        )
        session.flush()
        return int(result)


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

    @staticmethod
    def delete(session: Session, key: str) -> bool:
        config = (
            session.query(SystemConfigModel)
            .filter(SystemConfigModel.key == key)
            .first()
        )
        if not config:
            return False
        session.delete(config)
        session.flush()
        return True


# =============================================================================
# Multi-End Interop Repositories (多端互通)
# =============================================================================


class UserRepository:
    """User management for platform authentication."""

    @staticmethod
    def create(session: Session, user_id: str, username: str,
               password_hash: str, role: str = "user") -> UserModel:
        user = UserModel(
            id=user_id, username=username,
            password_hash=password_hash, role=role,
        )
        session.add(user)
        session.flush()
        return user

    @staticmethod
    def get_by_username(session: Session, username: str) -> Optional[UserModel]:
        return session.query(UserModel).filter(UserModel.username == username).first()

    @staticmethod
    def get(session: Session, user_id: str) -> Optional[UserModel]:
        return session.query(UserModel).filter(UserModel.id == user_id).first()

    @staticmethod
    def list_all(session: Session, limit: int = 100) -> List[UserModel]:
        return session.query(UserModel).order_by(UserModel.created_at).limit(limit).all()

    @staticmethod
    def update(session: Session, user_id: str, updates: Dict[str, Any]) -> Optional[UserModel]:
        """Update a user's role / enabled flag (and optionally password hash)."""
        user = session.query(UserModel).filter(UserModel.id == user_id).first()
        if not user:
            return None
        for key, value in updates.items():
            if key in ("username", "role", "enabled", "password_hash") and hasattr(user, key):
                setattr(user, key, value)
        session.flush()
        return user

    @staticmethod
    def delete(session: Session, user_id: str) -> bool:
        user = session.query(UserModel).filter(UserModel.id == user_id).first()
        if not user:
            return False
        # Cascade delete the user's issued tokens first.
        AuthTokenRepository.delete_user_tokens(session, user_id)
        session.delete(user)
        session.flush()
        return True


class AuthTokenRepository:
    """Issued API token storage."""

    @staticmethod
    def create(session: Session, user_id: str, token_hash: str,
               scope: str = "app") -> AuthTokenModel:
        token = AuthTokenModel(user_id=user_id, token_hash=token_hash, scope=scope)
        session.add(token)
        session.flush()
        return token

    @staticmethod
    def get_by_hash(session: Session, token_hash: str) -> Optional[AuthTokenModel]:
        return session.query(AuthTokenModel).filter(AuthTokenModel.token_hash == token_hash).first()

    @staticmethod
    def delete_user_tokens(session: Session, user_id: str) -> None:
        session.query(AuthTokenModel).filter(AuthTokenModel.user_id == user_id).delete()


class DeviceRepository:
    """Device registry for multi-end interop (device center)."""

    @staticmethod
    def upsert(session: Session, device_id: str, data: Dict[str, Any]) -> DeviceModel:
        device = session.query(DeviceModel).filter(DeviceModel.id == device_id).first()
        extra = data.get("extra", {})
        if device:
            for key in ("name", "device_type", "client_type", "mac", "ip",
                        "status", "firmware_version"):
                if key in data:
                    setattr(device, key, data[key])
            if data.get("online") is True:
                device.status = "online"
                device.last_seen = datetime.now(timezone.utc)
            if data.get("online") is False:
                device.status = "offline"
            if extra:
                device.extra_json = json.dumps(extra)
        else:
            device = DeviceModel(
                id=device_id,
                name=data.get("name", device_id),
                device_type=data.get("device_type", "generic"),
                client_type=data.get("client_type", "web"),
                mac=data.get("mac"),
                ip=data.get("ip"),
                status="online" if data.get("online", True) else "offline",
                firmware_version=data.get("firmware_version"),
                extra_json=json.dumps(extra),
                last_seen=datetime.now(timezone.utc),
            )
            session.add(device)
        session.flush()
        return device

    @staticmethod
    def get(session: Session, device_id: str) -> Optional[DeviceModel]:
        return session.query(DeviceModel).filter(DeviceModel.id == device_id).first()

    @staticmethod
    def list_all(session: Session, client_type: Optional[str] = None,
                 status: Optional[str] = None, limit: int = 200) -> List[DeviceModel]:
        query = session.query(DeviceModel)
        if client_type:
            query = query.filter(DeviceModel.client_type == client_type)
        if status:
            query = query.filter(DeviceModel.status == status)
        return query.order_by(DeviceModel.updated_at.desc()).limit(limit).all()

    @staticmethod
    def set_offline(session: Session, device_id: str) -> None:
        device = session.query(DeviceModel).filter(DeviceModel.id == device_id).first()
        if device:
            device.status = "offline"

    @staticmethod
    def update(session: Session, device_id: str, updates: Dict[str, Any]) -> Optional[DeviceModel]:
        """Update mutable device fields (name / status / firmware / extra)."""
        device = session.query(DeviceModel).filter(DeviceModel.id == device_id).first()
        if not device:
            return None
        for key in ("name", "device_type", "client_type", "mac", "ip",
                    "status", "firmware_version"):
            if key in updates:
                setattr(device, key, updates[key])
        if "extra" in updates:
            device.extra_json = json.dumps(updates["extra"])
        if updates.get("online") is True:
            device.status = "online"
            device.last_seen = datetime.now(timezone.utc)
        session.flush()
        return device

    @staticmethod
    def delete(session: Session, device_id: str) -> bool:
        device = session.query(DeviceModel).filter(DeviceModel.id == device_id).first()
        if not device:
            return False
        session.delete(device)
        session.flush()
        return True


class WifiStateRepository:
    """Persist & restore the latest WiFi / ESP32 provisioning state."""

    @staticmethod
    def get(session: Session) -> Optional[WifiStateModel]:
        return session.query(WifiStateModel).order_by(WifiStateModel.id.desc()).first()

    @staticmethod
    def save(session: Session, ssid: Optional[str], password: Optional[str],
             mode: str, ip: Optional[str], esp32_connected: bool) -> WifiStateModel:
        state = WifiStateRepository.get(session)
        if state:
            state.ssid = ssid
            state.password = password
            state.mode = mode
            state.ip = ip
            state.esp32_connected = 1 if esp32_connected else 0
        else:
            state = WifiStateModel(
                ssid=ssid, password=password, mode=mode, ip=ip,
                esp32_connected=1 if esp32_connected else 0,
            )
            session.add(state)
        session.flush()
        return state

    @staticmethod
    def clear(session: Session) -> bool:
        """Clear the persisted WiFi provisioning state."""
        states = session.query(WifiStateModel).all()
        if not states:
            return False
        for state in states:
            session.delete(state)
        session.flush()
        return True


# =============================================================================
# Loop Engineering Repositories (闭环工程数据持久化)
# =============================================================================


class EvaluationReportRepository:
    """CRUD operations for loop engineering evaluation reports."""

    @staticmethod
    def create(
        session: Session,
        report_id: str,
        task_id: Optional[str],
        composite_score: float,
        grade: str,
        dimensions: Dict[str, Any],
        recommendations: List[Any],
        raw_data: Dict[str, Any],
        summary: str = "",
    ) -> EvaluationReportModel:
        report = EvaluationReportModel(
            id=report_id,
            task_id=task_id,
            composite_score=composite_score,
            grade=grade,
            dimensions_json=json.dumps(dimensions),
            recommendations_json=json.dumps(recommendations),
            raw_data_json=json.dumps(raw_data),
            summary=summary,
        )
        session.add(report)
        session.flush()
        return report

    @staticmethod
    def get(session: Session, report_id: str) -> Optional[EvaluationReportModel]:
        return session.query(EvaluationReportModel).filter(
            EvaluationReportModel.id == report_id
        ).first()

    @staticmethod
    def list_all(
        session: Session,
        task_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[EvaluationReportModel]:
        query = session.query(EvaluationReportModel)
        if task_id:
            query = query.filter(EvaluationReportModel.task_id == task_id)
        return query.order_by(EvaluationReportModel.created_at.desc()).offset(offset).limit(limit).all()

    @staticmethod
    def update(
        session: Session,
        report_id: str,
        updates: Dict[str, Any],
    ) -> Optional[EvaluationReportModel]:
        report = session.query(EvaluationReportModel).filter(
            EvaluationReportModel.id == report_id
        ).first()
        if not report:
            return None
        for key, value in updates.items():
            if key == "dimensions" and isinstance(value, dict):
                report.dimensions_json = json.dumps(value)
            elif key == "recommendations" and isinstance(value, list):
                report.recommendations_json = json.dumps(value)
            elif key == "raw_data" and isinstance(value, dict):
                report.raw_data_json = json.dumps(value)
            elif hasattr(report, key):
                setattr(report, key, value)
        session.flush()
        return report

    @staticmethod
    def delete(session: Session, report_id: str) -> bool:
        report = session.query(EvaluationReportModel).filter(
            EvaluationReportModel.id == report_id
        ).first()
        if not report:
            return False
        session.delete(report)
        session.flush()
        return True


class PerformanceProfileRepository:
    """CRUD operations for agent performance profiles."""

    @staticmethod
    def create(
        session: Session,
        task_id: Optional[str],
        agent_name: str,
        operation: str,
        duration_ms: float = 0.0,
        p50_ms: float = 0.0,
        p95_ms: float = 0.0,
        p99_ms: float = 0.0,
        calls: int = 0,
        slow_count: int = 0,
        metadata: Dict[str, Any] = None,
    ) -> PerformanceProfileModel:
        profile = PerformanceProfileModel(
            task_id=task_id,
            agent_name=agent_name,
            operation=operation,
            duration_ms=duration_ms,
            p50_ms=p50_ms,
            p95_ms=p95_ms,
            p99_ms=p99_ms,
            calls=calls,
            slow_count=slow_count,
            metadata_json=json.dumps(metadata or {}),
        )
        session.add(profile)
        session.flush()
        return profile

    @staticmethod
    def get(session: Session, profile_id: int) -> Optional[PerformanceProfileModel]:
        return session.query(PerformanceProfileModel).filter(
            PerformanceProfileModel.id == profile_id
        ).first()

    @staticmethod
    def list_all(
        session: Session,
        agent_name: Optional[str] = None,
        task_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[PerformanceProfileModel]:
        query = session.query(PerformanceProfileModel)
        if agent_name:
            query = query.filter(PerformanceProfileModel.agent_name == agent_name)
        if task_id:
            query = query.filter(PerformanceProfileModel.task_id == task_id)
        return query.order_by(PerformanceProfileModel.created_at.desc()).offset(offset).limit(limit).all()

    @staticmethod
    def update(
        session: Session,
        profile_id: int,
        updates: Dict[str, Any],
    ) -> Optional[PerformanceProfileModel]:
        profile = session.query(PerformanceProfileModel).filter(
            PerformanceProfileModel.id == profile_id
        ).first()
        if not profile:
            return None
        for key, value in updates.items():
            if key == "metadata" and isinstance(value, dict):
                profile.metadata_json = json.dumps(value)
            elif hasattr(profile, key):
                setattr(profile, key, value)
        session.flush()
        return profile

    @staticmethod
    def delete(session: Session, profile_id: int) -> bool:
        profile = session.query(PerformanceProfileModel).filter(
            PerformanceProfileModel.id == profile_id
        ).first()
        if not profile:
            return False
        session.delete(profile)
        session.flush()
        return True


class InteractionLogRepository:
    """CRUD operations for agent interaction logs."""

    @staticmethod
    def create(
        session: Session,
        task_id: Optional[str],
        caller: str,
        callee: str,
        interaction_type: str,
        context_size: int = 0,
        duration_ms: float = 0.0,
        is_redundant: bool = False,
        metadata: Dict[str, Any] = None,
    ) -> InteractionLogModel:
        log = InteractionLogModel(
            task_id=task_id,
            caller=caller,
            callee=callee,
            interaction_type=interaction_type,
            context_size=context_size,
            duration_ms=duration_ms,
            is_redundant=1 if is_redundant else 0,
            metadata_json=json.dumps(metadata or {}),
        )
        session.add(log)
        session.flush()
        return log

    @staticmethod
    def get(session: Session, log_id: int) -> Optional[InteractionLogModel]:
        return session.query(InteractionLogModel).filter(
            InteractionLogModel.id == log_id
        ).first()

    @staticmethod
    def list_all(
        session: Session,
        task_id: Optional[str] = None,
        caller: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[InteractionLogModel]:
        query = session.query(InteractionLogModel)
        if task_id:
            query = query.filter(InteractionLogModel.task_id == task_id)
        if caller:
            query = query.filter(InteractionLogModel.caller == caller)
        return query.order_by(InteractionLogModel.created_at.desc()).offset(offset).limit(limit).all()

    @staticmethod
    def update(
        session: Session,
        log_id: int,
        updates: Dict[str, Any],
    ) -> Optional[InteractionLogModel]:
        log = session.query(InteractionLogModel).filter(
            InteractionLogModel.id == log_id
        ).first()
        if not log:
            return None
        for key, value in updates.items():
            if key == "metadata" and isinstance(value, dict):
                log.metadata_json = json.dumps(value)
            elif key == "is_redundant":
                log.is_redundant = 1 if value else 0
            elif hasattr(log, key):
                setattr(log, key, value)
        session.flush()
        return log

    @staticmethod
    def delete(session: Session, log_id: int) -> bool:
        log = session.query(InteractionLogModel).filter(
            InteractionLogModel.id == log_id
        ).first()
        if not log:
            return False
        session.delete(log)
        session.flush()
        return True


class SkillRepository:
    """CRUD operations for extracted reusable skills."""

    @staticmethod
    def create(
        session: Session,
        skill_id: str,
        name: str,
        description: str = "",
        steps: List[Any] = None,
        preconditions: Dict[str, Any] = None,
        postconditions: Dict[str, Any] = None,
        effectiveness: float = 0.0,
        source_agent: Optional[str] = None,
        version: int = 1,
    ) -> SkillModel:
        skill = SkillModel(
            id=skill_id,
            name=name,
            description=description,
            steps_json=json.dumps(steps or []),
            preconditions_json=json.dumps(preconditions or {}),
            postconditions_json=json.dumps(postconditions or {}),
            effectiveness=effectiveness,
            reuse_count=0,
            success_count=0,
            failure_count=0,
            source_agent=source_agent,
            version=version,
        )
        session.add(skill)
        session.flush()
        return skill

    @staticmethod
    def get(session: Session, skill_id: str) -> Optional[SkillModel]:
        return session.query(SkillModel).filter(SkillModel.id == skill_id).first()

    @staticmethod
    def list_all(
        session: Session,
        name: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SkillModel]:
        query = session.query(SkillModel)
        if name:
            query = query.filter(SkillModel.name == name)
        return query.order_by(SkillModel.updated_at.desc()).offset(offset).limit(limit).all()

    @staticmethod
    def update(session: Session, skill_id: str, updates: Dict[str, Any]) -> Optional[SkillModel]:
        skill = session.query(SkillModel).filter(SkillModel.id == skill_id).first()
        if not skill:
            return None
        for key, value in updates.items():
            if key == "steps" and isinstance(value, list):
                skill.steps_json = json.dumps(value)
            elif key == "preconditions" and isinstance(value, dict):
                skill.preconditions_json = json.dumps(value)
            elif key == "postconditions" and isinstance(value, dict):
                skill.postconditions_json = json.dumps(value)
            elif hasattr(skill, key):
                setattr(skill, key, value)
        session.flush()
        return skill

    @staticmethod
    def delete(session: Session, skill_id: str) -> bool:
        skill = session.query(SkillModel).filter(SkillModel.id == skill_id).first()
        if not skill:
            return False
        session.delete(skill)
        session.flush()
        return True


class KnowledgeLineageRepository:
    """CRUD operations for knowledge inheritance lineage."""

    @staticmethod
    def create(
        session: Session,
        from_version: str,
        to_version: str,
        inherited_params: Dict[str, Any] = None,
        deprecated_params: List[Any] = None,
        transfer_success_rate: float = 0.0,
        notes: str = "",
    ) -> KnowledgeLineageModel:
        lineage = KnowledgeLineageModel(
            from_version=from_version,
            to_version=to_version,
            inherited_params_json=json.dumps(inherited_params or {}),
            deprecated_params_json=json.dumps(deprecated_params or []),
            transfer_success_rate=transfer_success_rate,
            notes=notes,
        )
        session.add(lineage)
        session.flush()
        return lineage

    @staticmethod
    def get(session: Session, lineage_id: int) -> Optional[KnowledgeLineageModel]:
        return session.query(KnowledgeLineageModel).filter(
            KnowledgeLineageModel.id == lineage_id
        ).first()

    @staticmethod
    def list_all(
        session: Session,
        to_version: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[KnowledgeLineageModel]:
        query = session.query(KnowledgeLineageModel)
        if to_version:
            query = query.filter(KnowledgeLineageModel.to_version == to_version)
        return query.order_by(KnowledgeLineageModel.created_at.desc()).offset(offset).limit(limit).all()

    @staticmethod
    def update(
        session: Session,
        lineage_id: int,
        updates: Dict[str, Any],
    ) -> Optional[KnowledgeLineageModel]:
        lineage = session.query(KnowledgeLineageModel).filter(
            KnowledgeLineageModel.id == lineage_id
        ).first()
        if not lineage:
            return None
        for key, value in updates.items():
            if key == "inherited_params" and isinstance(value, dict):
                lineage.inherited_params_json = json.dumps(value)
            elif key == "deprecated_params" and isinstance(value, list):
                lineage.deprecated_params_json = json.dumps(value)
            elif hasattr(lineage, key):
                setattr(lineage, key, value)
        session.flush()
        return lineage

    @staticmethod
    def delete(session: Session, lineage_id: int) -> bool:
        lineage = session.query(KnowledgeLineageModel).filter(
            KnowledgeLineageModel.id == lineage_id
        ).first()
        if not lineage:
            return False
        session.delete(lineage)
        session.flush()
        return True


class MetaSkillRepository:
    """CRUD operations for meta-skills (optimization strategies)."""

    @staticmethod
    def create(
        session: Session,
        meta_skill_id: str,
        name: str,
        strategy_type: str,
        prompt_template: str = "",
        effectiveness: float = 0.0,
        improvement_pct: float = 0.0,
        rules: List[Any] = None,
    ) -> MetaSkillModel:
        meta = MetaSkillModel(
            id=meta_skill_id,
            name=name,
            strategy_type=strategy_type,
            prompt_template=prompt_template,
            effectiveness=effectiveness,
            application_count=0,
            improvement_pct=improvement_pct,
            rules_json=json.dumps(rules or []),
        )
        session.add(meta)
        session.flush()
        return meta

    @staticmethod
    def get(session: Session, meta_skill_id: str) -> Optional[MetaSkillModel]:
        return session.query(MetaSkillModel).filter(
            MetaSkillModel.id == meta_skill_id
        ).first()

    @staticmethod
    def list_all(
        session: Session,
        strategy_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[MetaSkillModel]:
        query = session.query(MetaSkillModel)
        if strategy_type:
            query = query.filter(MetaSkillModel.strategy_type == strategy_type)
        return query.order_by(MetaSkillModel.updated_at.desc()).offset(offset).limit(limit).all()

    @staticmethod
    def update(
        session: Session,
        meta_skill_id: str,
        updates: Dict[str, Any],
    ) -> Optional[MetaSkillModel]:
        meta = session.query(MetaSkillModel).filter(
            MetaSkillModel.id == meta_skill_id
        ).first()
        if not meta:
            return None
        for key, value in updates.items():
            if key == "rules" and isinstance(value, list):
                meta.rules_json = json.dumps(value)
            elif hasattr(meta, key):
                setattr(meta, key, value)
        session.flush()
        return meta

    @staticmethod
    def delete(session: Session, meta_skill_id: str) -> bool:
        meta = session.query(MetaSkillModel).filter(
            MetaSkillModel.id == meta_skill_id
        ).first()
        if not meta:
            return False
        session.delete(meta)
        session.flush()
        return True