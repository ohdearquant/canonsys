"""Data protection service - thin wrapper over data protection phrases.

The service layer provides:
- Evidence emission via hooks
- RequestContext management

All logic lives in phrases/.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from canon.enforcement.service import CanonService, CanonServiceConfig, action

from .phrases import (
    require_encrypted_transmission,
    require_internal_publication,
    require_limited_audience,
    require_pci_classification,
    require_phi_classification,
    require_pii_classification,
    require_processor_terms_verified,
    require_retention_compliance,
    verify_data_minimization,
    verify_purpose_limitation,
)

if TYPE_CHECKING:
    from canon.enforcement.service import RequestContext

__all__ = ["DataProtectionService"]


class DataProtectionService(CanonService):
    """Data protection service - manages data classification, transmission, and privacy gates.

    Thin wrapper that delegates to phrase functions.

    Regulatory domains:
        - GDPR Art. 5, 28, 32: Data principles, processor terms, security
        - HIPAA 164.502, 164.312: Minimum necessary, transmission security
        - PCI DSS v4.0 Req. 3, 4, 7: Cardholder data protection
        - CCPA/CPRA Section 1798: Consumer rights
        - SOX Section 802: Document retention
    """

    config: ClassVar[CanonServiceConfig] = CanonServiceConfig(
        provider="canon", name="data_protection"
    )

    # -------------------------------------------------------------------------
    # Classification gates (require evidence)
    # -------------------------------------------------------------------------

    @action(evidence_type="data_protection.require_pii_classification")
    async def require_pii_classification(self, payload: dict, ctx: RequestContext) -> dict:
        """Require that PII-containing resources are not made public.

        Raises PIIExposureError if resource contains PII and target is PUBLIC.
        """
        return await require_pii_classification(payload, ctx)

    @action(evidence_type="data_protection.require_pci_classification")
    async def require_pci_classification(self, payload: dict, ctx: RequestContext) -> dict:
        """Require that PCI data is classified at CONFIDENTIAL or above.

        Raises ClassificationViolationError if resource contains PCI data and
        target classification is PUBLIC or INTERNAL.
        """
        return await require_pci_classification(payload, ctx)

    @action(evidence_type="data_protection.require_phi_classification")
    async def require_phi_classification(self, payload: dict, ctx: RequestContext) -> dict:
        """Require that PHI data is classified at CONFIDENTIAL or above.

        Raises ClassificationViolationError if resource contains PHI and
        target classification is PUBLIC or INTERNAL.
        """
        return await require_phi_classification(payload, ctx)

    # -------------------------------------------------------------------------
    # Transmission and audience gates (require evidence)
    # -------------------------------------------------------------------------

    @action(evidence_type="data_protection.require_encrypted_transmission")
    async def require_encrypted_transmission(self, payload: dict, ctx: RequestContext) -> dict:
        """Require that data transmission uses adequate encryption.

        Raises EncryptionMissingError if channel lacks required encryption.
        """
        return await require_encrypted_transmission(payload, ctx)

    @action(evidence_type="data_protection.require_limited_audience")
    async def require_limited_audience(self, payload: dict, ctx: RequestContext) -> dict:
        """Require that confidential content targets a limited audience.

        Raises LimitedAudienceRequiredError if confidential/restricted content
        targets unlimited audience.
        """
        return await require_limited_audience(payload, ctx)

    @action(evidence_type="data_protection.require_internal_publication")
    async def require_internal_publication(self, payload: dict, ctx: RequestContext) -> dict:
        """Require that restricted content is not published externally.

        Raises PublicationRestrictedError if content has publication restrictions.
        """
        return await require_internal_publication(payload, ctx)

    # -------------------------------------------------------------------------
    # Processor and retention gates (require evidence)
    # -------------------------------------------------------------------------

    @action(evidence_type="data_protection.require_processor_terms")
    async def require_processor_terms(self, payload: dict, ctx: RequestContext) -> dict:
        """Require verified processor/DPA terms before data sharing.

        Raises ProcessorTermsNotVerifiedError if terms are not verified.
        """
        return await require_processor_terms_verified(payload, ctx)

    @action(evidence_type="data_protection.require_retention_compliance")
    async def require_retention_compliance(self, payload: dict, ctx: RequestContext) -> dict:
        """Require that data is not retained beyond scheduled retention period.

        Raises RetentionComplianceRequiredError if data is being retained beyond schedule.
        Note: Returns success if under legal hold (retention allowed).
        """
        return await require_retention_compliance(payload, ctx)

    # -------------------------------------------------------------------------
    # Verification actions (skip evidence - hot path reads)
    # -------------------------------------------------------------------------

    @action(skip_evidence=True)
    async def verify_data_minimization(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify that only necessary fields are requested for workflow.

        Returns verification result without emitting evidence (hot path).
        """
        return await verify_data_minimization(payload, ctx)

    @action(skip_evidence=True)
    async def verify_purpose_limitation(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify that requested use matches declared purpose for data.

        Returns verification result without emitting evidence (hot path).
        """
        return await verify_purpose_limitation(payload, ctx)
