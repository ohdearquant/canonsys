"""Tests for Legal domain charter compilation.

Verifies all Legal surface charters compile without errors.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from canon.dsl import compile_charter

# Directory containing Legal charters
LEGAL_CHARTERS_DIR = (
    Path(__file__).parent.parent.parent / "charters" / "surfaces" / "legal"
)


# -----------------------------------------------------------------
# Parameterized test for all Legal charters
# -----------------------------------------------------------------

LEGAL_CHARTER_FILES = [
    "cs_008_legal_hold.canon",
    "cs_065_litigation_hold_release.canon",
    "cs_066_privilege_waiver.canon",
    "cs_067_settlement_authority.canon",
    "cs_068_regulatory_disclosure.canon",
    "cs_069_contract_amendment.canon",
    "cs_070_ip_assignment.canon",
    "cs_071_indemnification_waiver.canon",
]


@pytest.mark.parametrize("charter_file", LEGAL_CHARTER_FILES)
def test_legal_charter_compiles(charter_file: str):
    """Verify Legal charter compiles without registries (syntax + structure only)."""
    charter_path = LEGAL_CHARTERS_DIR / charter_file

    assert charter_path.exists(), f"Charter file not found: {charter_path}"

    source = charter_path.read_text()

    # compile_charter without registries does syntax + structural validation
    # (skips feature/policy/package validation)
    compiled = compile_charter(source)

    assert compiled is not None
    assert compiled.name is not None
    assert compiled.version == "v1.0"
    assert len(compiled.workflow_names) == 1


@pytest.mark.parametrize("charter_file", LEGAL_CHARTER_FILES)
def test_legal_charter_has_packages(charter_file: str):
    """Verify Legal charter declares vocabulary packages."""
    charter_path = LEGAL_CHARTERS_DIR / charter_file
    source = charter_path.read_text()

    compiled = compile_charter(source)

    # All redesigned charters should have packages declared
    assert len(compiled.package_names) > 0, f"{charter_file} should have packages"

    # Common packages that should be present in Legal charters
    common_packages = {"legal", "authorization", "certification", "evidence", "policy"}
    assert common_packages.issubset(compiled.package_names), (
        f"{charter_file} should include common packages: {common_packages}"
    )


@pytest.mark.parametrize("charter_file", LEGAL_CHARTER_FILES)
def test_legal_charter_has_triggers(charter_file: str):
    """Verify Legal charter has event triggers."""
    charter_path = LEGAL_CHARTERS_DIR / charter_file
    source = charter_path.read_text()

    # Triggers are in the AST
    compiled = compile_charter(source)

    # Check that triggers are present in the AST
    assert compiled.ast.triggers is not None
    assert len(compiled.ast.triggers) >= 3, (
        f"{charter_file} should have at least 3 triggers for event-driven flow"
    )


@pytest.mark.parametrize("charter_file", LEGAL_CHARTER_FILES)
def test_legal_charter_has_phases(charter_file: str):
    """Verify Legal charter has proper phases."""
    charter_path = LEGAL_CHARTERS_DIR / charter_file
    source = charter_path.read_text()

    compiled = compile_charter(source)

    workflow_name = compiled.workflow_names[0]
    phase_order = compiled.phase_order[workflow_name]

    # All charters should have multiple phases
    assert len(phase_order) >= 4, f"{charter_file} should have at least 4 phases"


@pytest.mark.parametrize("charter_file", LEGAL_CHARTER_FILES)
def test_legal_charter_has_situations(charter_file: str):
    """Verify Legal charter has situational conditions."""
    charter_path = LEGAL_CHARTERS_DIR / charter_file
    source = charter_path.read_text()

    compiled = compile_charter(source)

    assert len(compiled.situations) >= 1, (
        f"{charter_file} should have at least one situational condition"
    )


@pytest.mark.parametrize("charter_file", LEGAL_CHARTER_FILES)
def test_legal_charter_has_roles(charter_file: str):
    """Verify Legal charter defines roles."""
    charter_path = LEGAL_CHARTERS_DIR / charter_file
    source = charter_path.read_text()

    compiled = compile_charter(source)

    assert len(compiled.roles) >= 2, f"{charter_file} should define at least 2 roles"

    # Check for break_glass roles (usually GC)
    break_glass_roles = [r for r in compiled.roles if r.break_glass]
    assert len(break_glass_roles) >= 1, f"{charter_file} should have at least one break_glass role"


@pytest.mark.parametrize("charter_file", LEGAL_CHARTER_FILES)
def test_legal_charter_has_certification_phase(charter_file: str):
    """Verify Legal charter ends with certification phase."""
    charter_path = LEGAL_CHARTERS_DIR / charter_file
    source = charter_path.read_text()

    compiled = compile_charter(source)

    workflow_name = compiled.workflow_names[0]
    phase_order = compiled.phase_order[workflow_name]

    # Last phase should be certification
    assert phase_order[-1] == "certification", (
        f"{charter_file} last phase should be 'certification'"
    )


class TestSpecificLegalCharters:
    """Tests for specific legal charter requirements."""

    def test_legal_hold_has_hold_events(self):
        """CS-008 Legal Hold should have hold-related triggers."""
        source = (LEGAL_CHARTERS_DIR / "cs_008_legal_hold.canon").read_text()
        compiled = compile_charter(source)

        trigger_names = {t.name for t in compiled.ast.triggers}
        assert "hold_requested" in trigger_names
        assert "hold_activated" in trigger_names

    def test_litigation_hold_release_has_release_events(self):
        """CS-065 Litigation Hold Release should have release triggers."""
        source = (LEGAL_CHARTERS_DIR / "cs_065_litigation_hold_release.canon").read_text()
        compiled = compile_charter(source)

        trigger_names = {t.name for t in compiled.ast.triggers}
        assert "release_requested" in trigger_names
        assert "litigation_resolved" in trigger_names
        assert "release_executed" in trigger_names

    def test_privilege_waiver_has_gc_authorization(self):
        """CS-066 Privilege Waiver should have GC authorization trigger."""
        source = (LEGAL_CHARTERS_DIR / "cs_066_privilege_waiver.canon").read_text()
        compiled = compile_charter(source)

        trigger_names = {t.name for t in compiled.ast.triggers}
        assert "gc_authorized" in trigger_names
        assert "waiver_executed" in trigger_names

    def test_settlement_authority_has_board_process(self):
        """CS-067 Settlement Authority should have board process trigger."""
        source = (LEGAL_CHARTERS_DIR / "cs_067_settlement_authority.canon").read_text()
        compiled = compile_charter(source)

        trigger_names = {t.name for t in compiled.ast.triggers}
        assert "board_notified" in trigger_names
        assert "settlement_executed" in trigger_names

    def test_regulatory_disclosure_has_gc_authorization(self):
        """CS-068 Regulatory Disclosure should have GC authorization."""
        source = (LEGAL_CHARTERS_DIR / "cs_068_regulatory_disclosure.canon").read_text()
        compiled = compile_charter(source)

        trigger_names = {t.name for t in compiled.ast.triggers}
        assert "gc_authorized" in trigger_names
        assert "disclosure_transmitted" in trigger_names

    def test_regulatory_disclosure_has_data_protection_package(self):
        """CS-068 Regulatory Disclosure should use data_protection package for PII."""
        source = (LEGAL_CHARTERS_DIR / "cs_068_regulatory_disclosure.canon").read_text()
        compiled = compile_charter(source)
        assert "data_protection" in compiled.package_names

    def test_contract_amendment_has_financial_analysis(self):
        """CS-069 Contract Amendment should have financial analysis trigger."""
        source = (LEGAL_CHARTERS_DIR / "cs_069_contract_amendment.canon").read_text()
        compiled = compile_charter(source)

        trigger_names = {t.name for t in compiled.ast.triggers}
        assert "financial_analysis_completed" in trigger_names
        assert "amendment_executed" in trigger_names

    def test_ip_assignment_has_strategic_phases(self):
        """CS-070 IP Assignment should have valuation and strategic phases."""
        source = (LEGAL_CHARTERS_DIR / "cs_070_ip_assignment.canon").read_text()
        compiled = compile_charter(source)

        workflow_name = compiled.workflow_names[0]
        phase_order = compiled.phase_order[workflow_name]

        assert "valuation" in phase_order
        assert "strategic_classification" in phase_order

    def test_indemnification_waiver_has_exposure_analysis(self):
        """CS-071 Indemnification Waiver should have exposure analysis."""
        source = (LEGAL_CHARTERS_DIR / "cs_071_indemnification_waiver.canon").read_text()
        compiled = compile_charter(source)

        workflow_name = compiled.workflow_names[0]
        phase_order = compiled.phase_order[workflow_name]

        assert "exposure_analysis" in phase_order
        assert "insurance_review" in phase_order


class TestLegalCharterDSLFeatures:
    """Test specific DSL features used in legal charters."""

    @pytest.mark.parametrize("charter_file", LEGAL_CHARTER_FILES)
    def test_legal_charter_uses_inline_when_blocks(self, charter_file: str):
        """Legal charters should use inline when blocks for conditional logic."""
        charter_path = LEGAL_CHARTERS_DIR / charter_file
        source = charter_path.read_text()

        # Check for inline when blocks within phases
        assert "when " in source, f"{charter_file} should have inline when blocks"

    @pytest.mark.parametrize("charter_file", LEGAL_CHARTER_FILES)
    def test_legal_charter_uses_await(self, charter_file: str):
        """Legal charters should use await for event-driven flow."""
        charter_path = LEGAL_CHARTERS_DIR / charter_file
        source = charter_path.read_text()

        # Check for await statements
        assert "await " in source, f"{charter_file} should have await statements"

    @pytest.mark.parametrize("charter_file", LEGAL_CHARTER_FILES)
    def test_legal_charter_uses_legal_phrases(self, charter_file: str):
        """Legal charters should use legal package phrases."""
        charter_path = LEGAL_CHARTERS_DIR / charter_file
        source = charter_path.read_text()

        # Check for legal package phrases
        legal_phrases = [
            "require_legal_review_complete",
            "verify_privileged_review_complete",
            "require_nda_valid",
            "lock_criteria",
            "verify_gc_approval",
        ]

        used_phrases = [p for p in legal_phrases if p in source]
        assert len(used_phrases) >= 2, f"{charter_file} should use at least 2 legal package phrases"

    @pytest.mark.parametrize("charter_file", LEGAL_CHARTER_FILES)
    def test_legal_charter_has_immutable_certification(self, charter_file: str):
        """Legal charters should have immutable certification."""
        charter_path = LEGAL_CHARTERS_DIR / charter_file
        source = charter_path.read_text()

        assert "certify immutable" in source, f"{charter_file} should have immutable certification"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
