"""ReviewState API — Phase 6.

Endpoints:
    GET /api/v1/questions/{question_id}/review-state
    PUT /api/v1/questions/{question_id}/review-state
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.db.models.question import Question
from app.db.session import get_db
from app.review.policy import apply_self_assessment
from app.schemas.review import ManualMasteryRequest, ReviewStateResponse
from app.services.review_service import get_review_state_or_default, upsert_review_state

router = APIRouter(prefix="/api/v1")


# ---------------------------------------------------------------------------
# GET /api/v1/questions/{question_id}/review-state
# ---------------------------------------------------------------------------

@router.get(
    "/questions/{question_id}/review-state",
    response_model=ReviewStateResponse,
)
def get_review_state(question_id: str, db: Session = Depends(get_db)):
    """Get ReviewState for a question. Returns default if not exists."""
    # Validate question exists
    q = db.query(Question.id).filter(Question.id == question_id).first()
    if not q:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "QUESTION_NOT_FOUND",
                "message": "题目不存在",
                "details": None,
            },
        )

    result = get_review_state_or_default(db, question_id)
    return ReviewStateResponse(**result)


# ---------------------------------------------------------------------------
# PUT /api/v1/questions/{question_id}/review-state
# ---------------------------------------------------------------------------

@router.put(
    "/questions/{question_id}/review-state",
    response_model=ReviewStateResponse,
)
def update_review_state(
    question_id: str,
    body: ManualMasteryRequest,
    db: Session = Depends(get_db),
):
    """Manual mastery update. Uses Self-Assessment Policy."""
    # Validate question exists
    q = db.query(Question.id).filter(Question.id == question_id).first()
    if not q:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "QUESTION_NOT_FOUND",
                "message": "题目不存在",
                "details": None,
            },
        )

    # Check idempotent: if current mastery_state matches, return existing
    from app.services.review_service import get_review_state
    current = get_review_state(db, question_id)
    if current and current["mastery_state"] == body.mastery_state:
        return ReviewStateResponse(**current)

    # Apply self-assessment policy (same as manual mastery)
    tz = ZoneInfo(settings.APP_TIMEZONE)
    business_today = datetime.now(tz).date()

    current_algo_json = None
    if current and current.get("policy_version"):
        from app.db.models.review import ReviewState as RSModel
        rs_row = db.query(RSModel.algorithm_state_json).filter(
            RSModel.question_id == question_id
        ).first()
        current_algo_json = rs_row[0] if rs_row else None

    policy_result = apply_self_assessment(
        mastery_state=body.mastery_state,
        business_today=business_today,
        current_mastery_state=current["mastery_state"] if current else None,
        current_consecutive_successes=current["consecutive_successes"] if current else 0,
        current_algorithm_state_json=current_algo_json,
    )

    upsert_review_state(
        db,
        question_id=question_id,
        mastery_state=policy_result.mastery_state,
        review_stage=policy_result.review_stage,
        next_review_date=policy_result.next_review_date,
        consecutive_successes=policy_result.consecutive_successes,
        policy_version=policy_result.policy_version,
        algorithm_state_json=policy_result.algorithm_state_json,
        # Manual update: don't change last_attempt_id, don't increment review_count
    )

    db.commit()

    result = get_review_state_or_default(db, question_id)
    return ReviewStateResponse(**result)