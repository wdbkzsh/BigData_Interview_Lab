"""Task 1.5 — Real SQLite constraint behaviour tests.

Every test creates an isolated temporary database via tmp_path + Alembic upgrade head.
The formal data/app.db is never touched.
"""
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.session import create_db_engine
from tests.test_migration import run_alembic, BACKEND_DIR

# ---------------------------------------------------------------------------
# Fixture: tmp engine with foreign_keys=ON
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary SQLite database with Alembic schema and FK enabled."""
    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    result = run_alembic(["upgrade", "head"], db_url)
    assert result.returncode == 0, f"upgrade head failed: {result.stderr}"
    engine = create_db_engine(db_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db(tmp_db):
    """Provide a raw sqlite3.Connection with foreign_keys=ON for direct constraint tests."""
    url = str(tmp_db.url)
    # Extract path from sqlite:/// URL
    db_path = url.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# 1. foreign_keys = 1
# ---------------------------------------------------------------------------

def test_foreign_keys_enabled(tmp_db):
    with tmp_db.connect() as conn:
        result = conn.execute(text("PRAGMA foreign_keys"))
        assert result.scalar() == 1


# ---------------------------------------------------------------------------
# 2. FK: knowledge_point.parent_id → nonexistent
# ---------------------------------------------------------------------------

def test_fk_knowledge_point_parent_nonexistent(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO knowledge_point (id, name, level, sort_order, is_active, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
            ("kp.child", "Child", 2, 0, 1),
        )
        # Now insert with a parent that doesn't exist
        db.execute(
            "INSERT INTO knowledge_point (id, parent_id, name, level, sort_order, is_active, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
            ("kp.orphan", "kp.nonexistent", "Orphan", 2, 0, 1),
        )
        db.commit()


# ---------------------------------------------------------------------------
# 3. FK: question.primary_knowledge_point_id → nonexistent
# ---------------------------------------------------------------------------

def test_fk_question_primary_kp_nonexistent(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO question (id, question_type, primary_knowledge_point_id, difficulty, current_revision, is_active, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
            ("q.001", "choice", "kp.nonexistent", 3, 1, 1),
        )
        db.commit()


# ---------------------------------------------------------------------------
# 4. FK: Attempt (question_id, question_revision) → nonexistent QuestionVersion
# ---------------------------------------------------------------------------

def test_fk_attempt_question_version_nonexistent(db):
    # Insert a valid question first
    db.execute(
        "INSERT INTO knowledge_point (id, name, level, sort_order, is_active, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
        ("kp.1", "KP1", 1, 0, 1),
    )
    db.execute(
        "INSERT INTO question (id, question_type, primary_knowledge_point_id, difficulty, current_revision, is_active, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
        ("q.1", "choice", "kp.1", 3, 1, 1),
    )
    db.commit()
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO attempt (question_id, question_revision, attempt_type, user_answer, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            ("q.1", 999, "new", "A", "completed"),
        )
        db.commit()


# ---------------------------------------------------------------------------
# 5. FK: DailyTaskItem (question_id, question_revision) → nonexistent QuestionVersion
# ---------------------------------------------------------------------------

def test_fk_daily_task_item_question_version_nonexistent(db):
    # Valid daily_task
    db.execute(
        "INSERT INTO daily_task (task_date, status, new_question_target, generated_at) "
        "VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
        ("2026-01-01", "active", 5),
    )
    db.commit()
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO daily_task_item (daily_task_id, question_id, question_revision, item_type, sort_order, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (1, "q.nonexistent", 1, "new", 1, "pending"),
        )
        db.commit()


# ---------------------------------------------------------------------------
# 6. PK: QuestionVersion composite duplicate
# ---------------------------------------------------------------------------

def test_question_version_composite_pk_duplicate(db):
    db.execute(
        "INSERT INTO knowledge_point (id, name, level, sort_order, is_active, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
        ("kp.1", "KP1", 1, 0, 1),
    )
    db.execute(
        "INSERT INTO question (id, question_type, primary_knowledge_point_id, difficulty, current_revision, is_active, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
        ("q.1", "choice", "kp.1", 3, 1, 1),
    )
    db.execute(
        "INSERT INTO question_version (question_id, revision, payload_json, imported_at) "
        "VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
        ("q.1", 1, "{}"),
    )
    db.commit()
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO question_version (question_id, revision, payload_json, imported_at) "
            "VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            ("q.1", 1, "{}"),
        )
        db.commit()


# ---------------------------------------------------------------------------
# 7. PK: QuestionVersion different revision allowed
# ---------------------------------------------------------------------------

def test_question_version_different_revision_allowed(db):
    db.execute(
        "INSERT INTO knowledge_point (id, name, level, sort_order, is_active, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
        ("kp.1", "KP1", 1, 0, 1),
    )
    db.execute(
        "INSERT INTO question (id, question_type, primary_knowledge_point_id, difficulty, current_revision, is_active, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
        ("q.1", "choice", "kp.1", 3, 1, 1),
    )
    db.execute(
        "INSERT INTO question_version (question_id, revision, payload_json, imported_at) "
        "VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
        ("q.1", 1, "{}"),
    )
    db.execute(
        "INSERT INTO question_version (question_id, revision, payload_json, imported_at) "
        "VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
        ("q.1", 2, "{}"),
    )
    db.commit()
    cursor = db.execute("SELECT COUNT(*) FROM question_version WHERE question_id = 'q.1'")
    assert cursor.fetchone()[0] == 2


# ---------------------------------------------------------------------------
# 8. UNIQUE: attempt.client_request_id duplicate non-NULL
# ---------------------------------------------------------------------------

def test_attempt_client_request_id_unique_duplicate(db):
    db.execute(
        "INSERT INTO knowledge_point (id, name, level, sort_order, is_active, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
        ("kp.1", "KP1", 1, 0, 1),
    )
    db.execute(
        "INSERT INTO question (id, question_type, primary_knowledge_point_id, difficulty, current_revision, is_active, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
        ("q.1", "choice", "kp.1", 3, 1, 1),
    )
    db.execute(
        "INSERT INTO question_version (question_id, revision, payload_json, imported_at) "
        "VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
        ("q.1", 1, "{}"),
    )
    db.execute(
        "INSERT INTO attempt (question_id, question_revision, attempt_type, user_answer, status, client_request_id, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
        ("q.1", 1, "new", "A", "completed", "req-001"),
    )
    db.commit()
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO attempt (question_id, question_revision, attempt_type, user_answer, status, client_request_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            ("q.1", 1, "new", "B", "completed", "req-001"),
        )
        db.commit()


# ---------------------------------------------------------------------------
# 9. UNIQUE: attempt.client_request_id multiple NULL allowed
# ---------------------------------------------------------------------------

def test_attempt_client_request_id_multiple_null_allowed(db):
    db.execute(
        "INSERT INTO knowledge_point (id, name, level, sort_order, is_active, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
        ("kp.1", "KP1", 1, 0, 1),
    )
    db.execute(
        "INSERT INTO question (id, question_type, primary_knowledge_point_id, difficulty, current_revision, is_active, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
        ("q.1", "choice", "kp.1", 3, 1, 1),
    )
    db.execute(
        "INSERT INTO question_version (question_id, revision, payload_json, imported_at) "
        "VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
        ("q.1", 1, "{}"),
    )
    db.execute(
        "INSERT INTO attempt (question_id, question_revision, attempt_type, user_answer, status, client_request_id, created_at) "
        "VALUES (?, ?, ?, ?, ?, NULL, CURRENT_TIMESTAMP)",
        ("q.1", 1, "new", "A", "completed"),
    )
    db.execute(
        "INSERT INTO attempt (question_id, question_revision, attempt_type, user_answer, status, client_request_id, created_at) "
        "VALUES (?, ?, ?, ?, ?, NULL, CURRENT_TIMESTAMP)",
        ("q.1", 1, "new", "B", "completed"),
    )
    db.commit()
    cursor = db.execute("SELECT COUNT(*) FROM attempt")
    assert cursor.fetchone()[0] == 2


# ---------------------------------------------------------------------------
# 10. UNIQUE: daily_task.task_date duplicate
# ---------------------------------------------------------------------------

def test_daily_task_task_date_unique_duplicate(db):
    db.execute(
        "INSERT INTO daily_task (task_date, status, new_question_target, generated_at) "
        "VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
        ("2026-01-01", "active", 5),
    )
    db.commit()
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO daily_task (task_date, status, new_question_target, generated_at) "
            "VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            ("2026-01-01", "active", 3),
        )
        db.commit()


# ---------------------------------------------------------------------------
# 11. UNIQUE: daily_task_item (daily_task_id, question_id) duplicate
# ---------------------------------------------------------------------------

def test_daily_task_item_unique_task_question_duplicate(db):
    db.execute(
        "INSERT INTO knowledge_point (id, name, level, sort_order, is_active, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
        ("kp.1", "KP1", 1, 0, 1),
    )
    db.execute(
        "INSERT INTO question (id, question_type, primary_knowledge_point_id, difficulty, current_revision, is_active, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
        ("q.1", "choice", "kp.1", 3, 1, 1),
    )
    db.execute(
        "INSERT INTO question_version (question_id, revision, payload_json, imported_at) "
        "VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
        ("q.1", 1, "{}"),
    )
    db.execute(
        "INSERT INTO daily_task (task_date, status, new_question_target, generated_at) "
        "VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
        ("2026-01-01", "active", 5),
    )
    db.execute(
        "INSERT INTO daily_task_item (daily_task_id, question_id, question_revision, item_type, sort_order, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
        (1, "q.1", 1, "new", 1, "pending"),
    )
    db.commit()
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO daily_task_item (daily_task_id, question_id, question_revision, item_type, sort_order, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (1, "q.1", 1, "new", 2, "pending"),
        )
        db.commit()


# ---------------------------------------------------------------------------
# 12. UNIQUE: knowledge_card.knowledge_point_id duplicate
# ---------------------------------------------------------------------------

def test_knowledge_card_knowledge_point_id_unique_duplicate(db):
    db.execute(
        "INSERT INTO knowledge_point (id, name, level, sort_order, is_active, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
        ("kp.1", "KP1", 1, 0, 1),
    )
    db.execute(
        "INSERT INTO knowledge_card (id, knowledge_point_id, current_revision, is_active, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
        ("kc.1", "kp.1", 1, 1),
    )
    db.commit()
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO knowledge_card (id, knowledge_point_id, current_revision, is_active, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
            ("kc.2", "kp.1", 1, 1),
        )
        db.commit()


# ---------------------------------------------------------------------------
# 13. CHECK: difficulty boundaries
# ---------------------------------------------------------------------------

def _insert_question(db, qid, difficulty):
    """Helper to insert a question with given difficulty."""
    db.execute(
        "INSERT INTO knowledge_point (id, name, level, sort_order, is_active, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
        ("kp.1", "KP1", 1, 0, 1),
    )
    db.execute(
        "INSERT INTO question (id, question_type, primary_knowledge_point_id, difficulty, current_revision, is_active, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
        (qid, "choice", "kp.1", difficulty, 1, 1),
    )
    db.commit()


def test_check_difficulty_0_fails(db):
    with pytest.raises(sqlite3.IntegrityError):
        _insert_question(db, "q.0", 0)


def test_check_difficulty_6_fails(db):
    with pytest.raises(sqlite3.IntegrityError):
        _insert_question(db, "q.6", 6)


def test_check_difficulty_1_succeeds(db):
    _insert_question(db, "q.1", 1)
    cursor = db.execute("SELECT difficulty FROM question WHERE id = 'q.1'")
    assert cursor.fetchone()[0] == 1


def test_check_difficulty_5_succeeds(db):
    _insert_question(db, "q.5", 5)
    cursor = db.execute("SELECT difficulty FROM question WHERE id = 'q.5'")
    assert cursor.fetchone()[0] == 5


# ---------------------------------------------------------------------------
# 14. WAL
# ---------------------------------------------------------------------------

def test_journal_mode_wal(tmp_db):
    with tmp_db.connect() as conn:
        result = conn.execute(text("PRAGMA journal_mode"))
        assert result.scalar() == "wal"


# ---------------------------------------------------------------------------
# 15. Circular FK: normal business insert flow
# ---------------------------------------------------------------------------

def test_circular_fk_normal_flow(db):
    """Test that the circular FK between attempt ↔ daily_task_item works with proper ordering."""
    # Setup: knowledge_point → question → question_version
    db.execute(
        "INSERT INTO knowledge_point (id, name, level, sort_order, is_active, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
        ("kp.1", "KP1", 1, 0, 1),
    )
    db.execute(
        "INSERT INTO question (id, question_type, primary_knowledge_point_id, difficulty, current_revision, is_active, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
        ("q.1", "choice", "kp.1", 3, 1, 1),
    )
    db.execute(
        "INSERT INTO question_version (question_id, revision, payload_json, imported_at) "
        "VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
        ("q.1", 1, "{}"),
    )
    # daily_task
    db.execute(
        "INSERT INTO daily_task (task_date, status, new_question_target, generated_at) "
        "VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
        ("2026-01-01", "active", 5),
    )
    # daily_task_item (completed_attempt_id is NULL initially)
    db.execute(
        "INSERT INTO daily_task_item (daily_task_id, question_id, question_revision, item_type, sort_order, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
        (1, "q.1", 1, "new", 1, "pending"),
    )
    # attempt (references daily_task_item)
    db.execute(
        "INSERT INTO attempt (question_id, question_revision, daily_task_item_id, attempt_type, user_answer, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
        ("q.1", 1, 1, "new", "A", "completed"),
    )
    db.commit()

    # Verify both rows exist
    cursor = db.execute("SELECT COUNT(*) FROM attempt")
    assert cursor.fetchone()[0] == 1
    cursor = db.execute("SELECT COUNT(*) FROM daily_task_item")
    assert cursor.fetchone()[0] == 1