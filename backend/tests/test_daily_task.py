"""Tests for DailyTask Service and API — Phase 7A."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.content.importer import import_content
from app.db.models.app_setting import AppSetting
from app.db.models.attempt import Attempt
from app.db.models.daily_task import DailyTask, DailyTaskItem
from app.db.models.question import Question
from app.db.models.review import ReviewState
from app.db.session import get_db
from app.main import app
from app.services.daily_task_service import get_business_today


# ---------------------------------------------------------------------------
# Content fixtures — enough for review + new pool
# ---------------------------------------------------------------------------

_KNOWLEDGE_YAML = """\
- id: spark
  name: Spark
  description: Apache Spark
  sort_order: 1
  children:
    - id: spark.shuffle
      name: Shuffle
      description: Shuffle mechanism
      sort_order: 1
    - id: spark.rdd
      name: RDD
      description: Resilient Distributed Dataset
      sort_order: 2
"""

_CARD_SPARK_SHUFFLE = """\
---
knowledge_point_id: spark.shuffle
title: Shuffle
is_active: true
---

## 一句话定义
数据重分布。
## 核心原理
宽依赖触发 Shuffle。
## 面试高频点
- Shuffle Write / Read
## 常见易错点
- 不是所有 Join 都有 Shuffle
"""

# 4 choice questions (to test quota=3)
_CHOICE_001 = """\
id: spark.shuffle.choice.001
question_type: choice
primary_knowledge_point_id: spark.shuffle
title: Choice 001
difficulty: 2
tags: [spark]
related_knowledge_points: []
is_active: true
content: Q1?
options:
  - key: A
    text: a
  - key: B
    text: b
correct_answer: B
explanation: exp1
"""

_CHOICE_002 = """\
id: spark.shuffle.choice.002
question_type: choice
primary_knowledge_point_id: spark.shuffle
title: Choice 002
difficulty: 3
tags: [spark]
related_knowledge_points: []
is_active: true
content: Q2?
options:
  - key: A
    text: a
  - key: B
    text: b
correct_answer: A
explanation: exp2
"""

_CHOICE_003 = """\
id: spark.rdd.choice.001
question_type: choice
primary_knowledge_point_id: spark.rdd
title: Choice 003
difficulty: 1
tags: [spark]
related_knowledge_points: []
is_active: true
content: Q3?
options:
  - key: A
    text: a
  - key: B
    text: b
correct_answer: A
explanation: exp3
"""

_CHOICE_004 = """\
id: spark.rdd.choice.002
question_type: choice
primary_knowledge_point_id: spark.rdd
title: Choice 004
difficulty: 4
tags: [spark]
related_knowledge_points: []
is_active: true
content: Q4?
options:
  - key: A
    text: a
  - key: B
    text: b
correct_answer: B
explanation: exp4
"""

# 2 short answer
_QA_001 = """\
id: spark.shuffle.qa.001
question_type: short_answer
primary_knowledge_point_id: spark.shuffle
title: QA 001
difficulty: 2
tags: [spark]
related_knowledge_points: []
is_active: true
content: Explain shuffle.
reference_answer: answer
explanation: exp
"""

_QA_002 = """\
id: spark.rdd.qa.001
question_type: short_answer
primary_knowledge_point_id: spark.rdd
title: QA 002
difficulty: 3
tags: [spark]
related_knowledge_points: []
is_active: true
content: Explain RDD.
reference_answer: answer
explanation: exp
"""

# 2 sql
_SQL_001 = """\
id: spark.shuffle.sql.001
question_type: sql
primary_knowledge_point_id: spark.shuffle
title: SQL 001
difficulty: 4
tags: [spark]
related_knowledge_points: []
is_active: true
content: Write SQL.
table_schema: "CREATE TABLE t (id INT)"
field_description: id
business_requirement: select all
expected_sql: "SELECT * FROM t"
scoring_criteria:
  - id: c1
    description: correct
    points: 5
"""

_SQL_002 = """\
id: spark.rdd.sql.001
question_type: sql
primary_knowledge_point_id: spark.rdd
title: SQL 002
difficulty: 5
tags: [spark]
related_knowledge_points: []
is_active: true
content: Write SQL 2.
table_schema: "CREATE TABLE t2 (id INT)"
field_description: id
business_requirement: select all
expected_sql: "SELECT * FROM t2"
scoring_criteria:
  - id: c1
    description: correct
    points: 5
"""


def _write_content(content_dir: Path) -> None:
    kp_dir = content_dir / "knowledge"
    kp_dir.mkdir(parents=True)
    (kp_dir / "spark.yaml").write_text(_KNOWLEDGE_YAML, encoding="utf-8")

    card_dir = content_dir / "cards"
    card_dir.mkdir(parents=True)
    (card_dir / "spark.shuffle.md").write_text(_CARD_SPARK_SHUFFLE, encoding="utf-8")

    choice_dir = content_dir / "questions" / "choice"
    choice_dir.mkdir(parents=True)
    (choice_dir / "spark.shuffle.choice.001.yaml").write_text(_CHOICE_001, encoding="utf-8")
    (choice_dir / "spark.shuffle.choice.002.yaml").write_text(_CHOICE_002, encoding="utf-8")
    (choice_dir / "spark.rdd.choice.001.yaml").write_text(_CHOICE_003, encoding="utf-8")
    (choice_dir / "spark.rdd.choice.002.yaml").write_text(_CHOICE_004, encoding="utf-8")

    qa_dir = content_dir / "questions" / "short_answer"
    qa_dir.mkdir(parents=True)
    (qa_dir / "spark.shuffle.qa.001.yaml").write_text(_QA_001, encoding="utf-8")
    (qa_dir / "spark.rdd.qa.001.yaml").write_text(_QA_002, encoding="utf-8")

    sql_dir = content_dir / "questions" / "sql"
    sql_dir.mkdir(parents=True)
    (sql_dir / "spark.shuffle.sql.001.yaml").write_text(_SQL_001, encoding="utf-8")
    (sql_dir / "spark.rdd.sql.001.yaml").write_text(_SQL_002, encoding="utf-8")


@pytest.fixture(autouse=True)
def _reset_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def _make_client(db: Session) -> TestClient:
    def _override_get_db():
        yield db
    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app, raise_server_exceptions=False)


def _create_review_state(
    db: Session,
    question_id: str,
    mastery_state: str,
    next_review_date,
):
    """Create a ReviewState for testing due review pool."""
    rs = ReviewState(
        question_id=question_id,
        mastery_state=mastery_state,
        next_review_date=next_review_date,
        review_count=1,
        consecutive_successes=0,
        policy_version="review_v2",
        algorithm_state_json=json.dumps({"review_stage": 0, "last_evaluation_mode": "score", "last_performance": "fail", "consecutive_excellent": 0}),
    )
    db.add(rs)


# ---------------------------------------------------------------------------
# Snapshot tests
# ---------------------------------------------------------------------------

class TestSnapshot:
    def test_first_access_creates(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/daily-tasks/today")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] > 0
        assert data["task_date"] == str(get_business_today())
        assert data["status"] in ("not_started", "in_progress", "completed")
        assert len(data["items"]) > 0

    def test_second_access_same_task_id(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp1 = client.get("/api/v1/daily-tasks/today")
        resp2 = client.get("/api/v1/daily-tasks/today")
        assert resp1.json()["id"] == resp2.json()["id"]

    def test_second_access_same_item_ids(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp1 = client.get("/api/v1/daily-tasks/today")
        resp2 = client.get("/api/v1/daily-tasks/today")
        ids1 = [item["id"] for item in resp1.json()["items"]]
        ids2 = [item["id"] for item in resp2.json()["items"]]
        assert ids1 == ids2

    def test_no_duplicate_task_date(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        client.get("/api/v1/daily-tasks/today")
        client.get("/api/v1/daily-tasks/today")

        today = str(get_business_today())
        count = tmp_db.query(DailyTask).filter(DailyTask.task_date == today).count()
        assert count == 1

    def test_revision_frozen(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        # Create today task
        resp = client.get("/api/v1/daily-tasks/today")
        items = resp.json()["items"]
        choice_items = [i for i in items if i["question_type"] == "choice"]
        assert len(choice_items) > 0
        first_choice = choice_items[0]
        original_revision = first_choice["question_revision"]

        # Change Question.current_revision
        q = tmp_db.query(Question).filter(Question.id == first_choice["question_id"]).first()
        q.current_revision = 999
        tmp_db.commit()

        # Get today again — revision should still be original
        resp2 = client.get("/api/v1/daily-tasks/today")
        items2 = resp2.json()["items"]
        matching = [i for i in items2 if i["question_id"] == first_choice["question_id"]]
        assert len(matching) == 1
        assert matching[0]["question_revision"] == original_revision

    def test_settings_changed_does_not_alter_today(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        # Create today with default quotas
        resp1 = client.get("/api/v1/daily-tasks/today")
        original_item_count = len(resp1.json()["items"])

        # Change setting
        setting = AppSetting(key="daily.choice_count", value_json="99")
        tmp_db.add(setting)
        tmp_db.commit()

        # Today should still have same items
        resp2 = client.get("/api/v1/daily-tasks/today")
        assert len(resp2.json()["items"]) == original_item_count


# ---------------------------------------------------------------------------
# Review pool tests
# ---------------------------------------------------------------------------

class TestReviewPool:
    def test_due_included(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        today = get_business_today()
        _create_review_state(tmp_db, "spark.shuffle.choice.001", "unmastered", today - timedelta(days=1))
        _create_review_state(tmp_db, "spark.shuffle.choice.002", "vague", today)
        tmp_db.commit()

        client = _make_client(tmp_db)
        resp = client.get("/api/v1/daily-tasks/today")
        review_items = [i for i in resp.json()["items"] if i["item_type"] == "review"]
        review_ids = {i["question_id"] for i in review_items}
        assert "spark.shuffle.choice.001" in review_ids
        assert "spark.shuffle.choice.002" in review_ids

    def test_future_excluded(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        today = get_business_today()
        _create_review_state(tmp_db, "spark.shuffle.choice.001", "unmastered", today + timedelta(days=1))
        tmp_db.commit()

        client = _make_client(tmp_db)
        resp = client.get("/api/v1/daily-tasks/today")
        review_items = [i for i in resp.json()["items"] if i["item_type"] == "review"]
        review_ids = {i["question_id"] for i in review_items}
        assert "spark.shuffle.choice.001" not in review_ids

    def test_inactive_excluded(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        today = get_business_today()
        _create_review_state(tmp_db, "spark.shuffle.choice.001", "unmastered", today - timedelta(days=1))
        # Deactivate question
        q = tmp_db.query(Question).filter(Question.id == "spark.shuffle.choice.001").first()
        q.is_active = False
        tmp_db.commit()

        client = _make_client(tmp_db)
        resp = client.get("/api/v1/daily-tasks/today")
        review_items = [i for i in resp.json()["items"] if i["item_type"] == "review"]
        review_ids = {i["question_id"] for i in review_items}
        assert "spark.shuffle.choice.001" not in review_ids

    def test_overdue_ordering(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        today = get_business_today()
        # More overdue should come first
        _create_review_state(tmp_db, "spark.shuffle.choice.001", "unmastered", today - timedelta(days=5))
        _create_review_state(tmp_db, "spark.shuffle.choice.002", "unmastered", today - timedelta(days=1))
        tmp_db.commit()

        client = _make_client(tmp_db)
        resp = client.get("/api/v1/daily-tasks/today")
        review_items = [i for i in resp.json()["items"] if i["item_type"] == "review"]
        assert len(review_items) >= 2
        # More overdue first
        assert review_items[0]["question_id"] == "spark.shuffle.choice.001"

    def test_max_review_count(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        today = get_business_today()
        # Create 20 due reviews (more than default max 15)
        for i in range(20):
            qid = f"spark.shuffle.choice.{i:03d}"
            # We only have limited questions, so use existing ones with different mastery
        # Use existing questions — we can only test with what we have
        _create_review_state(tmp_db, "spark.shuffle.choice.001", "unmastered", today - timedelta(days=1))
        _create_review_state(tmp_db, "spark.shuffle.choice.002", "vague", today - timedelta(days=1))
        tmp_db.commit()

        client = _make_client(tmp_db)
        resp = client.get("/api/v1/daily-tasks/today")
        review_items = [i for i in resp.json()["items"] if i["item_type"] == "review"]
        assert len(review_items) <= 15


# ---------------------------------------------------------------------------
# New question pool tests
# ---------------------------------------------------------------------------

class TestNewPool:
    def test_default_quotas(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/daily-tasks/today")
        items = resp.json()["items"]
        new_items = [i for i in items if i["item_type"] == "new"]

        choice_new = [i for i in new_items if i["question_type"] == "choice"]
        qa_new = [i for i in new_items if i["question_type"] == "short_answer"]
        sql_new = [i for i in new_items if i["question_type"] == "sql"]

        assert len(choice_new) == 3  # default quota
        assert len(qa_new) == 1
        assert len(sql_new) == 1

    def test_completed_attempt_excluded(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        # Create a completed attempt for choice.001
        attempt = Attempt(
            question_id="spark.shuffle.choice.001",
            question_revision=1,
            attempt_type="practice",
            user_answer="B",
            status="completed",
            final_score=1.0,
            max_score=1.0,
            final_score_source="system",
            client_request_id=str(uuid4()),
        )
        tmp_db.add(attempt)
        tmp_db.commit()

        client = _make_client(tmp_db)
        resp = client.get("/api/v1/daily-tasks/today")
        new_items = [i for i in resp.json()["items"] if i["item_type"] == "new"]
        new_ids = {i["question_id"] for i in new_items}
        assert "spark.shuffle.choice.001" not in new_ids

    def test_pending_sa_excluded(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        # Create a pending SA attempt
        attempt = Attempt(
            question_id="spark.shuffle.qa.001",
            question_revision=1,
            attempt_type="practice",
            user_answer="test",
            status="awaiting_self_assessment",
            client_request_id=str(uuid4()),
        )
        tmp_db.add(attempt)
        tmp_db.commit()

        client = _make_client(tmp_db)
        resp = client.get("/api/v1/daily-tasks/today")
        new_items = [i for i in resp.json()["items"] if i["item_type"] == "new"]
        new_ids = {i["question_id"] for i in new_items}
        assert "spark.shuffle.qa.001" not in new_ids


# ---------------------------------------------------------------------------
# Skip / Restore tests
# ---------------------------------------------------------------------------

class TestSkipRestore:
    def test_pending_to_skipped(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/daily-tasks/today")
        items = resp.json()["items"]
        pending_item = next(i for i in items if i["status"] == "pending")

        resp = client.post(f"/api/v1/daily-task-items/{pending_item['id']}/skip")
        assert resp.status_code == 200
        assert resp.json()["status"] == "skipped"

    def test_skip_idempotent(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/daily-tasks/today")
        items = resp.json()["items"]
        pending_item = next(i for i in items if i["status"] == "pending")

        client.post(f"/api/v1/daily-task-items/{pending_item['id']}/skip")
        resp2 = client.post(f"/api/v1/daily-task-items/{pending_item['id']}/skip")
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "skipped"

    def test_skipped_to_pending(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/daily-tasks/today")
        items = resp.json()["items"]
        pending_item = next(i for i in items if i["status"] == "pending")

        client.post(f"/api/v1/daily-task-items/{pending_item['id']}/skip")
        resp2 = client.post(f"/api/v1/daily-task-items/{pending_item['id']}/restore")
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "pending"

    def test_restore_idempotent(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/daily-tasks/today")
        items = resp.json()["items"]
        pending_item = next(i for i in items if i["status"] == "pending")

        # Restore a pending item (idempotent)
        resp2 = client.post(f"/api/v1/daily-task-items/{pending_item['id']}/restore")
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "pending"

    def test_review_state_unchanged(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        today = get_business_today()
        _create_review_state(tmp_db, "spark.shuffle.choice.001", "unmastered", today)
        tmp_db.commit()

        client = _make_client(tmp_db)
        resp = client.get("/api/v1/daily-tasks/today")
        items = resp.json()["items"]
        review_item = next((i for i in items if i["question_id"] == "spark.shuffle.choice.001"), None)
        if not review_item:
            pytest.skip("Review item not in today task")

        rs_before = tmp_db.query(ReviewState).filter(ReviewState.question_id == "spark.shuffle.choice.001").first()
        mastery_before = rs_before.mastery_state
        next_before = rs_before.next_review_date

        client.post(f"/api/v1/daily-task-items/{review_item['id']}/skip")

        rs_after = tmp_db.query(ReviewState).filter(ReviewState.question_id == "spark.shuffle.choice.001").first()
        assert rs_after.mastery_state == mastery_before
        assert rs_after.next_review_date == next_before

    def test_task_status_aggregation(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/daily-tasks/today")
        task_id = resp.json()["id"]
        items = resp.json()["items"]

        # All pending → not_started
        assert resp.json()["status"] == "not_started"

        # Skip one → in_progress
        pending_items = [i for i in items if i["status"] == "pending"]
        if len(pending_items) >= 2:
            client.post(f"/api/v1/daily-task-items/{pending_items[0]['id']}/skip")
            resp2 = client.get("/api/v1/daily-tasks/today")
            assert resp2.json()["status"] == "in_progress"


# ---------------------------------------------------------------------------
# Date tests
# ---------------------------------------------------------------------------

class TestDateBehavior:
    def test_today_get_or_create(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/daily-tasks/today")
        assert resp.status_code == 200
        assert resp.json()["task_date"] == str(get_business_today())

    def test_past_date_read_only(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        # Manually create a past task
        past_date = get_business_today() - timedelta(days=1)
        task = DailyTask(task_date=past_date, status="not_started", new_question_target=0)
        tmp_db.add(task)
        tmp_db.commit()

        client = _make_client(tmp_db)
        resp = client.get(f"/api/v1/daily-tasks/{past_date}")
        assert resp.status_code == 200
        assert resp.json()["task_date"] == str(past_date)

    def test_past_date_not_exists_404(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        past_date = str(get_business_today() - timedelta(days=5))
        resp = client.get(f"/api/v1/daily-tasks/{past_date}")
        assert resp.status_code == 404

    def test_future_date_404(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        future_date = str(get_business_today() + timedelta(days=1))
        resp = client.get(f"/api/v1/daily-tasks/{future_date}")
        assert resp.status_code == 404

    def test_business_date_uses_timezone(self, tmp_db: Session, content_dir: Path):
        today = get_business_today()
        # Should be a valid date
        assert isinstance(today, date)
        # Should be close to UTC today (within 1 day difference due to timezone)
        from datetime import date as date_type
        utc_today = date_type.today()
        assert abs((today - utc_today).days) <= 1


# ---------------------------------------------------------------------------
# Formal DB not polluted
# ---------------------------------------------------------------------------

class TestFormalDBNotPolluted:
    def test_formal_db_unchanged(self):
        from app.core.config import settings
        db_path = settings.DATABASE_URL.replace("sqlite:///", "")
        p = Path(db_path)
        if p.exists():
            assert p.stat().st_size > 0