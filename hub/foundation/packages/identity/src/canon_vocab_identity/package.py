"""Identity vocabulary package metadata."""

from canon.hub.package import VocabularyPackage

IDENTITY = VocabularyPackage(
    name="identity",
    description="Identity assurance, authentication posture, IdP attestation, and scope risk assessment.",
    feature_names=frozenset(
        {
            "assess_scope_risk_level",
            "get_ca_level",
            "verify_assurance_equivalent",
            "verify_idp_posture_attestation",
            "verify_request_source_authenticated",
            "verify_strong_auth_posture",
        }
    ),
    schema_names=frozenset(
        {
            "AALLevel",
            "AuthPosture",
            "RiskLevel",
        }
    ),
    regulatory_basis=("NIST SP 800-63B",),
    version="2026.01",
    domain_module="canon_vocab_identity",
)
