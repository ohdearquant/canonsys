"""Evidence vocabulary package metadata."""

from canon.hub.package import VocabularyPackage

EVIDENCE = VocabularyPackage(
    name="evidence",
    description="Evidence creation, chaining, sealing, custody verification, integrity, and timeline.",
    feature_names=frozenset(
        {
            # Chain operations
            "chain_evidence",
            "create_genesis_entry",
            "lock_evidence_chain",
            # CEP operations
            "create_cep",
            "seal_cep",
            "verify_cep_reference",
            "verify_cep_sealed",
            "verify_cep_not_expired",
            "require_cep_hash_match",
            # Evidence operations
            "save_evidence",
            "supersede_evidence",
            "compute_evidence_hash",
            "verify_evidence_integrity",
            # Requirement (gate) phrases
            "require_chain_of_custody_complete",
            "require_evidence_not_superseded",
            "require_evidence_present",
            # Query phrases
            "get_case_evidence",
            "get_case_history",
            "get_evidence_timeline",
            # Verification phrases
            "verify_case_integrity",
            "verify_chain",
            "verify_chain_of_custody_complete",
        }
    ),
    schema_names=frozenset(
        {
            "CEP",
            "CEPStatus",
            "CEPType",
            "ChainEventType",
            "CustodyChainStatus",
            "TimelineEntry",
            "TimelineEvent",
            # Specs classes
            "ChainEvidenceSpecs",
            "ComputeEvidenceHashSpecs",
            "CreateCEPSpecs",
            "CreateGenesisEntrySpecs",
            "GetCaseEvidenceSpecs",
            "GetCaseHistorySpecs",
            "GetEvidenceTimelineSpecs",
            "LockEvidenceChainSpecs",
            "RequireChainOfCustodyCompleteSpecs",
            "RequireCEPHashMatchSpecs",
            "RequireEvidenceNotSupersededSpecs",
            "RequireEvidencePresentSpecs",
            "SaveEvidenceSpecs",
            "SealCEPSpecs",
            "SupersedeEvidenceSpecs",
            "VerifyCaseIntegritySpecs",
            "VerifyCEPNotExpiredSpecs",
            "VerifyCEPReferenceSpecs",
            "VerifyCEPSealedSpecs",
            "VerifyChainOfCustodyCompleteSpecs",
            "VerifyChainSpecs",
            "VerifyEvidenceIntegritySpecs",
        }
    ),
    regulatory_basis=(
        "FRE 901",
        "ISO 27037",
        "FCRA Section 1681m",
        "SOX Section 802",
        "FRCP Rule 37(e)",
    ),
    version="2026.01",
    domain_module="canon_vocab_evidence",
)
