"""Core compliance features.

Foundational features for charter management, overrides, audit verification,
and general-purpose compliance gates.

Regulatory context:
    - SOX Section 404 (Internal controls)
    - SOC 2 (Control environment)
    - ISO 27001 (Information security)
    - BSA/AML (Bank Secrecy Act)
    - PCI DSS (Payment Card Industry)
    - EU AI Act (AI governance)
    - FCRA (Fair Credit Reporting Act)
    - GDPR (General Data Protection Regulation)

Structure:
    - types/: Type definitions (dataclasses, enums)
    - phrases/: Feature implementations using @phrase pattern
    - exceptions.py: Exception re-exports
    - service.py: CoreService with evidence emission

Usage:
    from canon_vocab_core import (
        # Phrases
        activate_charter,
        derive_amount_band,
        verify_audit_complete,
        # Types
        AuditStatus,
        BreakGlassCertificate,
        # Exceptions
        RequirementNotMetError,
        ValueExceedsLimitError,
        # Service
        CoreService,
        # Package metadata
        CORE,
    )
"""

# Exceptions
from .exceptions import RequirementNotMetError, ValueExceedsLimitError

# Package metadata
from .package import CORE

# Phrases (Specs classes + phrase functions)
from .phrases import (
    ActivateCharterSpecs,  # Specs classes; Phrase functions
    CharterSummary,
    DeriveAmountBandSpecs,
    GetCharterByIdSpecs,
    GetCharterHistorySpecs,
    InvokeBreakGlassSpecs,
    InvokeExecutiveOverrideSpecs,
    RatifyCharterSpecs,
    RequireAlternativeReviewedSpecs,
    RequireFraudScreeningPassSpecs,
    RequireProvenanceDocumentedSpecs,
    RequireSOXComplianceReviewSpecs,
    RequireValueWithinLimitSpecs,
    ResolveCharterSpecs,
    VerifyAuditCompleteSpecs,
    VerifyAuditCurrentSpecs,
    VerifyEvidenceFreshnessSpecs,
    VerifySignerIdentitySpecs,
    VerifyValuesMatchSpecs,
    activate_charter,
    derive_amount_band,
    get_charter_by_id,
    get_charter_history,
    invoke_break_glass,
    invoke_executive_override,
    ratify_charter,
    require_alternative_reviewed,
    require_fraud_screening_pass,
    require_provenance_documented,
    require_sox_compliance_review,
    require_value_within_limit,
    resolve_charter,
    verify_audit_complete,
    verify_audit_current,
    verify_evidence_freshness,
    verify_signer_identity,
    verify_values_match,
)

# Service
from .service import CoreService

# Types
from .types import (
    AlternativeReviewStatus,
    AmountBandConfig,
    AmountBandResult,
    AuditStatus,
    BreakGlassCertificate,
    BreakGlassReason,
    ExecutiveOverride,
    FraudScreeningResult,
    FreshnessResult,
    NumericValue,
    OverrideAuthority,
    RequireAlternativeReviewedResult,
    RequireFraudScreeningPassResult,
    RequireProvenanceDocumentedResult,
    RequireSOXComplianceReviewResult,
    Signatory,
    SignerIdentityResult,
    SOXReviewStatus,
    ValuesMatchResult,
    ValueWithinLimitResult,
    VerifyAuditCompleteResult,
    VerifyAuditCurrentResult,
)

__all__ = [
    # Package metadata
    "CORE",
    # Service
    "CoreService",
    # Specs classes (Pydantic BaseModels for @phrase pattern)
    "ActivateCharterSpecs",
    "CharterSummary",
    "DeriveAmountBandSpecs",
    "GetCharterByIdSpecs",
    "GetCharterHistorySpecs",
    "InvokeBreakGlassSpecs",
    "InvokeExecutiveOverrideSpecs",
    "RatifyCharterSpecs",
    "RequireAlternativeReviewedSpecs",
    "RequireFraudScreeningPassSpecs",
    "RequireProvenanceDocumentedSpecs",
    "RequireSOXComplianceReviewSpecs",
    "RequireValueWithinLimitSpecs",
    "ResolveCharterSpecs",
    "VerifyAuditCompleteSpecs",
    "VerifyAuditCurrentSpecs",
    "VerifyEvidenceFreshnessSpecs",
    "VerifySignerIdentitySpecs",
    "VerifyValuesMatchSpecs",
    # Types - Requirements
    "AlternativeReviewStatus",
    "AmountBandConfig",
    "AmountBandResult",
    # Types - Audit
    "AuditStatus",
    "BreakGlassCertificate",
    # Types - Override
    "BreakGlassReason",
    "ExecutiveOverride",
    "FraudScreeningResult",
    "FreshnessResult",
    # Types - Primitives
    "NumericValue",
    "OverrideAuthority",
    "RequireAlternativeReviewedResult",
    "RequireFraudScreeningPassResult",
    "RequireProvenanceDocumentedResult",
    "RequireSOXComplianceReviewResult",
    # Exceptions
    "RequirementNotMetError",
    "SOXReviewStatus",
    # Types - Charter
    "Signatory",
    "SignerIdentityResult",
    "ValueExceedsLimitError",
    "ValueWithinLimitResult",
    "ValuesMatchResult",
    "VerifyAuditCompleteResult",
    "VerifyAuditCurrentResult",
    # Phrase functions - Charter
    "activate_charter",
    # Phrase functions - Primitives
    "derive_amount_band",
    "get_charter_by_id",
    "get_charter_history",
    # Phrase functions - Override
    "invoke_break_glass",
    "invoke_executive_override",
    "ratify_charter",
    # Phrase functions - Requirements
    "require_alternative_reviewed",
    "require_fraud_screening_pass",
    "require_provenance_documented",
    "require_sox_compliance_review",
    "require_value_within_limit",
    "resolve_charter",
    # Phrase functions - Audit
    "verify_audit_complete",
    "verify_audit_current",
    "verify_evidence_freshness",
    "verify_signer_identity",
    "verify_values_match",
]
