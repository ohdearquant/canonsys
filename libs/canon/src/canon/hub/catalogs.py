"""Re-export catalog builders from canon-catalogs package.

This module provides backward-compatible imports for code that uses
`from .catalogs import ...` within the canon.hub module.

The actual implementations live in the canon-catalogs package at
hub/catalogs/src/catalogs/.
"""

try:
    from catalogs import build_canon_hr_catalog, build_canonsys_catalog
except ModuleNotFoundError:

    def build_canon_hr_catalog(catalog):  # type: ignore[misc]
        """Stub — install canon-catalogs package for real catalogs."""

    def build_canonsys_catalog(catalog):  # type: ignore[misc]
        """Stub — install canon-catalogs package for real catalogs."""


__all__ = ("build_canon_hr_catalog", "build_canonsys_catalog")
