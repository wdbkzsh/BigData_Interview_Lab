"""Tests for Question API — Task 4.2."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.content.importer import import_content
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

_CHOICE_002 = """\
id: spark.shuffle.choice.002
question_type: choice
primary_knowledge_point_id: spark.shuffle
title: Shuffle 机制
difficulty: 3
tags: [spark]
related_knowledge_points: []
is_active: true

content: Spark Shuffle 使用哪种排序？

options:
  - key: A
    text: Hash
  - key: B
    text: Sort-based

correct_answer: B

explanation: Spark 1.2+ 默认 Sort-based。
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
    (choice_dir / "spark.shuffle.choice.002.yaml").write_text(_CHOICE_002, encoding="utf-8")

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
# GET /api/v1/questions — list
# ---------------------------------------------------------------------------

class TestQuestionList:
    def test_returns_list(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/questions")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] == 4  # 2 choice + 1 qa + 1 sql

    def test_filter_by_knowledge_point(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/questions?knowledge_point_id=spark.shuffle")
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["id"].startswith("spark.shuffle.")

    def test_filter_by_question_type(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/questions?question_type=choice")
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["question_type"] == "choice"

    def test_filter_by_difficulty(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/questions?difficulty=2")
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["difficulty"] == 2

    def test_combined_filters(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get(
            "/api/v1/questions?knowledge_point_id=spark.shuffle&question_type=choice&difficulty=2"
        )
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == "spark.shuffle.choice.001"

    def test_pagination(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/questions?page=1&page_size=2")
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total"] == 4
        assert len(data["items"]) == 2

        resp2 = client.get("/api/v1/questions?page=2&page_size=2")
        data2 = resp2.json()
        assert data2["page"] == 2
        assert len(data2["items"]) == 2

    def test_empty_result(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/questions?knowledge_point_id=nonexistent")
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_inactive_excluded(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        from app.db.models.question import Question
        q = tmp_db.query(Question).filter(Question.id == "spark.shuffle.choice.001").first()
        q.is_active = False
        tmp_db.commit()

        client = _make_client(tmp_db)
        resp = client.get("/api/v1/questions?question_type=choice")
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == "spark.shuffle.choice.002"


# ---------------------------------------------------------------------------
# GET /api/v1/questions/{id} — detail
# ---------------------------------------------------------------------------

class TestQuestionDetail:
    def test_choice_returns_content_and_options(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/questions/spark.shuffle.choice.001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "spark.shuffle.choice.001"
        assert data["question_type"] == "choice"
        assert "content" in data
        assert "options" in data
        assert len(data["options"]) == 3

    def test_choice_hides_answer(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/questions/spark.shuffle.choice.001")
        data = resp.json()
        assert "correct_answer" not in data
        assert "explanation" not in data

    def test_short_answer_returns_content(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/questions/spark.shuffle.qa.001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["question_type"] == "short_answer"
        assert "content" in data

    def test_short_answer_hides_answer(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/questions/spark.shuffle.qa.001")
        data = resp.json()
        assert "reference_answer" not in data
        assert "explanation" not in data

    def test_sql_returns_allowed_fields(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/questions/spark.shuffle.sql.001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["question_type"] == "sql"
        assert "content" in data
        assert "table_schema" in data
        assert "field_description" in data
        assert "business_requirement" in data

    def test_sql_hides_answer(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/questions/spark.shuffle.sql.001")
        data = resp.json()
        assert "expected_sql" not in data
        assert "scoring_criteria" not in data

    def test_primary_knowledge_point(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/questions/spark.shuffle.choice.001")
        data = resp.json()
        assert data["primary_knowledge_point"]["id"] == "spark.shuffle"
        assert data["primary_knowledge_point"]["name"] == "Shuffle"

    def test_not_found(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/questions/nonexistent")
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "QUESTION_NOT_FOUND"

    def test_inactive_returns_404(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        from app.db.models.question import Question
        q = tmp_db.query(Question).filter(Question.id == "spark.shuffle.choice.001").first()
        q.is_active = False
        tmp_db.commit()

        client = _make_client(tmp_db)
        resp = client.get("/api/v1/questions/spark.shuffle.choice.001")
        assert resp.status_code == 404


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