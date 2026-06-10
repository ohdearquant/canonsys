# Copyright (c) 2026 HaiyangLi
# SPDX-License-Identifier: Apache-2.0
"""ScrapedProfile model for market candidate profiles.

Stores aggregate market profile data scraped from LinkedIn.
This is MARKET INTELLIGENCE data, not individual candidate PII.

Used for:
- Talent pool analysis (qualified profiles count)
- Feeder company identification
- Geographic distribution analysis
- Skills frequency analysis

Note: Profile data requires GDPR-compliant sourcing. Currently
awaiting compliant data from enterprise partnerships.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from app.db.base import Base
from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Index, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column


class ScrapedProfile(Base):
    """Market profile data for talent pool analysis.

    This is aggregate market data for talent intelligence,
    NOT individual candidate records for hiring decisions.

    Used for:
    - Talent pool sizing (how many people match criteria)
    - Feeder company identification (where talent comes from)
    - Geographic distribution (talent density by location)
    - Skills analysis (common skills in talent pool)

    Embedding: OpenAI text-embedding-3-small (1536 dimensions)
    """

    __tablename__ = "scraped_profiles"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    linkedin_url: Mapped[str | None] = mapped_column(String(500), unique=True, default=None)
    name: Mapped[str | None] = mapped_column(String(255), default=None)
    headline: Mapped[str | None] = mapped_column(String(500), default=None)
    current_company: Mapped[str | None] = mapped_column(String(255), default=None)
    current_title: Mapped[str | None] = mapped_column(String(255), default=None)
    location: Mapped[str | None] = mapped_column(String(255), default=None)
    skills: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=None)
    experience_years: Mapped[int | None] = mapped_column(default=None)
    education: Mapped[str | None] = mapped_column(String(500), default=None)
    summary: Mapped[str | None] = mapped_column(Text, default=None)

    # Open to work indicator (for talent availability analysis)
    open_to_work: Mapped[bool | None] = mapped_column(default=None)

    # Scraping metadata
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    source: Mapped[str] = mapped_column(String(50), default="apify")
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)

    # Vector embedding for similarity search (pgvector)
    # 1536 dimensions for OpenAI text-embedding-3-small
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1536),
        nullable=True,
    )

    __table_args__ = (
        # Index for company lookups (feeder company analysis)
        Index("ix_scraped_profiles_company", "current_company"),
        # Index for title lookups
        Index("ix_scraped_profiles_title", "current_title"),
        # Index for location lookups
        Index("ix_scraped_profiles_location", "location"),
        # Index for open_to_work filtering
        Index("ix_scraped_profiles_open_to_work", "open_to_work"),
        # HNSW index for vector similarity search
        Index(
            "ix_scraped_profiles_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
