"""Policy protocols and types.

Defines contracts for policy resolution and evaluation.
Implementations provided by domain libs (e.g., canon-core).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from kron.types import DataClass, Enum

from .context import RequestContext

__all__ = (
    "EnforcementLevel",
    "PolicyEngine",
    "PolicyResolver",
    "ResolvedPolicy",
)


class EnforcementLevel(Enum):
    """How strictly to enforce policy violations.

    HARD_MANDATORY: Blocks action, no override possible
    SOFT_MANDATORY: Blocks action, but can be overridden with justification
    ADVISORY: Warns but allows action to proceed
    """

    HARD_MANDATORY = "hard_mandatory"
    SOFT_MANDATORY = "soft_mandatory"
    ADVISORY = "advisory"

    @classmethod
    def is_blocking(cls, result: Any) -> bool:
        """Check if policy result blocks the action."""
        enforcement = getattr(result, "enforcement", "")
        return enforcement in (
            cls.HARD_MANDATORY.value,
            cls.SOFT_MANDATORY.value,
        )

    @classmethod
    def is_advisory(cls, result: Any) -> bool:
        """Check if policy result is advisory (not blocking)."""
        return getattr(result, "enforcement", "") == cls.ADVISORY.value


@dataclass(slots=True)
class ResolvedPolicy(DataClass):
    """A policy resolved for evaluation.

    Returned by PolicyResolver.resolve(). Contains policy ID and
    any resolution metadata needed by the engine.
    """

    policy_id: str
    enforcement: str = EnforcementLevel.HARD_MANDATORY.value
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class PolicyEngine(Protocol):
    """Abstract policy evaluation engine.

    kron defines the contract. Implementations:
    - canon-core: OPAEngine (Rego/Regorus evaluation)
    - Testing: MockPolicyEngine
    """

    async def evaluate(
        self,
        policy_id: str,
        input_data: dict[str, Any],
        **options: Any,
    ) -> Any:
        """Evaluate a single policy against input."""
        ...

    async def evaluate_batch(
        self,
        policy_ids: Sequence[str],
        input_data: dict[str, Any],
        **options: Any,
    ) -> list[Any]:
        """Evaluate multiple policies."""
        ...


@runtime_checkable
class PolicyResolver(Protocol):
    """Resolves which policies apply to a given context.

    kron defines the contract. Implementations:
    - canon-core: CharteredResolver (charter-based resolution)
    - Testing: MockPolicyResolver, StaticPolicyResolver
    """

    def resolve(self, ctx: RequestContext) -> Sequence[ResolvedPolicy]:
        """Determine applicable policies for context."""
        ...
