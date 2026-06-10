"""Verify dataset snapshot integrity.

Detects dataset integrity drift from a baseline snapshot.

Regulatory context:
    - SOC 2 CC6.7: Transmission and removal restrictions
    - ISO 27001 A.12.1.2: Change management
    - GDPR Art. 5(1)(f): Integrity and confidentiality
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyDatasetSnapshotSpecs", "verify_dataset_snapshot_match"]


class VerifyDatasetSnapshotSpecs(BaseModel):
    """Specs for verify dataset snapshot phrase."""

    # inputs
    dataset_id: UUID
    expected_hash: str
    current_records: list[str] | None = None
    # outputs
    matches: bool | None = None
    current_hash: str | None = None


def _compute_dataset_hash(records: list[str]) -> str:
    """Compute SHA256 hash of sorted dataset records."""
    sorted_records = sorted(records)
    content = "\n".join(sorted_records)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@canon_phrase(
    Operable.from_structure(VerifyDatasetSnapshotSpecs),
    inputs={"dataset_id", "expected_hash", "current_records"},
    outputs={"matches", "dataset_id", "expected_hash", "current_hash"},
)
async def verify_dataset_snapshot_match(
    options: VerifyDatasetSnapshotSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify dataset contents match a baseline snapshot.

    Computes hash of current dataset records and compares against the expected
    hash from a baseline snapshot. Used to detect unauthorized modifications
    to data that could affect scope integrity or compliance posture.

    Regulatory Citations:
        - SOC 2 CC6.7: The entity restricts the transmission, movement, and
          removal of information to authorized internal and external users.
          Dataset integrity must be verified.
        - ISO 27001 A.12.1.2: Changes to organization, business processes,
          information processing facilities shall be controlled.
        - GDPR Art. 5(1)(f): Personal data shall be processed in a manner
          that ensures integrity using appropriate technical measures.

    Args:
        options: Dataset snapshot verification options.
        ctx: Request context (tenant, actor).

    Returns:
        dict with matches, dataset_id, expected_hash, current_hash.
    """
    current_records = options.current_records or []
    current_hash = _compute_dataset_hash(current_records)

    return {
        "matches": current_hash == options.expected_hash,
        "dataset_id": options.dataset_id,
        "expected_hash": options.expected_hash,
        "current_hash": current_hash,
    }
