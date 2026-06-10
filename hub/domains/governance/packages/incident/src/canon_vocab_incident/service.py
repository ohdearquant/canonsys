"""Incident service - thin wrapper over incident phrases.

The service layer provides:
- Evidence emission via hooks
- RequestContext management

All logic lives in phrases/.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from canon.enforcement.service import CanonService, CanonServiceConfig, action

from .phrases import (
    require_containment_verified,
    require_incident_declared,
    require_root_cause_identified,
    verify_containment_verified,
    verify_root_cause_identified,
)

if TYPE_CHECKING:
    from canon.enforcement.service import RequestContext

__all__ = ["IncidentService"]


class IncidentService(CanonService):
    """Incident service - manages security incident response controls.

    Thin wrapper that delegates to phrase functions.

    Regulatory context:
        - GDPR Article 33 (Breach notification timing)
        - HIPAA 164.308(a)(6) (Security incident procedures)
        - SOC 2 CC7.2-CC7.4 (Incident identification, response, recovery)
        - ISO 27001 A.16.1.6 (Learning from incidents)
        - NIST SP 800-61 (Computer Security Incident Handling)
    """

    config: ClassVar[CanonServiceConfig] = CanonServiceConfig(provider="canon", name="incident")

    # --- Requirement phrases (mutations with evidence) ---

    @action(evidence_type="incident.declare")
    async def declare(self, payload: dict, ctx: RequestContext) -> dict:
        """Declare a security incident."""
        return await require_incident_declared(payload, ctx)

    @action(evidence_type="incident.require_containment")
    async def require_containment(self, payload: dict, ctx: RequestContext) -> dict:
        """Require containment verification gate."""
        return await require_containment_verified(payload, ctx)

    @action(evidence_type="incident.require_root_cause")
    async def require_root_cause(self, payload: dict, ctx: RequestContext) -> dict:
        """Require root cause identification gate."""
        return await require_root_cause_identified(payload, ctx)

    # --- Verification phrases (reads, no evidence) ---

    @action(skip_evidence=True)
    async def verify_containment(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify containment is complete (hot path)."""
        return await verify_containment_verified(payload, ctx)

    @action(skip_evidence=True)
    async def verify_root_cause(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify root cause is identified (hot path)."""
        return await verify_root_cause_identified(payload, ctx)
