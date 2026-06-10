"""Session and Branch: central orchestration for messages, services, and operations.

Session owns branches, messages, services registry, and operations registry.
Branch is a named message progression with capability/resource access control.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

from pydantic import Field

from kron.core import Element, Flow, Progression
from kron.errors import AccessError, NotFoundError
from kron.operations import OperationRegistry
from kron.services import ServiceRegistry
from kron.types import HashableModel, Unset, UnsetType, not_sentinel

from .message import Message

if TYPE_CHECKING:
    from kron.services.backend import Calling

__all__ = (
    "Branch",
    "Session",
    "SessionConfig",
    "capabilities_must_be_subset_of_branch",
    "resource_must_be_accessible_by_branch",
    "resource_must_exist_in_session",
)


class SessionConfig(HashableModel):
    """Session initialization configuration.

    Attributes:
        default_branch_name: Name for auto-created default branch.
        default_capabilities: Capabilities granted to default branch.
        default_resources: Resources accessible by default branch.
        auto_create_default_branch: Create "main" branch on init.
    """

    default_branch_name: str | None = None
    default_capabilities: set[str] = Field(default_factory=set)
    default_resources: set[str] = Field(default_factory=set)
    auto_create_default_branch: bool = True


class Branch(Progression):
    """Message progression with capability and resource access control.

    Branch extends Progression with session binding and access control.
    Messages are referenced by UUID in the order list.

    Attributes:
        session_id: Owning session (immutable after creation).
        capabilities: Allowed structured output schema names.
        resources: Allowed service names for access control.
    """

    session_id: UUID = Field(..., frozen=True)
    capabilities: set[str] = Field(default_factory=set)
    resources: set[str] = Field(default_factory=set)

    def __repr__(self) -> str:
        name_str = f" name='{self.name}'" if self.name else ""
        return f"Branch(messages={len(self)}, session={str(self.session_id)[:8]}{name_str})"


class Session(Element):
    """Central orchestrator: messages, branches, services, operations.

    Lifecycle:
        1. Create session (auto-creates default branch unless disabled)
        2. Register services and operations
        3. Create branches for different contexts/users
        4. Add messages, conduct operations, make service requests

    Attributes:
        user: Optional user identifier.
        communications: Flow containing messages and branches.
        services: Service registry for backend access.
        operations: Operation factory registry.
        config: Session configuration.
        default_branch_id: Branch used when none specified.

    Example:
        session = Session(user="agent-1")
        session.services.register("openai", openai_service)
        session.operations.register("chat", chat_factory)
        result = await session.conduct("chat", params={"prompt": "hello"})
    """

    user: str | None = None
    communications: Flow[Message, Branch] = None  # type: ignore
    services: ServiceRegistry = None  # type: ignore
    operations: OperationRegistry = None  # type: ignore
    config: SessionConfig = None  # type: ignore
    default_branch_id: UUID | None = None

    def __init__(
        self,
        user: str | None = None,
        communications: Flow[Message, Branch] | None = None,
        services: ServiceRegistry | None = None,
        operations: OperationRegistry | None = None,
        config: SessionConfig | dict | None = None,
        default_branch_id: UUID | None = None,
        **data,
    ):
        """Initialize session with optional pre-configured components.

        Args:
            user: User identifier.
            communications: Pre-existing Flow (creates new if None).
            services: Pre-existing ServiceRegistry (creates new if None).
            operations: Pre-existing OperationRegistry (creates new if None).
            config: SessionConfig or dict (uses defaults if None).
            default_branch_id: Pre-set default branch.
            **data: Additional Element fields.
        """
        super().__init__(**data)
        self.user = user
        self.communications = communications or Flow(item_type=Message)
        self.services = services or ServiceRegistry()
        self.operations = operations or OperationRegistry()
        self.default_branch_id = default_branch_id

        if config is None:
            self.config = SessionConfig()
        elif isinstance(config, dict):
            self.config = SessionConfig(**config)
        else:
            self.config = config

        if self.config.auto_create_default_branch and self.default_branch_id is None:
            branch = self.create_branch(
                name=self.config.default_branch_name or "main",
                capabilities=self.config.default_capabilities,
                resources=self.config.default_resources,
            )
            self.default_branch_id = branch.id

    @property
    def messages(self):
        """All messages in session (Pile[Message])."""
        return self.communications.items

    @property
    def branches(self):
        """All branches in session (Pile[Branch])."""
        return self.communications.progressions

    @property
    def default_branch(self) -> Branch | None:
        """Default branch, or None if unset or deleted."""
        if self.default_branch_id is None:
            return None
        with contextlib.suppress(KeyError, NotFoundError):
            return self.communications.get_progression(self.default_branch_id)
        return None

    def create_branch(
        self,
        *,
        name: str | None = None,
        capabilities: set[str] | None = None,
        resources: set[str] | None = None,
        messages: Iterable[UUID | Message] | None = None,
    ) -> Branch:
        """Create and register a new branch.

        Args:
            name: Branch name (auto: "branch_N").
            capabilities: Allowed schema names.
            resources: Allowed service names.
            messages: Initial message UUIDs or objects.

        Returns:
            Created Branch added to session.
        """
        order: list[UUID] = []
        if messages:
            for msg in messages:
                order.append(msg.id if isinstance(msg, Message) else msg)

        branch = Branch(
            session_id=self.id,
            name=name or f"branch_{len(self.branches)}",
            capabilities=capabilities or set(),
            resources=resources or set(),
            order=order,
        )

        self.communications.add_progression(branch)
        return branch

    def get_branch(
        self, branch: UUID | str | Branch, default: Branch | UnsetType = Unset, /
    ) -> Branch:
        """Get branch by UUID, name, or instance.

        Args:
            branch: Branch identifier.
            default: Return this if not found (else raise).

        Returns:
            Branch instance.

        Raises:
            NotFoundError: If not found and no default.
        """
        if isinstance(branch, Branch) and branch in self.branches:
            return branch
        with contextlib.suppress(KeyError):
            return self.communications.get_progression(branch)
        if not_sentinel(default):
            return default
        raise NotFoundError("Branch not found")

    def set_default_branch(self, branch: Branch | UUID | str) -> None:
        """Set the default branch for operations.

        Args:
            branch: Branch to set as default (must exist).

        Raises:
            NotFoundError: If branch not in session.
        """
        resolved = self.get_branch(branch)
        self.default_branch_id = resolved.id

    def fork(
        self,
        branch: Branch | UUID | str,
        *,
        name: str | None = None,
        capabilities: set[str] | Literal[True] | None = None,
        resources: set[str] | Literal[True] | None = None,
    ) -> Branch:
        """Fork branch for divergent exploration.

        Creates new branch with same messages. Use True to copy access control.

        Args:
            branch: Source branch (Branch|UUID|str).
            name: Fork name (auto: "{source}_fork").
            capabilities: True=copy, None=empty, or explicit set.
            resources: True=copy, None=empty, or explicit set.

        Returns:
            New Branch with forked_from metadata.
        """
        source = self.get_branch(branch)

        forked = self.create_branch(
            name=name or f"{source.name}_fork",
            messages=source.order,
            capabilities=(
                {*source.capabilities} if capabilities is True else (capabilities or set())
            ),
            resources=({*source.resources} if resources is True else (resources or set())),
        )

        forked.metadata["forked_from"] = {
            "branch_id": str(source.id),
            "branch_name": source.name,
            "created_at": source.created_at.isoformat(),
            "message_count": len(source),
        }
        return forked

    def add_message(
        self,
        message: Message,
        branches: list[Branch | UUID | str] | Branch | UUID | str | None = None,
    ) -> None:
        """Add message to session, optionally appending to branch(es)."""
        self.communications.add_item(message, progressions=branches)

    async def request(
        self,
        service_name: str,
        *,
        branch: Branch | UUID | str | None = None,
        poll_timeout: float | None = None,
        poll_interval: float | None = None,
        **kwargs,
    ) -> Calling:
        """Direct service invocation with optional access control.

        Args:
            service_name: Registered service name.
            branch: If provided, checks service in branch.resources.
            poll_timeout: Max wait seconds.
            poll_interval: Poll interval seconds.
            **kwargs: Service-specific arguments.

        Returns:
            Calling with execution results.

        Raises:
            AccessError: If branch lacks access to service.
            NotFoundError: If service not registered.
        """
        if branch is not None:
            resolved_branch = self.get_branch(branch)
            resource_must_be_accessible_by_branch(resolved_branch, service_name)

        service = self.services.get(service_name)
        return await service.invoke(
            poll_timeout=poll_timeout,
            poll_interval=poll_interval,
            **kwargs,
        )

    async def conduct(
        self,
        operation_type: str,
        branch: Branch | UUID | str | None = None,
        params: Any | None = None,
    ) -> Any:
        """Execute operation via registry.

        Args:
            operation_type: Registry key.
            branch: Target branch (default if None).
            params: Operation parameters.

        Returns:
            Operation result.

        Raises:
            RuntimeError: No branch and no default.
            KeyError: Operation not registered.
        """
        resolved = self._resolve_branch(branch)
        factory = self.operations.get(operation_type)
        return await factory(self, resolved, params)

    def _resolve_branch(self, branch: Branch | UUID | str | None) -> Branch:
        """Resolve to Branch, falling back to default. Raises if neither available."""
        if branch is not None:
            return self.get_branch(branch)
        if self.default_branch is not None:
            return self.default_branch
        raise RuntimeError("No branch provided and no default branch set")

    def __repr__(self) -> str:
        return (
            f"Session(messages={len(self.messages)}, "
            f"branches={len(self.branches)}, "
            f"services={len(self.services)})"
        )


def resource_must_exist_in_session(session: Session, name: str) -> None:
    """Validate service exists. Raise NotFoundError with available names if not."""
    if not session.services.has(name):
        raise NotFoundError(
            f"Service '{name}' not found in session services",
            details={"available": session.services.list_names()},
        )


def resource_must_be_accessible_by_branch(branch: Branch, name: str) -> None:
    """Validate branch has resource access. Raise AccessError if not."""
    if name not in branch.resources:
        raise AccessError(
            f"Branch '{branch.name}' has no access to resource '{name}'",
            details={
                "branch": branch.name,
                "resource": name,
                "available": list(branch.resources),
            },
        )


def capabilities_must_be_subset_of_branch(branch: Branch, capabilities: set[str]) -> None:
    """Validate branch has all capabilities. Raise AccessError listing missing."""
    if not capabilities.issubset(branch.capabilities):
        missing = capabilities - branch.capabilities
        raise AccessError(
            f"Branch '{branch.name}' missing capabilities: {missing}",
            details={
                "requested": sorted(capabilities),
                "available": sorted(branch.capabilities),
            },
        )


def resolve_branch_exists_in_session(session: Session, branch: Branch | str) -> Branch:
    """Get branch from session. Raise NotFoundError if not found."""
    if (b_ := session.get_branch(branch, None)) is None:
        raise NotFoundError(f"Branch '{branch}' does not exist in session")
    return b_
