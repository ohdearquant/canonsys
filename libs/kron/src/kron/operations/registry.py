"""Per-session operation factory registry.

Maps operation names to async factory functions. Instantiated per-Session
for isolation, testability, and per-session customization.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

__all__ = ("OperationRegistry",)

OperationFactory = Callable[..., Awaitable[Any]]
"""Factory signature: async (session, branch, parameters) -> result"""


class OperationRegistry:
    """Map operation names to async factory functions.

    Per-session registry (not global) for isolation and testability.

    Example:
        registry = OperationRegistry()
        registry.register("chat", chat_factory)
        factory = registry.get("chat")
        result = await factory(session, branch, params)
    """

    def __init__(self):
        """Initialize empty registry."""
        self._factories: dict[str, OperationFactory] = {}

    def register(
        self,
        operation_name: str,
        factory: OperationFactory,
        *,
        override: bool = False,
    ) -> None:
        """Register factory for operation name.

        Args:
            operation_name: Lookup key.
            factory: Async (session, branch, params) -> result.
            override: Allow replacing existing. Default False.

        Raises:
            ValueError: If name exists and override=False.
        """
        if operation_name in self._factories and not override:
            raise ValueError(
                f"Operation '{operation_name}' already registered. Use override=True to replace."
            )
        self._factories[operation_name] = factory

    def get(self, operation_name: str) -> OperationFactory:
        """Get factory by name. Raises KeyError with available names if not found."""
        if operation_name not in self._factories:
            raise KeyError(
                f"Operation '{operation_name}' not registered. Available: {self.list_names()}"
            )
        return self._factories[operation_name]

    def has(self, operation_name: str) -> bool:
        """Check if name is registered."""
        return operation_name in self._factories

    def unregister(self, operation_name: str) -> bool:
        """Remove registration. Returns True if existed."""
        if operation_name in self._factories:
            del self._factories[operation_name]
            return True
        return False

    def list_names(self) -> list[str]:
        """Return all registered operation names."""
        return list(self._factories.keys())

    def __contains__(self, operation_name: str) -> bool:
        """Support 'name in registry' syntax."""
        return operation_name in self._factories

    def __len__(self) -> int:
        """Count of registered operations."""
        return len(self._factories)

    def __repr__(self) -> str:
        return f"OperationRegistry(operations={self.list_names()})"
