"""Notice service - formal compliance notices.

FCRA requires:
1. Pre-adverse action notice (before decision is final)
2. Waiting period (typically 5 business days)
3. Adverse action notice (if decision stands)

Each notice, waiting period state change, and delivery attempt is tracked
as Evidence with ChainEntry for litigation-grade proof.

CRITICAL: This is FCRA compliance - EVERY operation uses emit_chained_evidence().
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, ClassVar

from canon.entities.consent import ConsentScope
from canon.service import BaseService, ResponseModel
from canon.types import Evidence
from kron.utils import now_utc

from .models import (
    CheckWaitingOptions,
    CreateAdverseOptions,
    CreateNoticeOptions,
    CreatePreAdverseOptions,
    DeliveryAttempt,
    DeliveryStatus,
    GetDeliveriesOptions,
    GetNoticeOptions,
    GetWaitingOptions,
    NoticePayload,
    NoticeRequest,
    NoticeType,
    PauseWaitingOptions,
    RecordAcknowledgmentOptions,
    RecordDeliveryOptions,
    ResumeWaitingOptions,
    WaitingPeriod,
)

if TYPE_CHECKING:
    from uuid import UUID

# Jurisdiction waiting periods (business days)
WAITING_PERIODS = {
    "federal": 5,
    "ca": 7,
    "nyc": 5,
    "default": 5,
}

# Evidence types for notice service
EVIDENCE_TYPE_NOTICE = "notice"
EVIDENCE_TYPE_WAITING = "notice.waiting_period"
EVIDENCE_TYPE_DELIVERY = "notice.delivery"
EVIDENCE_TYPE_ACKNOWLEDGMENT = "notice.acknowledgment"


class NoticeService(BaseService[NoticeRequest]):
    """Service for managing formal compliance notices.

    Handles pre-adverse and adverse action notices with
    delivery tracking and waiting period management.

    All operations are persisted to Evidence with ChainEntry
    for FCRA compliance audit trail.
    """

    request_class: ClassVar[type[NoticeRequest]] = NoticeRequest
    _service_name: ClassVar[str] = "notice"

    # -------------------------------------------------------------------------
    # Handler: Create Pre-Adverse Notice
    # -------------------------------------------------------------------------

    async def _handle_create_pre_adverse(self, req: NoticeRequest) -> ResponseModel:
        """Create and send a pre-adverse action notice.

        Creates:
        1. Notice evidence (the actual notice record)
        2. Waiting period evidence (tracks the waiting period state)

        Returns notice_id and waiting_period in response data.

        Requires: BACKGROUND_CHECK consent for subject_id.
        """
        opts = self._options_as(req, CreatePreAdverseOptions)

        # Verify consent before proceeding (FCRA requirement)
        consent_valid = await self._verify_consent(opts.subject_id, ConsentScope.BACKGROUND_CHECK)
        if not consent_valid:
            return ResponseModel.fail(
                "BACKGROUND_CHECK consent required for pre-adverse notice",
                data={"required_scope": ConsentScope.BACKGROUND_CHECK.value},
            )
        now = now_utc()

        # Calculate waiting period
        days = WAITING_PERIODS.get(opts.jurisdiction.lower(), WAITING_PERIODS["default"])
        ends_at = now + timedelta(days=days)

        payload = NoticePayload(
            notice_type=NoticeType.PRE_ADVERSE_ACTION,
            jurisdiction=opts.jurisdiction,
            template_version=opts.template_version,
            delivery_method=opts.delivery_method,
            delivery_address=opts.delivery_address,
            sent_at=now.isoformat(),
            delivery_status=DeliveryStatus.SENT,
            content_hash=opts.content_hash,
        )

        # Create notice evidence with chain entry
        notice_evidence = await self.emit_chained_evidence(
            operation="create_pre_adverse",
            data=payload.model_dump(mode="json"),
            subject_id=opts.subject_id,
            title=f"Pre-Adverse Action Notice - {opts.jurisdiction}",
            collected_by_id=opts.collected_by_id,  # type: ignore[arg-type]
            evidence_type=EVIDENCE_TYPE_NOTICE,
        )

        # Create waiting period record
        waiting = WaitingPeriod(
            notice_id=notice_evidence.id,
            started_at=now.isoformat(),
            required_days=days,
            jurisdiction=opts.jurisdiction,
            ends_at=ends_at.isoformat(),
            elapsed=False,
        )

        # Store waiting period as separate evidence (for independent queries)
        await self.emit_chained_evidence(
            operation="waiting_period_started",
            data=waiting.model_dump(mode="json"),
            subject_id=opts.subject_id,
            title=f"Waiting Period Started - {opts.jurisdiction} ({days} days)",
            evidence_type=EVIDENCE_TYPE_WAITING,
        )

        return ResponseModel.ok(
            {
                "notice_id": str(notice_evidence.id),
                "waiting_period": waiting.model_dump(mode="json"),
            }
        )

    # -------------------------------------------------------------------------
    # Handler: Create Adverse Notice
    # -------------------------------------------------------------------------

    async def _handle_create_adverse(self, req: NoticeRequest) -> ResponseModel:
        """Create and send an adverse action notice.

        Verifies waiting period has elapsed before proceeding.

        Requires: BACKGROUND_CHECK consent for subject_id.
        """
        opts = self._options_as(req, CreateAdverseOptions)

        # Verify consent before proceeding (FCRA requirement)
        consent_valid = await self._verify_consent(opts.subject_id, ConsentScope.BACKGROUND_CHECK)
        if not consent_valid:
            return ResponseModel.fail(
                "BACKGROUND_CHECK consent required for adverse notice",
                data={"required_scope": ConsentScope.BACKGROUND_CHECK.value},
            )

        # Verify waiting period has elapsed
        waiting = await self._get_waiting_period(opts.pre_adverse_notice_id)
        if waiting and not waiting.elapsed:
            now_str = now_utc().isoformat()
            if waiting.ends_at > now_str:
                return ResponseModel.fail(
                    f"Waiting period has not elapsed. Ends at: {waiting.ends_at}",
                    data={"ends_at": waiting.ends_at},
                )

        now = now_utc()
        payload = NoticePayload(
            notice_type=NoticeType.ADVERSE_ACTION,
            jurisdiction=opts.jurisdiction,
            template_version=opts.template_version,
            delivery_method=opts.delivery_method,
            delivery_address=opts.delivery_address,
            sent_at=now.isoformat(),
            delivery_status=DeliveryStatus.SENT,
            content_hash=opts.content_hash,
        )

        # Create notice evidence with chain entry
        notice_evidence = await self.emit_chained_evidence(
            operation="create_adverse",
            data={
                **payload.model_dump(mode="json"),
                "pre_adverse_notice_id": str(opts.pre_adverse_notice_id),
            },
            subject_id=opts.subject_id,
            title=f"Adverse Action Notice - {opts.jurisdiction}",
            collected_by_id=opts.collected_by_id,  # type: ignore[arg-type]
            evidence_type=EVIDENCE_TYPE_NOTICE,
        )

        return ResponseModel.ok(
            {
                "notice_id": str(notice_evidence.id),
            }
        )

    # -------------------------------------------------------------------------
    # Handler: Check Waiting Period
    # -------------------------------------------------------------------------

    async def _handle_check_waiting(self, req: NoticeRequest) -> ResponseModel:
        """Check and update waiting period status.

        Automatically marks as elapsed if time has passed.
        """
        opts = self._options_as(req, CheckWaitingOptions)

        waiting = await self._get_waiting_period(opts.notice_id)
        if not waiting:
            return ResponseModel.fail(f"Waiting period not found for notice: {opts.notice_id}")

        now_str = now_utc().isoformat()
        needs_update = False

        # Check if elapsed (time passed and not paused)
        if not waiting.elapsed and waiting.ends_at <= now_str and not waiting.paused_at:
            waiting.elapsed = True
            needs_update = True

        if needs_update:
            # Record the elapsed state change
            await self.emit_chained_evidence(
                operation="waiting_period_elapsed",
                data=waiting.model_dump(mode="json"),
                title=f"Waiting Period Elapsed - {waiting.jurisdiction}",
                evidence_type=EVIDENCE_TYPE_WAITING,
            )

        return ResponseModel.ok(
            {
                "waiting_period": waiting.model_dump(mode="json"),
            }
        )

    # -------------------------------------------------------------------------
    # Handler: Pause Waiting Period
    # -------------------------------------------------------------------------

    async def _handle_pause_waiting(self, req: NoticeRequest) -> ResponseModel:
        """Pause the waiting period (e.g., dispute filed)."""
        opts = self._options_as(req, PauseWaitingOptions)

        waiting = await self._get_waiting_period(opts.notice_id)
        if not waiting:
            return ResponseModel.fail(f"Waiting period not found for notice: {opts.notice_id}")

        if waiting.elapsed:
            return ResponseModel.fail("Cannot pause an elapsed waiting period")

        if waiting.paused_at:
            return ResponseModel.fail("Waiting period is already paused")

        waiting.paused_at = now_utc().isoformat()
        waiting.paused_reason = opts.reason

        # Record the pause
        await self.emit_chained_evidence(
            operation="waiting_period_paused",
            data=waiting.model_dump(mode="json"),
            title=f"Waiting Period Paused - {opts.reason}",
            evidence_type=EVIDENCE_TYPE_WAITING,
        )

        return ResponseModel.ok(
            {
                "waiting_period": waiting.model_dump(mode="json"),
            }
        )

    # -------------------------------------------------------------------------
    # Handler: Resume Waiting Period
    # -------------------------------------------------------------------------

    async def _handle_resume_waiting(self, req: NoticeRequest) -> ResponseModel:
        """Resume a paused waiting period."""
        opts = self._options_as(req, ResumeWaitingOptions)

        waiting = await self._get_waiting_period(opts.notice_id)
        if not waiting:
            return ResponseModel.fail(f"Waiting period not found for notice: {opts.notice_id}")

        if not waiting.paused_at:
            return ResponseModel.fail("Waiting period is not paused")

        now = now_utc()
        waiting.resumed_at = now.isoformat()

        # Extend ends_at by the pause duration
        paused_at = datetime.fromisoformat(waiting.paused_at)
        pause_duration = now - paused_at
        original_end = datetime.fromisoformat(waiting.ends_at)
        new_end = original_end + pause_duration
        waiting.ends_at = new_end.isoformat()

        # Clear pause state
        old_paused_at = waiting.paused_at
        old_reason = waiting.paused_reason
        waiting.paused_at = None
        waiting.paused_reason = None

        # Record the resume
        await self.emit_chained_evidence(
            operation="waiting_period_resumed",
            data={
                **waiting.model_dump(mode="json"),
                "pause_duration_seconds": pause_duration.total_seconds(),
                "previous_paused_at": old_paused_at,
                "previous_paused_reason": old_reason,
            },
            title=f"Waiting Period Resumed - extended to {waiting.ends_at}",
            evidence_type=EVIDENCE_TYPE_WAITING,
        )

        return ResponseModel.ok(
            {
                "waiting_period": waiting.model_dump(mode="json"),
            }
        )

    # -------------------------------------------------------------------------
    # Handler: Record Delivery
    # -------------------------------------------------------------------------

    async def _handle_record_delivery(self, req: NoticeRequest) -> ResponseModel:
        """Record a delivery attempt."""
        opts = self._options_as(req, RecordDeliveryOptions)

        attempt = DeliveryAttempt(
            attempted_at=now_utc().isoformat(),
            method=opts.delivery_method,
            address=opts.delivery_address,
            status=opts.status,
            error_message=opts.error_message,
            provider_response=opts.provider_response,
        )

        # Record delivery attempt
        await self.emit_chained_evidence(
            operation="delivery_recorded",
            data={
                "notice_id": str(opts.notice_id),
                **attempt.model_dump(mode="json"),
            },
            title=f"Delivery Attempt - {opts.status.value}",
            evidence_type=EVIDENCE_TYPE_DELIVERY,
        )

        return ResponseModel.ok(
            {
                "delivery_attempt": attempt.model_dump(mode="json"),
            }
        )

    # -------------------------------------------------------------------------
    # Handler: Get Waiting Period
    # -------------------------------------------------------------------------

    async def _handle_get_waiting(self, req: NoticeRequest) -> ResponseModel:
        """Get waiting period for a notice."""
        opts = self._options_as(req, GetWaitingOptions)

        waiting = await self._get_waiting_period(opts.notice_id)
        if not waiting:
            return ResponseModel.fail(f"Waiting period not found for notice: {opts.notice_id}")

        return ResponseModel.ok(
            {
                "waiting_period": waiting.model_dump(mode="json"),
            }
        )

    # -------------------------------------------------------------------------
    # Handler: Get Deliveries
    # -------------------------------------------------------------------------

    async def _handle_get_deliveries(self, req: NoticeRequest) -> ResponseModel:
        """Get delivery attempts for a notice."""
        opts = self._options_as(req, GetDeliveriesOptions)

        attempts = await self._get_delivery_attempts(opts.notice_id)

        return ResponseModel.ok(
            {
                "delivery_attempts": [a.model_dump(mode="json") for a in attempts],
            }
        )

    # -------------------------------------------------------------------------
    # Handler: Create Generic Notice (PIP, Policy, etc.)
    # -------------------------------------------------------------------------

    async def _handle_create(self, req: NoticeRequest) -> ResponseModel:
        """Create a generic notice (PIP specification, policy update, etc.).

        Unlike FCRA notices, generic notices don't automatically create
        waiting periods. They track delivery and acknowledgment.
        """
        opts = self._options_as(req, CreateNoticeOptions)
        now = now_utc()

        payload = NoticePayload(
            notice_type=opts.notice_type,
            jurisdiction=opts.jurisdiction or "federal",
            template_version=opts.template_version or "1.0",
            delivery_method=opts.delivery_method,
            delivery_address=opts.delivery_address,
            sent_at=now.isoformat(),
            delivery_status=DeliveryStatus.SENT,
            content_hash=opts.content_hash,
        )

        # Build notice data with optional fields
        notice_data = payload.model_dump(mode="json")
        if opts.case_id:
            notice_data["case_id"] = str(opts.case_id)
        if opts.title:
            notice_data["title"] = opts.title
        if opts.summary:
            notice_data["summary"] = opts.summary
        if opts.payload:
            notice_data["payload"] = opts.payload

        # Create notice evidence with chain entry
        notice_evidence = await self.emit_chained_evidence(
            operation="create_notice",
            data=notice_data,
            subject_id=opts.subject_id,
            title=opts.title or f"{opts.notice_type.value} Notice",
            collected_by_id=opts.collected_by_id,  # type: ignore[arg-type]
            evidence_type=EVIDENCE_TYPE_NOTICE,
        )

        return ResponseModel.ok(
            {
                "notice_id": str(notice_evidence.id),
                "notice_type": opts.notice_type.value,
            }
        )

    # -------------------------------------------------------------------------
    # Handler: Record Acknowledgment
    # -------------------------------------------------------------------------

    async def _handle_record_acknowledgment(self, req: NoticeRequest) -> ResponseModel:
        """Record employee acknowledgment of a notice.

        Used for PIP acknowledgments, policy acknowledgments, etc.
        Captures method (portal_click, email_reply, signature, in_person)
        and optional employee response.
        """
        opts = self._options_as(req, RecordAcknowledgmentOptions)
        now = now_utc()

        # Get the original notice to verify it exists and get subject_id
        notice = await self._get_notice(opts.notice_id)
        if not notice:
            return ResponseModel.fail(f"Notice not found: {opts.notice_id}")

        ack_data = {
            "notice_id": str(opts.notice_id),
            "acknowledged_at": opts.acknowledged_at or now.isoformat(),
            "acknowledgment_method": opts.acknowledgment_method,
        }
        if opts.employee_response:
            ack_data["employee_response"] = opts.employee_response

        # Extract subject_id from notice if available
        subject_id = notice.data.get("subject_id") if notice.data else None

        # Record acknowledgment as evidence
        ack_evidence = await self.emit_chained_evidence(
            operation="record_acknowledgment",
            data=ack_data,
            subject_id=subject_id,  # type: ignore[arg-type]
            title=f"Notice Acknowledged - {opts.acknowledgment_method}",
            evidence_type=EVIDENCE_TYPE_ACKNOWLEDGMENT,
        )

        return ResponseModel.ok(
            {
                "acknowledgment_id": str(ack_evidence.id),
                "notice_id": str(opts.notice_id),
                "acknowledged_at": ack_data["acknowledged_at"],
            }
        )

    # -------------------------------------------------------------------------
    # Handler: Get Notice
    # -------------------------------------------------------------------------

    async def _handle_get(self, req: NoticeRequest) -> ResponseModel:
        """Get a notice by ID."""
        opts = self._options_as(req, GetNoticeOptions)

        notice = await self._get_notice(opts.notice_id)
        if not notice:
            return ResponseModel.fail(f"Notice not found: {opts.notice_id}")

        # Also fetch any acknowledgments
        ack = await self._get_acknowledgment(opts.notice_id)

        return ResponseModel.ok(
            {
                "notice_id": str(notice.id),
                "notice": notice.data,
                "acknowledgment": ack,
            }
        )

    # -------------------------------------------------------------------------
    # Private Helpers - Evidence Queries
    # -------------------------------------------------------------------------

    async def _get_waiting_period(self, notice_id: UUID) -> WaitingPeriod | None:
        """Get the latest waiting period state for a notice from Evidence.

        Queries waiting period evidence records and returns the most recent state.
        """
        records = await Evidence.select(
            where={
                "tenant_id": str(self.tenant_id),
                "evidence_type": EVIDENCE_TYPE_WAITING,
            },
            order_by=[("collected_at", "desc")],
        )

        # Find records that reference this notice_id
        for record in records:
            if not record.data:
                continue
            if str(record.data.get("notice_id")) == str(notice_id):
                return WaitingPeriod.model_validate(record.data)

        return None

    async def _get_delivery_attempts(self, notice_id: UUID) -> list[DeliveryAttempt]:
        """Get all delivery attempts for a notice from Evidence."""
        records = await Evidence.select(
            where={
                "tenant_id": str(self.tenant_id),
                "evidence_type": EVIDENCE_TYPE_DELIVERY,
            },
            order_by=[("collected_at", "asc")],
        )

        attempts = []
        for record in records:
            if not record.data:
                continue
            if str(record.data.get("notice_id")) == str(notice_id):
                # Extract delivery attempt data (excluding notice_id)
                attempt_data = {k: v for k, v in record.data.items() if k != "notice_id"}
                attempts.append(DeliveryAttempt.model_validate(attempt_data))

        return attempts

    async def _get_notice(self, notice_id: UUID) -> Evidence | None:
        """Get a notice by ID from Evidence."""
        records = await Evidence.select(
            where={
                "id": str(notice_id),
                "tenant_id": str(self.tenant_id),
                "evidence_type": EVIDENCE_TYPE_NOTICE,
            },
        )
        return records[0] if records else None

    async def _get_acknowledgment(self, notice_id: UUID) -> dict | None:
        """Get acknowledgment for a notice from Evidence."""
        records = await Evidence.select(
            where={
                "tenant_id": str(self.tenant_id),
                "evidence_type": EVIDENCE_TYPE_ACKNOWLEDGMENT,
            },
        )

        # Find record that references this notice_id
        for record in records:
            if not record.data:
                continue
            if str(record.data.get("notice_id")) == str(notice_id):
                return record.data

        return None

    async def _verify_consent(self, subject_id: UUID, scope: ConsentScope) -> bool:
        """Verify consent exists for a subject and scope.

        Uses ConsentToken to check for valid, non-revoked consent.
        This is a hot-path check - no evidence emission.

        Args:
            subject_id: The person whose consent is being checked
            scope: The consent scope required (e.g., BACKGROUND_CHECK)

        Returns:
            True if valid consent exists, False otherwise
        """
        from canon.types import ConsentToken

        tokens = await ConsentToken.select(
            where={
                "tenant_id": str(self.tenant_id),
                "person_id": str(subject_id),
                "scope": scope.value,
                "revoked_at": None,  # Not revoked
            }
        )

        if not tokens:
            return False

        # Check if any token is still valid (not expired)
        now_str = now_utc().isoformat()
        return any(token.expires_at is None or token.expires_at > now_str for token in tokens)


# Service Factory


def get_notice_service(tenant_id: UUID) -> NoticeService:
    """Get notice service instance for a tenant.

    Unlike the old singleton pattern, each service instance is tenant-scoped.
    """
    return NoticeService(tenant_id)
