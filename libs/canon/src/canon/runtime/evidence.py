"""Automatic evidence recording for Charter Runtime.

Records audit-grade evidence for phase transitions, grant operations,
and workflow events. Evidence is immutable and forms the compliance
audit trail.

Evidence Types:
    - Phase transitions: activation, completion, failure, skip
    - Grant operations: issued, revoked, transferred
    - Workflow events: started, completed, failed

Regulatory Context:
    - SOX 404: Multi-level approval documentation
    - Employment law: Decision audit trail
    - FCRA: Access tracking for consumer reports

Usage:
    from canon.runtime.evidence import record_phase_evidence, record_grant_evidence

    # Record phase completion
    evidence_id = await record_phase_evidence(
        run_id=run_id,
        phase_name="hm_approval",
        event_type=EvidenceEventType.PHASE_COMPLETED,
        actor_id=user_id,
        tenant_id=tenant_id,
        subject_id=candidate_id,
        data={"action": "approve", "notes": "LGTM"},
        conn=conn,
    )

    # Record grant issuance
    evidence_id = await record_grant_evidence(
        token_id=token_id,
        event_type=EvidenceEventType.GRANT_ISSUED,
        actor_id=system_user_id,
        tenant_id=tenant_id,
        subject_id=candidate_id,
        data={"document_type": "resume", "grantee_id": str(user_id)},
        conn=conn,
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from canon.db import TenantScope, insert_entity
from canon.entities.evidence import Evidence, EvidenceContent

__all__ = (
    "EvidenceEventType",
    "EvidenceResult",
    "record_grant_evidence",
    "record_phase_evidence",
    "record_workflow_evidence",
)

logger = logging.getLogger(__name__)


class EvidenceEventType(StrEnum):
    """Types of events that generate evidence records.

    Naming Convention: {domain}_{action}
    - Domain: phase, grant, workflow
    - Action: what happened (activated, completed, etc.)
    """

    # Phase lifecycle events
    PHASE_ACTIVATED = "phase.activated"
    """Phase moved from pending to waiting_user."""

    PHASE_CLAIMED = "phase.claimed"
    """User claimed the phase (started work)."""

    PHASE_COMPLETED = "phase.completed"
    """Phase completed successfully (approved)."""

    PHASE_FAILED = "phase.failed"
    """Phase failed (rejected or gate failure)."""

    PHASE_SKIPPED = "phase.skipped"
    """Phase was skipped (conditional logic)."""

    PHASE_DELEGATED = "phase.delegated"
    """Phase was delegated to another user."""

    # Grant lifecycle events
    GRANT_ISSUED = "grant.issued"
    """Document access grant was issued."""

    GRANT_ACCESSED = "grant.accessed"
    """Document was accessed using the grant."""

    GRANT_REVOKED = "grant.revoked"
    """Grant was revoked (phase completed or manual)."""

    GRANT_EXPIRED = "grant.expired"
    """Grant expired due to TTL."""

    GRANT_TRANSFERRED = "grant.transferred"
    """Grant was transferred to another user (delegation)."""

    # Workflow lifecycle events
    WORKFLOW_STARTED = "workflow.started"
    """Charter workflow was initiated."""

    WORKFLOW_COMPLETED = "workflow.completed"
    """Workflow completed successfully (all phases done)."""

    WORKFLOW_FAILED = "workflow.failed"
    """Workflow failed (phase rejection or gate failure)."""

    WORKFLOW_CANCELLED = "workflow.cancelled"
    """Workflow was cancelled before completion."""

    # Trigger events
    TRIGGER_FIRED = "trigger.fired"
    """External trigger event was fired to unblock an await directive."""


@dataclass(frozen=True, slots=True)
class EvidenceResult:
    """Result of an evidence recording operation."""

    evidence_id: UUID
    evidence_type: str
    created_at: datetime

    def to_dict(self) -> dict:
        """Serialize for API responses."""
        return {
            "evidence_id": str(self.evidence_id),
            "evidence_type": self.evidence_type,
            "created_at": self.created_at.isoformat(),
        }


async def record_phase_evidence(
    *,
    run_id: UUID,
    phase_name: str,
    event_type: EvidenceEventType,
    actor_id: UUID,
    tenant_id: UUID,
    subject_id: UUID | None = None,
    data: dict[str, Any] | None = None,
    conn,
) -> EvidenceResult:
    """Record evidence for a phase transition or event.

    Creates an immutable Evidence entity capturing the phase event with
    full context for compliance audit.

    Args:
        run_id: CharterRun ID.
        phase_name: Name of the phase.
        event_type: Type of event (see EvidenceEventType).
        actor_id: User who triggered the event.
        tenant_id: Tenant ID.
        subject_id: Person ID the workflow is about (optional).
        data: Additional event data (action taken, notes, etc.).
        conn: Database connection.

    Returns:
        EvidenceResult with evidence ID.

    Evidence Data Structure:
        {
            "run_id": str(UUID),
            "phase_name": str,
            "event_type": str,
            "actor_id": str(UUID),
            "timestamp": ISO timestamp,
            ...additional data...
        }
    """
    now = datetime.now(UTC)
    evidence_id = uuid4()

    # Build evidence data
    evidence_data = {
        "run_id": str(run_id),
        "phase_name": phase_name,
        "event_type": event_type.value,
        "actor_id": str(actor_id),
        "timestamp": now.isoformat(),
    }

    if data:
        # Merge additional data, converting UUIDs to strings
        for key, value in data.items():
            if isinstance(value, UUID):
                evidence_data[key] = str(value)
            else:
                evidence_data[key] = value

    # Create title from event type
    title = _format_evidence_title(event_type, phase_name)

    # Create Evidence entity
    evidence = Evidence(
        id=evidence_id,
        created_at=now,
        content=EvidenceContent(
            tenant_id=tenant_id,
            subject_id=subject_id,
            evidence_type=f"runtime.{event_type.value}",
            title=title,
            data=evidence_data,
            source="canon.runtime",
            source_id=str(run_id),
            collected_at=now,
            collected_by_id=actor_id,
        ),
    )

    await insert_entity(evidence, conn=conn, tenant_scope=TenantScope.DISABLED)

    logger.debug(
        "Recorded evidence: %s (phase: %s, run: %s, actor: %s)",
        event_type.value,
        phase_name,
        run_id,
        actor_id,
    )

    return EvidenceResult(
        evidence_id=evidence_id,
        evidence_type=f"runtime.{event_type.value}",
        created_at=now,
    )


async def record_grant_evidence(
    *,
    token_id: UUID,
    event_type: EvidenceEventType,
    actor_id: UUID,
    tenant_id: UUID,
    subject_id: UUID,
    run_id: UUID | None = None,
    phase_name: str | None = None,
    data: dict[str, Any] | None = None,
    conn,
) -> EvidenceResult:
    """Record evidence for a grant operation.

    Creates an immutable Evidence entity capturing the grant event with
    full context for access audit (FCRA compliance).

    Args:
        token_id: DocumentAccessToken ID.
        event_type: Type of event (GRANT_ISSUED, GRANT_REVOKED, etc.).
        actor_id: User who triggered the event.
        tenant_id: Tenant ID.
        subject_id: Person whose documents were accessed.
        run_id: Optional CharterRun ID.
        phase_name: Optional phase name.
        data: Additional event data (document_type, grantee_id, etc.).
        conn: Database connection.

    Returns:
        EvidenceResult with evidence ID.
    """
    now = datetime.now(UTC)
    evidence_id = uuid4()

    # Build evidence data
    evidence_data = {
        "token_id": str(token_id),
        "event_type": event_type.value,
        "actor_id": str(actor_id),
        "subject_id": str(subject_id),
        "timestamp": now.isoformat(),
    }

    if run_id:
        evidence_data["run_id"] = str(run_id)
    if phase_name:
        evidence_data["phase_name"] = phase_name

    if data:
        # Merge additional data, converting UUIDs to strings
        for key, value in data.items():
            if isinstance(value, UUID):
                evidence_data[key] = str(value)
            else:
                evidence_data[key] = value

    # Create title from event type and document type
    document_type = data.get("document_type", "document") if data else "document"
    title = _format_grant_evidence_title(event_type, document_type)

    # Create Evidence entity
    evidence = Evidence(
        id=evidence_id,
        created_at=now,
        content=EvidenceContent(
            tenant_id=tenant_id,
            subject_id=subject_id,
            evidence_type=f"runtime.{event_type.value}",
            title=title,
            data=evidence_data,
            source="canon.runtime.grants",
            source_id=str(token_id),
            collected_at=now,
            collected_by_id=actor_id,
        ),
    )

    await insert_entity(evidence, conn=conn, tenant_scope=TenantScope.DISABLED)

    logger.debug(
        "Recorded grant evidence: %s (token: %s, actor: %s)",
        event_type.value,
        token_id,
        actor_id,
    )

    return EvidenceResult(
        evidence_id=evidence_id,
        evidence_type=f"runtime.{event_type.value}",
        created_at=now,
    )


async def record_workflow_evidence(
    *,
    run_id: UUID,
    workflow_name: str,
    event_type: EvidenceEventType,
    actor_id: UUID,
    tenant_id: UUID,
    subject_id: UUID,
    data: dict[str, Any] | None = None,
    conn,
) -> EvidenceResult:
    """Record evidence for a workflow event.

    Creates an immutable Evidence entity capturing the workflow event
    (start, complete, fail, cancel) with full context.

    Args:
        run_id: CharterRun ID.
        workflow_name: Name of the workflow.
        event_type: Type of event (WORKFLOW_STARTED, etc.).
        actor_id: User who triggered the event.
        tenant_id: Tenant ID.
        subject_id: Person the workflow is about.
        data: Additional event data.
        conn: Database connection.

    Returns:
        EvidenceResult with evidence ID.
    """
    now = datetime.now(UTC)
    evidence_id = uuid4()

    # Build evidence data
    evidence_data = {
        "run_id": str(run_id),
        "workflow_name": workflow_name,
        "event_type": event_type.value,
        "actor_id": str(actor_id),
        "subject_id": str(subject_id),
        "timestamp": now.isoformat(),
    }

    if data:
        # Merge additional data, converting UUIDs to strings
        for key, value in data.items():
            if isinstance(value, UUID):
                evidence_data[key] = str(value)
            else:
                evidence_data[key] = value

    # Create title from event type
    title = _format_workflow_evidence_title(event_type, workflow_name)

    # Create Evidence entity
    evidence = Evidence(
        id=evidence_id,
        created_at=now,
        content=EvidenceContent(
            tenant_id=tenant_id,
            subject_id=subject_id,
            evidence_type=f"runtime.{event_type.value}",
            title=title,
            data=evidence_data,
            source="canon.runtime.workflow",
            source_id=str(run_id),
            collected_at=now,
            collected_by_id=actor_id,
        ),
    )

    await insert_entity(evidence, conn=conn, tenant_scope=TenantScope.DISABLED)

    logger.debug(
        "Recorded workflow evidence: %s (workflow: %s, run: %s, actor: %s)",
        event_type.value,
        workflow_name,
        run_id,
        actor_id,
    )

    return EvidenceResult(
        evidence_id=evidence_id,
        evidence_type=f"runtime.{event_type.value}",
        created_at=now,
    )


def _format_evidence_title(event_type: EvidenceEventType, phase_name: str) -> str:
    """Format a human-readable title for phase evidence."""
    titles = {
        EvidenceEventType.PHASE_ACTIVATED: f"Phase '{phase_name}' activated",
        EvidenceEventType.PHASE_CLAIMED: f"Phase '{phase_name}' claimed",
        EvidenceEventType.PHASE_COMPLETED: f"Phase '{phase_name}' completed",
        EvidenceEventType.PHASE_FAILED: f"Phase '{phase_name}' failed",
        EvidenceEventType.PHASE_SKIPPED: f"Phase '{phase_name}' skipped",
        EvidenceEventType.PHASE_DELEGATED: f"Phase '{phase_name}' delegated",
    }
    return titles.get(event_type, f"Phase '{phase_name}' event: {event_type.value}")


def _format_grant_evidence_title(event_type: EvidenceEventType, document_type: str) -> str:
    """Format a human-readable title for grant evidence."""
    titles = {
        EvidenceEventType.GRANT_ISSUED: f"Access granted to '{document_type}'",
        EvidenceEventType.GRANT_ACCESSED: f"Document '{document_type}' accessed",
        EvidenceEventType.GRANT_REVOKED: f"Access to '{document_type}' revoked",
        EvidenceEventType.GRANT_EXPIRED: f"Access to '{document_type}' expired",
        EvidenceEventType.GRANT_TRANSFERRED: f"Access to '{document_type}' transferred",
    }
    return titles.get(event_type, f"Document access event: {event_type.value}")


def _format_workflow_evidence_title(event_type: EvidenceEventType, workflow_name: str) -> str:
    """Format a human-readable title for workflow evidence."""
    titles = {
        EvidenceEventType.WORKFLOW_STARTED: f"Workflow '{workflow_name}' started",
        EvidenceEventType.WORKFLOW_COMPLETED: f"Workflow '{workflow_name}' completed",
        EvidenceEventType.WORKFLOW_FAILED: f"Workflow '{workflow_name}' failed",
        EvidenceEventType.WORKFLOW_CANCELLED: f"Workflow '{workflow_name}' cancelled",
    }
    return titles.get(event_type, f"Workflow event: {event_type.value}")
