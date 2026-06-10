"""Verify that a specific role has approved a request.

Complete vertical slice:
- Queries approvals with role information
- Supports delegation chains
- Returns verification result (does not raise)

Regulatory:
    - SOX Section 404 (Internal controls require appropriate authority)
    - SOC 2 CC6.1 (Logical access controls)
    - GDPR Art. 37-39 (DPO requirements for privacy matters)
    - ISO 27001 A.6.1.1 (Roles and responsibilities)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = [
    "VerifyRoleApprovalSpecs",
    "verify_board_approval",
    "verify_cfo_approval",
    "verify_ciso_approval",
    "verify_compliance_approval",
    "verify_cto_approval",
    "verify_dpo_approval",
    "verify_executive_approval",
    "verify_gc_approval",
    "verify_hr_approval",
    "verify_role_approval",
]


class VerifyRoleApprovalSpecs(BaseModel):
    """Specs for verify role approval phrase."""

    # inputs
    request_id: UUID
    required_role: str
    allow_delegation: bool = True
    max_delegation_depth: int = 2
    # outputs (defaults required for instantiation with inputs only)
    approved: bool = False
    approver_id: UUID | None = None
    approver_name: str | None = None
    approved_at: datetime | None = None
    delegation_chain: tuple[str, ...] | None = None
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(VerifyRoleApprovalSpecs),
    inputs={"request_id", "required_role", "allow_delegation", "max_delegation_depth"},
    outputs={
        "approved",
        "request_id",
        "required_role",
        "approver_id",
        "approver_name",
        "approved_at",
        "delegation_chain",
        "reason",
    },
)
async def verify_role_approval(
    options: VerifyRoleApprovalSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify that a specific role has approved a request.

    Checks the approval chain for a request and verifies that an approver
    with the required role (or valid delegation) has approved.

    Args:
        options: Options containing request_id, required_role, allow_delegation, max_delegation_depth
        ctx: Request context with connection

    Returns:
        Dict with approval status and metadata.
    """
    request_id: UUID = options.request_id
    required_role = options.required_role.upper()
    allow_delegation = options.allow_delegation
    max_delegation_depth = options.max_delegation_depth

    # Query for approvals on this request with role information
    query = """
        SELECT
            a.approver_id,
            a.approved_at,
            p.name as approver_name,
            p.role as approver_role,
            d.delegation_chain
        FROM approvals a
        JOIN principals p ON a.approver_id = p.id
        LEFT JOIN LATERAL (
            SELECT array_agg(delegator_role ORDER BY depth) as delegation_chain
            FROM approval_delegations
            WHERE delegatee_id = a.approver_id
              AND delegated_role = $2
              AND is_active = true
              AND depth <= $3
        ) d ON true
        WHERE a.request_id = $1
          AND a.status = 'approved'
          AND (
              p.role = $2
              OR ($4 = true AND d.delegation_chain IS NOT NULL)
          )
        ORDER BY a.approved_at DESC
        LIMIT 1
    """

    row = await ctx.conn.fetchrow(
        query,
        request_id,
        required_role,
        max_delegation_depth,
        allow_delegation,
    )

    if not row:
        return {
            "approved": False,
            "request_id": request_id,
            "required_role": required_role,
            "approver_id": None,
            "approver_name": None,
            "approved_at": None,
            "delegation_chain": None,
            "reason": f"No approval from {required_role} found",
        }

    # Build delegation chain tuple if present
    delegation_chain = None
    if row["delegation_chain"]:
        delegation_chain = tuple(row["delegation_chain"])

    return {
        "approved": True,
        "request_id": request_id,
        "required_role": required_role,
        "approver_id": row["approver_id"],
        "approver_name": row["approver_name"],
        "approved_at": row["approved_at"],
        "delegation_chain": delegation_chain,
        "reason": None,
    }


# =============================================================================
# Convenience wrappers for common roles
# These use the same VerifyRoleApprovalSpecs but with pre-filled role
# =============================================================================


async def verify_ciso_approval(
    request_id: UUID,
    ctx: RequestContext,
    *,
    allow_delegation: bool = True,
) -> dict:
    """Verify CISO approval for security-sensitive requests.

    Regulatory:
        - SOC 2 CC6.1 (Logical access controls)
        - ISO 27001 A.6.1.1 (Information security roles)
    """
    options = {
        "request_id": request_id,
        "required_role": "CISO",
        "allow_delegation": allow_delegation,
    }
    return await verify_role_approval(options, ctx)


async def verify_cfo_approval(
    request_id: UUID,
    ctx: RequestContext,
    *,
    allow_delegation: bool = True,
) -> dict:
    """Verify CFO approval for financial requests.

    Regulatory:
        - SOX Section 302 (CEO/CFO certification)
        - SOX Section 404 (Internal controls)
    """
    options = {
        "request_id": request_id,
        "required_role": "CFO",
        "allow_delegation": allow_delegation,
    }
    return await verify_role_approval(options, ctx)


async def verify_gc_approval(
    request_id: UUID,
    ctx: RequestContext,
    *,
    allow_delegation: bool = True,
) -> dict:
    """Verify General Counsel approval for legal requests.

    Regulatory:
        - Various litigation hold requirements
        - Employment law compliance
    """
    options = {
        "request_id": request_id,
        "required_role": "GC",
        "allow_delegation": allow_delegation,
    }
    return await verify_role_approval(options, ctx)


async def verify_dpo_approval(
    request_id: UUID,
    ctx: RequestContext,
    *,
    allow_delegation: bool = True,
) -> dict:
    """Verify Data Protection Officer approval for privacy requests.

    Regulatory:
        - GDPR Art. 37-39 (DPO designation and tasks)
        - CCPA/CPRA (Privacy officer requirements)
    """
    options = {
        "request_id": request_id,
        "required_role": "DPO",
        "allow_delegation": allow_delegation,
    }
    return await verify_role_approval(options, ctx)


async def verify_cto_approval(
    request_id: UUID,
    ctx: RequestContext,
    *,
    allow_delegation: bool = True,
) -> dict:
    """Verify CTO approval for technology and architecture decisions.

    Regulatory:
        - SOC 2 CC6.6 (Change management)
        - ISO 27001 A.12.1.2 (Change management)
        - PCI-DSS 6.4 (Change control procedures)
    """
    options = {
        "request_id": request_id,
        "required_role": "CTO",
        "allow_delegation": allow_delegation,
    }
    return await verify_role_approval(options, ctx)


async def verify_executive_approval(
    request_id: UUID,
    ctx: RequestContext,
    *,
    allow_delegation: bool = True,
) -> dict:
    """Verify executive sponsor approval for strategic decisions.

    Regulatory:
        - SOX Section 302 (Executive certification)
        - SOC 2 CC1.1 (Management oversight)
        - ISO 27001 A.5.1 (Management direction)
    """
    options = {
        "request_id": request_id,
        "required_role": "EXEC_SPONSOR",
        "allow_delegation": allow_delegation,
    }
    return await verify_role_approval(options, ctx)


async def verify_hr_approval(
    request_id: UUID,
    ctx: RequestContext,
    *,
    allow_delegation: bool = True,
) -> dict:
    """Verify HR approval for employment and personnel decisions.

    Regulatory:
        - FCRA (Pre-adverse action notice requirements)
        - EEOC (Equal employment opportunity compliance)
        - ADA (Accommodation request processing)
        - FMLA (Leave management authorization)
    """
    options = {
        "request_id": request_id,
        "required_role": "HR",
        "allow_delegation": allow_delegation,
    }
    return await verify_role_approval(options, ctx)


async def verify_board_approval(
    request_id: UUID,
    ctx: RequestContext,
    *,
    allow_delegation: bool = False,
) -> dict:
    """Verify Board of Directors approval for governance-level decisions.

    Board approval typically cannot be delegated due to fiduciary duties.

    Regulatory:
        - SOX Section 301 (Audit committee requirements)
        - SOX Section 404 (Material weakness disclosure)
        - SEC Rule 10A-3 (Audit committee independence)
        - NYSE/NASDAQ listing requirements (Board oversight)
    """
    options = {
        "request_id": request_id,
        "required_role": "BOARD",
        "allow_delegation": allow_delegation,
    }
    return await verify_role_approval(options, ctx)


async def verify_compliance_approval(
    request_id: UUID,
    ctx: RequestContext,
    *,
    allow_delegation: bool = True,
) -> dict:
    """Verify Chief Compliance Officer approval for regulatory matters.

    Regulatory:
        - SOX Section 406 (Code of ethics for senior officers)
        - BSA/AML (Anti-money laundering compliance)
        - OFAC (Sanctions compliance)
        - SOC 2 CC2.1 (Board and management oversight)
    """
    options = {
        "request_id": request_id,
        "required_role": "COMPLIANCE",
        "allow_delegation": allow_delegation,
    }
    return await verify_role_approval(options, ctx)
