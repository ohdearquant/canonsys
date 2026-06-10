"""Charter entity types for CanonSys.

The Charter binds together:
- Organization (tenant)
- Surfaces (control points)
- Policies (Rego rules)
- Evidence requirements

Charter is the governance document that defines what compliance rules
apply to a tenant and which surfaces enforce them.

Pattern: Follows Evidence/EvidenceContent from core/evidence.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from .status import CharterStatus

__all__ = (
    # Entities
    "Charter",
    "CharterSurfaceBinding",
    # Creation payloads
    "CharterContent",
    "CharterSurfaceBindingContent",
)


# =============================================================================
# Charter Entity
# =============================================================================


@dataclass(frozen=True, slots=True)
class Charter:
    """Charter governance document.

    The Charter is the root governance document for a tenant. It defines:
    - Which surfaces (control points) are active
    - What policies govern each surface
    - What evidence is required for decisions

    Attributes:
        id: Unique charter identifier.
        tenant_id: Owning tenant/organization.
        name: Human-readable charter name (e.g., "ACME Corp Hiring Charter v2.0").
        description: Optional description of charter scope and purpose.
        version: Semantic version for charter updates (e.g., "2.0.0").
        status: Current lifecycle status.
        effective_date: When charter becomes/became enforceable.
        expiry_date: Optional date when charter automatically retires.
        created_at: When charter was created.
        updated_at: When charter was last modified.

    Invariants:
        - Only one ACTIVE charter per tenant at a time
        - Immutable after ACTIVE (changes require new version)
        - effective_date required for ACTIVE status
    """

    id: UUID
    tenant_id: UUID
    name: str
    version: str  # Semantic version: "1.0.0", "2.0.0"
    status: CharterStatus
    created_at: datetime
    updated_at: datetime

    # Optional fields
    description: str | None = None
    effective_date: datetime | None = None
    expiry_date: datetime | None = None

    def is_effective(self, as_of: datetime | None = None) -> bool:
        """Check if charter is currently effective.

        Args:
            as_of: Point in time to check (default: now)

        Returns:
            True if charter is ACTIVE and within effective date range
        """
        if self.status != CharterStatus.ACTIVE:
            return False

        from kron.utils import now_utc

        check_time = as_of or now_utc()

        if self.effective_date and check_time < self.effective_date:
            return False
        if self.expiry_date and check_time >= self.expiry_date:
            return False

        return True

    def is_expired(self, as_of: datetime | None = None) -> bool:
        """Check if charter has expired.

        Args:
            as_of: Point in time to check (default: now)

        Returns:
            True if expiry_date has passed
        """
        if self.expiry_date is None:
            return False

        from kron.utils import now_utc

        check_time = as_of or now_utc()
        return check_time >= self.expiry_date


# =============================================================================
# Charter-Surface Binding
# =============================================================================


@dataclass(frozen=True, slots=True)
class CharterSurfaceBinding:
    """Binding between a Charter and a Control Surface.

    Links a charter to a specific control surface (e.g., CS-001 Termination,
    CS-015 Background Check) with its policy configuration and evidence
    requirements.

    Attributes:
        charter_id: Parent charter this binding belongs to.
        surface_id: Control surface identifier (e.g., "CS-001").
        policy_version: Hash of the Rego policy governing this surface.
        enabled: Whether this surface is active for enforcement.
        evidence_requirements: List of evidence types required for decisions
            on this surface (e.g., ["consent.background_check", "hr.manager_approval"]).

    Evidence Requirements:
        These define WHAT evidence artifacts must be present before a decision
        can be certified on this surface. Format: "{domain}.{evidence_type}"

    Example:
        CharterSurfaceBinding(
            charter_id=uuid4(),
            surface_id="CS-001",
            policy_version="sha256:abc123...",
            enabled=True,
            evidence_requirements=[
                "consent.termination_acknowledgment",
                "hr.pip_documentation",
                "legal.er_review",
            ],
        )
    """

    charter_id: UUID
    surface_id: str  # Control surface ID: "CS-001", "CS-015"
    policy_version: str  # Hash of Rego policy: "sha256:..."
    enabled: bool
    evidence_requirements: tuple[str, ...] = field(default_factory=tuple)

    def requires_evidence(self, evidence_type: str) -> bool:
        """Check if this surface requires a specific evidence type.

        Args:
            evidence_type: Evidence type to check (e.g., "consent.background_check")

        Returns:
            True if evidence_type is in requirements
        """
        return evidence_type in self.evidence_requirements

    def missing_evidence(self, provided: frozenset[str]) -> tuple[str, ...]:
        """Get evidence types that are required but not provided.

        Args:
            provided: Set of evidence types that have been collected

        Returns:
            Tuple of missing evidence types
        """
        return tuple(req for req in self.evidence_requirements if req not in provided)


# =============================================================================
# Creation Payloads
# =============================================================================


@dataclass(frozen=True, slots=True)
class CharterContent:
    """Payload for creating a new Charter.

    Used as input to charter creation features. Does not include
    system-generated fields (id, created_at, updated_at).

    Example:
        content = CharterContent(
            tenant_id=tenant.id,
            name="ACME Corp Hiring Charter",
            version="1.0.0",
            description="Governance for all hiring decisions",
            effective_date=datetime(2026, 2, 1),
        )
        charter = await create_charter(content, ctx)
    """

    tenant_id: UUID
    name: str
    version: str

    # Optional fields
    description: str | None = None
    effective_date: datetime | None = None
    expiry_date: datetime | None = None


@dataclass(frozen=True, slots=True)
class CharterSurfaceBindingContent:
    """Payload for binding a surface to a charter.

    Used as input to surface binding features.

    Example:
        binding = CharterSurfaceBindingContent(
            surface_id="CS-001",
            policy_version="sha256:abc123...",
            enabled=True,
            evidence_requirements=[
                "consent.termination_acknowledgment",
                "hr.manager_approval",
            ],
        )
        await bind_surface_to_charter(charter_id, binding, ctx)
    """

    surface_id: str
    policy_version: str
    enabled: bool = True
    evidence_requirements: tuple[str, ...] = field(default_factory=tuple)
