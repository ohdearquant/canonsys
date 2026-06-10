"""Freshness service - thin wrapper over freshness phrases.

The service layer provides:
- Evidence emission via hooks
- RequestContext management

All logic lives in phrases/.

Regulatory Context:
    - SOX Section 302/404: Quarterly certifications and internal controls
    - GDPR Art. 5(1)(d): Data accuracy
    - FCRA Section 604: Report freshness requirements
    - PCI DSS 7.2: Access control systems review
    - Breach notification laws: 72h GDPR, varies by state
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from canon.enforcement.service import CanonService, CanonServiceConfig, action

from .phrases import (
    check_equity_staleness,
    check_legal_review_freshness,
    check_privilege_review,
    check_receipt_freshness,
    check_tia_freshness,
    derive_extension_days,
    derive_filing_deadline,
    derive_quarter_end,
    derive_regulatory_deadline,
    verify_credit_freshness,
)

if TYPE_CHECKING:
    from canon.enforcement.service import RequestContext

__all__ = ["FreshnessService"]


class FreshnessService(CanonService):
    """Freshness service - manages timing and staleness compliance.

    Thin wrapper that delegates to phrase functions.
    All operations are read-only checks/derivations (skip_evidence=True).
    """

    config: ClassVar[CanonServiceConfig] = CanonServiceConfig(provider="canon", name="freshness")

    @action(skip_evidence=True)
    async def check_equity_staleness(self, payload: dict, ctx: RequestContext) -> dict:
        """Check equity data staleness (SOX Section 404)."""
        return await check_equity_staleness(payload, ctx)

    @action(skip_evidence=True)
    async def check_legal_review_freshness(self, payload: dict, ctx: RequestContext) -> dict:
        """Check legal review freshness (compliance requirement)."""
        return await check_legal_review_freshness(payload, ctx)

    @action(skip_evidence=True)
    async def check_privilege_review(self, payload: dict, ctx: RequestContext) -> dict:
        """Check privilege review freshness (PCI DSS 7.2)."""
        return await check_privilege_review(payload, ctx)

    @action(skip_evidence=True)
    async def check_receipt_freshness(self, payload: dict, ctx: RequestContext) -> dict:
        """Check receipt freshness for audit trail."""
        return await check_receipt_freshness(payload, ctx)

    @action(skip_evidence=True)
    async def check_tia_freshness(self, payload: dict, ctx: RequestContext) -> dict:
        """Check Transfer Impact Assessment freshness (GDPR)."""
        return await check_tia_freshness(payload, ctx)

    @action(skip_evidence=True)
    async def derive_extension_days(self, payload: dict, ctx: RequestContext) -> dict:
        """Derive extension days based on business rules."""
        return await derive_extension_days(payload, ctx)

    @action(skip_evidence=True)
    async def derive_filing_deadline(self, payload: dict, ctx: RequestContext) -> dict:
        """Derive filing deadline (SOX Section 302)."""
        return await derive_filing_deadline(payload, ctx)

    @action(skip_evidence=True)
    async def derive_quarter_end(self, payload: dict, ctx: RequestContext) -> dict:
        """Derive fiscal quarter end date (SOX Section 404)."""
        return await derive_quarter_end(payload, ctx)

    @action(skip_evidence=True)
    async def derive_regulatory_deadline(self, payload: dict, ctx: RequestContext) -> dict:
        """Derive regulatory deadline based on jurisdiction."""
        return await derive_regulatory_deadline(payload, ctx)

    @action(skip_evidence=True)
    async def verify_credit_freshness(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify credit assessment freshness (FCRA Section 604)."""
        return await verify_credit_freshness(payload, ctx)
