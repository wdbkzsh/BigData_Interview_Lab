"""Content importer — syncs validated content/ files into SQLite."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.content.loader import (
    build_card_content_json,
    load_all_choice_questions,
    load_all_knowledge_cards,
    load_all_knowledge_points,
    load_all_short_answer_questions,
    load_all_sql_questions,
)
from app.content.validator import ValidationResult, validate_all, _flatten_knowledge_points
from app.db.models.knowledge import KnowledgeCard, KnowledgeCardVersion, KnowledgePoint
from app.db.models.question import (
    Question,
    QuestionRelatedKnowledgePoint,
    QuestionVersion,
)


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------


class ContentImportError(Exception):
    """Base import error."""


class ContentImportValidationError(ContentImportError):
    """Validator failed — no DB writes allowed."""

    def __init__(self, issues: list) -> None:
        self.issues = issues
        super().__init__(f"Content validation failed with {len(issues)} issues")


class StableBindingError(ContentImportError):
    """Stable binding (question_type, primary_kp, KP tree) changed."""

    def __init__(
        self,
        entity_type: str,
        entity_id: str,
        field: str,
        old_value: str,
        new_value: str,
        source_path: str = "",
    ) -> None:
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.field = field
        self.old_value = old_value
        self.new_value = new_value
        self.source_path = source_path
        super().__init__(
            f"{entity_type} '{entity_id}': {field} cannot change "
            f"from '{old_value}' to '{new_value}'"
            + (f" (source: {source_path})" if source_path else "")
        )


# ---------------------------------------------------------------------------
# ContentImportResult
# ---------------------------------------------------------------------------


@dataclass
class ContentImportResult:
    """Structured result of a content import."""

    knowledge_points_inserted: int = 0
    knowledge_points_updated: int = 0
    knowledge_points_deactivated: int = 0
    cards_inserted: int = 0
    cards_updated: int = 0
    card_versions_created: int = 0
    cards_deactivated: int = 0
    questions_inserted: int = 0
    questions_updated: int = 0
    question_versions_created: int = 0
    questions_deactivated: int = 0
    relations_created: int = 0
    relations_deleted: int = 0
    unchanged: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_line_endings(text: str) -> str:
    """Normalize \\r\\n and \\r to \\n."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _relative_source_path(abs_path: str, content_dir: Path) -> str:
    """Convert absolute file path to stable repo-relative path starting with content/."""
    p = Path(abs_path)
    try:
        relative = p.relative_to(content_dir)
        return (Path("content") / relative).as_posix()
    except ValueError:
        return (Path("content") / p.name).as_posix()


def _compute_card_hash(title: str, body: str) -> str:
    """SHA-256 hash of normalized title + body."""
    norm_title = _normalize_line_endings(title)
    norm_body = _normalize_line_endings(body)
    canonical = f"{norm_title}\n{norm_body}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _serialize_tags(tags: list[str]) -> str:
    """Serialize tags list to deterministic JSON string."""
    return json.dumps(tags, ensure_ascii=False, separators=(",", ":"))


# Question version-field mapping
_CHOICE_VERSION_FIELDS = ("content", "options", "correct_answer", "explanation")
_QA_VERSION_FIELDS = ("content", "reference_answer", "explanation")
_SQL_VERSION_FIELDS = (
    "content",
    "table_schema",
    "field_description",
    "business_requirement",
    "expected_sql",
    "scoring_criteria",
)


def _build_question_payload(qtype: str, data: dict[str, Any]) -> dict[str, Any]:
    """Build the version payload dict for a question."""
    if qtype == "choice":
        return {k: data[k] for k in _CHOICE_VERSION_FIELDS}
    elif qtype == "short_answer":
        return {k: data[k] for k in _QA_VERSION_FIELDS}
    elif qtype == "sql":
        payload = {k: data.get(k) for k in _SQL_VERSION_FIELDS}
        # Auto-compute max_score from scoring_criteria
        criteria = payload.get("scoring_criteria") or []
        payload["max_score"] = sum(c["points"] for c in criteria if isinstance(c, dict))
        return payload
    raise ValueError(f"Unknown question type: {qtype}")


def _compute_question_hash(payload: dict[str, Any]) -> str:
    """SHA-256 hash of canonical JSON payload."""
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _payload_to_json(payload: dict[str, Any]) -> str:
    """Serialize payload to canonical JSON string."""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Knowledge Point import
# ---------------------------------------------------------------------------


def _import_knowledge_points(
    content_dir: Path,
    db: Session,
    result: ContentImportResult,
) -> set[str]:
    """Import knowledge points. Returns set of imported KP IDs."""
    raw_points = load_all_knowledge_points(content_dir)
    flat_nodes = _flatten_knowledge_points(raw_points)

    imported_ids: set[str] = set()

    for node in flat_nodes:
        node_id = node["id"]
        imported_ids.add(node_id)

        existing = db.get(KnowledgePoint, node_id)
        if existing is None:
            # INSERT
            db.add(KnowledgePoint(
                id=node_id,
                parent_id=node["parent_id"],
                name=node["name"],
                level=node["level"],
                description=node.get("description"),
                sort_order=node.get("sort_order", 0),
                is_active=node.get("is_active", True),
            ))
            result.knowledge_points_inserted += 1
        else:
            # Check tree structure binding
            if existing.parent_id != node["parent_id"]:
                source_path = _relative_source_path(node.get("__file__", ""), content_dir)
                raise StableBindingError(
                    "knowledge_point", node_id, "parent_id",
                    str(existing.parent_id), str(node["parent_id"]),
                    source_path,
                )
            if existing.level != node["level"]:
                source_path = _relative_source_path(node.get("__file__", ""), content_dir)
                raise StableBindingError(
                    "knowledge_point", node_id, "level",
                    str(existing.level), str(node["level"]),
                    source_path,
                )

            # Track if anything actually changed
            changed = False
            if existing.name != node["name"]:
                existing.name = node["name"]
                changed = True
            if existing.description != node.get("description"):
                existing.description = node.get("description")
                changed = True
            if existing.sort_order != node.get("sort_order", 0):
                existing.sort_order = node.get("sort_order", 0)
                changed = True
            if existing.is_active != node.get("is_active", True):
                existing.is_active = node.get("is_active", True)
                changed = True

            if changed:
                result.knowledge_points_updated += 1
            else:
                result.unchanged += 1

    # Deactivate KPs that disappeared from content
    for existing in db.query(KnowledgePoint).all():
        if existing.id not in imported_ids and existing.is_active:
            existing.is_active = False
            result.knowledge_points_deactivated += 1

    return imported_ids


# ---------------------------------------------------------------------------
# Knowledge Card import
# ---------------------------------------------------------------------------


def _import_knowledge_cards(
    content_dir: Path,
    db: Session,
    kp_ids: set[str],
    result: ContentImportResult,
) -> None:
    """Import knowledge cards and versions."""
    cards = load_all_knowledge_cards(content_dir)

    imported_card_ids: set[str] = set()

    for card_data in cards:
        file_path = card_data.get("__file__", "unknown")
        fm_title = card_data.get("title", "")
        fm_kp_id = card_data.get("knowledge_point_id", "")
        fm_is_active = card_data.get("is_active", True)
        body = card_data.get("__body__", "")

        card_id = f"card.{fm_kp_id}"
        imported_card_ids.add(card_id)

        source_hash = _compute_card_hash(fm_title, body)
        source_path = _relative_source_path(file_path, content_dir)
        content_json = build_card_content_json(fm_title, body)
        content_json_str = json.dumps(
            content_json, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )

        existing_card = db.get(KnowledgeCard, card_id)

        if existing_card is None:
            # New card
            db.add(KnowledgeCard(
                id=card_id,
                knowledge_point_id=fm_kp_id,
                current_revision=1,
                is_active=fm_is_active,
            ))
            db.add(KnowledgeCardVersion(
                card_id=card_id,
                revision=1,
                content_json=content_json_str,
                source_path=source_path,
                source_hash=source_hash,
            ))
            result.cards_inserted += 1
            result.card_versions_created += 1
        else:
            # Card identity is card_id = card.{knowledge_point_id}
            # If knowledge_point_id changed, it's a new card identity
            # (handled by card_id being different → treated as new above)

            # Check is_active change
            if existing_card.is_active != fm_is_active:
                existing_card.is_active = fm_is_active
                result.cards_updated += 1

            # Check content change
            latest_version = db.get(
                KnowledgeCardVersion, (card_id, existing_card.current_revision)
            )
            if latest_version is None or latest_version.source_hash != source_hash:
                new_rev = existing_card.current_revision + 1
                db.add(KnowledgeCardVersion(
                    card_id=card_id,
                    revision=new_rev,
                    content_json=content_json_str,
                    source_path=source_path,
                    source_hash=source_hash,
                ))
                existing_card.current_revision = new_rev
                result.card_versions_created += 1
                if existing_card.is_active == fm_is_active:
                    # Only count as updated if not already counted from is_active change
                    result.cards_updated += 1
            elif existing_card.is_active == fm_is_active:
                # Nothing changed
                result.unchanged += 1

    # Deactivate cards that disappeared from content
    for existing in db.query(KnowledgeCard).all():
        if existing.id not in imported_card_ids and existing.is_active:
            existing.is_active = False
            result.cards_deactivated += 1


# ---------------------------------------------------------------------------
# Question import
# ---------------------------------------------------------------------------

# Map question_type to version field names
_VERSION_FIELDS_MAP: dict[str, tuple[str, ...]] = {
    "choice": _CHOICE_VERSION_FIELDS,
    "short_answer": _QA_VERSION_FIELDS,
    "sql": _SQL_VERSION_FIELDS,
}


def _import_questions(
    content_dir: Path,
    db: Session,
    kp_ids: set[str],
    result: ContentImportResult,
) -> None:
    """Import all question types (choice, short_answer, sql)."""
    # Collect all questions by type
    all_questions: list[tuple[str, dict[str, Any]]] = []

    for q_data in load_all_choice_questions(content_dir):
        all_questions.append(("choice", q_data))
    for q_data in load_all_short_answer_questions(content_dir):
        all_questions.append(("short_answer", q_data))
    for q_data in load_all_sql_questions(content_dir):
        all_questions.append(("sql", q_data))

    imported_qids: set[str] = set()

    for qtype, q_data in all_questions:
        qid = q_data.get("id", "")
        file_path = q_data.get("__file__", "unknown")
        imported_qids.add(qid)

        # Build version payload and hash
        payload = _build_question_payload(qtype, q_data)
        source_hash = _compute_question_hash(payload)
        source_path = _relative_source_path(file_path, content_dir)

        existing_q = db.get(Question, qid)

        if existing_q is None:
            # New question
            db.add(Question(
                id=qid,
                question_type=qtype,
                primary_knowledge_point_id=q_data["primary_knowledge_point_id"],
                title=q_data.get("title"),
                difficulty=q_data["difficulty"],
                tags_json=_serialize_tags(q_data.get("tags", [])),
                current_revision=1,
                is_active=q_data.get("is_active", True),
            ))
            db.add(QuestionVersion(
                question_id=qid,
                revision=1,
                payload_json=_payload_to_json(payload),
                source_path=source_path,
                source_hash=source_hash,
            ))
            result.questions_inserted += 1
            result.question_versions_created += 1
        else:
            # Stable binding checks
            if existing_q.question_type != qtype:
                raise StableBindingError(
                    "question", qid, "question_type",
                    existing_q.question_type, qtype, source_path,
                )
            if existing_q.primary_knowledge_point_id != q_data["primary_knowledge_point_id"]:
                raise StableBindingError(
                    "question", qid, "primary_knowledge_point_id",
                    existing_q.primary_knowledge_point_id,
                    q_data["primary_knowledge_point_id"],
                    source_path,
                )

            # Metadata update (no revision)
            meta_changed = False
            if existing_q.title != q_data.get("title"):
                existing_q.title = q_data.get("title")
                meta_changed = True
            if existing_q.difficulty != q_data["difficulty"]:
                existing_q.difficulty = q_data["difficulty"]
                meta_changed = True
            new_tags = _serialize_tags(q_data.get("tags", []))
            if existing_q.tags_json != new_tags:
                existing_q.tags_json = new_tags
                meta_changed = True
            if existing_q.is_active != q_data.get("is_active", True):
                existing_q.is_active = q_data.get("is_active", True)
                meta_changed = True

            # Content change check
            latest_version = db.get(
                QuestionVersion, (qid, existing_q.current_revision)
            )
            if latest_version is None or latest_version.source_hash != source_hash:
                new_rev = existing_q.current_revision + 1
                db.add(QuestionVersion(
                    question_id=qid,
                    revision=new_rev,
                    payload_json=_payload_to_json(payload),
                    source_path=source_path,
                    source_hash=source_hash,
                ))
                existing_q.current_revision = new_rev
                result.question_versions_created += 1
                result.questions_updated += 1
            elif meta_changed:
                result.questions_updated += 1
            else:
                result.unchanged += 1

        # Sync related_knowledge_points
        _sync_related_knowledge_points(db, qid, q_data, result)

    # Deactivate questions that disappeared from content
    for existing in db.query(Question).all():
        if existing.id not in imported_qids and existing.is_active:
            existing.is_active = False
            result.questions_deactivated += 1


# ---------------------------------------------------------------------------
# Related knowledge points sync
# ---------------------------------------------------------------------------


def _sync_related_knowledge_points(
    db: Session,
    question_id: str,
    q_data: dict[str, Any],
    result: ContentImportResult,
) -> None:
    """Sync question_related_knowledge_point for a single question."""
    yaml_related = set(q_data.get("related_knowledge_points", []))
    db_related = {
        r.knowledge_point_id
        for r in db.query(QuestionRelatedKnowledgePoint)
        .filter_by(question_id=question_id)
        .all()
    }

    # Add new relations
    for kp_id in yaml_related - db_related:
        db.add(QuestionRelatedKnowledgePoint(
            question_id=question_id,
            knowledge_point_id=kp_id,
            # weight uses DB default 1.0
        ))
        result.relations_created += 1

    # Remove stale relations
    for kp_id in db_related - yaml_related:
        rel = (
            db.query(QuestionRelatedKnowledgePoint)
            .filter_by(question_id=question_id, knowledge_point_id=kp_id)
            .first()
        )
        if rel:
            db.delete(rel)
            result.relations_deleted += 1


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def import_content(content_dir: Path, db: Session) -> ContentImportResult:
    """Import validated content into the database.

    Validates first, then imports all content within a single transaction.
    The caller does NOT need to commit — this function handles atomicity.

    Requires a fresh Session without an active transaction.

    Raises:
        ContentImportValidationError: if content validation fails
        StableBindingError: if a stable binding changes
        ContentImportError: if the Session already has an active transaction
    """
    # 1. Validate
    vr = validate_all(content_dir)
    if not vr.is_valid:
        raise ContentImportValidationError(vr.issues)

    # 2. Require fresh Session — never touch the caller's existing transaction
    if db.in_transaction():
        raise ContentImportError(
            "import_content requires a fresh Session without an active transaction"
        )

    # 3. Import within a transaction
    result = ContentImportResult()

    with db.begin():
        kp_ids = _import_knowledge_points(content_dir, db, result)
        _import_knowledge_cards(content_dir, db, kp_ids, result)
        _import_questions(content_dir, db, kp_ids, result)

    return result
