"""Evidence feature - foundation package for compliance evidence management.

This is a **foundation package** that other domain packages depend on for
audit trail operations. The following packages import from evidence:
- ai_governance (save_evidence)
- timing (save_evidence, supersede_evidence)
- workflow (save_evidence)

This module provides the complete evidence domain implementation:
- Types: CEPStatus, CEPType, CustodyChainStatus, ChainEventType
- Phrases: create_cep, seal_cep, chain_evidence, verify_chain, etc.
- Exceptions: CEPNotFoundError, ChainIntegrityError, etc.
- Service: EvidenceService

Usage:
    from canon_vocab_evidence import (
        # Types
        CEPStatus,
        CEPType,
        CustodyChainStatus,
        # Phrases
        create_cep,
        seal_cep,
        verify_chain,
        # Cross-cutting (used by other packages)
        save_evidence,
        supersede_evidence,
        # Specs
        CreateCEPSpecs,
        SealCEPSpecs,
        VerifyChainSpecs,
        # Exceptions
        CEPNotFoundError,
        ChainIntegrityError,
        # Package metadata
        EVIDENCE,
    )
"""

# Phrases (from phrases/__init__.py)
# Exceptions
from .exceptions import (
    CEPAlreadySealedError,
    CEPNotFoundError,
    CEPNotSealedError,
    CEPSupersededError,
    CEPTenantMismatchError,
    ChainIntegrityError,
    ChainNotFoundError,
    ChainOfCustodyIncompleteError,
    EvidenceNotFoundError,
    EvidenceTenantMismatchError,
    GenesisEntryMissingError,
)

# Package metadata
from .package import EVIDENCE
from .phrases import (
    CEP,  # Domain types; Specs classes; Phrase functions
    CEPStatus,
    CEPType,
    ChainEvidenceSpecs,
    CreateCEPSpecs,
    CreateGenesisEntrySpecs,
    CustodyChainStatus,
    EmitChainedEvidenceSpecs,
    GetCaseEvidenceSpecs,
    GetCaseHistorySpecs,
    RequireChainOfCustodyCompleteSpecs,
    SaveEvidenceSpecs,
    SealCEPSpecs,
    SupersedeEvidenceSpecs,
    TimelineEntry,
    VerifyCaseIntegritySpecs,
    VerifyCEPReferenceSpecs,
    VerifyChainOfCustodyCompleteSpecs,
    VerifyChainSpecs,
    VerifyEvidenceChainSpecs,
    chain_evidence,
    create_cep,
    create_genesis_entry,
    emit_chained_evidence,
    get_case_evidence,
    get_case_history,
    require_chain_of_custody_complete,
    save_evidence,
    seal_cep,
    supersede_evidence,
    verify_case_integrity,
    verify_cep_reference,
    verify_chain,
    verify_chain_of_custody_complete,
    verify_evidence_chain,
)

# Service
from .service import EvidenceService

# Types (from types/__init__.py - re-export for convenience)
from .types import (
    CEPStatus as CEPStatusType,
    CEPType as CEPTypeEnum,
    ChainEventType,
    CustodyChainStatus as CustodyChainStatusType,
)

__all__ = [
    # Domain types
    "CEP",
    # Exceptions - CEP
    "CEPAlreadySealedError",
    "CEPNotFoundError",
    "CEPNotSealedError",
    "CEPStatus",
    "CEPStatusType",
    "CEPSupersededError",
    "CEPTenantMismatchError",
    "CEPType",
    "CEPTypeEnum",
    "ChainEventType",
    # Specs classes
    "ChainEvidenceSpecs",
    "EmitChainedEvidenceSpecs",
    # Exceptions - Chain
    "ChainIntegrityError",
    "ChainNotFoundError",
    "ChainOfCustodyIncompleteError",
    "CreateCEPSpecs",
    "CreateGenesisEntrySpecs",
    "CustodyChainStatus",
    "CustodyChainStatusType",
    # Package metadata
    "EVIDENCE",
    # Exceptions - Evidence
    "EvidenceNotFoundError",
    # Service
    "EvidenceService",
    "EvidenceTenantMismatchError",
    "GenesisEntryMissingError",
    "GetCaseEvidenceSpecs",
    "GetCaseHistorySpecs",
    "RequireChainOfCustodyCompleteSpecs",
    "SaveEvidenceSpecs",
    "SealCEPSpecs",
    "SupersedeEvidenceSpecs",
    "TimelineEntry",
    "VerifyCEPReferenceSpecs",
    "VerifyCaseIntegritySpecs",
    "VerifyChainOfCustodyCompleteSpecs",
    "VerifyChainSpecs",
    "VerifyEvidenceChainSpecs",
    # Phrase functions
    "chain_evidence",
    "emit_chained_evidence",
    "create_cep",
    "create_genesis_entry",
    "get_case_evidence",
    "get_case_history",
    "require_chain_of_custody_complete",
    "save_evidence",
    "seal_cep",
    "supersede_evidence",
    "verify_case_integrity",
    "verify_cep_reference",
    "verify_chain",
    "verify_chain_of_custody_complete",
    "verify_evidence_chain",
]
