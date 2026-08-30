"""Attempt service — Phase 6.

Handles attempt creation, answer saving, choice auto-grading,
client_request_id idempotency, question_revision version binding,
feedback for Choice / Short Answer, self-assessment, and Choice→ReviewState.
Does NOT handle Wrong Book, DailyTask, or AI grading.
"""

from __future__ import annotations

import json
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.attempt import Attempt
from app.db.models.question import Question, QuestionVersion


def create_attempt(
    db: Session,
    *,
    question_id: str,
    question_revision: int,
    attempt_type: str,
    client_request_id: UUID,
    answer: str,
) -> dict[str, Any]:
    """Create an attempt for a question with idempotency.

    Returns dict with attempt fields + feedback.
    Raises:
        QuestionNotFoundError: question not found or inactive
        InvalidRevisionError: specified revision does not exist
    """
    # 1. Idempotency: check if client_request_id already exists
    existing = (
        db.query(Attempt)
        .filter(Attempt.client_request_id == str(client_request_id))
        .first()
    )
    if existing:
        return _build_response_from_existing(db, existing)

    # 2. Validate question exists and is active
    q = (
        db.query(Question)
        .filter(
            Question.id == question_id,
            Question.is_active == True,  # noqa: E712
        )
        .first()
    )
    if not q:
        raise QuestionNotFoundError()

    # 3. Get specified version (not current_revision)
    version = (
        db.query(QuestionVersion)
        .filter(
            QuestionVersion.question_id == q.id,
            QuestionVersion.revision == question_revision,
        )
        .first()
    )
    if not version:
        raise InvalidRevisionError()

    # 4. Determine status and scoring based on question type
    payload = json.loads(version.payload_json)

    is_correct: Optional[bool] = None
    score: Optional[float] = None
    max_score: Optional[float] = None
    final_score_source: Optional[str] = None
    correct_answer: Optional[str] = None
    reference_answer: Optional[str] = None
    explanation: Optional[str] = None
    status = "completed"

    if q.question_type == "choice":
        ca = payload.get("correct_answer", "")
        correct_answer = ca
        explanation = payload.get("explanation")
        is_correct = answer.strip() == ca.strip()
        score = 1.0 if is_correct else 0.0
        max_score = 1.0
        final_score_source = "system"

    elif q.question_type == "short_answer":
        status = "awaiting_self_assessment"
        reference_answer = payload.get("reference_answer")
        explanation = payload.get("explanation")
        # No auto-grading: is_correct, score, max_score remain None

    # sql: status="completed", no auto-grading, no feedback

    # 5. Create attempt
    attempt = Attempt(
        question_id=q.id,
        question_revision=question_revision,
        attempt_type=attempt_type,
        user_answer=answer,
        status=status,
        final_score=score,
        max_score=max_score,
        final_score_source=final_score_source,
        client_request_id=str(client_request_id),
    )
    db.add(attempt)

    # 6. Flush to get attempt.id without committing
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(Attempt)
            .filter(Attempt.client_request_id == str(client_request_id))
            .first()
        )
        if existing:
            return _build_response_from_existing(db, existing)
        raise

    # 7. Choice: apply score-based ReviewState in same transaction
    if q.question_type == "choice" and score is not None and max_score is not None:
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo
        from app.core.config import settings
        from app.review.policy import apply_score_based
        from app.services.review_service import get_review_state, upsert_review_state

        tz = ZoneInfo(settings.APP_TIMEZONE)
        business_today = datetime.now(tz).date()

        current_rs = get_review_state(db, q.id)
        current_mastery = current_rs["mastery_state"] if current_rs else None
        current_consecutive = current_rs["consecutive_successes"] if current_rs else 0
        current_algo_json = None
        if current_rs and current_rs.get("policy_version"):
            from app.db.models.review import ReviewState as RSModel
            rs_row = db.query(RSModel.algorithm_state_json).filter(
                RSModel.question_id == q.id
            ).first()
            current_algo_json = rs_row[0] if rs_row else None

        policy_result = apply_score_based(
            final_score=score,
            max_score=max_score,
            business_today=business_today,
            current_mastery_state=current_mastery,
            current_consecutive_successes=current_consecutive,
            current_algorithm_state_json=current_algo_json,
        )

        now = datetime.now(timezone.utc)
        upsert_review_state(
            db,
            question_id=q.id,
            mastery_state=policy_result.mastery_state,
            review_stage=policy_result.review_stage,
            next_review_date=policy_result.next_review_date,
            consecutive_successes=policy_result.consecutive_successes,
            policy_version=policy_result.policy_version,
            algorithm_state_json=policy_result.algorithm_state_json,
            last_attempt_id=attempt.id,
            increment_review_count=(attempt_type == "review"),
        )
        attempt.review_applied_at = now

    # 8. Single commit for everything
    try:
        db.commit()
        db.refresh(attempt)
    except Exception:
        db.rollback()
        raise

    return _build_new_response(
        attempt,
        is_correct=is_correct,
        score=score,
        correct_answer=correct_answer,
        reference_answer=reference_answer,
        explanation=explanation,
    )


def _build_new_response(
    attempt: Attempt,
    *,
    is_correct: Optional[bool],
    score: Optional[float],
    correct_answer: Optional[str],
    reference_answer: Optional[str],
    explanation: Optional[str],
) -> dict[str, Any]:
    """Build response dict for a newly created attempt."""
    return {
        "attempt_id": attempt.id,
        "question_id": attempt.question_id,
        "question_revision": attempt.question_revision,
        "answer": attempt.user_answer,
        "status": attempt.status,
        "is_correct": is_correct,
        "score": score,
        "correct_answer": correct_answer,
        "reference_answer": reference_answer,
        "explanation": explanation,
        "existed": False,
    }


def _build_response_from_existing(db: Session, attempt: Attempt) -> dict[str, Any]:
    """Build response for an idempotent hit (existing attempt).

    Reads QuestionVersion.payload_json using the attempt's question_id
    and question_revision (NOT current_revision).
    """
    is_correct: Optional[bool] = None
    score: Optional[float] = None
    correct_answer: Optional[str] = None
    reference_answer: Optional[str] = None
    explanation: Optional[str] = None

    if attempt.final_score is not None and attempt.max_score is not None:
        score = attempt.final_score
        is_correct = score == attempt.max_score

    # Read feedback from the QuestionVersion this attempt was graded against
    version = (
        db.query(QuestionVersion)
        .filter(
            QuestionVersion.question_id == attempt.question_id,
            QuestionVersion.revision == attempt.question_revision,
        )
        .first()
    )
    if version:
        payload = json.loads(version.payload_json)
        q = (
            db.query(Question.question_type)
            .filter(Question.id == attempt.question_id)
            .first()
        )
        if q:
            if q.question_type == "choice":
                correct_answer = payload.get("correct_answer")
                explanation = payload.get("explanation")
            elif q.question_type == "short_answer":
                reference_answer = payload.get("reference_answer")
                explanation = payload.get("explanation")

    return {
        "attempt_id": attempt.id,
        "question_id": attempt.question_id,
        "question_revision": attempt.question_revision,
        "answer": attempt.user_answer,
        "status": attempt.status,
        "is_correct": is_correct,
        "score": score,
        "correct_answer": correct_answer,
        "reference_answer": reference_answer,
        "explanation": explanation,
        "existed": True,
    }


class QuestionNotFoundError(Exception):
    """Question does not exist or is inactive."""


class InvalidRevisionError(Exception):
    """Specified question revision does not exist."""


# ---------------------------------------------------------------------------
# Self-Assessment (Phase 5)
# ---------------------------------------------------------------------------

def submit_self_assessment(
    db: Session,
    *,
    attempt_id: int,
    mastery_state: str,
) -> dict[str, Any]:
    """Submit self-assessment for a short-answer attempt.

    Uses conditional UPDATE as the first state change to claim processing
    rights. Prevents concurrent double-application of ReviewState.

    Returns:
        {"attempt_id", "status", "self_assessed_mastery_state",
         "review_state": {"mastery_state", "next_review_date", "policy_version"},
         "existed": bool}
    Raises:
        AttemptNotFoundError: attempt does not exist
        InvalidSelfAssessmentError: attempt not in correct state
        SelfAssessmentConflictError: already completed with different mastery_state
    """
    from datetime import datetime, timezone

    from sqlalchemy import update
    from zoneinfo import ZoneInfo

    from app.core.config import settings
    from app.db.models.question import Question
    from app.db.models.review import ReviewState
    from app.review.policy import apply_self_assessment

    now = datetime.now(timezone.utc)

    # 1. Atomic claim: conditional UPDATE as first state change
    stmt = (
        update(Attempt)
        .where(
            Attempt.id == attempt_id,
            Attempt.status == "awaiting_self_assessment",
            Attempt.review_applied_at.is_(None),
        )
        .values(
            self_assessed_mastery_state=mastery_state,
            status="completed",
            finalized_at=now,
        )
    )
    result = db.execute(stmt)

    if result.rowcount == 1:
        # ---- Claimed processing rights ----
        attempt = db.query(Attempt).filter(Attempt.id == attempt_id).first()

        # Validate question_type (after claim — if invalid, we rollback)
        q = (
            db.query(Question.question_type, Question.id)
            .filter(Question.id == attempt.question_id)
            .first()
        )
        if not q or q.question_type != "short_answer":
            db.rollback()
            raise InvalidSelfAssessmentError("只有问答题可以自评")

        # Get current ReviewState
        current_rs = (
            db.query(ReviewState)
            .filter(ReviewState.question_id == attempt.question_id)
            .first()
        )
        current_mastery = current_rs.mastery_state if current_rs else None
        current_consecutive = current_rs.consecutive_successes if current_rs else 0
        current_algo_json = current_rs.algorithm_state_json if current_rs else None

        # Apply review policy
        tz = ZoneInfo(settings.APP_TIMEZONE)
        business_today = datetime.now(tz).date()

        policy_result = apply_self_assessment(
            mastery_state=mastery_state,
            business_today=business_today,
            current_mastery_state=current_mastery,
            current_consecutive_successes=current_consecutive,
            current_algorithm_state_json=current_algo_json,
        )

        # Upsert ReviewState
        if current_rs:
            current_rs.mastery_state = policy_result.mastery_state
            current_rs.last_attempt_id = attempt.id
            current_rs.last_review_at = now
            current_rs.next_review_date = policy_result.next_review_date
            if attempt.attempt_type == "review":
                current_rs.review_count += 1
            current_rs.consecutive_successes = policy_result.consecutive_successes
            current_rs.policy_version = policy_result.policy_version
            current_rs.algorithm_state_json = policy_result.algorithm_state_json
        else:
            new_rs = ReviewState(
                question_id=attempt.question_id,
                mastery_state=policy_result.mastery_state,
                last_attempt_id=attempt.id,
                last_review_at=now,
                next_review_date=policy_result.next_review_date,
                review_count=1 if attempt.attempt_type == "review" else 0,
                consecutive_successes=policy_result.consecutive_successes,
                policy_version=policy_result.policy_version,
                algorithm_state_json=policy_result.algorithm_state_json,
            )
            db.add(new_rs)

        attempt.review_applied_at = now

        try:
            db.commit()
            db.refresh(attempt)
        except Exception:
            db.rollback()
            raise

        rs = (
            db.query(ReviewState)
            .filter(ReviewState.question_id == attempt.question_id)
            .first()
        )
        return _build_self_assessment_response(attempt, rs, existed=False)

    # ---- rowcount == 0: claim failed ----
    # Re-read attempt to determine the reason
    attempt = db.query(Attempt).filter(Attempt.id == attempt_id).first()
    if not attempt:
        raise AttemptNotFoundError()

    # Check question_type for proper error message
    q = (
        db.query(Question.question_type)
        .filter(Question.id == attempt.question_id)
        .first()
    )
    if not q or q.question_type != "short_answer":
        raise InvalidSelfAssessmentError("只有问答题可以自评")

    # Already completed — check idempotent vs conflict
    if attempt.status == "completed" and attempt.review_applied_at is not None:
        if attempt.self_assessed_mastery_state == mastery_state:
            rs = (
                db.query(ReviewState)
                .filter(ReviewState.question_id == attempt.question_id)
                .first()
            )
            return _build_self_assessment_response(attempt, rs, existed=True)
        else:
            raise SelfAssessmentConflictError()

    # Other non-awaiting state → 409 (state conflict, not request error)
    raise SelfAssessmentConflictError()


def _build_self_assessment_response(
    attempt: Attempt,
    review_state: Optional[Any],
    *,
    existed: bool,
) -> dict[str, Any]:
    """Build response for self-assessment."""
    rs_snapshot = None
    if review_state:
        rs_snapshot = {
            "mastery_state": review_state.mastery_state,
            "next_review_date": review_state.next_review_date,
            "policy_version": review_state.policy_version,
        }

    return {
        "attempt_id": attempt.id,
        "status": attempt.status,
        "self_assessed_mastery_state": attempt.self_assessed_mastery_state,
        "review_state": rs_snapshot,
        "existed": existed,
    }


class AttemptNotFoundError(Exception):
    """Attempt does not exist."""


class InvalidSelfAssessmentError(Exception):
    """Attempt is not in a valid state for self-assessment."""


class SelfAssessmentConflictError(Exception):
    """Attempt already completed with a different mastery_state."""


# ---------------------------------------------------------------------------
# Attempt detail / pending (recovery)
# ---------------------------------------------------------------------------

def get_attempt_detail(db: Session, attempt_id: int) -> Optional[dict[str, Any]]:
    """Get attempt detail with reference_answer/explanation for awaiting SA."""
    attempt = db.query(Attempt).filter(Attempt.id == attempt_id).first()
    if not attempt:
        return None

    result: dict[str, Any] = {
        "id": attempt.id,
        "question_id": attempt.question_id,
        "question_revision": attempt.question_revision,
        "attempt_type": attempt.attempt_type,
        "status": attempt.status,
        "answer": attempt.user_answer,
        "self_assessed_mastery_state": attempt.self_assessed_mastery_state,
    }

    # For awaiting self-assessment, include reference_answer/explanation
    if attempt.status == "awaiting_self_assessment":
        from app.db.models.question import Question, QuestionVersion

        q = (
            db.query(Question.question_type)
            .filter(Question.id == attempt.question_id)
            .first()
        )
        if q and q.question_type == "short_answer":
            version = (
                db.query(QuestionVersion)
                .filter(
                    QuestionVersion.question_id == attempt.question_id,
                    QuestionVersion.revision == attempt.question_revision,
                )
                .first()
            )
            if version:
                payload = json.loads(version.payload_json)
                result["reference_answer"] = payload.get("reference_answer")
                result["explanation"] = payload.get("explanation")

    return result


def get_pending_attempts(db: Session) -> dict[str, list[dict[str, Any]]]:
    """Get all attempts awaiting self-assessment."""
    rows = (
        db.query(Attempt)
        .filter(Attempt.status == "awaiting_self_assessment")
        .order_by(Attempt.created_at.asc())
        .all()
    )

    items = [
        {
            "attempt_id": r.id,
            "question_id": r.question_id,
            "created_at": str(r.created_at) if r.created_at else None,
        }
        for r in rows
    ]

    return {"short_answer_self_assessment": items}