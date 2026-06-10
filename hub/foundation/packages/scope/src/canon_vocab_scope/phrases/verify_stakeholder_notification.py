"""Verify stakeholder notification completeness.

Ensures all stakeholders in scope have been properly notified.

Regulatory context:
    - GDPR Art. 13/14: Data subjects must be informed of processing
    - WARN Act: Employee notification requirements
    - SOC 2 CC2.2: Communication of information
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = [
    "VerifyStakeholderNotificationSpecs",
    "verify_stakeholder_notification_complete",
]


class VerifyStakeholderNotificationSpecs(BaseModel):
    """Specs for verify stakeholder notification phrase."""

    # inputs
    manifest_id: UUID
    notification_log_id: UUID
    required_targets: list[str] | None = None
    notified_targets: list[str] | None = None
    # outputs
    complete: bool | None = None
    notified_count: int | None = None
    required_count: int | None = None
    missing: tuple[str, ...] | None = None


@canon_phrase(
    Operable.from_structure(VerifyStakeholderNotificationSpecs),
    inputs={
        "manifest_id",
        "notification_log_id",
        "required_targets",
        "notified_targets",
    },
    outputs={"complete", "manifest_id", "notified_count", "required_count", "missing"},
)
async def verify_stakeholder_notification_complete(
    options: VerifyStakeholderNotificationSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify all stakeholders in scope have been notified.

    Compares the notification log against the scope manifest to ensure
    complete notification coverage. Returns list of any missing notifications.

    Regulatory Citations:
        - GDPR Art. 13: Information to be provided where personal data are
          collected from the data subject.
        - GDPR Art. 14: Information to be provided where personal data have
          not been obtained from the data subject.
        - WARN Act (29 USC 2102): Employers must provide 60-day notice to
          employees affected by plant closings or mass layoffs.
        - SOC 2 CC2.2: The entity internally and externally communicates
          information necessary to achieve objectives.

    Args:
        options: Notification verification options.
        ctx: Request context (tenant, actor).

    Returns:
        dict with complete, manifest_id, notified_count, required_count, missing.
    """
    required_targets = options.required_targets or []
    notified_targets = options.notified_targets or []

    required_set = set(required_targets)
    notified_set = set(notified_targets)

    missing = required_set - notified_set
    notified_count = len(required_set & notified_set)
    required_count = len(required_set)

    return {
        "complete": len(missing) == 0,
        "manifest_id": options.manifest_id,
        "notified_count": notified_count,
        "required_count": required_count,
        "missing": tuple(sorted(missing)),
    }
