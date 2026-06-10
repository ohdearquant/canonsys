"""Core types for policy enforcement.

Provides:
- EnforcementLevel: From canon.enforcement.policy (canonical location)
- PolicyResult: Re-exported from canon.utils.opa.types
- AggregatedResult: Re-exported from canon.utils.opa.types
- ServiceContext: Service-level context for policy resolution
- ctx_to_evidence_data: Serialize RequestContext for evidence storage
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

# Canonical definition in canon.enforcement.policy
from canon.enforcement.policy import EnforcementLevel
from canon.utils.opa.types import AggregatedResult, PolicyResult

__all__ = (
    # From canon.enforcement.policy
    "EnforcementLevel",
    # Re-exported from canon.utils.opa.types
    "PolicyResult",
    "AggregatedResult",
    # Local types
    "ServiceContext",
    "ctx_to_evidence_data",
)


@dataclass
class ServiceContext:
    """Service-level context - resolved at service init.

    Provides tenant and charter for policy resolution.

    This is NOT per-request. See RequestContext for request-level state.
    """

    tenant_id: UUID
    """Tenant this service instance serves."""

    charter: Charter | None = None  # type: ignore[name-defined]
    """Active charter - policy_ids controls situational gate activation."""

    jurisdiction: str | None = None
    """Primary jurisdiction scope for this service."""

    service_name: str | None = None
    """Service identifier."""


def ctx_to_evidence_data(ctx: Any) -> dict[str, Any]:
    """Serialize RequestContext for evidence storage.

    Works with kron's RequestContext — reads fields from metadata via
    __getattr__. UUIDs are stringified, None values preserved.
    """

    def _str_or_none(val: Any) -> str | None:
        return str(val) if val is not None else None

    charter = ctx.charter
    jurisdictions = ctx.jurisdictions
    gate_results = ctx.gate_results

    return {
        "tenant_id": _str_or_none(ctx.tenant_id),
        "actor_id": _str_or_none(ctx.actor_id),
        "subject_id": _str_or_none(ctx.subject_id),
        "organization_id": _str_or_none(ctx.organization_id),
        "request_id": _str_or_none(ctx.request_id),
        "correlation_id": _str_or_none(ctx.correlation_id),
        "causation_id": _str_or_none(ctx.causation_id),
        "service_name": ctx.service_name,
        "action": ctx.action,
        "jurisdictions": list(jurisdictions) if jurisdictions else [],
        "policy_version": ctx.policy_version,
        "policy_library_hash": ctx.policy_library_hash,
        "charter_version": (
            charter.content.version if charter and hasattr(charter, "content") else None
        ),
        "gate_results": gate_results or [],
    }
