from __future__ import annotations

from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Attempt(Base):
    __tablename__ = "attempt"
    __table_args__ = (
        ForeignKeyConstraint(
            ["question_id", "question_revision"],
            ["question_version.question_id", "question_version.revision"],
            name="fk_attempt_question_version",
        ),
        UniqueConstraint("client_request_id", name="uq_attempt_client_request_id"),
        Index("ix_attempt_question_id", "question_id"),
        Index("ix_attempt_created_at", "created_at"),
        Index("ix_attempt_status", "status"),
        Index("ix_attempt_finalized_at", "finalized_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_id: Mapped[str] = mapped_column(String, nullable=False)
    question_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    daily_task_item_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("daily_task_item.id"), nullable=True, default=None
    )
    attempt_type: Mapped[str] = mapped_column(String, nullable=False)
    user_answer: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    self_assessed_mastery_state: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, default=None
    )
    final_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    max_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    final_result_json: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, default=None
    )
    final_score_source: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, default=None
    )
    client_request_id: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, default=None
    )
    created_at: Mapped[str] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    finalized_at: Mapped[Optional[str]] = mapped_column(
        DateTime, nullable=True, default=None
    )
    review_applied_at: Mapped[Optional[str]] = mapped_column(
        DateTime, nullable=True, default=None
    )


class AIAssessment(Base):
    __tablename__ = "ai_assessment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attempt_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("attempt.id"), nullable=False
    )
    provider: Mapped[Optional[str]] = mapped_column(String, nullable=True, default=None)
    model: Mapped[Optional[str]] = mapped_column(String, nullable=True, default=None)
    prompt_version: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    raw_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    max_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    result_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=None)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=None)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=None)
    created_at: Mapped[str] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


class AttemptKnowledgeResult(Base):
    __tablename__ = "attempt_knowledge_result"
    __table_args__ = (
        Index("ix_attempt_knowledge_result_knowledge_point_id", "knowledge_point_id"),
        Index("ix_attempt_knowledge_result_attempt_id", "attempt_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attempt_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("attempt.id"), nullable=False
    )
    knowledge_point_id: Mapped[str] = mapped_column(
        String, ForeignKey("knowledge_point.id"), nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(String, nullable=False)
    earned_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    max_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    detail_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)