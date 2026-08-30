"""Question query service — Phase 7.

Provides list and detail queries for questions.
List includes ReviewState summary, pending self-assessment info, and domain.
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


def _get_root_kp_map(db: Session, kp_ids: set[str]) -> dict[str, dict[str, str]]:
    """Build kp_id → {domain_id, domain_name} map by walking parent hierarchy.

    Returns a dict mapping each kp_id to its root ancestor (domain).
    If kp_id itself is root, domain = itself.
    """
    if not kp_ids:
        return {}

    # Load all KP rows we need (the ones in kp_ids + their ancestors)
    # Strategy: iterative parent resolution
    all_kps: dict[str, tuple[Optional[str], str]] = {}  # id → (parent_id, name)
    to_load = set(kp_ids)

    while to_load:
        rows = (
            db.query(KnowledgePoint.id, KnowledgePoint.parent_id, KnowledgePoint.name)
            .filter(KnowledgePoint.id.in_(to_load))
            .all()
        )
        new_ids: set[str] = set()
        for r in rows:
            if r.id not in all_kps:
                all_kps[r.id] = (r.parent_id, r.name)
                if r.parent_id and r.parent_id not in all_kps:
                    new_ids.add(r.parent_id)
        to_load = new_ids

    # Walk to root for each kp_id
    result: dict[str, dict[str, str]] = {}
    for kp_id in kp_ids:
        current = kp_id
        visited = set()
        while current in all_kps and current not in visited:
            visited.add(current)
            parent_id, name = all_kps[current]
            if parent_id is None or parent_id not in all_kps:
                # current is root
                result[kp_id] = {"id": current, "name": name}
                break
            current = parent_id
        else:
            # Fallback: kp_id itself
            if kp_id in all_kps:
                result[kp_id] = {"id": kp_id, "name": all_kps[kp_id][1]}

    return result


def _get_descendant_kp_ids(db: Session, root_id: str) -> set[str]:
    """Get all descendant KnowledgePoint IDs under root_id (inclusive)."""
    result: set[str] = {root_id}
    to_check = {root_id}

    while to_check:
        children = (
            db.query(KnowledgePoint.id)
            .filter(KnowledgePoint.parent_id.in_(to_check))
            .all()
        )
        new_ids = {c.id for c in children} - result
        result.update(new_ids)
        to_check = new_ids

    return result


def list_questions(
    db: Session,
    *,
    knowledge_point_id: Optional[str] = None,
    question_type: Optional[str] = None,
    difficulty: Optional[int] = None,
    mastery_state: Optional[str] = None,
    domain_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """Query questions with filters, pagination, ReviewState, and domain.

    mastery_state filter values:
        not_started, unmastered, vague, familiar, mastered

    domain_id: filter by root KnowledgePoint (includes all descendants)

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

    # domain_id filter: include all descendant KPs
    if domain_id is not None:
        descendant_ids = _get_descendant_kp_ids(db, domain_id)
        base = base.filter(Question.primary_knowledge_point_id.in_(descendant_ids))

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

    # Batch-load KP names and domain info (avoid N+1)
    kp_ids = {r.primary_knowledge_point_id for r in rows}
    kp_names: dict[str, str] = {}
    kp_domain_map: dict[str, dict[str, str]] = {}
    if kp_ids:
        kps = (
            db.query(KnowledgePoint.id, KnowledgePoint.name)
            .filter(KnowledgePoint.id.in_(kp_ids))
            .all()
        )
        kp_names = {kp.id: kp.name for kp in kps}
        kp_domain_map = _get_root_kp_map(db, kp_ids)

    # Build items
    items = []
    for r in rows:
        review_state = None
        if r.rs_mastery_state is not None:
            review_state = {
                "mastery_state": r.rs_mastery_state,
                "next_review_date": str(r.rs_next_review_date) if r.rs_next_review_date else None,
            }

        domain = kp_domain_map.get(r.primary_knowledge_point_id)

        items.append({
            "id": r.id,
            "title": r.title,
            "question_type": r.question_type,
            "difficulty": r.difficulty,
            "primary_knowledge_point": {
                "id": r.primary_knowledge_point_id,
                "name": kp_names.get(r.primary_knowledge_point_id),
            },
            "domain": domain,
            "review_state": review_state,
            "pending_self_assessment_attempt_id": r.pending_sa_id,
        })

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
    }


def list_domains(db: Session) -> list[dict[str, str]]:
    """List all root KnowledgePoints (domains).

    Returns [{"id": "spark", "name": "Spark"}, ...]
    """
    roots = (
        db.query(KnowledgePoint.id, KnowledgePoint.name)
        .filter(
            KnowledgePoint.parent_id.is_(None),
            KnowledgePoint.is_active == True,  # noqa: E712
        )
        .order_by(KnowledgePoint.sort_order.asc(), KnowledgePoint.id.asc())
        .all()
    )
    return [{"id": r.id, "name": r.name} for r in roots]


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