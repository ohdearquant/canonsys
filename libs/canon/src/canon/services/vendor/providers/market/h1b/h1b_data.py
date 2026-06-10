"""
H1B Salary Data Service - Actual Disclosed Compensation Intelligence

Provides salary intelligence from DOL H1B LCA disclosure data:
- Actual offered salaries (not estimates)
- Prevailing wage (government-determined market baseline)
- Wage levels (I-IV) mapping to seniority
- SOC codes for canonical role mapping

This is the gold standard for compensation data - legally required disclosures
from H1B visa applications.

Cost: $0 (public government data)
"""

import logging
import re
from typing import Any

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..base import SalaryBands

logger = logging.getLogger(__name__)


def extract_search_keywords(job_title: str) -> list[str]:
    """
    Extract searchable keywords from a job title.

    "Senior System Software Engineer - GPU Systems"
    -> ["Software Engineer", "System Software Engineer", "GPU"]

    Strategy:
    1. Extract core role (Engineer, Manager, Analyst, etc.)
    2. Extract modifiers (Senior, Software, System, Data, ML, etc.)
    3. Generate combinations for broader H1B matching
    """
    # Normalize
    title = job_title.strip()

    # Common role bases to look for
    role_bases = [
        "Engineer",
        "Developer",
        "Architect",
        "Manager",
        "Analyst",
        "Scientist",
        "Designer",
        "Administrator",
        "Lead",
        "Director",
        "Specialist",
        "Consultant",
        "Coordinator",
        "Technician",
    ]

    # Common modifiers
    modifiers = [
        "Software",
        "System",
        "Systems",
        "Data",
        "Machine Learning",
        "ML",
        "AI",
        "Cloud",
        "DevOps",
        "Platform",
        "Backend",
        "Frontend",
        "Full Stack",
        "Infrastructure",
        "Security",
        "Network",
        "Database",
        "SRE",
        "QA",
        "Product",
        "Project",
        "Program",
        "Technical",
        "Research",
        "Applied",
    ]

    # Seniority levels (strip for core search)
    seniority = ["Senior", "Staff", "Principal", "Lead", "Junior", "Entry", "Sr", "Jr"]

    keywords = []

    # 1. Try to find base role
    found_base = None
    for base in role_bases:
        if base.lower() in title.lower():
            found_base = base
            break

    # 2. Find modifiers present
    found_modifiers = []
    for mod in modifiers:
        if mod.lower() in title.lower():
            found_modifiers.append(mod)

    # 3. Build keyword combinations
    if found_base:
        # Core role alone
        keywords.append(found_base)

        # Modifier + Role combinations
        for mod in found_modifiers[:2]:  # Limit to avoid explosion
            keywords.append(f"{mod} {found_base}")

    # 4. Add the original title (for exact matches)
    keywords.insert(0, title)

    # 5. Strip seniority and try again
    stripped = title
    for s in seniority:
        stripped = re.sub(rf"\b{s}\b", "", stripped, flags=re.IGNORECASE).strip()
    stripped = re.sub(r"\s+", " ", stripped).strip(" -")
    if stripped and stripped != title:
        keywords.append(stripped)

    # Dedupe while preserving order
    seen = set()
    unique = []
    for kw in keywords:
        if kw.lower() not in seen and len(kw) > 2:
            seen.add(kw.lower())
            unique.append(kw)

    return unique[:5]  # Return top 5 keywords


class CompanyH1BStats(BaseModel):
    """H1B filing stats for a company."""

    company: str
    total_filings: int
    avg_wage: int | None
    median_wage: int | None
    top_roles: list[dict[str, Any]]
    wage_levels: dict[str, int]  # Count by level I/II/III/IV


class RoleNormalization(BaseModel):
    """Canonical role mapping from SOC codes."""

    soc_code: str
    soc_title: str  # Canonical job title
    sample_job_titles: list[str]
    filing_count: int


class H1BDataService:
    """H1B salary intelligence from DOL disclosure data."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_salary_bands(
        self,
        job_title: str,
        location: str | None = None,
        soc_code: str | None = None,
    ) -> SalaryBands:
        """
        Get salary bands for a role from H1B data.

        Args:
            job_title: Job title to search (fuzzy matched with keyword expansion)
            location: Optional state filter (e.g., "CA", "NY")
            soc_code: Optional SOC code for exact match

        Returns:
            SalaryBands with p25/p50/p75/p90 and prevailing wage
        """
        if soc_code:
            # Direct SOC code lookup
            return await self._query_salary_bands(soc_code=soc_code, location=location)

        # Try keyword expansion for broader matches
        keywords = extract_search_keywords(job_title)
        logger.info(f"H1B search keywords for '{job_title}': {keywords}")

        for keyword in keywords:
            result = await self._query_salary_bands(title_pattern=keyword, location=location)
            if result.count >= 10:  # Found good data
                logger.info(f"H1B match found with '{keyword}': {result.count} records")
                return result

        # If no good match, return best effort from first keyword
        return await self._query_salary_bands(
            title_pattern=keywords[0] if keywords else job_title, location=location
        )

    async def _query_salary_bands(
        self,
        title_pattern: str | None = None,
        soc_code: str | None = None,
        location: str | None = None,
    ) -> SalaryBands:
        """Internal query helper for salary bands."""
        query = """
            SELECT
                COUNT(*) as count,
                ROUND(AVG(wage_from)::numeric, 0) as avg_wage,
                ROUND(AVG(prevailing_wage)::numeric, 0) as prevailing_avg,
                ROUND(percentile_cont(0.25) WITHIN GROUP (ORDER BY wage_from)::numeric, 0) as p25,
                ROUND(percentile_cont(0.50) WITHIN GROUP (ORDER BY wage_from)::numeric, 0) as p50,
                ROUND(percentile_cont(0.75) WITHIN GROUP (ORDER BY wage_from)::numeric, 0) as p75,
                ROUND(percentile_cont(0.90) WITHIN GROUP (ORDER BY wage_from)::numeric, 0) as p90
            FROM h1b_salaries
            WHERE wage_from > 30000  -- Filter out bad data
            AND wage_from < 1000000  -- Filter out outliers
        """

        params = {}

        if soc_code:
            query += " AND soc_code = :soc_code"
            params["soc_code"] = soc_code
        elif title_pattern:
            query += " AND job_title ILIKE :title_pattern"
            params["title_pattern"] = f"%{title_pattern}%"

        if location:
            # Support both state abbreviations and full names
            if len(location) == 2:
                query += " AND worksite_state = :state"
                params["state"] = location.upper()
            else:
                query += " AND (worksite_state ILIKE :loc OR worksite_city ILIKE :loc)"
                params["loc"] = f"%{location}%"

        result = await self.session.execute(text(query), params)
        row = result.fetchone()

        if not row or row.count == 0:
            return SalaryBands(count=0)

        return SalaryBands(
            p25=int(row.p25) if row.p25 else None,
            p50=int(row.p50) if row.p50 else None,
            p75=int(row.p75) if row.p75 else None,
            p90=int(row.p90) if row.p90 else None,
            avg=int(row.avg_wage) if row.avg_wage else None,
            count=row.count,
            prevailing_wage_avg=int(row.prevailing_avg) if row.prevailing_avg else None,
        )

    async def get_salary_by_level(
        self,
        job_title: str,
        location: str | None = None,
    ) -> dict[str, SalaryBands]:
        """
        Get salary bands broken down by wage level (seniority).

        Wage levels map to:
        - Level I: Entry/Junior
        - Level II: Mid-level
        - Level III: Senior
        - Level IV: Lead/Principal/Expert

        Returns:
            Dict mapping level to SalaryBands
        """
        query = """
            SELECT
                wage_level,
                COUNT(*) as count,
                ROUND(AVG(wage_from)::numeric, 0) as avg_wage,
                ROUND(percentile_cont(0.50) WITHIN GROUP (ORDER BY wage_from)::numeric, 0) as p50
            FROM h1b_salaries
            WHERE wage_from > 30000
            AND wage_from < 1000000
            AND wage_level IS NOT NULL
            AND job_title ILIKE :title_pattern
        """

        params = {"title_pattern": f"%{job_title}%"}

        if location and len(location) == 2:
            query += " AND worksite_state = :state"
            params["state"] = location.upper()

        query += " GROUP BY wage_level ORDER BY wage_level"

        result = await self.session.execute(text(query), params)

        levels = {}
        for row in result:
            level_name = {
                "I": "entry",
                "II": "mid",
                "III": "senior",
                "IV": "lead",
            }.get(row.wage_level, row.wage_level)

            levels[level_name] = SalaryBands(
                p50=int(row.p50) if row.p50 else None,
                avg=int(row.avg_wage) if row.avg_wage else None,
                count=row.count,
            )

        return levels

    async def get_company_stats(self, company: str) -> CompanyH1BStats | None:
        """
        Get H1B filing statistics for a company.

        Args:
            company: Company name to search

        Returns:
            CompanyH1BStats with filing counts, wages, top roles
        """
        # Get overall stats
        stats_query = """
            SELECT
                COUNT(*) as total,
                ROUND(AVG(wage_from)::numeric, 0) as avg_wage,
                ROUND(percentile_cont(0.50) WITHIN GROUP (ORDER BY wage_from)::numeric, 0) as median_wage
            FROM h1b_salaries
            WHERE employer_name ILIKE :company_pattern
            AND wage_from > 30000
        """

        result = await self.session.execute(text(stats_query), {"company_pattern": f"%{company}%"})
        stats_row = result.fetchone()

        if not stats_row or stats_row.total == 0:
            return None

        # Get top roles
        roles_query = """
            SELECT
                soc_title,
                COUNT(*) as count,
                ROUND(AVG(wage_from)::numeric, 0) as avg_wage
            FROM h1b_salaries
            WHERE employer_name ILIKE :company_pattern
            AND wage_from > 30000
            AND soc_title IS NOT NULL
            GROUP BY soc_title
            ORDER BY count DESC
            LIMIT 10
        """

        roles_result = await self.session.execute(
            text(roles_query), {"company_pattern": f"%{company}%"}
        )
        top_roles = [
            {
                "role": r.soc_title,
                "count": r.count,
                "avg_wage": int(r.avg_wage) if r.avg_wage else None,
            }
            for r in roles_result
        ]

        # Get wage level distribution
        levels_query = """
            SELECT wage_level, COUNT(*) as count
            FROM h1b_salaries
            WHERE employer_name ILIKE :company_pattern
            AND wage_level IS NOT NULL
            GROUP BY wage_level
        """

        levels_result = await self.session.execute(
            text(levels_query), {"company_pattern": f"%{company}%"}
        )
        wage_levels = {r.wage_level: r.count for r in levels_result}

        return CompanyH1BStats(
            company=company,
            total_filings=stats_row.total,
            avg_wage=int(stats_row.avg_wage) if stats_row.avg_wage else None,
            median_wage=int(stats_row.median_wage) if stats_row.median_wage else None,
            top_roles=top_roles,
            wage_levels=wage_levels,
        )

    async def get_top_employers(
        self,
        job_title: str,
        location: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Get top employers filing H1B for a role.

        This is hiring velocity intelligence - companies actively
        sponsoring visas for this role.
        """
        query = """
            SELECT
                employer_name,
                COUNT(*) as filings,
                ROUND(AVG(wage_from)::numeric, 0) as avg_wage,
                ROUND(percentile_cont(0.50) WITHIN GROUP (ORDER BY wage_from)::numeric, 0) as median_wage
            FROM h1b_salaries
            WHERE job_title ILIKE :title_pattern
            AND wage_from > 30000
        """

        params = {"title_pattern": f"%{job_title}%"}

        if location and len(location) == 2:
            query += " AND worksite_state = :state"
            params["state"] = location.upper()

        query += """
            GROUP BY employer_name
            HAVING COUNT(*) >= 2
            ORDER BY filings DESC
            LIMIT :limit
        """
        params["limit"] = limit

        result = await self.session.execute(text(query), params)

        return [
            {
                "employer": r.employer_name,
                "filings": r.filings,
                "avg_wage": int(r.avg_wage) if r.avg_wage else None,
                "median_wage": int(r.median_wage) if r.median_wage else None,
            }
            for r in result
        ]

    async def normalize_role(self, job_title: str) -> RoleNormalization | None:
        """
        Map a job title to its canonical SOC classification.

        This enables deterministic role normalization instead of
        LLM heuristics.
        """
        query = """
            SELECT
                soc_code,
                soc_title,
                COUNT(*) as count,
                array_agg(DISTINCT job_title) FILTER (WHERE job_title IS NOT NULL) as sample_titles
            FROM h1b_salaries
            WHERE job_title ILIKE :title_pattern
            AND soc_code IS NOT NULL
            AND soc_title IS NOT NULL
            GROUP BY soc_code, soc_title
            ORDER BY count DESC
            LIMIT 1
        """

        result = await self.session.execute(text(query), {"title_pattern": f"%{job_title}%"})
        row = result.fetchone()

        if not row:
            return None

        # Get sample titles (limit to 5)
        sample_titles = row.sample_titles[:5] if row.sample_titles else []

        return RoleNormalization(
            soc_code=row.soc_code,
            soc_title=row.soc_title,
            sample_job_titles=sample_titles,
            filing_count=row.count,
        )

    async def get_geo_distribution(
        self,
        job_title: str,
        limit: int = 15,
    ) -> list[dict[str, Any]]:
        """Get geographic distribution of H1B filings for a role."""
        query = """
            SELECT
                worksite_state,
                COUNT(*) as filings,
                ROUND(AVG(wage_from)::numeric, 0) as avg_wage
            FROM h1b_salaries
            WHERE job_title ILIKE :title_pattern
            AND wage_from > 30000
            AND worksite_state IS NOT NULL
            GROUP BY worksite_state
            ORDER BY filings DESC
            LIMIT :limit
        """

        result = await self.session.execute(
            text(query), {"title_pattern": f"%{job_title}%", "limit": limit}
        )

        return [
            {
                "state": r.worksite_state,
                "filings": r.filings,
                "avg_wage": int(r.avg_wage) if r.avg_wage else None,
            }
            for r in result
        ]


async def get_h1b_service(session: AsyncSession) -> H1BDataService:
    """Factory function for H1BDataService."""
    return H1BDataService(session)


__all__ = [
    "CompanyH1BStats",
    "H1BDataService",
    "RoleNormalization",
    "SalaryBands",
    "get_h1b_service",
]
