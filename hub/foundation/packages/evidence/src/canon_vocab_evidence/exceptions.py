"""Evidence domain exceptions.

These exceptions are raised by evidence actions and phrases when invariants are violated.
All inherit from EvidenceViolation (the domain's base exception from enforcement).

Regulatory context:
    - SOX Section 802: Document integrity and retention
    - FRCP Rule 37(e): ESI preservation duty
    - FRE 901: Authentication of evidence
    - ISO 27037: Digital evidence handling
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from canon.enforcement.exceptions import EvidenceViolation

if TYPE_CHECKING:
    from uuid import UUID

__all__ = [
    "CEPAlreadySealedError",
    # CEP exceptions
    "CEPNotFoundError",
    "CEPNotSealedError",
    "CEPSupersededError",
    "CEPTenantMismatchError",
    # Chain exceptions
    "ChainIntegrityError",
    "ChainNotFoundError",
    "ChainOfCustodyIncompleteError",
    # Evidence exceptions
    "EvidenceNotFoundError",
    "EvidenceTenantMismatchError",
    "GenesisEntryMissingError",
]


# =============================================================================
# CEP Exceptions
# =============================================================================


class CEPNotFoundError(EvidenceViolation):
    """CEP does not exist.

    Raised when: An operation requires a CEP that cannot be found.

    Regulatory basis:
    - FCRA Section 1681m: Pre-adverse action notice requires evidence
    - Employment law: Termination decisions require supporting evidence

    Phrase: cep_must_exist
    """

    default_regulation = "FCRA Section 1681m"
    default_message = "Certified Evidence Packet not found"

    __slots__ = ("cep_id",)

    def __init__(
        self,
        cep_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Initialize CEP not found error.

        Args:
            cep_id: UUID of the CEP that was not found.
            **kwargs: Additional arguments passed to parent.
        """
        self.cep_id = cep_id
        extra_context = kwargs.pop("context", None) or {}
        base_context = {"cep_id": str(cep_id)}
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"CEP {cep_id} not found",
            context=merged_context,
            **kwargs,
        )


class CEPNotSealedError(EvidenceViolation):
    """CEP is not in SEALED status.

    Raised when: An operation requires a sealed CEP but the CEP
    status is DRAFT, SUPERSEDED, or otherwise not SEALED.

    Regulatory basis:
    - FCRA Section 1681m: Pre-adverse action notice requires sealed evidence
    - Employment law: Termination decisions require sealed evidence packets
    - SOX Section 802: Document integrity for financial decisions

    Phrase: cep_must_be_sealed
    """

    default_regulation = "FCRA Section 1681m"
    default_message = "CEP must be sealed before use"

    __slots__ = ("cep_id", "current_status")

    def __init__(
        self,
        cep_id: UUID,
        current_status: str,
        **kwargs: Any,
    ) -> None:
        """Initialize CEP not sealed error.

        Args:
            cep_id: UUID of the CEP that is not sealed.
            current_status: Current status of the CEP (e.g., "DRAFT").
            **kwargs: Additional arguments passed to parent.
        """
        self.cep_id = cep_id
        self.current_status = current_status
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "cep_id": str(cep_id),
            "current_status": current_status,
            "required_status": "SEALED",
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"CEP {cep_id} has status '{current_status}' but must be SEALED",
            context=merged_context,
            **kwargs,
        )


class CEPAlreadySealedError(EvidenceViolation):
    """CEP is already sealed and cannot be modified.

    Raised when: Attempting to modify or re-seal a CEP that is already sealed.

    Regulatory basis:
    - SOX Section 802: Document integrity (sealed = immutable)
    - ISO 27001 A.12.4.1: Event logging integrity

    Phrase: sealed_cep_must_not_be_modified
    """

    default_regulation = "SOX Section 802"
    default_message = "CEP is already sealed and cannot be modified"

    __slots__ = ("cep_id",)

    def __init__(
        self,
        cep_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Initialize CEP already sealed error.

        Args:
            cep_id: UUID of the CEP that is already sealed.
            **kwargs: Additional arguments passed to parent.
        """
        self.cep_id = cep_id
        extra_context = kwargs.pop("context", None) or {}
        base_context = {"cep_id": str(cep_id), "current_status": "SEALED"}
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"CEP {cep_id} is already SEALED and cannot be modified",
            context=merged_context,
            **kwargs,
        )


class CEPSupersededError(EvidenceViolation):
    """CEP has been superseded by a newer version.

    Raised when: Attempting to use a CEP that has been superseded.

    Regulatory basis:
    - SOX Section 802: Use current, valid documents
    - Audit requirements: Reference authoritative versions

    Phrase: cep_must_not_be_superseded
    """

    default_regulation = "SOX Section 802"
    default_message = "CEP has been superseded"

    __slots__ = ("cep_id", "superseded_by_id")

    def __init__(
        self,
        cep_id: UUID,
        superseded_by_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Initialize CEP superseded error.

        Args:
            cep_id: UUID of the superseded CEP.
            superseded_by_id: UUID of the CEP that supersedes this one.
            **kwargs: Additional arguments passed to parent.
        """
        self.cep_id = cep_id
        self.superseded_by_id = superseded_by_id
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "cep_id": str(cep_id),
            "superseded_by_id": str(superseded_by_id),
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"CEP {cep_id} has been superseded by {superseded_by_id}",
            context=merged_context,
            **kwargs,
        )


class CEPTenantMismatchError(EvidenceViolation):
    """CEP tenant does not match request context.

    Raised when: A CEP is accessed with a different tenant context.

    Regulatory basis:
    - Multi-tenant isolation requirements
    - Data protection: tenant boundary enforcement

    Phrase: cep_tenant_must_match
    """

    default_regulation = "SOC 2 CC6.1"
    default_message = "CEP tenant mismatch"

    __slots__ = ("cep_id", "cep_tenant_id", "request_tenant_id")

    def __init__(
        self,
        cep_id: UUID,
        cep_tenant_id: UUID,
        request_tenant_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Initialize CEP tenant mismatch error.

        Args:
            cep_id: UUID of the CEP.
            cep_tenant_id: Tenant ID of the CEP.
            request_tenant_id: Tenant ID from the request context.
            **kwargs: Additional arguments passed to parent.
        """
        self.cep_id = cep_id
        self.cep_tenant_id = cep_tenant_id
        self.request_tenant_id = request_tenant_id
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "cep_id": str(cep_id),
            "cep_tenant_id": str(cep_tenant_id),
            "request_tenant_id": str(request_tenant_id),
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"CEP {cep_id} belongs to tenant {cep_tenant_id}, "
            f"but request is from tenant {request_tenant_id}",
            context=merged_context,
            **kwargs,
        )


# =============================================================================
# Evidence Exceptions
# =============================================================================


class EvidenceNotFoundError(EvidenceViolation):
    """Evidence record does not exist.

    Raised when: An operation requires evidence that cannot be found.

    Regulatory basis:
    - FCRA Section 1681m: Evidence must exist for adverse actions
    - FRE 901: Authentication requires existing evidence

    Phrase: evidence_must_exist
    """

    default_regulation = "FCRA Section 1681m"
    default_message = "Evidence not found"

    __slots__ = ("evidence_id",)

    def __init__(
        self,
        evidence_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Initialize evidence not found error.

        Args:
            evidence_id: UUID of the evidence that was not found.
            **kwargs: Additional arguments passed to parent.
        """
        self.evidence_id = evidence_id
        extra_context = kwargs.pop("context", None) or {}
        base_context = {"evidence_id": str(evidence_id)}
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Evidence {evidence_id} not found",
            context=merged_context,
            **kwargs,
        )


class EvidenceTenantMismatchError(EvidenceViolation):
    """Evidence tenant does not match request context.

    Raised when: Evidence is accessed with a different tenant context.

    Regulatory basis:
    - Multi-tenant isolation requirements
    - Data protection: tenant boundary enforcement

    Phrase: evidence_tenant_must_match
    """

    default_regulation = "SOC 2 CC6.1"
    default_message = "Evidence tenant mismatch"

    __slots__ = ("evidence_id", "evidence_tenant_id", "request_tenant_id")

    def __init__(
        self,
        evidence_id: UUID,
        evidence_tenant_id: UUID,
        request_tenant_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Initialize evidence tenant mismatch error.

        Args:
            evidence_id: UUID of the evidence.
            evidence_tenant_id: Tenant ID of the evidence.
            request_tenant_id: Tenant ID from the request context.
            **kwargs: Additional arguments passed to parent.
        """
        self.evidence_id = evidence_id
        self.evidence_tenant_id = evidence_tenant_id
        self.request_tenant_id = request_tenant_id
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "evidence_id": str(evidence_id),
            "evidence_tenant_id": str(evidence_tenant_id),
            "request_tenant_id": str(request_tenant_id),
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Evidence {evidence_id} belongs to tenant {evidence_tenant_id}, "
            f"but request is from tenant {request_tenant_id}",
            context=merged_context,
            **kwargs,
        )


# =============================================================================
# Chain Exceptions
# =============================================================================


class ChainIntegrityError(EvidenceViolation):
    """Evidence chain integrity verification failed.

    Raised when: verify_chain finds a hash mismatch in the evidence chain,
    indicating tampering or corruption.

    Regulatory basis:
    - FRCP Rule 37(e): ESI preservation duty
    - FRE 901: Authentication of evidence
    - ISO 27037: Digital evidence handling

    Phrase: chain_must_be_intact
    """

    default_regulation = "FRCP Rule 37(e)"
    default_message = "Evidence chain integrity compromised"

    __slots__ = ("actual_hash", "break_sequence", "chain_id", "expected_hash")

    def __init__(
        self,
        chain_id: UUID,
        break_sequence: int,
        expected_hash: str,
        actual_hash: str,
        **kwargs: Any,
    ) -> None:
        """Initialize chain integrity error.

        Args:
            chain_id: UUID of the evidence chain.
            break_sequence: Sequence number where the break occurred.
            expected_hash: Hash value that was expected.
            actual_hash: Hash value that was found.
            **kwargs: Additional arguments passed to parent.
        """
        self.chain_id = chain_id
        self.break_sequence = break_sequence
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "chain_id": str(chain_id),
            "break_sequence": break_sequence,
            "expected_hash": expected_hash,
            "actual_hash": actual_hash,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Chain {chain_id} integrity failed at sequence {break_sequence}: "
            f"expected {expected_hash[:12]}..., got {actual_hash[:12]}...",
            context=merged_context,
            **kwargs,
        )


class ChainNotFoundError(EvidenceViolation):
    """Evidence chain does not exist for resource.

    Raised when: verify_chain or chain_evidence cannot find the chain.

    Regulatory basis:
    - FRE 901: Evidence must have chain of custody
    - ISO 27037: Digital evidence requires chain documentation

    Phrase: chain_must_exist
    """

    default_regulation = "FRE 901"
    default_message = "Evidence chain not found"

    __slots__ = ("resource_id", "resource_type")

    def __init__(
        self,
        resource_id: UUID,
        resource_type: str = "evidence",
        **kwargs: Any,
    ) -> None:
        """Initialize chain not found error.

        Args:
            resource_id: UUID of the resource missing a chain.
            resource_type: Type of the resource (e.g., "evidence").
            **kwargs: Additional arguments passed to parent.
        """
        self.resource_id = resource_id
        self.resource_type = resource_type
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "resource_id": str(resource_id),
            "resource_type": resource_type,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"No chain found for {resource_type} {resource_id}",
            context=merged_context,
            **kwargs,
        )


class ChainOfCustodyIncompleteError(EvidenceViolation):
    """Chain of custody is incomplete.

    Raised when: require_chain_of_custody_complete finds gaps in custody.

    Regulatory basis:
    - FRE 901: Authentication requires complete chain
    - FRCP 34: Production of documents requirements
    - ISO 27037: Digital evidence handling standards

    Phrase: chain_of_custody_must_be_complete
    """

    default_regulation = "FRE 901"
    default_message = "Chain of custody is incomplete"

    __slots__ = ("entries_count", "evidence_id", "status")

    def __init__(
        self,
        evidence_id: UUID,
        entries_count: int,
        status: str,
        **kwargs: Any,
    ) -> None:
        """Initialize chain of custody incomplete error.

        Args:
            evidence_id: UUID of the evidence with incomplete chain.
            entries_count: Number of entries found in the chain.
            status: Current chain status (e.g., "incomplete", "broken").
            **kwargs: Additional arguments passed to parent.
        """
        self.evidence_id = evidence_id
        self.entries_count = entries_count
        self.status = status
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "evidence_id": str(evidence_id),
            "entries_count": entries_count,
            "chain_status": status,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Chain of custody for evidence {evidence_id} is {status} ({entries_count} entries)",
            context=merged_context,
            **kwargs,
        )


class GenesisEntryMissingError(EvidenceViolation):
    """Evidence chain is missing genesis (first) entry.

    Raised when: Chain verification finds the chain does not start at sequence 0.

    Regulatory basis:
    - FRE 901: Evidence must have documented origin
    - ISO 27037: Digital evidence requires collection documentation

    Phrase: genesis_entry_must_exist
    """

    default_regulation = "FRE 901"
    default_message = "Chain genesis entry missing"

    __slots__ = ("first_sequence", "resource_id")

    def __init__(
        self,
        resource_id: UUID,
        first_sequence: int,
        **kwargs: Any,
    ) -> None:
        """Initialize genesis entry missing error.

        Args:
            resource_id: UUID of the resource with missing genesis.
            first_sequence: The first sequence number found (should be 0).
            **kwargs: Additional arguments passed to parent.
        """
        self.resource_id = resource_id
        self.first_sequence = first_sequence
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "resource_id": str(resource_id),
            "expected_first_sequence": 0,
            "actual_first_sequence": first_sequence,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Chain for {resource_id} missing genesis: starts at sequence {first_sequence}",
            context=merged_context,
            **kwargs,
        )
