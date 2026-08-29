"""YAML / Markdown content file loaders with duplicate-key detection."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Duplicate-key-safe YAML loader
# ---------------------------------------------------------------------------

class _DuplicateKeyLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate mapping keys."""

    pass


def _construct_mapping_check_duplicates(
    loader: yaml.SafeLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict:
    """Construct mapping while checking for duplicate keys."""
    loader.flatten_mapping(node)
    pairs = loader.construct_pairs(node)
    seen: dict[str, int] = {}
    for key, _value in pairs:
        if key in seen:
            raise ValueError(
                f"duplicate key '{key}' at line {seen[key] + 1}"
            )
        seen[key] = node.start_mark.line
    return dict(pairs)


_DuplicateKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping_check_duplicates,
)


def safe_load_yaml_str(text: str, file_path: str = "<string>") -> dict[str, Any]:
    """Load YAML string with duplicate-key detection.

    Raises:
        ValueError: on duplicate keys
        yaml.YAMLError: on parse errors
    """
    try:
        return yaml.load(text, Loader=_DuplicateKeyLoader) or {}
    except ValueError as exc:
        raise ValueError(f"{file_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise yaml.YAMLError(f"{file_path}: YAML 解析错误: {exc}") from exc


def safe_load_yaml_file(path: Path) -> dict[str, Any]:
    """Load a YAML file with duplicate-key detection."""
    text = path.read_text(encoding="utf-8")
    return safe_load_yaml_str(text, file_path=str(path))


# ---------------------------------------------------------------------------
# Markdown Front Matter parser (minimal, no external dependency)
# ---------------------------------------------------------------------------

_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_markdown_front_matter(text: str, file_path: str = "<file>") -> tuple[dict[str, Any], str]:
    """Parse YAML front matter from a Markdown file.

    Returns:
        (front_matter_dict, body_markdown)

    Raises:
        ValueError: on duplicate keys or missing front matter
        yaml.YAMLError: on parse errors
    """
    match = _FRONT_MATTER_RE.match(text)
    if not match:
        raise ValueError(f"{file_path}: 缺少 YAML Front Matter (---)")
    yaml_text = match.group(1)
    body = text[match.end():]
    front_matter = safe_load_yaml_str(yaml_text, file_path=file_path)
    return front_matter, body


def parse_markdown_front_matter_file(path: Path) -> tuple[dict[str, Any], str]:
    """Parse YAML front matter from a Markdown file on disk."""
    text = path.read_text(encoding="utf-8")
    return parse_markdown_front_matter(text, file_path=str(path))


# ---------------------------------------------------------------------------
# Heading extraction (ignoring fenced code blocks)
# ---------------------------------------------------------------------------

_FENCED_CODE_RE = re.compile(r"^```", re.MULTILINE)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def extract_headings(body: str) -> list[tuple[int, str]]:
    """Extract Markdown headings from body, ignoring fenced code blocks.

    Returns a list of (level, text) tuples where level is 1-6.
    """
    parts = _FENCED_CODE_RE.split(body)
    outside_code = parts[::2]

    headings: list[tuple[int, str]] = []
    for segment in outside_code:
        for match in _HEADING_RE.finditer(segment):
            level = len(match.group(1))
            text = match.group(2).strip()
            headings.append((level, text))
    return headings


# ---------------------------------------------------------------------------
# Content directory loaders
# ---------------------------------------------------------------------------

def load_all_knowledge_points(content_dir: Path) -> list[dict[str, Any]]:
    """Load all knowledge point YAML files from content/knowledge/.

    YAML files may contain a single dict or a list of dicts.
    """
    knowledge_dir = content_dir / "knowledge"
    if not knowledge_dir.is_dir():
        return []
    results = []
    for yaml_file in sorted(knowledge_dir.glob("*.yaml")):
        data = safe_load_yaml_file(yaml_file)
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    item["__file__"] = str(yaml_file)
                    results.append(item)
        elif isinstance(data, dict):
            data["__file__"] = str(yaml_file)
            results.append(data)
    return results


def load_all_knowledge_cards(content_dir: Path) -> list[dict[str, Any]]:
    """Load all knowledge card Markdown files from content/cards/."""
    cards_dir = content_dir / "cards"
    if not cards_dir.is_dir():
        return []
    results = []
    for md_file in sorted(cards_dir.glob("*.md")):
        front_matter, body = parse_markdown_front_matter_file(md_file)
        front_matter["__body__"] = body
        front_matter["__file__"] = str(md_file)
        front_matter["__filename_stem__"] = md_file.stem
        results.append(front_matter)
    return results


def load_all_choice_questions(content_dir: Path) -> list[dict[str, Any]]:
    """Load all choice question YAML files from content/questions/choice/."""
    choice_dir = content_dir / "questions" / "choice"
    if not choice_dir.is_dir():
        return []
    results = []
    for yaml_file in sorted(choice_dir.glob("*.yaml")):
        data = safe_load_yaml_file(yaml_file)
        data["__file__"] = str(yaml_file)
        data["__filename_stem__"] = yaml_file.stem
        results.append(data)
    return results


def load_all_short_answer_questions(content_dir: Path) -> list[dict[str, Any]]:
    """Load all short answer question YAML files from content/questions/short_answer/."""
    sa_dir = content_dir / "questions" / "short_answer"
    if not sa_dir.is_dir():
        return []
    results = []
    for yaml_file in sorted(sa_dir.glob("*.yaml")):
        data = safe_load_yaml_file(yaml_file)
        data["__file__"] = str(yaml_file)
        data["__filename_stem__"] = yaml_file.stem
        results.append(data)
    return results


def load_all_sql_questions(content_dir: Path) -> list[dict[str, Any]]:
    """Load all SQL question YAML files from content/questions/sql/."""
    sql_dir = content_dir / "questions" / "sql"
    if not sql_dir.is_dir():
        return []
    results = []
    for yaml_file in sorted(sql_dir.glob("*.yaml")):
        data = safe_load_yaml_file(yaml_file)
        data["__file__"] = str(yaml_file)
        data["__filename_stem__"] = yaml_file.stem
        results.append(data)
    return results
