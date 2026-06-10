"""Chain evidence entries together.

Complete vertical slice:
- Creates ChainEntry linking evidence in tamper-evident chain
- Computes hash linking for integrity verification
- Handles genesis (first entry) and continuation
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, insert, select_one
from canon.enforcement.executor import canon_phrase
from canon.entities import ChainEntry, ChainEntryContent
from kron.specs import Operable
from kron.utils import compute_hash

if TYPE_CHECKING:
    from canon.enforcement import RequestContext
    from canon.entities import Evidence

__all__ = [
    "ChainEvidenceSpecs",
    "CreateGenesisEntrySpecs",
    "chain_evidence",
    "create_genesis_entry",
]


class ChainEvidenceSpecs(BaseModel):
    """Specs for chain evidence phrase."""

    # inputs
    parent: Any  # Evidence entity
    child: Any  # Evidence entity
    event_type: str = "evidence_linked"
    # outputs
    entry_id: UUID | None = None
    chain_hash: str | None = None
    sequence: int | None = None


class CreateGenesisEntrySpecs(BaseModel):
    """Specs for create genesis entry phrase."""

    # inputs
    evidence: Any  # Evidence entity
    event_type: str = "evidence_collected"
    # outputs
    entry_id: UUID | None = None
    chain_hash: str | None = None


@canon_phrase(
    Operable.from_structure(ChainEvidenceSpecs),
    inputs={"parent", "child", "event_type"},
    outputs={"entry_id", "chain_hash", "sequence"},
)
async def chain_evidence(
    options: ChainEvidenceSpecs,
    ctx: RequestContext,
) -> dict:
    """Create chain entry linking parent -> child evidence.

    Args:
        options: Chain options containing parent, child evidence
        ctx: Request context (tenant, actor)

    Returns:
        Dict with entry_id, chain_hash, sequence

    Raises:
        ValueError: If evidence belongs to different tenants
    """
    parent: Evidence = options.parent
    child: Evidence = options.child
    event_type = options.event_type

    # Validate same tenant
    if parent.content.tenant_id != child.content.tenant_id:
        raise ValueError("Cannot chain evidence across tenants")

    if parent.content.tenant_id != ctx.tenant_id:
        raise ValueError("Evidence tenant doesn't match context")

    # Get parent's chain entry for previous_hash
    parent_chain = await select_one(
        "chain_entrys",
        where={"resource_id": parent.id, "resource_type": "evidence"},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not parent_chain:
        raise ValueError(f"Parent evidence {parent.id} has no chain entry")

    previous_hash = parent_chain["chain_hash"]
    sequence = parent_chain["sequence"] + 1

    # Compute chain hash
    chain_data = {
        "previous_hash": previous_hash,
        "payload_hash": child.content_hash,
        "sequence": sequence,
    }
    chain_hash = compute_hash(chain_data)

    content = ChainEntryContent(
        tenant_id=ctx.tenant_id,
        subject_id=child.content.subject_id,
        actor_id=ctx.actor_id,
        event_type=event_type,
        resource_type="evidence",
        resource_id=child.id,
        payload_hash=child.content_hash or "",
        previous_hash=previous_hash,
        chain_hash=chain_hash,
        sequence=sequence,
    )

    entry = ChainEntry(content=content)

    # Insert chain entry
    row_data = {
        "id": entry.id,
        "created_at": entry.created_at,
        "tenant_id": content.tenant_id,
        "subject_id": content.subject_id,
        "actor_id": content.actor_id,
        "event_type": content.event_type,
        "resource_type": content.resource_type,
        "resource_id": content.resource_id,
        "payload_hash": content.payload_hash,
        "previous_hash": content.previous_hash,
        "chain_hash": content.chain_hash,
        "sequence": content.sequence,
        "payload": content.payload,
        "updated_at": entry.updated_at,
        "version": entry.version,
    }

    await insert(
        "chain_entrys",
        row_data,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    return {
        "entry_id": entry.id,
        "chain_hash": chain_hash,
        "sequence": sequence,
    }


@canon_phrase(
    Operable.from_structure(CreateGenesisEntrySpecs),
    inputs={"evidence", "event_type"},
    outputs={"entry_id", "chain_hash"},
)
async def create_genesis_entry(
    options: CreateGenesisEntrySpecs,
    ctx: RequestContext,
) -> dict:
    """Create genesis (first) chain entry for evidence.

    Args:
        options: Genesis options containing evidence
        ctx: Request context

    Returns:
        Dict with entry_id, chain_hash
    """
    evidence: Evidence = options.evidence
    event_type = options.event_type

    # Genesis entry has no previous_hash
    chain_data = {
        "previous_hash": None,
        "payload_hash": evidence.content_hash,
        "sequence": 0,
    }
    chain_hash = compute_hash(chain_data)

    content = ChainEntryContent(
        tenant_id=ctx.tenant_id,
        subject_id=evidence.content.subject_id,
        actor_id=ctx.actor_id,
        event_type=event_type,
        resource_type="evidence",
        resource_id=evidence.id,
        payload_hash=evidence.content_hash or "",
        previous_hash=None,
        chain_hash=chain_hash,
        sequence=0,
    )

    entry = ChainEntry(content=content)

    row_data = {
        "id": entry.id,
        "created_at": entry.created_at,
        "tenant_id": content.tenant_id,
        "subject_id": content.subject_id,
        "actor_id": content.actor_id,
        "event_type": content.event_type,
        "resource_type": content.resource_type,
        "resource_id": content.resource_id,
        "payload_hash": content.payload_hash,
        "previous_hash": content.previous_hash,
        "chain_hash": content.chain_hash,
        "sequence": content.sequence,
        "payload": content.payload,
        "updated_at": entry.updated_at,
        "version": entry.version,
    }

    await insert(
        "chain_entrys",
        row_data,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    return {
        "entry_id": entry.id,
        "chain_hash": chain_hash,
    }
