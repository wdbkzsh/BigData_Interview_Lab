"""Wrong Book Service — Phase 6.

Queries Question + ReviewState + QuestionPreference dynamically.
No dedicated wrong_book table.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models.knowledge import KnowledgeCard
from app.db.models.question import Question
from app.db.models.review import QuestionPreference, ReviewState


def query_wrong_book(
    db: Session,
    *,
    knowledge_point_id: Optional[str] = None,
    question_type: Optional[str] = None,
    mastery_state: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """Query wrong book with filters and pagination.

    Rules:
    - follow → always show
    - ignore → always hide
    - auto → show if mastery_state in (unmastered, vague)
    """
    # Subquery: get all active questions with their review state and preference
    base = (
        db.query(
            Question.id,
            Question.title,
            Question.question_type,
            Question.difficulty,
            Question.primary_knowledge_point_id,
            ReviewState.mastery_state.label("rs_mastery_state"),
            ReviewState.next_review_date.label("rs_next_review_date"),
            QuestionPreference.wrong_book_mode,
        )
        .outerjoin(ReviewState, ReviewState.question_id == Question.id)
        .outerjoin(QuestionPreference, QuestionPreference.question_id == Question.id)
        .filter(Question.is_active == True)  # noqa: E712
    )

    # Apply wrong book visibility filter
    # follow → show, ignore → hide, auto → mastery in (unmastered, vague)
    visibility = or_(
        QuestionPreference.wrong_book_mode == "follow",
        # auto (default) with low mastery
        (
            (QuestionPreference.wrong_book_mode.is_(None))
            | (QuestionPreference.wrong_book_mode == "auto")
        ) & (
            (ReviewState.mastery_state.in_(["unmastered", "vague"]))
            | (ReviewState.mastery_state.is_(None))
        ),
    )
    base = base.filter(visibility)

    # Apply optional filters
    if knowledge_point_id:
        base = base.filter(
            Question.primary_knowledge_point_id == knowledge_point_id
        )
    if question_type:
        base = base.filter(Question.question_type == question_type)
    if mastery_state:
        base = base.filter(ReviewState.mastery_state == mastery_state)

    # Count
    total = base.count()

    # Paginate
    rows = (
        base.order_by(Question.difficulty.asc(), Question.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # Build items
    items = []
    for row in rows:
        # Check if knowledge card exists
        has_card = (
            db.query(KnowledgeCard.id)
            .filter(
                KnowledgeCard.knowledge_point_id == row.primary_knowledge_point_id,
                KnowledgeCard.is_active == True,  # noqa: E712
            )
            .first()
            is not None
        )

        items.append({
            "question_id": row.id,
            "title": row.title,
            "question_type": row.question_type,
            "difficulty": row.difficulty,
            "primary_knowledge_point_id": row.primary_knowledge_point_id,
            "primary_knowledge_point_name": None,  # Lazy — not needed for MVP
            "mastery_state": row.rs_mastery_state,
            "next_review_date": str(row.rs_next_review_date) if row.rs_next_review_date else None,
            "wrong_book_mode": row.wrong_book_mode or "auto",
            "has_card": has_card,
        })

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
    }


def set_wrong_book_preference(
    db: Session,
    *,
    question_id: str,
    mode: str,
) -> dict[str, Any]:
    """Set wrong book preference for a question. Idempotent."""
    pref = (
        db.query(QuestionPreference)
        .filter(QuestionPreference.question_id == question_id)
        .first()
    )

    if pref:
        pref.wrong_book_mode = mode
    else:
        pref = QuestionPreference(
            question_id=question_id,
            wrong_book_mode=mode,
        )
        db.add(pref)

    db.commit()

    return {
        "question_id": question_id,
        "mode": pref.wrong_book_mode,
    }