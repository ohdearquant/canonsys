"""Identity domain phrases.

All identity verification and assessment operations:
- Risk assessment: assess_scope_risk_level
- Certificate authority: get_ca_level
- Assurance verification: verify_assurance_equivalent
- IdP posture: verify_idp_posture_attestation
- Request authentication: verify_request_source_authenticated
- Auth posture: verify_strong_auth_posture
- Gate: require_strong_auth
"""

from .assess_scope_risk_level import AssessScopeRiskLevelSpecs, assess_scope_risk_level
from .get_ca_level import GetCALevelSpecs, get_ca_level
from .require_strong_auth import RequireStrongAuthSpecs, require_strong_auth
from .verify_assurance_equivalent import (
    VerifyAssuranceEquivalentSpecs,
    verify_assurance_equivalent,
)
from .verify_idp_posture_attestation import (
    VerifyIdPPostureAttestationSpecs,
    verify_idp_posture_attestation,
)
from .verify_request_source_authenticated import (
    VerifyRequestSourceAuthenticatedSpecs,
    verify_request_source_authenticated,
)
from .verify_strong_auth_posture import (
    VerifyStrongAuthPostureSpecs,
    verify_strong_auth_posture,
)

__all__ = [
    # Specs classes (Pydantic BaseModels)
    "AssessScopeRiskLevelSpecs",
    "GetCALevelSpecs",
    "RequireStrongAuthSpecs",
    "VerifyAssuranceEquivalentSpecs",
    "VerifyIdPPostureAttestationSpecs",
    "VerifyRequestSourceAuthenticatedSpecs",
    "VerifyStrongAuthPostureSpecs",
    # Phrase functions - Risk assessment
    "assess_scope_risk_level",
    # Phrase functions - CA level
    "get_ca_level",
    # Phrase functions - Gate: strong auth
    "require_strong_auth",
    # Phrase functions - Assurance equivalence
    "verify_assurance_equivalent",
    # Phrase functions - IdP posture
    "verify_idp_posture_attestation",
    # Phrase functions - Request source auth
    "verify_request_source_authenticated",
    # Phrase functions - Auth posture
    "verify_strong_auth_posture",
]
