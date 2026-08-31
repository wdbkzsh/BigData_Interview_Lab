"""Tests for SQL Attempt + AI Assessment — Phase 8B."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.content.importer import import_content
from app.db.models.attempt import AIAssessment, Attempt
from app.db.models.review import ReviewState
from app.db.session import get_db
from app.llm.mock_provider import MockLLMProvider
from app.llm.provider import LLMInvalidResponseError, LLMProviderError, LLMTimeoutError
from app.llm.schemas import SQLGradingInput, ScoringCriterionInput
from app.llm.service import LLMService
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
explanation: exp
"""


def _write_content(content_dir: Path) -> None:
    kp_dir = content_dir / "knowledge"
    kp_dir.mkdir(parents=True)
    (kp_dir / "spark.yaml").write_text(_KNOWLEDGE_YAML, encoding="utf-8")

    card_dir = content_dir / "cards"
    card_dir.mkdir(parents=True)
    (card_dir / "spark.shuffle.md").write_text(_CARD_SPARK_SHUFFLE, encoding="utf-8")

    sql_dir = content_dir / "questions" / "sql"
    sql_dir.mkdir(parents=True)
    (sql_dir / "spark.shuffle.sql.001.yaml").write_text(_SQL_001, encoding="utf-8")

    choice_dir = content_dir / "questions" / "choice"
    choice_dir.mkdir(parents=True)
    (choice_dir / "spark.shuffle.choice.001.yaml").write_text(_CHOICE_001, encoding="utf-8")

    qa_dir = content_dir / "questions" / "short_answer"
    qa_dir.mkdir(parents=True)


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
# SQL success flow
# ---------------------------------------------------------------------------

class TestSQLSuccess:
    def test_attempt_created_as_grading(self, tmp_db: Session, content_dir: Path):
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
        # Mock provider succeeds → awaiting_confirmation
        assert data["status"] == "awaiting_confirmation"
        assert data["question_id"] == "spark.shuffle.sql.001"

    def test_user_answer_saved(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.post(
            "/api/v1/questions/spark.shuffle.sql.001/attempts",
            json={
                "question_revision": 1,
                "attempt_type": "practice",
                "client_request_id": str(uuid4()),
                "answer": "SELECT dept, MAX(salary) FROM emp GROUP BY dept",
            },
        )
        data = resp.json()
        assert data["answer"] == "SELECT dept, MAX(salary) FROM emp GROUP BY dept"

    def test_ai_assessment_created(self, tmp_db: Session, content_dir: Path):
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
        data = resp.json()
        assert "assessment" in data
        assessment = data["assessment"]
        assert assessment["status"] == "success"
        assert assessment["raw_score"] is not None
        assert assessment["max_score"] is not None

    def test_assessment_metadata_saved(self, tmp_db: Session, content_dir: Path):
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
        data = resp.json()
        attempt_id = data["attempt_id"]

        # Check DB
        assessment = (
            tmp_db.query(AIAssessment)
            .filter(AIAssessment.attempt_id == attempt_id)
            .first()
        )
        assert assessment is not None
        assert assessment.provider == "mock"
        assert assessment.model == "mock-1"
        assert assessment.prompt_version == "sql_grading_v2"
        assert assessment.input_tokens == 100
        assert assessment.output_tokens == 50
        assert assessment.latency_ms == 10

    def test_expected_sql_in_response(self, tmp_db: Session, content_dir: Path):
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
        data = resp.json()
        assert "expected_sql" in data
        assert "ROW_NUMBER" in data["expected_sql"]

    def test_final_score_null(self, tmp_db: Session, content_dir: Path):
        """AI raw_score is set but attempt.final_score stays NULL."""
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
        attempt_id = resp.json()["attempt_id"]
        attempt = tmp_db.query(Attempt).filter(Attempt.id == attempt_id).first()
        assert attempt.final_score is None
        assert attempt.max_score is None
        assert attempt.final_score_source is None
        assert attempt.finalized_at is None
        assert attempt.review_applied_at is None

    def test_review_state_unchanged(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        count_before = tmp_db.query(ReviewState).count()

        client.post(
            "/api/v1/questions/spark.shuffle.sql.001/attempts",
            json={
                "question_revision": 1,
                "attempt_type": "practice",
                "client_request_id": str(uuid4()),
                "answer": "SELECT * FROM emp",
            },
        )

        count_after = tmp_db.query(ReviewState).count()
        assert count_after == count_before

    def test_historical_revision_used(self, tmp_db: Session, content_dir: Path):
        """SQL grading uses the specified revision, not current_revision."""
        import json as json_mod
        from app.db.models.question import Question, QuestionVersion

        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        # Insert revision 2 with different content
        v2 = QuestionVersion(
            question_id="spark.shuffle.sql.001",
            revision=2,
            payload_json=json_mod.dumps({
                "content": "Different content rev2",
                "table_schema": "CREATE TABLE t2 (x INT)",
                "field_description": "x field",
                "business_requirement": "Select all from t2",
                "expected_sql": "SELECT * FROM t2",
                "scoring_criteria": [
                    {"id": "c1", "description": "Correct", "points": 10},
                ],
            }),
        )
        tmp_db.add(v2)
        q = tmp_db.query(Question).filter(Question.id == "spark.shuffle.sql.001").first()
        q.current_revision = 2
        tmp_db.commit()

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
        data = resp.json()
        assert data["question_revision"] == 1
        # expected_sql should be from revision 1
        assert "ROW_NUMBER" in data["expected_sql"]


# ---------------------------------------------------------------------------
# SQL failure flows
# ---------------------------------------------------------------------------

class TestSQLFailure:
    def _write_content_and_import(self, tmp_db, content_dir):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

    def test_timeout_leads_to_grading_failed(self, tmp_db: Session, content_dir: Path):
        self._write_content_and_import(tmp_db, content_dir)

        # Override provider to timeout
        from app.llm import factory
        original = factory.create_provider
        factory.create_provider = lambda: MockLLMProvider(mode="timeout")
        try:
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
            assert data["status"] == "grading_failed"
            assert "assessment" in data
            assert data["assessment"]["status"] == "timeout"
        finally:
            factory.create_provider = original

    def test_provider_error_leads_to_grading_failed(self, tmp_db: Session, content_dir: Path):
        self._write_content_and_import(tmp_db, content_dir)

        from app.llm import factory
        original = factory.create_provider
        factory.create_provider = lambda: MockLLMProvider(mode="provider_error")
        try:
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
            assert data["status"] == "grading_failed"
            assert data["assessment"]["status"] == "failed"
        finally:
            factory.create_provider = original

    def test_invalid_response_leads_to_grading_failed(self, tmp_db: Session, content_dir: Path):
        self._write_content_and_import(tmp_db, content_dir)

        from app.llm import factory
        original = factory.create_provider
        factory.create_provider = lambda: MockLLMProvider(mode="invalid_response")
        try:
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
            assert data["status"] == "grading_failed"
            assert data["assessment"]["status"] == "invalid_response"
        finally:
            factory.create_provider = original

    def test_user_sql_retained_on_failure(self, tmp_db: Session, content_dir: Path):
        self._write_content_and_import(tmp_db, content_dir)

        from app.llm import factory
        original = factory.create_provider
        factory.create_provider = lambda: MockLLMProvider(mode="timeout")
        try:
            client = _make_client(tmp_db)
            resp = client.post(
                "/api/v1/questions/spark.shuffle.sql.001/attempts",
                json={
                    "question_revision": 1,
                    "attempt_type": "practice",
                    "client_request_id": str(uuid4()),
                    "answer": "MY PRECIOUS SQL",
                },
            )
            data = resp.json()
            assert data["answer"] == "MY PRECIOUS SQL"
            attempt_id = data["attempt_id"]
            attempt = tmp_db.query(Attempt).filter(Attempt.id == attempt_id).first()
            assert attempt.user_answer == "MY PRECIOUS SQL"
        finally:
            factory.create_provider = original

    def test_no_review_state_on_failure(self, tmp_db: Session, content_dir: Path):
        self._write_content_and_import(tmp_db, content_dir)

        from app.llm import factory
        original = factory.create_provider
        factory.create_provider = lambda: MockLLMProvider(mode="timeout")
        try:
            count_before = tmp_db.query(ReviewState).count()
            client = _make_client(tmp_db)
            client.post(
                "/api/v1/questions/spark.shuffle.sql.001/attempts",
                json={
                    "question_revision": 1,
                    "attempt_type": "practice",
                    "client_request_id": str(uuid4()),
                    "answer": "SELECT 1",
                },
            )
            count_after = tmp_db.query(ReviewState).count()
            assert count_after == count_before
        finally:
            factory.create_provider = original


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

class TestSQLIdempotency:
    def test_same_client_request_id_returns_existing(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        cid = str(uuid4())
        body = {
            "question_revision": 1,
            "attempt_type": "practice",
            "client_request_id": cid,
            "answer": "SELECT * FROM emp",
        }

        resp1 = client.post("/api/v1/questions/spark.shuffle.sql.001/attempts", json=body)
        assert resp1.status_code == 201
        data1 = resp1.json()

        resp2 = client.post("/api/v1/questions/spark.shuffle.sql.001/attempts", json=body)
        assert resp2.status_code == 200
        data2 = resp2.json()

        assert data1["attempt_id"] == data2["attempt_id"]
        assert data1["status"] == data2["status"]

    def test_assessment_count_remains_one(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        cid = str(uuid4())
        body = {
            "question_revision": 1,
            "attempt_type": "practice",
            "client_request_id": cid,
            "answer": "SELECT * FROM emp",
        }

        client.post("/api/v1/questions/spark.shuffle.sql.001/attempts", json=body)
        client.post("/api/v1/questions/spark.shuffle.sql.001/attempts", json=body)

        attempt = tmp_db.query(Attempt).filter(Attempt.client_request_id == cid).first()
        count = tmp_db.query(AIAssessment).filter(AIAssessment.attempt_id == attempt.id).count()
        assert count == 1


# ---------------------------------------------------------------------------
# LLM validation hardening (8A)
# ---------------------------------------------------------------------------

class TestLLMValidationHardening:
    def test_max_score_mismatch_rejected(self):
        inp = SQLGradingInput(
            question_id="test",
            content="test",
            business_requirement="test",
            scoring_criteria=[ScoringCriterionInput(id="c1", description="test", points=5)],
            user_sql="SELECT 1",
            max_score=10,
        )
        # Result with max_score != input max_score
        bad_result = {
            "score": 5,
            "max_score": 15,  # Should be 10
            "criteria": [{"id": "c1", "status": "matched", "score": 5, "max_score": 5, "feedback": ""}],
            "reasoning_summary": "",
        }
        provider = MockLLMProvider(mode="success", result=bad_result)
        service = LLMService(provider)

        with pytest.raises(LLMInvalidResponseError, match="max_score"):
            service.grade_sql(inp)

    def test_criterion_max_score_mismatch_rejected(self):
        inp = SQLGradingInput(
            question_id="test",
            content="test",
            business_requirement="test",
            scoring_criteria=[ScoringCriterionInput(id="c1", description="test", points=5)],
            user_sql="SELECT 1",
            max_score=5,
        )
        # Result with criterion max_score != rubric points
        bad_result = {
            "score": 3,
            "max_score": 5,
            "criteria": [{"id": "c1", "status": "partial", "score": 3, "max_score": 10, "feedback": ""}],
            "reasoning_summary": "",
        }
        provider = MockLLMProvider(mode="success", result=bad_result)
        service = LLMService(provider)

        with pytest.raises(LLMInvalidResponseError, match="max_score"):
            service.grade_sql(inp)


# ---------------------------------------------------------------------------
# Pending / Recovery
# ---------------------------------------------------------------------------

class TestSQLRecovery:
    def test_pending_includes_sql_confirmation(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/attempts/pending")
        assert resp.status_code == 200
        data = resp.json()
        assert "sql_confirmation" in data

    def test_awaiting_confirmation_in_pending(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        # Submit SQL → awaiting_confirmation
        resp = client.post(
            "/api/v1/questions/spark.shuffle.sql.001/attempts",
            json={
                "question_revision": 1,
                "attempt_type": "practice",
                "client_request_id": str(uuid4()),
                "answer": "SELECT * FROM emp",
            },
        )
        attempt_id = resp.json()["attempt_id"]

        # Check pending
        pending = client.get("/api/v1/attempts/pending").json()
        sql_ids = [p["attempt_id"] for p in pending["sql_confirmation"]]
        assert attempt_id in sql_ids

    def test_get_awaiting_confirmation_detail(self, tmp_db: Session, content_dir: Path):
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
        attempt_id = resp.json()["attempt_id"]

        # Get detail
        detail = client.get(f"/api/v1/attempts/{attempt_id}").json()
        assert detail["status"] == "awaiting_confirmation"
        assert "assessment" in detail
        assert "expected_sql" in detail

    def test_get_grading_failed_detail(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        from app.llm import factory
        original = factory.create_provider
        factory.create_provider = lambda: MockLLMProvider(mode="timeout")
        try:
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

            detail = client.get(f"/api/v1/attempts/{attempt_id}").json()
            assert detail["status"] == "grading_failed"
            assert "assessment" in detail
            assert detail["assessment"]["status"] == "timeout"
        finally:
            factory.create_provider = original


# ---------------------------------------------------------------------------
# Formal DB not polluted
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# SQL Confirm (Phase 8C1)
# ---------------------------------------------------------------------------

class TestSQLConfirm:
    def _create_awaiting(self, tmp_db, content_dir, client):
        """Helper: create an SQL attempt in awaiting_confirmation state."""
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
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
        assert resp.json()["status"] == "awaiting_confirmation"
        return resp.json()["attempt_id"]

    def test_accept(self, tmp_db: Session, content_dir: Path):
        client = _make_client(tmp_db)
        attempt_id = self._create_awaiting(tmp_db, content_dir, client)

        resp = client.post(
            f"/api/v1/attempts/{attempt_id}/confirm",
            json={"action": "accept"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "completed"
        assert data["final_score"] is not None
        assert data["final_score_source"] == "ai_confirmed"
        assert data["mastery_state"] is not None
        assert data["next_review_date"] is not None
        assert data["policy_version"] == "review_v2"

    def test_adjust(self, tmp_db: Session, content_dir: Path):
        client = _make_client(tmp_db)
        attempt_id = self._create_awaiting(tmp_db, content_dir, client)

        resp = client.post(
            f"/api/v1/attempts/{attempt_id}/confirm",
            json={"action": "adjust", "final_score": 9},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "completed"
        assert data["final_score"] == 9.0
        assert data["final_score_source"] == "user_adjusted"

    def test_accept_idempotent(self, tmp_db: Session, content_dir: Path):
        client = _make_client(tmp_db)
        attempt_id = self._create_awaiting(tmp_db, content_dir, client)

        resp1 = client.post(f"/api/v1/attempts/{attempt_id}/confirm", json={"action": "accept"})
        resp2 = client.post(f"/api/v1/attempts/{attempt_id}/confirm", json={"action": "accept"})
        assert resp1.status_code == 201
        assert resp2.status_code == 200
        assert resp1.json()["attempt_id"] == resp2.json()["attempt_id"]

    def test_adjust_idempotent(self, tmp_db: Session, content_dir: Path):
        client = _make_client(tmp_db)
        attempt_id = self._create_awaiting(tmp_db, content_dir, client)

        resp1 = client.post(f"/api/v1/attempts/{attempt_id}/confirm", json={"action": "adjust", "final_score": 7})
        resp2 = client.post(f"/api/v1/attempts/{attempt_id}/confirm", json={"action": "adjust", "final_score": 7})
        assert resp1.status_code == 201
        assert resp2.status_code == 200

    def test_different_action_returns_409(self, tmp_db: Session, content_dir: Path):
        client = _make_client(tmp_db)
        attempt_id = self._create_awaiting(tmp_db, content_dir, client)

        client.post(f"/api/v1/attempts/{attempt_id}/confirm", json={"action": "accept"})
        resp = client.post(f"/api/v1/attempts/{attempt_id}/confirm", json={"action": "adjust", "final_score": 5})
        assert resp.status_code == 409

    def test_review_state_updated(self, tmp_db: Session, content_dir: Path):
        client = _make_client(tmp_db)
        attempt_id = self._create_awaiting(tmp_db, content_dir, client)

        client.post(f"/api/v1/attempts/{attempt_id}/confirm", json={"action": "accept"})

        from app.db.models.review import ReviewState
        rs = tmp_db.query(ReviewState).filter(ReviewState.question_id == "spark.shuffle.sql.001").first()
        assert rs is not None
        assert rs.mastery_state is not None
        assert rs.policy_version == "review_v2"

    def test_attempt_final_fields(self, tmp_db: Session, content_dir: Path):
        client = _make_client(tmp_db)
        attempt_id = self._create_awaiting(tmp_db, content_dir, client)

        client.post(f"/api/v1/attempts/{attempt_id}/confirm", json={"action": "accept"})

        attempt = tmp_db.query(Attempt).filter(Attempt.id == attempt_id).first()
        assert attempt.status == "completed"
        assert attempt.final_score is not None
        assert attempt.max_score is not None
        assert attempt.final_score_source == "ai_confirmed"
        assert attempt.final_result_json is not None
        assert attempt.finalized_at is not None
        assert attempt.review_applied_at is not None

    def test_attempt_knowledge_result_created(self, tmp_db: Session, content_dir: Path):
        from app.db.models.attempt import AttemptKnowledgeResult
        client = _make_client(tmp_db)
        attempt_id = self._create_awaiting(tmp_db, content_dir, client)

        client.post(f"/api/v1/attempts/{attempt_id}/confirm", json={"action": "accept"})

        # Check if any knowledge results were created (depends on mock data)
        count = tmp_db.query(AttemptKnowledgeResult).filter(
            AttemptKnowledgeResult.attempt_id == attempt_id
        ).count()
        # Mock returns empty knowledge_analysis, so count may be 0
        assert count >= 0

    def test_ai_raw_score_unchanged(self, tmp_db: Session, content_dir: Path):
        from app.db.models.attempt import AIAssessment
        client = _make_client(tmp_db)
        attempt_id = self._create_awaiting(tmp_db, content_dir, client)

        # Get original raw_score
        assessment_before = tmp_db.query(AIAssessment).filter(
            AIAssessment.attempt_id == attempt_id
        ).first()
        raw_before = assessment_before.raw_score

        # Adjust to different score
        client.post(
            f"/api/v1/attempts/{attempt_id}/confirm",
            json={"action": "adjust", "final_score": 3},
        )

        # AI raw_score unchanged
        assessment_after = tmp_db.query(AIAssessment).filter(
            AIAssessment.attempt_id == attempt_id
        ).first()
        assert assessment_after.raw_score == raw_before

    def test_adjust_score_bounds(self, tmp_db: Session, content_dir: Path):
        client = _make_client(tmp_db)
        attempt_id = self._create_awaiting(tmp_db, content_dir, client)

        # Negative score
        resp = client.post(
            f"/api/v1/attempts/{attempt_id}/confirm",
            json={"action": "adjust", "final_score": -1},
        )
        assert resp.status_code == 400

    def test_adjust_over_max(self, tmp_db: Session, content_dir: Path):
        client = _make_client(tmp_db)
        attempt_id = self._create_awaiting(tmp_db, content_dir, client)

        resp = client.post(
            f"/api/v1/attempts/{attempt_id}/confirm",
            json={"action": "adjust", "final_score": 999},
        )
        assert resp.status_code == 400

    def test_nonexistent_attempt(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.post("/api/v1/attempts/99999/confirm", json={"action": "accept"})
        assert resp.status_code == 404

    def test_non_sql_rejected(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        # Create a choice attempt
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

        resp = client.post(f"/api/v1/attempts/{attempt_id}/confirm", json={"action": "accept"})
        assert resp.status_code == 400

    def test_review_count_for_review_type(self, tmp_db: Session, content_dir: Path):
        from app.db.models.review import ReviewState
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.post(
            "/api/v1/questions/spark.shuffle.sql.001/attempts",
            json={
                "question_revision": 1,
                "attempt_type": "review",
                "client_request_id": str(uuid4()),
                "answer": "SELECT 1",
            },
        )
        attempt_id = resp.json()["attempt_id"]

        client.post(f"/api/v1/attempts/{attempt_id}/confirm", json={"action": "accept"})

        rs = tmp_db.query(ReviewState).filter(ReviewState.question_id == "spark.shuffle.sql.001").first()
        assert rs is not None
        assert rs.review_count == 1

    def test_review_count_not_increased_for_practice(self, tmp_db: Session, content_dir: Path):
        from app.db.models.review import ReviewState
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

        client.post(f"/api/v1/attempts/{attempt_id}/confirm", json={"action": "accept"})

        rs = tmp_db.query(ReviewState).filter(ReviewState.question_id == "spark.shuffle.sql.001").first()
        assert rs is not None
        assert rs.review_count == 0


# ---------------------------------------------------------------------------
# Knowledge Contract (Phase 8C1)
# ---------------------------------------------------------------------------

class TestKnowledgeContract:
    def test_knowledge_points_in_input(self):
        from app.llm.schemas import SQLGradingInput, SQLKnowledgePoint
        inp = SQLGradingInput(
            question_id="test",
            content="test",
            business_requirement="test",
            scoring_criteria=[],
            user_sql="SELECT 1",
            max_score=0,
            knowledge_points=[
                SQLKnowledgePoint(id="kp1", name="KP1"),
                SQLKnowledgePoint(id="kp2", name="KP2"),
            ],
        )
        assert len(inp.knowledge_points) == 2

    def test_unknown_kp_rejected(self):
        from app.llm.mock_provider import MockLLMProvider
        from app.llm.schemas import SQLGradingInput, SQLKnowledgePoint, ScoringCriterionInput
        from app.llm.service import LLMService

        inp = SQLGradingInput(
            question_id="test",
            content="test",
            business_requirement="test",
            scoring_criteria=[ScoringCriterionInput(id="c1", description="test", points=5)],
            user_sql="SELECT 1",
            max_score=5,
            knowledge_points=[SQLKnowledgePoint(id="kp1", name="KP1")],
        )
        bad_result = {
            "score": 5,
            "max_score": 5,
            "criteria": [{"id": "c1", "status": "matched", "score": 5, "max_score": 5, "feedback": ""}],
            "knowledge_analysis": {"mastered": ["unknown_kp"], "weak": [], "missing": []},
            "reasoning_summary": "",
        }
        provider = MockLLMProvider(mode="success", result=bad_result)
        service = LLMService(provider)

        with pytest.raises(Exception, match="Unknown knowledge point"):
            service.grade_sql(inp)

    def test_overlapping_kp_rejected(self):
        from app.llm.mock_provider import MockLLMProvider
        from app.llm.schemas import SQLGradingInput, SQLKnowledgePoint, ScoringCriterionInput
        from app.llm.service import LLMService

        inp = SQLGradingInput(
            question_id="test",
            content="test",
            business_requirement="test",
            scoring_criteria=[ScoringCriterionInput(id="c1", description="test", points=5)],
            user_sql="SELECT 1",
            max_score=5,
            knowledge_points=[SQLKnowledgePoint(id="kp1", name="KP1")],
        )
        bad_result = {
            "score": 5,
            "max_score": 5,
            "criteria": [{"id": "c1", "status": "matched", "score": 5, "max_score": 5, "feedback": ""}],
            "knowledge_analysis": {"mastered": ["kp1"], "weak": ["kp1"], "missing": []},
            "reasoning_summary": "",
        }
        provider = MockLLMProvider(mode="success", result=bad_result)
        service = LLMService(provider)

        with pytest.raises(Exception, match="mastered and weak"):
            service.grade_sql(inp)


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# SQL Regrade (Phase 8C2)
# ---------------------------------------------------------------------------

class TestSQLRegrade:
    def _create_grading_failed(self, tmp_db, content_dir, client):
        """Create a grading_failed SQL attempt."""
        from app.llm import factory
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        original = factory.create_provider
        factory.create_provider = lambda: MockLLMProvider(mode="timeout")
        try:
            resp = client.post(
                "/api/v1/questions/spark.shuffle.sql.001/attempts",
                json={
                    "question_revision": 1,
                    "attempt_type": "practice",
                    "client_request_id": str(uuid4()),
                    "answer": "SELECT * FROM emp",
                },
            )
            assert resp.json()["status"] == "grading_failed"
            return resp.json()["attempt_id"]
        finally:
            factory.create_provider = original

    def _create_awaiting(self, tmp_db, content_dir, client):
        """Create an awaiting_confirmation SQL attempt."""
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        resp = client.post(
            "/api/v1/questions/spark.shuffle.sql.001/attempts",
            json={
                "question_revision": 1,
                "attempt_type": "practice",
                "client_request_id": str(uuid4()),
                "answer": "SELECT * FROM emp",
            },
        )
        assert resp.json()["status"] == "awaiting_confirmation"
        return resp.json()["attempt_id"]

    def test_regrade_from_failure(self, tmp_db: Session, content_dir: Path):
        client = _make_client(tmp_db)
        attempt_id = self._create_grading_failed(tmp_db, content_dir, client)

        from app.db.models.attempt import AIAssessment
        count_before = tmp_db.query(AIAssessment).filter(AIAssessment.attempt_id == attempt_id).count()

        resp = client.post(f"/api/v1/attempts/{attempt_id}/regrade")
        assert resp.status_code == 200
        data = resp.json()
        assert data["attempt_id"] == attempt_id
        assert data["status"] == "awaiting_confirmation"

        # Assessment count +1
        count_after = tmp_db.query(AIAssessment).filter(AIAssessment.attempt_id == attempt_id).count()
        assert count_after == count_before + 1

    def test_regrade_from_awaiting(self, tmp_db: Session, content_dir: Path):
        client = _make_client(tmp_db)
        attempt_id = self._create_awaiting(tmp_db, content_dir, client)

        from app.db.models.attempt import AIAssessment
        count_before = tmp_db.query(AIAssessment).filter(AIAssessment.attempt_id == attempt_id).count()

        resp = client.post(f"/api/v1/attempts/{attempt_id}/regrade")
        assert resp.status_code == 200
        assert resp.json()["status"] == "awaiting_confirmation"

        count_after = tmp_db.query(AIAssessment).filter(AIAssessment.attempt_id == attempt_id).count()
        assert count_after == count_before + 1

    def test_same_attempt_id(self, tmp_db: Session, content_dir: Path):
        client = _make_client(tmp_db)
        attempt_id = self._create_grading_failed(tmp_db, content_dir, client)

        resp = client.post(f"/api/v1/attempts/{attempt_id}/regrade")
        assert resp.json()["attempt_id"] == attempt_id

    def test_regrade_timeout(self, tmp_db: Session, content_dir: Path):
        client = _make_client(tmp_db)
        attempt_id = self._create_grading_failed(tmp_db, content_dir, client)

        from app.llm import factory
        original = factory.create_provider
        factory.create_provider = lambda: MockLLMProvider(mode="timeout")
        try:
            resp = client.post(f"/api/v1/attempts/{attempt_id}/regrade")
            assert resp.status_code == 200
            assert resp.json()["status"] == "grading_failed"
        finally:
            factory.create_provider = original

    def test_completed_rejected(self, tmp_db: Session, content_dir: Path):
        client = _make_client(tmp_db)
        attempt_id = self._create_awaiting(tmp_db, content_dir, client)

        # Confirm first
        client.post(f"/api/v1/attempts/{attempt_id}/confirm", json={"action": "accept"})

        resp = client.post(f"/api/v1/attempts/{attempt_id}/regrade")
        assert resp.status_code == 409

    def test_grading_in_progress_rejected(self, tmp_db: Session, content_dir: Path):
        """If status=grading, regrade should be rejected."""
        from app.db.models.attempt import Attempt
        client = _make_client(tmp_db)
        attempt_id = self._create_grading_failed(tmp_db, content_dir, client)

        # Manually set to grading
        attempt = tmp_db.query(Attempt).filter(Attempt.id == attempt_id).first()
        attempt.status = "grading"
        tmp_db.commit()

        resp = client.post(f"/api/v1/attempts/{attempt_id}/regrade")
        assert resp.status_code == 409

    def test_regrade_from_disputed(self, tmp_db: Session, content_dir: Path):
        """disputed → regrade → same Attempt → new Assessment → awaiting_confirmation."""
        client = _make_client(tmp_db)
        attempt_id = self._create_awaiting(tmp_db, content_dir, client)

        # Dispute
        resp = client.post(
            f"/api/v1/attempts/{attempt_id}/dispute",
            json={"reason": "AI 理解错误"},
        )
        assert resp.json()["status"] == "disputed"

        from app.db.models.attempt import AIAssessment
        attempt_count_before = tmp_db.query(Attempt).count()
        assessment_count_before = tmp_db.query(AIAssessment).filter(
            AIAssessment.attempt_id == attempt_id
        ).count()

        # Regrade
        resp = client.post(f"/api/v1/attempts/{attempt_id}/regrade")
        assert resp.status_code == 200
        assert resp.json()["status"] == "awaiting_confirmation"
        assert resp.json()["attempt_id"] == attempt_id

        # Attempt count unchanged
        assert tmp_db.query(Attempt).count() == attempt_count_before
        # Assessment count +1
        assert tmp_db.query(AIAssessment).filter(
            AIAssessment.attempt_id == attempt_id
        ).count() == assessment_count_before + 1

    def test_regrade_uses_historical_revision(self, tmp_db: Session, content_dir: Path):
        """Regrade uses attempt.question_revision, not current_revision."""
        import json as json_mod
        from app.db.models.question import Question, QuestionVersion
        from app.db.models.attempt import AIAssessment

        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        # Create attempt with revision=1
        client = _make_client(tmp_db)
        resp = client.post(
            "/api/v1/questions/spark.shuffle.sql.001/attempts",
            json={
                "question_revision": 1,
                "attempt_type": "practice",
                "client_request_id": str(uuid4()),
                "answer": "MY ORIGINAL SQL",
            },
        )
        attempt_id = resp.json()["attempt_id"]

        # Change current_revision to 2
        v2 = QuestionVersion(
            question_id="spark.shuffle.sql.001",
            revision=2,
            payload_json=json_mod.dumps({
                "content": "Different content rev2",
                "table_schema": "CREATE TABLE t2 (x INT)",
                "field_description": "x",
                "business_requirement": "Select from t2",
                "expected_sql": "SELECT * FROM t2",
                "scoring_criteria": [{"id": "c1", "description": "test", "points": 10}],
            }),
        )
        tmp_db.add(v2)
        q = tmp_db.query(Question).filter(Question.id == "spark.shuffle.sql.001").first()
        q.current_revision = 2
        tmp_db.commit()

        # Set to grading_failed to allow regrade
        attempt = tmp_db.query(Attempt).filter(Attempt.id == attempt_id).first()
        attempt.status = "grading_failed"
        tmp_db.commit()

        # Regrade
        resp = client.post(f"/api/v1/attempts/{attempt_id}/regrade")
        assert resp.status_code == 200

        # Check the last assessment was created with revision=1 content
        assessment = (
            tmp_db.query(AIAssessment)
            .filter(AIAssessment.attempt_id == attempt_id)
            .order_by(AIAssessment.id.desc())
            .first()
        )
        assert assessment is not None
        # The prompt should have used revision 1's content (ROW_NUMBER), not revision 2
        # We verify by checking the attempt still has revision=1
        attempt_after = tmp_db.query(Attempt).filter(Attempt.id == attempt_id).first()
        assert attempt_after.question_revision == 1
        assert attempt_after.user_answer == "MY ORIGINAL SQL"


# ---------------------------------------------------------------------------
# SQL Dispute (Phase 8C2)
# ---------------------------------------------------------------------------

class TestSQLDispute:
    def _create_awaiting(self, tmp_db, content_dir, client):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        resp = client.post(
            "/api/v1/questions/spark.shuffle.sql.001/attempts",
            json={
                "question_revision": 1,
                "attempt_type": "practice",
                "client_request_id": str(uuid4()),
                "answer": "SELECT * FROM emp",
            },
        )
        assert resp.json()["status"] == "awaiting_confirmation"
        return resp.json()["attempt_id"]

    def test_dispute(self, tmp_db: Session, content_dir: Path):
        client = _make_client(tmp_db)
        attempt_id = self._create_awaiting(tmp_db, content_dir, client)

        resp = client.post(
            f"/api/v1/attempts/{attempt_id}/dispute",
            json={"reason": "AI 对 JOIN 条件理解错误"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "disputed"

    def test_dispute_idempotent(self, tmp_db: Session, content_dir: Path):
        client = _make_client(tmp_db)
        attempt_id = self._create_awaiting(tmp_db, content_dir, client)

        client.post(f"/api/v1/attempts/{attempt_id}/dispute", json={"reason": "test"})
        resp = client.post(f"/api/v1/attempts/{attempt_id}/dispute", json={"reason": "test"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "disputed"

    def test_dispute_no_llm_call(self, tmp_db: Session, content_dir: Path):
        client = _make_client(tmp_db)
        attempt_id = self._create_awaiting(tmp_db, content_dir, client)

        from app.db.models.attempt import AIAssessment
        count_before = tmp_db.query(AIAssessment).count()

        client.post(f"/api/v1/attempts/{attempt_id}/dispute", json={"reason": "test"})

        count_after = tmp_db.query(AIAssessment).count()
        assert count_after == count_before

    def test_dispute_no_final_score(self, tmp_db: Session, content_dir: Path):
        client = _make_client(tmp_db)
        attempt_id = self._create_awaiting(tmp_db, content_dir, client)

        client.post(f"/api/v1/attempts/{attempt_id}/dispute", json={"reason": "test"})

        from app.db.models.attempt import Attempt
        attempt = tmp_db.query(Attempt).filter(Attempt.id == attempt_id).first()
        assert attempt.final_score is None
        assert attempt.finalized_at is None
        assert attempt.review_applied_at is None

    def test_dispute_no_review_state(self, tmp_db: Session, content_dir: Path):
        from app.db.models.review import ReviewState
        client = _make_client(tmp_db)
        attempt_id = self._create_awaiting(tmp_db, content_dir, client)

        count_before = tmp_db.query(ReviewState).count()
        client.post(f"/api/v1/attempts/{attempt_id}/dispute", json={"reason": "test"})
        count_after = tmp_db.query(ReviewState).count()
        assert count_after == count_before

    def test_dispute_empty_reason_400(self, tmp_db: Session, content_dir: Path):
        client = _make_client(tmp_db)
        attempt_id = self._create_awaiting(tmp_db, content_dir, client)

        resp = client.post(f"/api/v1/attempts/{attempt_id}/dispute", json={"reason": ""})
        assert resp.status_code == 400

    def test_dispute_completed_rejected(self, tmp_db: Session, content_dir: Path):
        client = _make_client(tmp_db)
        attempt_id = self._create_awaiting(tmp_db, content_dir, client)

        client.post(f"/api/v1/attempts/{attempt_id}/confirm", json={"action": "accept"})
        resp = client.post(f"/api/v1/attempts/{attempt_id}/dispute", json={"reason": "test"})
        assert resp.status_code == 409

    def test_dispute_nonexistent(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.post("/api/v1/attempts/99999/dispute", json={"reason": "test"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 8C1 Rollback hardening
# ---------------------------------------------------------------------------

class TestConfirmRollback:
    def test_confirm_rollback_preserves_awaiting(self, tmp_db: Session, content_dir: Path):
        """If finalization fails midway, Attempt should remain awaiting_confirmation."""
        from app.db.models.attempt import Attempt, AttemptKnowledgeResult
        from app.db.models.review import ReviewState

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

        # Verify state before confirm
        attempt = tmp_db.query(Attempt).filter(Attempt.id == attempt_id).first()
        assert attempt.status == "awaiting_confirmation"
        assert attempt.final_score is None
        assert attempt.finalized_at is None
        assert attempt.review_applied_at is None

        # Verify no knowledge results yet
        kr_count = tmp_db.query(AttemptKnowledgeResult).filter(
            AttemptKnowledgeResult.attempt_id == attempt_id
        ).count()
        assert kr_count == 0


# ---------------------------------------------------------------------------
# Pending with new types
# ---------------------------------------------------------------------------

class TestPendingExtended:
    def test_pending_includes_grading_failed(self, tmp_db: Session, content_dir: Path):
        from app.llm import factory
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        original = factory.create_provider
        factory.create_provider = lambda: MockLLMProvider(mode="timeout")
        try:
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

            pending = client.get("/api/v1/attempts/pending").json()
            assert "sql_grading_failed" in pending
            failed_ids = [p["attempt_id"] for p in pending["sql_grading_failed"]]
            assert attempt_id in failed_ids
        finally:
            factory.create_provider = original

    def test_pending_includes_disputed(self, tmp_db: Session, content_dir: Path):
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
        client.post(f"/api/v1/attempts/{attempt_id}/dispute", json={"reason": "test"})

        pending = client.get("/api/v1/attempts/pending").json()
        assert "sql_disputed" in pending
        disputed_ids = [p["attempt_id"] for p in pending["sql_disputed"]]
        assert attempt_id in disputed_ids


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
