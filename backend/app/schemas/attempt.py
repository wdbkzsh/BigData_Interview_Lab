"""Pydantic schemas for Attempt API — Task 5.1."""

from __future__ import annotations

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