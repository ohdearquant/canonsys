"""All vocabulary packages - discovered from domain directories at import time.

This module provides the ALL_PACKAGES tuple used by build_hub() to
construct the full Hub with all vocabulary packages registered.

Packages are discovered from the domain-organized layout:
    hub/foundation/packages/     — cross-cutting vocabulary primitives
    hub/domains/*/packages/      — domain-specific packages
    hub/packages/                — legacy fallback (for backward compatibility)
"""

from __future__ import annotations

import os
from pathlib import Path

from .loader import discover_packages
from .package import VocabularyPackage

__all__ = ("ALL_PACKAGES", "get_packages_dir")


def get_packages_dir() -> Path:
    """Get the path to the hub/ root directory.

    Returns the hub/ directory (parent of domains/, foundation/, packages/).

    Looks for the hub directory relative to common project layouts:
    1. CANON_PACKAGES_DIR environment variable (explicit override, returns as-is)
    2. Relative to this file: ../../../../../hub (development layout)
    3. Current working directory: hub (when running from project root)
    """
    # Environment variable override (backward compat: may point to hub/packages/)
    if env_path := os.environ.get("CANON_PACKAGES_DIR"):
        p = Path(env_path)
        # If it points to hub/packages, return parent (hub/)
        if p.name == "packages" and (p.parent / "domains").exists():
            return p.parent
        return p

    # Development layout: libs/canon/src/canon/hub/packages.py -> hub/
    this_file = Path(__file__).resolve()
    dev_path = this_file.parent.parent.parent.parent.parent.parent / "hub"
    if dev_path.exists():
        return dev_path

    # Project root layout
    cwd_path = Path.cwd() / "hub"
    if cwd_path.exists():
        return cwd_path

    # Fallback
    return dev_path


def _discover_package_dirs(hub_dir: Path) -> list[Path]:
    """Collect all package directories from the domain-organized layout.

    Scans:
        hub_dir/foundation/packages/*/
        hub_dir/domains/*/packages/*/
        hub_dir/packages/*/              (legacy fallback)
    """
    dirs: list[Path] = []

    # Foundation packages
    foundation_pkgs = hub_dir / "foundation" / "packages"
    if foundation_pkgs.is_dir():
        dirs.append(foundation_pkgs)

    # Domain packages
    domains_dir = hub_dir / "domains"
    if domains_dir.is_dir():
        for domain in sorted(domains_dir.iterdir()):
            domain_pkgs = domain / "packages"
            if domain_pkgs.is_dir():
                dirs.append(domain_pkgs)

    # Legacy: hub/packages/ (backward compatibility)
    legacy_pkgs = hub_dir / "packages"
    if legacy_pkgs.is_dir():
        dirs.append(legacy_pkgs)

    return dirs


def _load_all_packages() -> tuple[VocabularyPackage, ...]:
    """Load all vocabulary packages from domain-organized directories."""
    hub_dir = get_packages_dir()
    if not hub_dir.exists():
        return ()

    all_packages: list[VocabularyPackage] = []
    seen_names: set[str] = set()

    for pkg_dir in _discover_package_dirs(hub_dir):
        for pkg in discover_packages(pkg_dir):
            if pkg.name not in seen_names:
                all_packages.append(pkg)
                seen_names.add(pkg.name)

    all_packages.sort(key=lambda p: p.name)
    return tuple(all_packages)


# Discover all packages at module import time
ALL_PACKAGES: tuple[VocabularyPackage, ...] = _load_all_packages()
