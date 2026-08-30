"""Tests for Review Policy — Phase 6.

Covers:
- Score-Based Policy (choice/SQL)
- Self-Assessment Policy (short-answer)
- Task 4.6 Choice→ReviewState scenarios
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.content.importer import import_content
from app.db.models.attempt import Attempt
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

    # Empty dirs for other types
    for d in ["short_answer", "sql"]:
        p = content_dir / "questions" / d
        p.mkdir(parents=True, exist_ok=True)


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
# Score-Based Policy unit tests
# ---------------------------------------------------------------------------

class TestScoreBasedPolicy:
    def test_classify_fail(self):
        from app.review.policy import classify_score
        assert classify_score(0.0) == "fail"
        assert classify_score(0.59) == "fail"

    def test_classify_partial(self):
        from app.review.policy import classify_score
        assert classify_score(0.60) == "partial"
        assert classify_score(0.79) == "partial"

    def test_classify_good(self):
        from app.review.policy import classify_score
        assert classify_score(0.80) == "good"
        assert classify_score(0.94) == "good"

    def test_classify_excellent(self):
        from app.review.policy import classify_score
        assert classify_score(0.95) == "excellent"
        assert classify_score(1.0) == "excellent"

    def test_first_fail(self):
        from app.review.policy import apply_score_based
        today = date(2026, 8, 29)
        result = apply_score_based(
            final_score=0, max_score=1, business_today=today,
        )
        assert result.mastery_state == "unmastered"
        assert result.review_stage == 0
        assert result.next_review_date == today + timedelta(days=1)
        assert result.consecutive_successes == 0

    def test_first_excellent(self):
        from app.review.policy import apply_score_based
        today = date(2026, 8, 29)
        result = apply_score_based(
            final_score=1, max_score=1, business_today=today,
        )
        assert result.mastery_state == "vague"
        assert result.review_stage == 1
        assert result.next_review_date == today + timedelta(days=2)
        assert result.consecutive_successes == 1

    def test_first_partial(self):
        from app.review.policy import apply_score_based
        today = date(2026, 8, 29)
        result = apply_score_based(
            final_score=7, max_score=10, business_today=today,
        )
        assert result.mastery_state == "vague"
        assert result.review_stage == 0
        assert result.consecutive_successes == 0

    def test_first_good(self):
        from app.review.policy import apply_score_based
        today = date(2026, 8, 29)
        result = apply_score_based(
            final_score=8, max_score=10, business_today=today,
        )
        assert result.mastery_state == "vague"
        assert result.review_stage == 1
        assert result.consecutive_successes == 1

    def test_fail_resets_to_unmastered(self):
        from app.review.policy import apply_score_based
        today = date(2026, 8, 29)
        algo = json.dumps({"review_stage": 4, "consecutive_excellent": 0})
        result = apply_score_based(
            final_score=0, max_score=1, business_today=today,
            current_mastery_state="mastered",
            current_algorithm_state_json=algo,
        )
        assert result.mastery_state == "unmastered"
        assert result.review_stage == 0
        assert result.consecutive_successes == 0

    def test_partial_regression(self):
        from app.review.policy import apply_score_based
        today = date(2026, 8, 29)
        algo = json.dumps({"review_stage": 3, "consecutive_excellent": 0})
        result = apply_score_based(
            final_score=6, max_score=10, business_today=today,
            current_algorithm_state_json=algo,
        )
        assert result.mastery_state == "vague"
        assert result.review_stage == 2
        assert result.consecutive_successes == 0

    def test_good_progression(self):
        from app.review.policy import apply_score_based
        today = date(2026, 8, 29)
        algo = json.dumps({"review_stage": 2, "consecutive_excellent": 0})
        result = apply_score_based(
            final_score=8, max_score=10, business_today=today,
            current_consecutive_successes=3,
            current_algorithm_state_json=algo,
        )
        assert result.review_stage == 3
        assert result.mastery_state == "familiar"
        assert result.consecutive_successes == 4

    def test_excellent_progression(self):
        from app.review.policy import apply_score_based
        today = date(2026, 8, 29)
        algo = json.dumps({"review_stage": 2, "consecutive_excellent": 0})
        result = apply_score_based(
            final_score=10, max_score=10, business_today=today,
            current_algorithm_state_json=algo,
        )
        assert result.review_stage == 3
        assert result.consecutive_successes == 1

    def test_consecutive_excellent_acceleration(self):
        from app.review.policy import apply_score_based
        today = date(2026, 8, 29)
        algo = json.dumps({"review_stage": 2, "consecutive_excellent": 1})
        result = apply_score_based(
            final_score=10, max_score=10, business_today=today,
            current_algorithm_state_json=algo,
        )
        assert result.review_stage == 4  # +2 acceleration
        assert result.mastery_state == "mastered"

    def test_stage_cap_5(self):
        from app.review.policy import apply_score_based
        today = date(2026, 8, 29)
        algo = json.dumps({"review_stage": 5, "consecutive_excellent": 2})
        result = apply_score_based(
            final_score=10, max_score=10, business_today=today,
            current_algorithm_state_json=algo,
        )
        assert result.review_stage == 5

    def test_mastery_from_stage(self):
        from app.review.policy import _STAGE_MASTERY
        assert _STAGE_MASTERY[0] == "vague"
        assert _STAGE_MASTERY[1] == "vague"
        assert _STAGE_MASTERY[2] == "familiar"
        assert _STAGE_MASTERY[3] == "familiar"
        assert _STAGE_MASTERY[4] == "mastered"
        assert _STAGE_MASTERY[5] == "mastered"

    def test_algorithm_state_json_structure(self):
        from app.review.policy import apply_score_based
        result = apply_score_based(
            final_score=1, max_score=1, business_today=date(2026, 8, 29),
        )
        algo = json.loads(result.algorithm_state_json)
        assert algo["review_stage"] == 1
        assert algo["last_evaluation_mode"] == "score"
        assert algo["last_performance"] == "excellent"
        assert algo["consecutive_excellent"] == 1

    def test_policy_version_review_v2(self):
        from app.review.policy import apply_score_based
        result = apply_score_based(
            final_score=1, max_score=1, business_today=date(2026, 8, 29),
        )
        assert result.policy_version == "review_v2"


# ---------------------------------------------------------------------------
# Choice → ReviewState integration (Task 4.6)
# ---------------------------------------------------------------------------

class TestChoiceReviewState:
    def test_first_correct(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.post(
            "/api/v1/questions/spark.shuffle.choice.001/attempts",
            json={
                "question_revision": 1,
                "attempt_type": "practice",
                "client_request_id": str(uuid4()),
                "answer": "B",
            },
        )
        assert resp.status_code == 201

        rs = (
            tmp_db.query(ReviewState)
            .filter(ReviewState.question_id == "spark.shuffle.choice.001")
            .first()
        )
        assert rs is not None
        assert rs.mastery_state == "vague"
        assert rs.policy_version == "review_v2"
        algo = json.loads(rs.algorithm_state_json)
        assert algo["review_stage"] == 1
        assert algo["last_performance"] == "excellent"

    def test_first_wrong(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.post(
            "/api/v1/questions/spark.shuffle.choice.001/attempts",
            json={
                "question_revision": 1,
                "attempt_type": "practice",
                "client_request_id": str(uuid4()),
                "answer": "A",
            },
        )
        assert resp.status_code == 201

        rs = (
            tmp_db.query(ReviewState)
            .filter(ReviewState.question_id == "spark.shuffle.choice.001")
            .first()
        )
        assert rs is not None
        assert rs.mastery_state == "unmastered"
        algo = json.loads(rs.algorithm_state_json)
        assert algo["review_stage"] == 0
        assert algo["last_performance"] == "fail"

    def test_second_correct_progresses(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        # First: wrong → unmastered/stage 0
        client.post(
            "/api/v1/questions/spark.shuffle.choice.001/attempts",
            json={
                "question_revision": 1, "attempt_type": "practice",
                "client_request_id": str(uuid4()), "answer": "A",
            },
        )

        # Second: correct → vague/stage 1
        client.post(
            "/api/v1/questions/spark.shuffle.choice.001/attempts",
            json={
                "question_revision": 1, "attempt_type": "practice",
                "client_request_id": str(uuid4()), "answer": "B",
            },
        )

        rs = (
            tmp_db.query(ReviewState)
            .filter(ReviewState.question_id == "spark.shuffle.choice.001")
            .first()
        )
        assert rs.mastery_state == "vague"
        algo = json.loads(rs.algorithm_state_json)
        assert algo["review_stage"] == 1

    def test_mastered_then_wrong_resets(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        # Build up to mastered: 4 consecutive excellent
        for _ in range(4):
            client.post(
                "/api/v1/questions/spark.shuffle.choice.001/attempts",
                json={
                    "question_revision": 1, "attempt_type": "practice",
                    "client_request_id": str(uuid4()), "answer": "B",
                },
            )

        rs = (
            tmp_db.query(ReviewState)
            .filter(ReviewState.question_id == "spark.shuffle.choice.001")
            .first()
        )
        assert rs.mastery_state == "mastered"

        # Now fail
        client.post(
            "/api/v1/questions/spark.shuffle.choice.001/attempts",
            json={
                "question_revision": 1, "attempt_type": "practice",
                "client_request_id": str(uuid4()), "answer": "A",
            },
        )

        rs = (
            tmp_db.query(ReviewState)
            .filter(ReviewState.question_id == "spark.shuffle.choice.001")
            .first()
        )
        assert rs.mastery_state == "unmastered"
        algo = json.loads(rs.algorithm_state_json)
        assert algo["review_stage"] == 0

    def test_practice_redo_updates_review_state(
        self, tmp_db: Session, content_dir: Path
    ):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        # First attempt (new)
        client.post(
            "/api/v1/questions/spark.shuffle.choice.001/attempts",
            json={
                "question_revision": 1, "attempt_type": "new",
                "client_request_id": str(uuid4()), "answer": "A",
            },
        )

        # Practice redo
        client.post(
            "/api/v1/questions/spark.shuffle.choice.001/attempts",
            json={
                "question_revision": 1, "attempt_type": "practice",
                "client_request_id": str(uuid4()), "answer": "B",
            },
        )

        rs = (
            tmp_db.query(ReviewState)
            .filter(ReviewState.question_id == "spark.shuffle.choice.001")
            .first()
        )
        # Should have progressed from unmastered
        assert rs.mastery_state != "unmastered"

    def test_review_count_only_for_review(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        # practice attempt
        client.post(
            "/api/v1/questions/spark.shuffle.choice.001/attempts",
            json={
                "question_revision": 1, "attempt_type": "practice",
                "client_request_id": str(uuid4()), "answer": "B",
            },
        )

        rs = (
            tmp_db.query(ReviewState)
            .filter(ReviewState.question_id == "spark.shuffle.choice.001")
            .first()
        )
        assert rs.review_count == 0

    def test_review_type_increments_count(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        client.post(
            "/api/v1/questions/spark.shuffle.choice.001/attempts",
            json={
                "question_revision": 1, "attempt_type": "review",
                "client_request_id": str(uuid4()), "answer": "B",
            },
        )

        rs = (
            tmp_db.query(ReviewState)
            .filter(ReviewState.question_id == "spark.shuffle.choice.001")
            .first()
        )
        assert rs.review_count == 1

    def test_review_applied_at_set(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.post(
            "/api/v1/questions/spark.shuffle.choice.001/attempts",
            json={
                "question_revision": 1, "attempt_type": "practice",
                "client_request_id": str(uuid4()), "answer": "B",
            },
        )
        attempt_id = resp.json()["attempt_id"]

        attempt = tmp_db.query(Attempt).filter(Attempt.id == attempt_id).first()
        assert attempt.review_applied_at is not None

    def test_idempotent_retry_no_double_apply(
        self, tmp_db: Session, content_dir: Path
    ):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        cid = str(uuid4())
        body = {
            "question_revision": 1, "attempt_type": "practice",
            "client_request_id": cid, "answer": "B",
        }

        client.post("/api/v1/questions/spark.shuffle.choice.001/attempts", json=body)
        client.post("/api/v1/questions/spark.shuffle.choice.001/attempts", json=body)

        rs = (
            tmp_db.query(ReviewState)
            .filter(ReviewState.question_id == "spark.shuffle.choice.001")
            .first()
        )
        # Should be stage 1 (first excellent), not further advanced
        algo = json.loads(rs.algorithm_state_json)
        assert algo["review_stage"] == 1

    def test_history_attempts_preserved(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        id1 = client.post(
            "/api/v1/questions/spark.shuffle.choice.001/attempts",
            json={
                "question_revision": 1, "attempt_type": "practice",
                "client_request_id": str(uuid4()), "answer": "A",
            },
        ).json()["attempt_id"]

        id2 = client.post(
            "/api/v1/questions/spark.shuffle.choice.001/attempts",
            json={
                "question_revision": 1, "attempt_type": "practice",
                "client_request_id": str(uuid4()), "answer": "B",
            },
        ).json()["attempt_id"]

        a1 = tmp_db.query(Attempt).filter(Attempt.id == id1).first()
        a2 = tmp_db.query(Attempt).filter(Attempt.id == id2).first()
        assert a1.user_answer == "A"
        assert a2.user_answer == "B"
        assert a1.id != a2.id

    def test_choice_not_awaiting(self, tmp_db: Session, content_dir: Path):
        """Choice attempts are completed, not awaiting_self_assessment."""
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.post(
            "/api/v1/questions/spark.shuffle.choice.001/attempts",
            json={
                "question_revision": 1, "attempt_type": "practice",
                "client_request_id": str(uuid4()), "answer": "B",
            },
        )
        assert resp.json()["status"] == "completed"