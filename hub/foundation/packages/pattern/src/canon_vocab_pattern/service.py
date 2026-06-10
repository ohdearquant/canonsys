"""Pattern service - thin wrapper over pattern detection phrases.

The service layer provides:
- Evidence emission via hooks
- RequestContext management

All logic lives in phrases/.

Regulatory Context:
    - SOX Section 302 (Management assessment)
    - BSA/AML (Suspicious activity patterns)
    - Employment law (Progressive discipline)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from canon.enforcement.service import CanonService, CanonServiceConfig, action

from .phrases import (
    check_pattern_threshold,
    check_prior_bypasses,
    check_prior_escalations,
    check_prior_exemptions,
    derive_cumulative_amount,
    derive_cumulative_exception_amount,
    derive_cumulative_reallocation_amount,
    derive_manager_bypass_count_12m,
    derive_manager_salary_exception_count_12m,
    derive_prior_action_count,
)

if TYPE_CHECKING:
    from canon.enforcement.service import RequestContext

__all__ = ["PatternService"]


class PatternService(CanonService):
    """Pattern service - detects compliance patterns.

    Thin wrapper that delegates to phrase functions.
    All phrases are read-only derivations/checks (no mutations).
    """

    config: ClassVar[CanonServiceConfig] = CanonServiceConfig(provider="canon", name="pattern")

    @action(skip_evidence=True)
    async def derive_prior_action_count(self, payload: dict, ctx: RequestContext) -> dict:
        """Derive count of prior actions within lookback window."""
        return await derive_prior_action_count(payload, ctx)

    @action(skip_evidence=True)
    async def check_pattern_threshold(self, payload: dict, ctx: RequestContext) -> dict:
        """Check if prior action count meets or exceeds threshold."""
        return await check_pattern_threshold(payload, ctx)

    @action(skip_evidence=True)
    async def derive_cumulative_amount(self, payload: dict, ctx: RequestContext) -> dict:
        """Sum amounts over period for anti-gaming detection."""
        return await derive_cumulative_amount(payload, ctx)

    @action(skip_evidence=True)
    async def derive_manager_bypass_count_12m(self, payload: dict, ctx: RequestContext) -> dict:
        """this surface: Derive manager posting bypass count over 12 months."""
        return await derive_manager_bypass_count_12m(payload, ctx)

    @action(skip_evidence=True)
    async def derive_manager_salary_exception_count_12m(
        self, payload: dict, ctx: RequestContext
    ) -> dict:
        """this surface: Derive manager salary exception count over 12 months."""
        return await derive_manager_salary_exception_count_12m(payload, ctx)

    @action(skip_evidence=True)
    async def check_prior_escalations(self, payload: dict, ctx: RequestContext) -> dict:
        """this surface: Check prior privilege escalations."""
        return await check_prior_escalations(payload, ctx)

    @action(skip_evidence=True)
    async def check_prior_exemptions(self, payload: dict, ctx: RequestContext) -> dict:
        """this surface: Check prior MFA exemptions."""
        return await check_prior_exemptions(payload, ctx)

    @action(skip_evidence=True)
    async def check_prior_bypasses(self, payload: dict, ctx: RequestContext) -> dict:
        """this surface: Check prior application bypasses."""
        return await check_prior_bypasses(payload, ctx)

    @action(skip_evidence=True)
    async def derive_cumulative_reallocation_amount(
        self, payload: dict, ctx: RequestContext
    ) -> dict:
        """this surface: Derive cumulative budget reallocation amount."""
        return await derive_cumulative_reallocation_amount(payload, ctx)

    @action(skip_evidence=True)
    async def derive_cumulative_exception_amount(self, payload: dict, ctx: RequestContext) -> dict:
        """this surface: Derive cumulative expense exception amount."""
        return await derive_cumulative_exception_amount(payload, ctx)
