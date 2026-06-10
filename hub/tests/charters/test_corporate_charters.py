"""Tests for Corporate domain charter compilation.

Verifies all Corporate surface charters compile without errors.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from canon.dsl import compile_charter

# Directory containing Corporate charters
CORPORATE_CHARTERS_DIR = (
    Path(__file__).parent.parent.parent
    / "charters"
    / "surfaces"
    / "corporate"
)


# -----------------------------------------------------------------
# Parameterized test for all Corporate charters
# -----------------------------------------------------------------

CORPORATE_CHARTER_FILES = [
    "due_diligence_access.canon",
    "integration_system_link.canon",
    "carve_out_execution.canon",
    "material_change_disclosure.canon",
    "closing_condition_waiver.canon",
]


@pytest.mark.parametrize("charter_file", CORPORATE_CHARTER_FILES)
def test_corporate_charter_compiles(charter_file: str):
    """Verify Corporate charter compiles without registries (syntax + structure only)."""
    charter_path = CORPORATE_CHARTERS_DIR / charter_file

    assert charter_path.exists(), f"Charter file not found: {charter_path}"

    source = charter_path.read_text()

    # compile_charter without registries does syntax + structural validation
    # (skips feature/policy/package validation)
    compiled = compile_charter(source)

    assert compiled is not None
    assert compiled.name is not None
    assert compiled.version == "v1.0"
    assert len(compiled.workflow_names) == 1


@pytest.mark.parametrize("charter_file", CORPORATE_CHARTER_FILES)
def test_corporate_charter_has_packages(charter_file: str):
    """Verify Corporate charter declares vocabulary packages."""
    charter_path = CORPORATE_CHARTERS_DIR / charter_file
    source = charter_path.read_text()

    compiled = compile_charter(source)

    # All redesigned charters should have packages declared
    assert len(compiled.package_names) > 0, f"{charter_file} should have packages"

    # Common packages that should be present in Corporate charters
    common_packages = {
        "corporate",
        "legal",
        "authorization",
        "certification",
        "evidence",
    }
    assert common_packages.issubset(compiled.package_names), (
        f"{charter_file} should include common packages: {common_packages}"
    )


@pytest.mark.parametrize("charter_file", CORPORATE_CHARTER_FILES)
def test_corporate_charter_has_triggers(charter_file: str):
    """Verify Corporate charter has event triggers."""
    charter_path = CORPORATE_CHARTERS_DIR / charter_file
    source = charter_path.read_text()

    # Triggers are in the AST
    compiled = compile_charter(source)

    # Check that triggers are present in the AST
    assert compiled.ast.triggers is not None
    assert len(compiled.ast.triggers) >= 3, (
        f"{charter_file} should have at least 3 triggers for event-driven flow"
    )


@pytest.mark.parametrize("charter_file", CORPORATE_CHARTER_FILES)
def test_corporate_charter_phase_order(charter_file: str):
    """Verify Corporate charter phases are properly ordered."""
    charter_path = CORPORATE_CHARTERS_DIR / charter_file
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


@pytest.mark.parametrize("charter_file", CORPORATE_CHARTER_FILES)
def test_corporate_charter_has_situations(charter_file: str):
    """Verify Corporate charter has situational conditions."""
    charter_path = CORPORATE_CHARTERS_DIR / charter_file
    source = charter_path.read_text()

    compiled = compile_charter(source)

    assert len(compiled.situations) >= 1, (
        f"{charter_file} should have at least one situational condition"
    )


@pytest.mark.parametrize("charter_file", CORPORATE_CHARTER_FILES)
def test_corporate_charter_has_roles(charter_file: str):
    """Verify Corporate charter defines roles."""
    charter_path = CORPORATE_CHARTERS_DIR / charter_file
    source = charter_path.read_text()

    compiled = compile_charter(source)

    assert len(compiled.roles) >= 2, f"{charter_file} should define at least 2 roles"

    # Check for break_glass roles (usually legal or exec)
    break_glass_roles = [r for r in compiled.roles if r.break_glass]
    assert len(break_glass_roles) >= 1, f"{charter_file} should have at least one break_glass role"


class TestCorporateCharterSpecifics:
    """Tests for specific Corporate charter requirements."""

    def test_due_diligence_uses_clean_team(self):
        """Charter should use derive_clean_team_required."""
        source = (CORPORATE_CHARTERS_DIR / "due_diligence_access.canon").read_text()
        assert "derive_clean_team_required" in source

    def test_carve_out_uses_readiness(self):
        """Charter should use derive_carve_out_readiness."""
        source = (CORPORATE_CHARTERS_DIR / "carve_out_execution.canon").read_text()
        assert "derive_carve_out_readiness" in source

    def test_closing_waiver_uses_condition_status(self):
        """Charter should use derive_condition_satisfaction_status."""
        source = (CORPORATE_CHARTERS_DIR / "closing_condition_waiver.canon").read_text()
        assert "derive_condition_satisfaction_status" in source

    def test_integration_link_uses_findings_addressed(self):
        """Charter should use derive_conditional_findings_addressed."""
        source = (CORPORATE_CHARTERS_DIR / "integration_system_link.canon").read_text()
        assert "derive_conditional_findings_addressed" in source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
