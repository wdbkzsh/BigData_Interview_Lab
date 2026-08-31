"""LLM Provider interface and exceptions — Phase 8A.

Defines the vendor-agnostic provider contract.
Actual providers (OpenAI, Anthropic, etc.) will be added in Phase 8E.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


# ---------------------------------------------------------------------------
# Provider Response
# ---------------------------------------------------------------------------

@dataclass
class ProviderResponse:
    """Response from an LLM provider, including metadata."""

    content: str
    provider: Optional[str] = None
    model: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    latency_ms: Optional[int] = None


# ---------------------------------------------------------------------------
# Provider Protocol
# ---------------------------------------------------------------------------

class LLMProvider(Protocol):
    """Vendor-agnostic LLM provider interface."""

    def complete(self, prompt: str) -> ProviderResponse:
        """Send a prompt and return the model's response.

        Raises:
            LLMTimeoutError: request timed out
            LLMProviderError: provider-level failure
        """
        ...


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class LLMTimeoutError(Exception):
    """LLM request timed out."""


class LLMProviderError(Exception):
    """Provider-level failure (network, auth, rate limit, etc.)."""


class LLMInvalidResponseError(Exception):
    """LLM response could not be parsed or validated."""
