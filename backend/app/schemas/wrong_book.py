"""Pydantic schemas for Wrong Book API — Phase 6."""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel


class WrongBookItem(BaseModel):
    """A single item in the wrong book."""

    question_id: str
    title: Optional[str] = None
    question_type: str
    difficulty: int
    primary_knowledge_point_id: str
    primary_knowledge_point_name: Optional[str] = None
    mastery_state: Optional[str] = None
    next_review_date: Optional[date] = None
    wrong_book_mode: str = "auto"
    has_card: bool = False


class WrongBookResponse(BaseModel):
    """Response for GET /api/v1/wrong-book."""

    items: list[WrongBookItem]
    page: int
    page_size: int
    total: int


class WrongBookPreferenceRequest(BaseModel):
    """Request for PUT /api/v1/questions/{id}/wrong-book-preference."""

    mode: Literal["auto", "follow", "ignore"]