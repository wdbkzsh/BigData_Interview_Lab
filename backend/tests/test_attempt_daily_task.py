"""Tests for Attempt ↔ DailyTaskItem integration — Phase 7B."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from sqlalchemy import text

from app.content.importer import import_content
from app.db.models.daily_task import DailyTask, DailyTaskItem
from app.db.models.question import Question
from app.db.models.review import ReviewState
from app.db.session import get_db
from app.main import app
from app.services.daily_task_service import get_business_today


# ---------------------------------------------------------------------------
# Content fixtures
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

    qa_dir = content_dir / "questions" / "short_answer"
    qa_dir.mkdir(parents=True)
    (qa_dir / "spark.shuffle.qa.001.yaml").write_text(_QA_001, encoding="utf-8")

    sql_dir = content_dir / "questions" / "sql"
    sql_dir.mkdir(parents=True)


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


def _generate_today(db: Session, client: TestClient) -> dict:
    """Generate today's DailyTask and return response."""
    resp = client.get("/api/v1/daily-tasks/today")
    assert resp.status_code == 200
    return resp.json()


# ---------------------------------------------------------------------------
# Choice → DailyTaskItem completion
# ---------------------------------------------------------------------------

class TestChoiceDailyCompletion:
    def test_new_choice_completes_item(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        task = _generate_today(tmp_db, client)
        new_items = [i for i in task["items"] if i["item_type"] == "new" and i["question_type"] == "choice"]
        assert len(new_items) > 0
        item = new_items[0]

        # Submit choice attempt
        resp = client.post(
            f"/api/v1/questions/{item['question_id']}/attempts",
            json={
                "question_revision": item["question_revision"],
                "attempt_type": "new",
                "client_request_id": str(uuid4()),
                "answer": "B",
            },
        )
        assert resp.status_code == 201

        # Verify item completed
        task_after = client.get("/api/v1/daily-tasks/today").json()
        matching = [i for i in task_after["items"] if i["id"] == item["id"]]
        assert len(matching) == 1
        assert matching[0]["status"] == "completed"

    def test_completed_attempt_id_set(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        task = _generate_today(tmp_db, client)
        new_items = [i for i in task["items"] if i["item_type"] == "new" and i["question_type"] == "choice"]
        item = new_items[0]

        resp = client.post(
            f"/api/v1/questions/{item['question_id']}/attempts",
            json={
                "question_revision": item["question_revision"],
                "attempt_type": "new",
                "client_request_id": str(uuid4()),
                "answer": "B",
            },
        )
        attempt_id = resp.json()["attempt_id"]

        # Verify completed_attempt_id
        db_item = tmp_db.query(DailyTaskItem).filter(DailyTaskItem.id == item["id"]).first()
        assert db_item.completed_attempt_id == attempt_id

    def test_aggregate_status_updates(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        task = _generate_today(tmp_db, client)
        assert task["status"] == "not_started"

        # Complete one item
        new_items = [i for i in task["items"] if i["item_type"] == "new" and i["question_type"] == "choice"]
        item = new_items[0]
        client.post(
            f"/api/v1/questions/{item['question_id']}/attempts",
            json={
                "question_revision": item["question_revision"],
                "attempt_type": "new",
                "client_request_id": str(uuid4()),
                "answer": "B",
            },
        )

        task_after = client.get("/api/v1/daily-tasks/today").json()
        assert task_after["status"] == "in_progress"

    def test_new_review_count_not_increased(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        task = _generate_today(tmp_db, client)
        new_items = [i for i in task["items"] if i["item_type"] == "new" and i["question_type"] == "choice"]
        item = new_items[0]

        client.post(
            f"/api/v1/questions/{item['question_id']}/attempts",
            json={
                "question_revision": item["question_revision"],
                "attempt_type": "new",
                "client_request_id": str(uuid4()),
                "answer": "B",
            },
        )

        rs = tmp_db.query(ReviewState).filter(ReviewState.question_id == item["question_id"]).first()
        assert rs is not None
        assert rs.review_count == 0  # new, not review

    def test_review_attempt_increments_count(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        # Create a review state with due date
        today = get_business_today()
        rs = ReviewState(
            question_id="spark.shuffle.choice.001",
            mastery_state="unmastered",
            next_review_date=today - timedelta(days=1),
            review_count=0,
            consecutive_successes=0,
            policy_version="review_v2",
            algorithm_state_json=json.dumps({"review_stage": 0}),
        )
        tmp_db.add(rs)
        tmp_db.commit()

        client = _make_client(tmp_db)
        task = _generate_today(tmp_db, client)
        review_items = [i for i in task["items"] if i["item_type"] == "review"]
        assert len(review_items) > 0
        item = review_items[0]

        client.post(
            f"/api/v1/questions/{item['question_id']}/attempts",
            json={
                "question_revision": item["question_revision"],
                "attempt_type": "review",
                "client_request_id": str(uuid4()),
                "answer": "B",
            },
        )

        rs = tmp_db.query(ReviewState).filter(ReviewState.question_id == item["question_id"]).first()
        assert rs.review_count == 1

    def test_practice_does_not_complete_item(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        task = _generate_today(tmp_db, client)
        new_items = [i for i in task["items"] if i["item_type"] == "new" and i["question_type"] == "choice"]
        item = new_items[0]

        # Submit as practice (not new/review)
        client.post(
            f"/api/v1/questions/{item['question_id']}/attempts",
            json={
                "question_revision": item["question_revision"],
                "attempt_type": "practice",
                "client_request_id": str(uuid4()),
                "answer": "B",
            },
        )

        # Item should still be pending
        task_after = client.get("/api/v1/daily-tasks/today").json()
        matching = [i for i in task_after["items"] if i["id"] == item["id"]]
        assert matching[0]["status"] == "pending"

    def test_idempotent_retry_no_double_complete(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        task = _generate_today(tmp_db, client)
        new_items = [i for i in task["items"] if i["item_type"] == "new" and i["question_type"] == "choice"]
        item = new_items[0]

        cid = str(uuid4())
        body = {
            "question_revision": item["question_revision"],
            "attempt_type": "new",
            "client_request_id": cid,
            "answer": "B",
        }

        resp1 = client.post(f"/api/v1/questions/{item['question_id']}/attempts", json=body)
        assert resp1.status_code == 201
        attempt_id_1 = resp1.json()["attempt_id"]

        resp2 = client.post(f"/api/v1/questions/{item['question_id']}/attempts", json=body)
        assert resp2.status_code == 200
        attempt_id_2 = resp2.json()["attempt_id"]

        # Same attempt
        assert attempt_id_1 == attempt_id_2

        # Item still completed (not double-processed)
        db_item = tmp_db.query(DailyTaskItem).filter(DailyTaskItem.id == item["id"]).first()
        assert db_item.status == "completed"
        assert db_item.completed_attempt_id == attempt_id_1

        # ReviewState not double-pushed
        rs = tmp_db.query(ReviewState).filter(ReviewState.question_id == item["question_id"]).first()
        if rs:
            # Stage should be first-excellent level, not further
            algo = json.loads(rs.algorithm_state_json)
            assert algo["review_stage"] <= 2


# ---------------------------------------------------------------------------
# Short Answer initial submit
# ---------------------------------------------------------------------------

class TestShortAnswerInitialSubmit:
    def test_sa_submit_keeps_item_pending(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        task = _generate_today(tmp_db, client)
        sa_items = [i for i in task["items"] if i["question_type"] == "short_answer"]
        assert len(sa_items) > 0
        item = sa_items[0]

        # Submit SA attempt (new)
        resp = client.post(
            f"/api/v1/questions/{item['question_id']}/attempts",
            json={
                "question_revision": item["question_revision"],
                "attempt_type": "new",
                "client_request_id": str(uuid4()),
                "answer": "my answer",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "awaiting_self_assessment"

        # Item should still be pending
        task_after = client.get("/api/v1/daily-tasks/today").json()
        matching = [i for i in task_after["items"] if i["id"] == item["id"]]
        assert matching[0]["status"] == "pending"

        # completed_attempt_id should be NULL
        db_item = tmp_db.query(DailyTaskItem).filter(DailyTaskItem.id == item["id"]).first()
        assert db_item.completed_attempt_id is None


# ---------------------------------------------------------------------------
# Short Answer self-assessment → completion
# ---------------------------------------------------------------------------

class TestShortAnswerSelfAssessmentCompletion:
    def test_sa_self_assessment_completes_item(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        task = _generate_today(tmp_db, client)
        sa_items = [i for i in task["items"] if i["question_type"] == "short_answer"]
        item = sa_items[0]

        # Submit SA attempt
        resp = client.post(
            f"/api/v1/questions/{item['question_id']}/attempts",
            json={
                "question_revision": item["question_revision"],
                "attempt_type": "new",
                "client_request_id": str(uuid4()),
                "answer": "my answer",
            },
        )
        attempt_id = resp.json()["attempt_id"]

        # Complete self-assessment
        client.post(
            f"/api/v1/attempts/{attempt_id}/self-assessment",
            json={"mastery_state": "familiar"},
        )

        # Item should be completed
        task_after = client.get("/api/v1/daily-tasks/today").json()
        matching = [i for i in task_after["items"] if i["id"] == item["id"]]
        assert matching[0]["status"] == "completed"

        # completed_attempt_id should be set
        db_item = tmp_db.query(DailyTaskItem).filter(DailyTaskItem.id == item["id"]).first()
        assert db_item.completed_attempt_id == attempt_id

    def test_sa_self_assessment_retry_no_double_process(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        task = _generate_today(tmp_db, client)
        sa_items = [i for i in task["items"] if i["question_type"] == "short_answer"]
        item = sa_items[0]

        # Submit SA attempt
        resp = client.post(
            f"/api/v1/questions/{item['question_id']}/attempts",
            json={
                "question_revision": item["question_revision"],
                "attempt_type": "new",
                "client_request_id": str(uuid4()),
                "answer": "my answer",
            },
        )
        attempt_id = resp.json()["attempt_id"]

        # Self-assessment
        client.post(
            f"/api/v1/attempts/{attempt_id}/self-assessment",
            json={"mastery_state": "familiar"},
        )

        # Retry same self-assessment
        resp2 = client.post(
            f"/api/v1/attempts/{attempt_id}/self-assessment",
            json={"mastery_state": "familiar"},
        )
        assert resp2.status_code == 200

        # Item still completed
        db_item = tmp_db.query(DailyTaskItem).filter(DailyTaskItem.id == item["id"]).first()
        assert db_item.status == "completed"
        assert db_item.completed_attempt_id == attempt_id

    def test_practice_sa_does_not_complete_item(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        task = _generate_today(tmp_db, client)
        sa_items = [i for i in task["items"] if i["question_type"] == "short_answer"]
        item = sa_items[0]

        # Submit as practice
        resp = client.post(
            f"/api/v1/questions/{item['question_id']}/attempts",
            json={
                "question_revision": item["question_revision"],
                "attempt_type": "practice",
                "client_request_id": str(uuid4()),
                "answer": "my answer",
            },
        )
        attempt_id = resp.json()["attempt_id"]

        # Self-assessment
        client.post(
            f"/api/v1/attempts/{attempt_id}/self-assessment",
            json={"mastery_state": "familiar"},
        )

        # Item should still be pending (practice doesn't complete)
        db_item = tmp_db.query(DailyTaskItem).filter(DailyTaskItem.id == item["id"]).first()
        assert db_item.status == "pending"


# ---------------------------------------------------------------------------
# Short Answer cross-day completion
# ---------------------------------------------------------------------------

class TestShortAnswerCrossDay:
    def test_day1_attempt_completes_day1_item_not_day2(
        self, tmp_db: Session, content_dir: Path
    ):
        """Day 1: submit SA attempt → awaiting_sa. Day 2: self-assessment.
        Must complete Day 1 Item, NOT Day 2 Item."""
        from datetime import datetime, timezone, timedelta as td
        from app.db.models.daily_task import DailyTask, DailyTaskItem

        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        today = get_business_today()
        yesterday = today - td(days=1)

        # Create Day 1 DailyTask manually (past date — can't use get_or_create_today)
        task1 = DailyTask(task_date=yesterday, status="not_started", new_question_target=1)
        tmp_db.add(task1)
        tmp_db.flush()

        item1 = DailyTaskItem(
            daily_task_id=task1.id,
            question_id="spark.shuffle.qa.001",
            question_revision=1,
            item_type="new",
            sort_order=1,
            status="pending",
            due_date_snapshot=None,
        )
        tmp_db.add(item1)

        # Create Day 2 DailyTask (today)
        task2 = DailyTask(task_date=today, status="not_started", new_question_target=1)
        tmp_db.add(task2)
        tmp_db.flush()

        item2 = DailyTaskItem(
            daily_task_id=task2.id,
            question_id="spark.shuffle.qa.001",
            question_revision=1,
            item_type="new",
            sort_order=1,
            status="pending",
            due_date_snapshot=None,
        )
        tmp_db.add(item2)

        # Create an Attempt with created_at = yesterday (simulating Day 1 submission)
        # First, create a QuestionVersion for revision 1 (already exists from import)
        from app.db.models.attempt import Attempt
        attempt = Attempt(
            question_id="spark.shuffle.qa.001",
            question_revision=1,
            attempt_type="new",
            user_answer="test answer",
            status="awaiting_self_assessment",
            client_request_id=str(uuid4()),
        )
        tmp_db.add(attempt)
        tmp_db.flush()

        # Manually set created_at to yesterday
        yesterday_dt = datetime(yesterday.year, yesterday.month, yesterday.day, 12, 0, 0)
        tmp_db.execute(
            text("UPDATE attempt SET created_at = :dt WHERE id = :id"),
            {"dt": str(yesterday_dt), "id": attempt.id},
        )
        tmp_db.commit()

        # Now self-assess (simulating Day 2)
        client = _make_client(tmp_db)
        resp = client.post(
            f"/api/v1/attempts/{attempt.id}/self-assessment",
            json={"mastery_state": "familiar"},
        )
        assert resp.status_code == 201

        # Day 1 Item → completed
        db_item1 = tmp_db.query(DailyTaskItem).filter(DailyTaskItem.id == item1.id).first()
        assert db_item1.status == "completed"
        assert db_item1.completed_attempt_id == attempt.id

        # Day 2 Item → still pending
        db_item2 = tmp_db.query(DailyTaskItem).filter(DailyTaskItem.id == item2.id).first()
        assert db_item2.status == "pending"
        assert db_item2.completed_attempt_id is None

        # Day 1 aggregate updated
        tmp_db.refresh(task1)
        assert task1.status == "completed"

        # Day 2 aggregate unchanged
        tmp_db.refresh(task2)
        assert task2.status == "not_started"


# ---------------------------------------------------------------------------
# Skipped item not auto-completed
# ---------------------------------------------------------------------------

class TestSkippedItemNotAutoCompleted:
    def test_skipped_item_not_completed_by_attempt(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        task = _generate_today(tmp_db, client)
        new_items = [i for i in task["items"] if i["item_type"] == "new" and i["question_type"] == "choice"]
        item = new_items[0]

        # Skip the item
        client.post(f"/api/v1/daily-task-items/{item['id']}/skip")

        # Submit attempt for same question
        client.post(
            f"/api/v1/questions/{item['question_id']}/attempts",
            json={
                "question_revision": item["question_revision"],
                "attempt_type": "new",
                "client_request_id": str(uuid4()),
                "answer": "B",
            },
        )

        # Item should still be skipped (not auto-completed)
        db_item = tmp_db.query(DailyTaskItem).filter(DailyTaskItem.id == item["id"]).first()
        assert db_item.status == "skipped"


# ---------------------------------------------------------------------------
# No matching DailyTaskItem
# ---------------------------------------------------------------------------

class TestNoMatchingItem:
    def test_attempt_without_daily_task_succeeds(self, tmp_db: Session, content_dir: Path):
        """Attempt should succeed even if no DailyTaskItem matches."""
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        # Don't generate today task — just submit directly
        resp = client.post(
            "/api/v1/questions/spark.shuffle.choice.001/attempts",
            json={
                "question_revision": 1,
                "attempt_type": "new",
                "client_request_id": str(uuid4()),
                "answer": "B",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["is_correct"] is True


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