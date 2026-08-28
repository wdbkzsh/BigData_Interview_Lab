from __future__ import annotations

from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class KnowledgePoint(Base):
    __tablename__ = "knowledge_point"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    parent_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("knowledge_point.id"), nullable=True, default=None
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[str] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[str] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class KnowledgeCard(Base):
    __tablename__ = "knowledge_card"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    knowledge_point_id: Mapped[str] = mapped_column(
        String, ForeignKey("knowledge_point.id"), nullable=False, unique=True
    )
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[str] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[str] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class KnowledgeCardVersion(Base):
    __tablename__ = "knowledge_card_version"

    card_id: Mapped[str] = mapped_column(
        String, ForeignKey("knowledge_card.id"), primary_key=True
    )
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_json: Mapped[str] = mapped_column(Text, nullable=False)
    source_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    source_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    imported_at: Mapped[str] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


class KnowledgeCardProgress(Base):
    __tablename__ = "knowledge_card_progress"

    card_id: Mapped[str] = mapped_column(
        String, ForeignKey("knowledge_card.id"), primary_key=True
    )
    first_viewed_at: Mapped[Optional[str]] = mapped_column(
        DateTime, nullable=True, default=None
    )
    last_viewed_at: Mapped[Optional[str]] = mapped_column(
        DateTime, nullable=True, default=None
    )
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String, nullable=False, default="unread")