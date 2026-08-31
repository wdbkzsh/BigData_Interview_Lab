"""Pydantic schemas for DailyTask API — Phase 7A."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class DomainRef(BaseModel):
    id: str
    name: Optional[str]


class KnowledgePointRef(BaseModel):
    id: str
    name: Optional[str]


class DailyTaskItemResponse(BaseModel):
    id: int
    question_id: str
    question_revision: int
    title: Optional[str]
    question_type: str
    item_type: str
    status: str
    sort_order: int
    due_date_snapshot: Optional[str]
    domain: Optional[DomainRef] = None
    primary_knowledge_point: Optional[KnowledgePointRef] = None


class DailyTaskResponse(BaseModel):
    id: int
    task_date: str
    status: str
    new_question_target: int
    generated_at: Optional[str]
    completed_at: Optional[str]
    items: list[DailyTaskItemResponse]