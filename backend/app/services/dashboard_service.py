"""Dashboard Service — Phase 7C1.

Provides aggregated dashboard data from existing facts.
Does NOT store statistics — computes in real-time.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.db.models.attempt import Attempt
from app.db.models.daily_task import DailyTask, DailyTaskItem
from app.db.models.question import Question
from app.db.models.review import ReviewState
from app.services.daily_task_service import get_or_create_today


def get_dashboard(db: Session) -> dict[str, Any]:
    """Build the full dashboard response."""
    tz = ZoneInfo(settings.APP_TIMEZONE)
    business_today = datetime.now(tz).date()

    # 1. Today task (get_or_create)
    task_data = get_or_create_today(db)

    # 2. Today summary from items
    today_summary = _build_today_summary(task_data)

    # 3. Review due/overdue counts
    review_data = _build_review_counts(db, business_today)

    # 4. Weekly stats
    week_data = _build_week_stats(db, business_today, tz)

    # 5. Pending attempts
    pending_data = _build_pending_counts(db)

    return {
        "today": {
            "date": str(business_today),
            "task_id": task_data["id"],
            "status": task_data["status"],
            **today_summary,
        },
        "review": review_data,
        "week": week_data,
        "pending": pending_data,
        "weak_knowledge_points": [],  # deferred to Phase 9
    }


def _build_today_summary(task_data: dict) -> dict[str, int]:
    """Aggregate today's task items into review/new totals."""
    items = task_data.get("items", [])

    review_total = 0
    review_completed = 0
    review_skipped = 0
    new_total = 0
    new_completed = 0
    new_skipped = 0

    for item in items:
        if item["item_type"] == "review":
            review_total += 1
            if item["status"] == "completed":
                review_completed += 1
            elif item["status"] == "skipped":
                review_skipped += 1
        elif item["item_type"] == "new":
            new_total += 1
            if item["status"] == "completed":
                new_completed += 1
            elif item["status"] == "skipped":
                new_skipped += 1

    return {
        "review_total": review_total,
        "review_completed": review_completed,
        "review_skipped": review_skipped,
        "new_total": new_total,
        "new_completed": new_completed,
        "new_skipped": new_skipped,
    }


def _build_review_counts(db: Session, business_today: date) -> dict[str, int]:
    """Count due and overdue review questions."""
    # due: next_review_date <= today AND question active
    due_count = (
        db.query(func.count())
        .select_from(ReviewState)
        .join(Question, Question.id == ReviewState.question_id)
        .filter(
            ReviewState.next_review_date <= business_today,
            Question.is_active == True,  # noqa: E712
        )
        .scalar()
    )

    # overdue: next_review_date < today AND question active
    overdue_count = (
        db.query(func.count())
        .select_from(ReviewState)
        .join(Question, Question.id == ReviewState.question_id)
        .filter(
            ReviewState.next_review_date < business_today,
            Question.is_active == True,  # noqa: E712
        )
        .scalar()
    )

    return {
        "due_count": due_count or 0,
        "overdue_count": overdue_count or 0,
    }


def _build_week_stats(
    db: Session, business_today: date, tz: ZoneInfo
) -> dict[str, Any]:
    """Compute current business week statistics."""
    # Monday of current week
    monday = business_today - timedelta(days=business_today.weekday())
    # End of week (next Monday)
    next_monday = monday + timedelta(days=7)

    # Convert to UTC datetime range for DB query
    monday_start = datetime(monday.year, monday.month, monday.day, tzinfo=tz)
    next_monday_start = datetime(next_monday.year, next_monday.month, next_monday.day, tzinfo=tz)

    # completed attempts this week
    completed_attempts = (
        db.query(func.count())
        .select_from(Attempt)
        .filter(
            Attempt.status == "completed",
            Attempt.created_at >= monday_start.astimezone(timezone.utc).replace(tzinfo=None),
            Attempt.created_at < next_monday_start.astimezone(timezone.utc).replace(tzinfo=None),
        )
        .scalar()
    )

    # study days: distinct business dates with completed attempts
    # SQLite stores naive UTC — need to convert
    week_attempts = (
        db.query(Attempt.created_at)
        .filter(
            Attempt.status == "completed",
            Attempt.created_at >= monday_start.astimezone(timezone.utc).replace(tzinfo=None),
            Attempt.created_at < next_monday_start.astimezone(timezone.utc).replace(tzinfo=None),
        )
        .all()
    )

    study_dates: set[date] = set()
    for (created_at,) in week_attempts:
        if created_at is not None:
            # naive datetime — assume UTC, convert to business date
            if created_at.tzinfo is None:
                aware = created_at.replace(tzinfo=timezone.utc)
            else:
                aware = created_at
            biz_date = aware.astimezone(tz).date()
            study_dates.add(biz_date)

    # choice accuracy
    choice_correct = (
        db.query(func.count())
        .select_from(Attempt)
        .join(Question, Question.id == Attempt.question_id)
        .filter(
            Attempt.status == "completed",
            Question.question_type == "choice",
            Attempt.final_score == Attempt.max_score,
            Attempt.final_score.isnot(None),
            Attempt.max_score.isnot(None),
            Attempt.created_at >= monday_start.astimezone(timezone.utc).replace(tzinfo=None),
            Attempt.created_at < next_monday_start.astimezone(timezone.utc).replace(tzinfo=None),
        )
        .scalar()
    )

    choice_total = (
        db.query(func.count())
        .select_from(Attempt)
        .join(Question, Question.id == Attempt.question_id)
        .filter(
            Attempt.status == "completed",
            Question.question_type == "choice",
            Attempt.final_score.isnot(None),
            Attempt.created_at >= monday_start.astimezone(timezone.utc).replace(tzinfo=None),
            Attempt.created_at < next_monday_start.astimezone(timezone.utc).replace(tzinfo=None),
        )
        .scalar()
    )

    accuracy = None
    if choice_total and choice_total > 0:
        accuracy = round(choice_correct / choice_total, 2)

    return {
        "completed_attempts": completed_attempts or 0,
        "study_days": len(study_dates),
        "choice_accuracy": accuracy,
    }


def _build_pending_counts(db: Session) -> dict[str, int]:
    """Count pending attempts by type."""
    # Short Answer awaiting self-assessment
    sa_pending = (
        db.query(func.count())
        .select_from(Attempt)
        .join(Question, Question.id == Attempt.question_id)
        .filter(
            Attempt.status == "awaiting_self_assessment",
            Question.question_type == "short_answer",
        )
        .scalar()
    )

    # SQL pending (grading/grading_failed/awaiting_confirmation/disputed)
    sql_pending = (
        db.query(func.count())
        .select_from(Attempt)
        .join(Question, Question.id == Attempt.question_id)
        .filter(
            Attempt.status.in_(["grading", "grading_failed", "awaiting_confirmation", "disputed"]),
            Question.question_type == "sql",
        )
        .scalar()
    )

    return {
        "short_answer_self_assessment": sa_pending or 0,
        "sql_assessment": sql_pending or 0,
    }