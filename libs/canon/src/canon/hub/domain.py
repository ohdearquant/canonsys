"""Domain manifest: declarative grouping over vocabulary packages.

Domains are bounded contexts that group related vocabulary packages,
entities, routers, and charters. They provide organizational structure
without changing runtime resolution — PhraseResolver and PackageRegistry
still work by name, domains add a metadata layer on top.

Usage:
    from canon.hub.domain import DomainManifest
    from canon.hub.domain_loader import discover_domains

    domains = discover_domains(Path("hub/domains"))
    for d in domains:
        print(f"{d.name}: {d.package_names}")
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ("DomainManifest",)


@dataclass(frozen=True, slots=True)
class DomainManifest:
    """Declarative domain grouping over vocabulary packages.

    Each domain maps to a bounded context in the compliance system.
    Packages within a domain share regulatory scope and ubiquitous language.

    Attributes:
        name: Domain identifier (e.g., "talent", "governance").
        description: Human-readable domain purpose.
        version: Semantic version string.
        package_names: Packages this domain owns (exclusive — no sharing).
        charter_globs: Glob patterns for charter files (e.g., "exception_offer.*").
        entity_modules: Importable module paths for domain entities.
        router_modules: Importable module paths for FastAPI routers.
        regulatory_basis: Aggregated regulatory references.
        dependencies: Other domain names this depends on (should be minimal).
    """

    name: str
    description: str
    version: str = "2026.01"
    package_names: frozenset[str] = frozenset()
    charter_globs: tuple[str, ...] = ()
    entity_modules: tuple[str, ...] = ()
    router_modules: tuple[str, ...] = ()
    regulatory_basis: tuple[str, ...] = ()
    dependencies: frozenset[str] = frozenset()
