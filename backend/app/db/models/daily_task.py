from __future__ import annotations

from typing import Optional

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DailyTask(Base):
    __tablename__ = "daily_task"
    __table_args__ = (UniqueConstraint("task_date", name="uq_daily_task_task_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_date: Mapped[str] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    new_question_target: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_at: Mapped[str] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    completed_at: Mapped[Optional[str]] = mapped_column(
        DateTime, nullable=True, default=None
    )


class DailyTaskItem(Base):
    __tablename__ = "daily_task_item"
    __table_args__ = (
        ForeignKeyConstraint(
            ["question_id", "question_revision"],
            ["question_version.question_id", "question_version.revision"],
            name="fk_daily_task_item_question_version",
        ),
        UniqueConstraint(
            "daily_task_id", "question_id", name="uq_daily_task_item_task_question"
        ),
        Index("ix_daily_task_item_daily_task_id", "daily_task_id"),
        Index("ix_daily_task_item_question_id", "question_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    daily_task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("daily_task.id"), nullable=False
    )
    question_id: Mapped[str] = mapped_column(String, nullable=False)
    question_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    item_type: Mapped[str] = mapped_column(String, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    due_date_snapshot: Mapped[Optional[str]] = mapped_column(
        Date, nullable=True, default=None
    )
    completed_attempt_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("attempt.id"), nullable=True, default=None
    )
    created_at: Mapped[str] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )