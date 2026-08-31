"""LLM Provider Factory — Phase 8B.

Minimal factory for creating providers based on config.
Only 'mock' is currently implemented. Real providers come in Phase 8E.
"""

from __future__ import annotations

from app.core.config import settings
from app.llm.mock_provider import MockLLMProvider
from app.llm.provider import LLMProvider, LLMProviderError


def create_provider() -> LLMProvider:
    """Create an LLM provider based on settings.LLM_PROVIDER.

    Currently only 'mock' is supported.
    Unknown providers raise LLMProviderError.
    """
    provider_name = getattr(settings, "LLM_PROVIDER", "mock").lower()

    if provider_name == "mock":
        return MockLLMProvider(mode="success")

    raise LLMProviderError(
        f"Unknown LLM provider: '{provider_name}'. "
        f"Currently only 'mock' is supported. "
        f"Real providers will be added in Phase 8E."
    )
