"""Tests for content validator."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.content.loader import safe_load_yaml_str
from app.content.validator import validate_all


# ---------------------------------------------------------------------------
# Fixtures — create minimal content trees in tmp_path
# ---------------------------------------------------------------------------

def _write_file(path: Path, content: str) -> Path:
    """Write a file, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# Minimal valid content fragments
_KNOWLEDGE_SPARK = """\
id: spark
name: Spark
sort_order: 1
children:
  - id: spark.shuffle
    name: Shuffle
    sort_order: 1
  - id: spark.rdd
    name: RDD
    sort_order: 2
"""

_CARD_SPARK_SHUFFLE = """\
---
knowledge_point_id: spark.shuffle
title: Shuffle
---

## 一句话定义

Spark Shuffle 是宽依赖的数据重新分布过程。

## 核心原理

父 RDD 分区数据被子 RDD 多个分区使用时触发 Shuffle。

## 面试高频点

- 默认分区器是 HashPartitioner
- Shuffle 是性能瓶颈

## 常见易错点

- map 不触发 Shuffle，repartition 触发
"""

_CHOICE_SPARK_SHUFFLE = """\
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

content: 以下哪个操作一定会触发 Spark Shuffle？

options:
  - key: A
    text: map
  - key: B
    text: filter
  - key: C
    text: repartition
  - key: D
    text: mapPartitions

correct_answer: C

explanation: repartition 会重新分区，因此会触发 Shuffle。
"""

_SA_SPARK_SHUFFLE = """\
id: spark.shuffle.qa.001
question_type: short_answer
primary_knowledge_point_id: spark.shuffle
title: Shuffle 本质
difficulty: 3
tags:
  - spark
related_knowledge_points: []
is_active: true

content: 请解释 Spark Shuffle 的本质。

reference_answer: |
  Spark Shuffle 是宽依赖的数据重新分布过程。

explanation: |
  面试中从是什么、为什么慢、如何优化三段式展开。
"""

_SQL_SPARK_SHUFFLE = """\
id: spark.shuffle.sql.001
question_type: sql
primary_knowledge_point_id: spark.shuffle
title: Top3 门店
difficulty: 4
tags:
  - sql
related_knowledge_points: []
is_active: true

content: |
  查询每个品类销售额排名前 3 的门店。

business_requirement: |
  1. 按品类分组计算门店总销售额
  2. 品类内降序排名
  3. 返回前 3

expected_sql: |
  SELECT category, store_id, SUM(sale_amount) AS total
  FROM store_sales
  GROUP BY category, store_id;

scoring_criteria:
  - id: c1
    description: 正确分组汇总
    points: 5
  - id: c2
    description: 正确排名
    points: 5
"""


def _build_valid_tree(tmp_path: Path) -> Path:
    """Build a minimal valid content tree."""
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    _write_file(content_dir / "cards" / "spark.shuffle.md", _CARD_SPARK_SHUFFLE)
    _write_file(content_dir / "questions" / "choice" / "spark.shuffle.choice.001.yaml", _CHOICE_SPARK_SHUFFLE)
    _write_file(content_dir / "questions" / "short_answer" / "spark.shuffle.qa.001.yaml", _SA_SPARK_SHUFFLE)
    _write_file(content_dir / "questions" / "sql" / "spark.shuffle.sql.001.yaml", _SQL_SPARK_SHUFFLE)
    return content_dir


# ===================================================================
# 1. Valid content passes
# ===================================================================

def test_valid_content_passes(tmp_path: Path) -> None:
    content_dir = _build_valid_tree(tmp_path)
    result = validate_all(content_dir)
    assert result.is_valid, result.summary_text()


# ===================================================================
# 2. Real content passes
# ===================================================================

def test_real_content_passes() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    content_dir = repo_root / "content"
    if not content_dir.is_dir():
        pytest.skip("content/ directory not found")
    result = validate_all(content_dir)
    assert result.is_valid, result.summary_text()


# ===================================================================
# 3. Duplicate YAML key
# ===================================================================

def test_duplicate_yaml_key_fails(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", "id: spark\nname: Spark\nsort_order: 1\nsort_order: 2\n")
    result = validate_all(content_dir)
    assert not result.is_valid
    assert any("duplicate key" in str(i).lower() or "sort_order" in str(i) for i in result.issues)


# ===================================================================
# 4. Knowledge ID duplicate
# ===================================================================

def test_knowledge_id_duplicate_fails(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    _write_file(content_dir / "knowledge" / "spark2.yaml", _KNOWLEDGE_SPARK)
    result = validate_all(content_dir)
    assert not result.is_valid
    assert any("重复" in str(i) for i in result.issues)


# ===================================================================
# 5. Knowledge filename / top-level ID mismatch
# ===================================================================

def test_knowledge_filename_mismatch_fails(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", "id: hive\nname: Hive\nsort_order: 2\n")
    result = validate_all(content_dir)
    assert not result.is_valid
    assert any("文件名" in str(i) and "不一致" in str(i) for i in result.issues)


# ===================================================================
# 6. Knowledge child ID not starting with parent
# ===================================================================

def test_knowledge_child_id_mismatch_fails(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    yaml_content = """\
id: spark
name: Spark
sort_order: 1
children:
  - id: hive.shuffle
    name: Bad Child
    sort_order: 1
"""
    _write_file(content_dir / "knowledge" / "spark.yaml", yaml_content)
    result = validate_all(content_dir)
    assert not result.is_valid
    assert any("不以父 id" in str(i) for i in result.issues)


# ===================================================================
# 7. Card references non-existent KP
# ===================================================================

def test_card_missing_kp_fails(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    card = """\
---
knowledge_point_id: nonexistent.kp
title: Test
---

## 一句话定义

Test.

## 核心原理

Test.

## 面试高频点

Test.

## 常见易错点

Test.
"""
    _write_file(content_dir / "cards" / "nonexistent.kp.md", card)
    result = validate_all(content_dir)
    assert not result.is_valid
    assert any("不存在" in str(i) for i in result.issues)


# ===================================================================
# 8. Card filename / KP mismatch
# ===================================================================

def test_card_filename_mismatch_fails(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    _write_file(content_dir / "cards" / "wrong_name.md", _CARD_SPARK_SHUFFLE)
    result = validate_all(content_dir)
    assert not result.is_valid
    assert any("文件名" in str(i) and "不一致" in str(i) for i in result.issues)


# ===================================================================
# 9. Card missing required section
# ===================================================================

def test_card_missing_section_fails(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    card = """\
---
knowledge_point_id: spark.shuffle
title: Shuffle
---

## 一句话定义

Test.

## 核心原理

Test.
"""
    _write_file(content_dir / "cards" / "spark.shuffle.md", card)
    result = validate_all(content_dir)
    assert not result.is_valid
    assert any("缺少 section" in str(i) for i in result.issues)


# ===================================================================
# 10. Card body contains H1
# ===================================================================

def test_card_body_h1_fails(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    card = """\
---
knowledge_point_id: spark.shuffle
title: Shuffle
---

# This is H1

## 一句话定义

Test.

## 核心原理

Test.

## 面试高频点

Test.

## 常见易错点

Test.
"""
    _write_file(content_dir / "cards" / "spark.shuffle.md", card)
    result = validate_all(content_dir)
    assert not result.is_valid
    assert any("一级标题" in str(i) for i in result.issues)


# ===================================================================
# 11. Choice stable ID / primary mismatch
# ===================================================================

def test_choice_id_primary_mismatch_fails(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    yaml_content = """\
id: spark.rdd.choice.001
question_type: choice
primary_knowledge_point_id: spark.shuffle
difficulty: 2
tags: []
related_knowledge_points: []
is_active: true

content: Test?

options:
  - key: A
    text: A
  - key: B
    text: B

correct_answer: A

explanation: Test.
"""
    _write_file(content_dir / "questions" / "choice" / "spark.rdd.choice.001.yaml", yaml_content)
    result = validate_all(content_dir)
    assert not result.is_valid
    assert any("不一致" in str(i) for i in result.issues)


# ===================================================================
# 12. Question filename / ID mismatch
# ===================================================================

def test_question_filename_mismatch_fails(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    _write_file(content_dir / "questions" / "choice" / "wrong_name.yaml", _CHOICE_SPARK_SHUFFLE)
    result = validate_all(content_dir)
    assert not result.is_valid
    assert any("文件名" in str(i) and "不一致" in str(i) for i in result.issues)


# ===================================================================
# 13. Non-existent primary KP
# ===================================================================

def test_nonexistent_primary_kp_fails(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    yaml_content = """\
id: nonexistent.kp.choice.001
question_type: choice
primary_knowledge_point_id: nonexistent.kp
difficulty: 2
tags: []
related_knowledge_points: []
is_active: true

content: Test?

options:
  - key: A
    text: A
  - key: B
    text: B

correct_answer: A

explanation: Test.
"""
    _write_file(content_dir / "questions" / "choice" / "nonexistent.kp.choice.001.yaml", yaml_content)
    result = validate_all(content_dir)
    assert not result.is_valid
    assert any("不存在" in str(i) for i in result.issues)


# ===================================================================
# 14. Non-existent related KP
# ===================================================================

def test_nonexistent_related_kp_fails(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    yaml_content = """\
id: spark.shuffle.choice.001
question_type: choice
primary_knowledge_point_id: spark.shuffle
difficulty: 2
tags: []
related_knowledge_points:
  - nonexistent.kp
is_active: true

content: Test?

options:
  - key: A
    text: A
  - key: B
    text: B

correct_answer: A

explanation: Test.
"""
    _write_file(content_dir / "questions" / "choice" / "spark.shuffle.choice.001.yaml", yaml_content)
    result = validate_all(content_dir)
    assert not result.is_valid
    assert any("不存在" in str(i) for i in result.issues)


# ===================================================================
# 15. Primary in related
# ===================================================================

def test_primary_in_related_fails(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    yaml_content = """\
id: spark.shuffle.choice.001
question_type: choice
primary_knowledge_point_id: spark.shuffle
difficulty: 2
tags: []
related_knowledge_points:
  - spark.shuffle
is_active: true

content: Test?

options:
  - key: A
    text: A
  - key: B
    text: B

correct_answer: A

explanation: Test.
"""
    _write_file(content_dir / "questions" / "choice" / "spark.shuffle.choice.001.yaml", yaml_content)
    result = validate_all(content_dir)
    assert not result.is_valid
    assert any("不应出现在 related" in str(i) for i in result.issues)


# ===================================================================
# 16. Related duplicate
# ===================================================================

def test_related_duplicate_fails(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    yaml_content = """\
id: spark.shuffle.choice.001
question_type: choice
primary_knowledge_point_id: spark.shuffle
difficulty: 2
tags: []
related_knowledge_points:
  - spark.rdd
  - spark.rdd
is_active: true

content: Test?

options:
  - key: A
    text: A
  - key: B
    text: B

correct_answer: A

explanation: Test.
"""
    _write_file(content_dir / "questions" / "choice" / "spark.shuffle.choice.001.yaml", yaml_content)
    result = validate_all(content_dir)
    assert not result.is_valid
    assert any("重复" in str(i) for i in result.issues)


# ===================================================================
# 17. Difficulty out of range
# ===================================================================

def test_difficulty_out_of_range_fails(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    yaml_content = """\
id: spark.shuffle.choice.001
question_type: choice
primary_knowledge_point_id: spark.shuffle
difficulty: 6
tags: []
related_knowledge_points: []
is_active: true

content: Test?

options:
  - key: A
    text: A
  - key: B
    text: B

correct_answer: A

explanation: Test.
"""
    _write_file(content_dir / "questions" / "choice" / "spark.shuffle.choice.001.yaml", yaml_content)
    result = validate_all(content_dir)
    assert not result.is_valid
    assert any("difficulty" in str(i).lower() for i in result.issues)


# ===================================================================
# 18. Choice option key duplicate
# ===================================================================

def test_choice_option_key_duplicate_fails(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    yaml_content = """\
id: spark.shuffle.choice.001
question_type: choice
primary_knowledge_point_id: spark.shuffle
difficulty: 2
tags: []
related_knowledge_points: []
is_active: true

content: Test?

options:
  - key: A
    text: First
  - key: A
    text: Second

correct_answer: A

explanation: Test.
"""
    _write_file(content_dir / "questions" / "choice" / "spark.shuffle.choice.001.yaml", yaml_content)
    result = validate_all(content_dir)
    assert not result.is_valid
    assert any("key" in str(i).lower() and "重复" in str(i) for i in result.issues)


# ===================================================================
# 19. Choice correct_answer not in options
# ===================================================================

def test_choice_correct_answer_invalid_fails(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    yaml_content = """\
id: spark.shuffle.choice.001
question_type: choice
primary_knowledge_point_id: spark.shuffle
difficulty: 2
tags: []
related_knowledge_points: []
is_active: true

content: Test?

options:
  - key: A
    text: A
  - key: B
    text: B

correct_answer: E

explanation: Test.
"""
    _write_file(content_dir / "questions" / "choice" / "spark.shuffle.choice.001.yaml", yaml_content)
    result = validate_all(content_dir)
    assert not result.is_valid
    assert any("correct_answer" in str(i) and "不在" in str(i) for i in result.issues)


# ===================================================================
# 20. Short Answer reference_answer empty
# ===================================================================

def test_sa_reference_answer_empty_fails(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    yaml_content = """\
id: spark.shuffle.qa.001
question_type: short_answer
primary_knowledge_point_id: spark.shuffle
difficulty: 3
tags: []
related_knowledge_points: []
is_active: true

content: Explain Shuffle.

reference_answer: ""

explanation: Some explanation.
"""
    _write_file(content_dir / "questions" / "short_answer" / "spark.shuffle.qa.001.yaml", yaml_content)
    result = validate_all(content_dir)
    assert not result.is_valid
    assert any("reference_answer" in str(i) for i in result.issues)


# ===================================================================
# 21. SQL criterion id duplicate
# ===================================================================

def test_sql_criterion_id_duplicate_fails(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    yaml_content = """\
id: spark.shuffle.sql.001
question_type: sql
primary_knowledge_point_id: spark.shuffle
difficulty: 3
tags: []
related_knowledge_points: []
is_active: true

content: Test SQL.

business_requirement: |
  1. Do something

scoring_criteria:
  - id: c1
    description: First
    points: 5
  - id: c1
    description: Duplicate
    points: 5
"""
    _write_file(content_dir / "questions" / "sql" / "spark.shuffle.sql.001.yaml", yaml_content)
    result = validate_all(content_dir)
    assert not result.is_valid
    assert any("id" in str(i).lower() and "重复" in str(i) for i in result.issues)


# ===================================================================
# 22. SQL points <= 0
# ===================================================================

def test_sql_points_zero_fails(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    yaml_content = """\
id: spark.shuffle.sql.001
question_type: sql
primary_knowledge_point_id: spark.shuffle
difficulty: 3
tags: []
related_knowledge_points: []
is_active: true

content: Test SQL.

business_requirement: |
  1. Do something

scoring_criteria:
  - id: c1
    description: First
    points: 0
"""
    _write_file(content_dir / "questions" / "sql" / "spark.shuffle.sql.001.yaml", yaml_content)
    result = validate_all(content_dir)
    assert not result.is_valid
    assert any("points" in str(i).lower() for i in result.issues)


# ===================================================================
# 23. Unknown field rejected (extra=forbid)
# ===================================================================

def test_unknown_field_rejected(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    yaml_content = """\
id: spark.shuffle.choice.001
question_type: choice
primary_knowledge_point_id: spark.shuffle
difficulty: 2
tags: []
related_knowledge_points: []
is_active: true

content: Test?

options:
  - key: A
    text: A
  - key: B
    text: B

correct_answer: A

explanation: Test.

scoring_rubric: should not exist
"""
    _write_file(content_dir / "questions" / "choice" / "spark.shuffle.choice.001.yaml", yaml_content)
    result = validate_all(content_dir)
    assert not result.is_valid
    assert any("scoring_rubric" in str(i) or "extra" in str(i).lower() for i in result.issues)


# ===================================================================
# 24. Valid Knowledge Point passes
# ===================================================================

def test_valid_knowledge_point_passes(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    result = validate_all(content_dir)
    assert result.is_valid, result.summary_text()


# ===================================================================
# 25. Valid Card passes
# ===================================================================

def test_valid_card_passes(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    _write_file(content_dir / "cards" / "spark.shuffle.md", _CARD_SPARK_SHUFFLE)
    result = validate_all(content_dir)
    assert result.is_valid, result.summary_text()


# ===================================================================
# 26. Valid Choice passes
# ===================================================================

def test_valid_choice_passes(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    _write_file(content_dir / "questions" / "choice" / "spark.shuffle.choice.001.yaml", _CHOICE_SPARK_SHUFFLE)
    result = validate_all(content_dir)
    assert result.is_valid, result.summary_text()


# ===================================================================
# 27. Valid Short Answer passes
# ===================================================================

def test_valid_short_answer_passes(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    _write_file(content_dir / "questions" / "short_answer" / "spark.shuffle.qa.001.yaml", _SA_SPARK_SHUFFLE)
    result = validate_all(content_dir)
    assert result.is_valid, result.summary_text()


# ===================================================================
# 28. Valid SQL passes
# ===================================================================

def test_valid_sql_passes(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    _write_file(content_dir / "questions" / "sql" / "spark.shuffle.sql.001.yaml", _SQL_SPARK_SHUFFLE)
    result = validate_all(content_dir)
    assert result.is_valid, result.summary_text()


# ===================================================================
# 29. YAML loader duplicate key detection
# ===================================================================

def test_yaml_duplicate_key_detected() -> None:
    with pytest.raises(ValueError, match="duplicate key"):
        safe_load_yaml_str("name: test\nname: duplicate\n", file_path="test.yaml")


# ===================================================================
# 30. Card unknown Front Matter field rejected
# ===================================================================

def test_card_unknown_front_matter_field_fails(tmp_path: Path) -> None:
    """extra=forbid should catch unknown fields in card front matter."""
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    card = """\
---
knowledge_point_id: spark.shuffle
title: Shuffle
unknown_field: xxx
---

## 一句话定义

Test.

## 核心原理

Test.

## 面试高频点

Test.

## 常见易错点

Test.
"""
    _write_file(content_dir / "cards" / "spark.shuffle.md", card)
    result = validate_all(content_dir)
    assert not result.is_valid
    assert any("unknown_field" in str(i) or "extra" in str(i).lower() for i in result.issues)


# ===================================================================
# 31-34. Strict type tests (difficulty, is_active, sort_order, points)
# ===================================================================

@pytest.mark.parametrize("difficulty_value", ['"2"', '"true"', "null"])
def test_choice_strict_difficulty_fails(tmp_path: Path, difficulty_value: str) -> None:
    """difficulty must be a real integer, not a string or null."""
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    yaml_content = f"""\
id: spark.shuffle.choice.001
question_type: choice
primary_knowledge_point_id: spark.shuffle
difficulty: {difficulty_value}
tags: []
related_knowledge_points: []
is_active: true

content: Test?

options:
  - key: A
    text: A
  - key: B
    text: B

correct_answer: A

explanation: Test.
"""
    _write_file(content_dir / "questions" / "choice" / "spark.shuffle.choice.001.yaml", yaml_content)
    result = validate_all(content_dir)
    assert not result.is_valid
    assert result.is_valid is False


def test_choice_strict_is_active_string_fails(tmp_path: Path) -> None:
    """is_active: 'true' (string) should fail strict validation."""
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    yaml_content = """\
id: spark.shuffle.choice.001
question_type: choice
primary_knowledge_point_id: spark.shuffle
difficulty: 2
tags: []
related_knowledge_points: []
is_active: "true"

content: Test?

options:
  - key: A
    text: A
  - key: B
    text: B

correct_answer: A

explanation: Test.
"""
    _write_file(content_dir / "questions" / "choice" / "spark.shuffle.choice.001.yaml", yaml_content)
    result = validate_all(content_dir)
    assert not result.is_valid


def test_choice_strict_is_active_int_fails(tmp_path: Path) -> None:
    """is_active: 1 (int) should fail strict validation."""
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    yaml_content = """\
id: spark.shuffle.choice.001
question_type: choice
primary_knowledge_point_id: spark.shuffle
difficulty: 2
tags: []
related_knowledge_points: []
is_active: 1

content: Test?

options:
  - key: A
    text: A
  - key: B
    text: B

correct_answer: A

explanation: Test.
"""
    _write_file(content_dir / "questions" / "choice" / "spark.shuffle.choice.001.yaml", yaml_content)
    result = validate_all(content_dir)
    assert not result.is_valid


# ===================================================================
# 35. Card H3 must not satisfy H2 section requirement
# ===================================================================

def test_card_h3_cannot_substitute_h2(tmp_path: Path) -> None:
    """### 一句话定义 must not satisfy the ## 一句话定义 requirement."""
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    card = """\
---
knowledge_point_id: spark.shuffle
title: Shuffle
---

### 一句话定义

This is H3, not H2.

## 核心原理

Test.

## 面试高频点

Test.

## 常见易错点

Test.
"""
    _write_file(content_dir / "cards" / "spark.shuffle.md", card)
    result = validate_all(content_dir)
    assert not result.is_valid
    assert any("缺少 section '## 一句话定义'" in str(i) for i in result.issues)


# ===================================================================
# 36. SQL max_score correctly summed
# ===================================================================

def test_sql_max_score_sum(tmp_path: Path) -> None:
    """SQL scoring_criteria points should be correctly summed and exposed."""
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    _write_file(content_dir / "questions" / "sql" / "spark.shuffle.sql.001.yaml", _SQL_SPARK_SHUFFLE)
    result = validate_all(content_dir)
    assert result.is_valid, result.summary_text()
    assert "spark.shuffle.sql.001" in result.sql_max_scores
    assert result.sql_max_scores["spark.shuffle.sql.001"] == 10


def test_sql_max_score_not_recorded_on_invalid(tmp_path: Path) -> None:
    """If scoring_criteria is invalid, max_score should not be recorded."""
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    yaml_content = """\
id: spark.shuffle.sql.001
question_type: sql
primary_knowledge_point_id: spark.shuffle
difficulty: 3
tags: []
related_knowledge_points: []
is_active: true

content: Test SQL.

business_requirement: |
  1. Do something

scoring_criteria:
  - id: c1
    description: First
    points: 0
"""
    _write_file(content_dir / "questions" / "sql" / "spark.shuffle.sql.001.yaml", yaml_content)
    result = validate_all(content_dir)
    assert not result.is_valid
    assert "spark.shuffle.sql.001" not in result.sql_max_scores


# ===================================================================
# 37-38. Invalid types don't crash validator
# ===================================================================

def test_invalid_id_type_does_not_crash(tmp_path: Path) -> None:
    """id: 123 (int) should not crash the validator."""
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    yaml_content = """\
id: 123
question_type: choice
primary_knowledge_point_id: spark.shuffle
difficulty: 2
tags: []
related_knowledge_points: []
is_active: true

content: Test?

options:
  - key: A
    text: A
  - key: B
    text: B

correct_answer: A

explanation: Test.
"""
    _write_file(content_dir / "questions" / "choice" / "123.yaml", yaml_content)
    result = validate_all(content_dir)
    assert not result.is_valid
    # Must not crash — should return issues


def test_invalid_option_key_type_does_not_crash(tmp_path: Path) -> None:
    """options key: 1 (int) should not crash the validator."""
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    yaml_content = """\
id: spark.shuffle.choice.001
question_type: choice
primary_knowledge_point_id: spark.shuffle
difficulty: 2
tags: []
related_knowledge_points: []
is_active: true

content: Test?

options:
  - key: 1
    text: xxx
  - key: B
    text: yyy

correct_answer: 1

explanation: Test.
"""
    _write_file(content_dir / "questions" / "choice" / "spark.shuffle.choice.001.yaml", yaml_content)
    result = validate_all(content_dir)
    assert not result.is_valid


# ===================================================================
# 39. Multiple bad files summarized together
# ===================================================================

def test_multiple_bad_files_summarized(tmp_path: Path) -> None:
    """Two bad YAML files should both appear in issues."""
    content_dir = tmp_path / "content"
    _write_file(content_dir / "knowledge" / "spark.yaml", _KNOWLEDGE_SPARK)
    bad1 = """\
id: spark.shuffle.choice.001
question_type: choice
primary_knowledge_point_id: spark.shuffle
difficulty: 99
tags: []
related_knowledge_points: []
is_active: true

content: Test?

options:
  - key: A
    text: A
  - key: B
    text: B

correct_answer: A

explanation: Test.
"""
    bad2 = """\
id: spark.shuffle.qa.001
question_type: short_answer
primary_knowledge_point_id: spark.shuffle
difficulty: 3
tags: []
related_knowledge_points: []
is_active: true

content: Test.

reference_answer: ""

explanation: Test.
"""
    _write_file(content_dir / "questions" / "choice" / "spark.shuffle.choice.001.yaml", bad1)
    _write_file(content_dir / "questions" / "short_answer" / "spark.shuffle.qa.001.yaml", bad2)
    result = validate_all(content_dir)
    assert not result.is_valid
    files_mentioned = {i.path for i in result.issues}
    assert any("choice" in f for f in files_mentioned)
    assert any("short_answer" in f for f in files_mentioned)
