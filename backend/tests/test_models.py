"""Task 1.3 ORM Model metadata tests.

All tests inspect Base.metadata only — no database is created.
"""
import pytest
from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase

from app.db.base import Base
import app.db.models  # noqa: F401 — trigger model registration


# ---------------------------------------------------------------------------
# 1. Table registration
# ---------------------------------------------------------------------------

EXPECTED_TABLES = {
    "knowledge_point",
    "knowledge_card",
    "knowledge_card_version",
    "knowledge_card_progress",
    "question",
    "question_version",
    "question_related_knowledge_point",
    "attempt",
    "ai_assessment",
    "attempt_knowledge_result",
    "review_state",
    "question_preference",
    "daily_task",
    "daily_task_item",
    "app_setting",
}


def test_base_is_declarative():
    assert issubclass(Base, DeclarativeBase)


def test_metadata_contains_all_15_tables():
    registered = set(Base.metadata.tables.keys())
    assert registered == EXPECTED_TABLES, f"Missing: {EXPECTED_TABLES - registered}, Extra: {registered - EXPECTED_TABLES}"


@pytest.mark.parametrize("table_name", sorted(EXPECTED_TABLES))
def test_each_table_registered(table_name):
    assert table_name in Base.metadata.tables


# ---------------------------------------------------------------------------
# 2. Composite primary keys
# ---------------------------------------------------------------------------

def test_question_version_composite_pk():
    pk_cols = {c.name for c in Base.metadata.tables["question_version"].primary_key.columns}
    assert pk_cols == {"question_id", "revision"}


def test_knowledge_card_version_composite_pk():
    pk_cols = {c.name for c in Base.metadata.tables["knowledge_card_version"].primary_key.columns}
    assert pk_cols == {"card_id", "revision"}


def test_question_related_knowledge_point_composite_pk():
    pk_cols = {c.name for c in Base.metadata.tables["question_related_knowledge_point"].primary_key.columns}
    assert pk_cols == {"question_id", "knowledge_point_id"}


# ---------------------------------------------------------------------------
# 3. Composite foreign keys (Attempt → QuestionVersion, DailyTaskItem → QuestionVersion)
# ---------------------------------------------------------------------------

def _get_fk_names(table_name: str) -> list[set[str]]:
    """Return list of FK column-sets for the given table."""
    table = Base.metadata.tables[table_name]
    return [{c.name for c in fk.constraint.columns} for fk in table.foreign_keys]


def test_attempt_has_fk_to_question_version():
    table = Base.metadata.tables["attempt"]
    from sqlalchemy import ForeignKeyConstraint
    composite_fks = [
        c for c in table.constraints
        if isinstance(c, ForeignKeyConstraint) and len(c.columns) > 1
    ]
    assert len(composite_fks) >= 1, "Attempt must have a composite FK to question_version"
    fk = composite_fks[0]
    ref_cols = {e.column.name for e in fk.elements}
    assert ref_cols == {"question_id", "revision"}


def test_daily_task_item_has_fk_to_question_version():
    table = Base.metadata.tables["daily_task_item"]
    from sqlalchemy import ForeignKeyConstraint
    composite_fks = [
        c for c in table.constraints
        if isinstance(c, ForeignKeyConstraint) and len(c.columns) > 1
    ]
    assert len(composite_fks) >= 1, "DailyTaskItem must have a composite FK to question_version"
    fk = composite_fks[0]
    ref_cols = {e.column.name for e in fk.elements}
    assert ref_cols == {"question_id", "revision"}


# ---------------------------------------------------------------------------
# 4. CheckConstraint — difficulty 1..5
# ---------------------------------------------------------------------------

def test_question_difficulty_check_constraint():
    table = Base.metadata.tables["question"]
    checks = [c for c in table.constraints if isinstance(c, CheckConstraint)]
    difficulty_checks = [c for c in checks if "difficulty" in str(c.sqltext)]
    assert len(difficulty_checks) >= 1, "Question must have difficulty CheckConstraint"


# ---------------------------------------------------------------------------
# 5. Unique constraints
# ---------------------------------------------------------------------------

def _get_unique_column_sets(table_name: str) -> list[set[str]]:
    table = Base.metadata.tables[table_name]
    return [
        {c.name for c in uq.columns}
        for uq in table.constraints
        if isinstance(uq, UniqueConstraint)
    ]


def test_attempt_client_request_id_unique():
    uqs = _get_unique_column_sets("attempt")
    assert {"client_request_id"} in uqs


def test_daily_task_task_date_unique():
    uqs = _get_unique_column_sets("daily_task")
    assert {"task_date"} in uqs


def test_daily_task_item_unique_task_question():
    uqs = _get_unique_column_sets("daily_task_item")
    assert {"daily_task_id", "question_id"} in uqs


# ---------------------------------------------------------------------------
# 6. Indexes
# ---------------------------------------------------------------------------

def _get_index_column_sets(table_name: str) -> list[set[str]]:
    table = Base.metadata.tables[table_name]
    return [{c.name for c in idx.columns} for idx in table.indexes]


def test_attempt_indexes():
    idx_cols = _get_index_column_sets("attempt")
    assert {"question_id"} in idx_cols
    assert {"created_at"} in idx_cols
    assert {"status"} in idx_cols
    assert {"finalized_at"} in idx_cols


def test_review_state_indexes():
    idx_cols = _get_index_column_sets("review_state")
    assert {"next_review_date"} in idx_cols
    assert {"mastery_state"} in idx_cols


def test_question_indexes():
    idx_cols = _get_index_column_sets("question")
    assert {"primary_knowledge_point_id"} in idx_cols
    assert {"question_type"} in idx_cols
    assert {"is_active"} in idx_cols


def test_daily_task_item_indexes():
    idx_cols = _get_index_column_sets("daily_task_item")
    assert {"daily_task_id"} in idx_cols
    assert {"question_id"} in idx_cols


def test_attempt_knowledge_result_indexes():
    idx_cols = _get_index_column_sets("attempt_knowledge_result")
    assert {"knowledge_point_id"} in idx_cols
    assert {"attempt_id"} in idx_cols


# ---------------------------------------------------------------------------
# 7. Default values
# ---------------------------------------------------------------------------

def test_question_preference_wrong_book_mode_default():
    table = Base.metadata.tables["question_preference"]
    col = table.columns["wrong_book_mode"]
    assert col.default.arg == "auto", f"Expected default='auto', got {col.default.arg}"


# ---------------------------------------------------------------------------
# 8. Foreign key coverage (spot checks)
# ---------------------------------------------------------------------------

def _get_fk_targets(table_name: str) -> list[str]:
    table = Base.metadata.tables[table_name]
    return [fk.target_fullname for fk in table.foreign_keys]


def test_knowledge_point_parent_fk():
    targets = _get_fk_targets("knowledge_point")
    assert "knowledge_point.id" in targets


def test_question_primary_knowledge_point_fk():
    targets = _get_fk_targets("question")
    assert "knowledge_point.id" in targets


def test_knowledge_card_knowledge_point_fk():
    targets = _get_fk_targets("knowledge_card")
    assert "knowledge_point.id" in targets


def test_review_state_question_fk():
    targets = _get_fk_targets("review_state")
    assert "question.id" in targets


def test_ai_assessment_attempt_fk():
    targets = _get_fk_targets("ai_assessment")
    assert "attempt.id" in targets


def test_attempt_knowledge_result_attempt_fk():
    targets = _get_fk_targets("attempt_knowledge_result")
    assert "attempt.id" in targets
    assert "knowledge_point.id" in targets


def test_daily_task_item_daily_task_fk():
    targets = _get_fk_targets("daily_task_item")
    assert "daily_task.id" in targets


def test_knowledge_card_version_card_fk():
    targets = _get_fk_targets("knowledge_card_version")
    assert "knowledge_card.id" in targets