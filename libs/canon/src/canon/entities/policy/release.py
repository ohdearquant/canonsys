"""PolicyRelease - versioned snapshot of policies (Key 3)."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from ..entity import Entity, register_entity
from ..shared import TenantAware


class PolicyReleaseContent(TenantAware):
    """Immutable versioned snapshot of policies (Key 3 of 3).

    Like a software release: once published, cannot be modified.
    Provides audit trail of what policies were active when.
    Multiple tenants can activate the same release via Charter.
    """

    release_version: str
    """Release version (e.g., "2026.01", "2026.01.1")."""

    description: str = ""

    # Content snapshot (JSONB - frozen after publish)
    policies: dict[str, dict] = Field(default_factory=dict)
    """policy_id → config snapshot."""

    policy_families: dict[str, dict] = Field(default_factory=dict)
    """Policy family configurations."""

    # OPA bundle
    bundle_path: str | None = None
    """Path to OPA bundle .tar.gz."""

    bundle_hash: str | None = None
    """SHA256 of bundle for integrity verification."""

    # Lifecycle
    status: str = "draft"  # draft → published → active → deprecated
    published_at: datetime | None = None
    published_by: str | None = None
    deprecated_at: datetime | None = None
    deprecated_reason: str | None = None

    # Signature
    signature: str | None = None
    """Cryptographic signature of release content."""

    signed_by: str | None = None

    def is_published(self) -> bool:
        """Check if release is published (frozen)."""
        return self.status in ("published", "active", "deprecated")

    def get_policy_ids(self) -> list[str]:
        """Return all policy IDs in this release."""
        return list(self.policies.keys())


@register_entity("policy_releases", immutable=True)
class PolicyRelease(Entity):
    """Immutable policy release. WHEN policies were active."""

    content: PolicyReleaseContent
