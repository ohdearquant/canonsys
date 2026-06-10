"""Tests for Supplemental domain charter compilation.

Verifies all Supplemental surface charters compile without errors.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from canon.dsl import compile_charter

# Directory containing Supplemental charters
SUPPLEMENTAL_CHARTERS_DIR = (
    Path(__file__).parent.parent.parent
    / "charters"
    / "surfaces"
    / "supplemental"
)


# -----------------------------------------------------------------
# Parameterized test for all Supplemental charters
# -----------------------------------------------------------------

SUPPLEMENTAL_CHARTER_FILES = [
    "privileged_finance_role.canon",
    "monitoring_removal.canon",
    "dlp_disable.canon",
    "export_permission.canon",
    "ethics_case_closure.canon",
    "reinstate_access.canon",
    "export_control_override.canon",
    "disable_audit_logging.canon",
    "legal_data_release.canon",
]


@pytest.mark.parametrize("charter_file", SUPPLEMENTAL_CHARTER_FILES)
def test_supplemental_charter_compiles(charter_file: str):
    """Verify Supplemental charter compiles without registries (syntax + structure only)."""
    charter_path = SUPPLEMENTAL_CHARTERS_DIR / charter_file

    assert charter_path.exists(), f"Charter file not found: {charter_path}"

    source = charter_path.read_text()

    # compile_charter without registries does syntax + structural validation
    # (skips feature/policy/package validation)
    compiled = compile_charter(source)

    assert compiled is not None
    assert compiled.name is not None
    assert compiled.version == "v1.0"
    assert len(compiled.workflow_names) == 1


@pytest.mark.parametrize("charter_file", SUPPLEMENTAL_CHARTER_FILES)
def test_supplemental_charter_has_packages(charter_file: str):
    """Verify Supplemental charter declares vocabulary packages."""
    charter_path = SUPPLEMENTAL_CHARTERS_DIR / charter_file
    source = charter_path.read_text()

    compiled = compile_charter(source)

    # All redesigned charters should have packages declared
    assert len(compiled.package_names) > 0, f"{charter_file} should have packages"

    # Common packages that should be present in Supplemental charters
    common_packages = {
        "authorization",
        "export_control",
        "controls",
        "lifecycle",
        "evidence",
    }
    assert common_packages.issubset(compiled.package_names), (
        f"{charter_file} should include common packages: {common_packages}"
    )


@pytest.mark.parametrize("charter_file", SUPPLEMENTAL_CHARTER_FILES)
def test_supplemental_charter_has_triggers(charter_file: str):
    """Verify Supplemental charter has event triggers."""
    charter_path = SUPPLEMENTAL_CHARTERS_DIR / charter_file
    source = charter_path.read_text()

    # Triggers are in the AST
    compiled = compile_charter(source)

    # Check that triggers are present in the AST
    assert compiled.ast.triggers is not None
    assert len(compiled.ast.triggers) >= 3, (
        f"{charter_file} should have at least 3 triggers for event-driven flow"
    )


@pytest.mark.parametrize("charter_file", SUPPLEMENTAL_CHARTER_FILES)
def test_supplemental_charter_phase_order(charter_file: str):
    """Verify Supplemental charter phases are properly ordered."""
    charter_path = SUPPLEMENTAL_CHARTERS_DIR / charter_file
    source = charter_path.read_text()

    compiled = compile_charter(source)

    workflow_name = compiled.workflow_names[0]
    phase_order = compiled.phase_order[workflow_name]

    # All charters should have at least eligibility and certification phases
    assert len(phase_order) >= 3, f"{charter_file} should have at least 3 phases"

    # First phase should be eligibility
    assert phase_order[0] == "eligibility", f"{charter_file} first phase should be 'eligibility'"

    # Last phase should be certification
    assert phase_order[-1] == "certification", (
        f"{charter_file} last phase should be 'certification'"
    )


@pytest.mark.parametrize("charter_file", SUPPLEMENTAL_CHARTER_FILES)
def test_supplemental_charter_has_situations(charter_file: str):
    """Verify Supplemental charter has situational conditions."""
    charter_path = SUPPLEMENTAL_CHARTERS_DIR / charter_file
    source = charter_path.read_text()

    compiled = compile_charter(source)

    assert len(compiled.situations) >= 1, (
        f"{charter_file} should have at least one situational condition"
    )


@pytest.mark.parametrize("charter_file", SUPPLEMENTAL_CHARTER_FILES)
def test_supplemental_charter_has_roles(charter_file: str):
    """Verify Supplemental charter defines roles."""
    charter_path = SUPPLEMENTAL_CHARTERS_DIR / charter_file
    source = charter_path.read_text()

    compiled = compile_charter(source)

    assert len(compiled.roles) >= 2, f"{charter_file} should define at least 2 roles"

    # Check for break_glass roles (usually legal or exec)
    break_glass_roles = [r for r in compiled.roles if r.break_glass]
    assert len(break_glass_roles) >= 1, f"{charter_file} should have at least one break_glass role"


class TestSupplementalCharterSpecifics:
    """Tests for specific Supplemental charter requirements."""

    def test_export_permission_uses_ofac(self):
        """Charter should use verify_ofac_clearance."""
        source = (SUPPLEMENTAL_CHARTERS_DIR / "export_permission.canon").read_text()
        assert "verify_ofac_clearance" in source

    def test_export_control_override_uses_ofac(self):
        """Charter should use verify_ofac_clearance."""
        source = (SUPPLEMENTAL_CHARTERS_DIR / "export_control_override.canon").read_text()
        assert "verify_ofac_clearance" in source

    def test_finance_role_uses_control_coverage(self):
        """Charter should use assess_control_coverage."""
        source = (SUPPLEMENTAL_CHARTERS_DIR / "privileged_finance_role.canon").read_text()
        assert "assess_control_coverage" in source

    def test_monitoring_removal_uses_control_coverage(self):
        """Charter should use assess_control_coverage."""
        source = (SUPPLEMENTAL_CHARTERS_DIR / "monitoring_removal.canon").read_text()
        assert "assess_control_coverage" in source

    def test_dlp_disable_uses_control_coverage(self):
        """Charter should use assess_control_coverage."""
        source = (SUPPLEMENTAL_CHARTERS_DIR / "dlp_disable.canon").read_text()
        assert "assess_control_coverage" in source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
