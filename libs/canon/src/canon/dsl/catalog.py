"""Versioned schema catalog for Charter DSL output types.

Charters pin a catalog version via `schemas: namespace@version`.
Each phase's `output` directive references a named schema from
the pinned catalog. The resolver validates these references at
compile time.

Usage:
    catalog = SchemaCatalog()
    catalog.register("canon.hr", "2026.01", "EligibilityReport", EligibilityReport)

    # Lookup
    schema_type = catalog.get("canon.hr", "2026.01", "EligibilityReport")

    # List
    names = catalog.list_types("canon.hr", "2026.01")
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = (
    "CatalogEntry",
    "SchemaCatalog",
)


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """A versioned schema type in the catalog."""

    name: str
    schema_type: type
    version: str
    namespace: str


class SchemaCatalog:
    """Versioned registry of named output types.

    Schemas are organized by namespace and version. Charters pin
    a specific version, ensuring reproducible compilation.

    Storage key: (namespace, version, name) -> type
    """

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str, str], CatalogEntry] = {}
        self._versions: set[tuple[str, str]] = set()

    def register(
        self,
        namespace: str,
        version: str,
        name: str,
        schema_type: type,
    ) -> None:
        """Register a schema type under namespace@version.

        Args:
            namespace: Catalog namespace (e.g., "canon.hr")
            version: Catalog version (e.g., "2026.01")
            name: Schema type name (e.g., "EligibilityReport")
            schema_type: The Python type (frozen dataclass or BaseModel)
        """
        key = (namespace, version, name)
        self._entries[key] = CatalogEntry(
            name=name,
            schema_type=schema_type,
            version=version,
            namespace=namespace,
        )
        self._versions.add((namespace, version))

    def get(
        self,
        namespace: str,
        version: str,
        name: str,
    ) -> type | None:
        """Look up a schema type.

        Returns:
            The Python type if found, None otherwise.
        """
        entry = self._entries.get((namespace, version, name))
        return entry.schema_type if entry else None

    def get_entry(
        self,
        namespace: str,
        version: str,
        name: str,
    ) -> CatalogEntry | None:
        """Look up a catalog entry with full metadata."""
        return self._entries.get((namespace, version, name))

    def has_version(self, namespace: str, version: str) -> bool:
        """Check if a namespace@version exists in the catalog."""
        return (namespace, version) in self._versions

    def list_types(self, namespace: str, version: str) -> list[str]:
        """List all type names under a namespace@version.

        Returns:
            Sorted list of schema type names.
        """
        return sorted(
            entry.name
            for key, entry in self._entries.items()
            if key[0] == namespace and key[1] == version
        )

    def list_versions(self, namespace: str) -> list[str]:
        """List all versions for a namespace.

        Returns:
            Sorted list of version strings.
        """
        return sorted(v for ns, v in self._versions if ns == namespace)
