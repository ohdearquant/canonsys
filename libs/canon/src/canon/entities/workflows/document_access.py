# Copyright (c) 2024-2025, CanonSys
# SPDX-License-Identifier: Apache-2.0
"""Document access token entity.

Provides JIT (Just-In-Time) document access control:
    DocumentAccessToken: Time-limited access grant to specific documents

Regulatory context:
    - FCRA 1681b(b)(3): Consent-based access to consumer reports
    - GDPR Art. 5(1)(c): Data minimization - access only what's needed
    - SOC 2 CC6.1: Principle of least privilege
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from kron.types import FK
from kron.utils import now_utc

from ..entity import Entity, register_entity
from ..shared import Person, TenantAware, User
from .queue import DocumentAccessPurpose, DocumentAccessStatus

__all__ = (
    "DocumentAccessToken",
    "DocumentAccessTokenContent",
)


class DocumentAccessTokenContent(TenantAware):
    """Content for a document access token.

    Document access tokens implement JIT (Just-In-Time) access control.
    Instead of granting persistent access to sensitive documents,
    tokens provide time-limited access for specific purposes.

    Lifecycle:
        1. Workflow step activates, issuing tokens for needed documents
        2. User accesses document, token status moves to USED
        3. Token expires or is revoked when step completes
        4. Access audit trail preserved for compliance

    Access validation:
        Use is_valid() to check if a token can be used.
        Use can_access(document_type) to check specific document access.
        Use record_access() to track document access events.
    """

    # Subject (whose documents are being accessed)
    subject_id: FK[Person]
    """The person whose documents are being accessed."""

    # Grantee (who has access)
    grantee_id: FK[User]
    """The user granted access."""

    # Workflow context
    workflow_instance_id: UUID | None = None
    """Workflow instance that issued this token (if applicable)."""

    workflow_step_id: UUID | None = None
    """Workflow step that issued this token (if applicable)."""

    # Document scope
    document_type: str
    """Type of document access granted (e.g., 'resume', 'background_report')."""

    purpose: DocumentAccessPurpose
    """Purpose for the access grant."""

    # Status
    status: DocumentAccessStatus = DocumentAccessStatus.ACTIVE
    """Current status of the token."""

    # Timing
    issued_at: datetime = Field(default_factory=now_utc)
    """When the token was issued."""

    expires_at: datetime
    """When the token expires (absolute deadline)."""

    first_accessed_at: datetime | None = None
    """When the document was first accessed using this token."""

    # Access tracking
    access_count: int = 0
    """Number of times this token has been used to access documents."""

    last_accessed_at: datetime | None = None
    """Most recent access time."""

    # Revocation
    revoked_at: datetime | None = None
    """When the token was revoked (if applicable)."""

    revoked_by_id: FK[User] | None = None
    """User who revoked the token (if applicable)."""

    revocation_reason: str | None = None
    """Reason for revocation (if applicable)."""

    # Evidence tracking
    evidence_id: UUID | None = None
    """Evidence record for the access grant."""

    def is_valid(self) -> bool:
        """Check if this token is currently valid for access.

        Returns:
            True if token is active/used and not expired.
        """
        if self.status not in (
            DocumentAccessStatus.ACTIVE,
            DocumentAccessStatus.USED,
        ):
            return False
        return datetime.utcnow() < self.expires_at

    def can_access(self, document_type: str) -> bool:
        """Check if this token grants access to a specific document type.

        Args:
            document_type: The document type to check access for.

        Returns:
            True if token is valid and grants access to the document type.
        """
        if not self.is_valid():
            return False
        return self.document_type == document_type

    def record_access(self) -> None:
        """Record a document access event.

        Updates access tracking fields. Should be called each time
        the token is used to access a document.

        Note: This mutates the content. Caller must persist the entity.
        """
        now = now_utc()
        if self.first_accessed_at is None:
            self.first_accessed_at = now
            self.status = DocumentAccessStatus.USED
        self.last_accessed_at = now
        self.access_count += 1


@register_entity("document_access_tokens")
class DocumentAccessToken(Entity):
    """Entity representing a JIT document access token.

    Tokens provide time-limited, purpose-bound access to sensitive
    documents. Each access is tracked for compliance audit.
    """

    content: DocumentAccessTokenContent

    _indexes = [
        # Fast lookup by subject (all access grants for a person)
        {"columns": ["subject_id"]},
        # Fast lookup by grantee + status (my active tokens)
        {"columns": ["grantee_id", "status"]},
        # Fast lookup by workflow instance (tokens for a workflow)
        {"columns": ["workflow_instance_id"]},
        # Fast lookup by workflow step (tokens for a step)
        {"columns": ["workflow_step_id"]},
        # Expiration monitoring (tokens to clean up)
        {"columns": ["status", "expires_at"]},
        # Audit query (access by document type)
        {"columns": ["document_type", "purpose"]},
    ]
