"""Create a new charter in DRAFT status.

Complete vertical slice:
- Creates charter with content hash for integrity
- Initializes in DRAFT status (immutable after activation)
- Validates tenant ownership
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel

from canon.db import TenantScope, insert
from canon.enforcement import RequestContext
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import compute_hash, now_utc

from ..types import CharterStatus

__all__ = ["CreateCharterSpecs", "create_charter"]


class CreateCharterSpecs(BaseModel):
    """Specs for create charter phrase."""

    # inputs
    name: str
    version: str
    description: str | None = None
    effective_date: datetime | None = None
    expiry_date: datetime | None = None

    # outputs
    charter_id: UUID | None = None
    tenant_id: UUID | None = None
    status: CharterStatus | None = None
    created_at: datetime | None = None
    content_hash: str | None = None


@canon_phrase(
    Operable.from_structure(CreateCharterSpecs),
    inputs={"name", "version", "description", "effective_date", "expiry_date"},
    outputs={
        "charter_id",
        "tenant_id",
        "version",
        "status",
        "created_at",
        "content_hash",
    },
)
async def create_charter(
    options: dict,
    ctx: RequestContext,
) -> dict:
    """Create a new charter in DRAFT status.

    Creates a charter governance document that defines:
    - Name and version for identification
    - Effective date range for enforcement
    - Surfaces are bound separately via bind_surface

    Charters are immutable after activation. Changes require creating
    a new charter version.

    Args:
        options: Charter creation options (name, version, description, dates)
        ctx: Request context (tenant, actor)

    Returns:
        Dict with charter_id and metadata

    Raises:
        ValueError: If required fields are missing
    """
    name = options.get("name")
    version = options.get("version")
    description = options.get("description")
    effective_date = options.get("effective_date")
    expiry_date = options.get("expiry_date")

    if not name:
        raise ValueError("Charter name is required")
    if not version:
        raise ValueError("Charter version is required")

    now = now_utc()
    charter_id = uuid4()

    # Compute content hash for integrity verification
    hash_data = {
        "tenant_id": str(ctx.tenant_id),
        "name": name,
        "version": version,
        "description": description,
        "effective_date": effective_date.isoformat() if effective_date else None,
        "expiry_date": expiry_date.isoformat() if expiry_date else None,
    }
    content_hash = compute_hash(hash_data)

    # Prepare row data
    row_data = {
        "id": charter_id,
        "tenant_id": ctx.tenant_id,
        "name": name,
        "version": version,
        "description": description,
        "status": CharterStatus.DRAFT.value,
        "effective_date": effective_date,
        "expiry_date": expiry_date,
        "content_hash": content_hash,
        "created_at": now,
        "updated_at": now,
        "created_by": str(ctx.actor_id) if ctx.actor_id else None,
    }

    await insert(
        "charters",
        row_data,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    return {
        "charter_id": charter_id,
        "tenant_id": ctx.tenant_id,
        "version": version,
        "status": CharterStatus.DRAFT,
        "created_at": now,
        "content_hash": content_hash,
    }
