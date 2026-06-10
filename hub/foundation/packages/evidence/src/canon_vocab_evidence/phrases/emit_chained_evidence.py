"""Emit chained evidence with hash-linking.

Complete vertical slice:
- Creates new evidence entry and persists it
- Links it into a tamper-evident chain via hash-linking
- Handles genesis (new chain) and continuation (existing chain)
- Returns chain metadata for further operations

Regulatory: FRE 901, ISO 27037, SOX Section 802
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from pydantic import BaseModel

from canon.db import TenantScope, insert, insert_entity, select
from canon.enforcement.executor import canon_phrase
from canon.entities import ChainEntry, ChainEntryContent, Evidence, EvidenceContent
from kron.specs import Operable
from kron.utils import compute_hash

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["EmitChainedEvidenceSpecs", "emit_chained_evidence"]


class EmitChainedEvidenceSpecs(BaseModel):
    """Specs for emit chained evidence phrase."""

    # inputs
    subject_id: UUID
    evidence_type: str
    content: dict[str, Any]
    chain_id: UUID | None = None  # None = create new chain (genesis)
    previous_hash: str | None = None  # Explicit chaining override
    # outputs
    evidence_id: UUID | None = None
    sequence_number: int | None = None
    content_hash: str | None = None


@canon_phrase(
    Operable.from_structure(EmitChainedEvidenceSpecs),
    inputs={"subject_id", "evidence_type", "content", "chain_id", "previous_hash"},
    outputs={
        "evidence_id",
        "chain_id",
        "sequence_number",
        "content_hash",
        "previous_hash",
        "evidence_type",
    },
)
async def emit_chained_evidence(
    options: EmitChainedEvidenceSpecs,
    ctx: RequestContext,
) -> dict:
    """Emit a new evidence entry linked into a tamper-evident chain.

    Creates an Evidence record and a corresponding ChainEntry that
    hash-links it to the previous entry in the chain. If no chain_id
    is provided, a new chain is created with this as the genesis entry.

    Hash-linking scheme:
        payload_hash = SHA-256(canonical JSON of evidence content)
        chain_hash   = SHA-256({previous_hash, payload_hash, sequence})
        previous_hash links to the prior entry's chain_hash (None for genesis)

    Args:
        options: Emission options containing subject, evidence type, content,
            and optional chain/hash parameters.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with evidence_id, chain_id, sequence_number, content_hash,
        previous_hash, evidence_type.

    Raises:
        ValueError: If tenant context is invalid.

    Regulatory basis:
        - FRE 901: Authentication of evidence
        - ISO 27037: Digital evidence handling
        - SOX Section 802: Document integrity
    """
    subject_id = options.subject_id
    evidence_type = options.evidence_type
    content = options.content
    chain_id = options.chain_id
    explicit_previous_hash = options.previous_hash

    # Compute content hash from the evidence payload
    content_hash = compute_hash(content)

    # Create and persist Evidence entity
    evidence_content = EvidenceContent(
        tenant_id=ctx.tenant_id,
        subject_id=subject_id,
        evidence_type=evidence_type,
        data=content,
    )
    evidence = Evidence(content=evidence_content)

    saved = await insert_entity(
        evidence,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    # Determine chain membership
    is_genesis = chain_id is None
    if is_genesis:
        chain_id = uuid4()

    # Resolve previous_hash and sequence number
    if is_genesis:
        previous_hash: str | None = None
        sequence = 0
    else:
        # Look up the latest entry in this chain
        latest_entries = await select(
            "chain_entrys",
            where={"resource_id": chain_id, "resource_type": "evidence_chain"},
            order_by="sequence DESC",
            limit=1,
            conn=ctx.conn,
            tenant_scope=TenantScope.REQUIRED,
        )

        if latest_entries:
            latest = latest_entries[0]
            previous_hash = (
                explicit_previous_hash
                if explicit_previous_hash is not None
                else latest["chain_hash"]
            )
            sequence = latest["sequence"] + 1
        else:
            # chain_id provided but no entries exist yet -- treat as genesis
            previous_hash = explicit_previous_hash  # may be None
            sequence = 0

    # Compute chain hash for tamper-evident linking
    chain_data = {
        "previous_hash": previous_hash,
        "payload_hash": content_hash,
        "sequence": sequence,
    }
    chain_hash = compute_hash(chain_data)

    # Create ChainEntry linking evidence into the chain
    entry_content = ChainEntryContent(
        tenant_id=ctx.tenant_id,
        subject_id=subject_id,
        actor_id=ctx.actor_id,
        event_type="evidence_emitted",
        resource_type="evidence_chain",
        resource_id=chain_id,
        payload_hash=content_hash,
        previous_hash=previous_hash,
        chain_hash=chain_hash,
        sequence=sequence,
        payload={"evidence_id": str(saved.id), "evidence_type": evidence_type},
    )

    entry = ChainEntry(content=entry_content)

    row_data = {
        "id": entry.id,
        "created_at": entry.created_at,
        "tenant_id": entry_content.tenant_id,
        "subject_id": entry_content.subject_id,
        "actor_id": entry_content.actor_id,
        "event_type": entry_content.event_type,
        "resource_type": entry_content.resource_type,
        "resource_id": entry_content.resource_id,
        "payload_hash": entry_content.payload_hash,
        "previous_hash": entry_content.previous_hash,
        "chain_hash": entry_content.chain_hash,
        "sequence": entry_content.sequence,
        "payload": entry_content.payload,
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
        "evidence_id": saved.id,
        "chain_id": chain_id,
        "sequence_number": sequence,
        "content_hash": content_hash,
        "previous_hash": previous_hash,
        "evidence_type": evidence_type,
    }
