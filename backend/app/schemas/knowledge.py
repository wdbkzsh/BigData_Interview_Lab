"""Pydantic response schemas for Knowledge API — Task 3.1."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class KnowledgePointTreeNode(BaseModel):
    """Recursive tree node for GET /api/v1/knowledge-points."""

    id: str
    name: str
    level: int
    children: list[KnowledgePointTreeNode] = Field(default_factory=list)


class KnowledgePointDetail(BaseModel):
    """Detail for GET /api/v1/knowledge-points/{id}."""

    id: str
    name: str
    description: Optional[str]
    question_count: int
    has_card: bool


class CardContent(BaseModel):
    """Structured card content parsed from content_json."""

    title: str
    one_line_definition: str
    core_principle: str
    interview_highlights: str
    common_mistakes: str


class KnowledgeCardResponse(BaseModel):
    """Response for GET /api/v1/knowledge-points/{id}/card."""

    id: str
    knowledge_point_id: str
    revision: int
    content: CardContent
