"""Review Service — ReviewState queries and persistence.

Orchestrates Review Policy (pure calculation) with DB operations.
Does NOT handle Attempt lifecycle — that is Attempt Service's job.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.db.models.review import ReviewState


def get_review_state(db: Session, question_id: str) -> Optional[dict[str, Any]]:
    """Get ReviewState for a question, or None if not exists."""
    rs = (
        db.query(ReviewState)
        .filter(ReviewState.question_id == question_id)
        .first()
    )
    if not rs:
        return None
    return _review_state_to_dict(rs)


def get_review_state_or_default(db: Session, question_id: str) -> dict[str, Any]:
    """Get ReviewState or return default 'not started' response."""
    rs = get_review_state(db, question_id)
    if rs:
        return rs
    return {
        "question_id": question_id,
        "mastery_state": None,
        "next_review_date": None,
        "review_count": 0,
        "consecutive_successes": 0,
        "review_stage": None,
        "policy_version": None,
    }


def upsert_review_state(
    db: Session,
    *,
    question_id: str,
    mastery_state: str,
    review_stage: int,
    next_review_date: Any,  # date object
    consecutive_successes: int,
    policy_version: str,
    algorithm_state_json: str,
    last_attempt_id: Optional[int] = None,
    increment_review_count: bool = False,
) -> dict[str, Any]:
    """Create or update ReviewState.

    Returns the updated ReviewState as dict.
    """
    now = datetime.now(timezone.utc)

    rs = (
        db.query(ReviewState)
        .filter(ReviewState.question_id == question_id)
        .first()
    )

    if rs:
        rs.mastery_state = mastery_state
        rs.last_attempt_id = last_attempt_id or rs.last_attempt_id
        rs.last_review_at = now
        rs.next_review_date = next_review_date
        if increment_review_count:
            rs.review_count += 1
        rs.consecutive_successes = consecutive_successes
        rs.policy_version = policy_version
        rs.algorithm_state_json = algorithm_state_json
    else:
        rs = ReviewState(
            question_id=question_id,
            mastery_state=mastery_state,
            last_attempt_id=last_attempt_id,
            last_review_at=now,
            next_review_date=next_review_date,
            review_count=1 if increment_review_count else 0,
            consecutive_successes=consecutive_successes,
            policy_version=policy_version,
            algorithm_state_json=algorithm_state_json,
        )
        db.add(rs)

    return _review_state_to_dict(rs)


def _review_state_to_dict(rs: ReviewState) -> dict[str, Any]:
    """Convert ReviewState ORM to dict."""
    review_stage = None
    if rs.algorithm_state_json:
        try:
            algo = json.loads(rs.algorithm_state_json)
            review_stage = algo.get("review_stage")
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "question_id": rs.question_id,
        "mastery_state": rs.mastery_state,
        "next_review_date": str(rs.next_review_date) if rs.next_review_date else None,
        "review_count": rs.review_count,
        "consecutive_successes": rs.consecutive_successes,
        "review_stage": review_stage,
        "policy_version": rs.policy_version,
    }