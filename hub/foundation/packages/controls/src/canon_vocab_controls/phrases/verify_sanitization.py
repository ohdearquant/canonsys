"""Verify sanitization profile covers required data types.

Checks that a sanitization profile is properly configured and
covers all data types that require sanitization.

Regulatory Context:
    - GDPR Article 32 (Security of processing)
    - SOC 2 CC6.7 (Data sanitization)
    - NIST SP 800-88 (Media sanitization guidelines)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, fetch, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifySanitizationSpecs", "verify_sanitization_profile"]


class VerifySanitizationSpecs(BaseModel):
    """Specs for verify sanitization profile phrase."""

    # inputs
    profile_id: UUID
    required_data_types: list[str]
    # outputs
    valid: bool
    sanitization_level: str
    covers_data_types: tuple[str, ...]
    missing_coverage: tuple[str, ...]


@canon_phrase(
    Operable.from_structure(VerifySanitizationSpecs),
    inputs={"profile_id", "required_data_types"},
    outputs={
        "valid",
        "profile_id",
        "sanitization_level",
        "covers_data_types",
        "missing_coverage",
    },
)
async def verify_sanitization_profile(
    options: dict,
    ctx: RequestContext,
) -> dict:
    """Verify sanitization profile covers required data types.

    Checks that a sanitization profile is properly configured and
    covers all data types that require sanitization for a given
    processing context.

    Sanitization levels follow NIST SP 800-88:
    - clear: Logical techniques, data recoverable with effort
    - purge: Physical/logical techniques, data not recoverable
    - destroy: Physical destruction, media unusable

    Args:
        options: Verification options (profile_id, required_data_types)
        ctx: Request context (tenant, actor)

    Returns:
        dict with valid, profile_id, sanitization_level, covers_data_types, missing_coverage

    Regulatory:
        - GDPR Article 32: Appropriate security measures for processing
        - SOC 2 CC6.7: Secure disposal of data and media
        - NIST SP 800-88: Media sanitization categorization
    """
    profile_id = options.get("profile_id")
    required_data_types = options.get("required_data_types") or []

    if not required_data_types:
        # No requirements - query profile for metadata only
        row = await select_one(
            "sanitization_profiles",
            where={
                "profile_id": profile_id,
                "tenant_id": ctx.tenant_id,
                "status": "active",
            },
            conn=ctx.conn,
            tenant_scope=TenantScope.REQUIRED,
        )

        if not row:
            return {
                "valid": False,
                "profile_id": profile_id,
                "sanitization_level": "unknown",
                "covers_data_types": (),
                "missing_coverage": (),
            }

        return {
            "valid": True,
            "profile_id": profile_id,
            "sanitization_level": row.get("sanitization_level", "unknown"),
            "covers_data_types": (),
            "missing_coverage": (),
        }

    # Query profile and its covered data types
    query = """
        SELECT
            sp.profile_id,
            sp.sanitization_level,
            ARRAY_AGG(spc.data_type) AS covered_types
        FROM sanitization_profiles sp
        LEFT JOIN sanitization_profile_coverage spc
            ON spc.profile_id = sp.profile_id
        WHERE sp.profile_id = $1
          AND sp.tenant_id = $2
          AND sp.status = 'active'
        GROUP BY sp.profile_id, sp.sanitization_level
    """
    rows = await fetch(
        query,
        profile_id,
        ctx.tenant_id,
        conn=ctx.conn,
    )
    row = rows[0] if rows else None

    if not row:
        return {
            "valid": False,
            "profile_id": profile_id,
            "sanitization_level": "unknown",
            "covers_data_types": (),
            "missing_coverage": tuple(required_data_types),
        }

    covered_types = set(row.get("covered_types") or [])
    required_set = set(required_data_types)

    missing = required_set - covered_types

    return {
        "valid": len(missing) == 0,
        "profile_id": profile_id,
        "sanitization_level": row.get("sanitization_level", "unknown"),
        "covers_data_types": tuple(sorted(covered_types & required_set)),
        "missing_coverage": tuple(sorted(missing)),
    }
