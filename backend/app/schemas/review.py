"""Pydantic schemas for ReviewState API — Phase 6."""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel


class ReviewStateResponse(BaseModel):
    """Response for GET /api/v1/questions/{id}/review-state."""

    question_id: str
    mastery_state: Optional[str] = None
    next_review_date: Optional[date] = None
    review_count: int = 0
    consecutive_successes: int = 0
    review_stage: Optional[int] = None
    policy_version: Optional[str] = None


class ManualMasteryRequest(BaseModel):
    """Request for PUT /api/v1/questions/{id}/review-state."""

    mastery_state: Literal["unmastered", "vague", "familiar", "mastered"]