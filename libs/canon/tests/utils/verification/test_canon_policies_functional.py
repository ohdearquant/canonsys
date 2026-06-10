"""Functional tests for Canon policy rego files.

These tests load and evaluate ACTUAL Canon policy rego files using
regorus, validating real compliance policy behavior.

Test coverage includes:
- NY WARN Act notice requirements for PIP-to-termination
- Whistleblower retaliation protection
- Input validation (fail-closed behavior)
- Applicability determination
- Violation and remediation generation
- Unified decision contract validation
"""


from __future__ import annotations

import pytest

pytest.importorskip("regorus")


import json
from pathlib import Path

import pytest

from canon.utils.opa.engine import EnginePool

# Paths to Canon policy rego files
# Path: canon/tests/utils/verification/test_canon_policies_functional.py
# Go up 5 levels to canonsys root, then into hub/policies
REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent
POLICY_DIR = REPO_ROOT / "hub" / "policies"
NY_WARN_POLICY = (
    POLICY_DIR / "jurisdictions" / "new_york" / "policies" / "pip" / "ny_warn_notice.rego"
)
WHISTLEBLOWER_POLICY = (
    POLICY_DIR / "jurisdictions" / "new_york" / "policies" / "pip" / "whistleblower_protection.rego"
)


def evaluate_policy(pool: EnginePool, query: str, input_data: dict) -> dict:
    """Helper to evaluate a policy query against input data.

    Uses the checkout pattern to get a raw regorus engine.
    Uses set_input_json to preserve boolean types (regorus set_input
    converts Python booleans to numbers which breaks Rego comparisons).
    """
    with pool.checkout() as engine:
        # Use set_input_json to preserve boolean types
        engine.set_input_json(json.dumps(input_data))
        result = engine.eval_rule(query)
        return result


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def ny_warn_pool():
    """Create EnginePool with NY WARN policy loaded."""
    if not NY_WARN_POLICY.exists():
        pytest.skip(f"Policy file not found: {NY_WARN_POLICY}")

    pool = EnginePool(size=1)
    pool.initialize()

    rego_content = NY_WARN_POLICY.read_text()
    pool.add_policy("ny_warn_notice.rego", rego_content)

    return pool


@pytest.fixture
def whistleblower_pool():
    """Create EnginePool with whistleblower policy loaded."""
    if not WHISTLEBLOWER_POLICY.exists():
        pytest.skip(f"Policy file not found: {WHISTLEBLOWER_POLICY}")

    pool = EnginePool(size=1)
    pool.initialize()

    rego_content = WHISTLEBLOWER_POLICY.read_text()
    pool.add_policy("whistleblower_protection.rego", rego_content)

    return pool


# =============================================================================
# NY WARN Notice - Valid Scenarios
# =============================================================================


class TestNYWARNNoticeValid:
    """Test NY WARN notice compliance when all requirements met."""

    def test_warn_notice_satisfied_allows(self, ny_warn_pool) -> None:
        """Proper WARN notice (90 days, all recipients) allows termination."""
        result = evaluate_policy(
            ny_warn_pool,
            "data.canonsys.statutory.us_ny.warn.pip_termination.decision",
            {
                "ctx": {
                    "action": "certify_outcome",
                    "jurisdictions": ["US-NY"],
                },
                "evidence": {
                    "warn_notice": {
                        "filed": True,
                        "affected_employees_notified": True,
                        "ny_dol_notified": True,
                        "lwdb_notified": True,
                        "local_officials_notified": True,
                    },
                },
                "facts": {
                    "employer_fulltime_employee_count": 100,
                    "part_of_rif": True,
                    "rif_affected_count": 50,
                    "site_fulltime_employee_count": 100,
                },
                "derived": {
                    "calendar_days_notice_given": 90,
                },
            },
        )
        assert result["allow"] is True
        assert result["status"] == "allow"

    def test_decision_has_policy_metadata(self, ny_warn_pool) -> None:
        """Decision includes policy metadata for audit."""
        result = evaluate_policy(
            ny_warn_pool,
            "data.canonsys.statutory.us_ny.warn.pip_termination.decision",
            {
                "ctx": {"action": "certify_outcome", "jurisdictions": ["US-NY"]},
                "evidence": {
                    "warn_notice": {
                        "filed": True,
                        "affected_employees_notified": True,
                        "ny_dol_notified": True,
                        "lwdb_notified": True,
                        "local_officials_notified": True,
                    },
                },
                "facts": {
                    "employer_fulltime_employee_count": 100,
                    "part_of_rif": True,
                    "rif_affected_count": 50,
                    "site_fulltime_employee_count": 100,
                },
                "derived": {"calendar_days_notice_given": 90},
            },
        )
        assert "policy" in result
        assert result["policy"]["policy_id"] == "ny_warn_pip_termination"
        assert result["policy"]["authority"] == "STATUTORY"

    def test_exactly_90_days_allows(self, ny_warn_pool) -> None:
        """Exactly 90 calendar days notice is sufficient."""
        result = evaluate_policy(
            ny_warn_pool,
            "data.canonsys.statutory.us_ny.warn.pip_termination.decision",
            {
                "ctx": {"action": "certify_outcome", "jurisdictions": ["US-NY"]},
                "evidence": {
                    "warn_notice": {
                        "filed": True,
                        "affected_employees_notified": True,
                        "ny_dol_notified": True,
                        "lwdb_notified": True,
                        "local_officials_notified": True,
                    },
                },
                "facts": {
                    "employer_fulltime_employee_count": 50,
                    "part_of_rif": True,
                    "rif_affected_count": 250,
                    "site_fulltime_employee_count": 500,
                },
                "derived": {"calendar_days_notice_given": 90},
            },
        )
        assert result["allow"] is True


# =============================================================================
# NY WARN Notice - Violations
# =============================================================================


class TestNYWARNNoticeViolations:
    """Test NY WARN notice violations when requirements not met."""

    def test_insufficient_notice_blocks(self, ny_warn_pool) -> None:
        """Less than 90 days notice blocks termination."""
        result = evaluate_policy(
            ny_warn_pool,
            "data.canonsys.statutory.us_ny.warn.pip_termination.decision",
            {
                "ctx": {"action": "certify_outcome", "jurisdictions": ["US-NY"]},
                "evidence": {
                    "warn_notice": {
                        "filed": True,
                        "affected_employees_notified": True,
                        "ny_dol_notified": True,
                        "lwdb_notified": True,
                        "local_officials_notified": True,
                    },
                },
                "facts": {
                    "employer_fulltime_employee_count": 100,
                    "part_of_rif": True,
                    "rif_affected_count": 50,
                    "site_fulltime_employee_count": 100,
                },
                "derived": {"calendar_days_notice_given": 60},  # Only 60 days
            },
        )
        assert result["allow"] is False
        assert result["status"] == "deny"

    def test_violation_has_correct_code(self, ny_warn_pool) -> None:
        """Violation includes correct code for tracking."""
        result = evaluate_policy(
            ny_warn_pool,
            "data.canonsys.statutory.us_ny.warn.pip_termination.decision",
            {
                "ctx": {"action": "certify_outcome", "jurisdictions": ["US-NY"]},
                "evidence": {"warn_notice": None},
                "facts": {
                    "employer_fulltime_employee_count": 100,
                    "part_of_rif": True,
                    "rif_affected_count": 50,
                    "site_fulltime_employee_count": 100,
                },
                "derived": {"calendar_days_notice_given": 0},
            },
        )
        assert result["violation"]["code"] == "NY_WARN_NOTICE_REQUIRED"

    def test_remediation_provided(self, ny_warn_pool) -> None:
        """Remediation steps provided when violation occurs."""
        result = evaluate_policy(
            ny_warn_pool,
            "data.canonsys.statutory.us_ny.warn.pip_termination.decision",
            {
                "ctx": {"action": "certify_outcome", "jurisdictions": ["US-NY"]},
                "evidence": {"warn_notice": None},
                "facts": {
                    "employer_fulltime_employee_count": 100,
                    "part_of_rif": True,
                    "rif_affected_count": 50,
                    "site_fulltime_employee_count": 100,
                },
                "derived": {"calendar_days_notice_given": 0},
            },
        )
        assert result["remediation"] is not None
        assert len(result["remediation"]) > 0
        assert any("90 calendar days" in r for r in result["remediation"])

    def test_missing_recipient_blocks(self, ny_warn_pool) -> None:
        """Missing NY DOL notification blocks termination."""
        result = evaluate_policy(
            ny_warn_pool,
            "data.canonsys.statutory.us_ny.warn.pip_termination.decision",
            {
                "ctx": {"action": "certify_outcome", "jurisdictions": ["US-NY"]},
                "evidence": {
                    "warn_notice": {
                        "filed": True,
                        "affected_employees_notified": True,
                        "ny_dol_notified": False,  # Missing!
                        "lwdb_notified": True,
                        "local_officials_notified": True,
                    },
                },
                "facts": {
                    "employer_fulltime_employee_count": 100,
                    "part_of_rif": True,
                    "rif_affected_count": 50,
                    "site_fulltime_employee_count": 100,
                },
                "derived": {"calendar_days_notice_given": 90},
            },
        )
        assert result["allow"] is False


# =============================================================================
# NY WARN Notice - Applicability
# =============================================================================


class TestNYWARNApplicability:
    """Test NY WARN applicability determination."""

    def test_not_applicable_for_non_ny_jurisdiction(self, ny_warn_pool) -> None:
        """Policy skips for non-NY jurisdictions."""
        result = evaluate_policy(
            ny_warn_pool,
            "data.canonsys.statutory.us_ny.warn.pip_termination.decision",
            {
                "ctx": {"action": "certify_outcome", "jurisdictions": ["US-CA"]},
                "evidence": {},
                "facts": {
                    "employer_fulltime_employee_count": 100,
                    "part_of_rif": True,
                    "rif_affected_count": 50,
                    "site_fulltime_employee_count": 100,
                },
                "derived": {},
            },
        )
        assert result["applicable"] is False
        assert result["status"] == "skip"

    def test_not_applicable_for_small_employer(self, ny_warn_pool) -> None:
        """Policy skips for employers under 50 employees."""
        result = evaluate_policy(
            ny_warn_pool,
            "data.canonsys.statutory.us_ny.warn.pip_termination.decision",
            {
                "ctx": {"action": "certify_outcome", "jurisdictions": ["US-NY"]},
                "evidence": {},
                "facts": {
                    "employer_fulltime_employee_count": 40,  # Under threshold
                    "part_of_rif": True,
                    "rif_affected_count": 10,
                    "site_fulltime_employee_count": 40,
                },
                "derived": {},
            },
        )
        assert result["applicable"] is False
        assert result["status"] == "skip"

    def test_not_applicable_when_not_part_of_rif(self, ny_warn_pool) -> None:
        """Policy skips when termination is not part of RIF."""
        result = evaluate_policy(
            ny_warn_pool,
            "data.canonsys.statutory.us_ny.warn.pip_termination.decision",
            {
                "ctx": {"action": "certify_outcome", "jurisdictions": ["US-NY"]},
                "evidence": {},
                "facts": {
                    "employer_fulltime_employee_count": 100,
                    "part_of_rif": False,  # Not part of RIF
                    "rif_affected_count": 0,
                    "site_fulltime_employee_count": 100,
                },
                "derived": {},
            },
        )
        assert result["applicable"] is False


# =============================================================================
# NY WARN Notice - Input Validation
# =============================================================================


class TestNYWARNInputValidation:
    """Test fail-closed input validation."""

    def test_missing_ctx_causes_error(self, ny_warn_pool) -> None:
        """Missing ctx field results in error status."""
        result = evaluate_policy(
            ny_warn_pool,
            "data.canonsys.statutory.us_ny.warn.pip_termination.decision",
            {
                # No ctx field
                "evidence": {},
                "facts": {},
                "derived": {},
            },
        )
        assert result["status"] == "error"
        assert result["allow"] is False
        assert result["violation"]["code"] == "INPUT_INVALID"

    def test_malformed_input_causes_error(self, ny_warn_pool) -> None:
        """Malformed input results in error status."""
        result = evaluate_policy(
            ny_warn_pool,
            "data.canonsys.statutory.us_ny.warn.pip_termination.decision",
            {
                "ctx": "not_an_object",  # Should be object
                "evidence": {},
                "facts": {},
                "derived": {},
            },
        )
        assert result["status"] == "error"


# =============================================================================
# Decision Contract Validation
# =============================================================================


class TestDecisionContract:
    """Test unified decision contract format."""

    def test_decision_has_all_required_fields(self, ny_warn_pool) -> None:
        """Decision includes all contract-required fields."""
        result = evaluate_policy(
            ny_warn_pool,
            "data.canonsys.statutory.us_ny.warn.pip_termination.decision",
            {
                "ctx": {"action": "certify_outcome", "jurisdictions": ["US-NY"]},
                "evidence": {
                    "warn_notice": {
                        "filed": True,
                        "affected_employees_notified": True,
                        "ny_dol_notified": True,
                        "lwdb_notified": True,
                        "local_officials_notified": True,
                    },
                },
                "facts": {
                    "employer_fulltime_employee_count": 100,
                    "part_of_rif": True,
                    "rif_affected_count": 50,
                    "site_fulltime_employee_count": 100,
                },
                "derived": {"calendar_days_notice_given": 90},
            },
        )

        # Required fields per contract
        assert "allow" in result
        assert "applicable" in result
        assert "status" in result
        assert "violation" in result
        assert "remediation" in result
        assert "conditions" in result
        assert "policy" in result
        assert "contract_version" in result

    def test_conditions_tracking_when_allowed(self, ny_warn_pool) -> None:
        """Conditions tracking shows met requirements."""
        result = evaluate_policy(
            ny_warn_pool,
            "data.canonsys.statutory.us_ny.warn.pip_termination.decision",
            {
                "ctx": {"action": "certify_outcome", "jurisdictions": ["US-NY"]},
                "evidence": {
                    "warn_notice": {
                        "filed": True,
                        "affected_employees_notified": True,
                        "ny_dol_notified": True,
                        "lwdb_notified": True,
                        "local_officials_notified": True,
                    },
                },
                "facts": {
                    "employer_fulltime_employee_count": 100,
                    "part_of_rif": True,
                    "rif_affected_count": 50,
                    "site_fulltime_employee_count": 100,
                },
                "derived": {"calendar_days_notice_given": 90},
            },
        )
        conditions = result["conditions"]
        assert "met" in conditions
        assert "missing" in conditions
        assert "warn_notice_filed" in conditions["met"]
        assert len(conditions["missing"]) == 0
