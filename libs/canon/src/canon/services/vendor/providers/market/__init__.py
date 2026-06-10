# Copyright (c) 2026 HaiyangLi
# SPDX-License-Identifier: Apache-2.0
"""Market data providers - external data source integrations.

Architecture:
    providers/market/          # Pure infrastructure (API/SDK calls)
    ├── base.py                # Data models (SalaryBands, MarketIntelligence)
    └── apify/                 # LinkedIn scraping via Apify actors
        ├── endpoint.py        # ApifyEndpoint (SDK override)
        └── normalizers.py     # Vendor schema → internal

    market/endpoints/          # Endpoints (registered via @register_endpoint)
    ├── perplexity.py          # PerplexityEndpoint (AI-powered search)
    ├── exa.py                 # ExaEndpoint (neural search)
    └── h1b.py                 # H1BEndpoint (DOL salary data)

Usage:
    from hub.services.vendor.providers.market import SalaryBands, MarketIntelligence
    from canon.utils.endpoints import match_endpoint

    # Endpoints are resolved via registry
    endpoint = match_endpoint(provider="perplexity", endpoint="chat/completions")
"""

from .base import MarketIntelligence, NormalizedRole, SalaryBands

__all__ = [
    "MarketIntelligence",
    "NormalizedRole",
    "SalaryBands",
]
