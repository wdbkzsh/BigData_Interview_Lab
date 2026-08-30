"""Pydantic schemas for Attempt API — Task 5.1 + Phase 5 self-assessment."""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel


class AttemptSubmitRequest(BaseModel):
    """Request body for POST /api/v1/questions/{id}/attempts."""

    question_revision: int
    attempt_type: Literal["new", "review", "practice"]
    client_request_id: UUID
    answer: str


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


class PendingAttemptItem(BaseModel):
    """A single pending attempt for recovery."""

    attempt_id: int
    question_id: str
    created_at: Optional[str] = None


class PendingAttemptsResponse(BaseModel):
    """Response for GET /api/v1/attempts/pending."""

    short_answer_self_assessment: list[PendingAttemptItem]