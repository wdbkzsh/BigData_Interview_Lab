"""Tests for content importer — Task 2.8 + 2.9."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.content.importer import (
    ContentImportError,
    ContentImportResult,
    ContentImportValidationError,
    StableBindingError,
    import_content,
)
from app.db.models.knowledge import KnowledgeCard, KnowledgeCardVersion, KnowledgePoint
from app.db.models.question import (
    Question,
    QuestionRelatedKnowledgePoint,
    QuestionVersion,
)


# ---------------------------------------------------------------------------
# Test content fixtures — minimal but complete content/ tree
# ---------------------------------------------------------------------------

_KNOWLEDGE_SPARK = """\
- id: spark
  name: Spark
  sort_order: 1
  children:
    - id: spark.shuffle
      name: Shuffle
      sort_order: 1
"""

_CARD_SPARK_SHUFFLE = """\
---
knowledge_point_id: spark.shuffle
title: Shuffle
is_active: true
---

## 一句话定义

Shuffle 是数据重分布。

## 核心原理

宽依赖导致 Shuffle。

## 面试高频点

- Shuffle Write
- Shuffle Read

## 常见易错点

- 误以为所有 Join 都有 Shuffle
"""

_CHOICE_SPARK_SHUFFLE = """\
id: spark.shuffle.choice.001
question_type: choice
primary_knowledge_point_id: spark.shuffle
title: "Shuffle 触发条件"
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
    text: filter
  - key: C
    text: groupByKey
  - key: D
    text: union

correct_answer: C

explanation: groupByKey 需要按 key 重分布数据。
"""

_QA_SPARK_SHUFFLE = """\
id: spark.shuffle.qa.001
question_type: short_answer
primary_knowledge_point_id: spark.shuffle
title: "Shuffle 本质"
difficulty: 3
tags:
  - spark
related_knowledge_points: []
is_active: true

content: 请简述 Spark Shuffle 的本质。

reference_answer: |
  Shuffle 是数据重分布过程。
  涉及磁盘 IO 和网络传输。

explanation: |
  Shuffle 是性能瓶颈。
"""

_SQL_SPARK_SHUFFLE = """\
id: spark.shuffle.sql.001
question_type: sql
primary_knowledge_point_id: spark.shuffle
title: "各品类 Top3 门店"
difficulty: 4
tags:
  - sql
related_knowledge_points: []
is_active: true

content: |
  查询每个品类销售额 Top3 的门店。

table_schema: |
  CREATE TABLE orders (store_id INT, category STRING, amount DOUBLE);

field_description: |
  - store_id: 门店 ID
  - category: 品类
  - amount: 销售额

business_requirement: |
  1. 按品类分组
  2. 按销售额降序取前3

expected_sql: |
  SELECT * FROM (
    SELECT *, RANK() OVER (PARTITION BY category ORDER BY amount DESC) AS rk
    FROM orders
  ) t WHERE rk <= 3;

scoring_criteria:
  - id: c1
    description: 正确使用窗口函数
    points: 6
  - id: c2
    description: 正确过滤前3
    points: 4
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _setup_full_content(content_dir: Path) -> None:
    """Write a complete valid content/ tree."""
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    _write_file(content_dir / "cards" / "spark.shuffle.md", _CARD_SPARK_SHUFFLE)
    _write_file(
        content_dir / "questions" / "choice" / "spark.shuffle.choice.001.yaml",
        _CHOICE_SPARK_SHUFFLE,
    )
    _write_file(
        content_dir / "questions" / "short_answer" / "spark.shuffle.qa.001.yaml",
        _QA_SPARK_SHUFFLE,
    )
    _write_file(
        content_dir / "questions" / "sql" / "spark.shuffle.sql.001.yaml",
        _SQL_SPARK_SHUFFLE,
    )


# ---------------------------------------------------------------------------
# 1. Validator failure → zero writes
# ---------------------------------------------------------------------------


def test_validation_failure_no_write(tmp_db: Session, content_dir: Path) -> None:
    """If validator fails, no database rows should be written."""
    _write_file(content_dir / "knowledge" / "bad.yaml", "id: bad\n")

    with pytest.raises(ContentImportValidationError):
        import_content(content_dir, tmp_db)

    assert tmp_db.query(KnowledgePoint).count() == 0
    assert tmp_db.query(Question).count() == 0


# ---------------------------------------------------------------------------
# 2. First import Knowledge Point
# ---------------------------------------------------------------------------


def test_first_import_knowledge_point(tmp_db: Session, content_dir: Path) -> None:
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)

    result = import_content(content_dir, tmp_db)

    assert result.knowledge_points_inserted == 2  # spark + spark.shuffle
    kps = {kp.id: kp for kp in tmp_db.query(KnowledgePoint).all()}
    assert "spark" in kps
    assert "spark.shuffle" in kps
    assert kps["spark"].parent_id is None
    assert kps["spark"].level == 1
    assert kps["spark.shuffle"].parent_id == "spark"
    assert kps["spark.shuffle"].level == 2


# ---------------------------------------------------------------------------
# 3. First import Card + CardVersion revision=1
# ---------------------------------------------------------------------------


def test_first_import_card_and_version(tmp_db: Session, content_dir: Path) -> None:
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    _write_file(content_dir / "cards" / "spark.shuffle.md", _CARD_SPARK_SHUFFLE)

    result = import_content(content_dir, tmp_db)

    assert result.cards_inserted == 1
    assert result.card_versions_created == 1

    card = tmp_db.get(KnowledgeCard, "card.spark.shuffle")
    assert card is not None
    assert card.current_revision == 1
    assert card.is_active is True
    assert card.knowledge_point_id == "spark.shuffle"

    ver = tmp_db.get(KnowledgeCardVersion, ("card.spark.shuffle", 1))
    assert ver is not None
    assert ver.source_path == "content/cards/spark.shuffle.md"
    assert ver.source_hash is not None


# ---------------------------------------------------------------------------
# 4. Card content_json structure
# ---------------------------------------------------------------------------


def test_card_content_json_structure(tmp_db: Session, content_dir: Path) -> None:
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    _write_file(content_dir / "cards" / "spark.shuffle.md", _CARD_SPARK_SHUFFLE)

    import_content(content_dir, tmp_db)

    ver = tmp_db.get(KnowledgeCardVersion, ("card.spark.shuffle", 1))
    payload = json.loads(ver.content_json)

    assert payload["title"] == "Shuffle"
    assert "Shuffle" in payload["one_line_definition"]
    assert "宽依赖" in payload["core_principle"]
    assert "Shuffle Write" in payload["interview_highlights"]
    assert "Join" in payload["common_mistakes"]


# ---------------------------------------------------------------------------
# 5-7. First import Choice / Short Answer / SQL
# ---------------------------------------------------------------------------


def test_first_import_choice_question(tmp_db: Session, content_dir: Path) -> None:
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    _write_file(
        content_dir / "questions" / "choice" / "spark.shuffle.choice.001.yaml",
        _CHOICE_SPARK_SHUFFLE,
    )

    result = import_content(content_dir, tmp_db)

    assert result.questions_inserted == 1
    assert result.question_versions_created == 1

    q = tmp_db.get(Question, "spark.shuffle.choice.001")
    assert q is not None
    assert q.question_type == "choice"
    assert q.current_revision == 1
    assert q.difficulty == 2

    ver = tmp_db.get(QuestionVersion, ("spark.shuffle.choice.001", 1))
    assert ver is not None
    payload = json.loads(ver.payload_json)
    assert "Shuffle" in payload["content"]
    assert payload["correct_answer"] == "C"


def test_first_import_short_answer(tmp_db: Session, content_dir: Path) -> None:
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    _write_file(
        content_dir / "questions" / "short_answer" / "spark.shuffle.qa.001.yaml",
        _QA_SPARK_SHUFFLE,
    )

    result = import_content(content_dir, tmp_db)

    assert result.questions_inserted == 1
    q = tmp_db.get(Question, "spark.shuffle.qa.001")
    assert q.question_type == "short_answer"

    ver = tmp_db.get(QuestionVersion, ("spark.shuffle.qa.001", 1))
    payload = json.loads(ver.payload_json)
    assert "reference_answer" in payload
    assert "重分布" in payload["reference_answer"]


def test_first_import_sql_question(tmp_db: Session, content_dir: Path) -> None:
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    _write_file(
        content_dir / "questions" / "sql" / "spark.shuffle.sql.001.yaml",
        _SQL_SPARK_SHUFFLE,
    )

    result = import_content(content_dir, tmp_db)

    assert result.questions_inserted == 1
    q = tmp_db.get(Question, "spark.shuffle.sql.001")
    assert q.question_type == "sql"


# ---------------------------------------------------------------------------
# 8. SQL max_score in payload
# ---------------------------------------------------------------------------


def test_sql_max_score_in_payload(tmp_db: Session, content_dir: Path) -> None:
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    _write_file(
        content_dir / "questions" / "sql" / "spark.shuffle.sql.001.yaml",
        _SQL_SPARK_SHUFFLE,
    )

    import_content(content_dir, tmp_db)

    ver = tmp_db.get(QuestionVersion, ("spark.shuffle.sql.001", 1))
    payload = json.loads(ver.payload_json)
    assert payload["max_score"] == 10  # 6 + 4


# ---------------------------------------------------------------------------
# 9. Idempotent second import
# ---------------------------------------------------------------------------


def test_idempotent_second_import(tmp_db: Session, content_dir: Path) -> None:
    _setup_full_content(content_dir)

    import_content(content_dir, tmp_db)
    tmp_db.commit()

    r2 = import_content(content_dir, tmp_db)

    assert r2.knowledge_points_inserted == 0
    assert r2.knowledge_points_updated == 0
    assert r2.cards_inserted == 0
    assert r2.card_versions_created == 0
    assert r2.questions_inserted == 0
    assert r2.question_versions_created == 0
    assert r2.relations_created == 0
    assert r2.relations_deleted == 0
    assert r2.unchanged > 0

    card = tmp_db.get(KnowledgeCard, "card.spark.shuffle")
    assert card.current_revision == 1

    q = tmp_db.get(Question, "spark.shuffle.choice.001")
    assert q.current_revision == 1


# ---------------------------------------------------------------------------
# 10. KP name update
# ---------------------------------------------------------------------------


def test_kp_name_update_no_id_change(tmp_db: Session, content_dir: Path) -> None:
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    import_content(content_dir, tmp_db)
    tmp_db.commit()

    new_yaml = _KNOWLEDGE_SPARK.replace("name: Shuffle", "name: Shuffle 机制")
    _write_file(content_dir / "knowledge" / "spark.yaml", new_yaml)

    result = import_content(content_dir, tmp_db)

    assert result.knowledge_points_updated >= 1
    kp = tmp_db.get(KnowledgePoint, "spark.shuffle")
    assert kp.name == "Shuffle 机制"
    assert kp.id == "spark.shuffle"


# ---------------------------------------------------------------------------
# 11. KP parent/level change → StableBindingError
# Tested by modifying DB directly, then re-importing same YAML
# ---------------------------------------------------------------------------


def test_kp_parent_level_change_rejected(tmp_db: Session, content_dir: Path) -> None:
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    import_content(content_dir, tmp_db)
    tmp_db.commit()

    # Create a valid "other_parent" KP so FK constraint passes
    tmp_db.add(KnowledgePoint(id="other_parent", name="Other", level=1, sort_order=99))
    tmp_db.commit()

    # Directly modify DB to create a binding mismatch
    kp = tmp_db.get(KnowledgePoint, "spark.shuffle")
    kp.parent_id = "other_parent"
    kp.level = 2  # level stays 2, but parent changed
    tmp_db.commit()

    # Re-import same YAML — importer should detect parent_id mismatch
    with pytest.raises(StableBindingError) as exc_info:
        import_content(content_dir, tmp_db)

    assert "parent_id" in str(exc_info.value)
    assert "spark.shuffle" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 12. Disappeared content → auto deactivate
# ---------------------------------------------------------------------------


def test_disappeared_kp_auto_deactivated(tmp_db: Session, content_dir: Path) -> None:
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    import_content(content_dir, tmp_db)
    tmp_db.commit()

    (content_dir / "knowledge" / "spark.yaml").unlink()

    result = import_content(content_dir, tmp_db)
    tmp_db.commit()

    assert result.knowledge_points_deactivated >= 1
    kp = tmp_db.get(KnowledgePoint, "spark")
    assert kp.is_active is False


def test_disappeared_question_auto_deactivated(tmp_db: Session, content_dir: Path) -> None:
    _setup_full_content(content_dir)
    import_content(content_dir, tmp_db)
    tmp_db.commit()

    (content_dir / "questions" / "choice" / "spark.shuffle.choice.001.yaml").unlink()

    result = import_content(content_dir, tmp_db)
    tmp_db.commit()

    assert result.questions_deactivated >= 1
    q = tmp_db.get(Question, "spark.shuffle.choice.001")
    assert q.is_active is False


# ---------------------------------------------------------------------------
# 13. Card title/body change → revision + 1
# ---------------------------------------------------------------------------


def test_card_content_change_new_revision(tmp_db: Session, content_dir: Path) -> None:
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    _write_file(content_dir / "cards" / "spark.shuffle.md", _CARD_SPARK_SHUFFLE)
    import_content(content_dir, tmp_db)
    tmp_db.commit()

    new_card = _CARD_SPARK_SHUFFLE.replace(
        "Shuffle 是数据重分布。",
        "Shuffle 是跨 Stage 的数据重分布过程。",
    )
    _write_file(content_dir / "cards" / "spark.shuffle.md", new_card)

    result = import_content(content_dir, tmp_db)
    tmp_db.commit()

    assert result.card_versions_created == 1
    card = tmp_db.get(KnowledgeCard, "card.spark.shuffle")
    assert card.current_revision == 2

    old_ver = tmp_db.get(KnowledgeCardVersion, ("card.spark.shuffle", 1))
    assert old_ver is not None
    new_ver = tmp_db.get(KnowledgeCardVersion, ("card.spark.shuffle", 2))
    assert new_ver is not None
    assert old_ver.source_hash != new_ver.source_hash


# ---------------------------------------------------------------------------
# 14. Card is_active change → no new revision
# ---------------------------------------------------------------------------


def test_card_is_active_no_new_revision(tmp_db: Session, content_dir: Path) -> None:
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    _write_file(content_dir / "cards" / "spark.shuffle.md", _CARD_SPARK_SHUFFLE)
    import_content(content_dir, tmp_db)
    tmp_db.commit()

    new_card = _CARD_SPARK_SHUFFLE.replace("is_active: true", "is_active: false")
    _write_file(content_dir / "cards" / "spark.shuffle.md", new_card)

    result = import_content(content_dir, tmp_db)
    tmp_db.commit()

    assert result.card_versions_created == 0
    card = tmp_db.get(KnowledgeCard, "card.spark.shuffle")
    assert card.is_active is False
    assert card.current_revision == 1


# ---------------------------------------------------------------------------
# 15. Card identity change → new card + old deactivated
# ---------------------------------------------------------------------------


def test_card_identity_change_creates_new_card(tmp_db: Session, content_dir: Path) -> None:
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    _write_file(content_dir / "cards" / "spark.shuffle.md", _CARD_SPARK_SHUFFLE)
    import_content(content_dir, tmp_db)
    tmp_db.commit()

    # Change card to bind to a different KP
    new_card = _CARD_SPARK_SHUFFLE.replace(
        "knowledge_point_id: spark.shuffle",
        "knowledge_point_id: spark.rdd",
    )
    _write_file(content_dir / "cards" / "spark.rdd.md", new_card)
    new_kp = _KNOWLEDGE_SPARK + """\
    - id: spark.rdd
      name: RDD
      sort_order: 2
"""
    _write_file(content_dir / "knowledge" / "spark.yaml", new_kp)
    (content_dir / "cards" / "spark.shuffle.md").unlink()

    result = import_content(content_dir, tmp_db)
    tmp_db.commit()

    new_card_obj = tmp_db.get(KnowledgeCard, "card.spark.rdd")
    assert new_card_obj is not None
    assert new_card_obj.current_revision == 1

    old_card = tmp_db.get(KnowledgeCard, "card.spark.shuffle")
    assert old_card.is_active is False

    old_ver = tmp_db.get(KnowledgeCardVersion, ("card.spark.shuffle", 1))
    assert old_ver is not None


# ---------------------------------------------------------------------------
# 16. Choice content change → revision + 1
# ---------------------------------------------------------------------------


def test_choice_content_change_new_revision(tmp_db: Session, content_dir: Path) -> None:
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    _write_file(
        content_dir / "questions" / "choice" / "spark.shuffle.choice.001.yaml",
        _CHOICE_SPARK_SHUFFLE,
    )
    import_content(content_dir, tmp_db)
    tmp_db.commit()

    new_q = _CHOICE_SPARK_SHUFFLE.replace(
        "groupByKey 需要按 key 重分布数据。",
        "groupByKey 需要按 key 重分布数据，触发 Shuffle。",
    )
    _write_file(
        content_dir / "questions" / "choice" / "spark.shuffle.choice.001.yaml",
        new_q,
    )

    result = import_content(content_dir, tmp_db)
    tmp_db.commit()

    assert result.question_versions_created == 1
    q = tmp_db.get(Question, "spark.shuffle.choice.001")
    assert q.current_revision == 2


# ---------------------------------------------------------------------------
# 17. Choice difficulty change → no new revision
# ---------------------------------------------------------------------------


def test_choice_difficulty_no_new_revision(tmp_db: Session, content_dir: Path) -> None:
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    _write_file(
        content_dir / "questions" / "choice" / "spark.shuffle.choice.001.yaml",
        _CHOICE_SPARK_SHUFFLE,
    )
    import_content(content_dir, tmp_db)
    tmp_db.commit()

    new_q = _CHOICE_SPARK_SHUFFLE.replace("difficulty: 2", "difficulty: 4")
    _write_file(
        content_dir / "questions" / "choice" / "spark.shuffle.choice.001.yaml",
        new_q,
    )

    result = import_content(content_dir, tmp_db)
    tmp_db.commit()

    assert result.question_versions_created == 0
    q = tmp_db.get(Question, "spark.shuffle.choice.001")
    assert q.difficulty == 4
    assert q.current_revision == 1


# ---------------------------------------------------------------------------
# 18. Short Answer reference_answer change → revision + 1
# ---------------------------------------------------------------------------


def test_short_answer_ref_change_new_revision(tmp_db: Session, content_dir: Path) -> None:
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    _write_file(
        content_dir / "questions" / "short_answer" / "spark.shuffle.qa.001.yaml",
        _QA_SPARK_SHUFFLE,
    )
    import_content(content_dir, tmp_db)
    tmp_db.commit()

    new_q = _QA_SPARK_SHUFFLE.replace(
        "Shuffle 是数据重分布过程。",
        "Shuffle 是跨 Stage 的数据重分布过程。",
    )
    _write_file(
        content_dir / "questions" / "short_answer" / "spark.shuffle.qa.001.yaml",
        new_q,
    )

    result = import_content(content_dir, tmp_db)
    tmp_db.commit()

    assert result.question_versions_created == 1
    q = tmp_db.get(Question, "spark.shuffle.qa.001")
    assert q.current_revision == 2


# ---------------------------------------------------------------------------
# 19. SQL scoring_criteria change → revision + 1
# ---------------------------------------------------------------------------


def test_sql_scoring_change_new_revision(tmp_db: Session, content_dir: Path) -> None:
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    _write_file(
        content_dir / "questions" / "sql" / "spark.shuffle.sql.001.yaml",
        _SQL_SPARK_SHUFFLE,
    )
    import_content(content_dir, tmp_db)
    tmp_db.commit()

    new_q = _SQL_SPARK_SHUFFLE.replace("points: 6", "points: 7")
    _write_file(
        content_dir / "questions" / "sql" / "spark.shuffle.sql.001.yaml",
        new_q,
    )

    result = import_content(content_dir, tmp_db)
    tmp_db.commit()

    assert result.question_versions_created == 1
    ver = tmp_db.get(QuestionVersion, ("spark.shuffle.sql.001", 2))
    payload = json.loads(ver.payload_json)
    assert payload["max_score"] == 11  # 7 + 4


# ---------------------------------------------------------------------------
# 20. source_path is always content/...
# ---------------------------------------------------------------------------


def test_source_path_is_relative(tmp_db: Session, content_dir: Path) -> None:
    _setup_full_content(content_dir)
    import_content(content_dir, tmp_db)

    card_ver = tmp_db.get(KnowledgeCardVersion, ("card.spark.shuffle", 1))
    assert card_ver.source_path.startswith("content/")
    assert card_ver.source_path == "content/cards/spark.shuffle.md"

    q_ver = tmp_db.get(QuestionVersion, ("spark.shuffle.choice.001", 1))
    assert q_ver.source_path.startswith("content/")
    assert q_ver.source_path == "content/questions/choice/spark.shuffle.choice.001.yaml"


# ---------------------------------------------------------------------------
# 21-22. Old versions preserved
# ---------------------------------------------------------------------------


def test_old_question_version_preserved(tmp_db: Session, content_dir: Path) -> None:
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    _write_file(
        content_dir / "questions" / "choice" / "spark.shuffle.choice.001.yaml",
        _CHOICE_SPARK_SHUFFLE,
    )
    import_content(content_dir, tmp_db)
    tmp_db.commit()

    new_q = _CHOICE_SPARK_SHUFFLE.replace("以下哪个", "下列哪个")
    _write_file(
        content_dir / "questions" / "choice" / "spark.shuffle.choice.001.yaml",
        new_q,
    )
    import_content(content_dir, tmp_db)
    tmp_db.commit()

    v1 = tmp_db.get(QuestionVersion, ("spark.shuffle.choice.001", 1))
    v2 = tmp_db.get(QuestionVersion, ("spark.shuffle.choice.001", 2))
    assert v1 is not None
    assert v2 is not None
    assert v1.source_hash != v2.source_hash


def test_old_card_version_preserved(tmp_db: Session, content_dir: Path) -> None:
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    _write_file(content_dir / "cards" / "spark.shuffle.md", _CARD_SPARK_SHUFFLE)
    import_content(content_dir, tmp_db)
    tmp_db.commit()

    new_card = _CARD_SPARK_SHUFFLE.replace("数据重分布", "数据重新分布")
    _write_file(content_dir / "cards" / "spark.shuffle.md", new_card)
    import_content(content_dir, tmp_db)
    tmp_db.commit()

    v1 = tmp_db.get(KnowledgeCardVersion, ("card.spark.shuffle", 1))
    v2 = tmp_db.get(KnowledgeCardVersion, ("card.spark.shuffle", 2))
    assert v1 is not None
    assert v2 is not None
    assert v1.source_hash != v2.source_hash


# ---------------------------------------------------------------------------
# 23-25. Related knowledge points sync
# ---------------------------------------------------------------------------


def test_related_kp_sync_add_and_remove(tmp_db: Session, content_dir: Path) -> None:
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    _write_file(
        content_dir / "knowledge" / "hive.yaml",
        "- id: hive\n  name: Hive\n  sort_order: 2\n",
    )
    q_yaml = _CHOICE_SPARK_SHUFFLE.replace(
        "related_knowledge_points: []",
        "related_knowledge_points:\n  - hive",
    )
    _write_file(
        content_dir / "questions" / "choice" / "spark.shuffle.choice.001.yaml",
        q_yaml,
    )

    result = import_content(content_dir, tmp_db)
    tmp_db.commit()

    assert result.relations_created == 1
    rels = (
        tmp_db.query(QuestionRelatedKnowledgePoint)
        .filter_by(question_id="spark.shuffle.choice.001")
        .all()
    )
    assert len(rels) == 1
    assert rels[0].knowledge_point_id == "hive"

    # Remove related
    q_yaml2 = q_yaml.replace(
        "related_knowledge_points:\n  - hive",
        "related_knowledge_points: []",
    )
    _write_file(
        content_dir / "questions" / "choice" / "spark.shuffle.choice.001.yaml",
        q_yaml2,
    )

    tmp_db.commit()  # end auto-begun transaction from queries above
    result2 = import_content(content_dir, tmp_db)
    tmp_db.commit()

    assert result2.relations_deleted == 1
    rels2 = (
        tmp_db.query(QuestionRelatedKnowledgePoint)
        .filter_by(question_id="spark.shuffle.choice.001")
        .all()
    )
    assert len(rels2) == 0


def test_related_weight_is_default(tmp_db: Session, content_dir: Path) -> None:
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    _write_file(
        content_dir / "knowledge" / "hive.yaml",
        "- id: hive\n  name: Hive\n  sort_order: 2\n",
    )
    q_yaml = _CHOICE_SPARK_SHUFFLE.replace(
        "related_knowledge_points: []",
        "related_knowledge_points:\n  - hive",
    )
    _write_file(
        content_dir / "questions" / "choice" / "spark.shuffle.choice.001.yaml",
        q_yaml,
    )

    import_content(content_dir, tmp_db)

    rel = (
        tmp_db.query(QuestionRelatedKnowledgePoint)
        .filter_by(question_id="spark.shuffle.choice.001", knowledge_point_id="hive")
        .first()
    )
    assert rel is not None
    assert rel.weight == 1.0


# ---------------------------------------------------------------------------
# 26. Question question_type change → StableBindingError
# Tested by modifying DB directly, then re-importing same YAML
# ---------------------------------------------------------------------------


def test_question_type_change_rejected(tmp_db: Session, content_dir: Path) -> None:
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    _write_file(
        content_dir / "questions" / "choice" / "spark.shuffle.choice.001.yaml",
        _CHOICE_SPARK_SHUFFLE,
    )
    import_content(content_dir, tmp_db)
    tmp_db.commit()

    # Directly modify DB to create binding mismatch
    q = tmp_db.get(Question, "spark.shuffle.choice.001")
    q.question_type = "short_answer"
    tmp_db.commit()

    # Re-import same YAML — importer detects mismatch
    with pytest.raises(StableBindingError) as exc_info:
        import_content(content_dir, tmp_db)

    assert "question_type" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 27. Question primary KP change → StableBindingError
# Tested by modifying DB directly, then re-importing same YAML
# ---------------------------------------------------------------------------


def test_question_primary_kp_change_rejected(tmp_db: Session, content_dir: Path) -> None:
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    _write_file(
        content_dir / "questions" / "choice" / "spark.shuffle.choice.001.yaml",
        _CHOICE_SPARK_SHUFFLE,
    )
    import_content(content_dir, tmp_db)
    tmp_db.commit()

    # Create a valid "other_kp" so FK constraint passes
    tmp_db.add(KnowledgePoint(id="other_kp", name="Other", level=1, sort_order=99))
    tmp_db.commit()

    # Directly modify DB to create binding mismatch
    q = tmp_db.get(Question, "spark.shuffle.choice.001")
    q.primary_knowledge_point_id = "other_kp"
    tmp_db.commit()

    with pytest.raises(StableBindingError) as exc_info:
        import_content(content_dir, tmp_db)

    assert "primary_knowledge_point_id" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 28. Transaction rollback on failure
# ---------------------------------------------------------------------------


def test_transaction_rollback_on_failure(tmp_db: Session, content_dir: Path) -> None:
    """If import fails midway, the entire transaction should rollback."""
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    _write_file(
        content_dir / "questions" / "choice" / "spark.shuffle.choice.001.yaml",
        _CHOICE_SPARK_SHUFFLE,
    )
    import_content(content_dir, tmp_db)
    tmp_db.commit()

    # Verify state
    q = tmp_db.get(Question, "spark.shuffle.choice.001")
    assert q.difficulty == 2

    # Create a binding mismatch in DB + change KP name in YAML
    # The KP name change would succeed, but binding check fails → rollback
    kp = tmp_db.get(KnowledgePoint, "spark.shuffle")
    kp.parent_id = None  # Break the tree
    tmp_db.commit()

    # Modify KP name in YAML (would be an update if import succeeded)
    new_yaml = _KNOWLEDGE_SPARK.replace("name: Shuffle", "name: Shuffle 机制")
    _write_file(content_dir / "knowledge" / "spark.yaml", new_yaml)

    with pytest.raises(StableBindingError):
        import_content(content_dir, tmp_db)

    # After rollback, KP name should be unchanged
    tmp_db.expire_all()
    kp_after = tmp_db.get(KnowledgePoint, "spark.shuffle")
    assert kp_after.name == "Shuffle"  # NOT "Shuffle 机制"


# ---------------------------------------------------------------------------
# 29. Formal app.db not polluted
# ---------------------------------------------------------------------------


def test_formal_db_not_polluted(tmp_db: Session, content_dir: Path) -> None:
    formal_db = Path("data/app.db")
    if formal_db.exists():
        mtime_before = formal_db.stat().st_mtime
        _setup_full_content(content_dir)
        import_content(content_dir, tmp_db)
        mtime_after = formal_db.stat().st_mtime
        assert mtime_before == mtime_after


# ---------------------------------------------------------------------------
# 30. Full import of real content/ passes
# ---------------------------------------------------------------------------


def test_real_content_import(tmp_db: Session) -> None:
    real_content = Path("content").resolve()
    if not real_content.is_dir():
        pytest.skip("content/ directory not found")

    result = import_content(real_content, tmp_db)
    tmp_db.commit()

    assert result.knowledge_points_inserted > 0
    assert result.cards_inserted > 0
    assert result.questions_inserted > 0

    for ver in tmp_db.query(QuestionVersion).all():
        assert ver.revision == 1

    for ver in tmp_db.query(KnowledgeCardVersion).all():
        assert ver.revision == 1


# ---------------------------------------------------------------------------
# 31. Full regression — consistency check
# ---------------------------------------------------------------------------


def test_import_does_not_break_existing_content(tmp_db: Session, content_dir: Path) -> None:
    _setup_full_content(content_dir)

    r1 = import_content(content_dir, tmp_db)
    tmp_db.commit()

    assert r1.knowledge_points_inserted == 2
    assert r1.cards_inserted == 1
    assert r1.questions_inserted == 3
    assert r1.card_versions_created == 1
    assert r1.question_versions_created == 3

    r2 = import_content(content_dir, tmp_db)
    tmp_db.commit()

    assert r2.knowledge_points_inserted == 0
    assert r2.cards_inserted == 0
    assert r2.questions_inserted == 0
    assert r2.card_versions_created == 0
    assert r2.question_versions_created == 0
    assert r2.unchanged > 0


# ---------------------------------------------------------------------------
# 32. Transaction ownership — importer rejects active transaction
# ---------------------------------------------------------------------------


def test_importer_rejects_existing_transaction_without_committing_it(
    tmp_db: Session, content_dir: Path
) -> None:
    """import_content must refuse to run if the Session has an active transaction,
    and must NOT commit the caller's existing transaction."""
    _setup_full_content(content_dir)

    # Create an uncommitted business change
    tmp_db.add(KnowledgePoint(
        id="orphan_kp", name="Orphan", level=1, sort_order=99,
    ))
    tmp_db.flush()  # write to DB but keep transaction open

    assert tmp_db.in_transaction()

    # import_content must reject
    with pytest.raises(ContentImportError, match="fresh Session"):
        import_content(content_dir, tmp_db)

    # The uncommitted change must NOT have been committed by the importer.
    # Use a separate Session to check.
    from sqlalchemy.orm import Session as SASession

    engine = tmp_db.get_bind()
    CheckSession = SASession(bind=engine)
    try:
        found = CheckSession.get(KnowledgePoint, "orphan_kp")
        assert found is None, "Importer should not have committed the caller's transaction"
    finally:
        CheckSession.close()

    # Clean up — rollback the caller's transaction
    tmp_db.rollback()


# ---------------------------------------------------------------------------
# 33. Real content import (no skip)
# ---------------------------------------------------------------------------


def test_real_content_import(tmp_db: Session) -> None:
    """Import the actual project content/ directory into a temp DB."""
    repo_root = Path(__file__).resolve().parents[2]
    real_content = repo_root / "content"

    if not real_content.is_dir():
        # If running outside the repo, fall back to cwd-based path
        real_content = Path("content").resolve()

    assert real_content.is_dir(), f"content/ not found at {real_content}"

    result = import_content(real_content, tmp_db)
    tmp_db.commit()

    # Verify real content was imported
    assert result.knowledge_points_inserted > 0
    assert result.cards_inserted > 0
    assert result.card_versions_created > 0
    assert result.questions_inserted > 0
    assert result.question_versions_created > 0

    # All should be first revision
    for qv in tmp_db.query(QuestionVersion).all():
        assert qv.revision == 1
    for cv in tmp_db.query(KnowledgeCardVersion).all():
        assert cv.revision == 1

    # source_path must start with content/ and not be absolute
    for qv in tmp_db.query(QuestionVersion).all():
        assert qv.source_path.startswith("content/"), f"Bad source_path: {qv.source_path}"
        assert not Path(qv.source_path).is_absolute()
    for cv in tmp_db.query(KnowledgeCardVersion).all():
        assert cv.source_path.startswith("content/"), f"Bad source_path: {cv.source_path}"
        assert not Path(cv.source_path).is_absolute()
