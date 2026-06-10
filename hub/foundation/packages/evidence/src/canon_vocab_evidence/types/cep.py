"""CEP (Certified Evidence Packet) types.

CEPs are the legal-grade containers for evidence that justify decisions.
They transition from DRAFT -> SEALED (immutable) -> optionally SUPERSEDED.
"""

from __future__ import annotations

from kron.types import Enum

__all__ = ("CEPStatus", "CEPType")


class CEPStatus(Enum):
    """CEP lifecycle states.

    Lifecycle:
        DRAFT: Created, accumulating facts, not yet sealed
        SEALED: Signed + timestamped, immutable, ready for decision binding
        SUPERSEDED: Replaced by a new version (correction workflow)
    """

    DRAFT = "draft"
    SEALED = "sealed"
    SUPERSEDED = "superseded"


class CEPType(Enum):
    """Allowed CEP types - strict taxonomy.

    Each type maps to specific evidence categories and has different
    requirements for what facts must be included.

    Regulatory context:
        - FCRA Section 1681m: Evidence for adverse action decisions
        - Employment law: Documentation for termination decisions
        - SOX Section 802: Financial decision documentation
    """

    # Quantitative scores, quota attainment, error rates
    PERF_METRIC = "perf_metric"

    # Access logs, timecards, security alerts, policy violation records
    POLICY_LOG = "policy_log"

    # Redacted chat/email excerpts, communication records
    CONDUCT_RECORD = "conduct_record"

    # Final finding only from HR/legal investigation
    INVESTIGATION_RULING = "investigation_ruling"

    # Signed PIP document + binary pass/fail status
    PIP_FAIL = "pip_fail"

    # Background check results
    BACKGROUND_CHECK = "background_check"

    # Reference check summary
    REFERENCE_CHECK = "reference_check"

    # Skills assessment results
    ASSESSMENT_RESULT = "assessment_result"
