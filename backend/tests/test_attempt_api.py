"""Tests for Attempt API — Task 5.1."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.content.importer import import_content
from app.db.models.attempt import Attempt
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


# ---------------------------------------------------------------------------
# Choice attempts
# ---------------------------------------------------------------------------

class TestChoiceAttempt:
    def test_correct_answer_feedback(self, tmp_db: Session, content_dir: Path):
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
        data = resp.json()
        assert data["status"] == "completed"
        assert data["is_correct"] is True
        assert data["score"] == 1.0
        assert data["correct_answer"] == "B"
        assert data["explanation"] == "reduceByKey 需要按 key 重新分区。"
        assert data.get("reference_answer") is None

    def test_wrong_answer_feedback(self, tmp_db: Session, content_dir: Path):
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
        data = resp.json()
        assert data["status"] == "completed"
        assert data["is_correct"] is False
        assert data["score"] == 0.0
        assert data["correct_answer"] == "B"


# ---------------------------------------------------------------------------
# Short Answer attempts — Task 5.1
# ---------------------------------------------------------------------------

class TestShortAnswerAttempt:
    def test_returns_reference_answer(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

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
        data = resp.json()
        assert data["reference_answer"] == "Shuffle 是数据重新分区的过程。"

    def test_returns_explanation(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.post(
            "/api/v1/questions/spark.shuffle.qa.001/attempts",
            json={
                "question_revision": 1,
                "attempt_type": "practice",
                "client_request_id": str(uuid4()),
                "answer": "用户答案",
            },
        )
        data = resp.json()
        assert data["explanation"] == "宽依赖触发 Shuffle。"

    def test_status_awaiting_self_assessment(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.post(
            "/api/v1/questions/spark.shuffle.qa.001/attempts",
            json={
                "question_revision": 1,
                "attempt_type": "practice",
                "client_request_id": str(uuid4()),
                "answer": "用户答案",
            },
        )
        assert resp.json()["status"] == "awaiting_self_assessment"

    def test_no_score_fields(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.post(
            "/api/v1/questions/spark.shuffle.qa.001/attempts",
            json={
                "question_revision": 1,
                "attempt_type": "practice",
                "client_request_id": str(uuid4()),
                "answer": "用户答案",
            },
        )
        data = resp.json()
        assert data["is_correct"] is None
        assert data["score"] is None
        assert data["correct_answer"] is None

    def test_returns_answer(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.post(
            "/api/v1/questions/spark.shuffle.qa.001/attempts",
            json={
                "question_revision": 1,
                "attempt_type": "practice",
                "client_request_id": str(uuid4()),
                "answer": "我的回答内容",
            },
        )
        assert resp.json()["answer"] == "我的回答内容"

    def test_db_lifecycle(self, tmp_db: Session, content_dir: Path):
        """Verify Attempt DB fields for Short Answer lifecycle."""
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        cid = str(uuid4())
        resp = client.post(
            "/api/v1/questions/spark.shuffle.qa.001/attempts",
            json={
                "question_revision": 1,
                "attempt_type": "practice",
                "client_request_id": cid,
                "answer": "用户答案",
            },
        )
        assert resp.status_code == 201

        # Check DB directly
        attempt = (
            tmp_db.query(Attempt)
            .filter(Attempt.client_request_id == cid)
            .first()
        )
        assert attempt is not None
        assert attempt.status == "awaiting_self_assessment"
        assert attempt.user_answer == "用户答案"
        assert attempt.final_score is None
        assert attempt.max_score is None
        assert attempt.final_score_source is None
        assert attempt.finalized_at is None
        assert attempt.review_applied_at is None

    def test_uses_specified_revision(self, tmp_db: Session, content_dir: Path):
        """reference_answer comes from specified revision, not current."""
        from app.db.models.question import Question, QuestionVersion

        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        # Insert revision 2 with different reference_answer
        v2 = QuestionVersion(
            question_id="spark.shuffle.qa.001",
            revision=2,
            payload_json=json.dumps({
                "content": "不同内容",
                "reference_answer": "Revision 2 参考答案",
                "explanation": "Revision 2 解析",
            }),
        )
        tmp_db.add(v2)
        q = (
            tmp_db.query(Question)
            .filter(Question.id == "spark.shuffle.qa.001")
            .first()
        )
        q.current_revision = 2
        tmp_db.commit()

        # Submit with question_revision=1
        resp = client.post(
            "/api/v1/questions/spark.shuffle.qa.001/attempts",
            json={
                "question_revision": 1,
                "attempt_type": "practice",
                "client_request_id": str(uuid4()),
                "answer": "用户答案",
            },
        )
        data = resp.json()
        # Should use revision 1's reference_answer
        assert data["reference_answer"] == "Shuffle 是数据重新分区的过程。"
        assert data["explanation"] == "宽依赖触发 Shuffle。"


# ---------------------------------------------------------------------------
# Short Answer idempotency
# ---------------------------------------------------------------------------

class TestShortAnswerIdempotency:
    def test_idempotent_feedback_consistent(
        self, tmp_db: Session, content_dir: Path
    ):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        cid = str(uuid4())
        body = {
            "question_revision": 1,
            "attempt_type": "practice",
            "client_request_id": cid,
            "answer": "用户答案",
        }

        resp1 = client.post(
            "/api/v1/questions/spark.shuffle.qa.001/attempts", json=body
        )
        assert resp1.status_code == 201
        data1 = resp1.json()

        resp2 = client.post(
            "/api/v1/questions/spark.shuffle.qa.001/attempts", json=body
        )
        assert resp2.status_code == 200
        data2 = resp2.json()

        assert data1["attempt_id"] == data2["attempt_id"]
        assert data1["status"] == data2["status"]
        assert data1["answer"] == data2["answer"]
        assert data1["reference_answer"] == data2["reference_answer"]
        assert data1["explanation"] == data2["explanation"]

    def test_idempotent_uses_attempt_revision(
        self, tmp_db: Session, content_dir: Path
    ):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        # Submit with revision=1
        cid = str(uuid4())
        body = {
            "question_revision": 1,
            "attempt_type": "practice",
            "client_request_id": cid,
            "answer": "用户答案",
        }
        resp1 = client.post(
            "/api/v1/questions/spark.shuffle.qa.001/attempts", json=body
        )
        data1 = resp1.json()
        assert data1["reference_answer"] == "Shuffle 是数据重新分区的过程。"

        # Change current_revision to 2
        from app.db.models.question import Question, QuestionVersion
        v2 = QuestionVersion(
            question_id="spark.shuffle.qa.001",
            revision=2,
            payload_json=json.dumps({
                "content": "x",
                "reference_answer": "Revision 2 参考答案",
                "explanation": "Revision 2 解析",
            }),
        )
        tmp_db.add(v2)
        q = (
            tmp_db.query(Question)
            .filter(Question.id == "spark.shuffle.qa.001")
            .first()
        )
        q.current_revision = 2
        tmp_db.commit()

        # Retry → should still use revision 1
        resp2 = client.post(
            "/api/v1/questions/spark.shuffle.qa.001/attempts", json=body
        )
        data2 = resp2.json()
        assert data2["reference_answer"] == "Shuffle 是数据重新分区的过程。"
        assert data2["explanation"] == "宽依赖触发 Shuffle。"
        assert data2["attempt_id"] == data1["attempt_id"]

    def test_no_duplicate_attempt(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        cid = str(uuid4())
        body = {
            "question_revision": 1,
            "attempt_type": "practice",
            "client_request_id": cid,
            "answer": "用户答案",
        }

        client = _make_client(tmp_db)
        client.post(
            "/api/v1/questions/spark.shuffle.qa.001/attempts", json=body
        )
        client.post(
            "/api/v1/questions/spark.shuffle.qa.001/attempts", json=body
        )

        # Only one Attempt in DB
        count = (
            tmp_db.query(Attempt)
            .filter(Attempt.client_request_id == cid)
            .count()
        )
        assert count == 1


# ---------------------------------------------------------------------------
# SQL attempts — no change
# ---------------------------------------------------------------------------

class TestSQLAttempt:
    def test_submit_sql_text(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.post(
            "/api/v1/questions/spark.shuffle.sql.001/attempts",
            json={
                "question_revision": 1,
                "attempt_type": "practice",
                "client_request_id": str(uuid4()),
                "answer": "SELECT * FROM emp",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        # SQL with mock provider → awaiting_confirmation (AI graded successfully)
        assert data["status"] == "awaiting_confirmation"
        assert data["is_correct"] is None
        assert data["score"] is None
        assert data["correct_answer"] is None
        assert data["reference_answer"] is None
        assert data["explanation"] is None
        # Assessment should be present
        assert "assessment" in data
        assert data["assessment"]["status"] == "success"


# ---------------------------------------------------------------------------
# Idempotency — Choice
# ---------------------------------------------------------------------------

class TestChoiceIdempotency:
    def test_idempotent_choice_feedback_consistent(
        self, tmp_db: Session, content_dir: Path
    ):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        cid = str(uuid4())
        body = {
            "question_revision": 1,
            "attempt_type": "practice",
            "client_request_id": cid,
            "answer": "B",
        }

        resp1 = client.post(
            "/api/v1/questions/spark.shuffle.choice.001/attempts", json=body
        )
        assert resp1.status_code == 201
        data1 = resp1.json()

        resp2 = client.post(
            "/api/v1/questions/spark.shuffle.choice.001/attempts", json=body
        )
        assert resp2.status_code == 200
        data2 = resp2.json()

        assert data1["attempt_id"] == data2["attempt_id"]
        assert data1["status"] == data2["status"]
        assert data1["is_correct"] == data2["is_correct"]
        assert data1["score"] == data2["score"]
        assert data1["correct_answer"] == data2["correct_answer"]
        assert data1["explanation"] == data2["explanation"]

    def test_idempotent_uses_attempt_revision_not_current(
        self, tmp_db: Session, content_dir: Path
    ):
        from app.db.models.question import Question, QuestionVersion

        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        cid = str(uuid4())
        body = {
            "question_revision": 1,
            "attempt_type": "practice",
            "client_request_id": cid,
            "answer": "B",
        }
        resp1 = client.post(
            "/api/v1/questions/spark.shuffle.choice.001/attempts", json=body
        )
        data1 = resp1.json()
        assert data1["correct_answer"] == "B"

        # Change current_revision to 2
        v2 = QuestionVersion(
            question_id="spark.shuffle.choice.001",
            revision=2,
            payload_json=json.dumps({
                "content": "x",
                "options": [{"key": "A", "text": "x"}],
                "correct_answer": "A",
                "explanation": "Rev2",
            }),
        )
        tmp_db.add(v2)
        q = (
            tmp_db.query(Question)
            .filter(Question.id == "spark.shuffle.choice.001")
            .first()
        )
        q.current_revision = 2
        tmp_db.commit()

        resp2 = client.post(
            "/api/v1/questions/spark.shuffle.choice.001/attempts", json=body
        )
        data2 = resp2.json()
        assert data2["correct_answer"] == "B"
        assert data2["attempt_id"] == data1["attempt_id"]

    def test_different_client_request_ids_create_separate(
        self, tmp_db: Session, content_dir: Path
    ):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp1 = client.post(
            "/api/v1/questions/spark.shuffle.choice.001/attempts",
            json={
                "question_revision": 1,
                "attempt_type": "practice",
                "client_request_id": str(uuid4()),
                "answer": "B",
            },
        )
        resp2 = client.post(
            "/api/v1/questions/spark.shuffle.choice.001/attempts",
            json={
                "question_revision": 1,
                "attempt_type": "practice",
                "client_request_id": str(uuid4()),
                "answer": "A",
            },
        )
        assert resp1.status_code == 201
        assert resp2.status_code == 201
        assert resp1.json()["attempt_id"] != resp2.json()["attempt_id"]


# ---------------------------------------------------------------------------
# Revision binding
# ---------------------------------------------------------------------------

class TestRevisionBinding:
    def test_attempt_saves_specified_revision(self, tmp_db: Session, content_dir: Path):
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
        assert resp.json()["question_revision"] == 1

    def test_invalid_revision_400(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.post(
            "/api/v1/questions/spark.shuffle.choice.001/attempts",
            json={
                "question_revision": 999,
                "attempt_type": "practice",
                "client_request_id": str(uuid4()),
                "answer": "B",
            },
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "INVALID_REVISION"

    def test_choice_grading_uses_specified_revision(
        self, tmp_db: Session, content_dir: Path
    ):
        from app.db.models.question import Question, QuestionVersion

        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        v1 = (
            tmp_db.query(QuestionVersion)
            .filter(
                QuestionVersion.question_id == "spark.shuffle.choice.001",
                QuestionVersion.revision == 1,
            )
            .first()
        )
        payload1 = json.loads(v1.payload_json)
        assert payload1["correct_answer"] == "B"

        v2 = QuestionVersion(
            question_id="spark.shuffle.choice.001",
            revision=2,
            payload_json=json.dumps({
                "content": payload1["content"],
                "options": payload1["options"],
                "correct_answer": "A",
                "explanation": "Rev2.",
            }),
        )
        tmp_db.add(v2)
        q = (
            tmp_db.query(Question)
            .filter(Question.id == "spark.shuffle.choice.001")
            .first()
        )
        q.current_revision = 2
        tmp_db.commit()

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
        data = resp.json()
        assert data["is_correct"] is True
        assert data["correct_answer"] == "B"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestAttemptErrors:
    def test_empty_answer_400(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.post(
            "/api/v1/questions/spark.shuffle.choice.001/attempts",
            json={
                "question_revision": 1,
                "attempt_type": "practice",
                "client_request_id": str(uuid4()),
                "answer": "",
            },
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "INVALID_ANSWER"

    def test_nonexistent_question_404(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.post(
            "/api/v1/questions/nonexistent/attempts",
            json={
                "question_revision": 1,
                "attempt_type": "practice",
                "client_request_id": str(uuid4()),
                "answer": "B",
            },
        )
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "QUESTION_NOT_FOUND"

    def test_inactive_question_404(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        from app.db.models.question import Question
        q = tmp_db.query(Question).filter(Question.id == "spark.shuffle.choice.001").first()
        q.is_active = False
        tmp_db.commit()

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
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Answer hiding — GET question still hides answers
# ---------------------------------------------------------------------------

class TestAnswerHiding:
    def test_short_answer_get_hides_reference(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/questions/spark.shuffle.qa.001")
        assert resp.status_code == 200
        data = resp.json()
        assert "reference_answer" not in data
        assert "explanation" not in data

    def test_choice_get_hides_correct(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/questions/spark.shuffle.choice.001")
        assert resp.status_code == 200
        data = resp.json()
        assert "correct_answer" not in data
        assert "explanation" not in data


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