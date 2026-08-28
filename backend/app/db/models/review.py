from __future__ import annotations

from typing import Optional

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReviewState(Base):
    __tablename__ = "review_state"
    __table_args__ = (
        Index("ix_review_state_next_review_date", "next_review_date"),
        Index("ix_review_state_mastery_state", "mastery_state"),
    )

    question_id: Mapped[str] = mapped_column(
        String, ForeignKey("question.id"), primary_key=True
    )
    mastery_state: Mapped[str] = mapped_column(String, nullable=False)
    last_attempt_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("attempt.id"), nullable=True, default=None
    )
    last_review_at: Mapped[Optional[str]] = mapped_column(
        DateTime, nullable=True, default=None
    )
    next_review_date: Mapped[Optional[str]] = mapped_column(
        Date, nullable=True, default=None
    )
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consecutive_successes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    policy_version: Mapped[str] = mapped_column(String, nullable=False)
    algorithm_state_json: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, default=None
    )
    updated_at: Mapped[str] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class QuestionPreference(Base):
    __tablename__ = "question_preference"

    question_id: Mapped[str] = mapped_column(
        String, ForeignKey("question.id"), primary_key=True
    )
    wrong_book_mode: Mapped[str] = mapped_column(
        String, nullable=False, default="auto"
    )
    updated_at: Mapped[str] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )