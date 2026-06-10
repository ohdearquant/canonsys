# Copyright (c) 2026 HaiyangLi
# SPDX-License-Identifier: Apache-2.0
"""H1BSalary model for H1B visa salary data.

Stores H1B LCA salary data from DOL OFLC disclosure files.
This is ACTUAL disclosed salary data from H1B visa applications,
not estimates. Provides:
- Actual offered wages (WAGE_RATE_OF_PAY_FROM/TO)
- Prevailing wage (market baseline for the role)
- Wage level (I=Jr, II=Mid, III=Sr, IV=Lead/Principal)
- SOC codes for canonical job family mapping

Source: https://www.dol.gov/agencies/eta/foreign-labor/performance
Updated quarterly by DOL OFLC.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.db.base import Base
from sqlalchemy import DateTime, Float, Index, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column


class H1BSalary(Base):
    """H1B LCA salary data from DOL OFLC disclosure files.

    This is public data from H1B visa applications, providing:
    - Actual disclosed salaries (not estimates)
    - Prevailing wage benchmarks
    - Wage levels for seniority mapping
    - SOC codes for job family classification

    Used as fallback salary data when scraped job salaries unavailable.
    """

    __tablename__ = "h1b_salaries"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # Case identification
    case_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    case_status: Mapped[str | None] = mapped_column(String(50), default=None)

    # Employer info
    employer_name: Mapped[str] = mapped_column(String(500), nullable=False)
    employer_city: Mapped[str | None] = mapped_column(String(255), default=None)
    employer_state: Mapped[str | None] = mapped_column(String(10), default=None)

    # Worksite (actual job location)
    worksite_city: Mapped[str | None] = mapped_column(String(255), default=None)
    worksite_state: Mapped[str | None] = mapped_column(String(10), default=None)

    # Job info
    job_title: Mapped[str] = mapped_column(String(500), nullable=False)
    soc_code: Mapped[str | None] = mapped_column(
        String(20), default=None
    )  # Standard Occupational Classification
    soc_title: Mapped[str | None] = mapped_column(String(255), default=None)  # Canonical job title

    # Salary data (the gold!)
    wage_from: Mapped[float | None] = mapped_column(Float, default=None)  # Offered salary min
    wage_to: Mapped[float | None] = mapped_column(Float, default=None)  # Offered salary max
    wage_unit: Mapped[str | None] = mapped_column(String(20), default=None)  # Year/Hour/Week/Month
    prevailing_wage: Mapped[float | None] = mapped_column(Float, default=None)  # Market baseline
    wage_level: Mapped[str | None] = mapped_column(String(10), default=None)  # I/II/III/IV

    # Filing dates
    received_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    decision_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    # Fiscal year for partitioning/filtering
    fiscal_year: Mapped[int] = mapped_column(nullable=False)

    # Metadata
    loaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )

    __table_args__ = (
        # Index for job title fuzzy search
        Index("ix_h1b_salaries_job_title", "job_title"),
        # Index for SOC code lookups
        Index("ix_h1b_salaries_soc_code", "soc_code"),
        # Index for employer lookups
        Index("ix_h1b_salaries_employer", "employer_name"),
        # Index for location lookups
        Index("ix_h1b_salaries_worksite_state", "worksite_state"),
        # Composite index for common queries
        Index("ix_h1b_salaries_soc_state", "soc_code", "worksite_state"),
        # Index for fiscal year filtering
        Index("ix_h1b_salaries_fiscal_year", "fiscal_year"),
    )
