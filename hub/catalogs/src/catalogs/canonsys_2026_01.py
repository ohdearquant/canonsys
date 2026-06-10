"""CanonSys base schema catalog (canonsys@2026.01).

Base compliance schemas for evidence management, audit trails, consent
verification, policy evaluation, and compliance certification.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from canon.dsl.catalog import SchemaCatalog

__all__ = [
    # Catalog builder
    "build_canonsys_catalog",
    # Schemas
    "EvidenceReport",
    "ChainIntegrityReport",
    "AuditReport",
    "ConsentVerificationReport",
    "PolicyEvaluationReport",
    "ComplianceCertificate",
    "DecisionCertificate",
]


@dataclass(frozen=True, slots=True)
class EvidenceReport:
    """Generic evidence report schema."""

    evidence_id: UUID
    evidence_type: str
    subject_id: UUID
    created_at: datetime
    integrity_hash: str
    metadata: dict[str, str]


@dataclass(frozen=True, slots=True)
class ChainIntegrityReport:
    """Chain of evidence integrity verification result."""

    chain_id: UUID
    is_valid: bool
    entries_checked: int
    first_entry_at: datetime
    last_entry_at: datetime
    integrity_hash: str


@dataclass(frozen=True, slots=True)
class AuditReport:
    """Audit trail report schema."""

    audit_id: UUID
    scope: str
    period_start: datetime
    period_end: datetime
    findings: tuple[str, ...]
    passed: bool


@dataclass(frozen=True, slots=True)
class ConsentVerificationReport:
    """Consent verification result."""

    subject_id: UUID
    scope: str
    has_consent: bool
    granted_at: datetime | None
    expires_at: datetime | None
    token_id: UUID | None


@dataclass(frozen=True, slots=True)
class PolicyEvaluationReport:
    """Policy evaluation result from OPA/Rego."""

    policy_id: str
    decision: str  # "allow" | "deny"
    violations: tuple[str, ...]
    conditions: tuple[str, ...]
    evaluated_at: datetime


@dataclass(frozen=True, slots=True)
class ComplianceCertificate:
    """Compliance certification schema."""

    certificate_id: UUID
    subject_id: UUID
    compliance_type: str
    issued_at: datetime
    valid_until: datetime | None
    issuer: str
    integrity_hash: str


@dataclass(frozen=True, slots=True)
class DecisionCertificate:
    """High-stakes decision certification."""

    certificate_id: UUID
    decision_type: str
    subject_id: UUID
    decided_by: UUID
    decided_at: datetime
    evidence_ids: tuple[UUID, ...]
    policy_basis: tuple[str, ...]
    integrity_hash: str
    is_immutable: bool


def build_canonsys_catalog(catalog: SchemaCatalog) -> None:
    """Register all canonsys@2026.01 schemas."""
    ns, ver = "canonsys", "2026.01"
    for schema_type in (
        EvidenceReport,
        ChainIntegrityReport,
        AuditReport,
        ConsentVerificationReport,
        PolicyEvaluationReport,
        ComplianceCertificate,
        DecisionCertificate,
    ):
        catalog.register(ns, ver, schema_type.__name__, schema_type)
