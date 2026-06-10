"""Tests for UCS OPA data provider.

Validates that UCSDataProvider builds data structures matching
ucs_validator.rego expectations.
"""

from __future__ import annotations

from datetime import UTC, datetime

from canon.utils.verification.opa_data_provider import DEFAULT_ROLES, UCSDataProvider


class TestDefaultRoles:
    """Verify DEFAULT_ROLES has expected workflow types."""

    def test_has_termination_decision(self) -> None:
        """TERMINATION_DECISION workflow type exists."""
        assert "TERMINATION_DECISION" in DEFAULT_ROLES
        assert isinstance(DEFAULT_ROLES["TERMINATION_DECISION"], list)
        assert len(DEFAULT_ROLES["TERMINATION_DECISION"]) > 0

    def test_has_investigation_close(self) -> None:
        """INVESTIGATION_CLOSE workflow type exists."""
        assert "INVESTIGATION_CLOSE" in DEFAULT_ROLES
        assert isinstance(DEFAULT_ROLES["INVESTIGATION_CLOSE"], list)
        assert len(DEFAULT_ROLES["INVESTIGATION_CLOSE"]) > 0

    def test_has_pip_fail(self) -> None:
        """PIP_FAIL workflow type exists."""
        assert "PIP_FAIL" in DEFAULT_ROLES
        assert isinstance(DEFAULT_ROLES["PIP_FAIL"], list)
        assert len(DEFAULT_ROLES["PIP_FAIL"]) > 0

    def test_has_exec_override(self) -> None:
        """EXEC_OVERRIDE workflow type exists (matches ucs_validator.rego)."""
        assert "EXEC_OVERRIDE" in DEFAULT_ROLES
        assert isinstance(DEFAULT_ROLES["EXEC_OVERRIDE"], list)
        assert len(DEFAULT_ROLES["EXEC_OVERRIDE"]) > 0

    def test_termination_requires_senior_roles(self) -> None:
        """TERMINATION_DECISION requires senior HR or legal roles."""
        roles = DEFAULT_ROLES["TERMINATION_DECISION"]
        # Must include at least one senior role
        senior_roles = {"HRBP_DIRECTOR", "VP_HR", "CHRO", "LEGAL_COUNSEL"}
        assert any(role in senior_roles for role in roles)

    def test_exec_override_requires_executive_roles(self) -> None:
        """EXEC_OVERRIDE requires C-suite or general counsel."""
        roles = DEFAULT_ROLES["EXEC_OVERRIDE"]
        exec_roles = {"CHRO", "CEO", "GENERAL_COUNSEL"}
        assert any(role in exec_roles for role in roles)


class TestUCSDataProviderInit:
    """Test UCSDataProvider initialization."""

    def test_default_roles_used_when_none_provided(self) -> None:
        """Provider uses DEFAULT_ROLES when no roles specified."""
        provider = UCSDataProvider()
        assert provider.roles == DEFAULT_ROLES

    def test_custom_roles_accepted(self) -> None:
        """Provider accepts custom role configuration."""
        custom_roles = {"CUSTOM_WORKFLOW": ["ROLE_A", "ROLE_B"]}
        provider = UCSDataProvider(roles=custom_roles)
        assert provider.roles == custom_roles

    def test_empty_ceps_on_init(self) -> None:
        """No CEPs present on initialization."""
        provider = UCSDataProvider()
        assert provider.cep_count == 0

    def test_empty_signing_keys_on_init(self) -> None:
        """No signing keys present on initialization."""
        provider = UCSDataProvider()
        assert provider.signing_key_count == 0


class TestAddCep:
    """Test CEP addition and storage."""

    def test_add_cep_stores_correctly(self) -> None:
        """CEP fields are stored correctly."""
        provider = UCSDataProvider()
        valid_until = datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC)

        provider.add_cep(
            cep_id="cep-001",
            final_hash="sha256:abc123",
            cep_type="POLICY_SIGN_OFF",
            status="ACTIVE",
            valid_until_utc=valid_until,
        )

        assert provider.cep_count == 1
        data = provider.build_opa_data()
        cep = data["ceps"]["cep-001"]

        assert cep["cep_id"] == "cep-001"
        assert cep["final_hash"] == "sha256:abc123"
        assert cep["type"] == "POLICY_SIGN_OFF"
        assert cep["status"] == "ACTIVE"
        assert cep["valid_until_utc"] == valid_until.isoformat()

    def test_add_cep_default_status(self) -> None:
        """CEP defaults to ACTIVE status."""
        provider = UCSDataProvider()
        provider.add_cep(
            cep_id="cep-002",
            final_hash="sha256:def456",
            cep_type="ER_CLEARANCE",
        )

        data = provider.build_opa_data()
        assert data["ceps"]["cep-002"]["status"] == "ACTIVE"

    def test_add_cep_null_valid_until(self) -> None:
        """CEP valid_until_utc can be None."""
        provider = UCSDataProvider()
        provider.add_cep(
            cep_id="cep-003",
            final_hash="sha256:ghi789",
            cep_type="ATTESTATION",
            valid_until_utc=None,
        )

        data = provider.build_opa_data()
        assert data["ceps"]["cep-003"]["valid_until_utc"] is None

    def test_add_multiple_ceps(self) -> None:
        """Multiple CEPs can be added and retrieved."""
        provider = UCSDataProvider()
        provider.add_cep(cep_id="cep-a", final_hash="hash-a", cep_type="TYPE_A")
        provider.add_cep(cep_id="cep-b", final_hash="hash-b", cep_type="TYPE_B")
        provider.add_cep(cep_id="cep-c", final_hash="hash-c", cep_type="TYPE_C")

        assert provider.cep_count == 3
        data = provider.build_opa_data()
        assert "cep-a" in data["ceps"]
        assert "cep-b" in data["ceps"]
        assert "cep-c" in data["ceps"]

    def test_add_cep_overwrites_existing(self) -> None:
        """Adding CEP with same ID overwrites previous."""
        provider = UCSDataProvider()
        provider.add_cep(cep_id="cep-x", final_hash="old-hash", cep_type="OLD")
        provider.add_cep(cep_id="cep-x", final_hash="new-hash", cep_type="NEW")

        assert provider.cep_count == 1
        data = provider.build_opa_data()
        assert data["ceps"]["cep-x"]["final_hash"] == "new-hash"
        assert data["ceps"]["cep-x"]["type"] == "NEW"


class TestAddSigningKey:
    """Test signing key addition and storage."""

    def test_add_signing_key_stores_correctly(self) -> None:
        """Signing key fields are stored correctly."""
        provider = UCSDataProvider()
        valid_from = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        valid_to = datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC)

        provider.add_signing_key(
            key_id="key-001",
            valid_from_utc=valid_from,
            valid_to_utc=valid_to,
            revoked_at_utc=None,
        )

        assert provider.signing_key_count == 1
        data = provider.build_opa_data()
        key = data["signing_keys"]["key-001"]

        assert key["key_id"] == "key-001"
        assert key["valid_from_utc"] == valid_from.isoformat()
        assert key["valid_to_utc"] == valid_to.isoformat()
        assert key["revoked_at_utc"] is None

    def test_add_signing_key_with_revocation(self) -> None:
        """Signing key with revocation timestamp."""
        provider = UCSDataProvider()
        valid_from = datetime(2024, 1, 1, tzinfo=UTC)
        revoked_at = datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC)

        provider.add_signing_key(
            key_id="key-002",
            valid_from_utc=valid_from,
            revoked_at_utc=revoked_at,
        )

        data = provider.build_opa_data()
        key = data["signing_keys"]["key-002"]
        assert key["revoked_at_utc"] == revoked_at.isoformat()

    def test_add_signing_key_null_valid_to(self) -> None:
        """Signing key can have no expiration (valid_to_utc = None)."""
        provider = UCSDataProvider()
        valid_from = datetime(2024, 1, 1, tzinfo=UTC)

        provider.add_signing_key(
            key_id="key-003",
            valid_from_utc=valid_from,
            valid_to_utc=None,
        )

        data = provider.build_opa_data()
        assert data["signing_keys"]["key-003"]["valid_to_utc"] is None

    def test_add_multiple_signing_keys(self) -> None:
        """Multiple signing keys can be added."""
        provider = UCSDataProvider()
        base_time = datetime(2024, 1, 1, tzinfo=UTC)

        provider.add_signing_key(key_id="key-a", valid_from_utc=base_time)
        provider.add_signing_key(key_id="key-b", valid_from_utc=base_time)

        assert provider.signing_key_count == 2
        data = provider.build_opa_data()
        assert "key-a" in data["signing_keys"]
        assert "key-b" in data["signing_keys"]


class TestBuildOpaData:
    """Test build_opa_data output structure."""

    def test_returns_correct_structure(self) -> None:
        """Output contains roles, ceps, signing_keys keys."""
        provider = UCSDataProvider()
        data = provider.build_opa_data()

        assert "roles" in data
        assert "ceps" in data
        assert "signing_keys" in data

    def test_roles_match_rego_expectations(self) -> None:
        """Roles structure matches data.roles[workflow_type] in rego."""
        provider = UCSDataProvider()
        data = provider.build_opa_data()

        # Each role mapping is workflow_type -> list[str]
        for workflow_type, allowed_roles in data["roles"].items():
            assert isinstance(workflow_type, str)
            assert isinstance(allowed_roles, list)
            for role in allowed_roles:
                assert isinstance(role, str)

    def test_ceps_keyed_by_cep_id(self) -> None:
        """CEPs are keyed by cep_id for data.ceps[p.cep_id] access."""
        provider = UCSDataProvider()
        provider.add_cep(cep_id="my-cep-id", final_hash="hash", cep_type="TYPE")

        data = provider.build_opa_data()
        # Rego accesses: data.ceps[p.cep_id]
        assert "my-cep-id" in data["ceps"]

    def test_signing_keys_keyed_by_key_id(self) -> None:
        """Signing keys are keyed by key_id for data.signing_keys access."""
        provider = UCSDataProvider()
        provider.add_signing_key(
            key_id="my-key-id",
            valid_from_utc=datetime(2024, 1, 1, tzinfo=UTC),
        )

        data = provider.build_opa_data()
        # Rego accesses: data.signing_keys[input.seal.signing_key_id]
        assert "my-key-id" in data["signing_keys"]

    def test_datetime_as_iso8601_strings(self) -> None:
        """Datetime fields are ISO-8601 strings for time.parse_rfc3339_ns."""
        provider = UCSDataProvider()
        ts = datetime(2024, 6, 15, 12, 30, 45, tzinfo=UTC)

        provider.add_cep(
            cep_id="cep-ts",
            final_hash="hash",
            cep_type="TYPE",
            valid_until_utc=ts,
        )
        provider.add_signing_key(
            key_id="key-ts",
            valid_from_utc=ts,
            valid_to_utc=ts,
        )

        data = provider.build_opa_data()

        # OPA time.parse_rfc3339_ns expects ISO-8601 strings
        cep_ts = data["ceps"]["cep-ts"]["valid_until_utc"]
        assert isinstance(cep_ts, str)
        assert "2024-06-15" in cep_ts

        key_from = data["signing_keys"]["key-ts"]["valid_from_utc"]
        assert isinstance(key_from, str)
        assert "2024-06-15" in key_from


class TestClear:
    """Test clear method behavior."""

    def test_clear_removes_ceps(self) -> None:
        """Clear removes all CEPs."""
        provider = UCSDataProvider()
        provider.add_cep(cep_id="cep-1", final_hash="h1", cep_type="T1")
        provider.add_cep(cep_id="cep-2", final_hash="h2", cep_type="T2")

        assert provider.cep_count == 2
        provider.clear()
        assert provider.cep_count == 0

    def test_clear_removes_signing_keys(self) -> None:
        """Clear removes all signing keys."""
        provider = UCSDataProvider()
        base_time = datetime(2024, 1, 1, tzinfo=UTC)
        provider.add_signing_key(key_id="key-1", valid_from_utc=base_time)
        provider.add_signing_key(key_id="key-2", valid_from_utc=base_time)

        assert provider.signing_key_count == 2
        provider.clear()
        assert provider.signing_key_count == 0

    def test_clear_preserves_roles(self) -> None:
        """Clear does NOT remove roles (persistent config)."""
        custom_roles = {"WORKFLOW_X": ["ROLE_Y"]}
        provider = UCSDataProvider(roles=custom_roles)
        provider.add_cep(cep_id="cep", final_hash="h", cep_type="T")

        provider.clear()

        assert provider.cep_count == 0
        assert provider.roles == custom_roles

    def test_clear_allows_reuse(self) -> None:
        """Provider can be reused after clear."""
        provider = UCSDataProvider()
        provider.add_cep(cep_id="old-cep", final_hash="old", cep_type="OLD")
        provider.clear()

        provider.add_cep(cep_id="new-cep", final_hash="new", cep_type="NEW")

        assert provider.cep_count == 1
        data = provider.build_opa_data()
        assert "old-cep" not in data["ceps"]
        assert "new-cep" in data["ceps"]


class TestSetRoles:
    """Test set_roles method."""

    def test_set_roles_replaces_existing(self) -> None:
        """set_roles completely replaces role configuration."""
        provider = UCSDataProvider()
        original_roles = provider.roles.copy()

        new_roles = {"NEW_WORKFLOW": ["NEW_ROLE"]}
        provider.set_roles(new_roles)

        assert provider.roles == new_roles
        assert provider.roles != original_roles

    def test_set_roles_empty_dict(self) -> None:
        """set_roles can accept empty dict (deny all)."""
        provider = UCSDataProvider()
        provider.set_roles({})

        assert provider.roles == {}
        data = provider.build_opa_data()
        assert data["roles"] == {}
