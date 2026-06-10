"""Verify group membership snapshot.

Detects group membership drift from a baseline snapshot.

Regulatory context:
    - SOC 2 CC6.1: Logical access security
    - SOC 2 CC6.2: User registration and authorization
    - ISO 27001 A.9.2.5: Review of user access rights
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

__all__ = ["VerifyGroupMembershipSnapshotSpecs", "verify_group_membership_snapshot"]


class VerifyGroupMembershipSnapshotSpecs(BaseModel):
    """Specs for verify group membership snapshot phrase."""

    # inputs
    group_id: UUID
    expected_hash: str
    current_members: list[str] | None = None
    baseline_member_count: int | None = None
    # outputs
    matches: bool | None = None
    current_hash: str | None = None
    member_delta: int | None = None


def _compute_membership_hash(members: list[str]) -> str:
    """Compute SHA256 hash of sorted member list."""
    sorted_members = sorted(members)
    content = ",".join(sorted_members)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@canon_phrase(
    Operable.from_structure(VerifyGroupMembershipSnapshotSpecs),
    inputs={"group_id", "expected_hash", "current_members", "baseline_member_count"},
    outputs={"matches", "group_id", "expected_hash", "current_hash", "member_delta"},
)
async def verify_group_membership_snapshot(
    options: VerifyGroupMembershipSnapshotSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify group membership matches a baseline snapshot.

    Computes hash of current group members and compares against the expected
    hash from a baseline snapshot. Used to detect unauthorized membership
    changes that could expand or contract access scope.

    Regulatory Citations:
        - SOC 2 CC6.1: The entity implements logical access security software
          and infrastructure. Group membership changes must be controlled.
        - SOC 2 CC6.2: Prior to issuing system credentials, the entity
          registers and authorizes new users. Membership drift indicates
          potential control bypass.
        - ISO 27001 A.9.2.5: Asset owners shall review users' access rights
          at regular intervals. Snapshot verification enables this review.

    Args:
        options: Group snapshot verification options.
        ctx: Request context (tenant, actor).

    Returns:
        dict with matches, group_id, expected_hash, current_hash, member_delta.
    """
    current_members = options.current_members or []
    current_hash = _compute_membership_hash(current_members)

    matches = current_hash == options.expected_hash

    member_delta = 0
    if options.baseline_member_count is not None:
        member_delta = len(current_members) - options.baseline_member_count

    return {
        "matches": matches,
        "group_id": options.group_id,
        "expected_hash": options.expected_hash,
        "current_hash": current_hash,
        "member_delta": member_delta,
    }
