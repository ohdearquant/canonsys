"""Evidence domain: immutable audit artifacts and hash-linked chains.

Evidence: Proof artifacts that justify decisions (for court)
ChainEntry: Hash-linked event records forming tamper-evident audit trail

All are immutable entities - corrections use supersession pattern
(new record pointing to original, original unchanged).

Note: DecisionCertificate is in canon_vocab_certification package.
"""

from .chain import ChainEntry, ChainEntryContent
from .evidence import Evidence, EvidenceContent

__all__ = (
    "ChainEntry",
    "ChainEntryContent",
    "Evidence",
    "EvidenceContent",
)
