"""Domain discovery: scan for domain.toml manifests.

Mirrors the discover_packages() pattern from loader.py but for domains.
Each domain directory contains a domain.toml file declaring its packages,
charters, entities, and routers.

Usage:
    from canon.hub.domain_loader import discover_domains

    domains = discover_domains(Path("hub/domains"))
    foundation = load_domain(Path("hub/foundation"))
"""

from __future__ import annotations

import logging
import tomllib
from pathlib import Path
from typing import Any

from .domain import DomainManifest

__all__ = ("discover_domains", "load_domain")

logger = logging.getLogger(__name__)


def load_domain(domain_dir: Path) -> DomainManifest:
    """Load a DomainManifest from a domain.toml file.

    Args:
        domain_dir: Directory containing domain.toml.

    Returns:
        DomainManifest instance.

    Raises:
        FileNotFoundError: If domain.toml doesn't exist.
        ValueError: If the manifest is invalid.
    """
    toml_path = domain_dir / "domain.toml"
    if not toml_path.exists():
        raise FileNotFoundError(f"No domain.toml in {domain_dir}")

    content = toml_path.read_text()
    data = tomllib.loads(content)
    return _parse_domain(toml_path, data)


def discover_domains(*search_dirs: Path) -> list[DomainManifest]:
    """Discover domain manifests from one or more directories.

    Scans each search directory for subdirectories containing domain.toml.
    Also checks if the search directory itself contains domain.toml
    (for foundation-level manifests).

    Args:
        search_dirs: Directories to scan (e.g., Path("hub/domains"), Path("hub/foundation")).

    Returns:
        List of DomainManifest instances, sorted by name.
    """
    domains: list[DomainManifest] = []

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue

        # Check if the directory itself has domain.toml (e.g., hub/foundation/domain.toml)
        if (search_dir / "domain.toml").exists():
            try:
                domains.append(load_domain(search_dir))
            except (ValueError, tomllib.TOMLDecodeError) as e:
                logger.warning("Failed to load domain from %s: %s", search_dir, e)

        # Scan subdirectories
        for item in sorted(search_dir.iterdir()):
            if not item.is_dir():
                continue
            if item.name.startswith("_") or item.name.startswith("."):
                continue
            if (item / "domain.toml").exists():
                try:
                    domains.append(load_domain(item))
                except (ValueError, tomllib.TOMLDecodeError) as e:
                    logger.warning("Failed to load domain from %s: %s", item, e)

    return sorted(domains, key=lambda d: d.name)


def _parse_domain(path: Path, data: dict[str, Any]) -> DomainManifest:
    """Parse a domain.toml into a DomainManifest."""
    d = data.get("domain")
    if not d:
        raise ValueError(f"{path}: Missing [domain] section")

    name = d.get("name")
    if not name:
        raise ValueError(f"{path}: Missing domain.name")

    return DomainManifest(
        name=name,
        description=d.get("description", ""),
        version=d.get("version", "2026.01"),
        package_names=frozenset(d.get("packages", [])),
        charter_globs=tuple(d.get("charters", [])),
        entity_modules=tuple(d.get("entity_modules", [])),
        router_modules=tuple(d.get("router_modules", [])),
        regulatory_basis=tuple(d.get("regulatory_basis", [])),
        dependencies=frozenset(d.get("dependencies", [])),
    )
