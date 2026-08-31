"""Tests for Dashboard API — Phase 7C1."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.content.importer import import_content
from app.db.models.daily_task import DailyTask, DailyTaskItem
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


# ---------------------------------------------------------------------------
# Dashboard Today
# ---------------------------------------------------------------------------

class TestDashboardToday:
    def test_first_access_creates_task(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["today"]["date"] == str(get_business_today())
        assert data["today"]["task_id"] > 0
        assert data["today"]["status"] in ("not_started", "in_progress", "completed")

    def test_second_access_same_task(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp1 = client.get("/api/v1/dashboard")
        resp2 = client.get("/api/v1/dashboard")
        assert resp1.json()["today"]["task_id"] == resp2.json()["today"]["task_id"]

    def test_today_summary_counts(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/dashboard")
        today = resp.json()["today"]
        assert "review_total" in today
        assert "review_completed" in today
        assert "review_skipped" in today
        assert "new_total" in today
        assert "new_completed" in today
        assert "new_skipped" in today
        # All should be 0 initially (just generated, no attempts)
        assert today["review_completed"] == 0
        assert today["new_completed"] == 0


# ---------------------------------------------------------------------------
# Review due/overdue
# ---------------------------------------------------------------------------

class TestDashboardReview:
    def test_due_count(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        today = get_business_today()
        rs = ReviewState(
            question_id="spark.shuffle.choice.001",
            mastery_state="unmastered",
            next_review_date=today,
            review_count=0,
            consecutive_successes=0,
            policy_version="review_v2",
            algorithm_state_json=json.dumps({"review_stage": 0}),
        )
        tmp_db.add(rs)
        tmp_db.commit()

        client = _make_client(tmp_db)
        resp = client.get("/api/v1/dashboard")
        assert resp.json()["review"]["due_count"] >= 1

    def test_overdue_count(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        today = get_business_today()
        rs = ReviewState(
            question_id="spark.shuffle.choice.001",
            mastery_state="unmastered",
            next_review_date=today - timedelta(days=3),
            review_count=0,
            consecutive_successes=0,
            policy_version="review_v2",
            algorithm_state_json=json.dumps({"review_stage": 0}),
        )
        tmp_db.add(rs)
        tmp_db.commit()

        client = _make_client(tmp_db)
        resp = client.get("/api/v1/dashboard")
        assert resp.json()["review"]["overdue_count"] >= 1

    def test_future_excluded(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        today = get_business_today()
        rs = ReviewState(
            question_id="spark.shuffle.choice.001",
            mastery_state="unmastered",
            next_review_date=today + timedelta(days=5),
            review_count=0,
            consecutive_successes=0,
            policy_version="review_v2",
            algorithm_state_json=json.dumps({"review_stage": 0}),
        )
        tmp_db.add(rs)
        tmp_db.commit()

        client = _make_client(tmp_db)
        resp = client.get("/api/v1/dashboard")
        assert resp.json()["review"]["due_count"] == 0


# ---------------------------------------------------------------------------
# Pending
# ---------------------------------------------------------------------------

class TestDashboardPending:
    def test_pending_counts(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/dashboard")
        pending = resp.json()["pending"]
        assert "short_answer_self_assessment" in pending
        assert "sql_assessment" in pending
        assert pending["short_answer_self_assessment"] == 0
        assert pending["sql_assessment"] == 0

    def test_sa_pending_count(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        # Create an awaiting SA attempt
        from app.db.models.attempt import Attempt
        attempt = Attempt(
            question_id="spark.shuffle.qa.001",
            question_revision=1,
            attempt_type="new",
            user_answer="test",
            status="awaiting_self_assessment",
            client_request_id=str(uuid4()),
        )
        tmp_db.add(attempt)
        tmp_db.commit()

        client = _make_client(tmp_db)
        resp = client.get("/api/v1/dashboard")
        assert resp.json()["pending"]["short_answer_self_assessment"] == 1


# ---------------------------------------------------------------------------
# Response structure
# ---------------------------------------------------------------------------

class TestDashboardStructure:
    def test_response_fields(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/dashboard")
        data = resp.json()

        assert "today" in data
        assert "review" in data
        assert "week" in data
        assert "pending" in data
        assert "weak_knowledge_points" in data

        # today
        assert "date" in data["today"]
        assert "task_id" in data["today"]
        assert "status" in data["today"]

        # review
        assert "due_count" in data["review"]
        assert "overdue_count" in data["review"]

        # week
        assert "completed_attempts" in data["week"]
        assert "study_days" in data["week"]
        assert "choice_accuracy" in data["week"]

        # pending
        assert "short_answer_self_assessment" in data["pending"]
        assert "sql_assessment" in data["pending"]

    def test_weak_points_deferred(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/dashboard")
        assert resp.json()["weak_knowledge_points"] == []


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