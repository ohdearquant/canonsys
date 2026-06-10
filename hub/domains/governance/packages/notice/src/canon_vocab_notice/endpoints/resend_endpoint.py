# Copyright (c) 2024-2026, HaiyangLi
# SPDX-License-Identifier: Apache-2.0
"""Resend email endpoint using lionpride Endpoint pattern."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from kron.services import Endpoint, EndpointConfig, NormalizedResponse

__all__ = (
    "ResendEndpoint",
    "ResendRequest",
    "create_resend_endpoint_config",
)


class ResendRequest(BaseModel):
    """Resend API request payload.

    https://resend.com/docs/api-reference/emails/send-email
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    from_: str = Field(..., alias="from")
    to: list[str]
    subject: str
    html: str
    text: str | None = None
    reply_to: str | None = None
    cc: list[str] | None = None
    bcc: list[str] | None = None
    tags: list[dict[str, str]] | None = None


def create_resend_endpoint_config(
    api_key_env: str = "CANON_RESEND_API_KEY",
    timeout: int = 30,
) -> dict:
    """Factory for Resend endpoint config.

    Args:
        api_key_env: Environment variable name for API key.
        timeout: Request timeout in seconds.

    Returns:
        Config dict for ResendEndpoint.
    """
    return {
        "provider": "resend",
        "name": "send_email",
        "base_url": "https://api.resend.com",
        "endpoint": "emails",
        "method": "POST",
        "api_key": api_key_env,
        "auth_type": "bearer",
        "timeout": timeout,
        "request_options": ResendRequest,
    }


class ResendEndpoint(Endpoint):
    """Resend email API endpoint.

    Usage:
        endpoint = ResendEndpoint()
        response = await endpoint.call({
            "from": "noreply@example.com",
            "to": ["user@example.com"],
            "subject": "Hello",
            "html": "<p>Hello World</p>",
        })
    """

    def __init__(
        self,
        config: dict | EndpointConfig | None = None,
        **kwargs,
    ):
        """Initialize with Resend config."""
        if config is None:
            config = create_resend_endpoint_config()
        elif isinstance(config, EndpointConfig):
            config = config.model_dump()

        super().__init__(config=config, **kwargs)

    def create_payload(
        self,
        request: dict | BaseModel,
        extra_headers: dict | None = None,
        **kwargs,
    ) -> tuple[dict, dict]:
        """Create Resend API payload.

        Args:
            request: Email request dict or ResendRequest model.
            extra_headers: Additional headers to include.
            **kwargs: Additional arguments merged into request.

        Returns:
            (payload_dict, headers_dict)
        """
        from kron.services.utilities.header_factory import HeaderFactory

        # Build headers
        headers = HeaderFactory.get_header(
            auth_type=self.config.auth_type,
            content_type=self.config.content_type,
            api_key=self.config._api_key,
            default_headers=self.config.default_headers,
        )
        if extra_headers:
            headers.update(extra_headers)

        # Convert request to dict
        if isinstance(request, BaseModel):
            payload = request.model_dump(exclude_none=True, by_alias=True)
        else:
            payload = dict(request)

        # Merge kwargs
        if kwargs:
            payload.update(kwargs)

        # Validate using request_options schema
        if self.config.request_options:
            valid_fields = set(self.config.request_options.model_fields.keys())
            # Also include aliases
            for field_info in self.config.request_options.model_fields.values():
                if field_info.alias:
                    valid_fields.add(field_info.alias)

            filtered = {k: v for k, v in payload.items() if k in valid_fields}
            # Validate
            self.config.request_options.model_validate(filtered)
            payload = filtered

        return payload, headers

    def normalize_response(self, raw_response: dict[str, Any]) -> NormalizedResponse:
        """Normalize Resend API response.

        Args:
            raw_response: Raw JSON response from Resend API.

        Returns:
            NormalizedResponse with:
            - status: "success" or "error"
            - data: Message ID
            - raw_response: Original response
            - metadata: None
        """
        # Resend returns {"id": "message_id"} on success
        if (msg_id := raw_response.get("id")) is not None:
            return NormalizedResponse(
                status="success",
                data={"message_id": msg_id},
                raw_response=raw_response,
            )

        # Error response
        error_msg = raw_response.get("message") or raw_response.get("error") or "Unknown error"
        return NormalizedResponse(
            status="error",
            error=error_msg,
            raw_response=raw_response,
        )
