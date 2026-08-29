"""Content validator — validates all content files in content/ directory."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.content.loader import (
    extract_headings,
    load_all_choice_questions,
    load_all_knowledge_cards,
    load_all_knowledge_points,
    load_all_short_answer_questions,
    load_all_sql_questions,
)
from app.content.schemas import (
    ChoiceQuestionSchema,
    KnowledgeCardFrontMatter,
    KnowledgePointSchema,
    ShortAnswerQuestionSchema,
    SQLQuestionSchema,
)


# ---------------------------------------------------------------------------
# Error collection
# ---------------------------------------------------------------------------

class ContentValidationIssue:
    """A single validation issue."""

    def __init__(self, path: str, field: str, message: str) -> None:
        self.path = path
        self.field = field
        self.message = message

    def __str__(self) -> str:
        return f"{self.path}: {self.field}: {self.message}"

    def __repr__(self) -> str:
        return f"ContentValidationIssue({self!s})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ContentValidationIssue):
            return NotImplemented
        return (self.path, self.field, self.message) == (other.path, other.field, other.message)


class ValidationResult:
    """Aggregated validation result."""

    def __init__(self) -> None:
        self.issues: list[ContentValidationIssue] = []
        self.knowledge_point_count = 0
        self.knowledge_card_count = 0
        self.choice_count = 0
        self.short_answer_count = 0
        self.sql_count = 0
        self.sql_max_scores: dict[str, int] = {}

    def add(self, path: str, field: str, message: str) -> None:
        self.issues.append(ContentValidationIssue(path, field, message))

    @property
    def is_valid(self) -> bool:
        return len(self.issues) == 0

    def summary_text(self) -> str:
        lines = [
            f"Knowledge Points: {self.knowledge_point_count}",
            f"Knowledge Cards:  {self.knowledge_card_count}",
            f"Choice Questions: {self.choice_count}",
            f"Short Answer:     {self.short_answer_count}",
            f"SQL Questions:    {self.sql_count}",
            f"Issues:           {len(self.issues)}",
        ]
        if self.sql_max_scores:
            lines.append(f"SQL Max Scores:   {self.sql_max_scores}")
        if self.issues:
            lines.append("")
            lines.append("Errors:")
            for issue in self.issues:
                lines.append(f"  {issue}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Knowledge Point helpers
# ---------------------------------------------------------------------------

_KP_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9_]*)*$")


def _validate_kp_id_format(kp_id: str) -> str | None:
    """Return error message if ID format is invalid, else None."""
    if not isinstance(kp_id, str) or not _KP_ID_RE.match(kp_id):
        return f"id '{kp_id}' 格式不合法，只允许小写字母开头，小写字母/数字/点/下划线"
    return None


def _flatten_knowledge_points(
    nodes: list[dict[str, Any]],
    parent_id: str | None = None,
    level: int = 1,
) -> list[dict[str, Any]]:
    """Recursively flatten knowledge point tree into a flat list."""
    result: list[dict[str, Any]] = []
    for node in nodes:
        flat_node = {
            "id": node["id"],
            "name": node.get("name", ""),
            "sort_order": node.get("sort_order", 0),
            "description": node.get("description"),
            "is_active": node.get("is_active", True),
            "parent_id": parent_id,
            "level": level,
            "__file__": node.get("__file__", ""),
        }
        result.append(flat_node)
        for child in node.get("children", []):
            result.extend(_flatten_knowledge_points([child], parent_id=node["id"], level=level + 1))
    return result


def _detect_cycle(parent_map: dict[str, str | None]) -> str | None:
    """Detect cycle in parent map. Returns a node involved in cycle, or None."""
    visited: set[str] = set()
    path: set[str] = set()

    def dfs(node_id: str) -> bool:
        if node_id in path:
            return True
        if node_id in visited:
            return False
        visited.add(node_id)
        path.add(node_id)
        parent = parent_map.get(node_id)
        if parent and parent in parent_map:
            if dfs(parent):
                return True
        path.discard(node_id)
        return False

    for node_id in parent_map:
        if node_id not in visited:
            path.clear()
            if dfs(node_id):
                return node_id
    return None


# ---------------------------------------------------------------------------
# Knowledge Point validation
# ---------------------------------------------------------------------------

def _validate_knowledge_points(
    content_dir: Path,
    result: ValidationResult,
) -> dict[str, Any]:
    """Validate knowledge points and return {id: kp_info} dict."""
    try:
        raw_points = load_all_knowledge_points(content_dir)
    except (ValueError, Exception) as exc:
        result.add(str(content_dir), "knowledge", f"加载失败: {exc}")
        return {}

    kp_dict: dict[str, dict[str, Any]] = {}
    id_to_file: dict[str, str] = {}
    all_ids: set[str] = set()

    for raw in raw_points:
        file_path = raw.get("__file__", "unknown")
        filename_stem = Path(file_path).stem

        # Validate top-level ID matches filename
        top_id = raw.get("id", "")
        if top_id != filename_stem:
            result.add(file_path, "id", f"顶级知识点 id '{top_id}' 与文件名 '{filename_stem}' 不一致")

        # Check via schema validation
        schema_data = {k: v for k, v in raw.items() if not k.startswith("__")}
        try:
            KnowledgePointSchema.model_validate(schema_data)
        except ValidationError as exc:
            for err in exc.errors():
                field = ".".join(str(loc) for loc in err["loc"])
                result.add(file_path, field, err["msg"])
            continue

        # Flatten
        flat_nodes = _flatten_knowledge_points([raw])

        # Build parent map for cycle detection
        parent_map: dict[str, str | None] = {}
        for node in flat_nodes:
            node_id = node["id"]
            parent_map[node_id] = node.get("parent_id")

        # Cycle detection
        cycle_node = _detect_cycle(parent_map)
        if cycle_node:
            result.add(file_path, "children", f"id '{cycle_node}' 形成循环引用")

        # Validate each flattened node
        for node in flat_nodes:
            node_id = node["id"]
            node_file = file_path

            # ID format
            err = _validate_kp_id_format(node_id)
            if err:
                result.add(node_file, "id", err)

            # Global uniqueness
            if node_id in all_ids:
                other_file = id_to_file.get(node_id, "unknown")
                result.add(node_file, "id", f"id '{node_id}' 与 {other_file} 重复")
            all_ids.add(node_id)
            id_to_file[node_id] = node_file

            # Name non-empty
            if not node.get("name", "").strip():
                result.add(node_file, "name", f"id '{node_id}' 的 name 不能为空")

            # sort_order >= 0
            sort_order = node.get("sort_order", 0)
            if not isinstance(sort_order, int) or sort_order < 0:
                result.add(node_file, "sort_order", f"id '{node_id}' 的 sort_order 必须 >= 0")

            # Child ID starts with parent ID
            parent_id = node.get("parent_id")
            if parent_id and not node_id.startswith(parent_id + "."):
                result.add(
                    node_file, "id",
                    f"子知识点 id '{node_id}' 不以父 id '{parent_id}.' 开头",
                )

            # description not blank
            desc = node.get("description")
            if desc is not None and not desc.strip():
                result.add(node_file, "description", f"id '{node_id}' 的 description 不能为空白字符串")

            # Store in dict
            kp_dict[node_id] = node

    result.knowledge_point_count = len(kp_dict)
    return kp_dict


# ---------------------------------------------------------------------------
# Knowledge Card validation
# ---------------------------------------------------------------------------

_REQUIRED_CARD_SECTIONS = [
    "一句话定义",
    "核心原理",
    "面试高频点",
    "常见易错点",
]


def _validate_knowledge_cards(
    content_dir: Path,
    kp_ids: set[str],
    result: ValidationResult,
) -> None:
    """Validate knowledge card Markdown files."""
    try:
        cards = load_all_knowledge_cards(content_dir)
    except (ValueError, Exception) as exc:
        result.add(str(content_dir), "cards", f"加载失败: {exc}")
        return

    card_ids: set[str] = set()

    for card in cards:
        file_path = card.get("__file__", "unknown")
        filename_stem = card.get("__filename_stem__", "")

        # Pass full front matter to Pydantic (excluding internal fields)
        front_matter_data = {k: v for k, v in card.items() if not k.startswith("__")}

        # Schema validation (includes extra=forbid)
        schema_ok = True
        try:
            fm = KnowledgeCardFrontMatter.model_validate(front_matter_data)
        except ValidationError as exc:
            schema_ok = False
            for err in exc.errors():
                field = ".".join(str(loc) for loc in err["loc"])
                result.add(file_path, field, err["msg"])

        if not schema_ok:
            continue

        # knowledge_point_id exists
        if fm.knowledge_point_id not in kp_ids:
            result.add(
                file_path, "knowledge_point_id",
                f"knowledge_point_id '{fm.knowledge_point_id}' 不存在",
            )

        # Filename matches knowledge_point_id
        if filename_stem != fm.knowledge_point_id:
            result.add(
                file_path, "filename",
                f"文件名 '{filename_stem}' 与 knowledge_point_id '{fm.knowledge_point_id}' 不一致",
            )

        # Card ID uniqueness
        card_id = f"card.{fm.knowledge_point_id}"
        if card_id in card_ids:
            result.add(file_path, "knowledge_point_id", f"card id '{card_id}' 重复")
        card_ids.add(card_id)

        # Body validation
        body = card.get("__body__", "")

        # No H1 in body (only match level-1 heading, not ## or ###)
        _code_fence_re = re.compile(r"^```", re.MULTILINE)
        body_parts = _code_fence_re.split(body)
        body_outside_code = body_parts[::2]
        for segment in body_outside_code:
            if re.search(r"^#[^#]", segment, re.MULTILINE):
                result.add(file_path, "body", "Markdown body 不允许一级标题 #")
                break

        # Check required sections (must be exactly H2)
        headings = extract_headings(body)
        missing_sections: set[str] = set()
        for section in _REQUIRED_CARD_SECTIONS:
            # Must be level 2 with exact text match
            if not any(level == 2 and text == section for level, text in headings):
                result.add(file_path, "body", f"缺少 section '## {section}'")
                missing_sections.add(section)

        # Check section content not empty (only for sections that exist)
        body_no_code = re.sub(r"^```.*?^```", "", body, flags=re.MULTILINE | re.DOTALL)
        for section in _REQUIRED_CARD_SECTIONS:
            if section in missing_sections:
                continue
            pattern = re.compile(
                rf"^## {re.escape(section)}\s*\n(.*?)(?=^## |\Z)",
                re.MULTILINE | re.DOTALL,
            )
            match = pattern.search(body_no_code)
            if match:
                section_content = match.group(1).strip()
                if not section_content:
                    result.add(file_path, f"## {section}", "section 内容不能为空")

        # Section order check
        expected_order = [s for s in _REQUIRED_CARD_SECTIONS if s not in missing_sections]
        actual_order = [text for level, text in headings if level == 2 and text in set(_REQUIRED_CARD_SECTIONS)]
        if expected_order != actual_order:
            result.add(
                file_path, "body",
                f"section 顺序不正确，期望 {' > '.join(expected_order)}，实际 {' > '.join(actual_order)}",
            )

        # Each section exactly once
        for section in _REQUIRED_CARD_SECTIONS:
            if section in missing_sections:
                continue
            count = sum(1 for level, text in headings if level == 2 and text == section)
            if count > 1:
                result.add(file_path, "body", f"section '## {section}' 出现 {count} 次")

    result.knowledge_card_count = len(cards)


# ---------------------------------------------------------------------------
# Question ID format helpers
# ---------------------------------------------------------------------------

_CHOICE_ID_RE = re.compile(r"^([a-z][a-z0-9]*(?:\.[a-z][a-z0-9_]*)*)\.choice\.(\d{3})$")
_QA_ID_RE = re.compile(r"^([a-z][a-z0-9]*(?:\.[a-z][a-z0-9_]*)*)\.qa\.(\d{3})$")
_SQL_ID_RE = re.compile(r"^([a-z][a-z0-9]*(?:\.[a-z][a-z0-9_]*)*)\.sql\.(\d{3})$")

_ALLOWED_OPTION_KEYS = {"A", "B", "C", "D"}


def _validate_question_common(
    data: dict[str, Any],
    id_pattern: re.Pattern[str],
    question_type: str,
    kp_ids: set[str],
    question_ids: set[str],
    id_to_file: dict[str, str],
    result: ValidationResult,
) -> str | None:
    """Validate common question fields. Returns the question ID or None on fatal error."""
    file_path = data.get("__file__", "unknown")
    filename_stem = data.get("__filename_stem__", "")
    qid = data.get("id", "")

    # File name matches ID
    if filename_stem and filename_stem != qid:
        result.add(file_path, "id", f"文件名 '{filename_stem}' 与 id '{qid}' 不一致")

    # ID format
    if not isinstance(qid, str):
        result.add(file_path, "id", "id 必须是字符串")
        return None

    match = id_pattern.match(qid)
    if not match:
        result.add(file_path, "id", f"id '{qid}' 格式不合法")
        return None

    id_prefix = match.group(1)

    # Global uniqueness
    if qid in question_ids:
        other_file = id_to_file.get(qid, "unknown")
        result.add(file_path, "id", f"id '{qid}' 与 {other_file} 重复")
    question_ids.add(qid)
    id_to_file[qid] = file_path

    # question_type
    qt = data.get("question_type", "")
    if qt != question_type:
        result.add(file_path, "question_type", f"question_type 必须为 '{question_type}'，实际为 '{qt}'")

    # primary_knowledge_point_id
    primary_kp = data.get("primary_knowledge_point_id", "")
    if primary_kp not in kp_ids:
        result.add(
            file_path, "primary_knowledge_point_id",
            f"primary_knowledge_point_id '{primary_kp}' 不存在",
        )

    # ID prefix matches primary_knowledge_point_id
    if id_prefix != primary_kp:
        result.add(
            file_path, "id",
            f"id 前缀 '{id_prefix}' 与 primary_knowledge_point_id '{primary_kp}' 不一致",
        )

    # related_knowledge_points
    related = data.get("related_knowledge_points", [])
    if not isinstance(related, list):
        result.add(file_path, "related_knowledge_points", "related_knowledge_points 必须是列表")
    else:
        seen_related: set[str] = set()
        for _i, rkp in enumerate(related):
            if not isinstance(rkp, str):
                result.add(file_path, "related_knowledge_points", "related_knowledge_points 项必须是字符串")
                continue
            if rkp in seen_related:
                result.add(file_path, "related_knowledge_points", f"'{rkp}' 重复")
            seen_related.add(rkp)
            if rkp == primary_kp:
                result.add(
                    file_path, "related_knowledge_points",
                    f"primary_knowledge_point_id '{primary_kp}' 不应出现在 related_knowledge_points 中",
                )
            if rkp not in kp_ids:
                result.add(
                    file_path, "related_knowledge_points",
                    f"related_knowledge_point '{rkp}' 不存在",
                )

    # difficulty
    difficulty = data.get("difficulty")
    if not isinstance(difficulty, int) or difficulty < 1 or difficulty > 5:
        result.add(file_path, "difficulty", "difficulty 必须在 1-5 之间")

    # tags
    tags = data.get("tags", [])
    if not isinstance(tags, list):
        result.add(file_path, "tags", "tags 必须是列表")
    else:
        for i, tag in enumerate(tags):
            if not isinstance(tag, str) or not tag.strip():
                result.add(file_path, "tags", f"tags[{i}] 不能为空字符串")

    return qid


# ---------------------------------------------------------------------------
# Choice validation
# ---------------------------------------------------------------------------

def _validate_choice_questions(
    content_dir: Path,
    kp_ids: set[str],
    question_ids: set[str],
    id_to_file: dict[str, str],
    result: ValidationResult,
) -> None:
    """Validate choice question YAML files."""
    try:
        questions = load_all_choice_questions(content_dir)
    except (ValueError, Exception) as exc:
        result.add(str(content_dir), "choice", f"加载失败: {exc}")
        return

    for data in questions:
        file_path = data.get("__file__", "unknown")

        # Pydantic schema validation first
        schema_data = {k: v for k, v in data.items() if not k.startswith("__")}
        schema_ok = True
        try:
            ChoiceQuestionSchema.model_validate(schema_data)
        except ValidationError as exc:
            schema_ok = False
            for err in exc.errors():
                field = ".".join(str(loc) for loc in err["loc"])
                result.add(file_path, field, err["msg"])

        # Common validation (safe even if schema failed — uses isinstance guards)
        _validate_question_common(data, _CHOICE_ID_RE, "choice", kp_ids, question_ids, id_to_file, result)

        # Options validation (only if schema passed)
        if schema_ok:
            options = data.get("options", [])
            if not isinstance(options, list) or len(options) < 2:
                result.add(file_path, "options", "options 至少需要 2 个选项")
            else:
                option_keys: set[str] = set()
                for i, opt in enumerate(options):
                    if not isinstance(opt, dict):
                        result.add(file_path, f"options[{i}]", "选项必须是对象")
                        continue
                    key = opt.get("key", "")
                    text = opt.get("text", "")
                    if not isinstance(key, str) or not key.strip():
                        result.add(file_path, f"options[{i}].key", "key 不能为空")
                    elif key in option_keys:
                        result.add(file_path, f"options[{i}].key", f"key '{key}' 重复")
                    option_keys.add(key)
                    if isinstance(key, str) and key not in _ALLOWED_OPTION_KEYS:
                        result.add(file_path, f"options[{i}].key", f"key '{key}' 不合法，只允许 A/B/C/D")
                    if not isinstance(text, str) or not text.strip():
                        result.add(file_path, f"options[{i}].text", "text 不能为空")

            # correct_answer
            correct_answer = data.get("correct_answer", "")
            if isinstance(correct_answer, str) and isinstance(options, list):
                option_keys_set = {opt.get("key") for opt in options if isinstance(opt, dict)}
                if correct_answer not in option_keys_set:
                    result.add(
                        file_path, "correct_answer",
                        f"correct_answer '{correct_answer}' 不在 options key 中",
                    )

    result.choice_count = len(questions)


# ---------------------------------------------------------------------------
# Short Answer validation
# ---------------------------------------------------------------------------

def _validate_short_answer_questions(
    content_dir: Path,
    kp_ids: set[str],
    question_ids: set[str],
    id_to_file: dict[str, str],
    result: ValidationResult,
) -> None:
    """Validate short answer question YAML files."""
    try:
        questions = load_all_short_answer_questions(content_dir)
    except (ValueError, Exception) as exc:
        result.add(str(content_dir), "short_answer", f"加载失败: {exc}")
        return

    for data in questions:
        file_path = data.get("__file__", "unknown")

        # Pydantic schema validation
        schema_data = {k: v for k, v in data.items() if not k.startswith("__")}
        try:
            ShortAnswerQuestionSchema.model_validate(schema_data)
        except ValidationError as exc:
            for err in exc.errors():
                field = ".".join(str(loc) for loc in err["loc"])
                result.add(file_path, field, err["msg"])

        # Common validation
        _validate_question_common(data, _QA_ID_RE, "short_answer", kp_ids, question_ids, id_to_file, result)

    result.short_answer_count = len(questions)


# ---------------------------------------------------------------------------
# SQL validation
# ---------------------------------------------------------------------------

def _validate_sql_questions(
    content_dir: Path,
    kp_ids: set[str],
    question_ids: set[str],
    id_to_file: dict[str, str],
    result: ValidationResult,
) -> None:
    """Validate SQL question YAML files."""
    try:
        questions = load_all_sql_questions(content_dir)
    except (ValueError, Exception) as exc:
        result.add(str(content_dir), "sql", f"加载失败: {exc}")
        return

    for data in questions:
        file_path = data.get("__file__", "unknown")

        # Pydantic schema validation
        schema_data = {k: v for k, v in data.items() if not k.startswith("__")}
        schema_ok = True
        try:
            SQLQuestionSchema.model_validate(schema_data)
        except ValidationError as exc:
            schema_ok = False
            for err in exc.errors():
                field = ".".join(str(loc) for loc in err["loc"])
                result.add(file_path, field, err["msg"])

        # Common validation
        qid = _validate_question_common(data, _SQL_ID_RE, "sql", kp_ids, question_ids, id_to_file, result)

        # scoring_criteria (only if schema passed)
        if schema_ok:
            criteria = data.get("scoring_criteria", [])
            if not isinstance(criteria, list) or len(criteria) < 1:
                result.add(file_path, "scoring_criteria", "scoring_criteria 至少需要 1 个评分点")
            else:
                criterion_ids: set[str] = set()
                max_score = 0
                criteria_valid = True
                for i, c in enumerate(criteria):
                    if not isinstance(c, dict):
                        result.add(file_path, f"scoring_criteria[{i}]", "评分点必须是对象")
                        criteria_valid = False
                        continue
                    cid = c.get("id", "")
                    desc = c.get("description", "")
                    points = c.get("points")
                    if not isinstance(cid, str) or not cid.strip():
                        result.add(file_path, f"scoring_criteria[{i}].id", "id 不能为空")
                        criteria_valid = False
                    elif cid in criterion_ids:
                        result.add(file_path, f"scoring_criteria[{i}].id", f"id '{cid}' 重复")
                        criteria_valid = False
                    criterion_ids.add(cid)
                    if not isinstance(desc, str) or not desc.strip():
                        result.add(file_path, f"scoring_criteria[{i}].description", "description 不能为空")
                        criteria_valid = False
                    if not isinstance(points, int) or points <= 0:
                        result.add(file_path, f"scoring_criteria[{i}].points", "points 必须为正整数")
                        criteria_valid = False
                    elif isinstance(points, int) and points > 0:
                        max_score += points

                # Only record max_score if all criteria are valid and qid is known
                if criteria_valid and qid:
                    result.sql_max_scores[qid] = max_score

    result.sql_count = len(questions)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def validate_all(content_dir: Path) -> ValidationResult:
    """Validate all content files in the given directory.

    Returns a ValidationResult with all issues found.
    """
    result = ValidationResult()

    # 1. Load and validate Knowledge Points
    kp_dict = _validate_knowledge_points(content_dir, result)
    kp_ids = set(kp_dict.keys())

    # 2. Validate Knowledge Cards
    _validate_knowledge_cards(content_dir, kp_ids, result)

    # 3-5. Validate questions
    question_ids: set[str] = set()
    id_to_file: dict[str, str] = {}

    _validate_choice_questions(content_dir, kp_ids, question_ids, id_to_file, result)
    _validate_short_answer_questions(content_dir, kp_ids, question_ids, id_to_file, result)
    _validate_sql_questions(content_dir, kp_ids, question_ids, id_to_file, result)

    return result
