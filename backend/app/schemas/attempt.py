"""Pydantic schemas for Attempt API — Phase 8B."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel


class AttemptSubmitRequest(BaseModel):
    """Request body for POST /api/v1/questions/{id}/attempts."""

    question_revision: int
    attempt_type: Literal["new", "review", "practice"]
    client_request_id: UUID
    answer: str


class AssessmentData(BaseModel):
    """AI assessment data in attempt response."""

    assessment_id: int
    status: str
    raw_score: Optional[float] = None
    max_score: Optional[float] = None
    criteria: Optional[list[dict[str, Any]]] = None
    knowledge_analysis: Optional[dict[str, Any]] = None
    errors: Optional[list[str]] = None
    suggestions: Optional[list[str]] = None
    reasoning_summary: Optional[str] = None
    error_message: Optional[str] = None


class AttemptSubmitResponse(BaseModel):
    """Response for a successful attempt submission."""

    attempt_id: int
    question_id: str
    question_revision: int
    answer: str
    status: str
    is_correct: Optional[bool] = None
    score: Optional[float] = None
    correct_answer: Optional[str] = None
    reference_answer: Optional[str] = None
    explanation: Optional[str] = None
    # SQL fields
    assessment: Optional[AssessmentData] = None
    expected_sql: Optional[str] = None


# ---------------------------------------------------------------------------
# Self-Assessment (Phase 5)
# ---------------------------------------------------------------------------

class SelfAssessmentRequest(BaseModel):
    """Request body for POST /api/v1/attempts/{id}/self-assessment."""

    mastery_state: Literal["unmastered", "vague", "familiar", "mastered"]


class ReviewStateSnapshot(BaseModel):
    """ReviewState info returned after self-assessment."""

    mastery_state: str
    next_review_date: date
    policy_version: str


class SelfAssessmentResponse(BaseModel):
    """Response for a successful self-assessment."""

    attempt_id: int
    status: str
    self_assessed_mastery_state: str
    review_state: ReviewStateSnapshot


# ---------------------------------------------------------------------------
# Attempt detail / pending (recovery)
# ---------------------------------------------------------------------------

class AttemptDetailResponse(BaseModel):
    """Response for GET /api/v1/attempts/{id}."""

    id: int
    question_id: str
    question_revision: int
    attempt_type: str
    status: str
    answer: str
    self_assessed_mastery_state: Optional[str] = None
    reference_answer: Optional[str] = None
    explanation: Optional[str] = None
    # SQL recovery
    assessment: Optional[AssessmentData] = None
    expected_sql: Optional[str] = None


class PendingAttemptItem(BaseModel):
    """A single pending attempt for recovery."""

    attempt_id: int
    question_id: str
    question_revision: Optional[int] = None
    attempt_type: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[str] = None


# ---------------------------------------------------------------------------
# SQL Confirm (Phase 8C1)
# ---------------------------------------------------------------------------

class SQLConfirmRequest(BaseModel):
    """Request body for POST /api/v1/attempts/{id}/confirm."""

    action: Literal["accept", "adjust"]
    final_score: Optional[float] = None


class SQLConfirmResponse(BaseModel):
    """Response for SQL confirm."""

    attempt_id: int
    status: str
    final_score: Optional[float] = None
    max_score: Optional[float] = None
    final_score_source: Optional[str] = None
    mastery_state: Optional[str] = None
    next_review_date: Optional[str] = None
    policy_version: Optional[str] = None


class SQLDisputeRequest(BaseModel):
    """Request body for POST /api/v1/attempts/{id}/dispute."""

    reason: str


class SQLDisputeResponse(BaseModel):
    """Response for SQL dispute."""

    attempt_id: int
    status: str


class SQLRegradeResponse(BaseModel):
    """Response for SQL regrade."""

    attempt_id: int
    status: str
    assessment: Optional[AssessmentData] = None


class PendingAttemptsResponse(BaseModel):
    """Response for GET /api/v1/attempts/pending."""

    short_answer_self_assessment: list[PendingAttemptItem]
    sql_confirmation: list[PendingAttemptItem]
    sql_grading_failed: list[PendingAttemptItem]
    sql_disputed: list[PendingAttemptItem]
