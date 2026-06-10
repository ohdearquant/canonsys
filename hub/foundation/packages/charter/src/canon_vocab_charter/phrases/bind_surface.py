"""Bind a surface to a charter.

Complete vertical slice:
- Creates binding between charter and decision surface
- Records policy version and evidence requirements
- Enables decision evaluation for the bound surface
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel

from canon.db import TenantScope, insert, select_one
from canon.enforcement import RequestContext
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

from ..exceptions import (
    CharterNotFoundError,
    CharterStatusError,
    SurfaceAlreadyBoundError,
)
from ..types import CharterStatus

__all__ = ["BindSurfaceSpecs", "bind_surface"]


class BindSurfaceSpecs(BaseModel):
    """Specs for bind surface phrase."""

    # inputs
    charter_id: UUID
    surface_id: str
    policy_version: str
    evidence_requirements: list[str] | None = None

    # outputs
    binding_id: UUID | None = None
    bound_at: datetime | None = None


@canon_phrase(
    Operable.from_structure(BindSurfaceSpecs),
    inputs={"charter_id", "surface_id", "policy_version", "evidence_requirements"},
    outputs={
        "binding_id",
        "charter_id",
        "surface_id",
        "policy_version",
        "evidence_requirements",
        "bound_at",
    },
)
async def bind_surface(
    options: dict,
    ctx: RequestContext,
) -> dict:
    """Bind a surface to a charter.

    A surface represents a decision point in the system (e.g., "hiring.offer",
    "termination.involuntary"). Binding a surface to a charter:
    1. Associates the surface with the charter's policy configuration
    2. Records the policy version for audit trail
    3. Specifies evidence requirements for decisions on this surface

    Args:
        options: Binding options (charter_id, surface_id, policy_version, evidence_requirements)
        ctx: Request context (tenant, actor)

    Returns:
        Dict with binding details

    Raises:
        CharterNotFoundError: If charter doesn't exist
        CharterStatusError: If charter is not in valid state for binding
        SurfaceAlreadyBoundError: If surface is already bound
    """
    charter_id = options.get("charter_id")
    surface_id = options.get("surface_id")
    policy_version = options.get("policy_version")
    evidence_requirements = options.get("evidence_requirements")

    if not charter_id:
        raise ValueError("charter_id is required")
    if not surface_id:
        raise ValueError("surface_id is required")
    if not policy_version:
        raise ValueError("policy_version is required")

    # Fetch charter
    charter_row = await select_one(
        "charters",
        where={"id": charter_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not charter_row:
        raise CharterNotFoundError(str(charter_id))

    if charter_row["tenant_id"] != ctx.tenant_id:
        raise CharterStatusError(
            str(charter_id),
            current_status="tenant_mismatch",
            required_status="matching_tenant",
        )

    # Allow binding to DRAFT or ACTIVE charters
    current_status = charter_row.get("status", "unknown")
    valid_statuses = {
        CharterStatus.DRAFT.value,
        CharterStatus.ACTIVE.value,
    }
    if current_status not in valid_statuses:
        raise CharterStatusError(
            str(charter_id),
            current_status=current_status,
            required_status="draft or active",
        )

    # Check if surface is already bound
    existing_binding = await select_one(
        "charter_surface_bindings",
        where={"charter_id": charter_id, "surface_id": surface_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if existing_binding:
        raise SurfaceAlreadyBoundError(str(charter_id), surface_id)

    now = now_utc()
    binding_id = uuid4()
    requirements = tuple(evidence_requirements or [])

    # Create binding
    row_data = {
        "id": binding_id,
        "tenant_id": ctx.tenant_id,
        "charter_id": charter_id,
        "surface_id": surface_id,
        "policy_version": policy_version,
        "evidence_requirements": list(requirements),
        "bound_at": now,
        "bound_by": str(ctx.actor_id) if ctx.actor_id else None,
    }

    await insert(
        "charter_surface_bindings",
        row_data,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    return {
        "binding_id": binding_id,
        "charter_id": charter_id,
        "surface_id": surface_id,
        "policy_version": policy_version,
        "evidence_requirements": requirements,
        "bound_at": now,
    }
