"""Export control service - thin wrapper over export control phrases.

The service layer provides:
- Evidence emission via hooks
- RequestContext management

All logic lives in phrases/.

WARNING: Export control violations carry CRIMINAL penalties.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from canon.enforcement.service import CanonService, CanonServiceConfig, action

from .phrases import (
    RequireAllowedDestinationSpecs,
    VerifyBISSpecs,
    VerifyITARSpecs,
    VerifyOFACSpecs,
    require_allowed_destination,
    verify_bis_approval,
    verify_itar_authorization,
    verify_ofac_clearance,
)

if TYPE_CHECKING:
    from canon.enforcement.service import RequestContext

__all__ = ["ExportControlService"]


class ExportControlService(CanonService):
    """Export control service - manages export compliance verification.

    Thin wrapper that delegates to phrase functions.

    WARNING: Export control violations carry CRIMINAL penalties.
    """

    config: ClassVar[CanonServiceConfig] = CanonServiceConfig(  # type: ignore[misc]
        provider="canon", name="export_control"
    )

    @action(skip_evidence=True)
    async def check_allowed_destination(self, payload: dict, ctx: RequestContext) -> dict:
        """Require destination is allowed for export.

        Raises ProhibitedDestinationError if destination is comprehensively sanctioned.
        """
        options = RequireAllowedDestinationSpecs(**payload)
        result = await require_allowed_destination(options, ctx)
        return result

    @action(evidence_type="export_control.ofac_screening")
    async def screen_ofac(self, payload: dict, ctx: RequestContext) -> dict:
        """Screen entity against OFAC sanctions lists."""
        options = VerifyOFACSpecs(**payload)
        result = await verify_ofac_clearance(options, ctx)
        # Convert enum to string for serialization
        entity_type = result.get("entity_type")
        if hasattr(entity_type, "value"):
            result["entity_type"] = entity_type.value
        return result

    @action(evidence_type="export_control.bis_verification")
    async def verify_bis(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify BIS export license approval."""
        options = VerifyBISSpecs(**payload)
        result = await verify_bis_approval(options, ctx)
        # Convert enum to string for serialization
        license_type = result.get("license_type")
        if hasattr(license_type, "value"):
            result["license_type"] = license_type.value
        return result

    @action(evidence_type="export_control.itar_verification")
    async def verify_itar(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify ITAR authorization."""
        options = VerifyITARSpecs(**payload)
        result = await verify_itar_authorization(options, ctx)
        # Convert enum to string for serialization
        authorization_type = result.get("authorization_type")
        if authorization_type and hasattr(authorization_type, "value"):
            result["authorization_type"] = authorization_type.value
        return result
