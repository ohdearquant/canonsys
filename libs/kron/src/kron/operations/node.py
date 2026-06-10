"""Operation: executable graph node combining Node and Event."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import Field, PrivateAttr

from kron.core import Event, Node
from kron.types import Undefined, UndefinedType, is_sentinel

if TYPE_CHECKING:
    from kron.session import Branch, Session

__all__ = ("Operation", "create_operation")


class Operation(Node, Event):
    """Executable graph node that combines Node (storage) with Event (execution).

    Operations are the executable units in a workflow DAG. They hold:
    - operation_type: Registry key to look up the factory function
    - parameters: Arguments to pass to the factory

    Usage:
        op = Operation(operation_type="chat", parameters={"prompt": "Hello"})
        op.bind(session, branch)
        await op.invoke()
        result = op.execution.response
    """

    operation_type: str
    parameters: dict[str, Any] | Any = Field(
        default_factory=dict,
        description="Operation parameters (dict or Pydantic model)",
    )

    _session: Any = PrivateAttr(default=None)
    _branch: Any = PrivateAttr(default=None)

    def bind(self, session: Session, branch: Branch) -> Operation:
        """Bind session and branch for execution.

        Must be called before invoke() if not using Session.conduct().

        Args:
            session: Session with operations registry and services
            branch: Branch for message context

        Returns:
            Self for chaining
        """
        self._session = session
        self._branch = branch
        return self

    def _require_binding(self) -> tuple[Session, Branch]:
        """Return bound (session, branch) tuple or raise RuntimeError if unbound."""
        if self._session is None or self._branch is None:
            raise RuntimeError(
                "Operation not bound to session/branch. "
                "Use operation.bind(session, branch) or session.conduct(...)"
            )
        return self._session, self._branch

    async def _invoke(self) -> Any:
        """Execute via session's operation registry. Called by Event.invoke().

        Returns:
            Factory result (stored in execution.response).

        Raises:
            RuntimeError: If not bound.
            KeyError: If operation_type not registered.
        """
        session, branch = self._require_binding()
        factory = session.operations.get(self.operation_type)
        return await factory(session, branch, self.parameters)

    def __repr__(self) -> str:
        bound = "bound" if self._session is not None else "unbound"
        return (
            f"Operation(type={self.operation_type}, status={self.execution.status.value}, {bound})"
        )


def create_operation(
    operation_type: str | UndefinedType = Undefined,
    parameters: dict[str, Any] | UndefinedType = Undefined,
    **kwargs,
) -> Operation:
    """Factory for Operation nodes.

    Args:
        operation_type: Registry key (required).
        parameters: Factory arguments dict (default: {}).
        **kwargs: Additional fields (metadata, timeout, etc.).

    Returns:
        Unbound Operation ready for bind() and invoke().

    Raises:
        ValueError: If operation_type not provided.
    """
    if is_sentinel(operation_type):
        raise ValueError("operation_type is required")

    resolved_params: dict[str, Any] = {} if is_sentinel(parameters) else parameters

    return Operation(
        operation_type=operation_type,
        parameters=resolved_params,
        **kwargs,
    )
