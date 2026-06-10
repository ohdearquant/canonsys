"""Outreach workflow entities.

Entities for AI-powered candidate outreach with regulatory disclosure compliance.

Regulatory basis:
    - NYC LL144: AI disclosure for automated employment decisions
    - GDPR Art. 13-14: Information to be provided when collecting data
    - CCPA 1798.100(b): Notice at collection
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from kron.types import FK

from ...entity import Entity, register_entity
from ...shared import OptSubjectAware, Person, TenantAware

__all__ = (
    "AIDisclosure",
    "AIDisclosureContent",
    "OutreachMessage",
    "OutreachMessageContent",
)


class AIDisclosureContent(TenantAware):
    """AI disclosure template for candidate communications.

    Contains the required disclosure text for jurisdictions that mandate
    AI usage transparency in hiring (e.g., NYC LL144, Colorado SB 205).
    """

    disclosure_text: str
    """The full disclosure text to present to candidates."""

    jurisdiction: str
    """Jurisdiction this disclosure applies to (e.g., 'NYC', 'Colorado', 'EU')."""

    disclosure_version: str
    """Version identifier for tracking disclosure updates."""

    effective_at: datetime
    """When this disclosure version becomes/became effective."""

    retired_at: datetime | None = None
    """When this disclosure was superseded by a newer version."""


@register_entity("ai_disclosures")
class AIDisclosure(Entity):
    """Entity representing an AI disclosure template."""

    content: AIDisclosureContent


class OutreachMessageContent(TenantAware, OptSubjectAware):
    """Content for outreach messages sent to candidates.

    Tracks AI-generated outreach with required disclosures, personalization
    metrics, and consent links for compliance verification.
    """

    candidate_id: FK[Person]
    """The candidate receiving this outreach (required)."""

    ai_disclosure_text: str
    """The AI disclosure text included in this message."""

    personalization_score: float = Field(ge=0.0, le=1.0)
    """Quality score of AI personalization (0-1). Used for bias monitoring."""

    message_content: str
    """The full message content sent to the candidate."""

    sent_at: datetime | None = None
    """When the message was sent. None if still draft."""

    consent_form_url: str | None = None
    """URL to consent form for candidate response tracking."""

    delivered_at: datetime | None = None
    """When delivery was confirmed (if trackable)."""

    opened_at: datetime | None = None
    """When the candidate opened the message (if trackable)."""


@register_entity("outreach_messages")
class OutreachMessage(Entity):
    """Entity representing an outreach message to a candidate."""

    content: OutreachMessageContent
