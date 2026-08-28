from __future__ import annotations

from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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


class Question(Base):
    __tablename__ = "question"
    __table_args__ = (
        CheckConstraint("difficulty >= 1 AND difficulty <= 5", name="ck_question_difficulty"),
        Index("ix_question_primary_knowledge_point_id", "primary_knowledge_point_id"),
        Index("ix_question_question_type", "question_type"),
        Index("ix_question_is_active", "is_active"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    question_type: Mapped[str] = mapped_column(String, nullable=False)
    primary_knowledge_point_id: Mapped[str] = mapped_column(
        String, ForeignKey("knowledge_point.id"), nullable=False
    )
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    tags_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[str] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[str] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class QuestionVersion(Base):
    __tablename__ = "question_version"
    __table_args__ = (
        ForeignKeyConstraint(
            ["question_id"],
            ["question.id"],
        ),
    )

    question_id: Mapped[str] = mapped_column(String, primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    source_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    source_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    imported_at: Mapped[str] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


class QuestionRelatedKnowledgePoint(Base):
    __tablename__ = "question_related_knowledge_point"
    __table_args__ = (
        ForeignKeyConstraint(
            ["question_id"],
            ["question.id"],
        ),
        ForeignKeyConstraint(
            ["knowledge_point_id"],
            ["knowledge_point.id"],
        ),
    )

    question_id: Mapped[str] = mapped_column(String, primary_key=True)
    knowledge_point_id: Mapped[str] = mapped_column(String, primary_key=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)