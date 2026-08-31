"""SQL Grading Service — Phase 8B.

Handles SQL Attempt AI raw assessment lifecycle.
Does NOT handle confirm / adjust / regrade / dispute (Phase 8C).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.attempt import AIAssessment, Attempt
from app.db.models.question import QuestionVersion
from app.llm.provider import (
    LLMInvalidResponseError,
    LLMProviderError,
    LLMTimeoutError,
)
from app.llm.schemas import ScoringCriterionInput, SQLGradingInput
from app.llm.service import LLMService


def grade_sql_attempt(
    db: Session,
    *,
    attempt: Attempt,
    llm_service: LLMService,
) -> dict[str, Any]:
    """Grade a SQL attempt using LLM.

    Transaction A (attempt creation) must already be committed.
    This function handles Transaction B: AI assessment + status update.

    Returns:
        {"assessment_id", "status", "raw_score", "max_score", ...}
    """
    # 1. Get QuestionVersion for the attempt's revision
    version = (
        db.query(QuestionVersion)
        .filter(
            QuestionVersion.question_id == attempt.question_id,
            QuestionVersion.revision == attempt.question_revision,
        )
        .first()
    )
    if not version:
        _handle_failure(db, attempt, "failed", "QuestionVersion not found")
        return _build_assessment_response(attempt)

    # 2. Build grading input
    payload = json.loads(version.payload_json)
    scoring_criteria = []
    for c in payload.get("scoring_criteria", []):
        scoring_criteria.append(ScoringCriterionInput(
            id=c["id"],
            description=c["description"],
            points=c["points"],
        ))

    max_score = sum(c.points for c in scoring_criteria)

    grading_input = SQLGradingInput(
        question_id=attempt.question_id,
        content=payload.get("content", ""),
        table_schema=payload.get("table_schema"),
        field_description=payload.get("field_description"),
        business_requirement=payload.get("business_requirement", ""),
        scoring_criteria=scoring_criteria,
        expected_sql=payload.get("expected_sql"),
        user_sql=attempt.user_answer,
        max_score=max_score,
    )

    # 3. Call LLM
    try:
        result, provider_response, prompt_version = llm_service.grade_sql(grading_input)
    except LLMTimeoutError as e:
        _handle_failure(db, attempt, "timeout", str(e))
        return _build_assessment_response(attempt)
    except LLMProviderError as e:
        _handle_failure(db, attempt, "failed", str(e))
        return _build_assessment_response(attempt)
    except LLMInvalidResponseError as e:
        _handle_failure(db, attempt, "invalid_response", str(e))
        return _build_assessment_response(attempt)
    except Exception as e:
        _handle_failure(db, attempt, "failed", str(e))
        return _build_assessment_response(attempt)

    # 4. Success: create AIAssessment
    assessment = AIAssessment(
        attempt_id=attempt.id,
        provider=provider_response.provider,
        model=provider_response.model,
        prompt_version=prompt_version,
        status="success",
        raw_score=result.score,
        max_score=result.max_score,
        result_json=json.dumps(result.model_dump(), ensure_ascii=False),
        input_tokens=provider_response.input_tokens,
        output_tokens=provider_response.output_tokens,
        latency_ms=provider_response.latency_ms,
    )
    db.add(assessment)

    # 5. Update Attempt → awaiting_confirmation
    attempt.status = "awaiting_confirmation"

    try:
        db.commit()
        db.refresh(assessment)
    except Exception:
        db.rollback()
        raise

    return _build_assessment_response(attempt, assessment)


def _handle_failure(
    db: Session,
    attempt: Attempt,
    status: str,
    error_message: str,
) -> None:
    """Create a failed AIAssessment and set Attempt to grading_failed."""
    assessment = AIAssessment(
        attempt_id=attempt.id,
        prompt_version="sql_grading_v1",
        status=status,
        error_message=error_message[:500],  # Truncate
    )
    db.add(assessment)
    attempt.status = "grading_failed"

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def _build_assessment_response(
    attempt: Attempt,
    assessment: AIAssessment | None = None,
) -> dict[str, Any]:
    """Build response dict from attempt and optional assessment."""
    # If no assessment provided, load the latest one
    if assessment is None:
        from sqlalchemy import desc
        # Need a fresh query since we're outside the session context
        # Use the attempt's session
        assessment = (
            attempt._sa_instance_state.session.query(AIAssessment)
            .filter(AIAssessment.attempt_id == attempt.id)
            .order_by(desc(AIAssessment.id))
            .first()
        )

    result: dict[str, Any] = {
        "attempt_id": attempt.id,
        "question_id": attempt.question_id,
        "question_revision": attempt.question_revision,
        "answer": attempt.user_answer,
        "status": attempt.status,
    }

    if assessment:
        assessment_data: dict[str, Any] = {
            "assessment_id": assessment.id,
            "status": assessment.status,
            "raw_score": assessment.raw_score,
            "max_score": assessment.max_score,
        }

        if assessment.result_json:
            parsed = json.loads(assessment.result_json)
            assessment_data["criteria"] = parsed.get("criteria", [])
            assessment_data["knowledge_analysis"] = parsed.get("knowledge_analysis", {})
            assessment_data["errors"] = parsed.get("errors", [])
            assessment_data["suggestions"] = parsed.get("suggestions", [])
            assessment_data["reasoning_summary"] = parsed.get("reasoning_summary", "")

        if assessment.error_message:
            assessment_data["error_message"] = assessment.error_message

        result["assessment"] = assessment_data

    # Include expected_sql for awaiting_confirmation
    if attempt.status == "awaiting_confirmation":
        version = (
            attempt._sa_instance_state.session.query(QuestionVersion)
            .filter(
                QuestionVersion.question_id == attempt.question_id,
                QuestionVersion.revision == attempt.question_revision,
            )
            .first()
        )
        if version:
            payload = json.loads(version.payload_json)
            result["expected_sql"] = payload.get("expected_sql")

    return result
