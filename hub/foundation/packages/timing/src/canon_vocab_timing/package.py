"""Timing vocabulary package metadata."""

from canon.hub.package import VocabularyPackage

TIMING = VocabularyPackage(
    name="timing",
    description="Timing gates, business day computation, notice delivery, waiting period management, SLA verification, and timing constraint queries.",
    feature_names=frozenset(
        {
            # Gates
            "require_deadline_not_passed",
            "require_minimum_elapsed",
            # Waiting Period
            "check_waiting_period_elapsed",
            "get_waiting_period",
            "pause_waiting_period",
            "resume_waiting_period",
            # Notice
            "get_acknowledgment",
            "get_delivery_attempts",
            "get_notice",
            # Verification
            "verify_notice_delivered",
            "verify_sla_met",
            # Computation
            "compute_business_days",
            # Query
            "get_timing_constraints",
        }
    ),
    schema_names=frozenset(
        {
            "AcknowledgmentMethod",
            "ConstraintType",
            "DeliveryStatus",
            "Jurisdiction",
            "NoticeChannel",
            "NoticeDeliveryStatus",
            "NoticeType",
            "SlaType",
            "WaitingPeriodState",
        }
    ),
    regulatory_basis=(
        "FCRA \u00a7 1681b(b)(3)",
        "FCRA \u00a7 1681i",
        "FCRA \u00a7 1681m",
        "WARN Act",
        "NYC LL144",
        "GDPR Art. 12",
        "GDPR Art. 33",
        "SOC 2 CC7.4",
    ),
    version="2026.01",
    domain_module="canon_vocab_timing",
)
