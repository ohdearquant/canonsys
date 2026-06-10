"""UCS-v1 Transform Functions.

Transforms certificate data to UCS-v1 JSON format for OPA validation.
Output structure matches what ucs_validator.rego expects.

Reference: docs/v2/prds/SPEC-universal-certificate-schema.md
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from kron.utils import now_utc


def tokenize_subject(subject_id: str, salt: str) -> str:
    """Create privacy-preserving subject token.

    Args:
        subject_id: Raw subject identifier (e.g., employee_id)
        salt: Tenant-specific salt for tokenization

    Returns:
        SHA256 hex digest of (subject_id + salt)

    Example:
        >>> tokenize_subject("emp_123", "secret")
        '7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069'
    """
    return hashlib.sha256(f"{subject_id}{salt}".encode()).hexdigest()


def build_meta_block(
    certificate_id: str,
    schema_version: str = "1.0",
    issued_at: datetime | None = None,
    environment: str = "production",
) -> dict[str, Any]:
    """Build UCS meta block.

    Args:
        certificate_id: Globally unique certificate identifier
        schema_version: Schema version for forward compatibility (default: "1.0")
        issued_at: Certificate issuance timestamp (default: now)
        environment: Environment name (default: "production")

    Returns:
        Meta block dict ready for UCS JSON
    """
    if issued_at is None:
        issued_at = now_utc()

    return {
        "certificate_id": certificate_id,
        "schema_version": schema_version,
        "issued_at_utc": issued_at.isoformat(),
        "environment": environment,
    }


def build_context_block(
    workflow_type: str,
    subject_token: str,
    jurisdiction_code: str | None,
) -> dict[str, Any]:
    """Build UCS context block.

    Args:
        workflow_type: Type of workflow (e.g., "TERMINATION_DECISION")
        subject_token: Privacy-preserving subject identifier (SHA256 hash)
        jurisdiction_code: Jurisdiction code (e.g., "US-CA", "US-NYC")

    Returns:
        Context block dict ready for UCS JSON
    """
    return {
        "workflow_type": workflow_type,
        "subject_token": subject_token,
        "jurisdiction_code": jurisdiction_code or "",
    }


def build_authority_block(
    issuer_id: str,
    issuer_role: str,
    delegation_chain: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build UCS authority block.

    Args:
        issuer_id: Who clicked the button (user identifier)
        issuer_role: The seat of authority (role > individual)
        delegation_chain: If acting on behalf of someone else

    Returns:
        Authority block dict ready for UCS JSON
    """
    return {
        "issuer_id": issuer_id,
        "issuer_role": issuer_role,
        "delegation_chain": delegation_chain,
    }


def build_evidence_pointers(
    ceps: list[tuple[str, str, str]],
) -> list[dict[str, str]]:
    """Build evidence_pointers array.

    Args:
        ceps: List of (cep_id, cep_type, content_hash) tuples

    Returns:
        List of evidence pointer dicts for UCS JSON

    Example:
        >>> build_evidence_pointers([("CEP-001", "CEP_CONDUCT_RECORD", "sha256:abc")])
        [{"cep_id": "CEP-001", "type": "CEP_CONDUCT_RECORD", "hash": "sha256:abc"}]
    """
    return [
        {
            "cep_id": cep_id,
            "type": cep_type,
            "hash": content_hash,
        }
        for cep_id, cep_type, content_hash in ceps
    ]


def build_seal_block(
    payload_hash: str,
    signature: str | None = None,
    signing_key_id: str | None = None,
    signed_at_utc: datetime | None = None,
    previous_cert_hash: str | None = None,
    tsa_token: str | None = None,
) -> dict[str, Any]:
    """Build UCS seal block.

    Args:
        payload_hash: SHA256 hash of certificate payload
        signature: RSA-4096 signature of fields (default: "")
        signing_key_id: KMS key identifier (default: "")
        signed_at_utc: When signature was created (default: "")
        previous_cert_hash: For certificate chaining (default: null)
        tsa_token: RFC 3161 timestamp authority token (default: "")

    Returns:
        Seal block dict ready for UCS JSON

    Note:
        OPA validation requires non-empty signature, signing_key_id, and tsa_token
        for full approval. Empty strings will cause validation failure (intended).
    """
    signed_at_str = signed_at_utc.isoformat() if signed_at_utc else ""

    return {
        "previous_cert_hash": previous_cert_hash,
        "payload_hash": payload_hash,
        "signature": signature or "",
        "signing_key_id": signing_key_id or "",
        "signed_at_utc": signed_at_str,
        "tsa_token": tsa_token or "",
    }


def transform_to_ucs(
    certificate_id: str,
    action_type: str,
    subject_id: str,
    subject_salt: str,
    jurisdiction: str | None,
    actor_id: str,
    actor_role: str,
    ceps: list[tuple[str, str, str]],
    payload_hash: str,
    assertions: dict[str, Any] | None = None,
    seal_signature: str | None = None,
    signing_key_id: str | None = None,
    signed_at_utc: datetime | None = None,
    previous_cert_hash: str | None = None,
    tsa_token: str | None = None,
    schema_version: str = "1.0",
    environment: str = "production",
    issued_at: datetime | None = None,
) -> dict[str, Any]:
    """Transform certificate data to UCS-v1 JSON format.

    This function converts flat certificate fields into the nested UCS-v1 structure
    expected by OPA validation (ucs_validator.rego).

    Args:
        certificate_id: Globally unique certificate identifier
        action_type: Type of action (maps to workflow_type)
        subject_id: Raw subject identifier (will be tokenized)
        subject_salt: Tenant-specific salt for subject tokenization
        jurisdiction: Primary jurisdiction code (e.g., "US-CA")
        actor_id: Who made the decision (user identifier)
        actor_role: Role of the actor (e.g., "HRBP_DIRECTOR")
        ceps: List of (cep_id, cep_type, content_hash) tuples
        payload_hash: SHA256 hash of certificate payload
        assertions: Workflow-specific assertions (varies by action_type)
        seal_signature: RSA signature of certificate
        signing_key_id: KMS key identifier
        signed_at_utc: When signature was created
        previous_cert_hash: Hash of superseded certificate (if any)
        tsa_token: RFC 3161 timestamp authority token
        schema_version: Schema version (default: "1.0")
        environment: Environment name (default: "production")
        issued_at: Certificate issuance timestamp (default: now)

    Returns:
        Dict in UCS-v1 format ready for OPA validation

    Example:
        >>> ucs = transform_to_ucs(
        ...     certificate_id="cert-001",
        ...     action_type="TERMINATION_DECISION",
        ...     subject_id="emp_123",
        ...     subject_salt="tenant_salt",
        ...     jurisdiction="US-CA",
        ...     actor_id="user_456",
        ...     actor_role="HRBP_DIRECTOR",
        ...     ceps=[("CEP-001", "CEP_CONDUCT_RECORD", "sha256:abc")],
        ...     payload_hash="sha256:xyz",
        ...     assertions={"risk_acceptance": True, "parity_attested": True},
        ... )
        >>> ucs["context"]["workflow_type"]
        'TERMINATION_DECISION'
    """
    # Tokenize subject_id for privacy
    subject_token = tokenize_subject(subject_id, subject_salt)

    return {
        "meta": build_meta_block(
            certificate_id=certificate_id,
            schema_version=schema_version,
            issued_at=issued_at,
            environment=environment,
        ),
        "context": build_context_block(
            workflow_type=action_type,
            subject_token=subject_token,
            jurisdiction_code=jurisdiction,
        ),
        "authority": build_authority_block(
            issuer_id=actor_id,
            issuer_role=actor_role,
        ),
        "assertions": assertions or {},
        "evidence_pointers": build_evidence_pointers(ceps),
        "seal": build_seal_block(
            payload_hash=payload_hash,
            signature=seal_signature,
            signing_key_id=signing_key_id,
            signed_at_utc=signed_at_utc,
            previous_cert_hash=previous_cert_hash,
            tsa_token=tsa_token,
        ),
    }


__all__ = [
    "build_authority_block",
    "build_context_block",
    "build_evidence_pointers",
    "build_meta_block",
    "build_seal_block",
    "tokenize_subject",
    "transform_to_ucs",
]
