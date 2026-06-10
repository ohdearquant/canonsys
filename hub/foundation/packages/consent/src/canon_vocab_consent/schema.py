"""Consent service request/response schemas.

API-specific schemas for FastAPI endpoints.
Action Options/Results live in actions/.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from .types import ConsentScope

__all__ = [
    "ConsentLinkInfo",
    "ConsentLinkResponse",
    "ConsentListResponse",
    "ConsentRecord",
    # API response models
    "ConsentVerification",
    "CreateConsentLinkRequest",
    # API request models
    "GrantConsentRequest",
    "RevokeConsentRequest",
    "SubmitConsentLinkRequest",
]


# =============================================================================
# API Request Models
# =============================================================================


class GrantConsentRequest(BaseModel):
    """API request to grant consent."""

    person_id: UUID
    scope: ConsentScope
    version: str = "1.0"
    ip_address: str | None = None
    user_agent: str | None = None


class RevokeConsentRequest(BaseModel):
    """API request to revoke consent."""

    person_id: UUID
    scope: ConsentScope
    reason: str | None = None


class CreateConsentLinkRequest(BaseModel):
    """API request to create a one-time consent link."""

    person_id: UUID
    scopes: list[ConsentScope]
    expiry_days: int = 7
    job_title: str | None = None
    company_name: str | None = None


class SubmitConsentLinkRequest(BaseModel):
    """Candidate submitting consent via link."""

    first_name: str | None = None
    last_name: str | None = None


# =============================================================================
# API Response Models
# =============================================================================


class ConsentVerification(BaseModel):
    """Response for consent verification (hot path)."""

    has_consent: bool
    subject_id: UUID | None = None
    scope: str | None = None
    reason: str | None = None
    token_id: UUID | None = None
    granted_at: str | None = None


class ConsentLinkResponse(BaseModel):
    """Response with the generated consent link."""

    token: str
    link: str
    expires_at: str
    scopes: list[str]


class ConsentLinkInfo(BaseModel):
    """Info returned when viewing a consent link."""

    valid: bool
    scopes: list[str]
    job_title: str | None = None
    company_name: str | None = None
    expires_at: str | None = None
    error: str | None = None


class ConsentRecord(BaseModel):
    """Consent record response (from ConsentToken entity)."""

    token_id: UUID
    person_id: UUID
    scope: str
    status: str
    version: str | None
    granted_at: str | None
    granted_by_id: UUID | None = None
    revoked_at: str | None = None
    revoked_by_id: UUID | None = None
    revocation_reason: str | None = None
    expires_at: str | None = None


class ConsentListResponse(BaseModel):
    """Response for listing consents."""

    consents: list[ConsentRecord]
    total: int
