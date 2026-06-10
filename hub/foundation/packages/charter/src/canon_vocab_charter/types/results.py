"""Result types for charter actions.

Frozen dataclasses following vocabulary conventions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .status import CharterStatus

if TYPE_CHECKING:
    from uuid import UUID

__all__ = (
    "ActivateCharterResult",
    "BindSurfaceResult",
    "CreateCharterResult",
    "DecisionResult",
    "SurfaceBinding",
)


@dataclass(frozen=True, slots=True)
class CreateCharterResult:
    """Result of charter creation."""

    charter_id: UUID
    tenant_id: UUID
    version: str
    status: CharterStatus
    created_at: datetime
    content_hash: str


@dataclass(frozen=True, slots=True)
class ActivateCharterResult:
    """Result of charter activation."""

    charter_id: UUID
    status: CharterStatus
    effective_from: datetime
    activated_at: datetime
    superseded_charter_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class SurfaceBinding:
    """A bound surface with its policy configuration."""

    binding_id: UUID
    charter_id: UUID
    surface_id: str
    policy_version: str
    evidence_requirements: tuple[str, ...] = ()
    bound_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class BindSurfaceResult:
    """Result of surface binding operation."""

    binding_id: UUID
    charter_id: UUID
    surface_id: str
    policy_version: str
    evidence_requirements: tuple[str, ...]
    bound_at: datetime


@dataclass(frozen=True, slots=True)
class DecisionResult:
    """Result of decision evaluation against charter policy.

    Represents the outcome of evaluating whether an action is allowed
    under the charter's active policies for a specific surface.
    """

    allowed: bool
    """Whether the decision is permitted under charter policy."""

    charter_id: UUID
    """Charter that was evaluated."""

    surface_id: str
    """Surface the decision applies to."""

    policy_version: str
    """Policy version used for evaluation."""

    evaluated_at: datetime
    """When evaluation occurred."""

    conditions_met: tuple[str, ...] = ()
    """Conditions that were satisfied."""

    conditions_missing: tuple[str, ...] = ()
    """Conditions that were not satisfied."""

    evidence_required: tuple[str, ...] = ()
    """Evidence types required before proceeding."""

    blocking_policies: tuple[str, ...] = ()
    """Policy IDs that blocked the decision."""

    advisory_warnings: tuple[str, ...] = ()
    """Non-blocking warnings from advisory policies."""

    evaluation_context: dict[str, Any] = field(default_factory=dict)
    """Additional context from evaluation."""

    @property
    def requires_evidence(self) -> bool:
        """Check if evidence is required before proceeding."""
        return len(self.evidence_required) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if there are advisory warnings."""
        return len(self.advisory_warnings) > 0
