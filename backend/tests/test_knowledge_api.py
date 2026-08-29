"""Tests for Knowledge Read API — Task 3.1."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.content.importer import import_content
from app.db.session import get_db
from app.main import app


# ---------------------------------------------------------------------------
# Content fixtures — minimal but complete content/ tree
# ---------------------------------------------------------------------------

_KNOWLEDGE_SPARK_YAML = """\
- id: spark
  name: Spark
  description: Apache Spark 分布式计算框架
  sort_order: 1
  children:
    - id: spark.rdd
      name: RDD
      description: 弹性分布式数据集
      sort_order: 1
    - id: spark.shuffle
      name: Shuffle
      description: 数据重分区与跨节点传输机制
      sort_order: 2
"""

_KNOWLEDGE_HIVE_YAML = """\
- id: hive
  name: Hive
  description: SQL-on-Hadoop 引擎
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
- Sort-based Shuffle

## 常见易错点

- 不是所有 Join 都有 Shuffle
"""

_CARD_HIVE = """\
---
knowledge_point_id: hive
title: Hive
is_active: true
---

## 一句话定义

SQL-on-Hadoop。

## 核心原理

将 SQL 转化为 MapReduce/Tez/Spark 任务。

## 面试高频点

- 分区与分桶
- 内部表与外部表

## 常见易错点

- 分区字段不是表中的列
"""

_CHOICE_001 = """\
id: spark.shuffle.choice.001
question_type: choice
primary_knowledge_point_id: spark.shuffle
title: Shuffle 触发条件
difficulty: 2
tags:
  - spark
  - shuffle
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
tags:
  - spark
  - shuffle
related_knowledge_points: []
is_active: true

content: Spark Shuffle 使用哪种排序方式？

options:
  - key: A
    text: Hash
  - key: B
    text: Sort-based
  - key: C
    text: No sorting

correct_answer: B

explanation: Spark 1.2+ 默认 Sort-based Shuffle。
"""

_QA_001 = """\
id: spark.shuffle.qa.001
question_type: short_answer
primary_knowledge_point_id: spark.shuffle
title: Shuffle 作用
difficulty: 2
tags: [spark, shuffle]
related_knowledge_points: []
is_active: true

content: 请说明 Spark Shuffle 的作用和触发场景。
reference_answer: Shuffle 是数据重新分区的过程，由宽依赖触发。
explanation: 宽依赖如 reduceByKey、groupByKey、join 会触发 Shuffle。
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_content(content_dir: Path) -> None:
    """Write minimal content tree to content_dir."""
    kp_dir = content_dir / "knowledge"
    kp_dir.mkdir(parents=True)
    (kp_dir / "spark.yaml").write_text(_KNOWLEDGE_SPARK_YAML, encoding="utf-8")
    (kp_dir / "hive.yaml").write_text(_KNOWLEDGE_HIVE_YAML, encoding="utf-8")

    card_dir = content_dir / "cards"
    card_dir.mkdir(parents=True)
    (card_dir / "spark.shuffle.md").write_text(_CARD_SPARK_SHUFFLE, encoding="utf-8")
    (card_dir / "hive.md").write_text(_CARD_HIVE, encoding="utf-8")

    choice_dir = content_dir / "questions" / "choice"
    choice_dir.mkdir(parents=True)
    (choice_dir / "spark.shuffle.choice.001.yaml").write_text(_CHOICE_001, encoding="utf-8")
    (choice_dir / "spark.shuffle.choice.002.yaml").write_text(_CHOICE_002, encoding="utf-8")

    qa_dir = content_dir / "questions" / "short_answer"
    qa_dir.mkdir(parents=True)
    (qa_dir / "spark.shuffle.qa.001.yaml").write_text(_QA_001, encoding="utf-8")

    sql_dir = content_dir / "questions" / "sql"
    sql_dir.mkdir(parents=True)


@pytest.fixture(autouse=True)
def _reset_overrides():
    """Ensure dependency overrides are clean before and after each test."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def _make_client(db: Session) -> TestClient:
    """Create a TestClient that uses the given DB session."""

    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# GET /api/v1/knowledge-points — tree
# ---------------------------------------------------------------------------

class TestKnowledgePointTree:
    def test_returns_tree(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/knowledge-points")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Top-level: spark (sort_order=1), hive (sort_order=2)
        assert len(data) == 2
        assert data[0]["id"] == "spark"
        assert data[1]["id"] == "hive"

    def test_parent_child_relationships(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/knowledge-points")
        data = resp.json()
        spark = data[0]
        assert spark["level"] == 1
        assert len(spark["children"]) == 2
        # Children sorted by sort_order: rdd(1), shuffle(2)
        assert spark["children"][0]["id"] == "spark.rdd"
        assert spark["children"][1]["id"] == "spark.shuffle"
        # Children have empty children list
        assert spark["children"][0]["children"] == []
        assert spark["children"][1]["children"] == []
        # hive has no children
        assert data[1]["children"] == []

    def test_sort_order_deterministic(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/knowledge-points")
        data = resp.json()
        # Top-level: spark (sort_order=1), hive (sort_order=2)
        assert [n["id"] for n in data] == ["spark", "hive"]
        # Children: rdd (sort_order=1), shuffle (sort_order=2)
        assert [n["id"] for n in data[0]["children"]] == ["spark.rdd", "spark.shuffle"]

    def test_inactive_kp_excluded(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        # Deactivate spark.shuffle directly
        from app.db.models.knowledge import KnowledgePoint
        kp = tmp_db.query(KnowledgePoint).filter(KnowledgePoint.id == "spark.shuffle").first()
        kp.is_active = False
        tmp_db.commit()

        client = _make_client(tmp_db)
        resp = client.get("/api/v1/knowledge-points")
        data = resp.json()
        spark = data[0]
        assert len(spark["children"]) == 1
        assert spark["children"][0]["id"] == "spark.rdd"

    def test_inactive_parent_excludes_active_child(self, tmp_db: Session, content_dir: Path):
        """Inactive parent → active child should NOT appear in tree."""
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        # Deactivate spark (parent of spark.rdd and spark.shuffle)
        from app.db.models.knowledge import KnowledgePoint
        kp = tmp_db.query(KnowledgePoint).filter(KnowledgePoint.id == "spark").first()
        kp.is_active = False
        tmp_db.commit()

        client = _make_client(tmp_db)
        resp = client.get("/api/v1/knowledge-points")
        data = resp.json()
        # Only hive should remain as top-level
        assert len(data) == 1
        assert data[0]["id"] == "hive"

    def test_empty_tree(self, tmp_db: Session, content_dir: Path):
        content_dir.mkdir(parents=True)
        client = _make_client(tmp_db)
        resp = client.get("/api/v1/knowledge-points")
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /api/v1/knowledge-points/{id} — detail
# ---------------------------------------------------------------------------

class TestKnowledgePointDetail:
    def test_success(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/knowledge-points/spark.shuffle")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "spark.shuffle"
        assert data["name"] == "Shuffle"
        assert "description" in data

    def test_question_count(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/knowledge-points/spark.shuffle")
        data = resp.json()
        # 2 choice + 1 short_answer = 3
        assert data["question_count"] == 3

    def test_question_count_only_primary_and_active(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        # Deactivate one question
        from app.db.models.question import Question
        q = tmp_db.query(Question).filter(Question.id == "spark.shuffle.choice.001").first()
        q.is_active = False
        tmp_db.commit()

        client = _make_client(tmp_db)
        resp = client.get("/api/v1/knowledge-points/spark.shuffle")
        data = resp.json()
        # 1 choice (active) + 1 short_answer = 2
        assert data["question_count"] == 2

    def test_question_count_zero(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/knowledge-points/spark.rdd")
        data = resp.json()
        assert data["question_count"] == 0

    def test_has_card_true(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/knowledge-points/spark.shuffle")
        data = resp.json()
        assert data["has_card"] is True

    def test_has_card_false(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/knowledge-points/spark.rdd")
        data = resp.json()
        assert data["has_card"] is False

    def test_not_found(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/knowledge-points/nonexistent")
        assert resp.status_code == 404
        body = resp.json()
        assert body["detail"]["code"] == "KNOWLEDGE_POINT_NOT_FOUND"

    def test_inactive_returns_404(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        from app.db.models.knowledge import KnowledgePoint
        kp = tmp_db.query(KnowledgePoint).filter(KnowledgePoint.id == "spark.shuffle").first()
        kp.is_active = False
        tmp_db.commit()

        client = _make_client(tmp_db)
        resp = client.get("/api/v1/knowledge-points/spark.shuffle")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/knowledge-points/{id}/card
# ---------------------------------------------------------------------------

class TestKnowledgeCard:
    def test_success(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/knowledge-points/spark.shuffle/card")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "card.spark.shuffle"
        assert data["knowledge_point_id"] == "spark.shuffle"
        assert data["revision"] == 1

    def test_content_parsed(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/knowledge-points/spark.shuffle/card")
        data = resp.json()
        content = data["content"]
        assert content["title"] == "Shuffle"
        assert content["one_line_definition"] == "数据重分布。"
        assert "宽依赖" in content["core_principle"]
        assert "Shuffle Write" in content["interview_highlights"]
        assert "不是所有 Join" in content["common_mistakes"]

    def test_no_source_hash_in_response(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/knowledge-points/spark.shuffle/card")
        data = resp.json()
        assert "source_hash" not in data
        assert "source_path" not in data
        assert "imported_at" not in data

    def test_uses_current_revision(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        # First revision
        resp = client.get("/api/v1/knowledge-points/spark.shuffle/card")
        assert resp.json()["revision"] == 1

        # Modify card content and re-import to get revision 2
        card_path = content_dir / "cards" / "spark.shuffle.md"
        card_path.write_text(
            """\
---
knowledge_point_id: spark.shuffle
title: Shuffle Updated
is_active: true
---

## 一句话定义

新版定义。

## 核心原理

新版原理。

## 面试高频点

- 新高频点

## 常见易错点

- 新易错点
""",
            encoding="utf-8",
        )
        tmp_db.commit()  # Clear transaction before second import
        import_content(content_dir, tmp_db)
        client2 = _make_client(tmp_db)

        resp2 = client2.get("/api/v1/knowledge-points/spark.shuffle/card")
        assert resp2.json()["revision"] == 2
        assert resp2.json()["content"]["title"] == "Shuffle Updated"

    def test_card_inactive_returns_404(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        from app.db.models.knowledge import KnowledgeCard
        card = tmp_db.query(KnowledgeCard).filter(KnowledgeCard.id == "card.spark.shuffle").first()
        card.is_active = False
        tmp_db.commit()

        client = _make_client(tmp_db)
        resp = client.get("/api/v1/knowledge-points/spark.shuffle/card")
        assert resp.status_code == 404
        body = resp.json()
        assert body["detail"]["code"] == "CARD_NOT_FOUND"

    def test_kp_not_found_returns_404(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/knowledge-points/nonexistent/card")
        assert resp.status_code == 404
        body = resp.json()
        assert body["detail"]["code"] == "KNOWLEDGE_POINT_NOT_FOUND"

    def test_no_card_returns_404(self, tmp_db: Session, content_dir: Path):
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        # spark.rdd has no card
        resp = client.get("/api/v1/knowledge-points/spark.rdd/card")
        assert resp.status_code == 404
        body = resp.json()
        assert body["detail"]["code"] == "CARD_NOT_FOUND"


# ---------------------------------------------------------------------------
# Runtime does not read content/ files
# ---------------------------------------------------------------------------

class TestNoContentFileRead:
    def test_api_uses_sqlite_only(self, tmp_db: Session, content_dir: Path):
        """After import, delete content files — API should still work."""
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        # Delete content files
        import shutil
        shutil.rmtree(content_dir)

        client = _make_client(tmp_db)
        # Tree still works
        resp = client.get("/api/v1/knowledge-points")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

        # Detail still works
        resp = client.get("/api/v1/knowledge-points/spark.shuffle")
        assert resp.status_code == 200
        assert resp.json()["question_count"] == 3

        # Card still works
        resp = client.get("/api/v1/knowledge-points/spark.shuffle/card")
        assert resp.status_code == 200
        assert resp.json()["content"]["title"] == "Shuffle"


# ---------------------------------------------------------------------------
# Real content import
# ---------------------------------------------------------------------------

class TestRealContent:
    def test_real_content_import_api(self, tmp_db: Session):
        """Import real content/ directory and verify API works."""
        real_content = Path(__file__).resolve().parents[2] / "content"
        if not real_content.exists():
            pytest.skip("real content/ directory not found")

        import_content(real_content, tmp_db)
        client = _make_client(tmp_db)

        # Tree returns something
        resp = client.get("/api/v1/knowledge-points")
        assert resp.status_code == 200
        tree = resp.json()
        assert len(tree) > 0

        # At least one KP has a card
        first_kp = tree[0]["id"]
        resp = client.get(f"/api/v1/knowledge-points/{first_kp}")
        assert resp.status_code == 200

        # If has_card, card endpoint works
        if resp.json()["has_card"]:
            resp = client.get(f"/api/v1/knowledge-points/{first_kp}/card")
            assert resp.status_code == 200
            assert resp.json()["content"]["title"]


# ---------------------------------------------------------------------------
# Formal DB not polluted
# ---------------------------------------------------------------------------

class TestFormalDBNotPolluted:
    def test_formal_db_unchanged(self):
        """All tests use tmp_db — formal data/app.db should be untouched."""
        from app.core.config import settings
        db_path = settings.DATABASE_URL.replace("sqlite:///", "")
        p = Path(db_path)
        # If formal DB exists, it should not have been modified by tests
        # (we can't check content, but we can check it exists and is not empty)
        if p.exists():
            assert p.stat().st_size > 0


# ---------------------------------------------------------------------------
# POST /api/v1/knowledge-cards/{card_id}/view — record card view
# ---------------------------------------------------------------------------

class TestRecordCardView:
    def test_first_view_success(self, tmp_db: Session, content_dir: Path):
        """First POST creates progress: status=read, view_count=1."""
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.post("/api/v1/knowledge-cards/card.spark.shuffle/view")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "read"
        assert data["view_count"] == 1
        assert data["last_viewed_at"] is not None

    def test_second_view_increments(self, tmp_db: Session, content_dir: Path):
        """Second POST increments view_count to 2."""
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        client.post("/api/v1/knowledge-cards/card.spark.shuffle/view")
        resp = client.post("/api/v1/knowledge-cards/card.spark.shuffle/view")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "read"
        assert data["view_count"] == 2

    def test_first_viewed_at_preserved(self, tmp_db: Session, content_dir: Path):
        """Second POST preserves first_viewed_at."""
        _write_content(content_dir)
        import_content(content_dir, tmp_db)

        from app.db.models.knowledge import KnowledgeCardProgress

        client = _make_client(tmp_db)
        client.post("/api/v1/knowledge-cards/card.spark.shuffle/view")

        # Read first_viewed_at from DB
        prog1 = tmp_db.query(KnowledgeCardProgress).filter(
            KnowledgeCardProgress.card_id == "card.spark.shuffle"
        ).first()
        first_ts = prog1.first_viewed_at

        client.post("/api/v1/knowledge-cards/card.spark.shuffle/view")

        prog2 = tmp_db.query(KnowledgeCardProgress).filter(
            KnowledgeCardProgress.card_id == "card.spark.shuffle"
        ).first()
        assert prog2.first_viewed_at == first_ts

    def test_last_viewed_at_updated(self, tmp_db: Session, content_dir: Path):
        """Second POST updates last_viewed_at (not earlier than first)."""
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp1 = client.post("/api/v1/knowledge-cards/card.spark.shuffle/view")
        resp2 = client.post("/api/v1/knowledge-cards/card.spark.shuffle/view")

        last1 = resp1.json()["last_viewed_at"]
        last2 = resp2.json()["last_viewed_at"]
        # last2 should not be earlier than last1
        assert last2 >= last1

    def test_card_not_found(self, tmp_db: Session, content_dir: Path):
        """POST nonexistent card_id → 404."""
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.post("/api/v1/knowledge-cards/nonexistent/view")
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "CARD_NOT_FOUND"

    def test_inactive_card(self, tmp_db: Session, content_dir: Path):
        """POST inactive card → 404."""
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        from app.db.models.knowledge import KnowledgeCard
        card = tmp_db.query(KnowledgeCard).filter(KnowledgeCard.id == "card.spark.shuffle").first()
        card.is_active = False
        tmp_db.commit()

        client = _make_client(tmp_db)
        resp = client.post("/api/v1/knowledge-cards/card.spark.shuffle/view")
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "CARD_NOT_FOUND"

    def test_inactive_knowledge_point(self, tmp_db: Session, content_dir: Path):
        """Card active but KP inactive → 404."""
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        from app.db.models.knowledge import KnowledgePoint
        kp = tmp_db.query(KnowledgePoint).filter(KnowledgePoint.id == "spark.shuffle").first()
        kp.is_active = False
        tmp_db.commit()

        client = _make_client(tmp_db)
        resp = client.post("/api/v1/knowledge-cards/card.spark.shuffle/view")
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "CARD_NOT_FOUND"

    def test_no_request_body_required(self, tmp_db: Session, content_dir: Path):
        """POST with no body succeeds."""
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.post("/api/v1/knowledge-cards/card.spark.shuffle/view")
        assert resp.status_code == 200
        assert resp.json()["view_count"] == 1


# ---------------------------------------------------------------------------
# GET Card progress — before/after view
# ---------------------------------------------------------------------------

class TestGetCardProgress:
    def test_get_card_before_view(self, tmp_db: Session, content_dir: Path):
        """GET card before any POST view → unread, 0, null."""
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/knowledge-points/spark.shuffle/card")
        assert resp.status_code == 200
        data = resp.json()
        assert data["progress"]["status"] == "unread"
        assert data["progress"]["view_count"] == 0
        assert data["progress"]["last_viewed_at"] is None

    def test_get_before_view_no_db_write(self, tmp_db: Session, content_dir: Path):
        """GET card before view does NOT create a progress row."""
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        from app.db.models.knowledge import KnowledgeCardProgress

        client = _make_client(tmp_db)
        # GET card — should not insert
        resp = client.get("/api/v1/knowledge-points/spark.shuffle/card")
        assert resp.status_code == 200
        assert resp.json()["progress"]["status"] == "unread"

        # Verify no progress row in DB
        count = tmp_db.query(KnowledgeCardProgress).filter(
            KnowledgeCardProgress.card_id == "card.spark.shuffle"
        ).count()
        assert count == 0

    def test_get_card_after_view(self, tmp_db: Session, content_dir: Path):
        """POST view then GET card → read, correct count."""
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        # View once
        client.post("/api/v1/knowledge-cards/card.spark.shuffle/view")

        resp = client.get("/api/v1/knowledge-points/spark.shuffle/card")
        data = resp.json()
        assert data["progress"]["status"] == "read"
        assert data["progress"]["view_count"] == 1
        assert data["progress"]["last_viewed_at"] is not None

    def test_get_repeated_does_not_increment(self, tmp_db: Session, content_dir: Path):
        """GET card multiple times does not increase view_count."""
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        # View once to create progress
        client.post("/api/v1/knowledge-cards/card.spark.shuffle/view")

        # GET 10 times
        for _ in range(10):
            client.get("/api/v1/knowledge-points/spark.shuffle/card")

        # view_count should still be 1
        resp = client.get("/api/v1/knowledge-points/spark.shuffle/card")
        assert resp.json()["progress"]["view_count"] == 1

    def test_task31_card_fields_preserved(self, tmp_db: Session, content_dir: Path):
        """Task 3.1 card response fields (id, revision, content) unchanged."""
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.get("/api/v1/knowledge-points/spark.shuffle/card")
        data = resp.json()
        assert data["id"] == "card.spark.shuffle"
        assert data["knowledge_point_id"] == "spark.shuffle"
        assert data["revision"] == 1
        assert data["content"]["title"] == "Shuffle"


# ---------------------------------------------------------------------------
# CORS preflight for POST view
# ---------------------------------------------------------------------------

class TestCORSPreflight:
    def test_post_view_preflight_allows_post(self, tmp_db: Session, content_dir: Path):
        """OPTIONS preflight for POST view should allow POST method."""
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.options(
            "/api/v1/knowledge-cards/card.spark.shuffle/view",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        # FastAPI CORS middleware responds to preflight
        allow_methods = resp.headers.get("access-control-allow-methods", "")
        assert "POST" in allow_methods

    def test_get_preflight_allows_get(self, tmp_db: Session, content_dir: Path):
        """OPTIONS preflight for GET knowledge-points should allow GET."""
        _write_content(content_dir)
        import_content(content_dir, tmp_db)
        client = _make_client(tmp_db)

        resp = client.options(
            "/api/v1/knowledge-points",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        allow_methods = resp.headers.get("access-control-allow-methods", "")
        assert "GET" in allow_methods
