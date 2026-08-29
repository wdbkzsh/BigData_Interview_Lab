"""Knowledge API — Tasks 3.1 & 3.2.

Endpoints:
    GET  /api/v1/knowledge-points               — knowledge point tree
    GET  /api/v1/knowledge-points/{id}           — single knowledge point detail
    GET  /api/v1/knowledge-points/{id}/card      — card current version + progress
    POST /api/v1/knowledge-cards/{card_id}/view  — record card view
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.knowledge import (
    KnowledgeCard,
    KnowledgeCardProgress,
    KnowledgeCardVersion,
    KnowledgePoint,
)
from app.db.models.question import Question
from app.db.session import get_db
from app.schemas.knowledge import (
    CardContent,
    CardProgressResponse,
    KnowledgeCardResponse,
    KnowledgePointDetail,
    KnowledgePointTreeNode,
)

router = APIRouter(prefix="/api/v1")


# ---------------------------------------------------------------------------
# GET /api/v1/knowledge-points — tree
# ---------------------------------------------------------------------------

@router.get("/knowledge-points", response_model=list[KnowledgePointTreeNode])
def list_knowledge_points(db: Session = Depends(get_db)):
    """Return the full knowledge point tree (active only)."""
    rows = (
        db.query(KnowledgePoint)
        .filter(KnowledgePoint.is_active == True)  # noqa: E712
        .order_by(
            KnowledgePoint.level.asc(),
            KnowledgePoint.sort_order.asc(),
            KnowledgePoint.id.asc(),
        )
        .all()
    )

    # Group by parent_id for O(n) tree assembly
    children_map: dict[str | None, list[KnowledgePoint]] = defaultdict(list)
    for kp in rows:
        children_map[kp.parent_id].append(kp)

    def _build(parent_id: str | None) -> list[KnowledgePointTreeNode]:
        nodes: list[KnowledgePointTreeNode] = []
        for kp in children_map.get(parent_id, []):
            nodes.append(
                KnowledgePointTreeNode(
                    id=kp.id,
                    name=kp.name,
                    level=kp.level,
                    children=_build(kp.id),
                )
            )
        return nodes

    return _build(None)


# ---------------------------------------------------------------------------
# GET /api/v1/knowledge-points/{knowledge_point_id} — detail
# ---------------------------------------------------------------------------

@router.get("/knowledge-points/{knowledge_point_id}", response_model=KnowledgePointDetail)
def get_knowledge_point(knowledge_point_id: str, db: Session = Depends(get_db)):
    """Return a single knowledge point with question_count and has_card."""
    kp = (
        db.query(KnowledgePoint)
        .filter(
            KnowledgePoint.id == knowledge_point_id,
            KnowledgePoint.is_active == True,  # noqa: E712
        )
        .first()
    )
    if not kp:
        raise HTTPException(
            status_code=404,
            detail={"code": "KNOWLEDGE_POINT_NOT_FOUND", "message": "知识点不存在", "details": None},
        )

    # COUNT via database — do NOT load Question entities
    question_count = (
        db.query(func.count())
        .select_from(Question)
        .filter(
            Question.primary_knowledge_point_id == knowledge_point_id,
            Question.is_active == True,  # noqa: E712
        )
        .scalar()
    )

    # has_card — lightweight existence check
    has_card = (
        db.query(KnowledgeCard.id)
        .filter(
            KnowledgeCard.knowledge_point_id == knowledge_point_id,
            KnowledgeCard.is_active == True,  # noqa: E712
        )
        .first()
        is not None
    )

    return KnowledgePointDetail(
        id=kp.id,
        name=kp.name,
        description=kp.description,
        question_count=question_count,
        has_card=has_card,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/knowledge-points/{knowledge_point_id}/card
# ---------------------------------------------------------------------------

@router.get("/knowledge-points/{knowledge_point_id}/card", response_model=KnowledgeCardResponse)
def get_knowledge_card(knowledge_point_id: str, db: Session = Depends(get_db)):
    """Return the current version of a knowledge card."""
    # 1. Confirm KP exists and is active
    kp = (
        db.query(KnowledgePoint.id)
        .filter(
            KnowledgePoint.id == knowledge_point_id,
            KnowledgePoint.is_active == True,  # noqa: E712
        )
        .first()
    )
    if not kp:
        raise HTTPException(
            status_code=404,
            detail={"code": "KNOWLEDGE_POINT_NOT_FOUND", "message": "知识点不存在", "details": None},
        )

    # 2. Query active card
    card = (
        db.query(KnowledgeCard)
        .filter(
            KnowledgeCard.knowledge_point_id == knowledge_point_id,
            KnowledgeCard.is_active == True,  # noqa: E712
        )
        .first()
    )
    if not card:
        raise HTTPException(
            status_code=404,
            detail={"code": "CARD_NOT_FOUND", "message": "知识卡片不存在", "details": None},
        )

    # 3. Query current_revision version
    version = (
        db.query(KnowledgeCardVersion)
        .filter(
            KnowledgeCardVersion.card_id == card.id,
            KnowledgeCardVersion.revision == card.current_revision,
        )
        .first()
    )
    if not version:
        # Data integrity error — card exists but version missing
        raise HTTPException(
            status_code=500,
            detail={"code": "CARD_VERSION_MISSING", "message": "卡片版本数据异常", "details": None},
        )

    # 4. Parse content_json
    content_dict = json.loads(version.content_json)

    # 5. Query progress (read-only, no DB write)
    progress = (
        db.query(KnowledgeCardProgress)
        .filter(KnowledgeCardProgress.card_id == card.id)
        .first()
    )
    if progress:
        progress_data = CardProgressResponse(
            status=progress.status,
            view_count=progress.view_count,
            last_viewed_at=progress.last_viewed_at,
        )
    else:
        progress_data = CardProgressResponse(
            status="unread",
            view_count=0,
            last_viewed_at=None,
        )

    return KnowledgeCardResponse(
        id=card.id,
        knowledge_point_id=card.knowledge_point_id,
        revision=card.current_revision,
        content=CardContent(**content_dict),
        progress=progress_data,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/knowledge-cards/{card_id}/view
# ---------------------------------------------------------------------------

@router.post("/knowledge-cards/{card_id}/view", response_model=CardProgressResponse)
def record_card_view(card_id: str, db: Session = Depends(get_db)):
    """Record a knowledge card view (upsert progress)."""
    # 1. Check card exists and is active
    card = (
        db.query(KnowledgeCard)
        .filter(
            KnowledgeCard.id == card_id,
            KnowledgeCard.is_active == True,  # noqa: E712
        )
        .first()
    )
    if not card:
        raise HTTPException(
            status_code=404,
            detail={"code": "CARD_NOT_FOUND", "message": "知识卡片不存在", "details": None},
        )

    # 2. Check associated knowledge point is active
    kp = (
        db.query(KnowledgePoint.id)
        .filter(
            KnowledgePoint.id == card.knowledge_point_id,
            KnowledgePoint.is_active == True,  # noqa: E712
        )
        .first()
    )
    if not kp:
        raise HTTPException(
            status_code=404,
            detail={"code": "CARD_NOT_FOUND", "message": "知识卡片不存在", "details": None},
        )

    # 3. Upsert progress
    now = datetime.now(timezone.utc)
    progress = (
        db.query(KnowledgeCardProgress)
        .filter(KnowledgeCardProgress.card_id == card_id)
        .first()
    )
    if not progress:
        progress = KnowledgeCardProgress(
            card_id=card_id,
            first_viewed_at=now,
            last_viewed_at=now,
            view_count=1,
            status="read",
        )
        db.add(progress)
    else:
        # Preserve first_viewed_at
        progress.last_viewed_at = now
        progress.view_count += 1
        progress.status = "read"

    try:
        db.commit()
        db.refresh(progress)
    except Exception:
        db.rollback()
        raise

    return CardProgressResponse(
        status=progress.status,
        view_count=progress.view_count,
        last_viewed_at=progress.last_viewed_at,
    )
