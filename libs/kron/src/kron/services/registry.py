"""ServiceRegistry: manages iModel instances with name-based lookup."""

from __future__ import annotations

from typing import Any

from kron.types import Undefined, UndefinedType, is_sentinel

from .model import iModel

__all__ = ("ServiceRegistry",)


class ServiceRegistry:
    """Service registry managing iModel instances with O(1) name-based lookup.

    Provides type-safe storage with name-based indexing.
    Services must have unique names; duplicates raise ValueError unless update=True.

    Example:
        >>> registry = ServiceRegistry()
        >>> registry.register(iModel(backend=my_endpoint))
        >>> model = registry.get("my_service")
        >>> tagged = registry.list_by_tag("api")
    """

    def __init__(self):
        """Initialize empty registry with name index."""
        self._services: dict[str, iModel] = {}

    def register(self, model: iModel, update: bool = False) -> str:
        """Register iModel instance by name.

        Args:
            model: iModel instance to register.
            update: If True, replaces existing service with same name.

        Returns:
            Name of registered service.

        Raises:
            ValueError: If service name exists and update=False.
        """
        if model.name in self._services:
            if not update:
                raise ValueError(f"Service '{model.name}' already registered")

        self._services[model.name] = model
        return model.name

    def unregister(self, name: str) -> iModel:
        """Remove and return service by name. Raises KeyError if not found."""
        if name not in self._services:
            raise KeyError(f"Service '{name}' not found")
        return self._services.pop(name)

    def get(self, name: str | iModel, default: Any | UndefinedType = Undefined) -> iModel:
        """Get service by name or return iModel passthrough. Raises KeyError if not found."""
        if isinstance(name, iModel):
            return name
        if name not in self._services:
            if not is_sentinel(default):
                return default
            raise KeyError(f"Service '{name}' not found")
        return self._services[name]

    def has(self, name: str) -> bool:
        """Check if service exists."""
        return name in self._services

    def list_names(self) -> list[str]:
        """List all registered service names."""
        return list(self._services.keys())

    def list_by_tag(self, tag: str) -> list[iModel]:
        """Filter services by tag, returns list of matching iModels."""
        return [m for m in self._services.values() if tag in m.tags]

    def count(self) -> int:
        """Count registered services."""
        return len(self._services)

    def clear(self) -> None:
        """Remove all registered services."""
        self._services.clear()

    def __len__(self) -> int:
        """Return number of registered services."""
        return len(self._services)

    def __contains__(self, name: str) -> bool:
        """Check if service exists (supports `name in registry`)."""
        return name in self._services

    def __repr__(self) -> str:
        """String representation."""
        return f"ServiceRegistry(count={len(self)})"
