# Copyright (c) 2026 HaiyangLi
# SPDX-License-Identifier: Apache-2.0
"""Market intelligence database models.

This module provides models for market data that powers hiring briefs:
- ScrapedJob: Job postings with pgvector embeddings for similarity search
- H1BSalary: H1B LCA salary data from DOL OFLC disclosure files
- ScrapedProfile: Market candidate profiles (aggregate data, not PII)
- MarketDataCache: Cache layer for market intelligence queries

Data Sources:
- Job postings: Apify LinkedIn scraper
- H1B salaries: DOL OFLC quarterly disclosure files
- Profiles: Aggregate market data (not individual candidates)

Note: This is MARKET intelligence data, not candidate PII. Used for:
- Salary benchmarking (H1B disclosed wages)
- Similar job discovery (pgvector search)
- Talent supply/demand analysis
- Feeder company identification
"""

from .h1b_salary import H1BSalary
from .market_cache import MarketDataCache
from .scraped_job import ScrapedJob
from .scraped_profile import ScrapedProfile

__all__ = [
    "H1BSalary",
    "MarketDataCache",
    "ScrapedJob",
    "ScrapedProfile",
]
