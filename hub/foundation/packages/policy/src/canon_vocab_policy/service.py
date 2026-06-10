"""Policy service - thin wrapper over policy phrases.

The service layer provides:
- Evidence emission via hooks
- RequestContext management

All logic lives in phrases/.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from canon.enforcement.service import CanonService, CanonServiceConfig, action

from .phrases import (
    CreateAdapterSpecs,
    CreateDefinitionSpecs,
    CreateReleaseSpecs,
    EvaluatePolicySpecs,
    PublishReleaseSpecs,
    ResolvePolicySpecs,
    create_policy_adapter,
    create_policy_definition,
    create_policy_release,
    evaluate_policy,
    publish_policy_release,
    resolve_policy,
)

if TYPE_CHECKING:
    from canon.enforcement.service import RequestContext

__all__ = ["PolicyService"]


class PolicyService(CanonService):
    """Policy service - manages policy lifecycle and evaluation.

    Thin wrapper that delegates to phrase functions.
    """

    config: ClassVar[CanonServiceConfig] = CanonServiceConfig(
        provider="canon",
        name="policy",
    )

    # =========================================================================
    # Definition Management
    # =========================================================================

    @action(evidence_type="policy.definition.create")
    async def create_definition(self, payload: dict, ctx: RequestContext) -> dict:
        """Create a new policy definition (Legal-owned)."""
        options = CreateDefinitionSpecs(**payload)
        return await create_policy_definition(options, ctx)

    # =========================================================================
    # Adapter Management
    # =========================================================================

    @action(evidence_type="policy.adapter.create")
    async def create_adapter(self, payload: dict, ctx: RequestContext) -> dict:
        """Create a new policy adapter (Engineering-owned)."""
        options = CreateAdapterSpecs(**payload)
        return await create_policy_adapter(options, ctx)

    # =========================================================================
    # Release Management
    # =========================================================================

    @action(evidence_type="policy.release.create")
    async def create_release(self, payload: dict, ctx: RequestContext) -> dict:
        """Create a new policy release (draft)."""
        options = CreateReleaseSpecs(**payload)
        return await create_policy_release(options, ctx)

    @action(evidence_type="policy.release.publish")
    async def publish_release(self, payload: dict, ctx: RequestContext) -> dict:
        """Publish a policy release (freeze it)."""
        options = PublishReleaseSpecs(**payload)
        return await publish_policy_release(options, ctx)

    # =========================================================================
    # Evaluation
    # =========================================================================

    @action(skip_evidence=True)
    async def resolve(self, payload: dict, ctx: RequestContext) -> dict:
        """Resolve which policy version to use (hot path)."""
        options = ResolvePolicySpecs(**payload)
        return await resolve_policy(options, ctx)

    @action(evidence_type="policy.evaluate")
    async def evaluate(self, payload: dict, ctx: RequestContext) -> dict:
        """Evaluate a policy against input facts."""
        options = EvaluatePolicySpecs(**payload)
        return await evaluate_policy(options, ctx)
