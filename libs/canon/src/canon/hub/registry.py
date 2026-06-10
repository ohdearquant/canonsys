"""Package registry: lookup, list, and resolve vocabulary packages."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .package import PackageManifest, VocabularyPackage

__all__ = ("PackageRegistry",)


class PackageRegistry:
    """Registry of vocabulary packages with FeatureRegistry-compatible lookup.

    Implements the ``FeatureRegistry`` Protocol from
    ``canon.dsl.resolver`` via ``get_feature(name)``.
    """

    def __init__(self, packages: Sequence[VocabularyPackage]) -> None:
        self._packages: dict[str, VocabularyPackage] = {p.name: p for p in packages}
        self._feature_to_package: dict[str, str] = {}
        for pkg in packages:
            for fname in pkg.feature_names:
                self._feature_to_package[fname] = pkg.name

    # --- FeatureRegistry Protocol ---

    def get_feature(self, name: str) -> Any | None:
        """Return truthy sentinel if feature is known, None otherwise."""
        pkg_name = self._feature_to_package.get(name)
        return pkg_name if pkg_name is not None else None

    def get_all_feature_names(self) -> frozenset[str]:
        """Return all known feature names for suggestions."""
        return frozenset(self._feature_to_package.keys())

    # --- PackageRegistry Protocol ---

    def has_package(self, name: str) -> bool:
        return name in self._packages

    def get_package_phrases(self, name: str) -> frozenset[str] | None:
        """Return set of phrase names exported by package, or None if unknown."""
        pkg = self._packages.get(name)
        if pkg is None:
            return None
        return frozenset(pkg.feature_names)

    # --- Package operations ---

    def get_package(self, name: str) -> VocabularyPackage | None:
        return self._packages.get(name)

    def list_packages(self) -> list[VocabularyPackage]:
        return sorted(self._packages.values(), key=lambda p: p.name)

    def resolve(self, names: Sequence[str]) -> PackageManifest:
        """Resolve package names to a unified manifest.

        Raises:
            KeyError: If any package name is unknown.
        """
        packages: list[VocabularyPackage] = []
        all_features: set[str] = set()
        all_schemas: set[str] = set()
        all_regulatory: list[str] = []

        for name in names:
            pkg = self._packages.get(name)
            if pkg is None:
                known = sorted(self._packages.keys())
                raise KeyError(f"Unknown package '{name}'. Available: {known}")
            packages.append(pkg)
            all_features.update(pkg.feature_names)
            all_schemas.update(pkg.schema_names)
            all_regulatory.extend(pkg.regulatory_basis)

        return PackageManifest(
            packages=tuple(packages),
            feature_names=frozenset(all_features),
            schema_names=frozenset(all_schemas),
            regulatory_basis=tuple(dict.fromkeys(all_regulatory)),
        )

    def feature_package(self, feature_name: str) -> str | None:
        """Return the package name that owns a feature."""
        return self._feature_to_package.get(feature_name)
