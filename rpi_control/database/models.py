"""SQLAlchemy database models for the intelligent sampling robotic arm system."""

from datetime import datetime, timezone
import json

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Text, ForeignKey, create_engine
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def _utcnow():
    """Return current UTC datetime as naive datetime (SQLite compatible).

    Uses datetime.now(timezone.utc).replace(tzinfo=None) to produce a naive
    UTC datetime, since SQLite stores DateTime without timezone information.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _json_default(obj):
    """Default JSON encoder for non-serializable types."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


class TaskModel(Base):
    """Database model for sampling tasks."""
    __tablename__ = "tasks"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    strategy = Column(String(32), nullable=False, default="grid")
    status = Column(String(16), nullable=False, default="idle")
    bounds_json = Column(Text, default="{}")
    params_json = Column(Text, default="{}")
    priority = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    completed_at = Column(DateTime, nullable=True)

    samples = relationship("SampleModel", back_populates="task", cascade="all, delete-orphan")


class SampleModel(Base):
    """Database model for collected samples."""
    __tablename__ = "samples"

    id = Column(String(64), primary_key=True)
    task_id = Column(String(64), ForeignKey("tasks.id"), nullable=False)
    position_x = Column(Float, default=0.0)
    position_y = Column(Float, default=0.0)
    position_z = Column(Float, default=0.0)
    quality_score = Column(Float, default=0.0)
    status = Column(String(16), default="pending")
    defects_json = Column(Text, default="[]")
    sample_type = Column(String(32), default="unknown")
    image_path = Column(String(256), nullable=True)
    notes = Column(Text, nullable=True)
    inspected_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    task = relationship("TaskModel", back_populates="samples")


class ActionLogModel(Base):
    """Database model for action logs."""
    __tablename__ = "action_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action_type = Column(String(64), nullable=False)
    details_json = Column(Text, default="{}")
    timestamp = Column(DateTime, default=_utcnow)


class SystemConfigModel(Base):
    """Database model for system configuration."""
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(128), unique=True, nullable=False)
    value_json = Column(Text, default="{}")
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


# =============================================================================
# Loop Engineering Models
# =============================================================================


class EvaluationReportModel(Base):
    """Database model for loop engineering evaluation reports."""
    __tablename__ = "loop_evaluation_reports"

    id = Column(String(64), primary_key=True)
    task_id = Column(String(64), nullable=True, index=True)
    composite_score = Column(Float, default=0.0)
    grade = Column(String(8), default="N/A")
    dimensions_json = Column(Text, default="{}")
    recommendations_json = Column(Text, default="[]")
    raw_data_json = Column(Text, default="{}")
    summary = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow)


class PerformanceProfileModel(Base):
    """Database model for agent performance profiles."""
    __tablename__ = "loop_performance_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), nullable=True, index=True)
    agent_name = Column(String(128), nullable=False, index=True)
    operation = Column(String(128), nullable=False)
    duration_ms = Column(Float, default=0.0)
    p50_ms = Column(Float, default=0.0)
    p95_ms = Column(Float, default=0.0)
    p99_ms = Column(Float, default=0.0)
    calls = Column(Integer, default=0)
    slow_count = Column(Integer, default=0)
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=_utcnow)


class InteractionLogModel(Base):
    """Database model for agent interaction logs."""
    __tablename__ = "loop_interaction_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), nullable=True, index=True)
    caller = Column(String(128), nullable=False, index=True)
    callee = Column(String(128), nullable=False, index=True)
    interaction_type = Column(String(32), nullable=False)
    context_size = Column(Integer, default=0)
    duration_ms = Column(Float, default=0.0)
    is_redundant = Column(Integer, default=0)  # 0=False, 1=True
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=_utcnow)


class SkillModel(Base):
    """Database model for extracted and reusable skills."""
    __tablename__ = "loop_skills"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False, index=True)
    description = Column(Text, default="")
    steps_json = Column(Text, default="[]")
    preconditions_json = Column(Text, default="{}")
    postconditions_json = Column(Text, default="{}")
    effectiveness = Column(Float, default=0.0)
    reuse_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    source_agent = Column(String(64), nullable=True)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class KnowledgeLineageModel(Base):
    """Database model for knowledge inheritance lineage."""
    __tablename__ = "loop_knowledge_lineage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_version = Column(String(32), nullable=False)
    to_version = Column(String(32), nullable=False)
    inherited_params_json = Column(Text, default="{}")
    deprecated_params_json = Column(Text, default="[]")
    transfer_success_rate = Column(Float, default=0.0)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow)


class MetaSkillModel(Base):
    """Database model for meta-skills (optimization strategies)."""
    __tablename__ = "loop_meta_skills"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    strategy_type = Column(String(64), nullable=False)
    prompt_template = Column(Text, default="")
    effectiveness = Column(Float, default=0.0)
    application_count = Column(Integer, default=0)
    improvement_pct = Column(Float, default=0.0)
    rules_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)