"""Local LLM client for redaction service.

Provides a simple iModel interface compatible with the redaction helpers.
Uses httpx to call OpenRouter's OpenAI-compatible API directly.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

__all__ = ["LLMResponse", "iModel"]


# Provider configurations (base_url, api_key_env)
_PROVIDER_CONFIG: dict[str, tuple[str, str]] = {
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY"),
}


@dataclass
class LLMResponseData:
    """Response data wrapper."""

    data: dict[str, Any] | None = None


@dataclass
class LLMResponse:
    """Response wrapper matching expected interface.

    Usage:
        response = await model.invoke(messages=[...])
        if response.response and response.response.data:
            data = response.response.data
    """

    response: LLMResponseData | None = None
    raw: dict[str, Any] | None = None


@dataclass
class iModel:
    """Simple LLM client for PII detection/redaction.

    Matches the lionpride iModel interface used by redaction helpers:
    - Constructor takes model and provider
    - Works as async context manager
    - invoke() returns response with response.response.data

    Example:
        async with iModel(model="google/gemini-2.5-flash", provider="openrouter") as llm:
            response = await llm.invoke(
                messages=[{"role": "user", "content": "Hello"}],
                response_format={"type": "json_object"},
            )
            data = response.response.data
    """

    model: str = "google/gemini-2.5-flash"
    provider: str = "openrouter"
    _client: Any = field(default=None, repr=False)

    def __post_init__(self):
        """Validate provider."""
        if self.provider not in _PROVIDER_CONFIG:
            raise ValueError(
                f"Unknown provider: {self.provider}. Supported: {list(_PROVIDER_CONFIG.keys())}"
            )

    @property
    def _base_url(self) -> str:
        return _PROVIDER_CONFIG[self.provider][0]

    @property
    def _api_key_env(self) -> str:
        return _PROVIDER_CONFIG[self.provider][1]

    @property
    def _api_key(self) -> str:
        key = os.getenv(self._api_key_env)
        if not key:
            raise ValueError(f"API key not found. Set {self._api_key_env} environment variable.")
        return key

    async def __aenter__(self) -> iModel:
        """Enter async context, create httpx client."""
        import httpx

        self._client = httpx.AsyncClient(timeout=120.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit async context, close client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        return False

    async def invoke(
        self,
        messages: list[dict[str, str]],
        response_format: dict[str, str] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Invoke LLM with messages.

        Args:
            messages: Chat messages [{"role": "...", "content": "..."}]
            response_format: Optional format spec (e.g., {"type": "json_object"})
            **kwargs: Additional API parameters

        Returns:
            LLMResponse with parsed data in response.response.data
        """
        if self._client is None:
            raise RuntimeError("iModel must be used as async context manager")

        # Build request payload
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            **kwargs,
        }
        if response_format:
            payload["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        # Add OpenRouter-specific headers
        if self.provider == "openrouter":
            headers["HTTP-Referer"] = "https://canon-core.local"
            headers["X-Title"] = "canon-core-redaction"

        url = f"{self._base_url}/chat/completions"

        response = await self._client.post(url, json=payload, headers=headers)

        if response.status_code != 200:
            raise RuntimeError(f"LLM request failed: {response.status_code} - {response.text}")

        raw_data = response.json()

        # Parse response
        parsed_data = self._parse_response(raw_data, response_format)

        return LLMResponse(
            response=LLMResponseData(data=parsed_data),
            raw=raw_data,
        )

    def _parse_response(
        self, raw: dict[str, Any], response_format: dict[str, str] | None
    ) -> dict[str, Any] | None:
        """Parse API response to extract data."""
        if "choices" not in raw or not raw["choices"]:
            return None

        content = raw["choices"][0].get("message", {}).get("content", "")

        # If JSON response requested, parse it
        if response_format and response_format.get("type") == "json_object":
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {"raw_content": content}

        return {"content": content}
