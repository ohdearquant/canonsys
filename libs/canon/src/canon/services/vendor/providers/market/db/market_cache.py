# Copyright (c) 2026 HaiyangLi
# SPDX-License-Identifier: Apache-2.0
"""MarketDataCache model for market intelligence caching.

Provides a cache layer for expensive market data queries:
- LinkedIn/Apify API responses
- Aggregated market statistics
- Similar job search results

Cache Strategy:
- cache_key: Unique identifier (job_title + location hash)
- expires_at: 24-hour TTL for market data freshness
- data_json: Cached query results

Performance:
- Reduces Apify API calls (rate limits + cost optimization)
- UNIQUE constraint on cache_key prevents duplicate entries
- Index on expires_at for efficient cache invalidation queries
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from app.db.base import Base
from sqlalchemy import DateTime, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column


class MarketDataCache(Base):
    """Cache layer for market intelligence queries.

    Caches expensive market data operations with TTL expiration.
    Used to reduce API calls and improve response times.
    """

    __tablename__ = "market_data_cache"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    cache_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    data_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )

    __table_args__ = (
        # Index for cache expiration queries
        Index("ix_market_data_cache_expires_at", "expires_at"),
    )
