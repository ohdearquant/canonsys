"""RegoBuilder - transpiles PolicyDefinition to Rego source code.

This module implements the RegoBuilder for Canon's Two-Key Model:
- Key 1 (Legal): PolicyDefinition defines WHAT is required
- Key 2 (Engineering): RegoBuilder transpiles to HOW (executable Rego)

Neither key alone can modify enforcement behavior. Both must align
for a policy to be active.

Architecture References:
- design/opa_architecture.md Section 4 (RegoBuilder Design)
- research/rego_patterns.md (Rego policy patterns)
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from canon.exceptions import BundleError, TranspilationError
from kron.utils import compute_hash, now_utc

if TYPE_CHECKING:
    from canon.entities.policy import PolicyDefinition


# =============================================================================
# Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class RegoModule:
    """Generated Rego module from PolicyDefinition.

    Represents a single Rego policy module with source code and metadata.
    Used for bundling and deployment.

    Attributes:
        package: Rego package name (e.g., "canon.statutory.nyc.fair_chance")
        source: Rego source code
        policy_id: Source PolicyDefinition.policy_id
        version: Source PolicyDefinition.version
        generated_at: When module was generated
        metadata: Additional metadata
    """

    package: str
    source: str
    policy_id: str
    version: str
    generated_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def filename(self) -> str:
        """Generate filename from package name."""
        # canon.statutory.nyc.fair_chance -> fair_chance.rego
        parts = self.package.split(".")
        return f"{parts[-1]}.rego" if parts else "policy.rego"

    @property
    def relative_path(self) -> str:
        """Generate relative path from package name."""
        # canon.statutory.nyc.fair_chance -> canon/statutory/nyc/fair_chance.rego
        parts = self.package.split(".")
        return "/".join(parts[:-1]) + f"/{parts[-1]}.rego" if parts else "policy.rego"


class ValidationSeverity(StrEnum):
    """Severity level for Rego validation issues."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """Single validation issue found in Rego code.

    Attributes:
        severity: Issue severity level
        message: Human-readable description
        line: Line number (if applicable)
        column: Column number (if applicable)
        rule: Rule that triggered the issue (if applicable)
    """

    severity: ValidationSeverity
    message: str
    line: int | None = None
    column: int | None = None
    rule: str | None = None


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Result of Rego validation.

    Attributes:
        valid: True if no errors (warnings OK)
        issues: Tuple of validation issues
        parsed_at: When validation occurred
    """

    valid: bool
    issues: tuple[ValidationIssue, ...] = field(default_factory=tuple)
    parsed_at: datetime | None = None

    @property
    def errors(self) -> list[ValidationIssue]:
        """Get only error-level issues."""
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        """Get only warning-level issues."""
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]


@dataclass(frozen=True, slots=True)
class BundleInfo:
    """Information about a built policy bundle.

    Attributes:
        revision: Bundle revision string (e.g., "2026.01.11-a7f3c821")
        path: Path to bundle on disk
        loaded_at: When bundle was created/loaded
        policy_count: Number of policies in bundle
        roots: Rego package roots
        metadata: Additional bundle metadata
    """

    revision: str
    path: str
    loaded_at: datetime
    policy_count: int = 0
    roots: tuple[str, ...] = ("canon",)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def hash(self) -> str:
        """Policy library hash for evidence."""
        return f"sha256:{self.revision}"


# =============================================================================
# RegoBuilder Implementation
# =============================================================================


class RegoBuilder:
    """Transpiles PolicyDefinition to Rego source code.

    The RegoBuilder translates PolicyDefinition (Legal's language) to
    Rego (Engineering's execution). Maintains the Two-Key Model where
    both Legal and Engineering must approve policy changes.

    Transpilation Strategy:
    - Template-based generation with validation
    - PolicyDefinition fields map to Rego constructs
    - Business days calculated in Python, passed to Rego as input

    Example:
        builder = RegoBuilder()
        module = builder.transpile(policy_definition)
        validation = builder.validate(module.source)
        if validation.valid:
            bundle = builder.build_bundle([module], data={"holidays": {...}})

    Architecture Reference: design/opa_architecture.md Section 4
    """

    # Generator metadata
    GENERATOR_VERSION = "canon.rego_builder.v1"

    # Rego v1 import (required for modern Rego syntax)
    REGO_IMPORT = "import rego.v1"

    def __init__(self) -> None:
        """Initialize RegoBuilder."""
        pass

    # -------------------------------------------------------------------------
    # Main Interface
    # -------------------------------------------------------------------------

    def transpile(self, policy: PolicyDefinition) -> RegoModule:
        """Generate Rego module from PolicyDefinition.

        Args:
            policy: PolicyDefinition entity

        Returns:
            RegoModule with source code and metadata

        Raises:
            TranspilationError: On transpilation failure
        """
        # Validate required fields
        self._validate_policy(policy)

        # Derive package name from policy_id
        package = self._derive_package(policy)

        # Generate Rego source
        source = self._generate_rego(policy, package)

        return RegoModule(
            package=package,
            source=source,
            policy_id=policy.policy_id,
            version=policy.version,
            generated_at=now_utc(),
            metadata={
                "generator": self.GENERATOR_VERSION,
                "source_policy_status": policy.status,
            },
        )

    def validate(self, rego_source: str) -> ValidationResult:
        """Validate Rego syntax and semantics.

        Performs basic regex-based validation. For full validation,
        use OPA's `opa check` command or regorus parser.

        Args:
            rego_source: Rego source code

        Returns:
            ValidationResult with errors/warnings
        """
        issues: list[ValidationIssue] = []
        lines = rego_source.split("\n")

        # Check for required elements
        issues.extend(self._check_required_elements(rego_source, lines))

        # Check for syntax issues
        issues.extend(self._check_syntax_issues(rego_source, lines))

        # Check for best practices
        issues.extend(self._check_best_practices(rego_source, lines))

        # Determine validity (no errors)
        valid = not any(i.severity == ValidationSeverity.ERROR for i in issues)

        return ValidationResult(
            valid=valid,
            issues=tuple(issues),
            parsed_at=now_utc(),
        )

    def build_bundle(
        self,
        modules: list[RegoModule],
        data: dict[str, Any] | None = None,
        output_path: str | None = None,
    ) -> BundleInfo:
        """Build OPA bundle from modules and data.

        Creates a bundle directory structure:
            {output_path}/
            |-- .manifest
            |-- {module paths}
            |-- data/
                |-- {data files}

        Args:
            modules: List of Rego modules
            data: Static data (holidays, jurisdictions) - keys become filenames
            output_path: Where to write bundle (uses temp dir if None)

        Returns:
            BundleInfo with path and metadata

        Raises:
            BundleError: On bundle build failure
        """
        if not modules:
            raise BundleError(output_path, "No modules provided")

        # Use temp directory if no path specified
        if output_path is None:
            output_path = tempfile.mkdtemp(prefix="canon_bundle_")

        # Create directory structure
        os.makedirs(output_path, exist_ok=True)

        # Generate revision from module hashes
        revision = self._generate_revision(modules)

        # Write modules
        for module in modules:
            self._write_module(output_path, module)

        # Write data files
        if data:
            self._write_data(output_path, data)

        # Write manifest
        manifest = self._create_manifest(modules, revision, data)
        manifest_path = os.path.join(output_path, ".manifest")
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

        return BundleInfo(
            revision=revision,
            path=output_path,
            loaded_at=now_utc(),
            policy_count=len(modules),
            roots=tuple(self._get_roots(modules)),
            metadata=manifest.get("metadata", {}),
        )

    # -------------------------------------------------------------------------
    # Transpilation Helpers
    # -------------------------------------------------------------------------

    def _validate_policy(self, policy: PolicyDefinition) -> None:
        """Validate PolicyDefinition has required fields for transpilation."""
        if not policy.policy_id:
            raise TranspilationError(
                policy.policy_id or "<unknown>",
                "policy_id is required",
            )

        if not policy.version:
            raise TranspilationError(
                policy.policy_id,
                "version is required",
            )

        if not policy.name:
            raise TranspilationError(
                policy.policy_id,
                "name is required",
            )

    def _derive_package(self, policy: PolicyDefinition) -> str:
        """Derive Rego package name from PolicyDefinition.

        Package naming convention:
            canon.statutory.{jurisdiction}.{domain}

        Examples:
            us-nyc.fair_chance.adverse_action -> canon.statutory.nyc.fair_chance
            us.fcra.background_check -> canon.statutory.us.fcra
        """
        policy_id = policy.policy_id

        # Parse policy_id: {jurisdiction}.{domain}.{rule}
        parts = policy_id.split(".")
        if len(parts) < 2:
            raise TranspilationError(
                policy_id,
                f"Invalid policy_id format: expected {{jurisdiction}}.{{domain}}.{{rule}}, got {policy_id}",
            )

        # Extract jurisdiction (normalize: us-nyc -> nyc, us -> us)
        jurisdiction_part = parts[0].lower()
        if "-" in jurisdiction_part:
            # us-nyc -> nyc (take locality)
            jurisdiction = jurisdiction_part.split("-")[-1]
        else:
            jurisdiction = jurisdiction_part

        # Extract domain (second part)
        domain = parts[1].lower().replace("-", "_")

        return f"canon.statutory.{jurisdiction}.{domain}"

    def _generate_rego(self, policy: PolicyDefinition, package: str) -> str:
        """Generate Rego source code from PolicyDefinition.

        Template structure follows design/opa_architecture.md Section 4.4
        """
        generated_at = now_utc().isoformat()

        # Build metadata object
        metadata = self._build_metadata(policy, generated_at)

        # Build gate IDs array
        gate_ids = self._extract_gate_ids(policy)

        # Build jurisdictions array
        jurisdictions = policy.jurisdictions or []

        # Build action types array
        action_types = policy.action_types or []

        # Build effective_from date string
        effective_from = self._format_effective_date(policy)

        # Generate Rego using template
        rego = f"""# Generated from PolicyDefinition: {policy.policy_id} v{policy.version}
# Generated at: {generated_at}
# Generator: {self.GENERATOR_VERSION}
#
# DO NOT EDIT - This file is auto-generated from PolicyDefinition.
# Changes should be made to the PolicyDefinition entity.

package {package}

{self.REGO_IMPORT}

# =============================================================================
# Metadata (from PolicyDefinition)
# =============================================================================
metadata := {self._to_rego_object(metadata)}

# =============================================================================
# Applicability (from scope, jurisdictions, action_types)
# =============================================================================
default applicable := false

applicable if {{
{self._generate_applicability_conditions(jurisdictions, action_types, effective_from)}
}}

{self._generate_effective_rule(effective_from)}

# =============================================================================
# Gate Requirements (from required_gates)
# =============================================================================
required_gates := {self._to_rego_array(gate_ids)}

# =============================================================================
# Main Evaluation
# =============================================================================
default allow := false

allow if {{
    applicable
    gates_passed
    not deny
}}

gates_passed if {{
    every gate_id in required_gates {{
        gate_result_passed(gate_id)
    }}
}}

gate_result_passed(gate_id) if {{
    some result in input.gate_results
    result.gate == gate_id
    result.passed == true
}}

# =============================================================================
# Deny Conditions (explicit blocks)
# =============================================================================
default deny := false

{self._generate_deny_conditions(policy)}

# =============================================================================
# Deny Reasons (for evidence)
# =============================================================================
deny_reasons contains reason if {{
    applicable
    some gate_id in required_gates
    not gate_result_passed(gate_id)
    reason := sprintf("Required gate '%s' did not pass", [gate_id])
}}

{self._generate_additional_deny_reasons(policy)}

# =============================================================================
# Structured Output (for Evidence integration)
# =============================================================================
gate_output := {{
    "gate_id": concat(".", ["policy", metadata.policy_id]),
    "passed": allow,
    "message": output_message,
    "policy_id": metadata.policy_id,
    "policy_version": metadata.version,
    "jurisdiction": metadata.authority.jurisdiction_code,
    "regulation": metadata.authority.citation,
    "deny_reasons": deny_reasons,
    "gates_evaluated": required_gates,
    "applicable": applicable,
}}

output_message := "Policy requirements met" if allow
output_message := concat("; ", deny_reasons) if not allow
"""
        return rego

    def _build_metadata(self, policy: PolicyDefinition, generated_at: str) -> dict:
        """Build metadata object for Rego."""
        authority = policy.authority or {}

        return {
            "policy_id": policy.policy_id,
            "version": policy.version,
            "name": policy.name,
            "authority": {
                "citation": authority.get("citation", ""),
                "jurisdiction_code": authority.get("jurisdiction_code", ""),
                "effective_date": authority.get("effective_date", ""),
            },
            "generated_at": generated_at,
            "generator_version": self.GENERATOR_VERSION,
        }

    def _extract_gate_ids(self, policy: PolicyDefinition) -> list[str]:
        """Extract gate IDs from required_gates."""
        gate_ids = []
        for gate_req in policy.required_gates:
            if isinstance(gate_req, dict):
                gate_id = gate_req.get("gate_id")
                if gate_id:
                    gate_ids.append(gate_id)
        return gate_ids

    def _format_effective_date(self, policy: PolicyDefinition) -> str | None:
        """Format effective_from date for Rego comparison."""
        if policy.effective_from:
            return policy.effective_from.strftime("%Y-%m-%d")
        if policy.authority:
            effective_date = policy.authority.get("effective_date")
            if effective_date:
                if isinstance(effective_date, str):
                    return effective_date
                return (
                    effective_date.isoformat()
                    if hasattr(effective_date, "isoformat")
                    else str(effective_date)
                )
        return None

    def _generate_applicability_conditions(
        self,
        jurisdictions: list[str],
        action_types: list[str],
        effective_from: str | None,
    ) -> str:
        """Generate applicability conditions."""
        conditions = []

        if jurisdictions:
            jur_array = self._to_rego_array(jurisdictions)
            conditions.append(f"    input.jurisdiction in {jur_array}")

        if action_types:
            action_array = self._to_rego_array(action_types)
            conditions.append(f"    input.action_type in {action_array}")

        if effective_from:
            conditions.append("    is_effective")

        if not conditions:
            conditions.append("    true")  # Always applicable if no restrictions

        return "\n".join(conditions)

    def _generate_effective_rule(self, effective_from: str | None) -> str:
        """Generate is_effective rule."""
        if not effective_from:
            return """is_effective := true  # No effective date restriction"""

        return f"""is_effective if {{
    # Policy effective from {effective_from}
    time.parse_rfc3339_ns(input.evaluated_at) >= time.parse_ns("2006-01-02", "{effective_from}")
}}"""

    def _generate_deny_conditions(self, policy: PolicyDefinition) -> str:
        """Generate deny conditions based on policy requirements."""
        # Default deny condition when no gates have passed
        return """deny if {
    applicable
    count(required_gates) > 0
    count([g | some g in required_gates; gate_result_passed(g)]) == 0
}"""

    def _generate_additional_deny_reasons(self, policy: PolicyDefinition) -> str:
        """Generate additional deny reasons from requirements."""
        # Add deny reason for missing applicable context
        return """deny_reasons contains "Context not applicable to this policy" if {
    not applicable
}"""

    def _to_rego_object(self, obj: dict) -> str:
        """Convert Python dict to Rego object literal."""
        return json.dumps(obj, indent=4).replace('": ', '": ')

    def _to_rego_array(self, arr: list) -> str:
        """Convert Python list to Rego array literal."""
        return json.dumps(arr)

    # -------------------------------------------------------------------------
    # Validation Helpers
    # -------------------------------------------------------------------------

    def _check_required_elements(
        self,
        source: str,
        lines: list[str],
    ) -> list[ValidationIssue]:
        """Check for required Rego elements."""
        issues = []

        # Must have package declaration
        if not re.search(r"^\s*package\s+\S+", source, re.MULTILINE):
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message="Missing package declaration",
                    line=1,
                    rule="required-package",
                )
            )

        # Must have default allow
        if "default allow" not in source:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message="Missing 'default allow := false' - fail-closed semantics required",
                    rule="fail-closed",
                )
            )

        # Should import rego.v1 for modern syntax
        if "import rego.v1" not in source:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message="Missing 'import rego.v1' - recommended for modern Rego syntax",
                    rule="rego-v1",
                )
            )

        return issues

    def _check_syntax_issues(
        self,
        source: str,
        lines: list[str],
    ) -> list[ValidationIssue]:
        """Check for basic syntax issues."""
        issues = []

        for i, line in enumerate(lines, start=1):
            # Check for unbalanced braces in single line
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                open_braces = stripped.count("{") - stripped.count("}")
                if open_braces < 0:
                    issues.append(
                        ValidationIssue(
                            severity=ValidationSeverity.ERROR,
                            message="Unbalanced closing brace",
                            line=i,
                            rule="syntax-braces",
                        )
                    )

            # Check for common typos
            if "==true" in line.replace(" ", ""):
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.INFO,
                        message="Consider using '== true' with spaces for readability",
                        line=i,
                        rule="style-spacing",
                    )
                )

        return issues

    def _check_best_practices(
        self,
        source: str,
        lines: list[str],
    ) -> list[ValidationIssue]:
        """Check for best practice violations."""
        issues = []

        # Check for metadata
        if "metadata :=" not in source:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message="Missing metadata object - recommended for audit trail",
                    rule="best-practice-metadata",
                )
            )

        # Check for deny_reasons
        if "deny_reasons" not in source:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message="Missing deny_reasons - recommended for evidence generation",
                    rule="best-practice-deny-reasons",
                )
            )

        return issues

    # -------------------------------------------------------------------------
    # Bundle Helpers
    # -------------------------------------------------------------------------

    def _generate_revision(self, modules: list[RegoModule]) -> str:
        """Generate bundle revision from modules."""
        # Combine policy_ids and versions for hash
        content = ";".join(
            f"{m.policy_id}:{m.version}" for m in sorted(modules, key=lambda x: x.policy_id)
        )
        hash_suffix = compute_hash(content)[:8]
        date_prefix = now_utc().strftime("%Y.%m.%d")
        return f"{date_prefix}-{hash_suffix}"

    def _write_module(self, output_path: str, module: RegoModule) -> None:
        """Write a single Rego module to bundle."""
        # Create directory structure from package
        module_path = os.path.join(output_path, module.relative_path)
        os.makedirs(os.path.dirname(module_path), exist_ok=True)

        with open(module_path, "w") as f:
            f.write(module.source)

    def _write_data(self, output_path: str, data: dict[str, Any]) -> None:
        """Write data files to bundle."""
        data_dir = os.path.join(output_path, "data")
        os.makedirs(data_dir, exist_ok=True)

        for key, value in data.items():
            # Nested dict = nested directory
            if isinstance(value, dict):
                nested_dir = os.path.join(data_dir, key)
                os.makedirs(nested_dir, exist_ok=True)
                for subkey, subvalue in value.items():
                    file_path = os.path.join(nested_dir, f"{subkey}.json")
                    with open(file_path, "w") as f:
                        json.dump(subvalue, f, indent=2)
            else:
                file_path = os.path.join(data_dir, f"{key}.json")
                with open(file_path, "w") as f:
                    json.dump(value, f, indent=2)

    def _create_manifest(
        self,
        modules: list[RegoModule],
        revision: str,
        data: dict[str, Any] | None,
    ) -> dict:
        """Create bundle manifest."""
        return {
            "revision": revision,
            "rego_version": 1,
            "roots": list(self._get_roots(modules)),
            "metadata": {
                "policy_library_version": "1.0.0",
                "generated_at": now_utc().isoformat(),
                "generator": self.GENERATOR_VERSION,
                "policy_count": len(modules),
                "policies": [{"policy_id": m.policy_id, "version": m.version} for m in modules],
            },
            "wasm": [],
        }

    def _get_roots(self, modules: list[RegoModule]) -> set[str]:
        """Get unique package roots from modules."""
        roots = set()
        for module in modules:
            # canon.statutory.nyc.fair_chance -> canon
            parts = module.package.split(".")
            if parts:
                roots.add(parts[0])
        return roots or {"canon"}


# =============================================================================
# Module-level Factory
# =============================================================================

_rego_builder: RegoBuilder | None = None


def get_rego_builder() -> RegoBuilder:
    """Get the global RegoBuilder instance."""
    global _rego_builder
    if _rego_builder is None:
        _rego_builder = RegoBuilder()
    return _rego_builder


__all__ = [
    "BundleError",
    "BundleInfo",
    "RegoBuilder",
    "RegoModule",
    "TranspilationError",
    "ValidationIssue",
    "ValidationResult",
    "ValidationSeverity",
    "get_rego_builder",
]
