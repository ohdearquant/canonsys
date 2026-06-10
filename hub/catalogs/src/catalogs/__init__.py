"""Canon Schema Catalogs - versioned type registries for Charter DSL.

This package provides schema catalogs that define typed output schemas
for Charter workflows. Each catalog corresponds to a domain namespace
with versioned schema definitions.

Catalogs:
- canon.hr@2026.01: HR workflow schemas (eligibility, PIP, termination, etc.)
- canonsys@2026.01: Base compliance schemas (evidence, audit, certificates, etc.)

Usage:
    from catalogs import (
        # Catalog builders
        build_canon_hr_catalog,
        build_canonsys_catalog,
        # HR schemas (canon.hr@2026.01)
        EligibilityReport,
        PIPSpecification,
        TerminationCertificate,
        # Base schemas (canonsys@2026.01)
        EvidenceReport,
        DecisionCertificate,
    )

    # Build a catalog for Charter DSL
    from canon.dsl.catalog import SchemaCatalog
    catalog = SchemaCatalog()
    build_canon_hr_catalog(catalog)
    build_canonsys_catalog(catalog)
"""

# Canon HR schemas (canon.hr@2026.01)
from .canon_hr_2026_01 import (
    AcknowledgmentRecord,
    AdverseActionNotice,
    AIInterviewCertificate,
    BackgroundCheckReport,
    EligibilityReport,
    HiringDecisionReport,
    OutcomeRecord,
    PIPReport,
    PIPSpecification,
    ProgressReport,
    TerminationCertificate,
    build_canon_hr_catalog,
)

# CanonSys base schemas (canonsys@2026.01)
from .canonsys_2026_01 import (
    AuditReport,
    ChainIntegrityReport,
    ComplianceCertificate,
    ConsentVerificationReport,
    DecisionCertificate,
    EvidenceReport,
    PolicyEvaluationReport,
    build_canonsys_catalog,
)

__all__ = [
    # Catalog builders
    "build_canon_hr_catalog",
    "build_canonsys_catalog",
    # Canon HR schemas (canon.hr@2026.01)
    "EligibilityReport",
    "PIPSpecification",
    "PIPReport",
    "ProgressReport",
    "AcknowledgmentRecord",
    "OutcomeRecord",
    "TerminationCertificate",
    "AIInterviewCertificate",
    "HiringDecisionReport",
    "AdverseActionNotice",
    "BackgroundCheckReport",
    # CanonSys base schemas (canonsys@2026.01)
    "EvidenceReport",
    "ChainIntegrityReport",
    "AuditReport",
    "ConsentVerificationReport",
    "PolicyEvaluationReport",
    "ComplianceCertificate",
    "DecisionCertificate",
]
