"""Mock LLM Provider — Phase 8A.

Deterministic mock for testing. Does not access network.
"""

from __future__ import annotations

import json
from typing import Optional

from app.llm.provider import (
    LLMInvalidResponseError,
    LLMProviderError,
    LLMTimeoutError,
    ProviderResponse,
)


class MockLLMProvider:
    """Mock provider that returns configurable responses."""

    def __init__(
        self,
        *,
        mode: str = "success",
        result: Optional[dict] = None,
    ) -> None:
        self._mode = mode
        self._result = result
        self.call_count = 0
        self.last_prompt: Optional[str] = None

    def complete(self, prompt: str) -> ProviderResponse:
        self.call_count += 1
        self.last_prompt = prompt

        if self._mode == "timeout":
            raise LLMTimeoutError("Mock timeout")

        if self._mode == "provider_error":
            raise LLMProviderError("Mock provider error")

        if self._mode == "invalid_response":
            return ProviderResponse(
                content="This is not valid JSON at all",
                provider="mock",
                model="mock-1",
                input_tokens=100,
                output_tokens=50,
                latency_ms=10,
            )

        # success mode
        if self._result is not None:
            content = json.dumps(self._result)
        else:
            content = json.dumps(_default_result())

        return ProviderResponse(
            content=content,
            provider="mock",
            model="mock-1",
            input_tokens=100,
            output_tokens=50,
            latency_ms=10,
        )


def _default_result() -> dict:
    """Default successful grading result."""
    return {
        "score": 8,
        "max_score": 10,
        "criteria": [
            {
                "id": "c1",
                "status": "matched",
                "score": 5,
                "max_score": 5,
                "feedback": "正确使用了所需功能",
            },
            {
                "id": "c2",
                "status": "partial",
                "score": 3,
                "max_score": 5,
                "feedback": "部分正确",
            },
        ],
        "knowledge_analysis": {
            "mastered": ["SQL基础"],
            "weak": ["窗口函数"],
            "missing": [],
        },
        "errors": [],
        "suggestions": ["可以考虑使用窗口函数优化"],
        "reasoning_summary": "用户SQL基本满足业务需求，窗口函数使用部分正确。",
    }
