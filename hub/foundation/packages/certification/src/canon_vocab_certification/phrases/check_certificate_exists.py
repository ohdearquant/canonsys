"""Check if a certified certificate exists for a case.

Used to enforce certificate immutability - once certified,
cannot regenerate. This is a precondition check.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, fetch
from canon.enforcement import RequestContext
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

__all__ = ["CheckCertificateExistsSpecs", "check_certificate_exists"]


class CheckCertificateExistsSpecs(BaseModel):
    """Specs for certificate existence check phrase."""

    # inputs
    case_id: UUID
    certificate_type: str | None = None
    # outputs
    exists: bool | None = None
    certificate_id: UUID | None = None
    certified_at: datetime | None = None
    certificate_hash: str | None = None


@canon_phrase(
    Operable.from_structure(CheckCertificateExistsSpecs),
    inputs={"case_id", "certificate_type"},
    outputs={
        "case_id",
        "exists",
        "certificate_id",
        "certified_at",
        "certificate_hash",
        "certificate_type",
    },
)
async def check_certificate_exists(
    options: CheckCertificateExistsSpecs,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> dict:
    """Check if certified certificate exists for case.

    Queries evidence where:
    - data.case_id matches
    - data.certified = True
    - data.certificate_hash exists

    Args:
        options: Check options containing case_id, optional certificate_type
        ctx: Request context (tenant)
        conn: Optional DB connection

    Returns:
        Dict with exists flag and certificate details if found
    """
    # Query evidence for certified certificates
    # Check data.certified == True and data.certificate_hash exists
    # Use JSONB operators for efficient filtering
    if options.certificate_type is not None:
        sql = """
            SELECT id, evidence_type, data->>'certificate_hash' AS certificate_hash,
                   (data->>'certified_at')::timestamptz AS certified_at
            FROM evidences
            WHERE tenant_id = $1
              AND data->>'case_id' = $2
              AND (data->>'certified')::boolean = true
              AND data ? 'certificate_hash'
              AND evidence_type = $3
              AND is_deleted = false
            ORDER BY collected_at DESC
            LIMIT 1
        """
        args: tuple[Any, ...] = (
            ctx.tenant_id,
            str(options.case_id),
            options.certificate_type,
        )
    else:
        sql = """
            SELECT id, evidence_type, data->>'certificate_hash' AS certificate_hash,
                   (data->>'certified_at')::timestamptz AS certified_at
            FROM evidences
            WHERE tenant_id = $1
              AND data->>'case_id' = $2
              AND (data->>'certified')::boolean = true
              AND data ? 'certificate_hash'
              AND is_deleted = false
            ORDER BY collected_at DESC
            LIMIT 1
        """
        args = (ctx.tenant_id, str(options.case_id))

    rows = await fetch(
        sql,
        *args,
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not rows:
        return {
            "case_id": options.case_id,
            "exists": False,
            "certificate_id": None,
            "certified_at": None,
            "certificate_hash": None,
            "certificate_type": None,
        }

    row = rows[0]
    return {
        "case_id": options.case_id,
        "exists": True,
        "certificate_id": row["id"],
        "certified_at": row["certified_at"],
        "certificate_hash": row["certificate_hash"],
        "certificate_type": row["evidence_type"],
    }
