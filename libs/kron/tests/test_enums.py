"""Tests for kron.types.enums -- PhraseActionType, DataClassification, DecisionClass.

Covers:
    - Enum membership and values
    - String serialization (str, Enum) compatibility
    - from_phrase_name / from_code lookup helpers
    - DecisionClass.code / .number properties
    - Exhaustive coverage of the 92 DecisionClass members
    - JSON round-trip via json.dumps/loads
"""

from __future__ import annotations

import json

from kron.types.enums import DataClassification, DecisionClass, PhraseActionType

# =============================================================================
# PhraseActionType
# =============================================================================


class TestPhraseActionType:
    """Tests for PhraseActionType enum."""

    def test_is_str_enum(self):
        """PhraseActionType members are strings."""
        assert isinstance(PhraseActionType.VERIFY, str)
        assert PhraseActionType.VERIFY == "verify"

    def test_all_members_present(self):
        """All expected action types are defined."""
        expected = {
            "verify",
            "require",
            "check",
            "certify",
            "emit",
            "record",
            "save",
            "revoke",
            "cascade",
            "grant",
            "lock",
            "create",
            "complete",
            "derive",
            "compute",
            "evaluate",
            "get",
            "find",
            "list",
            "log",
            "notify",
            "schedule",
            "trigger",
            "invoke",
            "chain",
            "mint",
        }
        actual = {m.value for m in PhraseActionType}
        assert actual == expected

    def test_member_count(self):
        """Verify total member count."""
        assert len(PhraseActionType) == 26

    def test_from_phrase_name_basic(self):
        """from_phrase_name extracts the verb prefix."""
        assert PhraseActionType.from_phrase_name("verify_consent_token") is PhraseActionType.VERIFY
        assert (
            PhraseActionType.from_phrase_name("require_active_consent") is PhraseActionType.REQUIRE
        )
        assert PhraseActionType.from_phrase_name("derive_risk_tier") is PhraseActionType.DERIVE
        assert PhraseActionType.from_phrase_name("certify_rif_decision") is PhraseActionType.CERTIFY
        assert PhraseActionType.from_phrase_name("emit_certificate") is PhraseActionType.EMIT
        assert PhraseActionType.from_phrase_name("get_case_history") is PhraseActionType.GET
        assert PhraseActionType.from_phrase_name("create_workflow_run") is PhraseActionType.CREATE
        assert (
            PhraseActionType.from_phrase_name("check_waiting_period_elapsed")
            is PhraseActionType.CHECK
        )
        assert (
            PhraseActionType.from_phrase_name("cascade_revoke_consent_token")
            is PhraseActionType.CASCADE
        )
        assert PhraseActionType.from_phrase_name("lock_criteria") is PhraseActionType.LOCK
        assert (
            PhraseActionType.from_phrase_name("compute_evidence_hash") is PhraseActionType.COMPUTE
        )
        assert PhraseActionType.from_phrase_name("chain_evidence") is PhraseActionType.CHAIN
        assert PhraseActionType.from_phrase_name("mint_certificate") is PhraseActionType.MINT

    def test_from_phrase_name_unknown(self):
        """Unknown prefixes return None."""
        assert PhraseActionType.from_phrase_name("unknown_action") is None
        assert PhraseActionType.from_phrase_name("foobar_thing") is None

    def test_from_phrase_name_no_underscore(self):
        """Single-word name without underscore."""
        assert PhraseActionType.from_phrase_name("verify") is PhraseActionType.VERIFY
        assert PhraseActionType.from_phrase_name("nope") is None

    def test_allowed_classmethod(self):
        """allowed() returns tuple of all values (inherited from Enum base)."""
        allowed = PhraseActionType.allowed()
        assert isinstance(allowed, tuple)
        assert "verify" in allowed
        assert "require" in allowed
        assert len(allowed) == 26

    def test_json_serialization(self):
        """PhraseActionType serializes to string in JSON."""
        data = {"action": PhraseActionType.VERIFY}
        serialized = json.dumps(data)
        loaded = json.loads(serialized)
        assert loaded["action"] == "verify"

    def test_string_comparison(self):
        """PhraseActionType can be compared with plain strings."""
        assert PhraseActionType.VERIFY == "verify"
        assert PhraseActionType.REQUIRE != "verify"


# =============================================================================
# DataClassification
# =============================================================================


class TestDataClassification:
    """Tests for DataClassification enum."""

    def test_is_str_enum(self):
        """DataClassification members are strings."""
        assert isinstance(DataClassification.PII, str)
        assert DataClassification.PII == "pii"

    def test_all_members_present(self):
        """All expected classifications are defined."""
        expected = {
            "pii",
            "sensitive",
            "protected",
            "bgc",
            "comp",
            "medical",
            "public",
            "internal",
            "confidential",
        }
        actual = {m.value for m in DataClassification}
        assert actual == expected

    def test_member_count(self):
        """Verify total member count."""
        assert len(DataClassification) == 9

    def test_json_serialization(self):
        """DataClassification serializes to string in JSON."""
        data = {"classification": DataClassification.BGC}
        serialized = json.dumps(data)
        loaded = json.loads(serialized)
        assert loaded["classification"] == "bgc"

    def test_string_comparison(self):
        """DataClassification can be compared with plain strings."""
        assert DataClassification.MEDICAL == "medical"
        assert DataClassification.PUBLIC != "confidential"


# =============================================================================
# DecisionClass
# =============================================================================


class TestDecisionClass:
    """Tests for DecisionClass enum."""

    def test_is_str_enum(self):
        """DecisionClass members are strings."""
        assert isinstance(DecisionClass.LAYOFF_RIF_INCLUSION, str)
        assert DecisionClass.LAYOFF_RIF_INCLUSION == "layoff_rif_inclusion"

    def test_values_are_slugs(self):
        """Every value is the snake_case form of its member name."""
        for m in DecisionClass:
            assert m.value == m.name.lower()

    def test_values_unique(self):
        """No duplicate identifiers."""
        codes = [m.value for m in DecisionClass]
        assert len(codes) == len(set(codes))

    def test_code_property(self):
        """code property returns the identifier value."""
        assert DecisionClass.LAYOFF_RIF_INCLUSION.code == "layoff_rif_inclusion"
        assert DecisionClass.LEGAL_DATA_RELEASE.code == "legal_data_release"

    def test_from_code_valid(self):
        """from_code finds valid identifiers."""
        assert DecisionClass.from_code("layoff_rif_inclusion") is DecisionClass.LAYOFF_RIF_INCLUSION
        assert DecisionClass.from_code("legal_data_release") is DecisionClass.LEGAL_DATA_RELEASE
        assert DecisionClass.from_code("security_tool_bypass") is DecisionClass.SECURITY_TOOL_BYPASS

    def test_from_code_invalid(self):
        """from_code returns None for invalid codes."""
        assert DecisionClass.from_code("unknown_surface") is None
        assert DecisionClass.from_code("INVALID") is None

    def test_json_serialization(self):
        """DecisionClass serializes to its identifier string in JSON."""
        data = {"decision_class": DecisionClass.BREAK_GLASS}
        serialized = json.dumps(data)
        loaded = json.loads(serialized)
        assert loaded["decision_class"] == "break_glass"

    def test_string_comparison(self):
        """DecisionClass can be compared with plain strings."""
        assert DecisionClass.LEGAL_HOLD == "legal_hold"
        assert DecisionClass.DATA_SHARING != "legal_hold"

    # --- Domain spot checks ---

    def test_hr_members_present(self):
        """HR decision classes are defined."""
        members = [
            DecisionClass.LAYOFF_RIF_INCLUSION,
            DecisionClass.CONTESTED_RESIGNATION,
            DecisionClass.EXIT_INTERVIEW_DISCLOSURE,
            DecisionClass.REHIRE_ELIGIBILITY_OVERRIDE,
            DecisionClass.PROMOTION_WITHOUT_POSTING,
            DecisionClass.SALARY_BAND_EXCEPTION,
            DecisionClass.REMOTE_WORK_REVOCATION,
            DecisionClass.VISA_SPONSORSHIP_TERMINATION,
            DecisionClass.SEVERANCE_AGREEMENT_EXECUTION,
        ]
        for member in members:
            assert member.code == member.name.lower()

    def test_identity_members_present(self):
        """Identity decision classes are defined."""
        members = [
            DecisionClass.MFA_EXEMPTION,
            DecisionClass.SSO_BYPASS,
            DecisionClass.EMERGENCY_ACCOUNT,
            DecisionClass.BREAK_GLASS,
            DecisionClass.BIOMETRIC_BYPASS,
        ]
        for member in members:
            assert member.code == member.name.lower()

    def test_ai_members_present(self):
        """AI decision classes are defined."""
        members = [
            DecisionClass.MODEL_DEPLOYMENT_OVERRIDE,
            DecisionClass.TRAINING_DATA_INCLUSION,
            DecisionClass.BIAS_ASSESSMENT_WAIVER,
            DecisionClass.HUMAN_REVIEW_BYPASS,
            DecisionClass.AGENT_AUTONOMY_GRANT,
            DecisionClass.MODEL_RETIREMENT_OVERRIDE,
            DecisionClass.AI_INCIDENT_DISCLOSURE,
        ]
        assert len(members) == 7
        for member in members:
            assert member.code == member.name.lower()

    def test_supplemental_members_present(self):
        """Supplemental decision classes are defined."""
        members = [
            DecisionClass.PRIVILEGED_FINANCE_ROLE,
            DecisionClass.MONITORING_REMOVAL,
            DecisionClass.DLP_DISABLE,
            DecisionClass.EXPORT_PERMISSION,
            DecisionClass.ETHICS_CASE_CLOSURE,
            DecisionClass.REINSTATE_ACCESS,
            DecisionClass.EXPORT_CONTROL_OVERRIDE,
            DecisionClass.DISABLE_AUDIT_LOGGING,
            DecisionClass.LEGAL_DATA_RELEASE,
        ]
        assert len(members) == 9
        for member in members:
            assert member.code == member.name.lower()

    def test_core_members_spot_check(self):
        """Spot-check identifiers of frequently used members."""
        assert DecisionClass.PRIVILEGED_ROLE_ESCALATION.code == "privileged_role_escalation"
        assert DecisionClass.CREDENTIAL_ISSUANCE.code == "credential_issuance"
        assert DecisionClass.DESTRUCTIVE_MIGRATION.code == "destructive_migration"
        assert DecisionClass.FORCED_FAILOVER.code == "forced_failover"
        assert DecisionClass.DATA_SHARING.code == "data_sharing"
        assert DecisionClass.LEGAL_HOLD.code == "legal_hold"
        assert DecisionClass.WIRE_TRANSFER.code == "wire_transfer"
        assert DecisionClass.INCIDENT_CLOSURE.code == "incident_closure"


# =============================================================================
# Import path tests
# =============================================================================


class TestImportPaths:
    """Verify enums are importable from canonical locations."""

    def test_import_from_kron_types(self):
        """Enums are importable from kron.types."""
        from kron.types import (
            DataClassification as DC,
            DecisionClass as DClass,
            PhraseActionType as PAT,
        )

        assert PAT.VERIFY == "verify"
        assert DC.PII == "pii"
        assert DClass.LAYOFF_RIF_INCLUSION == "layoff_rif_inclusion"

    def test_import_from_kron_types_enums(self):
        """Enums are importable from kron.types.enums."""
        from kron.types.enums import DataClassification, DecisionClass, PhraseActionType

        assert PhraseActionType.REQUIRE == "require"
        assert DataClassification.BGC == "bgc"
        assert DecisionClass.BREAK_GLASS == "break_glass"
