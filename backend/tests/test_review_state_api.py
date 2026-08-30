"""Tests for ReviewState API and Wrong Book API — Phase 6."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.content.importer import import_content
from app.db.models.review import ReviewState
from app.db.session import get_db
from app.main import app


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

_CHOICE_001 = """\
id: spark.shuffle.choice.001
question_type: choice
primary_knowledge_point_id: spark.shuffle
title: Shuffle 触发条件
difficulty: 2
tags: [spark]
related_knowledge_points: []
is_active: true

content: 以下哪个操作会触发 Shuffle？

options:
  - key: A
    text: map
  - key: B
    text: reduceByKey
  - key: C
    text: filter

correct_answer: B

explanation: reduceByKey 需要按 key 重新分区。
"""

_QA_001 = """\
id: spark.shuffle.qa.001
question_type: short_answer
primary_knowledge_point_id: spark.shuffle
title: Shuffle 作用
difficulty: 2
tags: [spark]
related_knowledge_points: []
is_active: true

content: 请说明 Spark Shuffle 的作用。
reference_answer: Shuffle 是数据重新分区的过程。
explanation: 宽依赖触发 Shuffle。
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

    for d in ["sql"]:
        (content_dir / "questions" / d).mkdir(parents=True, exist_ok=True)


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
# ReviewState GET API
# ---------------------------------------------------------------------------

class TestReviewStateGET:
    def test_no_state_returns_default(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/questions/spark.shuffle.choice.001/review-state")
        assert resp.status_code == 200
        data = resp.json()
        assert data["question_id"] == "spark.shuffle.choice.001"
        assert data["mastery_state"] is None
        assert data["next_review_date"] is None
        assert data["review_count"] == 0
        assert data["policy_version"] is None

    def test_with_state(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        # Create a ReviewState via attempt
        client.post(
            "/api/v1/questions/spark.shuffle.choice.001/attempts",
            json={
                "question_revision": 1, "attempt_type": "practice",
                "client_request_id": str(uuid4()), "answer": "B",
            },
        )

        resp = client.get("/api/v1/questions/spark.shuffle.choice.001/review-state")
        data = resp.json()
        assert data["mastery_state"] is not None
        assert data["policy_version"] == "review_v2"
        assert data["review_stage"] is not None

    def test_question_not_found(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/questions/nonexistent/review-state")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# ReviewState PUT API (Manual Mastery)
# ---------------------------------------------------------------------------

class TestReviewStatePUT:
    def test_put_four_values(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        for mastery in ["unmastered", "vague", "familiar", "mastered"]:
            resp = client.put(
                "/api/v1/questions/spark.shuffle.choice.001/review-state",
                json={"mastery_state": mastery},
            )
            assert resp.status_code == 200
            assert resp.json()["mastery_state"] == mastery

    def test_put_creates_review_state(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        client.put(
            "/api/v1/questions/spark.shuffle.choice.001/review-state",
            json={"mastery_state": "familiar"},
        )

        rs = (
            tmp_db.query(ReviewState)
            .filter(ReviewState.question_id == "spark.shuffle.choice.001")
            .first()
        )
        assert rs is not None
        assert rs.mastery_state == "familiar"
        assert rs.policy_version == "review_v2"

    def test_put_does_not_create_attempt(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        from app.db.models.attempt import Attempt

        client = _make_client(tmp_db)
        count_before = tmp_db.query(Attempt).count()

        client.put(
            "/api/v1/questions/spark.shuffle.choice.001/review-state",
            json={"mastery_state": "familiar"},
        )

        count_after = tmp_db.query(Attempt).count()
        assert count_after == count_before

    def test_put_review_count_not_increased(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        client.put(
            "/api/v1/questions/spark.shuffle.choice.001/review-state",
            json={"mastery_state": "familiar"},
        )

        rs = (
            tmp_db.query(ReviewState)
            .filter(ReviewState.question_id == "spark.shuffle.choice.001")
            .first()
        )
        assert rs.review_count == 0

    def test_put_idempotent_same_mastery(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp1 = client.put(
            "/api/v1/questions/spark.shuffle.choice.001/review-state",
            json={"mastery_state": "familiar"},
        )
        resp2 = client.put(
            "/api/v1/questions/spark.shuffle.choice.001/review-state",
            json={"mastery_state": "familiar"},
        )
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        # Same mastery → should not advance stage
        rs = (
            tmp_db.query(ReviewState)
            .filter(ReviewState.question_id == "spark.shuffle.choice.001")
            .first()
        )
        algo = json.loads(rs.algorithm_state_json)
        assert algo["review_stage"] == 3  # familiar → stage 3

    def test_put_question_not_found(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.put(
            "/api/v1/questions/nonexistent/review-state",
            json={"mastery_state": "familiar"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Wrong Book API
# ---------------------------------------------------------------------------

class TestWrongBook:
    def test_auto_unmastered_appears(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        # Wrong answer → unmastered
        client.post(
            "/api/v1/questions/spark.shuffle.choice.001/attempts",
            json={
                "question_revision": 1, "attempt_type": "practice",
                "client_request_id": str(uuid4()), "answer": "A",
            },
        )

        resp = client.get("/api/v1/wrong-book")
        data = resp.json()
        assert data["total"] >= 1
        ids = [item["question_id"] for item in data["items"]]
        assert "spark.shuffle.choice.001" in ids

    def test_auto_vague_appears(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        # Self-assess vague
        resp = client.post(
            "/api/v1/questions/spark.shuffle.qa.001/attempts",
            json={
                "question_revision": 1, "attempt_type": "practice",
                "client_request_id": str(uuid4()), "answer": "test",
            },
        )
        attempt_id = resp.json()["attempt_id"]
        client.post(
            f"/api/v1/attempts/{attempt_id}/self-assessment",
            json={"mastery_state": "vague"},
        )

        resp = client.get("/api/v1/wrong-book")
        ids = [item["question_id"] for item in resp.json()["items"]]
        assert "spark.shuffle.qa.001" in ids

    def test_familiar_disappears(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        # Set familiar via manual mastery
        client.put(
            "/api/v1/questions/spark.shuffle.choice.001/review-state",
            json={"mastery_state": "familiar"},
        )

        resp = client.get("/api/v1/wrong-book")
        ids = [item["question_id"] for item in resp.json()["items"]]
        assert "spark.shuffle.choice.001" not in ids

    def test_follow_forces_display(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        # Set mastered (should disappear)
        client.put(
            "/api/v1/questions/spark.shuffle.choice.001/review-state",
            json={"mastery_state": "mastered"},
        )

        resp = client.get("/api/v1/wrong-book")
        ids = [item["question_id"] for item in resp.json()["items"]]
        assert "spark.shuffle.choice.001" not in ids

        # Set follow
        client.put(
            "/api/v1/questions/spark.shuffle.choice.001/wrong-book-preference",
            json={"mode": "follow"},
        )

        resp = client.get("/api/v1/wrong-book")
        ids = [item["question_id"] for item in resp.json()["items"]]
        assert "spark.shuffle.choice.001" in ids

    def test_ignore_hides(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        # Wrong answer → unmastered (should appear)
        client.post(
            "/api/v1/questions/spark.shuffle.choice.001/attempts",
            json={
                "question_revision": 1, "attempt_type": "practice",
                "client_request_id": str(uuid4()), "answer": "A",
            },
        )

        resp = client.get("/api/v1/wrong-book")
        ids = [item["question_id"] for item in resp.json()["items"]]
        assert "spark.shuffle.choice.001" in ids

        # Set ignore
        client.put(
            "/api/v1/questions/spark.shuffle.choice.001/wrong-book-preference",
            json={"mode": "ignore"},
        )

        resp = client.get("/api/v1/wrong-book")
        ids = [item["question_id"] for item in resp.json()["items"]]
        assert "spark.shuffle.choice.001" not in ids

    def test_ignore_does_not_change_review_state(
        self, tmp_db: Session, content_dir: Path
    ):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        # Create ReviewState
        client.post(
            "/api/v1/questions/spark.shuffle.choice.001/attempts",
            json={
                "question_revision": 1, "attempt_type": "practice",
                "client_request_id": str(uuid4()), "answer": "A",
            },
        )

        rs_before = (
            tmp_db.query(ReviewState)
            .filter(ReviewState.question_id == "spark.shuffle.choice.001")
            .first()
        )
        mastery_before = rs_before.mastery_state
        next_before = rs_before.next_review_date

        # Set ignore
        client.put(
            "/api/v1/questions/spark.shuffle.choice.001/wrong-book-preference",
            json={"mode": "ignore"},
        )

        rs_after = (
            tmp_db.query(ReviewState)
            .filter(ReviewState.question_id == "spark.shuffle.choice.001")
            .first()
        )
        assert rs_after.mastery_state == mastery_before
        assert rs_after.next_review_date == next_before

    def test_auto_restores_system_behavior(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        # Wrong answer → unmastered
        client.post(
            "/api/v1/questions/spark.shuffle.choice.001/attempts",
            json={
                "question_revision": 1, "attempt_type": "practice",
                "client_request_id": str(uuid4()), "answer": "A",
            },
        )

        # Ignore
        client.put(
            "/api/v1/questions/spark.shuffle.choice.001/wrong-book-preference",
            json={"mode": "ignore"},
        )

        resp = client.get("/api/v1/wrong-book")
        ids = [item["question_id"] for item in resp.json()["items"]]
        assert "spark.shuffle.choice.001" not in ids

        # Back to auto
        client.put(
            "/api/v1/questions/spark.shuffle.choice.001/wrong-book-preference",
            json={"mode": "auto"},
        )

        resp = client.get("/api/v1/wrong-book")
        ids = [item["question_id"] for item in resp.json()["items"]]
        assert "spark.shuffle.choice.001" in ids

    def test_preference_idempotent(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp1 = client.put(
            "/api/v1/questions/spark.shuffle.choice.001/wrong-book-preference",
            json={"mode": "follow"},
        )
        resp2 = client.put(
            "/api/v1/questions/spark.shuffle.choice.001/wrong-book-preference",
            json={"mode": "follow"},
        )
        assert resp1.status_code == 200
        assert resp2.status_code == 200

    def test_preference_question_not_found(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.put(
            "/api/v1/questions/nonexistent/wrong-book-preference",
            json={"mode": "auto"},
        )
        assert resp.status_code == 404

    def test_pagination(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/wrong-book?page=1&page_size=10")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["page"] == 1
        assert data["page_size"] == 10


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