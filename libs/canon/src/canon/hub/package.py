"""Vocabulary package: named bundle of phrases + schemas per regulatory domain."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ("PackageManifest", "VocabularyPackage")


@dataclass(frozen=True, slots=True)
class VocabularyPackage:
    """Named bundle of phrases + schemas for a regulatory domain.

    Each package maps 1:1 to a canon-core feature domain. Used in
    Charter DSL: ``packages: [consent, ai_governance]``
    """

    name: str
    description: str
    feature_names: frozenset[str]
    schema_names: frozenset[str]
    regulatory_basis: tuple[str, ...]
    version: str = "2026.01"
    domain_module: str = ""

    @property
    def feature_count(self) -> int:
        return len(self.feature_names)

    @property
    def schema_count(self) -> int:
        return len(self.schema_names)


@dataclass(frozen=True, slots=True)
class PackageManifest:
    """Resolved set of packages for a charter compilation.

    Created by ``PackageRegistry.resolve()`` when a charter declares
    ``packages: [consent, ai_governance, ...]``.
    """

    packages: tuple[VocabularyPackage, ...]
    feature_names: frozenset[str]
    schema_names: frozenset[str]
    regulatory_basis: tuple[str, ...]
