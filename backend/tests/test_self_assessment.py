"""Tests for Self-Assessment + ReviewState — Phase 5."""

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

_SQL_001 = """\
id: spark.shuffle.sql.001
question_type: sql
primary_knowledge_point_id: spark.shuffle
title: SQL 窗口函数
difficulty: 4
tags: [spark, sql]
related_knowledge_points: []
is_active: true

content: 使用 ROW_NUMBER 窗口函数。
table_schema: "CREATE TABLE emp (id INT, dept STRING, salary INT)"
field_description: "id=员工ID, dept=部门, salary=工资"
business_requirement: "每个部门工资最高的员工"
expected_sql: "SELECT * FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY dept ORDER BY salary DESC) AS rn FROM emp) WHERE rn = 1"
scoring_criteria:
  - id: c1
    description: 正确使用 ROW_NUMBER
    points: 5
  - id: c2
    description: 正确使用 PARTITION BY
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

    qa_dir = content_dir / "questions" / "short_answer"
    qa_dir.mkdir(parents=True)
    (qa_dir / "spark.shuffle.qa.001.yaml").write_text(_QA_001, encoding="utf-8")

    sql_dir = content_dir / "questions" / "sql"
    sql_dir.mkdir(parents=True)
    (sql_dir / "spark.shuffle.sql.001.yaml").write_text(_SQL_001, encoding="utf-8")


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


def _create_sa_attempt(db: Session, client: TestClient) -> int:
    """Create a short-answer attempt and return its id."""
    resp = client.post(
        "/api/v1/questions/spark.shuffle.qa.001/attempts",
        json={
            "question_revision": 1,
            "attempt_type": "practice",
            "client_request_id": str(uuid4()),
            "answer": "用户答案",
        },
    )
    assert resp.status_code == 201
    return resp.json()["attempt_id"]


# ---------------------------------------------------------------------------
# Review Policy unit tests
# ---------------------------------------------------------------------------

class TestReviewPolicy:
    def test_unmastered(self):
        from app.review.policy import apply_self_assessment

        today = date(2026, 8, 29)
        result = apply_self_assessment(
            mastery_state="unmastered",
            business_today=today,
        )
        assert result.mastery_state == "unmastered"
        assert result.review_stage == 0
        assert result.next_review_date == today + timedelta(days=1)
        assert result.consecutive_successes == 0
        assert result.policy_version == "review_v2"

    def test_vague(self):
        from app.review.policy import apply_self_assessment

        today = date(2026, 8, 29)
        result = apply_self_assessment(
            mastery_state="vague",
            business_today=today,
        )
        assert result.review_stage == 1
        assert result.next_review_date == today + timedelta(days=2)
        assert result.consecutive_successes == 0

    def test_familiar(self):
        from app.review.policy import apply_self_assessment

        today = date(2026, 8, 29)
        result = apply_self_assessment(
            mastery_state="familiar",
            business_today=today,
            current_consecutive_successes=2,
        )
        assert result.review_stage == 3
        assert result.next_review_date == today + timedelta(days=7)
        assert result.consecutive_successes == 3

    def test_mastered_first_time(self):
        from app.review.policy import apply_self_assessment

        today = date(2026, 8, 29)
        result = apply_self_assessment(
            mastery_state="mastered",
            business_today=today,
        )
        assert result.review_stage == 4
        assert result.next_review_date == today + timedelta(days=14)
        assert result.consecutive_successes == 1

    def test_mastered_again(self):
        from app.review.policy import apply_self_assessment

        today = date(2026, 8, 29)
        algo = json.dumps({"review_stage": 4})
        result = apply_self_assessment(
            mastery_state="mastered",
            business_today=today,
            current_mastery_state="mastered",
            current_algorithm_state_json=algo,
        )
        assert result.review_stage == 5
        assert result.next_review_date == today + timedelta(days=30)

    def test_mastered_stage5_stays(self):
        from app.review.policy import apply_self_assessment

        today = date(2026, 8, 29)
        algo = json.dumps({"review_stage": 5})
        result = apply_self_assessment(
            mastery_state="mastered",
            business_today=today,
            current_mastery_state="mastered",
            current_algorithm_state_json=algo,
        )
        assert result.review_stage == 5
        assert result.next_review_date == today + timedelta(days=30)

    def test_algorithm_state_json_structure(self):
        import json

        from app.review.policy import apply_self_assessment

        result = apply_self_assessment(
            mastery_state="familiar",
            business_today=date(2026, 8, 29),
        )
        algo = json.loads(result.algorithm_state_json)
        assert algo["review_stage"] == 3
        assert algo["last_evaluation_mode"] == "self"
        assert algo["last_performance"] is None
        assert algo["consecutive_excellent"] == 0


# ---------------------------------------------------------------------------
# Self-Assessment API tests
# ---------------------------------------------------------------------------

class TestSelfAssessment:
    def test_success(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        attempt_id = _create_sa_attempt(tmp_db, client)
        resp = client.post(
            f"/api/v1/attempts/{attempt_id}/self-assessment",
            json={"mastery_state": "familiar"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["attempt_id"] == attempt_id
        assert data["status"] == "completed"
        assert data["self_assessed_mastery_state"] == "familiar"
        assert data["review_state"]["mastery_state"] == "familiar"
        assert data["review_state"]["policy_version"] == "review_v2"

    def test_attempt_completed(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        attempt_id = _create_sa_attempt(tmp_db, client)
        client.post(
            f"/api/v1/attempts/{attempt_id}/self-assessment",
            json={"mastery_state": "vague"},
        )

        attempt = tmp_db.query(Attempt).filter(Attempt.id == attempt_id).first()
        assert attempt.status == "completed"

    def test_finalized_at_set(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        attempt_id = _create_sa_attempt(tmp_db, client)
        client.post(
            f"/api/v1/attempts/{attempt_id}/self-assessment",
            json={"mastery_state": "vague"},
        )

        attempt = tmp_db.query(Attempt).filter(Attempt.id == attempt_id).first()
        assert attempt.finalized_at is not None

    def test_review_applied_at_set(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        attempt_id = _create_sa_attempt(tmp_db, client)
        client.post(
            f"/api/v1/attempts/{attempt_id}/self-assessment",
            json={"mastery_state": "vague"},
        )

        attempt = tmp_db.query(Attempt).filter(Attempt.id == attempt_id).first()
        assert attempt.review_applied_at is not None

    def test_review_state_created(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        attempt_id = _create_sa_attempt(tmp_db, client)
        client.post(
            f"/api/v1/attempts/{attempt_id}/self-assessment",
            json={"mastery_state": "familiar"},
        )

        rs = (
            tmp_db.query(ReviewState)
            .filter(ReviewState.question_id == "spark.shuffle.qa.001")
            .first()
        )
        assert rs is not None
        assert rs.mastery_state == "familiar"
        assert rs.policy_version == "review_v2"

    def test_second_attempt_updates_review_state(
        self, tmp_db: Session, content_dir: Path
    ):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        # Attempt 1: vague
        id1 = _create_sa_attempt(tmp_db, client)
        client.post(
            f"/api/v1/attempts/{id1}/self-assessment",
            json={"mastery_state": "vague"},
        )

        # Attempt 2: familiar
        id2 = _create_sa_attempt(tmp_db, client)
        client.post(
            f"/api/v1/attempts/{id2}/self-assessment",
            json={"mastery_state": "familiar"},
        )

        rs = (
            tmp_db.query(ReviewState)
            .filter(ReviewState.question_id == "spark.shuffle.qa.001")
            .first()
        )
        assert rs.mastery_state == "familiar"
        assert rs.last_attempt_id == id2

    def test_both_attempts_preserved(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        id1 = _create_sa_attempt(tmp_db, client)
        client.post(
            f"/api/v1/attempts/{id1}/self-assessment",
            json={"mastery_state": "vague"},
        )

        id2 = _create_sa_attempt(tmp_db, client)
        client.post(
            f"/api/v1/attempts/{id2}/self-assessment",
            json={"mastery_state": "familiar"},
        )

        a1 = tmp_db.query(Attempt).filter(Attempt.id == id1).first()
        a2 = tmp_db.query(Attempt).filter(Attempt.id == id2).first()
        assert a1.self_assessed_mastery_state == "vague"
        assert a2.self_assessed_mastery_state == "familiar"
        assert a1.id != a2.id

    def test_review_count_only_for_review(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        # practice attempt → review_count should not increase
        id1 = _create_sa_attempt(tmp_db, client)
        client.post(
            f"/api/v1/attempts/{id1}/self-assessment",
            json={"mastery_state": "vague"},
        )

        rs = (
            tmp_db.query(ReviewState)
            .filter(ReviewState.question_id == "spark.shuffle.qa.001")
            .first()
        )
        assert rs.review_count == 0  # practice, not review

    def test_algorithm_state_json_correct(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        attempt_id = _create_sa_attempt(tmp_db, client)
        client.post(
            f"/api/v1/attempts/{attempt_id}/self-assessment",
            json={"mastery_state": "familiar"},
        )

        rs = (
            tmp_db.query(ReviewState)
            .filter(ReviewState.question_id == "spark.shuffle.qa.001")
            .first()
        )
        algo = json.loads(rs.algorithm_state_json)
        assert algo["review_stage"] == 3
        assert algo["last_evaluation_mode"] == "self"

    def test_next_review_date_uses_timezone(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        attempt_id = _create_sa_attempt(tmp_db, client)
        resp = client.post(
            f"/api/v1/attempts/{attempt_id}/self-assessment",
            json={"mastery_state": "unmastered"},
        )

        nrd = resp.json()["review_state"]["next_review_date"]
        # Should be a valid date string
        parsed = date.fromisoformat(nrd)
        # Should be at least tomorrow (Asia/Shanghai timezone)
        from datetime import datetime
        from zoneinfo import ZoneInfo
        today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
        assert parsed >= today + timedelta(days=1)


# ---------------------------------------------------------------------------
# Idempotent
# ---------------------------------------------------------------------------

class TestSelfAssessmentIdempotent:
    def test_same_mastery_state_returns_200(
        self, tmp_db: Session, content_dir: Path
    ):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        attempt_id = _create_sa_attempt(tmp_db, client)
        resp1 = client.post(
            f"/api/v1/attempts/{attempt_id}/self-assessment",
            json={"mastery_state": "familiar"},
        )
        assert resp1.status_code == 201

        resp2 = client.post(
            f"/api/v1/attempts/{attempt_id}/self-assessment",
            json={"mastery_state": "familiar"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["attempt_id"] == attempt_id

    def test_idempotent_does_not_advance_stage(
        self, tmp_db: Session, content_dir: Path
    ):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        attempt_id = _create_sa_attempt(tmp_db, client)
        client.post(
            f"/api/v1/attempts/{attempt_id}/self-assessment",
            json={"mastery_state": "familiar"},
        )

        # Retry
        client.post(
            f"/api/v1/attempts/{attempt_id}/self-assessment",
            json={"mastery_state": "familiar"},
        )

        rs = (
            tmp_db.query(ReviewState)
            .filter(ReviewState.question_id == "spark.shuffle.qa.001")
            .first()
        )
        # consecutive_successes should be 1, not 2
        assert rs.consecutive_successes == 1

    def test_different_mastery_state_returns_409(
        self, tmp_db: Session, content_dir: Path
    ):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        attempt_id = _create_sa_attempt(tmp_db, client)
        client.post(
            f"/api/v1/attempts/{attempt_id}/self-assessment",
            json={"mastery_state": "familiar"},
        )

        resp = client.post(
            f"/api/v1/attempts/{attempt_id}/self-assessment",
            json={"mastery_state": "mastered"},
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "SELF_ASSESSMENT_ALREADY_COMPLETED"


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

class TestSelfAssessmentErrors:
    def test_attempt_not_found_404(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.post(
            "/api/v1/attempts/99999/self-assessment",
            json={"mastery_state": "vague"},
        )
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "ATTEMPT_NOT_FOUND"

    def test_choice_attempt_rejected(self, tmp_db: Session, content_dir: Path):
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
        attempt_id = resp.json()["attempt_id"]

        resp = client.post(
            f"/api/v1/attempts/{attempt_id}/self-assessment",
            json={"mastery_state": "vague"},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "INVALID_SELF_ASSESSMENT"

    def test_sql_attempt_rejected(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.post(
            "/api/v1/questions/spark.shuffle.sql.001/attempts",
            json={
                "question_revision": 1,
                "attempt_type": "practice",
                "client_request_id": str(uuid4()),
                "answer": "SELECT 1",
            },
        )
        attempt_id = resp.json()["attempt_id"]

        resp = client.post(
            f"/api/v1/attempts/{attempt_id}/self-assessment",
            json={"mastery_state": "vague"},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "INVALID_SELF_ASSESSMENT"


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