"""Pydantic response schemas for Question API — Phase 6.5."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from pydantic import BaseModel


class KnowledgePointRef(BaseModel):
    """Reference to a knowledge point."""

    id: str
    name: Optional[str]


class ReviewStateSummary(BaseModel):
    """Summary of ReviewState for question list items."""

    mastery_state: str
    next_review_date: Optional[str] = None


class QuestionListItem(BaseModel):
    """A single item in the question list response."""

    id: str
    title: Optional[str]
    question_type: str
    difficulty: int
    primary_knowledge_point: KnowledgePointRef
    review_state: Optional[ReviewStateSummary] = None
    pending_self_assessment_attempt_id: Optional[int] = None


class QuestionListResponse(BaseModel):
    """Response for GET /api/v1/questions."""

    items: list[QuestionListItem]
    page: int
    page_size: int
    total: int


class ChoiceOption(BaseModel):
    """A single choice option (without correctness info)."""

    key: str
    text: str


class QuestionDetailResponse(BaseModel):
    """Response for GET /api/v1/questions/{id}.

    Fields vary by question_type — only relevant fields are present.
    """

    id: str
    revision: int
    question_type: str
    difficulty: int
    primary_knowledge_point: KnowledgePointRef

    # Choice: content + options
    content: Optional[str] = None
    options: Optional[list[ChoiceOption]] = None

    # SQL: additional fields
    table_schema: Optional[str] = None
    field_description: Optional[str] = None
    business_requirement: Optional[str] = None