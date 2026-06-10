"""Load vocabulary packages from canon.toml manifest files.

This module provides discovery and loading of vocabulary packages from their
declarative canon.toml manifest files, making the TOML the source of truth
instead of Python package.py files.

Usage:
    from canon.hub.loader import discover_packages, load_package

    # Discover all packages in a directory
    packages = discover_packages(Path("hub/packages"))

    # Load a single package
    pkg = load_package(Path("hub/packages/consent"))

    # Create registry from discovered packages
    registry = PackageRegistry(packages)
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from canon.exceptions import ConfigurationError

from .package import VocabularyPackage

__all__ = (
    "PackageManifestError",
    "discover_packages",
    "load_package",
    "load_package_from_toml",
)


class PackageManifestError(ConfigurationError):
    """Error loading or parsing a canon.toml manifest.

    Inherits from ConfigurationError so it's caught by `except CanonError`.
    """

    default_message = "Package manifest error"

    def __init__(self, path: Path, message: str) -> None:
        self.path = path
        super().__init__(
            f"{path}: {message}",
            details={"path": str(path), "message": message},
        )


def load_package_from_toml(toml_path: Path) -> VocabularyPackage:
    """Load a VocabularyPackage from a canon.toml file.

    Args:
        toml_path: Path to the canon.toml file.

    Returns:
        VocabularyPackage instance.

    Raises:
        PackageManifestError: If the file cannot be parsed or is invalid.
    """
    if not toml_path.exists():
        raise PackageManifestError(toml_path, "File not found")

    try:
        content = toml_path.read_text()
        data = tomllib.loads(content)
    except tomllib.TOMLDecodeError as e:
        raise PackageManifestError(toml_path, f"Invalid TOML: {e}") from e

    return _parse_manifest(toml_path, data)


def load_package(package_dir: Path) -> VocabularyPackage:
    """Load a VocabularyPackage from a package directory.

    Looks for canon.toml in the package directory.

    Args:
        package_dir: Path to the package directory.

    Returns:
        VocabularyPackage instance.

    Raises:
        PackageManifestError: If canon.toml is missing or invalid.
    """
    toml_path = package_dir / "canon.toml"
    return load_package_from_toml(toml_path)


def discover_packages(packages_dir: Path) -> list[VocabularyPackage]:
    """Discover and load all vocabulary packages in a directory.

    Scans for subdirectories containing canon.toml files.

    Args:
        packages_dir: Path to the packages directory (e.g., hub/packages).

    Returns:
        List of VocabularyPackage instances, sorted by name.

    Raises:
        PackageManifestError: If any package has an invalid manifest.
    """
    packages: list[VocabularyPackage] = []

    for item in sorted(packages_dir.iterdir()):
        if not item.is_dir():
            continue
        if item.name.startswith("_"):
            continue

        toml_path = item / "canon.toml"
        if toml_path.exists():
            pkg = load_package_from_toml(toml_path)
            packages.append(pkg)

    return packages


def _parse_manifest(path: Path, data: dict[str, Any]) -> VocabularyPackage:
    """Parse a canon.toml manifest into a VocabularyPackage."""
    # Required: [package] section
    pkg_section = data.get("package")
    if not pkg_section:
        raise PackageManifestError(path, "Missing [package] section")

    name = pkg_section.get("name")
    if not name:
        raise PackageManifestError(path, "Missing package.name")

    description = pkg_section.get("description", f"{name} vocabulary package")
    version = pkg_section.get("version", "2026.01")

    # Regulatory basis (optional)
    regulatory_section = pkg_section.get("regulatory", {})
    regulatory_basis = tuple(regulatory_section.get("basis", []))

    # Phrases section - collect all phrase types
    phrases_section = data.get("phrases", {})
    all_phrases: set[str] = set()

    for phrase_type in (
        "require",
        "verify",
        "derive",
        "action",
        "check",
        "get",
        "other",
    ):
        phrases = phrases_section.get(phrase_type, [])
        if isinstance(phrases, list):
            all_phrases.update(phrases)

    # Schemas section
    schemas_section = data.get("schemas", {})
    schema_types = schemas_section.get("types", [])

    # Dependencies section (for future use)
    # deps_section = data.get("dependencies", {})

    # Import module is canon_vocab_{name} (e.g., canon_vocab_consent)
    domain_module = f"canon_vocab_{name}"

    return VocabularyPackage(
        name=name,
        description=description,
        feature_names=frozenset(all_phrases),
        schema_names=frozenset(schema_types),
        regulatory_basis=regulatory_basis,
        version=version,
        domain_module=domain_module,
    )
