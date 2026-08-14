"""Sample data management API routes (CRUD).

- POST   /api/v1/samples         创建样本
- GET    /api/v1/samples         样本列表 (可按任务/质量过滤)
- GET    /api/v1/samples/{id}    样本详情
- PUT    /api/v1/samples/{id}    更新样本
- DELETE /api/v1/samples/{id}    删除样本
"""

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from rpi_control.database.repository import SampleRepository, db_manager
from rpi_control.web.services import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/samples", tags=["samples"])


def _sample_to_dict(sample) -> Dict[str, Any]:
    return {
        "id": sample.id,
        "task_id": sample.task_id,
        "position": {
            "x": sample.position_x,
            "y": sample.position_y,
            "z": sample.position_z,
        },
        "quality_score": sample.quality_score,
        "status": sample.status,
        "defects": json.loads(sample.defects_json) if sample.defects_json else [],
        "type": sample.sample_type,
        "image_path": sample.image_path,
        "notes": sample.notes,
        "inspected_at": sample.inspected_at.isoformat() if sample.inspected_at else None,
        "created_at": sample.created_at.isoformat() if sample.created_at else None,
    }


@router.post("", status_code=201)
async def create_sample(
    data: Dict[str, Any],
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Create a new sample record."""
    if not data.get("task_id"):
        raise HTTPException(status_code=400, detail="task_id is required")
    with db_manager.get_session() as session:
        sample = SampleRepository.create(session, data)
        session.refresh(sample)
        return _sample_to_dict(sample)


@router.get("")
async def list_samples(
    task_id: Optional[str] = Query(None),
    quality_min: Optional[float] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """List samples, optionally filtered by task or minimum quality."""
    with db_manager.get_session() as session:
        rows = SampleRepository.list_all(
            session, task_id=task_id, quality_min=quality_min, limit=limit, offset=offset
        )
        return [_sample_to_dict(r) for r in rows]


@router.get("/{sample_id}")
async def get_sample(
    sample_id: str,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Get a single sample by ID."""
    with db_manager.get_session() as session:
        sample = SampleRepository.get(session, sample_id)
        if not sample:
            raise HTTPException(status_code=404, detail=f"样本不存在: {sample_id}")
        return _sample_to_dict(sample)


@router.put("/{sample_id}")
async def update_sample(
    sample_id: str,
    updates: Dict[str, Any],
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Update sample fields (partial update)."""
    with db_manager.get_session() as session:
        sample = SampleRepository.update(session, sample_id, updates)
        if not sample:
            raise HTTPException(status_code=404, detail=f"样本不存在: {sample_id}")
        return _sample_to_dict(sample)


@router.delete("/{sample_id}")
async def delete_sample(
    sample_id: str,
    _: Dict[str, Any] = Depends(auth_service.get_current_user),
):
    """Delete a sample."""
    with db_manager.get_session() as session:
        if not SampleRepository.delete(session, sample_id):
            raise HTTPException(status_code=404, detail=f"样本不存在: {sample_id}")
    return {"status": "ok", "message": f"样本 {sample_id} 已删除"}
