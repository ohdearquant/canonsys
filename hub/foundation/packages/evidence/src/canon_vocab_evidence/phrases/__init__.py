"""Evidence phrase features.

Features for evidence management including chaining, supersession,
Certified Evidence Packets (CEPs), and case integrity verification.

Regulatory context:
    - FCRA (Evidence for adverse actions)
    - EU AI Act (Audit trail requirements)
    - FRE 901 (Authentication of evidence)
    - ISO 27037 (Digital evidence handling)
"""

from .chain_evidence import (
    ChainEvidenceSpecs,
    CreateGenesisEntrySpecs,
    chain_evidence,
    create_genesis_entry,
)
from .compute_evidence_hash import ComputeEvidenceHashSpecs, compute_evidence_hash
from .create_cep import CEP, CEPStatus, CEPType, CreateCEPSpecs, create_cep
from .emit_chained_evidence import EmitChainedEvidenceSpecs, emit_chained_evidence
from .get_case_evidence import GetCaseEvidenceSpecs, get_case_evidence
from .get_case_history import GetCaseHistorySpecs, TimelineEntry, get_case_history
from .get_evidence_timeline import (
    GetEvidenceTimelineSpecs,
    TimelineEvent,
    get_evidence_timeline,
)
from .lock_evidence_chain import (
    ChainAlreadyLockedError,
    LockEvidenceChainSpecs,
    lock_evidence_chain,
)
from .require_cep_hash_match import (
    CEPHashMismatchError,
    RequireCEPHashMatchSpecs,
    require_cep_hash_match,
)
from .require_chain_of_custody_complete import (
    RequireChainOfCustodyCompleteSpecs,
    require_chain_of_custody_complete,
)
from .require_evidence_not_superseded import (
    EvidenceSupersededError,
    RequireEvidenceNotSupersededSpecs,
    require_evidence_not_superseded,
)
from .require_evidence_present import (
    EvidenceMissingError,
    RequireEvidencePresentSpecs,
    require_evidence_present,
)
from .save_evidence import SaveEvidenceSpecs, save_evidence
from .seal_cep import SealCEPSpecs, seal_cep
from .supersede_evidence import SupersedeEvidenceSpecs, supersede_evidence
from .verify_case_integrity import VerifyCaseIntegritySpecs, verify_case_integrity
from .verify_cep_not_expired import (
    CEP_VALIDITY_PERIODS,
    VerifyCEPNotExpiredSpecs,
    verify_cep_not_expired,
)
from .verify_cep_reference import VerifyCEPReferenceSpecs, verify_cep_reference
from .verify_cep_sealed import VerifyCEPSealedSpecs, verify_cep_sealed
from .verify_chain import VerifyChainSpecs, verify_chain
from .verify_chain_of_custody_complete import (
    CustodyChainStatus,
    VerifyChainOfCustodyCompleteSpecs,
    verify_chain_of_custody_complete,
)
from .verify_evidence_chain import VerifyEvidenceChainSpecs, verify_evidence_chain
from .verify_evidence_integrity import (
    VerifyEvidenceIntegritySpecs,
    verify_evidence_integrity,
)

__all__ = [
    # Domain types
    "CEP",
    "CEPStatus",
    "CEPType",
    # Specs classes (Pydantic BaseModels)
    "ChainEvidenceSpecs",
    "ComputeEvidenceHashSpecs",
    "EmitChainedEvidenceSpecs",
    "CreateCEPSpecs",
    "CreateGenesisEntrySpecs",
    "CustodyChainStatus",
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
    "TimelineEntry",
    "TimelineEvent",
    "VerifyCaseIntegritySpecs",
    "VerifyCEPNotExpiredSpecs",
    "VerifyCEPReferenceSpecs",
    "VerifyCEPSealedSpecs",
    "VerifyChainOfCustodyCompleteSpecs",
    "VerifyChainSpecs",
    "VerifyEvidenceChainSpecs",
    "VerifyEvidenceIntegritySpecs",
    # Phrase functions
    "chain_evidence",
    "compute_evidence_hash",
    "emit_chained_evidence",
    "create_cep",
    "create_genesis_entry",
    "get_case_evidence",
    "get_case_history",
    "get_evidence_timeline",
    "lock_evidence_chain",
    "require_chain_of_custody_complete",
    "require_cep_hash_match",
    "require_evidence_not_superseded",
    "require_evidence_present",
    "save_evidence",
    "seal_cep",
    "supersede_evidence",
    "verify_case_integrity",
    "verify_cep_not_expired",
    "verify_cep_reference",
    "verify_cep_sealed",
    "verify_chain",
    "verify_chain_of_custody_complete",
    "verify_evidence_chain",
    "verify_evidence_integrity",
    # Error classes
    "CEP_VALIDITY_PERIODS",
    "CEPHashMismatchError",
    "ChainAlreadyLockedError",
    "EvidenceMissingError",
    "EvidenceSupersededError",
]
