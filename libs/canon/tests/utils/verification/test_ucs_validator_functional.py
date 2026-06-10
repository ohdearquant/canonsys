"""Functional tests for UCS Validator rego policy.

These tests load and evaluate the ACTUAL ucs_validator.rego file using
regorus, validating real policy behavior - not mocks.

Test coverage mirrors ucs_validator_test.rego:
- Valid termination certificates (allow = true)
- Type-swap attack detection (CEP type mismatch)
- Hash mismatch detection (integrity violation)
- Expired CEP detection (time validation)
- Revoked CEP detection (lifecycle validation)
- ER clearance validation (invariant enforcement)
- Role-based authority validation
- Signing key revocation (time-aware)
- Exec override workflow (evidence optional)
"""


from __future__ import annotations

import pytest

pytest.importorskip("regorus")


from pathlib import Path

import pytest

from canon.utils.opa.engine import EnginePool

# Path to actual rego files
REGO_DIR = (
    Path(__file__).parent.parent.parent.parent / "src" / "canon" / "utils" / "verification" / "opa"
)
UCS_VALIDATOR_PATH = REGO_DIR / "ucs_validator.rego"


# =============================================================================
# Test Data (mirrors ucs_validator_test.rego)
# =============================================================================


@pytest.fixture
def test_data():
    """Test data for UCS validator policy.

    Structure matches data.roles, data.ceps, data.signing_keys
    expected by ucs_validator.rego.
    """
    return {
        "roles": {
            "TERMINATION_DECISION": ["HRBP_DIRECTOR", "ER_LEAD", "LEGAL_COUNSEL"],
            "EXEC_OVERRIDE": ["CHRO", "GC", "CEO"],
            "INVESTIGATION_CLOSE": ["ER_LEAD", "LEGAL_COUNSEL"],
            "PIP_FAIL": ["HRBP_DIRECTOR", "ER_LEAD"],
        },
        "ceps": {
            "CEP-OK": {
                "type": "CEP_CONDUCT_RECORD",
                "final_hash": "sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
                "status": "ACTIVE",
                "valid_until_utc": "2030-01-01T00:00:00Z",
            },
            "CEP-EXPIRED": {
                "type": "CEP_CONDUCT_RECORD",
                "final_hash": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "status": "ACTIVE",
                "valid_until_utc": "2000-01-01T00:00:00Z",
            },
            "CEP-REVOKED": {
                "type": "CEP_CONDUCT_RECORD",
                "final_hash": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "status": "REVOKED",
                "valid_until_utc": "2030-01-01T00:00:00Z",
            },
            "CEP-PERF": {
                "type": "CEP_PERF_METRIC",
                "final_hash": "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
                "status": "ACTIVE",
                "valid_until_utc": "2030-01-01T00:00:00Z",
            },
        },
        "signing_keys": {
            "kms-key-001": {
                "key_id": "kms-key-001",
                "valid_from_utc": "2025-01-01T00:00:00Z",
                "valid_to_utc": None,
                "revoked_at_utc": None,
            },
            "kms-key-revoked-yesterday": {
                "key_id": "kms-key-revoked-yesterday",
                "valid_from_utc": "2025-01-01T00:00:00Z",
                "valid_to_utc": None,
                "revoked_at_utc": "2026-01-12T00:00:00Z",
            },
        },
    }


@pytest.fixture
def base_termination():
    """Valid termination certificate input.

    Baseline certificate that passes all checks when combined
    with test_data.
    """
    return {
        "meta": {
            "certificate_id": "11111111-1111-4111-8111-111111111111",
            "schema_version": "1.0",
            "issued_at_utc": "2026-01-13T12:00:00Z",
            "environment": "production",
        },
        "context": {
            "workflow_type": "TERMINATION_DECISION",
            "subject_token": "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
            "jurisdiction_code": "US-CA",
        },
        "authority": {
            "issuer_id": "user_123",
            "issuer_role": "LEGAL_COUNSEL",
            "delegation_chain": None,
        },
        "assertions": {
            "policy_basis": {"code": "POL-TERM-004", "exception_flag": False},
            "risk_acceptance": True,
            "parity_attested": True,
            "er_clearance": {
                "cleared": False,
                "timestamp_utc": "2026-01-13T11:59:00Z",
                "system_ref": "ERCHK-1",
            },
            "termination_type": "EGREGIOUS_CONDUCT",
        },
        "evidence_pointers": [
            {
                "cep_id": "CEP-OK",
                "type": "CEP_CONDUCT_RECORD",
                "hash": "sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
            }
        ],
        "seal": {
            "previous_cert_hash": None,
            "payload_hash": "sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
            "signature": "SIG",
            "signing_key_id": "kms-key-001",
            "signed_at_utc": "2026-01-13T12:00:00Z",
            "tsa_token": "TSA",
        },
    }


@pytest.fixture
def exec_override_cert():
    """Valid exec override certificate (no evidence required)."""
    return {
        "meta": {
            "certificate_id": "22222222-2222-4222-8222-222222222222",
            "schema_version": "1.0",
            "issued_at_utc": "2026-01-13T12:00:00Z",
            "environment": "production",
        },
        "context": {
            "workflow_type": "EXEC_OVERRIDE",
            "subject_token": "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
            "jurisdiction_code": "US-CA",
        },
        "authority": {
            "issuer_id": "user_gc",
            "issuer_role": "GC",
            "delegation_chain": None,
        },
        "assertions": {
            "override_scope": "Bypass standard warning requirement",
            "policy_deviation": "POL-TERM-004 requires prior warning; unmet",
            "risk_acceptance": True,
            "supporting_certificate_ids": [],
        },
        "evidence_pointers": [],
        "seal": {
            "previous_cert_hash": None,
            "payload_hash": "sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
            "signature": "SIG",
            "signing_key_id": "kms-key-001",
            "signed_at_utc": "2026-01-13T12:00:00Z",
            "tsa_token": "TSA",
        },
    }


@pytest.fixture
def engine_pool():
    """Create EnginePool with UCS validator policy loaded."""
    pool = EnginePool(size=1)
    pool.initialize()

    # Load the actual UCS validator rego file
    rego_content = UCS_VALIDATOR_PATH.read_text()
    pool.add_policy("ucs_validator.rego", rego_content)

    return pool


# =============================================================================
# Helper Functions
# =============================================================================


def evaluate_ucs(pool: EnginePool, input_data: dict, data: dict) -> bool:
    """Evaluate UCS certificate against validator policy.

    Args:
        pool: EnginePool with ucs_validator.rego loaded
        input_data: The UCS certificate input
        data: External data (roles, ceps, signing_keys)

    Returns:
        True if certificate is allowed, False otherwise
    """
    import json

    engine = pool.get_thread_engine()

    # Clear previous data and set fresh state
    engine.clear_data()

    # Use JSON serialization for proper boolean handling
    # Python True/False -> JSON true/false
    engine.set_input_json(json.dumps(input_data))
    engine.add_data_json(json.dumps(data))

    try:
        # Query the allow rule
        result = engine.eval_rule("data.ucs.validator.allow")
        return result is True
    finally:
        # Clean up
        engine.set_input({})


def get_decision(pool: EnginePool, input_data: dict, data: dict) -> dict:
    """Get full decision object from UCS validator.

    Args:
        pool: EnginePool with ucs_validator.rego loaded
        input_data: The UCS certificate input
        data: External data (roles, ceps, signing_keys)

    Returns:
        Decision dict with status and reason
    """
    import json

    engine = pool.get_thread_engine()

    # Clear previous data and set fresh state
    engine.clear_data()

    # Use JSON serialization for proper boolean handling
    engine.set_input_json(json.dumps(input_data))
    engine.add_data_json(json.dumps(data))

    try:
        result = engine.eval_rule("data.ucs.validator.decision")
        return result or {"status": "BLOCKED", "reason": "DEFAULT_DENY"}
    finally:
        engine.set_input({})


# =============================================================================
# Valid Certificate Tests
# =============================================================================


class TestValidCertificates:
    """Tests for valid certificates that should be allowed."""

    def test_valid_termination_certificate_allowed(self, engine_pool, base_termination, test_data):
        """Valid termination certificate should be allowed.

        This is the baseline test - all invariants satisfied:
        - Schema/context valid
        - Workflow type = TERMINATION_DECISION with required invariants
        - Authority role in allowed list
        - Evidence pointer hash, type, status, expiry all valid
        - Signing key valid at signing time
        """
        allowed = evaluate_ucs(engine_pool, base_termination, test_data)
        assert allowed is True

    def test_valid_termination_decision_approved(self, engine_pool, base_termination, test_data):
        """Valid termination certificate decision should be APPROVED."""
        decision = get_decision(engine_pool, base_termination, test_data)
        assert decision["status"] == "APPROVED"
        assert decision["reason"] == "OK"

    def test_exec_override_without_evidence_allowed(
        self, engine_pool, exec_override_cert, test_data
    ):
        """Exec override certificate should be allowed without evidence.

        EXEC_OVERRIDE workflow type has requires_evidence = false,
        so empty evidence_pointers is valid.
        """
        allowed = evaluate_ucs(engine_pool, exec_override_cert, test_data)
        assert allowed is True

    def test_all_allowed_roles_for_termination(self, engine_pool, base_termination, test_data):
        """All allowed roles for TERMINATION_DECISION should work."""
        allowed_roles = ["HRBP_DIRECTOR", "ER_LEAD", "LEGAL_COUNSEL"]

        for role in allowed_roles:
            cert = _copy_with_path(base_termination, ["authority", "issuer_role"], role)
            allowed = evaluate_ucs(engine_pool, cert, test_data)
            assert allowed is True, f"Role {role} should be allowed"


# =============================================================================
# Attack/Violation Detection Tests
# =============================================================================


class TestTypeSwapAttack:
    """Tests for type-swap attack detection.

    Type-swap attack: Evidence pointer claims a different type than
    what the CEP actually is. This could be used to pass integrity
    checks with wrong evidence type.
    """

    def test_type_swap_blocked(self, engine_pool, base_termination, test_data):
        """Type-swap attack should be blocked.

        Attack: Point to CEP-PERF (type=CEP_PERF_METRIC) but claim
        type=CEP_CONDUCT_RECORD in the pointer.
        """
        # Create bad certificate with type-swap
        bad = _copy_with_path(
            base_termination,
            ["evidence_pointers", 0],
            {
                "cep_id": "CEP-PERF",
                "type": "CEP_CONDUCT_RECORD",  # LIE - actual type is CEP_PERF_METRIC
                "hash": "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
            },
        )

        allowed = evaluate_ucs(engine_pool, bad, test_data)
        assert allowed is False


class TestHashMismatch:
    """Tests for hash mismatch detection (integrity validation)."""

    def test_hash_mismatch_blocked(self, engine_pool, base_termination, test_data):
        """Hash mismatch should be blocked (integrity violation).

        Attack: Modify evidence pointer hash to not match CEP's final_hash.
        """
        bad = _copy_with_path(
            base_termination,
            ["evidence_pointers", 0, "hash"],
            "sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        )

        allowed = evaluate_ucs(engine_pool, bad, test_data)
        assert allowed is False


class TestExpiredCEP:
    """Tests for expired CEP detection (time validation)."""

    def test_expired_cep_blocked(self, engine_pool, base_termination, test_data):
        """Expired CEP should be blocked.

        CEP-EXPIRED has valid_until_utc = 2000-01-01, which is in the past.
        """
        bad = _copy_with_path(
            base_termination,
            ["evidence_pointers", 0],
            {
                "cep_id": "CEP-EXPIRED",
                "type": "CEP_CONDUCT_RECORD",
                "hash": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            },
        )

        allowed = evaluate_ucs(engine_pool, bad, test_data)
        assert allowed is False


class TestRevokedCEP:
    """Tests for revoked CEP detection (lifecycle validation)."""

    def test_revoked_cep_blocked(self, engine_pool, base_termination, test_data):
        """Revoked CEP should be blocked.

        CEP-REVOKED has status = REVOKED.
        """
        bad = _copy_with_path(
            base_termination,
            ["evidence_pointers", 0],
            {
                "cep_id": "CEP-REVOKED",
                "type": "CEP_CONDUCT_RECORD",
                "hash": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            },
        )

        allowed = evaluate_ucs(engine_pool, bad, test_data)
        assert allowed is False


class TestERClearance:
    """Tests for ER clearance invariant enforcement.

    For TERMINATION_DECISION, er_clearance.cleared MUST be false.
    true or unknown blocks the certificate.
    """

    def test_er_clearance_true_blocked(self, engine_pool, base_termination, test_data):
        """ER clearance = true should block (active ER context)."""
        bad = _copy_with_path(
            base_termination,
            ["assertions", "er_clearance", "cleared"],
            True,
        )

        allowed = evaluate_ucs(engine_pool, bad, test_data)
        assert allowed is False

    def test_er_clearance_unknown_blocked(self, engine_pool, base_termination, test_data):
        """ER clearance = 'unknown' should block."""
        bad = _copy_with_path(
            base_termination,
            ["assertions", "er_clearance", "cleared"],
            "unknown",
        )

        allowed = evaluate_ucs(engine_pool, bad, test_data)
        assert allowed is False


class TestRoleAuthorization:
    """Tests for role-based authority validation."""

    def test_unauthorized_role_blocked(self, engine_pool, base_termination, test_data):
        """Unauthorized role should be blocked.

        MANAGER_L1 is not in allowed roles for TERMINATION_DECISION.
        """
        bad = _copy_with_path(
            base_termination,
            ["authority", "issuer_role"],
            "MANAGER_L1",
        )

        allowed = evaluate_ucs(engine_pool, bad, test_data)
        assert allowed is False

    def test_nonexistent_role_blocked(self, engine_pool, base_termination, test_data):
        """Non-existent role should be blocked."""
        bad = _copy_with_path(
            base_termination,
            ["authority", "issuer_role"],
            "NONEXISTENT_ROLE",
        )

        allowed = evaluate_ucs(engine_pool, bad, test_data)
        assert allowed is False


class TestSigningKeyValidation:
    """Tests for signing key time-aware validation."""

    def test_revoked_key_at_signing_time_blocked(self, engine_pool, base_termination, test_data):
        """Signing key revoked before signed_at should block.

        kms-key-revoked-yesterday was revoked at 2026-01-12,
        signed_at is 2026-01-13 (after revocation).
        """
        bad = _copy_with_path(
            base_termination,
            ["seal", "signing_key_id"],
            "kms-key-revoked-yesterday",
        )

        allowed = evaluate_ucs(engine_pool, bad, test_data)
        assert allowed is False

    def test_signing_before_key_valid_blocked(self, engine_pool, base_termination, test_data):
        """Signing before key validity period should block.

        kms-key-001 is valid from 2025-01-01, but signed_at is 2024-01-01.
        """
        bad = _copy_with_path(
            base_termination,
            ["seal", "signed_at_utc"],
            "2024-01-01T00:00:00Z",
        )

        allowed = evaluate_ucs(engine_pool, bad, test_data)
        assert allowed is False

    def test_missing_tsa_token_blocked(self, engine_pool, base_termination, test_data):
        """Missing TSA token should block."""
        bad = _copy_with_path(
            base_termination,
            ["seal", "tsa_token"],
            "",
        )

        allowed = evaluate_ucs(engine_pool, bad, test_data)
        assert allowed is False

    def test_missing_signature_blocked(self, engine_pool, base_termination, test_data):
        """Missing signature should block."""
        bad = _copy_with_path(
            base_termination,
            ["seal", "signature"],
            "",
        )

        allowed = evaluate_ucs(engine_pool, bad, test_data)
        assert allowed is False


class TestSchemaValidation:
    """Tests for schema/context validation."""

    def test_wrong_schema_version_blocked(self, engine_pool, base_termination, test_data):
        """Wrong schema version should block."""
        bad = _copy_with_path(
            base_termination,
            ["meta", "schema_version"],
            "2.0",
        )

        allowed = evaluate_ucs(engine_pool, bad, test_data)
        assert allowed is False

    def test_non_production_environment_blocked(self, engine_pool, base_termination, test_data):
        """Non-production environment should block."""
        bad = _copy_with_path(
            base_termination,
            ["meta", "environment"],
            "staging",
        )

        allowed = evaluate_ucs(engine_pool, bad, test_data)
        assert allowed is False

    def test_empty_workflow_type_blocked(self, engine_pool, base_termination, test_data):
        """Empty workflow type should block."""
        bad = _copy_with_path(
            base_termination,
            ["context", "workflow_type"],
            "",
        )

        allowed = evaluate_ucs(engine_pool, bad, test_data)
        assert allowed is False

    def test_empty_subject_token_blocked(self, engine_pool, base_termination, test_data):
        """Empty subject token should block."""
        bad = _copy_with_path(
            base_termination,
            ["context", "subject_token"],
            "",
        )

        allowed = evaluate_ucs(engine_pool, bad, test_data)
        assert allowed is False


class TestTerminationInvariants:
    """Tests for termination-specific invariant validation."""

    def test_risk_acceptance_false_blocked(self, engine_pool, base_termination, test_data):
        """risk_acceptance = false should block."""
        bad = _copy_with_path(
            base_termination,
            ["assertions", "risk_acceptance"],
            False,
        )

        allowed = evaluate_ucs(engine_pool, bad, test_data)
        assert allowed is False

    def test_parity_attested_false_blocked(self, engine_pool, base_termination, test_data):
        """parity_attested = false should block."""
        bad = _copy_with_path(
            base_termination,
            ["assertions", "parity_attested"],
            False,
        )

        allowed = evaluate_ucs(engine_pool, bad, test_data)
        assert allowed is False

    def test_no_evidence_blocked_for_termination(self, engine_pool, base_termination, test_data):
        """Empty evidence should block TERMINATION_DECISION.

        TERMINATION_DECISION requires evidence (unlike EXEC_OVERRIDE).
        """
        bad = _copy_with_path(
            base_termination,
            ["evidence_pointers"],
            [],
        )

        allowed = evaluate_ucs(engine_pool, bad, test_data)
        assert allowed is False


class TestDefaultDeny:
    """Tests for fail-closed default deny behavior."""

    def test_unknown_workflow_blocked(self, engine_pool, base_termination, test_data):
        """Unknown workflow type should be blocked.

        Only TERMINATION_DECISION and EXEC_OVERRIDE have workflow_ok rules.
        """
        bad = _copy_with_path(
            base_termination,
            ["context", "workflow_type"],
            "UNKNOWN_WORKFLOW",
        )

        allowed = evaluate_ucs(engine_pool, bad, test_data)
        assert allowed is False

    def test_default_decision_is_blocked(self, engine_pool, test_data):
        """Default decision should be BLOCKED with DEFAULT_DENY reason."""
        # Minimal invalid input
        invalid_input = {"meta": {}, "context": {}, "authority": {}, "assertions": {}}

        decision = get_decision(engine_pool, invalid_input, test_data)
        assert decision["status"] == "BLOCKED"
        assert decision["reason"] == "DEFAULT_DENY"


# =============================================================================
# Helper Functions
# =============================================================================


def _copy_with_path(obj: dict, path: list, value) -> dict:
    """Deep copy dict and set value at path.

    Args:
        obj: Original dict
        path: List of keys/indices to traverse
        value: Value to set at path

    Returns:
        New dict with value set
    """
    import copy

    result = copy.deepcopy(obj)

    # Navigate to parent
    current = result
    for key in path[:-1]:
        current = current[key]

    # Set value
    current[path[-1]] = value

    return result
