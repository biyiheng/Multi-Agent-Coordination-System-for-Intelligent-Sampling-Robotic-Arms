"""Loop Engineering data API routes (闭环工程数据管理).

为闭环工程 6 大数据模型提供完整 CRUD 接口 (持久化到 SQLite):

- 评估报告   /api/v1/loop/reports        (EvaluationReport)
- 性能画像   /api/v1/loop/profiles       (PerformanceProfile)
- 交互日志   /api/v1/loop/interactions   (InteractionLog)
- 技能库     /api/v1/loop/skills         (Skill)
- 知识谱系   /api/v1/loop/lineages       (KnowledgeLineage)
- 元技能库   /api/v1/loop/meta-skills    (MetaSkill)
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from rpi_control.database.repository import (
    EvaluationReportRepository,
    InteractionLogRepository,
    KnowledgeLineageRepository,
    MetaSkillRepository,
    PerformanceProfileRepository,
    SkillRepository,
    db_manager,
)
from rpi_control.web.services import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/loop", tags=["loop"])

# =============================================================================
# 评估报告 EvaluationReport
# =============================================================================


def _report_to_dict(report) -> Dict[str, Any]:
    return {
        "id": report.id,
        "task_id": report.task_id,
        "composite_score": report.composite_score,
        "grade": report.grade,
        "dimensions": json.loads(report.dimensions_json) if report.dimensions_json else {},
        "recommendations": json.loads(report.recommendations_json) if report.recommendations_json else [],
        "raw_data": json.loads(report.raw_data_json) if report.raw_data_json else {},
        "summary": report.summary,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


@router.post("/reports", status_code=201)
async def create_report(
    data: Dict[str, Any],
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Create an evaluation report."""
    report_id = data.get("id") or str(uuid.uuid4())
    with db_manager.get_session() as session:
        report = EvaluationReportRepository.create(
            session,
            report_id=report_id,
            task_id=data.get("task_id"),
            composite_score=data.get("composite_score", 0.0),
            grade=data.get("grade", "N/A"),
            dimensions=data.get("dimensions", {}),
            recommendations=data.get("recommendations", []),
            raw_data=data.get("raw_data", {}),
            summary=data.get("summary", ""),
        )
        session.refresh(report)
        return _report_to_dict(report)


@router.get("/reports")
async def list_reports(
    task_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """List evaluation reports, optionally filtered by task."""
    with db_manager.get_session() as session:
        rows = EvaluationReportRepository.list_all(
            session, task_id=task_id, limit=limit, offset=offset
        )
        return [_report_to_dict(r) for r in rows]


@router.get("/reports/{report_id}")
async def get_report(
    report_id: str,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Get a single evaluation report."""
    with db_manager.get_session() as session:
        report = EvaluationReportRepository.get(session, report_id)
        if not report:
            raise HTTPException(status_code=404, detail=f"报告不存在: {report_id}")
        return _report_to_dict(report)


@router.put("/reports/{report_id}")
async def update_report(
    report_id: str,
    updates: Dict[str, Any],
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Update an evaluation report (partial update)."""
    with db_manager.get_session() as session:
        report = EvaluationReportRepository.update(session, report_id, updates)
        if not report:
            raise HTTPException(status_code=404, detail=f"报告不存在: {report_id}")
        return _report_to_dict(report)


@router.delete("/reports/{report_id}")
async def delete_report(
    report_id: str,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Delete an evaluation report."""
    with db_manager.get_session() as session:
        if not EvaluationReportRepository.delete(session, report_id):
            raise HTTPException(status_code=404, detail=f"报告不存在: {report_id}")
    return {"status": "ok", "message": f"报告 {report_id} 已删除"}


# =============================================================================
# 性能画像 PerformanceProfile
# =============================================================================


def _profile_to_dict(profile) -> Dict[str, Any]:
    return {
        "id": profile.id,
        "task_id": profile.task_id,
        "agent_name": profile.agent_name,
        "operation": profile.operation,
        "duration_ms": profile.duration_ms,
        "p50_ms": profile.p50_ms,
        "p95_ms": profile.p95_ms,
        "p99_ms": profile.p99_ms,
        "calls": profile.calls,
        "slow_count": profile.slow_count,
        "metadata": json.loads(profile.metadata_json) if profile.metadata_json else {},
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
    }


@router.post("/profiles", status_code=201)
async def create_profile(
    data: Dict[str, Any],
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Create a performance profile."""
    with db_manager.get_session() as session:
        profile = PerformanceProfileRepository.create(
            session,
            task_id=data.get("task_id"),
            agent_name=data.get("agent_name", ""),
            operation=data.get("operation", ""),
            duration_ms=data.get("duration_ms", 0.0),
            p50_ms=data.get("p50_ms", 0.0),
            p95_ms=data.get("p95_ms", 0.0),
            p99_ms=data.get("p99_ms", 0.0),
            calls=data.get("calls", 0),
            slow_count=data.get("slow_count", 0),
            metadata=data.get("metadata", {}),
        )
        session.refresh(profile)
        return _profile_to_dict(profile)


@router.get("/profiles")
async def list_profiles(
    agent_name: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """List performance profiles."""
    with db_manager.get_session() as session:
        rows = PerformanceProfileRepository.list_all(
            session, agent_name=agent_name, task_id=task_id, limit=limit, offset=offset
        )
        return [_profile_to_dict(r) for r in rows]


@router.get("/profiles/{profile_id}")
async def get_profile(
    profile_id: int,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Get a single performance profile."""
    with db_manager.get_session() as session:
        profile = PerformanceProfileRepository.get(session, profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail=f"性能画像不存在: {profile_id}")
        return _profile_to_dict(profile)


@router.put("/profiles/{profile_id}")
async def update_profile(
    profile_id: int,
    updates: Dict[str, Any],
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Update a performance profile."""
    with db_manager.get_session() as session:
        profile = PerformanceProfileRepository.update(session, profile_id, updates)
        if not profile:
            raise HTTPException(status_code=404, detail=f"性能画像不存在: {profile_id}")
        return _profile_to_dict(profile)


@router.delete("/profiles/{profile_id}")
async def delete_profile(
    profile_id: int,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Delete a performance profile."""
    with db_manager.get_session() as session:
        if not PerformanceProfileRepository.delete(session, profile_id):
            raise HTTPException(status_code=404, detail=f"性能画像不存在: {profile_id}")
    return {"status": "ok", "message": f"性能画像 {profile_id} 已删除"}


# =============================================================================
# 交互日志 InteractionLog
# =============================================================================


def _interaction_to_dict(log) -> Dict[str, Any]:
    return {
        "id": log.id,
        "task_id": log.task_id,
        "caller": log.caller,
        "callee": log.callee,
        "interaction_type": log.interaction_type,
        "context_size": log.context_size,
        "duration_ms": log.duration_ms,
        "is_redundant": bool(log.is_redundant),
        "metadata": json.loads(log.metadata_json) if log.metadata_json else {},
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }


@router.post("/interactions", status_code=201)
async def create_interaction(
    data: Dict[str, Any],
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Create an interaction log entry."""
    with db_manager.get_session() as session:
        log = InteractionLogRepository.create(
            session,
            task_id=data.get("task_id"),
            caller=data.get("caller", ""),
            callee=data.get("callee", ""),
            interaction_type=data.get("interaction_type", "call"),
            context_size=data.get("context_size", 0),
            duration_ms=data.get("duration_ms", 0.0),
            is_redundant=data.get("is_redundant", False),
            metadata=data.get("metadata", {}),
        )
        session.refresh(log)
        return _interaction_to_dict(log)


@router.get("/interactions")
async def list_interactions(
    task_id: Optional[str] = Query(None),
    caller: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """List interaction logs."""
    with db_manager.get_session() as session:
        rows = InteractionLogRepository.list_all(
            session, task_id=task_id, caller=caller, limit=limit, offset=offset
        )
        return [_interaction_to_dict(r) for r in rows]


@router.get("/interactions/{log_id}")
async def get_interaction(
    log_id: int,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Get a single interaction log entry."""
    with db_manager.get_session() as session:
        log = InteractionLogRepository.get(session, log_id)
        if not log:
            raise HTTPException(status_code=404, detail=f"交互日志不存在: {log_id}")
        return _interaction_to_dict(log)


@router.put("/interactions/{log_id}")
async def update_interaction(
    log_id: int,
    updates: Dict[str, Any],
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Update an interaction log entry."""
    with db_manager.get_session() as session:
        log = InteractionLogRepository.update(session, log_id, updates)
        if not log:
            raise HTTPException(status_code=404, detail=f"交互日志不存在: {log_id}")
        return _interaction_to_dict(log)


@router.delete("/interactions/{log_id}")
async def delete_interaction(
    log_id: int,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Delete an interaction log entry."""
    with db_manager.get_session() as session:
        if not InteractionLogRepository.delete(session, log_id):
            raise HTTPException(status_code=404, detail=f"交互日志不存在: {log_id}")
    return {"status": "ok", "message": f"交互日志 {log_id} 已删除"}


# =============================================================================
# 技能库 Skill
# =============================================================================


def _skill_to_dict(skill) -> Dict[str, Any]:
    return {
        "id": skill.id,
        "name": skill.name,
        "description": skill.description,
        "steps": json.loads(skill.steps_json) if skill.steps_json else [],
        "preconditions": json.loads(skill.preconditions_json) if skill.preconditions_json else {},
        "postconditions": json.loads(skill.postconditions_json) if skill.postconditions_json else {},
        "effectiveness": skill.effectiveness,
        "reuse_count": skill.reuse_count,
        "success_count": skill.success_count,
        "failure_count": skill.failure_count,
        "source_agent": skill.source_agent,
        "version": skill.version,
        "created_at": skill.created_at.isoformat() if skill.created_at else None,
        "updated_at": skill.updated_at.isoformat() if skill.updated_at else None,
    }


@router.post("/skills", status_code=201)
async def create_skill(
    data: Dict[str, Any],
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Create a reusable skill."""
    skill_id = data.get("id") or str(uuid.uuid4())
    with db_manager.get_session() as session:
        skill = SkillRepository.create(
            session,
            skill_id=skill_id,
            name=data.get("name", ""),
            description=data.get("description", ""),
            steps=data.get("steps", []),
            preconditions=data.get("preconditions", {}),
            postconditions=data.get("postconditions", {}),
            effectiveness=data.get("effectiveness", 0.0),
            source_agent=data.get("source_agent"),
            version=data.get("version", 1),
        )
        session.refresh(skill)
        return _skill_to_dict(skill)


@router.get("/skills")
async def list_skills(
    name: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """List reusable skills."""
    with db_manager.get_session() as session:
        rows = SkillRepository.list_all(session, name=name, limit=limit, offset=offset)
        return [_skill_to_dict(r) for r in rows]


@router.get("/skills/{skill_id}")
async def get_skill(
    skill_id: str,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Get a single skill."""
    with db_manager.get_session() as session:
        skill = SkillRepository.get(session, skill_id)
        if not skill:
            raise HTTPException(status_code=404, detail=f"技能不存在: {skill_id}")
        return _skill_to_dict(skill)


@router.put("/skills/{skill_id}")
async def update_skill(
    skill_id: str,
    updates: Dict[str, Any],
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Update a skill (increment version when content changes)."""
    with db_manager.get_session() as session:
        skill = SkillRepository.update(session, skill_id, updates)
        if not skill:
            raise HTTPException(status_code=404, detail=f"技能不存在: {skill_id}")
        return _skill_to_dict(skill)


@router.delete("/skills/{skill_id}")
async def delete_skill(
    skill_id: str,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Delete a skill."""
    with db_manager.get_session() as session:
        if not SkillRepository.delete(session, skill_id):
            raise HTTPException(status_code=404, detail=f"技能不存在: {skill_id}")
    return {"status": "ok", "message": f"技能 {skill_id} 已删除"}


# =============================================================================
# 知识谱系 KnowledgeLineage
# =============================================================================


def _lineage_to_dict(lineage) -> Dict[str, Any]:
    return {
        "id": lineage.id,
        "from_version": lineage.from_version,
        "to_version": lineage.to_version,
        "inherited_params": json.loads(lineage.inherited_params_json) if lineage.inherited_params_json else {},
        "deprecated_params": json.loads(lineage.deprecated_params_json) if lineage.deprecated_params_json else [],
        "transfer_success_rate": lineage.transfer_success_rate,
        "notes": lineage.notes,
        "created_at": lineage.created_at.isoformat() if lineage.created_at else None,
    }


@router.post("/lineages", status_code=201)
async def create_lineage(
    data: Dict[str, Any],
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Create a knowledge lineage record."""
    with db_manager.get_session() as session:
        lineage = KnowledgeLineageRepository.create(
            session,
            from_version=data.get("from_version", ""),
            to_version=data.get("to_version", ""),
            inherited_params=data.get("inherited_params", {}),
            deprecated_params=data.get("deprecated_params", []),
            transfer_success_rate=data.get("transfer_success_rate", 0.0),
            notes=data.get("notes", ""),
        )
        session.refresh(lineage)
        return _lineage_to_dict(lineage)


@router.get("/lineages")
async def list_lineages(
    to_version: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """List knowledge lineage records."""
    with db_manager.get_session() as session:
        rows = KnowledgeLineageRepository.list_all(
            session, to_version=to_version, limit=limit, offset=offset
        )
        return [_lineage_to_dict(r) for r in rows]


@router.get("/lineages/{lineage_id}")
async def get_lineage(
    lineage_id: int,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Get a single knowledge lineage record."""
    with db_manager.get_session() as session:
        lineage = KnowledgeLineageRepository.get(session, lineage_id)
        if not lineage:
            raise HTTPException(status_code=404, detail=f"知识谱系不存在: {lineage_id}")
        return _lineage_to_dict(lineage)


@router.put("/lineages/{lineage_id}")
async def update_lineage(
    lineage_id: int,
    updates: Dict[str, Any],
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Update a knowledge lineage record."""
    with db_manager.get_session() as session:
        lineage = KnowledgeLineageRepository.update(session, lineage_id, updates)
        if not lineage:
            raise HTTPException(status_code=404, detail=f"知识谱系不存在: {lineage_id}")
        return _lineage_to_dict(lineage)


@router.delete("/lineages/{lineage_id}")
async def delete_lineage(
    lineage_id: int,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Delete a knowledge lineage record."""
    with db_manager.get_session() as session:
        if not KnowledgeLineageRepository.delete(session, lineage_id):
            raise HTTPException(status_code=404, detail=f"知识谱系不存在: {lineage_id}")
    return {"status": "ok", "message": f"知识谱系 {lineage_id} 已删除"}


# =============================================================================
# 元技能库 MetaSkill
# =============================================================================


def _meta_skill_to_dict(meta) -> Dict[str, Any]:
    return {
        "id": meta.id,
        "name": meta.name,
        "strategy_type": meta.strategy_type,
        "prompt_template": meta.prompt_template,
        "effectiveness": meta.effectiveness,
        "application_count": meta.application_count,
        "improvement_pct": meta.improvement_pct,
        "rules": json.loads(meta.rules_json) if meta.rules_json else [],
        "created_at": meta.created_at.isoformat() if meta.created_at else None,
        "updated_at": meta.updated_at.isoformat() if meta.updated_at else None,
    }


@router.post("/meta-skills", status_code=201)
async def create_meta_skill(
    data: Dict[str, Any],
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Create a meta-skill (optimization strategy)."""
    meta_id = data.get("id") or str(uuid.uuid4())
    with db_manager.get_session() as session:
        meta = MetaSkillRepository.create(
            session,
            meta_skill_id=meta_id,
            name=data.get("name", ""),
            strategy_type=data.get("strategy_type", ""),
            prompt_template=data.get("prompt_template", ""),
            effectiveness=data.get("effectiveness", 0.0),
            improvement_pct=data.get("improvement_pct", 0.0),
            rules=data.get("rules", []),
        )
        session.refresh(meta)
        return _meta_skill_to_dict(meta)


@router.get("/meta-skills")
async def list_meta_skills(
    strategy_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """List meta-skills."""
    with db_manager.get_session() as session:
        rows = MetaSkillRepository.list_all(
            session, strategy_type=strategy_type, limit=limit, offset=offset
        )
        return [_meta_skill_to_dict(r) for r in rows]


@router.get("/meta-skills/{meta_skill_id}")
async def get_meta_skill(
    meta_skill_id: str,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Get a single meta-skill."""
    with db_manager.get_session() as session:
        meta = MetaSkillRepository.get(session, meta_skill_id)
        if not meta:
            raise HTTPException(status_code=404, detail=f"元技能不存在: {meta_skill_id}")
        return _meta_skill_to_dict(meta)


@router.put("/meta-skills/{meta_skill_id}")
async def update_meta_skill(
    meta_skill_id: str,
    updates: Dict[str, Any],
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Update a meta-skill."""
    with db_manager.get_session() as session:
        meta = MetaSkillRepository.update(session, meta_skill_id, updates)
        if not meta:
            raise HTTPException(status_code=404, detail=f"元技能不存在: {meta_skill_id}")
        return _meta_skill_to_dict(meta)


@router.delete("/meta-skills/{meta_skill_id}")
async def delete_meta_skill(
    meta_skill_id: str,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Delete a meta-skill."""
    with db_manager.get_session() as session:
        if not MetaSkillRepository.delete(session, meta_skill_id):
            raise HTTPException(status_code=404, detail=f"元技能不存在: {meta_skill_id}")
    return {"status": "ok", "message": f"元技能 {meta_skill_id} 已删除"}
