"""Core consent types: ConsentScope, ConsentStatus, ConsentToken.

These are foundational entity types used by canon-core infrastructure
(specs, enforcement, type system). The consent vocabulary package in
canon-hub re-exports these and adds phrases/services on top.

Regulatory basis:
    - FCRA § 1681b(b)(3): Consent before procuring consumer report
    - GDPR Art. 6-7: Lawful basis for processing
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from kron.types import FK, Enum
from kron.utils import now_utc

from .entity import Entity, register_entity
from .shared import SubjectAware, TenantAware, User

__all__ = (
    "ConsentRequest",
    "ConsentRequestContent",
    "ConsentRequestStatus",
    "ConsentScope",
    "ConsentStatus",
    "ConsentToken",
    "ConsentTokenContent",
)


class ConsentScope(Enum):
    """Scopes that require explicit consent.

    CONSIDERATION_AUTHORIZATION is the primary consent - must be granted
    before any other consent can be granted. Revoking it cascades to all others.
    """

    # Primary consent - required before any other consent
    CONSIDERATION_AUTHORIZATION = "consideration_authorization"

    # Interview-specific consents
    AI_SCORING = "ai_scoring"
    INTERVIEW_RECORDING = "interview_recording"

    # Standard consents
    BACKGROUND_CHECK = "background_check"
    DATA_PROCESSING = "data_processing"
    COMMUNICATIONS = "communications"
    THIRD_PARTY_SHARING = "third_party_sharing"

    @classmethod
    def primary(cls) -> frozenset[ConsentScope]:
        """Return the primary consent scope that gates all others.

        Primary scopes that trigger cascade when revoked.
        Revoking these revokes ALL dependent scopes.
        """
        return _PRIMARY_SCOPE

    @classmethod
    def dependencies(cls) -> dict[ConsentScope, frozenset[ConsentScope]]:
        """Return the dependency map of primary scopes to dependent scopes."""
        return _SCOPE_DEPENDENCIES

    def requires_primary(self) -> None:
        """Check if a scope requires primary consent first."""
        return self not in self.primary()


_PRIMARY_SCOPE = frozenset(
    {
        ConsentScope.CONSIDERATION_AUTHORIZATION,
    }
)

_SCOPE_DEPENDENCIES = {
    ConsentScope.CONSIDERATION_AUTHORIZATION: frozenset(
        {
            ConsentScope.AI_SCORING,
            ConsentScope.INTERVIEW_RECORDING,
            ConsentScope.BACKGROUND_CHECK,
            ConsentScope.DATA_PROCESSING,
            ConsentScope.COMMUNICATIONS,
            ConsentScope.THIRD_PARTY_SHARING,
        }
    ),
}


class ConsentStatus(Enum):
    """Consent token lifecycle states."""

    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"


class ConsentTokenContent(TenantAware, SubjectAware):
    """Content for consent tokens.

    ConsentToken is the capability that gates check.
    Evidence records the audit trail separately.

    Lifecycle:
        Token created (ACTIVE) → Evidence emitted
        Token revoked (REVOKED) → Evidence emitted (new event, not update)
        Token expires → checked at query time

    Immutability Note:
        Revocation does NOT update existing record. Create new revocation
        event and update status. For full append-only, use supersession.
    """

    # Consent details
    scope: ConsentScope  # What this permits: background_check, ai_scoring, etc.
    consent_form_version: str | None = None  # Consent form/policy version

    # Grant info
    granted_at: datetime = Field(default_factory=now_utc)
    granted_by_id: FK[User] | None = None  # Who recorded (may differ from subject)

    # Status
    status: ConsentStatus = ConsentStatus.ACTIVE
    expires_at: datetime | None = None

    # Revocation (creates new evidence event)
    revoked_at: datetime | None = None
    revoked_by_id: FK[User] | None = None
    revocation_reason: str | None = None


@register_entity("consent_tokens")
class ConsentToken(Entity):
    """Entity representing a consent token."""

    content: ConsentTokenContent

    # Composite indexes for common query patterns
    _indexes = [
        # Fast lookup by tenant + subject + scope (most common query)
        {"columns": ["tenant_id", "subject_id", "scope"]},
        # Fast lookup by tenant + status (for active consent lists)
        {"columns": ["tenant_id", "status"]},
        # Fast lookup by subject for consent verification
        {"columns": ["subject_id", "scope", "status"]},
    ]


# ---------------------------------------------------------------------------
# Consent Request (candidate-granted consent flow)
# ---------------------------------------------------------------------------


class ConsentRequestStatus(Enum):
    """Lifecycle states for a consent request link."""

    PENDING = "pending"
    GRANTED = "granted"
    DENIED = "denied"
    WITHDRAWN = "withdrawn"  # Consent was granted then revoked by candidate
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ConsentRequestContent(TenantAware, SubjectAware):
    """Content for consent request links.

    A ConsentRequest represents a recruiter-generated link that a candidate
    opens to grant or deny consent. The candidate is the data subject —
    consent must come from them, not the recruiter.

    Flow:
        1. Recruiter creates request → link_token generated
        2. Candidate opens link → sees scopes, enters name, grants/denies
        3. On grant → ConsentToken(s) created, revocation_token issued
        4. Candidate can revoke via revocation_token at any time
    """

    # Link identification
    link_token: str  # UUID string for the consent URL
    requested_scopes: list[str]  # Scopes requested (ConsentScope values)

    # Context shown to candidate
    company_name: str
    job_title: str | None = None

    # Who requested
    requested_by_id: FK[User] | None = None

    # Status
    request_status: ConsentRequestStatus = ConsentRequestStatus.PENDING
    expires_at: datetime | None = None

    # Candidate response (set after grant/deny)
    granted_scopes: list[str] | None = None
    candidate_name: str | None = None
    responded_at: datetime | None = None

    # Revocation token (set after grant, used for revocation URL)
    revocation_token: str | None = None


@register_entity("consent_requests")
class ConsentRequest(Entity):
    """Entity representing a consent request link sent to a candidate."""

    content: ConsentRequestContent

    _indexes = [
        {"columns": ["link_token"], "unique": True},
        {"columns": ["revocation_token"], "unique": True},
        {"columns": ["tenant_id", "subject_id", "request_status"]},
    ]
