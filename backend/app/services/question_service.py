"""Question query service — Phase 6.5.

Provides list and detail queries for questions.
List includes ReviewState summary and pending self-assessment info.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.db.models.attempt import Attempt
from app.db.models.knowledge import KnowledgePoint
from app.db.models.question import Question, QuestionVersion
from app.db.models.review import ReviewState


def list_questions(
    db: Session,
    *,
    knowledge_point_id: Optional[str] = None,
    question_type: Optional[str] = None,
    difficulty: Optional[int] = None,
    mastery_state: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """Query questions with filters, pagination, and ReviewState summary.

    mastery_state filter values:
        not_started, unmastered, vague, familiar, mastered

    Returns:
        {"items": [...], "page": int, "page_size": int, "total": int}
    """
    # Subquery: pending self-assessment attempts
    pending_sa = (
        db.query(
            Attempt.question_id,
            Attempt.id.label("pending_sa_id"),
        )
        .filter(Attempt.status == "awaiting_self_assessment")
        .subquery()
    )

    # Base query with joins
    base = (
        db.query(
            Question.id,
            Question.title,
            Question.question_type,
            Question.difficulty,
            Question.primary_knowledge_point_id,
            ReviewState.mastery_state.label("rs_mastery_state"),
            ReviewState.next_review_date.label("rs_next_review_date"),
            pending_sa.c.pending_sa_id,
        )
        .outerjoin(ReviewState, ReviewState.question_id == Question.id)
        .outerjoin(pending_sa, pending_sa.c.question_id == Question.id)
        .filter(Question.is_active == True)  # noqa: E712
    )

    # Apply filters
    if knowledge_point_id is not None:
        base = base.filter(Question.primary_knowledge_point_id == knowledge_point_id)
    if question_type is not None:
        base = base.filter(Question.question_type == question_type)
    if difficulty is not None:
        base = base.filter(Question.difficulty == difficulty)

    # mastery_state filter
    if mastery_state is not None:
        if mastery_state == "not_started":
            base = base.filter(ReviewState.mastery_state.is_(None))
        else:
            base = base.filter(ReviewState.mastery_state == mastery_state)

    # Total count
    total = base.count()

    # Deterministic sort: difficulty ASC, id ASC
    rows = (
        base.order_by(Question.difficulty.asc(), Question.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # Get knowledge point names (batch to avoid N+1)
    kp_ids = {r.primary_knowledge_point_id for r in rows}
    kp_names: dict[str, str] = {}
    if kp_ids:
        kps = (
            db.query(KnowledgePoint.id, KnowledgePoint.name)
            .filter(KnowledgePoint.id.in_(kp_ids))
            .all()
        )
        kp_names = {kp.id: kp.name for kp in kps}

    # Build items
    items = []
    for r in rows:
        review_state = None
        if r.rs_mastery_state is not None:
            review_state = {
                "mastery_state": r.rs_mastery_state,
                "next_review_date": str(r.rs_next_review_date) if r.rs_next_review_date else None,
            }

        items.append({
            "id": r.id,
            "title": r.title,
            "question_type": r.question_type,
            "difficulty": r.difficulty,
            "primary_knowledge_point": {
                "id": r.primary_knowledge_point_id,
                "name": kp_names.get(r.primary_knowledge_point_id),
            },
            "review_state": review_state,
            "pending_self_assessment_attempt_id": r.pending_sa_id,
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