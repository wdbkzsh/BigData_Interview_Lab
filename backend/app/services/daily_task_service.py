"""DailyTask Service — Phase 7A.

Generates and persists daily task snapshots. Supports skip/restore.
Does NOT handle Attempt completion (Phase 7B) or Dashboard (Phase 7C).
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.db.models.app_setting import AppSetting
from app.db.models.attempt import Attempt
from app.db.models.daily_task import DailyTask, DailyTaskItem
from app.db.models.knowledge import KnowledgePoint
from app.db.models.question import Question
from app.db.models.review import ReviewState


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULT_MAX_REVIEW = 15
_DEFAULT_CHOICE_COUNT = 3
_DEFAULT_SHORT_ANSWER_COUNT = 1
_DEFAULT_SQL_COUNT = 1
_DEFAULT_NEW_QUESTION_COUNT = (
    _DEFAULT_CHOICE_COUNT + _DEFAULT_SHORT_ANSWER_COUNT + _DEFAULT_SQL_COUNT
)

_MASTERY_PRIORITY = {
    "unmastered": 0,
    "vague": 1,
    "familiar": 2,
    "mastered": 3,
}

# Attempt statuses that indicate "not completed" / in-flight
_NON_TERMINAL_STATUSES = {
    "awaiting_self_assessment",
    "grading",
    "grading_failed",
    "awaiting_confirmation",
    "disputed",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_business_today() -> date:
    """Get current business date in APP_TIMEZONE."""
    tz = ZoneInfo(settings.APP_TIMEZONE)
    return datetime.now(tz).date()


def _get_setting_int(db: Session, key: str, default: int) -> int:
    """Read an integer setting from AppSetting, return default if missing."""
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if not row:
        return default
    try:
        return int(json.loads(row.value_json))
    except (json.JSONDecodeError, TypeError, ValueError):
        return default


def _get_quotas(db: Session) -> dict[str, int]:
    """Read new question quotas from AppSetting."""
    return {
        "choice_count": _get_setting_int(
            db, "daily.choice_count", _DEFAULT_CHOICE_COUNT
        ),
        "short_answer_count": _get_setting_int(
            db, "daily.short_answer_count", _DEFAULT_SHORT_ANSWER_COUNT
        ),
        "sql_count": _get_setting_int(
            db, "daily.sql_count", _DEFAULT_SQL_COUNT
        ),
    }


def _compute_aggregate_status(task_id: int, db: Session) -> str:
    """Compute DailyTask aggregate status from its items."""
    items = (
        db.query(DailyTaskItem.status)
        .filter(DailyTaskItem.daily_task_id == task_id)
        .all()
    )
    if not items:
        return "not_started"

    statuses = {s[0] for s in items}
    has_pending = "pending" in statuses
    has_terminal = "completed" in statuses or "skipped" in statuses

    if not has_pending and not has_terminal:
        return "not_started"
    if has_pending and not has_terminal:
        return "not_started"
    if has_pending and has_terminal:
        return "in_progress"
    # All terminal
    if "completed" in statuses:
        return "completed"
    # All skipped
    return "completed"


# ---------------------------------------------------------------------------
# Due Review Pool
# ---------------------------------------------------------------------------

def _get_due_reviews(db: Session, business_today: date, limit: int) -> list[dict]:
    """Get questions due for review, sorted by priority."""
    rows = (
        db.query(
            Question.id,
            Question.title,
            Question.question_type,
            Question.primary_knowledge_point_id,
            Question.current_revision,
            ReviewState.next_review_date,
            ReviewState.mastery_state,
            ReviewState.last_review_at,
        )
        .join(ReviewState, ReviewState.question_id == Question.id)
        .filter(
            ReviewState.next_review_date <= business_today,
            Question.is_active == True,  # noqa: E712
        )
        .all()
    )

    # Sort by priority
    def sort_key(r):
        nrd = r.next_review_date
        if isinstance(nrd, str):
            nrd = date.fromisoformat(nrd)
        overdue_days = (business_today - nrd).days if nrd else 0
        mastery_prio = _MASTERY_PRIORITY.get(r.mastery_state, 99)
        return (-overdue_days, mastery_prio, str(nrd) if nrd else "", str(r.last_review_at) if r.last_review_at else "")

    rows.sort(key=sort_key)
    return [
        {
            "question_id": r.id,
            "title": r.title,
            "question_type": r.question_type,
            "primary_knowledge_point_id": r.primary_knowledge_point_id,
            "current_revision": r.current_revision,
            "due_date_snapshot": str(r.next_review_date) if r.next_review_date else None,
        }
        for r in rows[:limit]
    ]


# ---------------------------------------------------------------------------
# New Question Pool
# ---------------------------------------------------------------------------

def _get_new_questions(
    db: Session,
    question_type: str,
    limit: int,
    exclude_ids: Optional[set[str]] = None,
) -> list[dict]:
    """Get questions that have never been attempted (no completed or in-flight attempt)."""
    # Subquery: questions with any completed or in-flight attempt
    attempted_ids = (
        db.query(Attempt.question_id)
        .filter(
            Attempt.status.in_(["completed"] + list(_NON_TERMINAL_STATUSES))
        )
        .distinct()
        .subquery()
    )

    query = (
        db.query(
            Question.id,
            Question.title,
            Question.question_type,
            Question.primary_knowledge_point_id,
            Question.current_revision,
        )
        .filter(
            Question.is_active == True,  # noqa: E712
            Question.question_type == question_type,
            ~Question.id.in_(db.query(attempted_ids.c.question_id)),
        )
    )

    if exclude_ids:
        query = query.filter(~Question.id.in_(exclude_ids))

    rows = (
        query
        .order_by(Question.difficulty.asc(), Question.id.asc())
        .limit(limit)
        .all()
    )

    return [
        {
            "question_id": r.id,
            "title": r.title,
            "question_type": r.question_type,
            "primary_knowledge_point_id": r.primary_knowledge_point_id,
            "current_revision": r.current_revision,
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Snapshot Generation
# ---------------------------------------------------------------------------

def _generate_snapshot(
    db: Session,
    daily_task: DailyTask,
    business_today: date,
) -> None:
    """Generate DailyTaskItems for a newly created DailyTask."""
    quotas = _get_quotas(db)
    max_review = _get_setting_int(db, "daily.max_review_count", _DEFAULT_MAX_REVIEW)

    # Track which question IDs are already selected (to avoid UNIQUE conflicts)
    selected_ids: set[str] = set()

    # 1. Due reviews
    reviews = _get_due_reviews(db, business_today, max_review)
    sort_order = 1
    for r in reviews:
        due = r["due_date_snapshot"]
        due_date = date.fromisoformat(due) if due and isinstance(due, str) else due
        item = DailyTaskItem(
            daily_task_id=daily_task.id,
            question_id=r["question_id"],
            question_revision=r["current_revision"],
            item_type="review",
            sort_order=sort_order,
            status="pending",
            due_date_snapshot=due_date,
        )
        db.add(item)
        selected_ids.add(r["question_id"])
        sort_order += 1

    # 2. New questions per type (exclude already-selected review questions)
    for qtype, quota_key in [
        ("choice", "choice_count"),
        ("short_answer", "short_answer_count"),
        ("sql", "sql_count"),
    ]:
        count = quotas[quota_key]
        if count <= 0:
            continue
        new_questions = _get_new_questions(db, qtype, count, exclude_ids=selected_ids)
        for nq in new_questions:
            if nq["question_id"] in selected_ids:
                continue
            item = DailyTaskItem(
                daily_task_id=daily_task.id,
                question_id=nq["question_id"],
                question_revision=nq["current_revision"],
                item_type="new",
                sort_order=sort_order,
                status="pending",
                due_date_snapshot=None,
            )
            db.add(item)
            selected_ids.add(nq["question_id"])
            sort_order += 1

    daily_task.new_question_target = sum(quotas.values())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_or_create_today(db: Session) -> dict[str, Any]:
    """Get or create today's DailyTask. Idempotent via UNIQUE(task_date)."""
    business_today = get_business_today()
    return _get_or_create_for_date(db, business_today)


def get_task_by_date(db: Session, task_date: date) -> Optional[dict[str, Any]]:
    """Get DailyTask for a specific date. Returns None if not exists."""
    task = db.query(DailyTask).filter(DailyTask.task_date == task_date).first()
    if not task:
        return None
    return _build_task_response(db, task)


def _get_or_create_for_date(db: Session, business_today: date) -> dict[str, Any]:
    """Get or create DailyTask for a given date."""
    # Check if already exists
    existing = db.query(DailyTask).filter(DailyTask.task_date == business_today).first()
    if existing:
        return _build_task_response(db, existing)

    # Try to create
    new_task = DailyTask(
        task_date=business_today,
        status="not_started",
        new_question_target=0,
    )
    db.add(new_task)

    try:
        db.flush()  # Get new_task.id
        _generate_snapshot(db, new_task, business_today)
        new_task.status = _compute_aggregate_status(new_task.id, db)
        db.commit()
        db.refresh(new_task)
    except IntegrityError:
        # UNIQUE conflict — another request created it
        db.rollback()
        existing = db.query(DailyTask).filter(DailyTask.task_date == business_today).first()
        if existing:
            return _build_task_response(db, existing)
        raise

    return _build_task_response(db, new_task)


def skip_item(db: Session, item_id: int) -> dict[str, Any]:
    """Skip a DailyTaskItem. Idempotent for skipped, 409 for completed."""
    item = db.query(DailyTaskItem).filter(DailyTaskItem.id == item_id).first()
    if not item:
        raise ItemNotFoundError()

    if item.status == "completed":
        raise ItemConflictError("已完成的任务不能跳过")

    if item.status == "skipped":
        # Idempotent
        return _build_item_response(db, item)

    # pending → skipped
    item.status = "skipped"
    task_status = _compute_aggregate_status(item.daily_task_id, db)
    task = db.query(DailyTask).filter(DailyTask.id == item.daily_task_id).first()
    if task:
        task.status = task_status
        if task_status == "completed":
            task.completed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(item)
    return _build_item_response(db, item)


def restore_item(db: Session, item_id: int) -> dict[str, Any]:
    """Restore a skipped DailyTaskItem. Idempotent for pending, 409 for completed."""
    item = db.query(DailyTaskItem).filter(DailyTaskItem.id == item_id).first()
    if not item:
        raise ItemNotFoundError()

    if item.status == "completed":
        raise ItemConflictError("已完成的任务不能恢复")

    if item.status == "pending":
        # Idempotent
        return _build_item_response(db, item)

    # skipped → pending
    item.status = "pending"
    task_status = _compute_aggregate_status(item.daily_task_id, db)
    task = db.query(DailyTask).filter(DailyTask.id == item.daily_task_id).first()
    if task:
        task.status = task_status
        if task_status != "completed":
            task.completed_at = None

    db.commit()
    db.refresh(item)
    return _build_item_response(db, item)


# ---------------------------------------------------------------------------
# Response builders
# ---------------------------------------------------------------------------

def _build_task_response(db: Session, task: DailyTask) -> dict[str, Any]:
    """Build DailyTask response dict."""
    items = (
        db.query(DailyTaskItem)
        .filter(DailyTaskItem.daily_task_id == task.id)
        .order_by(DailyTaskItem.sort_order.asc())
        .all()
    )

    # Batch-load KP names
    kp_ids = {item.question_id.split(".")[0] for item in items}  # fallback
    # Actually get from Question table
    q_ids = [item.question_id for item in items]
    kp_map: dict[str, dict[str, str]] = {}
    if q_ids:
        questions = (
            db.query(Question.id, Question.primary_knowledge_point_id)
            .filter(Question.id.in_(q_ids))
            .all()
        )
        kp_ids = {q.primary_knowledge_point_id for q in questions}
        if kp_ids:
            kps = (
                db.query(KnowledgePoint.id, KnowledgePoint.name)
                .filter(KnowledgePoint.id.in_(kp_ids))
                .all()
            )
            kp_names = {kp.id: kp.name for kp in kps}
            for q in questions:
                kp_map[q.id] = {
                    "id": q.primary_knowledge_point_id,
                    "name": kp_names.get(q.primary_knowledge_point_id),
                }

    # Build domain map
    domain_map: dict[str, dict[str, str]] = {}
    if kp_ids:
        all_kps: dict[str, tuple[Optional[str], str]] = {}
        to_load = set(kp_ids)
        while to_load:
            rows = (
                db.query(KnowledgePoint.id, KnowledgePoint.parent_id, KnowledgePoint.name)
                .filter(KnowledgePoint.id.in_(to_load))
                .all()
            )
            new_ids: set[str] = set()
            for r in rows:
                if r.id not in all_kps:
                    all_kps[r.id] = (r.parent_id, r.name)
                    if r.parent_id and r.parent_id not in all_kps:
                        new_ids.add(r.parent_id)
            to_load = new_ids

        for kp_id in kp_ids:
            current = kp_id
            visited = set()
            while current in all_kps and current not in visited:
                visited.add(current)
                parent_id, name = all_kps[current]
                if parent_id is None or parent_id not in all_kps:
                    domain_map[kp_id] = {"id": current, "name": name}
                    break
                current = parent_id
            else:
                if kp_id in all_kps:
                    domain_map[kp_id] = {"id": kp_id, "name": all_kps[kp_id][1]}

    # Get question titles and types
    q_info: dict[str, tuple[str, str]] = {}
    if q_ids:
        qrows = (
            db.query(Question.id, Question.title, Question.question_type)
            .filter(Question.id.in_(q_ids))
            .all()
        )
        q_info = {q.id: (q.title, q.question_type) for q in qrows}

    item_responses = []
    for item in items:
        kp = kp_map.get(item.question_id, {"id": "", "name": None})
        title, qtype = q_info.get(item.question_id, (None, "unknown"))
        domain = domain_map.get(kp["id"])

        item_responses.append({
            "id": item.id,
            "question_id": item.question_id,
            "question_revision": item.question_revision,
            "title": title,
            "question_type": qtype,
            "item_type": item.item_type,
            "status": item.status,
            "sort_order": item.sort_order,
            "due_date_snapshot": str(item.due_date_snapshot) if item.due_date_snapshot else None,
            "domain": domain,
            "primary_knowledge_point": kp,
        })

    return {
        "id": task.id,
        "task_date": str(task.task_date),
        "status": task.status,
        "new_question_target": task.new_question_target,
        "generated_at": str(task.generated_at) if task.generated_at else None,
        "completed_at": str(task.completed_at) if task.completed_at else None,
        "items": item_responses,
    }


def _build_item_response(db: Session, item: DailyTaskItem) -> dict[str, Any]:
    """Build DailyTaskItem response dict."""
    q = (
        db.query(Question.title, Question.question_type, Question.primary_knowledge_point_id)
        .filter(Question.id == item.question_id)
        .first()
    )
    title = q.title if q else None
    qtype = q.question_type if q else "unknown"
    kp_id = q.primary_knowledge_point_id if q else ""

    kp = (
        db.query(KnowledgePoint.id, KnowledgePoint.name)
        .filter(KnowledgePoint.id == kp_id)
        .first()
    )
    kp_data = {"id": kp.id, "name": kp.name} if kp else {"id": kp_id, "name": None}

    return {
        "id": item.id,
        "question_id": item.question_id,
        "question_revision": item.question_revision,
        "title": title,
        "question_type": qtype,
        "item_type": item.item_type,
        "status": item.status,
        "sort_order": item.sort_order,
        "due_date_snapshot": str(item.due_date_snapshot) if item.due_date_snapshot else None,
        "primary_knowledge_point": kp_data,
    }


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ItemNotFoundError(Exception):
    """DailyTaskItem does not exist."""


class ItemConflictError(Exception):
    """Item is in a state that conflicts with the requested operation."""