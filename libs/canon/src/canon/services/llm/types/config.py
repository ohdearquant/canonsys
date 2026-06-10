"""LLM configuration types.

Defines model tiers and config structures for LLM service instantiation.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

__all__ = ["LLMConfig", "ModelTier"]


class ModelTier(str, Enum):
    """Model tier for cost/capability tradeoffs.

    Maps to vendor configs stored in DB.
    """

    FAST = "fast"  # Cheap, fast - gpt-4o-mini, gemini-flash
    SYNTHESIS = "synthesis"  # Mid-tier - gpt-4o, claude-sonnet
    REASONING = "reasoning"  # Expensive, capable - o1, claude-opus


class LLMConfig(BaseModel):
    """LLM configuration for iModel instantiation.

    Stored in VendorConfig.config_data and used to create
    lionagi iModel instances at runtime.
    """

    # Provider info
    provider: str = Field(description="Provider name: openrouter, openai, anthropic")
    model: str = Field(
        description="Model identifier (e.g., openai/gpt-4o-mini, claude-sonnet-4-20250514)"
    )

    # Model tier (for routing)
    tier: ModelTier = Field(
        default=ModelTier.FAST,
        description="Model tier for cost/capability routing",
    )

    # API config
    base_url: str | None = Field(
        default=None,
        description="Override base URL (for proxies like OpenRouter)",
    )
    api_key_env: str | None = Field(
        default=None,
        description="Environment variable name for API key",
    )

    # Generation params
    temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description="Sampling temperature",
    )
    max_tokens: int | None = Field(
        default=None,
        description="Max output tokens",
    )

    # Extra params passed to lionagi iModel
    extra_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional params for iModel constructor",
    )

    def to_imodel_kwargs(self) -> dict[str, Any]:
        """Convert to kwargs for lionagi iModel constructor."""
        kwargs: dict[str, Any] = {
            "provider": self.provider,
            "model": self.model,
            "temperature": self.temperature,
        }
        if self.base_url:
            kwargs["base_url"] = self.base_url
        if self.max_tokens:
            kwargs["max_tokens"] = self.max_tokens
        if self.extra_params:
            kwargs.update(self.extra_params)
        return kwargs
