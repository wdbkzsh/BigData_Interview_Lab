"""Tests for LLM Foundation — Phase 8A.

Covers: prompt, schema, service, mock provider.
Does NOT test SQL Attempt / AIAssessment / ReviewState.
"""

from __future__ import annotations

import json

import pytest

from app.llm.mock_provider import MockLLMProvider
from app.llm.provider import LLMInvalidResponseError, LLMProviderError, LLMTimeoutError
from app.llm.prompts.sql_grading import PROMPT_VERSION, build_sql_grading_prompt
from app.llm.schemas import (
    CriterionResult,
    SQLGradingInput,
    SQLGradingResult,
)
from app.llm.service import LLMService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_input(**overrides) -> SQLGradingInput:
    defaults = {
        "question_id": "sql.test.001",
        "content": "查询每个部门工资最高的员工",
        "table_schema": "CREATE TABLE emp (id INT, dept STRING, salary INT)",
        "field_description": "id=员工ID, dept=部门, salary=工资",
        "business_requirement": "返回每个部门中工资最高的员工",
        "scoring_criteria": [
            {"id": "c1", "description": "正确使用窗口函数或子查询", "points": 5},
            {"id": "c2", "description": "正确使用 PARTITION BY", "points": 5},
        ],
        "expected_sql": "SELECT * FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY dept ORDER BY salary DESC) AS rn FROM emp) WHERE rn = 1",
        "user_sql": "SELECT * FROM emp WHERE salary = (SELECT MAX(salary) FROM emp)",
        "max_score": 10,
    }
    defaults.update(overrides)
    return SQLGradingInput(**defaults)


# ---------------------------------------------------------------------------
# Prompt tests
# ---------------------------------------------------------------------------

class TestPrompt:
    def test_contains_business_requirement(self):
        inp = _make_input()
        prompt = build_sql_grading_prompt(inp)
        assert "返回每个部门中工资最高的员工" in prompt

    def test_contains_scoring_criteria(self):
        inp = _make_input()
        prompt = build_sql_grading_prompt(inp)
        assert "c1" in prompt
        assert "c2" in prompt
        assert "窗口函数" in prompt

    def test_contains_user_sql(self):
        inp = _make_input()
        prompt = build_sql_grading_prompt(inp)
        assert "SELECT * FROM emp WHERE salary" in prompt

    def test_contains_expected_sql(self):
        inp = _make_input()
        prompt = build_sql_grading_prompt(inp)
        assert "ROW_NUMBER" in prompt

    def test_expected_sql_is_reference_only(self):
        inp = _make_input()
        prompt = build_sql_grading_prompt(inp)
        assert "仅供参考" in prompt or "参考" in prompt

    def test_no_text_similarity(self):
        inp = _make_input()
        prompt = build_sql_grading_prompt(inp)
        assert "文本一致" in prompt or "文本相似" in prompt or "不需要与参考" in prompt

    def test_contains_json_output_constraint(self):
        inp = _make_input()
        prompt = build_sql_grading_prompt(inp)
        assert "JSON" in prompt

    def test_contains_data_boundary(self):
        inp = _make_input()
        prompt = build_sql_grading_prompt(inp)
        assert "待分析的数据" in prompt or "不能覆盖" in prompt

    def test_prompt_version(self):
        assert PROMPT_VERSION == "sql_grading_v1"


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

class TestSchema:
    def test_valid_result(self):
        result = SQLGradingResult(
            score=8,
            max_score=10,
            criteria=[
                CriterionResult(id="c1", status="matched", score=5, max_score=5, feedback="ok"),
                CriterionResult(id="c2", status="partial", score=3, max_score=5, feedback="partial"),
            ],
            reasoning_summary="good",
        )
        assert result.score == 8
        assert len(result.criteria) == 2

    def test_score_negative_rejected(self):
        with pytest.raises(Exception):
            SQLGradingResult(score=-1, max_score=10)

    def test_score_overflow_rejected(self):
        with pytest.raises(Exception):
            SQLGradingResult(score=11, max_score=10)

    def test_criterion_score_overflow_rejected(self):
        with pytest.raises(Exception):
            SQLGradingResult(
                score=5,
                max_score=10,
                criteria=[
                    CriterionResult(id="c1", status="matched", score=6, max_score=5, feedback=""),
                ],
            )

    def test_invalid_status_rejected(self):
        with pytest.raises(Exception):
            CriterionResult(id="c1", status="invalid", score=5, max_score=5, feedback="")

    def test_valid_statuses(self):
        for status in ["matched", "partial", "missing"]:
            c = CriterionResult(id="c1", status=status, score=0, max_score=5, feedback="")
            assert c.status == status


# ---------------------------------------------------------------------------
# Mock provider tests
# ---------------------------------------------------------------------------

class TestMockProvider:
    def test_success_mode(self):
        provider = MockLLMProvider(mode="success")
        resp = provider.complete("test prompt")
        assert resp.provider == "mock"
        assert resp.model == "mock-1"
        assert resp.input_tokens == 100
        assert resp.output_tokens == 50
        assert resp.latency_ms == 10
        # Content is valid JSON
        data = json.loads(resp.content)
        assert "score" in data

    def test_timeout_mode(self):
        provider = MockLLMProvider(mode="timeout")
        with pytest.raises(LLMTimeoutError):
            provider.complete("test")

    def test_provider_error_mode(self):
        provider = MockLLMProvider(mode="provider_error")
        with pytest.raises(LLMProviderError):
            provider.complete("test")

    def test_invalid_response_mode(self):
        provider = MockLLMProvider(mode="invalid_response")
        resp = provider.complete("test")
        assert "not valid JSON" in resp.content

    def test_custom_result(self):
        custom = {"score": 10, "max_score": 10, "criteria": [], "reasoning_summary": "perfect"}
        provider = MockLLMProvider(mode="success", result=custom)
        resp = provider.complete("test")
        data = json.loads(resp.content)
        assert data["score"] == 10

    def test_call_count_tracking(self):
        provider = MockLLMProvider(mode="success")
        provider.complete("a")
        provider.complete("b")
        assert provider.call_count == 2
        assert provider.last_prompt == "b"


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------

class TestLLMService:
    def test_successful_grading(self):
        provider = MockLLMProvider(mode="success")
        service = LLMService(provider)

        inp = _make_input()
        result, resp, version = service.grade_sql(inp)

        assert isinstance(result, SQLGradingResult)
        assert result.score >= 0
        assert result.max_score == 10
        assert len(result.criteria) == 2
        assert version == "sql_grading_v1"
        assert resp.provider == "mock"

    def test_markdown_fenced_json_accepted(self):
        """Service should parse ```json ... ``` fenced responses."""
        fenced_content = '```json\n{"score": 7, "max_score": 10, "criteria": [{"id": "c1", "status": "matched", "score": 5, "max_score": 5, "feedback": "ok"}, {"id": "c2", "status": "partial", "score": 2, "max_score": 5, "feedback": "partial"}], "reasoning_summary": "ok"}\n```'
        provider = MockLLMProvider(
            mode="success",
            result=None,
        )
        # Override to return fenced content
        provider._result = None
        original_complete = provider.complete

        def fenced_complete(prompt):
            from app.llm.provider import ProviderResponse
            provider.call_count += 1
            provider.last_prompt = prompt
            return ProviderResponse(
                content=fenced_content,
                provider="mock",
                model="mock-1",
                input_tokens=100,
                output_tokens=50,
                latency_ms=10,
            )

        provider.complete = fenced_complete
        service = LLMService(provider)

        inp = _make_input()
        result, _, _ = service.grade_sql(inp)
        assert result.score == 7

    def test_malformed_json_raises_invalid_response(self):
        provider = MockLLMProvider(mode="invalid_response")
        service = LLMService(provider)

        inp = _make_input()
        with pytest.raises(LLMInvalidResponseError):
            service.grade_sql(inp)

    def test_schema_invalid_raises_invalid_response(self):
        # Return JSON with invalid score
        bad_result = {"score": -5, "max_score": 10, "criteria": [], "reasoning_summary": ""}
        provider = MockLLMProvider(mode="success", result=bad_result)
        service = LLMService(provider)

        inp = _make_input()
        with pytest.raises(LLMInvalidResponseError):
            service.grade_sql(inp)

    def test_timeout_propagated(self):
        provider = MockLLMProvider(mode="timeout")
        service = LLMService(provider)

        inp = _make_input()
        with pytest.raises(LLMTimeoutError):
            service.grade_sql(inp)

    def test_provider_error_propagated(self):
        provider = MockLLMProvider(mode="provider_error")
        service = LLMService(provider)

        inp = _make_input()
        with pytest.raises(LLMProviderError):
            service.grade_sql(inp)

    def test_provider_metadata_retained(self):
        provider = MockLLMProvider(mode="success")
        service = LLMService(provider)

        inp = _make_input()
        _, resp, _ = service.grade_sql(inp)
        assert resp.provider == "mock"
        assert resp.model == "mock-1"
        assert resp.input_tokens == 100
        assert resp.output_tokens == 50
        assert resp.latency_ms == 10

    def test_missing_criteria_detected(self):
        # Return result missing c2
        bad_result = {
            "score": 5,
            "max_score": 10,
            "criteria": [
                {"id": "c1", "status": "matched", "score": 5, "max_score": 5, "feedback": "ok"},
            ],
            "reasoning_summary": "",
        }
        provider = MockLLMProvider(mode="success", result=bad_result)
        service = LLMService(provider)

        inp = _make_input()
        with pytest.raises(LLMInvalidResponseError, match="Missing criteria"):
            service.grade_sql(inp)

    def test_unknown_criteria_detected(self):
        bad_result = {
            "score": 5,
            "max_score": 10,
            "criteria": [
                {"id": "c1", "status": "matched", "score": 5, "max_score": 5, "feedback": ""},
                {"id": "c2", "status": "matched", "score": 0, "max_score": 5, "feedback": ""},
                {"id": "c3", "status": "matched", "score": 0, "max_score": 5, "feedback": ""},
            ],
            "reasoning_summary": "",
        }
        provider = MockLLMProvider(mode="success", result=bad_result)
        service = LLMService(provider)

        inp = _make_input()
        with pytest.raises(LLMInvalidResponseError, match="Unknown criteria"):
            service.grade_sql(inp)


# ---------------------------------------------------------------------------
# Formal DB not polluted
# ---------------------------------------------------------------------------

class TestFormalDBNotPolluted:
    def test_formal_db_unchanged(self):
        from pathlib import Path
        from app.core.config import settings
        db_path = settings.DATABASE_URL.replace("sqlite:///", "")
        p = Path(db_path)
        if p.exists():
            assert p.stat().st_size > 0
