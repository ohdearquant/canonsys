"""User inbox derivation - efficient queries for pending phases.

The inbox shows all phases waiting for a user's action. A phase appears
in a user's inbox when:
- status = 'waiting_user' (gates passed, waiting for action)
- assignee_id = user_id OR assignee_role in user.roles

This module provides efficient queries using the indexes defined on
phase_executions (tenant_id, status, assignee_role) and
(tenant_id, status, assignee_id).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from canon.entities.charter import PhaseStatus

if TYPE_CHECKING:
    import asyncpg

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class InboxItem:
    """A pending phase in a user's inbox.

    Represents a phase waiting for the user's action, with context
    about the charter run and subject.
    """

    # Phase identification
    run_id: UUID
    """Charter run this phase belongs to."""

    phase_execution_id: UUID
    """PhaseExecution record ID."""

    workflow_name: str
    """Name of the workflow."""

    phase_name: str
    """Name of this phase."""

    # Assignment
    assignee_role: str | None
    """Role required to act on this phase."""

    assignee_id: UUID | None
    """Specific user assigned (if claimed)."""

    # Charter context
    charter_id: UUID
    """Charter being executed."""

    charter_name: str
    """Human-readable charter name."""

    # Subject context
    subject_id: UUID
    """Person this run is about."""

    subject_name: str
    """Full name of the subject."""

    # Related entity
    related_entity_type: str
    """Type of related entity (offer, pip, etc.)."""

    related_entity_id: UUID
    """ID of the related entity."""

    # Timing
    waiting_since: datetime
    """When this phase became waiting_user."""

    waiting_days: int
    """Number of days waiting (for display)."""

    is_overdue: bool
    """Whether this phase is past SLA."""

    is_priority: bool
    """Whether this phase is high priority."""

    # Grants
    grant_document_types: list[str]
    """Document types accessible via grants for this phase."""


# Default SLA thresholds (could be made configurable)
OVERDUE_DAYS = 5
PRIORITY_DAYS = 3


async def get_user_inbox(
    user_id: UUID,
    tenant_id: UUID,
    conn: asyncpg.Connection,
    *,
    include_claimed_by_others: bool = False,
    limit: int | None = None,
) -> list[InboxItem]:
    """Get all pending phases assigned to a user.

    A phase is in user's inbox when:
    - status = 'waiting_user'
    - assignee_id = user_id OR assignee_role in user.roles

    Uses efficient indexed queries on phase_executions.

    Args:
        user_id: User UUID to get inbox for.
        tenant_id: Tenant UUID for isolation.
        conn: Database connection.
        include_claimed_by_others: If True, include phases where
            assignee_role matches but another user has claimed it.
            Default False (only show unclaimed or self-claimed).
        limit: Maximum number of items to return. None for all.

    Returns:
        List of InboxItem sorted by waiting_since (oldest first).
    """
    now = datetime.now(UTC)

    # Build the query with role-based matching
    # We join to users to get the user's roles, then match phases
    # where either assignee_id matches OR assignee_role is in user's roles
    query = """
        SELECT
            pe.id as phase_execution_id,
            pe.run_id,
            pe.workflow_name,
            pe.phase_name,
            pe.assignee_role,
            pe.assignee_id,
            pe.activated_at as waiting_since,
            pe.grant_token_ids,
            cr.charter_id,
            cr.subject_id,
            cr.related_entity_type,
            cr.related_entity_id,
            c.name as charter_name,
            COALESCE(p.first_name || ' ' || p.last_name, 'Unknown') as subject_name
        FROM phase_executions pe
        JOIN charter_runs cr ON pe.run_id = cr.id
        JOIN charters c ON cr.charter_id = c.id
        LEFT JOIN persons p ON cr.subject_id = p.id
        CROSS JOIN LATERAL (
            SELECT role FROM users WHERE id = $1
        ) u
        WHERE pe.tenant_id = $2
          AND pe.status = $3
          AND cr.status = 'active'
          AND (
              pe.assignee_id = $1
              OR (pe.assignee_role = u.role)
          )
    """

    # Optionally filter out phases claimed by others
    if not include_claimed_by_others:
        query += """
          AND (pe.assignee_id IS NULL OR pe.assignee_id = $1)
        """

    query += " ORDER BY pe.activated_at ASC"

    if limit:
        query += f" LIMIT {int(limit)}"

    rows = await conn.fetch(query, user_id, tenant_id, PhaseStatus.WAITING_USER)

    items: list[InboxItem] = []
    for row in rows:
        waiting_since = row["waiting_since"] or now
        waiting_delta = now - waiting_since
        waiting_days = max(0, waiting_delta.days)

        # Parse grant document types from grant_token_ids
        # (Would need to join to document_access_tokens for full grant info)
        grant_document_types: list[str] = []

        items.append(
            InboxItem(
                run_id=row["run_id"],
                phase_execution_id=row["phase_execution_id"],
                workflow_name=row["workflow_name"],
                phase_name=row["phase_name"],
                assignee_role=row["assignee_role"],
                assignee_id=row["assignee_id"],
                charter_id=row["charter_id"],
                charter_name=row["charter_name"],
                subject_id=row["subject_id"],
                subject_name=row["subject_name"],
                related_entity_type=row["related_entity_type"],
                related_entity_id=row["related_entity_id"],
                waiting_since=waiting_since,
                waiting_days=waiting_days,
                is_overdue=waiting_days >= OVERDUE_DAYS,
                is_priority=waiting_days >= PRIORITY_DAYS,
                grant_document_types=grant_document_types,
            )
        )

    logger.debug("Found %d inbox items for user %s", len(items), user_id)
    return items


async def get_inbox_count(
    user_id: UUID,
    tenant_id: UUID,
    conn: asyncpg.Connection,
) -> int:
    """Get count of pending phases for a user (for badge display).

    Efficient count query without loading full phase data.

    Args:
        user_id: User UUID.
        tenant_id: Tenant UUID.
        conn: Database connection.

    Returns:
        Number of phases in user's inbox.
    """
    count = await conn.fetchval(
        """
        SELECT COUNT(*)
        FROM phase_executions pe
        JOIN charter_runs cr ON pe.run_id = cr.id
        CROSS JOIN LATERAL (
            SELECT role FROM users WHERE id = $1
        ) u
        WHERE pe.tenant_id = $2
          AND pe.status = $3
          AND cr.status = 'active'
          AND (
              pe.assignee_id = $1
              OR (pe.assignee_role = u.role)
          )
          AND (pe.assignee_id IS NULL OR pe.assignee_id = $1)
        """,
        user_id,
        tenant_id,
        PhaseStatus.WAITING_USER,
    )
    return count or 0


async def get_inbox_by_role(
    role: str,
    tenant_id: UUID,
    conn: asyncpg.Connection,
    *,
    limit: int | None = None,
) -> list[InboxItem]:
    """Get all pending phases for a specific role (admin view).

    Shows all phases waiting for users with a given role,
    regardless of whether they've been claimed.

    Args:
        role: Role name (e.g., "hiring_manager", "svp").
        tenant_id: Tenant UUID.
        conn: Database connection.
        limit: Maximum number of items.

    Returns:
        List of InboxItem for the role.
    """
    now = datetime.now(UTC)

    query = """
        SELECT
            pe.id as phase_execution_id,
            pe.run_id,
            pe.workflow_name,
            pe.phase_name,
            pe.assignee_role,
            pe.assignee_id,
            pe.activated_at as waiting_since,
            pe.grant_token_ids,
            cr.charter_id,
            cr.subject_id,
            cr.related_entity_type,
            cr.related_entity_id,
            c.name as charter_name,
            COALESCE(p.first_name || ' ' || p.last_name, 'Unknown') as subject_name
        FROM phase_executions pe
        JOIN charter_runs cr ON pe.run_id = cr.id
        JOIN charters c ON cr.charter_id = c.id
        LEFT JOIN persons p ON cr.subject_id = p.id
        WHERE pe.tenant_id = $1
          AND pe.status = $2
          AND pe.assignee_role = $3
          AND cr.status = 'active'
        ORDER BY pe.activated_at ASC
    """

    if limit:
        query += f" LIMIT {int(limit)}"

    rows = await conn.fetch(query, tenant_id, PhaseStatus.WAITING_USER, role)

    items: list[InboxItem] = []
    for row in rows:
        waiting_since = row["waiting_since"] or now
        waiting_delta = now - waiting_since
        waiting_days = max(0, waiting_delta.days)

        items.append(
            InboxItem(
                run_id=row["run_id"],
                phase_execution_id=row["phase_execution_id"],
                workflow_name=row["workflow_name"],
                phase_name=row["phase_name"],
                assignee_role=row["assignee_role"],
                assignee_id=row["assignee_id"],
                charter_id=row["charter_id"],
                charter_name=row["charter_name"],
                subject_id=row["subject_id"],
                subject_name=row["subject_name"],
                related_entity_type=row["related_entity_type"],
                related_entity_id=row["related_entity_id"],
                waiting_since=waiting_since,
                waiting_days=waiting_days,
                is_overdue=waiting_days >= OVERDUE_DAYS,
                is_priority=waiting_days >= PRIORITY_DAYS,
                grant_document_types=[],
            )
        )

    logger.debug("Found %d inbox items for role %s", len(items), role)
    return items


async def get_overdue_phases(
    tenant_id: UUID,
    conn: asyncpg.Connection,
    *,
    threshold_days: int = OVERDUE_DAYS,
) -> list[InboxItem]:
    """Get all overdue phases for a tenant (admin/monitoring).

    Returns phases that have been waiting longer than the threshold.

    Args:
        tenant_id: Tenant UUID.
        conn: Database connection.
        threshold_days: Days after which a phase is considered overdue.

    Returns:
        List of overdue InboxItem.
    """
    now = datetime.now(UTC)
    threshold = now - timedelta(days=threshold_days)

    query = """
        SELECT
            pe.id as phase_execution_id,
            pe.run_id,
            pe.workflow_name,
            pe.phase_name,
            pe.assignee_role,
            pe.assignee_id,
            pe.activated_at as waiting_since,
            pe.grant_token_ids,
            cr.charter_id,
            cr.subject_id,
            cr.related_entity_type,
            cr.related_entity_id,
            c.name as charter_name,
            COALESCE(p.first_name || ' ' || p.last_name, 'Unknown') as subject_name
        FROM phase_executions pe
        JOIN charter_runs cr ON pe.run_id = cr.id
        JOIN charters c ON cr.charter_id = c.id
        LEFT JOIN persons p ON cr.subject_id = p.id
        WHERE pe.tenant_id = $1
          AND pe.status = $2
          AND pe.activated_at < $3
          AND cr.status = 'active'
        ORDER BY pe.activated_at ASC
    """

    rows = await conn.fetch(query, tenant_id, PhaseStatus.WAITING_USER, threshold)

    items: list[InboxItem] = []
    for row in rows:
        waiting_since = row["waiting_since"] or now
        waiting_delta = now - waiting_since
        waiting_days = max(0, waiting_delta.days)

        items.append(
            InboxItem(
                run_id=row["run_id"],
                phase_execution_id=row["phase_execution_id"],
                workflow_name=row["workflow_name"],
                phase_name=row["phase_name"],
                assignee_role=row["assignee_role"],
                assignee_id=row["assignee_id"],
                charter_id=row["charter_id"],
                charter_name=row["charter_name"],
                subject_id=row["subject_id"],
                subject_name=row["subject_name"],
                related_entity_type=row["related_entity_type"],
                related_entity_id=row["related_entity_id"],
                waiting_since=waiting_since,
                waiting_days=waiting_days,
                is_overdue=True,  # By definition
                is_priority=True,  # Overdue implies priority
                grant_document_types=[],
            )
        )

    logger.debug("Found %d overdue phases for tenant %s", len(items), tenant_id)
    return items
