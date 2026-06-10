"""Identity feature - vertical slice for identity and authentication verification.

This module provides the complete identity domain implementation:
- Types: AALLevel, AuthPosture, RiskLevel
- Phrases: assess_scope_risk_level, get_ca_level, verify_* functions
- Exceptions: AuthPostureInsufficientError, AssuranceLevelInsufficientError, etc.

Regulatory context:
    - NIST SP 800-63 (Digital Identity Guidelines)
    - NIST SP 800-63B (Authenticator and Verifier Requirements)
    - NIST SP 800-63C (Federation and Assertions)
    - SOC 2 CC6.1 (Logical access controls)
    - GDPR Art. 32 (Security of processing)
    - FedRAMP (Government auth requirements)

Usage:
    from canon_vocab_identity import (
        # Types
        AALLevel,
        AuthPosture,
        RiskLevel,
        # Service
        IdentityService,
        # Phrases
        verify_strong_auth_posture,
        verify_assurance_equivalent,
        assess_scope_risk_level,
        # Specs
        VerifyStrongAuthPostureSpecs,
        VerifyAssuranceEquivalentSpecs,
        AssessScopeRiskLevelSpecs,
        # Package metadata
        IDENTITY,
    )
"""

# Package metadata
# Exceptions
from .exceptions import (
    AssuranceLevelInsufficientError,
    AuthPostureInsufficientError,
    IdPPostureInsufficientError,
    RequestNotAuthenticatedError,
)
from .package import IDENTITY

# Phrases (includes all verification and assessment functions)
from .phrases import (
    AssessScopeRiskLevelSpecs,
    GetCALevelSpecs,
    VerifyAssuranceEquivalentSpecs,
    VerifyIdPPostureAttestationSpecs,
    VerifyRequestSourceAuthenticatedSpecs,
    VerifyStrongAuthPostureSpecs,
    assess_scope_risk_level,
    get_ca_level,
    verify_assurance_equivalent,
    verify_idp_posture_attestation,
    verify_request_source_authenticated,
    verify_strong_auth_posture,
)

# Service
from .service import IdentityService

# Types
from .types import AALLevel, AuthPosture, RiskLevel

__all__ = [
    # Package metadata
    "IDENTITY",
    # Service
    "IdentityService",
    # Types
    "AALLevel",
    "AuthPosture",
    "RiskLevel",
    # Exceptions
    "AssuranceLevelInsufficientError",
    "AuthPostureInsufficientError",
    "IdPPostureInsufficientError",
    "RequestNotAuthenticatedError",
    # Specs classes (Pydantic BaseModels)
    "AssessScopeRiskLevelSpecs",
    "GetCALevelSpecs",
    "VerifyAssuranceEquivalentSpecs",
    "VerifyIdPPostureAttestationSpecs",
    "VerifyRequestSourceAuthenticatedSpecs",
    "VerifyStrongAuthPostureSpecs",
    # Phrases - Risk assessment
    "assess_scope_risk_level",
    # Phrases - CA level
    "get_ca_level",
    # Phrases - Assurance equivalence
    "verify_assurance_equivalent",
    # Phrases - IdP posture
    "verify_idp_posture_attestation",
    # Phrases - Request source auth
    "verify_request_source_authenticated",
    # Phrases - Auth posture
    "verify_strong_auth_posture",
]
