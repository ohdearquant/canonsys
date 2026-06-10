"""PolicyAdapter - engineering implementation of policy (Key 2)."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from ..entity import Entity, register_entity
from ..shared import TenantAware
from .status import PolicyStatus


class PolicyAdapterContent(TenantAware):
    """Engineering implementation of policy (Key 2 of 3).

    OWNER: Engineering
    IMMUTABILITY: After deployment, changes require new version + hash

    Engineering owns HOW policy is implemented, not WHAT it requires.
    Must reference a specific PolicyDefinition version.
    """

    # Identity & version lock
    adapter_id: str
    """Format: {policy_id}.v{adapter_version}."""

    policy_id: str
    """Links to PolicyDefinition.policy_id."""

    policy_definition_version: str
    """MUST match PolicyDefinition.version - version lock."""

    adapter_version: str
    """Adapter's own version (independent of policy version)."""

    # OPA/Rego integration
    rego_package: str | None = None
    """Rego package path (e.g., "canon.policies.fcra.consent")."""

    rego_entrypoint: str = "allow"
    """Rego rule entrypoint."""

    # Implementation details (JSONB)
    gate_implementations: list[dict] = Field(default_factory=list)
    config: dict = Field(default_factory=dict)

    # Integrity & provenance
    adapter_hash: str | None = None
    """SHA256 of adapter source code."""

    build_commit: str | None = None
    """Git SHA of source commit."""

    # Lifecycle
    status: PolicyStatus = PolicyStatus.DRAFT
    implemented_by: str | None = None
    reviewed_by: str | None = None
    deployed_at: datetime | None = None

    def verify_version_lock(self, definition_version: str) -> bool:
        """Verify adapter matches PolicyDefinition version."""
        return self.policy_definition_version == definition_version


@register_entity("policy_adapters", immutable=True)
class PolicyAdapter(Entity):
    """Immutable policy adapter. Engineering owns HOW it's enforced."""

    content: PolicyAdapterContent
