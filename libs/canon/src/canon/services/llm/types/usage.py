"""LLM usage tracking types.

For evidence and metering of LLM calls.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

__all__ = ["LLMUsage", "LLMUsageRecord"]


class LLMUsage(BaseModel):
    """Token usage from a single LLM call."""

    prompt_tokens: int = Field(default=0, description="Input tokens")
    completion_tokens: int = Field(default=0, description="Output tokens")
    total_tokens: int = Field(default=0, description="Total tokens")

    @classmethod
    def from_raw(cls, raw: dict[str, Any] | None) -> LLMUsage:
        """Parse from raw API response usage dict."""
        if not raw:
            return cls()
        return cls(
            prompt_tokens=raw.get("prompt_tokens", 0),
            completion_tokens=raw.get("completion_tokens", 0),
            total_tokens=raw.get("total_tokens", 0),
        )


class LLMUsageRecord(BaseModel):
    """Complete usage record for evidence emission.

    Links LLM call to vendor config for "same tool" compliance.
    """

    # Identifiers
    vendor_code: str = Field(description="Vendor code (e.g., openrouter)")
    service_name: str = Field(description="Service/model name")
    config_hash: str = Field(description="SHA-256 of config for provenance")

    # Request info
    operation: str = Field(description="Operation type: invoke, operate, chat")
    stage: str | None = Field(default=None, description="Workflow stage (l1, l2, etc.)")

    # Usage
    usage: LLMUsage = Field(default_factory=LLMUsage)

    # Timing
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    duration_ms: int = 0

    # Status
    success: bool = True
    error: str | None = None

    # Linking
    workflow_run_id: UUID | None = Field(
        default=None, description="Workflow run this call belongs to"
    )
