"""Request context for service operations."""

from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID, uuid4

from kron.types import ID, DataClass

if TYPE_CHECKING:
    # Forward references for session types (not yet absorbed)
    from typing import TypeVar

    Session = TypeVar("Session")
    Branch = TypeVar("Branch")

__all__ = ("QueryFn", "RequestContext")


class QueryFn(Protocol):
    """Protocol for CRUD query functions used by declarative phrases.

    The query_fn is the bridge between declarative CrudPattern phrases
    and the actual database backend. Implementations MUST use parameterized
    queries to prevent SQL injection.

    Args:
        table: Validated database table name (alphanumeric + underscores only).
        operation: CRUD operation enum value.
        where: WHERE clause as dict of column -> value. None for insert.
        data: Data dict for insert/update. None for select/delete.
        ctx: The RequestContext (for connection, tenant isolation, etc).

    Returns:
        Row as dict if found/affected, None otherwise.
    """

    def __call__(
        self,
        table: str,
        operation: str,
        where: dict[str, Any] | None,
        data: dict[str, Any] | None,
        ctx: RequestContext,
    ) -> Awaitable[dict[str, Any] | None]: ...


@dataclass(slots=True)
class RequestContext(DataClass):
    """Context for a service request.

    Carries identity, scope, and metadata through the call chain.
    Extra kwargs become metadata entries accessible as attributes.

    Core fields (slots):
        name, id, session_id, branch_id, conn, query_fn, now

    Extension fields (metadata, accessible via attribute access):
        Any kwarg passed to __init__ is stored in metadata and accessible
        as ctx.field_name. Common extensions:
        - tenant_id: Tenant scope (auto-added to WHERE clauses)
        - actor_id: Who is performing the action
        - subject_id: Person subject of the operation
        - correlation_id: Trace ID linking related operations
        - causation_id: Parent operation that caused this
        - charter: Active governance document
        - jurisdictions: Jurisdiction scope tuple

    Usage:
        ctx = RequestContext(
            name="consent.grant",
            conn=connection,
            tenant_id=tenant_uuid,
            actor_id=actor_uuid,
            subject_id=subject_uuid,
            correlation_id=trace_id,
        )
        ctx.tenant_id   # -> tenant_uuid (from metadata)
        ctx.subject_id   # -> subject_uuid (from metadata)
    """

    name: str
    id: UUID = field(default_factory=uuid4)
    session_id: ID[Session] | None = None
    branch_id: ID[Branch] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    conn: Any | None = None
    query_fn: QueryFn | None = None
    now: datetime | None = None

    def __init__(
        self,
        name: str,
        session_id: ID[Session] | None = None,
        branch_id: ID[Branch] | None = None,
        id: UUID | None = None,
        conn: Any | None = None,
        query_fn: QueryFn | None = None,
        now: datetime | None = None,
        **kwargs: Any,
    ):
        self.name = name
        self.id = id or uuid4()
        self.session_id = session_id
        self.branch_id = branch_id
        self.conn = conn
        self.query_fn = query_fn
        self.now = now
        self.metadata = kwargs

    def __getattr__(self, name: str) -> Any:
        """Look up unknown attributes in metadata.

        Called only when normal attribute lookup fails (slots miss).
        Raises AttributeError for keys not present in metadata so that
        hasattr() works correctly.
        """
        if name.startswith("_"):
            raise AttributeError(name)
        metadata = object.__getattribute__(self, "metadata")
        try:
            return metadata[name]
        except KeyError:
            raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'") from None
