"""DailyTask API — Phase 7A.

Endpoints:
    GET  /api/v1/daily-tasks/today
    GET  /api/v1/daily-tasks/{task_date}
    POST /api/v1/daily-task-items/{id}/skip
    POST /api/v1/daily-task-items/{id}/restore
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.daily_task import (
    DailyTaskItemResponse,
    DailyTaskResponse,
    DomainRef,
    KnowledgePointRef,
)
from app.services.daily_task_service import (
    ItemConflictError,
    ItemNotFoundError,
    get_business_today,
    get_or_create_today,
    get_task_by_date,
    restore_item,
    skip_item,
)

router = APIRouter(prefix="/api/v1")


# ---------------------------------------------------------------------------
# GET /api/v1/daily-tasks/today
# ---------------------------------------------------------------------------

@router.get("/daily-tasks/today", response_model=DailyTaskResponse)
def get_today(db: Session = Depends(get_db)):
    """Get or create today's DailyTask."""
    result = get_or_create_today(db)
    return _to_response(result)


# ---------------------------------------------------------------------------
# GET /api/v1/daily-tasks/{task_date}
# ---------------------------------------------------------------------------

@router.get("/daily-tasks/{task_date}", response_model=DailyTaskResponse)
def get_by_date(task_date: date, db: Session = Depends(get_db)):
    """Get DailyTask for a specific date."""
    business_today = get_business_today()

    if task_date == business_today:
        # Today → get_or_create
        result = get_or_create_today(db)
        return _to_response(result)
    elif task_date > business_today:
        # Future → 404
        raise HTTPException(
            status_code=404,
            detail={"code": "TASK_NOT_FOUND", "message": "该日期的任务尚未生成", "details": None},
        )
    else:
        # Past → read only
        result = get_task_by_date(db, task_date)
        if not result:
            raise HTTPException(
                status_code=404,
                detail={"code": "TASK_NOT_FOUND", "message": "该日期没有任务记录", "details": None},
            )
        return _to_response(result)


# ---------------------------------------------------------------------------
# POST /api/v1/daily-task-items/{id}/skip
# ---------------------------------------------------------------------------

@router.post("/daily-task-items/{item_id}/skip", response_model=DailyTaskItemResponse)
def skip_task_item(item_id: int, db: Session = Depends(get_db)):
    """Skip a DailyTaskItem."""
    try:
        result = skip_item(db, item_id)
        return _to_item_response(result)
    except ItemNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"code": "ITEM_NOT_FOUND", "message": "任务项不存在", "details": None},
        )
    except ItemConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={"code": "ITEM_CONFLICT", "message": str(e), "details": None},
        )


# ---------------------------------------------------------------------------
# POST /api/v1/daily-task-items/{id}/restore
# ---------------------------------------------------------------------------

@router.post("/daily-task-items/{item_id}/restore", response_model=DailyTaskItemResponse)
def restore_task_item(item_id: int, db: Session = Depends(get_db)):
    """Restore a skipped DailyTaskItem."""
    try:
        result = restore_item(db, item_id)
        return _to_item_response(result)
    except ItemNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"code": "ITEM_NOT_FOUND", "message": "任务项不存在", "details": None},
        )
    except ItemConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={"code": "ITEM_CONFLICT", "message": str(e), "details": None},
        )


# ---------------------------------------------------------------------------
# Response builders
# ---------------------------------------------------------------------------

def _to_response(data: dict) -> DailyTaskResponse:
    items = []
    for item in data.get("items", []):
        domain_data = item.get("domain")
        kp_data = item.get("primary_knowledge_point")
        items.append(DailyTaskItemResponse(
            id=item["id"],
            question_id=item["question_id"],
            question_revision=item["question_revision"],
            title=item.get("title"),
            question_type=item.get("question_type", "unknown"),
            item_type=item["item_type"],
            status=item["status"],
            sort_order=item["sort_order"],
            due_date_snapshot=item.get("due_date_snapshot"),
            domain=DomainRef(id=domain_data["id"], name=domain_data["name"]) if domain_data else None,
            primary_knowledge_point=KnowledgePointRef(id=kp_data["id"], name=kp_data["name"]) if kp_data else None,
        ))
    return DailyTaskResponse(
        id=data["id"],
        task_date=data["task_date"],
        status=data["status"],
        new_question_target=data["new_question_target"],
        generated_at=data.get("generated_at"),
        completed_at=data.get("completed_at"),
        items=items,
    )


def _to_item_response(data: dict) -> DailyTaskItemResponse:
    kp_data = data.get("primary_knowledge_point")
    return DailyTaskItemResponse(
        id=data["id"],
        question_id=data["question_id"],
        question_revision=data["question_revision"],
        title=data.get("title"),
        question_type=data.get("question_type", "unknown"),
        item_type=data["item_type"],
        status=data["status"],
        sort_order=data["sort_order"],
        due_date_snapshot=data.get("due_date_snapshot"),
        primary_knowledge_point=KnowledgePointRef(id=kp_data["id"], name=kp_data["name"]) if kp_data else None,
    )