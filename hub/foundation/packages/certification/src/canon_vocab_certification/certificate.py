"""Decision certificate models.

Defines DecisionCertificate -- an immutable entity that proves process
adherence for regulated HR actions. Never revoked, only superseded.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, Field

from canon.entities.entity import ContentModel, Entity, register_entity
from kron.types import FK

if TYPE_CHECKING:
    from canon.entities.shared import Person, Tenant, User

SCHEMA_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CertificateStatus(str, Enum):
    """Certificate lifecycle status."""

    PROVISIONAL = "provisional"  # Editable, gathering evidence
    GATED = "gated"  # All gates passed, ready for minting
    MINTED = "minted"  # Certificate issued (temporal cliff)
    SUPERSEDED = "superseded"  # Replaced by subsequent certificate


class CertificateClass(str, Enum):
    """Certificate defensibility class."""

    CERTIFIED = "certified"  # Full compliance path
    BREAK_GLASS = "break_glass"  # Emergency override, degraded defensibility
    UNCOVERED = "uncovered"  # Action via excluded channel


class DefensibilityState(str, Enum):
    """Defensibility level of a certificate."""

    FULL = "full"
    PROVISIONAL = "provisional"
    DEGRADED = "degraded"


class IdentitySource(str, Enum):
    """Source of model identity information."""

    SELF_HOSTED = "self_hosted"
    PROVIDER_REPORTED = "provider_reported"


class ActionType(str, Enum):
    """Types of actions that can be certified."""

    TERMINATE_WORKER = "terminate_worker"
    INITIATE_PIP = "initiate_pip"
    ADVANCE_CANDIDATE = "advance_candidate"
    REJECT_CANDIDATE = "reject_candidate"
    GRANT_ACCOMMODATION = "grant_accommodation"
    DENY_ACCOMMODATION = "deny_accommodation"
    COMPLETE_INVESTIGATION = "complete_investigation"
    EXECUTE_RIF = "execute_rif"
    APPROVE_PROMOTION = "approve_promotion"


# ---------------------------------------------------------------------------
# Embedded models (stored as JSONB)
# ---------------------------------------------------------------------------


class ModelIdentity(BaseModel):
    """AI model provenance."""

    name: str
    version_hash: str
    prompt_chain_hash: str
    identity_source: IdentitySource = IdentitySource.PROVIDER_REPORTED


class InputFingerprint(BaseModel):
    """Hash of an input consumed during decision."""

    input_id: str
    content_hash: str
    schema_version: str = "1.0"


class GateEvaluation(BaseModel):
    """Record of a gate evaluation result."""

    gate_id: str
    evaluated_at: datetime
    passed: bool
    context_hash: str | None = None


class ReviewBehavior(BaseModel):
    """Anti-rubber stamp metrics proving meaningful human review."""

    review_duration_ms: int
    scroll_depth_percent: int


class JurisdictionContext(BaseModel):
    """Jurisdiction-specific context."""

    primary_jurisdiction: str
    secondary_jurisdictions: list[str] = Field(default_factory=list)
    rules_applied: list[str] = Field(default_factory=list)
    waiting_period_days: int | None = None
    special_requirements: list[str] = Field(default_factory=list)


class AttestationRecord(BaseModel):
    """Record of a signer attestation for non-repudiation."""

    signer_id: UUID
    signer_role: str
    signed_at: datetime
    method: str
    acknowledgment_text: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None


# ---------------------------------------------------------------------------
# Content model
# ---------------------------------------------------------------------------


class DecisionCertificateContent(ContentModel):
    """Content for decision certificates.

    The primary product artifact. Proves process was followed,
    not that the outcome was correct.

    Platform invariants:
        1. Supersession Doctrine -- never revoked, only superseded.
        2. Zero-Warnings Rule -- no minting unless all gates pass.
        3. Attestation Scope -- process adherence, not outcome correctness.
        4. Temporal Cliff -- MINTED marks irreversible immutability.
    """

    # Scope
    tenant_id: FK[Tenant]
    subject_id: FK[Person] | None = None
    actor_id: FK[User] | None = None

    # Schema
    schema_version: str = SCHEMA_VERSION

    # Decision context
    action_type: ActionType
    case_id: UUID | None = None

    # Computational state (frozen at certification)
    model_identity: ModelIdentity | None = None
    input_fingerprints: list[InputFingerprint] = Field(default_factory=list)
    policy_version: str | None = None
    policy_adapter_hash: str | None = None
    tenant_policy_activation_hash: str | None = None

    # Jurisdiction
    jurisdiction: str | None = None
    jurisdiction_context: JurisdictionContext | None = None

    # Gate evaluations
    gates_passed: list[GateEvaluation] = Field(default_factory=list)

    # Anti-rubber stamp
    review_behavior: ReviewBehavior | None = None

    # Evidence binding
    evidence_ids: list[UUID] = Field(default_factory=list)

    # Attestations
    attestations: list[AttestationRecord] = Field(default_factory=list)

    # Certification
    status: CertificateStatus = CertificateStatus.PROVISIONAL
    certificate_class: CertificateClass = CertificateClass.CERTIFIED
    defensibility_state: DefensibilityState = DefensibilityState.FULL
    minted_at: datetime | None = None

    # Validation gate
    validated_at: datetime | None = None
    validation_hash: str | None = None

    # Supersession
    supersedes_id: UUID | None = None

    # Outcome
    outcome: str | None = None
    outcome_rationale: str | None = None

    # Retention
    retention_policy_ref: str | None = None


# ---------------------------------------------------------------------------
# Public entity
# ---------------------------------------------------------------------------


@register_entity("decisioncertificates", immutable=True)
class DecisionCertificate(Entity):
    """Immutable entity proving process adherence for regulated HR actions."""

    content: DecisionCertificateContent
