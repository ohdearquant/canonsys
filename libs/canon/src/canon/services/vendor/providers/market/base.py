# Copyright (c) 2026 HaiyangLi
# SPDX-License-Identifier: Apache-2.0
"""Market data types for hiring intelligence.

Data models for salary bands, role normalization, and market intelligence.
Used by H1B provider, scraped jobs, and market services.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SalaryBands(BaseModel):
    """Salary band data from market sources.

    Represents salary percentiles for a role, typically from H1B disclosures
    or market data providers.
    """

    p25: int | None = None
    p50: int | None = None  # Median
    p75: int | None = None
    p90: int | None = None
    avg: int | None = None
    count: int = 0
    prevailing_wage_avg: int | None = None
    source: str = "unknown"


class NormalizedRole(BaseModel):
    """Canonical role classification.

    Maps job titles to standard occupational codes and levels.
    """

    soc_code: str | None = None
    soc_title: str | None = None
    inferred_level: str | None = None  # entry/mid/senior/lead
    confidence: float = 0.0
    source: str = "unknown"


class MarketIntelligence(BaseModel):
    """Comprehensive market intelligence for a role.

    Aggregates data from multiple sources for hiring intelligence.
    """

    # Salary data
    salary_bands: SalaryBands | None = None
    salary_by_level: dict[str, SalaryBands] | None = None

    # Market size
    total_h1b_filings: int = 0
    total_job_postings: int = 0

    # Top employers
    top_employers: list[dict[str, Any]] = []

    # Geographic distribution
    geo_distribution: list[dict[str, Any]] = []

    # Similar jobs (with URLs for proof)
    similar_jobs: list[dict[str, Any]] = []

    # Role normalization
    normalized_role: NormalizedRole | None = None

    # Candidate pool (from scraped profiles)
    candidate_count: int = 0
    candidates_by_company: list[dict[str, Any]] = []
    open_to_work_count: int = 0

    # Data sources used
    sources: list[str] = []
