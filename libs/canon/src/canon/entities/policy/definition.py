"""PolicyDefinition - legal-authored policy specification (Key 1)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import Field

from kron.utils import now_utc

from ..entity import Entity, register_entity
from ..shared import TenantAware
from .scope import PolicyScope
from .status import PolicyStatus


class PolicyDefinitionContent(TenantAware):
    """Legal-authored policy specification (Key 1 of 3).

    OWNER: Legal / Compliance
    IMMUTABILITY: After approval, changes require new version

    This is data, not code. Legal authors using legal language.
    Engineering implements via PolicyAdapter (Key 2).
    """

    # Identity
    policy_id: str
    """Canonical ID: {jurisdiction}.{domain}.{rule}."""

    policy_version: str
    """Semantic version of this policy."""

    name: str
    description: str | None = None

    # Legal authority (JSONB - PolicyAuthority.to_dict())
    authority: dict | None = None

    # Scope
    scope: PolicyScope = PolicyScope.GLOBAL
    jurisdictions: list[str] = Field(default_factory=list)
    """Applicable jurisdictions (e.g., ["US-NYC", "US-CA"])."""

    action_types: list[str] = Field(default_factory=list)
    """Action types this policy applies to (e.g., ["TERMINATE_WORKER"])."""

    # Requirements (in legal language)
    required_gates: list[dict] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    waiting_periods: dict[str, str] = Field(default_factory=dict)

    # Lifecycle
    status: PolicyStatus = PolicyStatus.DRAFT
    effective_from: datetime | None = None
    superseded_at: datetime | None = None
    sunset_date: datetime | None = None

    # Approval chain
    authored_by: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None

    def is_effective(self, as_of: datetime | None = None) -> bool:
        """Check if policy is currently effective."""
        if self.status not in (PolicyStatus.ACTIVE, PolicyStatus.APPROVED):
            return False

        check_time = as_of or now_utc()
        if self.effective_from and check_time < self.effective_from:
            return False
        if self.superseded_at and check_time >= self.superseded_at:
            return False

        # Check authority effective date if present
        effective_date = (self.authority or {}).get("effective_date")
        if effective_date:
            if isinstance(effective_date, str):
                effective_date = date.fromisoformat(effective_date)
            if check_time.date() < effective_date:
                return False

        return True


@register_entity("policy_definitions", immutable=True)
class PolicyDefinition(Entity):
    """Immutable policy definition. Legal owns WHAT is required."""

    content: PolicyDefinitionContent
