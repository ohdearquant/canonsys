"""Tests for UCS-v1 transform functions.

Validates that transform output matches what ucs_validator.rego expects.
Reference: src/canon/verification/opa/ucs_validator.rego
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime

from canon.utils.verification.ucs_transform import (
    build_authority_block,
    build_context_block,
    build_evidence_pointers,
    build_meta_block,
    build_seal_block,
    tokenize_subject,
    transform_to_ucs,
)


class TestTokenizeSubject:
    """Test privacy-preserving subject tokenization."""

    def test_produces_sha256_hex(self) -> None:
        """Token must be SHA256 hex digest."""
        token = tokenize_subject("emp_123", "secret_salt")
        # SHA256 produces 64 hex chars
        assert len(token) == 64
        assert all(c in "0123456789abcdef" for c in token)

    def test_deterministic(self) -> None:
        """Same inputs must produce same token."""
        token1 = tokenize_subject("emp_123", "salt")
        token2 = tokenize_subject("emp_123", "salt")
        assert token1 == token2

    def test_salt_differentiates(self) -> None:
        """Different salt must produce different token."""
        token1 = tokenize_subject("emp_123", "salt1")
        token2 = tokenize_subject("emp_123", "salt2")
        assert token1 != token2

    def test_subject_id_differentiates(self) -> None:
        """Different subject_id must produce different token."""
        token1 = tokenize_subject("emp_123", "salt")
        token2 = tokenize_subject("emp_456", "salt")
        assert token1 != token2

    def test_matches_manual_computation(self) -> None:
        """Verify against manual SHA256 computation."""
        subject_id = "emp_123"
        salt = "salt_abc"
        expected = hashlib.sha256(f"{subject_id}{salt}".encode()).hexdigest()
        assert tokenize_subject(subject_id, salt) == expected


class TestBuildMetaBlock:
    """Test meta block construction."""

    def test_required_fields(self) -> None:
        """Meta block must have all required fields."""
        meta = build_meta_block(certificate_id="cert-001")
        assert "certificate_id" in meta
        assert "schema_version" in meta
        assert "issued_at_utc" in meta
        assert "environment" in meta

    def test_certificate_id(self) -> None:
        """Certificate ID must be passed through."""
        meta = build_meta_block(certificate_id="cert-xyz")
        assert meta["certificate_id"] == "cert-xyz"

    def test_default_schema_version(self) -> None:
        """Default schema version must be 1.0."""
        meta = build_meta_block(certificate_id="cert-001")
        assert meta["schema_version"] == "1.0"

    def test_custom_schema_version(self) -> None:
        """Custom schema version must be respected."""
        meta = build_meta_block(certificate_id="cert-001", schema_version="2.0")
        assert meta["schema_version"] == "2.0"

    def test_default_environment(self) -> None:
        """Default environment must be production."""
        meta = build_meta_block(certificate_id="cert-001")
        assert meta["environment"] == "production"

    def test_custom_environment(self) -> None:
        """Custom environment must be respected."""
        meta = build_meta_block(certificate_id="cert-001", environment="simulation")
        assert meta["environment"] == "simulation"

    def test_issued_at_iso8601(self) -> None:
        """issued_at_utc must be ISO-8601 string."""
        dt = datetime(2026, 1, 13, 12, 0, 0, tzinfo=UTC)
        meta = build_meta_block(certificate_id="cert-001", issued_at=dt)
        assert meta["issued_at_utc"] == "2026-01-13T12:00:00+00:00"

    def test_issued_at_auto_generated(self) -> None:
        """issued_at_utc must be auto-generated if not provided."""
        meta = build_meta_block(certificate_id="cert-001")
        # Must be valid ISO-8601
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", meta["issued_at_utc"])


class TestBuildContextBlock:
    """Test context block construction."""

    def test_required_fields(self) -> None:
        """Context block must have all required fields."""
        ctx = build_context_block(
            workflow_type="TERMINATION_DECISION",
            subject_token="abc123",
            jurisdiction_code="US-CA",
        )
        assert "workflow_type" in ctx
        assert "subject_token" in ctx
        assert "jurisdiction_code" in ctx

    def test_workflow_type(self) -> None:
        """Workflow type must be passed through."""
        ctx = build_context_block(
            workflow_type="PIP_FAIL",
            subject_token="token",
            jurisdiction_code="US-NY",
        )
        assert ctx["workflow_type"] == "PIP_FAIL"

    def test_subject_token(self) -> None:
        """Subject token must be passed through."""
        ctx = build_context_block(
            workflow_type="TERMINATION_DECISION",
            subject_token="sha256_hash_here",
            jurisdiction_code="US-CA",
        )
        assert ctx["subject_token"] == "sha256_hash_here"

    def test_jurisdiction_code(self) -> None:
        """Jurisdiction code must be passed through."""
        ctx = build_context_block(
            workflow_type="TERMINATION_DECISION",
            subject_token="token",
            jurisdiction_code="US-NYC",
        )
        assert ctx["jurisdiction_code"] == "US-NYC"

    def test_null_jurisdiction_code(self) -> None:
        """Null jurisdiction code must be empty string for OPA."""
        ctx = build_context_block(
            workflow_type="TERMINATION_DECISION",
            subject_token="token",
            jurisdiction_code=None,
        )
        # OPA expects non-empty, so we use empty string to explicitly fail validation
        assert ctx["jurisdiction_code"] == ""


class TestBuildAuthorityBlock:
    """Test authority block construction."""

    def test_required_fields(self) -> None:
        """Authority block must have all required fields."""
        auth = build_authority_block(
            issuer_id="user_123",
            issuer_role="HRBP_DIRECTOR",
        )
        assert "issuer_id" in auth
        assert "issuer_role" in auth
        assert "delegation_chain" in auth

    def test_issuer_id(self) -> None:
        """Issuer ID must be passed through."""
        auth = build_authority_block(issuer_id="user_abc", issuer_role="LEGAL_COUNSEL")
        assert auth["issuer_id"] == "user_abc"

    def test_issuer_role(self) -> None:
        """Issuer role must be passed through."""
        auth = build_authority_block(issuer_id="user_123", issuer_role="ER_LEAD")
        assert auth["issuer_role"] == "ER_LEAD"

    def test_default_delegation_chain(self) -> None:
        """Default delegation chain must be null."""
        auth = build_authority_block(issuer_id="user_123", issuer_role="HRBP_DIRECTOR")
        assert auth["delegation_chain"] is None

    def test_custom_delegation_chain(self) -> None:
        """Custom delegation chain must be respected."""
        chain = [{"delegate_id": "user_456", "granted_by": "user_123"}]
        auth = build_authority_block(
            issuer_id="user_123", issuer_role="HRBP_DIRECTOR", delegation_chain=chain
        )
        assert auth["delegation_chain"] == chain


class TestBuildEvidencePointers:
    """Test evidence pointers construction."""

    def test_empty_list(self) -> None:
        """Empty input must produce empty list."""
        pointers = build_evidence_pointers([])
        assert pointers == []

    def test_single_cep(self) -> None:
        """Single CEP must produce single pointer."""
        ceps = [("CEP-001", "CEP_CONDUCT_RECORD", "sha256:abc123")]
        pointers = build_evidence_pointers(ceps)
        assert len(pointers) == 1
        assert pointers[0] == {
            "cep_id": "CEP-001",
            "type": "CEP_CONDUCT_RECORD",
            "hash": "sha256:abc123",
        }

    def test_multiple_ceps(self) -> None:
        """Multiple CEPs must produce multiple pointers."""
        ceps = [
            ("CEP-001", "CEP_CONDUCT_RECORD", "sha256:abc"),
            ("CEP-002", "CEP_PERF_METRIC", "sha256:def"),
        ]
        pointers = build_evidence_pointers(ceps)
        assert len(pointers) == 2
        assert pointers[0]["cep_id"] == "CEP-001"
        assert pointers[1]["cep_id"] == "CEP-002"

    def test_pointer_structure(self) -> None:
        """Each pointer must have cep_id, type, hash."""
        ceps = [("CEP-XYZ", "PERFORMANCE_DATA_PACKET", "sha256:ffff")]
        pointers = build_evidence_pointers(ceps)
        pointer = pointers[0]
        assert set(pointer.keys()) == {"cep_id", "type", "hash"}


class TestBuildSealBlock:
    """Test seal block construction."""

    def test_required_fields(self) -> None:
        """Seal block must have all required fields for OPA."""
        seal = build_seal_block(payload_hash="sha256:abc")
        # OPA expects all these fields
        assert "previous_cert_hash" in seal
        assert "payload_hash" in seal
        assert "signature" in seal
        assert "signing_key_id" in seal
        assert "signed_at_utc" in seal
        assert "tsa_token" in seal

    def test_payload_hash(self) -> None:
        """Payload hash must be passed through."""
        seal = build_seal_block(payload_hash="sha256:xyz123")
        assert seal["payload_hash"] == "sha256:xyz123"

    def test_default_signature(self) -> None:
        """Default signature must be empty string."""
        seal = build_seal_block(payload_hash="sha256:abc")
        assert seal["signature"] == ""

    def test_custom_signature(self) -> None:
        """Custom signature must be respected."""
        seal = build_seal_block(payload_hash="sha256:abc", signature="RSA_SIG_HERE")
        assert seal["signature"] == "RSA_SIG_HERE"

    def test_default_signing_key_id(self) -> None:
        """Default signing_key_id must be empty string."""
        seal = build_seal_block(payload_hash="sha256:abc")
        assert seal["signing_key_id"] == ""

    def test_custom_signing_key_id(self) -> None:
        """Custom signing_key_id must be respected."""
        seal = build_seal_block(payload_hash="sha256:abc", signing_key_id="kms-key-001")
        assert seal["signing_key_id"] == "kms-key-001"

    def test_signed_at_utc_iso8601(self) -> None:
        """signed_at_utc must be ISO-8601 string."""
        dt = datetime(2026, 1, 13, 12, 30, 0, tzinfo=UTC)
        seal = build_seal_block(payload_hash="sha256:abc", signed_at_utc=dt)
        assert seal["signed_at_utc"] == "2026-01-13T12:30:00+00:00"

    def test_default_tsa_token(self) -> None:
        """Default tsa_token must be empty string."""
        seal = build_seal_block(payload_hash="sha256:abc")
        assert seal["tsa_token"] == ""

    def test_custom_tsa_token(self) -> None:
        """Custom tsa_token must be respected."""
        seal = build_seal_block(payload_hash="sha256:abc", tsa_token="TSA_TOKEN_XYZ")
        assert seal["tsa_token"] == "TSA_TOKEN_XYZ"

    def test_default_previous_cert_hash(self) -> None:
        """Default previous_cert_hash must be null."""
        seal = build_seal_block(payload_hash="sha256:abc")
        assert seal["previous_cert_hash"] is None

    def test_custom_previous_cert_hash(self) -> None:
        """Custom previous_cert_hash must be respected."""
        seal = build_seal_block(payload_hash="sha256:abc", previous_cert_hash="sha256:prev")
        assert seal["previous_cert_hash"] == "sha256:prev"


class TestTransformToUcs:
    """Test full UCS transformation."""

    def test_produces_all_top_level_blocks(self) -> None:
        """UCS must have all top-level blocks."""
        ucs = transform_to_ucs(
            certificate_id="cert-001",
            action_type="TERMINATION_DECISION",
            subject_id="emp_123",
            subject_salt="salt",
            jurisdiction="US-CA",
            actor_id="user_456",
            actor_role="HRBP_DIRECTOR",
            ceps=[("CEP-001", "CEP_CONDUCT_RECORD", "sha256:abc")],
            payload_hash="sha256:xyz",
        )
        assert "meta" in ucs
        assert "context" in ucs
        assert "authority" in ucs
        assert "assertions" in ucs
        assert "evidence_pointers" in ucs
        assert "seal" in ucs

    def test_subject_token_is_hashed(self) -> None:
        """subject_token must be SHA256, not raw subject_id."""
        ucs = transform_to_ucs(
            certificate_id="cert-001",
            action_type="TERMINATION_DECISION",
            subject_id="emp_123",
            subject_salt="salt_abc",
            jurisdiction="US-CA",
            actor_id="user_456",
            actor_role="HRBP_DIRECTOR",
            ceps=[],
            payload_hash="sha256:xyz",
        )
        # Token must NOT be the raw subject_id
        assert ucs["context"]["subject_token"] != "emp_123"
        # Token must be the SHA256 hash
        expected_token = hashlib.sha256(b"emp_123salt_abc").hexdigest()
        assert ucs["context"]["subject_token"] == expected_token

    def test_workflow_type_from_action_type(self) -> None:
        """workflow_type must come from action_type."""
        ucs = transform_to_ucs(
            certificate_id="cert-001",
            action_type="PIP_FAIL",
            subject_id="emp_123",
            subject_salt="salt",
            jurisdiction="US-CA",
            actor_id="user_456",
            actor_role="ER_LEAD",
            ceps=[],
            payload_hash="sha256:xyz",
        )
        assert ucs["context"]["workflow_type"] == "PIP_FAIL"

    def test_evidence_pointers_populated(self) -> None:
        """evidence_pointers must be populated from ceps."""
        ceps = [
            ("CEP-001", "CEP_CONDUCT_RECORD", "sha256:aaa"),
            ("CEP-002", "CEP_PERF_METRIC", "sha256:bbb"),
        ]
        ucs = transform_to_ucs(
            certificate_id="cert-001",
            action_type="TERMINATION_DECISION",
            subject_id="emp_123",
            subject_salt="salt",
            jurisdiction="US-CA",
            actor_id="user_456",
            actor_role="HRBP_DIRECTOR",
            ceps=ceps,
            payload_hash="sha256:xyz",
        )
        assert len(ucs["evidence_pointers"]) == 2
        assert ucs["evidence_pointers"][0]["cep_id"] == "CEP-001"
        assert ucs["evidence_pointers"][1]["cep_id"] == "CEP-002"

    def test_assertions_passed_through(self) -> None:
        """Custom assertions must be passed through."""
        assertions = {
            "policy_basis": {"code": "POL-TERM-004", "exception_flag": False},
            "risk_acceptance": True,
            "parity_attested": True,
            "er_clearance": {"cleared": False},
        }
        ucs = transform_to_ucs(
            certificate_id="cert-001",
            action_type="TERMINATION_DECISION",
            subject_id="emp_123",
            subject_salt="salt",
            jurisdiction="US-CA",
            actor_id="user_456",
            actor_role="HRBP_DIRECTOR",
            ceps=[],
            assertions=assertions,
            payload_hash="sha256:xyz",
        )
        assert ucs["assertions"] == assertions

    def test_default_assertions_empty_dict(self) -> None:
        """Default assertions must be empty dict."""
        ucs = transform_to_ucs(
            certificate_id="cert-001",
            action_type="TERMINATION_DECISION",
            subject_id="emp_123",
            subject_salt="salt",
            jurisdiction="US-CA",
            actor_id="user_456",
            actor_role="HRBP_DIRECTOR",
            ceps=[],
            payload_hash="sha256:xyz",
        )
        assert ucs["assertions"] == {}

    def test_seal_fields_populated(self) -> None:
        """Seal fields must be populated."""
        ucs = transform_to_ucs(
            certificate_id="cert-001",
            action_type="TERMINATION_DECISION",
            subject_id="emp_123",
            subject_salt="salt",
            jurisdiction="US-CA",
            actor_id="user_456",
            actor_role="HRBP_DIRECTOR",
            ceps=[],
            payload_hash="sha256:payload",
            seal_signature="SIG",
            signing_key_id="kms-key-001",
            tsa_token="TSA",
        )
        assert ucs["seal"]["payload_hash"] == "sha256:payload"
        assert ucs["seal"]["signature"] == "SIG"
        assert ucs["seal"]["signing_key_id"] == "kms-key-001"
        assert ucs["seal"]["tsa_token"] == "TSA"


class TestOpaCompatibility:
    """Test that output is compatible with ucs_validator.rego expectations."""

    def test_termination_decision_structure(self) -> None:
        """Structure must match base_termination in ucs_validator_test.rego."""
        ucs = transform_to_ucs(
            certificate_id="11111111-1111-4111-8111-111111111111",
            action_type="TERMINATION_DECISION",
            subject_id="emp_xyz",
            subject_salt="salt",
            jurisdiction="US-CA",
            actor_id="user_123",
            actor_role="LEGAL_COUNSEL",
            ceps=[
                (
                    "CEP-OK",
                    "CEP_CONDUCT_RECORD",
                    "sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
                )
            ],
            assertions={
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
            payload_hash="sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
            seal_signature="SIG",
            signing_key_id="kms-key-001",
            tsa_token="TSA",
        )

        # OPA expects these exact paths
        assert ucs["meta"]["schema_version"] == "1.0"
        assert ucs["meta"]["environment"] == "production"
        assert ucs["context"]["workflow_type"] == "TERMINATION_DECISION"
        assert ucs["context"]["jurisdiction_code"] == "US-CA"
        assert len(ucs["context"]["subject_token"]) == 64  # SHA256 hex
        assert ucs["authority"]["issuer_role"] == "LEGAL_COUNSEL"
        assert ucs["assertions"]["risk_acceptance"] is True
        assert ucs["assertions"]["parity_attested"] is True
        assert ucs["assertions"]["er_clearance"]["cleared"] is False
        assert len(ucs["evidence_pointers"]) == 1
        assert ucs["evidence_pointers"][0]["cep_id"] == "CEP-OK"
        assert ucs["seal"]["signature"] == "SIG"
        assert ucs["seal"]["signing_key_id"] == "kms-key-001"
        assert ucs["seal"]["tsa_token"] == "TSA"
        assert ucs["seal"]["payload_hash"] != ""

    def test_exec_override_structure(self) -> None:
        """Structure must match exec override in ucs_validator_test.rego."""
        ucs = transform_to_ucs(
            certificate_id="22222222-2222-4222-8222-222222222222",
            action_type="EXEC_OVERRIDE",
            subject_id="emp_xyz",
            subject_salt="salt",
            jurisdiction="US-CA",
            actor_id="user_gc",
            actor_role="GC",
            ceps=[],  # No evidence required for EXEC_OVERRIDE
            assertions={
                "override_scope": "Bypass standard warning requirement",
                "policy_deviation": "POL-TERM-004 requires prior warning; unmet",
                "risk_acceptance": True,
                "supporting_certificate_ids": [],
            },
            payload_hash="sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
            seal_signature="SIG",
            signing_key_id="kms-key-001",
            tsa_token="TSA",
        )

        assert ucs["context"]["workflow_type"] == "EXEC_OVERRIDE"
        assert ucs["authority"]["issuer_role"] == "GC"
        assert ucs["assertions"]["risk_acceptance"] is True
        assert ucs["assertions"]["override_scope"] != ""
        assert ucs["assertions"]["policy_deviation"] != ""
        assert ucs["evidence_pointers"] == []
