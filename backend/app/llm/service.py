"""LLM Service — Phase 8A.

Orchestrates prompt building, provider call, JSON parsing, and validation.
Does NOT write to database.
"""

from __future__ import annotations

import json
import re

from app.llm.provider import (
    LLMInvalidResponseError,
    LLMProvider,
    LLMProviderError,
    LLMTimeoutError,
    ProviderResponse,
)
from app.llm.prompts.sql_grading import PROMPT_VERSION, build_sql_grading_prompt
from app.llm.schemas import SQLGradingInput, SQLGradingResult


class LLMService:
    """Vendor-agnostic LLM service for SQL grading."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    def grade_sql(self, inp: SQLGradingInput) -> tuple[SQLGradingResult, ProviderResponse, str]:
        """Grade a SQL submission.

        Returns:
            (SQLGradingResult, ProviderResponse, prompt_version)

        Raises:
            LLMTimeoutError: provider timed out
            LLMProviderError: provider failure
            LLMInvalidResponseError: response couldn't be parsed/validated
        """
        # 1. Build prompt
        prompt = build_sql_grading_prompt(inp)

        # 2. Call provider
        try:
            provider_response = self._provider.complete(prompt)
        except LLMTimeoutError:
            raise
        except LLMProviderError:
            raise
        except Exception as e:
            raise LLMProviderError(f"Unexpected provider error: {e}") from e

        # 3. Parse JSON from response
        result_dict = _extract_json(provider_response.content)

        # 4. Validate with Pydantic
        try:
            result = SQLGradingResult(**result_dict)
        except Exception as e:
            raise LLMInvalidResponseError(f"Invalid grading result: {e}") from e

        # 5. Business validation
        _validate_against_input(result, inp)

        return result, provider_response, PROMPT_VERSION


def _extract_json(content: str) -> dict:
    """Extract JSON from LLM response content.

    Handles:
    - Direct JSON
    - Markdown fenced JSON (```json ... ```)
    """
    content = content.strip()

    # Try direct parse first
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown JSON fence
    fence_pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
    match = re.search(fence_pattern, content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    raise LLMInvalidResponseError("Could not extract valid JSON from LLM response")


def _validate_against_input(result: SQLGradingResult, inp: SQLGradingInput) -> None:
    """Validate result consistency with input."""
    # max_score must match
    if result.max_score != inp.max_score:
        raise LLMInvalidResponseError(
            f"result.max_score {result.max_score} != input.max_score {inp.max_score}"
        )

    # Score bounds
    if result.score > inp.max_score:
        raise LLMInvalidResponseError(
            f"score {result.score} exceeds max_score {inp.max_score}"
        )

    # Criteria: all input criteria must be present
    input_ids = {c.id for c in inp.scoring_criteria}
    result_ids = {c.id for c in result.criteria}

    missing = input_ids - result_ids
    if missing:
        raise LLMInvalidResponseError(f"Missing criteria: {missing}")

    unknown = result_ids - input_ids
    if unknown:
        raise LLMInvalidResponseError(f"Unknown criteria: {unknown}")

    # Duplicate IDs
    if len(result.criteria) != len(result_ids):
        raise LLMInvalidResponseError("Duplicate criterion IDs in result")

    # Criterion max_score must match input rubric
    input_max_map = {c.id: c.points for c in inp.scoring_criteria}
    for rc in result.criteria:
        expected_max = input_max_map.get(rc.id)
        if expected_max is not None and rc.max_score != expected_max:
            raise LLMInvalidResponseError(
                f"criterion '{rc.id}': max_score {rc.max_score} != rubric {expected_max}"
            )

    # Knowledge analysis: IDs must be from allowed set, no overlaps
    if inp.knowledge_points:
        allowed_kp_ids = {kp.id for kp in inp.knowledge_points}
        ka = result.knowledge_analysis
        all_kp_ids = set(ka.mastered) | set(ka.weak) | set(ka.missing)
        unknown_kps = all_kp_ids - allowed_kp_ids
        if unknown_kps:
            raise LLMInvalidResponseError(
                f"Unknown knowledge point IDs in analysis: {unknown_kps}"
            )
        # Check mutual exclusivity
        if set(ka.mastered) & set(ka.weak):
            raise LLMInvalidResponseError("KP appears in both mastered and weak")
        if set(ka.mastered) & set(ka.missing):
            raise LLMInvalidResponseError("KP appears in both mastered and missing")
        if set(ka.weak) & set(ka.missing):
            raise LLMInvalidResponseError("KP appears in both weak and missing")
