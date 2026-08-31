"""LLM Provider Factory — Phase 8E1.

Creates providers based on settings.LLM_PROVIDER.
Supported: mock, openai_compatible.
"""

from __future__ import annotations

from app.core.config import settings
from app.llm.mock_provider import MockLLMProvider
from app.llm.openai_compatible_provider import OpenAICompatibleProvider
from app.llm.provider import LLMProvider, LLMProviderError


def create_provider() -> LLMProvider:
    """Create an LLM provider based on settings.

    Raises LLMProviderError if config is invalid.
    """
    provider_name = settings.LLM_PROVIDER.lower().strip()

    if provider_name == "mock":
        return MockLLMProvider(mode="success")

    if provider_name == "openai_compatible":
        if not settings.LLM_API_KEY:
            raise LLMProviderError("LLM_API_KEY is required for openai_compatible provider")
        if not settings.LLM_BASE_URL:
            raise LLMProviderError("LLM_BASE_URL is required for openai_compatible provider")
        if not settings.LLM_MODEL:
            raise LLMProviderError("LLM_MODEL is required for openai_compatible provider")

        return OpenAICompatibleProvider(
            base_url=settings.LLM_BASE_URL,
            model=settings.LLM_MODEL,
            api_key=settings.LLM_API_KEY,
            timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
        )

    raise LLMProviderError(
        f"Unknown LLM provider: '{provider_name}'. "
        f"Supported: 'mock', 'openai_compatible'."
    )