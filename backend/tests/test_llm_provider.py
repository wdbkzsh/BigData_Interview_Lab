"""Tests for LLM Provider — Phase 8E1.

Tests OpenAICompatibleProvider with httpx MockTransport.
No real network calls.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.llm.factory import create_provider
from app.llm.mock_provider import MockLLMProvider
from app.llm.openai_compatible_provider import OpenAICompatibleProvider
from app.llm.provider import (
    LLMInvalidResponseError,
    LLMProviderError,
    LLMTimeoutError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_transport(status_code: int = 200, body: dict | None = None):
    """Create an httpx MockTransport."""
    if body is None:
        body = {
            "model": "test-model",
            "choices": [{"message": {"content": '{"score": 8, "max_score": 10}'}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=body)

    return httpx.MockTransport(handler)


def _make_timeout_transport():
    """Create a transport that always times out."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Mock timeout")

    return httpx.MockTransport(handler)


def _make_provider(transport) -> OpenAICompatibleProvider:
    """Create a provider with a mock transport."""
    client = httpx.Client(transport=transport)
    return OpenAICompatibleProvider(
        base_url="https://fake.api.com/v1",
        model="test-model",
        api_key="test-key",
        timeout_seconds=5,
        client=client,
    )


# ---------------------------------------------------------------------------
# Provider Tests
# ---------------------------------------------------------------------------

class TestOpenAICompatibleProvider:
    def test_success(self):
        transport = _make_mock_transport()
        provider = _make_provider(transport)

        resp = provider.complete("test prompt")

        assert resp.content == '{"score": 8, "max_score": 10}'
        assert resp.provider == "openai_compatible"
        assert resp.model == "test-model"
        assert resp.input_tokens == 100
        assert resp.output_tokens == 50
        assert resp.latency_ms is not None
        assert resp.latency_ms >= 0

    def test_missing_usage(self):
        body = {
            "model": "test-model",
            "choices": [{"message": {"content": "hello"}}],
        }
        transport = _make_mock_transport(body=body)
        provider = _make_provider(transport)

        resp = provider.complete("test")

        assert resp.content == "hello"
        assert resp.input_tokens is None
        assert resp.output_tokens is None

    def test_timeout(self):
        transport = _make_timeout_transport()
        provider = _make_provider(transport)

        with pytest.raises(LLMTimeoutError):
            provider.complete("test")

    def test_401(self):
        body = {"error": "Unauthorized"}
        transport = _make_mock_transport(status_code=401, body=body)
        provider = _make_provider(transport)

        with pytest.raises(LLMProviderError, match="401"):
            provider.complete("test")

    def test_429(self):
        body = {"error": "Rate limited"}
        transport = _make_mock_transport(status_code=429, body=body)
        provider = _make_provider(transport)

        with pytest.raises(LLMProviderError, match="429"):
            provider.complete("test")

    def test_500(self):
        body = {"error": "Internal error"}
        transport = _make_mock_transport(status_code=500, body=body)
        provider = _make_provider(transport)

        with pytest.raises(LLMProviderError, match="500"):
            provider.complete("test")

    def test_invalid_json_response(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<html>error</html>")

        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport)
        provider = OpenAICompatibleProvider(
            base_url="https://fake.api.com/v1",
            model="test-model",
            api_key="test-key",
            client=client,
        )

        with pytest.raises(LLMProviderError, match="not valid JSON"):
            provider.complete("test")

    def test_missing_choices(self):
        body = {"model": "test-model"}
        transport = _make_mock_transport(body=body)
        provider = _make_provider(transport)

        with pytest.raises(LLMProviderError, match="no choices"):
            provider.complete("test")

    def test_empty_choices(self):
        body = {"model": "test-model", "choices": []}
        transport = _make_mock_transport(body=body)
        provider = _make_provider(transport)

        with pytest.raises(LLMProviderError, match="no choices"):
            provider.complete("test")

    def test_missing_message(self):
        body = {"model": "test-model", "choices": [{"index": 0}]}
        transport = _make_mock_transport(body=body)
        provider = _make_provider(transport)

        with pytest.raises(LLMProviderError, match="no message"):
            provider.complete("test")

    def test_empty_content(self):
        body = {
            "model": "test-model",
            "choices": [{"message": {"content": ""}}],
        }
        transport = _make_mock_transport(body=body)
        provider = _make_provider(transport)

        with pytest.raises(LLMProviderError, match="empty"):
            provider.complete("test")

    def test_none_content(self):
        body = {
            "model": "test-model",
            "choices": [{"message": {"content": None}}],
        }
        transport = _make_mock_transport(body=body)
        provider = _make_provider(transport)

        with pytest.raises(LLMProviderError, match="empty"):
            provider.complete("test")

    def test_request_payload(self):
        """Verify the request sent to the API."""
        captured_request = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_request["url"] = str(request.url)
            captured_request["body"] = json.loads(request.content)
            return httpx.Response(200, json={
                "model": "test-model",
                "choices": [{"message": {"content": "ok"}}],
            })

        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport)
        provider = OpenAICompatibleProvider(
            base_url="https://fake.api.com/v1",
            model="my-model",
            api_key="my-key",
            client=client,
        )

        provider.complete("hello world")

        assert "/chat/completions" in captured_request["url"]
        assert captured_request["body"]["model"] == "my-model"
        assert captured_request["body"]["temperature"] == 0
        assert captured_request["body"]["messages"][0]["role"] == "user"
        assert captured_request["body"]["messages"][0]["content"] == "hello world"

    def test_response_model_used(self):
        """If response has model field, use it."""
        body = {
            "model": "actual-model-from-response",
            "choices": [{"message": {"content": "ok"}}],
        }
        transport = _make_mock_transport(body=body)
        provider = _make_provider(transport)

        resp = provider.complete("test")
        assert resp.model == "actual-model-from-response"


# ---------------------------------------------------------------------------
# Factory Tests
# ---------------------------------------------------------------------------

class TestFactory:
    def test_mock_provider(self):
        from unittest.mock import patch
        with patch("app.llm.factory.settings") as mock_settings:
            mock_settings.LLM_PROVIDER = "mock"
            provider = create_provider()
            assert isinstance(provider, MockLLMProvider)

    def test_openai_compatible_valid(self):
        from unittest.mock import patch
        with patch("app.llm.factory.settings") as mock_settings:
            mock_settings.LLM_PROVIDER = "openai_compatible"
            mock_settings.LLM_API_KEY = "test-key"
            mock_settings.LLM_BASE_URL = "https://api.test.com/v1"
            mock_settings.LLM_MODEL = "test-model"
            mock_settings.LLM_TIMEOUT_SECONDS = 30
            provider = create_provider()
            assert isinstance(provider, OpenAICompatibleProvider)

    def test_openai_compatible_missing_api_key(self):
        from unittest.mock import patch
        with patch("app.llm.factory.settings") as mock_settings:
            mock_settings.LLM_PROVIDER = "openai_compatible"
            mock_settings.LLM_API_KEY = ""
            mock_settings.LLM_BASE_URL = "https://api.test.com/v1"
            mock_settings.LLM_MODEL = "test-model"
            with pytest.raises(LLMProviderError, match="LLM_API_KEY"):
                create_provider()

    def test_openai_compatible_missing_base_url(self):
        from unittest.mock import patch
        with patch("app.llm.factory.settings") as mock_settings:
            mock_settings.LLM_PROVIDER = "openai_compatible"
            mock_settings.LLM_API_KEY = "test-key"
            mock_settings.LLM_BASE_URL = ""
            mock_settings.LLM_MODEL = "test-model"
            with pytest.raises(LLMProviderError, match="LLM_BASE_URL"):
                create_provider()

    def test_openai_compatible_missing_model(self):
        from unittest.mock import patch
        with patch("app.llm.factory.settings") as mock_settings:
            mock_settings.LLM_PROVIDER = "openai_compatible"
            mock_settings.LLM_API_KEY = "test-key"
            mock_settings.LLM_BASE_URL = "https://api.test.com/v1"
            mock_settings.LLM_MODEL = ""
            with pytest.raises(LLMProviderError, match="LLM_MODEL"):
                create_provider()

    def test_unknown_provider(self):
        from unittest.mock import patch
        with patch("app.llm.factory.settings") as mock_settings:
            mock_settings.LLM_PROVIDER = "unknown_vendor"
            with pytest.raises(LLMProviderError, match="Unknown LLM provider"):
                create_provider()


# ---------------------------------------------------------------------------
# Integration Contract Test
# ---------------------------------------------------------------------------

class TestIntegrationContract:
    def test_llm_service_with_openai_provider(self):
        """Verify LLMService works with OpenAICompatibleProvider via mock HTTP."""
        from app.llm.schemas import SQLGradingInput, ScoringCriterionInput
        from app.llm.service import LLMService

        grading_result = {
            "score": 8,
            "max_score": 10,
            "criteria": [
                {"id": "c1", "status": "matched", "score": 5, "max_score": 5, "feedback": "ok"},
                {"id": "c2", "status": "partial", "score": 3, "max_score": 5, "feedback": "partial"},
            ],
            "knowledge_analysis": {"mastered": [], "weak": [], "missing": []},
            "errors": [],
            "suggestions": [],
            "reasoning_summary": "good",
        }

        body = {
            "model": "test-model",
            "choices": [{"message": {"content": json.dumps(grading_result)}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }
        transport = _make_mock_transport(body=body)
        provider = _make_provider(transport)
        service = LLMService(provider)

        inp = SQLGradingInput(
            question_id="test",
            content="test query",
            business_requirement="test requirement",
            scoring_criteria=[
                ScoringCriterionInput(id="c1", description="criterion 1", points=5),
                ScoringCriterionInput(id="c2", description="criterion 2", points=5),
            ],
            user_sql="SELECT 1",
            max_score=10,
        )

        result, resp, version = service.grade_sql(inp)

        assert result.score == 8
        assert result.max_score == 10
        assert len(result.criteria) == 2
        assert resp.provider == "openai_compatible"
        assert resp.model == "test-model"
        assert version == "sql_grading_v2"