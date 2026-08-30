"""Question query service — Task 4.1.

Provides list and detail queries for questions.
Does NOT expose HTTP endpoints — that is Task 4.2.
Does NOT access ReviewState / Attempt / DailyTask.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.knowledge import KnowledgePoint
from app.db.models.question import Question, QuestionVersion


def list_questions(
    db: Session,
    *,
    knowledge_point_id: Optional[str] = None,
    question_type: Optional[str] = None,
    difficulty: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """Query questions with filters and pagination.

    Returns:
        {"items": [...], "page": int, "page_size": int, "total": int}
    """
    # Base filter: active only
    base = db.query(Question).filter(Question.is_active == True)  # noqa: E712

    # Apply filters
    if knowledge_point_id is not None:
        base = base.filter(Question.primary_knowledge_point_id == knowledge_point_id)
    if question_type is not None:
        base = base.filter(Question.question_type == question_type)
    if difficulty is not None:
        base = base.filter(Question.difficulty == difficulty)

    # Total count
    total = base.count()

    # Deterministic sort: difficulty ASC, id ASC
    rows = (
        base.order_by(Question.difficulty.asc(), Question.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # Build items — lightweight list representation
    items = []
    for q in rows:
        items.append({
            "id": q.id,
            "title": q.title,
            "question_type": q.question_type,
            "difficulty": q.difficulty,
        })

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
    }


def get_question_detail(
    db: Session,
    question_id: str,
) -> Optional[dict[str, Any]]:
    """Query a single question detail with answer hiding.

    Returns None if question does not exist or is inactive.
    """
    q = (
        db.query(Question)
        .filter(
            Question.id == question_id,
            Question.is_active == True,  # noqa: E712
        )
        .first()
    )
    if not q:
        return None

    # Get current version
    version = (
        db.query(QuestionVersion)
        .filter(
            QuestionVersion.question_id == q.id,
            QuestionVersion.revision == q.current_revision,
        )
        .first()
    )
    if not version:
        return None

    # Parse payload
    payload = json.loads(version.payload_json)

    # Get primary knowledge point name
    kp = (
        db.query(KnowledgePoint)
        .filter(KnowledgePoint.id == q.primary_knowledge_point_id)
        .first()
    )
    kp_name = kp.name if kp else None

    # Build base result
    result: dict[str, Any] = {
        "id": q.id,
        "revision": q.current_revision,
        "question_type": q.question_type,
        "difficulty": q.difficulty,
        "primary_knowledge_point": {
            "id": q.primary_knowledge_point_id,
            "name": kp_name,
        },
    }

    # Add type-specific fields with answer hiding
    if q.question_type == "choice":
        result["content"] = payload.get("content")
        result["options"] = payload.get("options")
        # HIDE: correct_answer, explanation

    elif q.question_type == "short_answer":
        result["content"] = payload.get("content")
        # HIDE: reference_answer, explanation

    elif q.question_type == "sql":
        result["content"] = payload.get("content")
        result["table_schema"] = payload.get("table_schema")
        result["field_description"] = payload.get("field_description")
        result["business_requirement"] = payload.get("business_requirement")
        # HIDE: expected_sql, scoring_criteria

    else:
        # Unknown type — return what we can
        result["content"] = payload.get("content")

    return result