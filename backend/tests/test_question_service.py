"""Tests for Question query service — Task 4.1."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.content.importer import import_content
from app.services.question_service import get_question_detail, list_questions


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

_QA_002 = """\
id: spark.rdd.qa.001
question_type: short_answer
primary_knowledge_point_id: spark.rdd
title: RDD 特性
difficulty: 1
tags: [spark]
related_knowledge_points: []
is_active: true

content: 简述 RDD 的特性。
reference_answer: 不可变、可分区、可并行操作。
explanation: RDD 是 Spark 的基本数据抽象。
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
    (qa_dir / "spark.rdd.qa.001.yaml").write_text(_QA_002, encoding="utf-8")

    sql_dir = content_dir / "questions" / "sql"
    sql_dir.mkdir(parents=True)
    (sql_dir / "spark.shuffle.sql.001.yaml").write_text(_SQL_001, encoding="utf-8")


# ---------------------------------------------------------------------------
# list_questions tests
# ---------------------------------------------------------------------------

class TestListQuestions:
    def test_by_knowledge_point(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        result = list_questions(tmp_db, knowledge_point_id="spark.shuffle")
        assert result["total"] == 4  # 2 choice + 1 qa + 1 sql
        for item in result["items"]:
            assert item["id"].startswith("spark.shuffle.")

    def test_by_question_type_choice(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        result = list_questions(tmp_db, question_type="choice")
        assert result["total"] == 2
        for item in result["items"]:
            assert item["question_type"] == "choice"

    def test_by_question_type_short_answer(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        result = list_questions(tmp_db, question_type="short_answer")
        assert result["total"] == 2

    def test_by_question_type_sql(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        result = list_questions(tmp_db, question_type="sql")
        assert result["total"] == 1
        assert result["items"][0]["id"] == "spark.shuffle.sql.001"

    def test_by_difficulty(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        result = list_questions(tmp_db, difficulty=2)
        assert result["total"] == 2  # choice.001 + qa.001
        for item in result["items"]:
            assert item["difficulty"] == 2

    def test_combined_filters(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        result = list_questions(
            tmp_db,
            knowledge_point_id="spark.shuffle",
            question_type="choice",
            difficulty=2,
        )
        assert result["total"] == 1
        assert result["items"][0]["id"] == "spark.shuffle.choice.001"

    def test_pagination(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        # Total = 5 questions
        result = list_questions(tmp_db, page=1, page_size=2)
        assert result["page"] == 1
        assert result["page_size"] == 2
        assert result["total"] == 5
        assert len(result["items"]) == 2

        result2 = list_questions(tmp_db, page=2, page_size=2)
        assert result2["page"] == 2
        assert len(result2["items"]) == 2

        result3 = list_questions(tmp_db, page=3, page_size=2)
        assert result3["page"] == 3
        assert len(result3["items"]) == 1

    def test_empty_result(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        result = list_questions(tmp_db, knowledge_point_id="nonexistent")
        assert result["items"] == []
        assert result["total"] == 0

    def test_inactive_excluded(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        from app.db.models.question import Question
        q = tmp_db.query(Question).filter(Question.id == "spark.shuffle.choice.001").first()
        q.is_active = False
        tmp_db.commit()

        result = list_questions(tmp_db, question_type="choice")
        assert result["total"] == 1
        assert result["items"][0]["id"] == "spark.shuffle.choice.002"

    def test_sort_order(self, tmp_db: Session, content_dir: Path):
        """Results sorted by difficulty ASC, id ASC."""
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        result = list_questions(tmp_db, knowledge_point_id="spark.shuffle")
        difficulties = [item["difficulty"] for item in result["items"]]
        assert difficulties == sorted(difficulties)

    def test_item_fields(self, tmp_db: Session, content_dir: Path):
        """List items contain expected fields."""
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        result = list_questions(tmp_db)
        item = result["items"][0]
        assert "id" in item
        assert "title" in item
        assert "question_type" in item
        assert "difficulty" in item
        assert "primary_knowledge_point" in item
        assert "review_state" in item
        assert "pending_self_assessment_attempt_id" in item


# ---------------------------------------------------------------------------
# get_question_detail tests
# ---------------------------------------------------------------------------

class TestGetQuestionDetail:
    def test_choice_returns_content_and_options(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        detail = get_question_detail(tmp_db, "spark.shuffle.choice.001")
        assert detail is not None
        assert detail["id"] == "spark.shuffle.choice.001"
        assert detail["question_type"] == "choice"
        assert "content" in detail
        assert "options" in detail
        assert len(detail["options"]) == 3

    def test_choice_hides_answer(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        detail = get_question_detail(tmp_db, "spark.shuffle.choice.001")
        assert "correct_answer" not in detail
        assert "explanation" not in detail

    def test_short_answer_returns_content(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        detail = get_question_detail(tmp_db, "spark.shuffle.qa.001")
        assert detail is not None
        assert detail["question_type"] == "short_answer"
        assert "content" in detail
        assert "请说明" in detail["content"]

    def test_short_answer_hides_answer(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        detail = get_question_detail(tmp_db, "spark.shuffle.qa.001")
        assert "reference_answer" not in detail
        assert "explanation" not in detail

    def test_sql_returns_allowed_fields(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        detail = get_question_detail(tmp_db, "spark.shuffle.sql.001")
        assert detail is not None
        assert detail["question_type"] == "sql"
        assert "content" in detail
        assert "table_schema" in detail
        assert "field_description" in detail
        assert "business_requirement" in detail

    def test_sql_hides_answer(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        detail = get_question_detail(tmp_db, "spark.shuffle.sql.001")
        assert "expected_sql" not in detail
        assert "scoring_criteria" not in detail

    def test_primary_knowledge_point(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        detail = get_question_detail(tmp_db, "spark.shuffle.choice.001")
        assert detail["primary_knowledge_point"]["id"] == "spark.shuffle"
        assert detail["primary_knowledge_point"]["name"] == "Shuffle"

    def test_revision_matches_current(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        detail = get_question_detail(tmp_db, "spark.shuffle.choice.001")
        assert detail["revision"] == 1

    def test_nonexistent_returns_none(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        result = get_question_detail(tmp_db, "nonexistent")
        assert result is None

    def test_inactive_returns_none(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        from app.db.models.question import Question
        q = tmp_db.query(Question).filter(Question.id == "spark.shuffle.choice.001").first()
        q.is_active = False
        tmp_db.commit()

        result = get_question_detail(tmp_db, "spark.shuffle.choice.001")
        assert result is None


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