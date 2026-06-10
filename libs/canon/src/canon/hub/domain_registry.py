"""Domain registry: maps packages and features to domains.

Wraps PackageRegistry with domain grouping metadata. Does NOT replace
PackageRegistry — charter compilation and PhraseResolver still use
PackageRegistry directly. DomainRegistry adds organizational queries.

Usage:
    registry = DomainRegistry(domains, package_registry)
    registry.domain_for_package("consent")        # "foundation"
    registry.domain_for_feature("verify_consent")  # "foundation"
    registry.packages_in_domain("talent")          # [hiring_brief]
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .domain import DomainManifest
from .package import VocabularyPackage
from .registry import PackageRegistry

__all__ = ("DomainRegistry",)


class DomainRegistry:
    """Registry of domains with package and feature resolution.

    Enforces exclusive package ownership — each package belongs to
    exactly one domain. Provides queries for domain membership,
    feature→domain resolution, and charter cross-domain analysis.
    """

    def __init__(
        self,
        domains: Sequence[DomainManifest],
        package_registry: PackageRegistry,
    ) -> None:
        self._domains: dict[str, DomainManifest] = {}
        self._package_to_domain: dict[str, str] = {}

        for domain in domains:
            if domain.name in self._domains:
                raise ValueError(f"Duplicate domain name: '{domain.name}'")
            self._domains[domain.name] = domain

            for pkg_name in domain.package_names:
                if pkg_name in self._package_to_domain:
                    raise ValueError(
                        f"Package '{pkg_name}' claimed by both "
                        f"'{self._package_to_domain[pkg_name]}' and '{domain.name}'"
                    )
                self._package_to_domain[pkg_name] = domain.name

        self._package_registry = package_registry

    # --- Domain queries ---

    def get_domain(self, name: str) -> DomainManifest | None:
        """Get a domain by name."""
        return self._domains.get(name)

    def list_domains(self) -> list[DomainManifest]:
        """List all domains sorted by name."""
        return sorted(self._domains.values(), key=lambda d: d.name)

    def domain_for_package(self, package_name: str) -> str | None:
        """Return the domain name that owns a package."""
        return self._package_to_domain.get(package_name)

    def domain_for_feature(self, feature_name: str) -> str | None:
        """Trace feature → package → domain."""
        pkg_name = self._package_registry.feature_package(feature_name)
        if pkg_name is None:
            return None
        return self._package_to_domain.get(pkg_name)

    def packages_in_domain(self, domain_name: str) -> list[VocabularyPackage]:
        """Return VocabularyPackage instances belonging to a domain."""
        domain = self._domains.get(domain_name)
        if domain is None:
            return []
        result = []
        for pkg_name in sorted(domain.package_names):
            pkg = self._package_registry.get_package(pkg_name)
            if pkg is not None:
                result.append(pkg)
        return result

    def unassigned_packages(self) -> list[str]:
        """Return package names not belonging to any domain."""
        all_pkg_names = {p.name for p in self._package_registry.list_packages()}
        assigned = set(self._package_to_domain.keys())
        return sorted(all_pkg_names - assigned)

    # --- Cross-domain analysis ---

    def charter_domain_deps(self, package_names: frozenset[str]) -> set[str]:
        """Given charter package names, return which domains are involved."""
        domains_used: set[str] = set()
        for pkg_name in package_names:
            domain = self._package_to_domain.get(pkg_name)
            if domain:
                domains_used.add(domain)
        return domains_used

    # --- FeatureRegistry Protocol delegation ---

    def get_feature(self, name: str) -> Any | None:
        """Delegate to PackageRegistry."""
        return self._package_registry.get_feature(name)

    def get_all_feature_names(self) -> frozenset[str]:
        """Delegate to PackageRegistry."""
        return self._package_registry.get_all_feature_names()
