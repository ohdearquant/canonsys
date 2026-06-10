"""Grant lifecycle management for Charter Runtime.

Manages JIT (Just-In-Time) document access grants tied to phase lifecycle.
Grants are created when phases activate and revoked when phases complete.

Grant Types:
    - Phase-scoped (ttl_minutes=None): Active while phase is pending, auto-revoked on completion
    - Time-scoped (ttl_minutes=N): Has explicit expiry independent of phase status

Regulatory Context:
    - FCRA 1681b(b)(3): Consent-based access to consumer reports
    - GDPR Art. 5(1)(c): Data minimization - access only what's needed
    - SOC 2 CC6.1: Principle of least privilege

Usage:
    from canon.runtime.grants import create_phase_grant, revoke_phase_grants

    # When phase activates - create grants for assignee
    token_id = await create_phase_grant(
        run_id=run_id,
        phase_name="hm_approval",
        grant=GrantNode(document_type="resume", ttl_minutes=None),
        grantee_id=user_id,
        subject_id=candidate_id,
        tenant_id=tenant_id,
        conn=conn,
    )

    # When phase completes - revoke all phase grants
    revoked_count = await revoke_phase_grants(
        run_id=run_id,
        phase_name="hm_approval",
        user_id=actor_id,
        reason="Phase completed",
        conn=conn,
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from canon.db import TenantScope, fetch, insert_entity
from canon.entities.workflows.document_access import (
    DocumentAccessToken,
    DocumentAccessTokenContent,
)
from canon.entities.workflows.queue import DocumentAccessPurpose, DocumentAccessStatus

if TYPE_CHECKING:
    from canon.dsl.ast import GrantNode

__all__ = (
    "AccessCheckResult",
    "GrantResult",
    "check_document_access",
    "create_phase_grant",
    "document_type_to_purpose",
    "get_active_grants",
    "revoke_phase_grants",
    "transfer_phase_grants",
)

logger = logging.getLogger(__name__)

# Default safety window for phase-scoped grants (revoked on completion, but
# if revocation fails this provides a fallback expiry)
PHASE_GRANT_SAFETY_HOURS = 48


@dataclass(frozen=True, slots=True)
class GrantResult:
    """Result of a grant operation."""

    token_id: UUID
    document_type: str
    grantee_id: UUID
    subject_id: UUID
    expires_at: datetime | None
    is_phase_scoped: bool

    def to_dict(self) -> dict:
        """Serialize for logging/evidence."""
        return {
            "token_id": str(self.token_id),
            "document_type": self.document_type,
            "grantee_id": str(self.grantee_id),
            "subject_id": str(self.subject_id),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_phase_scoped": self.is_phase_scoped,
        }


@dataclass(frozen=True, slots=True)
class AccessCheckResult:
    """Result of a document access check."""

    allowed: bool
    token_id: UUID | None
    reason: str
    document_type: str | None = None
    subject_id: UUID | None = None

    def to_dict(self) -> dict:
        """Serialize for API responses."""
        return {
            "allowed": self.allowed,
            "token_id": str(self.token_id) if self.token_id else None,
            "reason": self.reason,
            "document_type": self.document_type,
            "subject_id": str(self.subject_id) if self.subject_id else None,
        }


async def check_document_access(
    *,
    user_id: UUID,
    subject_id: UUID,
    document_type: str,
    conn,
) -> AccessCheckResult:
    """Check if a user has a valid grant to access a document.

    Queries the document_access_tokens table for an active, non-expired
    token matching the user, subject, and document type.

    Args:
        user_id: User requesting access.
        subject_id: Person whose document is being accessed.
        document_type: Type of document (e.g., 'resume').
        conn: Database connection.

    Returns:
        AccessCheckResult with allowed=True and token_id if valid grant exists.
    """
    now = datetime.now(UTC)

    query = """
        SELECT id, status, expires_at, workflow_instance_id
        FROM document_access_tokens
        WHERE grantee_id = $1
          AND subject_id = $2
          AND document_type = $3
          AND status IN ('active', 'used')
          AND expires_at > $4
        ORDER BY issued_at DESC
        LIMIT 1
    """

    rows = await fetch(query, user_id, subject_id, document_type, now, conn=conn)

    if not rows:
        return AccessCheckResult(
            allowed=False,
            token_id=None,
            reason=f"No valid grant for document type '{document_type}'",
            document_type=document_type,
            subject_id=subject_id,
        )

    row = rows[0]
    token_id = row["id"]

    logger.debug(
        "Access granted: user %s -> %s for subject %s (token: %s)",
        user_id,
        document_type,
        subject_id,
        token_id,
    )

    return AccessCheckResult(
        allowed=True,
        token_id=token_id,
        reason="Valid document access grant",
        document_type=document_type,
        subject_id=subject_id,
    )


async def record_document_access(
    *,
    token_id: UUID,
    conn,
) -> None:
    """Record that a document was accessed via a grant token.

    Updates access tracking fields on the token.

    Args:
        token_id: DocumentAccessToken ID.
        conn: Database connection.
    """
    now = datetime.now(UTC)

    await fetch(
        """
        UPDATE document_access_tokens
        SET status = 'used',
            access_count = access_count + 1,
            last_accessed_at = $1,
            first_accessed_at = COALESCE(first_accessed_at, $1),
            updated_at = $1
        WHERE id = $2
        RETURNING id
        """,
        now,
        token_id,
        conn=conn,
    )


def document_type_to_purpose(document_type: str) -> DocumentAccessPurpose:
    """Map document type to access purpose.

    Args:
        document_type: Document type from charter grant (e.g., 'resume').

    Returns:
        Appropriate DocumentAccessPurpose enum value.
    """
    mapping = {
        "resume": DocumentAccessPurpose.RESUME_REVIEW,
        "background_report": DocumentAccessPurpose.BACKGROUND_CHECK,
        "offer_letter": DocumentAccessPurpose.OFFER_REVIEW,
        "offer_letter_draft": DocumentAccessPurpose.OFFER_REVIEW,
        "pip_plan": DocumentAccessPurpose.PIP_REVIEW,
        "performance_report": DocumentAccessPurpose.PIP_REVIEW,
        "termination_certificate": DocumentAccessPurpose.TERMINATION_REVIEW,
        "decision_certificate": DocumentAccessPurpose.TERMINATION_REVIEW,
        "separation_agreement": DocumentAccessPurpose.TERMINATION_REVIEW,
    }
    return mapping.get(document_type, DocumentAccessPurpose.RESUME_REVIEW)


async def create_phase_grant(
    *,
    run_id: UUID,
    phase_name: str,
    grant: GrantNode,
    grantee_id: UUID,
    subject_id: UUID,
    tenant_id: UUID,
    phase_execution_id: UUID | None = None,
    conn,
) -> GrantResult:
    """Create a document access grant for a phase.

    Creates a DocumentAccessToken with:
    - Phase-scoped (no TTL): Active while phase pending, safety expiry at +48h
    - Time-scoped (TTL): Explicit expiry from ttl_minutes

    The grant is automatically revoked when the phase completes via
    revoke_phase_grants(). Time-scoped grants may expire before phase
    completion.

    Args:
        run_id: CharterRun ID.
        phase_name: Name of the phase issuing the grant.
        grant: GrantNode from charter AST with document_type and ttl_minutes.
        grantee_id: User ID receiving access.
        subject_id: Person ID whose documents are being accessed.
        tenant_id: Tenant ID.
        phase_execution_id: Optional PhaseExecution ID for tracking.
        conn: Database connection.

    Returns:
        GrantResult with token details.
    """
    now = datetime.now(UTC)

    # Determine expiration
    if grant.ttl_minutes is not None:
        # Time-scoped grant - explicit TTL
        expires_at = now + timedelta(minutes=grant.ttl_minutes)
        is_phase_scoped = False
    else:
        # Phase-scoped grant - safety window (will be revoked on completion)
        expires_at = now + timedelta(hours=PHASE_GRANT_SAFETY_HOURS)
        is_phase_scoped = True

    # Determine purpose from document type
    purpose = document_type_to_purpose(grant.document_type)

    # Create the token
    token_id = uuid4()
    token = DocumentAccessToken(
        id=token_id,
        created_at=now,
        content=DocumentAccessTokenContent(
            tenant_id=tenant_id,
            subject_id=subject_id,
            grantee_id=grantee_id,
            workflow_instance_id=run_id,
            workflow_step_id=phase_execution_id,
            document_type=grant.document_type,
            purpose=purpose,
            status=DocumentAccessStatus.ACTIVE,
            issued_at=now,
            expires_at=expires_at,
        ),
    )

    await insert_entity(token, conn=conn, tenant_scope=TenantScope.DISABLED)

    logger.info(
        "Created document grant '%s' for phase '%s' (run: %s, grantee: %s, "
        "expires: %s, phase_scoped: %s)",
        grant.document_type,
        phase_name,
        run_id,
        grantee_id,
        expires_at.isoformat() if not is_phase_scoped else "phase-scoped",
        is_phase_scoped,
    )

    return GrantResult(
        token_id=token_id,
        document_type=grant.document_type,
        grantee_id=grantee_id,
        subject_id=subject_id,
        expires_at=expires_at,
        is_phase_scoped=is_phase_scoped,
    )


async def revoke_phase_grants(
    *,
    run_id: UUID,
    phase_name: str,
    user_id: UUID,
    reason: str,
    conn,
) -> int:
    """Revoke all grants associated with a phase.

    Called when a phase completes (approved/rejected/skipped) to revoke
    phase-scoped document access. This implements the principle of least
    privilege - access ends when the need ends.

    Args:
        run_id: CharterRun ID.
        phase_name: Name of the phase whose grants to revoke.
        user_id: User performing the revocation (for audit).
        reason: Reason for revocation (e.g., "Phase completed").
        conn: Database connection.

    Returns:
        Number of tokens revoked.

    Note:
        This revokes ALL tokens for the phase, including those that may
        have already been used or that have time-based expiry. The audit
        trail is preserved.
    """
    now = datetime.now(UTC)

    # We need to find tokens by:
    # 1. workflow_instance_id = run_id (the CharterRun)
    # 2. status in ('active', 'used') - don't re-revoke already revoked

    # The schema doesn't have granted_by_phase directly, but we can use
    # workflow_step_id which links to the PhaseExecution. However, the
    # simpler approach is to query all active tokens for the run and check
    # if they match the phase via phase_execution lookup.

    # For now, use the simpler approach: revoke tokens where:
    # - workflow_instance_id = run_id
    # - status in ('active', 'used')

    # In a more sophisticated implementation, we'd track granted_by_phase
    # on the token directly (as shown in the spec).

    revoke_query = """
        UPDATE document_access_tokens
        SET status = $1,
            revoked_at = $2,
            revoked_by_id = $3,
            revocation_reason = $4,
            updated_at = $2
        WHERE workflow_instance_id = $5
          AND status IN ('active', 'used')
        RETURNING id, document_type, grantee_id
    """

    revoked_rows = await fetch(
        revoke_query,
        DocumentAccessStatus.REVOKED.value,
        now,
        user_id,
        f"Phase '{phase_name}' completed: {reason}",
        run_id,
        conn=conn,
    )

    revoked_count = len(revoked_rows)

    # Log each revoked token
    for row in revoked_rows:
        logger.info(
            "Revoked document grant '%s' (token: %s, grantee: %s, reason: %s)",
            row["document_type"],
            row["id"],
            row["grantee_id"],
            reason,
        )

    if revoked_count > 0:
        logger.info(
            "Revoked %d document grants for phase '%s' (run: %s, reason: %s)",
            revoked_count,
            phase_name,
            run_id,
            reason,
        )

    return revoked_count


async def transfer_phase_grants(
    *,
    run_id: UUID,
    phase_name: str,
    grants: list[GrantNode],
    from_user_id: UUID,
    to_user_id: UUID,
    subject_id: UUID,
    tenant_id: UUID,
    phase_execution_id: UUID | None,
    conn,
) -> list[GrantResult]:
    """Transfer document grants from one user to another.

    Used when a phase is delegated to another user. Creates new grants
    for the delegate first, then revokes the old grants. This order
    prevents access gaps if new grant creation fails.

    Args:
        run_id: CharterRun ID.
        phase_name: Name of the phase.
        grants: List of GrantNode from charter AST.
        from_user_id: User losing access.
        to_user_id: User gaining access.
        subject_id: Person whose documents are being accessed.
        tenant_id: Tenant ID.
        phase_execution_id: Optional PhaseExecution ID.
        conn: Database connection.

    Returns:
        List of GrantResult for newly created tokens.
    """
    # First, create new grants for the delegate
    new_grants: list[GrantResult] = []

    for grant in grants:
        result = await create_phase_grant(
            run_id=run_id,
            phase_name=phase_name,
            grant=grant,
            grantee_id=to_user_id,
            subject_id=subject_id,
            tenant_id=tenant_id,
            phase_execution_id=phase_execution_id,
            conn=conn,
        )
        new_grants.append(result)

    # Only revoke old grants after new ones are successfully created
    # This is a partial revoke - only tokens for the from_user
    now = datetime.now(UTC)

    revoke_query = """
        UPDATE document_access_tokens
        SET status = $1,
            revoked_at = $2,
            revoked_by_id = $3,
            revocation_reason = $4,
            updated_at = $2
        WHERE workflow_instance_id = $5
          AND grantee_id = $6
          AND status IN ('active', 'used')
        RETURNING id, document_type
    """

    revoked_rows = await fetch(
        revoke_query,
        DocumentAccessStatus.REVOKED.value,
        now,
        from_user_id,
        f"Phase '{phase_name}' delegated to user {to_user_id}",
        run_id,
        from_user_id,
        conn=conn,
    )

    logger.info(
        "Transferred %d document grants from user %s to user %s for phase '%s' "
        "(run: %s, revoked: %d old grants)",
        len(new_grants),
        from_user_id,
        to_user_id,
        phase_name,
        run_id,
        len(revoked_rows),
    )

    return new_grants


async def get_active_grants(
    *,
    run_id: UUID,
    phase_execution_id: UUID | None = None,
    grantee_id: UUID | None = None,
    conn,
) -> list[dict]:
    """Get active grants for a run, optionally filtered by phase or grantee.

    Args:
        run_id: CharterRun ID.
        phase_execution_id: Optional PhaseExecution ID to filter by.
        grantee_id: Optional user ID to filter by.
        conn: Database connection.

    Returns:
        List of active grant records as dicts.
    """
    now = datetime.now(UTC)

    # Build query with optional filters
    conditions = [
        "workflow_instance_id = $1",
        "status IN ('active', 'used')",
        "expires_at > $2",
    ]
    params: list = [run_id, now]

    if phase_execution_id:
        conditions.append(f"workflow_step_id = ${len(params) + 1}")
        params.append(phase_execution_id)

    if grantee_id:
        conditions.append(f"grantee_id = ${len(params) + 1}")
        params.append(grantee_id)

    query = f"""
        SELECT id, document_type, grantee_id, subject_id, purpose,
               status, issued_at, expires_at, access_count
        FROM document_access_tokens
        WHERE {" AND ".join(conditions)}
        ORDER BY issued_at DESC
    """

    rows = await fetch(query, *params, conn=conn)
    return [dict(row) for row in rows]
