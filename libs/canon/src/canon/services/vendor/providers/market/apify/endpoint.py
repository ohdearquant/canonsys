# Copyright (c) 2026 HaiyangLi
# SPDX-License-Identifier: Apache-2.0
"""Apify endpoint using lionpride Endpoint pattern with apify_client SDK."""

from __future__ import annotations

import logging
import os
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from canon.utils.endpoints import register_endpoint
from kron.services import Endpoint, EndpointConfig, NormalizedResponse

logger = logging.getLogger(__name__)

__all__ = (
    "JOBS_SCRAPER_ACTOR",
    "PROFILE_SCRAPER_ACTOR",
    "ApifyEndpoint",
    "ApifyRequest",
    "create_apify_config",
)

# Actor IDs
JOBS_SCRAPER_ACTOR = "curious_coder/indeed-scraper"
PROFILE_SCRAPER_ACTOR = "harvestapi/linkedin-profile-search"


class ApifyRequest(BaseModel):
    """Apify actor run request."""

    model_config = ConfigDict(extra="forbid")

    actor: Literal["jobs", "profiles"]
    run_input: dict[str, Any]
    timeout_secs: int = 120


def create_apify_config(
    api_token_env: str = "APIFY_API_TOKEN",
    timeout: int = 120,
) -> dict:
    """Factory for Apify endpoint config.

    Args:
        api_token_env: Environment variable name for API token.
        timeout: Request timeout in seconds.

    Returns:
        Config dict for ApifyEndpoint.
    """
    return {
        "provider": "apify",
        "name": "linkedin_scraper",
        "base_url": "",  # Not used for SDK
        "endpoint": "actors",
        "method": "SDK",
        "api_key": api_token_env,
        "timeout": timeout,
        "request_options": ApifyRequest,
    }


@register_endpoint(provider="apify", endpoint="actors")
class ApifyEndpoint(Endpoint):
    """Apify LinkedIn scraping endpoint using apify_client SDK.

    Overrides call() to use apify_client instead of HTTP.

    Usage:
        endpoint = ApifyEndpoint()

        # Scrape jobs
        response = await endpoint.call({
            "actor": "jobs",
            "run_input": {
                "searchUrl": "https://linkedin.com/jobs/search/?keywords=...",
                "maxJobsToSearch": 50,
            },
        })

        # Scrape profiles
        response = await endpoint.call({
            "actor": "profiles",
            "run_input": {
                "currentJobTitles": ["Backend Engineer"],
                "locations": ["San Francisco"],
                "maxItems": 100,
            },
        })
    """

    def __init__(
        self,
        config: dict | EndpointConfig | None = None,
        api_token: str | None = None,
        **kwargs,
    ):
        """Initialize Apify endpoint."""
        if config is None:
            config = create_apify_config()
        elif isinstance(config, EndpointConfig):
            config = config.model_dump()

        self._api_token = api_token or os.getenv("APIFY_API_TOKEN")
        self._client: Any = None

        super().__init__(config=config, **kwargs)

    def _get_client(self) -> Any:
        """Get or create Apify client."""
        if self._client is None:
            try:
                from apify_client import ApifyClient
            except ImportError as err:
                raise RuntimeError(
                    "apify_client package required. Install with: pip install apify-client"
                ) from err

            if not self._api_token:
                raise RuntimeError("APIFY_API_TOKEN not configured")

            self._client = ApifyClient(self._api_token)

        return self._client

    @property
    def is_configured(self) -> bool:
        """Check if Apify is properly configured."""
        return bool(
            self._api_token and self._api_token != "apify_api_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
        )

    async def call(
        self,
        request: dict | BaseModel,
        **kwargs,
    ) -> NormalizedResponse:
        """Execute Apify actor using SDK.

        Overrides Endpoint.call() to use SDK instead of HTTP.
        """
        # Validate request
        req = ApifyRequest(**request) if isinstance(request, dict) else request

        if not self.is_configured:
            return NormalizedResponse(
                status="error",
                error="APIFY_API_TOKEN not configured",
                raw_response={},
            )

        client = self._get_client()

        # Select actor
        actor_id = JOBS_SCRAPER_ACTOR if req.actor == "jobs" else PROFILE_SCRAPER_ACTOR

        try:
            logger.info("Running Apify actor: %s", actor_id)

            # Run the actor (sync call - Apify handles async internally)
            run = client.actor(actor_id).call(
                run_input=req.run_input,
                timeout_secs=req.timeout_secs,
            )

            # Get results from dataset
            items = list(client.dataset(run["defaultDatasetId"]).iterate_items())

            logger.info("Apify actor returned %d items", len(items))

            return NormalizedResponse(
                status="success",
                data={
                    "items": items,
                    "count": len(items),
                    "actor": req.actor,
                    "run_id": run.get("id"),
                },
                raw_response=run,
            )

        except Exception as e:
            logger.error("Apify actor %s failed: %s", actor_id, str(e))
            return NormalizedResponse(
                status="error",
                error=str(e),
                raw_response={},
            )

    def normalize_response(self, raw_response: dict[str, Any]) -> NormalizedResponse:
        """Not used - call() handles normalization directly."""
        return NormalizedResponse(
            status="success",
            data=raw_response,
            raw_response=raw_response,
        )
