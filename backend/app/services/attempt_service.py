"""Attempt service — Task 4.4 + Step A feedback.

Handles attempt creation, answer saving, choice auto-grading,
client_request_id idempotency, question_revision version binding,
and correct_answer/explanation feedback for Choice.
Does NOT handle ReviewState, Wrong Book, DailyTask, or AI grading.
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

    Returns:
        {"attempt_id", "question_id", "question_revision", "answer",
         "is_correct", "score", "correct_answer", "explanation", "existed"}
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

    # 4. Determine scoring based on question type
    payload = json.loads(version.payload_json)

    is_correct: Optional[bool] = None
    score: Optional[float] = None
    max_score: Optional[float] = None
    final_score_source: Optional[str] = None
    correct_answer: Optional[str] = None
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
    # short_answer and sql: no auto-grading, no feedback

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

    try:
        db.commit()
        db.refresh(attempt)
    except IntegrityError:
        # UNIQUE(client_request_id) conflict — concurrent request
        db.rollback()
        existing = (
            db.query(Attempt)
            .filter(Attempt.client_request_id == str(client_request_id))
            .first()
        )
        if existing:
            return _build_response_from_existing(db, existing)
        raise

    return {
        "attempt_id": attempt.id,
        "question_id": attempt.question_id,
        "question_revision": attempt.question_revision,
        "answer": attempt.user_answer,
        "is_correct": is_correct,
        "score": score,
        "correct_answer": correct_answer,
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
        if q and q.question_type == "choice":
            correct_answer = payload.get("correct_answer")
            explanation = payload.get("explanation")

    return {
        "attempt_id": attempt.id,
        "question_id": attempt.question_id,
        "question_revision": attempt.question_revision,
        "answer": attempt.user_answer,
        "is_correct": is_correct,
        "score": score,
        "correct_answer": correct_answer,
        "explanation": explanation,
        "existed": True,
    }


class QuestionNotFoundError(Exception):
    """Question does not exist or is inactive."""


class InvalidRevisionError(Exception):
    """Specified question revision does not exist."""