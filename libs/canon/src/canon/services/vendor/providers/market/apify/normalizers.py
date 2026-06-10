# Copyright (c) 2026 HaiyangLi
# SPDX-License-Identifier: Apache-2.0
"""Apify schema normalizers - vendor schema → internal schema.

When switching data vendors, create new normalizers for the new vendor's
schema while keeping the same internal schema (ScrapedJob, ScrapedProfile).
"""

from __future__ import annotations

import re
import uuid as uuid_module
from datetime import datetime
from typing import Any

__all__ = (
    "extract_experience_years",
    "extract_skills",
    "normalize_job",
    "normalize_profile",
    "parse_applicant_count",
    "parse_salary",
    "profile_to_embedding_text",
)


# =============================================================================
# JOB NORMALIZATION (curious_coder/indeed-scraper)
# =============================================================================


def parse_salary(salary_str: str | None) -> tuple[int | None, int | None]:
    """Parse salary string like '$53,200.00/yr - $113,700.00/yr' into min/max."""
    if not salary_str:
        return None, None

    # Pattern: $XX,XXX.XX/yr - $XX,XXX.XX/yr or $XX/hr - $XX/hr
    pattern = r"\$([0-9,]+\.?\d*)/(?:yr|hr)\s*-\s*\$([0-9,]+\.?\d*)/(?:yr|hr)"
    match = re.search(pattern, salary_str)
    if match:
        try:
            min_val = int(float(match.group(1).replace(",", "")))
            max_val = int(float(match.group(2).replace(",", "")))
            return min_val, max_val
        except (ValueError, TypeError):
            pass

    # Single value pattern: $XX,XXX/yr
    single_pattern = r"\$([0-9,]+\.?\d*)/(?:yr|hr)"
    match = re.search(single_pattern, salary_str)
    if match:
        try:
            val = int(float(match.group(1).replace(",", "")))
            return val, val
        except (ValueError, TypeError):
            pass

    return None, None


def parse_applicant_count(count_str: str | None) -> int | None:
    """Parse applicant count from various formats."""
    if not count_str:
        return None

    # "26 applicants" or "Over 200 applicants"
    match = re.search(r"(\d+)\s*applicants?", count_str, re.IGNORECASE)
    if match:
        return int(match.group(1))

    return None


def normalize_job(job: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize job from Apify scrapers to internal schema.

    Supports both Indeed (curious_coder/indeed-scraper) and
    LinkedIn (bebity/linkedin-jobs-scraper) schemas.

    Args:
        job: Raw job dict from Apify scraper.

    Returns:
        Normalized job dict or None if invalid.
    """
    # Get URL (required) - Indeed: link/viewJobLink
    url = job.get("link") or job.get("viewJobLink") or job.get("url")
    if not url:
        return None

    # Get title (required) - Indeed: title/displayTitle
    title = job.get("title") or job.get("displayTitle")
    if not title:
        return None

    # Get company (required) - Indeed: company/truncatedCompany
    company = job.get("company") or job.get("truncatedCompany")
    if not company:
        return None

    # Get description - Indeed uses 'snippet' for job description summary
    description = job.get("snippet") or job.get("description") or ""

    # Get location - Indeed uses 'formattedLocation' or 'jobLocationCity/State'
    location = job.get("formattedLocation")
    if not location:
        city = job.get("jobLocationCity", "")
        state = job.get("jobLocationState", "")
        if city or state:
            location = f"{city}, {state}".strip(", ")

    # Parse salary from extractedSalary object or salarySnippet
    salary_min, salary_max = None, None
    extracted_salary = job.get("extractedSalary")
    if extracted_salary and isinstance(extracted_salary, dict):
        salary_min = extracted_salary.get("min")
        salary_max = extracted_salary.get("max")
        # Convert hourly to yearly if needed
        if extracted_salary.get("type") == "hourly" and salary_min:
            salary_min = salary_min * 2080  # 40hrs * 52weeks
            salary_max = (salary_max * 2080) if salary_max else None
    elif job.get("salarySnippet"):
        salary_text = job["salarySnippet"].get("text", "")
        salary_min, salary_max = parse_salary(salary_text)

    # Parse applicant count - not directly available in Indeed
    applicant_count = None

    # Get posted date from pubDate (Unix timestamp)
    posted_date = None
    pub_date = job.get("pubDate")
    if pub_date:
        try:
            # pubDate is Unix timestamp in milliseconds
            posted_date = datetime.fromtimestamp(pub_date / 1000).date()
        except (ValueError, TypeError, OSError):
            pass

    return {
        "id": str(uuid_module.uuid4()),
        "url": url,
        "job_title": title[:500],
        "company": company[:255] if company else None,
        "location": location[:255] if location else None,
        "description": description[:50000] if description else None,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "applicant_count": applicant_count,
        "posted_date": posted_date,
        "source": "indeed_live",
        "raw_data": job,
    }


# =============================================================================
# PROFILE NORMALIZATION (harvestapi/linkedin-profile-search)
# =============================================================================


def extract_experience_years(experience: list[dict] | None) -> int | None:
    """Calculate total years of experience from work history."""
    if not experience:
        return None

    total_months = 0
    for exp in experience:
        duration = exp.get("duration", "")
        if not duration:
            continue

        years = 0
        months = 0

        if "yr" in duration:
            parts = duration.split("yr")
            try:
                years = int(parts[0].strip().split()[-1])
            except (ValueError, IndexError):
                pass
            if len(parts) > 1 and "mo" in parts[1]:
                try:
                    months = int(parts[1].strip().split()[0])
                except (ValueError, IndexError):
                    pass
        elif "mo" in duration:
            try:
                months = int(duration.split("mo")[0].strip().split()[-1])
            except (ValueError, IndexError):
                pass

        total_months += years * 12 + months

    return total_months // 12 if total_months > 0 else None


def extract_skills(profile: dict[str, Any]) -> list[str]:
    """Extract skill names from profile."""
    skills = profile.get("skills", [])
    if not skills:
        return []
    return [s.get("name") for s in skills if s.get("name")][:50]


def profile_to_embedding_text(profile: dict[str, Any]) -> str:
    """Create text representation for embedding."""
    parts = []

    if profile.get("headline"):
        parts.append(profile["headline"])

    if profile.get("about"):
        parts.append(profile["about"][:500])

    # Current position
    exp = profile.get("experience", [])
    if exp:
        current = exp[0]
        parts.append(f"Current: {current.get('position', '')} at {current.get('companyName', '')}")
        if current.get("description"):
            parts.append(current["description"][:300])

    # Skills
    skills = extract_skills(profile)
    if skills:
        parts.append(f"Skills: {', '.join(skills[:20])}")

    # Education
    edu = profile.get("education", [])
    if edu:
        for e in edu[:2]:
            school = e.get("schoolName", "")
            degree = e.get("degree", "")
            field = e.get("fieldOfStudy", "")
            if school:
                parts.append(f"Education: {degree} {field} at {school}".strip())

    return "\n".join(parts)


def normalize_profile(profile: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize profile from Apify schema to internal schema.

    Args:
        profile: Raw profile dict from Apify harvestapi/linkedin-profile-search.

    Returns:
        Normalized profile dict or None if invalid.
    """
    linkedin_url = profile.get("linkedinUrl")
    if not linkedin_url:
        return None

    name = f"{profile.get('firstName', '')} {profile.get('lastName', '')}".strip()
    headline = profile.get("headline", "")
    location_data = profile.get("location", {})
    location = location_data.get("linkedinText", "") if isinstance(location_data, dict) else ""

    # Current position
    experience = profile.get("experience", [])
    current_company = ""
    current_title = ""
    if experience:
        current = experience[0]
        current_company = current.get("companyName", "")
        current_title = current.get("position", "")

    # Education summary
    education = profile.get("education", [])
    education_summary = ""
    if education:
        edu = education[0]
        education_summary = (
            f"{edu.get('degree', '')} {edu.get('fieldOfStudy', '')} at {edu.get('schoolName', '')}"
        ).strip()

    skills = extract_skills(profile)
    experience_years = extract_experience_years(experience)

    return {
        "id": str(uuid_module.uuid4()),
        "linkedin_url": linkedin_url,
        "name": name[:255] if name else None,
        "headline": headline[:500] if headline else None,
        "current_company": current_company[:255] if current_company else None,
        "current_title": current_title[:255] if current_title else None,
        "location": location[:255] if location else None,
        "skills": skills,
        "experience_years": experience_years,
        "education": education_summary[:500] if education_summary else None,
        "source": "linkedin_live",
        "raw_data": profile,
    }
