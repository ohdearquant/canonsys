"""Tests for AI domain charter compilation.

Verifies all AI surface charters compile without errors.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from canon.dsl import compile_charter

# Directory containing AI charters
AI_CHARTERS_DIR = (
    Path(__file__).parent.parent.parent / "charters" / "surfaces" / "ai"
)


# -----------------------------------------------------------------
# Parameterized test for all AI charters
# -----------------------------------------------------------------

AI_CHARTER_FILES = [
    "cs_072_model_deployment_override.canon",
    "cs_073_training_data_inclusion.canon",
    "cs_074_bias_assessment_waiver.canon",
    "cs_075_human_review_bypass.canon",
    "cs_076_agent_autonomy_grant.canon",
    "cs_077_model_retirement_override.canon",
    "cs_078_ai_incident_disclosure.canon",
]


@pytest.mark.parametrize("charter_file", AI_CHARTER_FILES)
def test_ai_charter_compiles(charter_file: str):
    """Verify AI charter compiles without registries (syntax + structure only)."""
    charter_path = AI_CHARTERS_DIR / charter_file

    assert charter_path.exists(), f"Charter file not found: {charter_path}"

    source = charter_path.read_text()

    # compile_charter without registries does syntax + structural validation
    # (skips feature/policy/package validation)
    compiled = compile_charter(source)

    assert compiled is not None
    assert compiled.name is not None
    assert compiled.version == "v1.0"
    assert len(compiled.workflow_names) == 1


@pytest.mark.parametrize("charter_file", AI_CHARTER_FILES)
def test_ai_charter_has_packages(charter_file: str):
    """Verify AI charter declares vocabulary packages."""
    charter_path = AI_CHARTERS_DIR / charter_file
    source = charter_path.read_text()

    compiled = compile_charter(source)

    # All redesigned charters should have packages declared
    assert len(compiled.package_names) > 0, f"{charter_file} should have packages"

    # Common packages that should be present in AI charters
    common_packages = {
        "ai_governance",
        "authorization",
        "certification",
        "evidence",
        "policy",
    }
    assert common_packages.issubset(compiled.package_names), (
        f"{charter_file} should include common packages: {common_packages}"
    )


@pytest.mark.parametrize("charter_file", AI_CHARTER_FILES)
def test_ai_charter_has_triggers(charter_file: str):
    """Verify AI charter has event triggers."""
    charter_path = AI_CHARTERS_DIR / charter_file
    source = charter_path.read_text()

    # Triggers are in the AST
    compiled = compile_charter(source)

    # Check that triggers are present in the AST
    assert compiled.ast.triggers is not None
    assert len(compiled.ast.triggers) >= 3, (
        f"{charter_file} should have at least 3 triggers for event-driven flow"
    )


@pytest.mark.parametrize("charter_file", AI_CHARTER_FILES)
def test_ai_charter_phase_order(charter_file: str):
    """Verify AI charter phases are properly ordered."""
    charter_path = AI_CHARTERS_DIR / charter_file
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


@pytest.mark.parametrize("charter_file", AI_CHARTER_FILES)
def test_ai_charter_has_situations(charter_file: str):
    """Verify AI charter has situational conditions."""
    charter_path = AI_CHARTERS_DIR / charter_file
    source = charter_path.read_text()

    compiled = compile_charter(source)

    assert len(compiled.situations) >= 1, (
        f"{charter_file} should have at least one situational condition"
    )


@pytest.mark.parametrize("charter_file", AI_CHARTER_FILES)
def test_ai_charter_has_roles(charter_file: str):
    """Verify AI charter defines roles."""
    charter_path = AI_CHARTERS_DIR / charter_file
    source = charter_path.read_text()

    compiled = compile_charter(source)

    assert len(compiled.roles) >= 2, f"{charter_file} should define at least 2 roles"

    # Check for break_glass roles (usually legal or exec)
    break_glass_roles = [r for r in compiled.roles if r.break_glass]
    assert len(break_glass_roles) >= 1, f"{charter_file} should have at least one break_glass role"


class TestAICharterSpecifics:
    """Tests for specific AI charter requirements."""

    def test_model_deployment_override_uses_bias_assessment(self):
        """CS-072 should use require_bias_assessment_documented."""
        source = (AI_CHARTERS_DIR / "cs_072_model_deployment_override.canon").read_text()
        assert "require_bias_assessment_documented" in source

    def test_human_review_bypass_uses_human_review_present(self):
        """CS-075 should use require_human_review_present."""
        source = (AI_CHARTERS_DIR / "cs_075_human_review_bypass.canon").read_text()
        assert "require_human_review_present" in source

    def test_bias_waiver_uses_ai_governance(self):
        """CS-074 should use ai_governance package."""
        source = (AI_CHARTERS_DIR / "cs_074_bias_assessment_waiver.canon").read_text()
        compiled = compile_charter(source)
        assert "ai_governance" in compiled.package_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
