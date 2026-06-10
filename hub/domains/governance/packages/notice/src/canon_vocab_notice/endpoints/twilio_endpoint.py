# Copyright (c) 2024-2026, HaiyangLi
# SPDX-License-Identifier: Apache-2.0
"""Twilio SMS endpoint using lionpride Endpoint pattern."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from kron.services import Endpoint, EndpointConfig, NormalizedResponse

__all__ = (
    "SMSRequest",
    "TwilioEndpoint",
    "create_twilio_config",
)


class SMSRequest(BaseModel):
    """Twilio SMS API request.

    https://www.twilio.com/docs/sms/api/message-resource
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    to: str = Field(..., alias="To")
    from_: str = Field(..., alias="From")
    body: str = Field(..., alias="Body")
    media_url: list[str] | None = Field(None, alias="MediaUrl")


def create_twilio_config(
    account_sid_env: str = "CANON_TWILIO_ACCOUNT_SID",
    auth_token_env: str = "CANON_TWILIO_AUTH_TOKEN",
    timeout: int = 30,
) -> dict:
    """Factory for Twilio endpoint config.

    Args:
        account_sid_env: Environment variable name for Account SID.
        auth_token_env: Environment variable name for Auth Token.
        timeout: Request timeout in seconds.

    Returns:
        Config dict for TwilioEndpoint.
    """
    import os

    account_sid = os.getenv(account_sid_env, "")

    return {
        "provider": "twilio",
        "name": "messages",
        "base_url": "https://api.twilio.com/2010-04-01",
        "endpoint": f"Accounts/{account_sid}/Messages.json",
        "method": "POST",
        "content_type": "application/x-www-form-urlencoded",
        "auth_type": "basic",
        "api_key": account_sid_env,  # Account SID as username
        "timeout": timeout,
        "request_options": SMSRequest,
        "client_kwargs": {"auth_token_env": auth_token_env},  # Store for later
    }


class TwilioEndpoint(Endpoint):
    """Twilio SMS API endpoint.

    Twilio uses form-data and basic auth, so we override _call_http.

    Usage:
        endpoint = TwilioEndpoint()
        response = await endpoint.call({
            "To": "+15551234567",
            "From": "+15559876543",
            "Body": "Hello!",
        })
        message_sid = response.data["message_sid"]
    """

    def __init__(
        self,
        config: dict | EndpointConfig | None = None,
        account_sid: str | None = None,
        auth_token: str | None = None,
        **kwargs,
    ):
        """Initialize with Twilio config."""
        import os

        if config is None:
            config = create_twilio_config()
        elif isinstance(config, EndpointConfig):
            config = config.model_dump()

        # Store auth credentials for basic auth
        self._account_sid = account_sid or os.getenv("CANON_TWILIO_ACCOUNT_SID", "")
        self._auth_token = auth_token or os.getenv(
            config.get("client_kwargs", {}).get("auth_token_env", "CANON_TWILIO_AUTH_TOKEN"),
            "",
        )

        super().__init__(config=config, **kwargs)

    async def _call_http(self, payload: dict, headers: dict, **kwargs):
        """Override to use form-data and basic auth for Twilio."""
        import httpx

        # Convert payload to form data format
        form_data: dict[str, Any] = {}
        for key, value in payload.items():
            if value is not None:
                # Handle MediaUrl list
                if key == "MediaUrl" and isinstance(value, list):
                    for i, url in enumerate(value):
                        form_data[f"MediaUrl{i}"] = url
                else:
                    form_data[key] = value

        async with self._create_http_client() as client:
            response = await client.request(
                method=self.config.method,
                url=self.config.full_url,
                auth=(self._account_sid, self._auth_token),
                data=form_data,  # Form data instead of JSON
                **kwargs,
            )

            if response.status_code == 429 or response.status_code >= 500:
                response.raise_for_status()
            elif response.status_code not in (200, 201):
                try:
                    error_body = response.json()
                    error_message = (
                        f"Request failed with status {response.status_code}: {error_body}"
                    )
                except Exception:
                    error_message = f"Request failed with status {response.status_code}"

                raise httpx.HTTPStatusError(
                    message=error_message,
                    request=response.request,
                    response=response,
                )

            return response.json()

    def normalize_response(self, raw_response: dict[str, Any]) -> NormalizedResponse:
        """Normalize Twilio SMS response.

        Args:
            raw_response: Raw JSON response from Twilio API.

        Returns:
            NormalizedResponse with message data.
        """
        if (message_sid := raw_response.get("sid")) is not None:
            return NormalizedResponse(
                status="success",
                data={
                    "message_sid": message_sid,
                    "status": raw_response.get("status", "queued"),
                    "segments": int(raw_response.get("num_segments", 1)),
                    "price": raw_response.get("price"),
                },
                raw_response=raw_response,
            )

        # Error response
        error = raw_response.get("message") or raw_response.get("error_message")
        return NormalizedResponse(
            status="error",
            error=error or "Unknown error",
            raw_response=raw_response,
        )
