"""Core service - thin wrapper over core compliance phrases.

The service layer provides:
- Evidence emission via hooks
- RequestContext management

All logic lives in phrases/.

Regulatory context:
    - SOX Section 404 (Internal controls)
    - SOC 2 (Control environment)
    - ISO 27001 (Information security)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from canon.enforcement.service import CanonService, CanonServiceConfig, action

from .phrases import (  # Charter operations; General verification; Override operations; Requirements; Audit verification
    activate_charter,
    derive_amount_band,
    get_charter_by_id,
    get_charter_history,
    invoke_break_glass,
    invoke_executive_override,
    ratify_charter,
    require_alternative_reviewed,
    require_fraud_screening_pass,
    require_provenance_documented,
    require_sox_compliance_review,
    require_value_within_limit,
    resolve_charter,
    verify_audit_complete,
    verify_audit_current,
    verify_evidence_freshness,
    verify_signer_identity,
    verify_values_match,
)

if TYPE_CHECKING:
    from canon.enforcement.service import RequestContext

__all__ = ["CoreService"]


class CoreService(CanonService):
    """Core compliance service - foundational compliance operations.

    Provides charter management, override invocation, audit verification,
    and general-purpose compliance gates.

    Thin wrapper that delegates to phrase functions.
    """

    config: ClassVar[CanonServiceConfig] = CanonServiceConfig(provider="canon", name="core")

    # =========================================================================
    # Charter Operations
    # =========================================================================

    @action(skip_evidence=True)
    async def get_charter(self, payload: dict, ctx: RequestContext) -> dict:
        """Get a specific charter by ID."""
        return await get_charter_by_id(payload, ctx)

    @action(skip_evidence=True)
    async def get_charter_history(self, payload: dict, ctx: RequestContext) -> dict:
        """Get charter history for a tenant."""
        return await get_charter_history(payload, ctx)

    @action(skip_evidence=True)
    async def resolve_charter(self, payload: dict, ctx: RequestContext) -> dict:
        """Resolve the active charter for a tenant."""
        return await resolve_charter(payload, ctx)

    @action(evidence_type="core.ratify_charter")
    async def ratify_charter(self, payload: dict, ctx: RequestContext) -> dict:
        """Ratify a draft charter with signatories."""
        return await ratify_charter(payload, ctx)

    @action(evidence_type="core.activate_charter")
    async def activate_charter(self, payload: dict, ctx: RequestContext) -> dict:
        """Activate a ratified charter, superseding current active charter."""
        return await activate_charter(payload, ctx)

    # =========================================================================
    # Override Operations
    # =========================================================================

    @action(evidence_type="core.break_glass")
    async def invoke_break_glass(self, payload: dict, ctx: RequestContext) -> dict:
        """Invoke break-glass for an emergency action.

        Creates a BreakGlassCertificate with DEGRADED defensibility.
        Triggers auto-notification to Legal, ER, and Audit.
        """
        return await invoke_break_glass(payload, ctx)

    @action(evidence_type="core.executive_override")
    async def invoke_executive_override(self, payload: dict, ctx: RequestContext) -> dict:
        """Invoke executive override for policy deviation.

        Creates a certificate with DEGRADED defensibility requiring Legal review.
        """
        return await invoke_executive_override(payload, ctx)

    # =========================================================================
    # Audit Verification
    # =========================================================================

    @action(skip_evidence=True)
    async def verify_audit_complete(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify that an audit has been completed for a resource.

        Regulatory:
            - SOX Section 404 (Internal control audit)
            - SOC 2 CC4.1 (Monitoring activities)
        """
        return await verify_audit_complete(payload, ctx)

    @action(skip_evidence=True)
    async def verify_audit_current(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify that an audit is current (within validity window).

        Regulatory:
            - SOX Section 404 (Periodic assessment)
            - SOC 2 CC4.2 (Ongoing evaluation)
        """
        return await verify_audit_current(payload, ctx)

    # =========================================================================
    # Requirement Gates
    # =========================================================================

    @action(skip_evidence=True)
    async def require_alternative_reviewed(self, payload: dict, ctx: RequestContext) -> dict:
        """Require that alternatives have been reviewed before proceeding.

        Regulatory:
            - EEOC guidance (Consideration of alternatives)
            - NYC LL144 (Less discriminatory alternatives)
        """
        return await require_alternative_reviewed(payload, ctx)

    @action(skip_evidence=True)
    async def require_fraud_screening_pass(self, payload: dict, ctx: RequestContext) -> dict:
        """Require fraud screening pass before proceeding.

        Regulatory:
            - BSA/AML (Bank Secrecy Act)
            - OFAC sanctions screening
        """
        return await require_fraud_screening_pass(payload, ctx)

    @action(skip_evidence=True)
    async def require_provenance_documented(self, payload: dict, ctx: RequestContext) -> dict:
        """Require that provenance is documented for a resource.

        Regulatory:
            - EU AI Act (Training data provenance)
            - SOC 2 CC6.1 (Logical access controls)
        """
        return await require_provenance_documented(payload, ctx)

    @action(skip_evidence=True)
    async def require_sox_compliance_review(self, payload: dict, ctx: RequestContext) -> dict:
        """Require SOX compliance review for financial controls.

        Regulatory:
            - SOX Section 302 (Corporate responsibility)
            - SOX Section 404 (Internal control assessment)
        """
        return await require_sox_compliance_review(payload, ctx)

    @action(skip_evidence=True)
    async def require_value_within_limit(self, payload: dict, ctx: RequestContext) -> dict:
        """Require that a value is within approved limits.

        Compliance context:
            - Finance surfaces require approval chains based on amount
            - Prevents unauthorized high-value transactions
        """
        return await require_value_within_limit(payload, ctx)

    # =========================================================================
    # General Verification
    # =========================================================================

    @action(skip_evidence=True)
    async def derive_amount_band(self, payload: dict, ctx: RequestContext) -> dict:
        """Derive amount band from actual amount value.

        Anti-gaming primitive: Amount bands MUST be derived from actual amount,
        never accepted as user input.
        """
        return await derive_amount_band(payload, ctx)

    @action(skip_evidence=True)
    async def verify_evidence_freshness(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify that evidence is fresh (within acceptable age).

        Compliance context:
            - Stale evidence may not support current decisions
            - Different evidence types have different freshness windows
        """
        return await verify_evidence_freshness(payload, ctx)

    @action(skip_evidence=True)
    async def verify_signer_identity(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify the identity of a document signer.

        Regulatory:
            - E-SIGN Act (Electronic signatures)
            - UETA (Uniform Electronic Transactions Act)
        """
        return await verify_signer_identity(payload, ctx)

    @action(skip_evidence=True)
    async def verify_values_match(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify that two values match (reconciliation gate).

        Compliance context:
            - Data integrity verification
            - Cross-system reconciliation
        """
        return await verify_values_match(payload, ctx)
