"""OpenAI-compatible LLM Provider — Phase 8E1.

Works with any API that follows the OpenAI Chat Completions protocol:
    POST {base_url}/chat/completions

Does NOT use vendor-specific SDKs. Uses httpx for HTTP.
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional

import httpx

from app.llm.provider import (
    LLMInvalidResponseError,
    LLMProviderError,
    LLMTimeoutError,
    ProviderResponse,
)


class OpenAICompatibleProvider:
    """Provider for OpenAI-compatible Chat Completions APIs."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str,
        timeout_seconds: int = 30,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._client = client  # Injectable for testing

    def complete(self, prompt: str) -> ProviderResponse:
        """Send a prompt and return the model's response."""
        client = self._client or httpx.Client(timeout=self._timeout_seconds)
        own_client = self._client is None

        url = f"{self._base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }

        start_time = time.monotonic()
        try:
            response = client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as e:
            raise LLMTimeoutError(f"LLM request timed out: {e}") from e
        except httpx.RequestError as e:
            raise LLMProviderError(f"LLM network error: {e}") from e
        finally:
            if own_client:
                client.close()

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        # HTTP errors
        if response.status_code != 200:
            error_text = response.text[:200] if response.text else ""
            raise LLMProviderError(
                f"LLM provider returned HTTP {response.status_code}: {error_text}"
            )

        # Parse response JSON
        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError) as e:
            raise LLMProviderError(f"LLM response is not valid JSON: {e}") from e

        # Extract content
        content = _extract_content(data)

        # Extract metadata
        model = data.get("model", self._model)
        usage = data.get("usage")
        input_tokens = usage.get("prompt_tokens") if usage else None
        output_tokens = usage.get("completion_tokens") if usage else None

        return ProviderResponse(
            content=content,
            provider="openai_compatible",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=elapsed_ms,
        )


def _extract_content(data: dict[str, Any]) -> str:
    """Extract message content from OpenAI-compatible response."""
    choices = data.get("choices")
    if not choices or not isinstance(choices, list) or len(choices) == 0:
        raise LLMProviderError("LLM response has no choices")

    message = choices[0].get("message")
    if not message or not isinstance(message, dict):
        raise LLMProviderError("LLM response choice has no message")

    content = message.get("content")
    if content is None or (isinstance(content, str) and content.strip() == ""):
        raise LLMProviderError("LLM response message content is empty")

    return content