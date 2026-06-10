# Copyright (c) 2026 HaiyangLi
# SPDX-License-Identifier: Apache-2.0
"""ScrapedJob model for market job postings.

Stores job listings scraped from LinkedIn/job boards via Apify.
Used for:
- Real market intelligence (active jobs count, salary data)
- Vector similarity search for relevant job analysis
- Talent supply gauge calculations
- Top hiring company identification

Embedding: OpenAI text-embedding-3-small (1536 dimensions)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from app.db.base import Base
from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column


class ScrapedJob(Base):
    """LinkedIn job listings scraped via Apify.

    Used for market intelligence - NOT individual candidate data.
    Provides:
    - Real market intelligence (active jobs count, salary data)
    - Vector similarity search for relevant job analysis
    - Top hiring companies with job links (proof/attribution)
    - Skill frequency analysis from job descriptions

    Embedding: OpenAI text-embedding-3-small (1536 dimensions)
    """

    __tablename__ = "scraped_jobs"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    job_title: Mapped[str] = mapped_column(String(500), nullable=False)
    company: Mapped[str | None] = mapped_column(String(500), default=None)
    location: Mapped[str | None] = mapped_column(String(500), default=None)
    salary_min: Mapped[int | None] = mapped_column(default=None)
    salary_max: Mapped[int | None] = mapped_column(default=None)
    salary_currency: Mapped[str | None] = mapped_column(String(10), default="USD")
    description: Mapped[str | None] = mapped_column(Text, default=None)
    url: Mapped[str | None] = mapped_column(String(2000), unique=True, default=None)
    applicant_count: Mapped[int | None] = mapped_column(default=None)
    posted_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    source: Mapped[str] = mapped_column(String(100), default="linkedin")
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)

    # Enriched/computed fields from scraping
    role_category: Mapped[str | None] = mapped_column(String(50), default=None)
    seniority_level: Mapped[str | None] = mapped_column(String(30), default=None)
    location_type: Mapped[str | None] = mapped_column(String(20), default=None)
    competencies: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    salary_median: Mapped[int | None] = mapped_column(default=None)

    # Vector embedding for similarity search (pgvector)
    # 1536 dimensions for OpenAI text-embedding-3-small
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1536),
        nullable=True,
    )

    __table_args__ = (
        # Index for job title fuzzy search
        Index("ix_scraped_jobs_job_title", "job_title"),
        # Index for company lookups
        Index("ix_scraped_jobs_company", "company"),
        # Index for location lookups
        Index("ix_scraped_jobs_location", "location"),
        # Index for recency queries
        Index("ix_scraped_jobs_scraped_at", "scraped_at"),
        # HNSW index for vector similarity search (faster than IVFFlat for reads)
        Index(
            "ix_scraped_jobs_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
