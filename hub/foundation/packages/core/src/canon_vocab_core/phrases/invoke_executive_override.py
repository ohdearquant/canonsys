"""Invoke executive override phrase.

Policy deviation with executive authority.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import BaseModel

from canon.db import TenantScope, insert
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import compute_hash, now_utc

from ..types import ExecutiveOverride, OverrideAuthority

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["InvokeExecutiveOverrideSpecs", "invoke_executive_override"]


class InvokeExecutiveOverrideSpecs(BaseModel):
    """Specs for invoke executive override phrase.

    Creates a certificate with DEGRADED defensibility requiring Legal review.
    """

    # inputs
    authority: OverrideAuthority
    override_scope: str
    policy_deviation: str
    attestation_text: str
    referenced_certificate_id: UUID | None = None
    # outputs
    override_id: UUID
    override_hash: str
    created_at: datetime
    risk_acceptance: bool


@canon_phrase(
    Operable.from_structure(InvokeExecutiveOverrideSpecs),
    inputs={
        "authority",
        "override_scope",
        "policy_deviation",
        "attestation_text",
        "referenced_certificate_id",
    },
    outputs={"override_id", "override_hash", "created_at", "risk_acceptance"},
)
async def invoke_executive_override(
    options: dict,
    ctx: RequestContext,
) -> dict:
    """Invoke executive override for policy deviation.

    This is NOT a bypass - it creates a certificate with DEGRADED
    defensibility that requires Legal review.

    Args:
        options: Override options (authority, override_scope, policy_deviation, attestation_text)
        ctx: Request context (tenant, actor)

    Returns:
        dict with override record details

    Raises:
        ValueError: If attestation too short or actor missing.
    """
    authority: OverrideAuthority = options["authority"]
    override_scope: str = options["override_scope"]
    policy_deviation: str = options["policy_deviation"]
    attestation_text: str = options.get("attestation_text", "")
    referenced_certificate_id: UUID | None = options.get("referenced_certificate_id")

    if len(attestation_text.strip()) < 50:
        raise ValueError("Executive attestation must be substantive (min 50 characters)")

    if not ctx.actor_id:
        raise ValueError("Executive override requires identified actor")

    if ctx.tenant_id is None:
        raise ValueError("Executive override requires tenant context")

    now = now_utc()
    override_id = uuid4()

    # Compute override hash
    hash_data = {
        "id": str(override_id),
        "authority": authority.value,
        "override_scope": override_scope,
        "policy_deviation": policy_deviation,
        "attestation_text": attestation_text,
        "created_at": now.isoformat(),
    }
    override_hash = compute_hash(hash_data)

    override = ExecutiveOverride(
        id=override_id,
        tenant_id=ctx.tenant_id,
        authority=authority,
        authority_user_id=ctx.actor_id,
        override_scope=override_scope,
        policy_deviation=policy_deviation,
        risk_acceptance=True,  # Always true - that's the point
        override_hash=override_hash,
        created_at=now,
        referenced_certificate_id=referenced_certificate_id,
        attestation_text=attestation_text,
    )

    # Persist
    row_data = {
        "id": override.id,
        "tenant_id": override.tenant_id,
        "authority": override.authority.value,
        "authority_user_id": override.authority_user_id,
        "override_scope": override.override_scope,
        "policy_deviation": override.policy_deviation,
        "risk_acceptance": override.risk_acceptance,
        "override_hash": override.override_hash,
        "created_at": override.created_at,
        "referenced_certificate_id": override.referenced_certificate_id,
        "attestation_text": override.attestation_text,
    }

    await insert(
        "executive_overrides",
        row_data,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    return {
        "override_id": override.id,
        "override_hash": override.override_hash,
        "created_at": override.created_at,
        "risk_acceptance": override.risk_acceptance,
    }
