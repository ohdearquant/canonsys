# Copyright (c) 2026 HaiyangLi
# SPDX-License-Identifier: Apache-2.0
"""Apify integration - LinkedIn scraping via Apify actors.

Structure:
    endpoint.py     - ApifyEndpoint (lionpride pattern, uses apify_client SDK)
    normalizers.py  - Vendor schema → internal schema
    live_scraper.py - Service orchestration (DB, embeddings, progress)

When switching vendors:
    1. Create new vendor/endpoint.py
    2. Create new vendor/normalizers.py
    3. Update service to use new endpoint
"""

from .endpoint import (
    JOBS_SCRAPER_ACTOR,
    PROFILE_SCRAPER_ACTOR,
    ApifyEndpoint,
    ApifyRequest,
    create_apify_config,
)
from .normalizers import (
    extract_experience_years,
    extract_skills,
    normalize_job,
    normalize_profile,
    parse_applicant_count,
    parse_salary,
    profile_to_embedding_text,
)

__all__ = [
    "JOBS_SCRAPER_ACTOR",
    "PROFILE_SCRAPER_ACTOR",
    # Endpoint
    "ApifyEndpoint",
    "ApifyRequest",
    "create_apify_config",
    # Normalizers
    "extract_experience_years",
    "extract_skills",
    "normalize_job",
    "normalize_profile",
    "parse_applicant_count",
    "parse_salary",
    "profile_to_embedding_text",
]
