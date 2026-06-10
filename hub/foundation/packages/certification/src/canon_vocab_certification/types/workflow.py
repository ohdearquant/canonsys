"""Certification workflow types.

Enums for certification workflow orchestration.
"""

from __future__ import annotations

from kron.types import Enum

__all__ = (
    "CertificationEvent",
    "SignerRole",
    "WorkflowType",
)


class WorkflowType(Enum):
    """Certification workflow types."""

    PIP = "pip"  # P0: Performance Improvement Plan
    INVESTIGATION = "investigation"  # P1: Investigation Closure
    RIF = "rif"  # P2: Reduction in Force
    PROMOTION = "promotion"  # P3: Promotion/Leveling
    ACCOMMODATION = "accommodation"  # P4: ADA Accommodation
    AI_HIRING = "ai_hiring"  # P5: AI Hiring Approval


class CertificationEvent(Enum):
    """Certification events that mark state transitions.

    Makes the temporal cliff explicit in the data model.
    """

    CASE_CREATED = "case_created"
    EVIDENCE_SUBMITTED = "evidence_submitted"
    GATE_PASSED = "gate_passed"
    GATE_FAILED = "gate_failed"
    CERTIFICATE_MINTED = "certificate_minted"  # TEMPORAL CLIFF
    SUPERSEDED = "superseded"


class SignerRole(Enum):
    """Standard signer roles for attestations."""

    MANAGER = "manager"
    HRBP = "hrbp"
    EMPLOYEE = "employee"
    INVESTIGATOR = "investigator"
    LEGAL = "legal"
    EXECUTIVE = "executive"
    WITNESS = "witness"
    AUDITOR = "auditor"
