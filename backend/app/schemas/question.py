"""Pydantic response schemas for Question API — Task 4.2."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class QuestionListItem(BaseModel):
    """A single item in the question list response."""

    id: str
    title: Optional[str]
    question_type: str
    difficulty: int


class QuestionListResponse(BaseModel):
    """Response for GET /api/v1/questions."""

    items: list[QuestionListItem]
    page: int
    page_size: int
    total: int


class KnowledgePointRef(BaseModel):
    """Reference to a knowledge point."""

    id: str
    name: Optional[str]


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